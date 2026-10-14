"""交付核对闸必须**只在本次真有修复任务时**执行——否则每条普通 Issue 都产出一轮红。

监工自己的缺陷（这条是监工落地的那一格的副作用，不是 NPC 的）：
`$: issue.open` 链现在的形状是

    检查fix标签(success) → install-deps → AI-Issue驱动修复(无 fix 标签时 skipped)
      → 交付核对-产物必须真取回(**照跑，且必红**) → failStages 拉起 AI-修复-第1轮

效果层实测（监工探针 Issue **#74**，构建 `cnb-pnu-1k4seieri`，该 Issue **不带** `fix` 标签）：

    检查fix标签                 success
    AI-Issue驱动修复            skipped        ← 标签闸这一段是对的
    交付核对-产物必须真取回      error          ← 缺陷在这里
    诊断-收集失败上下文          success
    AI-修复-第1轮               start          ← 为一次"无事可做"拉起自愈 agent，白烧免费额度

`交付核对` 段的原文读数：`DELIVERY-FAIL reason=no-comments issue=74`
—— 本次没有修复任务，最新评论里当然没有产物可取，**这不是交付失败，是不该做这次核对**。

⇒ 后果有两层：① "所有工作流任务成功"永远达不到（任何普通 Issue 都造一轮红）；
   ② 自愈链被空任务触发，烧掉的是本可以用来修缺陷的额度。

这些用例当前为红。修法必须同时满足第 4、5 条**反向**要求：
不许为了让探针变绿就把核对段整段摘掉或改成恒真（那是把 #62/#63 修好的假交付防线拆回去）。
"""

from __future__ import annotations

import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8")) or {}
# `$` 是**顶层键**（与 `main` 同级），不是 `main` 的子键 —— 读错层级会让所有阶段"都不在"，
# 于是判据整份红、修法被误判成没做（监工第一版就是这么错的，10-14 用结构读数纠正）。
ISSUE_CHAIN = (CFG.get("$") or {}).get("issue.open")

DELIVERY_WORDS = ("交付核对", "产物必须真取回")
AGENT_STAGE_WORDS = ("AI-Issue驱动修复",)
# 标签闸的既有产物变量：`检查fix标签` 段会 `set env for key: NPC_FIX_GATE`
FIX_GATE_ENV = "NPC_FIX_GATE"


def _jobs(node):
    if isinstance(node, list):
        return [j for j in node if isinstance(j, dict)]
    return [node] if isinstance(node, dict) else []


def _issue_open_stages():
    out = []
    for job in _jobs(ISSUE_CHAIN):
        for s in (job.get("stages") or []):
            if isinstance(s, dict):
                out.append(s)
    return out


def _stage(name_words):
    for s in _issue_open_stages():
        nm = str(s.get("name") or "")
        if any(w in nm for w in name_words):
            return s
    return None


def test_chain_still_has_both_stages():
    """红线：闸与核对段都还在（不许用"删掉核对段"糊弄第 3 条）。"""
    assert _stage(AGENT_STAGE_WORDS), "`AI-Issue驱动修复` 段不许被摘掉"
    assert _stage(DELIVERY_WORDS), (
        "`交付核对-产物必须真取回` 段不许被摘掉——它是 #62/#63 修的"
        "『链的绿必须等于产物真取回』那条防线"
    )


def test_agent_stage_is_still_label_gated():
    """标签闸本身要继续有效：`AI-Issue驱动修复` 必须带条件（`if:`），且条件要看标签。"""
    agent = _stage(AGENT_STAGE_WORDS)
    cond = str(agent.get("if") or "")
    assert cond, "`AI-Issue驱动修复` 的 `if:` 不见了 ⇒ 任何 Issue 都会起修复 agent"
    assert "fix" in cond.lower() or FIX_GATE_ENV in cond, (
        "修复段的条件不再看 fix 标签：%r" % cond)


def test_delivery_gate_does_not_run_without_fix_label():
    """核心：交付核对段必须**同样**受 fix 标签约束。

    判据取声明层（YAML 里该段的 `if:`），因为效果层已经反证过：
    探针 Issue #74 不带标签时它照样跑了并回了 `reason=no-comments` 的 error。
    """
    gate = _stage(DELIVERY_WORDS)
    cond = str(gate.get("if") or "")
    assert cond, (
        "交付核对段没有条件 ⇒ 每条普通 Issue 都会跑它："
        "无产物 → error → failStages 拉起自愈 agent 白烧额度（实测 cnb-pnu-1k4seieri）"
    )
    assert ("fix" in cond.lower()) or (FIX_GATE_ENV in cond), (
        "交付核对的条件没看 fix 标签/闸变量：%r（必须与修复段同一条口径）" % cond)


def test_delivery_gate_still_fails_loudly_when_label_present():
    """反向红线：带 fix 标签时核对必须仍然严格——失败路径 `exit 1`、不许 `|| exit 0`、
    不许把 `reason=no-comments` 当成通过。加条件不能把闸变成恒真。"""
    gate = _stage(DELIVERY_WORDS)
    script = gate.get("script")
    if isinstance(script, dict):
        script = script.get("run") or ""
    script = str(script or "")
    assert script, "交付核对段没有 script 了"
    assert "exit 1" in script, "核对失败不 exit 1 ⇒ 永远打不红（假闸）"
    assert "|| exit 0" not in script, "核对里出现 `|| exit 0`：把失败吃成成功"
    assert "no-comments" in script or "artifact-unreachable" in script, (
        "核对不再点名失败原因（no-comments / artifact-unreachable 至少留一个）"
    )
    assert "finish with length" in script, (
        "核对要识别 `finish with length`（agent 单次输出超限的截停不带 error）"
    )


def test_fix_label_stage_still_sets_the_gate_variable():
    """接线：`检查fix标签` 段必须仍然导出 `NPC_FIX_GATE`，
    否则交付核对的条件会引用一个不存在的变量而恒假（等于悄悄拆闸）。"""
    label_stage = None
    for s in _issue_open_stages():
        if "fix标签" in str(s.get("name") or ""):
            label_stage = s
            break
    assert label_stage, "`检查fix标签` 段不在了"
    body = label_stage.get("script")
    if isinstance(body, dict):
        body = body.get("run") or ""
    blob = str(body or "") + yaml.safe_dump(label_stage, allow_unicode=True)
    assert FIX_GATE_ENV in blob, (
        "`检查fix标签` 不再导出 %s ⇒ 下游条件引用空变量，闸会被静默放宽" % FIX_GATE_ENV)
