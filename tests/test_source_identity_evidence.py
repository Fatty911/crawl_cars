import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from reconcile_source_identities import reconcile
from audit_pages_payload import audit_payload
from verify_publish_superset import verify_superset

EVIDENCE = ROOT / "config/source_identity_evidence.json"
EXPECTED = {"72741": "Temerario 2026款 标准版",
            "72435": "捷途山海L9 2024款 1.5TD 2DHT 行政版 5座",
            "72436": "捷途山海L9 2024款 1.5TD 2DHT 行政版 7座"}


def fixture():
    document = json.loads(EVIDENCE.read_bytes())
    rows = [{"车款ID": e["spec_id"], "品牌": e["brand"], "车系": e["series"],
             "车型名称": e["previous_name"], "年款": e["declared_year"],
             "车系ID": "7759" if e["spec_id"] == "72741" else "7397", "易车上市状态": "approved",
             "上市时间": e["declared_year"] + ".01",
             "数据来源": "汽车之家+懂车帝", "官方指导价": "23.89万", "配置": "保留所有原始值"}
            for e in document["entries"]]
    return document, rows


def test_all_three_observed_names_only_and_idempotent_without_losing_rows():
    document, rows = fixture()
    untouched = copy.deepcopy(rows)
    prepared, changes = reconcile(rows, document)
    assert len(prepared) == len(rows) == len(changes) == 3
    assert rows == untouched
    for before, after in zip(rows, prepared):
        assert after["车型名称"] == EXPECTED[before["车款ID"]]
        assert {k: v for k, v in before.items() if k != "车型名称"} == {
            k: v for k, v in after.items() if k != "车型名称"}
    assert reconcile(prepared, document) == (prepared, [])


@pytest.mark.parametrize("field,value", [("品牌", "其它品牌"), ("年款", "2025"),
                                        ("车型名称", "未审阅的新名称")])
def test_changed_saved_identity_is_rejected_instead_of_being_guessed(field, value):
    document, rows = fixture()
    rows[0][field] = value
    with pytest.raises(ValueError, match="differs from reviewed evidence"):
        reconcile(rows, document)


def test_foreign_source_id_collision_is_not_rewritten():
    document, rows = fixture()
    rows[0]["数据来源"] = "易车"
    assert reconcile(rows[:1], document) == (rows[:1], [])


@pytest.mark.parametrize("kind", ["excerpt", "wrong_spec", "wrong_anchor", "duplicate"])
def test_corrupt_or_misbound_evidence_fails_closed(kind):
    document, rows = fixture()
    source = document["entries"][1]["source"]
    if kind == "excerpt":
        source["selected_excerpt"]["title"] = "未验证标题"
    elif kind == "wrong_spec":
        source["url"] = source["url"].replace("72435", "72436")
    elif kind == "wrong_anchor":
        source["selected_excerpt"]["exact_spec_anchor_text"] = "2025款 其它车款"
        source["excerpt_sha256"] = hashlib.sha256(json.dumps(source["selected_excerpt"], ensure_ascii=False,
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    else:
        document["entries"].append(copy.deepcopy(document["entries"][0]))
    with pytest.raises(ValueError):
        reconcile(rows, document)


def test_real_cli_in_place_binds_input_output_and_source_evidence(tmp_path):
    _, rows = fixture()
    data = tmp_path / "input.json"
    data.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    before = data.read_bytes()
    report = tmp_path / "report.json"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/reconcile_source_identities.py"),
        "--input", str(data), "--output", str(data), "--evidence", str(EVIDENCE),
        "--report", str(report)], capture_output=True)
    assert result.returncode == 0, result.stderr
    proof = json.loads(report.read_bytes())
    assert proof["input_sha256"] == hashlib.sha256(before).hexdigest()
    assert proof["output_sha256"] == hashlib.sha256(data.read_bytes()).hexdigest()
    assert proof["evidence_sha256"] == hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()
    assert proof["source_http_requests"] == 0
    assert [row["车型名称"] for row in json.loads(data.read_bytes())] == list(EXPECTED.values())

@pytest.mark.parametrize("query", [
    "specid=72741",
    "mode=1&site=1&seriesid=9999&specid=72741",
    "mode=2&site=1&seriesid=7759&specid=72741",
    "mode=1&site=2&seriesid=7759&specid=72741",
    "mode=1&site=1&specid=72741",
    "mode=1&site=1&seriesid=7759&specid=72741&specid=72741",
    "mode=1&site=1&seriesid=7759&specid=72741&extra=1",
])
def test_api_evidence_keeps_complete_authorized_capture_url(query):
    document, rows = fixture()
    document["entries"][0]["source"]["url"] = (
        "https://car-web-api.autohome.com.cn/car/param/getParamConf?" + query)
    with pytest.raises(ValueError, match="bound to the requested spec"):
        reconcile(rows, document)
