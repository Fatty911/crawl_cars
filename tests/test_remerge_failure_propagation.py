import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow_command(needle):
    config = yaml.safe_load((ROOT / ".github/workflows/remerge-and-publish.yml").read_text(encoding="utf-8"))
    for step in config["jobs"]["remerge-and-publish"]["steps"]:
        lines = step.get("run", "").splitlines()
        for index, line in enumerate(lines):
            if line.strip().startswith(needle):
                command = [line]
                while command[-1].rstrip().endswith("\\"):
                    index += 1
                    command.append(lines[index])
                return "\n".join(command)
    raise AssertionError("required verification command is missing: " + needle)


@pytest.mark.parametrize("needle", ["python scripts/audit_pages_payload.py", "python scripts/prepare_cnb_pages.py --site site --verify-url"])
def test_real_shell_does_not_convert_verification_failure_to_success(needle):
    bash = str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe") if os.name == "nt" else shutil.which("bash")
    if not bash or not Path(bash).is_file():
        pytest.skip("bash is required for the actual workflow shell failure injection")
    command = workflow_command(needle)
    prelude = "set -euo pipefail\nDATE=20261015\nGITHUB_SHA=test\nPAGE_URL=https://example.invalid\npython() { return 23; }\n"
    result = subprocess.run([bash, "--noprofile", "--norc", "-c", prelude + command], capture_output=True)
    assert result.returncode == 23, result.stdout + result.stderr
    negative = subprocess.run([bash, "--noprofile", "--norc", "-c", prelude + command + " || true"], capture_output=True)
    assert negative.returncode == 0


@pytest.mark.parametrize("script,required", [
    ("verify_publish_superset.py", "--strict-identities"),
    ("audit_pages_payload.py", "--full-validation"),
])
def test_filtered_gate_uses_original_wide_and_original_filtered_and_propagates_failure(tmp_path, script, required):
    import yaml
    config = yaml.safe_load((ROOT / ".github/workflows/remerge-and-publish.yml").read_text(encoding="utf-8"))
    step = next(s for s in config["jobs"]["remerge-and-publish"]["steps"] if s["name"] == "组装发布站点")
    assert step["env"]["RAW_WIDE"] == "${{ steps.fetch.outputs.src }}"
    lines = step["run"].splitlines()
    commands = []
    for i, line in enumerate(lines):
        if line.strip().startswith("python scripts/" + script):
            command = [line]
            while command[-1].rstrip().endswith("\\"):
                i += 1
                command.append(lines[i])
            if "site/data/filtered.json" in "\n".join(command):
                commands.append("\n".join(command))
    assert len(commands) == 1
    bash = str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe") if os.name == "nt" else shutil.which("bash")
    if not bash or not Path(bash).is_file():
        pytest.skip("bash is required for the actual workflow shell failure injection")
    args_file = tmp_path / "args.txt"
    env = dict(os.environ, TEST_ARGS=args_file.as_posix())
    shell = 'set -euo pipefail\nDATE=20261015\nGITHUB_SHA=test\nRAW_WIDE=original-wide.json\npython() { printf "%s\\n" "$@" > "$TEST_ARGS"; return 23; }\n'
    result = subprocess.run([bash, "--noprofile", "--norc", "-c", shell + commands[0]], env=env, capture_output=True)
    assert result.returncode == 23, result.stdout + result.stderr
    args = args_file.read_text(encoding="utf-8").splitlines()
    assert args[args.index("--baseline") + 1] == "baseline-filtered-20261015.json"
    assert args[args.index("--wide-baseline") + 1] == "original-wide.json"
    assert args[args.index("--candidate") + 1] == "site/data/filtered.json"
    assert required in args


def test_raw_source_correction_precedes_merge_and_keeps_original_input_immutable():
    config = yaml.safe_load((ROOT / ".github/workflows/remerge-and-publish.yml").read_text(encoding="utf-8"))
    steps = config["jobs"]["remerge-and-publish"]["steps"]
    before = next(i for i, s in enumerate(steps) if s.get("id") == "correct_source_identities")
    merge = next(i for i, s in enumerate(steps) if s.get("id") == "remerge")
    assert before < merge
    correction = steps[before]["run"]
    assert '--input "$SRC" --output "$CORRECTED_SRC"' in correction
    assert '--input "$FILT" --output "$CORRECTED_FILT"' in correction
    assert "corrected-inputs/" in correction and "source-identity-latest.json" in correction
    assert "source-identity-filtered.json" in correction
    assert "steps.correct_source_identities.outputs.src" in steps[merge]["env"]["SRC"]
    assert "steps.correct_source_identities.outputs.filtered" in steps[merge]["env"]["FILT"]
    assert not any("python scripts/reconcile_source_identities.py" in s.get("run", "") for s in steps[merge + 1:])
