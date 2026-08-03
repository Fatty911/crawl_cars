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
