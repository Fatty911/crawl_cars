分支 `npc/84-merge-idempotence`（本地提交 `f5ec26e`，基线 `main@6999c96`）｜推送 HTTP 403（`repo-code:rw` 缺失）｜`POST /-/pulls` HTTP 403（`repo-pr:rw` 缺失）｜按 Issue 口径附件交付（bundle + patch + 本报告）｜实际模型 `deepseek-v4.1-flash`（npc:go，maxTurns=150）

# Issue #84 修复报告：合并幂等（同一段值第二次合并不许叠前缀/同源多段）

## 1. 根因

现网 `汽车之家:汽车之家:…` 逐轮膨胀的根因是跨源合并两处写出点的解析形状：

- `_merge_existing_with_source` 尾部把 `existing` 与 `source_name:added` 直接字面拼接，不先解析既有串里各源位置 ⇒ 已带前缀的串再合一次就在外层套第二层前缀（判据实测 main 第 1 次 `汽车之家:汽车之家:电动调节…`，第 2 次叠第三层）。
- 值串里**没有源前缀的尾段**（`汽车之家:真皮|仿皮` 的 `仿皮`）被当成独立"新源"，每轮重拼一次。
- `_merge_distinct_values` 只用 `incoming_text in parts` 做字面成员判断，不解析源归属 ⇒ 同族写出点形状分叉（判据 `test_both_writers_leave_at_most_one_segment_per_source`）。

## 2. 实际改动（1 个源码文件）

`scripts/merge_data.py`（+63 −67 行，净 −4）：

- **新增 3 个纯函数**（插在 `_merge_existing_with_source` 定义前，复用既有 `_preserved_value_parts`、不改其签名）：
  - `_folded_source_buckets(value, default_sources=())`：把值串解析成 `{源: [字面段]}`；**无前缀尾段归前面最近源**；整值无前缀时归 `default_sources`（裸值归该行全部原子源）；剥同源重复前缀。
  - `_merge_source_buckets(base, extra)`：**同源按字面 token 去重**（不用 `canonical_compare` 归一键，避免误删合法信息）；裸段已被任一源记录时不重复；**不跨源折叠**（真冲突留痕）。
  - `_render_source_buckets(buckets)`：按 `源:段|段|源2:段` 拼回。
- **`_merge_existing_with_source` 写出点**：`if parts and all(...)` 分叉分支替换为统一折叠——`default_sources = atomic_source_names(current_source) or [current_source or "已有来源"]`，两侧折桶后合并、再渲染。删除了原来只会拼 `f"{existing}|{source_name}:{added}"` / `f"{preserved}|{source_name}:{added}"` 的两条写出行。
- **`_merge_distinct_values` 尾部**：替换为 `_folded_source_buckets(existing)` + `_merge_source_buckets(...)` + `return _render_source_buckets(folded) or existing`（同族写出点一起改，不留半修）。

未动：`canonical_compare`/`VALUE_SYNONYMS`/`_DATE_FIELDS`/`_SHIFT_FIELDS`（#81 已合入）、`_preserved_value_parts` 签名、`merge_source_rows` 行级主干（其经 `merge_single_row` 调用同一套 helper）。新增判据文件 `tests/test_merge_value_idempotence.py` **原样落盘**（归一行尾后 sha256 = `aa1de4dbd5aaba76b65b2d12457305ed1c242c06ad48c81d3a55a9bc32ae5f99`，与 Issue 下发块一致，未改一字）。

| 文件 | 改动 |
|---|---|
| `scripts/merge_data.py` | +63 −67（新增 3 纯函数；两处写出点统一折叠） |
| `tests/test_merge_value_idempotence.py` | 新增，判据原样落盘 |

## 3. 判据运行结果原文

```
$ python -m pytest tests/test_merge_value_idempotence.py -q --no-header    # 修前（红样，缺陷存在证据）
3 failed, 3 passed in 0.05s

$ python -m pytest tests/test_merge_value_idempotence.py -q --no-header    # 修后
......                                                                   [100%]
6 passed in 0.04s
```

改前红样三条：`test_existing_prefixed_value_is_not_prefixed_again`（叠第二层前缀）、
`test_remerging_the_same_incoming_is_idempotent`（非幂等）、
`test_both_writers_leave_at_most_one_segment_per_source`（同族写出点分叉）。
红线三条（真冲突留痕 / helper 不许改名 / 幂等底线）当时即绿，修后仍绿。

## 4. 全量套件失败集合比对（同比成员，不比条数）

```
$ python -m pytest tests/ -q --no-header        # 修前基线
3 failed, 788 passed, 139 subtests passed in 23.07s

$ python -m pytest tests/ -q --no-header        # 修后
791 passed, 139 subtests passed in 22.31s
```

失败集合 diff（`comm -13 改前红集 改后红集`）= **空** ⇒ 新增红 0；改前 3 红全部为本单判据（修复后转绿）。

守卫组（本次一并复跑）：`test_merge_matching.py` / `test_merge_data_aliases.py` /
`test_prepare_pages_payload.py` / `test_capability_column_value_domain.py` → `92 passed`；
`test_publish_baseline_dirty_values_refolded.py` 亦绿。`py_compile scripts/merge_data.py` → `COMPILE_OK`。

## 5. 红线自查

1. **真跨源冲突留痕**：`加热` vs `制冷` 两源两段都在（不折叠、不覆盖）；同源字面去重不涉跨源。
2. **幂等**：`twice == once` 逐字相等（行合并 + 值合并两条路径都验）。
3. **不许改名绕过**：`_merge_existing_with_source` / `_merge_distinct_values` 均在场可调用。
4. **判据未改字**：归一行尾后 sha256 与 Issue 下发版一致。
5. **受保护面未动**：`tests/`（除本单判据）、`scripts/check_npc_free_quota.py`、
   `scripts/finalize_npc_repair.py`、`AGENTS.md`、`failStages` 安全链均未触碰。
6. **凭据**：仅 `GIT_ASKPASS` 临时脚本（已 `rm -f`）；未进 URL/进程表/被跟踪文件/本报告。
7. **未用** `--no-verify` / `SKIP_TESTS` / `SKIP_REVIEW`；测试一律 `python -m pytest tests/...` 口径。

## 6. 产物（附件交付）

- `issue84-merge-idempotence.patch`（`6999c96..f5ec26e`，git format-patch）
- `issue84-merge-idempotence.bundle`（同区间 bundle，`git bundle verify` 通过）
- 本报告 `issue84-_fix_report_.md`

各产物上传后经 GET 回读 http=200 + sha256 一致（读数见 Issue #84 最新评论）。

## 7. effective_max_turns

本会话 `maxTurns=150`，当前约第 40 轮，**剩余约 110 轮**。
