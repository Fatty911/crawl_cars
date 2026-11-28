#!/usr/bin/env python3
"""Compare all public Pages mirrors (cars/cars2/cars3) and reconcile drift."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SITES = {
    "github": "https://cars.jiucai.eu.org",
    "cloudflare": "https://cars2.jiucai.eu.org",
    "codeberg": "https://cars3.jiucai.eu.org",
}
FRONTEND_ASSETS = ("/index.html", "/app.js", "/styles.css", "/filter_conditions.json")


def fetch_url(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "crawl-cars-mesh/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError(f"{url} returned HTTP {resp.status}")
        return resp.read()


def manifest_core(raw: bytes) -> dict[str, Any]:
    doc = json.loads(raw.decode("utf-8"))
    prov = doc.get("provenance") or {}
    return {
        "date": doc.get("date"),
        "updatedAt": doc.get("updatedAt"),
        "rowCount": doc.get("rowCount"),
        "filteredRowCount": doc.get("filteredRowCount"),
        "awsRawRelease": prov.get("awsRawRelease"),
        "workflowRunId": prov.get("workflowRunId"),
    }


def inspect_site(base_url: str, fetch=fetch_url) -> dict[str, Any]:
    assets = {}
    for asset in FRONTEND_ASSETS:
        data = fetch(base_url + asset)
        assets[asset] = hashlib.sha256(data).hexdigest()
    m_raw = fetch(base_url + "/data/manifest.json")
    return {"url": base_url, "assets": assets, "manifest": manifest_core(m_raw)}


def compare_sites(sites: dict[str, str] = SITES, fetch=fetch_url) -> dict[str, Any]:
    snapshots: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for name, url in sites.items():
        try:
            snapshots[name] = inspect_site(url, fetch=fetch)
        except Exception as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"

    ref_name = "github" if "github" in snapshots else (next(iter(snapshots), ""))
    drifted: dict[str, list[str]] = {}
    if ref_name:
        ref = snapshots[ref_name]
        for name, snap in snapshots.items():
            if name == ref_name:
                continue
            reasons = [
                f"asset:{k}" for k in FRONTEND_ASSETS if snap["assets"].get(k) != ref["assets"].get(k)
            ]
            if snap["manifest"] != ref["manifest"]:
                reasons.append("manifest")
            if reasons:
                drifted[name] = reasons
    return {
        "reference": ref_name,
        "snapshots": snapshots,
        "errors": errors,
        "drifted": drifted,
        "in_sync": not errors and not drifted,
    }


def dispatch_reconcile(report: dict[str, Any], repo: str, latest_tag: str = "") -> list[str]:
    triggered: list[str] = []
    targets = set(report.get("drifted", {}).keys()) | set(report.get("errors", {}).keys())
    if not targets:
        return triggered
    if "github" in targets:
        subprocess.run(["gh", "workflow", "run", "deploy-frontend.yml", "--repo", repo, "--ref", "main"], check=True)
        triggered.append("deploy-frontend.yml")
    if "cloudflare" in targets:
        cmd = ["gh", "workflow", "run", "cnb-pages.yml", "--repo", repo, "--ref", "main", "-f", "target=cloudflare"]
        if latest_tag:
            cmd.extend(["-f", f"release_tag={latest_tag}"])
        subprocess.run(cmd, check=True)
        triggered.append("cnb-pages.yml")
    if "codeberg" in targets:
        cmd = ["gh", "workflow", "run", "codeberg-pages.yml", "--repo", repo, "--ref", "main"]
        if latest_tag:
            cmd.extend(["-f", f"release_tag={latest_tag}"])
        subprocess.run(cmd, check=True)
        triggered.append("codeberg-pages.yml")
    return triggered


def resolve_latest_immutable_tag(repo: str) -> str:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from download_verified_release import require_immutable, select_release  # noqa: E402
    from publish_github_release import GitHub  # noqa: E402

    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PAT") or ""
    api = GitHub(repo, token)
    if not token:
        api.headers.pop("Authorization", None)
    release = require_immutable(select_release(api, allow_legacy=False))
    return str(release["tag_name"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Exit non-zero if any site differs or fails")
    parser.add_argument("--apply", action="store_true", help="Trigger workflows for drifted sites")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "Fatty911/crawl_cars"))
    parser.add_argument("--latest-tag", default="")
    args = parser.parse_args()

    report = compare_sites()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.apply and not report["in_sync"]:
        tag = args.latest_tag.strip() or resolve_latest_immutable_tag(args.repo)
        triggered = dispatch_reconcile(report, args.repo, latest_tag=tag)
        print("Triggered reconcile workflows:", triggered)
        if not triggered or args.check:
            return 1
        return 0
    if args.check and not report["in_sync"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
