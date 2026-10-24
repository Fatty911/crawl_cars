#!/usr/bin/env python3
"""Copy a verified site and shard its complete JSON payload for Cloudflare Pages."""

import argparse
import gzip
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_cnb_pages import checked_assets, safe_path


DEFAULT_MAX_BYTES = 10 * 1024 * 1024
CLOUDFLARE_MAX_BYTES = 25 * 1024 * 1024


def local_path(root, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"invalid local manifest path: {value!r}")
    try:
        parts = safe_path(value).parts
    except ValueError as exc:
        raise ValueError(f"manifest path escapes site or is invalid: {value!r}") from exc
    path = root.joinpath(*parts).resolve()
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
    canonical = lambda rows: json.dumps(rows, ensure_ascii=False, sort_keys=True,
                                        separators=(",", ":"), allow_nan=False)
    if canonical(rebuilt) != canonical(expected_rows):
        raise ValueError("reconstructed dataset differs in rows, identity, facts or order")


def digest_file(path, opener=open):
    digest = hashlib.sha256()
    size = 0
    with opener(path, "rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def compress_exact_download(path, staging):
    """Preserve every original byte, including CSV columns/order/quoting/BOM."""
    original_sha, original_size = digest_file(path)
    target = path.with_name(path.name + ".gz")
    with path.open("rb") as source, target.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=1, mtime=0) as zipped:
            shutil.copyfileobj(source, zipped, 1024 * 1024)
    if digest_file(target, gzip.open) != (original_sha, original_size):
        raise ValueError("compressed download differs from its complete original")
    sha, size = digest_file(target)
    if size > CLOUDFLARE_MAX_BYTES:
        raise ValueError("complete compressed download exceeds Cloudflare asset limit")
    descriptor = {"path": target.relative_to(staging).as_posix(), "sha256": sha, "size": size,
                  "compression": "gzip", "originalPath": path.relative_to(staging).as_posix(),
                  "originalSha256": original_sha, "originalSize": original_size}
    path.unlink()  # Only the staging copy, after complete-byte equivalence is proved.
    return descriptor


def rewrite_references(value, compressed):
    if isinstance(value, str):
        replacement = compressed.get(safe_path(value).as_posix())
        return replacement["path"] if replacement else value
    if isinstance(value, list):
        return [rewrite_references(item, compressed) for item in value]
    if isinstance(value, dict):
        if isinstance(value.get("path"), str):
            replacement = compressed.get(safe_path(value["path"]).as_posix())
            return dict(value, **replacement) if replacement else dict(value)
        return {key: rewrite_references(item, compressed) for key, item in value.items()}
    raise ValueError("unsupported manifest file reference")


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
    if any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("input site must contain only regular files and directories")
    checked_assets(source, manifest)
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
        if files.get("latestJsonChunks"):
            verify_chunks(staging, files["latestJsonChunks"], latest, CLOUDFLARE_MAX_BYTES)
        if not files.get("latestJsonChunks") or any(item["size"] > max_bytes for item in files["latestJsonChunks"]):
            files["latestJsonChunks"] = write_chunks(latest, staging, "latest", max_bytes)
        latest_ref = files.get("latestJson", "data/latest.json")
        compressed = {}
        if files.get("filteredJsonChunks"):
            if filtered is None:
                raise ValueError("filtered chunks require a complete filtered dataset")
            verify_chunks(staging, files["filteredJsonChunks"], filtered, CLOUDFLARE_MAX_BYTES)
        if filtered_ref and local_path(staging, filtered_ref).stat().st_size > max_bytes:
            if not files.get("filteredJsonChunks") or any(item["size"] > max_bytes for item in files["filteredJsonChunks"]):
                files["filteredJsonChunks"] = write_chunks(filtered, staging, "filtered", max_bytes)
        for path in list(staging.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(staging).as_posix()
            data_snapshot = path.parent == staging / "data" and (
                path.name == "latest.json" or path.name.startswith("latest_")
                or path.name == "filtered.json" or path.name.startswith("filtered_"))
            size = path.stat().st_size
            if size > max_bytes and (path.suffix.lower() == ".csv" or (
                    path.suffix == ".json" and (data_snapshot or relative in {latest_ref, filtered_ref}))):
                compressed[relative] = compress_exact_download(path, staging)
            elif size > CLOUDFLARE_MAX_BYTES:
                raise ValueError(f"unsupported oversized asset: {relative}")
        files = rewrite_references(files, compressed)
        descriptors = {item["path"]: dict(item) for item in files.get("additionalDataAssets", [])}
        for path in staging.rglob("*"):
            if path.is_file() and path.name != "manifest.json" and path.suffix.lower() in {".json", ".csv", ".gz"}:
                relative = path.relative_to(staging).as_posix()
                sha, size = digest_file(path)
                entry = descriptors.setdefault(relative, {"path": relative})
                entry.update(sha256=sha, size=size)
        for item in compressed.values():
            descriptors[item["path"]].update(item)
        files["additionalDataAssets"] = list(descriptors.values())
        manifest["files"] = files
        manifest["compressedDownloads"] = list(compressed.values())
        manifest["omittedDownloads"] = []
        checked_assets(staging, manifest)
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
