#!/usr/bin/env python3
"""Fail closed when the transformed Pages payload regresses published identities or sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable

from merge_data import atomic_source_names, partition_publishable_rows, series_year_key
from prepare_debug_merge_inputs import filter_valid_identity_rows, identity_key, load_json_rows
from prepare_pages_payload import (
    VISIBLE_COMPONENT_EVIDENCE,
    VISIBLE_COMPONENT_ID,
    annotate_safe_visible_components,
    source_provenance_contradictions,
    visible_card_stats,
)

SCHEMA_VERSION = "pages-payload-audit-v2"
_SOURCE_SPLIT = re.compile(r"[|,，;/；、+]+")


def _sources(value: object) -> set[str]:
    sources: set[str] = set()
    for part in _SOURCE_SPLIT.split(str(value or "")):
        part = part.strip()
        if not part:
            continue
        known = atomic_source_names([part])
        sources.update(known or [part])
    return sources


def _key_hash(key: object) -> str:
    raw = json.dumps(key, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _index(rows: Iterable[dict]) -> dict[object, set[str]]:
    indexed: dict[object, set[str]] = {}
    for row in rows:
        key = identity_key(row)
        indexed.setdefault(key, set()).update(_sources(row.get("数据来源")))
    return indexed


def audit_payload(baseline_rows: list[dict], candidate_rows: list[dict], *, head_sha: str) -> dict:
    baseline_rows, baseline_publish_stats = partition_publishable_rows(baseline_rows)
    candidate_rows, candidate_publish_stats = partition_publishable_rows(candidate_rows)
    baseline_rows, invalid_baseline = filter_valid_identity_rows(baseline_rows)
    candidate_rows, invalid_candidate = filter_valid_identity_rows(candidate_rows)
    baseline = _index(baseline_rows)
    candidate = _index(candidate_rows)
    baseline_buckets = {identity_key(row): series_year_key(row) for row in baseline_rows}
    candidate_bucket_sources: dict[str, set[str]] = {}
    for row in candidate_rows:
        bucket = series_year_key(row)
        if bucket:
            candidate_bucket_sources.setdefault(bucket, set()).update(_sources(row.get("数据来源")))
    violations: list[dict] = []

    def add(code: str, keys: Iterable[object]) -> None:
        hashes = sorted(_key_hash(key) for key in keys)
        if hashes:
            violations.append({"code": code, "count": len(hashes), "identity_hashes": hashes[:20]})

    if not baseline:
        violations.append({"code": "empty_baseline", "count": 1, "identity_hashes": []})
    if not candidate:
        violations.append({"code": "empty_candidate", "count": 1, "identity_hashes": []})
    if invalid_baseline:
        violations.append({"code": "invalid_baseline_identity", "count": len(invalid_baseline), "identity_hashes": []})
    if invalid_candidate:
        violations.append({"code": "invalid_candidate_identity", "count": len(invalid_candidate), "identity_hashes": []})

    missing = set(baseline) - set(candidate)
    add("missing_identity", missing)
    source_regressions = []
    intentional_source_retirements = 0
    for key in set(baseline) & set(candidate):
        retired_sources = baseline[key] - candidate[key]
        if not retired_sources:
            continue
        bucket_sources = candidate_bucket_sources.get(baseline_buckets.get(key, ""), set())
        if retired_sources.issubset(bucket_sources):
            intentional_source_retirements += 1
        else:
            source_regressions.append(key)
    add("source_regression", source_regressions)

    expected_candidate_rows, component_stats = annotate_safe_visible_components(candidate_rows)
    missing_annotations = []
    unsafe_annotations = []
    evidence_mismatches = []
    for index, (actual, expected) in enumerate(zip(candidate_rows, expected_candidate_rows)):
        actual_id = str(actual.get(VISIBLE_COMPONENT_ID, "") or "")
        expected_id = str(expected.get(VISIBLE_COMPONENT_ID, "") or "")
        if expected_id and not actual_id:
            missing_annotations.append(("row", index))
        elif actual_id and actual_id != expected_id:
            unsafe_annotations.append(("row", index))
        if actual_id == expected_id and actual_id:
            if str(actual.get(VISIBLE_COMPONENT_EVIDENCE, "") or "") != str(
                expected.get(VISIBLE_COMPONENT_EVIDENCE, "") or ""
            ):
                evidence_mismatches.append(("row", index))
    add("missing_visible_component_annotation", missing_annotations)
    add("unsafe_visible_component_annotation", unsafe_annotations)
    add("visible_component_evidence_mismatch", evidence_mismatches)
    provenance_rows = []
    for actual, expected in zip(candidate_rows, expected_candidate_rows):
        normalized = dict(actual)
        expected_id = str(expected.get(VISIBLE_COMPONENT_ID, "") or "")
        if expected_id:
            normalized[VISIBLE_COMPONENT_ID] = expected_id
        else:
            normalized.pop(VISIBLE_COMPONENT_ID, None)
        provenance_rows.append(normalized)
    provenance_contradictions = source_provenance_contradictions(provenance_rows)
    add("field_source_contradiction", provenance_contradictions)
    violations.sort(key=lambda item: item["code"])

    baseline_visible = visible_card_stats(baseline_rows)
    candidate_visible = visible_card_stats(candidate_rows)

    fingerprint_input = {
        "schema_version": SCHEMA_VERSION,
        "violation_classes": [
            {"code": item["code"], "identity_hashes": item["identity_hashes"]}
            for item in violations
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_input, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "audit_scope": "regression-only",
        "status": "blocked" if violations else "pass",
        "head_sha": head_sha,
        "fingerprint": fingerprint,
        "stats": {
            "baseline_rows": len(baseline_rows),
            "candidate_rows": len(candidate_rows),
            "baseline_identities": len(baseline),
            "candidate_identities": len(candidate),
            "added_identities": len(set(candidate) - set(baseline)),
            "intentional_source_retirements": intentional_source_retirements,
            "baseline_invalid_brand_dropped": baseline_publish_stats["invalid_brand"],
            "baseline_invalid_model_name_dropped": baseline_publish_stats["invalid_model_name"],
            "candidate_invalid_brand_dropped": candidate_publish_stats["invalid_brand"],
            "candidate_invalid_model_name_dropped": candidate_publish_stats["invalid_model_name"],
            "baseline_visible_rows": baseline_visible["visible_rows"],
            "baseline_visible_single": baseline_visible["visible_single"],
            "baseline_visible_multi": baseline_visible["visible_multi"],
            "candidate_visible_rows": candidate_visible["visible_rows"],
            "candidate_visible_single": candidate_visible["visible_single"],
            "candidate_visible_multi": candidate_visible["visible_multi"],
            "candidate_visible_rate": candidate_visible["visible_rate"],
            "visible_multi_delta": candidate_visible["visible_multi"] - baseline_visible["visible_multi"],
            "field_source_contradictions": len(provenance_contradictions),
            **component_stats,
        },
        "violations": violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args()
    try:
        report = audit_payload(load_json_rows(args.baseline), load_json_rows(args.candidate), head_sha=args.head_sha)
        report["baseline_sha256"] = _sha256(args.baseline)
        report["candidate_sha256"] = _sha256(args.candidate)
    except Exception as exc:
        report = {
            "schema_version": SCHEMA_VERSION,
            "audit_scope": "regression-only",
            "status": "blocked",
            "head_sha": args.head_sha,
            "fingerprint": hashlib.sha256(f"{SCHEMA_VERSION}:audit_error".encode()).hexdigest(),
            "stats": {},
            "violations": [{"code": "audit_error", "count": 1, "identity_hashes": []}],
            "error_type": type(exc).__name__,
        }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": report["status"], "fingerprint": report["fingerprint"], "report": str(args.report)}, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
