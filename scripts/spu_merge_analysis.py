#!/usr/bin/env python3
"""spu_merge_analysis.py — SKU 所在 SPU 归并分析（任务 3）

目标：列出全部单源数据，并对"多源车系（SPU）内的单源 SKU 行"做归并分析——
找出同一 SPU 中疑似与已有多源行对应、但因命名/签名差异未能配对的单源行，
输出归并候选清单（供修复链/人工判定），并给出每类差异的样例与数量。

用法:
  python scripts/spu_merge_analysis.py --data site/data/latest.json
      [--output docs/analysis/spu_merge_analysis.json] [--top 30]

输出:
  - 单源数据总量/车系级单源/SPU 内单源统计
  - 多源车系列表（各源行数）
  - 归并候选：SPU 内单源行 × 同 SPU 多源行的名称相似度匹配结果
    （token 归一后同核心词但字符串不同 → 疑似可归并）
  - top N 差异样例（每类差异给出具体名称对，供修复链参考）
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

# 身份列（不算属性，归并分析时排除）
_IDENTITY_KEYS = {
    "品牌", "车系", "车系ID", "车型名称", "年款", "车款ID", "数据来源",
    "上市时间", "官方指导价", "厂商指导价", "经销商参考价", "交叉核验", "合并匹配置信度",
}

_SPACE_RE = re.compile(r"\s+")
_UNIT_RE = re.compile(r"[\(\[\（\[]?(\d+(?:\.\d+)?)\s*(?:km|kw|kwh|l|kg|mm|inch|吋|寸|座|个|万元|万|元)[\)\]\）\]]?", re.I)


def _norm_token(text: str) -> str:
    """归一化：去空白、统一全半角。"""
    t = _SPACE_RE.sub("", text)
    t = t.replace("（", "(").replace("）", ")").replace("【", "[").replace("】", "]")
    return t


def _core_tokens(name: str) -> set[str]:
    """提取名称核心 token（保留型号词与带单位数值属性，不拆英文连字符标识）。

    - 去年款前缀（2023款/23款）
    - 只提取带单位的数值属性（125km/671km/2.0T/6座）——裸数字（i8 的 8、H10 的 10）不提取
    - 型号词按空白/括号切分（GT-Line 保持完整），不过滤"款/版/型"等有效区分词
    """
    t = name.replace("（", "(").replace("）", ")").replace("【", "[").replace("】", "]")
    t = re.sub(r"(?:20\d{2}款?|\d{2}款)", "", t)
    tokens: set[str] = set()
    for m in re.finditer(r"\d+(?:\.\d+)?(?:km|kw|kwh|l|kg|mm|t|寸|吋|座|个)", t, re.I):
        tokens.add(m.group(0).lower())
    for p in re.split(r"[()\[\]（）【】\s]+", t):
        p = p.strip()
        if len(p) < 2:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?(?:km|kw|kwh|l|kg|mm|t|寸|吋|座|个)", p, re.I):
            continue  # 带单位数值（已由数值 token 覆盖）
        if re.fullmatch(r"\d+(?:\.\d+)?", p):
            continue  # 裸数字（i8 的 8 / H10 的 10）——不提取，防虚高配对
        tokens.add(p.lower())
    return tokens


_NUM_TOKEN_RE = re.compile(r"^\d+(?:\.\d+)?[a-z]*$")


def _token_score(stokens: set[str], mtokens: set[str]) -> float:
    """token 匹配分：相等或包含关系算命中；数值属性（125km/671km）命中加权。

    分母 = 双方 token 总数，避免 token 少时虚高（'四驱高性能' vs '后驱长续航'
    无重叠应为 0，而非 1.0）。
    """
    if not stokens or not mtokens:
        return 0.0
    hits = 0
    for s in stokens:
        for m in mtokens:
            if s == m or s in m or m in s:
                hits += 2 if (_NUM_TOKEN_RE.match(s) and _NUM_TOKEN_RE.match(m)) else 1
                break
    total = len(stokens) + len(mtokens)
    return hits / total if total else 0.0


def _source_names(source: str) -> list[str]:
    """拆出源列表：'仅懂车帝'→['懂车帝']；'汽车之家+懂车帝'→['汽车之家','懂车帝']。"""
    s = str(source).replace("仅", "").replace("＋", "+").replace("、", "+")
    return [x.strip() for x in s.split("+") if x.strip()]


def _is_single(row: dict) -> bool:
    """单源判定：数据来源不含多源分隔符（+ 或 、）。交叉核验是前端动态生成，数据文件里为空。"""
    src = str(row.get("数据来源") or "").strip()
    if not src:
        return False
    return "+" not in src and "、" not in src


def analyze(rows: list[dict], top: int = 30) -> dict:
    by_series: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        series = str(row.get("车系") or "").strip()
        if not series:
            continue
        by_series[series].append(row)

    total_single = 0
    series_only_single = 0        # 整系单源
    spu_inner_single = 0          # 多源车系内的单源行
    multi_series: list[dict] = []
    merge_candidates: list[dict] = []
    diff_samples: dict[str, list[dict]] = defaultdict(list)

    for series, srows in by_series.items():
        src_rows: dict[str, list[dict]] = defaultdict(list)
        for r in srows:
            for src in _source_names(str(r.get("数据来源") or "")):
                src_rows[src].append(r)
        sources = set(src_rows.keys())
        single_rows = [r for r in srows if _is_single(r)]
        total_single += len(single_rows)
        if len(sources) <= 1:
            series_only_single += len(srows)
            continue
        # 多源车系：SPU 内单源行 → 归并分析
        spu_inner_single += len(single_rows)
        multi_series.append({
            "series": series,
            "sources": sorted(sources),
            "rows": len(srows),
            "single_rows": len(single_rows),
        })
        if not single_rows:
            continue
        # 归并候选：单源行 vs 同 SPU 多源行，核心 token 交集
        multi_rows = [r for r in srows if not _is_single(r)]
        for sr in single_rows:
            sname = str(sr.get("车型名称") or "")
            stokens = _core_tokens(sname)
            best = None
            best_score = 0
            for mr in multi_rows:
                mname = str(mr.get("车型名称") or "")
                mtokens = _core_tokens(mname)
                score = _token_score(stokens, mtokens)
                if score > best_score:
                    best_score = score
                    best = mr
            if best and best_score >= 0.3 and _norm_token(sname) != _norm_token(str(best.get("车型名称") or "")):
                # 年款一致性约束：不同年款不是同一 SKU（2024款 vs 2026款 不得配对）
                sy = str(sr.get("年款") or "").strip()
                my = str(best.get("年款") or "").strip()
                if sy and my and sy != my:
                    continue
                key = "name_diff"
                cand = {
                    "series": series,
                    "single_row": sname,
                    "single_source": "、".join(_source_names(str(sr.get("数据来源") or ""))),
                    "multi_row": str(best.get("车型名称") or ""),
                    "multi_source": "、".join(_source_names(str(best.get("数据来源") or ""))),
                    "score": round(best_score, 2),
                    "single_year": str(sr.get("年款") or ""),
                    "multi_year": str(best.get("年款") or ""),
                }
                merge_candidates.append(cand)
                diff_samples[key].append(cand)
                if len(diff_samples[key]) > 5:
                    diff_samples[key].pop(0)  # 每类保留最近 5 个样例

    multi_series.sort(key=lambda x: -x["single_rows"])
    return {
        "total_rows": len(rows),
        "total_single": total_single,
        "series_only_single": series_only_single,
        "spu_inner_single": spu_inner_single,
        "total_series": len(by_series),
        "multi_series_count": len(multi_series),
        "merge_candidate_count": len(merge_candidates),
        "top_multi_series": multi_series[:top],
        "merge_candidates_sample": merge_candidates[:50],
        "diff_samples": {k: v for k, v in diff_samples.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs/analysis/spu_merge_analysis.json"))
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    with args.data.open(encoding="utf-8") as f:
        rows = json.load(f)
    report = analyze(rows, top=args.top)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"总行数 {report['total_rows']} | 单源 {report['total_single']} "
        f"（车系级 {report['series_only_single']} + SPU 内 {report['spu_inner_single']}）"
    )
    print(f"多源车系 {report['multi_series_count']} 个，SPU 内归并候选 {report['merge_candidate_count']} 对")
    for k, samples in report["diff_samples"].items():
        print(f"\n差异类型 [{k}] 样例（共 {len(samples)} 个保留样例）:")
        for s in samples[-5:]:
            print(f"  {s['series']} | 单源[{s['single_source']}] {s['single_row']}（{s['single_year']}）")
            print(f"    vs 多源[{s['multi_source']}] {s['multi_row']}（{s['multi_year']}） score={s['score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
