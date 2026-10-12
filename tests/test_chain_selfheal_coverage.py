"""自愈覆盖面：按 **YAML 实际键名** 枚举所有触发器链，要求每条链都有 `failStages`。

这是 Issue #14 判据里 `test_every_chain_can_trigger_repair_on_error` 的**修正版**。
原版的缺陷（监工自己造的死角，实测取证）：它枚举的是裸名 `("push","pull_request","api_trigger","crontab")`，
而 `origin/main` 的 `main:` 实际键是

    ['push', 'api_trigger', 'crontab: 5 8 1,16 * *', 'pull_request', 'crontab: 37 8 * * 0']
    顶层另有 ['$'] → '$: issue.open'

⇒ 没有裸 `crontab` 键 ⇒ 原版把 `crontab` 永远记成缺失：**补满 failStages 也不会绿**（不可满足）；
⇒ 它也没枚举 `$:` 下的链 ⇒ 派发链 `issue.open`（实测 7 次红、红了没人修）完全不在要求内。
⇒ 原版字节已下发，不改（改了会被 `check_criteria_untouched` 误判为篡改）；本文件接替它做覆盖面判定。

判据口径：
1. 链的集合从 YAML 里**读出来**（`main.*` 与 `$. *`），不写死链名；表达式型键名（`crontab: …`）按原样算一条链；
2. 每条链的 job 必须有 `failStages`（或 `fail_stages`）非空 —— 写在注释/prompt 文本里的字不算，
   所以只认解析后的 job 字典键；
3. 至少要有 5 条链被识别到（防止"解析退化成一个空集合"造成假绿：读不到就判崩，不判通过）。
"""

from __future__ import annotations

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8"))
MIN_CHAINS = 5


def _chains():
    """返回 [(链名, job dict)]；覆盖 main.* 与顶层 $.*。"""
    out = []
    for section, prefix in (("main", ""), ("$", "$: ")):
        node = (CFG or {}).get(section) or {}
        if not isinstance(node, dict):
            continue
        for key, val in node.items():
            jobs = val if isinstance(val, list) else [val]
            for i, j in enumerate(jobs):
                name = "%s%s" % (prefix, key) if len(jobs) == 1 else "%s%s[%d]" % (prefix, key, i)
                out.append((name, j if isinstance(j, dict) else None))
    return out


def test_chains_are_discovered_not_assumed() -> None:
    chains = _chains()
    assert len(chains) >= MIN_CHAINS, (
        "只从 .cnb.yml 认出 %d 条链（<%d）：解析退化或结构被改，"
        "这种读数不许当通过（宁可判崩）：%s" % (len(chains), MIN_CHAINS, [c[0] for c in chains]))
    named = " ".join(name for name, _ in chains)
    for must in ("push", "api_trigger", "crontab", "pull_request", "$: issue.open"):
        assert must in named, "链集合里找不到 %r（实际识别到：%s）" % (must, named)


def test_every_chain_has_selfheal_entry() -> None:
    missing = []
    broken = []
    for name, job in _chains():
        if job is None:
            broken.append(name)
            continue
        fs = job.get("failStages") or job.get("fail_stages")
        if not (isinstance(fs, list) and fs):
            missing.append(name)
    assert not broken, "这些触发器结构形态异常（job 不是字典）：%s" % broken
    assert not missing, (
        "这些链没有 job 级 failStages ⇒ 一红就没人修，违反『工作流报错时自动触发 NPC 修复』：%s。"
        "现状实测覆盖面 2/6，缺 push、pull_request、crontab: 37 8 * * 0、$: issue.open"
        % missing)


def test_selfheal_entry_points_at_a_repair_stage() -> None:
    """有 failStages 还不够：它必须真的指向含 npc:go 的修复阶段，否则是空壳闸门。"""
    weak = []
    for name, job in _chains():
        if not isinstance(job, dict):
            continue
        fs = job.get("failStages") or job.get("fail_stages")
        if not (isinstance(fs, list) and fs):
            continue
        stages = [s for s in fs if isinstance(s, dict)]
        has_agent = any(str(s.get("type") or "").strip().lower() == "npc:go" for s in stages)
        has_repair_name = any("修复" in str(s.get("name") or "") or "repair" in str(s.get("name") or "").lower()
                              for s in stages)
        if not (has_agent or has_repair_name):
            weak.append(name)
    assert not weak, (
        "这些链的 failStages 里没有 npc:go / 修复阶段，是空壳自愈入口：%s" % weak)
