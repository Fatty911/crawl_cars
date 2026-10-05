"""易车 WAF 用 HTTP 200 + 腾讯验证码壳页挡爬，必须与「真的没有在售车款」区分开。

实测：被挡时返回 1745 字节的壳页，含 TCaptcha/seqid；配置 API 仍返回
status=1 的完整数据。若不识别，approve_rows_from_sale_page 会把好数据全部丢弃。
"""

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

# 从真实被挡响应里保留下来的骨架
CAPTCHA_PAGE = """
        <script>
            var seqid = "c8fcf985c6be00e57519f7085c33d84f__captcha"
        </script>
        <script src="https://ssl.captcha.qq.com/TCaptcha.js"></script>
        <script>
            var captcha = new TencentCaptcha('2017163193', function(res){})
            function loadXMLDoc(serverName, content) {}
        </script>
""".strip()


def test_real_captcha_shell_is_detected() -> None:
    assert CRAWLER.is_captcha_challenge(CAPTCHA_PAGE)


def test_empty_html_is_not_reported_as_captcha() -> None:
    """空页/无在售车款是真结果，不能被当成被挡而无限重试。"""
    assert not CRAWLER.is_captcha_challenge("")
    assert not CRAWLER.is_captcha_challenge("<html><head></head><body></body></html>")


def test_large_real_page_is_not_captcha() -> None:
    page = "<html><body>" + ("车系配置 在售车款 模型Y " * 2000) + "</html>"
    assert len(page.encode("utf-8")) > CRAWLER.CAPTCHA_PAGE_MAX_BYTES
    assert not CRAWLER.is_captcha_challenge(page)


def test_captcha_marker_inside_a_real_page_body_does_not_trigger() -> None:
    """真实页面页脚偶有验证码脚本引用，超出壳页体积即不再判定为被挡。"""
    page = "<html><body>" + ("x" * (CRAWLER.CAPTCHA_PAGE_MAX_BYTES + 10)) + "TCaptcha</body></html>"
    assert not CRAWLER.is_captcha_challenge(page)


def test_none_input_is_safe() -> None:
    assert not CRAWLER.is_captcha_challenge(None)
