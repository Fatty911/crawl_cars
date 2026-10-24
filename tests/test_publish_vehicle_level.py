import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_pages_payload import audit_payload
from prepare_pages_payload import prepare_rows_with_stats
from publish_value_domains import clean_vehicle_level


@pytest.mark.parametrize(("value", "expected"), [
    ("汽车之家:中大型SUV|懂车帝:中大型SUV|L2级", "汽车之家:中大型SUV|懂车帝:中大型SUV"),
    ("紧凑型SUV|●|○ 暂无价格", "紧凑型SUV"),
    ("L2级", ""),
    ("中大型车|紧凑型车", "中大型车|紧凑型车"),
    ("未知分类", "未知分类"),
])
def test_level_cleanup_is_field_specific_and_idempotent(value, expected):
    result, _ = clean_vehicle_level(value)
    assert result == expected
    assert clean_vehicle_level(result) == (result, [])


def row():
    return {"品牌": "比亚迪", "车系": "汉", "车系ID": "100", "车款ID": "123",
            "车型名称": "汉 2026款 EV 506KM 尊贵型", "年款": "2026", "数据来源": "汽车之家",
            "官方指导价": "12.34万", "上市时间": "2026.01", "级别": "中大型车|L2级",
            "辅助驾驶级别": "L2级"}


def test_prepare_preserves_rows_identity_other_facts_and_input():
    original = row()
    prepared, stats = prepare_rows_with_stats([original], 2022)
    assert len(prepared) == 1
    assert prepared[0]["级别"] == "中大型车"
    assert prepared[0]["辅助驾驶级别"] == "L2级"
    assert prepared[0]["车款ID"] == original["车款ID"]
    assert original["级别"] == "中大型车|L2级"
    assert stats["vehicleLevelRemovedSegments"] == 1
    repeated, _ = prepare_rows_with_stats(prepared, 2022)
    assert repeated == prepared


def test_full_audit_rejects_shared_dirty_baseline_instead_of_only_regression():
    dirty = row()
    report = audit_payload([dirty], [dict(dirty)], head_sha="test", full_validation=True)
    assert report["status"] == "blocked"
    assert any(v["code"] == "vehicle_level_foreign_value" for v in report["violations"])


def test_full_audit_allows_corrected_value_without_losing_identity():
    dirty = row()
    clean = dict(dirty, 级别="中大型车")
    report = audit_payload([dirty], [clean], head_sha="test", full_validation=True)
    assert report["status"] == "pass"
    assert report["stats"]["candidate_identities"] == 1


def test_full_audit_reports_residuals_on_rows_excluded_from_comparison():
    clean = dict(row(), 级别="中大型车")
    historical = dict(clean, 车款ID="past123", 年款="2021", 上市时间="2021.01",
                      车型名称="汉 2021款 EV 506KM 尊贵型", 远程启动="3.0T 354马力 V6")
    candidate = [clean, historical]
    before = [dict(value) for value in candidate]
    full = audit_payload([clean], candidate, head_sha="test", full_validation=True)
    assert full["stats"]["candidate_rows"] == 1
    assert full["status"] == "blocked"
    violation = next(value for value in full["violations"] if value["code"] == "capability_value_residual")
    assert violation["count"] == 1
    assert full["stats"]["capabilityValueResidual"] == {"远程启动": 1}
    legacy = audit_payload([clean], candidate, head_sha="test")
    assert legacy["status"] == "pass"
    assert legacy["stats"]["capabilityValueResidual"] == {}
    assert candidate == before
