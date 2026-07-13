#!/usr/bin/env python3
"""Fail closed unless a publish candidate preserves every baseline identity and row."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from prepare_debug_merge_inputs import identity_key, load_rows


def verify_superset(baseline_rows: list[dict], candidate_rows: list[dict]) -> dict[str, int]:
    if not baseline_rows or not candidate_rows:
        raise ValueError("baseline and candidate must both be non-empty")
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
        stats = verify_superset(load_rows(args.baseline), load_rows(args.candidate))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"publish superset verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
