"""合并必须**幂等**、且**绝不叠前缀**——现网跨源合并串无限膨胀的根因判据。

实测（2026-10-14，main tip `90ec3f0` 内容上直接调用函数，见 npc-redtests/check_main_merge_1014.txt）：
    _merge_existing_with_source({"外后视镜记忆": "汽车之家:电动调节 / 电动折叠|懂车帝:电动调节|锁车自动折叠"},
                                "汽车之家", "懂车帝", {"外后视镜记忆": "电动调节|锁车自动折叠|电动折叠"})
  第 1 次 => '汽车之家:汽车之家:电动调节 / 电动折叠|懂车帝:…|懂车帝:电动调节|锁车自动折叠|电动折叠'
  第 2 次 => '汽车之家:汽车之家:汽车之家:…'（每喂一次多一层，汽车之家/懂车帝 前缀各 3 次）
现网后果（filtered 面 manifest 2026-10-14T04:16Z，13388 行）：
  510 行含跨源合并串；单值 `|` 个数最高 448，出现 342 个 `|` 的值有 19 条；
  39 条值里同一源前缀出现 ≥2 段，123 条值里同一 token 重复 ≥3 次（集中在 外后视镜记忆）。

这些用例当前为红。修复要满足的红线在第 4、5 条里，不许用"折叠成真冲突"换取幂等。
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

SPEC = importlib.util.spec_from_file_location("merge_data", ROOT / "scripts" / "merge_data.py")
MD = importlib.util.module_from_spec(SPEC)
try:
    SPEC.loader.exec_module(MD)
except SystemExit:  # pragma: no cover - module-level CLI guard
    pass

SOURCES = ("汽车之家", "懂车帝", "易车")


def _prefix_counts(text):
    return {s: len(re.findall(re.escape(s) + r"\s*[:：]", str(text))) for s in SOURCES}


def _row_value(current, current_source, source_name, incoming, key="外后视镜记忆"):
    return MD._merge_existing_with_source(current, current_source, source_name, incoming).get(key)


def test_existing_prefixed_value_is_not_prefixed_again():
    """existing 已经是 `汽车之家:…|懂车帝:…` 时，再合并**不许**在外面套第二层源前缀。"""
    existing = "汽车之家:电动调节 / 电动折叠|懂车帝:电动调节|锁车自动折叠"
    out = _row_value({"外后视镜记忆": existing}, "汽车之家", "懂车帝",
                     {"外后视镜记忆": "电动调节|锁车自动折叠|电动折叠"})
    assert "汽车之家:汽车之家:" not in str(out), "叠了第二层 汽车之家: 前缀（实测 main 就是这样）"
    assert "懂车帝:懂车帝:" not in str(out), "叠了第二层 懂车帝: 前缀"
    counts = _prefix_counts(out)
    assert all(n <= 1 for n in counts.values()), "同一源在合并串里出现多段：%s" % counts


def test_remerging_the_same_incoming_is_idempotent():
    """同一份输入喂第二次，结果必须逐字不变（否则每轮发布都在往上摞）。"""
    current = {"外后视镜记忆": "汽车之家:电动调节 / 电动折叠"}
    incoming = {"外后视镜记忆": "电动调节|锁车自动折叠"}
    once = _row_value(dict(current), "汽车之家", "懂车帝", dict(incoming))
    twice = _row_value({"外后视镜记忆": once}, "汽车之家", "懂车帝", dict(incoming))
    assert twice == once, "非幂等：一次=%r 两次=%r" % (once, twice)


def test_merge_distinct_values_is_idempotent_too():
    """`_merge_distinct_values` 是同族写出点，不许只修一处留下第二处（半修）。"""
    existing = "汽车之家:加热 / 通风|懂车帝:加热|通风"
    incoming = "汽车之家:加热|通风|按摩"
    once = MD._merge_distinct_values(existing, incoming)
    twice = MD._merge_distinct_values(once, incoming)
    assert twice == once, "非幂等：一次=%r 两次=%r" % (once, twice)
    counts = _prefix_counts(once)
    assert all(n <= 1 for n in counts.values()), "同一源多段：%s（值=%r）" % (counts, once)


def test_both_writers_leave_at_most_one_segment_per_source():
    """同族写出点必须**一起**改：两个路径都不许留下同一源的多个代码段。

    为什么单列一条：本仓的合并串有两个写出点（merge_data 的 `_merge_existing_with_source`
    与 `_merge_distinct_values`），历史上"只改一份"反复出现（`.cnb.yml` 的 api_trigger
    与 crontab 两份拷贝也是同一个教训）。形状不一致时去重键会分叉，
    直接喂给 SPU 重复 SKU 那一族缺陷。
    （注意：两条路径掌握的信息不同——行合并知道 incoming 属于哪个源，值合并不知道——
      所以这里**不比逐字相等**，只比"每源 ≤1 段"这个共同底线。）
    """
    via_row = _row_value({"外后视镜记忆": "汽车之家:电动调节"}, "汽车之家", "懂车帝",
                         {"外后视镜记忆": "电动调节|电动折叠"})
    via_distinct = MD._merge_distinct_values("汽车之家:电动调节", "电动调节|电动折叠")
    for label, text in (("行合并", via_row), ("值合并", via_distinct)):
        counts = _prefix_counts(text)
        assert all(n <= 1 for n in counts.values()), (
            "%s 路径留下同源代码多段：%s（值=%r）" % (label, counts, text))
        assert not re.search(r"(汽车之家|懂车帝|易车)\s*[:：]\s*\1\s*[:：]", str(text)), (
            "%s 路径叠了相邻两层同源前缀：%r" % (label, text))


def test_real_conflict_is_still_preserved():
    """红线：不许为了幂等把**真正不同**的两源写法折叠掉（用户口径：不同功能不能合并）。

    加热 vs 制冷 是实质差异，合并后必须仍能同时看到两个源各自的写法。
    """
    out = _row_value({"外后视镜记忆": "汽车之家:加热"}, "汽车之家", "懂车帝", {"外后视镜记忆": "制冷"})
    assert "加热" in str(out) and "制冷" in str(out), "真冲突被折叠掉：%r" % out
    counts = _prefix_counts(out)
    assert counts["汽车之家"] >= 1 and counts["懂车帝"] >= 1, "两源都必须在串里留痕：%s" % counts


def test_helpers_are_not_renamed_or_removed():
    """红线：不许靠改名/删函数让上面的用例跳过。"""
    for name in ("_merge_existing_with_source", "_merge_distinct_values"):
        assert callable(getattr(MD, name, None)), "写出点 %s 不在了（不许用改名绕过判据）" % name
