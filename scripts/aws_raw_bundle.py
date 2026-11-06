#!/usr/bin/env python3
"""Package and validate source-only crawler output for the Pages workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


MANIFEST = "aws-raw-manifest.json"
SOURCES = {
    "autohome": ("autoHome_aws.json", "汽车之家"),
    "dongchedi": ("dongchedi_aws.json", "懂车帝"),
    "yiche": ("yiche_aws.json", "易车"),
}
MAX_ASSET_BYTES = 200 * 1024 * 1024


def validate_identity(tag: str, commit: str) -> None:
    if not re.fullmatch(r"aws-raw-[0-9]{8}T[0-9]{6}Z", tag):
        raise ValueError("raw release tag must be aws-raw-YYYYMMDDTHHMMSSZ")
    datetime.strptime(tag.removeprefix("aws-raw-"), "%Y%m%dT%H%M%SZ")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("producer commit must be a full Git SHA")


def inspect_asset(path: Path, source: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or non-regular {source} asset")
    size = path.stat().st_size
    if not 0 < size <= MAX_ASSET_BYTES:
        raise ValueError(f"invalid size for {source} asset")
    raw = path.read_bytes()
    rows = json.loads(raw)
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{source} asset must contain source rows")
    label = SOURCES[source][1]
    for row in rows:
        if not isinstance(row, dict) or not all(
            isinstance(row.get(key), str) and row[key].strip(" -")
            for key in ("车系", "车型名称")
        ):
            raise ValueError(f"{source} asset contains a row without a series or trim")
        if row.get("数据来源") not in (None, "", label):
            raise ValueError(f"{source} asset contains a row from another source")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw), "rows": len(rows)}


def pack(destination: Path, tag: str, commit: str, inputs: dict[str, Path]) -> dict:
    validate_identity(tag, commit)
    if not inputs:
        raise ValueError("at least one source asset is required")
    if destination.exists() or destination.is_symlink():
        raise ValueError("output directory already exists")
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".aws-raw-") as work:
        staged = Path(work) / "bundle"
        staged.mkdir()
        assets = {}
        for source, path in inputs.items():
            name = SOURCES[source][0]
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ASSET_BYTES:
                raise ValueError(f"invalid source file for {source}")
            shutil.copyfile(path, staged / name)
            assets[source] = {"file": name, **inspect_asset(staged / name, source)}
        manifest = {"schema": 1, "tag": tag, "producer_commit": commit, "assets": assets}
        (staged / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        staged.rename(destination)
    return manifest


def verify(bundle: Path, tag: str) -> dict:
    manifest_path = bundle / MANIFEST
    if manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size > 8192:
        raise ValueError("invalid raw manifest file")
    manifest = json.loads(manifest_path.read_bytes())
    if not isinstance(manifest, dict) or manifest.get("schema") != 1 or manifest.get("tag") != tag:
        raise ValueError("raw manifest schema or release tag mismatch")
    validate_identity(tag, manifest.get("producer_commit", ""))
    assets = manifest.get("assets")
    if not isinstance(assets, dict) or not assets or not assets.keys() <= SOURCES.keys():
        raise ValueError("raw manifest sources are invalid")
    expected = {MANIFEST}
    for source, entry in assets.items():
        name = SOURCES[source][0]
        actual = {"file": name, **inspect_asset(bundle / name, source)}
        if entry != actual:
            raise ValueError(f"raw manifest mismatch for {source}")
        expected.add(name)
    if {path.name for path in bundle.iterdir()} != expected:
        raise ValueError("bundle has unexpected files")
    return manifest



def gh(*args: str, missing: str = "", timeout: int = 600) -> str | None:
    result = subprocess.run(["gh", *args], capture_output=True, encoding="utf-8", timeout=timeout)
    if result.returncode == 0:
        return result.stdout
    if missing and missing in result.stderr.strip().splitlines():
        return None
    raise RuntimeError(f"GitHub CLI failed: {result.stderr.strip()[:300]}")


def release_missing_assets(release: dict, manifest: dict, expected: dict) -> list[str]:
    if (release.get("tagName") != manifest["tag"]
            or release.get("targetCommitish") != manifest["producer_commit"]
            or release.get("isPrerelease") is not True
            or type(release.get("isDraft")) is not bool):
        raise ValueError("existing GitHub release has different provenance or type")
    seen = set()
    for asset in release["assets"]:
        name = asset.get("name")
        if name in seen or name not in expected:
            raise ValueError("existing GitHub release has unexpected or duplicate assets")
        if asset.get("state") == "starter":
            raise ValueError(f"existing GitHub release has an interrupted upload; left unchanged: {name}")
        if asset.get("state") != "uploaded" or (
            asset.get("size"), asset.get("digest")
        ) != expected[name]:
            raise ValueError(f"existing GitHub release asset does not match: {name}")
        seen.add(name)
    return sorted(expected.keys() - seen)


def publish_github(bundle: Path, tag: str, repo: str, *, check_only: bool = False) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("repo must be owner/repository")
    bundle = bundle.resolve()
    manifest = verify(bundle, tag)
    commit = manifest["producer_commit"]
    manifest_bytes = (bundle / MANIFEST).read_bytes()
    expected = {MANIFEST: (len(manifest_bytes), "sha256:" + hashlib.sha256(manifest_bytes).hexdigest())}
    expected.update({entry["file"]: (entry["size"], "sha256:" + entry["sha256"])
                     for entry in manifest["assets"].values()})
    remote = "github.com/" + repo
    ref_path = f"repos/{repo}/git/ref/tags/{tag}"

    def check_ref() -> bool:
        ref = gh("api", "--hostname", "github.com", ref_path, missing="gh: Not Found (HTTP 404)")
        if ref is None:
            return False
        obj = json.loads(ref).get("object", {})
        if obj.get("type") != "commit" or obj.get("sha") != commit:
            raise ValueError("remote tag points to a different producer commit")
        return True

    def create_ref() -> None:
        # POST never moves an existing tag. A concurrent creation fails closed.
        gh("api", "--hostname", "github.com", "--method", "POST", f"repos/{repo}/git/refs",
           "-f", f"ref=refs/tags/{tag}", "-f", f"sha={commit}")
        if not check_ref():
            raise ValueError("GitHub did not expose the new producer tag")

    ref_exists = check_ref()
    fields = "assets,isDraft,isPrerelease,tagName,targetCommitish,url"
    args = ("--repo", remote, "--json", fields)
    current = gh("release", "view", tag, *args, missing="release not found")
    if current is None:
        if check_only:
            raise ValueError("GitHub raw release is missing")
        if not ref_exists:
            create_ref()
            ref_exists = True
        gh("release", "create", tag, "--repo", remote, "--target", commit, "--verify-tag", "--draft",
           "--prerelease", "--latest=false", "--title", f"AWS source-only data {tag}",
           "--notes", "AWS crawler input for the Pages workflow. Raw source assets only.")
        current = gh("release", "view", tag, *args)
    release = json.loads(current)
    missing_assets = release_missing_assets(release, manifest, expected)
    if release["isDraft"]:
        if check_only:
            raise ValueError("GitHub raw release is still a draft")
        if missing_assets:
            gh("release", "upload", tag, "--repo", remote,
               *(str(bundle / name) for name in missing_assets), timeout=3600)
        release = json.loads(gh("release", "view", tag, *args))
        if release_missing_assets(release, manifest, expected):
            raise ValueError("GitHub raw release is missing verified assets")
        if release["isDraft"]:
            if not check_ref():
                if ref_exists:
                    raise ValueError("GitHub producer tag disappeared before publication")
                create_ref()
            gh("release", "edit", tag, "--repo", remote, "--draft=false", "--prerelease", "--latest=false")
        release = json.loads(gh("release", "view", tag, *args))
    if release["isDraft"] or release_missing_assets(release, manifest, expected):
        raise ValueError("GitHub raw release is incomplete")
    if not check_ref():
        raise ValueError("published release has no producer tag")
    return {"tag": tag, "url": release["url"], "assets": sorted(expected)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    pack_parser = subparsers.add_parser("pack")
    pack_parser.add_argument("--tag", required=True)
    pack_parser.add_argument("--producer-commit", required=True)
    pack_parser.add_argument("--output", type=Path, required=True)
    for source in SOURCES:
        pack_parser.add_argument("--" + source, type=Path)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--tag", required=True)
    verify_parser.add_argument("bundle", type=Path)
    publish_parser = subparsers.add_parser("publish-github")
    publish_parser.add_argument("--tag", required=True)
    publish_parser.add_argument("--repo", required=True)
    publish_parser.add_argument("--check-only", action="store_true")
    publish_parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "pack":
            paths = {source: getattr(args, source) for source in SOURCES if getattr(args, source)}
            manifest = pack(args.output, args.tag, args.producer_commit, paths)
        elif args.command == "verify":
            manifest = verify(args.bundle, args.tag)
        else:
            manifest = publish_github(args.bundle, args.tag, args.repo, check_only=args.check_only)
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.error(str(error))
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
