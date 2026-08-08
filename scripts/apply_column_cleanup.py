#!/usr/bin/env python3
"""Deterministic column-name convergence: pull the live Pages payload,
diagnose value-leak columns, and write hidden_columns + column aliases so
the published column set shrinks every round until clean.

- value_only_header with diagnosis confidence >= 0.9 -> hidden_columns.json
- attribute_value_header whose suggested attribute is a real candidate
  attribute -> column_header_aliases.json (value-suffix injection)
Runs without an LLM; every entry passes the same deterministic checks the
repair chain uses.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from column_name_diagnostics import diagnose_columns  # noqa: E402

HIDDEN_PATH = ROOT / "config" / "hidden_columns.json"
ALIASES_PATH = ROOT / "config" / "column_header_aliases.json"
HIDE_CONFIDENCE = 0.9
# Columns consumed by prepare-time validation must never be hidden even
# though they look like internal columns.
KEEP_FOR_VALIDATION = {"易车上市状态"}
ALIAS_CONFIDENCE = 0.9
MAX_NEW_HIDDEN = 200
MAX_NEW_ALIASES = 100


def _fold_compatible(rows: list[dict], col_a: str, col_b: str) -> bool:
    """Both columns may be folded only if no row has conflicting non-empty
    values (either equal or at least one side missing)."""
    for row in rows:
        va = row.get(col_a)
        vb = row.get(col_b)
        if va is None or str(va).strip() in ("", "-"):
            continue
        if vb is None or str(vb).strip() in ("", "-"):
            continue
        if str(va).strip() != str(vb).strip():
            return False
    return True


def fold_duplicate_columns(rows: list[dict], existing_alias_cols: set[str], existing_hidden_set: set[str], seen_alias: set[str], seen_hidden: set[str], new_aliases: list[dict], max_new: int) -> list[dict]:
    """Fold `Name(SUFFIX)` columns into their bare `Name` column as a
    value-compatible alias (e.g. 上坡辅助(HAC) -> 上坡辅助)."""
    import re
    cols = sorted({k for row in rows for k in row.keys()})
    base_groups: dict[str, list[str]] = {}
    for c in cols:
        m = re.match(r"^(.+?)\([^()]+\)$", c)
        if m:
            base_groups.setdefault(m.group(1), []).append(c)
    for base, variants in sorted(base_groups.items()):
        if base not in cols:
            continue
        if base in existing_hidden_set or base in seen_hidden:
            continue
        for v in sorted(variants):
            if len(new_aliases) >= max_new:
                return new_aliases
            if v in existing_alias_cols or v in seen_alias or v in existing_hidden_set or v in seen_hidden:
                continue
            if _fold_compatible(rows, v, base):
                new_aliases.append({
                    "column": v,
                    "canonical": base,
                    "confidence": 0.95,
                    "evidence": "deterministic duplicate-column fold (value-compatible)",
                })
                seen_alias.add(v)
    return new_aliases


def load_rows(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("cars") or data.get("data") or []
    return [row for row in data if isinstance(row, dict)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path, help="live Pages latest.json")
    parser.add_argument("--report", type=Path, help="optional diagnostic report output")
    args = parser.parse_args()

    rows = load_rows(args.input)
    # Large limit: per-kind quota is limit // kind_count, and the default
    # 120 would cap value_only/attribute_value lists at ~15 entries each.
    diagnosis = diagnose_columns(rows, limit=4000)
    suspects = diagnosis.get("suspects") or []
    candidate_attributes = set(diagnosis.get("candidate_attributes") or [])

    existing_hidden = json.loads(HIDDEN_PATH.read_text(encoding="utf-8")) if HIDDEN_PATH.exists() else {"version": 1, "hidden": []}
    existing_hidden_set = set(str(x) for x in existing_hidden.get("hidden", []) if isinstance(x, str))
    existing_aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8")) if ALIASES_PATH.exists() else {"version": 1, "aliases": []}
    existing_alias_cols = {str(a.get("column")) for a in existing_aliases.get("aliases", []) if isinstance(a, dict)}

    new_hidden: list[str] = []
    new_aliases: list[dict] = []
    seen_hidden: set[str] = set()
    seen_alias: set[str] = set()

    for item in suspects:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        confidence = float(item.get("confidence") or 0.0)
        if kind == "value_only_header" and confidence >= HIDE_CONFIDENCE:
            for column in item.get("columns") or [item.get("column")]:
                if (
                    isinstance(column, str)
                    and column not in existing_hidden_set
                    and column not in seen_hidden
                    and column not in candidate_attributes
                    and column not in KEEP_FOR_VALIDATION
                    and len(new_hidden) < MAX_NEW_HIDDEN
                ):
                    new_hidden.append(column)
                    seen_hidden.add(column)
        elif kind == "attribute_value_header" and confidence >= ALIAS_CONFIDENCE:
            column = item.get("column")
            suggested = item.get("suggested_attribute")
            value_suffix = item.get("value_suffix")
            if (
                isinstance(column, str)
                and isinstance(suggested, str)
                and suggested in candidate_attributes
                and column not in existing_alias_cols
                and column not in seen_alias
                and column not in seen_hidden
                and column not in existing_hidden_set
                and len(new_aliases) < MAX_NEW_ALIASES
            ):
                alias = {
                    "column": column,
                    "canonical": suggested,
                    "confidence": round(confidence, 4),
                    "evidence": "deterministic column-cleanup loop",
                }
                if isinstance(value_suffix, str) and value_suffix and "|" not in value_suffix and "\n" not in value_suffix:
                    alias["value"] = value_suffix
                new_aliases.append(alias)
                seen_alias.add(column)

    # 确定性重复列折叠（值兼容）：X(Y) -> X
    new_aliases = fold_duplicate_columns(
        rows, existing_alias_cols, existing_hidden_set,
        seen_alias, seen_hidden, new_aliases, MAX_NEW_ALIASES,
    )

    changed = False
    if new_hidden:
        existing_hidden.setdefault("hidden", [])
        # Defensive: never let a validation-consumed column stay hidden,
        # even if an earlier unguarded round added it.
        existing_hidden["hidden"] = [
            c for c in existing_hidden["hidden"] if c not in KEEP_FOR_VALIDATION
        ]
        existing_hidden["hidden"] = sorted(set(existing_hidden["hidden"]) | set(new_hidden))
        HIDDEN_PATH.write_text(json.dumps(existing_hidden, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed = True
    if new_aliases:
        by_column = {str(a.get("column")): a for a in existing_aliases.get("aliases", []) if isinstance(a, dict)}
        for alias in new_aliases:
            by_column[alias["column"]] = alias
        existing_aliases["aliases"] = [by_column[k] for k in sorted(by_column)]
        ALIASES_PATH.write_text(json.dumps(existing_aliases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed = True

    summary = {
        "rows": len(rows),
        "columns_total": len({k for row in rows for k in row.keys()}),
        "suspects_total": len(suspects),
        "new_hidden": len(new_hidden),
        "new_aliases": len(new_aliases),
        "folded_duplicates": sum(1 for a in new_aliases if "duplicate-column fold" in str(a.get("evidence"))),
        "hidden_total": len(existing_hidden["hidden"]),
        "aliases_total": len(existing_aliases["aliases"]),
        "changed": changed,
        "sample_hidden": new_hidden[:8],
        "sample_aliases": [a["column"] + "->" + a["canonical"] for a in new_aliases[:8]],
    }
    if args.report:
        args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
