#!/usr/bin/env python3
"""Deterministically diagnose Pages columns that encode values as headers.

The crawler payload is intentionally treated as evidence only.  This module
does not rename fields or infer new data; it reports high-signal header
patterns for the read-only audit Agent and the bounded repair workflow.
"""
from __future__ import annotations

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

_HYPHEN_VALUE = re.compile(r"^(.+?)\s+-\s+(\S.*)$")
_V4_VALUE = re.compile(r"^(.+_v4)_(.+)$")
_NUMERIC_SUFFIX = re.compile(r"^(.+)_(\d+)$")
_UNKNOWN_V4 = re.compile(r"^(.+_v4)(?:_|$)")
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
    return item


def diagnose_columns(rows: list[dict[str, Any]], *, limit: int = 80) -> dict[str, Any]:
    """Return bounded, deterministic evidence about suspicious column names.

    The report has three confidence levels:

    * ``attribute_value_header``: explicit ``属性 - 值`` or documented v4
      one-hot headers; the parent attribute is known.
    * ``package_pair_header``: a proven non-empty, different ``_1``/``_2``
      pair, matching the existing package normalizer's evidence rule.
    * ``numeric_suffix_header``: an unclassified numeric suffix that may be a
      one-hot value or a package field and needs model/source-code review.
    """
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise TypeError("rows must be a list of objects")

    counts = _column_counts(rows)
    suspects: list[dict[str, Any]] = []
    suspect_columns: set[str] = set()

    for column, occurrences in counts.items():
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
                )
            )
            suspect_columns.add(column)
            continue

    # Match the same positive/different-value proof used by
    # merge_data.normalize_option_package_fields.  Merely seeing `_1` is not
    # enough to call a field a package pair.
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
            pair_evidence[base] += 1
            pair_columns[base] = (str(column), second)

    for base, evidence_rows in pair_evidence.items():
        first, second = pair_columns[base]
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
    # the documented v4 map or proven package pair.  This is useful for model
    # diagnosis without allowing the model to silently rename them.
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
            )
        )
        suspect_columns.add(column)

    # Unknown v4 bases are worth surfacing separately.  They are not treated
    # as high-confidence fixes because the canonical attribute is not known.
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
                    value_suffix=column[len(match.group(1)) + 1 :].strip("_") if "_" in column[len(match.group(1)) :] else "",
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
    bounded = suspects[: max(0, int(limit))]
    by_kind: dict[str, dict[str, int]] = {}
    for item in suspects:
        kind = str(item["kind"])
        summary = by_kind.setdefault(kind, {"columns": 0, "occurrences": 0})
        summary["columns"] += 1
        summary["occurrences"] += int(item["occurrences"])

    return {
        "status": "suspects-found" if suspects else "clean",
        "row_count": len(rows),
        "column_count": len(counts),
        "suspect_column_count": len(suspect_columns),
        "suspect_occurrences": sum(int(item["occurrences"]) for item in suspects),
        "by_kind": by_kind,
        "suspects": bounded,
        "truncated": len(suspects) > len(bounded),
    }
