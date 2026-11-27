#!/usr/bin/env python3
"""AWS source-only collection, immutable mirrors and provenance-bound processing."""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from urllib.parse import quote, urlencode, urlsplit
from datetime import datetime, timezone
from pathlib import Path

from scripts import aws_raw_bundle as raw
from scripts import aws_raw_platforms as platforms
from scripts import plan_aws_crawl_priority as priority
from scripts.prepare_cnb_pages import manifest_assets, safe_path


ROOT = Path(__file__).resolve().parents[1]
PLAN = Path("/etc/crawl-cars/aws-crawl-plan.json")
CNB_BUILD_CREDENTIAL = Path("/etc/crawl-cars/cnb-build-credential.json")
STATE_ROOT = Path("/var/lib/crawl-cars/aws-pipeline")
WORKFLOW = "remerge-and-publish.yml"
PAGE_MIRRORS = {
    "cloudflare": ("cnb-pages.yml", "cloudflare-pages", ("https://cars2.jiucai.eu.org/",)),
    "codeberg": ("codeberg-pages.yml", "codeberg-pages",
                 ("https://cars3.jiucai.eu.org/", "https://xuerui911.codeberg.page/crawl-cars/")),
}
GITLAB_PAGES_BASE = "https://crawl-cars-5b0684.gitlab.io/"
CNB_ACCEPTANCE_STAGES = ("验收AWS原始镜像（不爬取、不自驱修复）", "验收已处理 Pages 制品")
PROCESSED_RELEASE = r"cnb-data-[0-9]{8}-remerged-verified-r[1-9][0-9]*a[1-9][0-9]*"
SOURCES = {
    "autohome": ("scripts.collect_aws_autohome", "autohome-source.json", "scripts/test_autohome.py"),
    "dongchedi": ("scripts.refresh_aws_dongchedi", "dongchedi-source.json", "scripts/crawl_dongchedi.py"),
    "yiche": ("scripts.collect_aws_yiche", "yiche-source.json", "scripts/crawl_yiche.py"),
}
REQUIRED_SOURCES = {
    "scripts/aws_crawl_pipeline.py", "scripts/aws_raw_platforms.py", "scripts/aws_raw_bundle.py",
    "scripts/aws_crawl_runtime.py", "scripts/plan_aws_crawl_priority.py",
    "scripts/refresh_aws_autohome_ranks.py", "scripts/normalize_autohome_priority_ranks.py",
    "scripts/collect_aws_autohome.py", "scripts/refresh_aws_dongchedi.py",
    "scripts/collect_aws_yiche.py", "scripts/test_autohome.py", "scripts/crawl_dongchedi.py",
    "scripts/crawl_yiche.py", "crawl_state/__init__.py", "crawl_state/registry.py",
    "requirements.txt", ".github/workflows/" + WORKFLOW,
    "config/filter_conditions.json", "docs/filter_conditions.json", "docs/app.js",
    "config/source_identity_evidence.json",
}


class PipelineError(RuntimeError):
    pass


class Pending(PipelineError):
    pass


class ReadbackPermissionDenied(PipelineError):
    """An explicit readback authorization denial, never a visibility delay."""
    pass


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


_NO_DIGEST = object()


def private_json(path, expected=_NO_DIGEST):
    path = Path(path)
    if path.is_symlink() or path.absolute() != path.resolve() or not path.is_file():
        raise PipelineError("private reference must be a regular absolute file without symlinks")
    stat = path.stat()
    if stat.st_uid not in (0, os.geteuid()) or stat.st_mode & 0o077 or stat.st_size > 1024 * 1024:
        raise PipelineError("private plan/manifest ownership, mode or size is invalid")
    payload = path.read_bytes()
    if expected is not _NO_DIGEST:
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise PipelineError("approved private reference digest must be a 64-hex sha256")
        if hashlib.sha256(payload).hexdigest() != expected:
            raise PipelineError("approved private reference changed")
    return json.loads(payload)


def atomic_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix=".pipeline-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def git(repo, *args):
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, check=False)
    if result.returncode:
        raise PipelineError("frozen source Git verification failed")
    return result.stdout


def validate_plan(path, repo=ROOT):
    plan = private_json(path)
    if plan.get("schema") != 1 or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", plan.get("plan_id", "")):
        raise PipelineError("invalid plan identity")
    producer = plan.get("producer_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", producer) or git(repo, "rev-parse", "HEAD").decode().strip() != producer:
        raise PipelineError("checkout is not the frozen producer commit")
    python = plan.get("python", {})
    executable = Path(sys.executable).resolve()
    if python.get("path") != str(executable) or python.get("sha256") != digest(executable):
        raise PipelineError("the approved existing Python changed")
    reference = plan.get("source_manifest", {})
    if not isinstance(reference, dict) or not {"path", "sha256"} <= reference.keys():
        raise PipelineError("source manifest reference must specify path and sha256")
    manifest = private_json(reference["path"], reference["sha256"])
    files = manifest.get("files", {})
    source_paths = git(repo, "ls-tree", "-r", "--name-only", producer, "--", "scripts", "crawl_state")
    tracked_python = {name for name in source_paths.decode().splitlines() if name.endswith(".py")}
    if manifest.get("producer_commit") != producer or not (REQUIRED_SOURCES | tracked_python) <= files.keys():
        raise PipelineError("source manifest omits required executable/consumer dependencies")
    for name, sha in files.items():
        source = repo / name
        if (Path(name).is_absolute() or ".." in Path(name).parts or source.is_symlink()
                or not source.is_file() or not re.fullmatch(r"[0-9a-f]{64}", sha)
                or digest(source) != sha or hashlib.sha256(git(repo, "show", producer + ":" + name)).hexdigest() != sha):
            raise PipelineError("relevant source is dirty, untracked or differs from the approved commit")
    workflow_text = (repo / (".github/workflows/" + WORKFLOW)).read_text()
    if "--original-only" in workflow_text or "--pattern 'merged_*.json'" in workflow_text:
        raise PipelineError("AWS-only verified baseline follow-up is not installed; activation remains blocked")
    mode = plan.get("mode", "debug")
    if mode not in ("debug", "aws-production"):
        raise PipelineError("unsupported collection mode")
    targets = plan.get("targets", {})
    if not targets or not targets.keys() <= SOURCES.keys():
        raise PipelineError("plan must select known explicit sources")
    caps = []
    for source, entry in targets.items():
        limit = entry.get("row_limit", 30)
        runtime = entry.get("runtime_seconds", 240)
        if type(limit) is not int or not 0 <= limit <= 30 or type(runtime) is not int or not 60 <= runtime <= 3600:
            raise PipelineError("invalid collection cap")
        caps.append(limit)
        ranking = entry.get("priority")
        if ranking is not None:
            if (not isinstance(ranking, dict) or not {"catalog_path", "catalog_sha256"} <= ranking.keys()
                    or not ranking.keys() <= {"catalog_path", "catalog_sha256", "rankings_path", "refresh"}
                    or "path" in entry or "sha256" in entry or not limit
                    or type(ranking.get("refresh", False)) is not bool
                    or ranking.get("refresh") and (source != "autohome" or not ranking.get("rankings_path"))):
                raise PipelineError("priority targets require a pinned catalog and a positive row cap")
            catalog = private_json(ranking["catalog_path"], ranking["catalog_sha256"])
            if catalog.get("source") != source or not catalog.get("targets"):
                raise PipelineError("priority catalog source is not the configured collector")
            continue
        values = private_json(entry["path"], entry["sha256"])
        if Path(entry["path"]).stat().st_size > 65536:
            raise PipelineError("target manifest exceeds the collector's existing size bound")
        if not 1 <= len(values) <= 30:
            raise PipelineError("target manifest must contain 1 to 30 explicit targets")
        if source == "yiche":
            if not isinstance(values, dict):
                raise PipelineError("Yiche manifest must map explicit URLs to identities")
            for url, identity in values.items():
                if (not re.fullmatch(r"https://car\.yiche\.com/[a-z0-9-]+/peizhi/", url)
                        or not isinstance(identity, dict) or set(identity) != {"serial_id", "series", "brand"}
                        or not re.fullmatch(r"[1-9][0-9]{0,9}", identity.get("serial_id", ""))
                        or not all(isinstance(x, str) and x.strip() for x in identity.values())):
                    raise PipelineError("invalid Yiche target")
        else:
            if not isinstance(values, list):
                raise PipelineError("source target manifest must be an array")
            required = {"car_id", "series", "brand"} if source == "autohome" else {"id", "name", "brand"}
            seen = set()
            for identity in values:
                key = "car_id" if source == "autohome" else "id"
                if (not isinstance(identity, dict) or not required <= identity.keys()
                        or not identity.keys() <= (required | ({"spec_id"} if source == "autohome" else set()))
                        or not all(isinstance(x, str) and x.strip() for x in identity.values())
                        or not re.fullmatch(r"[1-9][0-9]{0,9}", identity.get(key, ""))
                        or (identity[key], identity.get("spec_id")) in seen):
                    raise PipelineError("invalid or duplicate source target")
                seen.add((identity[key], identity.get("spec_id")))
    if mode == "debug" and (0 in caps or sum(caps) > 30):
        raise PipelineError("debug collection requires a positive total row cap <=30")
    network = plan.get("network", {})
    address = ipaddress.ip_address(network.get("probe_ip", ""))
    if address.version != 4 or address.is_loopback or address.is_unspecified or not 1 <= network.get("probe_port", 22) <= 65535:
        raise PipelineError("invalid direct-denial control probe")
    remotes = plan.get("platforms", {})
    required_mirrors = {"github", "cnb", "gitlab"}
    if (not required_mirrors <= remotes.keys() <= required_mirrors | {"gitee"}
            or remotes["github"].get("repo") != "Fatty911/crawl_cars"):
        raise PipelineError("required raw mirrors or platform names differ from the approved configuration")
    if "gitee" in remotes and (
            set(remotes["gitee"]) != {"project", "storage"} or remotes["gitee"]["project"] != platforms.GITEE_PROJECT):
        raise PipelineError("Gitee project differs from the approved storage repository")
    if remotes["cnb"].get("repo") != "xuerui911-mirror/crawl_cars":
        raise PipelineError("CNB repository differs from the approved storage repository")
    for platform in remotes.keys() - {"github"}:
        storage = remotes[platform].get("storage", {})
        if storage.get("ref") != "main" or not re.fullmatch(r"[0-9a-f]{40}", storage.get("commit", "")):
            raise PipelineError("native storage ref must have its own pinned commit")
    if remotes["gitlab"].get("project") != "xuerui911/crawl_cars":
        raise PipelineError("GitLab project differs from the approved storage repository")
    cnb_acceptance = remotes["cnb"].get("acceptance")
    if cnb_acceptance is not None and (
            not isinstance(cnb_acceptance, dict)
            or not {"ci_sha256"} <= cnb_acceptance.keys() <= {"ci_sha256", "credential"}
            or ("credential" in cnb_acceptance and cnb_acceptance["credential"] != "dedicated")
            or not re.fullmatch(r"[0-9a-f]{64}", cnb_acceptance.get("ci_sha256", ""))):
        raise PipelineError("CNB acceptance requires a pinned data-only CI file and a supported credential source")
    native_pages = remotes["gitlab"].get("pages")
    if native_pages is not None and (
            not isinstance(native_pages, dict) or set(native_pages) != {"url", "ci_sha256"}
            or native_pages.get("url") != GITLAB_PAGES_BASE
            or not re.fullmatch(r"[0-9a-f]{64}", native_pages.get("ci_sha256", ""))):
        raise PipelineError("GitLab Pages requires the verified project origin and a pinned data-only CI file")
    process = plan.get("processing", {})
    mirrors = process.get("page_mirrors", [])
    if (not isinstance(mirrors, list) or any(not isinstance(name, str) or name not in PAGE_MIRRORS for name in mirrors)
            or len(mirrors) != len(set(mirrors))
            or any(".github/workflows/" + PAGE_MIRRORS[name][0] not in files for name in mirrors)):
        raise PipelineError("Pages mirror workflows must be explicitly selected and pinned")
    if (process.get("commit") != producer or process.get("ref") != "main"
            or process.get("workflow") != WORKFLOW or process.get("pages_base") != "https://cars.jiucai.eu.org/"
            or process.get("workflow_sha256") != files[".github/workflows/" + WORKFLOW]):
        raise PipelineError("processing consumer/ref/Pages identity differs from approved source")
    fingerprint = {"plan_sha256": digest(Path(path)), "sources": files,
                   "source_manifest_sha256": reference["sha256"],
                   "targets": {key: (value["priority"]["catalog_sha256"] if value.get("priority") is not None else value["sha256"])
                               for key, value in targets.items()}}
    return plan, fingerprint


def assert_aws(mode):
    if os.geteuid() != 0 or Path("/sys/devices/virtual/dmi/id/sys_vendor").read_text().strip() != "Amazon EC2":
        raise PipelineError("collection application is restricted to the authorized AWS EC2 host")
    if mode == "aws-production":
        cgroup = Path("/proc/self/cgroup").read_text()
        if ("/crawl-cars-aws-pipeline.service" not in cgroup or not os.getenv("INVOCATION_ID")
                or os.getenv("AWS_CRAWL_PRODUCTION_AUTHORIZED") != "1"):
            raise PipelineError("unbounded production requires the approved AWS systemd service")


def collector_command(source, entry, target, output, network):
    command = [sys.executable, "-m", SOURCES[source][0], "--output", str(output),
               "--probe-ip", network["probe_ip"], "--probe-port", str(network.get("probe_port", 22)),
               "--runtime-seconds", str(entry.get("runtime_seconds", 240))]
    limit = entry.get("row_limit", 30)
    if source == "yiche":
        values = json.loads(target.read_bytes())
        command += ["--target-manifest", str(target), "--max-series", str(len(values)), "--max-rows", str(limit)]
        for url in values:
            command += ["--series", url]
    else:
        command += ["--targets", str(target), "--max-trims", str(limit)]
    return command


class Actions:
    def __init__(self, repo):
        self.base = "repos/" + repo

    def api(self, method, path, body=None):
        command = ["gh", "api", "--hostname", "github.com", "--method", method,
                   "-H", "X-GitHub-Api-Version: 2026-03-10", self.base + path]
        if body is not None:
            command += ["--input", "-"]
        result = subprocess.run(command, input=json.dumps(body) if body is not None else None,
                                capture_output=True, text=True, timeout=120, check=False)
        if result.returncode:
            raise Pending("GitHub API failed; durable dispatch state is retained")
        return json.loads(result.stdout) if result.stdout.strip() else None


def page_get(url, maximum):
    platforms.https_url(url)
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "aws-crawl-provenance"})
    try:
        with urllib.request.build_opener(platforms.NoRedirect()).open(request, timeout=30) as response:
            payload = response.read(maximum + 1)
            if response.status != 200 or not payload or len(payload) > maximum:
                raise PipelineError("Pages health response is empty, oversized or unsuccessful")
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise ReadbackPermissionDenied("Pages readback authorization denied") from None
        raise Pending("Pages readback unavailable; cursor was not advanced") from None
    except OSError:
        raise Pending("Pages readback unavailable; cursor was not advanced") from None
    return payload


def verify_page_data(manifest, base, get_page):
    """Read back what Pages actually serves, including the filtered snapshot."""
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise Pending("Pages data asset inventory is unavailable")
    try:
        expected = {}
        for name, metadata in manifest_assets(files):
            if not metadata:
                continue
            entry = (metadata.get("sha256"), metadata.get("size"))
            if name in expected and expected[name] != entry:
                raise ValueError("conflicting asset descriptors")
            expected[name] = entry
        references = []
        for field in ("latestJsonChunks", "filteredJsonChunks"):
            chunks = files.get(field)
            if chunks is None:
                continue
            if not isinstance(chunks, list):
                raise ValueError("invalid Pages chunk descriptors")
            paths = [entry["path"] for entry in chunks]
            if len(set(paths)) != len(paths):
                raise ValueError("duplicate Pages chunk references")
            references.extend(paths)
        if not files.get("latestJsonChunks") and "latestJson" not in files:
            raise ValueError("missing latest Pages data reference")
        references.append(files["filteredJson"])
        references.extend(files[field] for field in ("latestJson", "latestCsv", "filteredCsv") if field in files)
        references = list(dict.fromkeys(references))
        if len(references) > 128:
            raise ValueError("excessive Pages readback references")
        assets, total = {}, 0
        for name in references:
            path = safe_path(name).as_posix()
            if not path.startswith("data/"):
                raise ValueError("data reference escaped the data directory")
            digest, size = expected[name]
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("missing exact asset digest")
            if type(size) is not int or not 0 < size <= raw.MAX_ASSET_BYTES:
                raise ValueError("invalid asset byte bound")
            total += size
            if total > 512 * 1024 * 1024:
                raise ValueError("data readback exceeds total byte budget")
            assets[path] = {"sha256": digest, "size": size}
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise Pending("Pages data asset inventory is invalid") from error
    for name, entry in assets.items():
        try:
            payload = get_page(base + quote(name, safe="/"), entry["size"])
        except ReadbackPermissionDenied:
            raise
        except PipelineError as error:
            raise Pending("Pages data asset is not yet available") from error
        if len(payload) != entry["size"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            raise Pending("Pages data asset bytes differ from the verified manifest: " + name)
    return assets


def verified_archive(actions, manifest, payload):
    provenance = manifest.get("provenance", {})
    date = manifest.get("date", "")
    run_id = str(provenance.get("workflowRunId", ""))
    attempt = str(provenance.get("workflowRunAttempt", ""))
    if (not isinstance(date, str) or not re.fullmatch(r"[0-9]{8}", date)
            or not re.fullmatch(r"[1-9][0-9]{0,17}", run_id)
            or not re.fullmatch(r"[1-9][0-9]{0,5}", attempt)):
        raise Pending("live Pages has no exact verified archive identity")
    tag = f"cnb-data-{date}-remerged-verified-r{run_id}a{attempt}"
    release = actions.api("GET", "/releases/tags/" + tag)
    if (release.get("tag_name") != tag or release.get("immutable") is not True
            or release.get("draft") is not False or release.get("prerelease") is not False):
        raise Pending("the exact Pages archive is not an immutable published release")
    required = {"manifest.json", "verified-site.zip"}
    assets = [item for item in release.get("assets", []) if item.get("name") in required]
    if (len(assets) != len(required) or {item["name"] for item in assets} != required
            or any(item.get("state") != "uploaded" or type(item.get("size")) is not int
                   or item["size"] <= 0 or not re.fullmatch(r"sha256:[0-9a-f]{64}", item.get("digest") or "")
                   for item in assets)):
        raise Pending("the exact Pages archive lacks completed immutable assets")
    live_sha = hashlib.sha256(payload).hexdigest()
    entry = next(item for item in assets if item["name"] == "manifest.json")
    if entry["size"] != len(payload) or entry["digest"] != "sha256:" + live_sha:
        raise Pending("live Pages manifest bytes differ from the exact verified archive")
    return tag, live_sha


def advance_processing(state, plan, actions, save, get_page=page_get):
    process = plan["processing"]
    tag, producer = state["tag"], plan["producer_commit"]
    dispatch = state.setdefault("dispatch", {})
    remotes = plan.get("platforms", {})
    native_followup = (remotes.get("gitlab", {}).get("pages") or remotes.get("cnb", {}).get("acceptance")
                       or process.get("page_mirrors"))
    if native_followup and dispatch.get("status") == "accepted":
        return
    if not dispatch:
        if actions.api("GET", "/git/ref/heads/main")["object"]["sha"] != process["commit"]:
            raise PipelineError("processing main advanced; the frozen plan cannot dispatch")
        if actions.api("GET", "/git/ref/tags/" + tag)["object"]["sha"] != producer:
            raise PipelineError("raw tag moved away from the producer")
        manifest_url = process["pages_base"] + "data/manifest.json"
        baseline_payload = get_page(manifest_url, 1024 * 1024)
        baseline_manifest = json.loads(baseline_payload)
        if baseline_manifest.get("provenance", {}).get("awsRawRelease") == tag:
            raise Pending("live Pages already includes this raw tag; reconcile its existing dispatch")
        baseline_tag, baseline_sha = verified_archive(actions, baseline_manifest, baseline_payload)
        runs = actions.api("GET", "/actions/workflows/" + WORKFLOW + "/runs?event=workflow_dispatch&per_page=100")
        if get_page(manifest_url, 1024 * 1024) != baseline_payload:
            raise Pending("live Pages advanced during dispatch preflight")
        dispatch.update(status="pending", before_ids=[x["id"] for x in runs["workflow_runs"]],
                        ref="main", head_sha=process["commit"], raw_tag=tag,
                        baseline_tag=baseline_tag, baseline_manifest_sha256=baseline_sha)
        save()  # Commit intent before POST; retries never blindly send it again.
        response = actions.api("POST", "/actions/workflows/" + WORKFLOW + "/dispatches",
                               {"ref": "main", "inputs": {"aws_raw_release": tag, "release_tag": baseline_tag}})
        if not response or type(response.get("workflow_run_id")) is not int:
            raise Pending("dispatch response has no run ID; reconcile recorded before/after IDs without redispatch")
        dispatch["run_id"] = response["workflow_run_id"]
        save()
    if "run_id" not in dispatch:
        runs = actions.api("GET", "/actions/workflows/" + WORKFLOW + "/runs?event=workflow_dispatch&per_page=100")
        dispatch["after_ids"] = [x["id"] for x in runs["workflow_runs"]]
        candidates = [x for x in runs["workflow_runs"] if x["id"] not in dispatch["before_ids"]
                      and x.get("head_sha") == process["commit"] and x.get("head_branch") == "main"]
        dispatch["candidate_ids"] = [x["id"] for x in candidates]
        save()
        evidence = json.loads(get_page(process["pages_base"] + "data/manifest.json", 1024 * 1024)).get("provenance", {})
        proven = [x for x in candidates if str(x["id"]) == str(evidence.get("workflowRunId", ""))
                  and x.get("status") == "completed" and x.get("conclusion") == "success"
                  and str(x.get("run_attempt")) == str(evidence.get("workflowRunAttempt", ""))]
        if (len(proven) != 1 or evidence.get("awsRawRelease") != tag
                or evidence.get("awsRawManifestSha256") != state["raw_manifest_sha256"]
                or evidence.get("awsRawProducerCommit") != producer or evidence.get("codeCommit") != process["commit"]):
            raise Pending("dispatch identity uncertain; candidate IDs recorded, automatic redispatch forbidden")
        dispatch["run_id"] = proven[0]["id"]
        dispatch["reconciled_from_pages_provenance"] = True
        save()
    run = actions.api("GET", "/actions/runs/" + str(dispatch["run_id"]))
    if (run.get("id") != dispatch["run_id"] or run.get("event") != "workflow_dispatch"
            or run.get("head_sha") != process["commit"] or run.get("head_branch") != "main"
            or str(run.get("path", "")).split("@", 1)[0] != ".github/workflows/" + WORKFLOW):
        raise PipelineError("processing run identity differs from the exact dispatch")
    if run.get("status") != "completed":
        raise Pending("exact processing run is still pending")
    if run.get("conclusion") != "success":
        raise PipelineError("exact processing run failed; cursor was not advanced")
    payload = get_page(process["pages_base"] + "data/manifest.json", 1024 * 1024)
    manifest = json.loads(payload)
    provenance = manifest.get("provenance", {})
    if (provenance.get("awsRawRelease") != tag or provenance.get("awsRawManifestSha256") != state["raw_manifest_sha256"]
            or provenance.get("codeCommit") != process["commit"]
            or provenance.get("awsRawProducerCommit") != producer
            or str(provenance.get("workflowRunId", "")) != str(dispatch["run_id"])
            or str(provenance.get("workflowRunAttempt", "")) != str(run.get("run_attempt"))
            or type(manifest.get("rowCount")) is not int or manifest["rowCount"] <= 0
            or type(manifest.get("filteredRowCount")) is not int or manifest["filteredRowCount"] <= 0):
        raise Pending("Pages provenance does not yet bind this raw tag/manifest/processing commit")
    if dispatch.get("baseline_tag") and provenance.get("inputRelease") != dispatch["baseline_tag"]:
        raise Pending("Pages input baseline differs from the durable dispatch")
    processed_tag, processed_sha = verified_archive(actions, manifest, payload)
    assets = verify_page_data(manifest, process["pages_base"], get_page)
    health = get_page(process["pages_base"] + "index.html", 1024 * 1024)
    dispatch.update(status="accepted", conclusion="success", pages_manifest_sha256=processed_sha,
                    processed_release=processed_tag, row_count=manifest["rowCount"],
                    filtered_row_count=manifest["filteredRowCount"],
                    pages_health_sha256=hashlib.sha256(health).hexdigest(), verified_data_assets=assets,
                    run_attempt=run.get("run_attempt"))
    if not native_followup:
        state["complete"] = True
    save()


def advance_public_page_mirrors(state, mirrors, producer, save, get_page=page_get):
    if not mirrors:
        return
    primary = state["dispatch"]
    if primary.get("status") != "accepted":
        raise PipelineError("Pages mirror readback requires the accepted primary release")
    journal = state.setdefault("public_page_mirrors", {})
    for name in mirrors:
        _, platform, sites = PAGE_MIRRORS[name]
        for site in sites:
            if site in journal:
                continue
            payload = get_page(site + "data/manifest.json", 1024 * 1024)
            manifest = json.loads(payload)
            publication = manifest.get("publication", {})
            provenance = manifest.get("provenance", {})
            if (publication.get("platform") != platform
                    or publication.get("sourceVerifiedRelease") != primary["processed_release"]
                    or publication.get("sourceManifestSha256") != primary["pages_manifest_sha256"]
                    or provenance.get("awsRawRelease") != state["tag"]
                    or provenance.get("awsRawProducerCommit") != producer
                    or provenance.get("awsRawManifestSha256") != state["raw_manifest_sha256"]
                    or manifest.get("rowCount") != primary["row_count"]
                    or manifest.get("filteredRowCount") != primary["filtered_row_count"]):
                raise Pending("Pages mirror has not served the exact processed batch: " + name)
            assets = verify_page_data(manifest, site, get_page)
            expected_assets = primary.get("verified_data_assets")
            if expected_assets is not None and assets != expected_assets:
                raise Pending("Pages mirror data assets differ from the accepted primary release: " + name)
            health = get_page(site, 1024 * 1024)
            journal[site] = {"manifest_sha256": hashlib.sha256(payload).hexdigest(),
                             "health_sha256": hashlib.sha256(health).hexdigest(), "assets": assets}
            save()


def private_gitlab_page_reader(base, token):
    if base != GITLAB_PAGES_BASE:
        raise PipelineError("GitLab Pages readback origin is not pinned")
    target = urlsplit(base)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), platforms.NoRedirect())

    def get(url, maximum):
        supplied = urlsplit(url)
        if (supplied.scheme != target.scheme or supplied.netloc != target.netloc
                or not supplied.path.startswith(target.path) or supplied.query or supplied.fragment):
            raise PipelineError("GitLab Pages readback cannot leave the verified origin")
        request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token,
                    "Cache-Control": "no-cache", "User-Agent": "aws-crawl-provenance"})
        try:
            with opener.open(request, timeout=30) as response:
                payload = response.read(maximum + 1)
                if response.status != 200 or not payload or len(payload) > maximum:
                    raise Pending("GitLab Pages returned an unsuccessful or oversized response")
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                raise ReadbackPermissionDenied("GitLab Pages readback authorization denied") from None
            raise Pending("authenticated GitLab Pages readback unavailable") from None
        except OSError:
            raise Pending("authenticated GitLab Pages readback unavailable") from None
        return payload

    return get


def advance_gitlab_pages(state, config, producer_commit, api, save, get_page):
    primary = state.get("dispatch", {})
    if (primary.get("status") != "accepted"
            or not re.fullmatch(PROCESSED_RELEASE, primary.get("processed_release", ""))
            or not re.fullmatch(r"[0-9a-f]{64}", primary.get("pages_manifest_sha256", ""))):
        raise PipelineError("GitLab Pages requires the immutable verified primary archive")
    base = "/api/v4/projects/" + quote(config["project"], safe="")
    commit = config["storage"]["commit"]
    pages = config["pages"]
    variables = {
        "CARS_PROCESSED_RELEASE": primary["processed_release"],
        "CARS_AWS_RAW_RELEASE": state["tag"],
        "CARS_AWS_PRODUCER_COMMIT": producer_commit,
        "CARS_AWS_RAW_MANIFEST_SHA256": state["raw_manifest_sha256"],
    }
    settings = api.request("GET", base + "/pages")
    if settings.get("url", "").rstrip("/") + "/" != pages["url"]:
        raise PipelineError("GitLab Pages settings differ from the pinned project origin")
    runs_path = base + "/pipelines?ref=main&sha=" + commit + "&source=api&per_page=100"
    journal = state.setdefault("gitlab_pages", {})
    if not journal:
        ref = api.request("GET", base + "/repository/branches/main")
        ci = api.request("GET", base + "/repository/files/.gitlab-ci.yml?ref=main")
        if (ref["commit"]["id"] != commit or ci.get("commit_id") != commit
                or ci.get("content_sha256") != pages["ci_sha256"]):
            raise PipelineError("GitLab CI and main must match the approved data-only deployment")
        runs = api.request("GET", runs_path)
        if (not isinstance(runs, list) or any(not isinstance(run, dict)
                or type(run.get("id")) is not int or run["id"] <= 0 for run in runs)):
            raise PipelineError("GitLab pipeline list has an invalid response shape")
        journal.update(status="pending", before_ids=[run["id"] for run in runs], variables=variables)
        save()
        try:
            response = api.request("POST", base + "/pipeline?ref=main",
                                   {"variables": [{"key": key, "value": value} for key, value in variables.items()]})
        except platforms.PlatformError:
            raise Pending("GitLab dispatch response unavailable; reconcile the saved intent") from None
        if not isinstance(response, dict) or type(response.get("id")) is not int or response["id"] <= 0:
            raise Pending("GitLab dispatch response has no pipeline ID; reconcile without redispatch")
        journal["pipeline_id"] = response["id"]
        save()
    if journal.get("variables") != variables:
        raise PipelineError("GitLab dispatch journal differs from the verified archive inputs")
    if "pipeline_id" not in journal:
        runs = api.request("GET", runs_path)
        if (not isinstance(runs, list) or any(not isinstance(run, dict)
                or type(run.get("id")) is not int or run["id"] <= 0 for run in runs)):
            raise PipelineError("GitLab pipeline list has an invalid response shape")
        new_ids = [run["id"] for run in runs if run["id"] not in journal["before_ids"]]
        if len(new_ids) > 5:
            raise Pending("too many new GitLab pipelines to reconcile safely")
        matching = []
        for pipeline_id in new_ids:
            observed = api.request("GET", base + "/pipelines/" + str(pipeline_id) + "/variables")
            if (not isinstance(observed, list) or any(not isinstance(item, dict)
                    or not isinstance(item.get("key"), str)
                    or not isinstance(item.get("value"), str) for item in observed)):
                raise PipelineError("GitLab pipeline variables have an invalid response shape")
            selected = [(item["key"], item["value"]) for item in observed if item.get("key") in variables]
            if len(selected) == len(variables) and dict(selected) == variables:
                matching.append(pipeline_id)
        if len(matching) != 1:
            raise Pending("GitLab pipeline identity remains uncertain; dispatch will not be repeated")
        journal.update(pipeline_id=matching[0], reconciled=True)
        save()
    run = api.request("GET", base + "/pipelines/" + str(journal["pipeline_id"]))
    if (run.get("id") != journal["pipeline_id"] or run.get("ref") != "main"
            or run.get("sha") != commit or run.get("source") != "api"):
        raise PipelineError("GitLab pipeline identity differs from the exact native dispatch")
    if run.get("status") in {"failed", "canceled", "skipped", "manual"}:
        raise PipelineError("GitLab deployment did not succeed")
    if run.get("status") != "success":
        raise Pending("GitLab deployment is still pending")
    manifest = get_page(pages["url"] + "data/manifest.json", 1024 * 1024)
    if hashlib.sha256(manifest).hexdigest() != primary["pages_manifest_sha256"]:
        raise Pending("GitLab Pages manifest differs from the exact verified primary archive")
    assets = verify_page_data(json.loads(manifest), pages["url"], get_page)
    health = get_page(pages["url"] + "index.html", 1024 * 1024)
    journal.update(status="accepted", verified_data_assets=assets,
                   pages_manifest_sha256=primary["pages_manifest_sha256"],
                   pages_health_sha256=hashlib.sha256(health).hexdigest())
    save()


def cnb_acceptance_credential(config):
    if config["acceptance"].get("credential") != "dedicated":
        return platforms.credential("cnb.cool", config["repo"])
    record = private_json(CNB_BUILD_CREDENTIAL)
    token = record.get("token") if isinstance(record, dict) and set(record) == {"token"} else None
    if (not isinstance(token, str) or not 0 < len(token) <= 4096
            or any(not 33 <= ord(char) <= 126 for char in token)):
        raise PipelineError("CNB dedicated build credential is invalid")
    return token


def advance_cnb_acceptance(state, config, producer, api, save):
    primary = state.get("dispatch", {})
    processed = primary.get("processed_release", "")
    if primary.get("status") != "accepted" or not re.fullmatch(PROCESSED_RELEASE, processed):
        raise PipelineError("CNB acceptance requires the immutable verified primary archive")
    repo = config["repo"]
    commit = config["storage"]["commit"]
    base = "/" + repo + "/-/"
    event = "api_trigger"
    title = "aws-accept " + state["tag"] + " " + state["raw_manifest_sha256"]
    request = {"branch": "main", "sha": commit, "event": event, "title": title,
               "sync": "false", "env": {"AWS_RAW_RELEASE": state["tag"], "AWS_RAW_PRODUCER_COMMIT": producer,
                                        "AWS_PROCESSED_RELEASE": processed,
                                        "AWS_RAW_MANIFEST_SHA256": state["raw_manifest_sha256"]}}
    history = base + "build/logs?" + urlencode({"sha": commit, "event": event, "title": title, "page_size": 20})
    journal = state.setdefault("cnb_acceptance", {})
    if journal and journal.get("request") != request:
        raise PipelineError("CNB acceptance journal differs from the verified archive inputs")
    if journal.get("status") == "accepted":
        return

    def matching_builds():
        response = api.request("GET", history)
        rows = response.get("data") if isinstance(response, dict) else None
        total = response.get("total") if isinstance(response, dict) else None
        if (type(total) is not int or not isinstance(rows, list) or not 0 <= total == len(rows) < 20
                or any(not isinstance(row, dict) for row in rows)):
            raise Pending("CNB build history is incomplete; dispatch identity cannot be reconciled")
        return {row["sn"] for row in rows if row.get("title") == title and row.get("sha") == commit
                and row.get("slug") == repo and row.get("event") == event
                and row.get("sourceRef") in ("main", "refs/heads/main")
                and isinstance(row.get("sn"), str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", row["sn"])}

    if not journal:
        branch = api.request("GET", base + "git/branches/main")
        ci = api.request("GET", base + "git/contents/.cnb.yml?ref=" + commit)
        try:
            content = base64.b64decode(ci["content"], validate=True)
        except (KeyError, TypeError, ValueError):
            raise PipelineError("CNB returned invalid pipeline configuration bytes") from None
        if (branch["commit"]["sha"] != commit or ci.get("encoding") != "base64"
                or hashlib.sha256(content).hexdigest() != config["acceptance"]["ci_sha256"]):
            raise PipelineError("CNB CI and main must match the approved data-only acceptance")
        prior = matching_builds()
        if prior:
            raise Pending("CNB already has matching builds without a dispatch journal")
        journal.update(status="pending", request=request)
        save()
        try:
            response = api.request("POST", base + "build/start", request)
        except (platforms.PlatformError, ValueError):
            raise Pending("CNB dispatch response unavailable; reconcile the saved intent") from None
        sn = response.get("sn") if isinstance(response, dict) and response.get("success") is True else None
        if not isinstance(sn, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", sn):
            raise Pending("CNB dispatch has no confirmed build number; reconcile without redispatch")
        journal["sn"] = sn
        save()

    matches = matching_builds()
    if len(matches) != 1 or ("sn" in journal and journal["sn"] not in matches):
        raise Pending("CNB build identity remains uncertain; dispatch will not be repeated")
    if "sn" not in journal:
        journal.update(sn=next(iter(matches)), reconciled=True)
        save()
    result = api.request("GET", base + "build/status/" + journal["sn"])
    if not isinstance(result, dict):
        raise Pending("CNB did not return a build status")
    if result.get("status") in {"error", "cancel", "failed", "canceled"}:
        raise PipelineError("CNB data acceptance failed")
    if result.get("status") != "success":
        raise Pending("CNB data acceptance is still pending")
    pipelines = result.get("pipelinesStatus")
    runs = list(pipelines.values()) if isinstance(pipelines, dict) else []
    successful = len(runs) == 1 and isinstance(runs[0], dict) and runs[0].get("status") == "success"
    stages = runs[0].get("stages") if successful else None
    if (not isinstance(stages, list) or any(not isinstance(stage, dict) for stage in stages)
            or [(stage.get("name"), stage.get("status")) for stage in stages] != [
                (name, "success") for name in CNB_ACCEPTANCE_STAGES]):
        raise PipelineError("CNB success does not attest both approved data acceptance stages")
    journal.update(status="accepted", stages=list(CNB_ACCEPTANCE_STAGES))
    save()


def refresh_priority_rankings(plan, directory, period, repo):
    ranking = plan["targets"].get("autohome", {}).get("priority") or {}
    if not ranking.get("refresh"):
        return
    receipt = directory / "autohome-ranking-attempt.json"
    if receipt.exists() and private_json(receipt).get("period") == period:
        return
    atomic_json(receipt, {"period": period, "status": "started"})
    network = plan["network"]
    command = [sys.executable, "-m", "scripts.refresh_aws_autohome_ranks",
               "--rankings", ranking["rankings_path"], "--probe-ip", network["probe_ip"],
               "--probe-port", str(network.get("probe_port", 22))]
    try:
        result = subprocess.run(command, cwd=repo, check=False, timeout=100)
        status = "attempted" if result.returncode == 0 else "failed"
    except (OSError, subprocess.SubprocessError):
        status = "failed"
    atomic_json(receipt, {"period": period, "status": status})
    if status == "failed":
        print("Autohome ranking refresh failed; keep any verified saved signals", file=sys.stderr)


def plan_run_targets(plan, period, history):
    observed_on = datetime.strptime(period, "%Y%m%d").date()
    selected = {}
    for source, entry in plan["targets"].items():
        rank_plan = entry.get("priority")
        if rank_plan is None:
            selected[source] = {"sha256": entry["sha256"]}
            continue
        catalog = private_json(rank_plan["catalog_path"], rank_plan["catalog_sha256"])
        if catalog.get("source") != source:
            raise PipelineError("priority catalog source differs from the collector")
        rank_file = rank_plan.get("rankings_path")
        if rank_file and (not rank_plan.get("refresh") or Path(rank_file).exists() or Path(rank_file).is_symlink()):
            rankings = private_json(rank_file)
            if not isinstance(rankings, dict) or not rankings.keys() <= {"heat", "sales"}:
                raise PipelineError("priority rankings may not change the approved targets")
            catalog["rankings"] = rankings
        accepted = history.get(source, {})
        for item in catalog["targets"]:
            series_id = priority.target_identity(source, item["target"])
            seen = accepted.get(series_id)
            if seen:
                item["last_success"] = max(seen, item.get("last_success") or "")
        targets, decision = priority.plan(catalog, observed_on, entry.get("row_limit", 30))
        if not targets:
            continue
        # The payload string preserves Yiche's queue order when the journal sorts its keys.
        payload = json.dumps(targets, ensure_ascii=False, indent=2) + "\n"
        encoded = payload.encode()
        if len(encoded) > 65536:
            raise PipelineError("selected priority targets exceed the collector manifest size")
        selected[source] = {"payload": payload, "sha256": hashlib.sha256(encoded).hexdigest(),
                            "rankings_used": decision["rankings_used"],
                            "evidence_sha256": hashlib.sha256(json.dumps(catalog, ensure_ascii=False,
                                                                        sort_keys=True).encode()).hexdigest()}
    return selected


def frozen_target_payload(selection):
    payload = selection["payload"].encode()
    if not 0 < len(payload) <= 65536 or hashlib.sha256(payload).hexdigest() != selection["sha256"]:
        raise PipelineError("frozen target payload does not match its recorded digest")
    return payload


def write_target_snapshot(path, payload):
    fd, temporary = tempfile.mkstemp(prefix=".target-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def accepted_priority_history(state, run_dir, history):
    if not state.get("complete"):
        raise PipelineError("priority history requires a verified publication")
    updated = {source: dict(values) for source, values in history.items()}
    observed_on = datetime.strptime(state["period"], "%Y%m%d").date().isoformat()
    for source, selection in state.get("targets", {}).items():
        if "payload" not in selection:
            continue
        planned = json.loads(frozen_target_payload(selection))
        path = run_dir / source / SOURCES[source][1]
        if raw.inspect_asset(path, source) != state["sources"][source]:
            raise PipelineError("completed source differs from its priority history receipt")
        rows = json.loads(path.read_bytes())
        if source == "yiche":
            groups = {}
            for target in planned.values():
                key = (target["brand"], target["series"])
                groups.setdefault(key, set()).add(target["serial_id"])
            identities = [groups.get((row.get("品牌"), row.get("车系")), set()) for row in rows]
            observed = {next(iter(ids)) for ids in identities if len(ids) == 1}
        else:
            field = "car_id" if source == "autohome" else "id"
            requested = {target[field] for target in planned}
            observed = requested & {str(row.get("车系ID") or "") for row in rows}
        if observed:
            source_history = updated.setdefault(source, {})
            for key in observed:
                source_history[key] = max(observed_on, source_history.get(key, ""))
    return updated


def finalize_priority_history(state, directory, history_path, history):
    if state.get("priority_history_committed") or not any("payload" in item for item in state.get("targets", {}).values()):
        return history
    updated = accepted_priority_history(state, directory / state["tag"], history)
    if updated != history:
        atomic_json(history_path, updated)
    state["priority_history_committed"] = True
    atomic_json(directory / "state.json", state)
    return updated


def raw_mirror_routes():
    return (
        ("cnb", platforms.mirror_cnb, platforms.CNB, "cnb.cool", "CNB"),
        ("gitlab", platforms.mirror_gitlab, platforms.GITLAB, "gitlab.com", "GitLab"),
        ("gitee", platforms.mirror_gitee, platforms.GITEE, "gitee.com", "Gitee"),
    )


def native_release_credentials(remotes):
    tokens = {}
    for name, _, _, host, label in raw_mirror_routes():
        if name not in remotes:
            continue
        config = remotes[name]
        project = config["repo"] if name == "cnb" else config["project"]
        try:
            tokens[name] = platforms.credential(host, project)
        except (platforms.PlatformError, OSError, subprocess.SubprocessError):
            raise PipelineError(f"{label} raw mirror credential unavailable") from None

    cnb = remotes["cnb"]
    if (cnb.get("acceptance") or {}).get("credential") == "dedicated":
        try:
            tokens["cnb_build"] = cnb_acceptance_credential(cnb)
        except (PipelineError, OSError, ValueError):
            raise PipelineError("CNB build credential unavailable") from None
    return tokens


def execute(plan_path, *, apply=False, repo=ROOT, state_root=STATE_ROOT):
    plan, fingerprint = validate_plan(plan_path, repo)
    if not apply:
        return {"status": "DRY_RUN_VALIDATED", "fingerprint": fingerprint, "remote_writes": 0, "collector_calls": 0}
    if Path(plan_path) != PLAN:
        raise PipelineError("application requires the installed private plan reference")
    assert_aws(plan.get("mode", "debug"))
    os.umask(0o077)
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if state_root.is_symlink() or state_root.stat().st_uid != os.geteuid() or state_root.stat().st_mode & 0o077:
        raise PipelineError("pipeline state root is not private and owned")
    lock_fd = os.open(state_root / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        directory = state_root / plan["plan_id"]
        directory.mkdir(mode=0o700, exist_ok=True)
        if directory.is_symlink() or directory.stat().st_uid != os.geteuid() or directory.stat().st_mode & 0o077:
            raise PipelineError("pipeline state directory is not private and owned")
        path = directory / "state.json"
        state = private_json(path) if path.exists() else {"fingerprint": fingerprint}
        if state.get("fingerprint") != fingerprint:
            raise PipelineError("durable state belongs to a different plan/source; preserve it")
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        history_path = directory / "priority-history.json"
        history = private_json(history_path) if history_path.exists() else {}
        if state.get("complete"):
            history = finalize_priority_history(state, directory, history_path, history)
        if state.get("complete") and state.get("period") == today:
            atomic_json(directory / "cursor.json", {"tag": state["tag"], "run_id": state["dispatch"]["run_id"],
                        "producer_commit": plan["producer_commit"], "raw_manifest_sha256": state["raw_manifest_sha256"]})
            return {"status": "ALREADY_ACCEPTED", "tag": state["tag"], "run_id": state["dispatch"]["run_id"]}
        tokens = native_release_credentials(plan["platforms"])
        if "tag" not in state or state.get("complete"):
            if state.get("complete"):
                atomic_json(directory / (state["tag"] + ".receipt.json"), state)
            refresh_priority_rankings(plan, directory, today, repo)
            targets = plan_run_targets(plan, today, history)
            if not targets:
                return {"status": "NO_DUE_TARGETS", "period": today}
            state = {"fingerprint": fingerprint, "period": today, "targets": targets,
                     "tag": "aws-raw-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), "sources": {}, "mirrors": {}}
        raw.validate_identity(state["tag"], plan["producer_commit"])
        save = lambda: atomic_json(path, state)
        save()
        run_dir = directory / state["tag"]
        run_dir.mkdir(mode=0o700, exist_ok=True)
        if run_dir.is_symlink() or run_dir.stat().st_uid != os.geteuid() or run_dir.stat().st_mode & 0o077:
            raise PipelineError("run directory is not private and owned")
        selections = state.get("targets")
        if selections is None:
            # Existing pending journals used only fixed, pinned target manifests.
            selections = {source: {"sha256": entry["sha256"]} for source, entry in plan["targets"].items()}
        if not selections or not selections.keys() <= plan["targets"].keys():
            raise PipelineError("frozen journal contains an unexpected source selection")
        for source, selection in selections.items():
            entry = plan["targets"][source]
            if validate_plan(plan_path, repo)[1] != fingerprint:
                raise PipelineError("plan/source drift during collection")
            output = run_dir / source
            result = output / SOURCES[source][1]
            if source not in state["sources"]:
                target = run_dir / (source + "-targets.json")
                if "payload" in selection:
                    target_bytes = frozen_target_payload(selection)
                else:
                    target_bytes = Path(entry["path"]).read_bytes()
                    if hashlib.sha256(target_bytes).hexdigest() != selection["sha256"]:
                        raise PipelineError("approved target changed while freezing the run")
                if target.exists() or target.is_symlink():
                    if target.is_symlink() or digest(target) != selection["sha256"]:
                        raise PipelineError("frozen target snapshot changed")
                else:
                    write_target_snapshot(target, target_bytes)
                environment = dict(os.environ, AWS_CRAWL_UNIT_NAME="crawl-cars-aws-collector")
                subprocess.run(collector_command(source, entry, target, output, plan["network"]), cwd=repo,
                               env=environment, check=True, timeout=entry.get("runtime_seconds", 240) + 90)
                info = raw.inspect_asset(result, source)
                if entry.get("row_limit", 30) and info["rows"] > entry.get("row_limit", 30):
                    raise PipelineError("collector output exceeds approved row cap")
                state["sources"][source] = info
                save()
            if raw.inspect_asset(result, source) != state["sources"][source]:
                raise PipelineError("completed source bytes changed")
        bundle = run_dir / "bundle"
        if not bundle.exists():
            raw.pack(bundle, state["tag"], plan["producer_commit"],
                     {source: run_dir / source / SOURCES[source][1] for source in selections})
        manifest = raw.verify(bundle, state["tag"])
        if (manifest["producer_commit"] != plan["producer_commit"] or set(manifest["assets"]) != set(state["sources"])
                or any({key: item[key] for key in ("sha256", "size", "rows")} != state["sources"][source]
                       for source, item in manifest["assets"].items())):
            raise PipelineError("frozen bundle differs from the completed source receipts")
        manifest_sha = digest(bundle / raw.MANIFEST)
        if state.get("raw_manifest_sha256", manifest_sha) != manifest_sha:
            raise PipelineError("frozen raw manifest changed")
        state["raw_manifest_sha256"] = manifest_sha
        save()
        if validate_plan(plan_path, repo)[1] != fingerprint:
            raise PipelineError("plan/source drift before raw publication")
        github_journal = state.setdefault("transactions", {}).setdefault("github", {})
        raw.publish_github(bundle, state["tag"], plan["platforms"]["github"]["repo"],
                           check_only="github" in state["mirrors"], journal=github_journal, save=save)
        state["mirrors"]["github"] = {"verified": True, "producer_commit": plan["producer_commit"]}
        save()
        for name, function, origin, _, _ in raw_mirror_routes():
            if name not in plan["platforms"]:
                continue
            config = plan["platforms"][name]
            project = config["repo"] if name == "cnb" else config["project"]
            api = platforms.Api(origin, tokens[name], gitlab=name == "gitlab")
            journal = state.setdefault("transactions", {}).setdefault(name, {})
            state["mirrors"][name] = function(api, project, bundle, state["tag"], plan["producer_commit"],
                                             config["storage"], journal, save, check_only=name in state["mirrors"])
            save()
        if not all(state["mirrors"].get(name, {}).get("verified") is True for name in plan["platforms"]):
            raise PipelineError("not all configured raw mirrors verified")
        if validate_plan(plan_path, repo)[1] != fingerprint:
            raise PipelineError("source drift before processing dispatch")
        advance_processing(state, plan, Actions(plan["platforms"]["github"]["repo"]), save)
        gitlab = plan["platforms"]["gitlab"]
        if gitlab.get("pages"):
            token = tokens["gitlab"]
            api = platforms.Api(platforms.GITLAB, token, gitlab=True)
            reader = private_gitlab_page_reader(gitlab["pages"]["url"], token)
            advance_gitlab_pages(state, gitlab, plan["producer_commit"], api, save, reader)
        cnb = plan["platforms"]["cnb"]
        if cnb.get("acceptance"):
            api = platforms.Api(platforms.CNB, tokens.get("cnb_build", tokens["cnb"]))
            advance_cnb_acceptance(state, cnb, plan["producer_commit"], api, save)
        advance_public_page_mirrors(state, plan["processing"].get("page_mirrors", []), plan["producer_commit"], save)
        state["complete"] = True
        save()
        finalize_priority_history(state, directory, history_path, history)
        atomic_json(directory / "cursor.json", {"tag": state["tag"], "run_id": state["dispatch"]["run_id"],
                    "producer_commit": plan["producer_commit"], "raw_manifest_sha256": state["raw_manifest_sha256"]})
        return {"status": "ACCEPTED", "tag": state["tag"], "run_id": state["dispatch"]["run_id"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--apply", action="store_true", help="requires installed AWS-only private plan; default is zero-write dry-run")
    args = parser.parse_args()
    try:
        print(json.dumps(execute(args.plan, apply=args.apply), ensure_ascii=False, sort_keys=True))
    except Pending as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(75) from None
    except (PipelineError, platforms.PlatformError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        detail = str(error) if isinstance(error, (PipelineError, platforms.PlatformError)) else type(error).__name__
        print(f"AWS pipeline stopped: {detail}; private state retained", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
