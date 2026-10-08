#!/usr/bin/env python3
"""把 CNB 流水线的总时长预算按权重切分给各爬取源。

移植到 CNB 后 cars 的真实约束是「流水线 120 分钟硬上限」：CNB 日志明示
`maximum pipeline duration is exceeded: 120min`，超时整条构建被杀，
此时无论各源怎么续跑都拿不到本轮产物，Pages 只能停在上一轮日期。

而GitHub Actions 时代各源的 `--time-limit` 是各自独立的长预算
（汽车之家/懂车帝各 2700s，易车最长 21000s），三者相加远超 CNB 上限，
于是「每源都留足预算」反而等于「每源都会被中途腰斩」。

本脚本的职责只有一个：给定剩余秒数，按显式权重切出各源的 `--time-limit`，
使三者之和恒≤ 可用预算，并留出合并/发布阶段的固定开销。

设计约束（都来自实测，不是我拍脑袋定的）：
- 合并+组装+发布+回推在代理带宽下实测需要约 20 分钟，必须先扣掉。
- 汽车之家有 6 步、懂车帝有 2 步，两者是step 级--time-limit，
  一步一预算，所以权重按「步数」而不是按「源」计。
- 权重必须是整数且和为 1000（千分比），避免浮点除法误差在 sh 里失真。
- DEBUG_MODE 下走独立的固定小预算，与生产预算彻底分开：
  debug 的目的是跑通全链刷新 Pages 日期，不是采全量数据。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# CNB 流水线硬上限（日志明示 120min）。留 3 分钟余量给 runner 收尾与心跳尾巴。
PIPELINE_LIMIT_SECONDS = 120 * 60
PIPELINE_SAFETY_MARGIN_SECONDS = 180

# 合并 / 组装 / 发布 / 线上验收 / 回推的固定开销。
# 115MB 全量基线 + 代理带宽是主因，实测这一段本身就是十几分钟量级。
PUBLISH_PHASE_RESERVE_SECONDS = 20 * 60

# 各爬取步的权重（千分比，合计必须为 1000）。
# 汽车之家 6 步但只有 step1 吃 --time-limit（step2-6 是本地解析，不过预算闸），
# 因此按「吃预算的步数」给权重：汽车之家 1 份、懂车帝 2 份（step1+step2）、
# 易车 1 份。懂车帝单步最重（每步都要起 Chrome），故 2 份。
#
# 经销商报价**不在这里**：它已拆成独立链路（crontab: 37 8,16 * * *），
# 失败域隔离——报价失败不许拖住基础属性（用户裁定 2026-10-09）。
# 它自带 --time-limit 1500，与 120min 总预算无关。
STEP_WEIGHTS = {
    "autohome_step1": 250,
    "dongchedi_step1": 250,
    "dongchedi_step2": 250,
    "yiche": 250,
}
WEIGHT_TOTAL = 1000

# 权重表必须自洽：权重和与声明的千分比一致，否则说明有人改权重时漏了改这里。
# 不一致时 allocate() 仍能正常工作（按实际权重和归一），但预算口径会与文档不符，
# 所以在import 时就直接失败——这类「配置漂移」应该在启动时炸，而不是在 CNB 上
# 跑了一个小时后才被kill。
if sum(STEP_WEIGHTS.values()) != WEIGHT_TOTAL:
    raise ValueError(
        f"STEP_WEIGHTS 权重和 {sum(STEP_WEIGHTS.values())} != WEIGHT_TOTAL {WEIGHT_TOTAL}；"
        "改权重时必须同步改 WEIGHT_TOTAL"
    )

# 单步下限：低于这个秒数，爬虫连一个车系都跑不完，纯浪费一个 stage。
# 下限只保证「不为零」，不保证有意义，因此同时受总预算约束。
MIN_STEP_SECONDS = 120

# DEBUG 模式固定预算：目标是「跑通全链 + 刷新 Pages 日期」，
# 不是采全量。给每步 8 分钟足够爬完有限车系并产出可发布产物。
DEBUG_STEP_SECONDS = 480


def _is_debug(explicit: str | None) -> bool:
    if explicit is not None:
        return explicit.strip().lower() == "true"
    return os.environ.get("DEBUG_MODE", "false").strip().lower() == "true"


def _resolve_total_seconds(total_seconds: int | None, elapsed_seconds: int) -> int:
    """算出留给爬取的秒数。

    顺序不可调换：先扣安全余量（防止刚好压在120min 上被腰斩），
    再扣已耗时，最后扣发布阶段固定开销。
    """
    if total_seconds is not None:
        available = total_seconds
    else:
        available = PIPELINE_LIMIT_SECONDS - PIPELINE_SAFETY_MARGIN_SECONDS - elapsed_seconds
    return max(0, available - PUBLISH_PHASE_RESERVE_SECONDS)


def allocate(total_seconds: int | None, elapsed_seconds: int, *, debug: bool) -> dict[str, int]:
    """返回 {步名: 秒数}。

    debug 模式下每个吃预算的步拿固定小额度；生产模式下按权重切分，
    并保证各步之和不超过可用预算（向下取整后必然成立，此处再做一次钳制，
    避免未来有人改权重时把总和改超）。
    """
    if debug:
        return {step: DEBUG_STEP_SECONDS for step in STEP_WEIGHTS}

    available = _resolve_total_seconds(total_seconds, elapsed_seconds)
    weight_sum = sum(STEP_WEIGHTS.values())
    allocated = {
        step: available * weight // weight_sum
        for step, weight in STEP_WEIGHTS.items()
    }

    # 权重和 != WEIGHT_TOTAL 时按实际权重和归一，保证各步之和 ≤ 可用预算。
    # 这里刻意不用 WEIGHT_TOTAL 参与除法：那样在权重被改坏（例如总和 1500）时
    # 会把每一步都按比例放大 1.5 倍，反而超预算——正是本函数要防的事。
    overspend = sum(allocated.values()) - available
    if overspend > 0:
        heaviest = max(allocated, key=lambda step: allocated[step])
        allocated[heaviest] = max(MIN_STEP_SECONDS, allocated[heaviest] - overspend)

    for step in list(allocated):
        allocated[step] = max(MIN_STEP_SECONDS, allocated[step])
    return allocated


def emit_env(path: str, budgets: dict[str, int], *, debug: bool, available: int) -> None:
    """落盘成 shell 可 source 的 env 文件（不打印到 stdout，避免污染调用方日志）。"""
    lines = [
        "# 由 scripts/allocate_crawl_budget.py 生成，请勿手改",
        f"CRAWL_BUDGET_DEBUG={'true' if debug else 'false'}",
        f"CRAWL_BUDGET_AVAILABLE_SECONDS={available}",
    ]
    for step, seconds in budgets.items():
        lines.append(f"{step.upper()}_TIME_LIMIT={seconds}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="按 CNB 流水线上限切分各爬取步的时间预算")
    parser.add_argument(
        "--output",
        default="/tmp/cnb-budget.env",
        help="生成的 env 文件路径（shell source 用）",
    )
    parser.add_argument(
        "--total-seconds",
        type=int,
        default=None,
        help="留给爬取的总秒数；缺省按 120min 上限减已耗时再减发布阶段开销",
    )
    parser.add_argument(
        "--elapsed-seconds",
        type=int,
        default=0,
        help="本轮已耗时秒数（缺省 0，即流水线刚开始）",
    )
    parser.add_argument(
        "--debug-mode",
        default=None,
        help="强制 DEBUG_MODE 开关；缺省读环境变量",
    )
    parser.add_argument(
        "--print",
        dest="print_json",
        action="store_true",
        help="把结果以 JSON 打到 stdout（便于测试与诊断）",
    )
    args = parser.parse_args()

    debug = _is_debug(args.debug_mode)
    budgets = allocate(args.total_seconds, args.elapsed_seconds, debug=debug)
    available = _resolve_total_seconds(args.total_seconds, args.elapsed_seconds)

    emit_env(args.output, budgets, debug=debug, available=available)

    if debug:
        print(
            f"DEBUG 模式：各爬取步固定 {DEBUG_STEP_SECONDS}s"
            f"（合计 {DEBUG_STEP_SECONDS * len(STEP_WEIGHTS)}s），目标是跑通全链刷新 Pages 日期",
            file=sys.stderr,
        )
    else:
        print(
            f"生产预算：可用 {available}s，按权重切分 "
            + " ".join(f"{step}={seconds}s" for step, seconds in budgets.items())
            + f"（合计 {sum(budgets.values())}s）",
            file=sys.stderr,
        )

    if args.print_json:
        print(json.dumps(
            {
                "debug": debug,
                "available_seconds": available,
                "step_seconds": budgets,
                "total_allocated": sum(budgets.values()),
            },
            ensure_ascii=False,
        ))
    return 0


if __name__ == "__main__":
    sys.exit(main())