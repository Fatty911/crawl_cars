import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from publish_value_domains import model_year_conflicts
from merge_data import dedupe_merged_rows


@pytest.mark.parametrize(("name", "year", "bad"), [
    ("汉 2025款 尊贵型", "2026", True),
    ("汉 2025 款 尊贵型", "2024", True),
    ("汉 2025款|2026款", "2025", True),
    ("汉 2025款", "2025|2026", True),
    ("汉 2025款", 2025, False),
    ("汉 2025款", "", False),
    ("汉 2025KM", "2026", False),
    ("汉 12025款", "2026", False),
    ("汉 25款", "2026", False),
])
def test_only_explicit_year_evidence(name, year, bad):
    rows = [{"车型名称": name, "年款": year, "上市时间": "2024-01-01"}]
    original = copy.deepcopy(rows)
    assert model_year_conflicts(rows) == ([0] if bad else [])
    assert rows == original




@pytest.mark.parametrize("reverse", [False, True])
def test_dedupe_keeps_observed_consistent_name_and_all_other_selected_facts(reverse):
    dirty = {"品牌":"奥迪", "车系":"奥迪Q6L e-tron", "车款ID":"65052",
             "车型名称":"奥迪Q6L e-tron 2025款 超长续航版", "年款":"2026",
             "数据来源":"汽车之家+懂车帝", "官方指导价":"36.98万", "保留事实":"原始配置"}
    valid = dict(dirty, 车型名称="奥迪Q6L e-tron 2026款 超长续航版", 数据来源="仅汽车之家")
    items = [valid, dirty] if reverse else [dirty, valid]
    snapshot = copy.deepcopy(items)
    output = dedupe_merged_rows(items)
    assert len(output) == 1
    assert output[0]["车型名称"] == valid["车型名称"]
    assert output[0]["年款"] == dirty["年款"]
    assert {k:v for k,v in output[0].items() if k != "车型名称"} == {k:v for k,v in dirty.items() if k != "车型名称"}
    assert output == dedupe_merged_rows(output)
    assert items == snapshot


def test_dedupe_does_not_invent_consistent_name_when_all_observations_conflict():
    dirty = {"车系":"测试", "车款ID":"1", "车型名称":"测试 2025款 标准版",
             "年款":"2026", "数据来源":"仅汽车之家", "官方指导价":"1万"}
    output = dedupe_merged_rows([dirty, dict(dirty)])
    assert len(output) == 1
    assert output[0]["车型名称"] == dirty["车型名称"]
    assert model_year_conflicts(output) == [0]


@pytest.mark.parametrize("reverse", [False, True])
def test_yearless_observed_name_keeps_rich_identity_while_wrong_year_is_excluded(reverse):
    base = {"品牌": "阿维塔", "车系": "阿维塔07", "车款ID": "74558", "年款": "2026",
            "官方指导价": "21.99万", "数据来源": "汽车之家+懂车帝", "驱动形式": "后置后驱"}
    rich = dict(base, 车型名称="Elite 后驱增程版 39.05kWh")
    year_only = dict(base, 车型名称="阿维塔07 2026款 Elite 增程版")
    wrong_year = dict(base, 车型名称="阿维塔07 2025款 Elite 后驱增程版 39.05kWh")
    items = [wrong_year, year_only, rich]
    if reverse:
        items.reverse()
    before = copy.deepcopy(items)
    output = dedupe_merged_rows(items)
    assert len(output) == 1
    assert output[0]["车型名称"] == rich["车型名称"]
    assert output[0]["年款"] == "2026"
    assert model_year_conflicts(output) == []
    assert items == before

@pytest.mark.parametrize("declared", ["", "-", None])
@pytest.mark.parametrize("reverse", [False, True])
def test_missing_declared_year_keeps_observed_year_through_real_remerge(declared, reverse, monkeypatch):
    import merge_data
    import remerge_published_data as pipeline
    named = {"品牌": "比亚迪", "车系": "汉", "车款ID": "123",
             "车型名称": "汉 2026款 EV 506KM 尊贵型", "年款": declared,
             "数据来源": "汽车之家", "官方指导价": "12.34万",
             "级别": "中大型车", "上市时间": "2026.01"}
    short = dict(named, 车型名称="汉 EV 506KM 尊贵型", 数据来源="懂车帝")
    rows = [short, named] if reverse else [named, short]
    original = copy.deepcopy(rows)
    merged = dedupe_merged_rows(rows)
    assert len(merged) == 1 and merged[0]["车型名称"] == named["车型名称"]
    assert merge_data.row_year(merged[0]) == 2026
    assert merge_data.keep_pages_year(merged[0])
    assert rows == original
    monkeypatch.setattr(pipeline, "MIN_ROWS", 1)
    published = pipeline.remerge(rows, max_drop_pct=100)
    assert len(published) == 1 and pipeline.sku_ids(published) == {"123"}
    assert published[0]["车型名称"] == named["车型名称"]
    assert rows == original


@pytest.mark.parametrize("reverse", [False, True])
def test_formatted_explicit_field_year_keeps_compatible_observed_name(reverse):
    named = {"品牌": "比亚迪", "车系": "汉", "车款ID": "123",
             "车型名称": "汉 2026款 EV 506KM 尊贵型", "年款": "2026款",
             "数据来源": "汽车之家", "官方指导价": "12.34万"}
    short = dict(named, 车型名称="汉 EV 506KM 尊贵型", 数据来源="懂车帝")
    rows = [short, named] if reverse else [named, short]
    original = copy.deepcopy(rows)
    merged = dedupe_merged_rows(rows)
    assert len(merged) == 1 and merged[0]["车型名称"] == named["车型名称"]
    assert merged[0]["年款"] == "2026款" and rows == original
