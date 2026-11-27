#!/usr/bin/env python3
"""Preserve every currently published identity in a debug merge candidate."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import re
import tempfile
from pathlib import Path

from merge_data import (
    _preserved_value_parts,
    _price_norm,
    IDENTITY_FIELDS,
    atomic_source_names,
    collect_fields,
    clean_brand_field,
    is_excluded_brand,
    annotate_ev_range,
    filter_car,
    has_explicit_battery_field_inconsistency,
    keep_pages_year,
    match_score,
    model_variant_conflict_reason,
    model_variant_signature,
    narrow_pages_rows,
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


def refold_source_segments(value: str) -> str:
    """把存量脏值重折成「每源一段」：复用 merge_data 的源段切分器。

    与 merge_data 同一条口径：无源前缀的尾段归属上一个源；同源多段按字面并集；
    不跨源折叠；同源段内重复前缀（叠前缀）就地剥掉。
    """
    previous = ""
    order: list[str] = []
    tokens: dict[str, list[str]] = {}
    for label, text in _preserved_value_parts(value):
        source = label or previous
        if label:
            previous = label
        if source not in tokens:
            tokens[source] = []
            order.append(source)
        folded = text
        while source and folded.startswith(f"{source}:"):
            folded = folded[len(source) + 1:]
        if folded not in tokens[source]:
            tokens[source].append(folded)
    return "|".join(
        f"{source}:{'|'.join(tokens[source])}" if source else "|".join(tokens[source])
        for source in order
    )


def refold_row(row: dict) -> dict:
    """只改值：把行内非身份/非来源字段的存量脏值重折成每源一段。"""
    result = dict(row)
    for field, value in row.items():
        if field == "数据来源" or field in IDENTITY_FIELDS:
            continue
        if not isinstance(value, str) or missing_value(value):
            continue
        folded = refold_source_segments(value)
        if folded != value:
            result[field] = folded
    return result


def enrich_baseline_row(
    baseline: dict, candidate: dict, *, keep_existing_values: bool = False
) -> tuple[dict, bool]:
    enriched = dict(baseline) if keep_existing_values else refold_row(baseline)
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
        existing = enriched.get(field)
        if field == "纯电续航(km)" and re.fullmatch(r"(?:0|999)(?:\.0+)?", str(existing).strip()):
            normalized = annotate_ev_range(dict(baseline)).get(field)
            observed = annotate_ev_range(dict(candidate)).get(field)
            # A retained legacy sentinel is replaceable only when the old row
            # does not establish a real zero and a source supplies a distance.
            if missing_value(normalized) and any(
                (match := re.fullmatch(r"(?:(?:CLTC|WLTC|NEDC|WLTP|EPA|工信部)\s*[:：]\s*)?(\d+(?:\.\d+)?)\s*(?:km)?", part.strip(), flags=re.I))
                and float(match[1]) not in (0, 999)
                for part in re.split(r"[|｜/／]", str(observed or ""))
            ):
                enriched[field] = observed
                changed = True
            continue
        if missing_value(existing) and not missing_value(value):
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

    preserved = [refold_row(row) for row in preserved]

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


def autohome_trim_id(row: dict) -> str:
    sources = set(atomic_source_names(row.get("数据来源")))
    if "汽车之家" not in sources:
        return ""
    native = str(row.get("车款ID_汽车之家") or "").strip()
    if sources == {"汽车之家"}:
        primary = str(row.get("车款ID") or "").strip()
        if native and primary and native != primary:
            return ""
        native = native or primary
    return native if native.isascii() and native.isdecimal() and not native.startswith("0") else ""


def city_road_status_refines(legacy: object, fresh: object) -> bool:
    if not isinstance(legacy, str) or not isinstance(fresh, str):
        return False
    old_parts = [part.strip() for part in legacy.replace("／", "/").split("/")]
    new_parts = [part.strip() for part in fresh.replace("／", "/").split("/")]
    if len(old_parts) != len(new_parts):
        return False
    marked = False
    for old, new in zip(old_parts, new_parts):
        if old == new:
            continue
        if old not in {"城市路段", "城区路段", "高速路段"} or new not in {"●" + old, "○" + old, "不支持" + old}:
            return False
        marked = True
    return marked


def refine_published_autohome_evidence(
    output: list[dict], baseline_rows: list[dict], candidate_rows: list[dict],
    verified_legacy_ids: dict[int, str] | None = None,
) -> tuple[int, int]:
    """Refresh road and sales evidence from a uniquely identified Autohome trim."""
    verified_legacy_ids = verified_legacy_ids or {}
    baseline_ids = [verified_legacy_ids.get(i) or autohome_trim_id(row) for i, row in enumerate(baseline_rows)]
    counts = Counter(baseline_ids)
    incoming: dict[str, list[dict]] = {}
    for row in candidate_rows:
        native = autohome_trim_id(row)
        if native:
            incoming.setdefault(native, []).append(row)

    road_refined = sale_refined = 0
    road_field = "辅助驾驶路段"
    sale_field = "上市状态_汽车之家"
    for index, (base, native) in enumerate(zip(baseline_rows, baseline_ids)):
        matches = incoming.get(native, [])
        if not native or counts[native] != 1 or len(matches) != 1:
            continue
        fresh = matches[0]
        if set(atomic_source_names(fresh.get("数据来源"))) != {"汽车之家"}:
            continue
        refine_road = city_road_status_refines(base.get(road_field), fresh.get(road_field))
        base_series = str(base.get("车系ID") or "").strip()
        refine_sale = (
            base.get(sale_field) == "在售" and fresh.get(sale_field) == "停产在售"
            and autohome_trim_id(base) == native and base_series.isdecimal()
            and base_series == str(fresh.get("车系ID") or "").strip()
            and bool(base.get("品牌")) and base["品牌"] == fresh.get("品牌")
        )
        if not refine_road and not refine_sale:
            continue
        if any(str(base.get(key) or "").strip() != str(fresh.get(key) or "").strip()
               for key in ("车系", "车型名称")) or row_year(base) != row_year(fresh):
            continue
        price = _price_norm(base.get("官方指导价"))
        fresh_price = _price_norm(fresh.get("官方指导价"))
        if missing_value(price) or missing_value(fresh_price):
            continue
        if price != fresh_price:
            refine_sale = False
            if not refine_road:
                continue
            # A source can revise the price of the same trim. Require its
            # published native ID, series and matching configuration before
            # taking the city marker alone from the newer observation.
            fields = (
                "品牌", "车系ID", "能源类型", "纯电续航(CLTC)", "轴距(mm)",
                "座位数(个)", "电动机总功率(kW)", "辅助驾驶系统",
            )
            if (autohome_trim_id(base) != native
                    or any(missing_value(base.get(key)) or base[key] != fresh.get(key)
                           for key in fields)):
                continue
        if model_variant_conflict_reason(base, fresh):
            continue
        updated = dict(output[index])
        if refine_road:
            updated[road_field] = fresh[road_field]
            road_refined += 1
        if refine_sale:
            updated[sale_field] = fresh[sale_field]
            if updated.get("上市状态") == "在售":
                # Force callers to read the refreshed per-source evidence.
                del updated["上市状态"]
            sale_refined += 1
        output[index] = updated
    return road_refined, sale_refined


def preserve_partial_rows(
    baseline_rows: list[dict], candidate_rows: list[dict]
) -> tuple[list[dict], dict[str, int]]:
    """Supplement a verified baseline from a partial snapshot; absence is not retirement."""
    if not baseline_rows or not candidate_rows:
        raise ValueError("partial publication needs a nonempty baseline and observations")
    # Reuse the published spelling for exact native matches that differ only
    # in spacing after a period, so enrichment preserves the published key.
    native_baseline: dict[str, list[dict]] = {}
    legacy_p7: dict[str, list[tuple[int, dict]]] = {}
    for index, row in enumerate(baseline_rows):
        native = str(row.get("车款ID") or "").strip()
        if native:
            legacy_p7.setdefault(native, []).append((index, row))
    verified_legacy_ids = {}
    for base in baseline_rows:
        native = autohome_trim_id(base)
        if native:
            native_baseline.setdefault(native, []).append(base)
    native_counts = Counter(autohome_trim_id(row) for row in candidate_rows)
    normalized = []
    for fresh in candidate_rows:
        native = autohome_trim_id(fresh)
        matches = native_baseline.get(native, [])
        if len(matches) == 1 and native_counts[native] == 1 and set(atomic_source_names(fresh.get("数据来源"))) == {"汽车之家"}:
            base = matches[0]
            fields = ("车系", "车型名称")
            old = [str(base.get(key) or "").strip() for key in fields]
            new = [str(fresh.get(key) or "").strip() for key in fields]
            series_id = str(base.get("车系ID") or "").strip()
            if (old != new and all(old) and all(new)
                    and [re.sub(r"\.\s+", ".", name) for name in old] ==
                        [re.sub(r"\.\s+", ".", name) for name in new]
                    and series_id and series_id == str(fresh.get("车系ID") or "").strip()
                    and row_year(base) == row_year(fresh)
                    and _price_norm(base.get("官方指导价"))
                    and _price_norm(base.get("官方指导价")) == _price_norm(fresh.get("官方指导价"))
                    and not model_variant_conflict_reason(base, fresh)):
                fresh = {**fresh, **dict(zip(fields, old))}
        # Autohome moved the new-generation P7 trims from the shared legacy
        # series key to its own series. Match the original trim and keep its key.
        legacy = legacy_p7.get(native, [])
        if len(legacy) == 1 and native_counts[native] == 1 and not fresh.get("懂车帝车型ID"):
            index, base = legacy[0]
            fresh_price = _price_norm(fresh.get("官方指导价"))
            if (str(fresh.get("车系ID")) == "5213" and str(base.get("车系ID")) == "3352"
                    and set(atomic_source_names(fresh.get("数据来源"))) == {"汽车之家"}
                    and set(atomic_source_names(base.get("数据来源"))) == {"汽车之家", "懂车帝"}
                    and all(base.get(k) == fresh.get(k) for k in ("品牌", "车系", "车型名称"))
                    and base.get("品牌") == "小鹏汽车" and base.get("车系") == "小鹏P7"
                    and str(base.get("懂车帝车型ID") or "").isdigit()
                    and str(base.get("懂车帝车型ID")) != native
                    and not base.get("车款ID_易车") and not base.get("易车车型ID")
                    and str(base.get("车款ID_汽车之家") or native) == native
                    and fresh_price and fresh_price == _price_norm(base.get("官方指导价"))
                    and row_year(base) == row_year(fresh)
                    and not model_variant_conflict_reason(base, fresh)):
                verified_legacy_ids[index] = native
                fresh = {**fresh, "车系ID": base["车系ID"]}
        normalized.append(fresh)
    candidate_rows = normalized
    baseline_keys = [identity_key(row) for row in baseline_rows]
    counts = Counter(baseline_keys)
    indexes = {key: idx for idx, key in enumerate(baseline_keys)}
    candidate_keys = unique_keys("candidate", candidate_rows)
    output = list(baseline_rows)
    stats = {
        "baseline_rows": len(output),
        "candidate_input_rows": len(candidate_rows),
        "candidate_added": 0,
        "candidate_enriched": 0,
        "ambiguous_baseline_matches": 0,
    }
    for key, row in zip(candidate_keys, candidate_rows):
        if counts[key] > 1:
            # A publication key can legitimately cover two distinct observations.
            stats["ambiguous_baseline_matches"] += 1
        elif key in indexes:
            idx = indexes[key]
            base = output[idx]
            if any(not missing_value(base.get(field)) and not missing_value(row.get(field))
                   and str(base[field]) != str(row[field])
                   for field in ("车款ID", "懂车帝车型ID", "易车车型ID")):
                stats["ambiguous_baseline_matches"] += 1
                continue
            enriched, changed = enrich_baseline_row(base, row, keep_existing_values=True)
            if identity_key(enriched) != key:
                raise ValueError("partial enrichment changed a published identity")
            output[idx] = enriched
            stats["candidate_enriched"] += int(changed)
        else:
            output.append(row)
            stats["candidate_added"] += 1
    road_refined, sale_refined = refine_published_autohome_evidence(
        output, baseline_rows, candidate_rows, verified_legacy_ids
    )
    if road_refined:
        stats["candidate_city_status_refined"] = road_refined
    if sale_refined:
        stats["candidate_autohome_sale_status_refined"] = sale_refined
    stats["candidate_output_rows"] = len(output)
    return output, stats


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
        filtered_rows = narrow_pages_rows(filtered_rows)
        header = collect_fields(rows)
        write_json(staged[merged_json], rows)
        write_csv(staged[merged_csv], rows, header)
        write_json(staged[filtered_json], filtered_rows)
        write_csv(staged[filtered_csv], filtered_rows, collect_fields(filtered_rows))
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
    parser.add_argument("--partial-input", action="store_true",
                        help="preserve all published observations; add facts from partial input")
    args = parser.parse_args()

    if args.partial_input:
        baseline = load_json_rows(args.baseline)
        candidates, _ = partition_publishable_rows(load_json_rows(args.merged_json))
        rows, stats = preserve_partial_rows(baseline, candidates)
        write_publish_assets(rows, args.merged_json, args.merged_csv, args.filtered_json, args.filtered_csv)
        print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
        return 0

    baseline_rows = [row for row in load_json_rows(args.baseline) if keep_pages_year(row)]
    seen_b = set()
    dedup_b = []
    for row in baseline_rows:
        try:
            k = identity_key(row)
        except ValueError:
            dedup_b.append(row)
            continue
        if k in seen_b:
            continue
        seen_b.add(k)
        dedup_b.append(row)
    if len(dedup_b) != len(baseline_rows):
        print(f"baseline identity 去重: {len(baseline_rows)} -> {len(dedup_b)} (旧管线重复行)")
    baseline_rows = dedup_b
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
    rows = [annotate_ev_range(row) for row in rows]
    rows = [clean_brand_field(row) for row in rows]
    rows = [row for row in rows if not is_excluded_brand(row)]
    write_publish_assets(rows, args.merged_json, args.merged_csv, args.filtered_json, args.filtered_csv)
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
