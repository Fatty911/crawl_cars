#!/usr/bin/env python3
"""Cross-platform mesh sync for crawl_cars code mirrors, aws-raw releases, and Pages."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import aws_raw_bundle  # noqa: E402
import aws_raw_platforms  # noqa: E402
import pages_mesh_reconcile  # noqa: E402

DEFAULT_PLAN = Path("/etc/crawl-cars/aws-crawl-plan.json")
DEFAULT_STATE_DIR = Path("/opt/crawl-cars-runtime/mesh-state")
AWS_RAW_TAG_RE = re.compile(r"^aws-raw-[0-9]{8}T[0-9]{6}Z$")
MIRROR_REF = "refs/heads/mirror/main"
GITHUB_MIRROR_SOURCE_REF = "refs/heads/main"


class MeshSyncError(RuntimeError):
    """Raised when cross-platform mesh inspection or repair fails safely."""


def _default_git_user(host: str) -> str:
    return {"cnb.cool": "cnb", "gitlab.com": "oauth2", "gitee.com": "git"}.get(host, "git")


def load_plan(plan_path: Path) -> dict[str, Any]:
    return json.loads(plan_path.read_text(encoding="utf-8"))


def parse_git_credential(
    host: str,
    project: str,
    store: Path = aws_raw_platforms.CREDENTIAL_STORE,
) -> tuple[str, str]:
    """Read (username, secret) for host/project without exposing credentials."""
    if store.exists():
        expected_paths = {f"/{project}", f"/{project}.git"}
        for line in store.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            parsed = urllib.parse.urlsplit(raw)
            if parsed.hostname == host and parsed.path.rstrip("/") in expected_paths and parsed.password:
                user = urllib.parse.unquote(parsed.username or "") or _default_git_user(host)
                return user, urllib.parse.unquote(parsed.password)
    secret = aws_raw_platforms.credential(host, project)
    return _default_git_user(host), secret


def has_git_credential(host: str, project: str, store: Path = aws_raw_platforms.CREDENTIAL_STORE) -> bool:
    try:
        parse_git_credential(host, project, store=store)
        return True
    except Exception:
        return False


def run_git_with_askpass(
    args: list[str],
    *,
    username: str = "",
    password: str = "",
    cwd: Path | None = None,
    timeout: int = 180,
) -> str:
    """Run git using an ephemeral GIT_ASKPASS helper so secrets stay off CLI args."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    env.pop("GIT_ASKPASS", None)
    env.pop("SSH_ASKPASS", None)
    askpass_path: Path | None = None
    try:
        if password:
            fd, raw_path = tempfile.mkstemp(prefix="crawl-mesh-askpass-", suffix=".sh")
            os.close(fd)
            askpass_path = Path(raw_path)
            askpass_path.write_text(
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "  *Username*|*username*) printf '%s\\n' \"$MESH_GIT_USER\" ;;\n"
                "  *) printf '%s\\n' \"$MESH_GIT_PASS\" ;;\n"
                "esac\n",
                encoding="utf-8",
                newline="\n",
            )
            askpass_path.chmod(0o700)
            env["GIT_ASKPASS"] = str(askpass_path)
            env["MESH_GIT_USER"] = username or "git"
            env["MESH_GIT_PASS"] = password
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            raise MeshSyncError(f"git {' '.join(args[:2])} failed: {proc.stderr.strip()[:240]}")
        return proc.stdout
    finally:
        if askpass_path is not None and askpass_path.exists():
            askpass_path.unlink()


def get_remote_branch_sha(url: str, ref: str, *, username: str = "", password: str = "") -> str | None:
    out = run_git_with_askpass(["ls-remote", url, ref], username=username, password=password)
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == ref and re.fullmatch(r"[0-9a-f]{40}", parts[0]):
            return parts[0]
    return None


def _mirror_targets(plan: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Return [(platform, host, project_slug, https_git_url)] eligible for mirror/main sync."""
    platforms = plan.get("platforms", {})
    targets: list[tuple[str, str, str, str]] = []
    if "cnb" in platforms:
        repo = platforms["cnb"]["repo"]
        targets.append(("cnb", "cnb.cool", repo, f"https://cnb.cool/{repo}.git"))
    if "gitlab" in platforms:
        proj = platforms["gitlab"]["project"]
        targets.append(("gitlab", "gitlab.com", proj, f"https://gitlab.com/{proj}.git"))
    if "gitee" in platforms:
        proj = platforms["gitee"]["project"]
        if has_git_credential("gitee.com", proj):
            targets.append(("gitee", "gitee.com", proj, f"https://gitee.com/{proj}.git"))
    return targets


def _push_mirror_ref(gh_url: str, target_sha: str, target_url: str, username: str, password: str, repo_dir: Path | None) -> None:
    if not MIRROR_REF.startswith("refs/heads/mirror/"):
        raise MeshSyncError("Refusing to write non-mirror branch")
    with tempfile.TemporaryDirectory(prefix="crawl-mesh-git-") as tmp:
        work = Path(tmp) / "mirror.git"
        if repo_dir and (repo_dir / ".git").exists():
            run_git_with_askpass(["clone", "--bare", str(repo_dir), str(work)])
            run_git_with_askpass(["-C", str(work), "fetch", gh_url, f"+{GITHUB_MIRROR_SOURCE_REF}:{GITHUB_MIRROR_SOURCE_REF}"])
        else:
            run_git_with_askpass(["init", "--bare", str(work)])
            run_git_with_askpass(["-C", str(work), "fetch", gh_url, f"+{GITHUB_MIRROR_SOURCE_REF}:{GITHUB_MIRROR_SOURCE_REF}"])
        run_git_with_askpass(["-C", str(work), "cat-file", "-e", f"{target_sha}^{{commit}}"])
        run_git_with_askpass(
            ["-C", str(work), "push", "--force", target_url, f"{target_sha}:{MIRROR_REF}"],
            username=username,
            password=password,
        )


def sync_code_mirror(plan: dict[str, Any], *, apply: bool = False, repo_dir: Path | None = None) -> dict[str, Any]:
    gh_repo = plan["platforms"]["github"]["repo"]
    gh_url = f"https://github.com/{gh_repo}.git"
    target_sha = get_remote_branch_sha(gh_url, GITHUB_MIRROR_SOURCE_REF)
    if not target_sha:
        raise MeshSyncError(f"Could not resolve {GITHUB_MIRROR_SOURCE_REF} on {gh_repo}")

    results: dict[str, Any] = {}
    in_sync = True
    for name, host, project, url in _mirror_targets(plan):
        try:
            user, secret = parse_git_credential(host, project)
            remote_sha = get_remote_branch_sha(url, MIRROR_REF, username=user, password=secret)
            if remote_sha == target_sha:
                results[name] = {"status": "in_sync", "ref": MIRROR_REF, "sha": remote_sha}
            elif apply:
                _push_mirror_ref(gh_url, target_sha, url, user, secret, repo_dir)
                verified_sha = get_remote_branch_sha(url, MIRROR_REF, username=user, password=secret)
                ok = verified_sha == target_sha
                if not ok:
                    in_sync = False
                results[name] = {
                    "status": "synced" if ok else "mismatch",
                    "ref": MIRROR_REF,
                    "sha": verified_sha,
                    "target_sha": target_sha,
                }
            else:
                in_sync = False
                results[name] = {"status": "drifted", "ref": MIRROR_REF, "remote_sha": remote_sha, "target_sha": target_sha}
        except Exception as exc:
            in_sync = False
            results[name] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    return {"source": "github", "target_ref": GITHUB_MIRROR_SOURCE_REF, "target_sha": target_sha, "platforms": results, "in_sync": in_sync}


def _platform_api(platform: str, plan: dict[str, Any]):
    cfg = plan["platforms"][platform]
    if platform == "cnb":
        token = aws_raw_platforms.credential("cnb.cool", cfg["repo"])
        return aws_raw_platforms.Api(aws_raw_platforms.CNB, token)
    if platform == "gitlab":
        token = aws_raw_platforms.credential("gitlab.com", cfg["project"])
        return aws_raw_platforms.Api(aws_raw_platforms.GITLAB, token, gitlab=True)
    if platform == "gitee":
        token = aws_raw_platforms.credential("gitee.com", cfg["project"])
        return aws_raw_platforms.Api(aws_raw_platforms.GITEE, token)
    raise MeshSyncError(f"Unsupported API platform: {platform}")


def _extract_list(payload: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


SOURCE_FILENAMES = {entry[0] for entry in aws_raw_bundle.SOURCES.values()}


def _has_complete_raw_asset_names(names: set[str]) -> bool:
    return aws_raw_bundle.MANIFEST in names and bool(names & SOURCE_FILENAMES)


def _safe_asset_path(dest: Path, name: str) -> Path:
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise MeshSyncError(f"Unsafe asset filename: {name!r}")
    root = dest.resolve()
    candidate = (root / name).resolve()
    if candidate.parent != root:
        raise MeshSyncError(f"Unsafe asset path escapes destination: {name!r}")
    return candidate


def list_platform_raw_tags(platform: str, plan: dict[str, Any]) -> list[str]:
    cfg = plan["platforms"][platform]
    if platform == "github":
        raw_out = aws_raw_bundle.gh("api", f"repos/{cfg['repo']}/releases?per_page=30")
        items = _extract_list(json.loads(raw_out or "[]"))
        return sorted(
            item["tag_name"]
            for item in items
            if not item.get("draft")
            and AWS_RAW_TAG_RE.fullmatch(item.get("tag_name") or "")
            and _has_complete_raw_asset_names(
                {a.get("name") for a in item.get("assets") or [] if a.get("name") and a.get("state", "uploaded") == "uploaded"}
            )
        )
    api = _platform_api(platform, plan)
    if platform == "cnb":
        items = _extract_list(api.request("GET", f"/{cfg['repo']}/-/releases?page=1&page_size=30"), "releases", "items")
        return sorted(
            item["tag_name"]
            for item in items
            if not item.get("draft")
            and AWS_RAW_TAG_RE.fullmatch(item.get("tag_name") or "")
            and _has_complete_raw_asset_names({a.get("name") for a in item.get("assets") or [] if a.get("name")})
        )
    if platform == "gitlab":
        base = "/api/v4/projects/" + urllib.parse.quote(str(cfg["project"]), safe="")
        items = _extract_list(api.request("GET", f"{base}/releases?per_page=30"))
        return sorted(
            item["tag_name"]
            for item in items
            if AWS_RAW_TAG_RE.fullmatch(item.get("tag_name") or "")
            and _has_complete_raw_asset_names(
                {link.get("name") for link in item.get("assets", {}).get("links") or [] if link.get("name")}
            )
        )
    if platform == "gitee":
        base = f"/api/v5/repos/{cfg['project']}/releases"
        items = _extract_list(api.request("GET", f"{base}?per_page=30"))
        tags: list[str] = []
        for item in items:
            tag = item.get("tag_name") or ""
            if not AWS_RAW_TAG_RE.fullmatch(tag):
                continue
            assets = item.get("assets")
            rel_id = item.get("id")
            if not isinstance(assets, list) and type(rel_id) is int and rel_id > 0:
                assets = api.request("GET", f"{base}/{rel_id}/attach_files")
            names = {a.get("name") for a in (assets or []) if isinstance(a, dict) and a.get("name")}
            if _has_complete_raw_asset_names(names):
                tags.append(tag)
        return sorted(tags)
    raise MeshSyncError(f"Unknown platform: {platform}")


def download_raw_bundle(source_platform: str, plan: dict[str, Any], tag: str, dest: Path) -> dict[str, Any]:
    if not AWS_RAW_TAG_RE.fullmatch(tag):
        raise MeshSyncError(f"Invalid aws-raw release tag: {tag!r}")
    dest.mkdir(parents=True, exist_ok=True)
    cfg = plan["platforms"][source_platform]
    if source_platform == "github":
        aws_raw_bundle.gh("release", "download", tag, "--repo", f"github.com/{cfg['repo']}", "--dir", str(dest), timeout=1200)
        return aws_raw_bundle.verify(dest, tag)

    api = _platform_api(source_platform, plan)
    if source_platform == "cnb":
        release = api.request("GET", f"/{cfg['repo']}/-/releases/tags/{tag}")
        for asset in release.get("assets") or []:
            name = asset.get("name") or ""
            target_path = _safe_asset_path(dest, name)
            encoded_name = urllib.parse.quote(name, safe="")
            payload = api.request("GET", f"/{cfg['repo']}/-/releases/download/{tag}/{encoded_name}", binary=True)
            target_path.write_bytes(payload)
        return aws_raw_bundle.verify(dest, tag)

    if source_platform == "gitlab":
        base = "/api/v4/projects/" + urllib.parse.quote(str(cfg["project"]), safe="")
        release = api.request("GET", f"{base}/releases/{tag}")
        desc = json.loads(release["description"])
        uploads = desc["uploads"]
        for name, upload_id in uploads.items():
            if type(upload_id) is not int or upload_id <= 0:
                raise MeshSyncError(f"Invalid GitLab upload id for {name!r}: {upload_id!r}")
            target_path = _safe_asset_path(dest, name)
            payload = api.request("GET", f"{base}/uploads/{upload_id}", binary=True)
            target_path.write_bytes(payload)
        return aws_raw_bundle.verify(dest, tag)

    if source_platform == "gitee":
        base = f"/api/v5/repos/{cfg['project']}/releases"
        release = api.request("GET", f"{base}/tags/{tag}")
        release_id = release.get("id")
        if type(release_id) is not int or release_id <= 0:
            raise MeshSyncError(f"Invalid Gitee release id: {release_id!r}")
        attachments_path = f"{base}/{release_id}/attach_files"
        for asset in api.request("GET", attachments_path):
            name = asset.get("name") or ""
            asset_id = asset.get("id")
            if type(asset_id) is not int or asset_id <= 0:
                raise MeshSyncError(f"Invalid Gitee attachment id for {name!r}: {asset_id!r}")
            target_path = _safe_asset_path(dest, name)
            payload = api.request("GET", f"{attachments_path}/{asset_id}/download", binary=True)
            target_path.write_bytes(payload)
        return aws_raw_bundle.verify(dest, tag)

    raise MeshSyncError(f"Unsupported source platform: {source_platform}")


def _journal_access(state_dir: Path, platform: str, tag: str) -> tuple[dict[str, Any], Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / f"{platform}-{tag}.journal.json"
    journal = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def save() -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    return journal, save


def publish_raw_bundle(
    target_platform: str,
    plan: dict[str, Any],
    bundle: Path,
    tag: str,
    producer_commit: str,
    state_dir: Path,
) -> dict[str, Any]:
    if not AWS_RAW_TAG_RE.fullmatch(tag):
        raise MeshSyncError(f"Invalid aws-raw release tag: {tag!r}")
    cfg = plan["platforms"][target_platform]
    journal, save = _journal_access(state_dir, target_platform, tag)
    if target_platform == "github":
        return aws_raw_bundle.publish_github(bundle, tag, cfg["repo"], journal=journal, save=save)
    api = _platform_api(target_platform, plan)
    storage = cfg["storage"]
    if target_platform == "cnb":
        return aws_raw_platforms.mirror_cnb(api, cfg["repo"], bundle, tag, producer_commit, storage, journal, save)
    if target_platform == "gitlab":
        return aws_raw_platforms.mirror_gitlab(api, cfg["project"], bundle, tag, producer_commit, storage, journal, save)
    if target_platform == "gitee":
        return aws_raw_platforms.mirror_gitee(api, cfg["project"], bundle, tag, producer_commit, storage, journal, save)
    raise MeshSyncError(f"Unsupported target platform: {target_platform}")


def _raw_platforms(plan: dict[str, Any]) -> list[str]:
    platforms = [p for p in ("github", "cnb", "gitlab") if p in plan.get("platforms", {})]
    if "gitee" in plan.get("platforms", {}) and has_git_credential("gitee.com", plan["platforms"]["gitee"]["project"]):
        platforms.append("gitee")
    return platforms


def sync_raw_releases(plan: dict[str, Any], *, apply: bool = False, state_dir: Path = DEFAULT_STATE_DIR) -> dict[str, Any]:
    tags_by_platform: dict[str, list[str]] = {}
    errors: dict[str, str] = {}
    for platform in _raw_platforms(plan):
        try:
            tags_by_platform[platform] = list_platform_raw_tags(platform, plan)
        except Exception as exc:
            errors[platform] = f"{type(exc).__name__}: {exc}"

    all_tags = sorted({tag for tags in tags_by_platform.values() for tag in tags})
    if not all_tags:
        return {"latest_tag": "", "tags_by_platform": tags_by_platform, "errors": errors, "backfilled": {}, "in_sync": not errors}

    latest_tag = all_tags[-1]
    sources = [p for p, tags in tags_by_platform.items() if latest_tag in tags]
    missing = [p for p, tags in tags_by_platform.items() if latest_tag not in tags]
    backfilled: dict[str, Any] = {}

    if apply and missing and sources:
        download_warnings: dict[str, str] = {}
        with tempfile.TemporaryDirectory(prefix="crawl-mesh-raw-") as tmp:
            bundle_root = Path(tmp) / latest_tag
            bundle_dir: Path | None = None
            manifest: dict[str, Any] | None = None
            chosen_source = ""
            for src in sources:
                attempt_dir = bundle_root / src
                try:
                    manifest = download_raw_bundle(src, plan, latest_tag, attempt_dir)
                    bundle_dir = attempt_dir
                    chosen_source = src
                    break
                except Exception as exc:
                    download_warnings[src] = f"{type(exc).__name__}: {exc}"
            if manifest is None or bundle_dir is None:
                errors.update({f"download:{k}": v for k, v in download_warnings.items()})
                return {
                    "latest_tag": latest_tag,
                    "sources": sources,
                    "missing": missing,
                    "errors": errors,
                    "backfilled": backfilled,
                    "in_sync": False,
                }
            producer = manifest["producer_commit"]
            for dst in list(missing):
                try:
                    backfilled[dst] = {
                        "source": chosen_source,
                        "receipt": publish_raw_bundle(dst, plan, bundle_dir, latest_tag, producer, state_dir),
                    }
                    missing.remove(dst)
                except Exception as exc:
                    errors[f"publish:{dst}"] = f"{type(exc).__name__}: {exc}"
        if download_warnings:
            return {
                "latest_tag": latest_tag,
                "sources": sources,
                "missing": missing,
                "download_warnings": download_warnings,
                "errors": errors,
                "backfilled": backfilled,
                "in_sync": not errors and not missing,
            }

    return {
        "latest_tag": latest_tag,
        "sources": sources,
        "missing": missing,
        "errors": errors,
        "backfilled": backfilled,
        "in_sync": not errors and not missing,
    }


def run_mesh(
    plan_path: Path,
    *,
    apply: bool = False,
    skip_code: bool = False,
    skip_raw: bool = False,
    skip_pages: bool = False,
    state_dir: Path = DEFAULT_STATE_DIR,
    repo_dir: Path | None = None,
) -> dict[str, Any]:
    plan = load_plan(plan_path)
    report: dict[str, Any] = {"mode": "apply" if apply else "check"}
    checks_sync: list[bool] = []
    checks_apply: list[bool] = []
    if not skip_code:
        code_res = sync_code_mirror(plan, apply=apply, repo_dir=repo_dir)
        report["code_mesh"] = code_res
        ok = bool(code_res.get("in_sync"))
        checks_sync.append(ok)
        checks_apply.append(ok)
    if not skip_raw:
        raw_res = sync_raw_releases(plan, apply=apply, state_dir=state_dir)
        report["raw_mesh"] = raw_res
        ok = bool(raw_res.get("in_sync"))
        checks_sync.append(ok)
        checks_apply.append(ok)
    if not skip_pages:
        pages_res = pages_mesh_reconcile.compare_sites()
        if apply and not pages_res.get("in_sync"):
            gh_repo = plan["platforms"]["github"]["repo"]
            try:
                tag = pages_mesh_reconcile.resolve_latest_immutable_tag(gh_repo)
                pages_res["triggered"] = pages_mesh_reconcile.dispatch_reconcile(pages_res, gh_repo, latest_tag=tag)
            except Exception as exc:
                pages_res["dispatch_error"] = f"{type(exc).__name__}: {exc}"
        report["pages_mesh"] = pages_res
        pages_sync = bool(pages_res.get("in_sync"))
        pages_dispatched = bool(pages_res.get("triggered")) and not pages_res.get("dispatch_error")
        checks_sync.append(pages_sync)
        checks_apply.append(pages_sync or pages_dispatched)
    report["in_sync"] = all(checks_sync)
    report["apply_ok"] = all(checks_apply)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--repo-dir", type=Path, default=None)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--skip-code", action="store_true")
    parser.add_argument("--skip-raw", action="store_true")
    parser.add_argument("--skip-pages", action="store_true")
    args = parser.parse_args()

    report = run_mesh(
        args.plan,
        apply=args.apply,
        skip_code=args.skip_code,
        skip_raw=args.skip_raw,
        skip_pages=args.skip_pages,
        state_dir=args.state_dir,
        repo_dir=args.repo_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.check and not report["in_sync"]:
        return 1
    if args.apply and not report.get("apply_ok", report["in_sync"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
