import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import merge_data
from scripts.analysis.merge_evidence_report import analyze
from scripts.merge_data import merge_rows, merge_single_row


def make(source, name, year="2026", energy="纯电", level="SUV", brand="测试", series="测试S"):
    return {"数据来源": source, "品牌": brand, "车系": series, "车型名称": name, "年款": year, "能源类型": energy, "级别": level}


def names(rows):
    return sorted((r["车型名称"], r["数据来源"]) for r in rows)


def test_series_matching_is_stable_when_input_order_changes():
    ah = [make("汽车之家", "2026款 测试S 纯电 长续航"), make("汽车之家", "2026款 测试S 增程 Max", energy="增程")]
    dcd = [make("懂车帝", "测试S 2026款 增程 Max", energy="增程"), make("懂车帝", "测试S 2026款 纯电 长续航")]
    rows = merge_rows(ah, dcd)
    assert names(rows) == names(merge_rows(list(reversed(ah)), list(reversed(dcd))))
    assert len(rows) == 2
    assert all(row["数据来源"] == "汽车之家+懂车帝(车系级)" for row in rows)


def test_same_series_year_multiple_models_do_not_blindly_pair_low_confidence():
    ah = [make("汽车之家", "2026款 测试S 入门版")]
    dcd = [make("懂车帝", "测试S 2026款 四驱旗舰 激光雷达", energy="插混")]
    rows = merge_rows(ah, dcd)
    assert len(rows) == 2
    assert {r["数据来源"] for r in rows} == {"仅汽车之家", "仅懂车帝"}
    assert merge_data.MERGE_ANALYSIS_STATS["低置信拒绝"] == 1


def test_synonym_values_merge_and_conflicts_remain_traceable():
    ah = make("汽车之家", "2026款 测试S Pro")
    dcd = make("懂车帝", "测试S 2026款 Pro")
    ah["远程启动"] = "标配"
    dcd["远程启动"] = "支持"
    ah["座椅材质"] = "真皮"
    dcd["座椅材质"] = "仿皮"
    merged = merge_single_row(ah, dcd)
    assert merged["远程启动"] == "支持"
    assert merged["座椅材质"] == "汽车之家:真皮|懂车帝:仿皮"


def test_exact_name_does_not_cross_brand_or_series_identity():
    ah = [make("汽车之家", "Pro", brand="品牌甲", series="甲系列")]
    dcd = [make("懂车帝", "Pro", brand="品牌乙", series="乙系列")]
    rows = merge_rows(ah, dcd)
    assert len(rows) == 2
    assert {row["数据来源"] for row in rows} == {"仅汽车之家", "仅懂车帝"}


def test_known_different_years_do_not_match_in_noyear_fallback():
    ah = [make("汽车之家", "测试S Pro 长续航", year="2025")]
    dcd = [make("懂车帝", "测试S Pro 长续航", year="2026")]
    rows = merge_rows(ah, dcd)
    assert len(rows) == 2
    assert {row["数据来源"] for row in rows} == {"仅汽车之家", "仅懂车帝"}


def test_same_energy_variants_use_model_tokens_without_score_saturation():
    ah = [
        make("汽车之家", "2026款 测试S Pro 长续航"),
        make("汽车之家", "2026款 测试S Max 高性能"),
    ]
    dcd = [
        make("懂车帝", "测试S 2026款 Max 高性能"),
        make("懂车帝", "测试S 2026款 Pro 长续航"),
    ]
    ah[0]["内部测试标记"] = "P"
    ah[1]["内部测试标记"] = "M"
    dcd[0]["内部测试标记"] = "M"
    dcd[1]["内部测试标记"] = "P"
    rows = merge_rows(ah, dcd)
    assert len(rows) == 2
    assert {row["内部测试标记"] for row in rows} == {"P", "M"}
    assert all(row["数据来源"] == "汽车之家+懂车帝(车系级)" for row in rows)


def test_tied_feature_candidates_are_kept_as_single_source():
    ah = [make("汽车之家", "2026款 测试S Pro 长续航")]
    dcd = [
        make("懂车帝", "测试S 2026款 Pro 长续航 A"),
        make("懂车帝", "测试S 2026款 Pro 长续航 B"),
    ]
    rows = merge_rows(ah, dcd)
    assert len(rows) == 3
    assert all("+" not in row["数据来源"] for row in rows)
    assert merge_data.MERGE_ANALYSIS_STATS["歧义拒绝"] >= 1


def test_evidence_report_counts_both_atomic_sources_and_prefixed_synonyms():
    rows = []
    for index, series in enumerate(("S1", "S1", "S2", "S2")):
        rows.append({
            "数据来源": "汽车之家+懂车帝(车系级)",
            "品牌": "证据品牌",
            "车系": series,
            "年款": "2026",
            "车型名称": f"车型{index}",
            "远程启动": "汽车之家:标配|懂车帝:支持",
        })
    report = analyze(rows)
    sample = report["sampleBrands"][0]
    assert sample["sourceEvidence"] == {"汽车之家": 4, "懂车帝": 4}
    assert ("远程启动", 4) in report["synonymEvidence"]


def test_publish_boundary_rejects_blank_brand_and_model():
    rows = [
        make("仅易车", "有效车型", brand="真实品牌") | {"易车上市状态": "approved"},
        make("仅易车", "空品牌", brand="  "),
        make("仅易车", "-", brand="真实品牌"),
    ]
    kept, stats = merge_data.partition_publishable_rows(rows)
    assert kept == [rows[0]]
    assert stats == {"invalid_brand": 0, "invalid_model_name": 0, "invalid_yiche_identity": 2}
