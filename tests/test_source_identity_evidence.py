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


def test_strict_identity_comparison_accounts_for_exact_source_supported_renames():
    document, baseline = fixture()
    candidate, _ = reconcile(baseline, document)
    stats = verify_superset(baseline, candidate, strict_identities=True, identity_evidence=document)
    assert stats["retained_rows"] == 3 and stats["evidenced_name_transitions"] == 3
    assert stats["missing_rows"] == stats["added_rows"] == 0
    report = audit_payload(baseline, candidate, head_sha="fixture", full_validation=True,
                           identity_evidence=document)
    assert report["status"] == "pass", report
    assert len(report["baseline_identity_transitions"]) == 3
    assert report["tolerated_violations"] == []
    with pytest.raises(ValueError, match="missing"):
        verify_superset(baseline, candidate, strict_identities=True)


def test_strict_modes_reject_one_unexplained_identity_loss_even_below_two_percent():
    baseline = [{"品牌":"比亚迪", "车系":"汉", "车系ID":"100", "车型名称":f"2026款 EV {i} 尊贵型",
                 "年款":"2026", "车款ID":str(1000+i), "数据来源":"汽车之家", "官方指导价":"12.34万",
                 "易车上市状态":"approved", "上市时间":"2026.01"}
                for i in range(100)]
    # Keep the same row count by adding a different SKU; percentage tolerance must not hide the loss.
    candidate = copy.deepcopy(baseline)
    candidate[0]["车型名称"] = "2026款 EV 新身份"
    candidate[0]["车款ID"] = "999999"
    with pytest.raises(ValueError, match="missing"):
        verify_superset(baseline, candidate, strict_identities=True)
    report = audit_payload(baseline, candidate, head_sha="fixture", full_validation=True)
    assert report["status"] == "blocked"
    assert any(v["code"] == "missing_identity" and v["count"] == 1 for v in report["violations"])
    assert report["tolerated_violations"] == []


def test_audit_requires_reconciled_candidate_and_never_rewrites_it():
    document, rows = fixture()
    before = copy.deepcopy(rows)
    report = audit_payload(rows, rows, head_sha="fixture", full_validation=True,
                           identity_evidence=document)
    assert rows == before
    assert report["status"] == "blocked"
    assert len(report["baseline_identity_transitions"]) == 3
    assert any(value["code"] == "missing_identity" and value["count"] == 3
               for value in report["violations"])


def test_raw_evidence_is_applied_before_merge_can_choose_a_yearless_name(tmp_path, monkeypatch):
    import remerge_published_data as pipeline
    from merge_data import dedupe_merged_rows
    document, all_rows = fixture()
    original = all_rows[1]
    raw = [original, dict(original, 车型名称="1.5TD 行政版", 数据来源="懂车帝")]
    before = copy.deepcopy(raw)
    # Reproduce the real failure: after merging the erroneous old name, the
    # retained exact-source validator rightly refuses the new short name.
    with pytest.raises(ValueError, match="differs from reviewed evidence"):
        reconcile(dedupe_merged_rows(copy.deepcopy(raw)), document)
    source = tmp_path / "original.json"
    source.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    original_bytes = source.read_bytes()
    out = tmp_path / "out"
    monkeypatch.setattr(pipeline, "MIN_ROWS", 1)
    monkeypatch.setattr(sys, "argv", ["remerge", "--merged", str(source), "--filtered", str(source),
        "--date", "20261015", "--outdir", str(out), "--max-drop-pct", "100",
        "--source-identity-evidence", str(EVIDENCE)])
    assert pipeline.main() == 0
    candidate = json.loads((out / "merged_20261015.json").read_bytes())
    assert len(candidate) == 1 and candidate[0]["车型名称"] == EXPECTED["72435"]
    assert source.read_bytes() == original_bytes and raw == before
    verify_superset(raw, candidate, strict_identities=True, identity_evidence=document)
    assert audit_payload(raw, candidate, head_sha="test", full_validation=True,
                         identity_evidence=document)["status"] == "pass"

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


def test_saved_autohome_row_repairs_require_exact_old_evidence():
    document = json.loads(EVIDENCE.read_bytes())
    rules = document["saved_row_repairs"]
    rows = [{**rule["match"], **rule["before"], "其他配置": "保留"} for rule in rules]
    repaired, changes = reconcile(rows, document)
    assert len(repaired) == 3
    assert {r["车款ID"] for r in repaired} == {"77823", "77981", "66826"}
    assert len(changes) == sum(len(rule["after"]) for rule in rules)
    assert all(r["其他配置"] == "保留" for r in repaired)
    assert reconcile(repaired, document) == (repaired, [])
    for key in ("数据来源", "车系ID", "官方指导价", "车款ID_汽车之家"):
        different = {**rows[1], key: "其他"}
        assert reconcile([different], document) == ([different], [])

    invalid = copy.deepcopy(document)
    invalid["saved_row_repairs"][0]["source"]["url"] += "?wrong=1"
    with pytest.raises(ValueError, match="does not match"):
        reconcile(rows, invalid)


def test_saved_autohome_repair_commutes_with_filtered_projection():
    from merge_data import narrow_pages_rows

    document = json.loads(EVIDENCE.read_bytes())
    rows = [{**rule["match"], **rule["before"]} for rule in document["saved_row_repairs"]]
    corrected, _ = reconcile(rows, document)
    original_projection = narrow_pages_rows(rows)
    corrected_projection, _ = reconcile(original_projection, document)
    assert corrected_projection == narrow_pages_rows(corrected)
    assert reconcile(corrected_projection, document) == (corrected_projection, [])
    for old, new in zip(original_projection, corrected_projection, strict=True):
        assert old.keys() == new.keys()
    # A present but different range cannot masquerade as a projected-out field.
    original_projection[0]["纯电续航(CLTC)"] = "999"
    assert reconcile(original_projection[:1], document) == (original_projection[:1], [])


def test_exact_legacy_filtered_projection_repairs_only_generic_autohome_id():
    document = json.loads(EVIDENCE.read_bytes())
    row = {"品牌": "蔚来", "车系": "蔚来EC7", "车系ID": "6994", "年款": "2024",
           "车型名称": "蔚来EC7 2024款 100kWh", "车款ID": "66804",
           "数据来源": "仅汽车之家", "上市时间": "2024.02",
           "官方指导价": "45.8万|45.80万", "纯电续航(km)": "CLTC:635"}
    output, changes = reconcile([row], document)
    assert output == [dict(row, 车款ID="66826")]
    assert [change["field"] for change in changes] == ["车款ID"]
    assert reconcile(output, document) == (output, [])
    for key in row:
        different = {**row, key: "其他"}
        assert reconcile([different], document) == ([different], [])
    for fields in ({"车款ID_汽车之家": "66999"}, {"纯电续航(CLTC)": "490"}):
        different = {**row, **fields}
        assert reconcile([different], document) == ([different], [])
