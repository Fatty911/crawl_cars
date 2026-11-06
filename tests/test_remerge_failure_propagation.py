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


@pytest.mark.parametrize("baseline_tag", ["", "cnb-data-fixed-baseline"])
@pytest.mark.parametrize("failure", ["", "download", "verify"])
def test_aws_fetch_uses_verified_archive_without_legacy_json_assets(tmp_path, baseline_tag, failure):
    config = yaml.safe_load((ROOT / ".github/workflows/remerge-and-publish.yml").read_text(encoding="utf-8"))
    command = next(s["run"] for s in config["jobs"]["remerge-and-publish"]["steps"] if s.get("id") == "fetch")
    bash = str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe") if os.name == "nt" else shutil.which("bash")
    if not bash or not Path(bash).is_file():
        pytest.skip("bash is required for actual workflow shell execution")
    outputs = tmp_path / "outputs"
    env = dict(os.environ, BASELINE_RELEASE=baseline_tag, AWS_RAW_RELEASE="aws-raw-20261105T023300Z",
               GITHUB_REPOSITORY="owner/repo", GITHUB_OUTPUT=outputs.as_posix(), FAIL_STAGE=failure)
    # The real shell gets only a verified archive interface. Legacy split
    # merged/filtered Release assets deliberately do not exist.
    prelude = r'''
python() {
  if [[ "$*" == *"--print-tag"* ]]; then
    printf '%s\n' cnb-data-latest-verified
    return
  fi
  if [ "$1" = scripts/download_verified_release.py ]; then
    [ "$FAIL_STAGE" != download ] || return 23
    printf '%s\n' "$@" > download-args
    mkdir -p src-data/verified-release
    printf archive > src-data/verified-release/verified-site.zip
    printf manifest > src-data/verified-release/manifest.json
  elif [ "$1" = scripts/prepare_cnb_pages.py ]; then
    [ "$FAIL_STAGE" != verify ] || return 23
    test -f src-data/verified-release/verified-site.zip
    test -f src-data/verified-release/manifest.json
    mkdir -p src-data/published-site/data
    printf '[{"identity":"published-wide"}]' > src-data/published-site/data/latest.json
    printf '[{"identity":"published-filtered"}]' > src-data/published-site/data/filtered.json
  else
    return 97
  fi
}
gh() { echo 'legacy Release JSON assets are absent' >&2; return 77; }
'''
    result = subprocess.run([bash, "--noprofile", "--norc", "-c", prelude + command],
                            cwd=tmp_path, env=env, capture_output=True)
    out = outputs.read_text() if outputs.exists() else ""
    if failure:
        assert result.returncode == 23, result.stdout + result.stderr
        assert "src=" not in out and "filtered=" not in out
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert (tmp_path / "src-data/merged_published.json").read_text() == '[{"identity":"published-wide"}]'
        assert (tmp_path / "src-data/filtered_cars_published.json").read_text() == '[{"identity":"published-filtered"}]'
        args = (tmp_path / "download-args").read_text().splitlines()
        assert args[args.index("--tag") + 1] == (baseline_tag or "cnb-data-latest-verified")
        assert "--no-legacy" in args
        assert "src=src-data/merged_published.json" in out
        assert "filtered=src-data/filtered_cars_published.json" in out
