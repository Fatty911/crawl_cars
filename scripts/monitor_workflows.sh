#!/bin/bash
# 工作流+Pages自动监控，仅首次运行起的7天内有效
# 用法: bash scripts/monitor_workflows.sh
set -euo pipefail

cd "$(dirname "$0")/.."
command -v gh >/dev/null 2>&1 || { echo "错误：未安装 gh CLI"; exit 1; }

# 7天自动过期：记录首次运行日期，超过7天不再执行
START_MARKER="/tmp/workflow_monitor_start"
if [ ! -f "$START_MARKER" ]; then
    date +%Y%m%d > "$START_MARKER"
fi
START_DATE=$(cat "$START_MARKER")
DAYS_ELAPSED=$(( ($(date +%s) - $(date -d "$START_DATE" +%s)) / 86400 ))
if [ $DAYS_ELAPSED -ge 7 ]; then
    echo "监控已运行 $DAYS_ELAPSED 天，超过7天限制，自动停止"
    rm -f "$START_MARKER"
    exit 0
fi
echo "监控第 $((DAYS_ELAPSED + 1)) 天 (最多7天)"

CURRENT_MONTH=$(date +%Y%m)
REPORT="/tmp/workflow_monitor_$(date +%Y%m%d_%H%M).txt"
echo "=== 工作流监控 $(date '+%Y-%m-%d %H:%M:%S') ===" > "$REPORT"
cd /root/crawl_cars
echo "--- 爬虫状态 ---" >> "$REPORT"
gh run list --workflow=crawl-autohome.yml --limit=2 --json databaseId,conclusion,createdAt >> "$REPORT"
gh run list --workflow=crawl-dongchedi.yml --limit=2 --json databaseId,conclusion,createdAt >> "$REPORT"
echo "--- Artifact ---" >> "$REPORT"
gh api repos/Fatty911/crawl_cars/actions/artifacts --jq ".artifacts[] | select(.name|test(\"autohome-data-${CURRENT_MONTH}|dongchedi-data-${CURRENT_MONTH}\")) | {name,size_kb:(.size_in_bytes/1024|floor),created_at}" | head -6 >> "$REPORT"
echo "--- Pages (manifest) ---" >> "$REPORT"
curl -s http://cars.jiucai.eu.org/data/manifest.json 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(f'  日期:{d[\"date\"]}  总行:{d[\"rowCount\"]}  筛选:{d[\"filteredRowCount\"]}')
except: print('  manifest解析失败')
" >> "$REPORT" 2>/dev/null
echo "--- Pages (双源核验) ---" >> "$REPORT"
curl -s http://cars.jiucai.eu.org/data/latest.json 2>/dev/null | python3 -c "
import json,sys
try:
    data=json.load(sys.stdin)
    srcs={}
    for r in data: srcs[r.get('数据来源','?')]=srcs.get(r.get('数据来源','?'),0)+1
    print(f'  数据来源分布: {srcs}')
    print(f'  总行数: {len(data)}')
except: print('  数据解析失败')
" >> "$REPORT" 2>/dev/null
echo "--- 合并分析 ---" >> "$REPORT"
gh run list --workflow=merge-and-filter.yml --limit=2 --json databaseId,conclusion,createdAt >> "$REPORT"
cat "$REPORT"
