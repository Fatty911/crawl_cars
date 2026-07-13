import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "crawl_dongchedi.py"


def load_module():
    old_argv = sys.argv[:]
    sys.argv = [str(SCRIPT)]
    try:
        spec = importlib.util.spec_from_file_location("crawl_dongchedi_test", SCRIPT)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {SCRIPT}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.argv = old_argv


class DongchediApiPayloadTest(unittest.TestCase):
    def setUp(self):
        self.module: Any = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.module.dcd_dir = str(root / "dongchedi")
        self.module.dcd_json_dir = str(root / "dongchedi" / "json")
        self.module.dcd_exception_dir = str(root / "dongchedi" / "exception")
        Path(self.module.dcd_json_dir).mkdir(parents=True)
        Path(self.module.dcd_exception_dir).mkdir(parents=True)
        self.module.progress_file = str(root / "dongchedi" / "progress.json")
        self.module.progress = {}
        self.module.MIN_YEAR = 2022

    def tearDown(self):
        self.tmp.cleanup()

    def test_fetch_series_entity_payload_batches_car_ids(self):
        calls = []

        def fake_request(url, params=None):
            calls.append((url, params))
            if "garage" in url:
                return {
                    "status": 0,
                    "message": "success",
                    "data": {
                        "list": [
                            {
                                "name": "2026",
                                "data": [
                                    {
                                        "data": [
                                            {"info": {"id": 256890}},
                                            {"info": {"car_id": "256891"}},
                                        ]
                                    }
                                ],
                            }
                        ]
                    },
                }
            return {
                "status": "success",
                "message": "data is load",
                "data": {
                    "car_info": [
                        {"car_name": "A", "car_year": "2026款", "official_price": "10万", "brand_name": "测试", "info": {"fuel": {"value": "汽油"}}},
                    ],
                    "properties": [{"key": "fuel", "text": "燃油类型"}],
                },
            }

        self.module._request_dongchedi_json = fake_request
        payload = self.module.fetch_series_entity_payload({"id": "3504", "name": "测试车系", "brand": "测试"})
        self.assertEqual(payload["car_ids"], ["256890", "256891"])
        self.assertEqual(payload["data"]["car_info"][0]["car_name"], "A")
        self.assertEqual(calls[0][1], {"no_sales": 1})
        self.assertEqual(calls[1][1], {"car_id_list": "256890,256891"})

    def test_fetch_series_entity_payload_rejects_empty_entity_data(self):
        responses = iter(
            [
                {
                    "status": 0,
                    "message": "success",
                    "data": {"list": [{"car_id": 256890}]},
                },
                {
                    "status": "success",
                    "message": "data is load",
                    "data": {"car_info": [], "properties": []},
                },
            ]
        )
        self.module._request_dongchedi_json = lambda url, params=None: next(responses)

        with self.assertRaisesRegex(RuntimeError, "car_info 为空"):
            self.module.fetch_series_entity_payload(
                {"id": "3504", "name": "测试车系", "brand": "测试"}
            )

    def test_parse_entity_api_payload_and_reject_login_shell(self):
        api_payload = {
            "source": "dongchedi_entity_api",
            "series_info": {"id": "3504", "name": "银河E5", "brand": "吉利银河"},
            "car_ids": ["256890"],
            "data": {
                "car_info": [
                    {
                        "car_name": "银河E5 2026款 探索版",
                        "car_year": "2026款",
                        "official_price": "10.98万",
                        "brand_name": "吉利银河",
                        "info": {"energy": {"value": "纯电动"}, "range": {"value": "530"}},
                    }
                ],
                "properties": [
                    {"key": "energy", "text": "能源类型"},
                    {"key": "range", "text": "CLTC纯电续航"},
                ],
            },
        }
        Path(self.module.dcd_json_dir, "3504.json").write_text(json.dumps(api_payload, ensure_ascii=False), encoding="utf-8")
        login_shell = {"page": "/login-required", "props": {"pageProps": {"redirect": "/auto/params-carIds-x-3505"}}}
        Path(self.module.dcd_json_dir, "3505.html").write_text(
            f'<script id="__NEXT_DATA__">{json.dumps(login_shell)}</script>', encoding="utf-8"
        )

        rows, headers = self.module.parse_config_pages([
            {"id": "3504", "name": "银河E5", "brand": "吉利银河"},
            {"id": "3505", "name": "登录壳", "brand": "测试"},
        ])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["品牌"], "吉利银河")
        self.assertEqual(rows[0]["车系ID"], "3504")
        self.assertEqual(rows[0]["车型名称"], "银河E5 2026款 探索版")
        self.assertIn("CLTC纯电续航", headers)


if __name__ == "__main__":
    unittest.main()
