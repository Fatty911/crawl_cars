import ast
import types
import unittest
from pathlib import Path
from unittest import mock

import requests


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "crawl_dongchedi.py"


class Step1DeadlineTest(unittest.TestCase):
    def setUp(self):
        names = {"human_delay", "_scan_all_series", "get_series_list", "_preserve_series_cache"}
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        functions = ast.Module(body=[node for node in tree.body
                                    if isinstance(node, ast.FunctionDef) and node.name in names],
                               type_ignores=[])
        self.now = 0.0
        self.module = types.SimpleNamespace(
            time=types.SimpleNamespace(monotonic=lambda: self.now, sleep=self.sleep),
            random=types.SimpleNamespace(uniform=lambda low, high: 8),
            MAX_TIME_PER_STEP=5, MAX_SERIES_PER_RUN=0, INCREMENTAL_MODE=False,
            CRAWL_MIN_DELAY_SECONDS=8, CRAWL_MAX_DELAY_SECONDS=20,
            progress={"series_list": [{"id": "old", "name": "cached"}]},
            save_progress=mock.Mock(), _get_existing_series_ids=lambda: set(),
            get_dcd_series_category=lambda row: "",
            is_excluded_vehicle_level=lambda category: False,
        )
        exec(compile(functions, str(SCRIPT), "exec"), self.module.__dict__)
        self.session = mock.Mock()
        self.session.post.side_effect = self.page
        self.session_patch = mock.patch.object(requests, "Session", return_value=self.session)
        self.session_patch.start()
        self.addCleanup(self.session_patch.stop)

    def sleep(self, seconds):
        self.assertLessEqual(seconds, 5 - self.now)
        self.now += seconds

    def page(self, *args, **kwargs):
        self.assertGreater(kwargs["timeout"], 0)
        self.assertLessEqual(kwargs["timeout"], 5 - self.now)
        self.now += min(2, kwargs["timeout"])
        response = mock.Mock()
        response.json.return_value = {"status": 0, "data": {
            "series": [{"id": "new", "outter_name": "discovered"}], "series_count": 100}}
        return response

    def test_regular_scan_caps_sleep_and_preserves_cached_targets(self):
        rows = self.module.get_series_list()
        self.assertEqual([row["id"] for row in rows], ["old", "new"])
        self.assertEqual(self.now, 5)
        self.assertEqual(self.session.post.call_count, 1)
        self.assertEqual(self.module.progress["series_list"], rows)
        self.module.save_progress.assert_called_once()

    def test_regular_exception_retry_does_not_exceed_deadline(self):
        def fail(*args, **kwargs):
            self.now += kwargs["timeout"]
            raise requests.Timeout("mock timeout")
        self.session.post.side_effect = fail
        rows = self.module.get_series_list()
        self.assertEqual([row["id"] for row in rows], ["old"])
        self.assertEqual(self.now, 5)
        self.assertEqual(self.session.post.call_count, 1)

    def test_incremental_scan_caps_each_request_and_retains_cached_targets(self):
        self.module.INCREMENTAL_MODE = True
        rows = self.module.get_series_list()
        self.assertEqual([row["id"] for row in rows], ["old", "new"])
        self.assertEqual(self.now, 5)
        self.assertEqual([call.kwargs["timeout"] for call in self.session.post.call_args_list],
                         [5, 3, 1])
        self.assertEqual(self.module.progress["series_list"], rows)

    def test_incremental_empty_timeout_keeps_old_pending_targets(self):
        self.module.INCREMENTAL_MODE = True
        def fail(*args, **kwargs):
            self.now += kwargs["timeout"]
            raise requests.Timeout("mock timeout")
        self.session.post.side_effect = fail
        rows = self.module.get_series_list()
        self.assertEqual([row["id"] for row in rows], ["old"])
        self.assertEqual(self.module.progress["series_list"], rows)

    def test_completed_refresh_replaces_old_list(self):
        response = mock.Mock()
        response.json.return_value = {"status": 0, "data": {
            "series": [{"id": "new", "outter_name": "fresh"}], "series_count": 1}}
        self.session.post.side_effect = None
        self.session.post.return_value = response
        self.assertEqual([row["id"] for row in self.module.get_series_list()], ["new"])

    def test_cache_union_updates_matching_id_without_duplicates(self):
        rows = self.module._preserve_series_cache(
            [{"id": "old", "name": "updated"}, {"id": "new", "name": "new"}],
            self.module.progress["series_list"])
        self.assertEqual([row["id"] for row in rows], ["old", "new"])
        self.assertEqual(rows[0]["name"], "updated")

    def test_unlimited_scan_keeps_existing_request_timeout(self):
        self.module.MAX_TIME_PER_STEP = 0
        response = mock.Mock()
        response.json.return_value = {"status": 0, "data": {
            "series": [{"id": "new", "outter_name": "fresh"}], "series_count": 1}}
        self.session.post.side_effect = None
        self.session.post.return_value = response
        self.assertEqual([row["id"] for row in self.module.get_series_list()], ["new"])
        self.assertEqual(self.session.post.call_args.kwargs["timeout"], 20)

    def test_empty_page_delay_stops_at_deadline(self):
        response = mock.Mock()
        response.json.return_value = {"status": 0, "data": {"series": []}}
        self.session.post.side_effect = None
        self.session.post.return_value = response
        self.assertEqual([row["id"] for row in self.module.get_series_list()], ["old"])
        self.assertEqual(self.now, 5)
        self.assertEqual(self.session.post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
