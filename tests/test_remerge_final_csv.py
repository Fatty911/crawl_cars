import csv
import importlib.util
import pytest
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_actual_workflow_writes_csv_from_prepared_json_and_binds_input(tmp_path):
    workflow = yaml.safe_load((ROOT / ".github/workflows/remerge-and-publish.yml").read_text(encoding="utf-8"))
    step = next(item for item in workflow["jobs"]["remerge-and-publish"]["steps"] if item["name"] == "组装发布站点")
    code = step["run"].split('python - "$DATE" <<\'PY\'\n', 1)[1].split("\nPY", 1)[0]
    (tmp_path / "site/data").mkdir(parents=True)
    (tmp_path / "site/analysis").mkdir()
    historical = tmp_path / "site/analysis/retained-history.json"
    historical.write_bytes(b'{"historical":"preserved"}')
    (tmp_path / "src-data").mkdir()
    (tmp_path / "config").mkdir()
    evidence_inputs = {"source_identity_evidence.json": b'{"verified":"source-excerpt"}',
                       "source-identity-latest.json": b'{"changes":[]}',
                       "source-identity-filtered.json": b'{"changes":[]}',
                       "pages-audit-report.json": b'{"status":"pass","fixture":true}',
                       "pages-filtered-audit-report.json": b'{"status":"pass","fixture":true}',
                       "remerge-stats.json": b'{"premerge_source_identity_changes":{"merged":3,"filtered":3}}'}
    for name, body in evidence_inputs.items():
        target = tmp_path / ("config" if name == "source_identity_evidence.json" else "") / name
        target.write_bytes(body)
    rows = [{"品牌": "测试", "车系": "系列", "年款": "2026", "级别": "中大型SUV"}]
    for name in ("latest", "filtered"):
        (tmp_path / f"site/data/{name}.json").write_text(json.dumps(rows), encoding="utf-8")
    raw = b'[{"original":"preserved"}]'
    (tmp_path / "src-data/merged_20261015.json").write_bytes(raw)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "scripts"), GITHUB_SHA="commit-proof",
               INPUT_RELEASE="cnb-data-original", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    result = subprocess.run([sys.executable, "-", "20261015"], input=code, text=True, encoding="utf-8",
                            env=env, cwd=tmp_path, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    for name in ("merged", "filtered_cars"):
        with (tmp_path / f"site/data/{name}_20261015.csv").open(encoding="utf-8-sig", newline="") as stream:
            exported = list(csv.DictReader(stream))
        assert len(exported) == 1
        assert exported[0]["级别"] == rows[0]["级别"]
        assert (tmp_path / f"out/{name}_{20261015}.csv").read_bytes() == (
            tmp_path / f"site/data/{name}_{20261015}.csv").read_bytes()
    assert (tmp_path / "out/merged_20261015.json").read_bytes() == (tmp_path / "site/data/latest.json").read_bytes()
    assert (tmp_path / "out/filtered_cars_20261015.json").read_bytes() == (tmp_path / "site/data/filtered.json").read_bytes()
    manifest = json.loads((tmp_path / "site/data/manifest.json").read_bytes())
    assert manifest["provenance"] == {
        "codeCommit": "commit-proof", "inputRelease": "cnb-data-original",
        "inputSha256": {"merged_20261015.json": hashlib.sha256(raw).hexdigest()},
        "sourceIdentityEvidenceSha256": {name: hashlib.sha256(body).hexdigest()
                                        for name, body in evidence_inputs.items()},
    }

    # Execute the real verifier against the actual workflow's complete output,
    # including aliases, evidence and retained historical JSON, not just four names.
    spec = importlib.util.spec_from_file_location("published_asset_checker", ROOT / "scripts/prepare_cnb_pages.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    assets = checker.checked_assets(tmp_path / "site", manifest)
    expected = {path.relative_to(tmp_path / "site").as_posix()
                for path in (tmp_path / "site").rglob("*")
                if path.is_file() and path.suffix in {".json", ".csv"}
                and path != tmp_path / "site/data/manifest.json"}
    assert set(assets) == expected
    assert historical.read_bytes() == b'{"historical":"preserved"}'
    alias = tmp_path / "site/data/latest.json"
    original = alias.read_bytes()
    changed = original.replace(b"2026", b"2025", 1)
    assert len(changed) == len(original) and changed != original
    alias.write_bytes(changed)
    with pytest.raises(ValueError, match="checksum mismatch"):
        checker.checked_assets(tmp_path / "site", manifest)
