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

    def valid_html(self, series: str = "Model 3", model: str = "2022款 后轮驱动版") -> str:
        config = {
            "result": {
                "paramtypeitems": [
                    {
                        "paramitems": [
                            {"name": "车型名称", "valueitems": [{"value": model}]},
                            {"name": "年款", "valueitems": [{"value": "2022"}]},
                            {"name": "车款ID", "valueitems": [{"value": "54529"}]},
                        ]
                    }
                ]
            }
        }
        option = {"result": {"configtypeitems": [{"configitems": [{"name": "配置项", "valueitems": [{"value": "有"}]}]}]}}
        return (
            f"<title>汽车之家 | {series} | 参数配置</title>"
            f"<script>var config = {json.dumps(config, ensure_ascii=False)};"
            f"var option = {json.dumps(option, ensure_ascii=False)};var bag = {{}};</script>"
        )

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
                mock.patch.object(self.autohome, "target_manifest_file", str(root / "target_manifest.json")),
                mock.patch.object(self.autohome, "series_queue_file", str(queue_path)),
                mock.patch.object(
                    self.autohome,
                    "progress",
                    {"download_car_pages": list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), "target_idx": 2},
                ),
            ):
                self.assertFalse(self.autohome.is_step1_completed())
                (root / "target_manifest.json").write_text(
                    json.dumps(
                        {
                            "a": {"cache_key": "a", "car_id": "a", "target_type": "current", "series": "Model 3", "brand": "特斯拉"},
                            "b": {"cache_key": "b", "car_id": "b", "target_type": "current", "series": "Model 3", "brand": "特斯拉"},
                            "a_history_no_data": {"target_type": "history_terminal_no_data", "terminal": True},
                            "b_history_no_data": {"target_type": "history_terminal_no_data", "terminal": True},
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                (html_dir / "a").write_text(self.valid_html(), encoding="utf-8")
                (html_dir / "b").write_text(self.valid_html(), encoding="utf-8")
                self.assertTrue(self.autohome.is_step1_completed())

    def test_unparseable_existing_cache_cannot_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            html_dir = root / "html"
            html_dir.mkdir()
            queue_path = root / "queue.json"
            queue_path.write_text(json.dumps([{"car_id": "5346"}]), encoding="utf-8")
            (root / "target_manifest.json").write_text(
                json.dumps(
                    {
                        "5346": {"cache_key": "5346", "car_id": "5346", "target_type": "current", "series": "Model 3", "brand": "特斯拉"},
                        "5346_history_no_data": {"target_type": "history_terminal_no_data", "terminal": True},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (html_dir / "5346").write_text("<html>blocked</html>", encoding="utf-8")
            with (
                mock.patch.object(self.autohome, "html_dir", str(html_dir)),
                mock.patch.object(self.autohome, "target_manifest_file", str(root / "target_manifest.json")),
                mock.patch.object(self.autohome, "series_queue_file", str(queue_path)),
                mock.patch.object(self.autohome, "progress", {"download_car_pages": list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), "target_idx": 1}),
            ):
                self.assertFalse(self.autohome.is_step1_completed())


    def test_api_html_preserves_spec_id_as_car_id(self) -> None:
        payload = {
            "result": {
                "bread": {"seriesname": "Model 3"},
                "titlelist": [
                    {"groupname": "参数信息", "items": [{"itemname": "车型名称"}]},
                ],
                "datalist": [
                    {"specid": 54529, "specname": "2022款 后轮驱动版", "paramconflist": [{"itemname": "2022款 后轮驱动版"}]},
                ],
            }
        }

        html = self.autohome.build_autohome_api_html("5346", payload)

        self.assertIsNotNone(html)
        config = self.autohome.extract_var_json(html, "config")
        identity_items = config["result"]["paramtypeitems"][0]["paramitems"]
        self.assertIn({"name": "车款ID", "valueitems": [{"value": "54529"}]}, identity_items)

    def test_history_spec_api_path_produces_valid_model3_cache_and_output(self) -> None:
        payload = {
            "returncode": 0,
            "result": {
                "bread": {"seriesname": "Model 3"},
                "titlelist": [
                    {"groupname": "参数信息", "items": [{"itemname": "车型名称"}, {"itemname": "能源类型"}]},
                ],
                "datalist": [
                    {
                        "specid": 54529,
                        "specname": "2022款 后轮驱动版",
                        "condition": ["2022"],
                        "paramconflist": [
                            {"itemname": "2022款 后轮驱动版"},
                            {"itemname": "纯电动"},
                        ],
                    },
                    {
                        "specid": 99999,
                        "specname": "2022款 其它版",
                        "condition": ["2022"],
                        "paramconflist": [
                            {"itemname": "2022款 其它版"},
                            {"itemname": "纯电动"},
                        ],
                    },
                ],
            },
        }
        response = mock.Mock(
            status_code=200,
            headers={"content-type": "application/json"},
            json=lambda: payload,
        )
        target = {
            "cache_key": "5346_spec_2022_54529",
            "car_id": "5346",
            "spec_id": "54529",
            "year": "2022",
            "brand": "特斯拉",
            "series": "Model 3",
            "target_type": "history",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("html", "newjson", "exception"):
                (root / name).mkdir()
            with (
                mock.patch.object(self.autohome, "html_dir", str(root / "html")),
                mock.patch.object(self.autohome, "newjson_dir", str(root / "newjson")),
                mock.patch.object(self.autohome, "exception_dir", str(root / "exception")),
                mock.patch.object(self.autohome, "working_dir", str(root)),
                mock.patch.object(self.autohome, "target_manifest_file", str(root / "target_manifest.json")),
                mock.patch.object(self.autohome.session, "get", return_value=response),
            ):
                (root / "target_manifest.json").write_text(
                    json.dumps({"5346_spec_2022_54529": target}, ensure_ascii=False),
                    encoding="utf-8",
                )
                html = self.autohome.fetch_autohome_history_spec_api_html(target)
                self.assertIsNotNone(html)
                (root / "html" / "5346_spec_2022_54529").write_text(html, encoding="utf-8")
                self.assertTrue(self.autohome.cached_html_has_valid_autohome_data("5346_spec_2022_54529"))
                (root / "newjson" / "5346_spec_2022_54529").write_text(html, encoding="utf-8")
                self.autohome.generate_csv()
                output = json.loads(next(root.glob("autoHome_*.json")).read_text(encoding="utf-8"))

        self.assertEqual(1, len(output))
        self.assertEqual("Model 3", output[0]["车系"])
        self.assertEqual("2022", output[0]["年款"])
        self.assertEqual("54529", output[0]["车款ID"])
        self.assertEqual("2022款 后轮驱动版", output[0]["车型名称"])

    def test_history_spec_api_rejects_payload_without_matching_spec_id(self) -> None:
        response = mock.Mock(
            status_code=200,
            headers={"content-type": "application/json"},
            json=lambda: {
                "returncode": 0,
                "result": {
                    "bread": {"seriesname": "Model 3"},
                    "titlelist": [{"groupname": "参数信息", "items": [{"itemname": "车型名称"}]}],
                    "datalist": [{"specid": 99999, "specname": "2022款 其它版", "paramconflist": [{"itemname": "2022款 其它版"}]}],
                },
            },
        )
        with mock.patch.object(self.autohome.session, "get", return_value=response):
            html = self.autohome.fetch_autohome_history_spec_api_html(
                {"car_id": "5346", "spec_id": "54529", "series": "Model 3"}
            )
        self.assertIsNone(html)

    def test_first_incomplete_target_index_rewinds_inserted_history_before_saved_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            html_dir = root / "html"
            html_dir.mkdir()
            (html_dir / "5346").write_text(self.valid_html(), encoding="utf-8")
            with (
                mock.patch.object(self.autohome, "html_dir", str(html_dir)),
                mock.patch.object(self.autohome, "target_manifest_file", str(root / "target_manifest.json")),
            ):
                (root / "target_manifest.json").write_text(
                    json.dumps(
                        {
                            "5346": {"cache_key": "5346", "car_id": "5346", "target_type": "current", "brand": "特斯拉", "series": "Model 3"},
                            "5346_spec_2022_54529": {"cache_key": "5346_spec_2022_54529", "car_id": "5346", "target_type": "history", "brand": "特斯拉", "series": "Model 3", "spec_id": "54529"},
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                idx = self.autohome.first_incomplete_target_index(
                    [
                        {"cache_key": "5346", "target_type": "current"},
                        {"cache_key": "5346_spec_2022_54529", "target_type": "history"},
                        {"cache_key": "2", "target_type": "current"},
                    ]
                )
        self.assertEqual(1, idx)

    def test_history_discovery_slice_allows_target_phase_to_run(self) -> None:
        manifest = {}
        progress = {}
        response = mock.Mock(
            status_code=200,
            text='<a href="//www.autohome.com.cn/spec/54529/">2022款 后轮驱动版</a>',
            apparent_encoding="utf-8",
        )
        with (
            mock.patch.object(self.autohome, "progress", progress),
            mock.patch.object(self.autohome.session, "get", mock.Mock(return_value=response)),
            mock.patch.object(self.autohome, "check_time_limit", return_value=False),
            mock.patch.dict("os.environ", {"AUTOHOME_HISTORY_DISCOVERY_BATCH": "1"}),
        ):
            targets = self.autohome.prepare_autohome_targets(
                [
                    {"car_id": "5346", "brand": "特斯拉", "series": "Model 3"},
                    {"car_id": "2", "brand": "特斯拉", "series": "Model Y"},
                ],
                manifest,
                0,
            )

        self.assertFalse(progress["history_discovery_complete"])
        self.assertGreaterEqual(len(targets), 2)
        self.assertEqual("5346", targets[0]["cache_key"])
        self.assertIn("5346_spec_2022_54529", [target["cache_key"] for target in targets])

    def test_sale_page_parser_keeps_one_2022_plus_spec_per_year(self) -> None:
        html = """
        <div class="spec-cont">
          <a href="//www.autohome.com.cn/spec/54529/">2022款 后轮驱动版</a>
          <a href="//www.autohome.com.cn/spec/55666/">2022款 高性能版</a>
          <a href="//www.autohome.com.cn/spec/60000/">2023款 后轮驱动版</a>
          <a href="//www.autohome.com.cn/spec/70000/">2021款 标准版</a>
          <a href="//www.autohome.com.cn/spec/80000/">2026款 预售版</a>
        </div>
        """
        targets = self.autohome.parse_sale_history_targets("5346", "特斯拉", "Model 3", html)
        self.assertEqual(["2022", "2023"], [target["year"] for target in targets])
        self.assertEqual("5346_spec_2022_54529", targets[0]["cache_key"])
        self.assertEqual("https://car.autohome.com.cn/config/spec/54529.html", targets[0]["url"])

    def test_history_cache_key_maps_to_original_series_in_output(self) -> None:
        self.assertEqual("5346", self.autohome.original_series_id_from_cache_key("5346_spec_2022_54529"))

    def test_no_history_data_records_terminal_target_only_for_verified_sale_structure(self) -> None:
        manifest = {}
        response = mock.Mock(
            status_code=200,
            text='<div class="spec-cont"><a href="//www.autohome.com.cn/spec/10001/">2021款 标准版</a></div>',
            apparent_encoding="utf-8",
        )
        with mock.patch.object(self.autohome.session, "get", return_value=response):
            targets, completed = self.autohome.discover_history_targets(
                "1",
                "特斯拉",
                "Model 3",
                manifest,
            )
        self.assertEqual([], targets)
        self.assertTrue(completed)
        self.assertTrue(manifest["1_history_no_data"]["terminal"])

    def test_antibot_sale_page_does_not_record_terminal_target(self) -> None:
        manifest = {}
        response = mock.Mock(status_code=200, text="<html>安全验证</html>", apparent_encoding="utf-8")
        with mock.patch.object(self.autohome.session, "get", return_value=response):
            targets, completed = self.autohome.discover_history_targets(
                "1",
                "特斯拉",
                "Model 3",
                manifest,
            )
        self.assertEqual([], targets)
        self.assertFalse(completed)
        self.assertNotIn("1_history_no_data", manifest)

    def test_debug_target_preparation_skips_unbounded_history_discovery(self) -> None:
        series_queue = [
            {"car_id": str(i), "brand": "品牌", "series": f"车系{i}"}
            for i in range(100)
        ]
        manifest = {}
        with (
            mock.patch.object(self.autohome, "DEBUG_MODE", True),
            mock.patch.object(self.autohome, "MAX_CARS_PER_RUN", 30),
            mock.patch.object(self.autohome, "discover_history_targets_until_deadline") as discover,
        ):
            targets = self.autohome.prepare_autohome_targets(series_queue, manifest, 0)

        discover.assert_not_called()
        self.assertEqual(30, len(targets))
        self.assertEqual([str(i) for i in range(30)], [target["car_id"] for target in targets])

    def test_full_target_preparation_keeps_history_discovery(self) -> None:
        series_queue = [{"car_id": "1", "brand": "品牌", "series": "车系"}]
        manifest = {}
        with (
            mock.patch.object(self.autohome, "DEBUG_MODE", False),
            mock.patch.object(self.autohome, "MAX_CARS_PER_RUN", 30),
            mock.patch.object(self.autohome, "discover_history_targets_until_deadline") as discover,
        ):
            targets = self.autohome.prepare_autohome_targets(series_queue, manifest, 0)

        discover.assert_called_once_with(series_queue, manifest, 0)
        self.assertEqual(["1"], [target["car_id"] for target in targets])

    def test_history_discovery_deadline_resumes_with_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {}
            progress = {"history_discovery_idx": 1}
            response = mock.Mock(
                status_code=200,
                text='<a href="//www.autohome.com.cn/spec/54529/">2022款 后轮驱动版</a>',
                apparent_encoding="utf-8",
            )
            get_mock = mock.Mock(return_value=response)
            with (
                mock.patch.object(self.autohome, "progress", progress),
                mock.patch.object(self.autohome, "progress_file", str(root / "progress.json")),
                mock.patch.object(self.autohome, "target_manifest_file", str(root / "target_manifest.json")),
                mock.patch.object(self.autohome.session, "get", get_mock),
                mock.patch.object(self.autohome, "check_time_limit", side_effect=[False, True]),
                mock.patch.object(self.autohome, "AUTO_MODE", True),
            ):
                completed = self.autohome.discover_history_targets_until_deadline(
                    [
                        {"car_id": "already", "brand": "特斯拉", "series": "旧"},
                        {"car_id": "5346", "brand": "特斯拉", "series": "Model 3"},
                        {"car_id": "2", "brand": "特斯拉", "series": "Model Y"},
                    ],
                    manifest,
                    0,
                )
            self.assertFalse(completed)
            self.assertEqual(2, progress["history_discovery_idx"])
            self.assertIn("5346_spec_2022_54529", manifest)

    def test_history_discovery_batch_limit_prevents_full_prescan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {}
            progress = {}
            response = mock.Mock(
                status_code=200,
                text='<a href="//www.autohome.com.cn/spec/54529/">2022款 后轮驱动版</a>',
                apparent_encoding="utf-8",
            )
            get_mock = mock.Mock(return_value=response)
            with (
                mock.patch.object(self.autohome, "progress", progress),
                mock.patch.object(self.autohome, "progress_file", str(root / "progress.json")),
                mock.patch.object(self.autohome, "target_manifest_file", str(root / "target_manifest.json")),
                mock.patch.object(self.autohome.session, "get", get_mock),
                mock.patch.object(self.autohome, "check_time_limit", return_value=False),
                mock.patch.object(self.autohome, "AUTO_MODE", True),
                mock.patch.dict("os.environ", {"AUTOHOME_HISTORY_DISCOVERY_BATCH": "1"}),
            ):
                completed = self.autohome.discover_history_targets_until_deadline(
                    [
                        {"car_id": "5346", "brand": "特斯拉", "series": "Model 3"},
                        {"car_id": "2", "brand": "特斯拉", "series": "Model Y"},
                    ],
                    manifest,
                    0,
                )
            self.assertFalse(completed)
            self.assertEqual(1, progress["history_discovery_idx"])
            self.assertEqual(1, get_mock.call_count)

    def test_history_discovery_default_has_no_200_batch_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {}
            progress = {}
            response = mock.Mock(
                status_code=200,
                text='<a href="//www.autohome.com.cn/spec/54529/">2022款 后轮驱动版</a>',
                apparent_encoding="utf-8",
            )
            get_mock = mock.Mock(return_value=response)
            with (
                mock.patch.object(self.autohome, "progress", progress),
                mock.patch.object(self.autohome, "progress_file", str(root / "progress.json")),
                mock.patch.object(self.autohome, "target_manifest_file", str(root / "target_manifest.json")),
                mock.patch.object(self.autohome.session, "get", get_mock),
                mock.patch.object(self.autohome, "check_time_limit", return_value=False),
                mock.patch.dict("os.environ", {}, clear=True),
            ):
                self.autohome.discover_history_targets_until_deadline(
                    [
                        {"car_id": str(i), "brand": "品牌", "series": f"车系{i}"}
                        for i in range(201)
                    ],
                    manifest,
                    0,
                )
            self.assertEqual(120, progress["history_discovery_idx"])
            self.assertEqual(120, get_mock.call_count)

    def test_history_discovery_pending_advances_to_next_series(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {}
            progress = {}
            bad = mock.Mock(status_code=200, text="<html>安全验证</html>", apparent_encoding="utf-8")
            good = mock.Mock(
                status_code=200,
                text='<a href="//www.autohome.com.cn/spec/54529/">2022款 后轮驱动版</a>',
                apparent_encoding="utf-8",
            )
            get_mock = mock.Mock(side_effect=[bad, good])
            with (
                mock.patch.object(self.autohome, "progress", progress),
                mock.patch.object(self.autohome, "progress_file", str(root / "progress.json")),
                mock.patch.object(self.autohome, "target_manifest_file", str(root / "target_manifest.json")),
                mock.patch.object(self.autohome.session, "get", get_mock),
                mock.patch.object(self.autohome, "check_time_limit", return_value=False),
                mock.patch.object(self.autohome, "AUTO_MODE", True),
            ):
                completed = self.autohome.discover_history_targets_until_deadline(
                    [
                        {"car_id": "bad", "brand": "品牌", "series": "坏页"},
                        {"car_id": "good", "brand": "品牌", "series": "好页"},
                    ],
                    manifest,
                    0,
                )
            self.assertFalse(completed)
            self.assertEqual(2, get_mock.call_count)
            self.assertIn("bad_history_pending", manifest)
            self.assertIn("good_spec_2022_54529", manifest)
            self.assertEqual(0, progress["history_discovery_idx"])

    def test_history_discovery_retries_pending_after_sweep(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {
                "bad_history_pending": {
                    "car_id": "bad",
                    "brand": "品牌",
                    "series": "坏页",
                    "target_type": "history_pending",
                }
            }
            progress = {"history_discovery_idx": 0}
            good = mock.Mock(
                status_code=200,
                text='<a href="//www.autohome.com.cn/spec/54529/">2022款 后轮驱动版</a>',
                apparent_encoding="utf-8",
            )
            with (
                mock.patch.object(self.autohome, "progress", progress),
                mock.patch.object(self.autohome, "progress_file", str(root / "progress.json")),
                mock.patch.object(self.autohome, "target_manifest_file", str(root / "target_manifest.json")),
                mock.patch.object(self.autohome.session, "get", return_value=good),
                mock.patch.object(self.autohome, "check_time_limit", return_value=False),
            ):
                self.autohome.discover_history_targets_until_deadline(
                    [{"car_id": "bad", "brand": "品牌", "series": "坏页"}],
                    manifest,
                    0,
                )
            self.assertEqual(1, progress["history_discovery_idx"])
            self.assertIn("bad_spec_2022_54529", manifest)

    def test_target_fetch_pending_marks_retry_without_losing_manifest(self) -> None:
        manifest = {
            "5346_spec_2022_54529": {
                "cache_key": "5346_spec_2022_54529",
                "car_id": "5346",
                "target_type": "history",
                "series": "Model 3",
                "brand": "特斯拉",
            }
        }
        self.autohome.mark_target_fetch_pending("5346_spec_2022_54529", manifest)
        self.assertTrue(manifest["5346_spec_2022_54529"]["fetch_pending"])
        self.assertEqual(1, manifest["5346_spec_2022_54529"]["fetch_retry_count"])
        self.assertEqual("5346", manifest["5346_spec_2022_54529"]["car_id"])

    def test_legacy_queue_idx_migrates_without_becoming_target_idx(self) -> None:
        progress = {"queue_idx": 1751}
        with tempfile.TemporaryDirectory() as tmp:
            progress_path = Path(tmp) / "progress.json"
            with mock.patch.object(self.autohome, "progress", progress), mock.patch.object(
                self.autohome, "progress_file", str(progress_path)
            ):
                if "target_idx" not in self.autohome.progress and "queue_idx" in self.autohome.progress:
                    self.autohome.progress["legacy_series_queue_idx"] = self.autohome.progress.get("queue_idx", 0)
                    self.autohome.progress["target_idx"] = 0
                    self.autohome.progress.pop("queue_idx", None)
            self.assertEqual(1751, progress["legacy_series_queue_idx"])
            self.assertEqual(0, progress["target_idx"])
            self.assertNotIn("queue_idx", progress)

    def test_current_api_empty_data_records_current_terminal(self) -> None:
        response = mock.Mock(
            status_code=200,
            headers={"content-type": "application/json"},
            json=lambda: {"returncode": 0, "result": {"titlelist": [], "datalist": []}},
        )
        with mock.patch.object(self.autohome.session, "get", return_value=response):
            content, terminal = self.autohome.fetch_autohome_api_html("1")
        self.assertIsNone(content)
        self.assertTrue(terminal)

    def test_current_terminal_target_does_not_block_history_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            html_dir = root / "html"
            html_dir.mkdir()
            queue_path = root / "queue.json"
            queue_path.write_text(json.dumps([{"car_id": "5346"}]), encoding="utf-8")
            (root / "target_manifest.json").write_text(
                json.dumps(
                    {
                        "5346": {
                            "cache_key": "5346",
                            "car_id": "5346",
                            "target_type": "current_terminal_no_data",
                            "terminal": True,
                            "series": "Model 3",
                            "brand": "特斯拉",
                        },
                        "5346_spec_2022_54529": {
                            "cache_key": "5346_spec_2022_54529",
                            "car_id": "5346",
                            "target_type": "history",
                            "series": "Model 3",
                            "brand": "特斯拉",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (html_dir / "5346_spec_2022_54529").write_text(self.valid_html(), encoding="utf-8")
            with (
                mock.patch.object(self.autohome, "html_dir", str(html_dir)),
                mock.patch.object(self.autohome, "target_manifest_file", str(root / "target_manifest.json")),
                mock.patch.object(self.autohome, "series_queue_file", str(queue_path)),
                mock.patch.object(self.autohome, "progress", {"download_car_pages": list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), "target_idx": 2}),
            ):
                self.assertTrue(self.autohome.is_step1_completed())

    def test_refetch_invalidates_downstream_cache_and_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirs = {}
            for name in ("html", "newhtml", "json", "content", "newjson"):
                dirs[name] = root / name
                dirs[name].mkdir()
            for path in [
                dirs["html"] / "5346",
                dirs["newhtml"] / "5346.html",
                dirs["json"] / "5346",
                dirs["content"] / "5346.html",
                dirs["newjson"] / "5346",
            ]:
                path.write_text("old", encoding="utf-8")
            progress = {
                "parse_js_to_html": ["5346"],
                "parse_json_data": ["5346"],
                "crack_html_files": ["5346.html"],
                "generate_data_files": ["5346"],
            }
            with (
                mock.patch.object(self.autohome, "html_dir", str(dirs["html"])),
                mock.patch.object(self.autohome, "newhtml_dir", str(dirs["newhtml"])),
                mock.patch.object(self.autohome, "json_dir", str(dirs["json"])),
                mock.patch.object(self.autohome, "content_dir", str(dirs["content"])),
                mock.patch.object(self.autohome, "newjson_dir", str(dirs["newjson"])),
            ):
                self.autohome.invalidate_autohome_target_cache("5346", progress)
            self.assertTrue(all(not path.exists() for directory in dirs.values() for path in directory.iterdir()))
            self.assertTrue(all(not values for values in progress.values()))

    def test_workflow_done_gate_requires_target_complete(self) -> None:
        workflow = (ROOT / ".github/workflows/crawl-autohome.yml").read_text(encoding="utf-8")
        marker = workflow.split("- name: Mark Autohome period complete", 1)[1].split("run: |", 1)[0]
        self.assertIn("steps.verify_autohome.outputs.target_complete == 'true'", marker)
        self.assertNotIn("fromJSON(steps.verify_autohome.outputs.row_count) >= 500", marker)

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
                    {"download_car_pages": list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), "target_idx": 0},
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
