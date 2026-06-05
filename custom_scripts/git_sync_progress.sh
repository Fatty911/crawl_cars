#!/usr/bin/env bash
set -euo pipefail

REMOTE_URL="${1:?remote url required}"
ATTEMPTS="${2:-3}"

for attempt in $(seq 1 "$ATTEMPTS"); do
  # stash 未提交的更改（如生成的数据文件），避免 rebase 冲突
  git stash push -m "sync-progress-stash-$attempt" 2>/dev/null || true

  if git pull --rebase "$REMOTE_URL" 2>/dev/null; then
    git push "$REMOTE_URL"
    git stash pop 2>/dev/null || true
    exit 0
  fi

  # rebase 失败时，检查是否有冲突需要解决
  if git status --porcelain | grep -q "^UU\|^AA\|^DD"; then
    echo "检测到冲突，使用远程版本解决..."
    # 对于 progress.json 等进度文件，使用远程版本（最新的进度）
    git checkout --theirs . 2>/dev/null || true
    git add -A
    git rebase --continue 2>/dev/null || true
    # 重新尝试 push
    if git push "$REMOTE_URL" 2>/dev/null; then
      git stash pop 2>/dev/null || true
      exit 0
    fi
  fi

  git rebase --abort 2>/dev/null || true
  git stash pop 2>/dev/null || true

  if [ "$attempt" -eq "$ATTEMPTS" ]; then
    echo "同步进度失败，已重试 ${ATTEMPTS} 次" >&2
    exit 1
  fi

  sleep $((RANDOM % 20 + 10))
done
