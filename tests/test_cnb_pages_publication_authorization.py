import importlib.util
import json
from pathlib import Path
import zipfile

import pytest


script = Path(__file__).resolve().parents[1] / "scripts" / "prepare_cnb_pages.py"
spec = importlib.util.spec_from_file_location("prepare_cnb_pages", script)
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)


def make_release(root, marker):
    manifest = {"date": "20261117", "files": {"filteredJson": "data/filtered.json.gz"}, **marker}
    expected = root / "manifest.json"
    expected.write_bytes(json.dumps(manifest).encode())
    archive = root / "site.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("data/manifest.json", expected.read_bytes())
        bundle.writestr("data/filtered.json.gz", b"bounded fixture")
        bundle.writestr("index.html", b"<title>fixture</title>")
    return archive, expected


@pytest.mark.parametrize("flag", [False, None, 0, "true"])
def test_explicit_non_approval_stops_before_extraction(tmp_path, flag):
    archive, manifest = make_release(tmp_path, {"publication_authorized": flag})
    site = tmp_path / "site"
    with pytest.raises(ValueError, match="does not authorize publication"):
        pages.prepare(archive, manifest, site)
    assert not site.exists()


@pytest.mark.parametrize("flag", [{"publication_authorized": True}, {}])
def test_approved_or_legacy_pinned_release_keeps_existing_checks(tmp_path, flag):
    archive, manifest = make_release(tmp_path, flag)
    site = tmp_path / "site"
    pages.prepare(archive, manifest, site)
    assert (site / "data/manifest.json").read_bytes() == manifest.read_bytes()
    assert (site / "data/filtered.json.gz").read_bytes() == b"bounded fixture"


def test_readback_rejects_an_explicitly_unapproved_manifest(tmp_path, monkeypatch):
    site = tmp_path / "site"
    (site / "data").mkdir(parents=True)
    (site / "data/manifest.json").write_text('{"publication_authorized":false}', encoding="utf-8")

    def no_network(*_args, **_kwargs):
        pytest.fail("readback should reject before fetching the site")

    monkeypatch.setattr(pages.urllib.request, "urlopen", no_network)
    with pytest.raises(ValueError, match="does not authorize publication"):
        pages.verify(site, "https://fixture.invalid/", attempts=1, verify_data=False)
