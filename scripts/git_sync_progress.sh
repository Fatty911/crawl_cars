#!/usr/bin/env bash
set -euo pipefail

REMOTE_URL="${1:?remote url required}"
MAX_ATTEMPTS="${2:-6}"
BRANCH="${GIT_SYNC_BRANCH:-main}"

# 检测可用代理
PROXY_URL="${https_proxy:-${HTTPS_PROXY:-}}"
ORIGINAL_HTTP_PROXY="${HTTP_PROXY:-}"
ORIGINAL_HTTPS_PROXY="${HTTPS_PROXY:-}"
ORIGINAL_ALL_PROXY="${ALL_PROXY:-}"
ORIGINAL_LOWER_HTTP_PROXY="${http_proxy:-}"
ORIGINAL_LOWER_HTTPS_PROXY="${https_proxy:-}"
ORIGINAL_LOWER_ALL_PROXY="${all_proxy:-}"

# 清除 git 代理配置
clear_proxy() {
  git config --unset http.proxy 2>/dev/null || true
  git config --unset https.proxy 2>/dev/null || true
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
}

# 设置代理
set_proxy() {
  if [ -n "$PROXY_URL" ]; then
    git config http.proxy "$PROXY_URL"
    git config https.proxy "$PROXY_URL"
    export HTTP_PROXY="${ORIGINAL_HTTP_PROXY:-$PROXY_URL}"
    export HTTPS_PROXY="${ORIGINAL_HTTPS_PROXY:-$PROXY_URL}"
    export http_proxy="${ORIGINAL_LOWER_HTTP_PROXY:-$PROXY_URL}"
    export https_proxy="${ORIGINAL_LOWER_HTTPS_PROXY:-$PROXY_URL}"
    if [ -n "$ORIGINAL_ALL_PROXY" ]; then
      export ALL_PROXY="$ORIGINAL_ALL_PROXY"
    fi
    if [ -n "$ORIGINAL_LOWER_ALL_PROXY" ]; then
      export all_proxy="$ORIGINAL_LOWER_ALL_PROXY"
    fi
    echo "[git-sync] 使用代理: $PROXY_URL"
  else
    echo "[git-sync] 无可用代理，使用直连"
  fi
}

# 尝试同步（pull + push）
rebase_in_progress() {
  [ -d "$(git rev-parse --git-path rebase-merge)" ] || [ -d "$(git rev-parse --git-path rebase-apply)" ]
}

resolve_rebase_conflicts() {
  local conflicts
  conflicts="$(git diff --name-only --diff-filter=U || true)"
  if [ -z "$conflicts" ]; then
    return 1
  fi

  echo "[git-sync] 检测到冲突，尝试合并进度文件..."
  while IFS= read -r path; do
    [ -z "$path" ] && continue
    if [[ "$path" == "progress.json" || "$path" == "dongchedi/progress.json" ]]; then
      local ours theirs
      ours="$(mktemp)"
      theirs="$(mktemp)"
      git show ":2:$path" > "$ours" 2>/dev/null || echo "{}" > "$ours"
      git show ":3:$path" > "$theirs" 2>/dev/null || echo "{}" > "$theirs"
      python custom_scripts/merge_progress_json.py "$path" "$ours" "$theirs"
      rm -f "$ours" "$theirs"
      git add "$path"
      echo "[git-sync] 已合并 $path"
    else
      echo "[git-sync] 非进度文件冲突 $path，保留当前提交版本"
      git checkout --theirs "$path" 2>/dev/null || true
      git add "$path" 2>/dev/null || true
    fi
  done <<< "$conflicts"

  return 0
}

finish_rebase() {
  local guard=0
  while rebase_in_progress; do
    guard=$((guard + 1))
    if [ "$guard" -gt 20 ]; then
      echo "[git-sync] rebase 状态处理超过 20 次，放弃" >&2
      return 1
    fi

    if git status --porcelain 2>/dev/null | grep -q "^UU\|^AA\|^DD"; then
      resolve_rebase_conflicts || return 1
    elif ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
      git add -A
    fi

    if GIT_EDITOR=true git rebase --continue; then
      continue
    fi

    if git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null; then
      echo "[git-sync] 当前 rebase 提交为空，执行 rebase --skip"
      GIT_EDITOR=true git rebase --skip || return 1
      continue
    fi

    return 1
  done
  return 0
}

print_git_failure() {
  local label="$1"
  local log_file="$2"
  echo "[git-sync] $label 失败，最近日志:" >&2
  sed -E 's#https://[^/@]+(:[^/@]+)?@github.com/#https://***@github.com/#g' "$log_file" | tail -n 40 >&2 || true
}

run_git_with_log() {
  local label="$1"
  shift
  local log_file
  log_file="$(mktemp)"
  if "$@" >"$log_file" 2>&1; then
    rm -f "$log_file"
    return 0
  fi
  print_git_failure "$label" "$log_file"
  rm -f "$log_file"
  return 1
}

try_sync() {
  # stash 未提交的更改
  git stash push -m "sync-progress-stash-$(date +%s)" 2>/dev/null || true

  # 尝试 fetch + rebase，失败时打印真实原因，避免只看到 pull --rebase 失败。
  if run_git_with_log "fetch" git fetch --no-tags "$REMOTE_URL" "$BRANCH"; then
    if run_git_with_log "rebase" git rebase FETCH_HEAD; then
      if run_git_with_log "push" git push "$REMOTE_URL" "HEAD:$BRANCH"; then
        git stash pop 2>/dev/null || true
        echo "[git-sync] 同步成功"
        return 0
      fi
    fi
  else
    echo "[git-sync] fetch 失败"
  fi

  if rebase_in_progress; then
    finish_rebase || true
    # 重新尝试 push
    if run_git_with_log "push after rebase recovery" git push "$REMOTE_URL" "HEAD:$BRANCH"; then
      git stash pop 2>/dev/null || true
      echo "[git-sync] rebase 修复后同步成功"
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
