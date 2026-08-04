from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts.single_source_repair import (
    ALLOWED_FILES,
    RepairInputError,
    _car_aliases_from_text,
    _car_manifest_patch,
    _car_replay_metrics,
    _car_selection,
    _call_repair_model,
    _get_agent_response,
    _json_response,
    _strict_json_load,
    analyze_payload,
    validate_patch_text,
)


class SingleSourceRepairTests(unittest.TestCase):
    def _agent_args(self, directory: str, **overrides: object) -> SimpleNamespace:
        values = {
            "agent_prompt_out": str(Path(directory) / "prompt.md"),
            "agent_request_out": str(Path(directory) / "request.json"),
            "agent_response_in": None,
            "agent_request_in": None,
            "repo_kind": "phones",
            "base_sha": "a" * 40,
            "pages_run_id": "123",
            "chain_id": "chain-1",
            "round": 1,
            "model_label": "provider/model",
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_prepare_agent_request_does_not_call_python_model_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = self._agent_args(directory)
            with mock.patch("scripts.single_source_repair._call_repair_model") as fallback:
                result = _get_agent_response(args, "strict JSON", "single-source-patch", "b" * 64, "c" * 64)
            self.assertIsNone(result)
            fallback.assert_not_called()
            self.assertTrue(Path(args.agent_prompt_out).is_file())
            self.assertTrue(Path(args.agent_request_out).is_file())

    def test_agent_response_must_match_request_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prepare = self._agent_args(directory)
            _get_agent_response(prepare, "strict JSON", "single-source-patch", "b" * 64, "c" * 64)
            response_path = Path(directory) / "response.txt"
            response_path.write_text('{"ok": true}', encoding="utf-8")
            validate = self._agent_args(
                directory,
                agent_prompt_out=None,
                agent_request_out=None,
                agent_response_in=str(response_path),
                agent_request_in=str(Path(directory) / "request.json"),
            )
            content, model = _get_agent_response(
                validate,
                "strict JSON",
                "single-source-patch",
                "b" * 64,
                "c" * 64,
            )
            self.assertEqual('{"ok": true}', content)
            self.assertEqual("provider/model", model)
            request = json.loads(Path(directory, "request.json").read_text(encoding="utf-8"))
            self.assertEqual("provider/model", request["model"])
            request["base_sha"] = "d" * 40
            Path(directory, "request.json").write_text(json.dumps(request), encoding="utf-8")
            with self.assertRaisesRegex(RepairInputError, "binding"):
                _get_agent_response(
                    validate,
                    "strict JSON",
                    "single-source-patch",
                    "b" * 64,
                    "c" * 64,
                )

    def test_plan_key_is_not_consumed_by_python_fallback(self) -> None:
        with (
            mock.patch.dict("os.environ", {"VOLCENGINE_AGENTPLAN_API_KEY": "plan-secret"}, clear=True),
            mock.patch("scripts.single_source_repair.urllib.request.urlopen") as urlopen,
        ):
            with self.assertRaisesRegex(RepairInputError, "no repair model API key"):
                _call_repair_model("strict JSON")
        urlopen.assert_not_called()

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
        # ```json fences and opencode console progress lines are now tolerated
        self.assertEqual(
            _json_response('```json {"should_fix": false}```'),
            {"should_fix": False},
        )
        self.assertEqual(
            _json_response('> plan · deepseek-v4-flash\n\n-> Read prompt.md [offset=2001]\n```json\n{"should_fix": true, "confidence": 0.9, "evidence": ["e"], "analysis": "a"}\n```\n'),
            {"should_fix": True, "confidence": 0.9, "evidence": ["e"], "analysis": "a"},
        )

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
            (
                "config/safe_v2_absorption_manifest.json",
                "config/column_header_aliases.json",
            ),
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
        selected, aliases, confidence, evidence, _analysis = _car_selection(response, report)
        self.assertEqual(["a" * 24], [item["candidate_id"] for item in selected])
        self.assertEqual([], aliases)
        self.assertEqual(0.95, confidence)
        self.assertTrue(evidence)

        invented = dict(response, approved_candidate_ids=["b" * 24])
        with self.assertRaises(RepairInputError):
            _car_selection(invented, report)

    def test_car_column_aliases_require_diagnosis_allowlist(self) -> None:
        report = {
            "candidates": [],
            "column_diagnosis": {
                "suspects": [
                    {
                        "kind": "bare_value_header",
                        "column": "NOMI Mate 3.0",
                        "confidence": 0.45,
                    },
                    {
                        "kind": "package_value_header",
                        "column": "NOMI Mate 3.0_1 / NOMI Mate 3.0_2",
                        "columns": ["NOMI Mate 3.0_1", "NOMI Mate 3.0_2"],
                        "confidence": 0.9,
                    },
                ],
                "candidate_attributes": ["车载智能系统", "辅助驾驶芯片", "品牌"],
            },
        }
        response = {
            "approved_candidate_ids": [],
            "confidence": 0.9,
            "evidence": ["无"],
            "analysis": "列名修复验证",
            "column_aliases": [
                {
                    "column": "NOMI Mate 3.0",
                    "canonical": "车载智能系统",
                    "value": "NOMI Mate 3.0",
                    "confidence": 0.95,
                    "evidence": "该列取值仅是有/无标记",
                },
                {
                    "column": "NOMI Mate 3.0_1",
                    "canonical": "车载智能系统",
                    "value": "NOMI Mate 3.0",
                    "confidence": 0.92,
                    "evidence": "选装包描述/状态对，包名是值",
                },
            ],
        }
        _selected, aliases, _confidence, _evidence, _analysis = _car_selection(response, report)
        self.assertEqual(2, len(aliases))
        self.assertEqual("NOMI Mate 3.0", aliases[0]["column"])
        self.assertEqual("车载智能系统", aliases[0]["canonical"])

        # canonical outside the candidate attributes is rejected
        bad = {
            "column": "NOMI Mate 3.0",
            "canonical": "智能座舱芯片",
            "confidence": 0.95,
            "evidence": "新属性名",
        }
        _selected, _aliases, _conf, _ev, _an = _car_selection(
            dict(response, column_aliases=[bad]),
            report,
        )
        self.assertEqual([], _aliases)

        # column outside the diagnosis suspects is rejected
        bad = {
            "column": "品牌",
            "canonical": "车载智能系统",
            "confidence": 0.95,
            "evidence": "身份列",
        }
        _selected, _aliases, _conf, _ev, _an = _car_selection(
            dict(response, column_aliases=[bad]),
            report,
        )
        self.assertEqual([], _aliases)

        # canonical mapping into a protected identity attribute is rejected
        bad = {
            "column": "NOMI Mate 3.0",
            "canonical": "品牌",
            "confidence": 0.95,
            "evidence": "试图映射到身份列",
        }
        _selected, _aliases, _conf, _ev, _an = _car_selection(
            dict(response, column_aliases=[bad]),
            report,
        )
        self.assertEqual([], _aliases)

        # confidence below the alias floor is rejected
        bad = {
            "column": "NOMI Mate 3.0",
            "canonical": "车载智能系统",
            "confidence": 0.8,
            "evidence": "信心不足",
        }
        _selected, _aliases, _conf, _ev, _an = _car_selection(
            dict(response, column_aliases=[bad]),
            report,
        )
        self.assertEqual([], _aliases)

        # duplicate columns are rejected
        bad = {
            "column": "NOMI Mate 3.0",
            "canonical": "辅助驾驶芯片",
            "confidence": 0.95,
            "evidence": "重复",
        }
        _selected, _aliases, _conf, _ev, _an = _car_selection(
            dict(response, column_aliases=[response["column_aliases"][0], bad]),
            report,
        )
        self.assertEqual([], _aliases)

    def test_car_alias_config_validation(self) -> None:
        _car_aliases_from_text('{"version": 1, "aliases": []}')
        _car_aliases_from_text(
            '{"version": 1, "aliases": [{"column": "NOMI Mate 3.0", "canonical": "车载智能系统", "value": "NOMI Mate 3.0", "confidence": 0.95, "evidence": "e"}]}'
        )
        with self.assertRaises(RepairInputError):
            _car_aliases_from_text('{"version": 1, "aliases": [{"column": "品牌", "canonical": "品牌"}]}')
        with self.assertRaises(RepairInputError):
            _car_aliases_from_text('{"version": 1, "aliases": "nope"}')
        with self.assertRaises(RepairInputError):
            _car_aliases_from_text('{"version": 1, "aliases": [{"column": "A", "canonical": "B"}, {"column": "A", "canonical": "C"}]}')

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


    def test_car_alias_config_rejects_protected_attributes(self) -> None:
        from scripts.single_source_repair import _car_aliases_from_text

        # canonical 侧指向身份列
        try:
            _car_aliases_from_text(
                '{"version": 1, "aliases": [{"column": "NOMI Mate 3.0", "canonical": "品牌", "confidence": 0.95, "evidence": "e"}]}'
            )
            raise AssertionError("expected RepairInputError for protected canonical")
        except RepairInputError:
            pass
        # column 侧是身份列
        try:
            _car_aliases_from_text(
                '{"version": 1, "aliases": [{"column": "车系", "canonical": "车载智能系统", "confidence": 0.95, "evidence": "e"}]}'
            )
            raise AssertionError("expected RepairInputError for protected column")
        except RepairInputError:
            pass


    def test_generated_alias_patch_touches_only_alias_config(self) -> None:
        from scripts.single_source_repair import (
            _car_aliases_from_text,
            _car_aliases_patch,
            validate_patch_text,
        )

        repo_root = Path(__file__).resolve().parents[1]
        aliases_path = repo_root / ALLOWED_FILES["cars"][1]
        baseline = _car_aliases_from_text('{"version": 1, "aliases": []}')
        patch, _candidate = _car_aliases_patch(
            aliases_path,
            baseline,
            [{"column": "NOMI Mate 3.0", "canonical": "车载智能系统", "confidence": 0.95, "evidence": "e", "value": "NOMI Mate 3.0"}],
        )
        assert validate_patch_text(patch, "cars") == [ALLOWED_FILES["cars"][1]]


    def test_multi_alias_same_canonical_merges_distinct_values(self) -> None:
        import sys
        from pathlib import Path

        from unittest import mock

        from scripts.prepare_pages_payload import normalize_publish_row_headers

        scripts_dir = str(Path(__file__).resolve().parents[1] / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        if "merge_data" not in sys.modules:
            import merge_data  # noqa: F401
        if "scripts.merge_data" not in sys.modules:
            import scripts.merge_data  # noqa: F401

        row = {
            "品牌": "甲",
            "车型名称": "M",
            "车载智能系统": "Banyan",
            "NOMI Mate 3.0": "标配",
            "Xiaomi HAD": "选配",
        }

        def lookup(key):
            aliases = {
                "NOMI Mate 3.0": {"canonical": "车载智能系统", "value": "NOMI Mate 3.0"},
                "Xiaomi HAD": {"canonical": "车载智能系统", "value": "Xiaomi HAD"},
            }
            return aliases.get(key)

        with mock.patch("merge_data.header_alias_lookup", side_effect=lookup), mock.patch(
            "scripts.merge_data.header_alias_lookup",
            side_effect=lookup,
        ), mock.patch(
            "scripts.prepare_pages_payload.header_alias_lookup",
            side_effect=lookup,
        ):
            out = normalize_publish_row_headers(row)
        assert out["车载智能系统"] == "Banyan|NOMI Mate 3.0|Xiaomi HAD"
        assert "NOMI Mate 3.0" not in out
        assert "Xiaomi HAD" not in out


    def test_car_column_alias_value_rejects_pipe_and_newlines(self) -> None:
        report = {
            "candidates": [],
            "column_diagnosis": {
                "suspects": [
                    {"kind": "bare_value_header", "column": "NOMI Mate 3.0", "confidence": 0.45},
                ],
                "candidate_attributes": ["车载智能系统", "品牌"],
            },
        }
        base = {
            "approved_candidate_ids": [],
            "confidence": 0.9,
            "evidence": ["无"],
            "analysis": "值校验",
        }
        for bad_value in ("A|B", "A\nB", "A\rB"):
            bad = {
                "column": "NOMI Mate 3.0",
                "canonical": "车载智能系统",
                "value": bad_value,
                "confidence": 0.95,
                "evidence": "值污染",
            }
            _selected, aliases, _conf, _ev, _an = _car_selection(
                dict(base, column_aliases=[bad]),
                report,
            )
            assert aliases == [], f"expected degraded aliases for value {bad_value!r}"


    def test_publish_pipeline_degrades_gracefully_without_alias_config(self) -> None:
        import sys
        from pathlib import Path

        from unittest import mock

        from scripts.prepare_pages_payload import normalize_publish_row_headers

        scripts_dir = str(Path(__file__).resolve().parents[1] / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        if "merge_data" not in sys.modules:
            import merge_data  # noqa: F401
        if "scripts.merge_data" not in sys.modules:
            import scripts.merge_data  # noqa: F401

        # 等价于配置文件缺失/损坏后的降级状态：_load_header_aliases() 返回空 dict
        with mock.patch("merge_data._load_header_aliases", return_value={}), mock.patch(
            "scripts.merge_data._load_header_aliases",
            return_value={},
        ):
            row = {"品牌": "甲", "车载智能系统": "Banyan", "NOMI Mate 3.0": "标配"}
            out = normalize_publish_row_headers(row)
        assert out["车载智能系统"] == "Banyan"
        assert out["NOMI Mate 3.0"] == "标配"


if __name__ == "__main__":
    unittest.main()

