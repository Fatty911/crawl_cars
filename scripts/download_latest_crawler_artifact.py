#!/usr/bin/env python3
"""Download the newest valid crawler data artifact for merge publishing."""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


DATE_RE = re.compile(r"(20\d{6})")


def request_json(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "crawl-cars-artifact-downloader",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_artifact_with_gh(repo: str, run_id: int, artifact_name: str, dest: Path) -> bool:
    cmd = [
        "gh",
        "run",
        "download",
        str(run_id),
        "--repo",
        repo,
        "--name",
        artifact_name,
        "--dir",
        str(dest),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=600)
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        print(f"gh run download 失败: {details[:500]}")
        return False
    return True


def extract_date(*values: str) -> str:
    for value in values:
        match = DATE_RE.search(value or "")
        if match:
            return match.group(1)
    return ""


def count_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        rows = json.load(f)
    return len(rows) if isinstance(rows, list) else 0


def copy_valid_jsons(extract_dir: Path, output_dir: Path, pattern: str, min_rows: int, label: str) -> bool:
    candidates = sorted(Path(p) for p in glob.glob(str(extract_dir / "**" / pattern), recursive=True))
    if not candidates:
        print(f"{label}: artifact 中未找到 {pattern}")
        return False

    valid = False
    for path in candidates:
        try:
            rows = count_rows(path)
        except Exception as exc:
            print(f"{label}: {path.name} 读取失败: {exc}")
            continue
        print(f"{label}: {path.name} 行数 {rows}")
        if rows < min_rows:
            print(f"{label}: {path.name} 少于 {min_rows} 行，跳过该 artifact")
            continue
        shutil.copy2(path, output_dir / path.name)
        valid = True
    return valid


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--artifact-prefix", required=True)
    parser.add_argument("--json-pattern", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--min-rows", type=int, default=50)
    parser.add_argument("--min-bytes", type=int, default=1024)
    parser.add_argument("--min-date", default="")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("缺少 GITHUB_TOKEN/GH_TOKEN，无法下载 Actions artifact")
        return 0
    if not args.repo:
        print("缺少 GitHub repo，无法下载 Actions artifact")
        return 0

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    api_root = f"https://api.github.com/repos/{args.repo}"
    runs_url = (
        f"{api_root}/actions/workflows/{args.workflow}/runs"
        f"?status=success&per_page={max(1, min(args.limit, 100))}"
    )

    try:
        runs = request_json(runs_url, token).get("workflow_runs", [])
    except urllib.error.HTTPError as exc:
        print(f"{args.label}: 获取 workflow runs 失败: HTTP {exc.code}")
        return 0
    except Exception as exc:
        print(f"{args.label}: 获取 workflow runs 失败: {exc}")
        return 0

    for run in runs:
        run_id = run.get("id")
        if not run_id:
            continue
        artifacts_url = f"{api_root}/actions/runs/{run_id}/artifacts?per_page=100"
        try:
            artifacts = request_json(artifacts_url, token).get("artifacts", [])
        except Exception as exc:
            print(f"{args.label}: run {run_id} artifact 列表读取失败: {exc}")
            continue

        for artifact in artifacts:
            name = artifact.get("name", "")
            if not name.startswith(args.artifact_prefix) or artifact.get("expired"):
                continue
            artifact_date = extract_date(name, run.get("created_at", ""))
            if args.min_date and artifact_date and artifact_date < args.min_date:
                print(f"{args.label}: {name} 早于 {args.min_date}，跳过")
                continue

            size = int(artifact.get("size_in_bytes") or 0)
            if size < args.min_bytes:
                print(f"{args.label}: {name} 只有 {size} bytes，跳过")
                continue

            print(f"{args.label}: 尝试下载 run {run_id} artifact {name} ({size} bytes)")
            with tempfile.TemporaryDirectory(prefix="crawler-artifact-") as tmp:
                tmp_dir = Path(tmp)
                extract_dir = tmp_dir / name
                extract_dir.mkdir(parents=True, exist_ok=True)
                if not download_artifact_with_gh(args.repo, int(run_id), name, extract_dir):
                    continue
                if copy_valid_jsons(extract_dir, output_dir, args.json_pattern, args.min_rows, args.label):
                    print(f"{args.label}: 已使用 run {run_id} 的 {name}")
                    return 0

    print(f"{args.label}: 未找到可用的 {args.artifact_prefix} artifact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
