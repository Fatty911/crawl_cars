分支 `agent/88-pushback-worktree-gate`（本地提交 `6f78c0f`，基线 `main@2a76534`）｜推送 HTTP 403（`repo-code:rw` 缺失，`--dry-run` 实测）｜开 PR 未测（按 Issue 口径走附件交付）｜实际模型 `deepseek-v4.1-flash`（npc:go，maxTurns=150）

# Issue #88 修复报告：回推段按工作树判成活（堵 `--autostash` rc=0 假成活 + 用尽后 break 仍 push）

## 1. 根因（两条独立假绿通道）

- **① `--autostash` rc=0 假成活**：脏树冲突时 `git rebase -q --autostash FETCH_HEAD` 返回 0，本地提交已重放、工作树留着冲突标记，`until` 第一次就"成功" ⇒ 不重试、不点名，随后 push 是 fast-forward ⇒ 判绿。
- **② 用尽后 `break` 仍走到 push**：三处回推段原来只 `break` 跳出循环，下一行无条件 `git push`；HEAD 与远端相同时 push 回 `Everything up-to-date` rc=0 ⇒ 又是绿。

## 2. 实际改动（2 个文件，均按派发单指定形状）

| 文件 | 改动 |
|---|---|
| `.cnb.yml` | 三处回推段：`break` → `exit 1`；push 前插入 5 行紧凑工作树闸（`git ls-files -u` 非空即 `PUSHBACK-FAIL reason=unmerged-after-rebase; exit 1`） |
| `tests/test_pushback_success_is_measured_on_worktree.py` | 新增，判据原样落盘（sha256 见 §5） |
| `tests/test_pushback_rebase_survives_dirty_tree.py` | **只尾部追加 44 行**（`git diff --numstat` = `44 0`，无删除）：三处样张 + 3 个 `test_*` 入口 |

三处位置（行号为改动前）：`api_trigger` `:473/478`、`crontab: 5 8 1,16 * *` `:1156/1161`、`crontab: 37 8 * * 0` `:1541/1546`；缩进各按其自身（18/18/20 空格）逐处修改。

## 3. 判据运行结果原文（验收命令全部 rc=0）

```
$ python -m pytest tests/test_pushback_success_is_measured_on_worktree.py -q --no-header
....                                                                     [100%]
4 passed in 0.09s

$ python -m pytest tests/test_pushback_rebase_survives_dirty_tree.py -q --no-header
...                                                                      [100%]
3 passed in 0.09s

$ python -m pytest tests/test_pushback_rebases_before_push.py tests/test_pushback_survives_publish_failure.py \
    tests/test_pushback_size_gate.py tests/test_pushback_excludes_pycache.py \
    tests/test_dealer_chain_isolation.py tests/test_chain_selfheal_coverage.py -q --no-header
..................................                             [100%]
34 passed, 10 subtests passed in 1.13s
```

修前基线：`test_pushback_success_is_measured_on_worktree.py` 红（3 failed），`check(load())` 三处全部点名
E1（只 break 无 exit）+ E2（push 前无未合并项检查）。自校 8/8 例（六变异全红 + 合规样张 + 三处识别）双向通过。
全量套件额外跑过 1 次用于最终确认：`798 passed, 139 subtests passed`（未为对齐报告数字重跑）。

## 4. 红线自查

- 未删/未放宽任何既有断言、`exit 1`、体积闸、白名单；既有 189 行逐字节未动（`44 0` 纯追加）。
- 未用 `--force`、未删 `--autostash`/`fetch`/rebase 到 `FETCH_HEAD` 语义；push 前 400 字符无 `|| true`/`|| exit 0`（实测三条全 False）。
- 凭据仅 `GIT_ASKPASS` 临时脚本（已 `rm -f`），未进 URL/被跟踪文件/本报告。
- 未碰 `failStages`、爬取预算、发布阶段实现、`scripts/check_npc_free_quota.py`、`AGENTS.md`。

## 5. 产物（附件交付）

本报告由 `_fix_report_.md` **全量覆写**（上一单 #84 的旧报告内容已随本单替换）。上传后经 GET 回读校验时报告 §5 的资产地址以 Issue 评论为准。

- `issue88-pushback-worktree-gate.bundle`（`2a76534..6f78c0f`）：8685 字节，sha256 `d5c6d285ac4c6b5ac5f30af18dfc114d6767380dedec409913d37e48f90a1264`，PUT 200
- `issue88-pushback-worktree-gate.patch`（`git format-patch 2a76534..6f78c0f`）：22637 字节，sha256 `2d597df63d8e36d6a10c4349484f79913ff534c58ddeaf1064bb0c13300a4d04`，PUT 200

判据文件字节（原样落盘校核）：`tests/test_pushback_success_is_measured_on_worktree.py` sha256 `e8ce07495c9788c4827f019385286b7e`（md5），与 Issue 下发 python 块逐字节相同（实测 `identical: True`）。

## 6. effective_max_turns

本会话 `maxTurns=150`，当前约第 60 轮，**剩余约 90 轮**。
