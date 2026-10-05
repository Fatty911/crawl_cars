"""易车配置表以符号编码，筛选层必须能识别，否则纯易车行永远无法通过配置类条件。"""

from __future__ import annotations

import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _merge_data():
    spec = importlib.util.spec_from_file_location("merge_data", ROOT / "scripts" / "merge_data.py")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit:  # pragma: no cover - module-level CLI guard
        pass
    return module


MD = _merge_data()


def _condition(condition_id: str):
    for condition in MD.FILTER_CONDITIONS:
        if condition.get("id") == condition_id:
            return condition
    raise AssertionError(f"condition {condition_id} is not configured")


def test_bluetooth_key_condition_requires_keyword() -> None:
    # 该前提一旦被改掉，下面的符号用例就失去意义
    assert _condition("bluetooth_key").get("requireKeyword") is True


def test_symbol_marker_satisfies_require_keyword_condition_by_field_name() -> None:
    """易车把「蓝牙/数字钥匙」整项标为 ●，值里没有关键词，但字段名本身就是该配置。"""
    row = {"数据来源": "仅易车", "蓝牙/数字钥匙": "●"}
    assert MD.check_feature(
        row,
        _condition("bluetooth_key")["fields"],
        _condition("bluetooth_key")["keywords"],
        True,
    )


def test_negative_marker_does_not_satisfy_require_keyword_condition() -> None:
    row = {"数据来源": "仅易车", "蓝牙/数字钥匙": "-"}
    assert not MD.check_feature(
        row,
        _condition("bluetooth_key")["fields"],
        _condition("bluetooth_key")["keywords"],
        True,
    )


def test_yiche_comfort_and_wiper_headers_map_to_filter_canonical_names() -> None:
    """易车参配表用自身列名，归一化后必须落到筛选条件认识的列上。"""
    assert MD.norm("感应雨刷功能") == "雨量感应式雨刷"
    assert MD.norm("远程控制功能") == "远程控制"


def test_rain_sensor_wiper_alias_still_requires_a_positive_value() -> None:
    row = {"数据来源": "仅易车", "感应雨刷功能": "-"}
    normalized = {MD.norm(k): v for k, v in row.items()}
    assert not MD.check_feature(
        normalized,
        _condition("rain_sensor_wiper")["fields"],
        _condition("rain_sensor_wiper")["keywords"],
        False,
    )


def test_pure_yiche_row_with_symbol_equipment_passes_full_filter() -> None:
    """真实形状的易车行：数值达标 + 配置用符号标注，应当入选。"""
    row = {
        "数据来源": "仅易车",
        "品牌": "奥迪",
        "车系": "奥迪A7L",
        "车型名称": "24款 45 TFSI S 四驱巅峰特别版",
        "年款": "2024",
        "百公里加速(s)": "6.7",
        "纯电续航(km)": "200",
        "最高车速(km/h)": "250",
        "NOA城市领航": "●",
        "远程启动": "●",
        "远程控制": "●",
        "蓝牙/数字钥匙": "●",
        "座椅记忆": "●",
        "后视镜记忆": "●",
        "手机App远程控制": "●",
        "雨量感应式雨刷": "●",
        "自动大灯": "●",
    }
    assert MD.filter_car(row) is True


def test_filter_config_used_by_pages_is_the_same_file_as_merge() -> None:
    config_path = ROOT / "config" / "filter_conditions.json"
    assert config_path.is_file()
    conditions = json.loads(config_path.read_text(encoding="utf-8")).get("conditions", [])
    assert [c["id"] for c in conditions] == [c["id"] for c in MD.FILTER_CONDITIONS]
