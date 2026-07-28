#!/usr/bin/env python3
"""Reject Codex auto-fix changes outside approved business paths or inside trust roots."""
from __future__ import annotations

import argparse
import subprocess
import sys

ALLOWED_PREFIXES = ("tests/",)
ALLOWED_FILES = {
    ".gitignore",
    "CHANGELOG.md",
    "DOCKER_DEPLOY.md",
    "HISTORY.md",
    "README.md",
    "VPS_DEPLOY.md",
    "crawl_dongchedi.py",
    "scripts/auto_fix_workflow.py",
    "scripts/crawl_dongchedi.py",
    "scripts/crawl_yiche.py",
    "scripts/generate_clash_config.py",
    "scripts/merge_data.py",
    "scripts/proxy_manager.py",
    "scripts/run_with_proxy.py",
    "scripts/test_autohome.py",
}
PROTECTED_PREFIXES = (
    ".github/",
    "site/data/",
    "config/",
)
PROTECTED_FILES = {
    "AGENTS.md",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "poetry.lock",
    "uv.lock",
    ".python-version",
    ".node-version",
    "requirements.txt",
    "requirements-dev.txt",
    "scripts/audit_pages_payload.py",
    "scripts/ensure_codex_autofix_scope.py",
    "scripts/prepare_pages_payload.py",
    "scripts/preserve_publish_baseline.py",
    "scripts/publish_identity.py",
    "scripts/verify_publish_superset.py",
    "scripts/validate_workflow_expectations.py",
    "tests/test_debug_publish_safety.py",
    "tests/test_pages_payload_audit.py",
}


def _git_paths(*args: str) -> set[str]:
    result = subprocess.run(["git", *args, "-z"], check=True, capture_output=True)
    return {part.decode("utf-8", "surrogateescape").replace("\\", "/") for part in result.stdout.split(b"\0") if part}


def changed_files() -> list[str]:
    paths = set()
    paths.update(_git_paths("diff", "--name-only", "--no-renames"))
    paths.update(_git_paths("diff", "--cached", "--name-only", "--no-renames"))
    paths.update(_git_paths("ls-files", "--others", "--exclude-standard"))
    return sorted(paths)


def is_allowed(path: str) -> bool:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized in PROTECTED_FILES or normalized.startswith(PROTECTED_PREFIXES):
        return False
    if normalized.startswith("requirements") and normalized.endswith(".txt"):
        return False
    return normalized in ALLOWED_FILES or normalized.startswith(ALLOWED_PREFIXES)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", action="store_true")
    args = parser.parse_args()
    paths = changed_files()
    bad_paths = [path for path in paths if not is_allowed(path)]
    if bad_paths:
        print("Codex auto-fix 修改了白名单之外或信任根文件，拒绝自动提交：")
        for path in bad_paths:
            print(f"- {path}")
        return 1
    if args.stage:
        for path in paths:
            subprocess.run(["git", "add", "-A", "--", path], check=True)
        print(f"Codex auto-fix 文件范围检查通过并已暂存 {len(paths)} 个路径")
    else:
        print("Codex auto-fix 文件范围检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
