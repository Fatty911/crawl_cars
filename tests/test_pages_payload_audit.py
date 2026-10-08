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

import yaml

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
        cls.prepare = load("prepare_pages_payload_for_audit", SCRIPTS / "prepare_pages_payload.py")

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
            "官方指导价": "12.34万",
            "上市时间": "2026.01",
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
        candidate, _ = self.prepare.annotate_safe_visible_components(
            [self.row("1", "汽车之家"), self.row("2", "懂车帝")]
        )
        report = self.audit.audit_payload(
            [self.row("1", "汽车之家+懂车帝")],
            candidate,
            head_sha="abc",
        )
        self.assertEqual("pass", report["status"])
        self.assertEqual([], report["violations"])
        self.assertEqual(1, report["stats"]["intentional_source_retirements"])

    def test_missing_identity_is_blocked(self) -> None:
        # 60 missing out of 200 unique identities = 30%, well above 2% threshold and 50-row floor
        def row_with_brand(i: int, source: str) -> dict:
            r = self.row(str(i), source)
            r["品牌"] = f"品牌{i}"
            r["车系"] = f"车系{i}"
            return r
        baseline = [row_with_brand(i, "汽车之家") for i in range(200)]
        candidate = [row_with_brand(i, "汽车之家") for i in range(140)]
        report = self.audit.audit_payload(baseline, candidate, head_sha="abc")
        self.assertEqual("blocked", report["status"])
        missing_v = [v for v in report["violations"] if v["code"] == "missing_identity"]
        self.assertEqual(1, len(missing_v))
        self.assertEqual(60, missing_v[0]["count"])

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

    def test_safe_visible_component_annotation_is_recomputed_and_counted(self) -> None:
        autohome = self.row("101", "仅汽车之家") | {
            "车型名称": "汉 2026款 EV 506KM 尊贵型",
            "能源类型": "纯电",
            "级别": "中大型车",
        }
        dongchedi = self.row("202", "仅懂车帝") | {
            "车型名称": "汉 26款 EV 506KM 尊贵型",
            "能源类型": "纯电",
            "级别": "中大型车",
        }
        baseline = [autohome, dongchedi]
        candidate, component_stats = self.prepare.annotate_safe_visible_components(baseline)

        report = self.audit.audit_payload(baseline, candidate, head_sha="abc")

        self.assertEqual("pass", report["status"])
        self.assertEqual(1, component_stats["visibleFResolvedComponents"])
        self.assertEqual(1, report["stats"]["candidate_visible_multi"])
        self.assertEqual(0, report["stats"]["candidate_visible_single"])

    def test_missing_or_tampered_visible_component_annotation_is_blocked(self) -> None:
        # Build many pairs to exceed the unsafe_visible_component_annotation threshold (50)
        base_rows = []
        for i in range(60):
            base_rows.append(self.row(str(100 + i), "仅汽车之家") | {
                "车型名称": f"车型{i} 2026款 EV",
                "能源类型": "纯电",
                "级别": "中大型车",
            })
            base_rows.append(self.row(str(200 + i), "仅懂车帝") | {
                "车型名称": f"车型{i} 26款 EV",
                "能源类型": "纯电",
                "级别": "中大型车",
            })
        annotated, _ = self.prepare.annotate_safe_visible_components(base_rows)
        # Small number of missing annotations (within 5 tolerance) should pass
        missing = [dict(row) for row in annotated]
        for i in range(3):
            missing[i].pop(self.prepare.VISIBLE_COMPONENT_ID, None)
            missing[i].pop(self.prepare.VISIBLE_COMPONENT_EVIDENCE, None)
        missing_report = self.audit.audit_payload(annotated, missing, head_sha="abc")
        self.assertEqual("pass", missing_report["status"])

        # Unsafe annotations exceeding 50-count tolerance should be blocked
        unsafe = [dict(row) for row in annotated]
        for i in range(55):
            unsafe[i][self.prepare.VISIBLE_COMPONENT_ID] = "visible-f-v1:forged" + str(i)
        unsafe_report = self.audit.audit_payload(annotated, unsafe, head_sha="abc")
        self.assertEqual("blocked", unsafe_report["status"])
        self.assertIn(
            "unsafe_visible_component_annotation",
            {violation["code"] for violation in unsafe_report["violations"]},
        )

    def test_existing_visible_component_annotation_violation_is_not_a_regression(self) -> None:
        autohome = self.row("101", "仅汽车之家") | {
            "车型名称": "汉 2026款 EV 506KM 尊贵型",
            "能源类型": "纯电",
            "级别": "中大型车",
        }
        dongchedi = self.row("202", "仅懂车帝") | {
            "车型名称": "汉 26款 EV 506KM 尊贵型",
            "能源类型": "纯电",
            "级别": "中大型车",
        }
        annotated, _ = self.prepare.annotate_safe_visible_components([autohome, dongchedi])
        old_payload = [dict(row, **{self.prepare.VISIBLE_COMPONENT_ID: "visible-f-v1:forged"}) for row in annotated]

        report = self.audit.audit_payload(old_payload, old_payload, head_sha="abc")

        self.assertEqual("pass", report["status"])
        self.assertEqual([], report["violations"])

    def test_field_source_marker_must_belong_to_effective_component_sources(self) -> None:
        autohome = self.row("101", "仅汽车之家") | {
            "驾驶辅助影像": "汽车之家:360度全景影像|懂车帝:倒车影像|透明影像",
        }

        report = self.audit.audit_payload([autohome], [autohome], head_sha="abc")

        self.assertEqual("blocked", report["status"])
        self.assertIn(
            "field_source_contradiction",
            {violation["code"] for violation in report["violations"]},
        )
        self.assertEqual(1, report["stats"]["field_source_contradictions"])

    def test_retirement_cleanup_preserves_current_source_and_passes_strict_audit(self) -> None:
        autohome = self.row("101", "仅汽车之家") | {
            "驾驶辅助影像": "汽车之家:360度全景影像|懂车帝:倒车影像|透明影像",
            "当前字段": "汽车之家:保留",
        }
        cleaned, cleanup_stats = self.prepare.reconcile_source_provenance(
            [autohome],
            cleanup_retired=True,
        )

        report = self.audit.audit_payload([cleaned[0]], cleaned, head_sha="abc")

        self.assertEqual("pass", report["status"])
        self.assertEqual("汽车之家:360度全景影像", cleaned[0]["驾驶辅助影像"])
        self.assertEqual("汽车之家:保留", cleaned[0]["当前字段"])
        self.assertEqual(1, cleanup_stats["retiredFieldSegmentsRemoved"])

    def test_component_evidence_sources_are_derived_from_actual_members(self) -> None:
        autohome = self.row("101", "仅汽车之家") | {
            "车型名称": "汉 2026款 EV 506KM 尊贵型",
            "能源类型": "纯电",
            "级别": "中大型车",
        }
        dongchedi = self.row("202", "仅懂车帝") | {
            "车型名称": "汉 26款 EV 506KM 尊贵型",
            "能源类型": "纯电",
            "级别": "中大型车",
        }
        annotated, _ = self.prepare.annotate_safe_visible_components(
            [autohome, dongchedi]
        )
        tampered = [dict(row) for row in annotated]
        evidence = json.loads(tampered[0][self.prepare.VISIBLE_COMPONENT_EVIDENCE])
        evidence["sources"] = ["汽车之家", "懂车帝", "易车"]
        forged = json.dumps(
            evidence,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for row in tampered:
            row[self.prepare.VISIBLE_COMPONENT_EVIDENCE] = forged

        report = self.audit.audit_payload(annotated, tampered, head_sha="abc")

        self.assertEqual("blocked", report["status"])
        self.assertIn(
            "visible_component_evidence_mismatch",
            {violation["code"] for violation in report["violations"]},
        )


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
            subprocess.run(["git", "-c", "core.hooksPath=", "commit", "-m", "base"], cwd=root, check=True, capture_output=True)
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
        # 断言对象是 **CNB 工作流**（.cnb.yml），不是 .github/workflows/merge-and-filter.yml。
        # 原因：GitHub Actions 已停用（2026-10-05 用户裁定，带 if:false），
        # 且 merge-and-filter.yml 里**根本没有执行 prepare_pages_payload.py**
        # ——那两处只是 `paths:` 触发列表里的文件名，不是执行行。
        # 原断言因此在 rindex() 上抛 ValueError，测的也是一个不执行的平台。
        #
        # 顺序必须在**同一段 script 内部**用字符位置比较：
        # prepare / audit / manifest 三步都写在「组装发布站点」这一个 stage 里，
        # 按 stage 索引比毫无意义（同一个 stage 三个索引相同）。
        #
        # 也因此不能用全文 rindex()：.cnb.yml 现在有两个独立发布 job
        # （基础属性链与经销商报价链），全文搜索会命中另一个 job 的调用。
        main = (yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8")) or {})["main"]
        checked = 0
        for key, job in main.items():
            if not isinstance(job, list) or not job or not isinstance(job[0], dict):
                continue
            for stage in job[0].get("stages") or []:
                script = stage.get("script") or ""
                if "audit_pages_payload" not in script:
                    continue
                with self.subTest(job=key):
                    audit_at = script.index("audit_pages_payload")
                    prepare_at = script.rindex("prepare_pages_payload", 0, audit_at)
                    manifest_at = script.index("manifest.json", audit_at)
                    self.assertLess(
                        prepare_at, audit_at,
                        f"{key}: prepare_pages_payload 必须先于 audit",
                    )
                    self.assertLess(
                        audit_at, manifest_at,
                        f"{key}: audit 必须先于写 manifest（否则审的是上一版数据）",
                    )
                    self.assertIn("pages-audit-report", script)
                checked += 1
        self.assertGreater(checked, 0, "没有任何 job 执行 audit_pages_payload —— 审计闸丢失了")

    def test_audit_uses_online_baseline(self) -> None:
        # 审计必须拿线上已发布数据做基线（对比发布前后差异），
        # 不能拿仓库里的自产数据自审。
        main = (yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8")) or {})["main"]
        checked = 0
        for key, job in main.items():
            if not isinstance(job, list) or not job or not isinstance(job[0], dict):
                continue
            for stage in job[0].get("stages") or []:
                script = stage.get("script") or ""
                if "audit_pages_payload" not in script:
                    continue
                with self.subTest(job=key):
                    block = script.split("audit_pages_payload", 1)[1][:800]
                    self.assertIn("--baseline", block)
                    self.assertNotIn(
                        "--baseline docs/data",
                        block,
                        "审计基线不能是仓库内自产数据，必须是线上已发布数据",
                    )
                checked += 1
        self.assertGreater(checked, 0, "找不到任何 audit_pages_payload 执行点")


if __name__ == "__main__":
    unittest.main()
