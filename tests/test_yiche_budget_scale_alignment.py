"""爬取预算必须与 job 声明的运行上限同尺度（Issue #5 的验收判据，自包含）。

现网事实（2026-10-11 实测）：
  `.cnb.yml` 的 api_trigger/crontab 爬虫 job 写着 `timeout: 10h`，注释里的本意是
  "易车 10800s + 汽车之家/懂车帝各 2700s×3"；而 `scripts/allocate_crawl_budget.py` 仍按
  `PIPELINE_LIMIT_SECONDS = 120*60` 折算，四步等权 ⇒ 易车每轮只拿到 ~855s（约本意的 6%）。
  这是易车覆盖从 382 掉到 4958 里"每轮爬不动"那条独立成因，与断点回灌、上游失败连带跳过并列。

判据断言的是**尺度一致性**，不是某个具体秒数：
  分配器承认的总上限 ≥（job 声明 timeout − 发布预留 − 安全余量）× 80%。
现网必须红（10h job vs 7200s 折算）；把 `PIPELINE_LIMIT_SECONDS` 与 job timeout 对齐后必须绿。
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
RATIO_FLOOR = 0.8  # 允许比 job 上限保守 20%，再多就是口径脱节


def _allocator():
    spec = importlib.util.spec_from_file_location(
        "allocate_crawl_budget", ROOT / "scripts" / "allocate_crawl_budget.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _job_timeout_seconds() -> int:
    """取爬虫 job 声明的 timeout（h/m 两种写法都认），取最大值即最长那个 job。"""
    text = (ROOT / ".cnb.yml").read_text(encoding="utf-8").replace("\r", "")
    found = re.findall(r"timeout:\s*(\d+)([hm])\b", text)
    assert found, ".cnb.yml 里找不到任何 job 级 timeout 声明"
    return max(int(v) * (3600 if u == "h" else 60) for v, u in found)


def _usable(job_seconds: int, mod) -> int:
    return job_seconds - mod.PUBLISH_PHASE_RESERVE_SECONDS - mod.PIPELINE_SAFETY_MARGIN_SECONDS


def test_allocator_ceiling_matches_declared_job_timeout():
    mod = _allocator()
    job_seconds = _job_timeout_seconds()
    ceiling = mod.PIPELINE_LIMIT_SECONDS - mod.PUBLISH_PHASE_RESERVE_SECONDS - mod.PIPELINE_SAFETY_MARGIN_SECONDS
    usable = _usable(job_seconds, mod)
    assert ceiling > 0, "分配器可用预算非正，任何一步都会被跳过"
    ratio = ceiling / usable
    assert ratio >= RATIO_FLOOR, (
        "预算口径与 job 上限脱节：job 声明 timeout=%ds，扣掉发布预留与安全余量后可给爬虫 %ds，"
        "但分配器只承认 %ds（%.0f%%）。改 job timeout 必须同步改 PIPELINE_LIMIT_SECONDS。"
        % (job_seconds, usable, ceiling, ratio * 100)
    )


def test_yiche_gets_at_least_sixteenths_of_the_declared_window():
    """易车单步实得不该只有本意的零头：按四步等权折算后仍要拿到 job 的 20% 以上。"""
    mod = _allocator()
    job_seconds = _job_timeout_seconds()
    budgets = mod.allocate(total_seconds=None, elapsed_seconds=1800, debug=False)
    assert sum(budgets.values()) <= mod.PIPELINE_LIMIT_SECONDS, "各步之和越过总上限"
    for step, seconds in budgets.items():
        assert seconds >= mod.MIN_STEP_SECONDS, "%s 低于单步下限 %ds" % (step, mod.MIN_STEP_SECONDS)
    share = budgets["yiche"] / job_seconds
    assert share >= 0.20, (
        "易车每轮只分到 %ds / job %ds = %.1f%%，远低于注释本意（10800s/36000s=30%%）："
        "每轮跑不完一个品牌，续爬断点自然永远不收敛" % (budgets["yiche"], job_seconds, share * 100)
    )
