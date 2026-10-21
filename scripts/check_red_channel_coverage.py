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
3. 监视器的 `if:` 只许 failure 触发（出现 success 即红），且修复腿必须是"开 Issue/归档证据"
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

    active = {str(w.get("name")) for w in states
              if str(w.get("state")) == "active" and str(w.get("name")) != SELF_NAME}
    if len(active) < MIN_ACTIVE:
        errors.append("读到的 active 数据链只有 %d 条（< %d）⇒ 状态读数可疑，不当成通过"
                      % (len(active), MIN_ACTIVE))
    missing = sorted(active - monitored)
    extra = sorted(monitored - active)
    if missing:
        errors.append("active 链没有被监视：%s" % missing)
    if extra:
        errors.append("监视名单里有非 active 的链（停用/不存在，属凑数覆盖）：%s" % extra)

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
