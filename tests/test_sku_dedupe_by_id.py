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
  D. 无 车款ID 的行保持原行为（键里带车系）；
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
