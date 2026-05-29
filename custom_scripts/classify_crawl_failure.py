#!/usr/bin/env python3
"""Classify crawler failures before invoking AI auto-fix."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


PROGRESS_PATTERNS = [
    r"Exit code:\s*10\b",
    r"exit code\s*10\b",
    r"已达到时间限制",
    r"已达到车型数量限制",
    r"已达到车系数量限制",
    r"未完成，.*等待下次继续",
    r"Step1 incomplete",
    r"Step2 incomplete",
    r"Update progress",
    r"Update dongchedi progress",
    r"Re-running step",
    r"Too many runs, stopping",
]

PROGRESS_AMOUNT_PATTERNS = [
    r"cars_downloaded[\"']?\s*[:=]\s*(\d+)",
    r"累计\s*(\d+)",
    r"共获取\s*(\d+)\s*个目标?车系",
    r"\[(\d+)/\d+\]\s*正在爬取",
    r"第(\d+)个车型",
    r"rows?\D+(\d+)",
]

SITE_BREAKAGE_PATTERNS = [
    r"未生成\s*(?:autoHome|dongchedi)_\*\.json",
    r"未解析到任何车型数据",
    r"只有\s*\d+\s*行",
    r"无法解析config或option",
    r"未能解析到配置数据",
    r"配置页面加载超时",
    r"连续\d+页为空",
    r"API异常",
    r"403\b|404\b|429\b|500\b|503\b|504\b",
    r"NoSuchElementException",
    r"TimeoutException",
]


def read_log(paths: list[str]) -> str:
    chunks = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE | re.MULTILINE) for pattern in patterns)


def max_progress_amount(text: str) -> int:
    values = []
    for pattern in PROGRESS_AMOUNT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            try:
                values.append(int(match.group(1)))
            except (TypeError, ValueError):
                pass
    return max(values, default=0)


def classify(text: str, progress_threshold: int) -> tuple[str, str]:
    if not text.strip():
        return "unknown", "日志为空，无法判断是否为主动分段退出"

    has_progress = matches_any(PROGRESS_PATTERNS, text)
    has_site_breakage = matches_any(SITE_BREAKAGE_PATTERNS, text)
    progress_amount = max_progress_amount(text)

    if has_progress and not has_site_breakage:
        return "progress_exit", "日志显示爬虫主动保存进度或达到分段限制"

    if has_progress and progress_amount >= progress_threshold:
        return (
            "progress_exit",
            f"日志显示已处理约 {progress_amount} 条，属于分段爬取/保护退出",
        )

    if has_site_breakage:
        return "site_breakage", "日志显示配置页、接口、解析或输出数据异常"

    return "unknown", "没有明确的主动退出或站点结构异常特征"


def main() -> int:
    parser = argparse.ArgumentParser(description="分类爬虫失败原因，避免误触发 AI 修复")
    parser.add_argument("logs", nargs="+", help="待分析的日志文件")
    parser.add_argument(
        "--progress-threshold",
        type=int,
        default=200,
        help="已处理数量达到该阈值时，倾向判定为分段爬取退出",
    )
    parser.add_argument(
        "--github-output",
        default="",
        help="可选：写入 GitHub Actions output 的文件路径",
    )
    args = parser.parse_args()

    text = read_log(args.logs)
    result, reason = classify(text, args.progress_threshold)
    should_fix = "true" if result in {"site_breakage", "unknown"} else "false"

    print(f"classification={result}")
    print(f"should_fix={should_fix}")
    print(f"reason={reason}")

    output_path = args.github_output
    if output_path:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"classification={result}\n")
            f.write(f"should_fix={should_fix}\n")
            f.write(f"reason={reason}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
