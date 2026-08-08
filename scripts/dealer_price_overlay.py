#!/usr/bin/env python3
"""Shared incremental dealer-price overlay (懂车帝 garage data)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_dealer_index() -> dict[tuple[str, str, str], str]:
    """Load data/dealer_prices.json into {(车系ID, 年款, 归一名称): dealer_price}.

    Returns an empty dict when the file is missing or malformed.
    """
    dp_path = Path(__file__).resolve().parents[1] / "data" / "dealer_prices.json"
    if not dp_path.exists():
        return {}
    try:
        data = json.loads(dp_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    by_series = data.get("series") or {}
    index: dict[tuple[str, str, str], str] = {}
    for sid, cars in by_series.items():
        for car in cars:
            if not car.get("dealer_price"):
                continue
            key = (str(sid), _norm_year(str(car.get("year", ""))),
                   _norm_name(str(car.get("name", ""))))
            index.setdefault(key, str(car["dealer_price"]))
    return index


def _norm_year(year: str) -> str:
    m = re.search(r"20\d{2}|\d{4}", year)
    return m.group(0) if m else year.strip()


def _norm_name(name: str) -> str:
    name = re.sub(r"^\d{2,4}款\s*", "", name.strip())
    return re.sub(r"\s+", "", name)


def overlay_dealer_prices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Overlay dealer prices onto rows; only rows lacking a real price
    (empty / - / 暂无报价 / None) are updated."""
    index = load_dealer_index()
    if not index:
        return rows
    updated = 0
    for row in rows:
        sid = str(row.get("车系ID") or "").strip()
        year = _norm_year(str(row.get("年款") or "").strip())
        name = _norm_name(str(row.get("车型名称") or ""))
        cur = str(row.get("经销商参考价") or "").strip()
        if cur and cur not in ("", "-", "暂无报价", "None"):
            continue
        price = index.get((sid, year, name))
        if price:
            row["经销商参考价"] = price
            updated += 1
    if updated:
        print(f"[dealer overlay] updated {updated} rows")
    return rows
