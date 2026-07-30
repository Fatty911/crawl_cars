#!/usr/bin/env python3
"""Build a sparse, recent-model JSON payload for the static Pages UI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from publish_identity import (
        autohome_publish_identity_valid,
        is_autohome_row,
        is_yiche_row,
        has_valid_listing_time,
        normalize_publish_official_price,
        publish_boundary_valid,
        row_car_id,
        yiche_publish_identity_valid,
    )
except ModuleNotFoundError:
    from scripts.publish_identity import (
        autohome_publish_identity_valid,
        is_autohome_row,
        is_yiche_row,
        has_valid_listing_time,
        normalize_publish_official_price,
        publish_boundary_valid,
        row_car_id,
        yiche_publish_identity_valid,
    )

try:
    from merge_data import (
        BRAND_NORMALIZE,
        _base_yiche_match_score,
        _merge_distinct_values,
        atomic_source_names,
        match_score,
        model_variant_conflict_reason,
        model_variant_signature,
        normalize_audited_publish_header,
        normalize_match_text,
        series_year_key,
        yiche_match_score,
    )
except ModuleNotFoundError:
    from scripts.merge_data import (
        BRAND_NORMALIZE,
        _base_yiche_match_score,
        _merge_distinct_values,
        atomic_source_names,
        match_score,
        model_variant_conflict_reason,
        model_variant_signature,
        normalize_audited_publish_header,
        normalize_match_text,
        series_year_key,
        yiche_match_score,
    )

YEAR_RE = re.compile(r"(?:19|20)\d{2}")
VISIBLE_COMPONENT_ID = "跨源归并ID"
VISIBLE_COMPONENT_EVIDENCE = "跨源归并证据"
VISIBLE_COMPONENT_SCHEMA = "visible-f-v1"
VISIBLE_ABSORPTION_SCHEMA = "visible-f-v2"
_MODEL_TEXT_PUNCTUATION = re.compile(r"[·・,，.。/／\\()（）\-_+]")
_EXTRA_TIER_PATTERN = re.compile(
    r"(?<![a-z0-9])(ultra\+|pro\+|max\+|ultra|pro|max|plus|core|air)(?![a-z])",
    re.IGNORECASE,
)
_BODY_FIELDS = ("车体结构", "车身结构", "车身型式", "车身形式")
_NEGATIVE_EQUIPMENT_VALUES = {"", "-", "无", "不支持", "否", "没有", "未配备", "不提供", "0", "0.0"}
_SOURCE_ORDER = {"汽车之家": 0, "懂车帝": 1, "易车": 2}
_NAMED_BATTERY_PATTERN = re.compile(r"(?<!\d)(\d{2,3}(?:\.\d+)?)\s*kwh", re.IGNORECASE)
_NAMED_RANGE_PATTERN = re.compile(r"(?<!\d)(\d{3,4}(?:\.\d+)?)\s*(?:km|公里)", re.IGNORECASE)
_SERIES_POWERTRAIN_SUFFIXES = (
    "插电式混合动力",
    "插电式混动",
    "插电混动",
    "phev",
)
_BATTERY_FIELDS = (
    "电池能量(kWh)",
    "电池能量_kWh_",
    "电池容量(kWh)",
    "电池容量_kWh_",
    "电池能量",
    "电池容量",
    "动力电池容量",
)
_RANGE_FIELDS = (
    "纯电续航(km)",
    "纯电续航_km_",
    "纯电续航里程(km)",
    "纯电续航里程_km_",
    "CLTC纯电续航(km)",
    "CLTC纯电续航_km_",
    "CLTC纯电续航里程(km)",
    "CLTC纯电续航里程_km_",
    "工信部纯电续航里程(km)",
    "工信部纯电续航里程_km_",
)
_SOURCE_MARKER_PATTERN = re.compile(r"(?:^|\|)(汽车之家|懂车帝|易车):")
_ABSORPTION_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "safe_v2_absorption_manifest.json"
)


def model_year(row: dict[str, Any]) -> int | None:
    for value in (row.get("年款"), row.get("车型名称")):
        match = YEAR_RE.search(str(value or ""))
        if match:
            return int(match.group(0))
    return None


def keep_value(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or value.strip() not in {"", "-"})


def positive_value(value: Any) -> bool:
    return str(value if value is not None else "").strip() not in _NEGATIVE_EQUIPMENT_VALUES


def source_allows_missing_year(row: dict[str, Any]) -> bool:
    return False


def has_chinese(value: Any) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(value or "")))


def normalize_publish_row_headers(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {}
    for key, value in row.items():
        canonical = normalize_audited_publish_header(key)
        if canonical in normalized:
            normalized[canonical] = _merge_distinct_values(normalized[canonical], value)
        else:
            normalized[canonical] = value
    return normalized


def _clean_model_text(value: Any) -> str:
    text = re.sub(r"\s+", "", str(value or "")).lower().replace("改款", "")
    return _MODEL_TEXT_PUNCTUATION.sub("", text)


def frontend_visible_key(row: dict[str, Any]) -> str:
    component_id = str(row.get(VISIBLE_COMPONENT_ID, "") or "").strip()
    if component_id:
        return f"audited|{component_id}"
    name = str(row.get("车型名称", "") or "").strip()
    series = str(row.get("车系", "") or "").strip()
    year = model_year(row)
    clean_name = _clean_model_text(name)
    parts = []
    if series and _clean_model_text(series) not in clean_name:
        parts.append(series)
    if year and f"{year}款" not in clean_name and str(year) not in clean_name:
        parts.append(f"{year}款")
    if name:
        parts.append(name)
    model_key = _clean_model_text(" ".join(parts))
    if model_key:
        return f"model|{model_key}"
    fallback = "|".join(
        re.sub(r"\s+", "", str(row.get(field, "") or "")).lower()
        for field in ("品牌", "车系", "车型名称", "年款")
    )
    return f"fallback|{fallback}"


def _frontend_nodes(
    rows: list[dict[str, Any]],
    key_function=frontend_visible_key,
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        key = key_function(row)
        if key not in groups:
            groups[key] = {"row": {}, "sources": set(), "indexes": [], "key": key}
        group = groups[key]
        group["indexes"].append(index)
        group["sources"].update(atomic_source_names(row.get("数据来源")))
        for field, value in row.items():
            if not positive_value(group["row"].get(field)) and positive_value(value):
                group["row"][field] = value
    return list(groups.values())


def _strict_frontend_visible_key(row: dict[str, Any]) -> str:
    component_id = str(row.get(VISIBLE_COMPONENT_ID, "") or "").strip()
    if component_id:
        return f"audited|{component_id}"
    name = str(row.get("车型名称", "") or "").strip()
    series = str(row.get("车系", "") or "").strip()
    year = model_year(row)

    def clean(value: Any) -> str:
        text = re.sub(r"\s+", "", str(value or "")).lower()
        return re.sub(r"[·・,，.。/／\\()（）\-_]", "", text)

    clean_name = clean(name)
    parts = []
    if series and clean(series) not in clean_name:
        parts.append(series)
    if year and f"{year}款" not in clean_name and str(year) not in clean_name:
        parts.append(f"{year}款")
    if name:
        parts.append(name)
    model_key = clean(" ".join(parts))
    return f"strict-model|{model_key}" if model_key else frontend_visible_key(row)


def canonical_series_name(row: dict[str, Any]) -> str:
    series = normalize_match_text(row.get("车系"))
    brand = normalize_match_text(row.get("品牌"))
    brand = BRAND_NORMALIZE.get(brand, brand)
    if brand and series.startswith(brand):
        series = series[len(brand):]
    for suffix in _SERIES_POWERTRAIN_SUFFIXES:
        if series.endswith(suffix) and len(series) > len(suffix):
            series = series[:-len(suffix)]
            break
    return series


def canonical_series_year_key(row: dict[str, Any]) -> str:
    brand = normalize_match_text(row.get("品牌"))
    brand = BRAND_NORMALIZE.get(brand, brand)
    series = canonical_series_name(row)
    year = model_year(row)
    if not brand or not series or year is None:
        return ""
    return f"{brand}|{series}|{year}"


def _energy_signature(row: dict[str, Any]) -> set[str]:
    text = " ".join(str(row.get(field, "") or "") for field in ("能源类型", "车型名称")).lower()
    compact = normalize_match_text(text)
    values = set()
    if "增程" in compact:
        values.add("range_extender")
    if "插电" in compact or "插混" in compact or "phev" in compact or "dmi" in compact or "dmp" in compact:
        values.add("plug_in_hybrid")
    if (
        "range_extender" not in values
        and "plug_in_hybrid" not in values
        and ("纯电" in compact or re.search(r"(?:^|[^a-z])ev(?:$|[^a-z])", text))
    ):
        values.add("battery_electric")
    if "48v轻混" in compact:
        values.add("48v_mild_hybrid")
    elif "油混" in compact or "油电" in compact or "混合动力" in compact or "混动" in compact or "hev" in compact:
        values.add("oil_hybrid")
    if not values and "汽油" in compact:
        values.add("gasoline")
    if not values and "柴油" in compact:
        values.add("diesel")
    return values


def _powertrain_signature(row: dict[str, Any]) -> set[str]:
    text = normalize_match_text(
        " ".join(str(row.get(field, "") or "") for field in ("能源类型", "车型名称"))
    )
    values = set()
    if "dmi" in text:
        values.add("dm_i")
    if "dmp" in text:
        values.add("dm_p")
    return values


def _extra_tier_signature(row: dict[str, Any]) -> set[str]:
    text = str(row.get("车型名称", "") or "").lower().replace("＋", "+")
    return {match.lower() for match in _EXTRA_TIER_PATTERN.findall(text)}


def _generic_drive_signature(row: dict[str, Any]) -> set[str]:
    text = " ".join(
        [str(row.get("车型名称", "") or "")]
        + [
            str(row.get(field, "") or "")
            for field in ("驱动形式", "驱动方式", "驱动形式分组", "电机布局", "四驱形式", "四驱类型")
        ]
    )
    values = set()
    if re.search(r"四驱|4wd|awd", text, re.IGNORECASE):
        values.add("4wd")
    if re.search(r"两驱|2wd", text, re.IGNORECASE):
        values.add("2wd")
    return values


def _lidar_presence(row: dict[str, Any]) -> set[str]:
    values = set()
    name = str(row.get("车型名称", "") or "")
    if "无激光雷达" in name:
        values.add("absent")
    elif "激光雷达" in name:
        values.add("present")
    for field, value in row.items():
        if "激光雷达" not in str(field):
            continue
        if positive_value(value):
            values.add("present")
        elif str(value if value is not None else "").strip() in _NEGATIVE_EQUIPMENT_VALUES:
            values.add("absent")
    return values


def _lidar_line_signature(row: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(value or "")
        for field, value in row.items()
        if field == "车型名称" or "激光雷达" in str(field)
    )
    return set(
        re.findall(
            r"(\d{2,4})\s*线[^|，,；;()（）]{0,20}激光雷达",
            text,
            re.IGNORECASE,
        )
    )


def _motor_count_signature(row: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(value or "")
        for field, value in row.items()
        if field == "车型名称" or "电机" in str(field)
    )
    values = set()
    for token, count in (
        ("单电机", "1"),
        ("双电机", "2"),
        ("两电机", "2"),
        ("三电机", "3"),
        ("四电机", "4"),
    ):
        if token in text:
            values.add(count)
    for match in re.finditer(r"(?:驱动)?电机(?:数量|数|个数)\D{0,3}([1-4])", text):
        values.add(match.group(1))
    return values


def _engine_count_signature(row: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(value or "")
        for field, value in row.items()
        if field == "车型名称" or "发动机" in str(field)
    )
    values = set()
    for token, count in (("单发动机", "1"), ("双发动机", "2"), ("两发动机", "2")):
        if token in text:
            values.add(count)
    for match in re.finditer(r"发动机(?:数量|数|个数)\D{0,3}([1-4])", text):
        values.add(match.group(1))
    return values


def _porsche_drive_badge(row: dict[str, Any]) -> set[str]:
    brand_series = normalize_match_text(
        f"{row.get('品牌', '')} {row.get('车系', '')}"
    )
    name = str(row.get("车型名称", "") or "").lower()
    if "保时捷" not in brand_series or "carrera" not in name:
        return set()
    return {"4"} if re.search(r"\bcarrera\s+4(?:\s|$)", name) else {"base"}


def _named_grade_signature(row: dict[str, Any]) -> set[str]:
    text = normalize_match_text(row.get("车型名称"))
    values = set()
    for token, grade in (
        ("标准版", "standard"),
        ("豪华版", "luxury"),
        ("纵野版", "wilderness"),
        ("享境版", "enjoy"),
        ("智境乾崑版", "smart_qiankun"),
        ("性能版", "performance"),
        ("智选版", "smart_choice"),
    ):
        if token in text:
            values.add(grade)
    return values


def _same_vehicle_name(left: dict[str, Any], right: dict[str, Any]) -> bool:
    def compact(row: dict[str, Any]) -> str:
        text = str(row.get("车型名称", "") or "").lower()
        text = re.sub(r"[（(][^）)]*(?:选装|可选装)[^）)]*[）)]", "", text)
        text = text.replace("改款", "")
        text = re.sub(r"(?:19|20)\d{2}款?", "", text)
        text = re.sub(r"[\s·・,，.。/／\\()（）\-_+]", "", text)
        for field in ("品牌", "车系"):
            prefix = re.sub(
                r"[\s·・,，.。/／\\()（）\-_+]",
                "",
                str(row.get(field, "") or "").lower(),
            )
            if prefix and text.startswith(prefix):
                text = text[len(prefix):]
        return text

    return bool(compact(left) and compact(left) == compact(right))


def _body_signature(row: dict[str, Any]) -> dict[str, set[str]]:
    text = normalize_match_text(
        " ".join(str(row.get(field, "") or "") for field in _BODY_FIELDS)
    )
    structure = set()
    shape = set()
    if "非承载式" in text:
        structure.add("non_load_bearing")
    elif "承载式" in text:
        structure.add("load_bearing")
    for token, canonical in (
        ("敞篷", "convertible"),
        ("旅行车", "wagon"),
        ("两厢", "hatchback"),
        ("三厢", "sedan"),
        ("掀背", "liftback"),
        ("suv", "suv"),
        ("mpv", "mpv"),
        ("皮卡", "pickup"),
        ("跑车", "coupe"),
    ):
        if token in text:
            shape.add(canonical)
    return {"structure": structure, "shape": shape}


def _level_signature(row: dict[str, Any]) -> set[str]:
    text = normalize_match_text(row.get("级别"))
    size = next(
        (
            token
            for token in ("中大型", "紧凑型", "微型", "小型", "中型", "大型")
            if token in text
        ),
        "",
    )
    body = next(
        (
            canonical
            for token, canonical in (
                ("suv", "suv"),
                ("mpv", "mpv"),
                ("轿车", "sedan"),
                ("跑车", "coupe"),
                ("皮卡", "pickup"),
            )
            if token in text
        ),
        "",
    )
    return {f"{size}|{body}"} if size or body else set()


def _named_variant_evidence(row: dict[str, Any]) -> dict[str, set[str]]:
    name = str(row.get("车型名称", "") or "").lower()
    battery = {f"{float(value):g}" for value in _NAMED_BATTERY_PATTERN.findall(name)}
    driving_range = {f"{float(value):g}" for value in _NAMED_RANGE_PATTERN.findall(name)}
    range_class = set()
    if "超长续航" in name:
        range_class.add("extra_long_range")
    elif "长续航" in name:
        range_class.add("long_range")
    if "标准续航" in name or "标准版" in name:
        range_class.add("standard_range")
    return {"battery": battery, "range": driving_range, "range_class": range_class}


def _field_measure_values(row: dict[str, Any], fields: tuple[str, ...]) -> set[str]:
    values = set()
    for field in fields:
        for number in re.findall(r"\d+(?:\.\d+)?", str(row.get(field, "") or "")):
            values.add(f"{float(number):g}")
    return values


def _optional_measure_values(row: dict[str, Any]) -> dict[str, set[str]]:
    battery = set()
    driving_range = set()
    for field, value in row.items():
        text = f"{field} {value}"
        if "选装" not in text and "选配" not in text:
            continue
        battery.update(f"{float(number):g}" for number in _NAMED_BATTERY_PATTERN.findall(text))
        driving_range.update(f"{float(number):g}" for number in _NAMED_RANGE_PATTERN.findall(text))
    return {"battery": battery, "range": driving_range}


def _measure_sets_disjoint(
    left_values: set[str],
    right_values: set[str],
    *,
    tolerance: float,
) -> bool:
    return not any(
        abs(float(left) - float(right))
        <= max(tolerance, 0.01 * max(abs(float(left)), abs(float(right))))
        for left in left_values
        for right in right_values
    )


def visible_component_conflict_reason(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_year = model_year(left)
    right_year = model_year(right)
    if left_year is not None and right_year is not None and left_year != right_year:
        return "year_mismatch"
    reason = model_variant_conflict_reason(left, right)
    if reason:
        return reason
    for label, left_values, right_values in (
        ("tier_mismatch", _extra_tier_signature(left), _extra_tier_signature(right)),
        ("drive_mismatch", _generic_drive_signature(left), _generic_drive_signature(right)),
        ("lidar_mismatch", _lidar_line_signature(left), _lidar_line_signature(right)),
        ("lidar_mismatch", _lidar_presence(left), _lidar_presence(right)),
        ("energy_mismatch", _energy_signature(left), _energy_signature(right)),
        ("powertrain_mismatch", _powertrain_signature(left), _powertrain_signature(right)),
        ("motor_count_mismatch", _motor_count_signature(left), _motor_count_signature(right)),
        ("engine_count_mismatch", _engine_count_signature(left), _engine_count_signature(right)),
        ("porsche_drive_badge_mismatch", _porsche_drive_badge(left), _porsche_drive_badge(right)),
        ("grade_mismatch", _named_grade_signature(left), _named_grade_signature(right)),
    ):
        if left_values and right_values and left_values.isdisjoint(right_values):
            return label
    left_body = _body_signature(left)
    right_body = _body_signature(right)
    for dimension in ("structure", "shape"):
        if (
            left_body[dimension]
            and right_body[dimension]
            and left_body[dimension].isdisjoint(right_body[dimension])
        ):
            return "body_mismatch"
    left_level = _level_signature(left)
    right_level = _level_signature(right)
    if left_level and right_level and left_level.isdisjoint(right_level):
        return "level_mismatch"
    left_evidence = _named_variant_evidence(left)
    right_evidence = _named_variant_evidence(right)
    for field in ("battery", "range", "range_class"):
        if (
            left_evidence[field]
            and right_evidence[field]
            and left_evidence[field].isdisjoint(right_evidence[field])
        ):
            return f"{field}_mismatch"
    left_optional = _optional_measure_values(left)
    right_optional = _optional_measure_values(right)
    for field, fields in (("battery", _BATTERY_FIELDS), ("range", _RANGE_FIELDS)):
        left_values = _field_measure_values(left, fields)
        right_values = _field_measure_values(right, fields)
        tolerance = 0.15 if field == "battery" else 1.0
        if (
            not left_values
            or not right_values
            or not _measure_sets_disjoint(
                left_values,
                right_values,
                tolerance=tolerance,
            )
        ):
            continue
        if (
            left_optional[field]
            and not _measure_sets_disjoint(
                left_optional[field],
                right_values,
                tolerance=tolerance,
            )
            or right_optional[field]
            and not _measure_sets_disjoint(
                right_optional[field],
                left_values,
                tolerance=tolerance,
            )
        ):
            continue
        if (
            field == "battery"
            and _same_vehicle_name(left, right)
            and not _measure_sets_disjoint(
                _field_measure_values(left, _RANGE_FIELDS),
                _field_measure_values(right, _RANGE_FIELDS),
                tolerance=1.0,
            )
        ):
            continue
        return f"{field}_mismatch"
    left_signature = model_variant_signature(left)
    right_signature = model_variant_signature(right)
    for field in ("seat", "lidar", "drive"):
        if (
            left_signature[field]
            and right_signature[field]
            and left_signature[field].isdisjoint(right_signature[field])
        ):
            return f"{field}_mismatch"
    return ""


def _model_id_fields(row: dict[str, Any]) -> dict[str, str]:
    values = {}
    for field, value in row.items():
        compact = re.sub(r"\s+", "", str(field))
        lower = compact.lower()
        if compact == "车系ID":
            continue
        if (
            lower in {"车款id", "车型id", "spec_id", "specid"}
            or (("车款" in compact or "车型" in compact or "关联" in compact or "相关" in compact) and "id" in lower)
        ):
            text = str(value or "").strip()
            if text and text != "-":
                values[str(field)] = text
    return values


def _model_ids(row: dict[str, Any]) -> set[str]:
    values = set()
    for text in _model_id_fields(row).values():
        values.update(re.findall(r"(?<!\d)\d{3,}(?!\d)", text))
    return values


def _component_pair_score(left: dict[str, Any], right: dict[str, Any]) -> tuple[float, list[str]]:
    left_sources = set(left["sources"])
    right_sources = set(right["sources"])
    if left_sources == {"易车"} and right_sources != {"易车"}:
        score, reasons = yiche_match_score(right["row"], left["row"], True)
        if reasons == ["energy_ambiguous"]:
            left_energy = _energy_signature(left["row"])
            right_energy = _energy_signature(right["row"])
            if len(left_energy) == len(right_energy) == 1 and left_energy == right_energy:
                return _base_yiche_match_score(right["row"], left["row"], True)
        return score, reasons
    if right_sources == {"易车"} and left_sources != {"易车"}:
        score, reasons = yiche_match_score(left["row"], right["row"], True)
        if reasons == ["energy_ambiguous"]:
            left_energy = _energy_signature(left["row"])
            right_energy = _energy_signature(right["row"])
            if len(left_energy) == len(right_energy) == 1 and left_energy == right_energy:
                return _base_yiche_match_score(left["row"], right["row"], True)
        return score, reasons
    return match_score(left["row"], right["row"], True)


def _legacy_component_pair_score(
    left: dict[str, Any],
    right: dict[str, Any],
) -> tuple[float, list[str]]:
    left_sources = set(left["sources"])
    right_sources = set(right["sources"])
    if left_sources & right_sources:
        return 0.0, ["source_overlap"]
    if "易车" in left_sources and "易车" not in right_sources:
        return yiche_match_score(right["row"], left["row"], True)
    if "易车" in right_sources and "易车" not in left_sources:
        return yiche_match_score(left["row"], right["row"], True)
    return match_score(left["row"], right["row"], True)


def _candidate_pairs(nodes: list[dict[str, Any]]) -> set[tuple[int, int]]:
    pairs = set()
    buckets: dict[str, list[int]] = {}
    ids: dict[str, list[int]] = {}
    for index, node in enumerate(nodes):
        bucket = canonical_series_year_key(node["row"])
        if bucket:
            buckets.setdefault(bucket, []).append(index)
        series = canonical_series_name(node["row"])
        year = model_year(node["row"])
        if series and year is not None:
            buckets.setdefault(f"series|{series}|{year}", []).append(index)
        series_id = str(node["row"].get("车系ID", "") or "").strip()
        if series_id and series_id != "-" and year is not None:
            buckets.setdefault(f"series-id|{series_id}|{year}", []).append(index)
        for model_id in _model_ids(node["row"]):
            ids.setdefault(model_id, []).append(index)
    for indexes in [*buckets.values(), *ids.values()]:
        for position, left in enumerate(indexes):
            for right in indexes[position + 1:]:
                pairs.add((min(left, right), max(left, right)))
    return pairs


def _component_evidence(
    component_id: str,
    nodes: list[dict[str, Any]],
    edges: list[tuple[int, int, float, list[str]]],
    *,
    schema: str = VISIBLE_COMPONENT_SCHEMA,
) -> str:
    members = []
    ordered_nodes = sorted(
        nodes,
        key=lambda item: (
            tuple(_SOURCE_ORDER.get(source, 99) for source in sorted(item["sources"])),
            str(item["row"].get("车型名称", "") or ""),
        ),
    )
    for node in ordered_nodes:
        row = node["row"]
        member_sources = sorted(
            node["sources"],
            key=lambda source: _SOURCE_ORDER.get(source, 99),
        )
        member = {
            "source": "+".join(member_sources),
            "brand": str(row.get("品牌", "") or ""),
            "series": str(row.get("车系", "") or ""),
            "year": str(row.get("年款", "") or ""),
            "model": str(row.get("车型名称", "") or ""),
            "ids": _model_id_fields(row),
        }
        if schema != VISIBLE_COMPONENT_SCHEMA:
            member["sources"] = member_sources
        members.append(member)
    source_by_node = {
        id(node): "+".join(
            sorted(node["sources"], key=lambda source: _SOURCE_ORDER.get(source, 99))
        )
        for node in nodes
    }
    edge_evidence = [
        {
            "left": source_by_node[id(nodes[left])],
            "right": source_by_node[id(nodes[right])],
            "score": round(score, 4),
            "reasons": reasons,
        }
        for left, right, score, reasons in edges
    ]
    evidence = {
        "schema": schema,
        "component": component_id,
        "sources": sorted(
            {source for node in nodes for source in node["sources"]},
            key=lambda source: _SOURCE_ORDER.get(source, 99),
        ),
        "members": members,
        "edges": sorted(edge_evidence, key=lambda item: (item["left"], item["right"])),
    }
    return json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _annotate_v1_components(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    annotated = []
    for row in rows:
        clean_row = dict(row)
        clean_row.pop(VISIBLE_COMPONENT_ID, None)
        clean_row.pop(VISIBLE_COMPONENT_EVIDENCE, None)
        annotated.append(clean_row)
    nodes = _frontend_nodes(annotated)
    buckets: dict[str, list[int]] = {}
    for index, node in enumerate(nodes):
        bucket = series_year_key(node["row"])
        if bucket:
            buckets.setdefault(bucket, []).append(index)

    adjacency: dict[int, set[int]] = {}
    all_edges: list[tuple[int, int, float, list[str]]] = []
    for indexes in buckets.values():
        for position, left_index in enumerate(indexes):
            for right_index in indexes[position + 1:]:
                left = nodes[left_index]
                right = nodes[right_index]
                if set(left["sources"]) & set(right["sources"]):
                    continue
                score, reasons = _legacy_component_pair_score(left, right)
                if score < 0.58:
                    continue
                adjacency.setdefault(left_index, set()).add(right_index)
                adjacency.setdefault(right_index, set()).add(left_index)
                all_edges.append((left_index, right_index, score, reasons))

    components = []
    visited = set()
    for start in sorted(adjacency):
        if start in visited:
            continue
        pending = [start]
        visited.add(start)
        component = []
        while pending:
            current = pending.pop()
            component.append(current)
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    pending.append(neighbor)
        components.append(sorted(component))

    rejection_counts: Counter[str] = Counter()
    accepted = []
    for component in components:
        component_nodes = [nodes[index] for index in component]
        if not all(len(node["sources"]) == 1 for node in component_nodes):
            rejection_counts["visibleFRejectedExistingMulti"] += 1
            continue
        source_counts = Counter(
            source
            for node in component_nodes
            for source in node["sources"]
        )
        if any(count != 1 for count in source_counts.values()):
            rejection_counts["visibleFRejectedDuplicateSource"] += 1
            continue
        if any(len(node["indexes"]) != 1 for node in component_nodes):
            rejection_counts["visibleFRejectedSameSourceFold"] += 1
            continue
        conflict = ""
        for left in range(len(component_nodes)):
            for right in range(left + 1, len(component_nodes)):
                conflict = _legacy_visible_component_conflict_reason(
                    component_nodes[left]["row"], component_nodes[right]["row"]
                )
                if conflict:
                    break
            if conflict:
                break
        if conflict:
            rejection_counts["visibleFRejectedHardConflict"] += 1
            continue
        bucket = series_year_key(component_nodes[0]["row"])
        multi_nodes = [
            nodes[index]
            for index in buckets.get(bucket, [])
            if len(nodes[index]["sources"]) > 1
        ]
        if any(
            _model_ids(node["row"]) & _model_ids(multi["row"])
            for node in component_nodes
            for multi in multi_nodes
        ):
            rejection_counts["visibleFRejectedExistingMultiId"] += 1
            continue
        accepted.append(component)

    for component in accepted:
        component_nodes = [nodes[index] for index in component]
        component_edges = [
            (component.index(left), component.index(right), score, reasons)
            for left, right, score, reasons in all_edges
            if left in component and right in component
        ]
        fingerprint = [
            {
                "source": next(iter(node["sources"])),
                "key": node["key"],
                "ids": _model_id_fields(node["row"]),
            }
            for node in sorted(
                component_nodes,
                key=lambda item: _SOURCE_ORDER.get(next(iter(item["sources"])), 99),
            )
        ]
        digest = hashlib.sha256(
            json.dumps(fingerprint, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]
        component_id = f"{VISIBLE_COMPONENT_SCHEMA}:{digest}"
        evidence = _component_evidence(component_id, component_nodes, component_edges)
        for node in component_nodes:
            row_index = node["indexes"][0]
            annotated[row_index][VISIBLE_COMPONENT_ID] = component_id
            annotated[row_index][VISIBLE_COMPONENT_EVIDENCE] = evidence

    stats = {
        "visibleFResolvedComponents": len(accepted),
        "visibleFResolvedRows": sum(len(component) for component in accepted),
        "visibleFTwoSourceComponents": sum(len(component) == 2 for component in accepted),
        "visibleFThreeSourceComponents": sum(len(component) == 3 for component in accepted),
        **rejection_counts,
    }
    return annotated, {key: value for key, value in stats.items() if value}


def _raw_node_rows(
    node: dict[str, Any],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [rows[index] for index in node["indexes"]]


def _absorption_scope_identities() -> set[tuple[str, str, str, str]]:
    with _ABSORPTION_MANIFEST_PATH.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    identities = {
        (
            str(item["brand"]),
            str(item["series"]),
            str(item["model"]),
            str(item["year"]),
        )
        for item in manifest.get("allowed_identities", [])
    }
    if manifest.get("schema") != "safe-v2-absorption-policy-v1" or len(identities) != 85:
        raise ValueError("safe-v2 absorption manifest is invalid")
    return identities


def _row_scope_identity(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("品牌", "") or "").strip(),
        str(row.get("车系", "") or "").strip(),
        str(row.get("车型名称", "") or "").strip(),
        str(row.get("年款", "") or "").strip(),
    )


def _raw_component_conflict_reason(
    component: list[int],
    nodes: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> str:
    members = [
        row
        for node_index in component
        for row in _raw_node_rows(nodes[node_index], rows)
    ]
    for left_index, left in enumerate(members):
        for right in members[left_index + 1:]:
            reason = visible_component_conflict_reason(left, right)
            if reason:
                return reason
    return ""


def _absorption_edge(
    left: dict[str, Any],
    right: dict[str, Any],
) -> tuple[float, list[str], bool] | None:
    left_brand = BRAND_NORMALIZE.get(
        normalize_match_text(left["row"].get("品牌")),
        normalize_match_text(left["row"].get("品牌")),
    )
    right_brand = BRAND_NORMALIZE.get(
        normalize_match_text(right["row"].get("品牌")),
        normalize_match_text(right["row"].get("品牌")),
    )
    left_series = canonical_series_name(left["row"])
    right_series = canonical_series_name(right["row"])
    shared_commercial_series = bool(
        left_series
        and left_series == right_series
        and len(left_series) >= 4
        and re.search(r"[\u4e00-\u9fff]", left_series)
    )
    if left_brand != right_brand and not shared_commercial_series:
        return None

    shared_ids = _model_ids(left["row"]) & _model_ids(right["row"])
    stable_id_match = bool(
        shared_ids
        and left_brand
        and left_brand == right_brand
        and model_year(left["row"]) == model_year(right["row"])
    )
    canonical_alias_match = bool(
        canonical_series_year_key(left["row"])
        and canonical_series_year_key(left["row"])
        == canonical_series_year_key(right["row"])
        and series_year_key(left["row"]) != series_year_key(right["row"])
    )
    score, reasons = _component_pair_score(left, right)
    if canonical_alias_match:
        alias_left = dict(left, row=dict(left["row"], 车系=left_series))
        alias_right = dict(right, row=dict(right["row"], 车系=right_series))
        alias_score, alias_reasons = _component_pair_score(alias_left, alias_right)
        if alias_score > score:
            score, reasons = alias_score, alias_reasons
    if score < 0.58 and not stable_id_match:
        return None
    if stable_id_match:
        reasons = [*reasons, "stable_model_id"]
    if canonical_alias_match and "canonical_series_alias" not in reasons:
        reasons = [*reasons, "canonical_series_alias"]
    return score, reasons, stable_id_match


def _annotate_safe_absorptions(
    rows: list[dict[str, Any]],
    absorption_scope: set[tuple[str, str, str, str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    annotated = [dict(row) for row in rows]
    allowed = (
        _absorption_scope_identities()
        if absorption_scope is None
        else absorption_scope
    )
    nodes = _frontend_nodes(annotated, key_function=_strict_frontend_visible_key)
    eligible = {
        index
        for index, node in enumerate(nodes)
        if not str(node["key"]).startswith("audited|")
    }
    multi_indexes = {
        index
        for index in eligible
        if len(nodes[index]["sources"]) > 1
    }
    single_indexes = {
        index
        for index in eligible
        if len(nodes[index]["sources"]) == 1
        and len(nodes[index]["indexes"]) == 1
        and _row_scope_identity(
            annotated[nodes[index]["indexes"][0]]
        ) in allowed
    }
    edge_records: dict[tuple[int, int], tuple[float, list[str], bool]] = {}
    edges_by_node: dict[int, dict[int, tuple[float, list[str], bool]]] = {}
    rejection_counts: Counter[str] = Counter()

    for left_index, right_index in sorted(_candidate_pairs(nodes)):
        if left_index not in eligible or right_index not in eligible:
            continue
        if left_index not in single_indexes and right_index not in single_indexes:
            continue
        if _raw_component_conflict_reason(
            [left_index, right_index],
            nodes,
            annotated,
        ):
            continue
        edge = _absorption_edge(nodes[left_index], nodes[right_index])
        if edge is None:
            continue
        edge_records[(left_index, right_index)] = edge
        edges_by_node.setdefault(left_index, {})[right_index] = edge
        edges_by_node.setdefault(right_index, {})[left_index] = edge

    target_by_single: dict[int, tuple[int, float, list[str], bool]] = {}
    for single_index in sorted(single_indexes):
        candidates = {
            target: edge
            for target, edge in edges_by_node.get(single_index, {}).items()
            if target in multi_indexes
            and set(nodes[single_index]["sources"]).issubset(nodes[target]["sources"])
        }
        if not candidates:
            continue
        stable_targets = [
            target
            for target, (_score, _reasons, stable) in candidates.items()
            if stable
        ]
        if len(stable_targets) == 1:
            target = stable_targets[0]
            score, reasons, stable = candidates[target]
            target_by_single[single_index] = (target, score, reasons, stable)
            continue
        if len(stable_targets) > 1:
            rejection_counts["visibleFRejectedAmbiguousUniverse"] += 1
            continue
        highest = max(score for score, _reasons, _stable in candidates.values())
        winners = [
            target
            for target, (score, _reasons, _stable) in candidates.items()
            if abs(score - highest) <= 1e-12
        ]
        if len(winners) != 1:
            rejection_counts["visibleFRejectedAmbiguousUniverse"] += 1
            continue
        target = winners[0]
        score, reasons, stable = candidates[target]
        target_by_single[single_index] = (target, score, reasons, stable)

    incoming_by_target: dict[int, list[int]] = {}
    for single_index, (target, _score, _reasons, _stable) in target_by_single.items():
        incoming_by_target.setdefault(target, []).append(single_index)

    absorbed_components: list[list[int]] = []
    for target, incoming in sorted(incoming_by_target.items()):
        component = [target, *sorted(incoming)]
        conflict = _raw_component_conflict_reason(component, nodes, annotated)
        if conflict:
            rejection_counts["visibleFRejectedAbsorptionHardConflict"] += len(incoming)
            continue
        target_sources = set(nodes[target]["sources"])
        final_sources = {
            source
            for node_index in component
            for source in nodes[node_index]["sources"]
        }
        if not target_sources.issubset(final_sources):
            rejection_counts["visibleFRejectedSourceRegression"] += len(incoming)
            continue
        absorbed_components.append(component)

    assigned_rows: set[int] = set()
    for component in absorbed_components:
        component_nodes = [nodes[index] for index in component]
        component_edges = []
        target = component[0]
        for single in component[1:]:
            score, reasons, _stable = edge_records[
                (min(single, target), max(single, target))
            ]
            component_edges.append(
                (
                    component.index(single),
                    component.index(target),
                    score,
                    reasons,
                )
            )
        fingerprint = [
            {
                "sources": sorted(
                    node["sources"],
                    key=lambda source: _SOURCE_ORDER.get(source, 99),
                ),
                "key": node["key"],
                "ids": _model_id_fields(node["row"]),
                "payloadIndexes": node["indexes"],
            }
            for node in sorted(
                component_nodes,
                key=lambda item: (
                    tuple(
                        _SOURCE_ORDER.get(source, 99)
                        for source in sorted(item["sources"])
                    ),
                    item["key"],
                ),
            )
        ]
        digest = hashlib.sha256(
            json.dumps(
                fingerprint,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:24]
        component_id = f"{VISIBLE_ABSORPTION_SCHEMA}:{digest}"
        evidence = _component_evidence(
            component_id,
            component_nodes,
            component_edges,
            schema=VISIBLE_ABSORPTION_SCHEMA,
        )
        for node in component_nodes:
            for row_index in node["indexes"]:
                if row_index in assigned_rows:
                    raise ValueError("payload row assigned to multiple visible-f-v2 components")
                assigned_rows.add(row_index)
                annotated[row_index][VISIBLE_COMPONENT_ID] = component_id
                annotated[row_index][VISIBLE_COMPONENT_EVIDENCE] = evidence

    if len(annotated) != len(rows):
        raise ValueError("visible-f-v2 payload row count changed")
    component_source_counts = [
        len(
            {
                source
                for index in component
                for source in nodes[index]["sources"]
            }
        )
        for component in absorbed_components
    ]
    stats = {
        "visibleFAbsorbedComponents": len(absorbed_components),
        "visibleFAbsorbedSingles": sum(
            len(component) - 1 for component in absorbed_components
        ),
        "visibleFAbsorbedPayloadRows": len(assigned_rows),
        "visibleFAbsorbedTwoSourceComponents": sum(
            count == 2 for count in component_source_counts
        ),
        "visibleFAbsorbedThreeSourceComponents": sum(
            count == 3 for count in component_source_counts
        ),
        **rejection_counts,
    }
    return annotated, {key: value for key, value in stats.items() if value}


def annotate_safe_visible_components(
    rows: list[dict[str, Any]],
    absorption_scope: set[tuple[str, str, str, str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    legacy, legacy_stats = _annotate_v1_components(rows)
    annotated, absorption_stats = _annotate_safe_absorptions(
        legacy,
        absorption_scope=absorption_scope,
    )
    stats = dict(legacy_stats)
    stats.update(absorption_stats)
    stats["visibleFResolvedComponents"] = (
        legacy_stats.get("visibleFResolvedComponents", 0)
        + absorption_stats.get("visibleFAbsorbedComponents", 0)
    )
    stats["visibleFResolvedRows"] = (
        legacy_stats.get("visibleFResolvedRows", 0)
        + absorption_stats.get("visibleFAbsorbedPayloadRows", 0)
    )
    stats["visibleFTwoSourceComponents"] = (
        legacy_stats.get("visibleFTwoSourceComponents", 0)
        + absorption_stats.get("visibleFAbsorbedTwoSourceComponents", 0)
    )
    stats["visibleFThreeSourceComponents"] = (
        legacy_stats.get("visibleFThreeSourceComponents", 0)
        + absorption_stats.get("visibleFAbsorbedThreeSourceComponents", 0)
    )
    return annotated, {key: value for key, value in stats.items() if value}


def _effective_sources(rows: list[dict[str, Any]]) -> list[set[str]]:
    component_sources: dict[str, set[str]] = {}
    for row in rows:
        component_id = str(row.get(VISIBLE_COMPONENT_ID, "") or "").strip()
        if component_id:
            component_sources.setdefault(component_id, set()).update(
                atomic_source_names(row.get("数据来源"))
            )
    effective = []
    for row in rows:
        component_id = str(row.get(VISIBLE_COMPONENT_ID, "") or "").strip()
        if component_id:
            effective.append(set(component_sources.get(component_id, set())))
        else:
            effective.append(set(atomic_source_names(row.get("数据来源"))))
    return effective


def _qualified_value_segments(value: Any) -> list[tuple[str, str]] | None:
    text = str(value or "")
    matches = list(_SOURCE_MARKER_PATTERN.finditer(text))
    if not matches:
        return None
    segments = []
    if matches[0].start() > 0:
        prefix = text[:matches[0].start()].rstrip("|")
        if prefix:
            segments.append(("", prefix))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[match.end():end]
        if content.endswith("|"):
            content = content[:-1]
        segments.append((match.group(1), content))
    return segments


def source_provenance_contradictions(
    rows: list[dict[str, Any]],
) -> list[tuple[int, str, str]]:
    contradictions = []
    for index, (row, effective_sources) in enumerate(zip(rows, _effective_sources(rows))):
        for field, value in row.items():
            if field in {"数据来源", VISIBLE_COMPONENT_ID, VISIBLE_COMPONENT_EVIDENCE}:
                continue
            segments = _qualified_value_segments(value)
            if segments is None:
                continue
            for source, _content in segments:
                if source and source not in effective_sources:
                    contradictions.append((index, str(field), source))
    return contradictions


def reconcile_source_provenance(
    rows: list[dict[str, Any]],
    *,
    cleanup_retired: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    reconciled = [dict(row) for row in rows]
    effective_by_row = _effective_sources(reconciled)
    contradiction_fields = set()
    removed_segments = 0
    removed_fields = 0
    for index, (row, effective_sources) in enumerate(zip(reconciled, effective_by_row)):
        for field in list(row):
            if field in {"数据来源", VISIBLE_COMPONENT_ID, VISIBLE_COMPONENT_EVIDENCE}:
                continue
            segments = _qualified_value_segments(row[field])
            if segments is None:
                continue
            retired = [
                (source, content)
                for source, content in segments
                if source and source not in effective_sources
            ]
            if not retired:
                continue
            contradiction_fields.add((index, str(field)))
            if not cleanup_retired:
                continue
            kept = [
                (source, content)
                for source, content in segments
                if not source or source in effective_sources
            ]
            removed_segments += len(retired)
            if not kept:
                row.pop(field, None)
                removed_fields += 1
                continue
            row[field] = "|".join(
                f"{source}:{content}" if source else content
                for source, content in kept
            )
    stats = {
        "fieldSourceContradictions": len(contradiction_fields),
        "retiredFieldSegmentsRemoved": removed_segments,
        "retiredFieldsRemoved": removed_fields,
    }
    return reconciled, stats


def visible_card_stats(rows: list[dict[str, Any]]) -> dict[str, int | float]:
    groups: dict[str, set[str]] = {}
    for row in rows:
        groups.setdefault(frontend_visible_key(row), set()).update(
            atomic_source_names(row.get("数据来源"))
        )
    visible_single = sum(len(sources) == 1 for sources in groups.values())
    visible_multi = sum(len(sources) >= 2 for sources in groups.values())
    visible_rows = visible_single + visible_multi
    return {
        "payload_rows": len(rows),
        "visible_rows": visible_rows,
        "visible_single": visible_single,
        "visible_multi": visible_multi,
        "visible_rate": round((visible_multi / visible_rows * 100) if visible_rows else 0.0, 12),
    }


def prepare_rows_with_stats(
    rows: Any,
    min_year: int,
    *,
    absorption_scope: set[tuple[str, str, str, str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if not isinstance(rows, list):
        raise ValueError("Pages payload input must be a JSON array")
    prepared = []
    stats = {
        "droppedMissingOfficialPrice": 0,
        "droppedMissingListingTime": 0,
        "droppedFutureListingTime": 0,
    }
    for row in rows:
        if not isinstance(row, dict):
            continue
        row = normalize_publish_row_headers(row)
        brand = str(row.get("品牌") or "").strip()
        model = str(row.get("车型名称") or "").strip()
        if brand in {"", "-"} or model in {"", "-"} or not yiche_publish_identity_valid(row):
            continue
        if is_autohome_row(row) and not autohome_publish_identity_valid(row):
            continue
        if not normalize_publish_official_price(row):
            stats["droppedMissingOfficialPrice"] += 1
            continue
        listing_time = str(row.get("上市时间") or "").strip()
        if not listing_time or listing_time in {"-", "--", "None", "null"}:
            stats["droppedMissingListingTime"] += 1
            continue
        if not has_valid_listing_time(row):
            stats["droppedFutureListingTime"] += 1
            continue
        if not publish_boundary_valid(row):
            continue
        year = model_year(row)
        if year is None or year < min_year:
            continue
        if "易车" in str(row.get("数据来源", "") or ""):
            series = str(row.get("车系") or "").strip()
            status = str(row.get("易车上市状态") or "").strip()
            if not series or series == "-" or not re.search(r"[\u4e00-\u9fff]", series):
                continue
            if status != "approved":
                continue
        prepared_row = {key: value for key, value in row.items() if keep_value(value)}
        normalize_publish_official_price(prepared_row)
        prepared_row["品牌"] = brand
        prepared_row["车型名称"] = model
        prepared.append(prepared_row)
    prepared, component_stats = annotate_safe_visible_components(
        prepared,
        absorption_scope=absorption_scope,
    )
    stats.update(component_stats)
    prepared, provenance_stats = reconcile_source_provenance(
        prepared,
        cleanup_retired=True,
    )
    stats.update({key: value for key, value in provenance_stats.items() if value})
    return prepared, stats


def prepare_rows(
    rows: Any,
    min_year: int,
    *,
    absorption_scope: set[tuple[str, str, str, str]] | None = None,
) -> list[dict[str, Any]]:
    prepared, _stats = prepare_rows_with_stats(
        rows,
        min_year,
        absorption_scope=absorption_scope,
    )
    return prepared


def write_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, ensure_ascii=False, separators=(",", ":"))
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-year", type=int, default=2022)
    args = parser.parse_args()

    before_bytes = args.input.stat().st_size
    with args.input.open(encoding="utf-8") as handle:
        rows = json.load(handle)
    prepared, stats = prepare_rows_with_stats(rows, args.min_year)
    write_atomic(args.output, prepared)
    print(
        json.dumps(
            {
                "inputRows": len(rows),
                "outputRows": len(prepared),
                "inputBytes": before_bytes,
                "outputBytes": args.output.stat().st_size,
                "minYear": args.min_year,
                "droppedMissingOfficialPrice": stats["droppedMissingOfficialPrice"],
                "droppedMissingListingTime": stats["droppedMissingListingTime"],
                "droppedFutureListingTime": stats["droppedFutureListingTime"],
                **{
                    key: value
                    for key, value in stats.items()
                    if key.startswith("visibleF")
                    or key.startswith("fieldSource")
                    or key.startswith("retiredField")
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _legacy_visible_component_conflict_reason(left: dict[str, Any], right: dict[str, Any]) -> str:
    reason = model_variant_conflict_reason(left, right)
    if reason:
        return reason
    for label, left_values, right_values in (
        ("tier_mismatch", _extra_tier_signature(left), _extra_tier_signature(right)),
        ("drive_mismatch", _generic_drive_signature(left), _generic_drive_signature(right)),
        ("lidar_mismatch", _lidar_presence(left), _lidar_presence(right)),
        ("energy_mismatch", _energy_signature(left), _energy_signature(right)),
        ("powertrain_mismatch", _powertrain_signature(left), _powertrain_signature(right)),
    ):
        if left_values and right_values and left_values.isdisjoint(right_values):
            return label
    left_body = _body_signature(left)
    right_body = _body_signature(right)
    for dimension in ("structure", "shape"):
        if (
            left_body[dimension]
            and right_body[dimension]
            and left_body[dimension].isdisjoint(right_body[dimension])
        ):
            return "body_mismatch"
    left_level = normalize_match_text(left.get("级别"))
    right_level = normalize_match_text(right.get("级别"))
    if left_level and right_level and left_level != right_level:
        return "level_mismatch"
    left_evidence = _named_variant_evidence(left)
    right_evidence = _named_variant_evidence(right)
    for field in ("battery", "range", "range_class"):
        if (
            left_evidence[field]
            and right_evidence[field]
            and left_evidence[field].isdisjoint(right_evidence[field])
        ):
            return f"{field}_mismatch"
    left_signature = model_variant_signature(left)
    right_signature = model_variant_signature(right)
    for field in ("seat", "lidar", "drive"):
        if (
            left_signature[field]
            and right_signature[field]
            and left_signature[field].isdisjoint(right_signature[field])
        ):
            return f"{field}_mismatch"
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
