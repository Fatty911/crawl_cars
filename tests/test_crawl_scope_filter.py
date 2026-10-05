"""发布基线必须执行 config/CRAWL_SCOPE.md 的车型范围：只留轿车/跑车/SUV。

该文件明确排除 MPV、房车、货车、皮卡等，但原实现的关键词表里没有 MPV 与房车，
且级别判断只对易车行生效，导致 merged/latest.json 里留有 1119 行 MPV/房车。
"""

from __future__ import annotations

import importlib.util
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


def _row(level: str, source: str = "仅懂车帝", **extra) -> dict:
    row = {
        "数据来源": source,
        "品牌": "测试品牌",
        "车系": "测试车系",
        "车型名称": "2026款 测试",
        "年款": "2026",
        "级别": level,
    }
    row.update(extra)
    return row


def test_crawl_scope_keywords_cover_the_documented_exclusions() -> None:
    """CRAWL_SCOPE.md 列出的排除项必须都在关键词表里。"""
    documented = ("MPV", "房车", "货车", "卡车", "微卡", "轻卡", "皮卡", "轻客", "客车", "微面", "面包车", "厢式", "载货", "牵引", "自卸")
    joined = "".join(MD.CRAWL_SCOPE_EXCLUDED_LEVEL_KEYWORDS)
    missing = [word for word in documented if word not in joined]
    assert not missing, f"CRAWL_SCOPE.md 要求排除但关键词缺失: {missing}"


def test_mpv_and_rv_are_excluded_regardless_of_source() -> None:
    """MPV 曾被既有测试当作乘用车保留，与 CRAWL_SCOPE.md 相反；已按文档裁决排除。"""
    for source in ("仅懂车帝", "仅汽车之家", "仅易车", "懂车帝+汽车之家"):
        assert MD.excluded_by_crawl_scope(_row("中大型MPV", source)), source
        assert MD.excluded_by_crawl_scope(_row("房车", source)), source


def test_commercial_levels_are_excluded_regardless_of_source() -> None:
    for source in ("仅懂车帝", "仅汽车之家", "仅易车", "懂车帝+汽车之家"):
        assert MD.excluded_by_crawl_scope(_row("轻型卡车", source)), source
        assert MD.excluded_by_crawl_scope(_row("皮卡", source)), source
        assert MD.excluded_by_crawl_scope(_row("微型面包车", source)), source


def test_documented_included_levels_are_kept() -> None:
    for level in ("微型车", "小型车", "紧凑型车", "中型车", "中大型车", "大型车", "跑车", "中型SUV", "紧凑型SUV", "大型SUV", "MPV级"):
        if level == "MPV级":
            continue
        assert not MD.excluded_by_crawl_scope(_row(level)), level


def test_empty_level_is_not_invented_as_excluded() -> None:
    """级别缺失不能当作排除依据，否则会把没写级别的车一起删掉。"""
    assert not MD.excluded_by_crawl_scope(_row(""))
    assert not MD.excluded_by_crawl_scope(_row("-"))


def test_offroad_body_structure_is_not_collaterally_excluded() -> None:
    """越野车/硬派方盒属于 SUV 范围，不能因车身结构字段被连带删掉。"""
    row = _row("中型SUV", 车身结构="硬派越野")
    assert not MD.excluded_by_crawl_scope(row)


def test_legacy_commercial_keyword_name_still_resolves() -> None:
    assert MD.YICHE_COMMERCIAL_LEVEL_KEYWORDS
