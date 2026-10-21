"""Deploy the verified CNB archive without rebuilding or rewriting its payload."""
import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import time
import urllib.parse
import urllib.request
import zipfile


def safe_path(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"invalid relative path: {value!r}")
    parsed = urllib.parse.urlsplit(value)
    decoded = urllib.parse.unquote(parsed.path)
    path = PurePosixPath(decoded)
    if parsed.scheme or parsed.netloc or path.is_absolute() or ":" in decoded:
        raise ValueError(f"non-local path: {value!r}")
    if "\\" in decoded or ".." in path.parts or not path.parts:
        raise ValueError(f"path traversal: {value!r}")
    return path


def file_references(value):
    """收集 manifest.files 里的文件引用。

    10-21：`latestJsonChunks` 这类分片清单（[{"path","sha256","rowCount","size"}]）也在这里。
    带 path 的条目只按 path 计；纯标量（rowCount/size 等元数据）不再当错误——旧版对 int 直接
    抛 ValueError，带分片的 manifest 根本进不了部署链，而分片正是绕开 114MB 单文件的那版契约。
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        path = value.get("path")
        if isinstance(path, str):
            yield path
        else:
            for child in value.values():
                yield from file_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from file_references(child)


def reference_checksums(value, found=None):
    """(路径 -> sha256)：分片/清单条目自带 sha256 时收进来，除存在性外再做一次内容校验。"""
    found = {} if found is None else found
    if isinstance(value, dict):
        path, sha = value.get("path"), value.get("sha256")
        if isinstance(path, str) and isinstance(sha, str):
            found[path] = sha
        else:
            for child in value.values():
                reference_checksums(child, found)
    elif isinstance(value, list):
        for child in value:
            reference_checksums(child, found)
    return found


def prepare(archive, expected_manifest, site):
    site = Path(site)
    if site.exists():
        raise ValueError(f"destination must not exist: {site}")
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        seen = set()
        for entry in members:
            path = safe_path(entry.filename)
            mode = entry.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError(f"non-regular ZIP member: {entry.filename}")
            if path in seen:
                raise ValueError(f"duplicate ZIP member: {entry.filename}")
            seen.add(path)
        site.mkdir(parents=True)
        for entry in members:
            target = site.joinpath(*safe_path(entry.filename).parts)
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(entry) as source, target.open("xb") as destination:
                    shutil.copyfileobj(source, destination)
    staged = site / "data" / "manifest.json"
    if staged.read_bytes() != Path(expected_manifest).read_bytes():
        raise ValueError("archive manifest differs from Release manifest asset")
    manifest = json.loads(staged.read_bytes())
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    if not (site / "index.html").is_file():
        raise ValueError("site index.html is missing")
    files = manifest.get("files", {})
    inventory = isinstance(files, dict) and bool(files) and all(
        isinstance(metadata, dict) and "sha256" in metadata
        for metadata in files.values()
    )
    references = list(files) if inventory else list(file_references(files))
    if not references and not any(path.name != "manifest.json" for path in (site / "data").glob("*.json")):
        raise ValueError("manifest has no data files")
    # 校验口径分两层：清单式（files 值都是 {"sha256": ...}）与分片式（latestJsonChunks 每条带 sha256），
    # 都做内容校验；纯字符串引用只查存在性（历史契约保持）。
    checksums = ({reference: files[reference]["sha256"] for reference in files} if inventory
                 else {reference: sha for reference, sha in reference_checksums(files).items()
                       if reference in set(references)})
    for reference in references:
        target = site.joinpath(*safe_path(reference).parts)
        if not target.is_file():
            raise ValueError(f"manifest references missing file: {reference}")
        if reference in checksums:
            import hashlib
            if hashlib.sha256(target.read_bytes()).hexdigest() != checksums[reference]:
                raise ValueError(f"manifest checksum mismatch: {reference}")
    print(f"verified CNB site: {len(members)} archive members, {len(references)} references")


def verify(site, page_url, attempts=12, interval=10):
    expected = (Path(site) / "data" / "manifest.json").read_bytes()
    url = urllib.parse.urljoin(page_url.rstrip("/") + "/", "data/manifest.json")
    for attempt in range(1, attempts + 1):
        separator = "&" if "?" in url else "?"
        request = urllib.request.Request(
            url + separator + urllib.parse.urlencode({"cnb_verify": time.time_ns()}),
            headers={"User-Agent": "Mozilla/5.0 CNB-Pages-Verification",
                     "Cache-Control": "no-cache", "Pragma": "no-cache"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                actual = response.read()
            if actual == expected:
                print("deployed manifest matches verified CNB payload byte-for-byte")
                return
            print(f"manifest mismatch on attempt {attempt}/{attempts}")
        except Exception as exc:
            print(f"manifest readback attempt {attempt}/{attempts}: {exc}")
        if attempt < attempts:
            time.sleep(interval)
    raise ValueError("deployed manifest did not match verified CNB payload")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    parser.add_argument("--archive")
    parser.add_argument("--manifest")
    parser.add_argument("--verify-url")
    args = parser.parse_args()
    if args.verify_url:
        verify(args.site, args.verify_url)
    elif args.archive and args.manifest:
        prepare(args.archive, args.manifest, args.site)
    else:
        parser.error("provide --archive and --manifest, or --verify-url")


if __name__ == "__main__":
    main()
