#!/usr/bin/env python3
"""remerge_published_data.py — 用**修好的合并逻辑**重跑一次已发布数据（不再爬取）。

为什么需要它：
  合并主链路以前从未调用 `dedupe_merged_rows`，发布面上的同一车款ID 会各成一行
  （实测 2026-10-15：1095 个车款ID 出现多行、涉 2327 行）。逻辑修好后，要让线上数据
  真正受益，就得把**上一轮真实爬取的合并产物**再过一遍修好的归并段——这正是本脚本。

为什么可以直接吃 `merged_<date>.json`（即发布面 latest）：
  流水线里 merge_data.main() 的顺序是
    merge_rows → 报价叠加 → 零整比 → identity_key 去重 → **dedupe_merged_rows**
    → 年款过滤 → 上市时间归一 → 品牌清洗 → 排除黑名单 → filter_car → narrow_pages_rows
  而 `merged_<date>.json` 已经走完年款过滤及之后的所有步骤；**归并键里含年款**，
  跨年款永不合并 ⇒ 在已过滤的数据上补跑 dedupe，与在流水线里跑的结果一致
  （被年款过滤掉的行只会和同样年款的行合并，而那些行也被同一规则过滤掉了）。

口径（用户 2026-10-15 裁定）：年款不同 = 不同 SKU，绝不合并。

用法:
  python scripts/remerge_published_data.py --merged merged_20261015.json [--date 20261015]
      [--outdir .] [--max-drop-pct 5]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# 复用 merge_data.py 的唯一实现：本脚本不复制任何归并/过滤逻辑
sys.path.insert(0, str(HERE))
_spec = importlib.util.spec_from_file_location("merge_data", HERE / "merge_data.py")
MD = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(MD)
except SystemExit:  # merge_data 模块级 CLI 守卫
    pass

MIN_ROWS = 1000          # 与流水线「合并数据少于 1000 行拒绝发布」同一条线
# 归并最多允许减少的百分比。实测（2026-10-15 发布面）：merged 面 19382 -> 18345
# = 5.35%，filtered 面 14097 -> 13395 = 4.98%——这就是重复 SKU 的真实量级。
# 阈值取 8% 是留余量：万一归并键被改宽（比如退化成只按车系），掉行会是几十个百分点，
# 这条闸门照样拦得住。
MAX_DROP_PCT = 8.0


def dup_id_groups(rows: list) -> tuple:
    """返回 (重复车款ID 组数, 涉及行数)：发布面重复 SKU 的直接读数。"""
    groups = defaultdict(list)
    for row in rows:
        sku = str(row.get("车款ID", "") or "").strip()
        if sku:
            groups[sku].append(row)
    dup = {k: v for k, v in groups.items() if len(v) > 1}
    return len(dup), sum(len(v) for v in dup.values())


def remerge(rows: list, max_drop_pct: float = MAX_DROP_PCT) -> list:
    """对已发布的合并产物补跑修好的归并段（幂等）。"""
    before = len(rows)
    merged = MD.dedupe_merged_rows([dict(r) for r in rows])
    # 幂等自检：归并本身必须稳定，否则说明键依赖了会变的东西
    again = MD.dedupe_merged_rows([dict(r) for r in merged])
    if len(again) != len(merged):
        raise SystemExit(
            "❌ dedupe_merged_rows 不幂等（一遍 %d 行 vs 二遍 %d 行），拒绝发布"
            % (len(merged), len(again)))
    # 年款过滤在这里是幂等的（输入已过滤），保留以保证与流水线口径一致
    merged = [row for row in merged if MD.keep_pages_year(row)]
    after = len(merged)
    if after < MIN_ROWS:
        raise SystemExit("❌ 重合并后只有 %d 行（< %d），拒绝发布" % (after, MIN_ROWS))
    drop_pct = (before - after) * 100.0 / before if before else 0.0
    if drop_pct > max_drop_pct:
        raise SystemExit(
            "❌ 重合并减少 %.2f%%（%d -> %d），超过阈值 %.2f%%，疑似归并键过宽，拒绝发布"
            % (drop_pct, before, after, max_drop_pct))
    return merged


def build_filtered(rows: list) -> list:
    filtered = [row for row in rows if MD.filter_car(row)]
    return MD.narrow_pages_rows(filtered)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged", required=True, type=Path, help="上一轮 merged_<date>.json（即发布面 latest）")
    ap.add_argument("--filtered", type=Path,
                    help="上一轮 filtered_cars_<date>.json（发布面 filtered）。给了就**只对它去重**"
                         "（保住现网发布行集不变），不给才用 filter_car 从合并结果重算")
    ap.add_argument("--date", default="", help="输出文件名里的日期；留空则从文件名里认")
    ap.add_argument("--outdir", default=".", type=Path)
    ap.add_argument("--max-drop-pct", type=float, default=MAX_DROP_PCT)
    args = ap.parse_args()

    date = args.date or ""
    if not date:
        import re
        m = re.search(r"(20\d{6})", args.merged.name)
        if not m:
            raise SystemExit("❌ 认不出日期，请显式给 --date")
        date = m.group(1)

    with args.merged.open(encoding="utf-8") as handle:
        rows = json.load(handle)
    if not isinstance(rows, list) or len(rows) < MIN_ROWS:
        raise SystemExit("❌ 输入 %s 只有 %d 行（< %d），拒绝重合并"
                         % (args.merged, len(rows) if isinstance(rows, list) else 0, MIN_ROWS))

    before_groups, before_rows = dup_id_groups(rows)
    merged = remerge(rows, args.max_drop_pct)
    after_groups, after_rows = dup_id_groups(merged)

    if args.filtered:
        # 只对现网发布行集去重：行集本身不动，只把重复的 SKU 折叠掉。
        # （不用 filter_car 从 merged 重算，是为了不让既有 filter_car 口径变化
        #   顺带把发布行集撑大——那不是本单要改的事。）
        with args.filtered.open(encoding="utf-8") as handle:
            old_filtered = json.load(handle)
        f_before_groups, _ = dup_id_groups(old_filtered)
        filtered = remerge(old_filtered, args.max_drop_pct)
    else:
        filtered = build_filtered(merged)
        f_before_groups = None
    f_after_groups, _ = dup_id_groups(filtered)

    args.outdir.mkdir(parents=True, exist_ok=True)
    fields = MD.collect_fields(merged)
    MD.write_csv(str(args.outdir / f"merged_{date}.csv"), merged, fields)
    MD.write_json(str(args.outdir / f"merged_{date}.json"), merged)
    ffields = MD.collect_fields(filtered)
    MD.write_csv(str(args.outdir / f"filtered_cars_{date}.csv"), filtered, ffields)
    MD.write_json(str(args.outdir / f"filtered_cars_{date}.json"), filtered)

    print(json.dumps({
        "date": date,
        "merged_rows_before": len(rows),
        "merged_rows_after": len(merged),
        "removed_by_sku_dedupe": len(rows) - len(merged),
        "filtered_rows_before": len([r for r in rows if MD.filter_car(r)]),
        "filtered_rows_after": len(filtered),
        "filtered_dup_sku_groups_before": f_before_groups,
        "filtered_dup_sku_groups_after": f_after_groups,
        "dup_sku_groups_before": before_groups,
        "dup_sku_groups_after": after_groups,
        "dup_sku_rows_before": before_rows,
        "dup_sku_rows_after": after_rows,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
