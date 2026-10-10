import json
import os
import shutil
from pathlib import Path
import subprocess

import pytest
import yaml

from scripts import finalize_npc_repair as repair


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    files = {
        ".cnb.yml": "main:\n  api_trigger:\n    - stages: [{name: normal, script: echo original}]\n      failStages: [{name: guard, script: echo protected}]\n  'crontab: 5 8 1,16 * *':\n    - failStages: [{name: guard, script: echo protected}]\n",
        "scripts/task.py": "VALUE = 1\n",
        "scripts/finalize_npc_repair.py": "# safety\n",
        "scripts/check_npc_free_quota.py": "# safety\n",
        "tests/test_original.py": "def test_original():\n    assert True\n",
        "AGENTS.md": "protected rules\n",
        "ai_tools/config.json": "{}\n",
        "docs/app.js": "const x = 1;\n",
    }
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                    "-c", "core.hooksPath=", "commit", "-qm", "fixture"], cwd=root, check=True)
    state = tmp_path / "state"
    repair.snapshot(root, state)
    return root, state


def mock_checks(command, **kwargs):
    return subprocess.CompletedProcess(command, 0, stdout="actual mocked executor success\n")


def proposal(root, state):
    (root / "scripts/task.py").write_text("VALUE = 2\n", encoding="utf-8")
    (root / "_fix_report_.md").write_text("Root cause and minimal fix\n", encoding="utf-8")
    repair.validate(root, state, runner=mock_checks)
    (root / "_review_result_.md").write_text("VERDICT: PASS\nIndependent evidence\n", encoding="utf-8")


def test_machine_allows_verified_reviewed_real_code_change(repo):
    root, state = repo
    proposal(root, state)
    assert repair.approved_changes(root, state) == ["scripts/task.py"]
    assert (state / "protected/tests/test_original.py").read_bytes() == (root / "tests/test_original.py").read_bytes()


@pytest.mark.parametrize("name", ["tests/test_original.py", "tests/test_new.py", "AGENTS.md",
    "ai_tools/config.json", "scripts/finalize_npc_repair.py", "scripts/check_npc_free_quota.py",
    "scripts/task.test.js", "scripts/test_hidden.py", "config/opencode.json"])
def test_rejects_protected_tracked_or_untracked_changes(repo, name):
    root, state = repo
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="PROTECTED_OR_UNAPPROVED"):
        repair.changed_files(root, json.loads((state / "baseline.json").read_text()))


def test_rejects_no_repair_and_cannot_claim_success(repo):
    root, state = repo
    with pytest.raises(ValueError, match="NO_REPAIR_CHANGES"):
        repair.validate(root, state, runner=mock_checks)


def test_allows_normal_workflow_fix_but_protects_fail_chain(repo):
    root, state = repo
    config = root / ".cnb.yml"
    config.write_text(config.read_text().replace("echo original", "echo repaired"), encoding="utf-8")
    baseline = json.loads((state / "baseline.json").read_text())
    assert repair.changed_files(root, baseline)[0] == [".cnb.yml"]
    config.write_text(config.read_text().replace("echo protected", "echo bypassed"), encoding="utf-8")
    with pytest.raises(ValueError, match="safety chains"):
        repair.changed_files(root, baseline)


def test_actual_test_exit_code_blocks_validation(repo):
    root, state = repo
    (root / "scripts/task.py").write_text("VALUE = 2\n")
    def failed(command, **kwargs):
        return subprocess.CompletedProcess(command, 7, stdout="failed pytest\n")
    with pytest.raises(subprocess.CalledProcessError) as failure:
        repair.validate(root, state, runner=failed)
    assert failure.value.returncode == 7
    assert not (state / "validated.json").exists()


@pytest.mark.parametrize("first", ["VERDICT: FAIL", " PASS", "VERDICT: PASSING", "Evidence: PASS"])
def test_exact_review_verdict_required(repo, first):
    root, state = repo
    proposal(root, state)
    (root / "_review_result_.md").write_text(first + "\n")
    with pytest.raises(ValueError, match="exactly"):
        repair.approved_changes(root, state)


def test_reviewer_cannot_change_source_or_repair_report(repo):
    root, state = repo
    proposal(root, state)
    (root / "scripts/task.py").write_text("VALUE = 3\n")
    with pytest.raises(ValueError, match="reviewer changed source"):
        repair.approved_changes(root, state)
    (root / "scripts/task.py").write_text("VALUE = 2\n")
    (root / "_fix_report_.md").write_text("reviewer tampered\n")
    with pytest.raises(ValueError, match="repair report"):
        repair.approved_changes(root, state)


@pytest.mark.parametrize("value", ["2", "3", "-1", "x", ""])
def test_bounded_retry_rejects_exhausted_or_invalid_counter(value):
    with pytest.raises(ValueError):
        repair.next_retry(value)


def test_finalize_retry_cap_blocks_before_any_git_mutation(repo, monkeypatch):
    root, state = repo
    monkeypatch.setenv("NPC_BUDGET_STATE", "RUN")
    monkeypatch.setenv("RETRY_COUNT", "2")
    def forbidden_git(*args):
        raise AssertionError("must not invoke git after retry cap")
    monkeypatch.setattr(repair, "git", forbidden_git)
    with pytest.raises(ValueError, match="RETRY_CAP_REACHED"):
        repair.finalize(root, state)


def test_retry_pins_sha_and_nested_env_and_checks_acceptance():
    captured = {}
    class Response:
        status = 201
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return b'{"success":true,"sn":"cnb-fixture"}'
    def open_request(request, timeout):
        captured["body"] = json.loads(request.data)
        captured["request"] = request
        return Response()
    repair.start_retry("a" * 40, 2, "secret", "main", "true", opener=open_request)
    assert captured["body"] == {"branch": "main", "event": "api_trigger", "sha": "a" * 40,
        "env": {"RETRY_COUNT": "2", "DEBUG_MODE": "true"}}
    assert "secret" not in captured["request"].full_url


@pytest.mark.parametrize("status,body", [(500, b'{}'), (200, b'not-json'), (200, b'{"success":false}'),
                                        (200, b'{"success":true}')])
def test_retry_rejects_bad_http_json_or_unaccepted_build(status, body):
    class Response:
        def __init__(self):
            self.status = status
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return body
    with pytest.raises((ValueError, json.JSONDecodeError)):
        repair.start_retry("a" * 40, 1, "secret", "main", "false", opener=lambda *args, **kwargs: Response())


def test_finalize_uses_special_token_clean_push_url_and_only_validated_paths(repo, monkeypatch):
    root, state = repo
    proposal(root, state)
    monkeypatch.setenv("NPC_BUDGET_STATE", "RUN")
    monkeypatch.setenv("RETRY_COUNT", "1")
    monkeypatch.setenv("CNB_BRANCH", "main")
    monkeypatch.setenv("CNB_TOKEN", "limited-platform-token")
    monkeypatch.setenv("CNB_AUTOFIX_TOKEN", "special-secret")
    original_git = repair.git
    fixture_sha = original_git(root, "rev-parse", "HEAD")
    calls = []
    def git_mock(root, *args):
        calls.append(args)
        if args[:1] == ("commit",):
            return "committed"
        if args[:1] == ("diff-tree",):
            return "scripts/task.py"
        if args[:1] == ("rev-parse",):
            return fixture_sha
        return ""
    monkeypatch.setattr(repair, "git", git_mock)
    monkeypatch.setattr(repair, "approved_changes", lambda *args: ["scripts/task.py"])
    pushes = []
    def push(command, **kwargs):
        pushes.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(repair.subprocess, "run", push)
    retries = []
    monkeypatch.setattr(repair, "start_retry", lambda *args: retries.append(args) or {"success": True, "sn": "cnb-test"})
    repair.finalize(root, state)
    assert retries[0][1:4] == (2, "special-secret", "main")
    assert pushes[0][0] == ["git", "push", "https://cnb.cool/xuerui911-mirror/crawl_cars.git", "HEAD:refs/heads/main"]
    assert pushes[0][1]["env"]["CNB_TOKEN"] == "special-secret"
    commit = next(args for args in calls if args[0] == "commit")
    assert "--only" in commit and commit[-1] == "scripts/task.py"


def test_both_fail_chains_use_shared_safe_order_and_distinct_models():
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / ".cnb.yml").read_text(encoding="utf-8"))
    chain = config["main"]["api_trigger"][0]["failStages"]
    assert chain == config["main"]["crontab: 5 8 1,16 * *"][0]["failStages"]
    names = [stage["name"] for stage in chain]
    assert names.index("备份受保护文件及固定安全检查器") < names.index("AI-修复-第1轮")
    assert names.index("验证-实际pytest及Node和语法") < names.index("NPC审核前免费额度复查") < names.index("审查-GLM只读交叉评审")
    models = [stage["options"]["model"] for stage in chain if stage.get("type") == "npc:go"]
    assert models == ["deepseek-v4.1-flash", "glm-5.3-flash"]
    for stage in chain:
        if stage.get("type") == "npc:go" or stage["name"].startswith("最终门禁"):
            assert stage["if"] == '[ "$NPC_BUDGET_STATE" = "RUN" ]'
    quota = next(stage for stage in chain if stage["name"] == "NPC免费额度前置门禁")
    review_quota = next(stage for stage in chain if stage["name"] == "NPC审核前免费额度复查")
    assert review_quota["script"] == quota["script"]
    assert review_quota["exports"] == quota["exports"]
    assert review_quota["if"] == '[ "$NPC_BUDGET_STATE" = "RUN" ]'
    assert next(stage for stage in chain if stage["name"] == "AI-修复-第1轮")["options"]["maxTurns"] == 120
    assert quota["exports"] == {"budget_state": "NPC_BUDGET_STATE"}
    assert '--unpaid-budget-confirmed --reserve-milli 50000' in quota["script"]
    assert '[ "$rc" -eq 20 ]' in quota["script"]
    assert 'CNB_AUTOFIX_TOKEN' in quota["script"]
    assert "重触发-自动重跑" not in names


@pytest.mark.parametrize("code,reason,expected_code,state", [
    (0, "READY_FREE_ONLY", 0, "RUN"),
    (20, "FREE_QUOTA_EXHAUSTED", 0, "FREE_QUOTA_EXHAUSTED"),
    (21, "FREE_BUDGET_INSUFFICIENT", 21, None),
    (30, "AUTHENTICATION_FAILED", 30, None),
])
def test_quota_stage_real_shell_preserves_distinct_exit_states(tmp_path, code, reason, expected_code, state):
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / ".cnb.yml").read_text(encoding="utf-8"))
    quota = next(stage for stage in config["main"]["api_trigger"][0]["failStages"]
                 if stage["name"] == "NPC免费额度前置门禁")
    mock = tmp_path / "scripts/check_npc_free_quota.py"
    mock.parent.mkdir()
    mock.write_text("import json,os,sys\nfrom pathlib import Path\n"
        "dest = sys.argv[sys.argv.index('--report-json')+1]\n"
        "Path(dest).write_text(json.dumps({'reason':os.environ['MOCK_REASON']}))\n"
        "assert os.environ['CNB_TOKEN'] == 'special-test-token'\n"
        "raise SystemExit(int(os.environ['MOCK_CODE']))\n", encoding="utf-8")
    import sys
    script = quota["script"].replace("/tmp/cars-npc-quota.json", (tmp_path / "quota.json").as_posix())
    script = script.replace("python ", '"' + Path(sys.executable).as_posix() + '" ')
    environment = dict(os.environ, RETRY_COUNT="0", MOCK_CODE=str(code), MOCK_REASON=reason,
                       CNB_TOKEN="limited-token", CNB_AUTOFIX_TOKEN="special-test-token")
    shell = shutil.which("bash")
    if not shell:
        pytest.skip("requires bash for the CNB shell integration test")
    process = subprocess.run([shell, "-c", script], cwd=tmp_path,
                             env=environment, text=True, capture_output=True)
    assert process.returncode == expected_code, process.stdout + process.stderr
    if state:
        assert "##[set-output budget_state=" + state + "]" in process.stdout
    else:
        assert reason in process.stdout
        assert "set-output budget_state=RUN" not in process.stdout
        assert "set-output budget_state=FREE_QUOTA_EXHAUSTED" not in process.stdout
    assert "special-test-token" not in process.stdout + process.stderr
