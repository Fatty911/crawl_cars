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

    def test_workflow_separates_partial_artifacts_from_completed_data(self) -> None:
        workflow = (ROOT / ".github/workflows/crawl-autohome.yml").read_text(encoding="utf-8")
        self.assertIn("AUTOHOME_ARTIFACT_PREFIX=autohome-partial-data", workflow)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertIn("steps.verify_autohome.outputs.has_data == 'true'", workflow)
        trigger = workflow.split("- name: Trigger merge-and-filter workflow", 1)[1]
        self.assertIn("steps.step1.outputs.complete == 'true'", trigger)
        self.assertIn("steps.retry_step1.outputs.complete == 'true'", trigger)


if __name__ == "__main__":
    unittest.main()
