"""懂车帝来源主键（car_id）与车型级别字段的来源真实性测试。

真实证据：小鹏 G9 series 5461 现用 entity API 返回 20 行，顶层 car_id 依次
255230 / 255231 / 255229，car_name 为 680 四驱 Max / 725 Max / 625 Max，
car_year 2026；info["jb"]["value"]="中大型SUV"，同时 info 含辅助驾驶级别 L2。
"""

import copy
import json
import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "crawl_dongchedi.py"
SERIES = [{"id": "5461", "name": "小鹏G9", "brand": "小鹏"}]
PROPERTIES = [
    {"key": "jb", "text": "级别"},
    {"key": "automatic_drive_level_v2_3", "text": "辅助驾驶级别"},
    {"key": "official_price", "text": "官方指导价"},
]


def load_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    helper = runpy.run_path(str(ROOT / "tests" / "test_dongchedi_api_payload.py"))
    return helper["load_module"]().__dict__


@pytest.fixture()
def dcd(tmp_path):
    module = load_module()
    module["dcd_dir"] = str(tmp_path / "dongchedi")
    module["dcd_json_dir"] = str(tmp_path / "dongchedi" / "json")
    module["dcd_exception_dir"] = str(tmp_path / "dongchedi" / "exception")
    Path(module["dcd_json_dir"]).mkdir(parents=True)
    Path(module["dcd_exception_dir"]).mkdir(parents=True)
    module["progress_file"] = str(tmp_path / "dongchedi" / "progress.json")
    module["progress"] = {}
    module["MIN_YEAR"] = 2022
    return module


def car_entry(car_id, name, level="中大型SUV", assist="L2", year="2026"):
    info = {"official_price": {"value": "30.99万"}}
    if level is not None:
        info["jb"] = {"value": level}
    if assist is not None:
        info["automatic_drive_level_v2_3"] = {"value": assist}
    return {
        "car_id": car_id,
        "car_name": name,
        "car_year": year,
        "official_price": "30.99万",
        "brand_name": "小鹏",
        "info": info,
    }


def write_series(dcd, car_info, payload_car_ids=None, props=None, series_id="5461"):
    payload = {
        "source": "dongchedi_entity_api",
        "series_info": {"id": series_id, "name": "小鹏G9", "brand": "小鹏"},
        "car_ids": list(payload_car_ids or []),
        "data": {
            "car_info": car_info,
            "properties": PROPERTIES if props is None else props,
        },
    }
    path = Path(dcd["dcd_json_dir"]) / f"{series_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def test_assist_level_header_order_never_becomes_vehicle_level(dcd):
    write_series(dcd, [car_entry(255230, "680 四驱 Max"), car_entry(255231, "725 Max")])
    rows, headers = dcd["parse_config_pages"](SERIES)
    # 辅助驾驶级别列在真正级别列之前出现，仍不得被当作车型级别
    assert dcd["get_vehicle_level"](rows[0], ["辅助驾驶级别", "级别"]) == "中大型SUV"
    assert dcd["get_vehicle_level"](rows[0], ["级别", "辅助驾驶级别"]) == "中大型SUV"
    assert dcd["get_vehicle_level"](rows[0], headers) == "中大型SUV"
    assert [row["级别"] for row in rows] == ["中大型SUV", "中大型SUV"]
    assert [row["辅助驾驶级别"] for row in rows] == ["L2", "L2"]
    assert len(rows) == 2


def test_vehicle_level_matches_normalized_exact_field_name_only(dcd):
    row = {"级别": "中大型SUV", "辅助驾驶级别": "L2"}
    assert dcd["get_vehicle_level"](row, ["辅助驾驶级别", "级别"]) == "中大型SUV"
    spaced_row = {" 辅 助 驾 驶 级 别 ": "L2", " 级别 ": "中大型SUV"}
    assert dcd["get_vehicle_level"](spaced_row, list(spaced_row)) == "中大型SUV"
    assert dcd["get_vehicle_level"]({"辅助驾驶级别": "L2"}, ["辅助驾驶级别"]) == ""
    assert (
        dcd["get_vehicle_level"]({"级别": "-", "车身结构": "5门5座SUV"}, ["级别", "车身结构"])
        == "5门5座SUV"
    )


def test_real_pickup_level_still_excluded(dcd):
    pickup_row = {"级别": "皮卡", "辅助驾驶级别": "L2"}
    assert dcd["get_vehicle_level"](pickup_row, ["辅助驾驶级别", "级别"]) == "皮卡"
    assert dcd["is_supported_vehicle_level"]("皮卡") is False
    write_series(dcd, [car_entry(1, "商用炮 两驱", level="皮卡")])
    rows, _ = dcd["parse_config_pages"](SERIES)
    assert rows == []


def test_missing_vehicle_level_with_only_assist_level_stays_unclassified(dcd):
    only_assist = {"辅助驾驶级别": "L2"}
    assert dcd["get_vehicle_level"](only_assist, ["辅助驾驶级别"]) == ""
    assert dcd["is_excluded_vehicle_level"]("") is False
    assert dcd["is_supported_vehicle_row"](only_assist, ["辅助驾驶级别"]) is True
    write_series(dcd, [car_entry(7, "G9 增程", level=None)])
    rows, _ = dcd["parse_config_pages"](SERIES)
    assert [row["车型名称"] for row in rows] == ["G9 增程"]
    assert rows[0].get("级别", "-") == "-"


def test_car_ids_follow_car_info_order_even_when_request_list_is_reversed(dcd):
    info = [car_entry(255230, "680 四驱 Max"), car_entry(255229, "625 Max")]
    payload = write_series(dcd, info, payload_car_ids=["255229", "255230"])
    before = copy.deepcopy(payload["data"]["car_info"])
    rows, headers = dcd["parse_config_pages"](SERIES)
    assert dcd["DCD_CAR_ID_FIELD"] == "懂车帝车型ID"
    assert "懂车帝车型ID" in headers
    assert [row["车型名称"] for row in rows] == ["680 四驱 Max", "625 Max"]
    assert [row["懂车帝车型ID"] for row in rows] == ["255230", "255229"]
    assert payload["car_ids"] == ["255229", "255230"]
    assert payload["data"]["car_info"] == before


def test_missing_car_id_is_not_backfilled_from_request_list(dcd):
    info = [car_entry(None, "680 四驱 Max"), car_entry(255231, "725 Max")]
    write_series(dcd, info, payload_car_ids=["111111", "222222"])
    rows, _ = dcd["parse_config_pages"](SERIES)
    assert [row["车型名称"] for row in rows] == ["680 四驱 Max", "725 Max"]
    assert rows[0].get("懂车帝车型ID", "-") == "-"
    assert rows[1]["懂车帝车型ID"] == "255231"
    assert {row.get("懂车帝车型ID") for row in rows}.isdisjoint({"111111", "222222"})


def test_invalid_car_id_values_never_become_identity(dcd):
    assert dcd["_extract_dcd_car_id"](255230) == "255230"
    assert dcd["_extract_dcd_car_id"]("255230") == "255230"
    for bad in [
        0, "0", "", "-", " ", "100,200", "abc", "23 45", "2.5",
        ["255230"], {"id": 255230}, None, True,
    ]:
        assert dcd["_extract_dcd_car_id"](bad) == "", bad
    info = [car_entry(0, "680 四驱 Max"), car_entry("100,200", "725 Max")]
    write_series(dcd, info, payload_car_ids=["333333"])
    rows, headers = dcd["parse_config_pages"](SERIES)
    assert [row["车型名称"] for row in rows] == ["680 四驱 Max", "725 Max"]
    assert "懂车帝车型ID" not in headers
    assert rows[0].get("懂车帝车型ID", "-") == "-"
    assert rows[1].get("懂车帝车型ID", "-") == "-"


def test_existing_fields_and_headers_stay_unchanged(dcd):
    write_series(dcd, [car_entry(255230, "680 四驱 Max")])
    rows, headers = dcd["parse_config_pages"](SERIES)
    row = rows[0]
    assert row["品牌"] == "小鹏"
    assert row["车系"] == "小鹏G9"
    assert row["车系ID"] == "5461"
    assert row["车型名称"] == "680 四驱 Max"
    assert row["年款"] == "2026"
    assert row["官方指导价"] == "30.99万"
    assert row["级别"] == "中大型SUV"
    assert row["辅助驾驶级别"] == "L2"
    assert row["懂车帝车型ID"] == "255230"
    assert "车型ID" not in row
    assert set(row) == {"品牌", "车系", "车系ID", "车型名称", "年款"} | set(headers)
