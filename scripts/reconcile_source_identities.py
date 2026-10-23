"""Reconcile saved names with reviewed source excerpts, without network access."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


def source_name(entry: dict) -> str:
    source = entry["source"]
    spec_id = entry["spec_id"]
    excerpt = source["selected_excerpt"]
    digest = hashlib.sha256(json.dumps(excerpt, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()
    if digest != source["excerpt_sha256"]:
        raise ValueError("source identity excerpt hash mismatch")
    if source["http_status"] != 200 or not re.fullmatch(r"[0-9a-f]{64}", source["raw_response_sha256"]):
        raise ValueError("source identity capture lacks successful raw-response evidence")
    stamp = datetime.fromisoformat(source["fetched_at_utc"])
    if stamp.tzinfo is None:
        raise ValueError("source identity timestamp must have a timezone")
    url = urlsplit(source["url"])
    if url.scheme != "https" or url.username or url.password or url.fragment or url.port:
        raise ValueError("invalid official source identity URL")
    if source["kind"] == "autohome-api-spec":
        series_id = entry.get("series_id")
        if not isinstance(series_id, str) or not re.fullmatch(r"[0-9]+", series_id):
            raise ValueError("API capture must retain its exact series ID")
        expected_url = ("https://car-web-api.autohome.com.cn/car/param/getParamConf"
                        f"?mode=1&site=1&seriesid={series_id}&specid={spec_id}")
        if (url.netloc != "car-web-api.autohome.com.cn" or url.path != "/car/param/getParamConf"
                or source["url"] != expected_url
                or str(excerpt["specid"]) != spec_id):
            raise ValueError("API excerpt is not bound to the requested spec")
        name = excerpt["param_name"]
        if name != entry["series"] + " " + excerpt["specname"]:
            raise ValueError("API model name disagrees with its spec identity")
        if entry["declared_year"] not in excerpt["condition"]:
            raise ValueError("API year condition disagrees with its spec identity")
    elif source["kind"] == "autohome-spec-page":
        if (url.netloc != "car.autohome.com.cn" or url.path != f"/config/spec/{spec_id}.html"
                or url.query):
            raise ValueError("page excerpt is not bound to the requested spec")
        match = re.fullmatch(r"【(.+)参数配置表】价格单_.*_汽车之家", excerpt["title"])
        if not match:
            raise ValueError("source page has no unambiguous model title")
        name = match[1]
        if name != entry["series"] + " " + excerpt["exact_spec_anchor_text"]:
            raise ValueError("source page title disagrees with its exact-spec anchor")
    else:
        raise ValueError("unsupported source identity evidence")
    if re.findall(r"(?<!\d)(20\d{2})\s*款", name) != [entry["declared_year"]]:
        raise ValueError("observed source name disagrees with the retained year")
    return name


def reconcile(rows: list[dict], document: dict) -> tuple[list[dict], list[dict]]:
    if document.get("schema_version") != 1 or not isinstance(document.get("entries"), list):
        raise ValueError("invalid source identity evidence schema")
    entries = {}
    for entry in document["entries"]:
        spec_id = entry["spec_id"]
        if not isinstance(spec_id, str) or not spec_id.isdecimal() or spec_id in entries:
            raise ValueError("source identity spec IDs must be unique decimal strings")
        entries[spec_id] = (entry, source_name(entry))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("source identity input must be a list of rows")
    result = []
    changes = []
    for index, row in enumerate(rows):
        matched = entries.get(str(row.get("车款ID") or ""))
        if matched and "汽车之家" in str(row.get("数据来源") or ""):
            entry, observed = matched
            if (row.get("品牌") != entry["brand"] or row.get("车系") != entry["series"]
                    or str(row.get("年款")) != entry["declared_year"]
                    or row.get("车型名称") not in {entry["previous_name"], observed}):
                raise ValueError(f"saved identity differs from reviewed evidence: spec {entry['spec_id']}")
            if row["车型名称"] != observed:
                changes.append({"row_index": index, "spec_id": entry["spec_id"],
                                "field": "车型名称", "before": row["车型名称"], "after": observed,
                                "source_url": entry["source"]["url"],
                                "raw_response_sha256": entry["source"]["raw_response_sha256"]})
                row = dict(row, 车型名称=observed)
        result.append(row)
    return result, changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    original = args.input.read_bytes()
    evidence = args.evidence.read_bytes()
    prepared, changes = reconcile(json.loads(original), json.loads(evidence))
    result = (json.dumps(prepared, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    report = {"schema_version": 1, "input_sha256": hashlib.sha256(original).hexdigest(),
              "output_sha256": hashlib.sha256(result).hexdigest(),
              "evidence_sha256": hashlib.sha256(evidence).hexdigest(),
              "rows": len(prepared), "changes": changes, "source_http_requests": 0}
    args.output.write_bytes(result)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
