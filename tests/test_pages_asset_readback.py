import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import threading
from unittest.mock import patch

import pytest

SPEC = importlib.util.spec_from_file_location(
    "pages_asset_bridge", Path(__file__).resolve().parents[1] / "scripts/prepare_cnb_pages.py"
)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


@pytest.fixture
def deployed(tmp_path):
    local, remote = tmp_path / "local", tmp_path / "remote"
    content = b'[{"id":"car-2026"}]'
    descriptor = {"path": "data/latest-0.json", "sha256": hashlib.sha256(content).hexdigest(),
                  "size": len(content), "rowCount": 1}
    manifest = json.dumps({"files": {"latestJsonChunks": [descriptor]}}).encode()
    for root in (local, remote):
        (root / "data").mkdir(parents=True)
        (root / "data/manifest.json").write_bytes(manifest)
        (root / "data/latest-0.json").write_bytes(content)
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(remote)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield local, remote, f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_full_readback_supports_chunk_descriptors(deployed):
    local, _, url = deployed
    bridge.verify(local, url, attempts=1, verify_data=True)


@pytest.mark.parametrize("fault", ["corrupt", "missing"])
def test_matching_manifest_cannot_hide_broken_data(deployed, fault):
    local, remote, url = deployed
    asset = remote / "data/latest-0.json"
    if fault == "corrupt":
        asset.write_bytes(asset.read_bytes().replace(b"2026", b"2025"))
    else:
        asset.unlink()
    with pytest.raises(ValueError, match="did not match"):
        bridge.verify(local, url, attempts=1, verify_data=True)


def test_local_descriptor_size_is_also_verified(deployed):
    local, _, _ = deployed
    manifest = json.loads((local / "data/manifest.json").read_bytes())
    manifest["files"]["latestJsonChunks"][0]["size"] += 1
    with pytest.raises(ValueError, match="size mismatch"):
        bridge.checked_assets(local, manifest)


@pytest.mark.parametrize("fault", [None, "corrupt", "missing"])
def test_workflow_named_path_manifest_verifies_actual_bytes(deployed, fault):
    local, remote, url = deployed
    # Same plain-string files shape emitted by remerge-and-publish.yml.
    manifest = json.dumps({"files": {"latestJson": "data/latest-0.json"}}).encode()
    for root in (local, remote):
        (root / "data/manifest.json").write_bytes(manifest)
    asset = remote / "data/latest-0.json"
    if fault == "corrupt":
        asset.write_bytes(asset.read_bytes().replace(b"2026", b"2025"))
    elif fault == "missing":
        asset.unlink()
    if fault:
        with pytest.raises(ValueError, match="did not match"):
            bridge.verify(local, url, attempts=1, verify_data=True)
    else:
        bridge.verify(local, url, attempts=1, verify_data=True)


def test_stale_asset_is_retried_after_manifest_matches(deployed):
    local, remote, url = deployed
    asset = remote / "data/latest-0.json"
    correct = asset.read_bytes()
    asset.write_bytes(correct.replace(b"2026", b"2025"))
    def propagate(_interval):
        asset.write_bytes(correct)
    with patch.object(bridge.time, "sleep", side_effect=propagate) as sleep:
        bridge.verify(local, url, attempts=2, interval=0, verify_data=True)
    sleep.assert_called_once_with(0)
