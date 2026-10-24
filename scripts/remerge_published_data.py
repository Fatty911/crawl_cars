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
# 归并最多允许减少的百分比（默认档位 = 无人值守轮次用的兜底）。
# 实测（2026-10-15 发布面）：merged 面 19382 -> 18345 = 5.35%，filtered 面 14097 -> 13395 = 4.98%。
# 阈值取 8% 是留余量：万一归并键被改宽（比如退化成只按车系），掉行会是几十个百分点，
# 这条闸门照样拦得住。
# 口径补记（负责人 10-15）：这条线不是人定的数（本仓 7a80657 由 harness 自己加的），
# 目的是防半月自动增量那类无人值守轮次出大问题；**调试轮在证据充足时可以抬高**，
# 抬高由 `remerge()` 里的身份不变式（车款ID 集合前后相等）把关，不许裸跳。
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


def sku_ids(rows: list) -> set:
    """发布面上的非空 车款ID 集合 = 源侧 SKU 身份。折叠只能让行数变少，不能让身份集合变小或变大。"""
    return {str(r.get("车款ID", "") or "").strip() for r in rows} - {"", "-"}


def remerge(rows: list, max_drop_pct: float = MAX_DROP_PCT) -> list:
    """对已发布的合并产物补跑修好的归并段（幂等）。"""
    before = len(rows)
    ids_before = sku_ids(rows)
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
    # 身份不变式**无条件**执行：折叠只该让行数变少，不该让任何非空 车款ID 从面上消失或凭空多出。
    # （评审 B2：以前只在抬高阈值时才查，默认 8% 档下"删了 ID 但没超阈值"就无人过问。）
    ids_after = sku_ids(merged)
    lost, added = ids_before - ids_after, ids_after - ids_before
    if lost or added:
        raise SystemExit(
            "❌ 折叠改变了 车款ID 身份集合：丢失=%d 新增=%d（样例 丢失%s 新增%s），拒绝发布"
            % (len(lost), len(added), sorted(lost)[:5], sorted(added)[:5]))
    if max_drop_pct > MAX_DROP_PCT:
        print("   档位抬到 %.2f%%（调试轮）：凭据是上面无条件通过的身份不变式（车款ID %d 个前后相等）"
              % (max_drop_pct, len(ids_before)), file=sys.stderr)
    return merged


def build_filtered(rows: list) -> list:
    filtered = [row for row in rows if MD.filter_car(row)]
    return MD.narrow_pages_rows(filtered)


def _identity_keys(row: dict) -> tuple:
    """一个行的身份键集合：车款ID 优先，没有就退到 (归一车系, 年款, 归一车型名称)。
    返回**元组的元组**：一行可能同时代表多种可比对身份，任一命中即算"同一个身份"。"""
    sku = str(row.get("车款ID", "") or "").strip()
    keys = []
    year = str(row.get("年款", "") or "").strip()
    price = str(MD._price_norm(row.get("官方指导价")) or "")
    if sku and sku != "-":
        # ID 键必须带**年款与归一价**（评审 E③）：折叠第一遍的键就是
        # `("sku", 车款ID, 年款, 价格)`，只按 ID 判"同一身份"会把
        # 同 ID 的不同年款/不同价的两行当成一行 ⇒ 已发布的那一行在并集里被当作
        # "已经有了"而不再补回，发布面被悄悄缩小（违反本流水线的"发布防缩小"原则）。
        keys.append(("sku", sku, year, price))
    # 键必须与折叠**同一把尺子**：用系统自己的 _series_norm_key / normalize_match_text。
    # 用原始串 lower/strip 会永不命中——折叠本身会改写名称（取最长写法、剥后缀），
    # 于是"其实已经折进去的那一行"被当成不同身份再补回来（评审 B4：实测补回 98 行里
    # 96 行是同车系同年款同价、只差名称写法的重复 SKU，重复回到用户面上）。
    series = str(MD._series_norm_key(str(row.get("车系", "") or "")) or "")
    name = str(MD.normalize_match_text(str(row.get("车型名称", "") or "")) or "")
    year = str(row.get("年款", "") or "").strip()
    if series and name:
        # 文本键也要带价格（评审 G⑩）：只比 (车系,年款,名称) 时，**同名称不同价**的已发布行
        # 会被文本键判成"已经有了"而不再补回——SKU 键补了年款/价也没用，`any(k not in seen)`
        # 任一命中即算同一身份。价格用 `_price_norm`，合并串 `40.5万|40.50万` 与 `40.5万` 同值。
        keys.append(("txt", series, year, price, name))
    return tuple(keys)


def union_filtered(inherited: list, rebuilt: list, raw_rebuilt: list) -> list:
    """发布面 filtered 的重建 = **现口径重算 ∪ 已发布行**，一个已发布身份都不许丢。

    为什么要并集而不是二选一（监工 2026-10-16 实测）：
    · 只折 inherited（旧行为）：`易车上市状态` 被 `narrow_pages_rows` 裁掉 ⇒
      发布门禁恒判不合格 ⇒ **整源 5069 行永远回不来**，重折救不了已删的行；
    · 只用重算（天真修法）：现网 filtered 里有 3 个身份（车款ID 70672/70687/72803，
      道朗格 YUKON育空、Lorinser 星际战车）在"现口径重算"里会被 `autohome_publish_identity_valid`
      拒掉（它们是在那道闸之前发布的），重算会**悄悄缩小发布面**，违反本流水线自己的
      "发布防缩小"原则。
    ⇒ 重算负责"把被误删的整源找回来"，inherited 负责"已发布身份一个不丢"。

    "一个不丢"必须按**折前的行集**判，不能按折后的判（10-22 r39755657893 实测：
    `现口径重算 17244 行 ｜ 从已发布面补回 155 行` ⇒ 宽面 17244、展示面 17399，
    差的 155 行全是无 车款ID 的懂车帝行，终验闸 V8 因此红）。`seen` 只吃 `rebuilt`（折后）时，
    "宽面已经把这一行折进了同簇的另一行"和"重算把这一行丢了"两件事长得一模一样，
    于是宽面刚判完的重复又被原样补回用户面。
    ⇒ 判据是 `raw_rebuilt`：同一套 `filter_car`+`narrow_pages_rows`、但**没跑折叠**的行集。
      折前就在 ⇒ 那是折叠的结果，不补回；折前就不在 ⇒ 那是筛选/身份闸的结果，补回。

    为什么不是"并集之后再折一遍窄面"（同轮实测）：对 17399 行的窄面补跑
    `dedupe_merged_rows` 折掉 258 行 = 该折的 155 继承行 + **103 行宽面刻意分开的行**
    （`narrow_pages_rows` 裁掉了冲突闸要看的列 ⇒ 同一把尺在窄面上是瞎的）。
    那一改会少 103 行真不同款，是把两个面对齐的代价换成把用户面折错。
    """
    from copy import deepcopy
    from publish_observation_lineage import filtered_fact_identity

    # Preserve observed configured facts only for one exact same identity/SKU/
    # year/price/source target. Never overwrite a current value or guess among
    # conflicting observations. Work on copied rows; caller inputs stay intact.
    out = [dict(row) for row in rebuilt]
    by_identity = defaultdict(list)
    for index, row in enumerate(out):
        identity = filtered_fact_identity(row)
        if identity is not None:
            by_identity[identity].append(index)
    proposals = {}
    for original in inherited:
        identity = filtered_fact_identity(original)
        targets = by_identity.get(identity, [])
        if not targets:
            continue
        for field in MD.resolve_pages_columns([original]):
            if field not in original or all(field in out[index] for index in targets):
                continue
            if len(targets) != 1:
                raise ValueError("ambiguous target for a retained configured fact")
            index = targets[0]
            encoded = json.dumps(original[field], ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":"), allow_nan=False)
            key = (index, field)
            if key in proposals and proposals[key][0] != encoded:
                raise ValueError("conflicting retained configured fact values")
            proposals[key] = (encoded, deepcopy(original[field]))
    for (index, field), (_, value) in proposals.items():
        out[index][field] = value
    seen = set()
    for row in rebuilt:
        seen.update(_identity_keys(row))
    pre_fold = set()
    for row in raw_rebuilt:
        pre_fold.update(_identity_keys(row))
    kept = folded_away = 0
    for row in inherited:
        keys = _identity_keys(row)
        if not keys or any(k in seen for k in keys):
            continue
        if any(k in pre_fold for k in keys):
            folded_away += 1        # 宽面已把它折进同簇行：补回来就是给用户面制造重复
            continue
        out.append(row)
        seen.update(keys)
        kept += 1
    print("   filtered 重建：现口径重算 %d 行 ｜ 补回 %d 行（折前就没有=筛选/身份闸丢的）"
          "｜ 不补回 %d 行（折前就有=宽面已折进同簇行）｜ 合计 %d 行"
          % (len(rebuilt), kept, folded_away, len(out)), file=sys.stderr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged", required=True, type=Path, help="上一轮 merged_<date>.json（即发布面 latest）")
    ap.add_argument("--filtered", type=Path,
                    help="上一轮 filtered_cars_<date>.json（发布面 filtered）。给了就**只对它去重**"
                         "（保住现网发布行集不变），不给才用 filter_car 从合并结果重算")
    ap.add_argument("--date", default="", help="输出文件名里的日期；留空则从文件名里认")
    ap.add_argument("--outdir", default=".", type=Path)
    ap.add_argument("--max-drop-pct", type=float, default=MAX_DROP_PCT)
    ap.add_argument("--source-identity-evidence", type=Path,
                    help="Retained exact source excerpts; reconcile raw identities before dedupe without network access")
    args = ap.parse_args()
    identity_evidence = None
    identity_changes = {"merged": 0, "filtered": 0}
    if args.source_identity_evidence:
        from reconcile_source_identities import reconcile
        identity_evidence = json.loads(args.source_identity_evidence.read_bytes())

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

    if identity_evidence is not None:
        rows, changes = reconcile(rows, identity_evidence)
        identity_changes["merged"] = len(changes)
    before_groups, before_rows = dup_id_groups(rows)
    merged = remerge(rows, args.max_drop_pct)
    after_groups, after_rows = dup_id_groups(merged)

    if args.filtered:
        # 重建 = 现口径重算 ∪ 已发布行（两个职责各管一半，见 union_filtered 的注释）。
        with args.filtered.open(encoding="utf-8") as handle:
            old_filtered = json.load(handle)
        if identity_evidence is not None:
            old_filtered, changes = reconcile(old_filtered, identity_evidence)
            identity_changes["filtered"] = len(changes)
        f_before_groups, _ = dup_id_groups(old_filtered)
        inherited = remerge(old_filtered, args.max_drop_pct)
        rebuilt = build_filtered(merged)
        # 折前基准：同一套 filter+narrow，但没跑折叠——用来分清"被宽面折掉"与"被重算丢掉"。
        raw_rebuilt = build_filtered(rows)
        filtered = union_filtered(inherited, rebuilt, raw_rebuilt)
        lost = sku_ids(inherited) - sku_ids(filtered)
        if lost:
            raise SystemExit("❌ 重建后的 filtered 丢了已发布身份 %d 个（样例 %s），拒绝发布"
                             % (len(lost), sorted(lost)[:5]))
        gained = sku_ids(rebuilt) - sku_ids(inherited)
        print("   filtered 身份：已发布 %d 个全保住 ｜ 重算找回 %d 个（被误删的整源）"
              % (len(sku_ids(inherited)), len(gained)), file=sys.stderr)
        # 两面对齐读数（终验闸 V8 的链内侧对照；这里只报数，判定在 V8 那把独立的尺上）：
        # 展示面里没有任何一行是宽面**折前**行集里没有的身份 ⇒ 展示面不再带宽面已判过的重复。
        pre_keys = set()
        for row in rows:
            pre_keys.update(_identity_keys(row))
        orphan = [row for row in filtered if not any(k in pre_keys for k in _identity_keys(row))]
        print("   两面对齐：展示面 %d 行 ｜ 其中身份在宽面折前行集里找不到的 = %d 行%s"
              % (len(filtered), len(orphan),
                 "" if not orphan else "（样例 %s）" % [str(r.get("车型名称"))[:20] for r in orphan[:3]]),
              file=sys.stderr)
        face_orphans = len(orphan)
    else:
        filtered = build_filtered(merged)
        f_before_groups = None
        face_orphans = None
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
        "premerge_source_identity_changes": identity_changes,
        "merged_rows_before": len(rows),
        "merged_rows_after": len(merged),
        "removed_by_sku_dedupe": len(rows) - len(merged),
        "filtered_rows_before": len([r for r in rows if MD.filter_car(r)]),
        "filtered_rows_after": len(filtered),
        "filtered_dup_sku_groups_before": f_before_groups,
        "filtered_dup_sku_groups_after": f_after_groups,
        "filtered_rows_not_in_wide_prefold": face_orphans,
        "dup_sku_groups_before": before_groups,
        "dup_sku_groups_after": after_groups,
        "dup_sku_rows_before": before_rows,
        "dup_sku_rows_after": after_rows,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
