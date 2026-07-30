from scripts.merge_data import match_score, pair_rows_by_features, series_year_key


def row(name, *, brand="AITO", series="问界M7", year="2026", energy="纯电动", level="中大型SUV"):
    return {"品牌": brand, "车系": series, "年款": year, "车型名称": name, "能源类型": energy, "级别": level}


def stats():
    return {"低置信拒绝": 0, "歧义拒绝": 0, "大桶跳过": 0, "大桶候选": 0}


def paired_names(left, right):
    pairs = pair_rows_by_features(left, right, stats(), "车系")
    return {(a["车型名称"], d["车型名称"]) for a, d, _score, _reasons in pairs}


def test_brand_aliases_share_series_year_bucket():
    assert series_year_key(row("2026款 Max", brand="小鹏汽车", series="小鹏G6")) == series_year_key(row("Max", brand="小鹏", series="小鹏G6"))
    assert series_year_key(row("2026款 Max", brand="腾势汽车", series="腾势N9")) == series_year_key(row("Max", brand="腾势", series="腾势N9"))


def test_chinese_and_arabic_seat_counts_pair_without_cross_seat_ambiguity():
    left = [row("问界M7 2026款 纯电 Max长续航版 5座"), row("问界M7 2026款 纯电 Max长续航版 6座")]
    right = [row("纯电 Max 五座 长续航版"), row("纯电 Max 六座 长续航版")]
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


def test_yu7_tiers_and_editions_resolve_to_unique_pairs():
    left = [row("小米YU7 2025款 Pro版", brand="小米汽车", series="小米YU7"), row("小米YU7 2025款 Max版", brand="小米汽车", series="小米YU7"), row("小米YU7 2025款 长续航版", brand="小米汽车", series="小米YU7")]
    right = [row("四驱Pro版", brand="小米汽车", series="小米YU7"), row("四驱Max版", brand="小米汽车", series="小米YU7"), row("后驱长续航版", brand="小米汽车", series="小米YU7")]
    assert paired_names(left, right) == {(left[0]["车型名称"], right[0]["车型名称"]), (left[1]["车型名称"], right[1]["车型名称"]), (left[2]["车型名称"], right[2]["车型名称"])}
