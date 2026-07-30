#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PagesPayloadAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = load("pages_payload_audit", SCRIPTS / "audit_pages_payload.py")

    @staticmethod
    def row(model_id: str, sources: str) -> dict:
        return {
            "品牌": "比亚迪",
            "车系": "汉",
            "车系ID": "100",
            "车型名称": f"2026款 EV 506KM 尊贵型 {model_id}",
            "年款": "2026",
            "车款ID": model_id,
            "易车上市状态": "approved",
            "数据来源": sources,
        }

    def test_final_payload_identity_and_source_superset_passes(self) -> None:
        baseline = [self.row("1", "汽车之家")]
        candidate = [self.row("1", "汽车之家|易车"), self.row("2", "易车")]
        report = self.audit.audit_payload(baseline, candidate, head_sha="abc")
        self.assertEqual("pass", report["status"])
        self.assertEqual("regression-only", report["audit_scope"])
        self.assertEqual([], report["violations"])
        self.assertEqual(1, report["stats"]["added_identities"])

    def test_alias_normalization_passes(self) -> None:
        report = self.audit.audit_payload(
            [self.row("1", "仅汽车之家")],
            [self.row("1", "汽车之家+懂车帝")],
            head_sha="abc",
        )
        self.assertEqual("pass", report["status"])
        self.assertEqual([], report["violations"])

    def test_unknown_source_replacement_blocks(self) -> None:
        report = self.audit.audit_payload(
            [self.row("1", "第三方A")],
            [self.row("1", "汽车之家")],
            head_sha="abc",
        )
        self.assertEqual("blocked", report["status"])
        self.assertEqual("source_regression", report["violations"][0]["code"])

    def test_mixed_unknown_token_preserved(self) -> None:
        report = self.audit.audit_payload(
            [self.row("1", "汽车之家+第三方A")],
            [self.row("1", "汽车之家")],
            head_sha="abc",
        )
        self.assertEqual("blocked", report["status"])
        self.assertEqual("source_regression", report["violations"][0]["code"])

    def test_source_regression_is_blocked_without_raw_vehicle_fields(self) -> None:
        report = self.audit.audit_payload(
            [self.row("1", "汽车之家|易车")],
            [self.row("1", "汽车之家")],
            head_sha="abc",
        )
        self.assertEqual("blocked", report["status"])
        violation = report["violations"][0]
        self.assertEqual("source_regression", violation["code"])
        self.assertEqual(1, violation["count"])
        rendered = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("尊贵型", rendered)
        self.assertNotIn("易车", rendered)

    def test_source_retirement_passes_when_source_remains_in_same_series_year(self) -> None:
        report = self.audit.audit_payload(
            [self.row("1", "汽车之家+懂车帝")],
            [self.row("1", "汽车之家"), self.row("2", "懂车帝")],
            head_sha="abc",
        )
        self.assertEqual("pass", report["status"])
        self.assertEqual([], report["violations"])
        self.assertEqual(1, report["stats"]["intentional_source_retirements"])

    def test_missing_identity_is_blocked(self) -> None:
        report = self.audit.audit_payload(
            [self.row("1", "汽车之家"), self.row("2", "易车")],
            [self.row("1", "汽车之家")],
            head_sha="abc",
        )
        self.assertEqual("blocked", report["status"])
        self.assertEqual("missing_identity", report["violations"][0]["code"])

    def test_cli_always_writes_report_and_binds_file_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            report = root / "report.json"
            baseline.write_text(json.dumps([self.row("1", "汽车之家|易车")], ensure_ascii=False), encoding="utf-8")
            candidate.write_text(json.dumps([self.row("1", "汽车之家")], ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "audit_pages_payload.py"), "--baseline", str(baseline), "--candidate", str(candidate), "--report", str(report), "--head-sha", "deadbeef"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(0, result.returncode)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual("deadbeef", payload["head_sha"])
            self.assertRegex(payload["baseline_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(payload["candidate_sha256"], r"^[0-9a-f]{64}$")


class SelfHealTrustRootScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scope = load("codex_scope", SCRIPTS / "ensure_codex_autofix_scope.py")

    def test_trust_roots_and_all_workflows_are_denied(self) -> None:
        denied = [
            ".github/workflows/new-bypass.yml",
            "AGENTS.md",
            "site/data/latest.json",
            "scripts/audit_pages_payload.py",
            "scripts/prepare_pages_payload.py",
            "scripts/preserve_publish_baseline.py",
            "scripts/ensure_codex_autofix_scope.py",
            "requirements.txt",
            "tests/test_pages_payload_audit.py",
        ]
        for path in denied:
            with self.subTest(path=path):
                self.assertFalse(self.scope.is_allowed(path))

    def test_explicit_business_paths_and_non_root_tests_remain_allowed(self) -> None:
        for path in ["scripts/merge_data.py", "scripts/crawl_yiche.py", "tests/test_merge_regression.py", "README.md"]:
            with self.subTest(path=path):
                self.assertTrue(self.scope.is_allowed(path))

    def test_protected_rename_exposes_both_old_and_new_paths(self) -> None:
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "ci@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "CI"], cwd=root, check=True)
            old = root / ".github/workflows/deploy-pages.yml"
            old.parent.mkdir(parents=True)
            old.write_text("name: protected\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, capture_output=True)
            new = root / ".github/workflows/deploy-pages-v2.yml"
            old.rename(new)
            try:
                os.chdir(root)
                paths = self.scope.changed_files()
            finally:
                os.chdir(previous)
        self.assertIn(".github/workflows/deploy-pages.yml", paths)
        self.assertIn(".github/workflows/deploy-pages-v2.yml", paths)


class PagesAuditWorkflowWiringTests(unittest.TestCase):
    def test_audit_runs_after_final_transform_and_before_manifest(self) -> None:
        text = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
        audit = text.index("python scripts/audit_pages_payload.py")
        self.assertGreater(audit, text.rindex("python scripts/prepare_pages_payload.py"))
        self.assertLess(audit, text.index('with open("site/data/manifest.json"'))
        self.assertIn("pages-audit-report", text)
        self.assertIn("/tmp/current-pages-latest.json", text)
        self.assertIn("scripts/audit_pages_payload.py", text.split("paths:", 1)[1])


if __name__ == "__main__":
    unittest.main()
