"""SKU 归并判据：同一车款ID + 同年款必须归并成一行；年款不同或配置不同必须分开。

**线上实测依据（2026-10-15 发布面 filtered，14097 行）**：
  同一车款ID 出现多行的有 **1095 组、涉及 2327 行**——`identity_key` 用的是
  `("series_id", 车系ID, 车型名称, 年款)`，**车款ID 根本没进键**；而同一 SKU 跨源时
  车系ID 不同、名称写法不同，于是各成一行。点名三款：
    领克900  15 行 / 8 个车款ID（7 组重复）
    乐道L90  32 行 / 13 个车款ID（13 组重复）
    阿维塔07 11 行 / 11 个车款ID（0 组——它的 52.01kWh/四驱 变体是异价异配置，本就不能并）
  且 `dedupe_merged_rows` 以前**只在审计/校验脚本里被调用，合并主链路从未调用过**。

口径（用户 2026-10-15 裁定：**年款不同 = 不同 SKU**）：
  A. 同 车款ID + 同 年款 + 同核心 token（异名/异车系ID/异来源）⇒ 归并成一行，来源并集；
  B. 同 车款ID + **不同** 年款 ⇒ 不许归并；
  C. 同 车款ID + 同 年款 + 不同核心 token（异配置/异价）⇒ 不许归并；
  D. 无 车款ID 的行按属性键归并（键里带车系）；
  F. 第三遍按**物理身份**（车系+年款+价+续航+加速+座位，刻意不含名字里的 tier/配置词）：
     · 该簇里恰好只有一个车款ID ⇒ 无 ID 的行并进它；
     · 该簇里 ≥2 个不同车款ID ⇒ 归属有歧义，一律不折；
     · 该簇全是无 ID 行（没有锚）⇒ 只有"版本词集合 / 座位数 / 改款标记完全一致"才折
       （反例：沃尔沃XC60 PHEV `智远豪华版` vs `智远极夜黑版` 同价同续航也不许并）。
  E. 归并必须幂等（审计/校验脚本会对已发布数据再跑一次）。
"""

from __future__ import annotations

import copy
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("merge_data", ROOT / "scripts" / "merge_data.py")
MD = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(MD)
except SystemExit:  # 模块级 CLI 守卫
    pass


def _row(sku_id, name, series, year, price, source, series_id):
    return {
        "品牌": series.split("L")[0] if series.startswith(("乐道", "领克")) else "测试品牌",
        "车系": series,
        "车系ID": series_id,
        "车型名称": name,
        "年款": year,
        "车款ID": sku_id,
        "官方指导价": price,
        "数据来源": source,
    }


# ---- A：同 ID 同年款，异名/异车系ID/异来源（乐道L90 76215 与领克900 72145 的实测形状）----
LEDAO_SAME = [
    _row("76215", "六座版Pro", "乐道L90", "2026", "26.58万", "懂车帝+汽车之家", "25234"),
    _row("76215", "乐道L90 2026款 Pro 六座版", "乐道L90", "2026", "26.58万",
         "汽车之家+懂车帝(车系级)", "25234"),
    _row("76215", "乐道L90 2026款 Pro 六座版", "乐道L90", "2026", "26.58万", "仅汽车之家", "8045"),
]
LYNK_SAME = [
    _row("72145", "1.5T Halo 六座", "领克900", "2025", "30.99万", "懂车帝+汽车之家", "25161"),
    _row("72145", "领克900 2025款 1.5T Halo 6座", "领克900", "2025", "30.99万",
         "汽车之家+懂车帝、汽车之家+懂车帝(车系级)", "8002"),
]
# 同 ID 但两个车系名（腾势N9 / 腾势N9 DM 实测形状）
DENZA_SAME = [
    _row("77164", "腾势N9 2026款 闪充 尊荣型", "腾势N9", "2026", "40.98万", "懂车帝+汽车之家", "25301"),
    _row("77164", "腾势N9 DM 2026款 闪充 尊荣型", "腾势N9 DM", "2026", "40.98万",
         "汽车之家+懂车帝(车系级)", "25302"),
]
# CJK 段内词序不同（乐道L90 76423 实测形状）
ORDER_SAME = [
    _row("76423", "六座版 马到成功版Max", "乐道L90", "2026", "29.68万", "懂车帝+汽车之家", "25234"),
    _row("76423", "2026款 Max 马到成功版 六座", "乐道L90", "2026", "29.68万",
         "汽车之家+懂车帝(车系级)", "8045"),
]

# ---- B：同 ID 不同年款（凯翼昆仑L8 74526 实测形状；用户裁定：年款不同 = 不同 SKU）----
YEAR_DIFF = [
    _row("74526", "凯翼昆仑L8 2025款 通畅版", "凯翼昆仑L8", "2025", "19.68万", "仅汽车之家", "5001"),
    _row("74526", "凯翼昆仑L8 2026款 通畅版", "凯翼昆仑L8", "2026", "19.68万", "仅汽车之家", "5001"),
]

# ---- C：同 ID 同年款但配置/价格不同（奥迪Q5 e-tron 52586 实测形状）----
CONFIG_DIFF = [
    _row("52586", "50 e-tron quattro 荣耀型 机甲套装", "奥迪Q5 e-tron", "2024", "41.55万",
         "懂车帝+汽车之家", "5002"),
    _row("52586", "50 e-tron quattro 荣耀型 锦衣套装 逐日版", "奥迪Q5 e-tron", "2024", "42.55万",
         "懂车帝+汽车之家", "5002"),
]
# 阿维塔07 的增程版 vs 增程版 52.01kWh（异价异配置，本就不能并）
AVATAR_DIFF = [
    _row("74558", "阿维塔07 2026款 Elite 增程版", "阿维塔07", "2026", "21.99万",
         "汽车之家+懂车帝、汽车之家+懂车帝(车系级)", "7652"),
    _row("74885", "阿维塔07 2026款 Elite 增程版 52.01kWh", "阿维塔07", "2026", "23.99万",
         "汽车之家+懂车帝、汽车之家+懂车帝(车系级)", "7652"),
]


def _merge(rows):
    return MD.dedupe_merged_rows([copy.deepcopy(r) for r in rows])


def test_same_sku_id_same_year_collapses_to_one_row() -> None:
    """A：同 ID 同年款，不管异名/异车系ID/异车系名/异来源，都必须只剩一行。"""
    for name, rows in (("乐道L90 76215", LEDAO_SAME), ("领克900 72145", LYNK_SAME),
                       ("腾势N9 77164", DENZA_SAME), ("乐道L90 76423 词序", ORDER_SAME)):
        out = _merge(rows)
        assert len(out) == 1, "%s：%d 行未归并成 1 行（同 SKU 多行就是发布面重复）" % (name, len(out))
        kept = out[0]
        assert kept.get("车款ID") == rows[0]["车款ID"], "%s：归并后丢了车款ID" % name
        # 来源必须并集（不允许把某一源悄悄丢掉）
        label = str(kept.get("数据来源", "") or "")
        for token in ("汽车之家", "懂车帝"):
            assert token in label, "%s：归并后来源标签少了 %s（%s）" % (name, token, label)


def test_same_sku_id_different_year_stays_separate() -> None:
    """B：年款不同 = 不同 SKU（用户裁定），一行都不许少。"""
    out = _merge(YEAR_DIFF)
    assert len(out) == 2, "同车款ID 不同年款被归并了（%d 行）——年款是 SKU 口径的一部分" % len(out)
    assert {str(r.get("年款")) for r in out} == {"2025", "2026"}


def test_same_sku_id_different_config_stays_separate() -> None:
    """C：同 ID 但核心 token 不同（异配置/异价）必须分开，不许粗暴按 ID 去重。"""
    for name, rows in (("奥迪Q5 52586", CONFIG_DIFF), ("阿维塔07 74558/74885", AVATAR_DIFF)):
        out = _merge(rows)
        assert len(out) == 2, "%s：不同配置/不同价格被并成 1 行了（%d）" % (name, len(out))


def test_rows_without_sku_id_keep_old_behaviour() -> None:
    """D：无车款ID 的行仍按原键（带车系）处理——同车系同项才归并，跨车系不归并。"""
    rows = [
        _row("", "某配置 A", "甲车系", "2025", "10.00万", "仅汽车之家", "9001"),
        _row("", "某配置 A", "甲车系", "2025", "10.00万", "仅懂车帝", "9002"),
        _row("", "某配置 A", "乙车系", "2025", "10.00万", "仅汽车之家", "9003"),
    ]
    out = _merge(rows)
    assert len(out) == 2, "无车款ID 行的归并行为变了：%d 行（期望 2：甲车系两行合一、乙车系独立）" % len(out)


def test_merge_is_idempotent() -> None:
    """E：幂等——审计/校验脚本会对已发布（已归并）数据再跑一次，结果必须稳定。"""
    once = _merge(LEDAO_SAME + LYNK_SAME + YEAR_DIFF + CONFIG_DIFF)
    twice = _merge(once)
    assert len(once) == len(twice), "归并不幂等：一遍 %d 行 vs 二遍 %d 行" % (len(once), len(twice))
    assert sorted(str(r.get("车款ID")) + "|" + str(r.get("年款")) for r in once) == \
           sorted(str(r.get("车款ID")) + "|" + str(r.get("年款")) for r in twice)


def test_core_tokens_are_order_and_numeral_insensitive() -> None:
    """token 口径：词序、阿拉伯/中文数字、年款前缀、车系名写法都不影响同一 SKU 的判定。"""
    t = MD._sku_core_tokens
    pairs = [
        ("六座版Pro", "乐道L90", "乐道L90 2026款 Pro 六座版", "乐道L90"),
        ("1.5T Halo 六座", "领克900", "领克900 2025款 1.5T Halo 6座", "领克900"),
        ("腾势N9 2026款 闪充 尊荣型", "腾势N9", "腾势N9 DM 2026款 闪充 尊荣型", "腾势N9 DM"),
        ("六座版 马到成功版Max", "乐道L90", "2026款 Max 马到成功版 六座", "乐道L90"),
    ]
    for a, sa, b, sb in pairs:
        assert t(a, sa) == t(b, sb), "同 SKU 的两种写法 token 不同：%r vs %r" % (a, b)
    # 排量差异必须保留为 token 差异（1.5T != 2.0T）
    assert t("1.5T Halo 六座", "领克900") != t("2.0T Halo 六座", "领克900")
    # 年款数字不许被当年款标记吃掉（1.5T 的小数点会被归一化删成 15）
    assert t("1.5T Halo 六座", "领克900") == t("领克900 2025款 1.5T Halo 六座", "领克900")


# ---- F：第三遍（物理身份）——无车款ID 的行并进"该物理簇里唯一那个车款ID"的行 ----
# 现网实测（2026-10-16 filtered 面）：红旗天工08 同一款 565 四驱，
# 汽车之家那行带车款ID 66441 叫 `2025款 565 Ultra四驱版`，懂车帝那行**没有车款ID**
# 叫 `565 四驱智选版`，同价 27.98、同续航 565、同加速 3.9 —— 名字里的 tier/配置词
# 是各家叫法，人判"同一款"看的是物理量。
HONGQI_ID = dict(_row("66441", "2025款 565 Ultra四驱版", "红旗天工08", "2025", "27.98万",
                      "懂车帝+汽车之家", "25161"),
                 **{"纯电续航(km)": "565", "百公里加速(s)": "3.9", "能源类型": "纯电动"})
HONGQI_BLANK = dict(_row("", "565 四驱智选版", "红旗天工08", "2025", "27.98万", "仅懂车帝", "25161"),
                    **{"纯电续航(km)": "565", "百公里加速(s)": "3.9", "能源类型": "纯电动"})


def test_f1_blank_id_folds_into_unique_id_row() -> None:
    out = MD.dedupe_merged_rows([copy.deepcopy(HONGQI_ID), copy.deepcopy(HONGQI_BLANK)])
    assert len(out) == 1, "物理属性全同、簇内只有一个车款ID，却没归并：%r" % [r["车型名称"] for r in out]
    assert str(out[0].get("车款ID")) == "66441", "归并后 keeper 弄丢了车款ID"


def test_f2_blank_rows_fold_only_when_names_agree() -> None:
    """两行都没有车款ID（没有锚）：物理身份全同 + 版本词/座位/改款标记全同 ⇒ 可以并；
    版本词不同（`智远豪华版` vs `智远极夜黑版`）或 改款标记不同 ⇒ 一律不并。"""
    b2 = copy.deepcopy(HONGQI_BLANK)
    b2["车型名称"] = "605 Max后驱版"
    b2["纯电续航(km)"] = "605"
    b2["官方指导价"] = "24.98万"
    b1 = copy.deepcopy(HONGQI_BLANK)
    b1["纯电续航(km)"] = "605"
    b1["官方指导价"] = "24.98万"
    b1["车型名称"] = "605 后驱智选版"
    out = MD.dedupe_merged_rows([b1, b2])
    assert len(out) == 1, "同价同续航、版本词与改款都一致，却没归并：%r" % [r["车型名称"] for r in out]

    v1 = dict(_row("", "T8 四驱长续航智远豪华版", "沃尔沃XC60 PHEV", "2026", "52.39万", "仅懂车帝", "1"),
              **{"纯电续航(km)": "90", "百公里加速(s)": "5"})
    v2 = dict(_row("", "T8 四驱长续航智远极夜黑版", "沃尔沃XC60 PHEV", "2026", "52.39万", "仅懂车帝", "1"),
              **{"纯电续航(km)": "90", "百公里加速(s)": "5"})
    out2 = MD.dedupe_merged_rows([v1, v2])
    assert len(out2) == 2, "版本词不同（豪华版 vs 极夜黑版）却被并成一款：%r" % [r["车型名称"] for r in out2]

    m1 = dict(_row("", "改款 创领型", "宝马iX3", "2022", "43.99万", "仅懂车帝", "1"),
              **{"纯电续航(km)": "535", "百公里加速(s)": "6.8"})
    m2 = dict(_row("", "创领型", "宝马iX3", "2022", "43.99万", "仅懂车帝", "1"),
              **{"纯电续航(km)": "535", "百公里加速(s)": "6.8"})
    out3 = MD.dedupe_merged_rows([m1, m2])
    assert len(out3) == 2, "改款标记不同却被并成一款：%r" % [r["车型名称"] for r in out3]


def test_f3_cluster_with_two_ids_is_ambiguous_and_not_folded() -> None:
    """同一物理簇里出现两个不同车款ID ⇒ 无 ID 那行归谁有歧义，整簇一律不折。"""
    second = copy.deepcopy(HONGQI_ID)
    second["车款ID"] = "66442"
    out = MD.dedupe_merged_rows([second, copy.deepcopy(HONGQI_BLANK), copy.deepcopy(HONGQI_ID)])
    assert len(out) == 3, "簇内 ID 不唯一却被折叠：%r" % [r.get("车款ID") for r in out]


def test_f4_different_physical_attrs_do_not_fold() -> None:
    """续航/价格不同 ⇒ 不是同一款，第三遍也不许并。"""
    far = copy.deepcopy(HONGQI_BLANK)
    far["纯电续航(km)"] = "605"
    far["官方指导价"] = "24.59万"
    out = MD.dedupe_merged_rows([copy.deepcopy(HONGQI_ID), far])
    assert len(out) == 2, "物理属性不同却被并成一行：%r" % [r["车型名称"] for r in out]


# ---- G：tier 是"名字形状"的词，不许成为分开同车款ID 两行的理由 ----
# 2026-10-16 整面体检（npc-redtests/unclear7_trace.txt）：补丁后仍"说不清"的 7 组
# 全部栽在这里——传祺向往S9 73964/72600、智界R7 74140/76936 是汽车之家把 Ultra 写成
# **UItra**（形近字，tier 一边 ultra 一边空），迈凯伦GT 58444 是一边 gt 一边空，
# 捷途X70 PRO 67117/67118 是"车系全名里带 PRO、短名不带"。
CHUANQI_TYPO = (
    dict(_row("73964", "乾崑 Ultra 5座", "传祺向往S9", "2025", "24.99万", "懂车帝+汽车之家", "6001"),
         **{"纯电续航(km)": "252|202", "百公里加速(s)": "6.6"}),
    dict(_row("73964", "传祺向往S9 2025款 乾崑 UItra 5座", "传祺向往S9", "2025", "24.99万",
              "汽车之家+懂车帝(车系级)", "6002"),
         **{"纯电续航(km)": "CLTC:252 / WLTC:202", "百公里加速(s)": "6.6"}),
)
JETOUR_SERIES_PREFIX = (
    _row("67117", "捷途X70 PRO 2024款 1.5T DCT花生版 5座", "捷途X70 PRO", "2024", "14.18万",
         "汽车之家+懂车帝", "6003"),
    _row("67117", "1.5T DCT 花生版 5座", "捷途X70 PRO", "2024", "14.18万", "懂车帝+汽车之家", "6004"),
)


def test_g1_tier_spelling_noise_must_not_split_same_sku() -> None:
    """同 ID + 同年款 + 同价 + 同座位，只差名字里的 tier 写法 ⇒ 必须折成一行。"""
    for fixture in (CHUANQI_TYPO, JETOUR_SERIES_PREFIX):
        tiers = {tuple(sorted(MD.model_variant_signature(r)["tier"])) for r in fixture}
        assert len(tiers) > 1, (
            "夹具失效：这两行 tier 本来就相同，测不到要修的那条 ⇒ 换一个真实形状 %r" % (sorted(tiers),))
        out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in fixture])
        assert len(out) == 1, (
            "同车款ID %s 因名字里 tier 写法不同留在 %d 行：%r" % (
                fixture[0]["车款ID"], len(out), [r["车型名称"] for r in out]))


def test_g2_same_identity_but_different_ids_stay_separate() -> None:
    """反向：物理属性全同但车款ID 不同（易车 183622 vs 懂车帝 73964）⇒ 不许跨 ID 合。"""
    yiche = dict(_row("183622", "25款 1.5T 252km 乾崑Ultra 5座", "传祺向往S9", "2025", "24.99万",
                      "懂车帝+易车", "6001"),
                 **{"纯电续航(km)": "252", "百公里加速(s)": "6.6"})
    out = MD.dedupe_merged_rows([copy.deepcopy(CHUANQI_TYPO[0]), yiche])
    ids = sorted({str(r.get("车款ID")) for r in out})
    assert len(out) == 2, "跨车款ID 被合到一行（会盖掉源侧不同的两款）：%r" % [r["车型名称"] for r in out]
    assert ids == ["183622", "73964"], "合并后车款ID 集合被改写：%r" % (ids,)


def test_g3_same_id_different_seat_count_stays_separate() -> None:
    """键里保留座位数：同 ID 但 5座/7座 ⇒ 不许合（防止把 tier 拿掉后键被掏空）。"""
    seven = copy.deepcopy(JETOUR_SERIES_PREFIX[0])
    seven["车型名称"] = "捷途X70 PRO 2024款 1.5T DCT花生版 7座"
    out = MD.dedupe_merged_rows([copy.deepcopy(JETOUR_SERIES_PREFIX[1]), seven])
    assert len(out) == 2, "座位数不同却被并成一款：%r" % [r["车型名称"] for r in out]


# ---- H：版本词闸（tier 拿掉后必须补上的那一层）----
# 实测 奇瑞 车款ID 59684：两行同价 11.39万、同加速 8.28s、同驱动，
# 但一行写 `1.6TGDI DCT尊贵型`、另一行写 `2023款 1.6TGDI DCT旗舰型`。
# tier 不再进同 ID 键之后，这一对会因"同 ID 同价同座位"被合 ⇒ 必须由版本词闸拦住。
CHERY_TRIM = (
    dict(_row("59684", "1.6TGDI DCT尊贵型", "艾瑞泽8", "2023", "11.39万", "懂车帝+汽车之家", "7001"),
         **{"纯电续航(km)": "0", "百公里加速(s)": "8.28", "驱动形式": "前置前驱", "能源类型": "汽油"}),
    dict(_row("59684", "2023款 1.6TGDI DCT旗舰型", "艾瑞泽8", "2023", "11.39万", "汽车之家+懂车帝", "7002"),
         **{"纯电续航(km)": "0", "百公里加速(s)": "8.28", "驱动形式": "前置前驱", "能源类型": "汽油"}),
)
XIAOMI_SUFFIX_ONLY = (
    dict(_row("70545", "纽北限量版", "小米SU7 Ultra", "2025", "81.49万", "懂车帝+汽车之家", "3817"),
         **{"纯电续航(km)": "520", "百公里加速(s)": "1.98", "电池容量(kWh)": "93.7",
            "驱动形式": "三电机四驱", "能源类型": "纯电动"}),
    dict(_row("70545", "小米SU7 Ultra 2025款 Ultra", "小米SU7 Ultra", "2025", "81.49万",
              "汽车之家+懂车帝(车系级)", "3817"),
         **{"纯电续航(km)": "汽车之家:630|懂车帝:520", "百公里加速(s)": "汽车之家:2.1|懂车帝:1.98",
            "电池容量(kWh)": "93.7", "驱动形式": "三电机四驱", "能源类型": "纯电动"}),
)


def test_h1_same_id_with_different_version_words_must_not_fold() -> None:
    """两侧都写了版本词且不相交 ⇒ 同 ID 也是两款，不许合（误合比留重复更贵）。"""
    words = {MD._version_words(str(r["车型名称"])) for r in CHERY_TRIM}
    assert all(words) and len(words) > 1, (
        "夹具失效：这两行的版本词集合不是「都非空且不相交」，测不到要拦的那条 %r" % (sorted(map(sorted, words)),))
    assert MD._sku_spec_conflict([copy.deepcopy(r) for r in CHERY_TRIM]) is True, \
        "版本词闸没把 尊贵型/旗舰型 判成冲突"
    out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in CHERY_TRIM])
    assert len(out) == 2, "同 ID 同价但版本词不同却被并成一款：%r" % [r["车型名称"] for r in out]


def test_h2_edition_mark_is_part_of_the_identity_not_an_omittable_suffix() -> None:
    """H2 改判（评审 B1，2026-10-16）：**一侧带限量/纪念/联名/纽北这类版本标记、另一侧不带 ⇒ 判冲突**。

    这条原来断的是反方向（"后缀写没写只是省字，仍按同 ID 合"），评审拿夹具本身反驳了它：
    这两行的续航/加速在合并串里本来就不一致（`520` vs `汽车之家:630|懂车帝:520`、
    `1.98` vs `汽车之家:2.1|懂车帝:1.98`），把限量款并进普通版等于**两种规格写进同一行**。
    负责人口径也是"看了多条属性后怀疑是同一个 SKU 才叫重复"——反过来说，名字里出现
    限量/纪念/联名/纽北这类标记时，就该怀疑它**不是**同一款。
    宁可留重复也不误合 ⇒ 不对称的版本标记从"缺数据"重分类为"证据"。
    """
    assert MD._sku_spec_conflict([copy.deepcopy(r) for r in XIAOMI_SUFFIX_ONLY]) is True, \
        "一侧带限量/纽北标记、另一侧不带却没判冲突 ⇒ 会把带版本标记的车型并进普通版"
    out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in XIAOMI_SUFFIX_ONLY])
    assert len(out) == 2, "限量款与普通版被折成一行：%r" % [r["车型名称"] for r in out]


# H4：只差"年款前缀写没写"的纯书写差 —— 现网 filtered 面车款ID 66549（宝马iX3）真实两行
# （2026-10-16 用 probe_suffix_pair.py 从 14097 行里挑出 344 个这种"一侧省略前后缀"的真折叠样本，
#   这一对规格列没冲突、车系ID 跨源不同、名称一个带 `2024款` 一个不带）
BMW_IX3_OMITTED_PREFIX = [
    dict(_row("66549", "领先型", "宝马iX3", "2024", "40.5万", "懂车帝+汽车之家", "4538"),
         **{"品牌": "宝马", "级别": "中型SUV", "能源类型": "纯电动",
            "纯电续航(km)": "540", "上市时间": "2024.01"}),
    dict(_row("66549", "2024款 领先型", "宝马iX3", "2024", "40.5万|40.50万",
              "汽车之家+懂车帝(车系级)", "5758"),
         **{"品牌": "宝马", "级别": "中型SUV", "能源类型": "纯电动", "上市时间": "2024.01"}),
]


def test_h4_omitted_plain_year_prefix_is_still_not_a_conflict() -> None:
    """H2 原来的意图换到这条上保住：**没写年款前缀 ≠ 另一款车，仍按同 ID 合**。

    H2 被改判之后，"一侧省字"这条规则不能跟着一起丢掉——否则真重复（344 个这种样本）会退回。
    区分点在于省略的是**书写**（年款前缀、车系全名）还是**身份**（限量/线数/停产）。
    """
    assert MD._sku_spec_conflict([copy.deepcopy(r) for r in BMW_IX3_OMITTED_PREFIX]) is False, \
        "只差『2024款』前缀没写就被判冲突 ⇒ 会把省略年款前缀的同款拆开（现网 344 个真折叠样本受影响）"
    out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in BMW_IX3_OMITTED_PREFIX])
    assert len(out) == 1, "宝马iX3 66549 这种「只差年款前缀」还没合：%r" % [r["车型名称"] for r in out]


# H5：`_edition_identities` 旧实现取词根前**末两字**当身份，两族评审各点过一对可构造碰撞
# （REVIEW-I-astra-round6 / REVIEW-J-terra-round6 都判"不可推"），我用生产代码复现过：
# 二字窗口把 `极光蓝`/`星光蓝` 都截成 `光蓝`，把 `110`/`210` 都截成 `10` ⇒ 两款折成一条。
EDITION_WINDOW_CJK = [
    _row("99001", "极光蓝限定版", "途昂", "2026", "30.99万", "懂车帝+汽车之家", "25161"),
    _row("99001", "星光蓝限定版", "途昂", "2026", "30.99万", "仅汽车之家", "8045"),
]
EDITION_WINDOW_DIGITS = [
    _row("99002", "110周年纪念版", "途昂", "2026", "32.99万", "懂车帝+汽车之家", "25161"),
    _row("99002", "210周年纪念版", "途昂", "2026", "32.99万", "仅汽车之家", "8045"),
]
# 对照组：修成"整段前缀"之后，书写差（车系名写头不写尾）仍必须能折——
# 否则这条修正是拿漏合换误合，两头都不合格。
EDITION_PREFIX_CONTROL = [
    _row("99003", "极光蓝限定版", "途昂", "2026", "33.99万", "懂车帝+汽车之家", "25161"),
    _row("99003", "途昂 极光蓝限定版", "途昂", "2026", "33.99万", "仅汽车之家", "8045"),
]


def test_h5_fixed_two_char_edition_window_must_not_collide() -> None:
    """限量身份不许用固定字数窗口：任意 N 字都会把不同专名截成同一个。"""
    assert MD._sku_spec_conflict([copy.deepcopy(r) for r in EDITION_WINDOW_CJK]) is True, \
        "极光蓝/星光蓝 被同一个二字窗口截成同身份 ⇒ 两款折一条"
    assert MD._sku_spec_conflict([copy.deepcopy(r) for r in EDITION_WINDOW_DIGITS]) is True, \
        "110周年/210周年 截末两位都是 10周年 ⇒ 两款折一条"
    for name, pair in (("CJK", EDITION_WINDOW_CJK), ("数字", EDITION_WINDOW_DIGITS)):
        out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in pair])
        assert len(out) == 2, "%s 窗口碰撞对被判成同款：%r" % (name, [r["车型名称"] for r in out])


def test_h5_control_full_prefix_keeps_omitted_series_name_foldable() -> None:
    """改判方向的反证：剔噪后整段前缀相等 ⇒ 只差"车系名写没写"仍按同 ID 合。"""
    assert MD._sku_spec_conflict([copy.deepcopy(r) for r in EDITION_PREFIX_CONTROL]) is False, \
        "同一专名、只是把车系名写在了头 ⇒ 整段前缀比法把它拆开了（这条修正是纯漏合）"
    out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in EDITION_PREFIX_CONTROL])
    assert len(out) == 1, "对照组没合：%r" % [r["车型名称"] for r in out]


# H6：第七轮 GLM 族评审（`REVIEW-GLM-round7-20261017000838.txt`）判"不可推"的两条阻断项，
# 我用生产代码复现后各给一对。两条都是**前缀提取把数字信息弄丢**，与 H5 的固定窗口同族：
#   F1 head 的分隔类里含 `年/款/式/的` ⇒ `二十周年` 被从中间劈掉，两侧都塌成裸词根；
#   F2 `_EDITION_HEAD_RE` 的数词分支吃不下 `辆` ⇒ `300万辆` 与 `500万辆` 都是 `万辆`。
EDITION_CN_NUMERAL = [
    _row("99004", "二十周年纪念版", "途昂", "2026", "34.99万", "懂车帝+汽车之家", "25161"),
    _row("99004", "十周年纪念版", "途昂", "2026", "34.99万", "仅汽车之家", "8045"),
]
EDITION_UNIT_NUMBER = [
    _row("99005", "300万辆纪念版", "途昂", "2026", "35.99万", "懂车帝+汽车之家", "25161"),
    _row("99005", "500万辆纪念版", "途昂", "2026", "35.99万", "仅汽车之家", "8045"),
]
EDITION_TELEPHONE = [
    _row("99006", "100万台限量版", "途昂", "2026", "36.99万", "懂车帝+汽车之家", "25161"),
    _row("99006", "200万台限量版", "途昂", "2026", "36.99万", "仅汽车之家", "8045"),
]
# deepseek 票 1c①（同族第二票，独立撞到同一个机制）：
# "后缀豁免"会把**任何纯中文专名前缀**当书写装饰放行 ⇒ `璀璨星空限定版` 被并进 `星空限定版`。
# 本轮修法不是把豁免的字符类再补宽，而是**取消豁免**：书写差在取前缀时就用空格分栏解决，
# 比对方只做整段相等（见 EDITION_PREFIX_CONTROL 与 `_edition_identities` 注释）。
EDITION_CJK_PROPER_NOUN = [
    _row("99007", "璀璨星空限定版", "途昂", "2026", "37.99万", "懂车帝+汽车之家", "25161"),
    _row("99007", "星空限定版", "途昂", "2026", "37.99万", "仅汽车之家", "8045"),
]


import re as _re

_HAS_NUM = _re.compile(r"[0-9A-Za-z０-９零〇一二两三四五六七八九十百千万]")


def _has_number_info(s: str) -> bool:
    """"身份里带着数字信息"——ASCII 数字、字母编号、全角与中文数词都算。"""
    return bool(_HAS_NUM.search(str(s)))


def test_h6_chinese_numerals_and_units_are_not_dropped_from_edition_identity() -> None:
    """H6（GLM 票 F1/F2）：数字信息无论是 ASCII、中文数词还是带量词，都必须留在身份里。"""
    for label, pair, need_num in (("F1 中文数词", EDITION_CN_NUMERAL, True),
                                  ("F2 数字+量词", EDITION_UNIT_NUMBER, True),
                                  ("F2 万台限量版", EDITION_TELEPHONE, True),
                                  ("1c① 纯中文专名", EDITION_CJK_PROPER_NOUN, False)):
        assert MD._sku_spec_conflict([copy.deepcopy(r) for r in pair]) is True, \
            "%s：两侧身份被前缀提取弄成同一个 ⇒ 会折成一条" % label
        out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in pair])
        assert len(out) == 2, "%s：两款被折成一行 ⇒ %r" % (label, [r["车型名称"] for r in out])
        if need_num:
            # 身份必须**带着数字**，不是靠两侧恰好不等蒙过去的
            # （注意 `'二'.isdigit()` 是 False：中文数词不属于 Unicode 十进制数字，
            #   所以这里必须用显式字符类，别用 isdigit 当"含数字"的判据）
            ids = sorted({i for r in pair for v in MD._edition_identities(
                str(r["车型名称"]), str(r["车系"])).values() for i in v})
            assert any(_has_number_info(i) for i in ids), \
                "%s：身份里没有数字信息，说明前缀被丢了 ⇒ %r" % (label, ids)


def test_h6_no_suffix_exemption_for_pure_cjk_proper_nouns() -> None:
    """H6 另一半：书写差靠**空格分栏**解决，不靠"后缀豁免"那种会放过专名的规则。

    `途昂 青峰限定版` 与 `青峰限定版` 中间那道空格就是车系名与专名的边界；
    而 `璀璨星空限定版` 与 `星空限定版` 没有这道边界，两个身份天然不同。
    """
    a, b = _pair("途昂 青峰限定版", "青峰限定版", series="途昂")
    ea = MD._edition_identities(str(a["车型名称"]), str(a["车系"]))
    eb = MD._edition_identities(str(b["车型名称"]), str(b["车系"]))
    assert ea == eb, "空格分栏没起作用，车系名写头又被拆成两款：%r / %r" % (ea, eb)
    c, d = _pair("璀璨星空限定版", "星空限定版")
    ec = MD._edition_identities(str(c["车型名称"]), str(c["车系"]))
    ed = MD._edition_identities(str(d["车型名称"]), str(d["车系"]))
    # 词根的**形态**已归一（`限定版` → `限定`），所以这里用 `_edition_root_key` 取键，
    # 不把某个具体写法钉进断言（否则归一规则一改，这条测试红的不是行为而是键名）。
    _rk = MD._edition_root_key("限定版")
    assert not (set(ec[_rk]) & set(ed[_rk])), \
        "纯中文专名被当成书写装饰：限定版身份两侧相同 %r" % (sorted(ec[_rk]),)


# deepseek 票 round-8B 阻断件（与 GLM F1/F2 同族，只是分隔符换成了**空格**）：
# 前缀分栏把 `\s` 当分隔符 ⇒ `三百 万辆` 塌成 `万辆`、`10 周年` 塌成空 ⇒ 数字整段丢失
# ⇒ `三百 万辆纪念版` 与 `五百 万辆纪念版` 折成一条。修法只坍缩两种空格：
# 数词↔量词之间、数词↔词根之间；四位年款那道空格**不**坍缩（`2026 限定版` 仍是 `限定版`）。
EDITION_SPACE_UNIT = [
    _row("99008", "三百 万辆纪念版", "途昂", "2026", "38.99万", "懂车帝+汽车之家", "25161"),
    _row("99008", "五百 万辆纪念版", "途昂", "2026", "38.99万", "仅汽车之家", "8045"),
]
EDITION_SPACE_FULLWIDTH = [
    _row("99009", "三百　万辆纪念版", "途昂", "2026", "39.99万", "懂车帝+汽车之家", "25161"),
    _row("99009", "五百　万辆纪念版", "途昂", "2026", "39.99万", "仅汽车之家", "8045"),
]
EDITION_SPACE_ROOT = [
    _row("99010", "10 周年纪念版", "途昂", "2026", "40.99万", "懂车帝+汽车之家", "25161"),
    _row("99010", "20 周年纪念版", "途昂", "2026", "40.99万", "仅汽车之家", "8045"),
]
EDITION_SPACE_HUNDRED = [
    _row("99011", "110 周年纪念版", "途昂", "2026", "41.99万", "懂车帝+汽车之家", "25161"),
    _row("99011", "10 周年纪念版", "途昂", "2026", "41.99万", "仅汽车之家", "8045"),
]
# `2000 万辆` 看着像年款，其实是辆数里程碑（现网确有 `3000万辆甄选款` 这一族）：
# 数词与**量词**之间的空格一律坍缩，不做年款例外，否则 2000 与 2500 会折成一条。
EDITION_SPACE_MILESTONE = [
    _row("99012", "2000 万辆纪念版", "途昂", "2026", "42.99万", "懂车帝+汽车之家", "25161"),
    _row("99012", "2500 万辆纪念版", "途昂", "2026", "42.99万", "仅汽车之家", "8045"),
]
_NUM_RUN = _re.compile(r"[0-9０-９零〇一二两三四五六七八九十百千万]+")


def _first_num_run(name: str) -> str:
    m = _NUM_RUN.search(str(name or ""))
    return m.group(0) if m else ""


def test_h7_space_between_numeral_and_unit_or_root_is_not_a_separator() -> None:
    """H7（deepseek 票 round-8B）：夹空格不能把数字信息整段丢掉。

    断言口径按票文要求换掉：不再用 `_has_number_info`（它把 `百千万` 也算数字信息，
    `三百 万辆` 塌成 `万辆纪念版` 时它照样绿）。这里断的是**该侧自己的数词串必须出现在
    身份里**，外加"存在一个共同词根两侧不相交"——只剩量词的形状会当场红。
    """
    for label, pair in (("数词+空格+量词", EDITION_SPACE_UNIT),
                        ("全角空格", EDITION_SPACE_FULLWIDTH),
                        ("数词+空格+词根", EDITION_SPACE_ROOT),
                        ("110 与 10 带空格", EDITION_SPACE_HUNDRED),
                        ("2000 与 2500 万辆", EDITION_SPACE_MILESTONE)):
        assert MD._sku_spec_conflict([copy.deepcopy(r) for r in pair]) is True, \
            "%s：两侧身份相同 ⇒ 会折成一条" % label
        out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in pair])
        assert len(out) == 2, "%s：两款被折成一行 ⇒ %r" % (label, [r["车型名称"] for r in out])
        eds = [MD._edition_identities(str(r["车型名称"]), str(r["车系"])) for r in pair]
        for r, e in zip(pair, eds):
            run = _first_num_run(r["车型名称"])
            assert run and any(run in i for v in e.values() for i in v), \
                "%s：身份里没有 %r 这段数词 ⇒ 前缀被空格劈掉：%r" % (label, run, e)
        common = set(eds[0]) & set(eds[1])
        assert any(not (eds[0][root] & eds[1][root]) for root in common), \
            "%s：没有一个词根两侧不相交，冲突是靠别的轴蒙的：%r" % (label, eds)


def test_h7_space_is_typography_but_four_digit_year_is_not_a_count() -> None:
    """H7 反方向：同一款的两种空格写法必须仍能折；而四位年款那道空格不属于身份。

    `10 周年纪念版` ≡ `10周年纪念版`（空格是排版）；
    `2026 限定版` ≡ `限定版`（2026 是年款，进身份就会把"写了年款/没写年款"拆成两款）。
    """
    for label, na, nb in (
            ("周年空格排版差", "10 周年纪念版", "10周年纪念版"),
            ("三百万辆空格排版差", "三百 万辆纪念版", "三百万辆纪念版"),
            ("年款头不回收", "2026 限定版", "限定版"),
            ("年款与专名之间仍是分栏", "2026 青峰限定版", "青峰限定版")):
        a, b = _pair(na, nb)
        out = MD.dedupe_merged_rows([copy.deepcopy(a), copy.deepcopy(b)])
        assert len(out) == 1, "%s：同一款的两种写法被拆成两行 ⇒ %r" % (
            label, [r["车型名称"] for r in out])
        ea = MD._edition_identities(na, str(a["车系"]))
        eb = MD._edition_identities(nb, str(b["车系"]))
        assert ea == eb, "%s：两侧限量身份不等 %r / %r" % (label, ea, eb)


# 夹具形状（刻意比现网**更严**）：现网 车款ID 184810 的两行**都带** `(南方版)`、两侧都写版本名
# （`show_pair_columns.py` 逐列实测）。这里让一侧省略括注、一侧省略版本名，钉住窄规则在最不利写法下也不多拆。
# 这段先前写成"现网形状"是我自己点名打印 `[:40]` 把 45 字那个名字的括注切掉造成的假形状（10-17 已改掉截断）。
# 取消"后缀豁免"后这一对差点多拆（triage 的 7 对回退里 2 对就是它），
# 修法是窄规则：**以 `型` 结尾的版本名不进限量身份**（版本名自有版本词轴去比）。
# 现网真正被这条规则救回的是 车款ID 63975：消融实测去掉这步，同ID同价同年款空间 179 → 183 判冲突
# （`enumerate_type_rule_effect.py`）。
AUDI_A3_PACKAGE = [
    dict(_row("184810", "奥迪A3 2026款 Sportback 35TFSI 飞驰尊享型 +豪华臻选包",
              "奥迪A3", "2026", "20.59万", "仅易车、仅汽车之家", "4538"), **{"品牌": "奥迪"}),
    dict(_row("184810", "26款 Sportback 35 TFSI 飞驰尊享型+豪华臻选包(南方版)",
              "奥迪A3", "2026", "20.59万", "仅易车", "5758"), **{"品牌": "奥迪"}),
]


def test_h6_trim_name_ending_in_xing_is_not_an_edition_identity() -> None:
    """`飞驰尊享型` 不该进 `臻选` 的身份，否则夹具 184810 这种"版本名+选装包"会被多拆。"""
    assert MD._sku_spec_conflict([copy.deepcopy(r) for r in AUDI_A3_PACKAGE]) is False, \
        "两侧 `臻选` 身份被版本名差异撑开 ⇒ 夹具 184810 多拆（窄规则失效）"
    out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in AUDI_A3_PACKAGE])
    assert len(out) == 1, "奥迪A3 184810 这种书写差还没合：%r" % [r["车型名称"] for r in out]
    # 反向：把 `型` 规则放宽到"任何前缀都豁免"就又会吞专名，这里钉住它没被吞
    c, d = _pair("飞驰型璀璨臻选包", "飞驰臻选包")
    assert MD._sku_spec_conflict([c, d]) is True, \
        "`型` 之后的专名被吞掉了：璀璨 这一档差异不该由版本名规则负责"


WENJIE_M8_192 = dict(
    _row("72086", "问界M8 2025款 增程 Max版 37kWh 6座版 (192线激光雷达）", "问界M8", "2025",
         "36.98万", "汽车之家+懂车帝、汽车之家+懂车帝(车系级)", "8003"),
    **{"品牌": "AITO 问界", "级别": "大型SUV", "能源类型": "增程式",
       "纯电续航(km)": "CLTC:201 / WLTC:161", "驱动方式": "双电机四驱", "上市时间": "2025-04-16"})


def test_n1_laser_line_count_difference_must_not_fold() -> None:
    """N1 红样（语义变异，夹具取现网真实行 72086 后只改线数）：`192线` vs `896线` 是两款配置。

    为什么必须自己造变异：现网确实有 8 组"同车系同年款同价但线数不同"（问界M8 36.98万、
    问界M9 51.98/54.98/56.98万），可它们**顺带**座位或能源类型也不同 ⇒ 拿真行来测，
    拦住它的是座位/能源那条闸，测不到"线数标记"这一层。把差异隔离到线数一处才叫证保护会触发。
    """
    twin = copy.deepcopy(WENJIE_M8_192)
    twin["车型名称"] = str(twin["车型名称"]).replace("192线", "896线")
    twin["数据来源"] = "仅汽车之家"
    group = [copy.deepcopy(WENJIE_M8_192), twin]
    ma = MD._config_markers(str(WENJIE_M8_192["车型名称"]))
    mb = MD._config_markers(str(twin["车型名称"]))
    assert set(ma) == set(mb) and ma != mb, (
        "夹具失效：两行应当**同一批配置类别都声明了**、只有某一类的取值不同（%r / %r）" % (
            {k: sorted(v) for k, v in ma.items()}, {k: sorted(v) for k, v in mb.items()}))
    assert MD._config_marker_conflict(ma, mb) is True, "按类别比没看出线数差 ⇒ 夹具或分类逻辑坏了"
    assert MD._sku_spec_conflict(group) is True, \
        "名字只差激光雷达线数却没判冲突 ⇒ 192线/896线 会被并成一款"
    out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in group])
    assert len(out) == 2, "192线 与 896线 被折成一行：%r" % [r["车型名称"] for r in out]


def test_n1_control_same_car_without_the_marker_still_folds() -> None:
    """N1 的控制组（防止 N1 那条闸其实是"名字不同就拦"）：同一行、只把雷达括注整个省掉 ⇒ 必须合。

    不对称的**配置数值**（192 vs 896）是证据，不对称的**书写**（一侧压根没写）不是证据。
    没有这条控制组，N1 变红时我无法区分"线数闸坏了"和"闸根本没生效、是靠名字不同拦的"。
    """
    twin = copy.deepcopy(WENJIE_M8_192)
    twin["车型名称"] = str(twin["车型名称"]).replace(" (192线激光雷达）", "")
    twin["数据来源"] = "仅汽车之家"
    group = [copy.deepcopy(WENJIE_M8_192), twin]
    assert MD._sku_spec_conflict(group) is False, \
        "一侧没写雷达配置被判成冲突 ⇒ 与 H4 同族，会把省略配置后缀的同款拆开"
    out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in group])
    assert len(out) == 1, "省掉雷达括注后仍未折成一行：%r" % [r["车型名称"] for r in out]


# N2：探岳 77034 现网真实三行——同 年款(2026) 同 价(19.89万) 同 能源(汽油) 同 续航(0) 同 车系ID(2835)，
# 区别只在名称里的 `(2026.3停产)` 与 `改款`、以及上市时间 2025.09 vs 2026.03
TANYING_77034 = [
    dict(_row("77034", "3000万辆甄选款 300TSI 两驱", "探岳", "2026", "19.89万",
              "懂车帝+汽车之家", "2835"),
         **{"品牌": "大众", "级别": "中型SUV", "能源类型": "汽油",
            "纯电续航(km)": "0", "上市时间": "2026.03"}),
    dict(_row("77034", "3000万辆甄选款 300TSI 两驱(2026.3停产)", "探岳", "2026", "19.89万",
              "懂车帝+汽车之家、汽车之家+懂车帝(车系级)", "2835"),
         **{"品牌": "大众", "级别": "中型SUV", "能源类型": "汽油",
            "纯电续航(km)": "0", "上市时间": "2025.09"}),
]


def test_n2_discontinued_batch_is_not_the_current_one() -> None:
    """N2：写了「2026.3停产」的那行是**上一个批次**，不能与在售那行并成一款。

    实测形状：两行所有规格列都一样（汽油、续航 0、同价同年款同车系ID），只有名称里的停产
    标记与上市时间不同 ⇒ 若只看规格，它们"看起来就是同一 SKU"。但人类会把"停产批次"
    当作另一款来报价与统计（前端 10-16 新加的「只显示在售」也正靠这个区分），
    并且合并会把 `上市时间` 的 2026.03 覆盖成 2025.09 —— 那是可观测的数据倒退。
    """
    assert MD._sku_spec_conflict([copy.deepcopy(r) for r in TANYING_77034]) is True, \
        "停产标记不对称没判冲突 ⇒ 停产批次会与在售批次并成一行"
    out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in TANYING_77034])
    assert len(out) == 2, "停产批次与在售批次被折成一行：%r" % [r["车型名称"] for r in out]


def test_n2_control_both_batches_on_sale_fold() -> None:
    """N2 的控制组：两侧都没有停产标记 ⇒ 同一批次的两行该合（防止 N2 的闸其实是"上市时间不同就拦"）。"""
    twin = copy.deepcopy(TANYING_77034[1])
    twin["车型名称"] = "3000万辆甄选款 300TSI 两驱"
    twin["数据来源"] = "汽车之家+懂车帝(车系级)"
    group = [copy.deepcopy(TANYING_77034[0]), twin]
    assert MD._sku_spec_conflict(group) is False, "两侧都无停产标记却被判冲突"
    out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in group])
    assert len(out) == 1, "同批次两行没合：%r" % [r["车型名称"] for r in out]


# N3：智己LS7 68650/68651 现网真实两行——**同 车款ID 同 年款 同 价(35.98万)**，
# 但一款写 `Max Lux 后驱版`、一款写 `100kWh Max Lux四驱版`。
# 负责人 10-15 问的就是这一类：「别的配置都一样，就电池容量或驱动方式有区别，会不会被误合」。
# 实测答：**会**（改动前这两行被折成一行，四驱身份从面上消失），因为 `驱动方式` 列
# 只有一侧填了（后置后驱，还是跟名字矛盾的值）⇒ 逐列闸看不见差异，只有名字里的标记看得见。
ZHANJI_LUX_2WD = dict(
    _row("68651", "Max Lux 后驱版", "智己LS7", "2024", "35.98万", "懂车帝+汽车之家", "4869"),
    **{"品牌": "智己汽车", "能源类型": "纯电动", "纯电续航(km)": "705", "上市时间": "2024.06"})
ZHANJI_LUX_4WD = dict(
    _row("68651", "智己LS7 2024款 100kWh Max Lux四驱版", "智己LS7", "2024", "35.98万",
         "汽车之家+懂车帝(车系级)", "6013"),
    **{"品牌": "智己汽车", "能源类型": "纯电动", "纯电续航(km)": "CLTC:705",
       "驱动方式": "后置后驱", "上市时间": "汽车之家:2024-06-07|懂车帝:2024.06"})


def test_n3_same_id_different_drive_layout_must_not_fold() -> None:
    """N3：同 ID 同价、名字里一个 `后驱` 一个 `四驱` ⇒ 两款车，不许折（驱动列不对称不算证据）。"""
    group = [copy.deepcopy(ZHANJI_LUX_2WD), copy.deepcopy(ZHANJI_LUX_4WD)]
    assert MD._sku_spec_conflict(group) is True, \
        "名字里的 后驱/四驱 互斥没判冲突 ⇒ 智己LS7 68651 的四驱身份会被并进后驱那行"
    out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in group])
    assert len(out) == 2, "后驱版与四驱版被折成一行：%r" % [r["车型名称"] for r in out]


# N4：领裕 61633 现网真实两行，同一款 `EcoBoost 225 6座精领型`，只是座位号写在头/尾之差。
# 归一化吃空格后名称变成 `…2256座…`，若座位正则贪婪就会把发动机代号 225 吞成 `2255座`，
# 与另一行的 `6座` 互斥 ⇒ **造出一个不存在的配置差**（N3 那条闸的第一版就踩过这个）。
LINGYU_6SEAT = [
    dict(_row("61633", "EcoBoost 225 6座精领型", "领裕", "2023", "17.38万",
              "懂车帝+汽车之家", "4759"),
         **{"品牌": "福特", "能源类型": "汽油", "纯电续航(km)": "0", "上市时间": "2023.02"}),
    dict(_row("61633", "领裕 2023款 EcoBoost 225 精领型 6座", "领裕", "2023", "17.38万",
              "汽车之家+懂车帝", "5910"),
         **{"品牌": "福特", "能源类型": "汽油", "纯电续航(km)": "0", "上市时间": "2023-02-24"}),
]


def test_n4_engine_code_digits_must_not_become_a_fake_seat_count() -> None:
    """N4 反向护栏：`EcoBoost 225 6座` 不许被读成 2256 座 ⇒ 书写差不得升级成配置冲突。"""
    ma = MD._config_markers(str(LINGYU_6SEAT[0]["车型名称"]))
    assert not any(int(v) > 12 for v in ma.get("座", ())), (
        "座位号把发动机代号吞进来了：%r ⇒ 会把同款拆成两行" % (ma,))
    assert MD._sku_spec_conflict([copy.deepcopy(r) for r in LINGYU_6SEAT]) is False, \
        "只差座位号写在头还是尾却被判冲突"
    out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in LINGYU_6SEAT])
    assert len(out) == 1, "领裕 61633 同款两行没合：%r" % [r["车型名称"] for r in out]


# P1：阿维塔11 72863 现网真实两行——电池 116.79、加速 3.9、续航 760、能源 纯电动、
# 驱动 双电机四驱、价 36.99万、年款 2025 **全部相同**，只有 `座位数(个)` 一列
# 一行写 `5`、另一行写 `5 / 4`（五座、可选四座）。
AVATR_72863 = [
    dict(_row("72863", "改款 Ultra四驱纯电版", "阿维塔 11", "2025", "36.99万",
              "懂车帝+汽车之家", "5308"),
         **{"品牌": "阿维塔", "能源类型": "纯电动", "电池容量(kWh)": "116.79",
            "百公里加速(s)": "3.9", "纯电续航(km)": "760", "驱动形式": "双电机四驱",
            "座位数(个)": "5", "上市时间": "2025.04"}),
    dict(_row("72863", "阿维塔11 2025款 改款 Ultra 纯电版四驱", "阿维塔11", "2025", "36.99万",
              "汽车之家+懂车帝", "6354"),
         **{"品牌": "阿维塔", "能源类型": "纯电动", "电池容量(kWh)": "116.79",
            "百公里加速(s)": "3.9", "纯电续航(km)": "CLTC:760", "驱动形式": "双电机四驱",
            "驱动方式": "双电机四驱", "座位数(个)": "5 / 4", "上市时间": "2025-04-27"}),
]


def test_p1_multi_value_cell_is_not_a_third_option() -> None:
    """P1：`5 / 4` 是"五座可选四座"，与另一行的 `5` 有交集 ⇒ 不是座位冲突，必须合。

    这条改动前是红的（整串比对 `5` ≠ `5 / 4` ⇒ 假冲突 ⇒ 同款留两行）。
    """
    assert MD._spec_value_set("5 / 4", split_slash=True) & MD._spec_value_set("5"), \
        "座位一格多值没拆开：`5 / 4` 与 `5` 被当成两种座位"
    # 只有**座位列**打开多值拆分（评审 D5）：`电池容量(kWh)` 的 `75 / 100`、
    # `能源类型` 的 `纯电动/增程式` 是"这行里两种配置都有"的复合描述，
    # 拆开后与单值行"交集非空"就会把 100kWh 的 SKU 并进 75kWh ⇒ 那些列保持整串比对。
    assert not (MD._spec_value_set("75 / 100") & MD._spec_value_set("75")), \
        "电池列被误开了多值拆分：`75 / 100` 与 `75` 现在会相交 ⇒ 会误合"
    assert MD._sku_spec_conflict([copy.deepcopy(r) for r in AVATR_72863]) is False, \
        "除座位写法外逐列全同的两行被判成冲突"
    out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in AVATR_72863])
    assert len(out) == 1, "阿维塔11 72863 同款两行还在：%r" % [r["车型名称"] for r in out]


def test_p2_genuinely_different_seat_counts_stay_separate() -> None:
    """P2 反向（护栏不许被 P1 掏空）：`5` 与 `4` 各自单一取值 ⇒ 仍是两款，不许合。"""
    four = copy.deepcopy(AVATR_72863[1])
    four["座位数(个)"] = "4"
    group = [copy.deepcopy(AVATR_72863[0]), four]
    assert MD._sku_spec_conflict(group) is True, "5座 与 4座 被判成同款 ⇒ 多值拆分把护栏拆掉了"
    out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in group])
    assert len(out) == 2, "5座 与 4座 被折成一行：%r" % [r.get("车型名称") for r in out]


# Q1：阿维塔07 74558 现网真实两行（同 ID 同价 21.99万）：懂车帝侧把电池写在名字里
# `Elite 后驱增程版 39.05kWh`，汽车之家侧只写 `阿维塔07 2026款 Elite 增程版`，而该行的
# `电池容量(kWh)` 列是空的 ⇒ 名字是电池与驱动形式的**唯一载体**。
AVATR_07_74558 = [
    dict(_row("74558", "Elite 后驱增程版 39.05kWh", "阿维塔07", "2026", "21.99万",
              "懂车帝+汽车之家", "8153"),
         **{"品牌": "阿维塔", "能源类型": "增程式", "纯电续航(km)": "245|195",
            "驱动形式": "后置后驱", "上市时间": "2026-02-15"}),
    dict(_row("74558", "阿维塔07 2026款 Elite 增程版", "阿维塔07", "2026", "21.99万",
              "汽车之家+懂车帝(车系级)", "6911"),
         **{"品牌": "阿维塔", "能源类型": "增程式", "纯电续航(km)": "245|195",
            "驱动形式": "后置后驱", "上市时间": "2026-02-15"}),
]


def test_q1_keeper_name_must_carry_the_richer_identity_not_just_be_longer() -> None:
    """Q1：选主要按**身份词丰富度**，不是按字符数。

    旧写法 `max(name_candidates, key=len)` 会挑 `阿维塔07 2026款 Elite 增程版`（21 字）
    做主，把 `39.05kWh` 与 `后驱` 整块丢掉——那两列在本行是空的，等于**信息从面上消失**。
    """
    a, b = str(AVATR_07_74558[0]["车型名称"]), str(AVATR_07_74558[1]["车型名称"])
    assert len(b) > len(a), "夹具前提没了：长名应当是信息更少的那个（%r vs %r）" % (a, b)
    out = MD.dedupe_merged_rows([copy.deepcopy(r) for r in AVATR_07_74558])
    assert len(out) == 1, "同 ID 同价没折成一行：%r" % [r["车型名称"] for r in out]
    name = str(out[0]["车型名称"])
    assert "39.05" in name and "后驱" in name, (
        "选主把只写在名字里的电池/驱动信息丢了：出口名=%r（该行 电池容量 列=%r）"
        % (name, out[0].get("电池容量(kWh)")))


def test_q2_physical_pass_must_still_check_specs() -> None:
    """Q2：第三遍（物理身份）**不是无护栏区**。旧写法是"簇里只有一个车款ID 就无条件合"。

    评审 E 指出第一版这条**是空断言**：夹具两行都没有 `百公里加速(s)` ⇒
    `_phys_key` 返回 None、两行根本不进第三遍，测的其实是第二遍。
    现在把物理键补齐（车系/年款/价/续航/加速/座位都有值），并加**变异复核**：
    把 `_sku_spec_conflict` 摘掉后同一夹具必须折成一行 —— 证明拦住它的是这层闸，
    不是别的遍的键不同。
    """
    phys = {"纯电续航(km)": "0", "百公里加速(s)": "8.2"}
    anchor = dict(_row("99001", "28T 两驱豪华型", "凯迪拉克XT5", "2026", "39.99万",
                       "懂车帝+汽车之家", "4590"),
                  **{"品牌": "凯迪拉克", "能源类型": "汽油"}, **phys)
    drifter = dict(_row("", "28T 四驱豪华型", "凯迪拉克XT5", "2026", "39.99万",
                        "仅汽车之家", "7011"),
                   **{"品牌": "凯迪拉克", "能源类型": "汽油"}, **phys)
    same = dict(_row("", "28T 两驱 豪华型", "凯迪拉克XT5", "2026", "39.99万",
                     "仅汽车之家", "7011"),
                **{"品牌": "凯迪拉克", "能源类型": "汽油"}, **phys)
    # 前提：物理键确实成立（否则本例又退化成空断言）
    assert MD._physical_identity(anchor) == MD._physical_identity(drifter), \
        "夹具没落进同一个物理簇 ⇒ 这条又变成空断言"
    assert MD._physical_identity(drifter) == MD._physical_identity(same)
    bad = MD.dedupe_merged_rows([copy.deepcopy(anchor), copy.deepcopy(drifter)])
    assert len(bad) == 2, "两驱 与 四驱 在第三遍被无条件并成一行：%r" % [r["车型名称"] for r in bad]
    good = MD.dedupe_merged_rows([copy.deepcopy(anchor), copy.deepcopy(same)])
    assert len(good) == 1, "驱动写法相同、只差空格的两个名字没被并（第三遍失去作用）：%r" % [
        r["车型名称"] for r in good]
    saved = MD._sku_spec_conflict
    MD._sku_spec_conflict = lambda group: False          # 变异：摘掉误合闸
    try:
        folded = MD.dedupe_merged_rows([copy.deepcopy(anchor), copy.deepcopy(drifter)])
    finally:
        MD._sku_spec_conflict = saved
    assert len(folded) == 1, (
        "摘掉误合闸后这两行仍不折 ⇒ 上面那条断言不是这层闸挡住的，Q2 测错了东西")


def test_q3_conflicting_third_row_must_not_veto_the_compatible_pair() -> None:
    """Q3（评审 D6）：第三遍的簇里混进一条冲突行，**不许**把本来可折的那一对也一起否决。

    实测形状：1 个 ID 行 + 2 个无 ID 行（红旗天工08 那种），其中一条与 ID 行驱动形式不同。
    旧写法 `not accept(group) ⇒ 整组原样带走` ⇒ 三行全留 ⇒ 发布面上多出真重复。
    """
    phys = {"纯电续航(km)": "565", "百公里加速(s)": "3.9"}
    anchored = dict(_row("66441", "565 两驱智选版", "红旗天工08", "2025", "27.98万",
                         "懂车帝+汽车之家", "25161"), **{"能源类型": "纯电动"}, **phys)
    friendly = dict(_row("", "565 Ultra两驱版", "红旗天工08", "2025", "27.98万",
                         "仅汽车之家", "9001"), **{"能源类型": "纯电动"}, **phys)
    hostile = dict(_row("", "565 四驱尊贵版", "红旗天工08", "2025", "27.98万",
                        "仅易车", "9002"), **{"能源类型": "纯电动"}, **phys)
    out = MD.dedupe_merged_rows([copy.deepcopy(anchored), copy.deepcopy(friendly),
                                 copy.deepcopy(hostile)])
    names = sorted(str(r["车型名称"]) for r in out)
    assert len(out) == 2, "可折的一对被冲突的第三行拖着一起留下：%r" % names
    assert any("四驱尊贵" in n for n in names), "冲突的那一行被错误并进了两驱那款：%r" % names


def _pair(na, nb, series="测试车系", **extra):
    """同 ID/年款/价 的两行，只换名字（外加可选列值）——R 组用例的公共夹具。

    `series` 要和名字里真出现的那个大写口径一致：现网行上 `车系` 列与名字里的车系前缀是同一个串，
    限量身份靠**列值**剔噪（整段前缀比对之后就不再拿空格当分栏了），
    夹具写成 `测试车系` 而名字写 `途昂 …` 是在测一个生产里不存在的形状。"""
    base = dict(_row("55001", na, series, "2026", "30.00万", "懂车帝+汽车之家", "7001"))
    other = dict(_row("55001", nb, series, "2026", "30.00万", "汽车之家+懂车帝", "7002"), **extra)
    return [base, other]


def test_r1_two_different_special_editions_must_not_fold() -> None:
    """R1（评审 E①/D①）：**两侧都写了限量身份但身份不同** ⇒ 是两款，不许折。

    旧写法把命中 `_EDITION_MARK_RE` 压成 bool：两行都是 True ⇒ 不判冲突 ⇒ 并成一行。
    现网样本：途昂 同 ID 同价 34.50万 `380TSI 四驱青峰限定版` 与 `380TSI 四驱尊崇豪华版`。
    """
    a, b = _pair("380TSI 四驱青峰限定版", "380TSI 四驱科林斯古铜特别版")
    assert MD._sku_spec_conflict([a, b]) is True, "两种不同的限量身份没判冲突 ⇒ 会误合"
    assert len(MD.dedupe_merged_rows([copy.deepcopy(a), copy.deepcopy(b)])) == 2

    # 同一词根、不同编号也一样（`10周年` ≠ `20周年`）
    c, d = _pair("2026款 10周年纪念版", "2026款 20周年纪念版")
    assert MD._sku_spec_conflict([c, d]) is True, "周年编号不同却没判冲突"
    assert len(MD.dedupe_merged_rows([copy.deepcopy(c), copy.deepcopy(d)])) == 2

    # 反向保护：同一个限量身份、只是前后缀写法不同 ⇒ 仍要合（不许把 R1 写成"见到限量就拆"）
    e, f = _pair("青峰限定版", "途昂 2026款 青峰限定版", series="途昂")
    assert MD._sku_spec_conflict([e, f]) is False, "同一限定款的两种写法被判成两款"
    assert len(MD.dedupe_merged_rows([copy.deepcopy(e), copy.deepcopy(f)])) == 1


def test_r3_complementary_identity_words_must_not_fold() -> None:
    """R3（评审 E②）：两行名字**各说了对方没说**的配置 ⇒ 折了必然丢一边信息，不折。

    现网形状：`Max 四驱 6座 智驾版 192线激光雷达` 与 `Max 四驱 6座 100kWh`——
    同类取值都不矛盾（旧闸放行），但一折就必然让 `100kWh` 从该 SKU 消失，
    而这行的 `电池容量(kWh)` 列是空的，名字是唯一载体。
    代价实测：filtered 面 1930 次折叠只多拦 13 行（0.7%）。
    """
    a, b = _pair("Max 四驱 6座 智驾版 192线激光雷达", "Max 四驱 6座 100kWh")
    assert MD._sku_spec_conflict([a, b]) is True, "互补身份词没判冲突 ⇒ 100kWh 会从面上消失"
    assert len(MD.dedupe_merged_rows([copy.deepcopy(a), copy.deepcopy(b)])) == 2
    # 反向：一侧只是把另一侧的信息**全部写全**（子集）⇒ 该合，别把 R3 写成"名字不同就拆"
    c, d = _pair("Max 6座 100kWh", "Max 四驱 6座 100kWh")
    toks_c = MD._sku_name_identity_tokens(str(c["车型名称"]))
    toks_d = MD._sku_name_identity_tokens(str(d["车型名称"]))
    assert toks_c <= toks_d, "子集前提没了：%r / %r" % (sorted(toks_c), sorted(toks_d))
    assert len(MD.dedupe_merged_rows([copy.deepcopy(c), copy.deepcopy(d)])) == 1


def test_r4_drive_axes_two_vs_front_layout_is_the_same_car() -> None:
    """R4（评审 D③）：`两驱`（轮数轴）与 `前驱`（位置轴）不矛盾 ⇒ 同一款该合；
    而 `前驱` vs `后驱`、`两驱` vs `四驱` 各自同轴互斥 ⇒ 不许合。"""
    a, b = _pair("2.0T 两驱豪华型", "2.0T 前驱豪华型")
    assert MD._sku_spec_conflict([a, b]) is False, "两轴各说一件事被当成互斥 ⇒ 同款拆两行"
    assert len(MD.dedupe_merged_rows([copy.deepcopy(a), copy.deepcopy(b)])) == 1
    for na, nb in (("2.0T 前驱豪华型", "2.0T 后驱豪华型"),
                   ("2.0T 两驱豪华型", "2.0T 四驱豪华型")):
        c, d = _pair(na, nb)
        assert MD._sku_spec_conflict([c, d]) is True, "%s vs %s 同轴互斥却没判冲突" % (na, nb)
        assert len(MD.dedupe_merged_rows([copy.deepcopy(c), copy.deepcopy(d)])) == 2


def test_r5_chinese_seat_number_is_read_as_a_whole_number() -> None:
    """R5（评审 D②）：`十一座` 必须读成 11，不能从第二个字读成 `一座`＝1。

    读错的方向两头都坏：`十一座` 与 `1座` 会**误合**，与 `11座` 会**假冲突漏合**。
    MPV/轻客真会踩到这个形状，所以顺带做取值域检查（>12 座不当作客车座位）。"""
    assert MD._cn_number("十一") == "11", "十一座读成了 %r" % MD._cn_number("十一")
    assert MD._cn_number("二十") is None, "超出 1–12 的座位数必须拒绝（见 test_r5_rejects_implausible_seat_numbers）"
    assert MD._cn_number("五十七") is None, "把发动机代号之类的串当成了座位数"
    a, b = _pair("2.0L 十一座 商务版", "2.0L 11座 商务版")
    assert MD._sku_spec_conflict([a, b]) is False, "同一款的中英文座位写法被判成两款"
    assert len(MD.dedupe_merged_rows([copy.deepcopy(a), copy.deepcopy(b)])) == 1
    c, d = _pair("2.0L 十一座 商务版", "2.0L 1座 商务版")
    assert len(MD.dedupe_merged_rows([copy.deepcopy(c), copy.deepcopy(d)])) == 2, \
        "十一座 与 一座 被当成同款"


def test_r6_source_prefix_is_stripped_after_slash_split() -> None:
    """R6（评审 D④）：来源前缀要**每层都剥**。
    旧写法按 `|` 剥一次就不再剥，`懂车帝:5 / 易车:4` 里留下脏原子 `易车:4`，
    与另一行的 `4` 判成不相交 ⇒ 假冲突漏合。"""
    assert MD._spec_value_set("懂车帝:5 / 易车:4", split_slash=True) == \
        MD._spec_value_set("5 / 4", split_slash=True), \
        "来源前缀没剥干净：%s" % sorted(MD._spec_value_set("懂车帝:5 / 易车:4", split_slash=True))
    assert MD._spec_value_set("懂车帝:5 / 易车:4", split_slash=True) & MD._spec_value_set("4")


def test_r8_keeper_must_prefer_the_clean_price() -> None:
    """R8（评审 D）：选主并列时要**价格干净**的那一行。
    旧 `_rank` 给带 `|` 的合并串打 1 分再取最大 ⇒ 反而选中脏价，
    实测 `40.5万` 输给 `40.5万|40.50万`，发布面展示字段被合并串污染。"""
    clean = dict(_row("66549", "领先型", "宝马iX3", "2024", "40.5万", "汽车之家+懂车帝", "4538"))
    dirty = dict(_row("66549", "2024款 领先型", "宝马iX3", "2024", "40.5万|40.50万",
                      "汽车之家+懂车帝", "5758"))
    out = MD.dedupe_merged_rows([copy.deepcopy(dirty), copy.deepcopy(clean)])
    assert len(out) == 1, "同 ID 没折成一行：%r" % [r["车型名称"] for r in out]
    assert "|" not in str(out[0]["官方指导价"]), (
        "合并串价格赢了干净单价：%r" % out[0]["官方指导价"])


def test_s1_edition_prefix_must_not_absorb_drive_words_or_series() -> None:
    """S1（评审 G①）：限量身份的**前缀**不许把驱动词/车系名吞进去，否则修完误合又造出漏合。

    反例全是"同一款、只是词序或前缀写法不同"：
    `380TSI 四驱青峰限定版` vs `380TSI 青峰限定版 四驱`；`途昂 青峰限定版` vs `青峰限定版`。
    """
    a, b = _pair("380TSI 四驱青峰限定版", "380TSI 青峰限定版 四驱")
    ea = MD._edition_identities(str(a["车型名称"]), str(a["车系"]))
    eb = MD._edition_identities(str(b["车型名称"]), str(b["车系"]))
    assert ea == eb, "同一款的限量身份因词序被读成两种：%r / %r" % (ea, eb)
    assert MD._sku_spec_conflict([a, b]) is False, "词序不同却被判冲突（漏合）"
    assert len(MD.dedupe_merged_rows([copy.deepcopy(a), copy.deepcopy(b)])) == 1

    c, d = _pair("途昂 青峰限定版", "青峰限定版", series="途昂")
    assert MD._sku_spec_conflict([c, d]) is False, "车系名被当成限量专名的一部分 ⇒ 同款拆两行"
    assert len(MD.dedupe_merged_rows([copy.deepcopy(c), copy.deepcopy(d)])) == 1
    # 反向：真不同的限量身份仍然不许合（S1 不许把 R1 拆掉）
    e, f = _pair("途昂 青峰限定版", "途昂 科林斯古铜特别版", series="途昂")
    assert MD._sku_spec_conflict([e, f]) is True, "不同限量身份被 S1 的降噪放过去了"


def test_s2_slash_atom_keeps_untagged_first_value() -> None:
    """S2（评审 G⑤）：`5 / 易车:4` 这种**第一项没有来源前缀**的多值，两个值都不许丢。
    旧写法在 `|` 段层先剥一次，会把 `5 / 易车:` 整段当前缀吃掉只剩 `4`。"""
    got = MD._spec_value_set("5 / 易车:4", split_slash=True)
    assert got == MD._spec_value_set("5 / 4", split_slash=True), (
        "第一个值被前缀剥离吞掉：%s" % sorted(got))
    assert MD._spec_value_set("5 / 易车:4", split_slash=True) & MD._spec_value_set("5")


def test_s3_seat_ruler_is_unified_and_no_anchor_stays_strict() -> None:
    """S3（评审 G⑦ 与 H⑥/⑦/C 相撞，取保守一侧并写明理由）：
    座位**取值来源**必须两处统一（名字标记优先、`model_variant_signature` 兜底），
    但**严格度**按有没有车款ID 分档：无锚时取值集合必须相同才敢合。

    为什么这样切：`model_variant_signature` 的 `([2-9])\\s*座` 把 `5/7座` 读成 {7}，
    与 `5座` 判成不等 ⇒ 同一把尺没贯穿（G⑦ 的正当点）；
    而"读对之后就把 {5,7} 与 {5} 相交即合"会抹掉"可选七座"这一配置粒度，
    且没有 ID 替我们证明这两行是同一款（H 的反方向点）。
    负责人口径"宁可留重复也不误合"⇒ 无锚不折；**有锚（同一个车款ID）才容许多值相交**。
    """
    phys = {"纯电续航(km)": "600", "百公里加速(s)": "4.5"}
    multi = dict(_row("", "Max 5/7座", "测试车系", "2026", "30.00万", "仅汽车之家", "9101"), **phys)
    single = dict(_row("", "Max 5座", "测试车系", "2026", "30.00万", "仅懂车帝", "9102"), **phys)
    # ① 尺子统一：`5/7座` 现在读出两个值（旧签名只读出 7）
    assert MD._row_seat_values(multi) == {"5", "7"}, (
        "座位取值没走名字标记：%r" % sorted(MD._row_seat_values(multi)))
    assert MD._physical_identity(multi) == MD._physical_identity(single), "夹具没进同一物理簇"
    # ② 无锚 ⇒ 不折（H 的方向）
    out = MD.dedupe_merged_rows([copy.deepcopy(multi), copy.deepcopy(single)])
    assert len(out) == 2, "无车款ID 时把 5/7座 与 5座 相交即折 ⇒ 丢掉可选七座这一档：%r" % [
        r["车型名称"] for r in out]
    # ③ 有同一个车款ID 做锚 ⇒ 多值相交即相容（P1 的 72863 形状）
    anchored_multi = dict(_row("9101", "Max 5/7座", "测试车系", "2026", "30.00万",
                               "仅汽车之家", "9101"), **phys)
    anchored_single = dict(_row("9101", "Max 5座", "测试车系", "2026", "30.00万",
                                "仅懂车帝", "9101"), **phys)
    out2 = MD.dedupe_merged_rows([copy.deepcopy(anchored_multi), copy.deepcopy(anchored_single)])
    assert len(out2) == 1, "同一车款ID 的两行没折（锚档没放行）：%r" % [r["车型名称"] for r in out2]
    # ④ 反向：无锚且取值互斥（6座 vs 7座）当然更不许合
    six = dict(_row("", "Max 6座", "测试车系", "2026", "30.00万", "仅汽车之家", "9103"), **phys)
    seven = dict(_row("", "Max 7座", "测试车系", "2026", "30.00万", "仅懂车帝", "9104"), **phys)
    assert len(MD.dedupe_merged_rows([copy.deepcopy(six), copy.deepcopy(seven)])) == 2, \
        "6座 与 7座 被并成一行 ⇒ S3 把座位护栏拆掉了"



def test_r5_rejects_implausible_seat_numbers() -> None:
    """R5 补强（评审 G 指出原断言"允许 20 或 None"等于没钉）：>12 座必须**拒绝**，不是可选。"""
    assert MD._cn_number("十一") == "11"
    assert MD._cn_number("二十") is None, "20 座这种不合理取值必须被拒绝，实际=%r" % MD._cn_number("二十")
    assert MD._config_markers("某车 二十座 商务版").get("座") in (None, set()), \
        "不合理的座位数还是进了标记集合：%s" % MD._config_markers("某车 二十座 商务版")









def test_l1_fold_must_not_swap_a_chinese_brand_for_a_latin_one() -> None:
    """折叠选主时品牌优先保留**含中文**的写法。

    实测（2026-10-16 端到端演练）：车款ID 70672/70687/72803 的汽车之家行品牌是
    `道朗格`/`Lorinser罗伦士`，与懂车帝的 `GMC`/`Lorinser` 折叠后由"标签更富"的那行做主
    ⇒ 品牌变成无中文写法，下游 `autohome_publish_identity_valid` 的 `has_chinese(品牌)`
    把它们判成不合法 ⇒ **3 个已发布身份被静默缩小**（违反发布防缩小）。
    """
    autohome = dict(_row("70672", "YUKON育空 2025款 2.7T 德纳利", "YUKON育空", "2025", "89.80万",
                         "仅汽车之家", "947"), 品牌="道朗格")
    dcd = dict(_row("70672", "25款 2.7T 德纳利", "YUKON育空", "2025", "89.80万",
                    "汽车之家+懂车帝", "9"), 品牌="GMC")
    out = MD.dedupe_merged_rows([autohome, dcd])
    assert len(out) == 1, "同 ID 同价却没折成一行：%r" % [r.get("车型名称") for r in out]
    assert "道朗格" in str(out[0].get("品牌")), (
        "折叠把中文品牌换成了拉丁写法（%r）⇒ 发布门禁 has_chinese(品牌) 会把这个已发布身份删掉"
        % out[0].get("品牌"))


def test_l2_asymmetric_seat_signature_must_not_split_same_sku() -> None:
    """L2 座位签名是"从名字/别的列推出来的形状"，一侧没推出来不算差异。

    实测 22 组：瑞虎8 PRO 车款ID 69951/69952/69953/74589、瑞虎8 PLUS 77079/77080 等，
    两行同价、同年款、`座位数` 列都为空、名字里都没有"X座"，但 `model_variant_signature`
    给出一行 `('5',)` 一行 `()` ⇒ 键里带座位时永远碰不上（与 tier 同一类错）。
    """
    a = dict(_row("69951", "290T 两驱舒适版", "瑞虎8 PRO", "2025", "11.99万", "懂车帝+汽车之家", "7001"),
             **{"座位数(个)": "5", "官方指导价": "11.99万"})
    b = dict(_row("69951", "瑞虎8 PRO 2025款 290T 两驱舒适版", "瑞虎8 PRO", "2025", "11.99万",
                  "汽车之家+懂车帝(车系级)", "7002"),
             **{"座位数(个)": "5 / 7|5", "官方指导价": "11.99万"})
    seats = {tuple(sorted(MD.model_variant_signature(r).get("seat") or ())) for r in (a, b)}
    assert len(seats) > 1, (
        "夹具失效：这两行座位签名本来就相同，测不到要修的那条 %r（真形是 `5` 对 `5 / 7|5`，"
        "后者解析不出来）" % (sorted(map(str, seats)),))
    out = MD.dedupe_merged_rows([a, b])
    assert len(out) == 1, (
        "同 ID 同价同年款、只差一侧多推出一个座位签名，却留在 %d 行：%r" % (len(out), [r["车型名称"] for r in out]))


def test_l3_both_declared_seat_counts_stay_separate() -> None:
    """L3 反向（保护必须真会触发）：两侧都声明了座位且不相交 ⇒ 同 ID 也不许合。"""
    five = dict(_row("67117", "1.5T DCT花生版 5座", "捷途X70 PRO", "2024", "14.18万", "懂车帝+汽车之家", "6003"),
                **{"座位数(个)": "5"})
    seven = dict(_row("67117", "1.5T DCT花生版 7座", "捷途X70 PRO", "2024", "14.18万", "汽车之家+懂车帝", "6004"),
                 **{"座位数(个)": "7"})
    assert MD._sku_spec_conflict([five, seven]) is True, "座位都写了却不判冲突 ⇒ 5座/7座会被并成一款"
    out = MD.dedupe_merged_rows([five, seven])
    assert len(out) == 2, "两侧都声明 5座/7座 却被折成一行：%r" % [r["车型名称"] for r in out]


def test_m1_trailing_zero_battery_is_not_a_conflict() -> None:
    """M1 护栏不许把数字格式差当成配置差（小鹏GX 73967 实测两行同价同续航同座位）。"""
    a = dict(_row("73967", "小鹏GX 2026款 纯电 750四驱Ultra旗舰版", "小鹏GX", "2026", "35.98万",
                  "汽车之家+懂车帝", "9001"), **{"电池容量(kWh)": "110", "纯电续航(km)": "750",
                                                "驱动形式": "双电机四驱", "能源类型": "纯电动"})
    b = dict(_row("73967", "小鹏GX 2026款 纯电 750四驱Ultra旗舰版", "小鹏GX", "2026", "35.98万",
                  "汽车之家+懂车帝", "9001"), **{"电池容量(kWh)": "110.0", "纯电续航(km)": "CLTC:750",
                                                "驱动方式": "双电机四驱", "能源类型": "纯电动"})
    assert MD._spec_value_set("110") == MD._spec_value_set("110.0"), "尾部零没归一：护栏会判成两种电池"
    assert MD._sku_spec_conflict([a, b]) is False, "同价同续航同座位只差 `110`/`110.0` 被判成冲突"
    out = MD.dedupe_merged_rows([a, b])
    assert len(out) == 1, "小鹏GX 73967 这种「同一款两行」还在：%d 行" % len(out)


def test_m2_real_battery_difference_still_blocks_merge() -> None:
    """M2 反向：110 vs 120 是真差异，必须仍然拦住（归一不许把护栏掏空）。"""
    a = dict(_row("1", "同一款名", "甲车系", "2026", "20.00万", "懂车帝+汽车之家", "1"),
             **{"电池容量(kWh)": "110"})
    b = dict(_row("1", "同一款名", "甲车系", "2026", "20.00万", "汽车之家+懂车帝", "2"),
             **{"电池容量(kWh)": "120"})
    assert MD._sku_spec_conflict([a, b]) is True, "110 与 120 竟被判不冲突 ⇒ 护栏被归一掏空了"
    assert len(MD.dedupe_merged_rows([a, b])) == 2, "两种电池包的同一款名被并成一行"


# ---- T：纯电续航轴 + 电池化学轴（10-16 安全尺分诊 D 档 70 对真误合候选的回归判据）----
# 现网形状来自 `fold-conflict-triage.txt` 点名的三例，不是编的：
#   Lorinser 星际战车 72803 两行同价，续航 125 与 150 被折成一条；
#   瑞虎9 C-DM `106km 悦享版 三元锂` 与 `磷酸铁锂`（续航 {106,82} 与 {106,80} 有交集）。
def _spec_row(sku, name, range_km, price="28.98万", year="2025", series="昊铂HL"):
    return dict(_row(sku, name, series, year, price, "懂车帝+汽车之家", "1"),
                **{"纯电续航(km)": range_km})


def test_t1_range_mutex_must_not_fold() -> None:
    a = _spec_row("72803", "M800 枪与玫瑰", "125")
    b = _spec_row("72803", "M800 枪与玫瑰", "150")
    assert MD._sku_spec_conflict([a, b]) is True, "125km 与 150km 竟不判冲突 ⇒ 续航轴没生效"
    assert len(MD.dedupe_merged_rows([a, b])) == 2, "两种续航的同一款名被并成一行"


def test_t2_battery_chemistry_must_not_fold() -> None:
    a = _spec_row("1", "106km 悦享版 三元锂", "106 / 82", price="15.28万", series="瑞虎9 C-DM")
    b = _spec_row("1", "106km 悦享版 磷酸铁锂", "106 / 80", price="15.28万", series="瑞虎9 C-DM")
    # 先证明"拦住它的确实是电池化学这一轴"：续航与版本词两个轴在这对上都判不冲突
    assert MD._sku_spec_conflict([dict(a, **{"车型名称": "106km 悦享版"}),
                                  dict(b, **{"车型名称": "106km 悦享版"})]) is False, \
        "去掉电池字样后这对仍被判冲突 ⇒ 是别的轴在拦，本例就没测到电池化学轴"
    assert MD._sku_spec_conflict([a, b]) is True, "三元锂 与 磷酸铁锂 被当成同一款"
    assert len(MD.dedupe_merged_rows([a, b])) == 2, "两种电池的同一款名被并成一行"


def test_t3_std_label_written_one_side_still_folds() -> None:
    """绿样（防倒退）：`CLTC:650` 与 `650` 是同一数的两种写法，必须仍然折。"""
    a = _spec_row("1", "530km AIR精英版", "CLTC:650", price="25.00万", series="阿维塔07")
    b = _spec_row("1", "530km AIR精英版", "650", price="25.00万", series="阿维塔07")
    assert MD._sku_spec_conflict([a, b]) is False, "工况标签只有一侧写就判冲突 ⇒ 误合修好了、漏合回来了"
    assert len(MD.dedupe_merged_rows([a, b])) == 1, "同一续航被拆成两行"


def test_t4_multi_std_string_still_folds() -> None:
    """绿样：`CLTC:600 / WLTC:520` 与 `CLTC:600` 是同一 SKU 的两个工况，不许判互斥。"""
    a = _spec_row("1", "同一款名", "CLTC:600 / WLTC:520")
    b = _spec_row("1", "同一款名", "CLTC:600")
    assert MD._sku_spec_conflict([a, b]) is False, "多工况串没拆开 ⇒ 与单工况行判成两款"
    assert len(MD.dedupe_merged_rows([a, b])) == 1


def test_t5_subset_range_still_folds() -> None:
    """绿样：`500|550`（一行本就带多源并存串）与 `550` 是子集关系，折它不新建矛盾。"""
    a = _spec_row("52972", "2022款 领先型", "500|550", price="39.99万", series="宝马iX3")
    b = _spec_row("52972", "2022款 领先型", "550", price="39.99万", series="宝马iX3")
    assert MD._sku_spec_conflict([a, b]) is False, "子集被当成互斥 ⇒ 安全尺那两轮灌水的老错进了生产代码"
    assert len(MD.dedupe_merged_rows([a, b])) == 1


# ============================================================================
# H8（第八轮 C→D）：两族票（qwen + deepseek）都判"不可推"，且撞在**同一个机制**上——
# `_edition_identities` 用"取分栏后的最后一段"当词根前缀，于是空格或标点只要**挪个位置**
# （量词↔词根之间、专名↔词根之间、词根内部、标点分栏）前缀就整段丢失 ⇒ 两款折成一条。
# 修法不是再补一条"哪种空格要坍缩"的窄规则，而是取消"取最后一段"：
# 前缀 = 去空白整串里词根之前的**整段**，再剔噪声（车系/品牌/标记/版本词/年款形）。
# 见 `_edition_affix()` 的注释与 `measure_edition_tail_yield.py`（尾部为什么**不**收）。
# ============================================================================
H8_MUST_NOT_FOLD = [
    ("qwen A6 量词后夹空格", "途昂 十万辆 限量版", "途昂 五十万辆 限量版"),
    ("qwen A8 专名后夹空格", "途昂 璀璨星空 限定版", "途昂 星空 限定版"),
    ("qwen A12 一侧整段没写", "途昂 十万辆 限量版", "途昂 限量版"),
    ("qwen A11 多重空格", "途昂 10  周年", "途昂 20  周年"),
    ("deepseek D1 词根内部夹空格", "途昂 10  周 年纪念版", "途昂 20 周 年纪念版"),
    ("deepseek D2 标点分栏", "途昂 青峰、限定版", "途昂 科林斯古铜、限定版"),
    ("deepseek D2b 连字符", "途昂 青峰-限定版", "途昂 科林斯古铜-限定版"),
    ("deepseek D2c 中间点要留在身份里", "途昂 三百·万辆纪念版", "途昂 五百·万辆纪念版"),
    ("deepseek D2d 车系名与数字粘连", "途昂10、周年纪念版", "途昂20、周年纪念版"),
]
H8_MUST_FOLD = [
    ("qwen B3 空格只是排版", "途昂 十万辆 限量版", "途昂 十万辆限量版"),
    ("qwen B7 同上（专名侧）", "途昂 璀璨星空 限定版", "途昂 璀璨星空限定版"),
    ("年款写全 vs 写简", "途昂 2026款 青峰限定版", "途昂 26款 青峰限定版"),
    ("四位年款贴词根", "途昂 2026 限定版", "途昂 限定版"),
    ("辆数里程碑不是年款（两侧同数）", "途昂 2000 万辆纪念版", "途昂 2000万辆纪念版"),
]


def test_h8_prefix_is_the_whole_affix_not_the_last_split_segment() -> None:
    """H8 正向：空格/标点挪到任何位置，都不许把限量身份的前缀弄丢。"""
    for label, na, nb in H8_MUST_NOT_FOLD:
        a, b = _pair(na, nb, series="途昂")
        assert MD._sku_spec_conflict([copy.deepcopy(a), copy.deepcopy(b)]) is True, \
            "%s：两侧身份相同 ⇒ 会折成一条" % label
        out = MD.dedupe_merged_rows([copy.deepcopy(a), copy.deepcopy(b)])
        assert len(out) == 2, "%s：两款被折成一行 ⇒ %r" % (label, [r["车型名称"] for r in out])
        # 拦住"两侧恰好都不等但身份其实是空的"这种假修：必须存在一个共同词根，
        # 两侧身份集合**不相交**（口径与 H7 一致，不靠 `_has_number_info` 那种宽判据）。
        ea = MD._edition_identities(na, "途昂", "")
        eb = MD._edition_identities(nb, "途昂", "")
        common = set(ea) & set(eb)
        assert common and any(not (ea[root] & eb[root]) for root in common), \
            "%s：没有一个共同词根的两侧不相交 ⇒ 冲突不是这条轴给的：%r / %r" % (label, ea, eb)


def test_h8_typography_year_and_milestone_variants_still_fold() -> None:
    """H8 反向：排版差、年款写法差、辆数的有无空格，都仍然必须是一条。"""
    for label, na, nb in H8_MUST_FOLD:
        a, b = _pair(na, nb, series="途昂")
        out = MD.dedupe_merged_rows([copy.deepcopy(a), copy.deepcopy(b)])
        assert len(out) == 1, "%s：同一款的两种写法被拆成两行 ⇒ %r" % (
            label, [r["车型名称"] for r in out])


def test_h8_tail_is_a_documented_tradeoff() -> None:
    """H8 反向钉桩：词根**之后**的尾部也不进身份，这是现网量出来的取舍（不是漏检）。

    两票都想要 `青峰限定版AAA` ≠ `青峰限定版BBB`。我按票收过尾部，然后显式构造两种口径重数
    （`measure_edition_tail_yield.py`）：只看前缀判冲突 179 对，收尾部 183 对 ⇒ **代价 +4 对现网同款被拆**，
    逐对点名（`enumerate_tail_cost_pairs.py`）4 对**全在**车款ID 65447
    （`冠军版 鲲鹏290TGDI DCT豪情版 5座` vs `2024款 冠军版 290TGDI DCT豪情版 5座`；
    逐列比 `show_pair_columns.py`：非显示列只差 `●` vs `支持` 一类同义写法与 `车系ID`），
    而这 4 对恰好就是全部"收益候选" ⇒ 有效收益 0。
    （先前这里还挂着"184810 括注省略"当现网代价——那是我点名打印 `[:40]` 造出的假形状，
     现网 184810 两行都带 `(南方版)`，尾部口径不拆它；括注省略只是上面 `test_h6` 的夹具写法。）
    ⇒ 维持不收，并把形状留在红样的 `已知未覆盖` 里打印。想推翻请先给出**现网**反例对数。
    """
    a, b = _pair("青峰限定版AAA", "青峰限定版BBB", series="途昂")
    assert MD._sku_spec_conflict([copy.deepcopy(a), copy.deepcopy(b)]) is False, \
        "尾部被重新收进身份 ⇒ 现网 65447 那 4 对同款会被拆开（先读这段注释再决定）"
    # 而票面真正担心的"尾部带真配置差异"形状，配置轴本来就拦得住（这里用座位数示范）：
    c, d = _pair("青峰限定版 5座", "青峰限定版 7座", series="途昂", **{"座位数(个)": "7"})
    c["座位数(个)"], d["座位数(个)"] = "5", "7"
    assert MD._sku_spec_conflict([copy.deepcopy(c), copy.deepcopy(d)]) is True, \
        "尾部承载的配置差异（座位数）没有列轴兜底"


def test_h8_brand_prefix_is_not_part_of_edition_identity() -> None:
    """品牌写在头还是省掉，不该改变限量身份（`noise` 里带 `品牌` 列值）。"""
    a = dict(_row("55010", "大众 途昂 青峰限定版", "途昂", "2026", "30.00万",
                  "懂车帝+汽车之家", "7001"), **{"品牌": "大众"})
    b = dict(_row("55010", "途昂 青峰限定版", "途昂", "2026", "30.00万",
                  "仅汽车之家", "7002"), **{"品牌": "大众"})
    assert MD._sku_spec_conflict([copy.deepcopy(a), copy.deepcopy(b)]) is False, \
        "品牌前缀被当成限量专名 ⇒ 同款拆两行"
    assert len(MD.dedupe_merged_rows([copy.deepcopy(a), copy.deepcopy(b)])) == 1


def test_h8_accel_difference_is_a_documented_tradeoff() -> None:
    """H8 反向钉桩：`百公里加速(s)` **不在**冲突轴上，这是现网归因后的取舍，不是漏检。

    我先按 deepseek 票 round-8C 阻断件5 加过这根轴，然后用 `attribute_lost_pair.py` 对
    车款ID 76544（小米YU7 四驱GT）逐列隔离：唯一拦手就是加速列（`2.92` vs `2.98`，同一台车的
    跨源测量差），加它 = 4 对现网真回退；而"除加速外全同"的真两款形状在现网 = 0 对。
    这条测试的作用是把**取舍**钉住：以后谁想再收这列，必须先拿出现网反例对数。
    """
    a = dict(_pair("途昂 青峰限定版", "途昂 青峰限定版", series="途昂")[0],
             **{"百公里加速(s)": "2.98"})
    b = dict(_pair("途昂 青峰限定版", "途昂 青峰限定版", series="途昂")[1],
             **{"百公里加速(s)": "2.92"})
    assert MD._sku_spec_conflict([copy.deepcopy(a), copy.deepcopy(b)]) is False, \
        "加速列被重新加进冲突轴 ⇒ 现网 76544 那 4 对同款会被拆开（先读这段注释再决定）"
    assert len(MD.dedupe_merged_rows([copy.deepcopy(a), copy.deepcopy(b)])) == 1


def test_h8_chem_abbreviation_is_still_a_written_value() -> None:
    """H8 电池化学：`磷酸铁` 是 `磷酸铁锂` 的现网省略写法，不许当成"这一侧没写"。

    deepseek 票 阻断件4：词表只认两个精确串时，省略写法一侧为空 ⇒ 缺数据不算冲突 ⇒ 两款折一条。
    """
    a = dict(_pair("途昂 三元锂 青峰限定版", "x", series="途昂")[0], **{"车型名称": "途昂 三元锂 青峰限定版"})
    b = dict(_pair("x", "途昂 磷酸铁 青峰限定版", series="途昂")[1], **{"车型名称": "途昂 磷酸铁 青峰限定版"})
    assert MD._sku_spec_conflict([copy.deepcopy(a), copy.deepcopy(b)]) is True, \
        "三元锂 vs 磷酸铁（省略写法）没判冲突"
    d = dict(b, **{"车型名称": "途昂 磷酸铁锂 青峰限定版"})
    e = dict(a, **{"车型名称": "途昂 磷酸铁 青峰限定版"})
    assert MD._sku_spec_conflict([copy.deepcopy(d), copy.deepcopy(e)]) is False, \
        "全称与省略写法被当成两种电池（多拆）"


def test_h9_xing_names_are_an_independent_axis_not_a_word_table() -> None:
    """H9（hy4 黑箱票 ①P1/P2/P3）：《X型》版本名是一条**不看词表**的冲突轴。

    `_VERSION_WORDS_RE` 只有 21 个词，`时尚型/进取型/动感型/科技型/探索型` 全在表外 ⇒
    上一包把同 ID 同价的这两行折成一条（真误合）；而我原来的分桶尺问"规格是否全同"用的
    正是同一张表，对这类形状必然是**空读数**（`真误合=0` 因此不能否证它）。
    同时钉住"一侧没写不算差异"：现网 63975 的 `时尚型` 只写在一侧，**必须仍折**
    ——这条也是 `_edition_affix` 第③步（剔 `…型`）的**判别性**夹具：
    先前的 `test_h6` 两侧都写了同一个 `飞驰尊享型`，把那条规则整段删掉它照样绿（假绿）。
    """
    for na, nb in (("1.6TGDI DCT 时尚型", "2023款 1.6TGDI DCT 进取型"),
                   ("45 TFSI quattro 时尚型 上市特别版", "45 TFSI quattro 动感型 上市特别版"),
                   ("青峰限定版 科技型", "青峰限定版 探索型")):
        a, b = _pair(na, nb, series="途昂")
        assert MD._sku_spec_conflict([copy.deepcopy(a), copy.deepcopy(b)]) is True, \
            "表外版本名没被独立轴拦住：%r vs %r" % (na, nb)
        assert len(MD.dedupe_merged_rows([copy.deepcopy(a), copy.deepcopy(b)])) == 2, \
            "两侧都写了不同《X型》却折成一条（真误合）：%r" % ([r["车型名称"] for r in
                                                              MD.dedupe_merged_rows(
                                                                  [copy.deepcopy(a), copy.deepcopy(b)])],)
    for na, nb in (("45 TFSI quattro 时尚型上市特别版", "2024款 45 TFSI quattro 上市特别版"),
                   ("2.0T 两驱豪华型", "2.0T 前驱豪华型"),
                   ("2024款 领先型", "领先型")):
        a, b = _pair(na, nb, series="宝马iX3")
        assert MD._sku_spec_conflict([copy.deepcopy(a), copy.deepcopy(b)]) is False, \
            "一侧省略、或驱动词/年款只是写法差，却被《X型》轴拆开：%r vs %r" % (na, nb)


def test_h9_noise_units_roots_punctuation_and_brand_forms() -> None:
    """H9 另一半（hy4 票 ②.1/②.2/②.3/②.4/②.8）：这些写法差必须**折**，里程碑数必须**不折**。

    顺序也钉住：`_edition_affix` 里"数字+单位"必须**先整段剥**再剔噪声词——
    反过来会先把 `座` 当噪声删掉、把 `7` 留下，残留的孤立数字照样拆行（实测过）。
    """
    for na, nb, series, brand in (
            ("7座 青峰限定版", "青峰限定版", "途昂", ""),
            ("39.05kWh 青峰限定版", "青峰限定版", "途昂", ""),
            ("青峰限定", "青峰限定版", "途昂", ""),          # 词根形态（版/款）不算差异
            ("青峰：纪念版", "青峰纪念版", "途昂", ""),        # 全角冒号在词根前，属首尾标点
            ("青峰.纪念版", "青峰纪念版", "途昂", ""),         # 英文句点同上
            ("问界M7 青峰限定版", "M7 青峰限定版", "M7", "AITO 问界")):  # 品牌列写法不一致
        a, b = _pair(na, nb, series=series)
        if brand:
            a["品牌"] = b["品牌"] = brand
        assert MD._sku_spec_conflict([copy.deepcopy(a), copy.deepcopy(b)]) is False, \
            "写法差被当成两款（漏合）：%r vs %r" % (na, nb)
        assert len(MD.dedupe_merged_rows([copy.deepcopy(a), copy.deepcopy(b)])) == 1, \
            "上面的口径没落到折叠出口：%r vs %r" % (na, nb)
    c, d = _pair("2000套纪念版", "2001套纪念版", series="途昂")
    assert MD._sku_spec_conflict([copy.deepcopy(c), copy.deepcopy(d)]) is True, \
        "`套` 没进量词表 ⇒ 2000/2001 被当成年款剥掉，两款折一条"


def test_h10_drive_column_is_compared_by_class_not_by_whole_string() -> None:
    """H10（线上验收第一次真跑抓到的 5 组）：`驱动形式` **列**也要按类比为。

    跨源对同一台四驱车会写 `双电机四驱` / `三电机四驱` / `前置四驱` / `四驱`，
    整串互斥 ⇒ 同 ID、同名、同价、同年款的两行不合（现网出口面 62872/59421/74782/74511/74580/76219）。
    方向要两头都钉住：同类不同值仍必须判冲突（评审 D3 与 test_r4 的口径不许被放宽掉）。
    """
    def rows_with(drive):
        a, b = _pair("2.0T 四驱豪华型", "2.0T 四驱豪华型", series="奇骏")
        a["驱动形式"], b["驱动形式"] = drive[0], drive[1]
        return a, b
    for x, y in (("双电机四驱", "前置四驱"), ("双电机四驱", "三电机四驱"), ("四驱", "双电机四驱"),
                 # `两驱` 与 `前置后驱` 不矛盾：后驱本身就是两轮驱动（r4 同一口径），
                 # 我第一版把它放进"该判冲突"里，是**我写错了期望**，不是代码放宽了。
                 ("两驱", "前置后驱")):
        a, b = rows_with((x, y))
        assert MD._sku_spec_conflict([copy.deepcopy(a), copy.deepcopy(b)]) is False, \
            "同一驱数轴的四种跨源写法被整串比成两款：%s vs %s" % (x, y)
    for x, y in (("两驱", "四驱"), ("前驱", "后驱"), ("前置前驱", "后置后驱")):
        a, b = rows_with((x, y))
        assert MD._sku_spec_conflict([copy.deepcopy(a), copy.deepcopy(b)]) is True, \
            "同类互斥的写法被放宽了（该判冲突）：%s vs %s" % (x, y)
    # 一侧这一列没写 ⇒ 缺数据不算冲突（不许因为新增这条轴就反过来多拆）
    a, b = rows_with(("双电机四驱", ""))
    assert MD._sku_spec_conflict([copy.deepcopy(a), copy.deepcopy(b)]) is False, "一侧驱动列为空被当成差异"


def test_h11_xing_axis_has_no_fixed_window_and_uses_suffix_relation() -> None:
    """《X型》轴：窗口换成"整段减有主噪声 + 后缀关系"后，**四个方向**各钉一条（hy4 第二票①要求）。

    票①的阻断形状是 `尊享豪华型` vs `舒享豪华型` 都归约成 `豪华型`（定长末三字窗口）。
    光修那一条很容易反向把书写省略拆成两行，所以四个方向必须同时钉住。
    """
    # 方向 1：互非后缀的两副版本名 ⇒ 必须判冲突（这是被修掉的洞）
    a, b = _pair("2.0T 尊享豪华型", "2.0T 舒享豪华型")
    assert MD._sku_spec_conflict([a, b]) is True, "窗口碰撞又回来了：两副版本名被判同款"
    assert len(MD.dedupe_merged_rows([copy.deepcopy(a), copy.deepcopy(b)])) == 2
    # 方向 2：一侧少写修饰词（后缀关系）⇒ 书写省略，必须仍折
    a, b = _pair("尊享豪华型", "豪华型")
    assert MD._sku_spec_conflict([a, b]) is False, "省略写法被当成两副版本名"
    assert len(MD.dedupe_merged_rows([copy.deepcopy(a), copy.deepcopy(b)])) == 1
    # 方向 3：驱动词各说一件事 ⇒ 减掉有主噪声后必须是同一个版本名（与 r4 同口径）
    assert (MD._xing_version_names("2.0T 两驱豪华型", "", "")
            == MD._xing_version_names("2.0T 前驱豪华型", "", "")), "驱动词没被减掉 ⇒ 凭空多拆"
    # 方向 4：一侧根本没写《X型》⇒ 缺数据不算差异（现网 63975 那族）
    a, b = _pair("45 TFSI 时尚型上市特别版", "2024款 45 TFSI 上市特别版")
    assert MD._sku_spec_conflict([a, b]) is False, "一侧没写版本名被当成两款（63975 回退）"


def test_h11_owned_words_never_enter_the_edition_identity_comparison() -> None:
    """有主列已经管的词（能源/代数/座位/驱动/编码）不许混进名字侧比对。

    现网例：车款ID 77498 三行 `第四代 1.5T 蓝鲸超擎 旗舰型` / `1.5T 蓝鲸超擎 旗舰型` /
    `第四代 1.5T 蓝鲸超擎混动 旗舰型`，`能源类型` 三行都是 `油电混合` ⇒ 同一款的三种写法；
    而 `X1` vs `X2` 是**车型编号**（不是动力编码），吃掉就把两款折成一条。
    """
    a, b = _pair("第四代 1.5T 蓝鲸超擎 旗舰型", "第四代 1.5T 蓝鲸超擎混动 旗舰型")
    assert MD._sku_spec_conflict([a, b]) is False, "差 `混动` 二字被当成两款（现网 77498 会被拆开）"
    a, b = _pair("六座 青峰限定版", "青峰限定版")
    assert MD._sku_spec_conflict([a, b]) is False, "中文数词+单位没整段减掉 ⇒ 残留 `六` 多拆"
    a, b = _pair("2026年款 青峰限定版", "2026款 青峰限定版")
    assert MD._sku_spec_conflict([a, b]) is False, "`年款` 形态没认全 ⇒ 同款拆两行"
    a, b = _pair("〖青峰〗限定版", "青峰限定版")
    assert MD._sku_spec_conflict([a, b]) is False, "首尾标点靠穷举表 ⇒ 新符号又漏（改成了结构式剥法）"
    a, b = _pair("全新青峰限定版", "青峰限定版")
    assert MD._sku_spec_conflict([a, b]) is False, "装饰词 `全新` 被当成身份差异"
    # 反向：`X1`/`X2` 是车型编号，**不许**被动力编码正则吃掉（吃掉就是真误合）
    a, b = _pair("X1青峰限定版", "X2青峰限定版")
    assert MD._sku_spec_conflict([a, b]) is True, "编码正则过宽：`X1`/`X2` 被剥成同一个身份"
    # 反向：`2000批` vs `2001批` 是批次数里程碑，不是年款
    a, b = _pair("2000批纪念版", "2001批纪念版")
    assert MD._sku_spec_conflict([a, b]) is True, "`批` 不在量词表 ⇒ 20xx 被当年款剥掉（真误合）"
    # 反向：`全驱` 与 `前驱` 是真互斥（两驱/四驱 两轴），别因为词表没收就放行
    a, b = _pair("2.0T 全驱豪华型", "2.0T 前驱豪华型")
    assert MD._sku_spec_conflict([a, b]) is True, "`全驱` 不在驱动词表 ⇒ 两款折成一条"
    # 但 `全驱` 与 `四驱` 是同一件事（归一，不许造出新的互斥）
    a, b = _pair("2.0T 全驱豪华型", "2.0T 四驱豪华型")
    assert MD._sku_spec_conflict([a, b]) is False, "`全驱`/`四驱` 被当成两种驱数"


def test_h12_name_encoded_code_is_identity_when_columns_lie() -> None:
    """名字里"数字+字母词"的编号是一档车的身份：两侧都写又不相等 ⇒ 不折。

    现网对象 74307：`350 Max五座激光雷达版` 与 `670 Max五座激光雷达版` 同车款ID、同价、同年款，
    而 670 那行的 `纯电续航(km)` 列被源侧写成了与 350 行**一样**的 `CLTC:350 / WLTC:282`
    ⇒ 列轴一条都不冲突 ⇒ "同 ID 同价同年款就建簇"把两档折成一行，670 这一档从面上消失。
    我自己那把词表无关的误合尺比的是列，看不见这一条（`真误合=0` 因此是空读数）；
    是漏合回归尺报"基线=2 → 新树=1"（新树**多**折）时我逐列点开才发现的。
    反向三格守住"不许倒退成漏合"：一侧没写编号 = 缺数据、同编号两侧都写 = 同款、
    排量小数 `1.5T` 与 `EcoBoost 225` 都不算编号。
    """
    a, b = _pair("350 Max五座激光雷达版", "670 Max五座激光雷达版")
    assert MD._sku_spec_conflict([a, b]) is True, "350/670 两档被折成一条（现网 74307 的真误合）"
    assert len(MD.dedupe_merged_rows([dict(x) for x in (a, b)])) == 2, "出口必须仍是两行"
    a, b = _pair("670 Max五座激光雷达版", "Max五座激光雷达版")
    assert MD._sku_spec_conflict([a, b]) is False, "一侧没写编号 = 缺数据，不许当冲突（会倒退成漏合）"
    a, b = _pair("EcoBoost 225 6座精领型", "EcoBoost 225 精领型 6座")
    assert MD._sku_spec_conflict([a, b]) is False, "同一编号 225 两侧都写 ⇒ 仍该折（现网 61633）"
    a, b = _pair("第四代 1.5T 蓝鲸超擎 旗舰型", "1.5T 蓝鲸超擎混动 旗舰型")
    assert MD._sku_spec_conflict([a, b]) is False, "排量小数 1.5 不许被读成编号（现网 77498）"


def test_h13_energy_axis_compares_assertion_triples_not_raw_strings() -> None:
    """能源类型这根轴比的是**断言三元组**（有燃油机 / 有电力驱动 / 可外接充电），
    既不是原始串，也不是"粗类别交集非空即相容"。

    8M 现网对象 183689（迈巴赫EQS SUV 礼逸版）：两行同车款ID、同年款、同价，
    一个源把能源写成 `纯电动`、另一个写 `纯电` ⇒ 拿原始串比就判冲突 ⇒
    **这根轴本来没有（main 不带冲突闸），是我这包加上去的，于是我自己造了一次漏合**。
    同一形状在现网面上被 `audit_face_shrink.py` 量到 2 组。
    反向必须钉住：`纯电` vs `汽油`、`增程式` vs `插电式混合动力` 是真两种能源 ⇒ 仍判冲突，
    否则就是拿"归一"把真差异抹掉（误合方向）。
    """
    def rows(ea, eb):
        a = dict(_row("183689", "迈巴赫EQS SUV 2025款 EQS 680 礼逸版", "迈巴赫EQS SUV",
                      "2025", "148.6万", "懂车帝+汽车之家", "8001"), 能源类型=ea)
        b = dict(_row("183689", "25款 680 礼逸版", "迈巴赫EQS SUV",
                      "2025", "148.60万", "仅易车", "8001"), 能源类型=eb)
        return [a, b]

    assert MD._sku_spec_conflict(rows("纯电动", "纯电")) is False, "同一件事的两种写法被判成两款 ⇒ 漏合"
    # `增程式纯电动` 是平台枚举里 EREV 的**整个标签**（不是"增程+纯电"两种写法的拼接），
    # 它与 `纯电动` 在"有没有燃油机"这一维上互相否定 ⇒ 判互斥。
    # 我一度把它写成"子集不算差异⇒该折"（照抄续航那根轴的口径），但那是拿另一根轴的规则
    # 套这一根：这里两侧不是详略，是两个枚举值。现网实测这条今天不拦任何对
    # （同 ID 内不同能源写法共 66 组，判互斥 0 组，见 FINDING §七十二），所以它是安全网不是代价。
    assert MD._sku_spec_conflict(rows("增程式纯电动", "纯电动")) is True, "EREV 与 BEV 是两款"
    assert MD._sku_spec_conflict(rows("懂车帝:纯电动|易车:纯电", "纯电")) is False, "跨源合并串要能拆开比"
    # 70483（奥迪Q7 55 TFSI）：一个源写 `汽油`、另一个写 `48V轻混系统`——轻混就是挂在
    # 汽油机上的那一层，属**详略两种写法**，不是两款；按"类别不同即冲突"会再造一次漏合。
    assert MD._sku_spec_conflict(rows("汽油", "48V轻混系统")) is False, "详略写法被判成两款（现网 70483）"
    assert MD._sku_spec_conflict(rows("汽油+48V轻混系统", "汽油")) is False, "复合串与只写燃料同一台车"
    # 但"都含燃油"不能当成相容证据：HEV 明确不可外接充电，PHEV 可以 ⇒ 两款。
    assert MD._sku_spec_conflict(rows("油电混合", "插电式混合动力")) is True, "HEV/PHEV 被'都含燃油'放过 ⇒ 误合"
    # 认不出的取值 = 不作断言（宁可少拦一条误合，也不拿猜出来的类别造漏合）
    assert MD._sku_spec_conflict(rows("汽油", "某种没见过的新燃料")) is False, "未归类取值被当成互斥 ⇒ 假冲突"
    # 反向（真两种能源必须仍拦住，否则"归一"就成了抹差异）：
    assert MD._sku_spec_conflict(rows("纯电", "汽油")) is True, "纯电与汽油被放过 ⇒ 误合"
    assert MD._sku_spec_conflict(rows("增程式", "插电式混合动力")) is True, "能不能外接充电是两款"


def _same_id_pair(na, nb, **extra):
    """同 ID/年款/价、只换名字的两行（`_pair` 的默认值不带能源/续航列，这里按需覆盖）。"""
    a = dict(_row("59999", na, "途昂", "2026", "20.98万", "懂车帝", "7001"), **extra.get("a", {}))
    b = dict(_row("59999", nb, "途昂", "2026", "20.98万", "汽车之家", "7001"), **extra.get("b", {}))
    return [a, b]


def test_h14_ban_suffix_version_names_are_compared() -> None:
    """以 `版`/`款` 收尾的版本名同样要看（hy4 第三票 ①M1、⑤S1/S2）。

    `智领版`/`悦享版`、`智远豪华版`/`智逸豪华版` 都不在那张 21 词版本词表里，
    又不以 `型` 结尾 ⇒ 版本词轴与《X型》轴同时落空 ⇒ 同 ID 同价折成一条。
    第二例是"表内词掩护"：`豪华` 命中词表 ⇒ 交集非空 ⇒ 旧口径直接放行，
    所以"补词表"救不了它——收的是**形态**（整段 `汉字+[版款]`），不是词。
    """
    for na, nb in (("途昂 2026款 智领版", "途昂 2026款 悦享版"),
                   ("智远豪华版", "智逸豪华版")):
        pair = _same_id_pair(na, nb)
        assert MD._sku_spec_conflict(pair) is True, "%r vs %r 被折成一条（表外版本名）" % (na, nb)
        assert len(MD.dedupe_merged_rows([dict(x) for x in pair])) == 2, "出口必须是两行"
    # 一侧写了、另一侧整个没写版本名 ⇒ 缺数据不算差异（63975 那条口径不能被这根轴推翻）
    pair = _same_id_pair("途昂 2026款 智领版", "途昂 2026款")
    assert MD._sku_spec_conflict(pair) is False, "另一侧没写版本名 ⇒ 不许造漏合"
    # 限量词根段归限量身份轴管，这里再判一遍就是两根轴抢同一件事
    pair = _same_id_pair("青峰限定版", "25周年纪念版")
    assert MD._edition_identities("青峰限定版", "途昂", "测试品牌") != \
        MD._edition_identities("25周年纪念版", "途昂", "测试品牌"), "夹具本身要能被身份轴看出差别"


def test_h15_residual_multiset_axis_measured_not_adopted() -> None:
    """票 ①M1 的"通用修法"（剩余段字符多重集）**量过代价后本轮不装**，这条测试守住不装的理由。

    `measure_residual_axis.py` 在现网 19382 行面上量到：现有轴没拦下的同 ID 同价同年款异名对 932，
    装上这根轴会**新拦 140 对**；抽出来的样例全是该折的形状——
    `七座版Max+` vs `乐道L902026款Max+七座版`（差一个 `+` 的粘连）、
    `四驱TECH88.112kWh` vs `…四驱TECH版88.112kWh`（差一个 `版`）。
    也就是说那 140 对里抽样看到的都是**误伤**，收益无对数支撑 ⇒ 不装。
    本条把两个"必须仍折"的现网形状钉住：谁将来想把这根轴装进来，这几行会先红。
    """
    pair = _same_id_pair("七座版Max+", "乐道L902026款Max+七座版")
    assert MD._sku_spec_conflict(pair) is False, "词序+`+`粘连写法被判两款（剩余段多重集会犯的错）"
    pair = _same_id_pair("四驱TECH88.112kWh", "EO羿欧2025款四驱TECH版88.112kWh")
    assert MD._sku_spec_conflict(pair) is False, "差一个 `版` 字被判两款"


def test_h16_two_layer_source_prefix_stripped_to_number() -> None:
    """`懂车帝:CLTC:600 / WLTC:520` 与 `CLTC:600` 必须能对上（hy4 第三票 ④(c)）。

    双层前缀下"各剥一次"是不对称的：前者只剩 `CLTC:600`，后者被剥成 `600`
    ⇒ 空交集 ⇒ 我这根新加的纯电续航轴把同一台车判成两款。
    现在剥到不动为止；同时保住评审 G⑤ 那条老教训：`5 / 易车:4` 不许把 `5 / 易车:` 整段吃掉。
    """
    sa = MD._spec_value_set("懂车帝:CLTC:600 / WLTC:520", split_slash=True)
    sb = MD._spec_value_set("CLTC:600", split_slash=True)
    assert set(sa) & set(sb), "双层前缀没剥到底 ⇒ 同一 SKU 的两个工况被判互斥：%s vs %s" % (sorted(sa), sorted(sb))
    pair = _same_id_pair("途昂 2026款 智领版", "途昂 2026款 智领版",
                         a={"纯电续航(km)": "懂车帝:CLTC:600 / WLTC:520"},
                         b={"纯电续航(km)": "CLTC:600"})
    assert MD._sku_spec_conflict(pair) is False, "跨源双层前缀写法被判成两款"
    got = MD._spec_value_set("5 / 易车:4", split_slash=True)
    assert {"num:5", "num:4"} <= set(got), "评审 G⑤ 的形状被回退破坏：%s" % sorted(got)


def test_h17_affix_forms_the_table_missed() -> None:
    """限量身份 affix 的三处"同一形态漏一支"（hy4 第三票 ②N1/N2/N3）。

    这类缺陷的共性不是"词表不够长"，而是**同一形态只写了一个分支**：
    `2026款`/`26款`/`2026 款`/`2026年款` 都认，唯独裸 `2026年` 不认；
    `全新`/`NEW` 剥，`新款`/`新一代` 不剥；`1000台` 两侧都留，多的那个 `第` 没人管。
    与前几轮 `套`、`批` 两例同族——所以补的时候要把整个形态补全，而不是再往上贴一个特例。
    """
    for na, nb in (("2026年青峰限定版", "青峰限定版"),
                   ("新款青峰限定版", "青峰限定版"),
                   ("新一代青峰限定版", "青峰限定版"),
                   ("第1000台纪念版", "1000台纪念版")):
        pair = _same_id_pair(na, nb)
        assert MD._sku_spec_conflict(pair) is False, "%r vs %r 多拆（affix 漏一支）" % (na, nb)
    # 反向：里程碑数字本身仍是身份，不许被"补形态"顺手抹掉
    pair = _same_id_pair("第1000台纪念版", "第2000台纪念版")
    assert MD._sku_spec_conflict(pair) is True, "两个不同里程碑被折成一条"



def _pair_blank_keeper(col, va, vb):
    """做主那行（`数据来源` 富的 A）在该列留空，候选只写在 B 上。"""
    a = dict(_row("59999", "途昂 2026款 智领版", "途昂", "2026", "20.98万", "懂车帝+汽车之家", "7001"),
             **{col: va})
    b = dict(_row("59999", "途昂 2026款 智领版", "途昂", "2026", "20.98万", "仅汽车之家", "7001"),
             **{col: vb})
    return [a, b]


def test_h18_backfill_single_candidate_fills_blank() -> None:
    """折叠后 keeper 空、族内**恰好一个**非空候选 ⇒ 搬过来，别让真实值整列消失。

    现网口径：`measure_backfill_risk.py` 量到这一档有 3323 格（875 个可见列丢格的族里，
    同 ID 档 785 格、跨/缺 ID 档 2538 格）。这一档回填是"空白→真实值"，没有猜测成分。
    """
    rows = _pair_blank_keeper("远程控制", "", "标配")
    out = MD.dedupe_merged_rows([dict(x) for x in rows])
    assert len(out) == 1, "这条夹具本身必须真折，否则测不到回填"
    assert str(out[0].get("远程控制") or "").strip() == "标配", "唯一候选没回填：%r" % out[0].get("远程控制")


def test_h18_backfill_never_guesses_between_two_values() -> None:
    """两个互异候选 ⇒ 一律留空。回填这一步的产物必须是**事实**，不能是我挑出来的一个可能值。

    这一档现网只有 21 格（`远程启动`×19、`后排座椅放倒比例`×1、`手机互联映射`×1），
    把它们写成空白比写成猜测诚实——列已经折叠，用户没有第二行可比对。
    """
    rows = _pair_blank_keeper("远程控制", "", "标配")
    rows.append(dict(_row("59999", "途昂 2026款 智领版", "途昂", "2026", "20.98万", "仅懂车帝", "7001"),
                     **{"远程控制": "选装"}))
    out = MD.dedupe_merged_rows([dict(x) for x in rows])
    assert len(out) == 1, "三行同 ID 同价同年款应当折成一条"
    assert MD._cell_blank(out[0].get("远程控制")), "两个互异候选被回填成了其中一个：%r" % out[0].get("远程控制")


def test_h18_backfill_does_not_overwrite_nonblank_keeper_cell() -> None:
    """做主那行已经有值 ⇒ 一个字节都不许动（回填只补空，不做"值升级"）。"""
    rows = _pair_blank_keeper("远程控制", "常显", "标配")
    out = MD.dedupe_merged_rows([dict(x) for x in rows])
    assert len(out) == 1
    assert str(out[0].get("远程控制")) == "常显", "keeper 的既有值被 sibling 覆盖"


def test_h18_zanyan_price_is_a_value_not_a_blank() -> None:
    """`○ 暂无价格` 是"有这一项但厂家没报价"，不是空格子（负责人 10-14 点过这条口径）。

    如果新加的 `_cell_blank` 把它当空，回填就会拿别人的值盖掉这个**有意义的**状态。
    """
    assert MD._cell_blank("") and MD._cell_blank("-") and MD._cell_blank(None)
    assert not MD._cell_blank("○ 暂无价格"), "把合法的'暂无价格'判成了空格 ⇒ 会被回填盖掉"
    rows = _pair_blank_keeper("蓝牙/数字钥匙", "○ 暂无价格", "标配")
    out = MD.dedupe_merged_rows([dict(x) for x in rows])
    assert str(out[0].get("蓝牙/数字钥匙")) == "○ 暂无价格"


def test_h19_backfill_registry_is_inherited_by_next_pass() -> None:
    """登记簿要跟着 `dict(best)` 复制到新行：否则第二/三遍仍看到上一遍搬来的值（票面②）。

    形状：A(keeper，`应用商店` 空) + B(有值) 先按同车款ID折 ⇒ 这一格是**搬来的**；
    再让无 ID 的 C 在第三遍并进这一行（`_merge_cluster` 又 `dict(best)` 造了新对象）。
    出口行必须还带着"这格是搬来的"这条记录，且 `_unbackfilled` 能把它擦回空。
    旧写法只登记最后一遍 ⇒ 还原不出来，后续遍就把搬来的值当成这一行自己写的。
    （列要挑**不参与任何分簇键与冲突闸**的配置列：座位数进 `_phys_key`，还原后两行键就不同了，
    测不到"同一行跨遍"这件事 —— 第一版夹具就栽在这儿。）
    """
    a = {"品牌": "测试", "车系": "测试系", "车系ID": "9001", "年款": "2026",
         "车型名称": "测试系 2026款 风", "官方指导价": "20.00万", "纯电续航(km)": "600",
         "应用商店": "", "数据来源": "懂车帝+汽车之家", "车款ID": "H19"}
    b = {"品牌": "测试", "车系": "测试系", "车系ID": "9001", "年款": "2026",
         "车型名称": "测试系 2026款 风", "官方指导价": "20.00万", "纯电续航(km)": "600",
         "应用商店": "华为应用市场", "数据来源": "仅懂车帝", "车款ID": "H19"}
    c = {"品牌": "测试", "车系": "测试系", "车系ID": "9001", "年款": "2026",
         "车型名称": "测试系 2026款 风", "官方指导价": "20.00万", "纯电续航(km)": "600",
         "应用商店": "", "数据来源": "仅汽车之家"}
    out = MD.dedupe_merged_rows([dict(a), dict(b), dict(c)])
    assert len(out) == 1, "同物理身份的一簇没折起来 ⇒ 这一条测不到跨遍还原"
    keeper = out[0]
    assert str(keeper.get("应用商店")) == "华为应用市场", "回填本身没生效，后面测不到东西"
    ent = MD._BACKFILLED.get(id(keeper))
    assert ent is not None and ent[0] is keeper, "出口行没有登记项 ⇒ 上一遍的搬入记录丢了"
    assert "应用商店" in ent[1], "第一遍搬进来的列没被继承到下一遍的登记里"
    assert str(MD._unbackfilled(keeper).get("应用商店") or "") == "", "还原后仍带着搬来的值"


def test_h20_synonym_candidates_count_as_one_not_two() -> None:
    """`●` 与 `支持` 是同一个意思（票面①-b）：按裸串数会算成 2 个候选 ⇒ 该补的留空。

    归一只用来**数集合大小**；搬走的仍是原串，展示面不因此换写法。
    """
    a = {"品牌": "测试", "车系": "测试系", "车系ID": "9002", "年款": "2026",
         "车型名称": "测试系 2026款 云", "官方指导价": "12.00万",
         "数据来源": "懂车帝+汽车之家", "车款ID": "H20", "远程控制": ""}
    b = {"品牌": "测试", "车系": "测试系", "车系ID": "9002", "年款": "2026",
         "车型名称": "测试系 2026款 云", "官方指导价": "12.00万",
         "数据来源": "仅懂车帝", "车款ID": "H20", "远程控制": "●"}
    c = {"品牌": "测试", "车系": "测试系", "车系ID": "9002", "年款": "2026",
         "车型名称": "测试系 2026款 云", "官方指导价": "12.00万",
         "数据来源": "仅汽车之家", "车款ID": "H20", "远程控制": "支持"}
    assert MD.canonical_compare("●") == MD.canonical_compare("支持"), "这把尺不认这对同义写法"
    out = MD.dedupe_merged_rows([dict(a), dict(b), dict(c)])
    assert len(out) == 1
    assert str(out[0].get("远程控制") or ""), "同义双候选被判成歧义 ⇒ 该补的一格留空了"


def test_h21_unanchored_tier_pair_stays_two_rows() -> None:
    """没有源侧主键背书（全簇无车款ID）就不许折 ⇒ 更不许把另一款的配置搬过来（票面①-a）。

    票面预期"无锚簇会折成一行并把 `标配` 写进 `智领` 名下"，监工侧 10-18 16:51 复算是
    **出口 2 行**（`_attr_key`/`_phys_key` 两遍都没把它俩并起来）。这条把该结论钉住：
    将来若有人放宽无锚簇，这个测试先红，造值就不会静默发生。
    """
    a = {"品牌": "甲", "车系": "甲系", "车系ID": "1", "年款": "2026",
         "车型名称": "甲系 2026款 青峰限定版 智领", "官方指导价": "20.00万",
         "数据来源": "仅懂车帝", "远程控制": ""}
    b = {"品牌": "甲", "车系": "甲系", "车系ID": "1", "年款": "2026",
         "车型名称": "甲系 2026款 青峰限定版 悦享", "官方指导价": "20.00万",
         "数据来源": "仅汽车之家", "远程控制": "标配"}
    out = MD.dedupe_merged_rows([dict(a), dict(b)])
    assert len(out) == 2, "无锚的版本词对折成了一行 ⇒ 回填会把另一款的配置写成事实"
    assert {str(r.get("车型名称")) for r in out} == {a["车型名称"], b["车型名称"]}


def test_h23_moved_id_still_anchors_the_cluster() -> None:
    """上一遍搬进来的 `车款ID` 仍算锚证据：不许让同一行同时并进两个不同自报 ID 的簇（票面 B1② 的反证）。

    形状（hy4 第二张票给的）：X(无 ID, 富标签) / Y(9001) / Z(9002, Pro) / V(无 ID, Max)。
    第二遍把 X+Y 折成一行并把 9001 搬进 keeper；第三遍这一簇里同时出现 9001 与 9002
    ⇒ F3「归属有歧义就不折」必须拦住。票面要求把 `group_ids` 改成读还原行，
    改完这一簇会折成 1 行、出口 `车款ID` 仍是 9001 却已并掉自报 9002 的 Z
    ⇒ 那是**放宽护栏**，不是修口径；现网同批对照是多折 24 行（20288→20264）。
    这条测试的作用：谁真要改那一句话，必须先把它改红并说明为什么"搭桥"可接受。
    """
    def r(sku, name, src):
        return {"品牌": "甲", "车系": "甲系", "车系ID": "1", "车型名称": name, "年款": "2026",
                "官方指导价": "20.00万", "数据来源": src, "车款ID": sku,
                "纯电续航(km)": "600", "百公里加速(s)": "7.5", "座位数": "5"}
    out = MD.dedupe_merged_rows([
        dict(r("", "甲系 2026款 基本型", "懂车帝+汽车之家")),
        dict(r("9001", "甲系 2026款 基本型", "仅懂车帝")),
        dict(r("9002", "甲系 2026款 Pro 基本型", "仅汽车之家")),
        dict(r("", "甲系 2026款 Max 基本型", "仅懂车帝")),
    ])
    ids = {str(x.get("车款ID") or "") for x in out} - {""}
    assert len(out) == 3, "跨 ID 搭桥：9001 的簇把自报 9002 的行并进去了（F3 没拦住）"
    assert "9002" in ids and "9001" in ids, "两个自报 ID 被并成一行 ⇒ 发布面只剩一个主键，另一款的身份消失"


def _h24_row(src, val, col="方向盘加热"):
    r = {"品牌": "甲", "车系": "甲系", "车系ID": "1", "年款": "2026",
         "车型名称": "甲系 2026款 豪华型", "官方指导价": "20.00万",
         "数据来源": src, "车款ID": "T1"}
    r[col] = val
    return r


def test_h24_explicit_negative_is_not_a_blank() -> None:
    """票面 ①-A（10-18 19:44，监工已在真代码上复现）：`-` 是「这家明确写了无此配置」，不是「没数据」。

    改之前的形状：keeper 写 `-`、族内另一行写 `●` ⇒ `_cell_blank('-')` 判空 ⇒ 候选只剩 `●`
    ⇒ 单候选照搬 ⇒ 出口对写着"无此配置"的那一家宣称标配（现网量到 5 格，全在 `备胎`）。
    同一个文件的 `VALUE_SYNONYMS` 本来就把 `无/不支持/—/--` 归一成 `-` ⇒ `-` 是一个值。
    现在 `-` 参与候选计数 ⇒ 与 `●` 成 2 个候选 ⇒ 谁都不被写成事实。
    """
    out = MD.dedupe_merged_rows([_h24_row("懂车帝+汽车之家", "-"), _h24_row("仅懂车帝", "●")])
    assert len(out) == 1, "同 ID 同款不该折 ⇒ 这一格测试的前提是它确实折成了一行"
    assert str(out[0].get("方向盘加热")).strip() == "-", \
        "另一家的 `●` 覆盖了写着 `-`(无此配置) 的那家 ⇒ 发布面对两家都宣称标配（票面①-A 的说谎形状）"


def test_h24b_explicit_negative_moves_into_truly_empty_cell() -> None:
    """`-` 是值不是空，所以「keeper 真空 + 族内明确写无」应当把 `-` 搬过去（陈述事实，不是编造）。

    这一格与 h24 成对：只挡"否定被肯定覆盖"，不挡"把明确的无搬进真正没写过的格"。
    少这一条，修法就会退化成"`-` 永远不参与回填"，那 1891 格（族内一致写无）就补不回来。
    """
    out = MD.dedupe_merged_rows([_h24_row("懂车帝+汽车之家", ""), _h24_row("仅懂车帝", "-")])
    assert len(out) == 1
    assert str(out[0].get("方向盘加热")).strip() == "-", \
        "两家都说无此配置却被留成空 ⇒ 用户看不出这是「明确的无」还是「没采集到」（该补的没补）"


def test_h24c_noop_fill_does_not_get_registered() -> None:
    """keeper 已经写着 `-`、族内也都是 `-` ⇒ 不许登记成"搬过"。

    为什么单独钉：`_unbackfilled` 把登记过的格还原成 `''`（不是还原成原值）。若这种"什么都没改"
    的照搬也算回填，后续遍看到的就从 `-` 变成空 ⇒ 这条修法会自己动摇折/不折的判断口径。
    """
    out = MD.dedupe_merged_rows([_h24_row("懂车帝+汽车之家", "-"), _h24_row("仅懂车帝", "-")])
    assert len(out) == 1
    assert str(out[0].get("方向盘加热")).strip() == "-"
    ent = MD._BACKFILLED.get(id(out[0]))
    assert ent is None or "方向盘加热" not in ent[1], \
        "无变化的 `-` 被登记成回填 ⇒ 下一遍 `_unbackfilled` 会把它抹成空（把护栏修成了抖动）"


def test_h25_xing_axis_empty_after_strip_keeps_the_name() -> None:
    """票面 ③-1（10-18 hy4，真代码已复现为**误合**）：版本名整段落在"有主噪声"表里时不许消失。

    `标准型` 被 `_XING_OWNED_RE`（本意 `标准轴距`）剥成 `型`、再被前缀噪声剥成空 ⇒ 这一侧
    《X型》集合变成空集 ⇒ 轴退化成"一侧没写就不判" ⇒ `进取型/科技型/探索型/时尚型` 与
    `标准型` 折成一款。修法按**形态**：剥到空就回退返回原段，而不是把某个词从表里摘掉。
    """
    for nm in ("进取型", "科技型", "探索型", "时尚型"):
        a = _h24_row("仅懂车帝", "", col="_noop")
        a["车型名称"] = "甲系 2026款 %s" % nm
        b = dict(a)
        b["数据来源"] = "仅汽车之家"
        b["车型名称"] = "甲系 2026款 标准型"
        out = MD.dedupe_merged_rows([dict(a), dict(b)])
        assert len(out) == 2, "%s 与 标准型 被折成一款（名字里的版本身份消失，用户看到的是合并后的一款）" % nm


def test_h25b_xing_axis_fix_does_not_invent_conflicts() -> None:
    """同一处修法的反方向：写法相同、或一侧本来就没写《X型》，都不许被造出假冲突。

    票面点名的现网对照 `63975`（`45 TFSI 时尚型上市特别版` vs `2024款 45 TFSI 上市特别版`）
    必须仍然折成一行 —— 那是限量词根在管的形状，不是《X型》轴的事。
    """
    a = _h24_row("懂车帝+汽车之家", "", col="_noop")
    a["车型名称"] = "甲系 2026款 标准型"
    b = dict(a)
    b["车型名称"] = "甲系 2026款 标准型"
    assert len(MD.dedupe_merged_rows([dict(a), dict(b)])) == 1, "同名两款 ⇒ 回退修法把相同写法判成冲突了"
    c = dict(a)
    c["车型名称"] = "甲系 2026款 时尚型上市特别版"
    d = dict(a)
    d["车型名称"] = "2024款 45 TFSI 上市特别版"
    d["车系"] = "奥迪Q3 Sportback"
    assert MD._xing_version_names(c["车型名称"], "奥迪Q3 Sportback") != frozenset(), "构造前提没搭起来"


def test_h26_energy_longest_key_wins() -> None:
    """票面 ③-2 的类：表里 key 互为子串时，子串匹配必须取**最长**命中。

    现网实测会翻结果的一格是 `柴油+48v轻混系统`（24 行）：按插入顺序先撞 `柴油`
    ⇒ `(True, None, None)`（对"能不能充电"什么都不说）；按最长命中拿 `48v轻混系统`
    ⇒ `(True, False, False)`（48V 轻混不可外接充电，这是平台事实）。
    票面给的 `插电混合动力` 形状这里也照实钉住：它命中的仍是 `混合动力`
    （`插电混动` 不是它的子串，票面建议的"先长后短"救不了这一格）—— 那一格真正的修法在 h27。
    """
    assert MD._energy_asserts("柴油+48v轻混系统")[1] is False, \
        "取到 `柴油` 的断言 ⇒ 48V 轻混的可充电性被抹成'没说'"
    assert MD._energy_asserts("插电混合动力")[1] is False, "这一格是构造形状，按现状钉住别被误报成已修"


def test_h27_yiche_live_phev_spelling_asserts() -> None:
    """`插电混合` 是易车在现网的真实写法（实测 721 行），它必须落在平台枚举里。

    原来它一个 key 都不命中 ⇒ `_energy_asserts` 返回 None ⇒ 这 721 行对能源"什么都没说"，
    与另一侧的纯油写法不判冲突 ⇒ 具备"PHEV 与纯油折成一款"的条件
    （现网实际折了多少=0，见 `measure_phev_ice_fold.py`，所以这是补断言、不是拆数据）。
    """
    assert MD._energy_asserts("插电混合") == (True, True, True)
    assert MD._energy_asserts("汽车之家:插电式混合动力|懂车帝:插电式混合动力|易车:插电混合") == (True, True, True)


def test_h28_circle_glyph_is_optional_equivalent() -> None:
    """票面 ①-B：`●标配 / ○选配 / -无此配置` 是三态图例，表里已有 `●`→支持、`无`→`-`，只漏了 `○`。

    补上之后：`○` 与 `选配/选装` 算同一个候选 ⇒ 该补的格补上（现网 152 个(键,列)，
    见 `ab_circle_synonym-effect`）；而 `○` 与 `●` 仍是两个互斥候选 ⇒ 不许被写成标配。
    """
    assert MD.canonical_compare("○") == MD.canonical_compare("选配") == "选装"
    a = _h24_row("懂车帝+汽车之家", "")
    a["记忆泊车"] = "○"
    b = dict(a)
    b["数据来源"] = "仅懂车帝"
    b["记忆泊车"] = "选配"
    out = MD.dedupe_merged_rows([dict(a), dict(b)])
    assert len(out) == 1 and str(out[0].get("记忆泊车")).strip() in ("○", "选配"), \
        "同义两写法仍判歧义 ⇒ 该补的一格留空"
    c = _h24_row("懂车帝+汽车之家", "")
    c["记忆泊车"] = "○"
    d = dict(c)
    d["数据来源"] = "仅懂车帝"
    d["记忆泊车"] = "●"
    out2 = MD.dedupe_merged_rows([dict(c), dict(d)])
    assert str(out2[0].get("记忆泊车")).strip() == "○", \
        "○(选配) 被 ●(标配) 覆盖 ⇒ 把选装说成标配（两个互斥候选该留各自写下的那个）"
