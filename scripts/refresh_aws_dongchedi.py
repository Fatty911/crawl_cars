#!/usr/bin/env python3
"""Refresh selected Dongchedi series on AWS through a loopback-only Mihomo unit."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path


from scripts.aws_crawl_runtime import ROOT, check_blocked, check_proxy, run_unit, write_json


SOURCE_FILE = "dongchedi-source.json"


def read_targets(path: Path) -> list[dict[str, str]]:
    if path.stat().st_size > 65536:
        raise ValueError("target list exceeds size limit")
    targets = json.loads(path.read_bytes())
    if not isinstance(targets, list) or not 1 <= len(targets) <= 30:
        raise ValueError("target list must contain 1 to 30 series")
    ids = set()
    for target in targets:
        if (not isinstance(target, dict) or set(target) != {"id", "name", "brand"}
                or not all(isinstance(value, str) and value.strip() for value in target.values())
                or not re.fullmatch(r"[1-9][0-9]{0,9}", target["id"])
                or target["id"] in ids):
            raise ValueError("target series must have a unique positive ID, name and brand")
        ids.add(target["id"])
    return targets


def collect(output: Path, targets: list[dict[str, str]], max_trims: int) -> None:
    os.umask(0o077)
    output.mkdir(mode=0o700, exist_ok=True)
    with (output / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan_path = output / "refresh-plan.json"
        source_path = ROOT / "scripts" / "crawl_dongchedi.py"
        plan = {
            "targets": targets,
            "max_trims": max_trims,
            "crawler_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "runtime_sha256": hashlib.sha256((ROOT / "scripts/aws_crawl_runtime.py").read_bytes()).hexdigest(),
        }
        if plan_path.exists():
            if json.loads(plan_path.read_bytes()) != plan:
                raise ValueError("output directory belongs to another refresh plan")
        else:
            if any(path != output / ".lock" for path in output.iterdir()):
                raise ValueError("output directory has files without a refresh plan")
            write_json(plan_path, plan)

        os.environ["DCD_RUN_STATE_DIR"] = str(output)
        argv = sys.argv
        try:
            sys.argv = ["crawl_dongchedi.py"]
            from scripts import crawl_dongchedi as dcd
        finally:
            sys.argv = argv

        # A retry reuses only evidence produced under this exact plan. No
        # crawler registry, HTML cache or historical parsed output is consulted.
        total = 0
        for target in targets:
            path = Path(dcd.dcd_json_dir) / f"{target['id']}.json"
            if path.is_symlink():
                raise ValueError("checkpoint may not be a symlink")
            if path.is_file():
                payload = json.loads(path.read_bytes())
            else:
                remaining = max_trims - total if max_trims else None
                payload = dcd.fetch_series_entity_payload(target, max_cars=remaining)
                write_json(path, payload)
            if payload.get("source") != "dongchedi_entity_api" or payload.get("series_info") != target:
                raise ValueError("checkpoint source or target identity mismatch")
            total += len(payload["car_ids"])
            if max_trims and total > max_trims:
                raise ValueError("checkpoint exceeds the trim request budget")
        expected = {f"{target['id']}.json" for target in targets}
        cached_names = {path.name for path in Path(dcd.dcd_json_dir).iterdir()
                        if not path.name.startswith(".refresh-")}
        if cached_names != expected:
            raise ValueError("refresh cache does not match the selected series")
        rows, _ = dcd.parse_config_pages(targets)
        dcd.require_non_empty_rows(rows, "AWS 定向刷新")
        write_json(output / SOURCE_FILE, [dcd.normalize_car_fields(row) for row in rows])
        print(f"AWS Dongchedi refresh: {total} requested trims, {len(rows)} parsed rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--probe-ip", type=ipaddress.IPv4Address, required=True)
    parser.add_argument("--probe-port", type=int, default=22)
    parser.add_argument("--max-trims", type=int, default=30, help="0 runs without a trim cap")
    parser.add_argument("--runtime-seconds", type=int, default=600)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.resolve()
    if (args.output.is_symlink() or output.is_relative_to(ROOT) or args.probe_ip.is_loopback
            or args.probe_ip.is_unspecified or not 1 <= args.probe_port <= 65535
            or not 0 <= args.max_trims <= 30 or not 30 <= args.runtime_seconds <= 3600):
        parser.error("invalid external run directory, direct probe, or collection budget")
    try:
        targets = read_targets(args.targets)
        address = str(args.probe_ip)
        if args.worker:
            check_blocked(address, args.probe_port)
            check_proxy()
            collect(output, targets, args.max_trims)
        else:
            run_unit("scripts.refresh_aws_dongchedi", [
                "--targets", str(args.targets.resolve()), "--output", str(output),
                "--probe-ip", address, "--probe-port", str(args.probe_port),
                "--max-trims", str(args.max_trims),
            ], address, args.probe_port, args.runtime_seconds)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
