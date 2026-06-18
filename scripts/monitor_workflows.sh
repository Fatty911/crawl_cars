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
fix_applied=false

# 防抖辅助函数：检查标记文件是否在24h内，空/损坏文件安全处理
throttle_24h() {
    local marker="$1"
    if [ ! -f "$marker" ]; then return 1; fi
    local ts
    ts=$(cat "$marker" 2>/dev/null) || return 1
    case "$ts" in
        ''|*[!0-9]*) return 1 ;;  # 空或非纯数字→视为无效
    esac
    [ $(($(date +%s) - ts)) -lt 86400 ]
}

# 修复1: 爬虫标记完成但artifact太小 → 删标记重新触发（24h防抖）
autohome_done=$(ls crawl_state/autohome_*_H2.done 2>/dev/null | head -1)
if [ -n "$autohome_done" ] && [ "$AH_ARTIFACT" != "none" ]; then
    ah_kb=$(echo "$AH_ARTIFACT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('size_kb',0))" 2>/dev/null || echo 0)
    if [ "$ah_kb" -lt 200 ]; then
        LAST_TRIGGER="/tmp/ah_fix_trigger"
        if throttle_24h "$LAST_TRIGGER"; then
            :
        else
            echo "[$(date)] 汽车之家done标记存在但artifact仅${ah_kb}KB→删除标记重新触发"
            rm -f crawl_state/autohome_*_H*.done
            gh workflow run crawl-autohome.yml
            date +%s > "$LAST_TRIGGER"
            fix_applied=true
        fi
fi

# 修复2: 爬虫失败/取消 → 重新触发（24h防抖）
if [ "$AH_COMPLETE" = "failure" ] || [ "$AH_COMPLETE" = "cancelled" ]; then
    LAST_TRIGGER="/tmp/ah_fail_trigger"
    if ! throttle_24h "$LAST_TRIGGER"; then
        echo "[$(date)] 汽车之家爬虫${AH_COMPLETE}→重新触发"
        gh workflow run crawl-autohome.yml
        date +%s > "$LAST_TRIGGER"
        fix_applied=true
    fi
fi
if [ "$DCD_COMPLETE" = "failure" ] || [ "$DCD_COMPLETE" = "cancelled" ]; then
    LAST_TRIGGER="/tmp/dcd_fail_trigger"
    if ! throttle_24h "$LAST_TRIGGER"; then
        echo "[$(date)] 懂车帝爬虫${DCD_COMPLETE}→重新触发"
        gh workflow run crawl-dongchedi.yml
        date +%s > "$LAST_TRIGGER"
        fix_applied=true
    fi
fi

# 修复3: artifact超3天未更新且无运行中爬虫 → 重新触发（24h内不重复触发）
if [ "$DCD_AGE_DAYS" -gt 3 ] && [ "$DCD_RUNNING" != "in_progress" ] && [ "$DCD_RUNNING" != "queued" ]; then
    LAST_TRIGGER="/tmp/dcd_last_trigger"
    if ! throttle_24h "$LAST_TRIGGER"; then
        echo "[$(date)] 懂车帝artifact${DCD_AGE_DAYS}天未更新→重新触发"
        gh workflow run crawl-dongchedi.yml
        date +%s > "$LAST_TRIGGER"
        fix_applied=true
    fi
fi

# 修复4: 爬虫都完成且有artifact → 触发合并分析（24h防抖）
ah_size=$(echo "$AH_ARTIFACT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('size_kb',0))" 2>/dev/null || echo 0)
dcd_size=$(echo "$DCD_ARTIFACT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('size_kb',0))" 2>/dev/null || echo 0)
if [ "$ah_size" -gt 100 ] && [ "$dcd_size" -gt 1000 ] && [ "$PAGE_DATE" != "$TODAY" ]; then
    LAST_TRIGGER="/tmp/merge_trigger"
    if ! throttle_24h "$LAST_TRIGGER"; then
        echo "[$(date)] 两个爬虫都有数据但Pages未更新→触发合并分析"
        gh workflow run merge-and-filter.yml
        date +%s > "$LAST_TRIGGER"
        fix_applied=true
    fi
fi

if [ "$fix_applied" = true ]; then
    echo "[$(date)] 已自动修复，等待下次监控验证"
elif [ -n "$ISSUES" ]; then
    echo "[$(date)] 发现问题但无法自动修复，需人工介入:"
    echo -e "$ISSUES"
else
    echo "[$(date)] 一切正常"
fi
