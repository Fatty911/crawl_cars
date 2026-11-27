"""Stage verified Pages assets in an isolated Codeberg checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from scripts.prepare_cnb_pages import checked_assets, manifest_assets, safe_path


MANIFEST = "data/manifest.json"
DOMAIN = "cars3.jiucai.eu.org"


def inside_checkout(checkout, relative):
    path = checkout / safe_path(relative)
    if path.resolve() != path:
        raise ValueError("Codeberg checkout has a symlink in a publication path")
    return path


def stage_site(site, checkout, release, release_manifest):
    site, checkout = site.resolve(), checkout.resolve()
    if site.is_relative_to(checkout) or checkout.is_relative_to(site):
        raise ValueError("Codeberg site and checkout must be separate directories")
    selected = re.fullmatch(r"cnb-data-(\d{8})-remerged-verified-r([1-9]\d*)a([1-9]\d*)", release)
    if not selected:
        raise ValueError("Codeberg requires an exact verified processing release")
    original = release_manifest.read_bytes()
    upstream = json.loads(original)
    manifest = json.loads((site / MANIFEST).read_bytes())
    provenance = upstream["provenance"]
    if (not re.fullmatch(r"aws-raw-\d{8}T\d{6}Z", provenance.get("awsRawRelease", ""))
            or not re.fullmatch(r"[0-9a-f]{64}", provenance.get("awsRawManifestSha256", ""))
            or selected.groups() != (upstream.get("date"), str(provenance.get("workflowRunId")), str(provenance.get("workflowRunAttempt")))
            or manifest["provenance"] != provenance
            or manifest["rowCount"] != upstream["rowCount"] or upstream["rowCount"] <= 0
            or manifest["filteredRowCount"] != upstream["filteredRowCount"]):
        raise ValueError("Codeberg payload differs from the verified processing release")
    assets = checked_assets(site, manifest)
    # Read required frontend before any checkout mutation.
    frontend_sha256 = hashlib.sha256((site / "app.js").read_bytes()).hexdigest()
    domains = inside_checkout(checkout, ".domains")
    if DOMAIN not in domains.read_text().splitlines():
        raise ValueError("Codeberg checkout lacks the existing custom-domain mapping")
    paths = list(site.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("Codeberg payload contains a symlink")
    payload = {p.relative_to(site).as_posix(): p for p in paths if p.is_file()}
    if any(".git" in Path(name).parts for name in payload):
        raise ValueError("Codeberg payload contains Git metadata")
    for name in (".domains", "CNAME", MANIFEST):
        payload.pop(name, None)
    if not assets.keys() <= payload.keys():
        raise ValueError("Codeberg asset inventory contains an excluded file")
    target_manifest = inside_checkout(checkout, MANIFEST)
    previous = json.loads(target_manifest.read_bytes())
    retired = {name for name, _ in manifest_assets(previous["files"])
               if safe_path(name).parts[0] == "data" and name not in payload and name != MANIFEST}
    copy_plan = [(source, inside_checkout(checkout, name)) for name, source in payload.items()]
    retire_plan = [inside_checkout(checkout, name) for name in sorted(retired)]
    if any(path.exists() and not path.is_file() for path in retire_plan):
        raise ValueError("superseded Codeberg manifest reference is not a regular file")
    for source, target in copy_plan:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for target in retire_plan:
        target.unlink(missing_ok=True)
    manifest["publication"] = {
        "platform": "codeberg-pages",
        "project": "xuerui911/crawl-cars",
        "sourceVerifiedRelease": release,
        "sourceManifestSha256": hashlib.sha256(original).hexdigest(),
        "frontendAppSha256": frontend_sha256,
    }
    target_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    if checked_assets(checkout, manifest) != assets:
        raise ValueError("staged Codeberg asset bytes differ from the verified site")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--release-manifest", type=Path, required=True)
    args = parser.parse_args()
    stage_site(args.site, args.checkout, args.release, args.release_manifest)
