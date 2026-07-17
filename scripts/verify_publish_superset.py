#!/usr/bin/env python3
"""Fail closed unless a publish candidate preserves every baseline identity and row."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from merge_data import keep_pages_year
from prepare_debug_merge_inputs import filter_valid_identity_rows, identity_key, load_json_rows


def verify_superset(baseline_rows: list[dict], candidate_rows: list[dict]) -> dict[str, int]:
    baseline_rows = [row for row in baseline_rows if keep_pages_year(row)]
    candidate_rows = [row for row in candidate_rows if keep_pages_year(row)]
    if not baseline_rows or not candidate_rows:
        raise ValueError("2022+ baseline and candidate must both be non-empty")
    if len(candidate_rows) < len(baseline_rows):
        raise ValueError(
            f"candidate row count decreased: baseline={len(baseline_rows)} candidate={len(candidate_rows)}"
        )
    baseline_keys = {identity_key(row) for row in baseline_rows}
    candidate_keys = {identity_key(row) for row in candidate_rows}
    missing = baseline_keys - candidate_keys
    if missing:
        sample = sorted(missing)[:5]
        raise ValueError(f"candidate is missing {len(missing)} baseline identities: {sample}")
    return {
        "baseline_rows": len(baseline_rows),
        "candidate_rows": len(candidate_rows),
        "retained_rows": len(baseline_keys),
        "added_rows": len(candidate_keys - baseline_keys),
        "missing_rows": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    try:
        baseline_rows = [row for row in load_json_rows(args.baseline) if keep_pages_year(row)]
        baseline_rows, invalid_baseline_rows = filter_valid_identity_rows(baseline_rows)
        candidate_rows, invalid_candidate_rows = filter_valid_identity_rows(load_json_rows(args.candidate))
        stats = verify_superset(baseline_rows, candidate_rows)
        if invalid_baseline_rows:
            stats["baseline_invalid_identity_dropped"] = len(invalid_baseline_rows)
            print(f"warning: dropped {len(invalid_baseline_rows)} published baseline rows without a verifiable identity")
        if invalid_candidate_rows:
            stats["candidate_invalid_identity_dropped"] = len(invalid_candidate_rows)
            print(f"warning: dropped {len(invalid_candidate_rows)} candidate rows without a verifiable identity")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"publish superset verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
