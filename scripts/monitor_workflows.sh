#!/bin/bash
# 工作流+Pages自动监控，发现问题自动调用OpenCode修复
# 仅首次运行起的7天内有效，每天运行一次
# 用法: bash scripts/monitor_workflows.sh
set -euo pipefail

cd "$(dirname "$0")/.."
command -v gh >/dev/null 2>&1 || { echo "错误：未安装 gh CLI"; exit 1; }

# 7天自动过期
START_MARKER="/tmp/workflow_monitor_start"
if [ ! -f "$START_MARKER" ]; then date +%Y%m%d > "$START_MARKER"; fi
START_DATE=$(cat "$START_MARKER")
DAYS_ELAPSED=$(( ($(date +%s) - $(date -d "$START_DATE" +%s)) / 86400 ))
if [ $DAYS_ELAPSED -ge 7 ]; then
    echo "[$(date)] 监控已运行 $DAYS_ELAPSED 天，超过7天限制，自动停止"
    rm -f "$START_MARKER"
    exit 0
fi
echo "[$(date)] 监控第 $((DAYS_ELAPSED + 1)) 天 (最多7天)"

CURRENT_MONTH=$(date +%Y%m)
TODAY=$(date +%Y%m%d)
AUTO_CMD="opencode run --project /root/crawl_cars"

# ── 1. 检查爬虫是否都在跑/已完成 ──
AH_RUNNING=$(gh run list --workflow=crawl-autohome.yml --limit=1 --json status -q '.[0].status' 2>/dev/null || echo "unknown")
DCD_RUNNING=$(gh run list --workflow=crawl-dongchedi.yml --limit=1 --json status -q '.[0].status' 2>/dev/null || echo "unknown")
AH_COMPLETE=$(gh run list --workflow=crawl-autohome.yml --limit=1 --json conclusion -q '.[0].conclusion' 2>/dev/null || echo "unknown")
DCD_COMPLETE=$(gh run list --workflow=crawl-dongchedi.yml --limit=1 --json conclusion -q '.[0].conclusion' 2>/dev/null || echo "unknown")

# ── 2. 检查最新 artifact ──
AH_ARTIFACT=$(gh api repos/Fatty911/crawl_cars/actions/artifacts --jq "[.artifacts[] | select(.name|test(\"autohome-data-${CURRENT_MONTH}\"))] | max_by(.created_at) | {name,size_kb:(.size_in_bytes/1024|floor),created_at}" 2>/dev/null || echo "none")
DCD_ARTIFACT=$(gh api repos/Fatty911/crawl_cars/actions/artifacts --jq "[.artifacts[] | select(.name|test(\"dongchedi-data-${CURRENT_MONTH}\"))] | max_by(.created_at) | {name,size_kb:(.size_in_bytes/1024|floor),created_at}" 2>/dev/null || echo "none")

# ── 3. 检查 Pages manifest ──
MANIFEST=$(curl -s --max-time 10 http://cars.jiucai.eu.org/data/manifest.json 2>/dev/null || echo "{}")
PAGE_DATE=$(echo "$MANIFEST" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('date','?'))" 2>/dev/null || echo "?")
PAGE_ROWS=$(echo "$MANIFEST" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('rowCount','?'))" 2>/dev/null || echo "?")

# ── 4. 诊断并自动修复 ──
ISSUES=""

# 爬虫失败
if [ "$AH_COMPLETE" = "failure" ]; then
    ISSUES="$ISSUES\n- 汽车之家爬虫失败，需要查看日志修复"
fi
if [ "$DCD_COMPLETE" = "failure" ]; then
    ISSUES="$ISSUES\n- 懂车帝爬虫失败，需要查看日志修复"
fi

# 没有当月artifact → 需要触发爬虫
if [ "$AH_ARTIFACT" = "none" ] || echo "$AH_ARTIFACT" | grep -q '"size_kb":0'; then
    ISSUES="$ISSUES\n- 汽车之家当月无有效artifact，需检查done标记并触发爬虫"
fi

# 懂车帝长期以来没产出（artifact超过7天）
DCD_AGE_DAYS=999
if [ "$DCD_ARTIFACT" != "none" ]; then
    DCD_DATE=$(echo "$DCD_ARTIFACT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('created_at','2000-01-01')[:10])" 2>/dev/null || echo "2000-01-01")
    DCD_EPOCH=$(date -d "$DCD_DATE" +%s 2>/dev/null || echo 0)
    NOW_EPOCH=$(date +%s)
    DCD_AGE_DAYS=$(( (NOW_EPOCH - DCD_EPOCH) / 86400 ))
    if [ $DCD_AGE_DAYS -gt 3 ]; then
        ISSUES="$ISSUES\n- 懂车帝最新artifact已${DCD_AGE_DAYS}天未更新"
    fi
fi

# Pages日期非今天 → 合并分析没跑
if [ "$PAGE_DATE" != "$TODAY" ] && [ "$PAGE_DATE" != "?" ]; then
    ISSUES="$ISSUES\n- Pages数据日期${PAGE_DATE}≠${TODAY}，合并分析可能未生成新Release"
fi

# ── 5. 自动修复 ──
if [ -n "$ISSUES" ]; then
    echo "[$(date)] 发现问题:" 
    echo -e "$ISSUES"
    
    FIX_PROMPT="自动诊断并修复以下crawl_cars项目问题：$ISSUES。请：1)查看工作流日志定位根因 2)修复代码或配置 3)如有必要重新触发工作流。遵循AGENTS.md规则，修改代码前必须多模型评审。"
    
    echo "[$(date)] 调用 OpenCode 自动修复..."
    cd /root/crawl_cars
    $AUTO_CMD "$FIX_PROMPT" 2>&1 | tail -20 || echo "[$(date)] opencode run 调用失败"
else
    echo "[$(date)] 一切正常：爬虫运行中/已完成，artifact已更新，Pages数据为${PAGE_DATE}"
fi
