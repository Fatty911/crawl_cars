#!/usr/bin/env python3
"""红线通道覆盖断言：Actions 里 state=active 的数据链，必须逐条出现在监视名单里。

为什么要有这条：GitHub 侧唯一的"红→修复"监视器原来监听四条**已停用**的链
（三条爬虫 + CI），而在跑的三条旁路链一条都没覆盖 ⇒ 旁路链红了没有任何东西接住它。
这里把"覆盖"变成每次旁路构建都实查的闸，而不是文档里的承诺。

判据（全部 fail-closed）：
1. 从 Actions API 读 state=active 的链（`AI Auto Fix Monitor` 自己除外）；
   读不到 / 读到的 active 少于 3 条 ⇒ 退出 2（第三态：不是红也不是过）。
2. 监视名单必须与 active 集合**完全相等**：
   少一条 ⇒ 红（被监视漏掉）；多一条（含已停用/不存在的链名）⇒ 红（凑数式覆盖）。
3. 监视器**自己**必须存在、身份唯一且 state=active：五条链 active 不证明有一个在跑的监视器。
   缺失 / 重复（身份不唯一）/ 未知状态 / state 不可读 ⇒ 拒绝放行（fail closed）；active 读数不足且名单无缺漏时仍保留既有第三态。
4. 监视器的 `if:` 只许 failure 触发（出现 success 即红），且修复腿必须是"开 Issue/归档证据"
   形状（必须含 `gh issue create`，不许出现付费模型 Action）。

本地复算用 `--states-json` 喂夹具，不碰网络；CI 里用 GITHUB_TOKEN 实查。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
MONITOR = ROOT / ".github/workflows/AI_Auto_Fix_Monitor.yml"
SELF_NAME = "AI Auto Fix Monitor"
MIN_ACTIVE = 3


class UnreadableState(RuntimeError):
    """读到的 active 集合可疑（少于地板值）⇒ 第三态，不是红也不是过。"""


def load_states(path: str | None, repo: str) -> list[dict]:
    if path:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
        if not token:
            raise RuntimeError("没有 GITHUB_TOKEN/GH_TOKEN ⇒ 不能实查 active 链")
        req = urllib.request.Request(
            "https://api.github.com/repos/%s/actions/workflows?per_page=100" % repo,
            headers={"Authorization": "Bearer " + token,
                     "Accept": "application/vnd.github+json",
                     "User-Agent": "red-channel-coverage"},
        )
        import ssl
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
            data = json.loads(r.read().decode("utf-8"))
    if isinstance(data, dict):
        data = data.get("workflows")
    if not isinstance(data, list):
        raise RuntimeError("workflows 接口返回的不是列表 ⇒ 读不到状态")
    return [w for w in data if isinstance(w, dict)]


def check(monitor_path: pathlib.Path, states: list[dict]) -> tuple[list[str], set[str], set[str]]:
    errors: list[str] = []
    text = monitor_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    on = data.get(True) if isinstance(data.get(True), dict) else data.get("on")
    wf_run = (on or {}).get("workflow_run") or {}
    monitored = set(wf_run.get("workflows") or [])
    if not monitored:
        errors.append("监视名单为空 ⇒ 通道不存在")

    # 监视器**自身**必须存在、身份唯一且 state=active。五条链 active 只证明被监视的链在跑，
    # 不证明有一个在跑的监视器——历史缺陷就是这里：self 被剔出 active 集合后再没人看它的状态，
    # 于是 `AI Auto Fix Monitor` 自身 disabled_manually 时全表照样绿。缺失/重复/未知/不可读
    # 一律拒绝放行（fail closed）；保留既有读数不足第三态，也不许挑一条"看起来绿"的来放行。
    self_entries = [w for w in states if str(w.get("name")) == SELF_NAME]
    if not self_entries:
        errors.append("监视器自身 `%s` 不在状态读数里 ⇒ 无法证明它在跑，红链没有执行者" % SELF_NAME)
    elif len(self_entries) > 1:
        errors.append("监视器身份不唯一：状态读数里 `%s` 出现 %d 次（state=%s）⇒ 不能挑一条放行"
                      % (SELF_NAME, len(self_entries),
                         [repr(w.get("state")) for w in self_entries]))
    else:
        self_state = self_entries[0].get("state")
        if not isinstance(self_state, str) or not self_state:
            errors.append("监视器自身 `%s` 的 state 不可读（%r）⇒ 读不懂就不能判绿"
                          % (SELF_NAME, self_state))
        elif self_state != "active":
            errors.append("监视器自身 `%s` state=%s ⇒ 它已被停用，红链没有执行者"
                          % (SELF_NAME, self_state))

    active = {str(w.get("name")) for w in states
              if str(w.get("state")) == "active" and str(w.get("name")) != SELF_NAME}
    # **先算名单差，再判"读数可疑"**：真有人停用了一条链时，名单会比 active 多一项 ⇒
    # 这是覆盖红(1)，不能被下面的第三态(2)吞掉。只有名单与 active 完全一致、而 active 仍低于
    # 地板值时，才说明是 API 读数退化/权限读不全 ⇒ 第三态。
    missing = sorted(active - monitored)
    extra = sorted(monitored - active)
    if missing:
        errors.append("active 链没有被监视：%s" % missing)
    if extra:
        errors.append("监视名单里有非 active 的链（停用/不存在，属凑数覆盖）：%s" % extra)
    if len(active) < MIN_ACTIVE and not missing and not extra:
        raise UnreadableState("active 数据链只有 %d 条（< %d），且名单与读到的 active 完全一致 ⇒ 状态读数可疑"
                              % (len(active), MIN_ACTIVE))

    jobs = data.get("jobs") or {}
    ifs = " ".join(str(j.get("if") or "") for j in jobs.values() if isinstance(j, dict))
    if "failure" not in ifs:
        errors.append("job if 里没有 failure 条件 ⇒ 红了也不触发")
    if "success" in ifs:
        errors.append("job if 里仍有 success 条件 ⇒ 绿的一轮也会被拉起（过度触发）")
    if "gh issue create" not in text:
        errors.append("没有 `gh issue create` ⇒ 红的证据不会落成 Issue，通道仍是断的")
    if "openai/codex-action" in text or "OPENAI_API_KEY" in text:
        errors.append("修复腿仍在调用付费模型 Action ⇒ 与本单口径冲突（只归档证据）")
    return errors, active, monitored


def main() -> int:
    # Windows 控制台默认 cp936：错误文案里有 `⇒`，不重配 stdout 会在**打印第三态时**崩成 rc=1
    # （实测：本机 degraded 分支 UnicodeEncodeError ⇒ 2 被降级成 1，第三态与红混在一起）。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--monitor", default=str(MONITOR))
    ap.add_argument("--states-json", default="", help="本地夹具：{\"workflows\":[{name,state}...]}")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "Fatty911/crawl_cars"))
    a = ap.parse_args()
    try:
        states = load_states(a.states_json, a.repo)
    except Exception as e:
        print("COVERAGE_UNREADABLE %r" % (e,))
        return 2
    try:
        errors, active, monitored = check(pathlib.Path(a.monitor), states)
    except UnreadableState as e:
        print("COVERAGE_UNREADABLE %s" % e)
        return 2
    except Exception as e:
        print("COVERAGE_UNREADABLE monitor=%r" % (e,))
        return 2
    if errors:
        print("COVERAGE_FAIL active=%d monitored=%d" % (len(active), len(monitored)))
        for e in errors:
            print("- " + e)
        return 1
    print("COVERAGE_OK active=%d monitored=%d" % (len(active), len(monitored)))
    for name in sorted(active):
        print("  covered: " + name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
