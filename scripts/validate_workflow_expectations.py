#!/usr/bin/env python3
"""Static checks for crawler workflow timing and self-healing rules."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PAGES_PUSH_DEPENDENCIES = (
    "docs/index.html",
    "docs/app.js",
    "docs/styles.css",
    "docs/config.js",
    "docs/filter_conditions.json",
    "docs/analysis/merge_evidence_report.json",
    "config/filter_conditions.json",
    "scripts/prepare_pages_payload.py",
    "scripts/publish_identity.py",
    "scripts/verify_publish_superset.py",
    "scripts/prepare_debug_merge_inputs.py",
    "scripts/preserve_publish_baseline.py",
    "scripts/filter_pages_source_baseline.py",
    "scripts/download_latest_crawler_artifact.py",
    "scripts/analysis/merge_evidence_report.py",
    "scripts/crawl_zero_to_whole_ratio.py",
    "scripts/merge_data.py",
    "scripts/test_autohome.py",
    "scripts/crawl_dongchedi.py",
    "scripts/crawl_yiche.py",
    ".github/workflows/merge-and-filter.yml",
    ".github/workflows/crawl-autohome.yml",
    ".github/workflows/crawl-dongchedi.yml",
    ".github/workflows/crawl-yiche.yml",
)
WINDOW_TEXT = "8:00-12:30"
AFTERNOON_TEXT = "13:00-22:00"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def assert_condition(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def github_path_pattern_matches(path: str, pattern: str) -> bool:
    """Match the positive subset of GitHub Actions path globs used by this workflow."""
    marker = "__DOUBLE_STAR__"
    expression = re.escape(pattern.replace("**", marker))
    expression = expression.replace(re.escape(marker), ".*")
    expression = expression.replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
    return re.fullmatch(expression, path) is not None


def pages_push_paths_cover(path: Path, dependencies: tuple[str, ...]) -> list[str]:
    data = load_yaml(path)
    push = data.get(True, {}).get("push", {})
    patterns = push.get("paths", []) if isinstance(push, dict) else []
    return [
        dependency
        for dependency in dependencies
        if not any(github_path_pattern_matches(dependency, pattern) for pattern in patterns)
    ]


def check_crawler_workflow(path: Path, errors: list[str]) -> None:
    data = load_yaml(path)
    text = path.read_text(encoding="utf-8")
    schedules = data.get(True, {}).get("schedule", [])

    assert_condition(not schedules, f"{path.name} 不应继续依赖 GitHub Actions schedule", errors)
    assert_condition("WINDOW_END_BUFFER_SECONDS" in text, f"{path.name} 缺少窗口结束缓冲", errors)
    assert_condition("scripts/crawl_budget.py configure" in text, f"{path.name} 未使用共享窗口预算脚本", errors)
    assert_condition("scripts/crawl_budget.py clamp" in text, f"{path.name} 未按 Action 和窗口综合预算收口", errors)
    crawler = "autohome" if path.name == "crawl-autohome.yml" else "dongchedi"
    assert_condition(
        f"group: {crawler}-crawl-${{{{ github.ref }}}}" in text,
        f"{path.name} concurrency 不得按 run_profile 分组",
        errors,
    )
    assert_condition('echo "MAX_CARS=30" >> "$GITHUB_ENV"' in text, f"{path.name} debug 上限必须固定为 30", errors)
    assert_condition("DEBUG_OUTPUT_MAX_ROWS: 30" in text, f"{path.name} debug 输出上限必须固定为 30 行", errors)
    assert_condition("min_rows = 20 if debug_mode" in text, f"{path.name} debug 有效输出不得少于 20 行", errors)
    assert_condition("debug_mode and len(rows) > max_rows" in text, f"{path.name} debug 有效输出不得多于 30 行", errors)
    assert_condition(
        "github.event.inputs.debug_mode != 'true'" in text.split("uses: actions/cache@main", 1)[0].rsplit("if:", 1)[-1],
        f"{path.name} debug 不得恢复正式 cache",
        errors,
    )
    assert_condition(
        'if [ "$DEBUG_MODE" != "true" ]; then' in text and "scripts/git_sync_progress.sh" in text,
        f"{path.name} debug 进度写回缺少保护",
        errors,
    )
    job = next(iter(data["jobs"].values()))
    self_heal_steps = []
    for step in job["steps"]:
        name = str(step.get("name", ""))
        if name.startswith("Auto-fix ") or (name.startswith("Retry ") and "after fix" in name):
            self_heal_steps.append(step)
    assert_condition(
        bool(self_heal_steps)
        and all("github.event.inputs.debug_mode != 'true'" in str(step.get("if", "")) for step in self_heal_steps),
        f"{path.name} debug 不得进入会提交推送的自动修复/重试路径",
        errors,
    )
    assert_condition(
        "github.event.inputs.debug_mode == 'true'" in "\n".join(
            str(step.get("if", ""))
            for step in job["steps"]
            if str(step.get("name", "")).startswith("Fail unresolved")
        ),
        f"{path.name} debug 爬取错误必须失败关闭",
        errors,
    )
    artifact_prefix = "autohome-debug-data" if crawler == "autohome" else "dongchedi-debug-data"
    assert_condition(
        f"{artifact_prefix}-${{CRAWL_DATE}}-${{{{ github.run_id }}}}-${{{{ github.run_attempt }}}}" in text,
        f"{path.name} debug artifact 未绑定 run_id/run_attempt",
        errors,
    )
    if path.name == "crawl-autohome.yml":
        assert_condition(
            "steps.verify_autohome.outputs.target_complete == 'true'" in text
            and "fromJSON(steps.verify_autohome.outputs.row_count) >= 500" not in text,
            f"{path.name} 完成标记必须绑定真实目标完成而非仅行数阈值",
            errors,
        )
        trigger_condition = text.split("name: Trigger merge-and-filter workflow", 1)[1].split("run: |", 1)[0]
        assert_condition(
            "if: steps.upload_autohome.outcome == 'success'" in trigger_condition
            and "steps.step1.outputs.complete" not in trigger_condition
            and "steps.retry_step1.outputs.complete" not in trigger_condition,
            f"{path.name} 任一有效 artifact 上传成功后都必须自动触发合并",
            errors,
        )
    for input_name in ("debug_mode", "crawler_run_id", "crawler_run_attempt", "trigger_source"):
        assert_condition(
            f"-f {input_name}=" in text,
            f"{path.name} dispatch merge 缺少 {input_name}",
            errors,
        )
    assert_condition(
        '--ref "${{ github.ref_name }}"' in text,
        f"{path.name} dispatch merge 未透传当前 workflow ref",
        errors,
    )
    configure_section = text.split("name: Configure crawl window", 1)[1].split(
        "name: Calculate delay from trigger time", 1
    )[0]
    assert_condition(
        'echo "DEBUG_MODE=true" >> "$GITHUB_ENV"' in configure_section
        and 'echo "DEBUG_MODE=false" >> "$GITHUB_ENV"' in configure_section,
        f"{path.name} 未将 debug_mode 持久化给后续 Verify 步骤",
        errors,
    )
    if path.name == "crawl-dongchedi.yml":
        assert_condition(
            "steps.step2.outputs.failed == 'false' && steps.step2.conclusion == 'success'" not in text,
            f"{path.name} 不得用 step2 failed=false 放行 step3/verify/upload",
            errors,
        )
        assert_condition(
            "find scripts/dongchedi/json -type f \\( -name '*.json' -o -name '*.html' \\) -size +0c" in text
            and "steps.finalize_dongchedi.outputs.has_output == 'true'" in text,
            f"{path.name} 未在有效配置 payload 缓存存在时才执行并发布 step3/4 结果",
            errors,
        )
        step2_section = text.split("id: step2", 1)[1].split("name: Upload Dongchedi", 1)[0]
        debug_incomplete_section = step2_section.split("if [ $EXIT_CODE -eq 10 ]; then", 1)[1].split(
            "Step2 incomplete", 1
        )[0]
        fail_unresolved_section = text.split("name: Fail unresolved step2 error", 1)[1].split(
            "name: Disable proxy", 1
        )[0]
        assert_condition(
            'if [ "$DEBUG_MODE" = "true" ]; then' in debug_incomplete_section
            and 'echo "failed=true" >> "$GITHUB_OUTPUT"' in debug_incomplete_section
            and "github.event.inputs.debug_mode == 'true'" in fail_unresolved_section,
            f"{path.name} debug step2 未完成时未失败关闭",
            errors,
        )
        assert_condition(
            "Mark Dongchedi period complete" in text
            and "steps.step2.outputs.complete == 'true' || steps.retry_step2.outputs.complete == 'true'" in text
            and "dongchedi-partial-data-${CRAWL_DATE}" in text
            and "dongchedi-debug-data-${CRAWL_DATE}-${{ github.run_id }}-${{ github.run_attempt }}" in text
            and "dongchedi-data-${CRAWL_DATE}" in text,
            f"{path.name} 必须仅在 step2/retry_step2 完成时写完成标记，并保持 debug/full/partial artifact 名称互斥",
            errors,
        )

        required_state_paths = (
            "rm -f scripts/dongchedi/progress.json dcd_step2_done",
            "rm -rf scripts/dongchedi/json",
            "path: scripts/dongchedi/json",
            "mkdir -p scripts/dongchedi/json",
            "[ -f scripts/dongchedi/progress.json ]",
            "scripts/dongchedi/json/",
            "scripts/dongchedi/progress.json",
        )
        assert_condition(
            all(required in text for required in required_state_paths),
            f"{path.name} 必须与 crawl_dongchedi.py 的 scripts/dongchedi 状态目录一致",
            errors,
        )
        forbidden_root_paths = (
            "rm -f dongchedi/progress.json",
            "rm -rf dongchedi/json",
            "path: dongchedi/json",
            "mkdir -p dongchedi/json",
            "[ -f dongchedi/progress.json ]",
            "find dongchedi/json",
        )
        assert_condition(
            not any(forbidden in text for forbidden in forbidden_root_paths),
            f"{path.name} 不得读写仓库根 dongchedi 状态目录",
            errors,
        )


def check_yiche_workflow(path: Path, errors: list[str]) -> None:
    data = load_yaml(path)
    text = path.read_text(encoding="utf-8")
    schedules = data.get(True, {}).get("schedule", [])

    assert_condition(not schedules, f"{path.name} 不应继续依赖 GitHub Actions schedule", errors)
    assert_condition("WINDOW_END_BUFFER_SECONDS" in text, f"{path.name} 缺少窗口结束缓冲", errors)
    assert_condition("scripts/crawl_budget.py configure" in text, f"{path.name} 未使用共享窗口预算脚本", errors)
    assert_condition("scripts/crawl_budget.py clamp" in text, f"{path.name} 未按 Action 和窗口综合预算收口", errors)
    assert_condition("group: yiche-crawl-${{ github.ref }}" in text, f"{path.name} concurrency 不得按 run_profile 分组", errors)
    assert_condition(
        "yiche-data-{os.environ['GITHUB_RUN_ID']}-{os.environ['GITHUB_RUN_ATTEMPT']}" in text
        and "yiche-partial-data-{name_match.group(1)}-" in text
        and "name: ${{ steps.verify_yiche.outputs.artifact_name }}" in text,
        f"{path.name} stable/partial artifact 未绑定 date/run_id/run_attempt",
        errors,
    )
    restore_section = text.split("name: Restore authenticated Yiche checkpoint", 1)[1].split("name: Setup environment", 1)[0]
    assert_condition(
        "actions/workflows/crawl-yiche.yml/runs?status=success&per_page=100" in restore_section
        and "git merge-base --is-ancestor" in restore_section
        and "yiche-checkpoint-$CANDIDATE_RUN_ID-$CANDIDATE_ATTEMPT" in restore_section
        and 'run.get("conclusion") != "success"' in restore_section
        and "sha256sum --check --strict" in restore_section
        and "load_resume_checkpoint(" in restore_section
        and 'payload.get("status") != "partial"' in restore_section
        and "自动恢复烟测未找到可认证 checkpoint" in restore_section,
        f"{path.name} 缺少零输入 checkpoint 自动续跑的认证、兼容性或失败关闭边界",
        errors,
    )
    for input_name in ("debug_mode", "crawler_run_id", "crawler_run_attempt", "trigger_source"):
        assert_condition(
            f"-f {input_name}=" in text,
            f"{path.name} dispatch merge 缺少 {input_name}",
            errors,
        )
    assert_condition(
        '--ref "${{ github.ref_name }}"' in text,
        f"{path.name} dispatch merge 未透传当前 workflow ref",
        errors,
    )
    configure_section = text.split("name: Configure crawl window", 1)[1].split("name: 安装依赖", 1)[0]
    assert_condition(
        'echo "DEBUG_MODE=true" >> "$GITHUB_ENV"' in configure_section
        and 'echo "DEBUG_MODE=false" >> "$GITHUB_ENV"' in configure_section,
        f"{path.name} 未将 debug_mode 持久化给后续 Verify 步骤",
        errors,
    )
    run_section = text.split("name: 运行易车爬虫", 1)[1].split("name: Disable proxy for Yiche checkpoint upload", 1)[0]
    assert_condition(
        'series_args=(--max-series "$MAX_SERIES")' in run_section
        and 'series_args=()' in run_section
        and '"${series_args[@]}"' in run_section
        and 'python scripts/crawl_yiche.py --time-limit "$RUN_TIME" --max-series "$MAX_SERIES"' not in run_section,
        f"{path.name} 恢复模式不得继续向 crawl_yiche.py 传 --max-series",
        errors,
    )
    trigger_section = text.split("name: Trigger merge-and-filter workflow", 1)[1]
    assert_condition(
        'MERGE_DEBUG_MODE="${DEBUG_MODE:-false}"' in trigger_section
        and 'if [ "$MERGE_DEBUG_MODE" != "true" ] && [ "${MAX_SERIES:-0}" != "0" ]; then' in trigger_section
        and "-f debug_mode=\"$MERGE_DEBUG_MODE\"" in trigger_section,
        f"{path.name} 有界监督样本未进入 merge debug stable-first 路径",
        errors,
    )


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


def check_dongchedi_reset_script(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    assert_condition(
        'Path(__file__).resolve().parent / "dongchedi" / "progress.json"' in text,
        "reset_dongchedi_progress.py 必须重置爬虫实际使用的 scripts/dongchedi/progress.json",
        errors,
    )
    assert_condition(
        'Path("dongchedi/progress.json")' not in text,
        "reset_dongchedi_progress.py 不得依赖调用方工作目录下的根 dongchedi/progress.json",
        errors,
    )


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
    data = load_yaml(path)
    text = path.read_text(encoding="utf-8")
    inputs = data.get(True, {}).get("workflow_dispatch", {}).get("inputs", {})
    assert_condition(
        {"debug_mode", "crawler_run_id", "crawler_run_attempt", "trigger_source"}.issubset(inputs),
        "merge-and-filter.yml 缺少 debug 精确定位 inputs",
        errors,
    )
    merge_steps = data.get("jobs", {}).get("merge-data", {}).get("steps", [])
    download_steps = [step for step in merge_steps if step.get("name") == "下载最新爬虫数据"]
    download_env = download_steps[0].get("env", {}) if len(download_steps) == 1 else {}
    assert_condition(
        len(download_steps) == 1
        and download_env.get("DEBUG_MODE") == "${{ github.event.inputs.debug_mode || 'false' }}"
        and download_env.get("TRIGGER_SOURCE") == "${{ github.event.inputs.trigger_source }}",
        "merge-and-filter.yml 下载步骤必须精确传递 DEBUG_MODE/TRIGGER_SOURCE partial 去重边界",
        errors,
    )
    assert_condition(
        "download_latest_crawler_artifact.py" in text,
        "merge-and-filter.yml 不应只下载最近一次成功爬虫 run，应扫描最近有效数据 artifact",
        errors,
    )
    assert_condition("MIN_ARTIFACT_DATE" in text, "merge-and-filter.yml 缺少当前半月 artifact 日期限制", errors)
    assert_condition(
        'if [ "$DEBUG_MODE" = "true" ]; then' in text
        and 'AUTOHOME_STABLE_MIN_DATE_ARGS=(--min-date "$MIN_ARTIFACT_DATE")' in text
        and 'DONGCHEDI_STABLE_MIN_DATE_ARGS=(--min-date "$MIN_ARTIFACT_DATE")' in text
        and "AUTOHOME_STABLE_MIN_DATE_ARGS=()" in text
        and "DONGCHEDI_STABLE_MIN_DATE_ARGS=()" in text
        and '"${AUTOHOME_STABLE_MIN_DATE_ARGS[@]}"' in text
        and '"${DONGCHEDI_STABLE_MIN_DATE_ARGS[@]}"' in text,
        "merge-and-filter.yml 未保持两来源独立的普通半月限制与 debug 历史基线回退",
        errors,
    )
    partial_gate_position = text.find('PARTIAL_ARTIFACT_NAME _ PARTIAL_ARTIFACT_SHA256 <<< "${PARTIAL_ARTIFACTS[0]}"')
    stable_download_position = text.find("python scripts/download_latest_crawler_artifact.py")
    source_specific_fallback = """if [ "$PARTIAL_SOURCE" = "autohome" ]; then
                  AUTOHOME_STABLE_MIN_DATE_ARGS=()
                elif [ "$PARTIAL_SOURCE" = "dongchedi" ]; then
                  DONGCHEDI_STABLE_MIN_DATE_ARGS=()
                fi"""
    assert_condition(
        "/attempts/$CRAWLER_RUN_ATTEMPT" in text
        and '"$RUN_STATUS" != "completed"' in text
        and '"$RUN_CONCLUSION" != "success"' in text
        and '"$ARTIFACT_DATE" < "$MIN_ARTIFACT_DATE"' in text
        and '"$ARTIFACT_CREATED_AT" < "$RUN_STARTED_AT"' in text
        and '"$ARTIFACT_CREATED_AT" > "$RUN_UPDATED_AT"' in text
        and source_specific_fallback in text
        and 'if [ "${#PARTIAL_ARTIFACTS[@]}" -gt 1 ]; then' in text
        and partial_gate_position >= 0
        and partial_gate_position < stable_download_position,
        "merge-and-filter.yml 未在下载 stable 前按精确成功 attempt 和当前半月 partial 仅放宽对应来源",
        errors,
    )
    assert_condition(
        "merge-inputs/stable/autohome" in text and "merge-inputs/stable/dongchedi" in text,
        "merge-and-filter.yml 未隔离两个来源的 stable 输入",
        errors,
    )
    assert_condition(
        "ARTIFACT_REGEX=" in text and "gh run download \"$CRAWLER_RUN_ID\"" in text,
        "merge-and-filter.yml 未按指定 run/attempt/source 精确下载 debug artifact",
        errors,
    )
    assert_condition(
        'RUN_PATH="${RUN_PATH%%@*}"' in text,
        "merge-and-filter.yml 未剥离 GitHub run.path 的 @ref 后缀",
        errors,
    )
    prepare_positions = [match.start() for match in re.finditer("python scripts/prepare_debug_merge_inputs.py", text)]
    merge_position = text.find("python scripts/merge_data.py")
    assert_condition(
        len(prepare_positions) == 5,
        "merge-and-filter.yml 未对两个 debug 主源及三来源 partial 分别执行 stable-first 规范化",
        errors,
    )
    assert_condition(
        "^autohome-partial-data-[0-9]{8}$" in text
        and "^dongchedi-partial-data-[0-9]{8}$" in text
        and "^yiche-partial-data-([0-9]{8})-${CRAWLER_RUN_ID}-${CRAWLER_RUN_ATTEMPT}$" in text
        and "merge-inputs/incremental/$PARTIAL_SOURCE" in text
        and "autoHome_partial_prepared.json" in text
        and "dongchedi_partial_prepared.json" in text
        and '"$RUN_PATH" != "$PARTIAL_WORKFLOW"' in text
        and 'actions/artifacts/$PARTIAL_ARTIFACT_ID/zip' in text
        and 'unzip -q "$PARTIAL_ARCHIVE"' in text
        and '--name "$PARTIAL_ARTIFACT_NAME"' not in text
        and "PARTIAL_ARTIFACT_SHA256" in text
        and 'sha256sum --check --strict' in text,
        "merge-and-filter.yml 未将指定 run/attempt/source 的三来源 partial artifact 纳入安全增量合并",
        errors,
    )
    assert_condition(
        '--source yiche --partial --output yiche_partial_prepared.json' in text
        and 'find merge-inputs/incremental/yiche' in text
        and 'if [ "${#YICHE_STABLE[@]}" -eq 1 ]; then' in text
        and "YICHE_PARTIAL_NOT_JOINED" in text
        and "stable identity preservation invariant failed" in (ROOT / "scripts/prepare_debug_merge_inputs.py").read_text(encoding="utf-8"),
        "merge-and-filter.yml 未将易车 partial 与历史 stable 做 identity 防回退合并",
        errors,
    )
    assert_condition(
        text.count("--artifact-prefix autohome-partial-data-") == 1
        and text.count("--artifact-prefix dongchedi-partial-data-") == 1
        and "--output-dir merge-inputs/incremental/autohome" in text
        and "--output-dir merge-inputs/incremental/dongchedi" in text
        and '--min-date "$MIN_ARTIFACT_DATE"' in text
        and '--source autohome --partial --output autoHome_partial_prepared.json' in text
        and '--source dongchedi --partial --output dongchedi_partial_prepared.json' in text
        and "AUTOHOME_PARTIAL_NOT_JOINED" in text
        and "DONGCHEDI_PARTIAL_NOT_JOINED" in text,
        "merge-and-filter.yml 未独立发现并 stable-first 接入两个主源的同半月 partial",
        errors,
    )
    assert_condition(
        "FINAL_AUTOHOME_INPUT" in text
        and "FINAL_DONGCHEDI_INPUT" in text
        and 'test -s "${FINAL_AUTOHOME_INPUT[0]}"' in text
        and 'test -s "${FINAL_DONGCHEDI_INPUT[0]}"' in text,
        "merge-and-filter.yml 缺少合并前双主源输入唯一且非空门禁",
        errors,
    )
    assert_condition(
        bool(prepare_positions) and merge_position != -1 and max(prepare_positions) < merge_position,
        "merge-and-filter.yml 必须先规范化 debug 输入再执行 merge_data.py",
        errors,
    )
    verify_position = text.find("python scripts/verify_publish_superset.py")
    preserve_position = text.find("python scripts/preserve_publish_baseline.py")
    upload_position = text.find("uses: actions/upload-artifact@v4")
    assert_condition(
        verify_position != -1
        and preserve_position != -1
        and upload_position != -1
        and merge_position < preserve_position < verify_position < upload_position
        and "https://cars.jiucai.eu.org/data/latest.json" in text
        and text.count("--retry-all-errors") >= 2
        and "Debug 保留当前 Pages 发布基线" not in text
        and "Debug 发布防缩小校验" not in text,
        "merge-and-filter.yml 缺少 merge 后、artifact/Release 前的全路径基线保留与防缩小校验",
        errors,
    )
    assert_condition(
        "release_tag=v" in text
        and "${{ github.run_id }}" in text
        and "release_tag: ${{ needs.merge-data.outputs.release_tag }}" in text
        and "needs.create-release.outputs.release_tag" in text,
        "merge-and-filter.yml Release tag 未绑定 run_id 或未精确传给 Pages",
        errors,
    )
    assert_condition(
        "mode" in inputs and "merge_and_deploy" in text,
        "merge-and-filter.yml 缺少合并后部署模式",
        errors,
    )


def check_deploy_workflow(path: Path, errors: list[str]) -> None:
    data = load_yaml(path)
    text = path.read_text(encoding="utf-8")
    triggers = data.get(True, {})
    inputs = triggers.get("workflow_dispatch", {}).get("inputs", {})
    push = triggers.get("push", {})
    missing_dependencies = pages_push_paths_cover(path, PAGES_PUSH_DEPENDENCIES)
    assert_condition(not missing_dependencies, f"{path.name} push paths 漏掉 Pages 依赖: {missing_dependencies}", errors)
    assert_condition(not push.get("paths-ignore"), f"{path.name} 不得用 paths-ignore 绕过 Pages 依赖", errors)
    assert_condition("release_tag" in inputs, f"{path.name} 缺少可选 release_tag", errors)
    assert_condition(
        'if [ -n "$RELEASE_TAG" ]; then' in text and 'TAGS=("$RELEASE_TAG")' in text,
        f"{path.name} 有 release_tag 时未限定为精确 tag",
        errors,
    )
    verify_position = text.find("python scripts/verify_publish_superset.py")
    copy_position = text.find('cp "$MERGED_JSON" site/data/latest.json')
    upload_position = text.find("uses: actions/upload-pages-artifact@v5")
    assert_condition(
        verify_position != -1
        and copy_position != -1
        and upload_position != -1
        and verify_position < copy_position < upload_position
        and "https://cars.jiucai.eu.org/data/latest.json" in text
        and "--retry-all-errors" in text,
        f"{path.name} 缺少复制/上传 Pages 数据前的全路径防缩小复核",
        errors,
    )


def check_single_source_repair_workflow(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    assert_condition(
        'DISPATCH_STARTED="$dispatch_started"' in text
        and "BEFORE_RUN_IDS" in text
        and "matches.sort(key=lambda r:" in text
        and 'dispatched_run_id=%s\\n' in text
        and "DISPATCHED_PAGES_RUN_ID" in text,
        f"{path.name} 必须在 dispatch 后按创建时间绑定精确 Pages run_id",
        errors,
    )
    wait_section = text.split("name: Wait for the dispatched Pages run", 1)[1]
    assert_condition(
        'actions/runs/$DISPATCHED_PAGES_RUN_ID' in wait_section
        and "actions/workflows/merge-and-filter.yml/runs?branch=main" not in wait_section,
        f"{path.name} 等待 Pages run 时不得按 head_sha 扫描最新 workflow_dispatch run",
        errors,
    )


def main() -> int:
    errors: list[str] = []
    check_crawler_workflow(ROOT / ".github/workflows/crawl-autohome.yml", errors)
    check_crawler_workflow(ROOT / ".github/workflows/crawl-dongchedi.yml", errors)
    check_yiche_workflow(ROOT / ".github/workflows/crawl-yiche.yml", errors)
    check_trigger(ROOT / ".github/workflows/crawl-trigger.yml", errors)
    check_budget_script(ROOT / "scripts/crawl_budget.py", errors)
    check_merge_workflow(ROOT / ".github/workflows/merge-and-filter.yml", errors)
    check_deploy_workflow(ROOT / ".github/workflows/merge-and-filter.yml", errors)
    check_single_source_repair_workflow(ROOT / ".github/workflows/single-source-repair.yml", errors)
    assert_condition(
        "/scripts/dongchedi/json/" in (ROOT / ".gitignore").read_text(encoding="utf-8"),
        "实际 Dongchedi HTML cache 路径未被 gitignore 排除",
        errors,
    )
    assert_condition(
        '"scripts/dongchedi/progress.json"' in (ROOT / "scripts/git_sync_progress.sh").read_text(encoding="utf-8"),
        "git_sync_progress.sh 未识别实际 Dongchedi progress 冲突路径",
        errors,
    )
    assert_condition((ROOT / "scripts/prepare_debug_merge_inputs.py").exists(), "缺少 debug stable-first 输入脚本", errors)
    assert_condition((ROOT / "scripts/preserve_publish_baseline.py").exists(), "缺少 debug 发布基线保留脚本", errors)
    assert_condition((ROOT / "scripts/verify_publish_superset.py").exists(), "缺少发布防缩小脚本", errors)
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
