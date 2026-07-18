import sys
import types

import requests
import pytest
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
    <a href="/hanl/peizhi/">汉L参数配置</a>
    '''
    candidates = yiche.extract_candidate_urls("https://car.yiche.com/", html)
    normalized = [yiche.normalize_series_url(url) for url in candidates]
    assert "https://car.yiche.com/hanl/peizhi/" in normalized
    assert "https://car.yiche.com/modely-6224/peizhi/" in normalized


def test_discovery_rejects_site_features_and_date_paths():
    paths = ["authenservice", "citybase", "api", "message", "current", "assets", "issue", "article", "videos", "20230523"]
    html = "".join(f'<a href="/{path}/">not a series</a>' for path in paths)
    assert yiche.extract_candidate_urls("https://car.yiche.com/", html) == []
    assert yiche.extract_series_targets(
        "https://car.yiche.com/",
        "".join(f'<div data-serial-id="123"><a href="/{path}/">not a series</a></div>' for path in paths),
    ) == {}


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
        {"name": "车型名称", "paramValues": [{"value": "2026款 旗舰版", "saleStatusName": "在售"}]},
        {"name": "厂商", "paramValues": [{"value": "测试品牌"}]},
        {"name": "厂商指导价", "paramValues": [{"value": "25.98万"}]},
        {"name": "轴距", "paramValues": [{"value": "2920"}]},
    ]}]}
    rows = yiche.extract_from_config_api(payload, yiche.make_target("101", "测试品牌", "测试车系"))
    assert yiche.validate_real_rows(rows) == [{"车型名称": "2026款 旗舰版", "年款": "2026", "易车上市状态": "approved", "厂商": "测试品牌", "价格": "25.98万", "轴距(mm)": "2920", "品牌": "测试品牌", "车系": "测试车系"}]


def test_first_api_item_supplies_model_identity_when_label_changes():
    payload = {"data": [{"items": [
        {"name": "基本信息", "paramValues": [{"value": "2026款 长续航版", "saleStatusName": "在售"}]},
        {"name": "厂商", "paramValues": [{"value": "测试品牌"}]},
        {"name": "厂商指导价", "paramValues": [{"value": "31.35万"}]},
    ]}]}
    assert yiche.validate_real_rows(yiche.extract_from_config_api(payload, yiche.make_target("102", "测试品牌", "测试车系"))) == [
        {"车型名称": "2026款 长续航版", "年款": "2026", "易车上市状态": "approved", "厂商": "测试品牌", "价格": "31.35万", "品牌": "测试品牌", "车系": "测试车系"}
    ]


def test_mixed_responses_only_count_real_configuration(monkeypatch):
    def mixed_fetch(session, url):
        if "blocked" in url:
            raise http_error(403)
        return '<table><tr><th>车型</th><th>2026款 真车</th></tr><tr><td>品牌</td><td>真实品牌</td></tr><tr><td>轴距</td><td>2900</td></tr><tr><td>上市状态</td><td>在售</td></tr></table>'

    monkeypatch.setattr(yiche, "fetch", mixed_fetch)
    rows = yiche.crawl([
        "https://car.yiche.com/blocked/peizhi/",
        "https://car.yiche.com/real/peizhi/",
    ], delay=0)
    assert rows == []


def test_budgeted_crawl_expands_beyond_twenty_targets(monkeypatch):
    fetched = []
    html = '<table><tr><th>车型</th><th>2026款 真车</th></tr><tr><td>品牌</td><td>真实品牌</td></tr><tr><td>轴距</td><td>2900</td></tr><tr><td>上市状态</td><td>在售</td></tr></table>'
    monkeypatch.setattr(yiche, "fetch", lambda session, url: fetched.append(url) or html)
    discovered = {f"https://car.yiche.com/series-{index}/peizhi/": "" for index in range(25)}
    calls = iter((discovered, {}, {}))

    rows = yiche.crawl(
        {"https://car.yiche.com/seed/peizhi/": {"brand":"真实品牌","series":"真实车系","serial_id":""}},
        delay=0,
        discovery_callback=lambda: next(calls),
        max_attempts=1,
    )

    assert len(fetched) == 26
    assert len(rows) == 1


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
    html = '<div data-serial-id="12345"><a href="/hanl/">汉L</a></div>'
    assert yiche.extract_series_targets("https://car.yiche.com/", html) == {
        "https://car.yiche.com/hanl/peizhi/": "12345"
    }


def test_discovery_keeps_structured_serial_id_and_drops_untrusted_candidates(monkeypatch):
    html = '''
    <div data-serial-id="12345"><a href="/hanl/">汉L</a></div>
    <a href="/article/peizhi/">文章</a>
    '''
    monkeypatch.setattr(yiche, "fetch", lambda session, url: html)
    assert yiche.discover_series_urls(requests.Session(), ["https://car.yiche.com/"], max_pages=0) == {
        "https://car.yiche.com/hanl/peizhi/": "12345"
    }


def test_automatic_target_without_serial_id_is_not_retried(monkeypatch):
    fetched = []
    monkeypatch.setattr(yiche, "fetch", lambda session, url: fetched.append(url) or "<html></html>")

    assert yiche.crawl(
        {"https://car.yiche.com/untrusted/peizhi/": ""},
        delay=0,
        max_attempts=5,
    ) == []
    assert fetched == ["https://car.yiche.com/untrusted/peizhi/"]


def test_numeric_url_suffix_is_used_as_page_provided_serial_id():
    assert yiche.serial_id_from_url("https://car.yiche.com/modely-6224/peizhi/") == "6224"
    assert yiche.serial_id_from_url("https://car.yiche.com/hanl/peizhi/") == ""


def test_extract_serial_id_from_page_state():
    assert yiche.extract_serial_id('<script>window.state={"serialId":12345}</script>') == "12345"


def test_structured_brand_frontier_discovers_hundreds_and_deduplicates(monkeypatch):
    master_html = '<div class="brand-list">' + "".join(
        f'<div class="item-brand" data-id="{index}" data-name="品牌{index}"></div>' for index in range(1, 4)
    ) + '</div>'

    def fake_api(session, endpoint, parameters):
        master_id = int(parameters["masterId"])
        start = (master_id - 1) * 100
        return {"data": [{"name": f"厂商{master_id}", "serialList": [
            {"id": index, "name": f"车系{index}", "brandName": f"品牌{master_id}", "allSpell": f"series-{index}"}
            for index in range(start + 1, start + 101)
        ] + ([{"id": 1, "name": "重复车系", "brandName": "品牌1", "allSpell": "duplicate"}] if master_id > 1 else [])}]}

    monkeypatch.setattr(yiche, "fetch_yiche_api", fake_api)
    monkeypatch.setattr(yiche, "fetch", lambda session, url: master_html)
    frontier = yiche.YicheDiscoveryFrontier(requests.Session())
    discovered = {}
    while not frontier.exhausted:
        discovered.update(frontier.discover())

    assert len(discovered) == 300
    assert frontier.brands_total == frontier.brands_scanned == 3
    assert frontier.pages_scanned == 3
    assert frontier.duplicate_serial_ids == 2
    assert all(yiche.is_series_path(url) for url in discovered)


def test_brand_series_requires_structured_identity_and_ignores_garbage_paths():
    payload = {"data": [{"name": "可信厂商", "serialList": [
        {"id": "101", "name": "可信车系", "brandName": "可信品牌", "allSpell": "trusted-series"},
        {"id": "bad", "name": "article", "brandName": "可信品牌", "allSpell": "article"},
        {"id": "102", "name": "", "brandName": "可信品牌", "allSpell": "20230523"},
    ]}]}
    assert yiche.extract_brand_series(payload) == [("https://car.yiche.com/trusted-series/peizhi/", {"serial_id": "101", "brand": "可信品牌", "series": "可信车系"})]


def test_crawl_continues_structured_discovery_after_initial_targets(monkeypatch):
    html = '<table><tr><th>车型</th><th>2026款 真车</th></tr><tr><td>品牌</td><td>真实品牌</td></tr><tr><td>轴距</td><td>2900</td></tr><tr><td>上市状态</td><td>在售</td></tr></table>'
    fetched = []
    monkeypatch.setattr(yiche, "fetch", lambda session, url: fetched.append(url) or html)

    class Frontier:
        exhausted = False
        brands_total = 1
        brands_scanned = 0
        pages_scanned = 0

        def discover(self):
            self.brands_scanned = self.pages_scanned = 1
            self.exhausted = True
            return {f"https://car.yiche.com/series-{index}/peizhi/": str(index) for index in range(100, 125)}

    rows = yiche.crawl({"https://car.yiche.com/seed-99/peizhi/": {"brand":"真实品牌","series":"真实车系","serial_id":"99"}}, 0, discovery_callback=Frontier())
    assert len(fetched) == 26
    assert len(rows) == 1


def test_brand_discovery_retries_timeout_then_succeeds(monkeypatch):
    master_html = '<div class="brand-list"><div class="item-brand" data-id="1" data-name="品牌1"></div></div>'
    calls = []

    def fake_api(session, endpoint, parameters):
        calls.append(parameters["masterId"])
        if len(calls) == 1:
            raise requests.ReadTimeout("temporary")
        return {"data": [{"name": "厂商1", "serialList": [
            {"id": "101", "name": "车系101", "brandName": "品牌1", "allSpell": "series-101"}
        ]}]}

    monkeypatch.setattr(yiche, "fetch", lambda session, url: master_html)
    monkeypatch.setattr(yiche, "fetch_yiche_api", fake_api)
    frontier = yiche.YicheDiscoveryFrontier(requests.Session(), retry_backoff=0)

    assert frontier.discover() == {}
    assert not frontier.exhausted
    assert frontier.discover() == {"https://car.yiche.com/series-101/peizhi/": {"serial_id": "101", "brand": "品牌1", "series": "车系101"}}
    assert frontier.exhausted
    assert frontier.brand_discovery_retries == 1
    assert frontier.brand_discovery_failures == 0


def test_failed_brand_reaches_limit_and_later_brand_continues(monkeypatch):
    master_html = '<div class="brand-list">' + \
        '<div class="item-brand" data-id="1" data-name="坏品牌"></div>' + \
        '<div class="item-brand" data-id="2" data-name="好品牌"></div></div>'
    calls = []

    def fake_api(session, endpoint, parameters):
        master_id = parameters["masterId"]
        calls.append(master_id)
        if master_id == "1":
            raise requests.ConnectionError("offline")
        return {"data": [{"name": "好厂商", "serialList": [
            {"id": "202", "name": "车系202", "brandName": "好品牌", "allSpell": "series-202"}
        ]}]}

    monkeypatch.setattr(yiche, "fetch", lambda session, url: master_html)
    monkeypatch.setattr(yiche, "fetch_yiche_api", fake_api)
    frontier = yiche.YicheDiscoveryFrontier(requests.Session(), max_brand_attempts=2, retry_backoff=0)
    discovered = {}
    while not frontier.exhausted:
        discovered.update(frontier.discover())

    assert discovered == {"https://car.yiche.com/series-202/peizhi/": {"serial_id": "202", "brand": "好品牌", "series": "车系202"}}
    assert calls == ["1", "1", "2"]
    assert frontier.brands_scanned == frontier.brands_total == 2
    assert frontier.brand_discovery_retries == 1
    assert frontier.brand_discovery_failures == 1
    assert frontier.last_failed_master_id == "1"


def test_crawl_discovery_network_error_preserves_existing_rows(monkeypatch):
    html = '<table><tr><th>车型</th><th>2026款 真车</th></tr><tr><td>品牌</td><td>真实品牌</td></tr><tr><td>轴距</td><td>2900</td></tr><tr><td>上市状态</td><td>在售</td></tr></table>'
    monkeypatch.setattr(yiche, "fetch", lambda session, url: html)

    class Frontier:
        exhausted = False
        calls = 0

        def discover(self):
            self.calls += 1
            if self.calls == 1:
                raise requests.ReadTimeout("temporary")
            self.exhausted = True
            return {}

    rows = yiche.crawl({"https://car.yiche.com/seed-99/peizhi/": {"brand":"真实品牌","series":"真实车系","serial_id":"99"}}, 0, discovery_callback=Frontier())
    assert len(rows) == 1


def test_bounded_crawl_preserves_seed_rows_when_structured_discovery_unavailable(monkeypatch, capsys):
    html = '<table><tr><th>车型</th><th>2026款 真车</th></tr><tr><td>品牌</td><td>真实品牌</td></tr><tr><td>轴距</td><td>2900</td></tr><tr><td>上市状态</td><td>在售</td></tr></table>'
    monkeypatch.setattr(yiche, "fetch", lambda session, url: html)

    class Frontier:
        exhausted = False

        def discover(self):
            raise RuntimeError("brand nodes missing")

    rows = yiche.crawl(
        {"https://car.yiche.com/seed-99/peizhi/": {"brand":"真实品牌","series":"真实车系","serial_id":"99"}},
        0,
        discovery_callback=Frontier(),
        max_targets=25,
    )

    assert len(rows) == 1
    assert "discovery_unavailable_after_seed_rows" in capsys.readouterr().out


def test_unbounded_crawl_still_fails_when_structured_discovery_unavailable(monkeypatch):
    html = '<table><tr><th>车型</th><th>2026款 真车</th></tr><tr><td>品牌</td><td>真实品牌</td></tr><tr><td>轴距</td><td>2900</td></tr><tr><td>上市状态</td><td>在售</td></tr></table>'
    monkeypatch.setattr(yiche, "fetch", lambda session, url: html)

    class Frontier:
        exhausted = False

        def discover(self):
            raise RuntimeError("brand nodes missing")

    assert yiche.crawl({"https://car.yiche.com/seed-99/peizhi/": {"brand":"真实品牌","series":"真实车系","serial_id":"99"}}, 0, discovery_callback=Frontier()) == []


def test_crawl_does_not_hide_discovery_programming_errors(monkeypatch):
    monkeypatch.setattr(yiche, "fetch", lambda session, url: "<html></html>")

    class Frontier:
        exhausted = False

        def discover(self):
            raise TypeError("bug")

    with pytest.raises(TypeError, match="bug"):
        yiche.crawl({"https://car.yiche.com/seed-99/peizhi/": {"brand":"真实品牌","series":"真实车系","serial_id":"99"}}, 0, discovery_callback=Frontier())


def test_crawl_limits_initial_and_structured_discovery_targets(monkeypatch):
    html = '<table><tr><th>车型</th><th>2026款 真车</th></tr><tr><td>品牌</td><td>真实品牌</td></tr><tr><td>轴距</td><td>2900</td></tr><tr><td>上市状态</td><td>在售</td></tr></table>'
    fetched = []
    monkeypatch.setattr(yiche, "fetch", lambda session, url: fetched.append(url) or html)

    class Frontier:
        exhausted = False

        def discover(self):
            return {f"https://car.yiche.com/series-{index}/peizhi/": str(index) for index in range(100, 125)}

    rows = yiche.crawl(
        {
            "https://car.yiche.com/seed-98/peizhi/": {"brand":"真实品牌","series":"真实车系","serial_id":"98"},
            "https://car.yiche.com/seed-99/peizhi/": {"brand":"真实品牌","series":"真实车系","serial_id":"99"},
        },
        0,
        discovery_callback=Frontier(),
        max_targets=3,
    )
    assert len(fetched) == 3
    assert len(rows) == 1


def test_crawl_limits_initial_targets_without_calling_discovery(monkeypatch):
    html = '<table><tr><th>车型</th><th>2026款 真车</th></tr><tr><td>品牌</td><td>真实品牌</td></tr><tr><td>轴距</td><td>2900</td></tr><tr><td>上市状态</td><td>在售</td></tr></table>'
    fetched = []
    monkeypatch.setattr(yiche, "fetch", lambda session, url: fetched.append(url) or html)

    class Frontier:
        exhausted = False

        def discover(self):
            raise AssertionError("discovery called after target limit")

    rows = yiche.crawl(
        {f"https://car.yiche.com/seed-{index}/peizhi/": {"brand":"真实品牌","series":"真实车系","serial_id":str(index)} for index in range(5)},
        0,
        discovery_callback=Frontier(),
        max_targets=3,
    )
    assert len(fetched) == 3
    assert len(rows) == 1


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


def test_yiche_rejects_no_year_slug_series_and_unapproved_status():
    rows = [
        {"品牌": "测试品牌", "车系": "测试车系", "车型名称": "无年款", "易车上市状态": "approved", "价格": "1万"},
        {"品牌": "测试品牌", "车系": "modely-6224", "车型名称": "2026款 真车", "年款": "2026", "易车上市状态": "approved", "价格": "1万"},
        {"品牌": "测试品牌", "车系": "测试车系", "车型名称": "2026款 基本型", "年款": "2026", "易车上市状态": "unapproved", "价格": "1万"},
    ]
    assert yiche.validate_real_rows(rows) == []


def test_yiche_keeps_approved_model_and_rejects_presale_same_series():
    payload = {"data": [{"items": [
        {"name": "车型名称", "paramValues": [
            {"value": "26款 405km Air", "carId": "1", "saleStatusName": "在售"},
            {"value": "2026款 改款 纯电版 基本型", "carId": "2", "saleStatusName": "即将上市"},
        ]},
        {"name": "厂商指导价", "paramValues": [{"value": "7.99万"}, {"value": "暂无"}]},
    ]}]}
    rows = yiche.extract_from_config_api(payload, {"brand": "长安启源", "series": "长安启源Q05"})
    assert [row["车型名称"] for row in yiche.validate_real_rows(rows)] == ["26款 405km Air"]
    assert yiche.validate_real_rows(rows)[0]["年款"] == "2026"


def test_brand_frontier_retries_empty_homepage_then_recovers(monkeypatch):
    pages = iter(["<html></html>", '<div class="brand-list"><div class="item-brand" data-id="1" data-name="品牌1"></div></div>'])
    monkeypatch.setattr(yiche, "fetch", lambda session, url: next(pages))
    monkeypatch.setattr(yiche.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(yiche, "fetch_yiche_api", lambda session, endpoint, parameters: {"data": [{"name": "厂商1", "serialList": [{"id": "101", "name": "车系101", "brandName": "品牌1", "allSpell": "series-101"}]}]})
    frontier = yiche.YicheDiscoveryFrontier(requests.Session(), retry_backoff=0)
    assert frontier.discover()
    assert frontier.init_attempts == 1


def test_yiche_identity_requires_chinese_series_year_and_approved_status():
    good = {"品牌": "真实品牌", "车系": "中文车系", "车型名称": "2026款 在售版", "年款": "2026", "易车上市状态": "approved", "轴距(mm)": "2900"}
    assert yiche.validate_real_rows([good]) == [good]
    assert yiche.validate_real_rows([{**good, "车系": "modely-6224"}]) == []
    assert yiche.validate_real_rows([{**good, "年款": ""}]) == []
    assert yiche.validate_real_rows([{**good, "易车上市状态": "unapproved"}]) == []


def test_config_api_extracts_year_and_rejects_presale_same_series():
    payload = {"data": [{"items": [
        {"name": "车型名称", "paramValues": [
            {"value": "2026款 405km Air", "carId": "1", "saleStatusName": "在售"},
            {"value": "2026款 改款 纯电版 基本型", "carId": "2", "saleStatusName": "即将上市"},
        ]},
        {"name": "厂商指导价", "paramValues": [{"value": "9.99万"}, {"value": "暂无"}]},
    ]}]}
    rows = yiche.extract_from_config_api(payload, yiche.make_target("11958", "长安启源", "长安启源Q05"))
    real = yiche.validate_real_rows(rows)
    assert len(real) == 1
    assert real[0]["车型名称"] == "2026款 405km Air"
    assert real[0]["年款"] == "2026"
    assert real[0]["车系"] == "长安启源Q05"


def test_brand_init_empty_then_recovers_from_structured_api(monkeypatch):
    monkeypatch.setattr(yiche, "fetch", lambda session, url: "<html></html>")
    def fake_api(session, endpoint, parameters):
        if endpoint == yiche.YICHE_MASTER_BRAND_API:
            return {"data": [{"masterId": "9", "masterName": "长安启源"}]}
        return {"data": [{"name": "长安启源", "serialList": [{"id": "11958", "name": "长安启源Q05", "brandName": "长安启源", "allSpell": "changanqiyuanq05-11958"}]}]}
    monkeypatch.setattr(yiche, "fetch_yiche_api", fake_api)
    frontier = yiche.YicheDiscoveryFrontier(requests.Session(), retry_backoff=0)
    found = frontier.discover()
    assert found["https://car.yiche.com/changanqiyuanq05-11958/peizhi/"]["series"] == "长安启源Q05"


def test_brand_init_repeated_empty_fails_closed(monkeypatch):
    monkeypatch.setattr(yiche, "fetch", lambda session, url: "<html></html>")
    monkeypatch.setattr(yiche, "fetch_yiche_api", lambda session, endpoint, parameters: {"data": []})
    frontier = yiche.YicheDiscoveryFrontier(requests.Session(), retry_backoff=0, max_brand_attempts=2)
    with pytest.raises(RuntimeError, match="结构化品牌发现反复不可用"):
        frontier.discover()
