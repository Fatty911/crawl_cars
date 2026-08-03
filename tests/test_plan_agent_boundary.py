from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_plan_agent_boundary.py"


def _validator():
    spec = importlib.util.spec_from_file_location("plan_agent_boundary", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_plan_credentials_are_agent_only():
    errors = _validator().validate_repository(ROOT)
    assert errors == [], "\\n".join(errors)


def test_validator_rejects_generic_plan_secret_in_run(tmp_path):
    module = _validator()
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    workflow = workflow_dir / "bad.yml"
    workflow.write_text(
        """name: bad
jobs:
  bad:
    runs-on: ubuntu-latest
    steps:
      - name: Bad Agent
        run: opencode run --pure --agent plan --model acme/model --dir \"$RUNNER_TEMP/opencode-agent\" --file prompt.md \"${{ secrets.ACME_CODINGPLAN_API_KEY }}\" > out.txt
""",
        encoding="utf-8",
    )
    errors = []
    module._check_workflow(workflow, errors, tmp_path)
    assert any("ACME_CODINGPLAN_API_KEY" in error and "env" in error for error in errors)


def test_validator_recursively_rejects_plan_secret_in_python(tmp_path):
    module = _validator()
    nested = tmp_path / "scripts" / "nested"
    nested.mkdir(parents=True)
    (nested / "worker.py").write_text(
        "PLAN = 'ACMEPLAN_API_KEY'\n",
        encoding="utf-8",
    )
    errors = module.validate_repository(tmp_path)
    assert any("worker.py" in error and "ACMEPLAN_API_KEY" in error for error in errors)


def test_validator_recognizes_plan_credential_suffix_variants():
    module = _validator()
    assert all(
        module._is_plan_key(value)
        for value in (
            "ACME_CODINGPLAN_API_KEY",
            "ACME_AGENTPLAN_TOKEN",
            "ACME_PLAN_SECRET",
        )
    )
    assert not module._is_plan_key("ACME_API_KEY")


def test_legacy_python_fixer_rejects_plan_prefixes():
    from scripts.auto_fix_workflow import is_plan_prefix

    assert all(
        is_plan_prefix(prefix)
        for prefix in (
            "VOLCENGINE_AGENTPLAN",
            "KIMI_CODINGPLAN",
            "MINIMAX_CODING_PLAN",
            "TENCENT_TOKENPLAN",
            "ACMEPLAN",
            "EXAMPLE_PLAN",
        )
    )
    assert not is_plan_prefix("NVIDIA_NIM")
