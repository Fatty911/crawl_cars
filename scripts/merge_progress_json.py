#!/usr/bin/env python3
"""Merge crawler progress JSON files during git sync conflicts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_list(left: list[Any], right: list[Any]) -> list[Any]:
    if all(isinstance(item, dict) and "id" in item for item in left + right):
        merged: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for item in left + right:
            key = str(item["id"])
            if key not in merged:
                merged[key] = dict(item)
                order.append(key)
            else:
                merged[key] = merge_value(merged[key], item)
        return [merged[key] for key in order]

    result: list[Any] = []
    seen: set[str] = set()
    for item in left + right:
        marker = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if marker not in seen:
            seen.add(marker)
            result.append(item)
    return result


def merge_value(left: Any, right: Any) -> Any:
    if isinstance(left, dict) and isinstance(right, dict):
        merged: dict[str, Any] = {}
        for key in sorted(set(left) | set(right)):
            if key in left and key in right:
                merged[key] = merge_value(left[key], right[key])
            elif key in left:
                merged[key] = left[key]
            else:
                merged[key] = right[key]
        return merged

    if isinstance(left, list) and isinstance(right, list):
        return merge_list(left, right)

    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return max(left, right)

    if right in (None, "", []):
        return left
    return right


def normalize_progress(data: Any) -> Any:
    if not isinstance(data, dict):
        return data

    series = data.get("series_list")
    crawled = data.get("crawled_series")
    if isinstance(series, list) and isinstance(crawled, list):
        order = {str(item.get("id")): idx for idx, item in enumerate(series) if isinstance(item, dict)}
        unique = []
        seen = set()
        for sid in crawled:
            sid_text = str(sid)
            if sid_text not in seen:
                seen.add(sid_text)
                unique.append(sid_text)
        unique.sort(key=lambda sid: (order.get(sid, len(order)), sid))
        data["crawled_series"] = unique

    return data


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: merge_progress_json.py OUTPUT LEFT RIGHT [RIGHT...]", file=sys.stderr)
        return 2

    output = Path(sys.argv[1])
    merged = load_json(sys.argv[2])
    for path in sys.argv[3:]:
        merged = merge_value(merged, load_json(path))
    merged = normalize_progress(merged)

    with open(output, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
