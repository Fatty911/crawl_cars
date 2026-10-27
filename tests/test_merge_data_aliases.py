from __future__ import annotations

from unittest import mock

from scripts.merge_data import (
    _load_header_aliases,
    header_alias_lookup,
    normalize_audited_publish_header,
)


def test_alias_lookup_returns_none_when_config_is_empty() -> None:
    # The committed config ships an empty aliases list.
    aliases = _load_header_aliases()
    assert isinstance(aliases, dict)
    assert header_alias_lookup("NOMI Mate 3.0") is None


def test_alias_lookup_degrades_on_corrupt_config() -> None:
    with mock.patch("scripts.merge_data.open", mock.mock_open(read_data="{not json")):
        with mock.patch("scripts.merge_data._HEADER_ALIASES", None):
            assert _load_header_aliases() == {}


def test_normalize_returns_stripped_original_without_alias_or_v4_suffix() -> None:
    # 未配置别名且无 v4 后缀、不在 HEADER_MAP 的列名原样返回（去掉首尾空白）
    assert normalize_audited_publish_header(" 未知属性X ") == "未知属性X"


def test_normalize_applies_configured_alias_canonical() -> None:
    with mock.patch(
        "scripts.merge_data.header_alias_lookup",
        return_value={"canonical": "车载智能系统", "value": "NOMI Mate 3.0"},
    ):
        assert normalize_audited_publish_header("NOMI Mate 3.0") == "车载智能系统"


def test_normalize_folds_v4_value_suffix_back_to_canonical_attribute() -> None:
    assert (
        normalize_audited_publish_header("driving_assist_chip_v4_NVIDIA DRIVE Orin X")
        == "辅助驾驶芯片"
    )


import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.merge_data import _merge_existing_with_source
from scripts.prepare_pages_payload import normalize_publish_row_headers

REPO_ROOT = Path(__file__).resolve().parent.parent

# 子进程内固定调用链：真实 _merge_existing_with_source + normalize_publish_row_headers。
_SUBPROCESS_PROBE = """
import json, sys
sys.path.insert(0, sys.argv[1])
from scripts.merge_data import _merge_existing_with_source
from scripts.prepare_pages_payload import normalize_publish_row_headers

current = json.loads(sys.argv[2])
incoming = json.loads(sys.argv[3])
merged = _merge_existing_with_source(current, "懂车帝", "易车", incoming)
normalized = normalize_publish_row_headers(merged)
print(json.dumps({
    "merged_keys": list(merged),
    "merged_screen": {k: v for k, v in merged.items() if "屏" in k},
    "merged_types": {k: type(v).__name__ for k, v in merged.items()},
    "normalized_screen": {k: v for k, v in normalized.items() if "屏" in k},
}, ensure_ascii=False))
"""

_SCREEN_CURRENT = {
    "品牌": "奔驰",
    "车系": "奔驰C级",
    "车型名称": "26款 C 260 L 运动轿车",
    "车款ID": "181360",
    "年款": "2026",
    "价格": "35.28",
    "数据来源": "懂车帝",
}
_SCREEN_INCOMING = {
    "数据来源": "易车",
    "中控屏幕尺寸": "●",
    "中控屏幕尺寸(英寸)": "11.9",
}


def _run_probe(seed: str, current: dict, incoming: dict) -> dict:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            _SUBPROCESS_PROBE,
            str(REPO_ROOT),
            json.dumps(current, ensure_ascii=False),
            json.dumps(incoming, ensure_ascii=False),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _seed_results(seeds, current=_SCREEN_CURRENT, incoming=_SCREEN_INCOMING):
    return {seed: _run_probe(seed, current, incoming) for seed in seeds}


def test_merge_plus_normalize_screen_value_is_identical_across_hash_seeds() -> None:
    # 真实子进程：同输入不同 PYTHONHASHSEED 必须给出同一字面值。
    results = _seed_results(("1", "2", "3", "5", "7", "11", "19", "31"))
    rendered = {seed: r["normalized_screen"]["中控屏幕尺寸"] for seed, r in results.items()}
    assert len(set(rendered.values())) == 1, rendered
    value = rendered["1"]
    assert "11.9" in value and "●" in value, value


def test_merge_key_order_is_identical_across_hash_seeds() -> None:
    results = _seed_results(("1", "5", "31"))
    orders = {seed: tuple(r["merged_keys"]) for seed, r in results.items()}
    assert len(set(orders.values())) == 1, orders
    # 既有字段前缀仍按 current 原次序在前。
    order = list(orders["1"])
    assert order[: len(_SCREEN_CURRENT)] == list(_SCREEN_CURRENT), order


def test_screen_atoms_kept_textual_and_never_coerced_to_measurement() -> None:
    results = _seed_results(("1", "5", "31"))
    for seed, r in results.items():
        # 原始 incoming 单元格保持原字面值：● 不变成数值，11.9 不被吞。
        assert r["merged_screen"]["中控屏幕尺寸"] == "●", seed
        assert r["merged_screen"]["中控屏幕尺寸(英寸)"] == "11.9", seed
        assert r["merged_types"]["中控屏幕尺寸"] == "str", seed
        segments = r["normalized_screen"]["中控屏幕尺寸"].split("|")
        assert sorted(segments) == ["11.9", "●"], (seed, segments)


def test_merge_is_insensitive_to_incoming_key_insertion_order() -> None:
    ordered = {"数据来源": "易车", "中控屏幕尺寸": "●", "中控屏幕尺寸(英寸)": "11.9"}
    reversed_order = {"中控屏幕尺寸(英寸)": "11.9", "数据来源": "易车", "中控屏幕尺寸": "●"}
    first = _run_probe("1", _SCREEN_CURRENT, ordered)
    second = _run_probe("1", _SCREEN_CURRENT, reversed_order)
    assert first["merged_keys"] == second["merged_keys"]
    assert first["merged_screen"] == second["merged_screen"]
    assert first["normalized_screen"] == second["normalized_screen"]


def test_merge_keeps_current_prefix_values_types_and_leaves_inputs_untouched() -> None:
    current = dict(_SCREEN_CURRENT)
    incoming = dict(_SCREEN_INCOMING)
    current_snapshot = dict(current)
    incoming_snapshot = dict(incoming)
    merged = _merge_existing_with_source(current, "懂车帝", "易车", incoming)
    assert current == current_snapshot
    assert incoming == incoming_snapshot
    assert list(merged)[: len(current_snapshot)] == list(current_snapshot)
    for key, value in current_snapshot.items():
        assert merged[key] == value
        assert type(merged[key]) is type(value)
    # 新增字段追加在既有前缀之后，原样保留 incoming 文本。
    assert merged["中控屏幕尺寸"] == "●"
    assert merged["中控屏幕尺寸(英寸)"] == "11.9"


def test_merge_keeps_source_priority_segmentation_negation_and_zero() -> None:
    segmented = _merge_existing_with_source(
        {"品牌": "奔驰", "数据来源": "懂车帝", "中控屏幕尺寸": "懂车帝:11.9"},
        "懂车帝",
        "易车",
        {"数据来源": "易车", "中控屏幕尺寸": "●"},
    )
    assert segmented["中控屏幕尺寸"] == "懂车帝:11.9|易车:●"

    zero = _merge_existing_with_source(
        {"纯电续航(km)": "605", "数据来源": "懂车帝"},
        "懂车帝",
        "易车",
        {"纯电续航(km)": "0", "数据来源": "易车"},
    )
    assert zero["纯电续航(km)"] == "懂车帝:605|易车:0"

    kept_when_incoming_blank = _merge_existing_with_source(
        {"中控屏幕尺寸": "11.9", "数据来源": "懂车帝"},
        "懂车帝",
        "易车",
        {"中控屏幕尺寸": "-", "数据来源": "易车"},
    )
    assert kept_when_incoming_blank["中控屏幕尺寸"] == "11.9"

    filled_when_current_blank = _merge_existing_with_source(
        {"中控屏幕尺寸": "-", "数据来源": "懂车帝"},
        "懂车帝",
        "易车",
        {"中控屏幕尺寸": "11.9", "数据来源": "易车"},
    )
    assert filled_when_current_blank["中控屏幕尺寸"] == "11.9"


def test_single_screen_field_without_collision_stays_verbatim() -> None:
    # 单字段无别名碰撞时不得改写或拼接任何字面值。
    for column, value in (("中控屏幕尺寸", "●"), ("中控屏幕尺寸(英寸)", "11.9")):
        current = {"品牌": "奔驰", "数据来源": "懂车帝"}
        incoming = {"数据来源": "易车", column: value}
        merged = _merge_existing_with_source(current, "懂车帝", "易车", incoming)
        assert merged[column] == value
        assert merged["品牌"] == "奔驰"
        normalized = normalize_publish_row_headers({column: value})
        assert normalized == {normalize_audited_publish_header(column): value}
