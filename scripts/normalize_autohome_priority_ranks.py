#!/usr/bin/env python3
"""Build a source-local ranking snapshot from saved official Autohome pages."""

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re

POSITIVE_ID = re.compile(r"[1-9][0-9]{0,9}")


def autohome_rank_snapshot(path, kind, observed_on):
    """Read official Next data for the unfiltered first ranking page."""
    with path.open("rb") as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("Autohome rank page exceeds size limit")
    match = re.search(rb'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', raw, re.S)
    if not match:
        raise ValueError("Autohome ranking payload is missing")
    props = json.loads(match[1])["props"]["pageProps"]
    initial = props["initialValues"]
    listing = props["listRes"]
    expected = ("1", "1", "全车型销量总榜") if kind == "sales" else ("2", "2001", "全车型关注总榜")
    observed = (str(initial["typeid"]), str(initial["subranktypeid"]), listing["scenetitle"])
    if (observed != expected or str(initial["levelid"]) != "0"
            or initial["price"] != "0-9000" or listing["pageindex"] != 1):
        raise ValueError("unexpected Autohome ranking view")
    ranks = {}
    for index, item in enumerate(listing["list"][:100], 1):
        series_id = str(item["seriesid"])
        if not POSITIVE_ID.fullmatch(series_id) or series_id in ranks:
            raise ValueError("ambiguous Autohome series rank")
        if kind == "sales" and (type(item["salecount"]) is not int or item["salecount"] <= 0):
            raise ValueError("Autohome sales list lacks positive sales")
        ranks[series_id] = index
    if not ranks:
        raise ValueError("Autohome ranking is empty")
    signal = {"observed_on": observed_on.isoformat(), "ranks": ranks,
              "source_page_sha256": hashlib.sha256(raw).hexdigest(), "scope": expected[2]}
    if kind == "sales":
        signal.update(metric="autohome_monthly_sales", period=initial["date"])
    return signal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--observed-on", type=date.fromisoformat, required=True)
    parser.add_argument("--sales-html", type=Path)
    parser.add_argument("--heat-html", type=Path)
    args = parser.parse_args()
    try:
        with args.catalog.open("rb") as stream:
            raw = stream.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("catalog exceeds size limit")
        document = json.loads(raw)
        if document["source"] != "autohome":
            raise ValueError("Autohome pages require an Autohome catalog")
        files = {"sales": args.sales_html, "heat": args.heat_html}
        signals = {kind: autohome_rank_snapshot(path, kind, args.observed_on)
                   for kind, path in files.items() if path is not None}
        if not signals:
            raise ValueError("at least one saved official ranking page is required")
        document["rankings"] = {**document.get("rankings", {}), **signals}
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    os.umask(0o077)
    main()
