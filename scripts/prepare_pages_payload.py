#!/usr/bin/env python3
"""Build a sparse, recent-model JSON payload for the static Pages UI."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
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

YEAR_RE = re.compile(r"(?:19|20)\d{2}")


def model_year(row: dict[str, Any]) -> int | None:
    for value in (row.get("年款"), row.get("车型名称")):
        match = YEAR_RE.search(str(value or ""))
        if match:
            return int(match.group(0))
    return None


def keep_value(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or value.strip() not in {"", "-"})


def source_allows_missing_year(row: dict[str, Any]) -> bool:
    return False


def has_chinese(value: Any) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(value or "")))


def prepare_rows_with_stats(rows: Any, min_year: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
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
    return prepared, stats


def prepare_rows(rows: Any, min_year: int) -> list[dict[str, Any]]:
    prepared, _stats = prepare_rows_with_stats(rows, min_year)
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
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
