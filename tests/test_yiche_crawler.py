import sys
import types

import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scripts.crawl_yiche as yiche


def test_default_series_urls_seed_no_configured_urls(monkeypatch):
    monkeypatch.delenv("YICHE_SERIES_URLS", raising=False)
    args = types.SimpleNamespace(url=None, url_file="/tmp/does-not-exist-yiche.txt")
    assert yiche.load_urls(args) == []
    assert yiche.DEFAULT_SERIES_URLS
    assert all(url.endswith("/peizhi/") for url in yiche.DEFAULT_SERIES_URLS)


def test_discovery_extracts_and_normalizes_series_candidates():
    html = '''
    <a href="/hanl/">汉L</a>
    <a href="https://car.yiche.com/modely-6224/peizhi/">Model Y参数配置</a>
    <a href="/brand/">品牌</a>
    '''
    candidates = yiche.extract_candidate_urls("https://car.yiche.com/", html)
    normalized = [yiche.normalize_series_url(url) for url in candidates]
    assert "https://car.yiche.com/hanl/peizhi/" in normalized
    assert "https://car.yiche.com/modely-6224/peizhi/" in normalized
    assert all("/brand/" not in url for url in normalized)


def test_extract_identity_from_meta_falls_back_to_series_row():
    html = '<html><head><title>【汉L配置】比亚迪_汉L详细参数介绍-易车</title></head><body></body></html>'
    rows = yiche.extract_identity_from_meta(html)
    assert rows == [{"车系": "汉L", "车型名称": "汉L", "品牌": "比亚迪"}]


def test_extract_identity_from_meta_skips_unpublished_description():
    html = '<html><head><title>【汉L配置】比亚迪_汉L详细参数介绍-易车</title><meta name="description" content="参数配置暂未公布"></head></html>'
    assert yiche.extract_identity_from_meta(html) == []


def test_extract_identity_from_url_uses_slug_when_page_has_no_static_identity():
    rows = yiche.extract_identity_from_url("https://car.yiche.com/hanl/peizhi/", "<html></html>")
    assert rows == [{"车系": "hanl", "车型名称": "hanl"}]


def test_extract_identity_from_url_skips_unpublished_page():
    rows = yiche.extract_identity_from_url("https://car.yiche.com/hanl/peizhi/", "参数配置暂未公布")
    assert rows == []



def http_error(status_code):
    response = requests.Response()
    response.status_code = status_code
    response.url = "https://car.yiche.com/blocked/peizhi/"
    return requests.HTTPError(f"{status_code} error", response=response)


def test_crawl_uses_url_fallback_for_rate_limited_pages(monkeypatch):
    def blocked_fetch(session, url):
        raise http_error(403)

    monkeypatch.setattr(yiche, "fetch", blocked_fetch)

    rows = yiche.crawl(["https://car.yiche.com/blocked/peizhi/"], delay=0)

    assert rows == [{"车系": "blocked", "车型名称": "blocked", "数据来源": "易车"}]


def test_crawl_uses_url_fallback_for_too_many_requests(monkeypatch):
    def limited_fetch(session, url):
        raise http_error(429)

    monkeypatch.setattr(yiche, "fetch", limited_fetch)

    rows = yiche.crawl(["https://car.yiche.com/limited/peizhi/"], delay=0)

    assert rows == [{"车系": "limited", "车型名称": "limited", "数据来源": "易车"}]


def test_crawl_skips_not_found_http_errors(monkeypatch):
    def not_found_fetch(session, url):
        raise http_error(404)

    monkeypatch.setattr(yiche, "fetch", not_found_fetch)

    assert yiche.crawl(["https://car.yiche.com/missing/peizhi/"], delay=0) == []


def test_crawl_skips_server_http_errors(monkeypatch):
    def failed_fetch(session, url):
        raise http_error(500)

    monkeypatch.setattr(yiche, "fetch", failed_fetch)

    assert yiche.crawl(["https://car.yiche.com/broken/peizhi/"], delay=0) == []


def test_crawl_skips_connection_errors(monkeypatch):
    def connection_error_fetch(session, url):
        raise requests.ConnectionError("network down")

    monkeypatch.setattr(yiche, "fetch", connection_error_fetch)

    assert yiche.crawl(["https://car.yiche.com/offline/peizhi/"], delay=0) == []
