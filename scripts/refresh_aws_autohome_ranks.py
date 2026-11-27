#!/usr/bin/env python3
"""Refresh the public Autohome rankings inside the AWS crawler network boundary."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import ipaddress
import json
import os
import sys
from pathlib import Path
import tempfile

import requests

from scripts import plan_aws_crawl_priority as priority
from scripts.aws_crawl_pipeline import PipelineError, atomic_json, private_json
from scripts.aws_crawl_runtime import PROXY, check_blocked, check_proxy, run_unit
from scripts.normalize_autohome_priority_ranks import autohome_rank_snapshot

RANK_ROOT = "https://www.autohome.com.cn/rank/"
MAX_PAGE_BYTES = 4 * 1024 * 1024
RUNTIME_SECONDS = 65


def page_urls(observed_on):
    last_month = observed_on.replace(day=1) - timedelta(days=1)
    return {
        "sales": RANK_ROOT + "1-1-0-0_9000-x-x-x/" + last_month.strftime("%Y-%m"),
        "heat": RANK_ROOT + "2-2001-0-x-x-x-0_9000",
    }


def fetch_page(url):
    with requests.Session() as session:
        session.trust_env = False
        with session.get(url, proxies={"https": PROXY}, allow_redirects=False,
                         stream=True, timeout=(10, 15)) as response:
            if response.status_code != 200 or "text/html" not in response.headers.get("Content-Type", ""):
                raise ValueError("Autohome did not return a ranking page")
            raw = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                raw.extend(chunk)
                if len(raw) > MAX_PAGE_BYTES:
                    raise ValueError("Autohome ranking page exceeds size limit")
            return bytes(raw)


def refresh_rankings(output, observed_on, fetch=fetch_page):
    parent = output.parent
    if (not output.is_absolute() or parent.resolve() != parent or output.is_symlink()
            or parent.stat().st_uid != os.geteuid() or parent.stat().st_mode & 0o022):
        raise PipelineError("rankings output must be in a private owned directory")
    fd = os.open(output.with_suffix(output.suffix + ".lock"),
                 os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous = private_json(output) if output.exists() else {}
        if not isinstance(previous, dict) or not previous.keys() <= {"sales", "heat"}:
            raise PipelineError("unexpected previous ranking snapshot")
        updated = dict(previous)
        errors = {}
        with tempfile.TemporaryDirectory(prefix="autohome-ranks-") as temporary:
            page = Path(temporary) / "page.html"
            for kind, url in page_urls(observed_on).items():
                try:
                    payload = fetch(url)
                    if len(payload) > MAX_PAGE_BYTES:
                        raise ValueError("Autohome ranking page exceeds size limit")
                    page.write_bytes(payload)
                    signal = autohome_rank_snapshot(page, kind, observed_on)
                    if kind not in priority.eligible_ranks({kind: signal}, observed_on, "autohome"):
                        raise ValueError("Autohome ranking does not describe a current published period")
                    before = previous.get(kind, {})
                    if (signal["observed_on"] < before.get("observed_on", "")
                            or kind == "sales" and signal["period"] < before.get("period", "")):
                        raise ValueError("Autohome ranking moved backwards")
                    candidate = dict(updated, **{kind: dict(signal, source_url=url)})
                    if candidate != updated:
                        atomic_json(output, candidate)
                        updated = candidate
                except (OSError, requests.RequestException, ValueError, KeyError, TypeError) as error:
                    errors[kind] = type(error).__name__
        return {"updated": [kind for kind in updated if updated[kind] != previous.get(kind)],
                "preserved": [kind for kind in previous if kind in errors], "failures": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rankings", type=Path, required=True)
    parser.add_argument("--probe-ip", type=ipaddress.IPv4Address, required=True)
    parser.add_argument("--probe-port", type=int, default=22)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.probe_ip.is_loopback or args.probe_ip.is_unspecified or not 1 <= args.probe_port <= 65535:
        parser.error("invalid direct-egress probe")
    try:
        if not args.worker:
            run_unit("scripts.refresh_aws_autohome_ranks", sys.argv[1:], str(args.probe_ip),
                     args.probe_port, RUNTIME_SECONDS)
            return
        check_blocked(str(args.probe_ip), args.probe_port)
        check_proxy()
        os.umask(0o077)
        print(json.dumps(refresh_rankings(args.rankings, datetime.now(timezone.utc).date()), ensure_ascii=False))
    except (OSError, PipelineError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
