import sys
import types
import hashlib
import json
import copy

import requests
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scripts.crawl_yiche as yiche


def valid_v2_checkpoint_payload():
    target_url = "https://car.yiche.com/test/peizhi/"
    return {
        "format": "yiche-raw-progress",
        "schema_version": yiche.YICHE_CHECKPOINT_SCHEMA_VERSION,
        "state_compat_version": yiche.YICHE_CHECKPOINT_STATE_COMPAT_VERSION,
        "producer": {
            "repository": "Fatty911/crawl_cars",
            "workflow": ".github/workflows/crawl-yiche.yml",
            "run_id": "123",
            "head_sha": "a" * 40,
            "crawler_sha256": "b" * 64,
        },
        "rows": [{
            "品牌": "测试品牌", "车系": "测试车系", "车型名称": "2026款 真车",
            "年款": "2026", "易车上市状态": "approved", "价格": "1万",
        }],
        "resume_state": {
            "stats": {"attempted": 1},
            "known_targets": {target_url: {"serial_id": "1"}},
            "pending": [target_url],
            "completed": [],
            "attempts": {},
            "frontier": {
                "brand_queue": [["2", "测试品牌"]],
                "retry_queue": [],
                "brand_attempts": {},
                "brands_total": 1,
                "brands_scanned": 0,
                "pages_scanned": 0,
                "seen_serial_ids": [],
                "duplicate_serial_ids": 0,
                "brand_discovery_retries": 0,
                "brand_discovery_failures": 0,
                "last_failed_master_id": "",
                "initialized": True,
            },
            "legacy_frontier": {},
        },
    }


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


def test_item_stall_is_bounded_heartbeated_and_checkpointed(monkeypatch, tmp_path, capsys):
    html = (
        "<table><tr><th>车型</th><th>2026款 真车</th></tr>"
        "<tr><td>轴距</td><td>2900</td></tr>"
        "<tr><td>上市状态</td><td>在售</td></tr></table>"
    )

    def fetch_with_stall(session, url):
        if "stalled" in url:
            yiche.time.sleep(0.2)
        return html

    monkeypatch.setattr(yiche, "fetch", fetch_with_stall)
    checkpoint = tmp_path / "yiche_checkpoint.json"
    started = yiche.time.monotonic()

    rows = yiche.crawl(
        {
            "https://car.yiche.com/stalled/peizhi/": {"brand": "真实品牌", "series": "阻塞车系"},
            "https://car.yiche.com/healthy/peizhi/": {"brand": "真实品牌", "series": "健康车系"},
        },
        delay=0,
        item_timeout=0.05,
        heartbeat_interval=0.01,
        checkpoint_path=str(checkpoint),
    )

    assert yiche.time.monotonic() - started < 0.18
    assert [row["车系"] for row in rows] == ["健康车系"]
    output = capsys.readouterr().out
    assert "易车心跳:" in output
    assert "易车阶段超时:" in output
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["stats"]["item_timeouts"] == 1
    assert payload["rows"] == rows


def test_nested_request_timer_preserves_shorter_item_deadline():
    started = yiche.time.monotonic()

    with pytest.raises(yiche.ItemStageTimeout):
        with yiche.item_wall_timeout(0.04, "deterministic-stall"):
            with yiche.request_wall_timeout(0.2):
                yiche.time.sleep(0.1)

    assert yiche.time.monotonic() - started < 0.09


def test_main_flushes_cancelled_checkpoint_on_sigterm(monkeypatch, tmp_path):
    checkpoint = tmp_path / "cancelled_checkpoint.json"

    def interrupting_crawl(*args, **kwargs):
        kwargs["observer"].start()
        yiche.os.kill(yiche.os.getpid(), yiche.signal.SIGTERM)

    monkeypatch.setattr(yiche, "crawl", interrupting_crawl)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crawl_yiche.py",
            "--url",
            "https://car.yiche.com/test/peizhi/",
            "--checkpoint",
            str(checkpoint),
            "--heartbeat-interval",
            "0",
        ],
    )

    assert yiche.main() == 128 + yiche.signal.SIGTERM
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["status"] == "cancelled"
    assert payload["signal"] == yiche.signal.SIGTERM


def test_legacy_incident_checkpoint_restores_authenticated_progress(monkeypatch, tmp_path):
    checkpoint = tmp_path / "yiche_checkpoint.json"
    checkpoint.write_text(
        json.dumps(
            {
                "status": "completed",
                "stage": "finished",
                "stats": {"attempted": 2229, "success": 613, "403": 1079, "429": 0, "failed": 1082,
                          "degraded_identity": 534, "discovery_rounds": 84, "discovery_network_errors": 0,
                          "retry_attempted": 806, "item_timeouts": 0, "invalid_brand": 0,
                          "invalid_model_name": 0, "invalid_series": 0, "invalid_year": 0,
                          "unapproved_status": 0},
                "targets_discovered": 1429,
                "current_url": "",
                "brands_scanned": 84,
                "remaining_brands": 651,
                "queue_depth": 7,
                "last_completed_url": "https://car.yiche.com/puravision/peizhi/",
                "stop_reason": "safety_buffer_reached",
                "rows": [{
                    "品牌": "测试品牌", "车系": "测试车系", "车型名称": "2026款 真车",
                    "年款": "2026", "易车上市状态": "approved", "价格": "1万",
                }],
                "updated_at": "2026-07-30T13:44:01+00:00",
                "elapsed_seconds": 8649.19,
                "last_progress_age_seconds": 0.006,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    checkpoint_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    monkeypatch.setitem(yiche.LEGACY_INCIDENT, "checkpoint_sha256", checkpoint_sha256)
    resume = yiche.load_resume_checkpoint(
        str(checkpoint),
        source_run_id="30538098345",
        source_artifact_id="8761651220",
        source_artifact_sha256="e0c4585eab10ff8f04c17a91c5e0ef9aa64ca2a990e12f854f2ccc68a886f177",
        source_checkpoint_sha256=checkpoint_sha256,
        source_head_sha="60e340af63f316785123ca38c958d7edfc570a4f",
        source_crawler_sha256="0" * 64,
    )

    assert resume["historical_stats"]["attempted"] == 2229
    assert resume["stats"]["attempted"] == 2228
    assert len(resume["rows"]) == 1
    assert resume["targets_discovered"] == 1429
    assert resume["legacy_frontier"]["scanned_master_ids"][-1] == "377"
    assert resume["pending"][0] == "https://car.yiche.com/puravision/peizhi/"
    assert resume["pending"][-1] == "https://car.yiche.com/viritechapricaleconcept/peizhi/"


def test_legacy_checkpoint_rejects_wrong_source_identity(tmp_path):
    checkpoint = tmp_path / "yiche_checkpoint.json"
    checkpoint.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="legacy checkpoint"):
        yiche.load_resume_checkpoint(
            str(checkpoint),
            source_run_id="30538098345",
            source_artifact_id="8761651220",
            source_artifact_sha256="0" * 64,
            source_checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            source_head_sha="60e340af63f316785123ca38c958d7edfc570a4f",
            source_crawler_sha256="0" * 64,
        )


def test_v2_checkpoint_rejects_wrong_crawler_identity(tmp_path):
    checkpoint = tmp_path / "yiche_checkpoint.json"
    source_head = "a" * 40
    source_crawler = "b" * 64
    payload = valid_v2_checkpoint_payload()
    payload["producer"]["crawler_sha256"] = "c" * 64
    checkpoint.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="producer identity"):
        yiche.load_resume_checkpoint(
            str(checkpoint),
            source_run_id="123",
            source_artifact_id="456",
            source_artifact_sha256="d" * 64,
            source_checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            source_head_sha=source_head,
            source_crawler_sha256=source_crawler,
        )


def test_v2_checkpoint_rejects_corrupt_progress_invariants(tmp_path):
    mutations = []
    invalid_attempt = valid_v2_checkpoint_payload()
    target_url = next(iter(invalid_attempt["resume_state"]["known_targets"]))
    invalid_attempt["resume_state"]["attempts"][target_url] = -1
    mutations.append(invalid_attempt)
    invalid_completed = valid_v2_checkpoint_payload()
    invalid_completed["resume_state"]["completed"] = ["https://car.yiche.com/unknown/peizhi/"]
    mutations.append(invalid_completed)
    invalid_frontier = valid_v2_checkpoint_payload()
    invalid_frontier["resume_state"]["frontier"]["brand_queue"] = [["2"]]
    mutations.append(invalid_frontier)

    for index, payload in enumerate(mutations):
        checkpoint = tmp_path / f"corrupt-{index}.json"
        checkpoint.write_text(json.dumps(copy.deepcopy(payload)), encoding="utf-8")
        with pytest.raises(ValueError, match="resume state invariants"):
            yiche.load_resume_checkpoint(
                str(checkpoint),
                source_run_id="123",
                source_artifact_id="456",
                source_artifact_sha256="d" * 64,
                source_checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                source_head_sha="a" * 40,
                source_crawler_sha256="b" * 64,
            )


def test_v2_checkpoint_accepts_exhausted_brand_discovery_failure(tmp_path):
    payload = valid_v2_checkpoint_payload()
    frontier = payload["resume_state"]["frontier"]
    frontier.update({
        "brands_total": 2,
        "brands_scanned": 1,
        "pages_scanned": 0,
        "brand_discovery_failures": 1,
    })
    checkpoint = tmp_path / "valid-brand-failure.json"
    checkpoint.write_text(json.dumps(payload), encoding="utf-8")

    resume = yiche.load_resume_checkpoint(
        str(checkpoint),
        source_run_id="123",
        source_artifact_id="456",
        source_artifact_sha256="d" * 64,
        source_checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        source_head_sha="a" * 40,
        source_crawler_sha256="b" * 64,
    )

    assert resume["frontier"]["brand_discovery_failures"] == 1
    assert resume["rows"] == payload["rows"]


def test_legacy_frontier_reconstructs_seen_ids_before_continuing(monkeypatch):
    payloads = {
        "1": {"data": [{"name": "品牌甲", "serialList": [
            {"id": "101", "name": "旧车系", "brandName": "品牌甲", "allSpell": "old-series"},
        ]}]},
        "2": {"data": [{"name": "品牌乙", "serialList": [
            {"id": "101", "name": "重复车系", "brandName": "品牌乙", "allSpell": "duplicate-series"},
            {"id": "202", "name": "新车系", "brandName": "品牌乙", "allSpell": "new-series"},
        ]}]},
    }
    monkeypatch.setattr(
        yiche,
        "fetch_yiche_api",
        lambda session, url, params: payloads[params["masterId"]],
    )
    frontier = yiche.YicheDiscoveryFrontier(
        requests.Session(),
        initial_brands=[("1", "品牌甲"), ("2", "品牌乙")],
        legacy_scanned_master_ids=["1"],
        legacy_brands_total=2,
        legacy_seen_serial_ids_count=1,
        legacy_seen_serial_ids_sha256=hashlib.sha256(b"101\n").hexdigest(),
    )

    discovered = frontier.discover()

    assert set(discovered) == {"https://car.yiche.com/new-series/peizhi/"}
    assert discovered["https://car.yiche.com/new-series/peizhi/"]["serial_id"] == "202"
    assert frontier.seen_serial_ids == {"101", "202"}


def test_resume_discovery_identity_failure_preserves_authenticated_rows(tmp_path):
    old_row = {
        "品牌": "旧品牌", "车系": "旧车系", "车型名称": "2025款 旧车",
        "年款": "2025", "易车上市状态": "approved", "价格": "1万",
    }
    resume = {
        "rows": [old_row],
        "stats": {"attempted": 5},
        "known_targets": {},
        "pending": [],
        "attempts": {},
        "completed": [],
        "targets_discovered": 10,
    }

    class Frontier:
        brands_scanned = 84
        remaining_brands = 651
        exhausted = False

        def discover(self):
            raise RuntimeError("legacy serial identity mismatch")

        def export_state(self):
            return {}

    checkpoint = tmp_path / "preserved.json"
    with pytest.raises(RuntimeError, match="identity mismatch"):
        yiche.crawl(
            {},
            delay=0,
            checkpoint_path=str(checkpoint),
            heartbeat_interval=0,
            resume_state=resume,
            discovery_callback=Frontier(),
        )

    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["status"] == "partial"
    assert payload["stop_reason"] == "resume_discovery_identity_mismatch"
    assert payload["stats"]["attempted"] == 5
    assert payload["rows"] == [old_row]


def test_resume_keeps_nonzero_rows_and_attempt_count(monkeypatch, tmp_path, capsys):
    html = (
        "<table><tr><th>车型</th><th>2026款 新车</th></tr>"
        "<tr><td>品牌</td><td>真实品牌</td></tr><tr><td>车系</td><td>真实车系</td></tr>"
        "<tr><td>价格</td><td>2万</td></tr><tr><td>上市状态</td><td>在售</td></tr></table>"
    )
    monkeypatch.setattr(yiche, "fetch", lambda session, url: html)
    old_row = {
        "品牌": "旧品牌", "车系": "旧车系", "车型名称": "2025款 旧车",
        "年款": "2025", "易车上市状态": "approved", "价格": "1万",
    }
    resume = {
        "rows": [old_row],
        "stats": {"attempted": 5, "success": 1, "403": 0, "429": 0, "failed": 0,
                  "degraded_identity": 0, "discovery_rounds": 0, "discovery_network_errors": 0,
                  "retry_attempted": 0, "item_timeouts": 0, "invalid_brand": 0,
                  "invalid_model_name": 0, "invalid_series": 0, "invalid_year": 0,
                  "unapproved_status": 0},
        "known_targets": {
            "https://car.yiche.com/new/peizhi/": {"brand": "真实品牌", "series": "真实车系", "serial_id": ""}
        },
        "pending": ["https://car.yiche.com/new/peizhi/"],
        "attempts": {},
        "completed": [],
        "targets_discovered": 1,
    }
    checkpoint = tmp_path / "resumed.json"

    rows = yiche.crawl(
        {},
        delay=0,
        checkpoint_path=str(checkpoint),
        heartbeat_interval=0,
        resume_state=resume,
        resume_smoke_targets=1,
    )

    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["stats"]["attempted"] == 6
    assert len(rows) == 2
    assert len(payload["rows"]) == 2
    assert payload["schema_version"] == yiche.YICHE_CHECKPOINT_SCHEMA_VERSION
    assert payload["resume_state"]["pending"] == []
    assert "易车恢复: attempted=5 rows=1" in capsys.readouterr().out


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
    assert "if: always()" in workflow
    assert "yiche-checkpoint-" in workflow
    assert "yiche_checkpoint.json" in workflow
    assert "resume_artifact_id:" in workflow
    assert "resume_artifact_sha256:" in workflow
    assert "resume_checkpoint_sha256:" in workflow
    assert "source_head_sha:" in workflow
    assert "--resume-source-crawler-sha256" in workflow
    assert "git merge-base --is-ancestor" in workflow
    assert 'path: ${{ steps.verify_yiche.outputs.data_path }}' in workflow
    assert 'glob.glob("yiche_*.json")' not in workflow


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


def test_config_api_prefers_base_info_and_rejects_status_8_predictions():
    payload = {"data": [{"items": [
        {"name": "车型名称", "paramValues": [
            {
                "value": "占位",
                "id": "185727",
                "status": 1,
                "baseInfo": json.dumps({
                    "carName": "26款 405km Air",
                    "brandName": "长安启源",
                    "serialName": "长安启源Q05",
                    "year": "2026",
                    "saleStatus": 1,
                }, ensure_ascii=False),
            },
            {
                "value": "占位",
                "id": "190799",
                "status": 8,
                "baseInfo": json.dumps({
                    "carName": "26款 改款 纯电版 基本型",
                    "brandName": "长安启源",
                    "serialName": "长安启源Q05",
                    "year": "2026",
                    "saleStatus": 8,
                }, ensure_ascii=False),
            },
        ]},
        {"name": "厂商指导价", "paramValues": [
            {"value": "9.99万", "id": "185727", "status": 1, "baseInfo": "{\"saleStatus\":1}"},
            {"value": "暂无", "id": "190799", "status": 8, "baseInfo": "{\"saleStatus\":8}"},
        ]},
    ]}]}
    rows = yiche.extract_from_config_api(payload, yiche.make_target("11958", "错误品牌", "错误车系"))
    real = yiche.validate_real_rows(rows)

    assert [(row["车款ID"], row["车型名称"], row["品牌"], row["车系"], row["年款"]) for row in real] == [
        ("185727", "26款 405km Air", "长安启源", "长安启源Q05", "2026")
    ]
    assert rows[1]["易车上市状态"] == "unapproved"


def test_config_api_splits_q05_mixed_official_status_ids():
    payload = {"data": [{"items": [
        {"name": "车型名称", "paramValues": [
            {"value": "26款 405km Air", "id": "185727", "status": 1, "baseInfo": "{\"saleStatus\":1,\"brandName\":\"长安启源\",\"serialName\":\"长安启源Q05\",\"year\":\"2026\"}"},
            {"value": "26款 506km Max", "id": "188822", "status": 1, "baseInfo": "{\"saleStatus\":1,\"brandName\":\"长安启源\",\"serialName\":\"长安启源Q05\",\"year\":\"2026\"}"},
            {"value": "26款 改款 纯电版 基本型", "id": "190799", "status": 8, "baseInfo": "{\"saleStatus\":8,\"brandName\":\"长安启源\",\"serialName\":\"长安启源Q05\",\"year\":\"2026\"}"},
            {"value": "26款 改款 纯电版 高配版", "id": "190800", "status": 8, "baseInfo": "{\"saleStatus\":8,\"brandName\":\"长安启源\",\"serialName\":\"长安启源Q05\",\"year\":\"2026\"}"},
        ]},
        {"name": "厂商指导价", "paramValues": [
            {"value": "7.99万"}, {"value": "10.99万"}, {"value": "暂无"}, {"value": "暂无"}
        ]},
    ]}]}

    real = yiche.validate_real_rows(yiche.extract_from_config_api(payload, yiche.make_target("11958", "长安启源", "长安启源Q05")))

    assert {row["车款ID"] for row in real} == {"185727", "188822"}
    assert {row["车型名称"] for row in real} == {"26款 405km Air", "26款 506km Max"}


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


def test_discovery_reuses_seed_homepage_brands_when_frontier_homepage_later_blocked(monkeypatch):
    master_html = '<a href="/xuanchegongju/?mid=740">长安启源</a><div data-serial-id="11958"><a href="/changanqiyuanq05-11958/">长安启源Q05</a></div>'
    monkeypatch.setattr(yiche, "fetch", lambda session, url: master_html)
    yiche.discover_series_urls(requests.Session(), ["https://car.yiche.com/"], max_pages=0)

    def blocked_fetch(session, url):
        raise requests.HTTPError("403")

    def fake_api(session, endpoint, parameters):
        assert parameters["masterId"] == "740"
        return {"data": [{"name": "长安启源", "serialList": [
            {"id": "11958", "name": "长安启源Q05", "brandName": "长安启源", "allSpell": "changanqiyuanq05-11958"}
        ]}]}

    monkeypatch.setattr(yiche, "fetch", blocked_fetch)
    monkeypatch.setattr(yiche, "fetch_yiche_api", fake_api)
    frontier = yiche.YicheDiscoveryFrontier(requests.Session(), initial_brands=yiche.LAST_DISCOVERED_MASTER_BRANDS)

    assert frontier.discover() == {
        "https://car.yiche.com/changanqiyuanq05-11958/peizhi/": {"serial_id": "11958", "brand": "长安启源", "series": "长安启源Q05"}
    }


def test_brand_series_carries_approved_model_ids_for_sale_filter():
    payload = {"data": [{"name": "长安启源", "serialList": [{
        "id": "11958", "name": "长安启源Q05", "brandName": "长安启源", "allSpell": "changanqiyuanq05-11958",
        "carList": [
            {"carId": "701", "carName": "2026款 405km Air", "saleStatusName": "在售"},
            {"carId": "702", "carName": "2026款 基本型", "saleStatusName": "即将上市"},
        ],
    }]}]}

    assert yiche.extract_brand_series(payload) == [(
        "https://car.yiche.com/changanqiyuanq05-11958/peizhi/",
        {"serial_id": "11958", "brand": "长安启源", "series": "长安启源Q05", "sale_model_ids": {"701"}},
    )]


def test_sale_filter_uses_target_model_ids_when_sale_page_blocked(monkeypatch):
    rows = [
        {"品牌": "长安启源", "车系": "长安启源Q05", "车型名称": "2026款 405km Air", "年款": "2026", "车款ID": "701", "价格": "9.99万", "易车上市状态": "unknown"},
        {"品牌": "长安启源", "车系": "长安启源Q05", "车型名称": "2026款 基本型", "年款": "2026", "车款ID": "702", "价格": "暂无", "易车上市状态": "unknown"},
    ]
    monkeypatch.setattr(yiche, "fetch", lambda session, url: (_ for _ in ()).throw(requests.HTTPError("403")))

    approved = yiche.approve_rows_from_sale_page(
        requests.Session(),
        "https://car.yiche.com/changanqiyuanq05-11958/peizhi/",
        rows,
        {"sale_model_ids": "701"},
    )

    assert approved == [rows[0]]
    assert rows[0]["易车上市状态"] == "approved"
    assert rows[1]["易车上市状态"] == "unapproved"


def test_serial_id_target_uses_config_api_before_page_fetch(monkeypatch):
    def fail_page_fetch(session, url):
        raise AssertionError(f"page fetch should not run for serialId target: {url}")

    payload = {"data": [{"items": [
        {"name": "车型名称", "paramValues": [{"value": "2026款 405km Air", "id": "185727", "saleStatus": "1"}]},
        {"name": "厂商指导价", "paramValues": [{"value": "9.99万", "id": "185727", "saleStatus": "1"}]},
    ]}]}

    monkeypatch.setattr(yiche, "fetch", fail_page_fetch)
    monkeypatch.setattr(yiche, "fetch_config_api", lambda session, serial_id: payload)

    rows = yiche.crawl(
        {"https://car.yiche.com/changanqiyuanq05-11958/peizhi/": {"serial_id": "11958", "brand": "长安启源", "series": "长安启源Q05"}},
        delay=0,
    )

    assert rows == [{
        "车型名称": "2026款 405km Air",
        "年款": "2026",
        "车款ID": "185727",
        "易车上市状态": "approved",
        "价格": "9.99万",
        "品牌": "长安启源",
        "车系": "长安启源Q05",
        "数据来源": "易车",
    }]


def test_approved_and_unapproved_api_statuses_do_not_fetch_sale_page(monkeypatch):
    rows = [
        {"品牌": "长安启源", "车系": "长安启源Q05", "车型名称": "2026款 405km Air", "年款": "2026", "车款ID": "185727", "价格": "9.99万", "易车上市状态": "approved"},
        {"品牌": "长安启源", "车系": "长安启源Q05", "车型名称": "2026款 基本型", "年款": "2026", "车款ID": "190799", "价格": "暂无", "易车上市状态": "unapproved"},
    ]
    monkeypatch.setattr(yiche, "fetch", lambda session, url: (_ for _ in ()).throw(AssertionError("sale page should not be fetched")))

    approved = yiche.approve_rows_from_sale_page(
        requests.Session(),
        "https://car.yiche.com/changanqiyuanq05-11958/peizhi/",
        rows,
        {},
    )

    assert approved == [rows[0]]



def test_yiche_two_digit_years_do_not_use_model_code_as_year():
    cases = {
        "8968": ("99款 2.6L MT", "1999"),
        "8967": ("99款 2.2L MT", "1999"),
        "6896": ("94款 1.8L", "1994"),
        "6897": ("94款 2.0L", "1994"),
        "6898": ("94款 2.2L（五缸）", "1994"),
        "6899": ("94款 2.6L（六缸）", "1994"),
        "105": ("03款 BJ2032Z2F1", "2003"),
    }
    payload = {
        "data": [
            {
                "items": [
                    {
                        "name": "车型名称",
                        "paramValues": [
                            {
                                "value": name,
                                "id": car_id,
                                "status": 1,
                                "baseInfo": json.dumps(
                                    {
                                        "saleStatus": 1,
                                        "brandName": "测试品牌",
                                        "serialName": "测试车系",
                                        "carName": name,
                                    },
                                    ensure_ascii=False,
                                ),
                            }
                            for car_id, (name, _year) in cases.items()
                        ],
                    },
                    {
                        "name": "价格",
                        "paramValues": [{"value": "1万", "id": car_id, "status": 1} for car_id in cases],
                    },
                ]
            }
        ]
    }

    rows = yiche.validate_real_rows(yiche.extract_from_config_api(payload, {"brand": "测试品牌", "series": "测试车系"}))

    assert {row["车款ID"]: row["年款"] for row in rows} == {car_id: year for car_id, (_name, year) in cases.items()}
