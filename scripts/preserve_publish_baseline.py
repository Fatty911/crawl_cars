#!/usr/bin/env python3
"""Preserve every currently published identity in a debug merge candidate."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from merge_data import (
    IDENTITY_FIELDS,
    atomic_source_names,
    collect_fields,
    filter_car,
    has_explicit_battery_field_inconsistency,
    keep_pages_year,
    match_score,
    model_variant_conflict_reason,
    model_variant_signature,
    normalize_series_match_text,
    partition_publishable_rows,
    row_year,
    write_csv,
    write_json,
)
from prepare_debug_merge_inputs import filter_valid_identity_rows, identity_key, load_json_rows
from prepare_pages_payload import prepare_rows
from publish_identity import publish_boundary_valid


ALIAS_ENRICH_THRESHOLD = 0.85


def unique_keys(label: str, rows: list[dict]) -> list[tuple[str, ...]]:
    keys = [identity_key(row) for row in rows]
    if len(set(keys)) != len(keys):
        raise ValueError(f"{label} input contains duplicate identities")
    return keys


def missing_value(value: object) -> bool:
    return value is None or str(value).strip() in {"", "-"}


def enrich_baseline_row(baseline: dict, candidate: dict) -> tuple[dict, bool]:
    enriched = dict(baseline)
    changed = False
    sources = atomic_source_names(baseline.get("数据来源"))
    for source in atomic_source_names(candidate.get("数据来源")):
        if source not in sources:
            sources.append(source)
            changed = True
    if changed:
        enriched["数据来源"] = "+".join(sources)

    for field, value in candidate.items():
        if field == "数据来源" or field in IDENTITY_FIELDS:
            continue
        if missing_value(enriched.get(field)) and not missing_value(value):
            enriched[field] = value
            changed = True
    return enriched, changed


def variant_bucket(row: dict) -> tuple[str, int] | None:
    series = normalize_series_match_text(row.get("车系", ""))
    year = row_year(row)
    return (series, year) if series and year else None


def stale_source_retirement_is_proven(
    baseline: dict,
    candidate: dict,
    retired_sources: set[str],
    candidate_rows_by_bucket: dict[tuple[str, int], list[dict]],
) -> bool:
    if has_explicit_battery_field_inconsistency(baseline):
        return True

    bucket = variant_bucket(candidate)
    if bucket is None:
        return False
    bucket_rows = candidate_rows_by_bucket.get(bucket, [])
    for source in retired_sources:
        source_rows = [
            row
            for row in bucket_rows
            if source in atomic_source_names(row.get("数据来源"))
        ]
        if len(source_rows) != 1:
            return False
        if model_variant_conflict_reason(candidate, source_rows[0]) != "tier_mismatch":
            return False
    return True


def format_sources(sources: set[str]) -> str:
    ordered = [source for source in ("汽车之家", "懂车帝", "易车") if source in sources]
    return f"仅{ordered[0]}" if len(ordered) == 1 else "+".join(ordered)


def retired_sources_without_identity_overlap(
    baseline: dict,
    candidate_rows_by_bucket: dict[tuple[str, int], list[dict]],
) -> set[str]:
    sources = set(atomic_source_names(baseline.get("数据来源")))
    if sources != {"汽车之家", "懂车帝"} or missing_value(baseline.get("车款ID")):
        return set()
    if has_explicit_battery_field_inconsistency(baseline):
        return {"懂车帝"}

    bucket = variant_bucket(baseline)
    if bucket is None:
        return set()
    dongchedi_rows = [
        row
        for row in candidate_rows_by_bucket.get(bucket, [])
        if "懂车帝" in atomic_source_names(row.get("数据来源"))
    ]
    if len(dongchedi_rows) != 1:
        return set()
    dongchedi_tiers = model_variant_signature(dongchedi_rows[0])["tier"]
    if dongchedi_tiers == {"basic"} and model_variant_conflict_reason(baseline, dongchedi_rows[0]) == "tier_mismatch":
        return {"懂车帝"}
    return set()


def alias_match_score(baseline: dict, candidate: dict, source: str) -> float:
    if source == "懂车帝":
        score, _reasons = match_score(candidate, baseline, True)
    else:
        score, _reasons = match_score(baseline, candidate, True)
    return score


def cross_identity_alias_matches(
    baseline_rows: list[dict],
    baseline_keys: list[tuple[str, ...]],
    candidate_keys: set[tuple[str, ...]],
    candidate_rows_by_bucket: dict[tuple[str, int], list[dict]],
) -> list[tuple[int, dict]]:
    """Return conservative one-to-one source aliases without changing identities."""
    baselines_by_source_bucket: dict[tuple[str, tuple[str, int]], list[tuple[int, dict]]] = {}
    for index, (row, key) in enumerate(zip(baseline_rows, baseline_keys)):
        if key in candidate_keys:
            continue
        sources = atomic_source_names(row.get("数据来源"))
        bucket = variant_bucket(row)
        if len(sources) != 1 or sources[0] not in {"汽车之家", "懂车帝"} or bucket is None:
            continue
        baselines_by_source_bucket.setdefault((sources[0], bucket), []).append((index, row))

    matches: list[tuple[int, dict]] = []
    for (source, bucket), baseline_group in baselines_by_source_bucket.items():
        candidate_group = [
            row
            for row in candidate_rows_by_bucket.get(bucket, [])
            if {"汽车之家", "懂车帝"}.issubset(
                atomic_source_names(row.get("数据来源"))
            )
        ]
        if not candidate_group or len(baseline_group) * len(candidate_group) > 20_000:
            continue

        best_by_baseline: dict[int, tuple[float, int, bool]] = {}
        best_by_candidate: dict[int, tuple[float, int, bool]] = {}
        for baseline_position, (_index, baseline) in enumerate(baseline_group):
            for candidate_position, candidate in enumerate(candidate_group):
                score = alias_match_score(baseline, candidate, source)
                if score < ALIAS_ENRICH_THRESHOLD:
                    continue
                current = best_by_baseline.get(baseline_position)
                if current is None or score > current[0]:
                    best_by_baseline[baseline_position] = (score, candidate_position, False)
                elif score == current[0]:
                    best_by_baseline[baseline_position] = (score, current[1], True)
                current = best_by_candidate.get(candidate_position)
                if current is None or score > current[0]:
                    best_by_candidate[candidate_position] = (score, baseline_position, False)
                elif score == current[0]:
                    best_by_candidate[candidate_position] = (score, current[1], True)

        for baseline_position, (_score, candidate_position, baseline_tied) in best_by_baseline.items():
            candidate_best = best_by_candidate.get(candidate_position)
            if (
                baseline_tied
                or candidate_best is None
                or candidate_best[2]
                or candidate_best[1] != baseline_position
            ):
                continue
            index, baseline = baseline_group[baseline_position]
            candidate = candidate_group[candidate_position]
            enriched, changed = enrich_baseline_row(baseline, candidate)
            if not changed or not publish_boundary_valid(enriched):
                continue
            try:
                if identity_key(enriched) != baseline_keys[index]:
                    continue
            except ValueError:
                continue
            matches.append((index, candidate))
    return matches


def preserve_rows(baseline_rows: list[dict], candidate_rows: list[dict]) -> tuple[list[dict], dict[str, int]]:
    baseline_rows = [row for row in baseline_rows if keep_pages_year(row)]
    candidate_rows = [row for row in candidate_rows if keep_pages_year(row)]
    if not baseline_rows:
        raise ValueError("2022+ baseline must be non-empty")
    if not candidate_rows:
        raise ValueError("2022+ candidate must be non-empty")

    baseline_keys = unique_keys("baseline", baseline_rows)
    candidate_keys = unique_keys("candidate", candidate_rows)
    output_indexes = {key: index for index, key in enumerate(baseline_keys)}
    candidate_rows_by_bucket: dict[tuple[str, int], list[dict]] = {}
    for row in prepare_rows(candidate_rows, min_year=2022):
        bucket = variant_bucket(row)
        if bucket is not None:
            candidate_rows_by_bucket.setdefault(bucket, []).append(row)
    preserved = list(baseline_rows)
    candidate_added = 0
    candidate_enriched = 0
    candidate_deenriched = 0
    for row, key in zip(candidate_rows, candidate_keys):
        if key not in output_indexes:
            output_indexes[key] = len(preserved)
            preserved.append(row)
            candidate_added += 1
            continue
        index = output_indexes[key]
        baseline_sources = set(atomic_source_names(preserved[index].get("数据来源")))
        candidate_sources = set(atomic_source_names(row.get("数据来源")))
        retired_sources = baseline_sources - candidate_sources
        if (
            candidate_sources
            and candidate_sources < baseline_sources
            and stale_source_retirement_is_proven(
                preserved[index],
                row,
                retired_sources,
                candidate_rows_by_bucket,
            )
        ):
            preserved[index] = row
            candidate_deenriched += 1
            continue
        preserved[index], changed = enrich_baseline_row(preserved[index], row)
        candidate_enriched += int(changed)

    candidate_key_set = set(candidate_keys)
    candidate_alias_enriched = 0
    for index, candidate in cross_identity_alias_matches(
        preserved,
        baseline_keys,
        candidate_key_set,
        candidate_rows_by_bucket,
    ):
        preserved[index], changed = enrich_baseline_row(preserved[index], candidate)
        candidate_alias_enriched += int(changed)

    for index, key in enumerate(baseline_keys):
        if key in candidate_key_set:
            continue
        retired_sources = retired_sources_without_identity_overlap(
            preserved[index],
            candidate_rows_by_bucket,
        )
        if not retired_sources:
            continue
        remaining_sources = set(atomic_source_names(preserved[index].get("数据来源"))) - retired_sources
        if not remaining_sources:
            continue
        preserved[index] = dict(preserved[index], 数据来源=format_sources(remaining_sources))
        candidate_deenriched += 1

    stats = {
        "baseline_rows": len(baseline_rows),
        "candidate_input_rows": len(candidate_rows),
        "overlap_kept_baseline": len(candidate_rows) - candidate_added,
        "candidate_added": candidate_added,
        "candidate_enriched": candidate_enriched,
        "candidate_output_rows": len(preserved),
    }
    if candidate_deenriched:
        stats["candidate_deenriched"] = candidate_deenriched
    if candidate_alias_enriched:
        stats["candidate_alias_enriched"] = candidate_alias_enriched
    return preserved, stats


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

    baseline_rows = [row for row in load_json_rows(args.baseline) if keep_pages_year(row)]
    baseline_rows, baseline_publish_stats = partition_publishable_rows(baseline_rows)
    baseline_rows, invalid_baseline_rows = filter_valid_identity_rows(baseline_rows)
    candidate_rows, candidate_publish_stats = partition_publishable_rows(load_json_rows(args.merged_json))
    candidate_rows, invalid_candidate_rows = filter_valid_identity_rows(candidate_rows)
    rows, stats = preserve_rows(baseline_rows, candidate_rows)
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
    write_publish_assets(rows, args.merged_json, args.merged_csv, args.filtered_json, args.filtered_csv)
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
