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


def resolve_workflow_file(path: Path) -> Path:
    """停用的 GitHub 工作流被改名为 *.yml.disabled（CNB 迁移后禁用了若干条）。

    期望检查仍要针对停用件执行：否则将来重新启用时会带着过期结构上线。
    """
    if path.is_file():
        return path
    disabled = Path(str(path) + ".disabled")
    if disabled.is_file():
        return disabled
    raise FileNotFoundError(f"workflow missing: {path} (also checked {disabled.name})")


def load_yaml(path: Path) -> dict:
    with resolve_workflow_file(path).open("r", encoding="utf-8") as f:
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
    text = resolve_workflow_file(path).read_text(encoding="utf-8")
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
    text = resolve_workflow_file(path).read_text(encoding="utf-8")
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
    text = resolve_workflow_file(path).read_text(encoding="utf-8")
    assert_condition("$((8 * 60))" in text, "crawl-trigger.yml 未使用 08:00 作为上午触发起点", errors)
    assert_condition(WINDOW_TEXT in text, "crawl-trigger.yml 未同步 08:00-12:30 文案", errors)
    assert_condition(AFTERNOON_TEXT in text, "crawl-trigger.yml 未同步 13:00-22:00 文案", errors)
    assert_condition('default: \'all\'' in text or 'default: "all"' in text, "crawl-trigger.yml 默认不应随机漏掉车源", errors)
    assert_condition("crawl-autohome.yml" in text and "crawl-dongchedi.yml" in text, "crawl-trigger.yml 未触发两个主爬虫", errors)
    assert_condition("RANDOM" not in text and "skip_delay" not in text, "crawl-trigger.yml 不应再追加随机启动延迟", errors)


def check_budget_script(path: Path, errors: list[str]) -> None:
    text = resolve_workflow_file(path).read_text(encoding="utf-8")
    assert_condition('"afternoon": (13 * 60, 22 * 60)' in text, "crawl_budget.py 未设置 13:00-22:00 下午窗口", errors)
    assert_condition("MAX_WORKFLOW_SECONDS" in text, "crawl_budget.py 缺少 Action 总时限预算", errors)
    assert_condition("PROGRESS_COMMIT_BUFFER_SECONDS" in text, "crawl_budget.py 缺少进度提交缓冲", errors)


def check_dongchedi_reset_script(path: Path, errors: list[str]) -> None:
    text = resolve_workflow_file(path).read_text(encoding="utf-8")
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
    """红线通道覆盖三条发布链、两条既有保护链和 CI，failure 时只归档证据。

    旧断言要求它监听两条**已停用**的爬虫链并集成付费 Codex Action —— 这两条都是
    "名单里有、实际接不住"的反面教材（停用链不会触发；绿的一轮也会被 `|| success` 拉起）。
    """
    data = load_yaml(path)
    text = resolve_workflow_file(path).read_text(encoding="utf-8")
    workflow_run = data.get(True, {}).get("workflow_run", {})
    workflows = set(workflow_run.get("workflows", []))
    expected = {"重合并并发布（不爬取）", "Deploy verified CNB Pages", "部署前端展示",
                "Markdown privacy (candidate)", "Runtime proxy cache guard", "CI"}

    assert_condition(workflows == expected,
                     "AI 监控名单必须精确覆盖三条发布链、两条保护链和 CI（实际：%s）" % sorted(workflows),
                     errors)
    ifs = " ".join(str(j.get("if") or "") for j in (data.get("jobs") or {}).values())
    assert_condition("failure" in ifs, "AI 监控必须只在 failure 时触发", errors)
    assert_condition("success" not in ifs, "AI 监控的 if 不得包含 success（绿的一轮也会被拉起）", errors)
    assert_condition("gh issue create" in text, "AI 监控缺少开 Issue 的归档腿", errors)
    assert_condition("openai/codex-action" not in text,
                     "AI 监控不得调用付费模型 Action（这一腿只归档证据）", errors)
    assert_condition("issues: write" in text, "AI 监控缺少 issues: write 权限，开不了 Issue", errors)
    for job in data.get("jobs", {}).values():
        condition = re.sub(r"[\s${}]+", "", str(job.get("if", "")))
        assert_condition(
            condition == "github.event.workflow_run.head_branch=='main'&&github.event.workflow_run.conclusion=='failure'",
            "AI 监控必须仅在 main 的失败 run 归档，不得用 OR 扩大触发", errors,
        )
        for step in job.get("steps", []):
            action = str(step.get("uses", "")).split("@", 1)[0]
            assert_condition(action in {"", "actions/checkout", "actions/upload-artifact"},
                             "AI 监控不得调用修复或付费 Action", errors)
            assert_condition(not re.search(r"gh\s+workflow\s+run|git\s+push|\b(?:codex|opencode)\s|npc:go|/dispatches", str(step.get("run", ""))),
                             "AI 监控只可归档证据，不得自驱修复或 dispatch", errors)


def check_merge_workflow(path: Path, errors: list[str]) -> None:
    data = load_yaml(path)
    text = resolve_workflow_file(path).read_text(encoding="utf-8")
    inputs = data.get(True, {}).get("workflow_dispatch", {}).get("inputs", {})
    missing = pages_push_paths_cover(path, PAGES_PUSH_DEPENDENCIES)
    push = data.get(True, {}).get("push", {})
    assert_condition(not missing, f"{path.name} push paths 漏掉 Pages 依赖: {missing}", errors)
    assert_condition(not push.get("paths-ignore"), f"{path.name} 不得用 paths-ignore 绕过 Pages 依赖", errors)
    assert_condition("release_tag" in inputs, f"{path.name} 缺少可选 release_tag", errors)
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
        "^yiche-(data|partial-data-[0-9]{8})-${CRAWLER_RUN_ID}-${CRAWLER_RUN_ATTEMPT}$" in text,
        "merge-and-filter.yml debug 易车入口未接受 yiche partial artifact",
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
        and "$PAGES_URL/data/latest.json" in text
        and text.count("--retry-all-errors") >= 2
        and "Debug 保留当前 Pages 发布基线" not in text
        and "Debug 发布防缩小校验" not in text,
        "merge-and-filter.yml 缺少 merge 后、artifact/Release 前的全路径基线保留与防缩小校验",
        errors,
    )
    jobs = data.get("jobs", {})
    producer = jobs.get("merge-data", {})
    release = jobs.get("create-release", {})
    date_run = "\n".join(str(step.get("run", "")) for step in merge_steps if step.get("id") == "date")
    tag_line = next((line for line in date_run.splitlines() if 'echo "release_tag=v' in line), "")
    release_steps = [step for step in release.get("steps", [])
                     if str(step.get("uses", "")).startswith("softprops/action-gh-release@")]
    assert_condition(
        "${{ github.run_id }}" in tag_line and "${{ github.run_attempt }}" in tag_line
        and producer.get("outputs", {}).get("release_tag") == "${{ steps.date.outputs.release_tag }}"
        and "merge-data" in release.get("needs", [])
        and release.get("outputs", {}).get("release_tag") == "${{ needs.merge-data.outputs.release_tag }}"
        and len(release_steps) == 1
        and release_steps[0].get("with", {}).get("tag_name") == "${{ needs.merge-data.outputs.release_tag }}",
        "merge-and-filter.yml Release tag 必须绑定 run_id/run_attempt 并精确传给 Release 生产者",
        errors,
    )
    # A producer without a Pages job does not consume its own Release. If an
    # inline consumer returns (including a disabled workflow), retain its guards.
    if any(str(step.get("uses", "")).startswith("actions/deploy-pages@")
           for job in jobs.values() for step in job.get("steps", [])):
        assert_condition("needs.create-release.outputs.release_tag" in text,
                         "inline Pages 必须消费本轮 create-release 的精确 tag", errors)
        check_deploy_workflow(path, errors)
    assert_condition(
        "mode" in inputs and "merge_and_deploy" in text,
        "merge-and-filter.yml 缺少合并后部署模式",
        errors,
    )


def publication_run(step: dict) -> str:
    lines = (line for line in str(step.get("run", "")).splitlines()
             if not line.lstrip().startswith("#"))
    return "\n".join(lines).replace("\\\n", " ")


def publication_step(steps: list[dict], marker: str, path: Path, errors: list[str]) -> tuple[int, dict]:
    """Locate a required operation in its job, excluding shell comment lines."""
    matches = [(i, step) for i, step in enumerate(steps)
               if (str(step.get("uses", "")).startswith(marker) if marker.startswith("actions/")
                   else marker in publication_run(step))]
    assert_condition(len(matches) == 1, f"{path.name} 必须唯一执行 {marker}", errors)
    if len(matches) != 1:
        return -1, {}
    index, step = matches[0]
    assert_condition("if" not in step and not step.get("continue-on-error"),
                     f"{path.name} {marker} 不得跳过或吞错误", errors)
    run = str(step.get("run", ""))
    assert_condition("|| true" not in run, f"{path.name} {marker} 不得吞错误", errors)
    return index, step


def check_verified_archive_deployment(path: Path, errors: list[str]) -> None:
    """Deployers consume attested bytes; data-changing audits belong to producers."""
    data = load_yaml(path)
    frontend = path.name == "deploy-frontend.yml"
    job_id, directory, site = ("deploy-frontend", "release-files", "site") if frontend else ("deploy", "release", "cnb-site")
    steps = data.get("jobs", {}).get(job_id, {}).get("steps", [])
    download_i, download = publication_step(steps, "python scripts/download_verified_release.py", path, errors)
    extract_i, extract = publication_step(steps, "python scripts/prepare_cnb_pages.py --archive", path, errors)
    upload_i, upload = publication_step(steps, "actions/upload-pages-artifact@", path, errors)
    deploy_i, _ = publication_step(steps, "actions/deploy-pages@", path, errors)
    verify_i, verify = publication_step(steps, f'--site {site} --verify-url "$PAGE_URL"', path, errors)
    download_run = str(download.get("run", "")).replace("\\\n", " ")
    extract_run = str(extract.get("run", ""))
    assert_condition(
        0 <= download_i <= extract_i < upload_i < deploy_i < verify_i
        and upload.get("with", {}).get("path") == site
        and f'--archive {directory}/verified-site.zip --manifest {directory}/manifest.json --site {site}' in extract_run
        and f'--dir {directory}' in download_run
        and f'--site {site} --verify-url "$PAGE_URL"' in str(verify.get("run", "")),
        f"{path.name} 必须先验证完整 Release 及 manifest 再上传同一目录，部署后回读", errors,
    )
    if frontend:
        assert_condition(
            0 <= extract_run.find("prepare_cnb_pages.py") < extract_run.find('Path("docs")')
            and 'relative.parts[0] == "data" or relative.as_posix() == "manifest.json"' in extract_run
            and 'cmp release-files/manifest.json site/data/manifest.json' in extract_run
            and "set -euo pipefail" in extract_run,
            f"{path.name} 前端覆盖不得修改已验证数据和 manifest", errors,
        )
    else:
        inputs = data.get(True, {}).get("workflow_dispatch", {}).get("inputs", {})
        assert_condition(
            "release_tag" in inputs
            and download.get("env", {}).get("RELEASE_TAG") == "${{ inputs.release_tag }}"
            and '--tag "$RELEASE_TAG"' in download_run and "--no-legacy" in download_run
            and "||" not in download_run and "--verify-data" in str(verify.get("run", "")),
            f"{path.name} 显式 release_tag 必须精确传给 fail-closed 下载器，禁止 latest 兜底", errors,
        )


def check_remerge_publication(path: Path, errors: list[str]) -> None:
    """The saved-input producer owns identity conservation before Pages/Release."""
    data = load_yaml(path)
    job = data.get("jobs", {}).get("remerge-and-publish", {})
    triggers = data.get(True, {})
    raw_input = triggers.get("workflow_dispatch", {}).get("inputs", {}).get("aws_raw_release", {})
    assert_condition(
        set(triggers) == {"workflow_dispatch"} and raw_input.get("required") is True
        and raw_input.get("type") == "string"
        and job.get("if") == "${{ github.ref == 'refs/heads/main' }}",
        f"{path.name} 必须由 main 的显式 AWS 制品输入触发，不得定时重放旧基线", errors,
    )
    steps = job.get("steps", [])
    fetch_i, fetch = publication_step(steps, '--archive src-data/verified-release/verified-site.zip', path, errors)
    ingest_i, ingest = publication_step(steps, 'scripts/aws_raw_bundle.py publish-github --check-only', path, errors)
    merge_i, _ = publication_step(steps, "python scripts/remerge_published_data.py", path, errors)
    guard_i, guard = publication_step(steps, '--candidate "out/merged_${DATE}.json"', path, errors)
    assemble_i, assemble = publication_step(steps, 'cp "out/merged_${DATE}.json" site/data/latest.json', path, errors)
    upload_i, upload = publication_step(steps, "actions/upload-pages-artifact@", path, errors)
    deploy_i, _ = publication_step(steps, "actions/deploy-pages@", path, errors)
    publish_i, publish = publication_step(steps, "python scripts/publish_github_release.py", path, errors)
    fetch_run = str(fetch.get("run", "")).replace("\\\n", " ")
    assert_condition(
        fetch.get("env", {}).get("BASELINE_RELEASE") == "${{ inputs.release_tag }}"
        and 'TAG="$BASELINE_RELEASE"' in fetch_run and 'if [ -z "$TAG" ]; then' in fetch_run
        and "--no-legacy --print-tag" in fetch_run and '--tag "$TAG" --no-legacy' in fetch_run
        and "python scripts/prepare_cnb_pages.py" in fetch_run
        and "--manifest src-data/verified-release/manifest.json" in fetch_run
        and "set -euo pipefail" in fetch_run and "gh release download" not in fetch_run,
        f"{path.name} 必须使用精确 tag 或最新完整验证归档，失败不得退回未验证输入", errors,
    )
    ingest_run = publication_run(ingest)
    assert_condition(
        ingest.get("env", {}).get("RAW_RELEASE") == "${{ inputs.aws_raw_release }}"
        and ingest.get("env", {}).get("BASELINE") == "${{ steps.correct_source_identities.outputs.src }}"
        and ingest.get("env", {}).get("BASELINE_FILTERED") == "${{ steps.correct_source_identities.outputs.filtered }}"
        and "if" not in ingest and "set -euo pipefail" in ingest_run
        and 0 <= ingest_run.find("publish-github --check-only") < ingest_run.find("python scripts/merge_data.py")
        < ingest_run.find('scripts/preserve_publish_baseline.py --partial-input --baseline "$BASELINE"')
        and 'echo "filtered=$BASELINE_FILTERED"' in ingest_run
        and assemble.get("env", {}).get("RAW_WIDE") == "${{ steps.ingest_aws.outputs.src }}",
        f"{path.name} 必须先验收 AWS 原始制品再合并", errors,
    )
    guard_run = publication_run(guard)
    assembly = publication_run(assemble)
    audit_latest = 'python scripts/audit_pages_payload.py'
    audits = [line.strip() for line in assembly.splitlines() if line.strip().startswith(audit_latest)]
    final_audits = all(
        any(f'--baseline "{baseline}"' in command and f'--candidate site/data/{name}.json' in command
            and '--head-sha "$GITHUB_SHA" --full-validation' in command
            and '--source-identity-evidence config/source_identity_evidence.json' in command
            and 0 <= assembly.find(f'--input site/data/{name}.json') < assembly.find(command)
            for command in audits)
        for name, baseline in (("latest", "baseline-${DATE}.json"),
                               ("filtered", "baseline-filtered-${DATE}.json"))
    )
    assert_condition(
        0 <= fetch_i < ingest_i < merge_i < guard_i < assemble_i < upload_i < deploy_i < publish_i
        and upload.get("with", {}).get("path") == "site"
        and "set -euo pipefail" in guard_run and "set -euo pipefail" in assembly
        and "python scripts/verify_publish_superset.py" in guard_run
        and '--baseline "baseline-${DATE}.json"' in guard_run and "--strict-identities" in guard_run
        and '--source-identity-evidence config/source_identity_evidence.json' in guard_run
        and '--candidate site/data/filtered.json --strict-identities' in assembly
        and '--wide-baseline "$RAW_WIDE"' in assembly
        and len(audits) == 2 and final_audits
        and assembly.count("--full-validation") == 2
        and '--candidate site/data/latest.json' in assembly
        and '--candidate site/data/filtered.json' in assembly
        and assembly.find("prepare_pages_payload.py") < assembly.find(audit_latest),
        f"{path.name} 必须在站点上传/Release 前执行严格身份守恒、防缩小及最终两份数据审计", errors,
    )
    published = str(publish.get("run", ""))
    assert_condition(
        assemble.get("env", {}).get("INPUT_RELEASE") == "${{ steps.fetch.outputs.tag }}"
        and 'echo "tag=$TAG" >> "$GITHUB_OUTPUT"' in fetch_run
        and 'TAG="cnb-data-${DATE}-remerged-verified-r${{ github.run_id }}a${{ github.run_attempt }}"' in published
        and '--site-dir site --repo "$GITHUB_REPOSITORY" --tag "$TAG" --ref "$GITHUB_SHA"' in published,
        f"{path.name} verified Release 必须绑定本轮 run_id/run_attempt 和已审计的同一 site", errors,
    )


def check_deploy_workflow(path: Path, errors: list[str]) -> None:
    data = load_yaml(path)
    text = resolve_workflow_file(path).read_text(encoding="utf-8")
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
        and "$PAGES_URL/data/latest.json" in text
        and "--retry-all-errors" in text,
        f"{path.name} 缺少复制/上传 Pages 数据前的全路径防缩小复核",
        errors,
    )


def read_workflow_text(path: Path, errors: list[str]) -> str | None:
    """GitHub 工作流停用时文件被改名为 *.yml.disabled（CNB 迁移后禁用了部分 GitHub 工作流）。

    期望检查仍必须对停用件生效：否则将来重新启用时会带着过期结构上线。
    两种文件名都不存在时记为错误而不是抛异常，避免校验器本身崩溃。
    """
    try:
        return resolve_workflow_file(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        errors.append(f"{path.name}: expected workflow is missing (also checked {path.name}.disabled)")
    errors.append(f"{path.name}: expected workflow is missing (also checked {path.name}.disabled)")
    return None


def check_single_source_repair_workflow(path: Path, errors: list[str]) -> None:
    text = read_workflow_text(path, errors)
    if text is None:
        return
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
    check_remerge_publication(ROOT / ".github/workflows/remerge-and-publish.yml", errors)
    check_verified_archive_deployment(ROOT / ".github/workflows/cnb-pages.yml", errors)
    check_verified_archive_deployment(ROOT / ".github/workflows/deploy-frontend.yml", errors)
    # Actions 停用期（2026-10-05 用户裁定）把该工作流改名为 .yml.disabled，
    # 守卫必须继续校验它，否则改名即等于护栏失效。
    check_single_source_repair_workflow(
        resolve_workflow_file(ROOT / ".github/workflows/single-source-repair.yml"), errors
    )
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
