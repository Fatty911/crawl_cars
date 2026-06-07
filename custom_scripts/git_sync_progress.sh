#!/usr/bin/env bash
set -euo pipefail

REMOTE_URL="${1:?remote url required}"
MAX_ATTEMPTS="${2:-6}"

# 检测可用代理
PROXY_URL="${https_proxy:-${HTTPS_PROXY:-}}"

# 清除 git 代理配置
clear_proxy() {
  git config --unset http.proxy 2>/dev/null || true
  git config --unset https.proxy 2>/dev/null || true
}

# 设置代理
set_proxy() {
  if [ -n "$PROXY_URL" ]; then
    git config http.proxy "$PROXY_URL"
    git config https.proxy "$PROXY_URL"
    echo "[git-sync] 使用代理: $PROXY_URL"
  else
    echo "[git-sync] 无可用代理，使用直连"
  fi
}

# 尝试同步（pull + push）
try_sync() {
  # stash 未提交的更改
  git stash push -m "sync-progress-stash-$(date +%s)" 2>/dev/null || true

  # 尝试 pull --rebase
  if git pull --rebase "$REMOTE_URL" 2>/dev/null; then
    # pull 成功，尝试 push
    if git push "$REMOTE_URL" 2>/dev/null; then
      git stash pop 2>/dev/null || true
      echo "[git-sync] 同步成功"
      return 0
    fi
    echo "[git-sync] push 失败"
  else
    echo "[git-sync] pull --rebase 失败"
  fi

  # 检查是否有冲突
  if git status --porcelain 2>/dev/null | grep -q "^UU\|^AA\|^DD"; then
    echo "[git-sync] 检测到冲突，使用远程版本解决..."
    git checkout --theirs . 2>/dev/null || true
    git add -A 2>/dev/null || true
    git rebase --continue 2>/dev/null || true
    # 重新尝试 push
    if git push "$REMOTE_URL" 2>/dev/null; then
      git stash pop 2>/dev/null || true
      echo "[git-sync] 冲突解决后同步成功"
      return 0
    fi
  fi

  # 清理状态
  git rebase --abort 2>/dev/null || true
  git stash pop 2>/dev/null || true
  return 1
}

# 主循环：交替尝试代理和直连
echo "[git-sync] 开始同步，最大重试次数: $MAX_ATTEMPTS"

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  echo "[git-sync] 第 $attempt/$MAX_ATTEMPTS 次尝试"

  # 奇数次尝试代理（如果有），偶数次尝试直连
  if [ $((attempt % 2)) -eq 1 ] && [ -n "$PROXY_URL" ]; then
    set_proxy
  else
    clear_proxy
    echo "[git-sync] 使用直连"
  fi

  if try_sync; then
    clear_proxy
    exit 0
  fi

  echo "[git-sync] 第 $attempt 次尝试失败"

  # 最后一次不等待
  if [ "$attempt" -lt "$MAX_ATTEMPTS" ]; then
    WAIT=$((RANDOM % 10 + 5))
    echo "[git-sync] 等待 ${WAIT}s 后重试..."
    sleep "$WAIT"
  fi
done

clear_proxy
echo "[git-sync] 同步进度失败，已重试 $MAX_ATTEMPTS 次" >&2
exit 1
