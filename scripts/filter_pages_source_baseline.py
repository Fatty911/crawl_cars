#!/usr/bin/env python3
"""Build an exact single-source Pages fallback baseline for partial merges."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prepare_debug_merge_inputs import filter_valid_identity_rows, load_json_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", choices=["autohome", "dongchedi"], required=True)
    parser.add_argument("--min-rows", type=int, default=50)
    args = parser.parse_args()
    label = "仅汽车之家" if args.source == "autohome" else "仅懂车帝"
    source_name = "汽车之家" if args.source == "autohome" else "懂车帝"
    rows = load_json_rows(args.input)
    exact_rows = [row for row in rows if str(row.get("数据来源", "") or "").strip() == label]
    cross_source_dropped = sum(
        1
        for row in rows
        if source_name in str(row.get("数据来源", "") or "")
        and str(row.get("数据来源", "") or "").strip() != label
    )
    valid_rows, invalid_rows = filter_valid_identity_rows(exact_rows, require_publish_boundary=True)
    stats = {
        "source": label,
        "total": len(rows),
        "single_source": len(valid_rows),
        "cross_source_dropped": cross_source_dropped,
        "invalid_identity_dropped": len(invalid_rows),
    }
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    if len(valid_rows) < args.min_rows:
        raise SystemExit(f"{label} Pages stable 基线不足: {len(valid_rows)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        json.dump(valid_rows, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
