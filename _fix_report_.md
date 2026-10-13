分支 `agent/56-independent-review-family`（本地就绪；代码提交 `c53dab6` + 报告随分支头提交，基线 `ea2a67c`）｜推送状态 HTTP 403（缺 `repo-code:rw` scope）｜PR 创建状态 HTTP 403（缺 `repo-pr:rw` scope）｜原因：容器凭据权限不足，按 Issue 口径改走附件交付（`POST /{repo}/-/upload/files` 通道，三件均已 cmp 校验）｜实际模型：`deepseek-v4.1-flash`｜实际轮数：约第 35 轮（effective_max_turns=150，剩余约 115）

# Issue #56 修复报告：把"评审"补成真正的独立评审

**交付方式**: 因推送被拒（403），按 Issue 指示改为附件交付。patch + bundle 已上传至 Issue #56（见「附件清单」）。代码提交 `c53dab6` 本地已就绪，监工可 fetch 附件 bundle 后复核。

---

## 1. 实际改动文件清单（2 个，+69/-2）

| 文件 | 改动 | 位置 |
|---|---|---|
| `.cnb.yml` | `NPC-PR审查`（`main.pull_request` 链 stages）`options.model`: `deepseek-v4.1-flash` → `glm-5.3-flash` | 第 1250 行，1 行替换 |
| `.cnb.yml` | `审查-GLM只读交叉评审` 的 `options.maxTurns`: `20` → `120` | 第 716 行，1 行替换 |
| `tests/test_npc_reviewer_fallback.py` | 新增（原样落盘 Issue 下发的验收判据，含 docstring；逐字节比对一致 `EQ True`，2356 bytes） | 67 行新增 |

`git diff --stat`（相对于 `ea2a67c` main）：

`git diff --stat`（相对 `ea2a67c`）：
```
 .cnb.yml                            |  4 +--
 tests/test_npc_reviewer_fallback.py | 67 ++++++++++++++++++++++++++++++++++++++
 2 files changed, 69 insertions(+), 2 deletions(-)
```

**关于"第二份拷贝"**：`.cnb.yml` 中 `审查-GLM只读交叉评审` 全文只有 **1 份物理定义**（YAML 锚点 `&cars_npc_repair_chain`，第 617 行），被 `main.api_trigger`（第 1225 行 `failStages: *cars_npc_repair_chain`）与 `main."crontab: 5 8 1,16 * *"`（第 1436 行同别名）两条链共享。改锚点一处即同步生效于两链——已用 YAML 解析验证两链 `failStages` 为**同一对象**（`id()` 相等），不存在"只改一份"的半修。

## 2. 判据运行结果原文

命令 1（Issue 指定）：

判定判据文件一致性：
```
python -m pytest tests/test_npc_reviewer_fallback.py tests/test_pr_review_turn_budget.py -q
10 passed in 0.08s
```

分文件：`test_npc_reviewer_fallback.py` → **7 passed**（修复前实测 `2 failed / 5 passed`，与监工一致）；`test_pr_review_turn_budget.py` → **3 passed**（未动坏）。

命令 2（读 `.cnb.yml` 一组，21 个测试文件，**比失败集合不比条数**）：

**修复前基线（同一判据，未改动 `.cnb.yml` 时、仅落盘判据文件后）**：
```
python -m pytest <21 files> -q
262 passed, 61 subtests passed in 15.60s
```

失败集合与基线（修改前留存 `/tmp/baseline_fail.txt`）**完全一致**：新增红 **0 条**。

命令 3（全量门禁）：

```
python -m pytest tests/ -x --tb=short -q
718 passed, 139 subtests passed in 31.44s
```

**退出码 0**。

## 3. 守卫未动清单

- 额度分支：`NPC审核前免费额度复查` 阶段保留；全文 `NPC_BUDGET_STATE` **7 处**（≥3），限额时按既有 RUN/跳过分支走，不报错中断；
- `reviewer_is_read_only_and_must_emit_verdict`：评审只读 + `VERDICT: PASS` + "不得修改源码" 原文未动；
- 两链等同（`test_finalize_npc_repair.py`：failStages 等同、模型序列 `["deepseek-v4.1-flash", "glm-5.3-flash"]`、`AI-修复-第1轮` 120 轮）→ 全绿；
- `pull_request` 链 150 轮（`test_pr_review_turn_budget.py`）→ 全绿；
- 未删除/注释/`skip`/放宽任何既有断言；未使用 `--no-verify` / `SKIP_TESTS` / `SKIP_REVIEW` / `ALLOW_UNREVIEWED_EDIT`；提交主题无跳过 CI 的字面量。

## 4. 附件清单（Issue #56 评论区）

| 附件 | 用途 |
|---|---|
| `agent-56-delivery.patch` | `git format-patch ea2a67c..HEAD` 全量补丁（含报告提交），`git am` 可落地 |
| `agent-56-independent-review-family.bundle` | 增量 bundle（`ea2a67c..HEAD`），`git fetch <bundle>` 可解析 |

## 5. 模型与轮数（如实记录）

- **实际使用模型**: `deepseek-v4.1-flash`（`.cnb.yml` `issue.open` → `AI-Issue驱动修复` 的 `options.model`，`thinkingLevel: max`）。
- **effective_max_turns**: `150`（`.cnb.yml:1428` `maxTurns: 150`）。本报告完成于第 **35** 轮上下，**剩余约 115 轮**。
- **三种静默终止（如实）**:
  - PR 创建（`POST /-/pulls`）：HTTP **403**，`Missing required scopes: repo-pr:rw`（仅试 1 次，未重试）；
- `reached maxTurns limit`：**未出现**；
  - `finish with length`：**未出现**（全部编辑均 ≤120 行小步替换）；
  - `finish with stop`：报告交付前**未出现**；本条为正常交付收尾，写完即停。
