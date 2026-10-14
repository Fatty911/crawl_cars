"""回推段的 rebase 必须能在**脏工作树**上成活（判据，main 上必须红）。

**这不是假想的坑，是刚发生的事**（监工 10-14 从轮次 `cnb-pvn-1k4sonk5m` 的日志里取到的原文）：

```
error: cannot rebase: You have unstaged changes.
error: Please commit or stash them.
[pushback] rebase 第 1 次没成，10s 后重试
[pushback] rebase 第 2 次没成，10s 后重试
PUSHBACK-FAIL reason=rebase-exhausted attempts=3
 ! [rejected]        HEAD -> main (non-fast-forward)
```

⇒ #69 加的"push 前有界 fetch+rebase"确实上场了，但**它自己被脏树挡死**：
白名单只 `git add` 了 `data/*` 与 `crawl_state` 等几处，段内其它阶段（发布/验收）写出来的文件
仍是 unstaged ⇒ `git rebase FETCH_HEAD` 直接拒绝 ⇒ 三次用尽 ⇒ 推送被拒 ⇒ **整轮爬取数据作废**。
这正是"易车覆盖倒退"三条成因里的第一条（回推被上游/自身失败连带跳过）换了个触发点重演。

判据钉四件事（都可结构判定；两份链拷贝各查一遍，只改一份 = 半修）：
1. 每个 `回推*` 段里那条 rebase 必须是**脏树可成活**的形状：
   `git rebase --autostash`（含 `pull --rebase --autostash`），
   或显式 `git stash push --include-untracked` + rebase + `git stash pop`；
2. **两份拷贝都要有**：脏树可成活的 rebase 出现次数 ≥ `回推*` 段个数（防"只改一处"）；
3. rebase 那一段**不许被 `|| true` 吃掉**（真失败必须走到 `PUSHBACK-FAIL reason=` 那条点名分支）；
4. 仍然必须保留 `fetch` + rebase 到 `FETCH_HEAD`/`origin/main` 的语义与 `PUSHBACK-FAIL reason=` 读数
   （不许用"把 rebase 删掉"或"push 加 --force"来凑绿 —— 那是把问题解决成掩盖问题）。

红样自校（`--selftest`）：把 `--autostash` 摘掉 / 只给一份拷贝 / 给 rebase 加 `|| true` /
改成 `push --force` —— 四种变异都必须干净变红；合规样张必须绿。
"""

from __future__ import annotations

import argparse
import copy
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = ROOT / ".cnb.yml"

AUTOSTASH_RE = re.compile(r"git\s+(?:-[^\s]+\s+)*rebase\b[^\n|;&]*--autostash|"
                          r"git\s+(?:-[^\s]+\s+)*pull\s+--rebase[^\n|;&]*--autostash")
STASH_PUSH_RE = re.compile(r"git\s+stash\s+push\b[^\n]*(?:-u|--include-untracked)")
STASH_POP_RE = re.compile(r"git\s+stash\s+pop\b")
REBASE_RE = re.compile(r"git\s+(?:-[^\s]+\s+)*rebase\b")
FETCH_RE = re.compile(r"git\s+fetch\b")
REASON_RE = re.compile(r"PUSHBACK-FAIL\s+reason=")
FORCE_PUSH_RE = re.compile(r"git\s+push\b[^\n]*(?:--force(?!-with-lease)|-f\b)")


def load(path=CFG):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def jobs_of(cfg):
    out = []
    for section, prefix in (("main", ""), ("$", "$: ")):
        node = cfg.get(section) or {}
        if not isinstance(node, dict):
            continue
        for event, jobs in node.items():
            for job in (jobs if isinstance(jobs, list) else [jobs]):
                if isinstance(job, dict):
                    out.append(("%s%s" % (prefix, event), job))
    return out


def pushback_stages(job):
    found = []
    for bucket in ("stages", "failStages"):
        for s in job.get(bucket) or []:
            if isinstance(s, dict) and "回推" in str(s.get("name") or ""):
                found.append(s)
    return found


def body_of(stage):
    return str(stage.get("script") or "") + "\n" + str(stage.get("steps") or "")


def check_stage(body):
    """单段是否满足：脏树可成活 + 保留 fetch/rebase 语义 + 点名失败 + 不靠 force-push。"""
    problems = []
    if not REBASE_RE.search(body):
        problems.append("没有 rebase")
    if not FETCH_RE.search(body):
        problems.append("没有 fetch")
    autostash = bool(AUTOSTASH_RE.search(body))
    stash_round = bool(STASH_PUSH_RE.search(body) and STASH_POP_RE.search(body))
    if REBASE_RE.search(body) and not (autostash or stash_round):
        problems.append("rebase 不是脏树可成活形状（缺 --autostash，也没有 stash push -u + stash pop）")
    for line in body.splitlines():
        if REBASE_RE.search(line) and re.search(r"\|\|\s*true", line):
            problems.append("rebase 那行被 || true 吃掉")
            break
    if not REASON_RE.search(body):
        problems.append("失败没有 PUSHBACK-FAIL reason= 点名")
    if FORCE_PUSH_RE.search(body):
        problems.append("用 push --force 掩盖 non-fast-forward（越权：会把别人的提交抹掉）")
    return problems


def check(cfg):
    bad = []
    total_stages = 0
    dirty_safe = 0
    for event, job in jobs_of(cfg):
        stages = pushback_stages(job)
        for stage in stages:
            total_stages += 1
            problems = check_stage(body_of(stage))
            if problems:
                bad.append("%s/%s：%s" % (event, stage.get("name"), "；".join(problems)))
            else:
                dirty_safe += 1
        if not stages:
            continue
    if total_stages and dirty_safe < total_stages:
        bad.append("半修风险：回推段共 %d 处，脏树可成活只有 %d 处" % (total_stages, dirty_safe))
    if not total_stages:
        bad.append("一条回推段都没认到 ⇒ 读数无效，不许判过")
    return bad


def sample(autostash=True, half=False, mask=False, force=False):
    """合规样张：两条链各一份回推段，都带 --autostash。
    half=True ⇒ 只有第一条带（模拟"两份拷贝只改一份"的半修）；
    mask=True ⇒ rebase 被 || true 吃掉；force=True ⇒ 改用 push --force。"""
    def block(second=False):
        use_autostash = autostash and not (half and second)
        rebase = "git rebase -q%s FETCH_HEAD" % (" --autostash" if use_autostash else "")
        if mask:
            rebase = rebase + " || true"
        push = 'git push%s "$PB_REMOTE" HEAD:main' % (" --force" if force else "")
        return ("set -e\n"
                "PB_REMOTE=https://cnb.example/repo.git\n"
                "n=0\n"
                "git add -f crawl_state || true\n"
                "until git fetch -q \"$PB_REMOTE\" main && %s; do\n"
                "  n=$((n+1)); [ $n -ge 3 ] && { echo \"PUSHBACK-FAIL reason=rebase-exhausted attempts=$n\"; exit 1; }\n"
                "  sleep 10\n"
                "done\n"
                "GIT_ASKPASS=/tmp/x.sh %s\n" % (rebase, push))

    return {"main": {
        "api_trigger": [{"name": "轮次", "stages": [
            {"name": "回推增量状态", "timeout": "1h", "script": block()}]}],
        "crontab: 5 8 1,16 * *": [{"name": "轮次2", "stages": [
            {"name": "回推增量状态", "timeout": "1h", "script": block(second=True)}]}]}}


def selftest() -> int:
    cases = []
    cases.append(("合规样张判绿", not check(sample()), check(sample())[:2]))
    cases.append(("缺 --autostash 判红", bool(check(sample(autostash=False))), []))
    cases.append(("只改一份拷贝判红", bool(check(sample(half=True))), []))
    cases.append(("rebase 被 || true 判红", bool(check(sample(mask=True))), []))
    cases.append(("用 push --force 判红", bool(check(sample(force=True))), []))
    fails = 0
    for name, want, extra in cases:
        fails += 0 if want else 1
        print("  自校 %-24s ⇒ %s%s" % (name, "OK" if want else "错",
                                       (" " + str(extra)) if extra and not want else ""))
    print("SELFTEST %s" % ("通过（双向都能判对）" if not fails else "失败 %d 例" % fails))
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    bad = check(load())
    if bad:
        print("回推 rebase 挡不住脏工作树：%d 处" % len(bad))
        for b in bad:
            print("  ✗ " + b)
        return 1
    print("回推 rebase 在脏工作树上可成活（两份拷贝都是），且失败仍点名、不靠 force-push")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ---------------- 尾部补齐：样张从两处补到三处 ----------------
# 既有 189 行一字未改。原 sample() 只造 api_trigger / 半月 crontab 两处回推段，而现网是三处
# （另有周报价链 `回推报价数据`）；派发单要求 `test_dirty_tree_recognizes_three_sites` 断言样张
# 认到三处、且既可跳过两处样张、又不许改既有行 ⇒ 只能在尾部把第三处补上（原实现保留为 _sample_two_sites）。
_sample_two_sites = sample


def sample(autostash=True, half=False, mask=False, force=False):
    """三处回推段样张：既有两处 + 尾部补的周报价链一处（语义与既有两处一致）。"""
    def block(third=False):
        use_autostash = autostash and not (half and third)
        rebase = "git rebase -q%s FETCH_HEAD" % (" --autostash" if use_autostash else "")
        if mask:
            rebase = rebase + " || true"
        push = 'git push%s "$PB_REMOTE" HEAD:main' % (" --force" if force else "")
        return ("set -e\n"
                "PB_REMOTE=https://cnb.example/repo.git\n"
                "n=0\n"
                "git add -f crawl_state || true\n"
                "until git fetch -q \"$PB_REMOTE\" main && %s; do\n"
                "  n=$((n+1)); [ $n -ge 3 ] && { echo \"PUSHBACK-FAIL reason=rebase-exhausted attempts=$n\"; exit 1; }\n"
                "  sleep 10\n"
                "done\n"
                "GIT_ASKPASS=/tmp/x.sh %s\n" % (rebase, push))

    cfg = _sample_two_sites(autostash=autostash, half=half, mask=mask, force=force)
    cfg["$"] = {"crontab: 37 8 * * 0": [{"name": "轮次3", "stages": [
        {"name": "回推报价数据", "timeout": "1h", "script": block(third=True)}]}]}
    return cfg


def test_dirty_tree_recognizes_three_sites():
    assert sum(len(pushback_stages(j)) for _e, j in jobs_of(sample())) == 3


def test_dirty_tree_selftest_bidirectional():
    assert selftest() == 0


def test_dirty_tree_repo_sites_all_dirty_safe():
    problems = check(load())
    assert not problems, "\n".join(problems)
