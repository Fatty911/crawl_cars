#!/usr/bin/env python3
"""Static checks for crawler workflow timing and self-healing rules."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WINDOW_TEXT = "8:00-12:30"
AFTERNOON_TEXT = "13:00-22:00"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def assert_condition(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def check_crawler_workflow(path: Path, errors: list[str]) -> None:
    data = load_yaml(path)
    text = path.read_text(encoding="utf-8")
    schedules = data.get(True, {}).get("schedule", [])

    assert_condition(not schedules, f"{path.name} 不应继续依赖 GitHub Actions schedule", errors)
    assert_condition("WINDOW_END_BUFFER_SECONDS" in text, f"{path.name} 缺少窗口结束缓冲", errors)
    assert_condition("scripts/crawl_budget.py configure" in text, f"{path.name} 未使用共享窗口预算脚本", errors)
    assert_condition("scripts/crawl_budget.py clamp" in text, f"{path.name} 未按 Action 和窗口综合预算收口", errors)


def check_trigger(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    assert_condition("$((8 * 60))" in text, "crawl-trigger.yml 未使用 08:00 作为上午触发起点", errors)
    assert_condition(WINDOW_TEXT in text, "crawl-trigger.yml 未同步 08:00-12:30 文案", errors)
    assert_condition(AFTERNOON_TEXT in text, "crawl-trigger.yml 未同步 13:00-22:00 文案", errors)
    assert_condition('default: \'all\'' in text or 'default: "all"' in text, "crawl-trigger.yml 默认不应随机漏掉车源", errors)
    assert_condition("crawl-autohome.yml" in text and "crawl-dongchedi.yml" in text, "crawl-trigger.yml 未触发两个主爬虫", errors)
    assert_condition("RANDOM" not in text and "skip_delay" not in text, "crawl-trigger.yml 不应再追加随机启动延迟", errors)


def check_budget_script(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    assert_condition('"afternoon": (13 * 60, 22 * 60)' in text, "crawl_budget.py 未设置 13:00-22:00 下午窗口", errors)
    assert_condition("MAX_WORKFLOW_SECONDS" in text, "crawl_budget.py 缺少 Action 总时限预算", errors)
    assert_condition("PROGRESS_COMMIT_BUFFER_SECONDS" in text, "crawl_budget.py 缺少进度提交缓冲", errors)


def check_ai_monitor(path: Path, errors: list[str]) -> None:
    data = load_yaml(path)
    text = path.read_text(encoding="utf-8")
    workflow_run = data.get(True, {}).get("workflow_run", {})
    workflows = set(workflow_run.get("workflows", []))

    assert_condition({"汽车之家爬虫", "懂车帝爬虫"}.issubset(workflows), "AI 监控未监听两个主爬虫", errors)
    assert_condition("openai/codex-action@v1" in text, "AI 监控未集成官方 Codex Action", errors)
    assert_condition("ensure_codex_autofix_scope.py" in text, "AI 监控缺少 Codex 修改范围检查", errors)
    assert_condition("check_workflow_expectations.py" in text, "AI 监控缺少 workflow 预期检查", errors)


def check_merge_workflow(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    assert_condition(
        "download_latest_crawler_artifact.py" in text,
        "merge-and-filter.yml 不应只下载最近一次成功爬虫 run，应扫描最近有效数据 artifact",
        errors,
    )
    assert_condition("MIN_ARTIFACT_DATE" in text, "merge-and-filter.yml 缺少当前半月 artifact 日期限制", errors)


def main() -> int:
    errors: list[str] = []
    check_crawler_workflow(ROOT / ".github/workflows/crawl-autohome.yml", errors)
    check_crawler_workflow(ROOT / ".github/workflows/crawl-dongchedi.yml", errors)
    check_trigger(ROOT / ".github/workflows/crawl-trigger.yml", errors)
    check_budget_script(ROOT / "scripts/crawl_budget.py", errors)
    check_merge_workflow(ROOT / ".github/workflows/merge-and-filter.yml", errors)
    assert_condition((ROOT / "scripts/configure_cron_job_org.py").exists(), "缺少 cron-job.org 配置脚本", errors)
    check_ai_monitor(ROOT / ".github/workflows/AI_Auto_Fix_Monitor.yml", errors)

    if errors:
        print("workflow 预期校验失败：")
        for error in errors:
            print(f"- {error}")
        return 1

    print("workflow 预期校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
