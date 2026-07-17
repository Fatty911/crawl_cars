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


def test_crawl_rejects_url_fallback_for_rate_limited_pages(monkeypatch):
    def blocked_fetch(session, url):
        raise http_error(403)

    monkeypatch.setattr(yiche, "fetch", blocked_fetch)

    rows = yiche.crawl(["https://car.yiche.com/blocked/peizhi/"], delay=0)

    assert rows == []


def test_crawl_rejects_url_fallback_for_too_many_requests(monkeypatch):
    def limited_fetch(session, url):
        raise http_error(429)

    monkeypatch.setattr(yiche, "fetch", limited_fetch)

    rows = yiche.crawl(["https://car.yiche.com/limited/peizhi/"], delay=0)

    assert rows == []


def test_extract_config_api_response_requires_real_model_and_configuration():
    payload = {"data": [{"items": [
        {"name": "车型名称", "paramValues": [{"value": "2026款 旗舰版"}]},
        {"name": "厂商", "paramValues": [{"value": "测试品牌"}]},
        {"name": "厂商指导价", "paramValues": [{"value": "25.98万"}]},
        {"name": "轴距", "paramValues": [{"value": "2920"}]},
    ]}]}
    rows = yiche.extract_from_config_api(payload)
    assert yiche.validate_real_rows(rows) == [{"车型名称": "2026款 旗舰版", "厂商": "测试品牌", "价格": "25.98万", "轴距(mm)": "2920", "品牌": "测试品牌"}]


def test_first_api_item_supplies_model_identity_when_label_changes():
    payload = {"data": [{"items": [
        {"name": "基本信息", "paramValues": [{"value": "2026款 长续航版"}]},
        {"name": "厂商", "paramValues": [{"value": "测试品牌"}]},
        {"name": "厂商指导价", "paramValues": [{"value": "31.35万"}]},
    ]}]}
    assert yiche.validate_real_rows(yiche.extract_from_config_api(payload)) == [
        {"车型名称": "2026款 长续航版", "厂商": "测试品牌", "价格": "31.35万", "品牌": "测试品牌"}
    ]


def test_mixed_responses_only_count_real_configuration(monkeypatch):
    def mixed_fetch(session, url):
        if "blocked" in url:
            raise http_error(403)
        return '<table><tr><th>车型</th><th>2026款 真车</th></tr><tr><td>品牌</td><td>真实品牌</td></tr><tr><td>轴距</td><td>2900</td></tr></table>'

    monkeypatch.setattr(yiche, "fetch", mixed_fetch)
    rows = yiche.crawl([
        "https://car.yiche.com/blocked/peizhi/",
        "https://car.yiche.com/real/peizhi/",
    ], delay=0)
    assert rows == [{"车型名称": "2026款 真车", "品牌": "真实品牌", "轴距(mm)": "2900", "车系": "real", "数据来源": "易车"}]


def test_budgeted_crawl_expands_beyond_twenty_targets(monkeypatch):
    fetched = []
    html = '<table><tr><th>车型</th><th>2026款 真车</th></tr><tr><td>品牌</td><td>真实品牌</td></tr><tr><td>轴距</td><td>2900</td></tr></table>'
    monkeypatch.setattr(yiche, "fetch", lambda session, url: fetched.append(url) or html)
    discovered = {f"https://car.yiche.com/series-{index}/peizhi/": "" for index in range(25)}
    calls = iter((discovered, {}, {}))

    rows = yiche.crawl(
        {"https://car.yiche.com/seed/peizhi/": ""},
        delay=0,
        discovery_callback=lambda: next(calls),
        max_attempts=1,
    )

    assert len(fetched) == 26
    assert len(rows) == 26


def test_deadline_stops_before_new_request_and_reports_reason(monkeypatch, capsys):
    monkeypatch.setattr(yiche.time, "monotonic", lambda: 95)
    monkeypatch.setattr(yiche, "fetch", lambda session, url: (_ for _ in ()).throw(AssertionError("request after deadline")))

    assert yiche.crawl(["https://car.yiche.com/seed/peizhi/"], delay=0, time_limit=100, start_time=0, finish_buffer=10) == []
    assert "stop_reason=safety_buffer_reached" in capsys.readouterr().out


def test_quality_gate_rejects_placeholder_rows():
    assert yiche.validate_real_rows([
        {"车系": "blocked", "车型名称": "blocked", "数据来源": "易车"}
    ]) == []


def test_discovery_pairs_page_url_with_serial_id():
    html = '<div data-id="12345"><a href="/hanl/">汉L</a></div>'
    assert yiche.extract_series_targets("https://car.yiche.com/", html) == {
        "https://car.yiche.com/hanl/peizhi/": "12345"
    }


def test_numeric_url_suffix_is_used_as_page_provided_serial_id():
    assert yiche.serial_id_from_url("https://car.yiche.com/modely-6224/peizhi/") == "6224"
    assert yiche.serial_id_from_url("https://car.yiche.com/hanl/peizhi/") == ""


def test_extract_serial_id_from_page_state():
    assert yiche.extract_serial_id('<script>window.state={"serialId":12345}</script>') == "12345"


def test_workflow_quality_gate_uses_real_row_validation():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/crawl-yiche.yml").read_text(encoding="utf-8")
    assert "validate_real_rows" in workflow
    assert "real_config_rows" in workflow


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
