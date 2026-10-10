from pathlib import Path
import subprocess
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]


def workflow_steps():
    workflow = yaml.safe_load((ROOT / ".github/workflows/deploy-frontend.yml").read_text(encoding="utf-8"))
    return workflow["jobs"]["deploy-frontend"]["steps"]


def test_frontend_and_verified_cnb_deployments_share_serial_pages_group():
    workflows = [yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
                 for name in ("deploy-frontend.yml", "cnb-pages.yml")]
    assert [workflow["concurrency"]["group"] for workflow in workflows] == ["pages", "pages"]
    assert all(workflow["concurrency"]["cancel-in-progress"] is False for workflow in workflows)


def test_frontend_requires_verified_release_before_overlay_and_deploy():
    steps = workflow_steps()
    prepare = next(step for step in steps if step["name"] == "准备静态站点")["run"]
    assert 'python scripts/download_verified_release.py --repo "$GITHUB_REPOSITORY" --dir release-files' in prepare
    assert "data-latest" not in prepare
    assert "python scripts/prepare_cnb_pages.py --archive release-files/verified-site.zip --manifest release-files/manifest.json --site site" in prepare
    assert prepare.index("prepare_cnb_pages.py") < prepare.index('Path("docs")')
    assert "set -euo pipefail" in prepare
    assert "|| true" not in prepare
    assert "prepare_pages_payload.py" not in prepare
    assert "cmp release-files/manifest.json site/data/manifest.json" in prepare
    render = next(step for step in steps if step["name"] == "验证渲染数据（解析前端JS逻辑）")["run"]
    assert "test -s site/data/latest.json" in render
    assert "跳过" not in render
    deployment_index = next(i for i, step in enumerate(steps) if step.get("id") == "deployment")
    verify_index = next(i for i, step in enumerate(steps) if "--verify-url" in step.get("run", ""))
    assert deployment_index < verify_index


def test_failed_verified_download_stops_before_extraction_or_overlay(tmp_path):
    prepare = next(step for step in workflow_steps() if step["name"] == "准备静态站点")["run"]
    commands = tmp_path / "commands.txt"
    mock = '''
    GITHUB_REPOSITORY=Fatty911/crawl_cars
    python() {
      case "$*" in
        *download_verified_release.py*) echo download >> commands.txt; return 7 ;;
        *prepare_cnb_pages.py*) echo extract >> commands.txt; return 0 ;;
        *) echo overlay >> commands.txt; return 0 ;;
      esac
    }
    '''
    result = subprocess.run(["sh", "-c", mock + prepare], cwd=tmp_path,
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 7, result.stderr
    assert commands.read_text().splitlines() == ["download"]


def test_frontend_overlay_keeps_verified_data_and_manifest_byte_identical(tmp_path):
    originals = {
        "site/data/latest.json": b'[{"evidence":"published"}]',
        "site/data/manifest.json": b'{"updatedAt":"2026-10-01T00:00:00Z","files":{"latestJson":"data/latest.json"}}',
        "site/manifest.json": b'{"root":"verified"}',
    }
    files = dict(originals, **{
        "site/index.html": b"old frontend",
        "docs/index.html": b"new frontend",
        "docs/assets/style.css": b"new styles",
        "docs/data/latest.json": b"unverified replacement",
        "docs/data/manifest.json": b"timestamp replacement",
        "docs/manifest.json": b"root replacement",
        "config/filter_conditions.json": b'{"conditions":[]}',
    })
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    prepare = next(step for step in workflow_steps() if step["name"] == "准备静态站点")["run"]
    overlay = prepare.split("python - <<'PY'\n", 1)[1].split("\nPY", 1)[0]
    result = subprocess.run([sys.executable, "-c", overlay], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    for name, data in originals.items():
        assert (tmp_path / name).read_bytes() == data
    assert (tmp_path / "site/index.html").read_bytes() == b"new frontend"
    assert (tmp_path / "site/assets/style.css").read_bytes() == b"new styles"
    assert (tmp_path / "site/config/filter_conditions.json").read_bytes() == b'{"conditions":[]}'
