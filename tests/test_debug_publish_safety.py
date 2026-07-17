from __future__ import annotations

import csv
import json
import importlib.util
import os
import subprocess
from datetime import datetime, timezone
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_validator_module():
    path = SCRIPTS / "validate_workflow_expectations.py"
    spec = importlib.util.spec_from_file_location("workflow_expectations_regression", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_zero_to_whole_module():
    path = SCRIPTS / "crawl_zero_to_whole_ratio.py"
    spec = importlib.util.spec_from_file_location("zero_to_whole_regression", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_merge_module():
    path = SCRIPTS / "merge_data.py"
    spec = importlib.util.spec_from_file_location("merge_data_regression", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ZeroToWholeRatioDateTests(unittest.TestCase):
    def test_dated_artifact_uses_shanghai_date_when_utc_is_previous_day(self) -> None:
        module = load_zero_to_whole_module()
        self.assertEqual("20260714", module.shanghai_datestamp(datetime(2026, 7, 13, 16, 30, tzinfo=timezone.utc)))


class PrepareDebugMergeInputsTests(unittest.TestCase):
    def run_prepare(
        self,
        stable: list[dict],
        debug: list[dict],
        *,
        debug_mode: str | None = None,
        trigger_source: str | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], list[dict]]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stable_path = root / "stable.json"
            debug_path = root / "debug.json"
            output_path = root / "prepared.json"
            stable_path.write_text(json.dumps(stable, ensure_ascii=False), encoding="utf-8")
            debug_path.write_text(json.dumps(debug, ensure_ascii=False), encoding="utf-8")
            command = [
                    sys.executable,
                    str(SCRIPTS / "prepare_debug_merge_inputs.py"),
                    "--stable",
                    str(stable_path),
                    "--debug",
                    str(debug_path),
                    "--output",
                    str(output_path),
                ]
            env = os.environ.copy()
            env.pop("DEBUG_MODE", None)
            env.pop("TRIGGER_SOURCE", None)
            if debug_mode is not None:
                env["DEBUG_MODE"] = debug_mode
            if trigger_source is not None:
                env["TRIGGER_SOURCE"] = trigger_source
            result = subprocess.run(
                command,
                capture_output=True,
                env=env,
                text=True,
                check=False,
            )
            rows = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else []
            return result, rows

    def test_stable_row_wins_and_debug_only_identity_is_appended(self) -> None:
        stable = [
            {"车系ID": "100", "车型名称": "A Max", "年款": "2026", "价格": "stable"},
            {"品牌": "甲", "车系": "A", "车型名称": "A Pro", "年款": "2025", "价格": "stable-fallback"},
        ]
        debug = [
            {"车系ID": "100", "车型名称": "A Max", "年款": "2026", "价格": "debug"},
            {"品牌": "甲", "车系": "A", "车型名称": "A Pro", "年款": "2025", "价格": "debug-fallback"},
            {"车系ID": "101", "车型名称": "A Ultra", "年款": "2026", "价格": "new"},
        ]

        result, rows = self.run_prepare(stable, debug)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(stable + [debug[-1]], rows)
        stats = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(
            {
                "stable_input": 2,
                "debug_input": 3,
                "debug_duplicates_dropped": 0,
                "overlap_kept_stable": 2,
                "debug_added": 1,
                "output_rows": 3,
            },
            stats,
        )

    def test_incomplete_identity_fails_closed(self) -> None:
        incomplete = [{"品牌": "甲", "车系": "A", "车型名称": "A"}]
        result, _ = self.run_prepare(incomplete, [])
        self.assertNotEqual(0, result.returncode)

    def test_empty_or_duplicate_input_fails_closed(self) -> None:
        row = {"车系ID": "100", "车型名称": "A", "年款": "2026"}
        for stable, debug in [([], [row]), ([row], []), ([row, row], [row]), ([row], [row, row])]:
            with self.subTest(stable=len(stable), debug=len(debug)):
                result, _ = self.run_prepare(stable, debug)
                self.assertNotEqual(0, result.returncode)

    def test_dongchedi_partial_dedupes_incoming_rows_but_stable_still_wins(self) -> None:
        stable = [{"车系ID": "100", "车型名称": "A", "年款": "2026", "价格": "stable"}]
        first_new = {"车系ID": "101", "车型名称": "B", "年款": "2026", "价格": "first"}
        debug = [
            {"车系ID": "100", "车型名称": "A", "年款": "2026", "价格": "debug"},
            {"车系ID": "100", "车型名称": "A", "年款": "2026", "价格": "debug-duplicate"},
            first_new,
            {"车系ID": "101", "车型名称": "B", "年款": "2026", "价格": "second"},
        ]

        result, rows = self.run_prepare(
            stable,
            debug,
            debug_mode="false",
            trigger_source="dongchedi-crawl",
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(stable + [first_new], rows)
        self.assertEqual(
            {
                "stable_input": 1,
                "debug_input": 4,
                "debug_duplicates_dropped": 2,
                "overlap_kept_stable": 1,
                "debug_added": 1,
                "output_rows": 2,
            },
            json.loads(result.stdout.strip().splitlines()[-1]),
        )

    def test_dongchedi_partial_dedupe_never_allows_duplicate_stable_input(self) -> None:
        row = {"车系ID": "100", "车型名称": "A", "年款": "2026"}

        result, _ = self.run_prepare(
            [row, dict(row)],
            [row],
            debug_mode="false",
            trigger_source="dongchedi-crawl",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("stable input contains duplicate identities", result.stderr)

    def test_partial_dedupe_environment_fails_closed_outside_normal_dongchedi(self) -> None:
        row = {"车系ID": "100", "车型名称": "A", "年款": "2026"}
        cases = [
            (None, "dongchedi-crawl"),
            ("", "dongchedi-crawl"),
            ("true", "dongchedi-crawl"),
            ("TRUE", "dongchedi-crawl"),
            ("false", "autohome-crawl"),
            (None, None),
        ]
        for debug_mode, trigger_source in cases:
            with self.subTest(debug_mode=debug_mode, trigger_source=trigger_source):
                result, _ = self.run_prepare(
                    [row],
                    [row, dict(row)],
                    debug_mode=debug_mode,
                    trigger_source=trigger_source,
                )
                self.assertNotEqual(0, result.returncode)
                self.assertIn("debug input contains duplicate identities", result.stderr)

    def test_missing_series_id_uses_fallback_and_identity_keeps_model_and_year(self) -> None:
        stable = [{"车系ID": "-", "品牌": "甲", "车系": "A", "车型名称": "A", "年款": "2025"}]
        debug = [
            {"车系ID": "100", "车型名称": "A", "年款": "2025"},
            {"车系ID": "100", "车型名称": "A Pro", "年款": "2025"},
            {"车系ID": "100", "车型名称": "A", "年款": "2026"},
        ]
        result, rows = self.run_prepare(stable, debug)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(stable + debug, rows)

    def test_yiche_no_year_keeps_stable_and_appends_debug_only(self) -> None:
        stable = [{"数据来源": "仅易车", "品牌": "甲", "车系": "A", "车型名称": "易车受限款", "年款": "", "价格": "stable"}]
        debug = [
            {"数据来源": "仅易车", "品牌": "甲", "车系": "A", "车型名称": "易车受限款", "年款": "-", "价格": "debug"},
            {"数据来源": "仅易车", "品牌": "甲", "车系": "A", "车型名称": "易车新增款", "年款": "", "价格": "new"},
        ]

        result, rows = self.run_prepare(stable, debug)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(stable + [debug[1]], rows)
        stats = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(1, stats["overlap_kept_stable"])
        self.assertEqual(1, stats["debug_added"])

    def test_yiche_no_year_without_brand_or_series_uses_model_identity(self) -> None:
        row = {"数据来源": "仅易车", "品牌": "甲", "车型名称": "易车受限款", "年款": ""}

        result, rows = self.run_prepare([row], [row])

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([row], rows)

    def test_yiche_no_year_without_model_still_fails_closed(self) -> None:
        row = {"数据来源": "仅易车", "品牌": "甲", "车系": "A", "车型名称": "", "年款": ""}

        result, _ = self.run_prepare([row], [row])

        self.assertNotEqual(0, result.returncode)
        self.assertIn("identity requires", result.stderr)

    def test_non_yiche_no_year_still_fails_closed(self) -> None:
        row = {"数据来源": "仅懂车帝", "品牌": "甲", "车系": "A", "车型名称": "未知年款", "年款": ""}

        result, _ = self.run_prepare([row], [row])

        self.assertNotEqual(0, result.returncode)
        self.assertIn("identity requires", result.stderr)

    def test_yiche_explicit_year_uses_existing_year_identity(self) -> None:
        stable = [{"数据来源": "仅易车", "品牌": "甲", "车系": "A", "车型名称": "易车旧款", "年款": "2021", "价格": "stable"}]
        debug = [{"数据来源": "仅易车", "品牌": "甲", "车系": "A", "车型名称": "易车旧款", "年款": "2021", "价格": "debug"}]

        result, rows = self.run_prepare(stable, debug)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(stable, rows)

    def test_duplicate_yiche_no_year_minimal_identity_fails_closed(self) -> None:
        row = {"数据来源": "仅易车", "车型名称": "易车受限款", "年款": ""}

        result, _ = self.run_prepare([row, dict(row)], [row])

        self.assertNotEqual(0, result.returncode)
        self.assertIn("duplicate identities", result.stderr)


class VerifyPublishSupersetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.merge_data = load_merge_module()

    def run_verify(self, baseline: list[dict], candidate: list[dict]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_path = root / "baseline.json"
            candidate_path = root / "candidate.json"
            baseline_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "verify_publish_superset.py"),
                    "--baseline",
                    str(baseline_path),
                    "--candidate",
                    str(candidate_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_identity_superset_with_non_decreasing_rows_passes(self) -> None:
        baseline = [{"车系ID": "100", "车型名称": "A", "年款": "2026"}]
        candidate = baseline + [{"品牌": "乙", "车系": "B", "车型名称": "B Pro", "年款": "2025"}]

        result = self.run_verify(baseline, candidate)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            {"baseline_rows": 1, "candidate_rows": 2, "retained_rows": 1, "added_rows": 1, "missing_rows": 0},
            json.loads(result.stdout.strip().splitlines()[-1]),
        )

    def test_model_name_year_fallback_matches_explicit_baseline_year(self) -> None:
        baseline = [{"车系ID": "100", "车型名称": "A 2026款 Pro", "年款": "2026"}]
        candidate = [{"车系ID": "100", "车型名称": "A 2026款 Pro", "年款": ""}]

        result = self.run_verify(baseline, candidate)

        self.assertEqual(0, result.returncode, result.stderr)

    def test_one_stable_and_twenty_five_debug_year_fallback_rows_verify(self) -> None:
        baseline = [{"车系ID": "100", "车型名称": "A 2026款 Pro", "年款": "2026"}]
        debug_rows = [
            {"车系ID": str(101 + index), "车型名称": f"{chr(66 + index)} 2026款 Pro", "年款": ""}
            for index in range(25)
        ]
        candidate = self.merge_data.norm_rows(baseline + debug_rows, "汽车之家")

        result = self.run_verify(baseline, candidate)

        self.assertEqual(26, len(candidate))
        self.assertTrue(all(row["年款"] == "2026" for row in candidate))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            {"baseline_rows": 1, "candidate_rows": 26, "retained_rows": 1, "added_rows": 25, "missing_rows": 0},
            json.loads(result.stdout.strip().splitlines()[-1]),
        )

    def test_norm_rows_preserves_explicit_year_when_model_name_has_other_year(self) -> None:
        rows = [{"车系ID": "100", "车型名称": "A 2026款 Pro", "年款": "2025"}]

        normalized = self.merge_data.norm_rows(rows, "汽车之家")

        self.assertEqual("2025", normalized[0]["年款"])

    def test_norm_rows_keeps_unparseable_missing_year_fail_closed(self) -> None:
        rows = [{"车系ID": "100", "车型名称": "A Pro", "年款": ""}]

        normalized = self.merge_data.norm_rows(rows, "汽车之家")
        result = self.run_verify([{"车系ID": "100", "车型名称": "A Pro", "年款": "2026"}], normalized)

        self.assertEqual("", normalized[0]["年款"])
        self.assertNotEqual(0, result.returncode)

    def test_yiche_no_year_superset_can_verify(self) -> None:
        baseline = [{"数据来源": "仅易车", "品牌": "甲", "车系": "A", "车型名称": "易车受限款", "年款": ""}]
        candidate = baseline + [{"车系ID": "100", "车型名称": "A", "年款": "2026"}]

        result = self.run_verify(baseline, candidate)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            {"baseline_rows": 1, "candidate_rows": 2, "retained_rows": 1, "added_rows": 1, "missing_rows": 0},
            json.loads(result.stdout.strip().splitlines()[-1]),
        )

    def test_merge_single_row_and_single_source_rows_backfill_model_name_year(self) -> None:
        merged = self.merge_data.merge_single_row(
            {"车系ID": "100", "车型名称": "A 2026款 Pro", "年款": "-"},
            {"车系ID": "100", "车型名称": "A 2026款 Pro", "年款": ""},
        )
        autohome_only = self.merge_data.norm_rows([{"车系ID": "101", "车型名称": "B 2026款 Pro", "年款": ""}], "汽车之家")
        dongchedi_only = self.merge_data.norm_rows([{"车系ID": "102", "车型名称": "C 2026款 Pro", "年款": "-"}], "懂车帝")

        self.assertEqual("2026", merged["年款"])
        self.assertEqual("2026", autohome_only[0]["年款"])
        self.assertEqual("2026", dongchedi_only[0]["年款"])

    def test_missing_identity_fails_even_when_candidate_has_more_rows(self) -> None:
        baseline = [
            {"车系ID": "100", "车型名称": "A", "年款": "2026"},
            {"车系ID": "101", "车型名称": "B", "年款": "2026"},
        ]
        candidate = [
            {"车系ID": "100", "车型名称": "A", "年款": "2026"},
            {"车系ID": "200", "车型名称": "C", "年款": "2026"},
            {"车系ID": "201", "车型名称": "D", "年款": "2026"},
        ]

        result = self.run_verify(baseline, candidate)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("missing", result.stderr.lower())

    def test_row_count_decrease_fails_closed(self) -> None:
        baseline = [
            {"车系ID": "100", "车型名称": "A", "年款": "2026"},
            {"车系ID": "100", "车型名称": "A", "年款": "2026"},
        ]
        candidate = [{"车系ID": "100", "车型名称": "A", "年款": "2026"}]

        result = self.run_verify(baseline, candidate)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("row count", result.stderr.lower())

    def test_pre_2022_baseline_rows_do_not_block_2022_plus_publication(self) -> None:
        baseline = [
            {"车系ID": "old", "车型名称": "旧款", "年款": "2021"},
            {"车系ID": "new", "车型名称": "新款", "年款": "2022"},
        ]
        candidate = [{"车系ID": "new", "车型名称": "新款", "年款": "2022"}]

        result = self.run_verify(baseline, candidate)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            {"baseline_rows": 1, "candidate_rows": 1, "retained_rows": 1, "added_rows": 0, "missing_rows": 0},
            json.loads(result.stdout.strip().splitlines()[-1]),
        )


class PreservePublishBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.merge_data = load_merge_module()

    def run_preserve(self, baseline: list[dict], candidate: list[dict]) -> tuple[subprocess.CompletedProcess[str], dict]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {
                "baseline": root / "baseline.json",
                "merged_json": root / "merged.json",
                "merged_csv": root / "merged.csv",
                "filtered_json": root / "filtered.json",
                "filtered_csv": root / "filtered.csv",
            }
            paths["baseline"].write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")
            paths["merged_json"].write_text(json.dumps(candidate, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "preserve_publish_baseline.py"),
                    "--baseline",
                    str(paths["baseline"]),
                    "--merged-json",
                    str(paths["merged_json"]),
                    "--merged-csv",
                    str(paths["merged_csv"]),
                    "--filtered-json",
                    str(paths["filtered_json"]),
                    "--filtered-csv",
                    str(paths["filtered_csv"]),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            outputs = {
                "merged_json": json.loads(paths["merged_json"].read_text(encoding="utf-8")),
                "merged_csv": self.read_csv(paths["merged_csv"]),
                "filtered_json": self.read_json(paths["filtered_json"]),
                "filtered_csv": self.read_csv(paths["filtered_csv"]),
                "temp_files": sorted(path.name for path in root.iterdir() if path.name.startswith(".")),
            }
            return result, outputs

    @staticmethod
    def read_json(path: Path) -> list[dict] | None:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    @staticmethod
    def read_csv(path: Path) -> list[dict] | None:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))

    @staticmethod
    def csv_rows(rows: list[dict], fieldnames: list[str]) -> list[dict[str, str]]:
        return [{field: str(row.get(field, "-")) for field in fieldnames} for row in rows]

    def test_baseline_wins_and_all_publish_assets_share_one_final_row_set(self) -> None:
        baseline = [
            {"车系ID": "old", "车型名称": "旧款", "年款": "2021", "价格": "old"},
            {"车系ID": "100", "车型名称": "A", "年款": "2026", "价格": "published"},
            {"车系ID": "101", "车型名称": "B", "年款": "2025", "价格": "published"},
        ]
        candidate = [
            {"车系ID": "old-debug", "车型名称": "旧调试款", "年款": "2021", "价格": "old-debug"},
            {"车系ID": "100", "车型名称": "A", "年款": "2026", "价格": "candidate"},
            {"车系ID": "102", "车型名称": "C", "年款": "2026", "价格": "new"},
        ]

        result, outputs = self.run_preserve(baseline, candidate)

        expected = baseline[1:] + [candidate[2]]
        expected_filtered = [row for row in expected if self.merge_data.filter_car(row)]
        header = self.merge_data.collect_fields(expected)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(expected, outputs["merged_json"])
        self.assertEqual(self.csv_rows(expected, header), outputs["merged_csv"])
        self.assertEqual(expected_filtered, outputs["filtered_json"])
        self.assertEqual(self.csv_rows(expected_filtered, header), outputs["filtered_csv"])
        self.assertEqual([], outputs["temp_files"])
        self.assertEqual(
            {
                "baseline_rows": 2,
                "candidate_input_rows": 2,
                "overlap_kept_baseline": 1,
                "candidate_added": 1,
                "candidate_output_rows": 3,
            },
            json.loads(result.stdout.strip().splitlines()[-1]),
        )

    def test_invalid_empty_or_duplicate_inputs_fail_closed_without_temp_files(self) -> None:
        row = {"车系ID": "100", "车型名称": "A", "年款": "2026"}
        cases = [
            ([{"车系ID": "100", "车型名称": "A"}], [row]),
            ([row, row], [row]),
            ([row], [row, row]),
            ([row], []),
        ]
        for baseline, candidate in cases:
            with self.subTest(baseline=len(baseline), candidate=len(candidate)):
                result, outputs = self.run_preserve(baseline, candidate)
                self.assertNotEqual(0, result.returncode)
                self.assertEqual([], outputs["temp_files"])

    def test_yiche_no_year_baseline_is_preserved(self) -> None:
        baseline = [{"数据来源": "仅易车", "车型名称": "易车受限款", "年款": "", "价格": "published"}]
        candidate = [
            {"数据来源": "仅易车", "车型名称": "易车受限款", "年款": "-", "价格": "candidate"},
            {"数据来源": "仅易车", "车型名称": "易车新增款", "年款": "", "价格": "new"},
        ]

        result, outputs = self.run_preserve(baseline, candidate)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(baseline + [candidate[1]], outputs["merged_json"])


class WorkflowValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator_module()

    def check_mutated_merge(self, text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "merge-and-filter.yml"
            path.write_text(text, encoding="utf-8")
            errors: list[str] = []
            self.validator.check_merge_workflow(path, errors)
            return errors

    def check_mutated_crawler(self, workflow_name: str, text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / workflow_name
            path.write_text(text, encoding="utf-8")
            errors: list[str] = []
            self.validator.check_crawler_workflow(path, errors)
            return errors

    def test_debug_self_heal_without_exclusion_is_rejected(self) -> None:
        path = ROOT / ".github/workflows/crawl-dongchedi.yml"
        text = path.read_text(encoding="utf-8")
        mutated = text.replace(
            "steps.classify_step2.outputs.should_fix == 'true' && github.event.inputs.debug_mode != 'true'",
            "steps.classify_step2.outputs.should_fix == 'true'",
            1,
        )
        errors = self.check_mutated_crawler(path.name, mutated)
        self.assertTrue(any("自动修复/重试路径" in error for error in errors))

    def test_dongchedi_debug_incomplete_must_fail_closed(self) -> None:
        path = ROOT / ".github/workflows/crawl-dongchedi.yml"
        text = path.read_text(encoding="utf-8")
        mutated = text.replace(
            'echo "failed=true" >> "$GITHUB_OUTPUT"',
            'echo "failed=false" >> "$GITHUB_OUTPUT"',
            1,
        )
        errors = self.check_mutated_crawler(path.name, mutated)
        self.assertTrue(any("失败关闭" in error for error in errors))

    def test_actual_dongchedi_cache_and_progress_paths_are_guarded(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        sync = (SCRIPTS / "git_sync_progress.sh").read_text(encoding="utf-8")
        self.assertIn("/scripts/dongchedi/json/", ignore)
        self.assertIn('"scripts/dongchedi/progress.json"', sync)
        self.assertIn("python3 scripts/merge_progress_json.py", sync)
        self.assertIn("if finish_rebase; then", sync)
        self.assertNotIn("finish_rebase || true", sync)

    def test_partial_autohome_upload_must_trigger_merge(self) -> None:
        path = ROOT / ".github/workflows/crawl-autohome.yml"
        text = path.read_text(encoding="utf-8")
        mutated = text.replace(
            "if: steps.upload_autohome.outcome == 'success'",
            "if: steps.upload_autohome.outcome == 'success' && steps.step1.outputs.complete == 'true'",
            1,
        )
        errors = self.check_mutated_crawler(path.name, mutated)
        self.assertTrue(any("自动触发合并" in error for error in errors))

    def test_partial_autohome_artifact_must_enter_safe_incremental_merge(self) -> None:
        text = (ROOT / ".github/workflows/merge-and-filter.yml").read_text(encoding="utf-8")
        errors = self.check_mutated_merge(text.replace("autoHome_partial_prepared.json", "autoHome_stable.json"))
        self.assertTrue(any("partial artifact" in error for error in errors))

    def test_partial_dongchedi_artifact_must_enter_safe_incremental_merge(self) -> None:
        text = (ROOT / ".github/workflows/merge-and-filter.yml").read_text(encoding="utf-8")
        errors = self.check_mutated_merge(text.replace("dongchedi_partial_prepared.json", "dongchedi_stable.json"))
        self.assertTrue(any("partial artifact" in error for error in errors))

    def test_partial_dedupe_environment_must_stay_on_download_step(self) -> None:
        text = (ROOT / ".github/workflows/merge-and-filter.yml").read_text(encoding="utf-8")
        debug_line = "          DEBUG_MODE: ${{ github.event.inputs.debug_mode || 'false' }}\n"
        missing = self.check_mutated_merge(text.replace(debug_line, "", 1))
        self.assertTrue(any("partial 去重边界" in error for error in missing))

        source_line = "          TRIGGER_SOURCE: ${{ github.event.inputs.trigger_source }}\n"
        moved = text.replace(source_line, "", 1)
        moved = moved.replace(
            "      - name: 安装合并依赖\n        run: pip install requests beautifulsoup4 lxml pdfplumber pypdf\n",
            "      - name: 安装合并依赖\n        env:\n"
            + source_line
            + "        run: pip install requests beautifulsoup4 lxml pdfplumber pypdf\n",
            1,
        )
        moved_errors = self.check_mutated_merge(moved)
        self.assertTrue(any("partial 去重边界" in error for error in moved_errors))

    def test_dongchedi_full_marker_requires_step2_completion(self) -> None:
        path = ROOT / ".github/workflows/crawl-dongchedi.yml"
        text = path.read_text(encoding="utf-8")
        mutated = text.replace(" && (steps.step2.outputs.complete == 'true' || steps.retry_step2.outputs.complete == 'true')", "", 1)
        errors = self.check_mutated_crawler(path.name, mutated)
        self.assertTrue(any("完成标记" in error for error in errors))

    def test_missing_prepare_reports_errors_without_traceback(self) -> None:
        text = (ROOT / ".github/workflows/merge-and-filter.yml").read_text(encoding="utf-8")
        errors = self.check_mutated_merge(text.replace("scripts/prepare_debug_merge_inputs.py", "scripts/removed.py"))
        self.assertTrue(errors)

    def test_prepare_after_merge_is_rejected(self) -> None:
        text = (ROOT / ".github/workflows/merge-and-filter.yml").read_text(encoding="utf-8")
        marker = "scripts/prepare_debug_merge_inputs.py"
        first, remainder = text.split(marker, 1)
        middle, last = remainder.split(marker, 1)
        mutated = first + marker + middle + "scripts/removed.py" + last + f"\n# {marker}\n"
        errors = self.check_mutated_merge(mutated)
        self.assertTrue(any("先规范化" in error for error in errors))

    def test_debug_publish_baseline_preservation_cannot_be_removed(self) -> None:
        text = (ROOT / ".github/workflows/merge-and-filter.yml").read_text(encoding="utf-8")
        errors = self.check_mutated_merge(text.replace("scripts/preserve_publish_baseline.py", "scripts/removed.py"))
        self.assertTrue(any("基线保留" in error for error in errors))

    def test_debug_stable_baseline_can_fall_back_to_historical_artifact(self) -> None:
        text = (ROOT / ".github/workflows/merge-and-filter.yml").read_text(encoding="utf-8")
        self.assertIn('if [ "$DEBUG_MODE" = "true" ]; then', text)
        self.assertIn("AUTOHOME_STABLE_MIN_DATE_ARGS=()", text)
        self.assertIn("DONGCHEDI_STABLE_MIN_DATE_ARGS=()", text)
        self.assertFalse(self.check_mutated_merge(text))

    def test_normal_stable_baselines_keep_independent_current_half_month_limits(self) -> None:
        text = (ROOT / ".github/workflows/merge-and-filter.yml").read_text(encoding="utf-8")
        for source in ("AUTOHOME", "DONGCHEDI"):
            with self.subTest(source=source):
                mutated = text.replace(
                    f'{source}_STABLE_MIN_DATE_ARGS=(--min-date "$MIN_ARTIFACT_DATE")',
                    f"{source}_STABLE_MIN_DATE_ARGS=()",
                    1,
                )
                errors = self.check_mutated_merge(mutated)
                self.assertTrue(any("普通半月限制" in error for error in errors))

    def test_missing_stable_artifact_delegates_to_safety_validation(self) -> None:
        text = (ROOT / ".github/workflows/merge-and-filter.yml").read_text(encoding="utf-8")
        self.assertIn(
            'echo "爬虫 stable artifact 尚未齐备，交由完整性校验安全跳过"\n            exit 0',
            text,
        )

    def test_partial_history_fallback_requires_exact_fresh_successful_attempt(self) -> None:
        text = (ROOT / ".github/workflows/merge-and-filter.yml").read_text(encoding="utf-8")
        mutations = (
            (text.replace("/attempts/$CRAWLER_RUN_ATTEMPT", "", 1), "精确成功 attempt"),
            (text.replace('"$RUN_CONCLUSION" != "success"', '"$RUN_CONCLUSION" != "failure"', 1), "精确成功 attempt"),
            (text.replace('"$ARTIFACT_DATE" < "$MIN_ARTIFACT_DATE"', '"$ARTIFACT_DATE" > "$MIN_ARTIFACT_DATE"', 1), "精确成功 attempt"),
            (text.replace('"$ARTIFACT_CREATED_AT" < "$RUN_STARTED_AT"', '"$ARTIFACT_CREATED_AT" > "$RUN_STARTED_AT"', 1), "精确成功 attempt"),
            (text.replace('"$ARTIFACT_CREATED_AT" > "$RUN_UPDATED_AT"', '"$ARTIFACT_CREATED_AT" < "$RUN_UPDATED_AT"', 1), "精确成功 attempt"),
            (text.replace('if [ "${#PARTIAL_ARTIFACTS[@]}" -gt 1 ]; then', 'if [ "${#PARTIAL_ARTIFACTS[@]}" -gt 2 ]; then', 1), "精确成功 attempt"),
            (text.replace("DONGCHEDI_STABLE_MIN_DATE_ARGS=()\n                fi", "AUTOHOME_STABLE_MIN_DATE_ARGS=()\n                  DONGCHEDI_STABLE_MIN_DATE_ARGS=()\n                fi", 1), "精确成功 attempt"),
            (text.replace("actions/artifacts/$PARTIAL_ARTIFACT_ID/zip", "actions/artifacts/by-name/zip", 1), "partial artifact"),
        )
        for mutated, expected_error in mutations:
            with self.subTest(expected_error=expected_error):
                errors = self.check_mutated_merge(mutated)
                self.assertTrue(any(expected_error in error for error in errors))


class MergePagesYearTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.merge_data = load_merge_module()

    def test_pages_year_filter_keeps_only_2022_and_newer(self) -> None:
        rows = [
            {"年款": "2021", "车型名称": "旧款"},
            {"年款": "2022", "车型名称": "新款"},
            {"年款": "-", "车型名称": "测试 2023款 Pro"},
            {"年款": "", "车型名称": "未知年款"},
            {"年款": "", "车型名称": "易车无年款", "数据来源": "仅易车"},
            {"年款": "", "车型名称": "易车补充无年款", "数据来源": "汽车之家+易车"},
            {"年款": "2021", "车型名称": "易车旧款", "数据来源": "仅易车"},
            {"年款": "", "车型名称": "懂车帝无年款", "数据来源": "仅懂车帝"},
        ]

        kept = [row["车型名称"] for row in rows if self.merge_data.keep_pages_year(row)]

        self.assertEqual(["新款", "测试 2023款 Pro", "易车无年款", "易车补充无年款"], kept)


class PagesPaginationTests(unittest.TestCase):
    def test_pages_supports_direct_page_jump(self) -> None:
        html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        script = (ROOT / "docs/app.js").read_text(encoding="utf-8")

        self.assertIn('id="pageJump" type="number"', html)
        self.assertIn('id="goPage"', html)
        self.assertIn('els.goPage.addEventListener("click", jumpToPage)', script)
        self.assertIn('els.pageJump.addEventListener("keydown"', script)
        self.assertIn("Math.min(pageCount, Math.max(1, requested))", script)


if __name__ == "__main__":
    unittest.main()
