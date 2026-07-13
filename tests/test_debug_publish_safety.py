from __future__ import annotations

import json
import importlib.util
import subprocess
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


class PrepareDebugMergeInputsTests(unittest.TestCase):
    def run_prepare(self, stable: list[dict], debug: list[dict]) -> tuple[subprocess.CompletedProcess[str], list[dict]]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stable_path = root / "stable.json"
            debug_path = root / "debug.json"
            output_path = root / "prepared.json"
            stable_path.write_text(json.dumps(stable, ensure_ascii=False), encoding="utf-8")
            debug_path.write_text(json.dumps(debug, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "prepare_debug_merge_inputs.py"),
                    "--stable",
                    str(stable_path),
                    "--debug",
                    str(debug_path),
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
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


class VerifyPublishSupersetTests(unittest.TestCase):
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

    def test_actual_dongchedi_cache_and_progress_paths_are_guarded(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        sync = (SCRIPTS / "git_sync_progress.sh").read_text(encoding="utf-8")
        self.assertIn("/scripts/dongchedi/json/", ignore)
        self.assertIn('"scripts/dongchedi/progress.json"', sync)

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


if __name__ == "__main__":
    unittest.main()
