"""`contains_chinese(车系)` 曾把车系名为拉丁字母的品牌整族删掉。

实测 serialId=6224（特斯拉 Model Y）：配置 API 正常返回 6 个车款、其中 4 个
易车上市状态=approved，却全部因车系名 "Model Y" 无汉字而被 is_real_config_row 否决，
merged 里特斯拉的易车数据因此为 0 行。垃圾车系本已由 is_slug_series 拦截。
"""

from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _crawler():
    spec = importlib.util.spec_from_file_location("crawl_yiche", ROOT / "scripts" / "crawl_yiche.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CRAWLER = _crawler()


def _model_y_row(**overrides) -> dict:
    row = {
        "品牌": "特斯拉",
        "车系": "Model Y",
        "车型名称": "26款 593km 后轮驱动版",
        "年款": "2026",
        "车款ID": "186270",
        "易车上市状态": "approved",
        "厂商指导价": "26.35万",
    }
    row.update(overrides)
    return row


def test_latin_series_name_is_accepted() -> None:
    assert CRAWLER.is_real_config_row(_model_y_row())


def test_camel_case_and_numeric_series_are_accepted() -> None:
    for series in ("Model 3", "Cayenne", "ID.4 X", "T5"):
        assert CRAWLER.is_real_config_row(_model_y_row(车系=series)), series


def test_slug_like_series_is_still_rejected() -> None:
    """放宽拉丁名不能把 URL 片段当成合法车系放进来。"""
    for series in ("modely-6224", "a6-etron-peizhi", "hafu-196"):
        assert not CRAWLER.is_real_config_row(_model_y_row(车系=series)), series


def test_unapproved_row_is_still_rejected() -> None:
    assert not CRAWLER.is_real_config_row(_model_y_row(易车上市状态="unapproved"))


def test_row_without_any_config_field_is_still_rejected() -> None:
    """身份齐全但没有任何配置字段，仍是降级身份，不能进榜。"""
    identity_only = {k: v for k, v in _model_y_row().items() if k in CRAWLER.IDENTITY_FIELDS or k in {"车款ID", "易车上市状态"}}
    assert not CRAWLER.is_real_config_row(identity_only)


def test_live_model_y_row_shape_is_publishable() -> None:
    """serialId=6224 实测返回的行形状：approved 的 Model Y 必须能进榜。"""
    live_row = {
        "品牌": "特斯拉",
        "车系": "Model Y",
        "车型名称": "26款 593km 后轮驱动版",
        "年款": "2026",
        "车款ID": "186270",
        "易车上市状态": "approved",
        "厂商指导价": "26.35万",
        "CLTC纯电续航(km)": "593",
    }
    assert CRAWLER.is_real_config_row(live_row)
