#!/usr/bin/env python3
"""Validate the intentionally small crawler storage footprint."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_DATA = {
    "data/dealer_prices.json",
    "data/diff_20260706.csv",
    "data/dongchedi_series_list.json",
    "data/progress.json",
}
RUNTIME_ONLY_PATHS = ("crawl_state/autohome", "step1_done", "dcd_step2_done")


# These two paths are runtime credential caches, never public source artifacts.
PUBLIC_PROXY_CACHE_PATHS = frozenset({"proxies.json", "data/proxies.json"})


def git_index_or_tree_paths(root: Path, source: str, args: list[str]) -> set[str]:
    # Metadata inspection is offline and must not invoke configured fsmonitor hooks.
    env = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_ALLOW_PROTOCOL="")
    try:
        output = subprocess.run(
            ["git", "--no-replace-objects", "-c", "core.fsmonitor=false", *args],
            cwd=root, env=env, capture_output=True, check=True, timeout=15,
        ).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f"cannot inspect Git {source}; refusing proxy-cache publication") from exc
    return set(output.decode("utf-8", errors="surrogateescape").split("\0")) - {""}


def validate_proxy_cache(root: Path = ROOT, *, check_head: bool = False) -> None:
    """Check raw Git object/index names, never credential contents or replaced trees."""
    queries = [("index", ["ls-files", "--cached", "-z"])]
    if check_head:
        queries.append(("HEAD", ["ls-tree", "-r", "-z", "--name-only", "HEAD"]))
    for source, args in queries:
        blocked = sorted(git_index_or_tree_paths(root, source, args) & PUBLIC_PROXY_CACHE_PATHS)
        if blocked:
            raise SystemExit(
                f"runtime proxy cache must not enter public Git ({source}): {', '.join(blocked)}"
            )


def stages_runtime_only_path(text: str) -> bool:
    names = "|".join(map(re.escape, RUNTIME_ONLY_PATHS))
    if re.search(rf"(?m)^\s*git\s+add[^\n]*(?:{names})", text):
        return True
    for loop in re.finditer(r"(?m)^\s*for\s+(\w+)\s+in\s+([^;\n]+);\s*do", text):
        variable, values = loop.groups()
        if not any(path in values for path in RUNTIME_ONLY_PATHS):
            continue
        body = text[loop.end() :]
        body = body.split("\ndone", 1)[0]
        reference = rf"\$(?:{re.escape(variable)}\b|\{{{re.escape(variable)}\}})"
        if re.search(rf"(?m)^\s*git\s+add[^\n]*{reference}", body):
            return True
    return False


def validate_detector() -> None:
    regression = """for path in crawl_state/autohome/progress.json step1_done; do
  git add -A -- \"$path\"
done"""
    if not stages_runtime_only_path(regression):
        raise RuntimeError("runtime-only staging detector regression")
    if stages_runtime_only_path("git add -A -- scripts/dongchedi/progress.json"):
        raise RuntimeError("runtime-only staging detector false positive")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proxy-cache-only", action="store_true")
    parser.add_argument("--check-head", action="store_true", help="also reject caches in the commit being published")
    args = parser.parse_args()
    validate_proxy_cache(check_head=args.check_head)
    if args.proxy_cache_only:
        print("runtime proxy cache is not tracked")
        return
    validate_detector()
    tracked = git_index_or_tree_paths(ROOT, "data index", ["ls-files", "--cached", "-z", "--", "data"])
    if tracked != ALLOWED_DATA:
        raise SystemExit(
            f"tracked data allowlist drift: added={sorted(tracked - ALLOWED_DATA)}, "
            f"missing={sorted(ALLOWED_DATA - tracked)}"
        )
    errors: list[str] = []
    for workflow in (ROOT / ".github/workflows").glob("*.y*ml"):
        text = workflow.read_text(encoding="utf-8")
        if re.search(r"(?m)^\s*git\s+add\s+(?:-A|\.)\s*$", text):
            errors.append(f"{workflow.name}: unscoped git add is forbidden")
        if re.search(r"(?m)^\s*git\s+add\s+-u\s*$", text) or re.search(
            r"git ls-files --others[^\n]*git add", text
        ):
            errors.append(f"{workflow.name}: equivalent unscoped git add is forbidden")
        if stages_runtime_only_path(text):
            errors.append(f"{workflow.name}: ignored runtime state must not be staged")
        lines = text.splitlines()
        upload_indexes = [
            index for index, line in enumerate(lines) if "uses: actions/upload-artifact@" in line
        ]
        for index in upload_indexes:
            step_start = max(
                (candidate for candidate in range(index, -1, -1) if re.match(r"^\s*- name:", lines[candidate])),
                default=index,
            )
            indent = len(lines[step_start]) - len(lines[step_start].lstrip())
            step_end = next(
                (
                    candidate
                    for candidate in range(index + 1, len(lines))
                    if re.match(rf"^\s{{{indent}}}- name:", lines[candidate])
                ),
                len(lines),
            )
            block = "\n".join(lines[step_start:step_end])
            retention = re.search(r"retention-days:\s*(\d+)", block)
            artifact_name = re.search(r"(?m)^\s+name:\s*(.+)$", block)
            classification_text = lines[step_start] + " " + (
                artifact_name.group(1) if artifact_name else ""
            )
            diagnostic = "if: failure()" in block or bool(
                re.search(r"(?i)(error|failure|diagnostic)[-_ ]?(log|artifact)?", classification_text)
            )
            expected = 7 if diagnostic else 3
            if retention is None:
                errors.append(f"{workflow.name}: upload-artifact step lacks retention-days")
            elif int(retention.group(1)) != expected:
                errors.append(
                    f"{workflow.name}: {'diagnostic' if diagnostic else 'success'} artifact "
                    f"retention must be {expected}, got {retention.group(1)}"
                )
    if errors:
        raise SystemExit("\n".join(errors))
    print("storage policy valid")


if __name__ == "__main__":
    main()
