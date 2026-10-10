import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare_cloudflare_payload.py"
spec = importlib.util.spec_from_file_location("cloudflare_payload_test", SCRIPT)
payload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(payload)


class CloudflarePayloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "site"
        self.output = self.root / "cf-site"
        (self.source / "data").mkdir(parents=True)
        (self.source / "index.html").write_text("verified frontend", encoding="utf-8")

    def setup_site(self, rows, filtered=None):
        filtered = [] if filtered is None else filtered
        for name, data in (("latest.json", rows), ("latest_stamp.json", rows),
                           ("filtered.json", filtered), ("filtered_stamp.json", filtered)):
            (self.source / "data" / name).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.source / "data/full.csv").write_bytes(b"x" * 400)
        (self.source / "data/filtered.csv").write_text("id\n1\n", encoding="utf-8")
        manifest = {"rowCount": len(rows), "filteredRowCount": len(filtered), "date": "20261010",
                    "updatedAt": "2026-10-10T01:00:00Z", "files": {
                        "latestJson": "data/latest_stamp.json", "filteredJson": "data/filtered_stamp.json",
                        "latestCsv": "data/full.csv", "filteredCsv": "data/filtered.csv"}}
        (self.source / "data/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def rows(self):
        return [{"id": i, "车型": "易车汉字🚗" * 5, "来源": "易车"} for i in range(5)]

    def test_full_raw_rows_order_and_facts_survive_non_ascii_shards(self):
        rows = self.rows()
        self.setup_site(rows, [{"id": 999, "默认筛选": True}])
        before = {p.relative_to(self.source): p.read_bytes() for p in self.source.rglob("*") if p.is_file()}
        manifest = payload.prepare_payload(self.source, self.output, 140)
        chunks = manifest["files"]["latestJsonChunks"]
        rebuilt = []
        for chunk in chunks:
            raw = (self.output / chunk["path"]).read_bytes()
            self.assertLessEqual(len(raw), 140)
            self.assertEqual(chunk["size"], len(raw))
            self.assertEqual(chunk["sha256"], hashlib.sha256(raw).hexdigest())
            decoded = json.loads(raw)
            self.assertEqual(chunk["rowCount"], len(decoded))
            rebuilt.extend(decoded)
        self.assertEqual(rebuilt, rows)
        self.assertEqual([row["id"] for row in rebuilt], list(range(5)))
        self.assertEqual(manifest["rowCount"], len(rows))
        self.assertEqual(manifest["files"]["filteredJson"], "data/filtered_stamp.json")
        self.assertNotIn("latestJson", manifest["files"])
        self.assertNotIn("latestCsv", manifest["files"])
        self.assertFalse((self.output / "data/latest.json").exists())
        self.assertFalse((self.output / "data/latest_stamp.json").exists())
        self.assertEqual(manifest["omittedDownloads"][0]["path"], "data/full.csv")
        self.assertEqual(before, {p.relative_to(self.source): p.read_bytes()
                                 for p in self.source.rglob("*") if p.is_file()})
        for value in manifest["files"].values():
            if isinstance(value, str):
                self.assertTrue((self.output / value).is_file())
            else:
                for chunk in value:
                    self.assertTrue((self.output / chunk["path"]).is_file())

    def test_exact_utf8_boundary_and_next_byte_make_another_shard(self):
        rows = [{"id": 1, "名": "汉🚗"}, {"id": 2, "名": "字🚗"}]
        complete = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        chunks = payload.write_chunks(rows, self.source, "boundary", len(complete))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["size"], len(complete))
        chunks = payload.write_chunks(rows, self.source, "split", len(complete) - 1)
        self.assertEqual(len(chunks), 2)

    def test_oversized_single_row_fails_without_output_or_source_mutation(self):
        self.setup_site([{"id": 1, "名": "汉" * 100}])
        before = (self.source / "data/latest_stamp.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "single latest row"):
            payload.prepare_payload(self.source, self.output, 100)
        self.assertFalse(self.output.exists())
        self.assertEqual((self.source / "data/latest_stamp.json").read_bytes(), before)

    def test_empty_full_dataset_rejected(self):
        self.setup_site([])
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            payload.prepare_payload(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_large_filtered_dataset_also_sharded_without_data_loss(self):
        rows = self.rows()
        self.setup_site(rows, rows[:3])
        manifest = payload.prepare_payload(self.source, self.output, 140)
        self.assertNotIn("filteredJson", manifest["files"])
        payload.verify_chunks(self.output, manifest["files"]["filteredJsonChunks"], rows[:3], 140)
        self.assertEqual(manifest["filteredRowCount"], 3)

    def test_manifest_count_mismatch_and_missing_reference_fail_closed(self):
        self.setup_site(self.rows())
        path = self.source / "data/manifest.json"
        manifest = json.loads(path.read_text())
        manifest["rowCount"] = 1
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "rowCount"):
            payload.prepare_payload(self.source, self.output)
        manifest["rowCount"] = 5
        manifest["files"]["otherJson"] = "data/missing.json"
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "missing file"):
            payload.prepare_payload(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_corrupted_shard_fails_hash_verification(self):
        rows = [{"id": 1}]
        chunks = payload.write_chunks(rows, self.source, "latest", 100)
        (self.source / chunks[0]["path"]).write_bytes(b'[{"id":2}]')
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            payload.verify_chunks(self.source, chunks, rows, 100)

    def test_path_boundaries_and_existing_output_are_not_overwritten(self):
        self.setup_site(self.rows())
        for output in (self.source, self.source / "nested", self.root):
            with self.subTest(output=output), self.assertRaises(ValueError):
                payload.prepare_payload(self.source, output)
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep")
        with self.assertRaisesRegex(ValueError, "already exists"):
            payload.prepare_payload(self.source, self.output)
        self.assertEqual(sentinel.read_text(), "keep")

    def test_duplicate_input_rows_remain_exactly_as_published(self):
        rows = [{"id": "same", "fact": "original"}, {"id": "same", "fact": "original"}]
        chunks = payload.write_chunks(rows, self.source, "latest", 40)
        payload.verify_chunks(self.source, chunks, rows, 40)
        self.assertEqual(sum(chunk["rowCount"] for chunk in chunks), 2)

    def test_unknown_oversized_asset_is_rejected_not_silently_dropped(self):
        self.setup_site(self.rows())
        (self.source / "opaque.bin").write_bytes(b"x" * 513)
        with mock.patch.object(payload, "CLOUDFLARE_MAX_BYTES", 512):
            with self.assertRaisesRegex(ValueError, "unsupported oversized asset"):
                payload.prepare_payload(self.source, self.output, 140)
        self.assertFalse(self.output.exists())
        self.assertEqual((self.source / "opaque.bin").stat().st_size, 513)

    def test_manifest_paths_cannot_escape_input_site(self):
        self.setup_site(self.rows())
        outside = self.root / "outside.json"
        outside.write_text('[{"id":1}]')
        manifest_path = self.source / "data/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["latestJson"] = "../outside.json"
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "escapes site"):
            payload.prepare_payload(self.source, self.output)
        self.assertFalse(self.output.exists())


class CloudflareWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow = yaml.safe_load((SCRIPT.parents[1] / ".cnb.yml").read_text(encoding="utf-8"))

        def jobs(value):
            if isinstance(value, dict):
                if isinstance(value.get("stages"), list):
                    yield value
                for child in value.values():
                    yield from jobs(child)
            elif isinstance(value, list):
                for child in value:
                    yield from jobs(child)

        cls.publish_jobs = [job for job in jobs(workflow)
                            if any(stage.get("name") == "组装Cloudflare完整分片"
                                   for stage in job["stages"])]

    def test_both_workflows_publish_full_primary_site_before_cloudflare_sharding(self):
        self.assertEqual(len(self.publish_jobs), 2)
        for job in self.publish_jobs:
            stages = job["stages"]
            names = [stage.get("name") for stage in stages]
            release_index = names.index("推送数据到GitHub Release")
            prepare_index = names.index("组装Cloudflare完整分片")
            cloudflare_index = names.index("发布到Cloudflare Pages")
            with self.subTest(job=names):
                self.assertLess(names.index("验证渲染数据"), release_index)
                self.assertLess(release_index, prepare_index)
                self.assertLess(prepare_index, cloudflare_index)
                self.assertIn("publish_github_release.py --site-dir site", stages[release_index]["script"])
                self.assertIn("prepare_cloudflare_payload.py --input site --output cf-site",
                              stages[prepare_index]["script"])
                self.assertIn("pages deploy cf-site", stages[cloudflare_index]["script"])

    def test_python_sharding_and_node_upload_use_their_own_runtime_stages(self):
        self.assertEqual(len(self.publish_jobs), 2)
        for job in self.publish_jobs:
            named = {stage.get("name"): stage for stage in job["stages"]}
            prepare = named["组装Cloudflare完整分片"]
            deploy = named["发布到Cloudflare Pages"]
            inherited_image = job.get("docker", {}).get("image", "")
            self.assertTrue(prepare.get("image", inherited_image).startswith("python:"))
            self.assertTrue(deploy.get("image", inherited_image).startswith("node:"))
            self.assertNotIn("python ", deploy["script"])
            self.assertNotIn("prepare_cloudflare_payload", deploy["script"])

    def test_no_size_based_deletion_or_filtered_to_latest_alias_in_either_pipeline(self):
        self.assertEqual(len(self.publish_jobs), 2)
        for job in self.publish_jobs:
            scripts = "\n".join(str(stage.get("script", "")) for stage in job["stages"])
            self.assertNotRegex(scripts, r"(?m)\b(?:cp|ln|mv)\s+[^\n;]*filtered[^\n;]*latest")
            self.assertNotRegex(scripts, r"(?m)\bfind\s+(?:site|cf-site)[^\n]*-size[^\n]*(?:-delete|\brm\b)")


if __name__ == "__main__":
    unittest.main()
