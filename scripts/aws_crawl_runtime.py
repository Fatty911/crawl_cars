"""Shared runtime boundary for AWS source-only crawlers."""

from __future__ import annotations

import errno
import json
import os
import re
import socket
import stat
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROXY = "http://127.0.0.1:17890"
CONTROLLER = "http://127.0.0.1:19090"
def validate_round_robin_config(config) -> None:
    if not isinstance(config, dict) or (config.get("mixed-port") != 17890 and config.get("port") != 17890):
        raise ValueError("Mihomo config does not bind the expected collector proxy port")
    if config.get("external-controller") != "127.0.0.1:19090" or config.get("rules") != ["MATCH,CRAWL"]:
        raise ValueError("Mihomo config does not use the loopback controller and CRAWL rule")
    groups = config.get("proxy-groups")
    crawl = [group for group in groups or [] if isinstance(group, dict) and group.get("name") == "CRAWL"]
    if (len(crawl) != 1 or crawl[0].get("type") != "load-balance"
            or crawl[0].get("strategy") != "round-robin" or crawl[0].get("empty-fallback") != "REJECT"):
        raise ValueError("Mihomo CRAWL config must use round-robin and reject fallback")


def check_mihomo_strategy() -> None:
    result = subprocess.run(["systemctl", "show", "crawl-cars-mihomo.service", "-p", "MainPID", "--value"],
                            capture_output=True, text=True, check=True, timeout=5)
    pid = result.stdout.strip()
    if not re.fullmatch(r"[1-9][0-9]*", pid):
        raise ValueError("collector Mihomo service has no running process")
    arguments = (Path("/proc") / pid / "cmdline").read_bytes().split(b"\0")
    config_flags = [index for index, arg in enumerate(arguments) if arg in (b"-f", b"--config")]
    if len(config_flags) != 1 or config_flags[0] + 1 >= len(arguments):
        raise ValueError("collector Mihomo process does not identify one configuration file")
    path = Path(os.fsdecode(arguments[config_flags[0] + 1]))
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("collector Mihomo configuration path must be an absolute regular file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022 or info.st_size > 1024 * 1024:
            raise ValueError("collector Mihomo configuration is not an owned bounded file")
        try:
            config = yaml.safe_load(stream.read(1024 * 1024 + 1))
        except yaml.YAMLError:
            raise ValueError("collector Mihomo configuration cannot be parsed") from None
    validate_round_robin_config(config)


def check_proxy() -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def read(path):
        with opener.open(CONTROLLER + path, timeout=5) as response:
            return json.load(response)

    group = read("/proxies/CRAWL")
    members = set(group.get("all", []))
    provider = read("/providers/proxies/crawler-nodes")
    alive = {node["name"] for node in provider.get("proxies", []) if node.get("alive") is True}
    if (group.get("type") != "LoadBalance" or group.get("emptyFallback") != "REJECT"
            or members & {"DIRECT", "COMPATIBLE", "GLOBAL", "REJECT"}
            or len(members & alive) < 2):
        raise ValueError("Mihomo CRAWL must have at least two healthy nodes and reject fallback")
    rules = read("/rules").get("rules", [])
    if len(rules) != 1 or rules[0].get("type") != "Match" or rules[0].get("proxy") != "CRAWL":
        raise ValueError("Mihomo routing must send every destination to CRAWL")
    check_mihomo_strategy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        os.environ[key] = os.environ[key.lower()] = PROXY
    os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"
    os.environ["PROXY_ENABLED"] = "true"
    os.environ["CHROME_PROXY_SERVER"] = PROXY


def check_blocked(ip: str, port: int) -> None:
    try:
        with socket.create_connection((ip, port), timeout=2):
            pass
    except TimeoutError:
        return
    except OSError as error:
        if error.errno in {errno.EACCES, errno.EPERM}:
            return
        raise
    raise ValueError("direct egress is possible inside the collection unit")


class WriteDurabilityUncertain(OSError):
    """Replacement occurred, but directory durability could not be confirmed."""


def write_json(path: Path, value: object) -> None:
    # All mutations are relative to one opened Linux directory, not a re-resolved path.
    # A renamed/replaced parent is reported, never redirected into a new directory.
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary_name = None
    temporary_created = False
    replaced = False
    try:
        opened = os.fstat(directory_fd)
        def check_parent_identity():
            current = path.parent.stat(follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                raise OSError(errno.ESTALE, "parent directory identity changed")
        os.fsync(directory_fd)
        check_parent_identity()
        temporary_name = ".refresh-" + os.urandom(16).hex()
        file_fd = os.open(temporary_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o600, dir_fd=directory_fd)
        temporary_created = True
        try:
            handle = os.fdopen(file_fd, "w", encoding="utf-8")
        except BaseException:
            os.close(file_fd)
            raise
        with handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        check_parent_identity()
        os.replace(temporary_name, path.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        replaced = True
        temporary_name = None
        try:
            os.fsync(directory_fd)
            check_parent_identity()
        except OSError as error:
            raise WriteDurabilityUncertain(
                error.errno,
                "replacement completed in opened directory; durability or parent identity unconfirmed; retain file and reconcile before retry",
            ) from error
    finally:
        try:
            if temporary_created and temporary_name is not None and not replaced:
                # Never re-resolve the parent path during cleanup.
                os.unlink(temporary_name, dir_fd=directory_fd)
        finally:
            os.close(directory_fd)


def run_unit(module: str, args: list[str], probe_ip: str, probe_port: int, runtime_seconds: int) -> None:
    """Run collection inside a bounded systemd unit with only loopback egress."""
    with socket.create_connection((probe_ip, probe_port), timeout=3):
        pass
    unit = os.environ.get("AWS_CRAWL_UNIT_NAME", "")
    if unit and not re.fullmatch(r"crawl-cars-aws-collector", unit):
        raise ValueError("invalid owned collection unit")
    unit_args = ["--unit=" + unit] if unit else []
    subprocess.run([
        "systemd-run", "--quiet", "--wait", "--pipe", "--collect",
        *unit_args,
        "--property=IPAddressDeny=any", "--property=IPAddressAllow=localhost",
        "--property=MemoryMax=2G", "--property=TasksMax=64",
        f"--property=RuntimeMaxSec={runtime_seconds}", f"--working-directory={ROOT}",
        sys.executable, "-m", module, "--worker", *args,
    ], check=True)
