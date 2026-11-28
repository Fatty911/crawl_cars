"""Unit tests for cross-platform mesh sync (code mirrors, aws-raw releases, and Pages)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import aws_raw_bundle  # noqa: E402
import overlay_pages_frontend  # noqa: E402
import pages_mesh_reconcile  # noqa: E402
import platform_mesh_sync as mesh  # noqa: E402

SHA_GH = "1" * 40
SHA_OLD = "2" * 40
PRODUCER = "a" * 40
STORAGE = {"ref": "main", "commit": "b" * 40}
TAG = "aws-raw-20261128T010203Z"


def _sample_plan() -> dict:
    return {
        "schema": 1,
        "platforms": {
            "github": {"repo": "Fatty911/crawl_cars"},
            "cnb": {"repo": "xuerui911-mirror/crawl_cars", "storage": dict(STORAGE)},
            "gitlab": {"project": "xuerui911/crawl_cars", "storage": dict(STORAGE)},
        },
    }


class PlatformMeshSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_code_mirror_never_touches_main_and_syncs_mirror_branch(self) -> None:
        plan = _sample_plan()
        refs = {
            ("https://github.com/Fatty911/crawl_cars.git", "refs/heads/main"): SHA_GH,
            ("https://cnb.cool/xuerui911-mirror/crawl_cars.git", mesh.MIRROR_REF): SHA_GH,
            ("https://gitlab.com/xuerui911/crawl_cars.git", mesh.MIRROR_REF): SHA_OLD,
        }
        pushed: list[tuple[str, str]] = []

        def fake_ls_remote(url: str, ref: str, **kwargs):
            return refs.get((url, ref))

        def fake_push(gh_url: str, target_sha: str, target_url: str, user: str, pwd: str, repo_dir):
            self.assertEqual(mesh.MIRROR_REF, "refs/heads/mirror/main")
            self.assertNotEqual(mesh.MIRROR_REF, "refs/heads/main")
            pushed.append((target_url, target_sha))
            refs[(target_url, mesh.MIRROR_REF)] = target_sha
            return target_sha

        with patch.object(mesh, "parse_git_credential", return_value=("oauth2", "secret")), \
             patch.object(mesh, "get_remote_branch_sha", side_effect=fake_ls_remote), \
             patch.object(mesh, "_push_mirror_ref", side_effect=fake_push):
            check_report = mesh.sync_code_mirror(plan, apply=False)
            self.assertFalse(check_report["in_sync"])
            self.assertEqual(check_report["platforms"]["cnb"]["status"], "in_sync")
            self.assertEqual(check_report["platforms"]["gitlab"]["status"], "drifted")

            apply_report = mesh.sync_code_mirror(plan, apply=True)
            self.assertTrue(apply_report["in_sync"])
            self.assertEqual(apply_report["platforms"]["gitlab"]["status"], "synced")
            self.assertEqual(pushed, [("https://gitlab.com/xuerui911/crawl_cars.git", SHA_GH)])

    def test_raw_release_mesh_backfills_missing_platform_from_healthy_source(self) -> None:
        plan = _sample_plan()
        src_file = self.root / "dcd.json"
        src_file.write_text('[{"车系":"测试车系","车型名称":"2026款测试版"}]', encoding="utf-8")
        bundle = self.root / "src_bundle"
        aws_raw_bundle.pack(bundle, TAG, PRODUCER, {"dongchedi": src_file})

        tags_map = {"github": [TAG], "cnb": [TAG], "gitlab": []}
        published: list[tuple[str, str, str]] = []

        def fake_download(src: str, p: dict, tag: str, dest: Path) -> dict:
            dest.mkdir(parents=True, exist_ok=True)
            for item in bundle.iterdir():
                (dest / item.name).write_bytes(item.read_bytes())
            return aws_raw_bundle.verify(dest, tag)

        def fake_publish(dst: str, p: dict, b: Path, tag: str, producer: str, state_dir: Path) -> dict:
            published.append((dst, tag, producer))
            return {"platform": dst, "verified": True}

        with patch.object(mesh, "list_platform_raw_tags", side_effect=lambda plat, p: tags_map[plat]), \
             patch.object(mesh, "download_raw_bundle", side_effect=fake_download), \
             patch.object(mesh, "publish_raw_bundle", side_effect=fake_publish):
            res_check = mesh.sync_raw_releases(plan, apply=False, state_dir=self.root / "state")
            self.assertFalse(res_check["in_sync"])
            self.assertEqual(res_check["missing"], ["gitlab"])

            res_apply = mesh.sync_raw_releases(plan, apply=True, state_dir=self.root / "state")
            self.assertTrue(res_apply["in_sync"])
            self.assertEqual(res_apply["missing"], [])
            self.assertEqual(published, [("gitlab", TAG, PRODUCER)])

    def test_raw_release_mesh_falls_back_to_second_healthy_source_on_download_error(self) -> None:
        plan = _sample_plan()
        src_file = self.root / "dcd.json"
        src_file.write_text('[{"车系":"测试车系","车型名称":"2026款测试版"}]', encoding="utf-8")
        bundle = self.root / "src_bundle"
        aws_raw_bundle.pack(bundle, TAG, PRODUCER, {"dongchedi": src_file})

        tags_map = {"github": [TAG], "cnb": [TAG], "gitlab": []}
        calls: list[str] = []

        def fake_download(src: str, p: dict, tag: str, dest: Path) -> dict:
            calls.append(src)
            if src == "github":
                raise RuntimeError("transient github failure")
            dest.mkdir(parents=True, exist_ok=True)
            for item in bundle.iterdir():
                (dest / item.name).write_bytes(item.read_bytes())
            return aws_raw_bundle.verify(dest, tag)

        with patch.object(mesh, "list_platform_raw_tags", side_effect=lambda plat, p: tags_map[plat]), \
             patch.object(mesh, "download_raw_bundle", side_effect=fake_download), \
             patch.object(mesh, "publish_raw_bundle", return_value={"platform": "gitlab", "verified": True}):
            res = mesh.sync_raw_releases(plan, apply=True, state_dir=self.root / "state")
            self.assertEqual(calls, ["github", "cnb"])
            self.assertEqual(res["backfilled"]["gitlab"]["source"], "cnb")
            self.assertTrue(res["in_sync"])

    def test_pages_mesh_detects_manifest_or_asset_drift_and_dispatches_targets(self) -> None:
        responses = {
            "https://cars.jiucai.eu.org/index.html": b"<html/>",
            "https://cars.jiucai.eu.org/app.js": b"v2",
            "https://cars.jiucai.eu.org/styles.css": b"css",
            "https://cars.jiucai.eu.org/filter_conditions.json": b"{}",
            "https://cars.jiucai.eu.org/data/manifest.json": json.dumps({"rowCount": 100, "date": "2026-11-28"}).encode(),
            "https://cars2.jiucai.eu.org/index.html": b"<html/>",
            "https://cars2.jiucai.eu.org/app.js": b"v1",
            "https://cars2.jiucai.eu.org/styles.css": b"css",
            "https://cars2.jiucai.eu.org/filter_conditions.json": b"{}",
            "https://cars2.jiucai.eu.org/data/manifest.json": json.dumps({"rowCount": 100, "date": "2026-11-28"}).encode(),
            "https://cars3.jiucai.eu.org/index.html": b"<html/>",
            "https://cars3.jiucai.eu.org/app.js": b"v2",
            "https://cars3.jiucai.eu.org/styles.css": b"css",
            "https://cars3.jiucai.eu.org/filter_conditions.json": b"{}",
            "https://cars3.jiucai.eu.org/data/manifest.json": json.dumps({"rowCount": 99, "date": "2026-11-28"}).encode(),
        }
        report = pages_mesh_reconcile.compare_sites(fetch=lambda url: responses[url])
        self.assertFalse(report["in_sync"])
        self.assertEqual(report["drifted"]["cloudflare"], ["asset:/app.js"])
        self.assertEqual(report["drifted"]["codeberg"], ["manifest"])

        with patch.object(pages_mesh_reconcile.subprocess, "run") as run_mock:
            triggered = pages_mesh_reconcile.dispatch_reconcile(report, "Fatty911/crawl_cars", latest_tag="cnb-data-1")
            self.assertEqual(triggered, ["cnb-pages.yml", "codeberg-pages.yml"])
            self.assertEqual(run_mock.call_count, 2)

    def test_overlay_pages_frontend_stamps_meta_and_preserves_manifest(self) -> None:
        fake_repo = self.root / "repo"
        (fake_repo / "docs" / "data").mkdir(parents=True)
        (fake_repo / "config").mkdir(parents=True)
        (fake_repo / "docs" / "index.html").write_text(
            '<html><head><meta name="frontend-updated" content="" /></head><body>ok</body></html>',
            encoding="utf-8",
        )
        (fake_repo / "docs" / "app.js").write_text("window.__appReady = true;\n", encoding="utf-8")
        (fake_repo / "docs" / "filter_conditions.json").write_text('{"conditions":["new"]}', encoding="utf-8")
        (fake_repo / "docs" / "data" / "manifest.json").write_text('{"rowCount":1}', encoding="utf-8")
        (fake_repo / "config" / "filter_conditions.json").write_text('{"conditions":["new"]}', encoding="utf-8")

        site = self.root / "site"
        (site / "data").mkdir(parents=True)
        (site / "config").mkdir(parents=True)
        (site / "filter_conditions.json").write_text('{"conditions":["verified"]}', encoding="utf-8")
        (site / "config" / "filter_conditions.json").write_text('{"conditions":["verified"]}', encoding="utf-8")
        verified_manifest = json.dumps({
            "rowCount": 999,
            "date": "2026-11-28",
            "files": {
                "additionalDataAssets": [
                    {"path": "filter_conditions.json"},
                    {"path": "config/filter_conditions.json"},
                ]
            },
        }).encode("utf-8")
        (site / "data" / "manifest.json").write_bytes(verified_manifest)
        manifest_copy = self.root / "verified_manifest.json"
        manifest_copy.write_bytes(verified_manifest)

        overlay_pages_frontend.overlay_frontend(
            site,
            manifest_path=manifest_copy,
            repo=fake_repo,
            frontend_updated="2026-11-28T10:20:30+08:00",
        )
        self.assertEqual((site / "data" / "manifest.json").read_bytes(), verified_manifest)
        self.assertIn('content="2026-11-28T10:20:30+08:00"', (site / "index.html").read_text(encoding="utf-8"))
        self.assertEqual((site / "app.js").read_text(encoding="utf-8"), "window.__appReady = true;\n")
        self.assertEqual((site / "filter_conditions.json").read_text(encoding="utf-8"), '{"conditions":["verified"]}')
        self.assertEqual((site / "config" / "filter_conditions.json").read_text(encoding="utf-8"), '{"conditions":["verified"]}')

    def test_safe_asset_path_and_complete_raw_asset_names_reject_unsafe_or_partial(self) -> None:
        with self.assertRaises(mesh.MeshSyncError):
            mesh._safe_asset_path(self.root, "../escape.json")
        with self.assertRaises(mesh.MeshSyncError):
            mesh._safe_asset_path(self.root, "sub/file.json")
        with self.assertRaises(mesh.MeshSyncError):
            mesh._safe_asset_path(self.root, "..")
        with self.assertRaises(mesh.MeshSyncError):
            mesh.download_raw_bundle("gitlab", _sample_plan(), "../bad-tag", self.root / "bad")
        self.assertFalse(mesh._has_complete_raw_asset_names({"dongchedi_aws.json"}))
        self.assertFalse(mesh._has_complete_raw_asset_names({"aws-raw-manifest.json"}))
        self.assertTrue(mesh._has_complete_raw_asset_names({"aws-raw-manifest.json", "dongchedi_aws.json"}))

    def test_run_mesh_apply_keeps_in_sync_false_when_pages_dispatched_async(self) -> None:
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(_sample_plan()), encoding="utf-8")
        with patch.object(mesh, "sync_code_mirror", return_value={"in_sync": True}), \
             patch.object(mesh, "sync_raw_releases", return_value={"in_sync": True}), \
             patch.object(mesh.pages_mesh_reconcile, "compare_sites", return_value={"in_sync": False, "drifted": {"cloudflare": ["asset:/app.js"]}, "errors": {}}), \
             patch.object(mesh.pages_mesh_reconcile, "resolve_latest_immutable_tag", return_value="cnb-data-1"), \
             patch.object(mesh.pages_mesh_reconcile, "dispatch_reconcile", return_value=["cnb-pages.yml"]):
            rep = mesh.run_mesh(plan_path, apply=True, state_dir=self.root / "state")
            self.assertFalse(rep["in_sync"])
            self.assertTrue(rep["apply_ok"])

    def test_code_mirror_keeps_target_sha_immutable_and_flags_mismatch(self) -> None:
        plan = _sample_plan()
        sha_wrong = "3" * 40
        refs = {
            ("https://github.com/Fatty911/crawl_cars.git", "refs/heads/main"): SHA_GH,
            ("https://cnb.cool/xuerui911-mirror/crawl_cars.git", mesh.MIRROR_REF): SHA_GH,
            ("https://gitlab.com/xuerui911/crawl_cars.git", mesh.MIRROR_REF): SHA_OLD,
        }

        def fake_ls_remote(url: str, ref: str, **kwargs):
            return refs.get((url, ref))

        def fake_push(gh_url: str, target_sha: str, target_url: str, user: str, pwd: str, repo_dir):
            refs[(target_url, mesh.MIRROR_REF)] = sha_wrong

        with patch.object(mesh, "parse_git_credential", return_value=("oauth2", "secret")), \
             patch.object(mesh, "get_remote_branch_sha", side_effect=fake_ls_remote), \
             patch.object(mesh, "_push_mirror_ref", side_effect=fake_push):
            rep = mesh.sync_code_mirror(plan, apply=True)
            self.assertFalse(rep["in_sync"])
            self.assertEqual(rep["target_sha"], SHA_GH)
            self.assertEqual(rep["platforms"]["gitlab"]["status"], "mismatch")
            self.assertEqual(rep["platforms"]["gitlab"]["sha"], sha_wrong)


if __name__ == "__main__":
    unittest.main()
