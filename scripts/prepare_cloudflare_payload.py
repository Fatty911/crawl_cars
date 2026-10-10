#!/usr/bin/env python3
"""Copy a verified site and shard its complete JSON payload for Cloudflare Pages."""

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path


DEFAULT_MAX_BYTES = 10 * 1024 * 1024
CLOUDFLARE_MAX_BYTES = 25 * 1024 * 1024


def local_path(root, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"invalid local manifest path: {value!r}")
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"manifest path escapes site: {value!r}")
    return path


def load_rows(path, *, allow_empty=False):
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"JSON rows must be an object array: {path}")
    if not rows and not allow_empty:
        raise ValueError(f"complete latest dataset must not be empty: {path}")
    return rows


def write_chunks(rows, root, prefix, max_bytes):
    descriptors = []
    encoded = []
    size = 2

    def flush():
        payload = b"[" + b",".join(encoded) + b"]"
        digest = hashlib.sha256(payload).hexdigest()
        relative = f"data/{prefix}_chunks/{prefix}-{len(descriptors):05d}-{digest[:16]}.json"
        path = local_path(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        descriptors.append({"path": relative, "sha256": digest,
                            "rowCount": len(encoded), "size": len(payload)})

    for index, row in enumerate(rows):
        item = json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(item) + 2 > max_bytes:
            raise ValueError(f"single {prefix} row {index} exceeds byte cap {max_bytes}")
        additional = len(item) + (1 if encoded else 0)
        if encoded and size + additional > max_bytes:
            flush()
            encoded = []
            size = 2
            additional = len(item)
        encoded.append(item)
        size += additional
    if encoded or not rows:
        flush()
    verify_chunks(root, descriptors, rows, max_bytes)
    return descriptors


def verify_chunks(root, descriptors, expected_rows, max_bytes):
    rebuilt = []
    paths = set()
    for descriptor in descriptors:
        if descriptor["path"] in paths:
            raise ValueError("duplicate chunk path")
        paths.add(descriptor["path"])
        payload = local_path(root, descriptor["path"]).read_bytes()
        if len(payload) > max_bytes or len(payload) != descriptor["size"]:
            raise ValueError("chunk byte size mismatch")
        if hashlib.sha256(payload).hexdigest() != descriptor["sha256"]:
            raise ValueError("chunk hash mismatch")
        rows = json.loads(payload)
        if not isinstance(rows, list) or len(rows) != descriptor["rowCount"]:
            raise ValueError("chunk row count mismatch")
        rebuilt.extend(rows)
    if rebuilt != expected_rows:
        raise ValueError("reconstructed dataset differs in rows, identity, facts or order")


def prepare_payload(source, output, max_bytes=DEFAULT_MAX_BYTES):
    source, output = Path(source).resolve(), Path(output).resolve()
    if max_bytes < 2 or max_bytes > CLOUDFLARE_MAX_BYTES:
        raise ValueError("byte cap must be between 2 and 25 MiB")
    if source == output or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("input and output must be separate, non-nested directories")
    if output.exists():
        raise ValueError("output already exists; choose a new output directory")
    manifest = json.loads((source / "data/manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]
    latest = load_rows(local_path(source, files.get("latestJson", "data/latest.json")))
    if manifest.get("rowCount") != len(latest):
        raise ValueError("manifest rowCount does not match the complete latest dataset")
    filtered_ref = files.get("filteredJson")
    filtered = load_rows(local_path(source, filtered_ref), allow_empty=True) if filtered_ref else None
    if filtered is not None and manifest.get("filteredRowCount") != len(filtered):
        raise ValueError("manifest filteredRowCount does not match filtered dataset")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as temporary:
        staging = Path(temporary) / "site"
        shutil.copytree(source, staging)
        files["latestJsonChunks"] = write_chunks(latest, staging, "latest", max_bytes)
        latest_ref = files.pop("latestJson", "data/latest.json")
        removed = {latest_ref}
        omitted = []
        if filtered_ref and local_path(staging, filtered_ref).stat().st_size > max_bytes:
            files["filteredJsonChunks"] = write_chunks(filtered, staging, "filtered", max_bytes)
            files.pop("filteredJson")
            removed.add(filtered_ref)
        for path in list(staging.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(staging).as_posix()
            data_snapshot = path.parent == staging / "data" and (
                path.name == "latest.json" or path.name.startswith("latest_")
                or path.name == "filtered.json" or path.name.startswith("filtered_"))
            size = path.stat().st_size
            if relative in removed or (data_snapshot and size > max_bytes and path.suffix == ".json"):
                path.unlink()
                removed.add(relative)
            elif path.suffix.lower() == ".csv" and size > max_bytes:
                path.unlink()
                removed.add(relative)
                omitted.append({"path": relative, "size": size,
                                "reason": "download exceeds Cloudflare payload byte cap; complete JSON remains in shards"})
            elif size > CLOUDFLARE_MAX_BYTES:
                raise ValueError(f"unsupported oversized asset: {relative}")
        for key, value in list(files.items()):
            if isinstance(value, str):
                if value in removed:
                    files.pop(key)
                elif not local_path(staging, value).is_file():
                    raise ValueError(f"manifest refers to missing file: {value}")
            elif isinstance(value, list):
                for descriptor in value:
                    if not isinstance(descriptor, dict) or not local_path(staging, descriptor.get("path")).is_file():
                        raise ValueError(f"manifest refers to missing chunk: {descriptor}")
            else:
                raise ValueError(f"unsupported manifest file reference: {key}")
        manifest["omittedDownloads"] = omitted
        (staging / "data/manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        for path in staging.rglob("*"):
            if path.is_file() and path.stat().st_size > CLOUDFLARE_MAX_BYTES:
                raise ValueError(f"asset exceeds Cloudflare 25 MiB limit: {path.relative_to(staging)}")
        staging.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("site"))
    parser.add_argument("--output", type=Path, default=Path("cf-site"))
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args()
    try:
        manifest = prepare_payload(args.input, args.output, args.max_bytes)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Cloudflare payload preparation failed: {exc}\n")
    print(json.dumps({"output": str(args.output), "rowCount": manifest["rowCount"],
                      "chunks": len(manifest["files"]["latestJsonChunks"]),
                      "omittedDownloads": manifest["omittedDownloads"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
