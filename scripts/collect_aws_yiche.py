#!/usr/bin/env python3
"""Collect source-only Yiche rows on AWS within the Mihomo network boundary."""

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
import tempfile
from pathlib import Path

from scripts.aws_crawl_runtime import ROOT, check_blocked, check_proxy, run_unit, write_json
from scripts.aws_raw_bundle import inspect_asset


CRAWLER = ROOT / "scripts" / "crawl_yiche.py"
PLAN = "collection-plan.json"
SOURCE = "yiche-source.json"


def resume_arguments(checkpoint: Path, plan: dict) -> tuple[str, list[str]]:
    if (checkpoint.is_symlink() or not checkpoint.is_file() or checkpoint.name != "checkpoint.json"
            or not checkpoint.parent.name.startswith("attempt-")):
        raise ValueError("resume checkpoint must be a regular collector attempt file")
    plan_path = checkpoint.parent.parent / PLAN
    previous_plan = json.loads(plan_path.read_bytes())
    previous_plan.pop("resume_checkpoint_sha256", None)
    if previous_plan != plan:
        raise ValueError("resume checkpoint belongs to another collection plan")
    raw = checkpoint.read_bytes()
    if not plan["discover"] and not json.loads(raw).get("resume_state", {}).get("pending"):
        raise ValueError("explicit Yiche checkpoint has no pending targets")
    digest = hashlib.sha256(raw).hexdigest()
    return digest, [
        "--resume-checkpoint", str(checkpoint),
        "--resume-source-checkpoint-sha256", digest,
        "--resume-source-crawler-sha256", plan["crawler_sha256"],
    ]


def collect(args, output: Path) -> None:
    os.umask(0o077)
    output.mkdir(mode=0o700, exist_ok=True)
    with (output / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest_bytes = None
        if args.target_manifest:
            with args.target_manifest.open("rb") as handle:
                manifest_bytes = handle.read(65537)
            if len(manifest_bytes) > 65536:
                raise ValueError("Yiche target manifest exceeds size limit")
        plan = {
            "series": args.series,
            "target_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest()
            if manifest_bytes is not None else None,
            "discover": args.discover,
            "max_series": args.max_series,
            "max_rows": args.max_rows,
            "crawler_sha256": hashlib.sha256(CRAWLER.read_bytes()).hexdigest(),
            "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "runtime_sha256": hashlib.sha256((ROOT / "scripts/aws_crawl_runtime.py").read_bytes()).hexdigest(),
        }
        resume = []
        if args.resume_from:
            digest, resume = resume_arguments(args.resume_from.absolute(), plan)
            plan["resume_checkpoint_sha256"] = digest
        path = output / PLAN
        if path.exists():
            if json.loads(path.read_bytes()) != plan:
                raise ValueError("output directory belongs to another collection plan")
        else:
            if any(p != output / ".lock" for p in output.iterdir()):
                raise ValueError("output directory has files without a collection plan")
            write_json(path, plan)

        target = output / SOURCE
        if target.exists():
            info = inspect_asset(target, "yiche")
            print(f"Yiche source already complete: {info['rows']} rows")
            return

        attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=output))
        pending = attempt / "rows.json"
        argv = [
            sys.executable, str(CRAWLER), "--url-file", "",
            "--output", str(pending), "--checkpoint", str(attempt / "checkpoint.json"),
            "--time-limit", str(args.runtime_seconds - 20),
        ]
        if not args.discover:
            argv.append("--no-discovery")
        if args.resume_from:
            argv.extend(resume)
            if args.max_series:
                argv.extend(["--resume-smoke-targets", str(args.max_series)])
        else:
            argv.extend(["--max-series", str(args.max_series)])
            for url in args.series:
                argv.extend(["--url", url])
            if manifest_bytes is not None:
                targets = attempt / "targets.json"
                targets.write_bytes(manifest_bytes)
                argv.extend(["--target-manifest", str(targets)])
        env = os.environ.copy()
        # These settings are sourced from the explicit AWS plan, not the caller.
        for key in ("YICHE_SERIES_URLS", "YICHE_DISCOVERY_URLS", "GITHUB_REPOSITORY",
                    "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA"):
            env.pop(key, None)
        subprocess.run(argv, cwd=ROOT, env=env, check=True)
        info = inspect_asset(pending, "yiche")
        if args.max_rows and info["rows"] > args.max_rows:
            raise ValueError("Yiche result exceeds the collection row budget")
        write_json(target, json.loads(pending.read_bytes()))
        print(f"AWS Yiche collection: {info['rows']} source rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", action="append", default=[])
    parser.add_argument("--target-manifest", type=Path)
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--probe-ip", type=ipaddress.IPv4Address, required=True)
    parser.add_argument("--probe-port", type=int, default=22)
    parser.add_argument("--max-series", type=int, default=1)
    parser.add_argument("--max-rows", type=int, default=30)
    parser.add_argument("--runtime-seconds", type=int, default=240)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.resolve()
    if (args.output.is_symlink() or output.is_relative_to(ROOT) or args.probe_ip.is_loopback
            or args.probe_ip.is_unspecified or not 1 <= args.probe_port <= 65535
            or not 60 <= args.runtime_seconds <= 3600
            or args.max_series < 0 or args.max_rows < 0
            or bool(args.series) == args.discover
            or (args.target_manifest and args.discover)
            or any(not re.fullmatch(r"https://car\.yiche\.com/[a-z0-9-]+/peizhi/", url)
                   for url in args.series)):
        parser.error("invalid run directory, direct probe, collection budget or Yiche target plan")
    address = str(args.probe_ip)
    try:
        if args.worker:
            check_blocked(address, args.probe_port)
            check_proxy()
            collect(args, output)
        else:
            run_unit("scripts.collect_aws_yiche", sys.argv[1:], address, args.probe_port, args.runtime_seconds)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
