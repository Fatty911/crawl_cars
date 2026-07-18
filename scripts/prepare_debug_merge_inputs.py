#!/usr/bin/env python3
"""Prepare one deterministic stable-first crawler input for a debug merge."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

try:
    from publish_identity import has_chinese, identity_key, publish_boundary_valid, publish_year, row_car_id, value
except ModuleNotFoundError:
    from scripts.publish_identity import has_chinese, identity_key, publish_boundary_valid, publish_year, row_car_id, value


def load_json_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        rows = json.load(file)
    if not isinstance(rows, list):
        raise ValueError(f"{path} must contain a JSON list")
    return rows


def filter_valid_identity_rows(
    rows: list[dict[str, Any]],
    *,
    require_publish_boundary: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid = []
    invalid = []
    for row in rows:
        try:
            identity_key(row)
            if require_publish_boundary and not publish_boundary_valid(row):
                raise ValueError("identity row does not satisfy publish boundary")
        except ValueError:
            invalid.append(row)
        else:
            valid.append(row)
    return valid, invalid


def merge_identity_invalid_reason(row: dict[str, Any]) -> str:
    if not isinstance(row, dict):
        return "not_object"
    brand = value(row, "品牌")
    series = value(row, "车系")
    model = value(row, "车型名称")
    year = value(row, "年款")
    model_id = row_car_id(row)
    if not brand or not has_chinese(brand):
        return "invalid_brand"
    if not series or not has_chinese(series):
        return "invalid_series"
    if not model:
        return "invalid_model_name"
    if not re.fullmatch(r"(?:19|20)\d{2}", year):
        return "invalid_year"
    if not model_id or not re.fullmatch(r"\d+", model_id):
        return "invalid_model_id"
    try:
        identity_key(row)
    except ValueError as exc:
        return f"invalid_identity:{exc}"
    return ""


def filter_merge_identity_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    valid = []
    stats: dict[str, int] = {"input": len(rows), "invalid_dropped": 0}
    for row in rows:
        reason = merge_identity_invalid_reason(row)
        if reason:
            stats["invalid_dropped"] += 1
            stats[f"{reason}_dropped"] = stats.get(f"{reason}_dropped", 0) + 1
        else:
            valid.append(row)
    stats["valid"] = len(valid)
    return valid, stats


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = load_json_rows(path)
    for row in rows:
        identity_key(row)
    return rows


def load_merge_rows(path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    return filter_merge_identity_rows(load_json_rows(path))


def prepare_rows(
    stable_rows: list[dict[str, Any]],
    debug_rows: list[dict[str, Any]],
    *,
    dedupe_partial: bool = False,
    debug_invalid_identity_dropped: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if not stable_rows or not debug_rows:
        raise ValueError("stable and debug inputs must both be non-empty")
    stable_keys_list = [identity_key(row) for row in stable_rows]
    if len(set(stable_keys_list)) != len(stable_keys_list):
        raise ValueError("stable input contains duplicate identities")
    debug_keys = [identity_key(row) for row in debug_rows]
    debug_duplicates_dropped = len(debug_keys) - len(set(debug_keys))
    if debug_duplicates_dropped and not dedupe_partial:
        raise ValueError("debug input contains duplicate identities")

    stable_keys = set(stable_keys_list)
    output = list(stable_rows)
    incoming_keys: set[tuple[str, ...]] = set()
    added_keys: set[tuple[str, ...]] = set()
    overlap = 0
    for row, key in zip(debug_rows, debug_keys):
        if key in incoming_keys:
            continue
        incoming_keys.add(key)
        if key in stable_keys:
            overlap += 1
        else:
            output.append(row)
            added_keys.add(key)
    stats = {
        "stable_input": len(stable_rows),
        "debug_input": len(debug_rows),
        "debug_duplicates_dropped": debug_duplicates_dropped,
        "overlap_kept_stable": overlap,
        "debug_added": len(added_keys),
        "debug_invalid_identity_dropped": debug_invalid_identity_dropped,
        "output_rows": len(output),
    }
    return output, stats


def write_json_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(rows, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stable", type=Path, required=True)
    parser.add_argument("--debug", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dedupe_partial = (
        os.environ.get("DEBUG_MODE") == "false"
        and os.environ.get("TRIGGER_SOURCE") == "dongchedi-crawl"
    )
    stable_rows, stable_filter_stats = load_merge_rows(args.stable)
    debug_rows, debug_filter_stats = load_merge_rows(args.debug)
    output, stats = prepare_rows(
        stable_rows,
        debug_rows,
        dedupe_partial=dedupe_partial,
        debug_invalid_identity_dropped=debug_filter_stats["invalid_dropped"],
    )
    stats.update({
        "stable_raw_input": stable_filter_stats["input"],
        "stable_invalid_dropped": stable_filter_stats["invalid_dropped"],
        "debug_raw_input": debug_filter_stats["input"],
        "debug_invalid_dropped": debug_filter_stats["invalid_dropped"],
    })
    for prefix, filter_stats in (("stable", stable_filter_stats), ("debug", debug_filter_stats)):
        for key, value in filter_stats.items():
            if key.endswith("_dropped") and key != "invalid_dropped" and value:
                stats[f"{prefix}_{key}"] = value
    write_json_atomic(args.output, output)
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
