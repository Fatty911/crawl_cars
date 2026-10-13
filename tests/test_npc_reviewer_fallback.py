"""CNB NPC 评审角色与配额闸的回归守卫（对齐 2026-10-11 cnb/main 实际结构）。

这些断言记录的是**既有事实**，用于防止后续改动悄悄削弱评审独立性：
  - 评审必须与实现者不同模型家族（实现 deepseek-v4-flash，评审 glm-5.3-flash）
  - 必须有显式配额前置检查，限额时整链按 RUN/跳过分支走，不得让 stage 报错
  - VERDICT 必须由 guard 消费，UNKNOWN/缺失不得当作通过
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEXT = (ROOT / ".cnb.yml").read_text(encoding="utf-8").replace("\r", "")


def test_implementer_and_cross_reviewer_are_different_families():
    assert "model: deepseek-v4.1-flash" in TEXT, "实现阶段模型已变更，请同步复核本守卫"
    assert "model: glm-5.3-flash" in TEXT, "独立家族评审阶段被移除（同族自审）"


def test_pr_review_is_not_same_family_self_review():
    """NPC-PR审查 目前与实现者同为 deepseek 家族，构成同族自审。
    负责人要求评审为 glm-5.3-flash，且额度耗尽时才降级到 deepseek 家族。"""
    start = TEXT.index("name: NPC-PR审查")
    block = TEXT[start:start + 1500]
    assert "model: glm-5.3-flash" in block, (
        "NPC-PR审查 仍是同族自审（当前模型："
        + (re.search(r"model: (\S+)", block).group(1) if re.search(r"model: (\S+)", block) else "无")
        + "）；负责人要求评审用 glm-5.3-flash，只有额度耗尽才降级到 deepseek 家族"
    )


def test_glm_cross_review_has_enough_turns():
    """审查-GLM只读交叉评审 仍是 maxTurns: 20 —— #18 只抬了 pull_request 链，这条没抬。
    20 轮读不完 diff 就收工，评审等于盖章。与实现阶段同档（>=100）。"""
    start = TEXT.index("name: 审查-GLM只读交叉评审")
    block = TEXT[start:start + 1200]
    m = re.search(r"maxTurns:\s*(\d+)", block)
    assert m, "GLM 交叉评审阶段找不到 maxTurns 声明（被删了？别用默认值当修法）"
    assert int(m.group(1)) >= 100, (
        "GLM 交叉评审 maxTurns=%s 仍是 20 档，读不完改动就结束；要求 >=100" % m.group(1)
    )


def test_quota_is_checked_before_spending_review_budget():
    assert "NPC审核前免费额度复查" in TEXT, "评审前的免费额度复查阶段被移除"
    assert TEXT.count("NPC_BUDGET_STATE") >= 3, "配额分支判定消失：限额时可能直接报错中断"


def test_reviewer_is_read_only_and_must_emit_verdict():
    review = TEXT[TEXT.index("审查-GLM只读交叉评审"):][:2200]
    assert "只读" in review and "VERDICT: PASS" in review
    assert "不得修改源码" in review, "评审只读约束被削弱"


def test_verdict_is_consumed_by_a_guard_not_by_a_human():
    assert "cars-npc-guard.py validate" in TEXT
    assert "cars-npc-guard.py finalize" in TEXT, "最终门禁丢失：评审结论可能不被执行"


def test_reviewer_cannot_be_satisfied_by_editing_assertions():
    review = TEXT[TEXT.index("审查-GLM只读交叉评审"):][:2200]
    assert re.search(r"不能以改断言掩盖问题|不得修改.{0,20}测试", review), (
        "缺少「不得靠改测试来通过」的评审约束"
    )
