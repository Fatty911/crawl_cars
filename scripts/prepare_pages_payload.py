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


YEAR_RE = re.compile(r"(?:19|20)\d{2}")


def model_year(row: dict[str, Any]) -> int | None:
    for value in (row.get("年款"), row.get("车型名称")):
        match = YEAR_RE.search(str(value or ""))
        if match:
            return int(match.group(0))
    return None


def keep_value(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or value.strip() not in {"", "-"})


def prepare_rows(rows: Any, min_year: int) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError("Pages payload input must be a JSON array")
    prepared = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        year = model_year(row)
        if year is None or year < min_year:
            continue
        prepared.append({key: value for key, value in row.items() if keep_value(value)})
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
    prepared = prepare_rows(rows, args.min_year)
    write_atomic(args.output, prepared)
    print(
        json.dumps(
            {
                "inputRows": len(rows),
                "outputRows": len(prepared),
                "inputBytes": before_bytes,
                "outputBytes": args.output.stat().st_size,
                "minYear": args.min_year,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
