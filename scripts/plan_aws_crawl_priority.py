#!/usr/bin/env python3
"""Freeze a rank-aware AWS target list from saved source-local evidence."""

import argparse
import calendar
from collections import deque
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re

POSITIVE_ID = re.compile(r"[1-9][0-9]{0,9}")
TARGET_FIELDS = {
    "autohome": {"car_id", "series", "brand"},
    "dongchedi": {"id", "name", "brand"},
    "yiche": {"serial_id", "series", "brand"},
}
CADENCE = {"hot": 3, "new_gap": 2, "oldest": 1}


def target_identity(source, target):
    if source not in TARGET_FIELDS or not isinstance(target, dict):
        raise ValueError("unknown source or malformed target")
    fields = TARGET_FIELDS[source]
    if source == "yiche":
        fields = fields | {"url"}
    if target.keys() != fields or any(not isinstance(value, str) or not value.strip() for value in target.values()):
        raise ValueError("target fields differ from the source collector")
    series_id = target[{"autohome": "car_id", "dongchedi": "id", "yiche": "serial_id"}[source]]
    if not POSITIVE_ID.fullmatch(series_id):
        raise ValueError("invalid source-local series ID")
    if source == "yiche" and not re.fullmatch(r"https://car\.yiche\.com/[a-z0-9-]+/peizhi/", target["url"]):
        raise ValueError("invalid Yiche source URL")
    return series_id


def age(value, today):
    if value is None:
        return None
    days = (today - date.fromisoformat(value)).days
    if days < 0:
        raise ValueError("observation date is in the future")
    return days


def eligible_ranks(rankings, today, source):
    """Use each fresh list independently; a missing listing is unknown."""
    result = {}
    for kind in ("sales", "heat"):
        signal = rankings.get(kind)
        if not signal:
            continue
        observed_age = age(signal["observed_on"], today)
        if kind == "heat" and observed_age > 7:
            continue
        if kind == "sales":
            metric = signal.get("metric")
            monthly_sales = metric == "monthly_retail" or (source == "autohome" and metric == "autohome_monthly_sales")
            if not monthly_sales or observed_age > 45:
                continue
            month = date.fromisoformat(signal["period"] + "-01")
            month_end = month.replace(day=calendar.monthrange(month.year, month.month)[1])
            if month_end >= date.fromisoformat(signal["observed_on"]) or (today - month_end).days > 75:
                continue
        ranks = signal["ranks"]
        if any(not POSITIVE_ID.fullmatch(key) or type(rank) is not int or rank <= 0 for key, rank in ranks.items()):
            raise ValueError("invalid source-local rank")
        result[kind] = ranks
    return result


def plan(document, today, trim_budget):
    if type(trim_budget) is not int or not 1 <= trim_budget <= 30:
        raise ValueError("debug trim budget must be 1 to 30")
    source = document["source"]
    if source not in TARGET_FIELDS:
        raise ValueError("unknown source")
    ranked = eligible_ranks(document.get("rankings", {}), today, source)
    candidates = []
    seen = set()
    urls = set()
    for item in document["targets"]:
        target = item["target"]
        key = target_identity(source, target)
        url = target.get("url")
        cost = item["trim_cost"]
        if key in seen or (url and url in urls) or type(cost) is not int or cost <= 0:
            raise ValueError("duplicate target or invalid trim estimate")
        seen.add(key)
        if url:
            urls.add(url)
        since = age(item.get("last_success"), today)
        new_age = age(item.get("first_seen"), today)
        missing = item.get("missing_source", False)
        if type(missing) is not bool:
            raise ValueError("missing_source must be boolean")
        ranks = {kind: values[key] for kind, values in ranked.items() if key in values}
        candidates.append({
            "target": target, "id": key, "cost": cost, "days_since_success": since,
            "new": new_age is not None and new_age <= 14, "missing_source": missing, "ranks": ranks,
        })

    def oldest(row):
        days = row["days_since_success"]
        return (days is not None, -(days or 0), bool(row["ranks"]), int(row["id"]))

    def due(row, lane):
        days = row["days_since_success"]
        # The age lane must not send a recently fetched ranked car around
        # the hot lane cooldown. A verified new/gap signal can refresh sooner.
        minimum = CADENCE["hot"] if lane == "oldest" and row["ranks"] else CADENCE[lane]
        return days is None or days >= minimum

    oldest_rows = sorted(candidates, key=oldest)
    queues = {
        "hot": sorted((row for row in candidates if due(row, "hot") and min(row["ranks"].values(), default=101) <= 100),
                      key=lambda row: (min(row["ranks"].values()), *oldest(row))),
        "oldest": [row for row in oldest_rows if due(row, "oldest")],
        "new_gap": [row for row in oldest_rows if due(row, "new_gap") and (row["new"] or row["missing_source"])],
    }
    budgets = {"hot": trim_budget // 2, "oldest": trim_budget * 3 // 10}
    budgets["new_gap"] = trim_budget - sum(budgets.values())
    chosen = set()
    used = dict.fromkeys(queues, 0)
    picked = {lane: deque() for lane in queues}

    def allocate(lane, limit):
        for row in queues[lane]:
            if row["id"] not in chosen and row["cost"] <= limit:
                chosen.add(row["id"])
                picked[lane].append({**row, "lane": lane})
                used[lane] += row["cost"]
                limit -= row["cost"]
        return limit

    for lane in ("new_gap", "hot", "oldest"):
        allocate(lane, budgets[lane])
    remaining = trim_budget - sum(used.values())
    for lane in ("oldest", "new_gap", "hot"):
        remaining = allocate(lane, remaining)
    selected = []
    while any(picked.values()):
        for lane in ("hot", "oldest", "new_gap"):
            if picked[lane]:
                selected.append(picked[lane].popleft())
    targets = [row["target"] for row in selected]
    if source == "yiche":
        targets = {target["url"]: {key: value for key, value in target.items() if key != "url"} for target in targets}
    return targets, {
        "source": source, "as_of": today.isoformat(), "rankings_used": list(ranked),
        "budget": trim_budget, "reserved_estimated_trims": budgets,
        "selected_estimated_trims": used, "estimated_trims_unused": remaining, "selected": selected,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True, help="one source catalog plus saved rank lists")
    parser.add_argument("--output", type=Path, required=True, help="new directory; refuses to overwrite")
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--trim-budget", type=int, default=30)
    args = parser.parse_args()
    try:
        with args.evidence.open("rb") as stream:
            raw = stream.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("evidence exceeds size limit")
        document = json.loads(raw)
        targets, report = plan(document, args.as_of, args.trim_budget)
        report["ranking_snapshots"] = {kind: {key: value for key, value in item.items() if key != "ranks"}
                                       for kind, item in document.get("rankings", {}).items()
                                       if kind in report["rankings_used"]}
        if not targets:
            raise ValueError("no due targets fit the budget")
        payload = (json.dumps(targets, ensure_ascii=False, indent=2) + "\n").encode()
        if len(payload) > 65536:
            raise ValueError("target manifest exceeds collector limit")
        report.update(evidence_sha256=hashlib.sha256(raw).hexdigest(),
                      targets_sha256=hashlib.sha256(payload).hexdigest())
        args.output.mkdir(mode=0o700)
        with (args.output / "decision.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        with (args.output / "targets.json").open("xb") as stream:
            stream.write(payload)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    os.umask(0o077)
    main()
