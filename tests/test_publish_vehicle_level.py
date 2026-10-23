import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
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
