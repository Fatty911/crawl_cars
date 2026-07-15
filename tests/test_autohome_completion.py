from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_autohome_module():
    path = ROOT / "scripts/test_autohome.py"
    spec = importlib.util.spec_from_file_location("autohome_completion_regression", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "argv", [path.name]):
        spec.loader.exec_module(module)
    return module


class AutohomeCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.autohome = load_autohome_module()

    def test_tracked_done_progress_cannot_complete_without_cached_series(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            html_dir = root / "html"
            html_dir.mkdir()
            queue_path = root / "queue.json"
            queue_path.write_text(
                json.dumps([{"car_id": "a"}, {"car_id": "b"}]),
                encoding="utf-8",
            )
            with (
                mock.patch.object(self.autohome, "html_dir", str(html_dir)),
                mock.patch.object(self.autohome, "series_queue_file", str(queue_path)),
                mock.patch.object(
                    self.autohome,
                    "progress",
                    {"download_car_pages": list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), "queue_idx": 2},
                ),
            ):
                self.assertFalse(self.autohome.is_step1_completed())
                (html_dir / "a").write_text("a", encoding="utf-8")
                (html_dir / "b").write_text("b", encoding="utf-8")
                self.assertTrue(self.autohome.is_step1_completed())

    def test_empty_queue_is_never_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            html_dir = root / "html"
            html_dir.mkdir()
            queue_path = root / "queue.json"
            queue_path.write_text("[]", encoding="utf-8")
            with (
                mock.patch.object(self.autohome, "html_dir", str(html_dir)),
                mock.patch.object(self.autohome, "series_queue_file", str(queue_path)),
                mock.patch.object(
                    self.autohome,
                    "progress",
                    {"download_car_pages": list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), "queue_idx": 0},
                ),
            ):
                self.assertFalse(self.autohome.is_step1_completed())

    def test_auto_mode_incomplete_state_uses_resumable_exit_code(self) -> None:
        with mock.patch.object(self.autohome, "AUTO_MODE", True):
            with self.assertRaises(SystemExit) as raised:
                self.autohome.stop_incomplete_step1("incomplete")
        self.assertEqual(10, raised.exception.code)

    def test_runtime_and_workflow_share_isolated_state_root(self) -> None:
        expected_root = ROOT / "crawl_state/autohome"
        self.assertEqual(expected_root, Path(self.autohome.state_dir))
        for path in [
            self.autohome.html_dir,
            self.autohome.newhtml_dir,
            self.autohome.json_dir,
            self.autohome.content_dir,
            self.autohome.newjson_dir,
            self.autohome.exception_dir,
        ]:
            self.assertEqual(expected_root, Path(path).parent)
        self.assertEqual(expected_root / "progress.json", Path(self.autohome.progress_file))
        self.assertEqual(ROOT / "scripts/data/autohome_series_queue.json", Path(self.autohome.series_queue_file))

        workflow = (ROOT / ".github/workflows/crawl-autohome.yml").read_text(encoding="utf-8")
        self.assertIn("path: crawl_state/autohome", workflow)
        self.assertIn("find crawl_state/autohome/html -type f", workflow)
        self.assertIn("crawl_state/autohome/progress.json", workflow)
        self.assertIn("crawl_state/model_registry_autohome.json", workflow)
        self.assertNotIn("path: html\n", workflow)
        self.assertNotIn("            progress.json\n", workflow)
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/crawl_state/autohome/", gitignore)
        self.assertFalse((ROOT / "scripts/progress.json").exists())

    def test_priority_loader_uses_latest_merged_intersection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir()
            (data_dir / "dongchedi_series_list.json").write_text(
                json.dumps(
                    ["雅 阁", {"车系": "汉"}, {"name": "Model 3"}, 123, {"unknown": "忽略"}],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (data_dir / "merged_20260713.json").write_text(
                json.dumps(
                    [{"数据来源": "仅懂车帝", "车系": "Model 3"}],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (data_dir / "merged_20260714.json").write_text(
                json.dumps(
                    [
                        {"数据来源": "仅懂车帝", "车系": "雅阁"},
                        {"数据来源": "汽车之家+懂车帝", "车系": "汉"},
                        {"数据来源": "仅懂车帝", "车系": "不在懂车帝列表"},
                        "忽略非字典行",
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (data_dir / "merged_99999999.json.bak").write_text(
                json.dumps([{"数据来源": "仅懂车帝", "车系": "汉"}], ensure_ascii=False),
                encoding="utf-8",
            )

            with mock.patch.object(self.autohome, "repo_dir", str(root)):
                self.assertEqual(
                    {"雅阁"}, self.autohome.load_autohome_priority_series_names()
                )

    def test_priority_queue_preserves_prefix_background_and_fields(self) -> None:
        queue = [
            {"series": "已处理一", "salecount": 1, "heat": 1},
            {"series": "已处理二", "salecount": 2, "heat": 2},
            {"series": "后台热门", "salecount": 100, "heat": 3},
            {"series": "优先车系", "salecount": 1, "heat": 99},
            {"series": "后台冷门", "salecount": 2, "heat": 999},
        ]
        original_keys = [set(item) for item in queue]

        with mock.patch.object(
            self.autohome,
            "load_autohome_priority_series_names",
            return_value={"优先车系"},
        ):
            result = self.autohome.prioritize_series_queue(queue, 2)

        self.assertIs(queue[0], result[0])
        self.assertIs(queue[1], result[1])
        self.assertEqual(["已处理一", "已处理二"], [item["series"] for item in result[:2]])
        self.assertEqual(
            ["优先车系", "后台热门", "后台冷门"],
            [item["series"] for item in result[2:]],
        )
        self.assertEqual(original_keys, [set(item) for item in queue])
        self.assertTrue(all("priority_source" not in item for item in result))
        self.assertEqual(len(queue), len(result))

    def test_priority_queue_missing_data_and_past_end_are_noops(self) -> None:
        queue = [
            {"series": "车系一", "salecount": 1, "heat": 1},
            {"series": "车系二", "salecount": 2, "heat": 2},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(self.autohome, "repo_dir", tmp):
                self.assertEqual(queue, self.autohome.prioritize_series_queue(queue, 0))
        with mock.patch.object(
            self.autohome,
            "load_autohome_priority_series_names",
            return_value={"车系二"},
        ):
            self.assertEqual(queue, self.autohome.prioritize_series_queue(queue, 99))

    def test_workflow_publishes_partial_artifacts_and_triggers_merge(self) -> None:
        workflow = (ROOT / ".github/workflows/crawl-autohome.yml").read_text(encoding="utf-8")
        self.assertIn("AUTOHOME_ARTIFACT_NAME=autohome-partial-data", workflow)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertIn("steps.verify_autohome.outputs.has_data == 'true'", workflow)
        trigger = workflow.split("- name: Trigger merge-and-filter workflow", 1)[1]
        condition = trigger.split("run: |", 1)[0]
        self.assertIn("if: steps.upload_autohome.outcome == 'success'", condition)
        self.assertNotIn("steps.step1.outputs.complete == 'true'", condition)
        self.assertNotIn("steps.retry_step1.outputs.complete == 'true'", condition)


if __name__ == "__main__":
    unittest.main()
