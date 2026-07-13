#!/usr/bin/env python3
"""Preserve every currently published identity in a debug merge candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from merge_data import collect_fields, filter_car, keep_pages_year, write_csv, write_json
from prepare_debug_merge_inputs import identity_key, load_rows


def preserve_rows(baseline_rows: list[dict], candidate_rows: list[dict]) -> tuple[list[dict], dict[str, int]]:
    baseline_rows = [row for row in baseline_rows if keep_pages_year(row)]
    candidate_rows = [row for row in candidate_rows if keep_pages_year(row)]
    if not baseline_rows or not candidate_rows:
        raise ValueError("2022+ baseline and candidate must both be non-empty")

    candidate_keys = {identity_key(row) for row in candidate_rows}
    preserved = list(candidate_rows)
    restored = 0
    for row in baseline_rows:
        key = identity_key(row)
        if key not in candidate_keys:
            preserved.append(row)
            candidate_keys.add(key)
            restored += 1

    return preserved, {
        "baseline_rows": len(baseline_rows),
        "candidate_input_rows": len(candidate_rows),
        "restored_rows": restored,
        "candidate_output_rows": len(preserved),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--merged-json", type=Path, required=True)
    parser.add_argument("--merged-csv", type=Path, required=True)
    parser.add_argument("--filtered-json", type=Path, required=True)
    parser.add_argument("--filtered-csv", type=Path, required=True)
    args = parser.parse_args()

    rows, stats = preserve_rows(load_rows(args.baseline), load_rows(args.merged_json))
    filtered_rows = [row for row in rows if filter_car(row)]
    header = collect_fields(rows)
    write_json(args.merged_json, rows)
    write_csv(args.merged_csv, rows, header)
    write_json(args.filtered_json, filtered_rows)
    write_csv(args.filtered_csv, filtered_rows, header)
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
