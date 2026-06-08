#!/usr/bin/env python3
"""Static checks for crawler workflow timing and self-healing rules."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
MORNING_CRON = "7,22,37,52 0-3 * * *"
AFTERNOON_CRON = "7,17,27 5 * * *"
MORNING_START_SNIPPET = "$((8 * 60))"
WINDOW_TEXT = "8:00-12:30"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def assert_condition(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def check_crawler_workflow(path: Path, errors: list[str]) -> None:
    data = load_yaml(path)
    text = path.read_text(encoding="utf-8")
    schedules = [item.get("cron") for item in data.get(True, {}).get("schedule", [])]

    assert_condition(MORNING_CRON in schedules, f"{path.name} 缺少 08:07-11:52 上午备用 cron", errors)
    assert_condition(AFTERNOON_CRON in schedules, f"{path.name} 缺少 13:07/13:17/13:27 下午 cron", errors)
    assert_condition(MORNING_START_SNIPPET in text, f"{path.name} 未使用 08:00 作为上午窗口起点", errors)
    assert_condition("13 * 60 + 30" in text, f"{path.name} 未保留 13:30 下午启动截止", errors)
    assert_condition("4 * 3600 + 30 * 60" in text, f"{path.name} 未保留 12:30 上午结束预算", errors)


def check_trigger(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    assert_condition("CN_HOUR -ge 8" in text, "crawl-trigger.yml 未使用 08:00 作为上午触发起点", errors)
    assert_condition(WINDOW_TEXT in text, "crawl-trigger.yml 未同步 08:00-12:30 文案", errors)


def check_ai_monitor(path: Path, errors: list[str]) -> None:
    data = load_yaml(path)
    text = path.read_text(encoding="utf-8")
    workflow_run = data.get(True, {}).get("workflow_run", {})
    workflows = set(workflow_run.get("workflows", []))

    assert_condition({"汽车之家爬虫", "懂车帝爬虫"}.issubset(workflows), "AI 监控未监听两个主爬虫", errors)
    assert_condition("openai/codex-action@v1" in text, "AI 监控未集成官方 Codex Action", errors)
    assert_condition("ensure_codex_autofix_scope.py" in text, "AI 监控缺少 Codex 修改范围检查", errors)
    assert_condition("check_workflow_expectations.py" in text, "AI 监控缺少 workflow 预期检查", errors)


def main() -> int:
    errors: list[str] = []
    check_crawler_workflow(ROOT / ".github/workflows/crawl-autohome.yml", errors)
    check_crawler_workflow(ROOT / ".github/workflows/crawl-dongchedi.yml", errors)
    check_trigger(ROOT / ".github/workflows/crawl-trigger.yml", errors)
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
