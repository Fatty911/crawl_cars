#!/usr/bin/env python3
"""Incremental dealer-price crawler for 懂车帝 garage API.

Fetches per-series garage payloads (lightweight: one request per series,
no full detail crawl) and extracts per-car dealer_price / price. Outputs
data/dealer_prices.json keyed by series id, so merge_data can overlay the
dealer reference price column without a full re-crawl.

Exit codes: 0 = ok (may be partial), 1 = hard failure (no data).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
GARAGE_URL = "https://www.dongchedi.com/motor/garage/get_cars_by_series_id/{series_id}/"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://www.dongchedi.com/"})
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})
    return s


def fetch_garage(session: requests.Session, series_id: str) -> dict[str, Any] | None:
    for attempt in range(3):
        try:
            r = session.get(GARAGE_URL.format(series_id=series_id), timeout=25)
            if r.status_code != 200:
                time.sleep(2 * (attempt + 1))
                continue
            payload = r.json()
            if payload.get("status") not in (0, "0"):
                return None
            return payload
        except (requests.RequestException, ValueError):
            time.sleep(2 * (attempt + 1))
    return None


def extract_cars(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """garage payload -> list of {name, id, dealer_price, price, year}."""
    cars: list[dict[str, Any]] = []
    data = payload.get("data") or {}
    for year_group in data.get("list") or []:
        for inner in year_group.get("data") or []:
            for car in inner.get("data") or []:
                info = car.get("info") or {}
                name = info.get("name")
                if not name:
                    continue
                cars.append({
                    "name": str(name),
                    "id": str(info.get("id", "")),
                    "dealer_price": info.get("dealer_price") or "",
                    "price": info.get("price") or "",
                    "year": str(info.get("year", "")),
                })
    return cars


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--series-input", required=True, type=Path,
                        help="latest.json (or any rows file) to derive series ids from")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "dealer_prices.json")
    parser.add_argument("--min-rows", type=int, default=2000,
                        help="abort if fewer series fetched than this (guards against mass blocking)")
    parser.add_argument("--delay", type=float, default=0.4, help="seconds between series requests")
    args = parser.parse_args()

    rows = json.loads(args.series_input.read_text(encoding="utf-8"))
    if isinstance(rows, dict):
        rows = rows.get("cars") or rows.get("data") or rows.get("rows") or []
    series_ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        sid = str(row.get("车系ID") or "").strip()
        if sid and sid not in seen:
            seen.add(sid)
            series_ids.append(sid)
    if not series_ids:
        print("no series ids found", file=sys.stderr)
        return 1

    # 增量合并：保留已有数据中本轮未成功抓取的车系（部分失败不丢旧值）
    previous: dict[str, Any] = {"series": {}}
    if args.output.exists():
        try:
            previous = json.loads(args.output.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {"series": {}}

    session = _session()
    result: dict[str, Any] = {"updated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                              "series": dict(previous.get("series") or {})}
    fetched = 0
    failures = 0
    for sid in series_ids:
        payload = fetch_garage(session, sid)
        if payload is None:
            failures += 1
            continue
        cars = extract_cars(payload)
        if cars:
            result["series"][sid] = cars
        fetched += 1
        if fetched % 200 == 0:
            print(f"progress: {fetched}/{len(series_ids)} series, {failures} failures", file=sys.stderr)
        time.sleep(args.delay)

    print(f"done: {fetched}/{len(series_ids)} series, {failures} failures, "
          f"{sum(len(v) for v in result['series'].values())} cars", file=sys.stderr)
    if fetched < args.min_rows:
        print(f"aborting: only {fetched} series fetched (< {args.min_rows})", file=sys.stderr)
        return 1
    if fetched and failures / (fetched + failures) > 0.10:
        print(f"aborting: failure rate {failures}/{fetched + failures} > 10% (likely mass blocking)", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({fetched} series)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
