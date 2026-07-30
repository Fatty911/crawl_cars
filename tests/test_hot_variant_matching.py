from scripts.merge_data import (
    match_score,
    merge_rows,
    pair_rows_by_features,
    series_year_key,
    tokenize_model,
)


def row(name, *, brand="AITO", series="问界M7", year="2026", energy="纯电动", level="中大型SUV", **fields):
    return {
        "品牌": brand,
        "车系": series,
        "年款": year,
        "车型名称": name,
        "能源类型": energy,
        "级别": level,
        **fields,
    }


def stats():
    return {"低置信拒绝": 0, "歧义拒绝": 0, "大桶跳过": 0, "大桶候选": 0}


def paired_names(left, right):
    pairs = pair_rows_by_features(left, right, stats(), "车系")
    return {(a["车型名称"], d["车型名称"]) for a, d, _score, _reasons in pairs}


def test_brand_aliases_share_series_year_bucket():
    assert series_year_key(row("2026款 Max", brand="小鹏汽车", series="小鹏G6")) == series_year_key(row("Max", brand="小鹏", series="小鹏G6"))
    assert series_year_key(row("2026款 Max", brand="腾势汽车", series="腾势N9")) == series_year_key(row("Max", brand="腾势", series="腾势N9"))


def test_n9_and_n9_dm_share_series_year_bucket():
    assert series_year_key(row("腾势N9 2026款 尊荣型", brand="腾势汽车", series="腾势N9")) == series_year_key(
        row("尊荣型", brand="腾势", series="腾势N9 DM")
    )


def test_compound_chinese_trims_resolve_all_six_n9_pairs():
    left_names = [
        "腾势N9 2026款 闪充 尊荣型",
        "腾势N9 2026款 闪充 尊越型",
        "腾势N9 2026款 闪充 旗舰型",
        "腾势N9 2026款 尊荣型",
        "腾势N9 2026款 尊越型",
        "腾势N9 2026款 旗舰版",
    ]
    right_names = ["闪充尊荣型", "闪充尊越型", "闪充旗舰型", "尊荣型", "尊越型", "旗舰型"]
    left = [row(name, brand="腾势汽车", series="腾势N9") for name in left_names]
    right = [row(name, brand="腾势", series="腾势N9 DM") for name in right_names]

    merged = merge_rows(left, right)

    assert len(merged) == 6
    assert all(item["数据来源"] == "汽车之家+懂车帝(车系级)" for item in merged)
    assert {
        (item["车型名称"], item["数据来源"])
        for item in merged
    } == {(name, "汽车之家+懂车帝(车系级)") for name in left_names}


def test_chinese_and_arabic_seat_counts_pair_without_cross_seat_ambiguity():
    left = [row("问界M7 2026款 纯电 Max长续航版 5座"), row("问界M7 2026款 纯电 Max长续航版 6座")]
    right = [
        row("纯电 Max 五座 长续航版", **{"座位数(个)": "5/6"}),
        row("纯电 Max 六座 长续航版", **{"座位数(个)": "5/6"}),
    ]
    assert paired_names(left, right) == {(left[0]["车型名称"], right[0]["车型名称"]), (left[1]["车型名称"], right[1]["车型名称"])}


def test_lidar_line_counts_are_hard_variant_separators():
    left = [row("问界M7 2026款 纯电 Max 5座(192线激光雷达)"), row("问界M7 2026款 纯电 Max 5座(896线激光雷达)")]
    right = [row("纯电 Max 五座(192线激光雷达)"), row("纯电 Max 五座(896线激光雷达)")]
    assert paired_names(left, right) == {(left[0]["车型名称"], right[0]["车型名称"]), (left[1]["车型名称"], right[1]["车型名称"])}


def test_plus_tiers_do_not_collapse_to_base_tiers():
    for base, plus in (("Pro", "Pro+"), ("Max", "Max+")):
        score, reasons = match_score(row(f"测试S 2026款 {plus}", brand="测试", series="测试S"), row(f"{base}版", brand="测试", series="测试S"), True)
        assert score == 0.0
        assert "tier_mismatch" in reasons


def test_max_and_ultra_are_explicit_grade_conflicts():
    score, reasons = match_score(row("问界M7 2026款 Max"), row("Ultra版"), True)
    assert score == 0.0
    assert "tier_mismatch" in reasons


def test_ascii_and_chinese_grades_share_one_conflict_domain():
    score, reasons = match_score(
        row("理想L6 2026款 Ultra", brand="理想", series="理想L6"),
        row("基本型", brand="理想", series="理想L6"),
        True,
    )
    assert score == 0.0
    assert "tier_mismatch" in reasons


def test_explicit_drive_conflicts_are_rejected_from_names_and_fields():
    cases = [
        (row("测试S 2026款 四驱版"), row("后驱版")),
        (row("测试S 2026款", 驱动形式="双电机四驱"), row("测试S", 驱动形式="后置后驱")),
    ]
    for left, right in cases:
        score, reasons = match_score(left, right, True)
        assert score == 0.0
        assert "drive_mismatch" in reasons


def test_exact_names_cannot_bypass_explicit_variant_conflicts():
    left = [row("测试S 2026款 同名版", brand="测试", series="测试S", 驱动形式="双电机四驱")]
    right = [row("测试S 2026款 同名版", brand="测试", series="测试S", 驱动形式="后置后驱")]

    merged = merge_rows(left, right)

    assert len(merged) == 2
    assert {item["数据来源"] for item in merged} == {"仅汽车之家", "仅懂车帝"}


def test_l60_battery_range_fields_add_only_positive_pairing_evidence():
    left = [
        row("乐道L60 2025款 60kWh 后驱版", brand="乐道", series="乐道L60", **{"电池能量(kWh)": "60", "纯电续航(km)": "560"}),
        row("乐道L60 2025款 85kWh 四驱版", brand="乐道", series="乐道L60", **{"电池能量(kWh)": "85", "纯电续航(km)": "707"}),
    ]
    right = [
        row("707km 长续航四驱版", brand="乐道", series="乐道L60", **{"电池容量(kWh)": "85.0", "纯电续航里程(km)": "707"}),
        row("560km 标准续航版", brand="乐道", series="乐道L60", **{"电池容量(kWh)": "60.0", "纯电续航里程(km)": "560"}),
    ]

    assert paired_names(left, right) == {
        (left[0]["车型名称"], right[1]["车型名称"]),
        (left[1]["车型名称"], right[0]["车型名称"]),
    }
    same_drive_exact_evidence = row(
        "后驱版",
        brand="乐道",
        series="乐道L60",
        驱动形式="后置后驱",
        **{"电池容量(kWh)": "60.0", "纯电续航里程(km)": "560"},
    )
    same_drive_mismatched_evidence = row(
        "后驱版",
        brand="乐道",
        series="乐道L60",
        驱动形式="后置后驱",
        **{"电池容量(kWh)": "85.0", "纯电续航里程(km)": "740"},
    )
    mismatch_score, mismatch_reasons = match_score(left[0], same_drive_mismatched_evidence, True)
    exact_score, exact_reasons = match_score(left[0], same_drive_exact_evidence, True)
    assert exact_score > mismatch_score > 0.0
    assert "same_battery" in exact_reasons
    assert "same_range" in exact_reasons
    assert "battery_mismatch" not in mismatch_reasons
    assert "range_mismatch" not in mismatch_reasons
    assert tokenize_model(left[0]) == tokenize_model(
        row("乐道L60 2025款 60kWh 后驱版", brand="乐道", series="乐道L60")
    )


def test_engine_and_transmission_metadata_are_identity_neutral():
    plain = row("测试S 2026款 Ultra", brand="测试", series="测试S")
    autohome_only_metadata = row(
        "测试S 2026款 Ultra",
        brand="测试",
        series="测试S",
        发动机="1.5T 152马力 L4",
        变速箱="电动车单速变速箱",
    )
    counterpart = row("Ultra版", brand="测试", series="测试S")

    assert tokenize_model(autohome_only_metadata) == tokenize_model(plain)
    assert match_score(autohome_only_metadata, counterpart, True) == match_score(plain, counterpart, True)


def test_yu7_tiers_and_editions_resolve_to_unique_pairs():
    left = [row("小米YU7 2025款 Pro版", brand="小米汽车", series="小米YU7"), row("小米YU7 2025款 Max版", brand="小米汽车", series="小米YU7"), row("小米YU7 2025款 长续航版", brand="小米汽车", series="小米YU7")]
    right = [row("四驱Pro版", brand="小米汽车", series="小米YU7"), row("四驱Max版", brand="小米汽车", series="小米YU7"), row("后驱长续航版", brand="小米汽车", series="小米YU7")]
    assert paired_names(left, right) == {(left[0]["车型名称"], right[0]["车型名称"]), (left[1]["车型名称"], right[1]["车型名称"]), (left[2]["车型名称"], right[2]["车型名称"])}
