"""Immutable raw mirrors; credentials stay in the existing Git credential helper."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import requests

from scripts import aws_raw_bundle as raw


CREDENTIAL_STORE = Path("/opt/crawl-cars-runtime/git-platform-credentials")
CNB = "https://api.cnb.cool"
GITLAB = "https://gitlab.com"
GITEE = "https://gitee.com"
GITEE_PROJECT = "xuerui911/crawl_cars"
GITEE_MAX_ATTACHMENT_BYTES = 100_000_000


class PlatformError(RuntimeError):
    pass


class GiteeReadTransportError(PlatformError):
    pass


def https_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise PlatformError("unsafe platform URL")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        if parsed.hostname == "localhost" or parsed.hostname.endswith(".localhost"):
            raise PlatformError("unsafe platform host") from None
    else:
        if not address.is_global:
            raise PlatformError("unsafe platform address")
    return url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class AssetRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        https_url(new_url)
        redirected = super().redirect_request(request, fp, code, message, headers, new_url)
        if redirected is not None:
            for name in ("Authorization", "Private-token"):
                redirected.remove_header(name)
        return redirected


def credential(host: str, project: str) -> str:
    """Use the URL-line store without putting its values in argv, logs or receipts."""
    if CREDENTIAL_STORE.is_symlink() or not CREDENTIAL_STORE.is_file():
        raise PlatformError("existing platform credential reference is unavailable")
    if CREDENTIAL_STORE.stat().st_mode & 0o077 or CREDENTIAL_STORE.stat().st_uid not in (0, os.geteuid()):
        raise PlatformError("platform credential store must be private")
    result = subprocess.run(
        ["git", "credential-store", "--file=" + str(CREDENTIAL_STORE), "get"],
        input=f"protocol=https\nhost={host}\npath={project.removesuffix('.git')}.git\n\n",
        capture_output=True, text=True, timeout=10, check=False,
    )
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    token = fields.get("password", "")
    if result.returncode or not token or "\n" in token or "\r" in token:
        raise PlatformError("existing platform credential lookup failed")
    return token


class Api:
    """Fixed-origin API requests; errors never include headers or signed URLs."""

    def __init__(self, origin: str, token: str, *, gitlab: bool = False):
        if origin not in (CNB, GITLAB, GITEE):
            raise PlatformError("unapproved platform origin")
        self.origin = origin
        self.headers = {"Accept": "application/json"}
        self.headers["PRIVATE-TOKEN" if gitlab else "Authorization"] = token if gitlab else "Bearer " + token

    def request(self, method, path, body=None, *, data=None, content_type=None, missing=False, binary=False):
        if not path.startswith("/") or path.startswith("//"):
            raise PlatformError("API path must stay on the approved origin")
        if self.origin == GITEE and method == "GET" and body is None and data is None:
            try:
                return self._read_gitee(path, missing=missing, binary=binary)
            except GiteeReadTransportError:
                return self._read_gitee(path, missing=missing, binary=binary)
        headers = dict(self.headers)
        if body is not None:
            data = json.dumps(body, sort_keys=True).encode()
            content_type = "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(self.origin + path, data=data, headers=headers, method=method)
        opener = urllib.request.build_opener(AssetRedirect() if binary else NoRedirect())
        try:
            with opener.open(request, timeout=120) as response:
                payload = response.read(raw.MAX_ASSET_BYTES + 1 if binary else 4 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            if error.code == 404 and missing:
                return None
            raise PlatformError(f"platform API HTTP {error.code}") from None
        except (OSError, TimeoutError):
            raise PlatformError("platform API transport failed; transaction remains pending") from None
        if len(payload) > (raw.MAX_ASSET_BYTES if binary else 4 * 1024 * 1024):
            raise PlatformError("platform response exceeds bound")
        return payload if binary else (json.loads(payload) if payload else None)

    @staticmethod
    def _read_gitee_payload(response, maximum):
        body = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            body.extend(chunk)
            if len(body) > maximum:
                raise PlatformError("Gitee response exceeds bound")
        return bytes(body)

    def _read_gitee(self, path, *, missing, binary):
        prefix = "/api/v5/repos/" + GITEE_PROJECT
        suffix = r"(?:/branches/main|/commits/aws-raw-\d{8}T\d{6}Z|/releases/tags/aws-raw-\d{8}T\d{6}Z|/releases/[1-9]\d*/attach_files(?:/[1-9]\d*/download)?)?"
        if not re.fullmatch(re.escape(prefix) + suffix, path):
            raise PlatformError("Gitee read escaped the approved repository")
        url = self.origin + path
        maximum = raw.MAX_ASSET_BYTES if binary else 4 * 1024 * 1024
        try:
            with requests.get(url, headers=self.headers, auth=lambda request: request, timeout=(10, 30),
                              allow_redirects=False, stream=True) as response:
                if response.status_code == 404 and missing:
                    return None
                if binary and response.is_redirect:
                    redirect = https_url(urllib.parse.urljoin(url, response.headers["Location"]))
                elif response.status_code != 200:
                    raise PlatformError(f"Gitee read HTTP {response.status_code}")
                else:
                    payload = self._read_gitee_payload(response, maximum)
                    return payload if binary else json.loads(payload)

            # A signed attachment URL is self-authenticating. Do not use netrc credentials.
            with requests.get(redirect, auth=lambda request: request, timeout=(10, 30),
                              allow_redirects=False, stream=True) as response:
                if response.status_code != 200:
                    raise PlatformError(f"Gitee attachment download HTTP {response.status_code}")
                return self._read_gitee_payload(response, maximum)
        except (requests.RequestException, OSError):
            raise GiteeReadTransportError("Gitee read unavailable; transaction remains pending") from None
        except (ValueError, KeyError):
            raise PlatformError("Gitee returned invalid readback data") from None

    def put_signed(self, url, path):
        request = urllib.request.Request(https_url(url), data=path.read_bytes(), method="PUT",
                                         headers={"Content-Type": "application/octet-stream"})
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=120) as response:
                if response.status not in (200, 201, 204):
                    raise PlatformError("object upload was not accepted")
        except (urllib.error.URLError, OSError):
            raise PlatformError("object upload failed; unpublished transaction retained") from None

    def upload_gitlab(self, endpoint, path, filename):
        return self.upload_attachment(endpoint, path, filename)

    def upload_attachment(self, endpoint, path, filename):
        if self.origin == GITEE:
            return self._upload_gitee_attachment(endpoint, path, filename)
        boundary = "aws-raw-" + hashlib.sha256(filename.encode()).hexdigest()
        prefix = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                  f'filename="{filename}"\r\nContent-Type: application/json\r\n\r\n').encode()
        data = prefix + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        return self.request("POST", endpoint, data=data,
                            content_type="multipart/form-data; boundary=" + boundary)

    def _upload_gitee_attachment(self, endpoint, path, filename):
        prefix = "/api/v5/repos/" + GITEE_PROJECT + "/releases/"
        if not re.fullmatch(re.escape(prefix) + r"[1-9][0-9]*/attach_files", endpoint):
            raise PlatformError("Gitee attachment path escaped the approved repository")
        if path.name != filename or filename not in {raw.MANIFEST, *(item[0] for item in raw.SOURCES.values())}:
            raise PlatformError("invalid Gitee attachment filename")
        if path.is_symlink() or not path.is_file():
            raise PlatformError("invalid Gitee attachment file")
        size = path.stat().st_size
        if not 0 < size <= GITEE_MAX_ATTACHMENT_BYTES:
            raise PlatformError("invalid Gitee attachment size")
        try:
            with path.open("rb") as stream, requests.post(
                self.origin + endpoint,
                headers=self.headers,
                auth=lambda request: request,
                files={"file": (filename, stream, "application/json")},
                timeout=(15, 70),
                allow_redirects=False,
                stream=True,
            ) as response:
                if response.status_code not in (200, 201):
                    raise PlatformError(f"Gitee attachment API HTTP {response.status_code}")
                body = bytearray()
                for chunk in response.iter_content(chunk_size=8192):
                    body.extend(chunk)
                    if len(body) > 1048576:
                        raise PlatformError("Gitee attachment response exceeds bound")
            item = json.loads(body)
        except (requests.RequestException, OSError, ValueError):
            raise PlatformError("Gitee attachment response unavailable; transaction remains pending") from None
        if (not isinstance(item, dict) or item.get("name") != filename or item.get("size") != size
                or type(item.get("id")) is not int or item["id"] < 1):
            raise PlatformError("Gitee attachment response identity differs; transaction remains pending")
        return item


def bundle_identity(bundle: Path, tag: str, producer: str, storage: dict) -> tuple[dict, dict]:
    manifest = raw.verify(bundle, tag)
    if manifest["producer_commit"] != producer or not re.fullmatch(r"[0-9a-f]{40}", storage.get("commit", "")):
        raise PlatformError("producer or storage commit mismatch")
    if storage.get("ref") != "main":
        raise PlatformError("only the approved native main storage ref is supported")
    assets = {}
    for path in sorted(bundle.iterdir()):
        payload = path.read_bytes()
        assets[path.name] = {"size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    binding = {"tag": tag, "producer_commit": producer, "storage_ref": storage["ref"],
               "storage_commit": storage["commit"], "assets": assets}
    return binding, assets


def verify_bytes(payload, expected):
    if len(payload) != expected["size"] or hashlib.sha256(payload).hexdigest() != expected["sha256"]:
        raise PlatformError("remote raw asset size or SHA-256 mismatch")


def mirror_cnb(api, repo, bundle, tag, producer, storage, journal, save, *, check_only=False):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise PlatformError("invalid approved CNB repository")
    binding, assets = bundle_identity(bundle, tag, producer, storage)
    base = "/" + repo + "/-/"
    description = json.dumps({"aws_raw": binding}, sort_keys=True, separators=(",", ":"))
    release = api.request("GET", base + "releases/tags/" + tag, missing=True)
    if release is None:
        if check_only:
            raise PlatformError("CNB raw release is absent")
        if journal.get("phase") == "creating-draft":
            raise PlatformError("CNB release creation is pending; awaiting visible release")
        branch = api.request("GET", base + "git/branches/main")
        if branch.get("commit", {}).get("sha") != storage["commit"]:
            raise PlatformError("CNB native storage ref moved; source is never force mirrored")
        existing_tag = api.request("GET", base + "git/tags/" + tag, missing=True)
        if existing_tag is not None and existing_tag.get("commit", {}).get("sha") != storage["commit"]:
            raise PlatformError("CNB tag already belongs to another storage commit")
        if journal and journal.get("binding") != binding:
            raise PlatformError("CNB transaction belongs to another raw plan")
        journal.update(binding=binding, phase="creating-draft")
        save()
        release = api.request("POST", base + "releases", {
            "tag_name": tag, "target_commitish": storage["commit"], "name": tag,
            "body": description, "draft": True, "prerelease": True, "make_latest": "false",
        })
        journal.update(release_id=release.get("id"), phase="draft")
        save()
    if (release.get("tag_name") != tag or release.get("body") != description
            or release.get("prerelease") is not True or type(release.get("draft")) is not bool):
        raise PlatformError("CNB release provenance/type differs")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", str(release.get("id", ""))):
        raise PlatformError("invalid CNB release identifier")
    if api.request("GET", base + "git/tags/" + tag).get("commit", {}).get("sha") != storage["commit"]:
        raise PlatformError("CNB raw tag points to another storage commit")
    if (release["draft"] and journal.get("binding") == binding
            and journal.get("phase") == "creating-draft" and not journal.get("release_id")):
        journal.update(release_id=release["id"], phase="draft")
        save()
    if release["draft"] and (check_only or journal.get("binding") != binding
                             or journal.get("release_id") != release.get("id")):
        raise PlatformError("CNB draft is not this owned unpublished transaction")

    def visible_assets(current):
        found = set()
        listed = current.get("assets")
        if listed is None:
            listed = []
        if not isinstance(listed, list):
            raise PlatformError("CNB release asset list has invalid shape")
        for asset in listed:
            name = asset.get("name")
            if name not in assets or name in found or asset.get("size") != assets[name]["size"]:
                raise PlatformError("CNB asset set/size differs")
            found.add(name)
        return found

    def verified(current):
        found = visible_assets(current)
        for name in sorted(found):
            verify_bytes(api.request("GET", base + "releases/download/" + tag + "/" + name, binary=True), assets[name])
        return set(assets) - found

    missing = verified(release)
    if not release["draft"] and missing:
        raise PlatformError("published CNB release is partial; it cannot be resumed as a draft")
    confirmed = set(journal.get("confirmed_assets", ()))
    if confirmed - set(assets):
        raise PlatformError("CNB journal names an unexpected confirmed asset")
    for name in sorted(missing - confirmed):
        upload = api.request("POST", base + "releases/" + release["id"] + "/asset-upload-url", {
            "asset_name": name, "size": assets[name]["size"], "overwrite": False, "ttl": 0,
        })
        api.put_signed(upload["upload_url"], bundle / name)
        verify = urllib.parse.urlsplit(upload["verify_url"])
        prefix = base + "releases/" + release["id"] + "/asset-upload-confirmation/"
        if (verify.scheme and (verify.scheme != "https" or verify.netloc != "api.cnb.cool")) or not verify.path.startswith(prefix):
            raise PlatformError("CNB confirmation URL escaped the owned release")
        api.request("POST", verify.path + "?ttl=0")
        confirmed.add(name)
        journal["confirmed_assets"] = sorted(confirmed)
        save()
    if release["draft"]:
        release_id = release["id"]
        for delay in (0, 2, 4, 8, 16, 30):
            if delay:
                time.sleep(delay)
            release = api.request("GET", base + "releases/tags/" + tag)
            if (release.get("id") != release_id or release.get("tag_name") != tag
                    or release.get("body") != description or release.get("prerelease") is not True
                    or type(release.get("draft")) is not bool):
                raise PlatformError("CNB release identity changed while awaiting confirmed assets")
            if visible_assets(release) == set(assets):
                break
        else:
            raise PlatformError("CNB confirmed assets are not yet visible; draft remains pending")
        if verified(release):
            raise PlatformError("CNB draft assets are not all verified")
        if release["draft"]:
            api.request("PATCH", base + "releases/" + release_id, {"draft": False, "prerelease": True, "make_latest": "false"})
        release = api.request("GET", base + "releases/tags/" + tag)
    target = api.request("GET", base + "git/tags/" + tag)
    if (release.get("draft") is not False or release.get("body") != description or release.get("tag_name") != tag
            or release.get("prerelease") is not True or verified(release)
            or target.get("commit", {}).get("sha") != storage["commit"]):
        raise PlatformError("CNB published identity is not verified")
    return {"platform": "cnb", "binding": binding, "release_id": release["id"], "verified": True}


def mirror_gitlab(api, project, bundle, tag, producer, storage, journal, save, *, check_only=False):
    binding, assets = bundle_identity(bundle, tag, producer, storage)
    base = "/api/v4/projects/" + urllib.parse.quote(str(project), safe="")
    release_path = base + "/releases/" + tag
    release = api.request("GET", release_path, missing=True)
    if journal and journal.get("binding") != binding:
        raise PlatformError("GitLab transaction belongs to another raw plan")
    if release is None:
        if check_only:
            raise PlatformError("GitLab raw release is absent")
        if journal.get("phase") == "creating-complete-release":
            raise PlatformError("GitLab release creation is pending; awaiting visible release")
        branch = api.request("GET", base + "/repository/branches/main")
        if branch.get("commit", {}).get("id") != storage["commit"]:
            raise PlatformError("GitLab native storage ref moved")
        existing_tag = api.request("GET", base + "/repository/tags/" + tag, missing=True)
        if existing_tag is not None and existing_tag.get("commit", {}).get("id") != storage["commit"]:
            raise PlatformError("GitLab tag already belongs to another storage commit")
        journal.setdefault("binding", binding)
        uploads = journal.setdefault("uploads", {})
        for name, expected in assets.items():
            remote_name = tag + "--" + expected["sha256"][:12] + "--" + name
            if name not in uploads:
                pending = journal.get("pending_upload")
                if pending != name:
                    journal["pending_upload"] = name
                    save()
                    api.upload_gitlab(base + "/uploads", bundle / name, remote_name)
                candidates = []
                for page in range(1, 11):
                    batch = api.request("GET", base + f"/uploads?per_page=100&page={page}")
                    candidates.extend(x for x in batch if x.get("filename") == remote_name and x.get("size") == expected["size"])
                    if len(batch) < 100:
                        break
                else:
                    raise PlatformError("GitLab upload catalog is incomplete; no guess or duplicate upload")
                if len(candidates) != 1 or not isinstance(candidates[0].get("id"), int):
                    raise PlatformError("GitLab pending upload is missing/ambiguous; no blind reupload")
                uploads[name] = candidates[0]["id"]
                journal.pop("pending_upload", None)
                save()
            verify_bytes(api.request("GET", base + "/uploads/" + str(uploads[name]), binary=True), expected)
        description = json.dumps({"aws_raw": binding, "uploads": uploads}, sort_keys=True, separators=(",", ":"))
        links = [{"name": name, "url": GITLAB + base + "/uploads/" + str(uploads[name]),
                  "direct_asset_path": "/" + name, "link_type": "other"} for name in sorted(assets)]
        journal["phase"] = "creating-complete-release"
        save()
        api.request("POST", base + "/releases", {"tag_name": tag, "ref": storage["commit"],
                    "name": tag, "description": description, "assets": {"links": links}})
        release = api.request("GET", release_path)
    try:
        description = json.loads(release["description"])
        uploads = description["uploads"]
    except (KeyError, TypeError, ValueError):
        raise PlatformError("GitLab release lacks exact raw provenance") from None
    if description.get("aws_raw") != binding or set(uploads) != set(assets) or release.get("tag_name") != tag:
        raise PlatformError("GitLab published provenance differs")
    links = release.get("assets", {}).get("links", [])
    expected_links = {name: GITLAB + base + "/uploads/" + str(uploads[name]) for name in assets}
    if len(links) != len(assets) or {x.get("name"): x.get("url") for x in links} != expected_links:
        raise PlatformError("GitLab published release is partial or has foreign links")
    target = api.request("GET", base + "/repository/tags/" + tag)
    if target.get("commit", {}).get("id") != storage["commit"]:
        raise PlatformError("GitLab tag does not bind the native storage commit")
    for name, expected in assets.items():
        verify_bytes(api.request("GET", base + "/uploads/" + str(uploads[name]), binary=True), expected)
    return {"platform": "gitlab", "binding": binding, "verified": True}


def mirror_gitee(api, project, bundle, tag, producer, storage, journal, save, *, check_only=False):
    if project != GITEE_PROJECT:
        raise PlatformError("Gitee project differs from the approved storage repository")
    binding, assets = bundle_identity(bundle, tag, producer, storage)
    if any(asset["size"] > GITEE_MAX_ATTACHMENT_BYTES for asset in assets.values()):
        raise PlatformError("Gitee raw attachment exceeds the per-file limit")
    if journal and journal.get("binding") != binding:
        raise PlatformError("Gitee transaction belongs to another raw plan")
    base = "/api/v5/repos/" + project
    if api.request("GET", base).get("full_name") != project:
        raise PlatformError("Gitee repository identity differs")
    releases = base + "/releases"
    release_path = releases + "/tags/" + tag
    tag_path = base + "/commits/" + tag

    def release_body(state):
        return json.dumps({"aws_raw": binding, "mirror_state": state}, sort_keys=True, separators=(",", ":"))

    pending_body, verified_body = release_body("pending"), release_body("verified")

    def release_payload(body):
        return {"tag_name": tag, "name": tag, "body": body, "prerelease": True}

    def check_release(release):
        if (not isinstance(release, dict) or release.get("tag_name") != tag
                or release.get("prerelease") is not True
                or release.get("body") not in (pending_body, verified_body)
                or type(release.get("id")) is not int or release["id"] < 1
                or journal.get("release_id", release["id"]) != release["id"]):
            raise PlatformError("Gitee release identity or provenance differs")

    release = api.request("GET", release_path, missing=True)
    if release is None:
        if check_only:
            raise PlatformError("Gitee raw release is absent")
        if journal:
            raise PlatformError("Gitee release creation is pending; awaiting visible release")
        branch = api.request("GET", base + "/branches/main")
        if branch.get("commit", {}).get("sha") != storage["commit"]:
            raise PlatformError("Gitee native storage ref moved")
        prior_tag = api.request("GET", tag_path, missing=True)
        if prior_tag is not None and prior_tag.get("sha") != storage["commit"]:
            raise PlatformError("Gitee tag already belongs to another storage commit")
        journal.update(binding=binding)
        save()
        api.request("POST", releases, {**release_payload(pending_body), "target_commitish": storage["commit"]})
        release = api.request("GET", release_path, missing=True)

    check_release(release)
    if api.request("GET", tag_path).get("sha") != storage["commit"]:
        raise PlatformError("Gitee raw tag points to another storage commit")
    release_id = release["id"]
    attachments_path = f"{releases}/{release_id}/attach_files"

    def list_attachments():
        attachments = api.request("GET", attachments_path)
        if not isinstance(attachments, list):
            raise PlatformError("Gitee attachment list has invalid shape")
        found = {}
        for asset in attachments:
            name, asset_id = asset.get("name"), asset.get("id")
            if (name not in assets or name in found or asset.get("size") != assets[name]["size"]
                    or type(asset_id) is not int or asset_id < 1):
                raise PlatformError("Gitee attachment identity or size differs")
            found[name] = asset_id
        return found

    def verify_attachment(name, asset_id):
        payload = api.request("GET", f"{attachments_path}/{asset_id}/download", binary=True)
        verify_bytes(payload, assets[name])

    def verify_attachments():
        found = list_attachments()
        for name, asset_id in found.items():
            verify_attachment(name, asset_id)
        return set(assets) - found.keys()

    missing = verify_attachments()
    if release["body"] == verified_body:
        if missing:
            raise PlatformError("verified Gitee release is missing raw attachments")
    else:
        if check_only or journal.get("binding") != binding:
            raise PlatformError("Gitee pending release is not an owned transaction")
        journal["release_id"] = release_id
        pending = journal.get("pending_upload")
        if pending is not None and (pending not in assets or pending in missing):
            raise PlatformError("Gitee attachment upload is pending; awaiting visible attachment")
        for name in sorted(missing):
            journal["pending_upload"] = name
            save()
            api.upload_attachment(attachments_path, bundle / name, name)
            asset_id = list_attachments().get(name)
            if asset_id is None:
                raise PlatformError("Gitee attachment upload is pending; awaiting visible attachment")
            verify_attachment(name, asset_id)
        if journal.pop("pending_upload", None) is not None:
            save()
        if verify_attachments() or api.request("GET", tag_path).get("sha") != storage["commit"]:
            raise PlatformError("Gitee pending release is not ready to verify")
        api.request("PATCH", f"{releases}/{release_id}", release_payload(verified_body))
        release = api.request("GET", release_path)
        check_release(release)
        if (release["body"] != verified_body or verify_attachments()
                or api.request("GET", tag_path).get("sha") != storage["commit"]):
            raise PlatformError("Gitee published identity is not verified")
    return {"platform": "gitee", "binding": binding, "release_id": release_id, "verified": True}
