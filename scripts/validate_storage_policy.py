#!/usr/bin/env python3
"""Validate the intentionally small crawler storage footprint."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_DATA = {
    "data/diff_20260706.csv",
    "data/dongchedi_20260302.json",
    "data/dongchedi_series_list.json",
    "data/filtered_cars_20260622.csv",
    "data/filtered_cars_20260622.json",
    "data/merged_20260622.csv",
    "data/merged_20260622.json",
    "data/progress.json",
    "data/proxies.json",
}
RUNTIME_ONLY_PATHS = ("crawl_state/autohome", "step1_done", "dcd_step2_done")


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
    validate_detector()
    tracked = set(
        subprocess.run(
            ["git", "ls-files", "data"], cwd=ROOT, text=True, capture_output=True, check=True
        ).stdout.splitlines()
    )
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
