import json
import subprocess

import pytest

from scripts.stage_codeberg_pages import DOMAIN, stage_site


RELEASE = "cnb-data-20261112-remerged-verified-r123a1"


def json_file(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def git(cwd, *args):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


@pytest.fixture
def site_and_checkout(tmp_path):
    site, target = tmp_path / "site", tmp_path / "checkout"
    manifest = {
        "date": "20261112",
        "rowCount": 1,
        "filteredRowCount": 1,
        "provenance": {
            "awsRawRelease": "aws-raw-20261112T065253Z",
            "awsRawManifestSha256": "c" * 64,
            "workflowRunId": "123",
            "workflowRunAttempt": "1",
        },
        "files": {"latestJson": "data/latest.json"},
    }
    json_file(site / "data/manifest.json", manifest)
    json_file(site / "data/latest.json", [{"sample": 1}])
    (site / "app.js").write_text("/* verified */")
    (site / "CNAME").write_text("github-host")
    json_file(target / "data/manifest.json", {"files": {"latestJson": "data/old.json"}})
    json_file(target / "data/old.json", [{"old": 1}])
    (target / "CNAME").write_text("native-host")
    (target / ".domains").write_text(DOMAIN + "\n")
    (target / "unrelated.txt").write_text("native content")
    release_manifest = tmp_path / "release-manifest.json"
    json_file(release_manifest, manifest)
    return site, target, release_manifest


def test_pages_branch_update_is_fast_forward_and_repeatable(tmp_path, site_and_checkout):
    site, target, release_manifest = site_and_checkout
    git(target, "init", "-b", "pages")
    git(target, "config", "user.name", "Pages fixture")
    git(target, "config", "user.email", "fixture@example.com")
    git(target, "add", "-A")
    git(target, "commit", "-m", "native pages")
    parent = git(target, "rev-parse", "HEAD")
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(target, "remote", "add", "origin", str(remote))
    git(target, "push", "origin", "HEAD:refs/heads/pages")
    stage_site(site, target, RELEASE, release_manifest)
    assert (target / ".domains").read_text() == DOMAIN + "\n"
    assert (target / "CNAME").read_text() == "native-host"
    assert (target / "unrelated.txt").read_text() == "native content"
    assert not (target / "data/old.json").exists()
    git(target, "add", "-A")
    git(target, "commit", "-m", "verified Pages fixture")
    git(target, "push", "origin", "HEAD:refs/heads/pages")
    assert git(remote, "rev-parse", "refs/heads/pages^") == parent
    stage_site(site, target, RELEASE, release_manifest)
    assert git(target, "status", "--porcelain") == ""


def test_mismatched_release_fails_before_checkout_write(site_and_checkout):
    site, target, release_manifest = site_and_checkout
    with pytest.raises(ValueError, match="differs"):
        stage_site(site, target, RELEASE.replace("r123a1", "r124a1"), release_manifest)
    assert (target / "data/old.json").exists()
    assert not (target / "data/latest.json").exists()


def test_symlinked_target_is_rejected_without_touching_external_file(tmp_path, site_and_checkout):
    site, target, release_manifest = site_and_checkout
    other = tmp_path / "external.js"
    other.write_text("preserve")
    (target / "app.js").symlink_to(other)
    with pytest.raises(ValueError, match="symlink"):
        stage_site(site, target, RELEASE, release_manifest)
    assert other.read_text() == "preserve"
