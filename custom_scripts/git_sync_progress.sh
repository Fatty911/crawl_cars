#!/usr/bin/env bash
set -euo pipefail

REMOTE_URL="${1:?remote url required}"
ATTEMPTS="${2:-3}"

for attempt in $(seq 1 "$ATTEMPTS"); do
  # stash 未提交的更改（如生成的数据文件），避免 rebase 冲突
  git stash push -m "sync-progress-stash-$attempt" 2>/dev/null || true

  if git pull --rebase "$REMOTE_URL" && git push "$REMOTE_URL"; then
    git stash pop 2>/dev/null || true
    exit 0
  fi

  git rebase --abort 2>/dev/null || true
  git stash pop 2>/dev/null || true

  if [ "$attempt" -eq "$ATTEMPTS" ]; then
    echo "同步进度失败，已重试 ${ATTEMPTS} 次" >&2
    exit 1
  fi

  sleep $((RANDOM % 20 + 10))
done
