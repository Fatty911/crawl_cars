"""发布面**存量**脏值必须被清洗，不能只防"新增膨胀"。

监工读代码得到的机制（不是猜）：
  `.cnb.yml` 的发布段先跑 `scripts/preserve_publish_baseline.py`（L401 / L1084 两份链拷贝），
  之后才跑 `scripts/prepare_pages_payload.py`（L508 / L1191）。
  而 `preserve_rows()` 的形状是 `preserved = list(baseline_rows)` + `enrich_baseline_row()`
  **只往缺失字段里补值**（`missing_value(enriched.get(field)) and not missing_value(value)`），
  ⇒ baseline 里**已经存在**的脏值原样带出，永远不会被新写的合并逻辑重写。

现网脏值形状（filtered 面 13388 行，manifest 2026-10-14T04:16Z 实测）：
  同源前缀在一个值里出现 ≥2 段 = **39 条**；同一 token 在一个值里重复 ≥3 次 = **123 条**；
  单值 `|` 最多 448 个；`汽车之家:汽车之家:…` 这种叠前缀的形状在 main 上函数级复现过。

⇒ 只修 Issue #70（合并不再叠前缀、必须幂等）会让"下一轮不再变坏"，
   但**存量脏值仍在发布面上**，第 6 项读数不会收敛。
   这条用例量的是"清洗存量"这一格，与 #70 是两格，缺一不可。

这些用例当前为红。
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
# `preserve_publish_baseline.py` 里是 `from merge_data import (...)`，
# 所以必须先把 scripts/ 放进 sys.path；否则判据在收集阶段就**崩**而不是干净变红
# （崩掉的套件不能当红样下发——它会让人以为缺陷没被量到）。
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    try:
        spec.loader.exec_module(module)
    except SystemExit:  # pragma: no cover - module-level CLI guard
        pass
    return module


PB = _load("preserve_publish_baseline")
MD = _load("merge_data")

SOURCES = ("汽车之家", "懂车帝", "易车")
KEYS = ("车系", "年款", "车型名称", "品牌", "数据来源")


def _row(**over):
    row = {"品牌": "测试牌", "车系": "测试S", "年款": "2026",
           "车型名称": "测试S 2026款 Pro", "数据来源": "汽车之家+懂车帝",
           "官方指导价": "10万"}
    row.update(over)
    return row


def _counts(text):
    return {s: len(re.findall(re.escape(s) + r"\s*[:：]", str(text))) for s in SOURCES}


def test_baseline_dirty_value_is_refolded_not_carried_through():
    """baseline 里的叠前缀/重复段必须被重折成"每源一段"，不许原样搬进发布面。"""
    dirty = "汽车之家:电动调节 / 电动折叠|懂车帝:电动调节|电动折叠|汽车之家:电动调节 / 电动折叠"
    out, _changed = PB.enrich_baseline_row(_row(外后视镜记忆=dirty), _row())
    got = str(out.get("外后视镜记忆", ""))
    assert "汽车之家:汽车之家:" not in got, "叠前缀形状被原样带出：%r" % got
    c = _counts(got)
    assert all(n <= 1 for n in c.values()), (
        "同一源仍有多个代码段（每源应 ≤1）：%s ← %r" % (c, got))


def test_cleaning_is_idempotent_on_already_clean_values():
    """清洗必须是幂等的：已经规范的值不许被改出第二形状（否则每轮都在动存量）。"""
    clean = "汽车之家:加热 / 通风|懂车帝:加热|通风"
    a, _ = PB.enrich_baseline_row(_row(前排座椅功能=clean), _row())
    b, _ = PB.enrich_baseline_row(a, _row())
    assert a.get("前排座椅功能") == clean, "规范值被改动：%r -> %r" % (clean, a.get("前排座椅功能"))
    assert b.get("前排座椅功能") == a.get("前排座椅功能"), "清洗不幂等"


def test_genuine_cross_source_conflict_survives_cleaning():
    """红线：清洗只消"同源代码多段/叠前缀/自我重复"，**不许**把真冲突折成一个源。"""
    real = "汽车之家:五连杆式独立悬架|懂车帝:多连杆式独立悬架"
    out, _ = PB.enrich_baseline_row(_row(后悬挂形式=real), _row())
    got = str(out.get("后悬挂形式", ""))
    assert "五连杆" in got and "多连杆" in got, "真冲突被折叠：%r" % got
    c = _counts(got)
    assert c["汽车之家"] >= 1 and c["懂车帝"] >= 1, "两源留痕被抹掉：%s" % c


def test_row_count_and_identity_fields_are_not_reduced():
    """红线：清洗**只改值**，不许丢身份/来源字段，也不许把行折叠掉。

    口径说明（监工自校过）：我第一版在这里直接调 `preserve_rows`，
    但它要求一整套真实行结构（`unique_keys`/身份字段/年款口径），
    用夹具硬造会让判据"因夹具错而红"——那会派着 agent 去修我的测试。
    所以这一条只量能确定性复现的那一层（`enrich_baseline_row` 是清洗的必经点），
    "整轮不丢行"由现网重量的**行数守恒**（`live_pages_meter.py` 的行数字节守恒自检）来兜。
    """
    dirty = _row(外后视镜记忆="汽车之家:A|懂车帝:A|汽车之家:A",
                 官方指导价="汽车之家:10万|懂车帝:10.00万")
    out, _changed = PB.enrich_baseline_row(dirty, _row())
    for k in KEYS:
        assert k in out, "清洗把身份/来源字段弄没了：%s" % k
    assert str(out.get("车系")) == "测试S" and str(out.get("车型名称")).startswith("测试S"), (
        "身份字段被改写：%r" % out)
    got = str(out.get("外后视镜记忆", ""))
    assert "汽车之家:汽车之家:" not in got, "叠前缀没被清洗：%r" % got
    assert "懂车帝" in str(out.get("数据来源", "")), "来源留痕被抹掉：%r" % out.get("数据来源")


def test_cleaner_is_reused_not_reimplemented():
    """接线：清洗必须复用 #70 落在 merge_data 的同一个解析/折叠器，
    避免"两套尺子"——发布面与合并面各折各的会再次分叉（本仓反复栽在这上面）。"""
    fold = [n for n in dir(MD) if re.search(r"(fold_source|_preserved_value_parts|source_segments)", n)]
    assert fold, "merge_data 里没有可复用的源段折叠器（#70 落地后应有）"
    src = (ROOT / "scripts" / "preserve_publish_baseline.py").read_text(encoding="utf-8")
    assert any(f in src for f in fold), (
        "preserve_publish_baseline.py 没引用 merge_data 的折叠器 %s ⇒ 它在自己那套逻辑里搬旧值" % fold)
