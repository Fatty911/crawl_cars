#!/usr/bin/env python3
"""Deterministically diagnose Pages columns that encode values as headers.

The crawler payload is intentionally treated as evidence only.  This module
does not rename fields or infer new data; it reports high-signal header
patterns for the read-only audit Agent and the bounded repair workflow.

Diagnosis kinds (confidence):

* ``attribute_value_header`` (0.99): explicit ``属性 - 值`` or documented v4
  one-hot headers; the parent attribute is known.
* ``v2v3_value_header`` (0.80): ``X_v2_<V>`` / ``X_v3_<V>`` one-hot where the
  ``X_v2`` / ``X_v3`` base column exists in the same payload.
* ``package_value_header`` (0.90): a proven non-empty ``<value>_1`` /
  ``<value>_2`` pair whose base itself looks like a value (contains spaces or
  mixed-case words), e.g. ``NOMI Mate 3.0_1``.
* ``package_pair_header`` (0.96): a proven non-empty, different ``_1``/``_2``
  pair matching the existing package normalizer's evidence rule.
* ``numeric_suffix_header`` (0.72): an unclassified numeric suffix that may be
  a one-hot value or a package field and needs model/source-code review.
* ``bare_value_header`` (0.45): a standalone value-looking English column
  (spaces / mixed case, no unit parentheses) with no known attribute mapping;
  only the model can decide.
* ``noncanonical_attribute_header`` (0.90): a documented v4 base used directly
  as a header without the ``_v4`` suffix convention.
* ``unmapped_v4_header`` (0.55): ``X_v4_<V>`` whose base is not in the
  documented v4 map.

The report also exposes ``candidate_attributes`` (columns that are *not*
suspicious and therefore safe mapping targets) so the repair Agent cannot
invent new attribute names.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from typing import Any

# These are the documented DCD v4 attribute bases.  A header such as
# ``driving_assist_op_system_v4_DiPilot`` therefore encodes the value
# ``DiPilot`` in the header instead of keeping the attribute as a column.
V4_ATTRIBUTE_MAP = {
    "laser_radar_v4": "激光雷达",
    "driving_assist_chip_computing_v4": "辅助驾驶芯片算力",
    "car_intelligent_system_v4": "车载智能系统",
    "driving_assist_chip_v4": "辅助驾驶芯片",
    "car_intelligent_chip_v4": "车载智能芯片",
    "driving_assist_op_system_v4": "辅助驾驶操作系统",
    "ultrasonic_radar_v4": "超声波雷达",
    "battery_brand_v4": "电池品牌",
    "millimeter_wave_radar_v4": "毫米波雷达",
    "camera_count_v4": "摄像头数量",
    "v2x_communication_v4": "V2X通信",
    "heat_pump_management_system_v4": "热泵管理系统",
    "mobile_remote_control_v4": "手机远程控制",
    "high_precision_map_v4": "高精度地图",
}

# English snake_case headers that are legitimate attribute fields on the
# live Pages payload (front-end filter groups, metric fields, crawler IDs).
# They must never be flagged as value headers.
KNOWN_ENGLISH_ATTRIBUTES = {
    "filter_group_car_year",
    "filter_group_capacity_l",
    "filter_group_driver_form",
    "departure_angle",
    "approach_angle",
    "engine_max_torque",
    "engine_max_power",
    "engine_description",
    "electric_max_torque",
    "electric_max_power",
    "total_electric_power",
    "total_electric_torque",
    "front_electric_max_horsepower",
    "fuel_consumption",
    "max_grade",
    "traction_weight",
    "cylinder_material",
    "inductive_back_door",
    "electric_back_door",
    "electric_back_door_memory_v2",
    "engine_anti_theft",
    "electric_layout",
    "ota_version",
    "low_speed_driving_warning_v3",
}

# Core identity columns that must never be renamed by the repair workflow.
PROTECTED_ATTRIBUTES = {
    "数据来源",
    "品牌",
    "车系",
    "车型名称",
    "年款",
    "厂商",
    "官方指导价",
    "经销商参考价",
    "级别",
    "上市时间",
    "车系ID",
    "车款ID",
    "跨源归并ID",
    "跨源归并证据",
    "易车匹配方式",
}

_HYPHEN_VALUE = re.compile(r"^(.+?)\s+-\s+(\S.*)$")
_V4_VALUE = re.compile(r"^(.+_v4)_(.+)$")
_V2V3_VALUE = re.compile(r"^(.+_(?:v[123]))_(.+)$")
_VN_BASE = re.compile(r"^(.+)_(v[0-9]+)$")
_NUMERIC_SUFFIX = re.compile(r"^(.+)_(\d+)$")
_UNKNOWN_V4 = re.compile(r"^(.+_v4)(?:_|$)")
_BARE_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._\-+/]*$")
_IDENTIFIER_LIKE = re.compile(r"^[a-z0-9_]+$")
_PAREN_VALUE = re.compile(r"^(.+?)[(（]([^()（）]+)[)）]$")
_PAREN_UNIT_OR_ABBR = re.compile(r"^[A-Za-z0-9/·.°℃%\s-]+等?$")
_UNDERSCORE_TOKEN = re.compile(r"_[^_]{1,6}_")
_VALUE_WORD = re.compile(
    r"(套装|套件|轮毂|轮圈|轮辋|轮胎|车漆|拉花|限定|订阅|选装包|升级包|装备包|礼包|"
    r"改装|特别版|专属|豪华包|舒适包|科技包|安全包|娱乐包|音响包|性能包|卡钳|刹车盘|"
    r"饰板|饰条|徽标|迎宾|贴膜|改色|装饰膜|遮阳帘|桌板|香氛|吧台|投影|行李架|踏板|车衣|"
    r"脚垫|冰箱|权益|车轮包|外饰|套餐|配色|专属设计)"
)
_INTERNAL_COLUMN = re.compile(r"^(易车|跨源归并|核验来源|匹配方式|上市状态|分组)")
_ATTRIBUTE_SUFFIX = re.compile(r"(类型|材质|工艺|数量|规格|形式|方式|功能|系统|结构|布局|尺寸|颜色|材料|品牌|型号|版本|级别|样式|类型)$")
_ENGLISH_COLUMN = re.compile(r"^[a-z_][a-z0-9_]*$")
_MIXED_ENGLISH_VALUE = re.compile(r"^[a-z_]+[a-z0-9_]*\d[a-z0-9_一-鿿]*$")
_SCHEMA_UNIT_TOKENS = {
    "s", "km", "km/h", "mm", "kg", "kW", "kWh", "N·m", "L", "mL", "°", "°C",
    "rpm", "Ps", "TOPS", "Wh/kg", "L/100km", "个", "万元", "元", "min", "h",
    "万色", "nit", "Hz", "PPI", "px", "线", "m", "cm", "V", "W", "A", "%", "K",
    "英寸", "吋", "寸", "GB", "万/秒", "ms", "kPa",
}
_NEGATIVE_VALUES = {"", "-", "--", "none", "null", "未知", "无"}


def _positive(value: Any) -> bool:
    return str(value if value is not None else "").strip().casefold() not in _NEGATIVE_VALUES


def _column_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(key) for row in rows for key in row)


def _record(
    *,
    kind: str,
    column: str,
    occurrences: int,
    confidence: float,
    suggested_attribute: str = "",
    value_suffix: str = "",
    columns: list[str] | None = None,
    sample_values: list[str] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "kind": kind,
        "column": column,
        "occurrences": occurrences,
        "confidence": confidence,
    }
    if suggested_attribute:
        item["suggested_attribute"] = suggested_attribute
    if value_suffix:
        item["value_suffix"] = value_suffix
    if columns:
        item["columns"] = columns
    if sample_values:
        item["sample_values"] = sample_values
    return item


def _sample_value_counts(rows: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    """Single pass over all rows collecting non-empty value counts per column.

    The diagnosis loop then looks samples up from this map instead of
    rescanning every row per column (O(rows*columns) -> O(rows*fields))."""
    samples: dict[str, Counter[str]] = {}
    for row in rows:
        for key, value in row.items():
            text = str(value if value is not None else "").strip()
            if not text:
                continue
            samples.setdefault(str(key), Counter())[text] += 1
    return samples


def _sample_values(
    value_counts: dict[str, Counter[str]],
    column: str,
    limit: int = 5,
) -> list[str]:
    return [text for text, _count in value_counts.get(column, Counter()).most_common(limit)]


def _collect_vn_bases(counts: Counter[str]) -> dict[str, str]:
    """Map ``X_v2`` -> ``v2`` for every base column actually present in the payload.

    Only v1..v3 bases feed the ``v2v3_value_header`` branch; v4 has its own
    documented map (_V4_VALUE / V4_ATTRIBUTE_MAP), and v5+ bases are rare and
    left for the lower-confidence numeric-suffix bucket."""
    bases: dict[str, str] = {}
    for column in counts:
        match = _VN_BASE.match(column)
        if match and match.group(2) in {"v1", "v2", "v3"}:
            bases[match.group(1) + "_" + match.group(2)] = match.group(2)
    return bases


def scan_data_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Scan for render-breaking data shapes so the repair chain can fix them.

    - pipe_multi_value_fields: columns whose values contain ``|`` separators
      (e.g. 纯电续航(km) = "220|185|185" — the pages numeric-range renderer
      would treat the tail as a unit suffix).
    - year_duplicate_models: model names that already embed the model year
      (e.g. "领克900 2026款 1.5T Halo 5座") while the 年款 field is set —
      the pages model-title suffix would repeat it.
    """
    import re
    pipe_counts: dict[str, int] = {}
    year_dup: list[str] = []
    for row in rows:
        for key, value in row.items():
            if isinstance(value, str) and "|" in value:
                pipe_counts[key] = pipe_counts.get(key, 0) + 1
        name = str(row.get("车型名称") or "")
        year = str(row.get("年款") or "")
        if year and re.search(r"\d{4}款", name) and year in name:
            year_dup.append(name)
    return {
        "pipe_multi_value_fields": sorted(
            pipe_counts.items(), key=lambda item: (-item[1], item[0])
        )[:20],
        "pipe_multi_value_rows": sum(pipe_counts.values()),
        "year_duplicate_models_count": len(year_dup),
        "year_duplicate_models_sample": year_dup[:5],
    }


def diagnose_columns(rows: list[dict[str, Any]], *, limit: int = 120) -> dict[str, Any]:
    """Return bounded, deterministic evidence about suspicious column names.

    ``candidate_attributes`` contains every non-suspicious column name and may
    be used as the allowlist of mapping targets for the repair Agent.
    """
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise TypeError("rows must be a list of objects")

    counts = _column_counts(rows)
    value_counts = _sample_value_counts(rows)
    vn_bases = _collect_vn_bases(counts)
    suspects: list[dict[str, Any]] = []
    suspect_columns: set[str] = set()

    for column, occurrences in counts.items():
        samples = _sample_values(value_counts, column)
        match = _HYPHEN_VALUE.match(column)
        if match:
            parent, suffix = (part.strip() for part in match.groups())
            suspects.append(
                _record(
                    kind="attribute_value_header",
                    column=column,
                    occurrences=occurrences,
                    confidence=0.99,
                    suggested_attribute=parent,
                    value_suffix=suffix,
                    sample_values=samples,
                )
            )
            suspect_columns.add(column)
            continue

        match = _V4_VALUE.match(column)
        if match and match.group(1) in V4_ATTRIBUTE_MAP:
            suspects.append(
                _record(
                    kind="attribute_value_header",
                    column=column,
                    occurrences=occurrences,
                    confidence=0.99,
                    suggested_attribute=V4_ATTRIBUTE_MAP[match.group(1)],
                    value_suffix=match.group(2).strip(),
                    sample_values=samples,
                )
            )
            suspect_columns.add(column)
            continue

        if column in V4_ATTRIBUTE_MAP:
            suspects.append(
                _record(
                    kind="noncanonical_attribute_header",
                    column=column,
                    occurrences=occurrences,
                    confidence=0.9,
                    suggested_attribute=V4_ATTRIBUTE_MAP[column],
                    sample_values=samples,
                )
            )
            suspect_columns.add(column)
            continue

        match = _V2V3_VALUE.match(column)
        if match and not _IDENTIFIER_LIKE.match(column):
            value_part = match.group(2).strip()
            if value_part and not _NEGATIVE_VALUES.intersection({value_part.casefold()}):
                suspects.append(
                    _record(
                        kind="v2v3_value_header",
                        column=column,
                        occurrences=occurrences,
                        confidence=0.8 if match.group(1) in vn_bases else 0.72,
                        suggested_attribute=match.group(1),
                        value_suffix=value_part,
                        sample_values=samples,
                    )
                )
                suspect_columns.add(column)
                continue

    # --- value-leak patterns: paren-value / underscore / english / internal ---
    mapped_columns: set[str] = set()
    try:
        _alias_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "column_header_aliases.json")
        with open(_alias_path, encoding="utf-8") as _fh:
            _alias_doc = json.load(_fh)
        for _alias_item in _alias_doc.get("aliases") or []:
            if isinstance(_alias_item, dict) and _alias_item.get("column"):
                mapped_columns.add(str(_alias_item["column"]))
    except (OSError, ValueError, TypeError):
        mapped_columns = set()

    def _plausible_attribute(name: str) -> bool:
        return bool(name) and any("\u4e00" <= ch <= "\u9fff" for ch in name) \
            and not _VALUE_WORD.search(name) and "+" not in name

    for column in list(counts.keys()):
        if column in suspect_columns or column in mapped_columns:
            continue
        match = _PAREN_VALUE.match(column)
        if match:
            name_part = match.group(1).strip()
            value_part = match.group(2).strip()
            if value_part in _SCHEMA_UNIT_TOKENS or _PAREN_UNIT_OR_ABBR.match(value_part):
                continue
            if _plausible_attribute(name_part):
                suspects.append(
                    _record(
                        kind="attribute_value_header",
                        column=column,
                        occurrences=counts[column],
                        confidence=0.95,
                        suggested_attribute=name_part,
                        value_suffix=value_part,
                        sample_values=_sample_values(value_counts, column),
                    )
                )
            else:
                suspects.append(
                    _record(
                        kind="value_only_header",
                        column=column,
                        occurrences=counts[column],
                        confidence=0.9,
                        sample_values=_sample_values(value_counts, column),
                    )
                )
            suspect_columns.add(column)
            continue
        if _UNDERSCORE_TOKEN.search(column) \
                and not _ENGLISH_COLUMN.match(column) \
                and not _MIXED_ENGLISH_VALUE.match(column):
            suspects.append(
                _record(
                    kind="attribute_value_header",
                    column=column,
                    occurrences=counts[column],
                    confidence=0.85,
                    suggested_attribute=column.replace("_", "/"),
                    sample_values=_sample_values(value_counts, column),
                )
            )
            suspect_columns.add(column)
            continue
        if _INTERNAL_COLUMN.search(column):
            suspects.append(
                _record(
                    kind="value_only_header",
                    column=column,
                    occurrences=counts[column],
                    confidence=0.98,
                    sample_values=_sample_values(value_counts, column),
                )
            )
            suspect_columns.add(column)
            continue
        if _MIXED_ENGLISH_VALUE.match(column):
            suspects.append(
                _record(
                    kind="value_only_header",
                    column=column,
                    occurrences=counts[column],
                    confidence=0.95,
                    sample_values=_sample_values(value_counts, column),
                )
            )
            suspect_columns.add(column)
            continue
        if _VALUE_WORD.search(column) and not _ATTRIBUTE_SUFFIX.search(column):
            suspects.append(
                _record(
                    kind="value_only_header",
                    column=column,
                    occurrences=counts[column],
                    confidence=0.92,
                    sample_values=_sample_values(value_counts, column),
                )
            )
            suspect_columns.add(column)
            continue

    # Proven ``<value>_1`` / ``<value>_2`` pairs whose base itself looks like a
    # value (spaces or mixed-case words).  This catches e.g. ``NOMI Mate 3.0_1``.
    pair_evidence: Counter[str] = Counter()
    pair_columns: dict[str, tuple[str, str]] = {}
    for row in rows:
        for column, value in row.items():
            match = _NUMERIC_SUFFIX.match(str(column))
            if not match or match.group(2) != "1":
                continue
            base = match.group(1)
            second = f"{base}_2"
            if second not in row or not _positive(value) or not _positive(row[second]):
                continue
            if str(value).strip() == str(row[second]).strip():
                continue
            if not re.search(r"\s|(?<=[a-z])(?=[A-Z])", base):
                continue
            pair_evidence[base] += 1
            pair_columns[base] = (str(column), second)

    for base, evidence_rows in pair_evidence.items():
        first, second = pair_columns[base]
        suspects.append(
            _record(
                kind="package_value_header",
                column=f"{base}_1 / {base}_2",
                columns=[first, second],
                occurrences=evidence_rows,
                confidence=0.9,
                suggested_attribute="选装包列表",
                value_suffix="_1=描述, _2=状态",
            )
        )
        suspect_columns.update((first, second))

    # Match the same positive/different-value proof used by
    # merge_data.normalize_option_package_fields for plain snake_case bases.
    package_evidence: Counter[str] = Counter()
    package_columns: dict[str, tuple[str, str]] = {}
    for row in rows:
        for column, value in row.items():
            match = _NUMERIC_SUFFIX.match(str(column))
            if not match or match.group(2) != "1":
                continue
            base = match.group(1)
            second = f"{base}_2"
            if second not in row or not _positive(value) or not _positive(row[second]):
                continue
            if str(value).strip() == str(row[second]).strip():
                continue
            if re.search(r"\s|(?<=[a-z])(?=[A-Z])", base):
                continue
            package_evidence[base] += 1
            package_columns[base] = (str(column), second)

    for base, evidence_rows in package_evidence.items():
        first, second = package_columns[base]
        suspects.append(
            _record(
                kind="package_pair_header",
                column=f"{base}_1 / {base}_2",
                columns=[first, second],
                occurrences=evidence_rows,
                confidence=0.96,
                suggested_attribute="选装包列表",
                value_suffix="_1=描述, _2=状态",
            )
        )
        suspect_columns.update((first, second))

    # Preserve a lower-confidence bucket for numeric suffixes not covered by
    # the documented v4 map or proven package pair.
    proven_columns = set(suspect_columns)
    for column, occurrences in counts.items():
        if column in proven_columns:
            continue
        match = _NUMERIC_SUFFIX.match(column)
        if not match:
            continue
        base, suffix = match.groups()
        suspects.append(
            _record(
                kind="numeric_suffix_header",
                column=column,
                occurrences=occurrences,
                confidence=0.72,
                suggested_attribute=base,
                value_suffix=suffix,
                sample_values=_sample_values(value_counts, column),
            )
        )
        suspect_columns.add(column)

    # Unknown v4 bases are worth surfacing separately.
    for column, occurrences in counts.items():
        if column in proven_columns or any(item.get("column") == column for item in suspects):
            continue
        match = _UNKNOWN_V4.match(column)
        if match and match.group(1) not in V4_ATTRIBUTE_MAP:
            suspects.append(
                _record(
                    kind="unmapped_v4_header",
                    column=column,
                    occurrences=occurrences,
                    confidence=0.55,
                    value_suffix=(
                        column[len(match.group(1)) + 1 :].strip("_")
                        if "_" in column[len(match.group(1)) :]
                        else ""
                    ),
                    sample_values=_sample_values(value_counts, column),
                )
            )
            suspect_columns.add(column)

    # Bare value-looking English headers: multi-word / mixed-case columns with
    # no unit parentheses, not snake_case identifiers, not known attributes.
    # These are low-confidence; only the model can map them to an attribute.
    for column, occurrences in counts.items():
        if column in proven_columns or any(item.get("column") == column for item in suspects):
            continue
        if occurrences < 3:
            continue
        if column in KNOWN_ENGLISH_ATTRIBUTES:
            continue
        if column in V4_ATTRIBUTE_MAP:
            continue
        if not _BARE_VALUE.match(column):
            continue
        if _IDENTIFIER_LIKE.match(column):
            continue
        if "(" in column or ")" in column or "（" in column or "）" in column:
            continue
        suspects.append(
            _record(
                kind="bare_value_header",
                column=column,
                occurrences=occurrences,
                confidence=0.45,
                sample_values=_sample_values(value_counts, column),
            )
        )
        suspect_columns.add(column)

    suspects.sort(
        key=lambda item: (
            -float(item["confidence"]),
            -int(item["occurrences"]),
            str(item["kind"]),
            str(item["column"]),
        )
    )
    # Bound by kind quota so low-confidence categories (bare value headers,
    # unmapped v4 bases) always keep representative entries for the model.
    kind_order = [kind for kind, _count in Counter(item["kind"] for item in suspects).most_common()]
    quota = max(4, int(limit) // max(1, len(kind_order)))
    bounded: list[dict[str, Any]] = []
    for kind in kind_order:
        if len(bounded) >= max(0, int(limit)):
            break
        bounded.extend([item for item in suspects if item["kind"] == kind][:quota])
    by_kind: dict[str, dict[str, int]] = {}
    for item in suspects:
        kind = str(item["kind"])
        summary = by_kind.setdefault(kind, {"columns": 0, "occurrences": 0})
        summary["columns"] += 1
        summary["occurrences"] += int(item["occurrences"])

    candidate_attributes = [
        column
        for column, _count in counts.most_common()
        if column not in suspect_columns
        and column not in PROTECTED_ATTRIBUTES
        and "(" not in column
        and "（" not in column
    ]

    return {
        "status": "suspects-found" if suspects else "clean",
        "row_count": len(rows),
        "column_count": len(counts),
        "suspect_column_count": len(suspect_columns),
        "suspect_occurrences": sum(int(item["occurrences"]) for item in suspects),
        "by_kind": by_kind,
        "suspects": bounded,
        "candidate_attributes": candidate_attributes,
        "truncated": len(suspects) > len(bounded),
    }
