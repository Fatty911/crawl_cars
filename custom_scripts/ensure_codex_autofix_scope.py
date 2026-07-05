#!/usr/bin/env python3
"""Reject Codex auto-fix changes outside the repository's approved scope."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ALLOWED_PREFIXES = (
    ".github/workflows/",
    "custom_scripts/",
)

ALLOWED_FILES = {
    ".gitignore",
    "AGENTS.md",
    "CHANGELOG.md",
    "config/CRAWL_SCOPE.md",
    "DOCKER_DEPLOY.md",
    "HISTORY.md",
    "README.md",
    "VPS_DEPLOY.md",
    "scripts/auto_fix_workflow.py",
    "crawl_dongchedi.py",
    "scripts/generate_clash_config.py",
    "scripts/merge_data.py",
    "scripts/proxy_manager.py",
    "scripts/run_with_proxy.py",
    "scripts/test_autohome.py",
}


def changed_files() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    paths = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        raw_path = line[3:].strip()
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1].strip()
        paths.append(raw_path.replace("\\", "/"))
    return paths


def is_allowed(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized in ALLOWED_FILES or normalized.startswith(ALLOWED_PREFIXES)


def main() -> int:
    bad_paths = [path for path in changed_files() if not is_allowed(path)]
    if bad_paths:
        print("Codex auto-fix 修改了白名单之外的文件，拒绝自动提交：")
        for path in bad_paths:
            print(f"- {path}")
        print("请人工检查这些文件，或把确有必要的路径加入白名单。")
        return 1

    print("Codex auto-fix 文件范围检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
