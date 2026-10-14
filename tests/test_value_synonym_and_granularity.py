"""A 类缺陷判据：同一事实被写成"跨源冲突串"，因为归一表缺拼写族/单位后缀，
且多源合并那条路径**没有**沿用到日期的"取精细"规则。

现网实测（filtered 面 13388 行，manifest 2026-10-14T04:16Z；
按"两个源段归一后其实相等却写成冲突串"统计）：

  换挡形式 166 行 / 前悬挂形式 150 行 / 后悬挂形式 99 行 / 外后视镜记忆 53 行 / 最小转弯半径 4 行
  上市时间 288 行全是 `汽车之家:2026-04-23|懂车帝:2026.04` 这种**同一事实两种粒度**

main 内容实测（直接调函数，见 npc-redtests/probe_a_class_behaviour.py）：

  canonical_compare('麦弗逊式独立悬架','前悬挂形式') != canonical_compare('麦弗逊式独立悬挂',…)  # 判异
  canonical_compare('59.88万','官方指导价') = '59.88万'  而  canonical_compare('59.88万元',…) = 'num:59.88'
      # 同一个数两种写法**折叠程度不一致**，不是"判异"，是归一表不闭环
  _merge_existing_with_source(…) 对 2026-04-23 vs 2026.04 **已经**会取 '2026-04-23'
  ⇒ 说明"取精细"规则只接在行合并那一条路径上，`merge_source_rows`（现网 288 行那条）没接

这些用例当前为红。第 4、5、6 条是**红线**：现在就该绿，修完必须还绿——
不许为了少几行合并串把真差异折掉（负责人原话：「无钥匙启动和远程启动是两种不同的功能」）。
"""

from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

SPEC = importlib.util.spec_from_file_location("merge_data", ROOT / "scripts" / "merge_data.py")
MD = importlib.util.module_from_spec(SPEC)
try:
    SPEC.loader.exec_module(MD)
except SystemExit:  # pragma: no cover - module-level CLI guard
    pass


def _merge_two(field, ah_value, dcd_value, **extra):
    """走**现网那条**多源合并路径（`merge_source_rows`），不是行合并助手。"""
    ah = {field: ah_value}
    dcd = {field: dcd_value}
    for k, v in extra.items():
        ah[k] = v
        dcd[k] = v
    return MD.merge_source_rows([("汽车之家", ah), ("懂车帝", dcd)])


def test_suspension_spelling_family_is_folded():
    """`悬架` 与 `悬挂` 是同一词的两种写法，判异才导致现网 249 行写成冲突串。"""
    assert MD.canonical_compare("麦弗逊式独立悬架", "前悬挂形式") == \
        MD.canonical_compare("麦弗逊式独立悬挂", "前悬挂形式"), (
        "悬架/悬挂 仍判异（现网实测 150+99 行因此成为跨源合并串）")
    out = _merge_two("前悬挂形式", "麦弗逊式独立悬架", "麦弗逊式独立悬挂")
    assert "|" not in str(out.get("前悬挂形式", "")), (
        "同一事实仍写成冲突串：%r" % out.get("前悬挂形式"))


def test_price_unit_suffix_folds_to_one_shape():
    """`59.88万` 与 `59.88万元` 必须折到**同一种**形状（现在一个折成 num:、一个不折）。"""
    a = MD.canonical_compare("59.88万", "官方指导价")
    b = MD.canonical_compare("59.88万元", "官方指导价")
    assert a == b, "同一价格的两种写法折叠程度不一致：%r vs %r" % (a, b)
    out = _merge_two("官方指导价", "59.88万", "59.88万元")
    assert "|" not in str(out.get("官方指导价", "")), "价格仍写成合并串：%r" % out.get("官方指导价")


def test_date_granularity_picks_the_finere_value_on_both_paths():
    """到日 vs 到月 是**粒度差**不是分歧：行合并路径已经会取 '2026-04-23'，
    多源合并路径（现网 288 行那条）也必须取精细那一条，且不许包成合并串。"""
    row_path = MD._merge_existing_with_source({"上市时间": "汽车之家:2026-04-23"},
                                              "汽车之家", "懂车帝", {"上市时间": "2026.04"})
    assert row_path.get("上市时间") == "2026-04-23", (
        "行合并路径的既有语义被改坏：%r" % row_path.get("上市时间"))
    out = _merge_two("上市时间", "2026-04-23", "2026.04")
    assert out.get("上市时间") == "2026-04-23", (
        "多源路径没接'取精细'规则，现网就是这样写出 288 行：%r" % out.get("上市时间"))


def test_genuine_structural_difference_stays_visible():
    """红线：`五连杆` 与 `多连杆` 是不同结构，必须仍写成两源各自取值。"""
    assert MD.canonical_compare("五连杆式独立悬架", "前悬挂形式") != \
        MD.canonical_compare("多连杆式独立悬架", "前悬挂形式"), "真结构差异被折掉了"
    out = _merge_two("前悬挂形式", "五连杆式独立悬架", "多连杆式独立悬架")
    text = str(out.get("前悬挂形式", ""))
    assert "五连杆" in text and "多连杆" in text, "真差异被折叠：%r" % text


def test_boolean_capability_domain_is_not_collapsed():
    """红线：`标配` 与 `选装` 语义不同（VALUE_SYNONYMS 里 标配→支持、选配→选装），
    不许因为都算'有能力'就折成一个值。"""
    assert MD.canonical_compare("标配", "远程启动") != MD.canonical_compare("选装", "远程启动"), (
        "标配/选装 被折成同值——这会把'要不要加钱'的信息抹掉")
    out = _merge_two("远程启动", "标配", "选装")
    text = str(out.get("远程启动", ""))
    assert "支持" in text or "标配" in text, "标配侧丢了：%r" % text
    assert "选装" in text, "选装侧丢了：%r" % text


def test_numeric_divergence_stays_divergent():
    """红线：`6` 与 `5.815m` 是两个源给了两个数，是真分歧，不许当归一问题折掉。"""
    assert MD.canonical_compare("6", "最小转弯半径") != \
        MD.canonical_compare("5.815m", "最小转弯半径")
    out = _merge_two("最小转弯半径", "6", "5.815m")
    text = str(out.get("最小转弯半径", ""))
    assert "6" in text and "5.815" in text, "真数值分歧被折叠：%r" % text
