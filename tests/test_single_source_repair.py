from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from scripts.single_source_repair import (
    ALLOWED_FILES,
    RepairInputError,
    _car_manifest_patch,
    _car_replay_metrics,
    _car_selection,
    _call_repair_model,
    _json_response,
    _strict_json_load,
    analyze_payload,
    validate_patch_text,
)


class SingleSourceRepairTests(unittest.TestCase):
    class _Response:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def test_repair_model_falls_back_from_nim_to_agent_plan(self) -> None:
        rate_limited = urllib.error.HTTPError("https://nim.test", 429, "quota", {}, None)
        plan_response = self._Response({"choices": [{"message": {"content": '{"ok": true}'}}]})
        environment = {
            "NVIDIA_NIM_API_KEY": "nim-secret",
            "VOLCENGINE_AGENTPLAN_API_KEY": "plan-secret",
            "DEEPSEEK_API_KEY": "deepseek-secret",
        }
        with (
            mock.patch.dict("os.environ", environment, clear=True),
            mock.patch(
                "scripts.single_source_repair.urllib.request.urlopen",
                side_effect=[rate_limited, rate_limited, rate_limited, plan_response],
            ) as urlopen,
            mock.patch("scripts.single_source_repair.time.sleep") as sleep,
        ):
            content, model = _call_repair_model("strict JSON")

        self.assertEqual('{"ok": true}', content)
        self.assertEqual("volcengine-agentplan/deepseek-v4-flash", model)
        self.assertEqual(4, urlopen.call_count)
        self.assertEqual([mock.call(1), mock.call(2)], sleep.call_args_list)
        plan_payload = json.loads(urlopen.call_args_list[-1].args[0].data.decode("utf-8"))
        self.assertNotIn("response_format", plan_payload)

    def test_repair_model_fails_closed_when_all_providers_reject(self) -> None:
        rejected = [
            urllib.error.HTTPError(f"https://provider-{index}.test", 401, "denied", {}, None)
            for index in range(3)
        ]
        environment = {
            "NVIDIA_NIM_API_KEY": "nim-secret",
            "VOLCENGINE_AGENTPLAN_API_KEY": "plan-secret",
            "DEEPSEEK_API_KEY": "deepseek-secret",
        }
        with (
            mock.patch.dict("os.environ", environment, clear=True),
            mock.patch(
                "scripts.single_source_repair.urllib.request.urlopen",
                side_effect=rejected,
            ),
            mock.patch("scripts.single_source_repair.time.sleep") as sleep,
        ):
            with self.assertRaisesRegex(RepairInputError, "all repair model providers failed"):
                _call_repair_model("strict JSON")
        sleep.assert_not_called()

    def test_phone_payload_uses_chinese_source_field(self) -> None:
        report = analyze_payload(
            [
                {"手机ID": "1", "品牌": "A", "型号": "M", "数据来源": "中关村在线+CNMO"},
                {"手机ID": "2", "品牌": "B", "型号": "N", "数据来源": "中关村在线"},
            ],
            "phones",
        )
        self.assertEqual(report["schema"], "phones:list")
        self.assertEqual(report["multi_count"], 1)
        self.assertEqual(report["single_count"], 1)

    def test_car_payload_groups_series_and_reports_merge_gap(self) -> None:
        report = analyze_payload(
            {
                "data": [
                    {"车系ID": "10", "车系": "A", "车型名称": "M", "年款": "2025", "数据来源": "汽车之家+懂车帝"},
                    {"车系ID": "10", "车系": "A", "车型名称": "M", "年款": "2025", "数据来源": "汽车之家"},
                    {"车系ID": "20", "车系": "B", "车型名称": "N", "年款": "2025", "数据来源": "汽车之家"},
                ]
            },
            "cars",
        )
        self.assertEqual(report["schema"], "cars:data")
        self.assertEqual(report["causes"]["cross_source_merge_gap"], 1)
        self.assertEqual(report["causes"]["identity_only_single"], 1)

    def test_laptop_atomic_source_array_is_preferred(self) -> None:
        report = analyze_payload(
            {
                "items": [
                    {"brand": "A", "model": "M", "source": "JD", "atomic_source_names": ["JD", "ZOL"]},
                    {"brand": "B", "model": "N", "source": "JD", "atomic_source_names": ["JD"]},
                ]
            },
            "laptops",
        )
        self.assertEqual(report["schema"], "laptops:items")
        self.assertEqual(report["multi_count"], 1)
        self.assertEqual(report["source_fields"]["atomic_source_names"], 2)

    def test_invalid_or_missing_source_payload_is_noop_input(self) -> None:
        with self.assertRaises(RepairInputError):
            analyze_payload({"items": []}, "laptops")
        with self.assertRaises(RepairInputError):
            analyze_payload([{"品牌": "A", "型号": "M"}], "phones")
        with self.assertRaises(RepairInputError):
            analyze_payload([{"手机ID": "local-only", "数据来源": "ZOL"}], "phones")

    def test_source_suffix_and_nonstandard_json_are_rejected_or_normalized(self) -> None:
        report = analyze_payload(
            [{"车系": "A", "车型名称": "M", "年款": "2025", "数据来源": "懂车帝(车系级)"}],
            "cars",
        )
        self.assertEqual(report["available_sources"], ["懂车帝(车系级)"])
        with self.assertRaises(RepairInputError):
            _json_response('{"should_fix": true, "confidence": NaN}')
        with self.assertRaises(RepairInputError):
            _json_response('{"should_fix": true, "confidence": 1e309}')
        with self.assertRaises(RepairInputError):
            _json_response('{"should_fix": true, "confidence": 0.9, "confidence": 0.8}')
        with self.assertRaises(RepairInputError):
            _json_response('```json {"should_fix": false}```')

    def test_strict_input_and_identity_boundaries(self) -> None:
        with self.assertRaises(RepairInputError):
            _strict_json_load('{"value": 1e309}', "Pages payload")
        with self.assertRaises(RepairInputError):
            analyze_payload(
                [{"品牌": "A", "型号": "M", "数据来源": {"name": "ZOL"}}],
                "phones",
            )
        with self.assertRaises(RepairInputError):
            analyze_payload(
                {"items": [{"brand": "A", "model": "M", "identity_key": "!!!", "source": "ZOL"}]},
                "laptops",
            )

    def test_workflow_patch_is_rejected(self) -> None:
        patch = """diff --git a/.github/workflows/deploy-pages.yml b/.github/workflows/deploy-pages.yml
--- a/.github/workflows/deploy-pages.yml
+++ b/.github/workflows/deploy-pages.yml
@@ -1,1 +1,1 @@
-name: old
+name: new
"""
        with self.assertRaises(RepairInputError):
            validate_patch_text(patch, "phones")
        self.assertTrue(ALLOWED_FILES["phones"])

    def test_car_repair_is_manifest_only_and_model_cannot_invent_candidates(self) -> None:
        self.assertEqual(
            ALLOWED_FILES["cars"],
            ("config/safe_v2_absorption_manifest.json",),
        )
        report = {
            "candidates": [
                {
                    "candidate_id": "a" * 24,
                    "members": [
                        {"brand": "甲", "series": "A", "model": "M1", "year": "2026", "sources": ["汽车之家"]},
                        {"brand": "甲", "series": "A", "model": "M2", "year": "2026", "sources": ["懂车帝"]},
                    ],
                }
            ]
        }
        response = {
            "approved_candidate_ids": ["a" * 24],
            "confidence": 0.95,
            "evidence": ["同品牌车系年款，且无硬冲突"],
            "analysis": "名称粒度差异",
        }
        selected, confidence, evidence, _analysis = _car_selection(response, report)
        self.assertEqual(["a" * 24], [item["candidate_id"] for item in selected])
        self.assertEqual(0.95, confidence)
        self.assertTrue(evidence)

        invented = dict(response, approved_candidate_ids=["b" * 24])
        with self.assertRaises(RepairInputError):
            _car_selection(invented, report)

    def test_car_replay_requires_real_visible_metric_improvement(self) -> None:
        rows = [
            {"数据来源": "仅汽车之家", "品牌": "甲", "车系": "A", "车型名称": "2026款 云游版", "年款": "2026"},
            {"数据来源": "仅懂车帝", "品牌": "甲", "车系": "A", "车型名称": "星河版", "年款": "2026"},
        ]
        members = [
            {"brand": "甲", "series": "A", "model": "星河版", "year": "2026", "sources": ["懂车帝"]},
            {"brand": "甲", "series": "A", "model": "2026款 云游版", "year": "2026", "sources": ["汽车之家"]},
        ]
        baseline = {
            "schema": "safe-v2-absorption-policy-v1",
            "allowed_identities": [],
            "approved_components": [],
        }
        candidate_id = hashlib.sha256(
            json.dumps(members, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]
        candidate = {
            **baseline,
            "approved_components": [{"candidate_id": candidate_id, "members": members}],
        }

        metrics = _car_replay_metrics(rows, baseline, candidate)

        self.assertEqual(1, metrics["multi_gain"])
        self.assertEqual(2, metrics["single_reduction"])
        with self.assertRaises(RepairInputError):
            _car_replay_metrics(rows, baseline, baseline)

    def test_car_manifest_rejects_overlap_with_existing_approval(self) -> None:
        shared = {
            "brand": "甲",
            "series": "A",
            "model": "星河版",
            "year": "2026",
            "sources": ["懂车帝"],
        }
        baseline = {
            "schema": "safe-v2-absorption-policy-v1",
            "allowed_identities": [],
            "approved_components": [
                {
                    "candidate_id": "a" * 24,
                    "members": [
                        shared,
                        {
                            "brand": "甲",
                            "series": "A",
                            "model": "云游版",
                            "year": "2026",
                            "sources": ["汽车之家"],
                        },
                    ],
                }
            ],
        }
        selected = [
            {
                "candidate_id": "b" * 24,
                "members": [
                    shared,
                    {
                        "brand": "甲",
                        "series": "A",
                        "model": "远航版",
                        "year": "2026",
                        "sources": ["易车"],
                    },
                ],
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.json"
            manifest_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(RepairInputError):
                _car_manifest_patch(manifest_path, baseline, selected)


if __name__ == "__main__":
    unittest.main()
