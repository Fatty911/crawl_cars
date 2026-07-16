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


def _value(row: dict[str, Any], field: str) -> str:
    value = str(row.get(field, "") or "").strip()
    return "" if value == "-" else value


def identity_key(row: dict[str, Any]) -> tuple[str, ...]:
    if not isinstance(row, dict):
        raise ValueError("each row must be a JSON object")
    model = _value(row, "车型名称")
    year = _value(row, "年款")
    if not year:
        match = re.search(r"(?:19|20)\d{2}", model)
        year = match.group(0) if match else ""
    series_id = _value(row, "车系ID")
    if not model:
        raise ValueError("identity requires 车型名称 and 年款")
    brand = _value(row, "品牌")
    series = _value(row, "车系")
    if not year and "易车" in _value(row, "数据来源"):
        if not brand or not series:
            raise ValueError("yiche no-year identity requires 品牌 and 车系")
        return ("yiche_no_year", brand, series, model)
    if not year:
        raise ValueError("identity requires 车型名称 and 年款")
    if series_id:
        return ("series_id", series_id, model, year)
    if not brand or not series:
        raise ValueError("identity without 车系ID requires 品牌 and 车系")
    return ("fallback", brand, series, model, year)


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        rows = json.load(file)
    if not isinstance(rows, list):
        raise ValueError(f"{path} must contain a JSON list")
    for row in rows:
        identity_key(row)
    return rows


def prepare_rows(stable_rows: list[dict[str, Any]], debug_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if not stable_rows or not debug_rows:
        raise ValueError("stable and debug inputs must both be non-empty")
    for label, rows in (("stable", stable_rows), ("debug", debug_rows)):
        keys = [identity_key(row) for row in rows]
        if len(set(keys)) != len(keys):
            raise ValueError(f"{label} input contains duplicate identities")
    stable_keys = {identity_key(row) for row in stable_rows}
    output = list(stable_rows)
    added_keys: set[tuple[str, ...]] = set()
    overlap = 0
    for row in debug_rows:
        key = identity_key(row)
        if key in stable_keys:
            overlap += 1
        elif key not in added_keys:
            output.append(row)
            added_keys.add(key)
    stats = {
        "stable_input": len(stable_rows),
        "debug_input": len(debug_rows),
        "overlap_kept_stable": overlap,
        "debug_added": len(added_keys),
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
    stable_rows = load_rows(args.stable)
    debug_rows = load_rows(args.debug)
    output, stats = prepare_rows(stable_rows, debug_rows)
    write_json_atomic(args.output, output)
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
