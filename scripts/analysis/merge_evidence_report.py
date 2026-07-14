#!/usr/bin/env python3
"""生成双源合并证据报告。优先使用传入的两源 JSON；不可用时分析仓库已发布合并数据。"""
import argparse, json, re
from collections import Counter, defaultdict
from pathlib import Path

EXCLUDED = {"问界", "智界", "享界", "尚界", "尊界"}
SYNONYMS = {"标配":"支持", "有":"支持", "●":"支持", "是":"支持", "选配":"选装", "无":"-", "不支持":"-"}

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def norm(v):
    return re.sub(r"\s+", "", str(v or "")).lower()

def key(row):
    return (norm(row.get("品牌")), norm(row.get("车系")), norm(row.get("年款")), norm(row.get("车型名称")))

def source(row):
    return str(row.get("数据来源") or row.get("核验来源") or "")

def choose_samples(rows):
    groups=defaultdict(list)
    for r in rows:
        b=str(r.get("品牌") or "").strip()
        if b and b not in EXCLUDED:
            groups[b].append(r)
    picked=[]
    for brand, items in sorted(groups.items(), key=lambda kv:(-len({x.get('车系') for x in kv[1]}), kv[0])):
        sources=Counter()
        for item in items:
            value=source(item)
            atomic=[name for name in ("汽车之家", "懂车帝") if name in value]
            sources.update(atomic or [value or "未知来源"])
        if len({x.get('车系') for x in items}) >= 2 and sum(sources.values()) >= 4:
            picked.append((brand, items[:30], dict(sources)))
        if len(picked) >= 4:
            break
    return picked

def analyze(rows):
    picked=choose_samples(sorted(rows, key=lambda r:(norm(r.get('品牌')), norm(r.get('车系')), norm(r.get('年款')), norm(r.get('车型名称')))))
    attr_counter=Counter(); conflict_counter=Counter(); synonym_hits=Counter(); candidates=[]
    normalized_synonyms={norm(x) for x in SYNONYMS}
    for brand, items, sources in picked:
        for r in items:
            vals={}
            for k,v in r.items():
                if k in {"数据来源","品牌","车系","车系ID","车型名称","年款"}: continue
                text=str(v or "").strip()
                if not text or text=="-": continue
                attr_counter[k]+=1
                parts=text.split('|')
                if len(parts)>1 or "汽车之家:" in text or "懂车帝:" in text:
                    conflict_counter[k]+=1
                for p in parts:
                    value=p.split(':', 1)[-1]
                    if norm(value) in normalized_synonyms:
                        synonym_hits[k]+=1
        candidates.append({"brand":brand,"rowCount":len(items),"seriesCount":len({x.get('车系') for x in items}),"sourceEvidence":sources,"examples":[{"车系":x.get('车系'),"年款":x.get('年款'),"车型名称":x.get('车型名称'),"数据来源":x.get('数据来源')} for x in items[:8]]})
    return {"inputRows":len(rows),"sampleBrands":candidates,"supportedValueRules":SYNONYMS,"topAttributes":attr_counter.most_common(25),"conflictEvidence":conflict_counter.most_common(25),"synonymEvidence":synonym_hits.most_common(25),"rejectionRules":["同车系同年款存在多个型号时按 token/年款/能源/级别评分；低于阈值不合并","最高分并列时视为歧义并保留单源","真正不同的非空配置值保留为 汽车之家:值|懂车帝:值"]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input', default='data/merged_20260622.json')
    ap.add_argument('--output', default='docs/analysis/merge_evidence_report.json')
    args=ap.parse_args()
    report=analyze(load(args.input))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({"output":args.output,"inputRows":report['inputRows'],"sampleBrands":[x['brand'] for x in report['sampleBrands']]}, ensure_ascii=False))
if __name__=='__main__': main()
