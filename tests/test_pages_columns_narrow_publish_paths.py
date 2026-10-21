"""Pages 发布列窄化必须落在**真正喂发布面的那条路径**上（半修探测判据，当前在 main 上必须红）。

**为什么有这一单（监工 2026-10-12 23:10 +08:00 实测，全部可复现）**：

Issue #41 的 NPC 实现（本地分支 `npc/41-pages-columns-narrow`，实装提交 `6192c47`，
判据 4 passed）在 `scripts/merge_data.py` 里加了 `resolve_pages_columns` / `narrow_pages_rows`，
并把 `filtered_rows` 收窄后才写 `filtered_cars_${DATE}.json` —— 方向是对的，
**但它只窄到了 merge_data 自己那个出口**：

1. `.cnb.yml:396-403`（合并与发布数据阶段）紧接着跑
   `python scripts/preserve_publish_baseline.py --filtered-json filtered_cars_${DATE}.json ...`；
2. 该脚本 `write_publish_assets`（`scripts/preserve_publish_baseline.py:322-327`）里是：
   ```python
   filtered_rows = [row for row in rows if filter_car(row)]   # rows = merged 宽行
   write_json(staged[filtered_json], filtered_rows)           # 无条件重写
   write_csv(staged[filtered_csv], filtered_rows, header)     # 无条件重写
   ```
   ⇒ merge_data 写出的窄 filtered 文件被**宽行覆盖**；
3. 之后 `:427-428` `prepare_pages_payload.py` 与 `:484` `prepare_cloudflare_payload.py`
   才把 `filtered_cars_${DATE}.json` → `site/data/filtered.json` → 前端分片。

⇒ **只在 merge_data 里窄化 = 被下游 preserve 覆盖 = 线上每行仍是 11574 B（实测值）**。
本判据抓的就是这个"两份写出拷贝只改一份"的半修形状（同 [[feedback-root-cause-then-verify]]
的"同一文件里的重复字面块只改一份=半修"，这里是跨文件的两份写出拷贝）。

**口径（四条都要成立）**：
  A. `merge_data.resolve_pages_columns(rows)` 存在，输出 ⊆ `defaultVisibleColumns ∪ 7 身份列`；
  B. **`preserve_publish_baseline.write_publish_assets(...)` 写出的 `filtered_json` / `filtered_csv`
     也必须是窄的**（这条才是发布面真口径；只做 A 不做 B = 半修，本判据存在的理由）；
  C. 收窄不减少行集合（9 行宽夹具过 `filter_car` 后必须仍是 9 行）；
  D. `merged_json` / `merged_csv`（latest 全量面）仍然带全部列——收列不许收掉全量产物。
"""

from __future__ import annotations

import csv
import importlib.util
import json
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "filter_conditions.json").read_text(encoding="utf-8"))
VISIBLE = [str(c) for c in (CONFIG.get("defaultVisibleColumns") or [])]


def test_identity_columns_are_declared_once() -> None:
    """本判据的身份列必须就是实现的那一份（同源），且发布面的列集合不得越界。"""
    from importlib import reload  # noqa: F401  (仅为可读性；不 reload)
    assert IDENTITY == tuple(MD.PAGES_IDENTITY_COLUMNS), "判据里的身份列与实现不是同一份"
    rows = _rows(3)
    cols = set(MD.resolve_pages_columns(rows))
    assert cols <= ALLOWED, "窄化后的列越界（不在 默认可见列 ∪ 身份列 里）：%s" % sorted(cols - ALLOWED)


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit:  # 模块级 CLI 守卫
        pass
    return module


MD = _load("merge_data", "scripts/merge_data.py")
PPB = _load("preserve_publish_baseline", "scripts/preserve_publish_baseline.py")

# 评审 S3：身份列**不许在本判据里另抄一份**（以前写死 7 列，实现加了第 8 列后判据就与实现脱钩，
# 越界没人报）。必须等 MD 装载完再取，所以放在这里而不是文件顶部常量区。
IDENTITY = tuple(MD.PAGES_IDENTITY_COLUMNS)
ALLOWED = set(VISIBLE) | set(IDENTITY)


def _wide_row(i: int) -> dict:
    row = {
        "品牌": "测试品牌", "车系": "测试车系%d" % i, "车型名称": "测试车型 %d" % i,
        "年款": "2026", "车系ID": str(i), "数据来源": "仅汽车之家", "车款ID": str(1000 + i),
        "能源类型": "纯电动", "官方指导价": "30.00万", "上市时间": "2026-03",
    }
    for n in range(400):
        row["伪造属性列%d" % n] = "值%d" % (i % 7)
    return row


def _rows(n: int = 9) -> list:
    return [_wide_row(i) for i in range(n)]


def test_default_visible_set_is_declared_and_non_trivial() -> None:
    assert len(VISIBLE) >= 20, (
        "config/filter_conditions.json 的 defaultVisibleColumns 只有 %d 条 ⇒ 判『读不到』，"
        "不许据此判列窄通过（清单被清空会让任何实现都『达标』）" % len(VISIBLE))


def test_merge_data_resolver_exists() -> None:
    assert hasattr(MD, "resolve_pages_columns"), (
        "merge_data.py 里没有 resolve_pages_columns(rows)：发布列集合无处收敛，"
        "现网实测 filtered 仍是 1205 列 / 每行 11574 B")


def test_merge_data_resolver_stays_inside_declared_set() -> None:
    if not hasattr(MD, "resolve_pages_columns"):
        assert False, "merge_data.py 没有 resolve_pages_columns(rows)，无法核对发布列集合（见上一条）"
    cols = list(MD.resolve_pages_columns(_rows(12)))
    extra = [c for c in cols if c not in ALLOWED]
    assert not extra, "发布列越出仓库声明的默认可见集合（+7 身份列）：越界 %d 个，例 %s" % (len(extra), extra[:6])
    assert len(cols) <= len(VISIBLE) + 8, (
        "发布列 %d 超过默认可见 %d + 容差 8 ⇒ 每行载荷会远超 1000 B 预算" % (len(cols), len(VISIBLE)))


def test_preserve_write_publish_assets_output_is_narrow(tmp_path) -> None:
    """B 条（本判据的核心）：preserve_publish_baseline 写出的 filtered 产物必须是窄的。

    只改 merge_data 不改这里 = 被 :322-327 无条件重写 = 线上不变（半修）。
    """
    rows = _rows(9)
    merged_json = tmp_path / "merged_20261012.json"
    merged_csv = tmp_path / "merged_20261012.csv"
    filtered_json = tmp_path / "filtered_cars_20261012.json"
    filtered_csv = tmp_path / "filtered_cars_20261012.csv"
    PPB.write_publish_assets(rows, merged_json, merged_csv, filtered_json, filtered_csv)

    written = json.loads(filtered_json.read_text(encoding="utf-8"))
    assert isinstance(written, list) and written, "preserve 写出的 filtered_json 不是非空行数组"
    keys = set()
    for row in written:
        keys.update(str(k) for k in row.keys())
    extra = sorted(keys - ALLOWED)
    assert not extra, (
        "preserve_publish_baseline.write_publish_assets 写出的 filtered_json 仍带 %d 个越界列"
        "（例 %s）：这正是覆盖 merge_data 窄化、让线上每行保持 11574 B 的那一份写出拷贝"
        % (len(extra), extra[:6]))

    with filtered_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        header = next(csv.reader(fh))
    csv_extra = [c for c in header if c not in ALLOWED]
    assert not csv_extra, (
        "preserve 写出的 filtered_csv 表头仍带越界列（例 %s）：前端/导出面与 JSON 分片会读到宽表"
        % csv_extra[:6])


def test_narrowing_does_not_drop_rows() -> None:
    rows = _rows(9)
    kept = [r for r in rows if MD.filter_car(dict(r))]
    assert len(kept) == len(rows), (
        "收窄列把行也吃掉了（%d→%d）：行全是 #32 的口径，列窄不许拿它交换" % (len(rows), len(kept)))


def test_full_data_outputs_still_wide(tmp_path) -> None:
    """D 条：merged（latest 全量面）仍然带全部列——收列不许收掉全量产物。"""
    rows = _rows(3)
    merged_json = tmp_path / "merged_20261012.json"
    merged_csv = tmp_path / "merged_20261012.csv"
    filtered_json = tmp_path / "filtered_cars_20261012.json"
    filtered_csv = tmp_path / "filtered_cars_20261012.csv"
    PPB.write_publish_assets(rows, merged_json, merged_csv, filtered_json, filtered_csv)
    written = json.loads(merged_json.read_text(encoding="utf-8"))
    keys = set()
    for row in written:
        keys.update(str(k) for k in row.keys())
    assert len(keys) > len(ALLOWED), (
        "merged_json 只剩 %d 列 ⇒ 全量面被一起收窄，那是丢数据不是收列" % len(keys))


PP = _load("prepare_pages_payload", "scripts/prepare_pages_payload.py")


def _yiche_row(i: int) -> dict:
    row = _wide_row(i)
    row["数据来源"] = "懂车帝+易车"
    row["易车上市状态"] = "approved"
    return row


def test_j1_gate_read_columns_must_survive_narrowing() -> None:
    """J1 不变式：发布门禁要读的列必须活过 `narrow_pages_rows`。

    实测反例（监工 2026-10-16，现网发布面包裹 19382 行）：`易车上市状态` 在
    `IDENTITY_ONLY_FIELDS`（merge_data.py:8185）里却不在 `PAGES_IDENTITY_COLUMNS`
    （:15546）里 ⇒ 被窄掉后 `yiche_publish_identity_valid` 的 `status == "approved"`
    恒假，**每一轮把 5069 条含易车标签的行整源删掉**，而 `stats` 里一个非零计数都没有
    （那条 `continue` 没有计数器）。
    """
    assert "易车上市状态" in MD.PAGES_IDENTITY_COLUMNS, (
        "发布门禁读的列没进身份列 ⇒ narrow 会把它裁掉，下游必然误杀整源")
    rows = [_yiche_row(i) for i in range(3)]
    narrowed = MD.narrow_pages_rows([dict(r) for r in rows])
    for row in narrowed:
        assert row.get("易车上市状态") == "approved", (
            "narrow 之后状态列没了 ⇒ 门禁读不到只能判不合格：%r" % sorted(row.keys()))
    out, stats = PP.prepare_rows_with_stats([dict(r) for r in narrowed], 2022)
    assert len(out) == 3, "带 approved 的易车行被发布门禁丢弃：剩 %d 行，分账=%s" % (
        len(out), stats.get("dropBySource"))


def test_j2_stopped_yiche_row_is_dropped_and_named() -> None:
    """J2 反向：保护必须真会触发——状态不是 approved 的易车行必须被丢，且按源点名。"""
    bad = _yiche_row(7)
    bad["易车上市状态"] = "停售"
    out, stats = PP.prepare_rows_with_stats([dict(bad)], 2022)
    assert out == [], "停售的易车行竟然发布出去了"
    by_src = stats.get("dropBySource") or {}
    assert any(v.get("易车") for v in by_src.values()), (
        "删了行却没有按源的分账 ⇒ 下一轮整源消失照样没人看得见：%s" % sorted(stats))


def test_j3_gate_fields_and_published_columns_stay_consistent() -> None:
    """J3 一致性：门禁读的字段必须都在「默认可见列 ∪ 发布身份列」里（两份字面块不许各说各话）。"""
    gate_fields = {"易车上市状态", "车款ID", "车系", "品牌", "车型名称", "年款", "数据来源"}
    allowed = set(VISIBLE) | set(MD.PAGES_IDENTITY_COLUMNS)
    missing = gate_fields - allowed
    assert not missing, "门禁要读的列没进发布身份列，窄化后必然误杀：%s" % sorted(missing)


def _load_payload_prep():
    spec = importlib.util.spec_from_file_location(
        "ppp_presence", str(ROOT / "scripts" / "prepare_pages_payload.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_source_presence_gate_blocks_a_lost_source_and_a_blanked_identity_column() -> None:
    """发布前"逐源在位"闸必须双向：整源没了要拦，身份列被裁空也要拦；都齐时不得挡路。

    为什么要钉在仓库里：10-18 现网 `latest` 有易车 5123 行、`filtered` 0 行，
    而发布链**照样绿、照样上线**——因为没人问"每个源还在不在"。
    根因是窄化把 `易车上市状态` 裁掉 ⇒ 下游身份闸永远读到空 ⇒ 整源被删且无计数。
    所以这一条同时看两件事，且**红就拒绝写出发布面**。
    """
    ppp = _load_payload_prep()
    inp = [
        {"数据来源": "仅懂车帝", "品牌": "甲", "车系": "甲系", "车型名称": "甲系 2026款 风",
         "年款": "2026", "车系ID": "1", "车款ID": "D1"},
        {"数据来源": "仅易车", "品牌": "乙", "车系": "乙系", "车型名称": "乙系 2026款 云",
         "年款": "2026", "车系ID": "2", "车款ID": "Y1", "易车上市状态": "approved"},
    ]
    # 绿：两个源都在、身份列都活着
    assert ppp.source_presence_problems(inp, [dict(r) for r in inp]) == ([], [])
    # 红 1：易车整面丢失
    missing, _ = ppp.source_presence_problems(inp, [dict(inp[0])])
    assert any(s == "易车" for s, _i, _o in missing), "整源丢失没被拦住"
    # 红 2：易车行还在，但身份列 `易车上市状态` 被裁成空列
    stripped = [{k: v for k, v in r.items() if k != "易车上市状态"} for r in inp]
    _m, blank = ppp.source_presence_problems(inp, stripped)
    assert any(c == "易车上市状态" for c, _n in blank), "身份列被裁空没被拦住"


def test_source_presence_gate_uses_the_same_identity_declaration_as_the_impl() -> None:
    """闸的"身份列"清单必须取自实现那份，不许在测试里另抄一张（抄了就会随实现漂移）。"""
    ppp = _load_payload_prep()
    inp = [{col: "x" for col in MD.PAGES_IDENTITY_COLUMNS} | {"数据来源": "仅懂车帝"}]
    out = [{col: "" for col in MD.PAGES_IDENTITY_COLUMNS if col != "数据来源"}
           | {"数据来源": "仅懂车帝"}]
    _m, blank = ppp.source_presence_problems(inp, out)
    cols = {c for c, _n in blank}
    assert cols == set(MD.PAGES_IDENTITY_COLUMNS) - {"数据来源"}, (
        "发布面把身份列全裁空却只报出 %s ⇒ 闸没跟着实现的那份清单走" % sorted(cols))
