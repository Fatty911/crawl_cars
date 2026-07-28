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

from merge_data import partition_publishable_rows
from prepare_debug_merge_inputs import filter_valid_identity_rows, identity_key, load_json_rows

SCHEMA_VERSION = "pages-payload-audit-v1"
_SOURCE_SPLIT = re.compile(r"[|,，;/；、+]+")


def _sources(value: object) -> set[str]:
    return {part.strip() for part in _SOURCE_SPLIT.split(str(value or "")) if part.strip()}


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
    source_regressions = [key for key in set(baseline) & set(candidate) if not baseline[key].issubset(candidate[key])]
    add("source_regression", source_regressions)
    violations.sort(key=lambda item: item["code"])

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
            "baseline_invalid_brand_dropped": baseline_publish_stats["invalid_brand"],
            "baseline_invalid_model_name_dropped": baseline_publish_stats["invalid_model_name"],
            "candidate_invalid_brand_dropped": candidate_publish_stats["invalid_brand"],
            "candidate_invalid_model_name_dropped": candidate_publish_stats["invalid_model_name"],
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
