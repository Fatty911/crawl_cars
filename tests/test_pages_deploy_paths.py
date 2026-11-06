from pathlib import Path

import json
import os
import shutil
import subprocess
import sys

import pytest
import yaml

from scripts import validate_workflow_expectations as validator

from scripts.validate_workflow_expectations import (
    PAGES_PUSH_DEPENDENCIES,
    pages_push_paths_cover,
    resolve_workflow_file,
)


def test_pages_push_paths_cover_the_traced_build_and_schema_dependencies():
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows/merge-and-filter.yml"
    missing = pages_push_paths_cover(workflow, PAGES_PUSH_DEPENDENCIES)
    assert missing == []


def test_single_source_repair_continues_only_after_bound_pages_success():
    # Actions 停用期该工作流被改名为 .yml.disabled，复用守卫里的解析函数取件
    workflow = resolve_workflow_file(
        Path(__file__).resolve().parents[1]
        / ".github/workflows/single-source-repair.yml"
    ).read_text(encoding="utf-8")
    continuation = workflow.split(
        "      - name: Continue the bounded repair chain\n", 1
    )[1].split("\n      - name: Update published chain state", 1)[0]

    assert "if: steps.pages.outputs.pages_status == 'success'" in continuation
    assert "gh workflow run single-source-repair.yml" in continuation
    assert '-f pages_run_id="${{ steps.pages.outputs.pages_run_id }}"' in continuation
    assert '-f source_sha="${{ steps.push.outputs.commit_sha || github.sha }}"' in continuation


ROOT = Path(__file__).resolve().parents[1]


class _WorkflowDumper(yaml.SafeDumper):
    pass


def _script_string(dumper, value):
    return dumper.represent_scalar("tag:yaml.org,2002:str", value,
                                   style="|" if "\n" in value else None)


_WorkflowDumper.add_representer(str, _script_string)


def _dump(workflow):
    return yaml.dump(workflow, Dumper=_WorkflowDumper, allow_unicode=True, sort_keys=False)


def _steps(workflow):
    return next(iter(workflow["jobs"].values()))["steps"]


def _step(workflow, marker):
    return next(step for step in _steps(workflow)
                if marker in str(step.get("run", "")) + str(step.get("uses", "")))


def _reject_mutation(tmp_path, name, mutate, check):
    workflow = yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
    path = tmp_path / name
    path.write_text(_dump(workflow), encoding="utf-8")
    errors = []
    check(path, errors)
    assert errors == [], "the real workflow must pass before applying the counterexample"
    mutate(workflow)
    path.write_text(_dump(workflow), encoding="utf-8")
    check(path, errors)
    assert errors, "the unsafe counterexample must be rejected"


def test_current_publication_owners_have_complete_guards():
    for name, check in (
        ("merge-and-filter.yml", validator.check_merge_workflow),
        ("remerge-and-publish.yml", validator.check_remerge_publication),
        ("cnb-pages.yml", validator.check_verified_archive_deployment),
        ("deploy-frontend.yml", validator.check_verified_archive_deployment),
        ("AI_Auto_Fix_Monitor.yml", validator.check_ai_monitor),
    ):
        errors = []
        check(ROOT / ".github/workflows" / name, errors)
        assert errors == [], (name, errors)


@pytest.mark.parametrize("broken", ["run_id", "run_attempt", "release_consumer", "inline_pages"])
def test_merge_release_identity_and_returning_inline_consumer_are_guarded(tmp_path, broken):
    # Legacy merge checks include indentation-sensitive shell blocks. Preserve
    # the real source bytes instead of reserializing unrelated shell structure.
    text = (ROOT / ".github/workflows/merge-and-filter.yml").read_text()
    path = tmp_path / "merge-and-filter.yml"
    path.write_text(text)
    errors = []
    validator.check_merge_workflow(path, errors)
    assert errors == []
    if broken in {"run_id", "run_attempt"}:
        tag_line = next(line for line in text.splitlines() if 'echo "release_tag=v' in line)
        text = text.replace(tag_line, tag_line.replace("${{ github." + broken + " }}", "fixed"))
    elif broken == "release_consumer":
        text = text.replace("tag_name: ${{ needs.merge-data.outputs.release_tag }}", "tag_name: latest")
    else:
        text += "\n  unsafe-inline-pages:\n    steps:\n      - uses: actions/deploy-pages@v5\n"
    path.write_text(text)
    validator.check_merge_workflow(path, errors)
    assert errors


@pytest.mark.parametrize("broken", ["exact_tag", "tag_env", "optional_extract", "upload_first", "other_site"])
def test_verified_deploy_rejects_unbound_tags_and_upload_before_validation(tmp_path, broken):
    def mutate(workflow):
        if broken in {"exact_tag", "tag_env"}:
            download = _step(workflow, "python scripts/download_verified_release.py")
            if broken == "exact_tag":
                download["run"] = download["run"].replace('--tag "$RELEASE_TAG"', "")
            else:
                download["env"]["RELEASE_TAG"] = "latest"
        elif broken == "optional_extract":
            _step(workflow, "--archive")["if"] = False
        elif broken == "upload_first":
            steps = _steps(workflow)
            upload = _step(workflow, "actions/upload-pages-artifact@")
            steps.remove(upload)
            steps.insert(0, upload)
        else:
            _step(workflow, "actions/upload-pages-artifact@")["with"]["path"] = "unverified-site"
    _reject_mutation(tmp_path, "cnb-pages.yml", mutate, validator.check_verified_archive_deployment)


def test_frontend_cannot_replace_verified_manifest_or_data(tmp_path):
    def mutate(workflow):
        prepare = _step(workflow, "python scripts/download_verified_release.py")
        prepare["run"] = prepare["run"].replace(
            'relative.parts[0] == "data" or relative.as_posix() == "manifest.json"', "False")
    _reject_mutation(tmp_path, "deploy-frontend.yml", mutate, validator.check_verified_archive_deployment)


@pytest.mark.parametrize("broken", ["strict_identity", "source_evidence", "guard_after_copy",
                                  "audit_after_upload", "attempt", "input_tag", "final_audit"])
def test_remerge_publication_rejects_identity_loss_or_late_guards(tmp_path, broken):
    def mutate(workflow):
        steps = _steps(workflow)
        if broken in {"strict_identity", "source_evidence"}:
            guard = _step(workflow, '--candidate "out/merged_${DATE}.json"')
            missing = ("--strict-identities" if broken == "strict_identity"
                       else "--source-identity-evidence config/source_identity_evidence.json")
            guard["run"] = guard["run"].replace(missing, "")
        elif broken == "input_tag":
            fetch = _step(workflow, 'gh release download "$TAG"')
            fetch["env"]["BASELINE_RELEASE"] = ""
            binding = 'TAG="$BASELINE_RELEASE"'
            assert fetch["run"].count(binding) == 1
            fetch["run"] = fetch["run"].replace(binding, 'TAG=""', 1)
        elif broken == "final_audit":
            assemble = _step(workflow, 'cp "out/merged_${DATE}.json" site/data/latest.json')
            assemble["run"] = assemble["run"].replace("--full-validation", "")
        elif broken == "attempt":
            publish = _step(workflow, "python scripts/publish_github_release.py")
            publish["run"] = publish["run"].replace("${{ github.run_attempt }}", "fixed")
        else:
            marker = ('--candidate "out/merged_${DATE}.json"' if broken == "guard_after_copy"
                      else 'cp "out/merged_${DATE}.json" site/data/latest.json')
            late = _step(workflow, marker)
            steps.remove(late)
            steps.append(late)
    _reject_mutation(tmp_path, "remerge-and-publish.yml", mutate, validator.check_remerge_publication)


@pytest.mark.parametrize("binding", ["exact", "unrelated", "missing"])
def test_remerge_exact_tag_can_use_a_bound_step_environment(tmp_path, binding):
    workflow = yaml.safe_load((ROOT / ".github/workflows/remerge-and-publish.yml").read_text())
    fetch = _step(workflow, 'gh release download "$TAG"')
    expression = "${{ github.event.inputs.release_tag || github.event.release.tag_name }}"
    fetch["run"] = fetch["run"].replace(f'TAG="{expression}"', 'TAG="$BASELINE_RELEASE"')
    fetch["env"] = ({"BASELINE_RELEASE": expression} if binding == "exact"
                    else {"BASELINE_RELEASE": "latest"} if binding == "unrelated" else {})
    path = tmp_path / "remerge-and-publish.yml"
    path.write_text(_dump(workflow))
    errors = []
    validator.check_remerge_publication(path, errors)
    assert bool(errors) == (binding != "exact"), errors


@pytest.mark.parametrize("broken", ["unauthorized", "missing", "success", "paid_action", "dispatch", "no_archive"])
def test_monitor_allows_only_authorized_failure_evidence_workflows(tmp_path, broken):
    def mutate(workflow):
        monitored = workflow[True]["workflow_run"]["workflows"]
        job = workflow["jobs"]["archive_failure"]
        if broken == "unauthorized":
            monitored.append("Unapproved AI repair")
        elif broken == "missing":
            monitored.remove("Runtime proxy cache guard")
        elif broken == "success":
            job["if"] = str(job["if"]) + " || success()"
        elif broken == "paid_action":
            job["steps"].append({"uses": "openai/codex-action@v1"})
        elif broken == "dispatch":
            job["steps"].append({"run": "gh workflow run AI_Auto_Fix_Monitor.yml"})
        else:
            job["steps"][0]["run"] = job["steps"][0]["run"].replace("gh issue create", "echo")
    _reject_mutation(tmp_path, "AI_Auto_Fix_Monitor.yml", mutate, validator.check_ai_monitor)


def test_disabled_single_source_workflow_keeps_its_unique_run_binding_guard(tmp_path):
    source = resolve_workflow_file(ROOT / ".github/workflows/single-source-repair.yml")
    assert source.name.endswith(".disabled")
    disabled = tmp_path / source.name
    disabled.write_bytes(source.read_bytes())
    requested = tmp_path / "single-source-repair.yml"
    errors = []
    validator.check_single_source_repair_workflow(requested, errors)
    assert errors == []
    disabled.write_text(disabled.read_text().replace("DISPATCHED_PAGES_RUN_ID", "UNBOUND_RUN"))
    validator.check_single_source_repair_workflow(requested, errors)
    assert errors, "a disabled suffix must not exempt the legacy consumer from its guard"


def _ci_smoke():
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    return next(s["run"] for s in ci["jobs"]["test"]["steps"]
                if s.get("name") == "Smoke test scripts/merge_data.py")


def test_ci_merge_smoke_uses_only_six_fixture_rows_and_preserves_both_identities(tmp_path):
    # Copy only executable dependencies/config; no crawler data or dealer cache.
    (tmp_path / "scripts").mkdir()
    (tmp_path / "config").mkdir()
    for name in ("merge_data.py", "publish_identity.py", "dealer_price_overlay.py"):
        shutil.copyfile(ROOT / "scripts" / name, tmp_path / "scripts" / name)
    shutil.copyfile(ROOT / "config/filter_conditions.json", tmp_path / "config/filter_conditions.json")
    env = dict(os.environ, TMPDIR=str(tmp_path), PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"])
    result = subprocess.run(["bash", "-e", "-c", _ci_smoke()], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not list(tmp_path.glob("autoHome_*.json"))
    assert not list(tmp_path.glob("merged_*.json"))
    assert not (tmp_path / "docs").exists()


def test_ci_merge_smoke_rejects_duplicate_source_identity_even_with_two_rows(tmp_path):
    assertion = _ci_smoke().rsplit("python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    from datetime import date
    duplicate = {"车款ID": "54529", "车型名称": "CI测试车型", "零整比": "330.50%"}
    for prefix in ("merged", "filtered_cars"):
        (tmp_path / f"{prefix}_{date.today():%Y%m%d}.json").write_text(json.dumps([duplicate, duplicate]))
    result = subprocess.run([sys.executable, "-c", assertion], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert "both distinct source identities" in result.stderr
