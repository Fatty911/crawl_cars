"""403 后必须换连接，否则重试仍打在同一个被封的出口 IP 上。"""

from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _crawler():
    spec = importlib.util.spec_from_file_location("crawl_yiche", ROOT / "scripts" / "crawl_yiche.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CRAWLER = _crawler()


class _FakeSession:
    def __init__(self, fail_on_close=False):
        self.closed = 0
        self.fail_on_close = fail_on_close

    def close(self):
        self.closed += 1
        if self.fail_on_close:
            raise RuntimeError("close blew up")


def test_new_session_carries_browser_user_agent() -> None:
    session = CRAWLER.new_session()
    assert session.headers.get("User-Agent") == "Mozilla/5.0"
    session.close()


def test_new_session_returns_independent_connection_pool() -> None:
    a = CRAWLER.new_session()
    b = CRAWLER.new_session()
    assert a is not b
    assert a.adapters is not b.adapters
    a.close()
    b.close()


def test_rotate_session_closes_previous_one() -> None:
    old = _FakeSession()
    new = CRAWLER.rotate_session(old)
    assert old.closed == 1
    assert new.headers.get("User-Agent") == "Mozilla/5.0"
    new.close()


def test_rotate_session_survives_close_failure() -> None:
    """换出口这件事不能因为旧连接关不掉就中断整轮抓取。"""
    old = _FakeSession(fail_on_close=True)
    new = CRAWLER.rotate_session(old)
    assert new is not None
    new.close()
