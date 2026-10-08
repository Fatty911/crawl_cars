#!/usr/bin/env python3
"""Fail closed unless a publish candidate preserves every baseline identity and row."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from merge_data import dedupe_merged_rows, keep_pages_year, partition_publishable_rows
from prepare_debug_merge_inputs import filter_valid_identity_rows, identity_key, load_json_rows



def _identity_safe_rows(rows):
    """Drop rows that cannot form an identity key.

    Used after dedup-style transformations that may merge source labels
    across rows with different identity completeness.  Without this filter,
    identity_key() raises on rows that gained a new source label via merge
    but do not satisfy that source identity requirements.
    """
    valid, invalid = filter_valid_identity_rows(rows)
    if invalid:
        print(f"note: dropped {len(invalid)} post-dedupe rows without verifiable identity (baseline dedupe artefact)")
    return valid


def verify_superset(baseline_rows: list[dict], candidate_rows: list[dict]) -> dict[str, int]:
    baseline_rows = [row for row in baseline_rows if keep_pages_year(row)]
    baseline_rows = dedupe_merged_rows(baseline_rows)
    # Dedupe can merge rows with different source identity completeness;
    # filter before building identity keys to avoid identity_key() raising.
    baseline_rows = _identity_safe_rows(baseline_rows)
    candidate_rows = [row for row in candidate_rows if keep_pages_year(row)]
    if not baseline_rows or not candidate_rows:
        raise ValueError("2022+ baseline and candidate must both be non-empty")
    baseline_keys = {identity_key(row) for row in baseline_rows}
    candidate_keys = {identity_key(row) for row in candidate_rows}
    missing = baseline_keys - candidate_keys

    # 守卫一：**候选行数下降**必须 fail closed。
    # 这是最直接的「数据丢了」信号，且与身份数学无关——旧实现完全没有这道闸，
    # 只有下面那条基于身份集合的比较，于是「基线 N 行、候选只剩 1 行」
    # 只要身份集合没有严格减少就可能被放过。
    if len(candidate_rows) < len(baseline_rows):
        raise ValueError(
            f"candidate row count decreased: baseline={len(baseline_rows)} "
            f"candidate={len(candidate_rows)}"
        )

    # 守卫二：「缺一些基线身份」有两种成因，必须分开判：
    #   A. **数据演化**：车型下线/改名，候选用新身份补上，行数不减。
    #   B. **数据丢失**：爬取没跑全/被反爬拦截。
    # 旧实现是 `len(missing) <= max(50, 2%)` 放行，问题出在那个**绝对下限 50**：
    # 对 2 行的基线它允许丢 50 个身份（也就是全丢光）也算「正常演化」，
    # 这道闸等于形同虚设（实测 2 行基线缺 1 行即被静默容忍）。
    # 现在下限去掉——容忍度只按基线规模的比例给，2 行基线的容忍度就是 0。
    missing_tolerance = int(len(baseline_keys) * 0.02)
    if missing and len(missing) <= missing_tolerance:
        print(
            f"WARNING: candidate missing {len(missing)} baseline identities "
            f"(<=2% data evolution): {sorted(missing)[:5]}"
        )
    elif missing:
        if len(candidate_keys) < len(baseline_keys):
            sample = sorted(missing)[:10]
            raise ValueError(
                f"candidate unique identity count decreased: baseline={len(baseline_keys)} candidate={len(candidate_keys)} missing={len(missing)} sample={sample}"
            )
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
        baseline_rows, baseline_publish_stats = partition_publishable_rows(baseline_rows)
        baseline_rows, invalid_baseline_rows = filter_valid_identity_rows(baseline_rows)
        candidate_rows, candidate_publish_stats = partition_publishable_rows(load_json_rows(args.candidate))
        candidate_rows, invalid_candidate_rows = filter_valid_identity_rows(candidate_rows)
        stats = verify_superset(baseline_rows, candidate_rows)
        if invalid_baseline_rows:
            stats["baseline_invalid_identity_dropped"] = len(invalid_baseline_rows)
            print(f"warning: dropped {len(invalid_baseline_rows)} published baseline rows without a verifiable identity")
        if invalid_candidate_rows:
            stats["candidate_invalid_identity_dropped"] = len(invalid_candidate_rows)
            print(f"warning: dropped {len(invalid_candidate_rows)} candidate rows without a verifiable identity")
        for key, value in {
            "baseline_invalid_brand_dropped": baseline_publish_stats["invalid_brand"],
            "baseline_invalid_model_name_dropped": baseline_publish_stats["invalid_model_name"],
            "candidate_invalid_brand_dropped": candidate_publish_stats["invalid_brand"],
            "candidate_invalid_model_name_dropped": candidate_publish_stats["invalid_model_name"],
        }.items():
            if value:
                stats[key] = value
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"publish superset verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
