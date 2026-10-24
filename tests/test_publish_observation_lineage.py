from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import merge_data
from publish_observation_lineage import dedupe_with_origins
from publish_observation_lineage import filtered_observation_coverage
from audit_pages_payload import audit_payload
from prepare_pages_payload import prepare_rows_with_stats
from remerge_published_data import build_filtered, union_filtered
from verify_publish_superset import verify_superset


def row(sku="100", source="仅汽车之家", **values):
    return {"品牌": "测试汽车", "车系": "测试车系", "车型名称": "测试车系 2026款 标准版",
            "年款": "2026", "官方指导价": "20万", "车款ID": sku, "数据来源": source,
            "级别": "中型SUV", "上市时间": "2026-01-01", **values}


def test_real_multiple_pass_merges_keep_every_original_once_without_changing_output():
    rows = [row(), row(source="仅懂车帝"), row(sku="", source="仅懂车帝")]
    before = deepcopy(rows)
    expected = merge_data.dedupe_merged_rows(deepcopy(rows))
    actual, origins = dedupe_with_origins(rows)
    assert actual == expected
    assert len(actual) == 1
    assert origins == [frozenset([0, 1, 2])]
    assert rows == before


def test_distinct_source_sku_variants_remain_separate_and_all_accounted():
    rows = [row(), row(sku="101"), row(**{"年款": "2025"}), row(**{"官方指导价": "21万"})]
    actual, origins = dedupe_with_origins(rows)
    assert len(actual) == 4
    assert set(origins) == {frozenset([i]) for i in range(4)}


def test_repeated_input_object_is_two_observations_and_nested_input_is_immutable():
    original = row(extra={"facts": [1, 2]})
    before = deepcopy(original)
    _, origins = dedupe_with_origins([original, original])
    assert origins == [frozenset([0, 1])]
    assert original == before


@pytest.mark.parametrize("failure", ["dropped", "duplicated", "unobserved"])
def test_missing_duplicate_or_unobserved_output_never_becomes_valid_lineage(monkeypatch, failure):
    def broken(rows, **_kwargs):
        if failure == "dropped":
            return rows[:-1]
        if failure == "duplicated":
            return rows + [rows[0]]
        return [dict(rows[0]), rows[1]]
    monkeypatch.setattr(merge_data, "dedupe_merged_rows", broken)
    with pytest.raises(ValueError, match="lineage"):
        dedupe_with_origins([row(), row(sku="101")])


@pytest.mark.parametrize("value", [None, {}, [None]])
def test_non_observations_are_rejected(value):
    with pytest.raises(ValueError, match="observations"):
        dedupe_with_origins(value)


def changed_source_representation():
    observed = row(sku="", source="仅懂车帝", **{"车系ID": "900", "车型名称": "测试车系 标准版"})
    anchored = row(sku="65052", **{"车系ID": "900"})
    baseline = [deepcopy(observed)]
    wide = [deepcopy(observed), anchored]
    merged = merge_data.dedupe_merged_rows(deepcopy(wide))
    inherited = merge_data.dedupe_merged_rows(deepcopy(baseline))
    rebuilt = union_filtered(inherited, build_filtered(merged), build_filtered(deepcopy(wide)))
    candidate, _ = prepare_rows_with_stats(rebuilt, 2022)
    assert len(candidate) == 1
    return baseline, wide, candidate


def test_true_observed_source_identity_change_needs_full_original_context():
    baseline, wide, candidate = changed_source_representation()
    before = deepcopy([baseline, wide, candidate])
    with pytest.raises(ValueError, match="missing|identity"):
        verify_superset(baseline, candidate, strict_identities=True)
    result = filtered_observation_coverage(baseline, wide, candidate)
    assert result.fact_rows_equal and len(result.allowed_identity_changes) == 1
    verified = verify_superset(baseline, candidate, strict_identities=True, wide_baseline_rows=wide)
    assert verified["missing_rows"] == 0
    assert verified["verified_display_identity_changes"] == 1
    report = audit_payload(baseline, candidate, head_sha="test", full_validation=True,
                           wide_baseline_rows=wide)
    assert report["status"] == "pass", report["violations"]
    assert [baseline, wide, candidate] == before


@pytest.mark.parametrize("damage", ["remove", "add", "duplicate", "change_value", "drop_field", "change_type"])
def test_context_cannot_waive_missing_extra_modified_or_missing_field_rows(damage):
    baseline, wide, candidate = changed_source_representation()
    broken = deepcopy(candidate)
    if damage == "remove":
        broken = []
    elif damage in {"add", "duplicate"}:
        broken.append(dict(candidate[0]))
        if damage == "add":
            broken[-1]["车型名称"] = "虚构的另一款"
    elif damage == "change_value":
        broken[0]["级别"] = "大型SUV"
    elif damage == "drop_field":
        broken[0].pop("级别")
    else:
        broken[0]["年款"] = 2026
    with pytest.raises(ValueError, match="canonical|nonempty|empty"):
        verify_superset(baseline, broken, strict_identities=True, wide_baseline_rows=wide)
    if broken:
        report = audit_payload(baseline, broken, head_sha="test", full_validation=True,
                               wide_baseline_rows=wide)
        assert report["status"] == "blocked"
        assert any(v["code"] == "canonical_fact_row_difference" for v in report["violations"])


def test_unseen_original_fact_cannot_be_explained_by_a_similar_display_key():
    baseline, wide, candidate = changed_source_representation()
    baseline[0]["未核实的历史事实"] = "不能猜测或删除"
    coverage = filtered_observation_coverage(baseline, wide, candidate)
    assert not coverage.allowed_identity_changes
    with pytest.raises(ValueError, match="missing|identity"):
        verify_superset(baseline, candidate, strict_identities=True, wide_baseline_rows=wide)


def test_context_requires_strict_identity_and_full_audit_modes():
    baseline, wide, candidate = changed_source_representation()
    with pytest.raises(ValueError, match="requires strict"):
        verify_superset(baseline, candidate, wide_baseline_rows=wide)
    with pytest.raises(ValueError, match="requires full"):
        audit_payload(baseline, candidate, head_sha="test", wide_baseline_rows=wide)


def test_full_audit_does_not_inherit_a_shared_bad_component_annotation():
    _, _, candidate = changed_source_representation()
    bad = [dict(candidate[0], 跨源归并ID="forged")]
    report = audit_payload(bad, deepcopy(bad), head_sha="test", full_validation=True)
    assert report["status"] == "blocked"
    assert any(v["code"] == "unsafe_visible_component_annotation" for v in report["violations"])


@pytest.mark.parametrize("field,value", [("能源类型", "纯电"), ("电池组质保", "八年")])
def test_configured_original_field_cannot_disappear_for_same_exact_identity(field, value):
    from publish_observation_lineage import filtered_fact_identity
    _, wide, candidate = changed_source_representation()
    baseline = deepcopy(candidate)
    baseline[0][field] = value
    before = deepcopy([baseline, wide, candidate])
    assert field in merge_data.FILTER_CONFIG["defaultVisibleColumns"]
    assert filtered_fact_identity(baseline[0]) == filtered_fact_identity(candidate[0])
    result = filtered_observation_coverage(baseline, wide, candidate)
    assert not result.fact_rows_equal
    assert result.report["missing_retained_configured_fact_rows"] == 1
    assert result.report["missing_retained_configured_fact_fields"] == 1
    assert [baseline, wide, candidate] == before


@pytest.mark.parametrize("field,value", [("车款ID", "65053"), ("年款", "2025"),
                                       ("官方指导价", "40.8万"), ("数据来源", "仅懂车帝")])
def test_retained_fact_identity_never_crosses_sku_year_price_or_source(field, value):
    from publish_observation_lineage import filtered_fact_identity
    original = row(sku="65052", **{"车系ID": "900"})
    other = dict(original, **{field: value})
    assert filtered_fact_identity(original) != filtered_fact_identity(other)


def test_exact_union_retains_missing_configured_fact_without_mutating_inputs():
    _, wide, candidate = changed_source_representation()
    inherited = deepcopy(candidate)
    inherited[0]["能源类型"] = "纯电"
    before = deepcopy([inherited, candidate, wide])
    result = union_filtered(inherited, candidate, build_filtered(deepcopy(wide)))
    assert len(result) == len(candidate) and result[0]["能源类型"] == "纯电"
    assert [inherited, candidate, wide] == before
    coverage = filtered_observation_coverage(inherited, wide, result)
    assert coverage.fact_rows_equal
    assert verify_superset(inherited, result, strict_identities=True, wide_baseline_rows=wide)["missing_rows"] == 0
    assert audit_payload(inherited, result, head_sha="test", full_validation=True,
                         wide_baseline_rows=wide)["status"] == "pass"
    broken = deepcopy(result)
    broken[0].pop("能源类型")
    with pytest.raises(ValueError, match="canonical"):
        verify_superset(inherited, broken, strict_identities=True, wide_baseline_rows=wide)
    report = audit_payload(inherited, broken, head_sha="test", full_validation=True, wide_baseline_rows=wide)
    assert report["status"] == "blocked"
    assert all(item["count"] > 0 for item in report["violations"])


def test_exact_union_never_overwrites_a_current_source_fact():
    _, wide, candidate = changed_source_representation()
    inherited = deepcopy(candidate)
    inherited[0]["能源类型"] = "纯电"
    candidate[0]["能源类型"] = "汽油"
    result = union_filtered(inherited, candidate, build_filtered(deepcopy(wide)))
    assert result[0]["能源类型"] == "汽油"


def test_exact_union_refuses_conflicting_or_ambiguous_retained_facts():
    _, wide, candidate = changed_source_representation()
    first = deepcopy(candidate[0])
    first["能源类型"] = "纯电"
    second = dict(first, **{"能源类型": "汽油"})
    with pytest.raises(ValueError, match="conflicting"):
        union_filtered([first, second], candidate, build_filtered(deepcopy(wide)))
    with pytest.raises(ValueError, match="ambiguous"):
        union_filtered([first], candidate + deepcopy(candidate), build_filtered(deepcopy(wide)))


def test_exact_union_does_not_copy_facts_between_distinct_skus():
    _, wide, candidate = changed_source_representation()
    inherited = deepcopy(candidate)
    inherited[0]["车款ID"] = "65053"
    inherited[0]["能源类型"] = "纯电"
    result = union_filtered(inherited, candidate, build_filtered(deepcopy(wide)))
    original_target = next(row for row in result if row.get("车款ID") == candidate[0].get("车款ID"))
    assert "能源类型" not in original_target


@pytest.mark.parametrize("spaced_part", ["year", "trim"])
def test_raw_source_evidence_is_not_reapplied_to_observed_composite_keeper(spaced_part):
    """Synthetic spacing only; retained official excerpts supply no new facts."""
    import json
    from reconcile_source_identities import reconcile, source_name
    document = json.loads((Path(__file__).resolve().parents[1] / "config/source_identity_evidence.json").read_bytes())
    entry = document["entries"][0]
    original = {"品牌": entry["brand"], "车系": entry["series"], "车型名称": entry["previous_name"],
                "车款ID": entry["spec_id"], "年款": entry["declared_year"], "车系ID": entry["series_id"],
                "数据来源": "汽车之家", "官方指导价": "23.89万", "上市时间": "2026.01"}
    observed = source_name(entry)
    alias = observed.replace("2026款", "2026 款") if spaced_part == "year" else observed.replace("标准版", "标准 版")
    other = dict(original, **{"数据来源": "懂车帝", "车款ID": "", "车型名称": alias})
    raw = [original, other]
    before = deepcopy(raw)
    corrected, changes = reconcile(raw, document)
    assert len(changes) == 1
    merged, origins = dedupe_with_origins(corrected)
    assert len(merged) == 1 and origins == [frozenset({0, 1})]
    assert merged[0]["车型名称"] == alias
    # The raw-only validator remains strict; it must not be weakened to accept
    # arbitrary unreviewed Autohome records just to accommodate a composite.
    with pytest.raises(ValueError, match="differs from reviewed evidence"):
        reconcile(merged, document)
    inherited, _ = dedupe_with_origins(reconcile([original], document)[0])
    expected = union_filtered(inherited, build_filtered(merged), build_filtered(deepcopy(corrected)))
    candidate, _ = prepare_rows_with_stats(deepcopy(expected), 2022, refresh_dealer_prices=False)
    assert len(candidate) == 1
    coverage = filtered_observation_coverage([original], raw, candidate, identity_evidence=document)
    assert coverage.fact_rows_equal
    assert coverage.report["verified_display_identity_transitions"] == 1
    assert raw == before


def test_evidence_matching_uses_same_checked_raw_names_across_old_and_new_caches():
    import json
    from reconcile_source_identities import reconcile, source_name
    document = json.loads((Path(__file__).resolve().parents[1] / "config/source_identity_evidence.json").read_bytes())
    entry = document["entries"][0]
    previous = {"品牌": entry["brand"], "车系": entry["series"], "车型名称": entry["previous_name"],
                "车款ID": entry["spec_id"], "年款": entry["declared_year"], "车系ID": entry["series_id"],
                "数据来源": "汽车之家", "官方指导价": "23.89万", "上市时间": "2026.01"}
    observed = source_name(entry)
    current = dict(previous, **{"车型名称": observed})
    alias = dict(previous, **{"数据来源": "懂车帝", "车款ID": "", "车型名称": observed.replace("2026款", "2026 款")})
    wide = [current, alias]
    before = deepcopy([previous, wide])
    checked, _ = reconcile(wide, document)
    merged, _ = dedupe_with_origins(checked)
    inherited, _ = dedupe_with_origins(reconcile([previous], document)[0])
    expected = union_filtered(inherited, build_filtered(merged), build_filtered(deepcopy(checked)))
    candidate, _ = prepare_rows_with_stats(deepcopy(expected), 2022, refresh_dealer_prices=False)
    result = filtered_observation_coverage([previous], wide, candidate, identity_evidence=document)
    assert result.fact_rows_equal and len(result.allowed_identity_changes) == 1
    assert result.report["unproved_display_identity_transitions"] == 0
    assert [previous, wide] == before
