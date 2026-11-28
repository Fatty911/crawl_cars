#!/usr/bin/env python3
"""Overlay static frontend files onto an extracted verified release site."""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from prepare_cnb_pages import file_references, safe_path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_PATHS = ("docs/", "config/filter_conditions.json")
META_RE = re.compile(r'(<meta\s+name="frontend-updated"\s+content=")[^"]*("\s*/?>)')


def resolve_frontend_updated_at(repo: Path = ROOT) -> str:
    """Return ISO timestamp of the latest commit touching frontend files."""
    res = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%cI", "--", *FRONTEND_PATHS],
        capture_output=True, text=True, check=False,
    )
    value = res.stdout.strip() if res.returncode == 0 else ""
    if value:
        return value
    fallback = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%cI"],
        capture_output=True, text=True, check=False,
    )
    return fallback.stdout.strip() if fallback.returncode == 0 else ""


def stamp_frontend_updated(index_path: Path, timestamp: str) -> None:
    """Set <meta name="frontend-updated"> content in index.html without mutating data."""
    if not timestamp or not index_path.is_file():
        return
    safe_ts = html_lib.escape(timestamp, quote=True)
    doc_text = index_path.read_text(encoding="utf-8")
    if META_RE.search(doc_text):
        updated = META_RE.sub(lambda m: f"{m.group(1)}{safe_ts}{m.group(2)}", doc_text, count=1)
    else:
        updated = doc_text.replace("</head>", f'  <meta name="frontend-updated" content="{safe_ts}" />\n</head>', 1)
    index_path.write_text(updated, encoding="utf-8")


def _protected_manifest_paths(manifest_bytes: bytes | None) -> set[str]:
    if not manifest_bytes:
        return set()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if not files:
        return set()
    return {safe_path(ref).as_posix() for ref in file_references(files)}


def overlay_frontend(site: Path, manifest_path: Path | None = None, repo: Path = ROOT, frontend_updated: str = "") -> None:
    """Copy docs/** UI files without mutating data/ or manifest-checksummed assets."""
    docs_dir = repo / "docs"
    before = manifest_path.read_bytes() if manifest_path and manifest_path.is_file() else None
    site_manifest = site / "data" / "manifest.json"
    manifest_bytes = before if before is not None else (site_manifest.read_bytes() if site_manifest.is_file() else None)
    protected = _protected_manifest_paths(manifest_bytes)
    for source in docs_dir.rglob("*"):
        if source.is_symlink():
            continue
        relative = source.relative_to(docs_dir)
        rel_posix = relative.as_posix()
        if relative.parts[0] == "data" or rel_posix == "manifest.json" or rel_posix in protected:
            continue
        if source.is_file():
            target = site / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    if "config/filter_conditions.json" not in protected:
        target_config = site / "config" / "filter_conditions.json"
        target_config.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / "config" / "filter_conditions.json", target_config)
    timestamp = frontend_updated.strip() or resolve_frontend_updated_at(repo)
    stamp_frontend_updated(site / "index.html", timestamp)
    if before is not None:
        if not site_manifest.is_file() or site_manifest.read_bytes() != before:
            raise RuntimeError("frontend overlay mutated verified data/manifest.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--frontend-updated", default="")
    args = parser.parse_args()
    overlay_frontend(args.site, manifest_path=args.manifest, frontend_updated=args.frontend_updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
