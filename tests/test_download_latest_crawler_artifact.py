from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "download_latest_crawler_artifact.py"


def load_module():
    spec = importlib.util.spec_from_file_location("download_latest_crawler_artifact_regression", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DownloadLatestCrawlerArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def run_main(self, output_dir: Path, min_bytes: str | None = None) -> int:
        args = [
            "download_latest_crawler_artifact.py",
            "--repo",
            "owner/repo",
            "--workflow",
            "crawl-yiche.yml",
            "--artifact-prefix",
            "yiche-data-",
            "--json-pattern",
            "yiche_*.json",
            "--label",
            "易车",
            "--output-dir",
            str(output_dir),
            "--min-rows",
            "1",
        ]
        if min_bytes is not None:
            args.extend(["--min-bytes", min_bytes])

        def fake_request_json(url: str, token: str) -> dict:
            if url.endswith("/runs?status=success&per_page=50"):
                return {"workflow_runs": [{"id": 123, "created_at": "2026-07-16T00:00:00Z"}]}
            if url.endswith("/runs/123/artifacts?per_page=100"):
                return {
                    "artifacts": [
                        {"name": "yiche-data-123-1", "expired": False, "size_in_bytes": 488},
                    ]
                }
            raise AssertionError(url)

        def fake_download(repo: str, run_id: int, artifact_name: str, dest: Path) -> bool:
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "yiche_20260716.json").write_text(
                json.dumps([{"数据来源": "仅易车", "品牌": "甲", "车系": "A", "车型名称": "A"}], ensure_ascii=False),
                encoding="utf-8",
            )
            return True

        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "token"}), \
            mock.patch.object(sys, "argv", args), \
            mock.patch.object(self.module, "request_json", side_effect=fake_request_json), \
            mock.patch.object(self.module, "download_artifact_with_gh", side_effect=fake_download):
            return self.module.main()

    def test_default_min_bytes_keeps_small_artifact_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            result = self.run_main(output_dir)

            self.assertEqual(0, result)
            self.assertEqual([], list(output_dir.glob("yiche_*.json")))

    def test_yiche_can_lower_min_bytes_for_small_valid_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            result = self.run_main(output_dir, min_bytes="1")

            self.assertEqual(0, result)
            self.assertEqual(["yiche_20260716.json"], [path.name for path in output_dir.glob("yiche_*.json")])


if __name__ == "__main__":
    unittest.main()
