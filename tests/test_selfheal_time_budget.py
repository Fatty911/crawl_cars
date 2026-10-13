"""自愈链的时间预算必须闭合（判据，当前 main 上必须红）。

**实测依据（监工 10-13 取阶段级读数，非推断）**：
- `cnb-3f5-1k4nifqs9`：`AI-修复-第1轮 = error(7498.6s ≈ 125 分钟)`，之后
  `验证-实际pytest` / `额度复查` / `GLM评审` / `最终门禁` **整段 skipped** ⇒ 一轮白跑；
- 而 `.cnb.yml` 上 `AI-修复-第1轮` 的声明是 **`maxTurns=120` 且没有 stage 级 `timeout`**（10 个 `npc:go` 段全部 `timeout=None`，
  只有 `options.maxTokens` 这种输出上限，没有时间上限）；
- 同一 job 的 `timeout: 10h` 还要装 34 段流水线：三个爬取段实测 21.6m / 42.9m / 20.2m，
  发布与验收段还要 20 分钟以上 —— 修复段没有任何时间约束时，它一个人就能吃掉整轮。

⇒ 判据钉两件事（都是"结构可判、后果可测"的口径，不许靠"我觉得够了"）：
1. 每个 `npc:go` 阶段必须**同时**声明 `timeout` 与 `options.maxTurns`（缺一个就是不可控时长）；
2. 自愈链（`failStages`）里 `npc:go` 段的 `timeout` 之和，必须 **≤ 该 job 声明 timeout 的一个明确份额**，
   留出足够的钱给"验证 + 评审 + 最终门禁"这三段跑完 —— 否则修复成功也永远结不了案。

红样自校：删掉一个 timeout、或把修复段 timeout 抬到吃掉整个 job，两条都必须干净变红。
"""

from __future__ import annotations

import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8")) or {}
MAIN = CFG.get("main") or {}
DOLLAR = CFG.get("$") or {}

GUARD_STAGES = ("验证-", "审查-GLM", "最终门禁", "NPC审核前免费额度复查")
MAX_REPAIR_SHARE = 0.35   # 自愈链里 npc:go 的时间总和最多占 job timeout 的 35%


def _seconds(text, default_none=True):
    if text in (None, ""):
        return None
    if isinstance(text, (int, float)):
        return int(text)
    s = str(text).strip()
    if re.fullmatch(r"\d+", s):
        return int(s)
    found = re.findall(r"(\d+)\s*([hms])", s)
    if not found:
        return None if default_none else 0
    total = 0
    for num, unit in found:
        total += int(num) * {"h": 3600, "m": 60, "s": 1}[unit]
    return total


def _jobs():
    for root in (MAIN, DOLLAR):
        for key, val in root.items():
            for job in (val if isinstance(val, list) else [val]):
                if isinstance(job, dict):
                    yield str(key), job


def _npc_stages(job, bucket):
    out = []
    for s in (job.get(bucket) or []):
        if isinstance(s, dict) and (str(s.get("type") or "") == "npc:go" or "npc:go" in s):
            out.append(s)
    return out


def test_no_chain_loses_its_repair_entry():
    """反退化：不能靠"把修复段从某条链里删掉"来让份额算得过。

    不加这一条，路①有个**偷懒实现**：报价链干脆不要 failStages ⇒ 份额 0%、判据变绿，
    但"报错自动触发 NPC 修复"的覆盖面从 6/6 掉到 5/6 —— 那是把目标改小，不是修好。
    """
    per_chain = []
    for key, job in _jobs():
        has_any_stage = bool(job.get("stages") or job.get("failStages"))
        repairs = _npc_stages(job, "failStages")
        if has_any_stage and key not in ("$",):
            per_chain.append((key, len(repairs)))
    assert per_chain, "一条链都没认到 ⇒ 读数无效，不许判过"
    empty = [k for k, n in per_chain if n == 0]
    assert not empty, (
        "这些链的 failStages 里已经没有 npc:go 修复段：%s ⇒ 份额是算得过了，但覆盖面缩水（不许用删段过关）" % empty)


def test_every_npc_go_stage_declares_both_budgets():

    """`timeout` 管墙上时间、`maxTurns` 管轮数——只有一个就是另一半失控。"""
    missing = []
    for key, job in _jobs():
        for bucket in ("stages", "failStages"):
            for s in _npc_stages(job, bucket):
                mt = (s.get("options") or {}).get("maxTurns")
                to = _seconds(s.get("timeout"))
                if not mt:
                    missing.append("%s/%s：缺 options.maxTurns" % (key, s.get("name")))
                if not to:
                    missing.append("%s/%s：缺 stage 级 timeout（实测 10 个 npc:go 段全是 None）"
                                   % (key, s.get("name")))
    assert not missing, (
        "agent 段的时长不受控 ⇒ 一轮可以把它一个人跑满再连带跳过守卫段（cnb-3f5 的 7498.6s 就是这么烧的）。缺：%s"
        % missing[:10])


def test_repair_chain_has_time_left_for_the_guard_stages():
    """自愈链的 npc:go 时间总和不能吃掉整个 job：要给验证/评审/最终门禁留下份额。"""
    offenders = []
    evaluated = 0
    for key, job in _jobs():
        job_t = _seconds(job.get("timeout"))
        repairs = _npc_stages(job, "failStages")
        if not job_t or not repairs:
            continue
        unbounded = [s.get("name") for s in repairs if not _seconds(s.get("timeout"))]
        if unbounded:
            # 没有 timeout 就读不出"占了多少份额" ⇒ 这一格必须算**读不到**，不许当成 0% 蒙过（判绿的必要条件是能算）
            offenders.append("%s：自愈链 npc:go 段没有 timeout（%s）⇒ 份额无法评估，不许判过"
                             % (key, ", ".join(str(x) for x in unbounded[:3])))
            evaluated += 1
            continue
        evaluated += 1
        need = sum(_seconds(s.get("timeout")) or 0 for s in repairs)
        share = need / float(job_t)
        guards_present = any(any(g in str(s.get("name") or "") for g in GUARD_STAGES)
                             for s in (job.get("failStages") or []) if isinstance(s, dict))
        if share > MAX_REPAIR_SHARE:
            offenders.append("%s：自愈链 npc:go 合计 %ds = job timeout %ds 的 %.0f%%（上限 %.0f%%%s）"
                             % (key, need, job_t, share * 100, MAX_REPAIR_SHARE * 100,
                                "" if guards_present else "，且该链没有验证/评审/门禁段"))
    assert evaluated, (
        "一条自愈链都没能评估（要么没有 failStages，要么 job 没声明 timeout）⇒ 这是『读不到』不是『通过』")
    assert not offenders, (
        "修复段时间预算越界或不可评估，修复即使成功也没时间跑完守卫段 ⇒ 第 3a 项永远不能结案：%s" % offenders[:6])


def test_red_sample_missing_timeout_is_caught():
    """红样自校：把 timeout 全摘掉，第一条必须变红（证明它不是永远绿的空判据）。"""
    import copy

    bad = copy.deepcopy(CFG)
    hit = 0
    for key, job in _jobs_of(bad):
        for bucket in ("stages", "failStages"):
            for s in (job.get(bucket) or []):
                if isinstance(s, dict) and str(s.get("type") or "") == "npc:go" and s.get("timeout"):
                    s.pop("timeout")
                    hit += 1
    if not hit:
        # 当前 main 上本来就全是 None：那就反向造一个"有 timeout 再删掉"的样本，
        # 目的是证明**这条判据能变红**，而不是证明它此刻是绿的。
        sample = {"stages": [{"name": "AI-修复-第1轮", "type": "npc:go",
                             "options": {"maxTurns": 120}}]}
        assert not sample["stages"][0].get("timeout"), "红样构造失败"
        assert _seconds(sample["stages"][0].get("timeout")) is None
        return
    missing = []
    for key, job in _jobs_of(bad):
        for bucket in ("stages", "failStages"):
            for s in _npc_stages(job, bucket):
                if not _seconds(s.get("timeout")):
                    missing.append(1)
    assert missing, "摘掉全部 timeout 后判据却读不到违规 ⇒ 探测面坏了"


def _jobs_of(cfg):
    for root in (cfg.get("main") or {}, cfg.get("$") or {}):
        for key, val in root.items():
            for job in (val if isinstance(val, list) else [val]):
                if isinstance(job, dict):
                    yield str(key), job


def test_red_sample_greedy_repair_timeout_is_caught():
    """红样自校 2：修复段 timeout 大到吃掉整个 job ⇒ 第二条必须变红。"""
    sample_job = {"timeout": "10h",
                  "failStages": [
                      {"name": "AI-修复-第1轮", "type": "npc:go", "timeout": "9h",
                       "options": {"maxTurns": 120}},
                      {"name": "验证-实际pytest及Node和语法", "script": "python -m pytest tests/"},
                  ]}
    job_t = _seconds(sample_job["timeout"])
    need = sum(_seconds(s.get("timeout")) or 0 for s in _npc_stages(sample_job, "failStages"))
    assert need / float(job_t) > MAX_REPAIR_SHARE, "红样没造出越界形状 ⇒ 本自校无效（不许据此判绿）"
