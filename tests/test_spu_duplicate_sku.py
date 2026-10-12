"""SPU 内重复 SKU 的验收判据（取自 2026-10-11 线上 filtered 分片的真实行）。

三类缺陷：
  D1 同一 SKU 的两源指导价写法差异被拼成 `130.0万|130.00万` 后当作不同价格，
     使 dedupe_merged_rows 的分组键分叉，SPU 内留下重复行。
  D2 数据来源标签不规范化：`懂车帝+汽车之家` 与 `汽车之家+懂车帝`、`(车系级)` 后缀
     并存，同一条标签内甚至重复原子，导致覆盖与「双源核验」计数随写法漂移。
  D3 线上存在分组键完全相同却仍并存的行，说明去重在该发布路径未生效或被绕过。

这些用例当前为红。修复必须让本文件全绿且不得削弱既有校验。
"""

from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _md():
    spec = importlib.util.spec_from_file_location("merge_data", ROOT / "scripts" / "merge_data.py")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit:  # pragma: no cover - module-level CLI guard
        pass
    return module


MD = _md()


def _yiche_series(name, year, price, source, *, body="SUV", seats=5, battery=None):
    row = {
        "数据来源": source,
        "品牌": "测试品牌",
        "车系": name,
        "车系ID": "1",
        "车型名称": f"{name} {year}款 鼎世版",
        "年款": year,
        "官方指导价": price,
        "车身结构": body,
        "座位数": str(seats),
    }
    if battery:
        row["电池容量(kWh)"] = battery
    return row


# --- D1：同一 SKU 因两源价格写法不同而分裂 ---------------------------------

def test_price_merge_string_does_not_split_one_sku():
    """仰望U8L 线上真实形态：一行 130.00万、一行 130.0万|130.00万。"""
    a = _yiche_series("仰望U8L", "2026", "130.00万", "汽车之家+懂车帝、汽车之家+懂车帝(车系级)、懂车帝+汽车之家")
    b = _yiche_series("仰望U8L", "2026", "130.0万|130.00万", "汽车之家+懂车帝(车系级)、仅懂车帝")
    out = MD.dedupe_merged_rows([a, b])
    assert len(out) == 1, f"同一 SKU 被价格写法拆成 {len(out)} 行"


def test_equivalent_price_spellings_share_one_group_key():
    assert MD._price_norm("130.0万|130.00万") == MD._price_norm("130.00万"), (
        "合并串价格必须归一到同一标量，否则去重键分叉"
    )


# --- D2：来源标签规范化 -----------------------------------------------------

def test_source_label_atoms_are_sorted_and_deduped():
    row = MD._dedupe_source_labels({"数据来源": "汽车之家+懂车帝、懂车帝+汽车之家"})
    assert row["数据来源"] == "汽车之家+懂车帝", row["数据来源"]


def test_same_source_set_yields_one_canonical_label():
    variants = [
        "懂车帝+汽车之家",
        "汽车之家+懂车帝",
        "汽车之家+懂车帝(车系级)",
        "仅汽车之家、仅懂车帝",
    ]
    canonical = {MD._dedupe_source_labels({"数据来源": v})["数据来源"] for v in variants}
    assert len(canonical) == 1, f"同一来源集仍有 {len(canonical)} 种写法: {canonical}"


def test_source_coverage_counts_ignore_label_spelling():
    """覆盖率计数按原子来源集合统计，不受标签写法顺序/后缀影响。"""
    rows = [{"数据来源": "懂车帝+汽车之家"}, {"数据来源": "汽车之家+懂车帝(车系级)"}]
    report = MD.build_source_coverage_report(rows, rows)
    assert report["懂车帝"]["rows"] == 2
    assert report["汽车之家"]["rows"] == 2


# --- D3：键相同必须折叠（线上真实形态） ------------------------------------

def test_identical_group_keys_collapse_even_across_source_labels():
    """宋L EV 线上并存两行：指导价/core/tier/seat 全同，仅来源标签不同。"""
    base = {
        "品牌": "比亚迪",
        "车系": "宋L EV",
        "车系ID": "7001",
        "车型名称": "宋L EV 2025款 智驾版 602km 激光雷达四驱型",
        "年款": "2025",
        "官方指导价": "24.98万",
        "座位数": "5",
        "车身结构": "SUV",
    }
    a = dict(base, 数据来源="懂车帝+汽车之家、汽车之家+懂车帝、汽车之家+懂车帝(车系级)")
    b = dict(base, 数据来源="仅汽车之家")
    out = MD.dedupe_merged_rows([a, b])
    assert len(out) == 1, f"同 SPU 同 SKU 仍并存 {len(out)} 行"


def test_no_duplicate_sku_in_real_like_spu_sample():
    """整个 SPU 样本内不得出现 (车系,年款,规范车型名) 相同的两行。"""
    rows = [
        _yiche_series("仰望U8L", "2026", "130.00万", "汽车之家+懂车帝"),
        _yiche_series("仰望U8L", "2026", "130.0万|130.00万", "仅懂车帝"),
        _yiche_series("仰望U8L", "2025", "128.00万", "汽车之家+懂车帝"),
        _yiche_series("阿维塔07", "2026", "24.99万", "懂车帝+易车"),
        _yiche_series("阿维塔07", "2026", "24.99万", "仅易车"),
    ]
    out = MD.dedupe_merged_rows(rows)
    import collections
    import re

    key = lambda r: (re.sub(r"\s+", "", str(r["车系"])), str(r["年款"]), re.sub(r"\s+", "", str(r["车型名称"])))
    counts = collections.Counter(key(r) for r in out)
    dups = {k: v for k, v in counts.items() if v > 1}
    assert not dups, f"SPU 内重复 SKU: {dups}"
