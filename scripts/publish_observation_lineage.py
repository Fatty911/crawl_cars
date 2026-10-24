"""Observe real accepted merge groups without inventing identities or changing rows."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json

import merge_data


def dedupe_with_origins(rows: list[dict]) -> tuple[list[dict], list[frozenset[int]]]:
    """Return ordinary merger output plus a complete partition of original indices.

    The observer receives the actual accepted group and its actual keeper from
    the production merger. No debug fields are inserted into data. References
    are retained until completion so Python object-id reuse cannot invent links.
    Input facts remain untouched, including nested values.
    """
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("lineage requires a list of JSON object observations")
    copied = [deepcopy(row) for row in rows]
    registry = {id(row): (row, frozenset([index])) for index, row in enumerate(copied)}

    def observed(group, keeper):
        if not group or not isinstance(keeper, dict):
            raise ValueError("merger supplied an invalid accepted group")
        origins = set()
        for row in group:
            saved = registry.get(id(row))
            if saved is None or saved[0] is not row:
                raise ValueError("accepted group has an unobserved contributor")
            origins.update(saved[1])
        registry[id(keeper)] = (keeper, frozenset(origins))

    merged = merge_data.dedupe_merged_rows(copied, _observe_merge=observed)
    if not isinstance(merged, list):
        raise ValueError("merger did not return a row list")
    origins = []
    for row in merged:
        saved = registry.get(id(row))
        if saved is None or saved[0] is not row:
            raise ValueError("surviving row has no actual merge lineage")
        origins.append(saved[1])
    counts = Counter(index for group in origins for index in group)
    if set(counts) != set(range(len(rows))) or any(count != 1 for count in counts.values()):
        raise ValueError("merge lineage is not an exact partition of original observations")
    return merged, origins


DERIVED_COMPONENT_FIELDS = frozenset({"跨源归并ID", "跨源归并证据"})


@dataclass(frozen=True)
class FilteredCoverage:
    allowed_identity_changes: frozenset
    fact_rows_equal: bool
    report: dict


def _fact_bytes(row):
    facts = {key: value for key, value in row.items() if key not in DERIVED_COMPONENT_FIELDS}
    return json.dumps(facts, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def filtered_fact_identity(row):
    """Exact display identity + SKU + source + normalized price; never fuzzy."""
    from prepare_debug_merge_inputs import identity_key
    try:
        identity = identity_key(row)
    except (ValueError, KeyError, TypeError):
        return None
    return (identity, str(row.get("车款ID", "") or "").strip(),
            str(row.get("数据来源", "") or "").strip(),
            str(merge_data._price_norm(row.get("官方指导价")) or ""))


def _missing_retained_configured_fields(baseline_rows, candidate_rows):
    """Required narrow-view facts cannot disappear behind canonical replay."""
    required = set(merge_data.resolve_pages_columns(baseline_rows)) - DERIVED_COMPONENT_FIELDS
    actual = {}
    for index, row in enumerate(candidate_rows):
        identity = filtered_fact_identity(row)
        if identity is not None:
            actual.setdefault(identity, []).append((index, row))
    gaps = []
    for index, row in enumerate(baseline_rows):
        if not merge_data.keep_pages_year(row):
            continue
        identity = filtered_fact_identity(row)
        for target_index, target in actual.get(identity, []):
            missing = required.intersection(row) - set(target)
            if missing:
                gaps.append((index, target_index, sorted(missing)))
    return gaps


def filtered_observation_coverage(baseline_rows, wide_rows, candidate_rows, *, identity_evidence=None):
    """Rebuild expected filtered facts from immutable inputs, never from candidate.

    Exact typed row multisets preserve multiplicity and every fact field. The
    two recomputed component annotations are independently hard-checked by the
    full payload auditor. A display-key change additionally needs exact source
    observations linked through actual accepted merge groups, with every target
    still present. No tolerance or fuzzy alias is granted.
    """
    from prepare_debug_merge_inputs import identity_key
    from prepare_pages_payload import prepare_rows_with_stats
    from reconcile_source_identities import reconcile
    from remerge_published_data import build_filtered, sku_ids, union_filtered

    for rows in (baseline_rows, wide_rows, candidate_rows):
        if not isinstance(rows, list) or not rows or any(not isinstance(r, dict) for r in rows):
            raise ValueError("filtered coverage requires nonempty object-row inputs")

    # Normalize only the explicitly reviewed three raw names. Keep the original
    # lists immutable, and use those same checked observations for index links
    # and exact projections when old/new cache names coexist across inputs.
    corrected_wide = reconcile(wide_rows, identity_evidence)[0] if identity_evidence is not None else wide_rows
    corrected_baseline = reconcile(baseline_rows, identity_evidence)[0] if identity_evidence is not None else baseline_rows

    def checked_merge(rows):
        merged, origins = dedupe_with_origins(rows)
        again = merge_data.dedupe_merged_rows(deepcopy(merged))
        if len(again) != len(merged) or sku_ids(rows) != sku_ids(merged):
            raise ValueError("observed merger changed SKU IDs or failed its existing idempotence contract")
        kept = [(r, o) for r, o in zip(merged, origins) if merge_data.keep_pages_year(r)]
        return [r for r, _ in kept], [o for _, o in kept]

    wide_merged, wide_origins = checked_merge(corrected_wide)
    inherited, inherited_origins = checked_merge(corrected_baseline)
    # Reproduce the published pipeline's raw-input union, including legitimate
    # inherited observations absent from current rebuilt scope.
    expected = union_filtered(inherited, build_filtered(wide_merged), build_filtered(deepcopy(corrected_wide)))
    # Raw evidence is checked before either real merge, never against a
    # composite keeper whose observed display name may come from another source.
    # All three inputs to this union already descend from checked raw rows.
    expected, _ = prepare_rows_with_stats(deepcopy(expected), 2022, refresh_dealer_prices=False)
    expected_counts = Counter(_fact_bytes(r) for r in expected)
    actual_counts = Counter(_fact_bytes(r) for r in candidate_rows)
    missing_facts = sum((expected_counts - actual_counts).values())
    added_facts = sum((actual_counts - expected_counts).values())
    retained_field_gaps = _missing_retained_configured_fields(corrected_baseline, candidate_rows)
    facts_equal = not missing_facts and not added_facts and not retained_field_gaps

    def key(row):
        try:
            return identity_key(row)
        except (ValueError, KeyError, TypeError):
            return None

    expected_keys = {key(r) for r in expected} - {None}
    actual_keys = {key(r) for r in candidate_rows} - {None}
    originals_by_key = {}
    for keeper, origins in zip(wide_merged, wide_origins):
        target_key = key(keeper)
        for index in origins:
            source_key = key(corrected_wide[index])
            if source_key is not None:
                originals_by_key.setdefault(source_key, []).append((index, target_key))
    allowed = set()
    unproved = 0
    for old_keeper, origins in zip(inherited, inherited_origins):
        old_key = key(old_keeper)
        if old_key is None or old_key in actual_keys:
            continue
        targets = set()
        complete = True
        for index in origins:
            original = corrected_baseline[index]
            source_fields = {k: v for k, v in original.items() if k not in DERIVED_COMPONENT_FIELDS}
            source_blob = _fact_bytes(source_fields)
            matched = set()
            for wide_index, target in originals_by_key.get(key(original), []):
                observed = corrected_wide[wide_index]
                if all(field in observed for field in source_fields):
                    projection = {field: observed[field] for field in source_fields}
                    if _fact_bytes(projection) == source_blob:
                        matched.add(target)
            if not matched:
                complete = False
            targets.update(matched)
        if facts_equal and complete and targets and None not in targets and targets <= expected_keys & actual_keys:
            allowed.add(old_key)
        else:
            unproved += 1
    report = {
        "schema_version": 1,
        "basis": "original wide+filtered observations; real merge groups; exact final fact-row multiset",
        "wide_original_rows": len(wide_rows), "filtered_original_rows": len(baseline_rows),
        "expected_final_rows": len(expected), "actual_final_rows": len(candidate_rows),
        "missing_or_modified_fact_rows": missing_facts, "added_or_modified_fact_rows": added_facts,
        "fact_row_multisets_equal": not missing_facts and not added_facts,
        "missing_retained_configured_fact_fields": sum(len(fields) for _, _, fields in retained_field_gaps),
        "missing_retained_configured_fact_rows": len({index for index, _, _ in retained_field_gaps}),
        "retained_configured_fact_field_names": sorted({field for _, _, fields in retained_field_gaps for field in fields}),
        "original_merge_index_partitions_verified": True,
        "verified_display_identity_transitions": len(allowed),
        "unproved_display_identity_transitions": unproved,
        "verified_transition_hashes": sorted(hashlib.sha256(json.dumps(k, ensure_ascii=False).encode()).hexdigest()
                                             for k in allowed),
        "derived_fields_separately_required_in_full_audit": sorted(DERIVED_COMPONENT_FIELDS),
        "candidate_repaired_or_used_as_baseline": False,
    }
    return FilteredCoverage(frozenset(allowed), facts_equal, report)
