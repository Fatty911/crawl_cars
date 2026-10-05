"""断点续跑必须能被产出它的那一轮自己读回来。

CI 从 CNB 运行时 GITHUB_REPOSITORY 不存在，写入端与校验端曾使用不一致的默认值，
导致每一轮都判定 producer identity mismatch 并退回从零重爬。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _crawler():
    spec = importlib.util.spec_from_file_location("crawl_yiche", ROOT / "scripts" / "crawl_yiche.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(**overrides) -> dict:
    crawler = _crawler()
    args = {
        "source_run_id": "",
        "source_artifact_id": "",
        "source_artifact_sha256": "0" * 64,
        "source_checkpoint_sha256": "",
        "source_head_sha": "",
        "source_crawler_sha256": crawler.file_sha256(str(ROOT / "scripts" / "crawl_yiche.py")),
    }
    args.update(overrides)
    return args


def _write_checkpoint(tmp_path: pathlib.Path, producer: dict) -> tuple[str, str]:
    crawler = _crawler()
    payload = {
        "format": "yiche-raw-progress",
        "schema_version": crawler.YICHE_CHECKPOINT_SCHEMA_VERSION,
        "state_compat_version": crawler.YICHE_CHECKPOINT_STATE_COMPAT_VERSION,
        "producer": producer,
        "resume_state": {},
        "rows": [],
    }
    path = tmp_path / "yiche_frontier.json"
    blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    path.write_bytes(blob)
    return str(path), hashlib.sha256(blob).hexdigest()


def test_repository_identity_resolver_is_used_by_both_sides() -> None:
    crawler = _crawler()
    assert callable(getattr(crawler, "producer_repository_identity", None)), (
        "写入端与校验端必须共用同一个仓库身份解析函数"
    )


def test_cnb_environment_resumes_its_own_checkpoint(tmp_path, monkeypatch) -> None:
    """无 GITHUB_REPOSITORY 时，本轮写下的 producer 必须能通过续跑校验。"""
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    crawler = _crawler()
    producer = {
        "repository": crawler.producer_repository_identity(),
        "workflow": ".github/workflows/crawl-yiche.yml",
        "run_id": "",
        "head_sha": "",
        "crawler_sha256": crawler.file_sha256(str(ROOT / "scripts" / "crawl_yiche.py")),
    }
    path, sha = _write_checkpoint(tmp_path, producer)
    try:
        crawler.load_resume_checkpoint(path, **_identity(source_checkpoint_sha256=sha))
    except ValueError as exc:
        # 允许在身份闸门之后的结构校验上失败，但绝不能因身份被拒
        assert "producer identity mismatch" not in str(exc), (
            f"CNB 自检断点被身份闸门拒绝：{exc}"
        )
    except Exception as exc:  # pragma: no cover - 非 ValueError 说明校验逻辑本身坏了
        raise AssertionError(f"unexpected failure type: {exc!r}")


def test_foreign_repository_checkpoint_is_still_rejected(tmp_path, monkeypatch) -> None:
    """修默认值不能把闸门拆掉：外来仓库的断点必须仍然被拒。"""
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    crawler = _crawler()
    producer = {
        "repository": "someone-else/other-repo",
        "workflow": ".github/workflows/crawl-yiche.yml",
        "run_id": "",
        "head_sha": "",
        "crawler_sha256": crawler.file_sha256(str(ROOT / "scripts" / "crawl_yiche.py")),
    }
    path, sha = _write_checkpoint(tmp_path, producer)
    import pytest

    with pytest.raises(ValueError, match="producer identity mismatch"):
        crawler.load_resume_checkpoint(path, **_identity(source_checkpoint_sha256=sha))
