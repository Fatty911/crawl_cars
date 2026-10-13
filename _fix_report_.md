分支 `npc/53-crawl-stage-timeout`（本地就绪，commit `85a8982`，base `ea2a67c`）｜推送状态 HTTP 403 ｜原因：容器凭据缺少 `repo-code:rw` scope（`Your token does not have the repo-code:rw scope required to push to this repository.`，Issue 配方给的 askpass 凭据仅试 1 次即停，未反复重试）；`POST /-/pulls` 另返 403 `missing required scopes: repo-pr:rw`｜交付方式：按 Issue 第 5 条改走 Issue #53 评论附件交付（patch + bundle，附件哈希与本地一致，`git apply --check` 在 base 上通过）。

# Issue #53 修复报告：爬取阶段 timeout 抬到预算尺度（两份拷贝 4 处）

**实际模型 / 轮数**: 模型 `deepseek-v4.1-flash`（NPC `npc:go` 会话，`maxTurns: 150`，`contextWindow: 256k`，`thinkingLevel: max`，`.cnb.yml:1426-1429`）。
本轮会话未触发 `reached maxTurns limit`（未到 150）；未触发 `finish with length`；**本报告写盘后本轮以正常收束结束**，非静默终止。`effective_max_turns` 已用约 30 轮，**剩余约 120 轮**（估计值：按本会话工具调用计数）。

---

## 1. 实际改动文件清单（2 个）

| 文件 | 改动 | 规模 |
|---|---|---|
| `.cnb.yml` | 4 处最小替换：`api_trigger`（206/207、240/241）与 `crontab: 5 8 1,16 * *`（817/818、851/852）两份拷贝中，`- name: 爬取-汽车之家` 下一行 `timeout: 1h→3h`、`- name: 爬取-懂车帝` 下一行 `timeout: 2h→5h` | 4 行替换（4-/4+） |
| `tests/test_crawl_stage_timeout_covers_budget.py` | 新增，Issue 下发判据原样落盘（未改判据字节） | 141 行新增 |

`git diff --stat`（相对 `ea2a67c`）：
```
 .cnb.yml                                        |   8 +-
 tests/test_crawl_stage_timeout_covers_budget.py | 141 ++++++++++++++++++++++++
 2 files changed, 145 insertions(+), 4 deletions(-)
```

**边界遵守声明**：只改上述 4 行 timeout + 1 个新增判据文件。未触碰报价链 `timeout: 1h`（`tests/test_dealer_chain_isolation.py:250` 钉死，实测仍为 `1h`，见 `grep -n "timeout: 1h"` 输出：167/496/569/778/1105/1177/1273 行均为报价/job 行）；未动 `爬取-易车`（保持 `6h`：288/289、897/898）；未动 `scripts/allocate_crawl_budget.py`（`PIPELINE_LIMIT_SECONDS` 仍 `10*60*60`、`STEP_WEIGHTS` 仍四步各 250‰）；未动 `failStages`、`scripts/check_npc_free_quota.py`、`scripts/finalize_npc_repair.py`；未用 `--no-verify` / `SKIP_TESTS` / `SKIP_REVIEW` / `ALLOW_UNREVIEWED_EDIT`；提交消息不含 CI 自跳过方括号词。

改动定位方式：以「`- name: <阶段名>` 的紧邻下一行 `timeout:`」为锚做定向替换（正则 `- name: 爬取-汽车之家\n\s+timeout: 1h`），保证不会误伤报价链的同值行。

判定判据文件一致性：
```
$ python - (difflib 比对 Issue 正文最后一个 ```python 块 vs tests/test_crawl_stage_timeout_covers_budget.py)
python blocks: 1
EQ: True 5251 5251        # 逐字节一致
```

## 2. 判据运行结果原文

**修复前基线（同一判据，未改动 `.cnb.yml` 时、仅落盘判据文件后）**：
```
$ python -m pytest tests/test_crawl_stage_timeout_covers_budget.py -q
1 failed, 2 passed in 0.09s        (exit 1)
缺口：['api_trigger / 爬取-汽车之家：阶段 timeout=3600s 盖不住分配器发的 8505s（差 4905s）',
      'api_trigger / 爬取-懂车帝：阶段 timeout=7200s 盖不住分配器发的 17010s（差 9810s）',
      'crontab: 5 8 1,16 * * / 爬取-汽车之家：阶段 timeout=3600s 盖不住分配器发的 8505s（差 4905s）',
      'crontab: 5 8 1,16 * * / 爬取-懂车帝：阶段 timeout=7200s 盖不住分配器发的 17010s（差 9810s）']
```
4 处缺口与监工实测逐条一致（数值与差值均对上）。

**修复后（commit `85a8982`）**：
```
$ python -m pytest tests/test_crawl_stage_timeout_covers_budget.py -q
...                                                                      [100%]
3 passed in 0.08s        (exit 0)
```

**读 `.cnb.yml` 的成员（20 个测试文件）**：
```
$ python -m pytest $(grep -rl "cnb.yml" tests/*.py | tr '\n' ' ') -q
258 passed, 61 subtests passed in 16.86s        (exit 0)
```
监工基线为 `5 failed / 253 passed / 61 subtests`，其中 4 条标注为「Windows 本机专属红」。本容器为 Linux ⇒ 那 4 条不复现，**失败集合为空**（比集合：空 ⊂ {那 4 条}，无新增失败）。

**全量门禁**：
```
$ python -m pytest tests/ -x --tb=short
714 passed, 139 subtests passed in 31.33s       (exit 0)
```

已知一次性抖动（如实记录，非本次引入）：首次全量 `-x` 曾红在
`tests/test_yiche_crawler.py::test_item_stall_is_bounded_heartbeated_and_checkpointed`
（`assert (274020.063872477 - 274019.874631931) < 0.18`，实测差 0.189s）。单独重跑 3/3 通过，判定为计时阈值抖动；本次改动只动 `.cnb.yml` 字面量 + 新增判据，与该测试无交集。随后全量 `-x` 直接通过（上方即是）。

## 3. 交付物与推送状态

- 分支：`npc/53-crawl-stage-timeout`（本地），修复 commit `85a8982`（代码改动以此 commit 为准；其后的提交只追加本报告文档），base `main@ea2a67c`；
- `git push origin HEAD:refs/heads/npc/53-crawl-stage-timeout` ⇒ **HTTP 403**（`repo-code:rw` 缺失），仅尝试 1 次后停止；
- `POST /-/pulls`（body 含 base/head/head_repo/title/body）⇒ **HTTP 403**（`repo-pr:rw` 缺失）；
- 改走 Issue #53 评论附件交付（多条评论均 HTTP 201）。**附件以 Issue #53 最新一条评论列出的 patch + bundle 为准**（该对附件的 bundle HEAD 即分支最新提交）；patch 的 `git apply --check` 在 `ea2a67c` 上通过，bundle 含 `refs/heads/npc/53-crawl-stage-timeout` 且 `git bundle verify` okay；
- 端到端复核（实测）：从 Issue 附件下载 bundle → 全新仓库 fetch 成功 → 在该分支工作树上复跑判据 `3 passed`；工作区从分支还原后 `python -m pytest tests/ -x --tb=short` ⇒ `714 passed, 139 subtests passed`；
- 监工侧接手路线：`git fetch <bundle> 'refs/heads/npc/53-crawl-stage-timeout:refs/heads/npc/53-crawl-stage-timeout'` 或 `git am <patch>`，然后由监工开 PR。

## 4. 为什么这是治本（不是假修）

- 判据是比值不变式（阶段 timeout ≥ 分配器实际发的预算），不是写死 3h/5h；
- 未削预算：`PIPELINE_LIMIT_SECONDS` 仍等于爬虫 job 声明的 `timeout: 10h` ⇒ `test_budget_not_gutted_to_pass_the_invariant` 通过；
- 抬升幅度为「与预算同尺度的最小抬升」：汽车之家 8505s ⇒ 3h(10800s)，懂车帝 17010s ⇒ 5h(18000s)，留出收尾余量且不虚高；
- 两份拷贝同批改 ⇒ `check_chain_copies.py` 语义（判据 `test_chains_discovered_and_budget_nonzero` 认 ≥2 份拷贝）通过。
