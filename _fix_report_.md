分支 `agent/54-codeberg-prep-retry`（代码提交 `be3f087`，本报告提交随分支头，基线 `main`@`ea2a67c`，起点 = #52 附件 bundle 的 `0dfb093`）｜推送状态 HTTP 403 ｜原因：容器凭据缺少 `repo-code:rw` scope（原文 `Your token does not have the repo-code:rw scope required to push to this repository.`）；PR API 同样 403（`Missing required scopes: repo-pr:rw`）。按 Issue §5 改走本 Issue 附件交付（bundle + patch），试 2 种凭据变体后停止推送，未反复重试。

# Issue #54 修复报告：Codeberg 段代理准备进重试（重试真正可达）+ 第四处令牌改走 askpass

**交付方式**: 推送被拒（403），改走 Issue #54 附件交付。附件 bundle 内 ref 为 `refs/heads/agent/54-codeberg-prep-retry`（HEAD = 本报告所在提交，内父含代码提交 `be3f087`），监工可 `git bundle verify` + `git fetch` 后直接复核。

**起点复用声明（未重新实现 #52）**: 本分支不是从 `main` 重做，而是 `git fetch <#52 附件 bundle> refs/heads/agent/52-codeberg-retry-all` 后以 `0dfb093` 为起点，在其上补本单两格。附件下载地址未抄进任何文件/提交说明/本报告。

---

## 1. 实际改动文件清单（4 个）

| 文件 | 改动 | 规模 |
|---|---|---|
| `.cnb.yml` | ① 两条链的 `发布到Codeberg Pages`：`setup_proxy_runtime.py` 由裸跑改为 3 次有界重试；② `crontab: 37 8 * * 0 / 失败诊断归档`：diag 回推令牌改走 `GIT_ASKPASS` | +45 / −5 行（两处编辑，均 ≤120 行最小替换） |
| `tests/test_codeberg_prep_reachable_and_no_token_url.py` | 新增（监工下发判据，原样落盘，`sha256=0ce1add9acafbb64c4884cd11985dfa03ccf9fcbc6e1be2c65580da7df4bb506`） | +137 行 |
| `apply_issue52.py` | 删除（过程脚本，不应长期留在 `main`） | −142 行 |
| `_fix_report_.md` | 本报告 | 覆盖为 #54 版 |

`git diff --stat`（`0dfb093` → `be3f087`）：

```
 .cnb.yml                                           |  45 ++++++-
 apply_issue52.py                                   | 142 ---------------------
 ...est_codeberg_prep_reachable_and_no_token_url.py | 137 ++++++++++++++++++++
 3 files changed, 179 insertions(+), 145 deletions(-)
```

### 格一：代理准备进有界重试（两份链拷贝同改）

改动前（`api_trigger` 与 `crontab: 5 8 1,16 * *` 各一份，`set -e` 下裸跑）：

```
: > /tmp/codeberg-proxy.env
python scripts/setup_proxy_runtime.py --github-env /tmp/codeberg-proxy.env --test-url https://codeberg.org
```

改动后（与既有 `CB_ATTEMPT` 循环同构：退避 + 耗尽 `exit 1`）：

```
: > /tmp/codeberg-proxy.env
# 代理准备自身会做 TLS 连通性探测，是第一条会抖的网络命令：
# 在 `set -e` 下必须与后面的预检/push 一样进有界重试，否则一抖就整段退出、后续循环一次都轮不到。
PREP_ATTEMPT=1
PREP_MAX_ATTEMPTS=3
while [ "$PREP_ATTEMPT" -le "$PREP_MAX_ATTEMPTS" ]; do
  if python scripts/setup_proxy_runtime.py --github-env /tmp/codeberg-proxy.env --test-url https://codeberg.org; then
    break
  fi
  echo "代理准备第 ${PREP_ATTEMPT} 次失败（TLS/代理抖动），退避后重试" >&2
  sleep $((PREP_ATTEMPT * 20))
  PREP_ATTEMPT=$((PREP_ATTEMPT + 1))
  if [ "$PREP_ATTEMPT" -gt "$PREP_MAX_ATTEMPTS" ]; then
    echo "代理准备在 ${PREP_MAX_ATTEMPTS} 次尝试后仍失败，本轮判红" >&2
    exit 1
  fi
done
```

语义：不吞失败（无 `|| true` / `|| exit 0`），3 次耗尽仍 `exit 1`；`setup_proxy_runtime.py` 与 `sed`/`.`/`PROXY_ENABLED` 硬校验这一环一个都没删。

### 格二：第四处（diag 回推）令牌改走 askpass

改动前：`git push -f "https://${CNB_TOKEN_USER_NAME:-cnb}:${CNB_TOKEN}@cnb.cool/…/crawl_cars.git" HEAD:refs/heads/diag`
改动后：heredoc 落 `/tmp/cnb-askpass.sh`（`chmod 700`）→ `GIT_ASKPASS=/tmp/cnb-askpass.sh git push -f "https://cnb.cool/xuerui911-mirror/crawl_cars.git" HEAD:refs/heads/diag` → `rm -f /tmp/cnb-askpass.sh`。
URL 与进程表内不再出现令牌；`|| echo "diag 推送失败（不阻断）"` 与 `HEAD:refs/heads/diag` 回推语义逐字保留（诊断证据仍能回推）。

### 反证（自跑，非推断；每次改完全部已 `git checkout` 复原）

| 反证 | 改动 | 实测结果 |
|---|---|---|
| A 删掉 diag 回推 | 注释掉 `HEAD:refs/heads/diag` 那条 push | `test_diag_pushback_still_exists_and_uses_askpass` **立刻红**（"全仓找不到了…不许用删段让上一条判据变绿"）⇒ 反空壳守卫有效，已复原 |
| B 删掉 PREP 循环内的 `exit 1` | 两处 `PREP_ATTEMPT` 耗尽分支去掉 `exit 1` | 本单 4 条判据 + v2/回推组仍 **11 passed**（该形状不在本单判据射程内），故**不是**判据兜住的——我仍保留 `exit 1`：耗尽必须判红是 Issue 明令（"重试不是放宽防护"），未借此放宽任何防护 |
| C 起点（裸跑形状） | 起点 `0dfb093` 原样 | `test_fallible_prep_is_reachable_from_a_retry_loop` 对 `api_trigger` 与 `crontab: 5 8 1,16 * *` 两份都报红 ⇒ 格一确实由本提交修复 |

形状验证（真跑，非静态读）：把 `失败诊断归档` 脚本抽出，配 git/askpass mock 执行，得到
`GITCALL: push -f https://cnb.cool/xuerui911-mirror/crawl_cars.git HEAD:refs/heads/diag`，
`ASKPASS=/tmp/cnb-askpass.sh`，askpass 对 username/password 两种 prompt 分别回 `cnb` / 令牌值 ⇒ URL 中无令牌、凭据只经 askpass 传递。

---

## 2. 判据运行结果原文

Issue §5.2 要求的三文件门禁（原样输出）：

```
$ python -m pytest tests/test_codeberg_prep_reachable_and_no_token_url.py \
                 tests/test_pushback_survives_publish_failure.py \
                 tests/test_codeberg_publish_retries_v2.py -q
...........                                                              [100%]
11 passed in 0.19s
```

单跑本单判据：

```
$ python -m pytest tests/test_codeberg_prep_reachable_and_no_token_url.py -q
....                                                                     [100%]
4 passed in 0.08s
```

修复前基线（起点 `0dfb093`，判据为缺陷本身，红是预期）：

```
3 failed, 1 passed in 0.10s
  test_fallible_prep_is_reachable_from_a_retry_loop  (api_trigger + crontab: 5 8 1,16 * * 两份都报)
  test_no_token_in_any_push_url                      (crontab: 37 8 * * 0 / 失败诊断归档)
  test_diag_pushback_still_exists_and_uses_askpass   (同上)
```

`.cnb.yml` 测试组全绿（`test_codeberg_publish_proxy.py`、`test_codeberg_publish_retries_v2.py`、`test_pushback_survives_publish_failure.py`、`test_pushback_size_gate.py`、`test_dealer_chain_isolation.py`、`test_chain_selfheal_coverage.py`、`test_setup_proxy_runtime.py` 等）：

```
$ python -m pytest tests/test_codeberg_publish_proxy.py tests/test_codeberg_publish_retries_v2.py \
                 tests/test_pushback_survives_publish_failure.py tests/test_pushback_size_gate.py \
                 tests/test_dealer_chain_isolation.py -q
29 passed, 10 subtests passed in 1.07s
```

全量口径（比失败集合不比条数；本容器 Linux 无 4 条 Windows 本机专属红，集合与 `main` 相同、零新增）：

```
$ python -m pytest tests -q
722 passed, 139 subtests passed in 31.27s

$ python -m pytest tests/ -x --tb=short -q
722 passed, 139 subtests passed in 31.11s
```

其它自校验：

- 判据文件与 Issue 下发文本 `cmp` 逐字节一致（`sha256=0ce1add9acafbb64c4884cd11985dfa03ccf9fcbc6e1be2c65580da7df4bb506`）。
- `.cnb.yml` 全文 77 个 stage/failStage 脚本逐个 `bash -n` 语法校验：`checked 77 bad 0`。
- `yaml.safe_load('.cnb.yml')` 通过（5 个顶层链键可读）。
- 提交主题/正文不含任何形式的跳过 CI 的方括号字面量（实测会让 main push CI 整轮 skipped）；未使用 `--no-verify` / `SKIP_TESTS` / `SKIP_REVIEW` / `ALLOW_UNREVIEWED_EDIT`。

---

## 3. 边界遵守声明

- 未改判据文件任何一个字节；未改 `scripts/check_npc_free_quota.py`、`scripts/finalize_npc_repair.py`、`failStages` 安全链、`/tmp` 快照检查器。
- 未动爬取阶段 `timeout`（属 #53）；未动 `回推增量状态`（#52 已定稿的 index 13 位置与白名单/5MB 闸逐字保留）。
- 单次编辑均 ≤120 行的最小替换，未整篇重写 `.cnb.yml`（两个 `str.replace` 定点替换 + 断言命中次数 2/1）。
- 既有 `exit 1` / 断言 / 防护行：0 删除、0 注释、0 放宽（改动 diff 中只新增循环与 askpass，删除的 `apply_issue52.py` 不在防护清单内）。

## 4. 三种静默终止自查

| 静默终止形态 | 本会话实测 |
|---|---|
| `finish with stop`（只有文字没命令 ⇒ 阶段假成功、零产物） | 未出现：每一条回复都带工具调用；交付动作（改文件→跑判据→commit→push 403→附件交付）全部落在第 100 轮之前 |
| `finish with length`（单条输出写满被截停，落盘前死掉） | 未出现：全程无截断；最大单次写盘为 `_fix_report_.md` 一次 heredoc（<7KB），`.cnb.yml` 为两个小段 `str.replace` |
| `reached maxTurns limit` | 未触及：见下节轮数自计 |

## 5. 模型与轮数（如实记录）

- **实际模型**: `deepseek-v4.1-flash`（`.cnb.yml` `issue.open` → `npc:go` `options.model`，`thinkingLevel: max`，`contextWindow: 256k`）。
- **effective_max_turns**: `150`。
- **实际轮数**: 本报告定稿于约第 **60** 个助手回合（约 70 次工具调用），**剩余约 90 轮**。口径：容器内读不到 CNB 系统计数器，按会话内助手消息自计，±5 回合误差。
- 探索命令（列目录/grep/读 Issue API）计数 ≈14 条 ≤ 20；首次对目标文件编辑发生在第 12 轮左右（早于第 15 轮硬口径）。

## 6. 附件清单

- `issue54.bundle`（ref `refs/heads/agent/54-codeberg-prep-retry`；`git bundle verify` 通过，历史含 `0dfb093` → `be3f087` → 报告提交；下载后回读校验字节数一致）
- `issue54-full.patch`（`ea2a67c`→HEAD 全范围补丁，3 个提交：`0dfb093`（#52 起点）+ `be3f087`（本单实修）+ 报告提交；实测 `git apply --check` 于 `origin/main` 通过、`git am` 后本单判据 4 passed、全量 722 passed）
- 交付评论已在 Issue #54 发出（HTTP 201）；`apply_issue52.py` 未随交付长期保留

派发附件 v1（监工下发，勿删本行）
