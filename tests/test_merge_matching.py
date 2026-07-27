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


def test_large_series_feature_bucket_is_skipped_instead_of_cartesian_hang():
    ah = [make("汽车之家", f"2026款 测试S {index}") for index in range(2)]
    dcd = [make("懂车帝", f"测试S 2026款 {index}") for index in range(3)]

    pairs = merge_data.pair_rows_by_features(ah, dcd, {}, "车系", max_candidates=5)

    assert pairs == []


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
        make("仅易车", "有效车型", brand="真实品牌") | {"易车上市状态": "approved", "车款ID": "185727"},
        make("仅易车", "空品牌", brand="  "),
        make("仅易车", "-", brand="真实品牌"),
    ]
    kept, stats = merge_data.partition_publishable_rows(rows)
    assert kept == [rows[0]]
    assert stats == {
        "invalid_brand": 0,
        "invalid_model_name": 0,
        "invalid_yiche_identity": 2,
        "excluded_yiche_commercial_level": 0,
    }


def test_publish_boundary_filters_yiche_commercial_levels_without_brand_blacklist():
    passenger_mpv = make("仅易车", "锐胜王牌M7", level="中大型MPV", brand="北京汽车制造厂") | {
        "易车上市状态": "approved",
        "车款ID": "185728",
    }
    passenger_suv = make("仅易车", "牧游侠", level="中型SUV", brand="五十铃") | {
        "易车上市状态": "approved",
        "车款ID": "185729",
    }
    passenger_micro = make("仅易车", "乘用微型车", level="微型车", brand="北京汽车制造厂") | {
        "易车上市状态": "approved",
        "车款ID": "185730",
    }
    light_truck = make("仅易车", "跨越王X1", level="轻型卡车", brand="长安跨越") | {
        "易车上市状态": "approved",
        "车款ID": "185731",
    }
    pickup = make("仅易车", "测试皮卡", level="皮卡", brand="任意品牌") | {
        "易车上市状态": "approved",
        "车款ID": "185732",
    }
    van = make("仅易车", "测试面包车", level="微型面包车", brand="任意品牌") | {
        "易车上市状态": "approved",
        "车款ID": "185733",
    }

    kept, stats = merge_data.partition_publishable_rows(
        [passenger_mpv, passenger_suv, passenger_micro, light_truck, pickup, van]
    )

    assert kept == [passenger_mpv, passenger_suv, passenger_micro]
    assert stats["excluded_yiche_commercial_level"] == 3


def test_publish_boundary_rejects_autohome_without_numeric_car_id():
    valid = make("仅汽车之家", "甲 2026款 Pro", brand="甲", series="甲车系") | {"车系ID": "100", "车款ID": "54529"}
    rows = [
        valid,
        make("仅汽车之家", "缺ID 2026款 Pro", brand="甲", series="甲车系") | {"车系ID": "101"},
        make("仅汽车之家", "脏ID 2026款 Pro", brand="甲", series="甲车系") | {"车系ID": "102", "车款ID": "abc"},
        make("仅汽车之家", "脏车系 2026款 Pro", brand="甲", series="modely-6224") | {"车系ID": "103", "车款ID": "54530"},
    ]

    kept, stats = merge_data.partition_publishable_rows(rows)

    assert kept == [valid]
    assert stats["invalid_autohome_identity"] == 3


def test_publish_boundary_keeps_autohome_latin_commercial_series():
    model3 = make("仅汽车之家", "2022款 后轮驱动版", year="2022", brand="特斯拉", series="Model 3") | {"车系ID": "5346", "车款ID": "54529"}
    ds9 = make("仅汽车之家", "2024款 歌剧院版", year="2024", brand="雪铁龙", series="DS 9") | {"车系ID": "5001", "车款ID": "60001"}
    mini = make("仅汽车之家", "2024款 Cooper", year="2024", brand="宝马", series="MINI") | {"车系ID": "5002", "车款ID": "60002"}
    dirty = make("仅汽车之家", "2026款 Pro", year="2026", brand="特斯拉", series="modely-6224") | {"车系ID": "100", "车款ID": "60003"}

    kept, stats = merge_data.partition_publishable_rows([model3, ds9, mini, dirty])

    assert kept == [model3, ds9, mini]
    assert stats["invalid_autohome_identity"] == 1


def test_header_normalization_is_exact_and_does_not_capture_longer_unrelated_attributes():
    assert merge_data.norm("前轮胎规格尺寸") == "前轮胎规格"
    assert merge_data.norm("前轮胎规格安全监测") == "前轮胎规格安全监测"


def test_single_one_hot_attribute_becomes_a_canonical_attribute_value():
    rows = [{"扬声器品牌 - Bose": "支持"}]
    assert merge_data.normalize_attribute_keys(rows) == [{"扬声器品牌": "Bose"}]


def test_attribute_normalization_preserves_existing_conflicting_values():
    rows = [{"音响品牌": "Bose", "音响品牌 - Harman Kardon": "支持"}]
    assert merge_data.normalize_attribute_keys(rows) == [{"音响品牌": "Bose|Harman Kardon"}]


def test_cross_source_header_aliases_merge_without_losing_conflicting_values():
    ah = merge_data.norm_rows([make("汽车之家", "同义列测试") | {"前轮胎规格尺寸": "235/50 R19"}], "汽车之家")[0]
    dcd = merge_data.norm_rows([make("懂车帝", "同义列测试") | {"前轮胎规格": "245/45 R20"}], "懂车帝")[0]
    merged = merge_single_row(ah, dcd)
    assert "前轮胎规格尺寸" not in merged
    assert merged["前轮胎规格"] == "汽车之家:235/50 R19|懂车帝:245/45 R20"


def test_option_package_pairs_become_structured_without_hiding_unpaired_suffix_attributes():
    rows = merge_data.norm_rows([
        make("懂车帝", "结构套餐测试") | {
            "冬季包_1": "方向盘加热",
            "冬季包_2": "选装",
            "安全轮胎_1": "支持",
            "camera_count_v4_1": "前视",
            "camera_count_v4_2": "后视",
            "camera_count_v4_3": "环视",
        }
    ], "懂车帝")
    row = rows[0]
    packages = merge_data.json.loads(row["选装包列表"])
    assert packages["冬季包"] == {"描述": "方向盘加热", "状态": "选装"}
    assert "冬季包_1" not in row
    assert "冬季包_2" not in row
    assert row["安全轮胎_1"] == "支持"
    assert row["摄像头数量"] == "前视|后视|环视"


def test_schema_headers_strip_boundary_whitespace_and_canonicalize_exact_source_units_without_losing_conflicts():
    row = make("懂车帝", "列名结构测试") | {
        " 能源类型 ": "纯电",
        "轴距[mm]": "2800",
        "轴距_mm_": "2810",
        "整备质量[kg]": "1900",
        "最高车速[km/h]": "180",
        "前轮距[mm]": "1600",
        "后轮距_mm_": "1610",
        "最大功率[kW]": "200",
        "最大扭矩_N·m_": "350",
        "USB_Type-C接口数量": "前排2个",
        "蓝牙_车载电话": "支持",
        "车门数": "5",
        "车门数_个_": "4",
        "battery_temperature_management_system_heating_v3": "支持",
        "battery_warranty_v3": "8年或16万公里",
    }

    normalized = merge_data.norm_rows([row], "懂车帝")[0]

    assert normalized["能源类型"] == "纯电"
    assert normalized["轴距(mm)"] == "2800|2810"
    assert normalized["整备质量(kg)"] == "1900"
    assert normalized["最高车速(km/h)"] == "180"
    assert normalized["前轮距(mm)"] == "1600"
    assert normalized["后轮距(mm)"] == "1610"
    assert normalized["最大功率(kW)"] == "200"
    assert normalized["最大扭矩(N·m)"] == "350"
    assert normalized["USB/Type-C接口数量"] == "前排2个"
    assert normalized["蓝牙/车载电话"] == "支持"
    assert normalized["车门数(个)"] == "5|4"
    assert normalized["电池温控(加热)"] == "支持"
    assert normalized["电池组质保"] == "8年或16万公里"
    assert not any(key != key.strip() for key in normalized)


def test_zero_to_fifty_acceleration_is_not_aliased_to_zero_to_one_hundred():
    normalized = merge_data.norm_rows([{
        "车型名称": "加速语义测试",
        "官方0—50Km/h加速时间(s)": "3.5",
        "百公里加速(s)": "7.0",
    }], "懂车帝")[0]

    assert normalized["官方0-50km/h加速(s)"] == "3.5"
    assert normalized["百公里加速(s)"] == "7.0"


def test_schema_unit_variants_and_acceleration_scopes_have_safe_canonical_headers():
    equivalent_groups = {
        "前电动机最大扭矩(N·m)": [
            "前电动机最大扭矩[N·m]",
            "前电动机最大扭矩_N·m_",
        ],
        "NEDC综合油耗(L/100km)": [
            "NEDC综合油耗[L/100km]",
            "NEDC综合油耗_L_100km_",
        ],
        "电能当量燃料消耗量(L/100km)": [
            "电能当量燃料消耗量[L/100km]",
            "电能当量燃料消耗量_L_100km_",
        ],
        "接近角(°)": ["接近角[°]", "接近角_°_"],
        "车机系统存储(GB)": ["车机系统存储[GB]", "车机系统存储_GB_"],
    }
    for canonical, variants in equivalent_groups.items():
        assert merge_data.norm(canonical) == canonical
        assert {merge_data.norm(variant) for variant in variants} == {canonical}

    assert merge_data.norm("官方0-100km/h加速[s]") == "百公里加速(s)"
    assert merge_data.norm("官方0-50km_h加速_s_") == "官方0-50km/h加速(s)"
    assert merge_data.norm("官方0—50Km/h加速时间(s)") == "官方0-50km/h加速(s)"
    assert merge_data.norm("官方0-50km_h加速_s_") != "百公里加速(s)"
    assert merge_data.norm("功放最大输出功率（W）") == "功放最大输出功率(W)"
    assert merge_data.norm("N-Box增强娱乐主机_1") == "N-BOX增强娱乐主机_1"
    assert merge_data.norm("智能驾驶辅助系统pro") == "智能驾驶辅助系统Pro"


def test_legacy_heat_pump_suffixes_and_quick_charge_schema_key_use_exact_aliases():
    normalized = merge_data.norm_rows([{
        "车型名称": "旧发布列测试",
        "CO2热泵空调系统_1": "是",
        "CO2热泵空调系统_2": "是",
        "CO2热泵空调包_1": "支持",
        "CO2热泵空调包_2": "支持",
        "quick_charge_interface_v3": "●",
        "安全轮胎_1": "支持",
    }], "懂车帝")[0]

    assert normalized["热泵空调"] == "是|支持"
    assert normalized["快充接口"] == "●"
    for legacy in (
        "CO2热泵空调系统_1",
        "CO2热泵空调系统_2",
        "CO2热泵空调包_1",
        "CO2热泵空调包_2",
        "quick_charge_interface_v3",
    ):
        assert legacy not in normalized
    assert normalized["安全轮胎_1"] == "支持"
