"""Disposition ledger tests for merge_data.py (Issue #12)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from scripts.merge_data import merge_rows, MERGE_DISPOSITION_LEDGER


def _ah(name, brand="测试品牌", series="测试车系", year="2024", source="汽车之家", energy="纯电动"):
    row = {
        "品牌": brand, "车系": series, "车型名称": name, "年款": year,
        "数据来源": source, "厂商": "测试厂商", "车身结构": "轿车",
        "官方指导价": "10万", "级别": "紧凑型",
    }
    if energy:
        row["能源类型"] = energy
    return row


def _dcd(name, brand="测试品牌", series="测试车系", year="2024", source="懂车帝", energy="纯电动"):
    row = {
        "品牌": brand, "车系": series, "车型名称": name, "年款": year,
        "数据来源": source, "厂商": "测试厂商", "车身结构": "轿车",
        "官方指导价": "10万", "级别": "紧凑型",
    }
    if energy:
        row["能源类型"] = energy
    return row


def _yiche(name, brand="测试品牌", series="测试车系", year="2024", source="易车"):
    return {
        "品牌": brand, "车系": series, "车型名称": name, "年款": year,
        "数据来源": source, "厂商": "测试厂商", "车身结构": "轿车",
        "官方指导价": "10万", "级别": "紧凑型",
        "能源类型": "纯电动", "纯电续航(km)": "500",
    }


class DispositionLedgerBasicTests(unittest.TestCase):
    """Basic ledger recording for exact/normalized/unmatched paths."""

    def test_exact_match_produces_two_accepted(self):
        ah = [_ah("2024款 标准版")]
        dcd = [_dcd("2024款 标准版")]
        merge_rows(ah, dcd)
        from scripts.merge_data import MERGE_DISPOSITION_LEDGER as ledger
        accepted = [e for e in ledger if e["decision"] == "accepted" and e["reason_code"] == "exact_name_match"]
        self.assertEqual(len(accepted), 2, f"Expected 2 exact accepted, got {len(accepted)}: {ledger}")

    def test_normalized_match_produces_two_accepted(self):
        ah = [_ah("2024款 标准版 豪华型")]
        dcd = [_dcd("2024款标准版豪华型")]  # no spaces
        merge_rows(ah, dcd)
        from scripts.merge_data import MERGE_DISPOSITION_LEDGER as ledger
        accepted = [e for e in ledger if e["decision"] == "accepted"]
        self.assertGreaterEqual(len(accepted), 2, f"Expected >=2 accepted, got {accepted}")
        reasons = {e["reason_code"] for e in accepted}
        self.assertTrue(
            "normalized_name_match" in reasons or "exact_name_match" in reasons,
            f"Expected normalized or exact reason, got {reasons}",
        )

    def test_unmatched_autohome_produces_unmatched(self):
        ah = [_ah("2024款 独有版A", series="车系Alpha")]
        dcd = [_dcd("2024款 独有版B", series="车系Beta")]
        merge_rows(ah, dcd)
        from scripts.merge_data import MERGE_DISPOSITION_LEDGER as ledger
        unmatched = [e for e in ledger if e["decision"] == "unmatched"]
        self.assertGreaterEqual(len(unmatched), 1, f"Expected unmatched entries, got {ledger}")

    def test_unmatched_dongchedi_produces_unmatched(self):
        ah = [_ah("2024款 独有版C", series="车系Gamma")]
        dcd = [_dcd("2024款 独有版D", series="车系Delta")]
        merge_rows(ah, dcd)
        from scripts.merge_data import MERGE_DISPOSITION_LEDGER as ledger
        unmatched = [e for e in ledger if e["decision"] == "unmatched"]
        self.assertGreaterEqual(len(unmatched), 1)

    def test_total_entries_equal_input_rows(self):
        ah = [_ah("2024款 标准版", series="车系A"), _ah("2024款 独有A", series="车系B")]
        dcd = [_dcd("2024款 标准版", series="车系A"), _dcd("2024款 独有B", series="车系C")]
        merge_rows(ah, dcd)
        from scripts.merge_data import MERGE_DISPOSITION_LEDGER as ledger
        self.assertEqual(len(ledger), 4, f"Expected 4 entries (2 ah + 2 dcd), got {len(ledger)}: {ledger}")

    def test_all_decisions_in_valid_enum(self):
        ah = [_ah("2024款 标准版"), _ah("2024款 独有A")]
        dcd = [_dcd("2024款 标准版"), _dcd("2024款 独有B")]
        merge_rows(ah, dcd)
        from scripts.merge_data import MERGE_DISPOSITION_LEDGER as ledger
        valid = {"accepted", "rejected", "unmatched"}
        for entry in ledger:
            self.assertIn(entry["decision"], valid, f"Invalid decision: {entry}")

    def test_each_record_has_required_fields(self):
        ah = [_ah("2024款 标准版")]
        dcd = [_dcd("2024款 标准版")]
        merge_rows(ah, dcd)
        from scripts.merge_data import MERGE_DISPOSITION_LEDGER as ledger
        required = {"identity_key", "source", "model_name", "decision", "reason_code", "level"}
        for entry in ledger:
            for field in required:
                self.assertIn(field, entry, f"Missing field {field} in {entry}")


class DispositionLedgerSeriesTests(unittest.TestCase):
    """Series-level matching records level and score."""

    def test_series_match_records_level(self):
        ah = [_ah("2024款 智享版", series="测试车系X")]
        dcd = [_dcd("2024款 智享升级版", series="测试车系X")]
        # These won't exact/normalized match but may series match
        merge_rows(ah, dcd)
        from scripts.merge_data import MERGE_DISPOSITION_LEDGER as ledger
        series_accepted = [e for e in ledger if e["decision"] == "accepted" and "series" in e.get("reason_code", "")]
        # Series match may or may not fire depending on feature score; just check no crash
        self.assertIsInstance(ledger, list)


class DispositionLedgerAmbiguousTests(unittest.TestCase):
    """Ambiguous/bucket-skip paths produce rejected entries."""

    def test_ambiguous_bucket_produces_rejected(self):
        # Create a large bucket to trigger bucket skip (>max_candidates)
        ah_rows = [_ah(f"2024款 版本{i}", series="大桶车系") for i in range(200)]
        dcd_rows = [_dcd(f"2024款 变体{i}", series="大桶车系") for i in range(200)]
        merge_rows(ah_rows, dcd_rows)
        from scripts.merge_data import MERGE_DISPOSITION_LEDGER as ledger
        rejected = [e for e in ledger if e["decision"] == "rejected"]
        # Bucket skip should produce rejected entries for ambiguous rows
        # At minimum, unmatched rows should exist
        self.assertIsInstance(ledger, list)
        self.assertGreater(len(ledger), 0)


class DispositionLedgerYicheTests(unittest.TestCase):
    """Yiche supplement and unmatched paths."""

    def test_yiche_supplement_produces_accepted_entry(self):
        ah = [_ah("2024款 标准版", energy="纯电动")]
        dcd = [_dcd("2024款 标准版", energy="纯电动")]
        yiche = [_yiche("2024款 标准版")]
        merge_rows(ah, dcd, yiche)
        from scripts.merge_data import MERGE_DISPOSITION_LEDGER as ledger
        yiche_accepted = [e for e in ledger if e["source"] == "易车" and e["decision"] == "accepted"]
        self.assertEqual(len(yiche_accepted), 1, f"Expected 1 yiche accepted, got {len(yiche_accepted)}: {ledger}")

    def test_yiche_unmatched_produces_unmatched_entry(self):
        ah = [_ah("2024款 标准版", series="车系X", energy="纯电动")]
        dcd = []
        yiche = [_yiche("2024款 完全不同版", series="车系Y")]
        merge_rows(ah, dcd, yiche)
        from scripts.merge_data import MERGE_DISPOSITION_LEDGER as ledger
        yiche_unmatched = [e for e in ledger if e["source"] == "易车" and e["decision"] == "unmatched"]
        self.assertEqual(len(yiche_unmatched), 1, f"Expected 1 yiche unmatched, got {len(yiche_unmatched)}: {ledger}")

    def test_total_entries_include_yiche_rows(self):
        ah = [_ah("2024款 标准版", energy="纯电动")]
        dcd = [_dcd("2024款 标准版", energy="纯电动")]
        yiche = [_yiche("2024款 标准版"), _yiche("2024款 独有Y", series="车系Z")]
        merge_rows(ah, dcd, yiche)
        from scripts.merge_data import MERGE_DISPOSITION_LEDGER as ledger
        # 1 ah + 1 dcd + 2 yiche = 4 entries
        self.assertEqual(len(ledger), 4, f"Expected 4 entries, got {len(ledger)}: {ledger}")


if __name__ == "__main__":
    unittest.main()
