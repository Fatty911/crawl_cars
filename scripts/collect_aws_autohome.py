#!/usr/bin/env python3
"""Refresh selected Autohome API targets on AWS through the Mihomo boundary."""

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


CRAWLER = ROOT / "scripts" / "test_autohome.py"
SOURCE = "autohome-source.json"


def read_targets(path: Path) -> list[dict[str, str]]:
    with path.open("rb") as stream:
        content = stream.read(65537)
    if len(content) > 65536:
        raise ValueError("Autohome target list exceeds size limit")
    targets = json.loads(content)
    if not isinstance(targets, list) or not 1 <= len(targets) <= 30:
        raise ValueError("Autohome targets must be a list of 1 to 30 entries")
    seen = set()
    for target in targets:
        if (not isinstance(target, dict) or not {"car_id", "series", "brand"} <= target.keys()
                or not target.keys() <= {"car_id", "series", "brand", "spec_id"}
                or not all(isinstance(value, str) and value.strip() for value in target.values())
                or not re.fullmatch(r"[1-9][0-9]{0,9}", target["car_id"])
                or ("spec_id" in target and not re.fullmatch(r"[1-9][0-9]{0,9}", target["spec_id"]))):
            raise ValueError("invalid Autohome target identity")
        key = (target["car_id"], target.get("spec_id"))
        if key in seen:
            raise ValueError("duplicate Autohome target")
        seen.add(key)
    return targets


def api_spec_ids(crawler, html: str) -> list[str]:
    config = crawler.extract_var_json(html, "config")
    if not isinstance(config, dict):
        raise ValueError("Autohome API response has no config object")
    fields = [item for group in config.get("result", {}).get("paramtypeitems", [])
              for item in group.get("paramitems", []) if item.get("name") == "车款ID"]
    if len(fields) != 1:
        raise ValueError("Autohome API response must have one trim ID field")
    ids = [str(item.get("value") or "") for item in fields[0].get("valueitems", [])]
    if not ids or len(set(ids)) != len(ids) or any(not re.fullmatch(r"[1-9][0-9]*", sku) for sku in ids):
        raise ValueError("Autohome API response has invalid trim identities")
    return ids


def collect(output: Path, targets: list[dict[str, str]], max_trims: int) -> None:
    os.umask(0o077)
    output.mkdir(mode=0o700, exist_ok=True)
    with (output / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = {
            "targets": targets, "max_trims": max_trims,
            "crawler_sha256": hashlib.sha256(CRAWLER.read_bytes()).hexdigest(),
            "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "runtime_sha256": hashlib.sha256((ROOT / "scripts/aws_crawl_runtime.py").read_bytes()).hexdigest(),
        }
        plan_file = output / "collection-plan.json"
        if plan_file.exists():
            if json.loads(plan_file.read_bytes()) != plan:
                raise ValueError("output directory belongs to another Autohome plan")
        else:
            if any(p != output / ".lock" for p in output.iterdir()):
                raise ValueError("output directory has files without an Autohome plan")
            write_json(plan_file, plan)
        target_file = output / SOURCE
        if target_file.exists():
            info = inspect_asset(target_file, "autohome")
            print(f"Autohome source already complete: {info['rows']} rows")
            return

        os.environ["AUTOHOME_RUN_STATE_DIR"] = str(output / "state")
        argv = sys.argv
        try:
            sys.argv = ["test_autohome.py"]
            from scripts import test_autohome as crawler
        finally:
            sys.argv = argv

        responses = output / "responses"
        responses.mkdir(exist_ok=True)
        manifest = {}
        total = 0
        for target in targets:
            key = target["car_id"] + ("_spec_" + target["spec_id"] if "spec_id" in target else "")
            checkpoint = responses / (key + ".json")
            if checkpoint.is_symlink():
                raise ValueError("Autohome checkpoint cannot be a symlink")
            if checkpoint.is_file():
                response = json.loads(checkpoint.read_bytes())
                if response.get("target") != target:
                    raise ValueError("Autohome checkpoint target mismatch")
            else:
                if max_trims and total >= max_trims:
                    raise ValueError("Autohome collection budget exhausted")
                if "spec_id" in target:
                    html = crawler.fetch_autohome_history_spec_api_html(target)
                    terminal = False
                else:
                    html, terminal = crawler.fetch_autohome_api_html(
                        target["car_id"], max_specs=max_trims-total if max_trims else None
                    )
                if not html and not terminal:
                    raise ValueError("Autohome API did not return usable configuration data")
                response = {"target": target, "html": html, "terminal_empty": terminal}
                write_json(checkpoint, response)
            html = response.get("html")
            if not html:
                if response.get("terminal_empty") is not True:
                    raise ValueError("Autohome checkpoint has no source evidence")
                continue
            ids = api_spec_ids(crawler, html)
            if "spec_id" in target and ids != [target["spec_id"]]:
                raise ValueError("Autohome API returned a different requested trim")
            total += len(ids)
            if max_trims and total > max_trims:
                raise ValueError("Autohome source exceeds the trim budget")
            manifest[key] = dict(target, cache_key=key)
            destination = Path(crawler.newjson_dir) / key
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                             prefix=".refresh-", delete=False) as stream:
                stream.write(html)
                temporary = Path(stream.name)
            temporary.replace(destination)
        cached_names = {p.name for p in Path(crawler.newjson_dir).iterdir()
                        if not p.name.startswith(".refresh-")}
        if cached_names != set(manifest):
            raise ValueError("Autohome parsed input cache differs from the target plan")
        crawler.save_target_manifest(manifest)
        parsed = output / "parsed"
        parsed.mkdir(exist_ok=True)
        rows = crawler.generate_csv(output_dir=parsed)
        if not rows:
            raise ValueError("Autohome source did not produce any verified trim rows")
        write_json(target_file, rows)
        inspect_asset(target_file, "autohome")
        print(f"AWS Autohome refresh: {total} requested trims, {len(rows)} source rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--probe-ip", type=ipaddress.IPv4Address, required=True)
    parser.add_argument("--probe-port", type=int, default=22)
    parser.add_argument("--max-trims", type=int, default=30)
    parser.add_argument("--runtime-seconds", type=int, default=240)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.resolve()
    if (args.output.is_symlink() or output.is_relative_to(ROOT) or args.probe_ip.is_loopback
            or args.probe_ip.is_unspecified or not 1 <= args.probe_port <= 65535
            or not 0 <= args.max_trims <= 30 or not 30 <= args.runtime_seconds <= 3600):
        parser.error("invalid run directory, direct probe or collection budget")
    try:
        targets = read_targets(args.targets)
        address = str(args.probe_ip)
        if args.worker:
            check_blocked(address, args.probe_port)
            check_proxy()
            collect(output, targets, args.max_trims)
        else:
            run_unit("scripts.collect_aws_autohome", [
                "--targets", str(args.targets.resolve()), "--output", str(output),
                "--probe-ip", address, "--probe-port", str(args.probe_port),
                "--max-trims", str(args.max_trims),
            ], address, args.probe_port, args.runtime_seconds)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
