"""Pages 发布列窄化必须落在**真正喂发布面的那条路径**上（半修探测判据，当前在 main 上必须红）。

**为什么有这一单（监工 2026-10-12 23:10 +08:00 实测，全部可复现）**：

Issue #41 的 NPC 实现（本地分支 `npc/41-pages-columns-narrow`，实装提交 `6192c47`，
判据 4 passed）在 `scripts/merge_data.py` 里加了 `resolve_pages_columns` / `narrow_pages_rows`，
并把 `filtered_rows` 收窄后才写 `filtered_cars_.json` —— 方向是对的，
**但它只窄到了 merge_data 自己那个出口**：

1. `.cnb.yml:396-403`（合并与发布数据阶段）紧接着跑
   `python scripts/preserve_publish_baseline.py --filtered-json filtered_cars_.json ...`；
2. 该脚本 `write_publish_assets`（`scripts/preserve_publish_baseline.py:322-327`）里是：
   ```python
   filtered_rows = [row for row in rows if filter_car(row)]   # rows = merged 宽行
   write_json(staged[filtered_json], filtered_rows)           # 无条件重写
   write_csv(staged[filtered_csv], filtered_rows, header)     # 无条件重写
   ```
   ⇒ merge_data 写出的窄 filtered 文件被**宽行覆盖**；
3. 之后 `:427-428` `prepare_pages_payload.py` 与 `:484` `prepare_cloudflare_payload.py`
   才把 `filtered_cars_.json` → `site/data/filtered.json` → 前端分片。

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
IDENTITY = ("品牌", "车系", "车型名称", "年款", "车系ID", "数据来源", "车款ID")
ALLOWED = set(VISIBLE) | set(IDENTITY)


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
