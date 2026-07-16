#!/usr/bin/env python3
"""Preserve every currently published identity in a debug merge candidate."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from merge_data import collect_fields, filter_car, keep_pages_year, write_csv, write_json
from prepare_debug_merge_inputs import identity_key, load_rows


def unique_keys(label: str, rows: list[dict]) -> list[tuple[str, ...]]:
    keys = [identity_key(row) for row in rows]
    if len(set(keys)) != len(keys):
        raise ValueError(f"{label} input contains duplicate identities")
    return keys


def preserve_rows(baseline_rows: list[dict], candidate_rows: list[dict]) -> tuple[list[dict], dict[str, int]]:
    baseline_rows = [row for row in baseline_rows if keep_pages_year(row)]
    candidate_rows = [row for row in candidate_rows if keep_pages_year(row)]
    if not baseline_rows:
        raise ValueError("2022+ baseline must be non-empty")
    if not candidate_rows:
        raise ValueError("2022+ candidate must be non-empty")

    baseline_keys = unique_keys("baseline", baseline_rows)
    candidate_keys = unique_keys("candidate", candidate_rows)
    output_keys = set(baseline_keys)
    preserved = list(baseline_rows)
    candidate_added = 0
    for row, key in zip(candidate_rows, candidate_keys):
        if key not in output_keys:
            preserved.append(row)
            output_keys.add(key)
            candidate_added += 1

    return preserved, {
        "baseline_rows": len(baseline_rows),
        "candidate_input_rows": len(candidate_rows),
        "overlap_kept_baseline": len(candidate_rows) - candidate_added,
        "candidate_added": candidate_added,
        "candidate_output_rows": len(preserved),
    }


def write_publish_assets(
    rows: list[dict],
    merged_json: Path,
    merged_csv: Path,
    filtered_json: Path,
    filtered_csv: Path,
) -> None:
    targets = (merged_json, merged_csv, filtered_json, filtered_csv)
    parents = {target.parent.resolve() for target in targets}
    if len(parents) != 1:
        raise ValueError("publish assets must share one output directory")
    if len({target.resolve() for target in targets}) != len(targets):
        raise ValueError("publish asset paths must be distinct")

    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)

    staged: dict[Path, Path] = {}
    try:
        for target in targets:
            descriptor, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
            os.close(descriptor)
            staged[target] = Path(temp_name)

        filtered_rows = [row for row in rows if filter_car(row)]
        header = collect_fields(rows)
        write_json(staged[merged_json], rows)
        write_csv(staged[merged_csv], rows, header)
        write_json(staged[filtered_json], filtered_rows)
        write_csv(staged[filtered_csv], filtered_rows, header)
        for temp_path in staged.values():
            with temp_path.open("rb+") as file:
                os.fsync(file.fileno())
        for target, temp_path in staged.items():
            os.replace(temp_path, target)
    finally:
        for temp_path in staged.values():
            temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--merged-json", type=Path, required=True)
    parser.add_argument("--merged-csv", type=Path, required=True)
    parser.add_argument("--filtered-json", type=Path, required=True)
    parser.add_argument("--filtered-csv", type=Path, required=True)
    args = parser.parse_args()

    rows, stats = preserve_rows(load_rows(args.baseline), load_rows(args.merged_json))
    write_publish_assets(rows, args.merged_json, args.merged_csv, args.filtered_json, args.filtered_csv)
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
