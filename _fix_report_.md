`BRANCH npc/44-pages-columns-publish | PUSH 403 (repo-code:rw 缺失，已试 2 种凭据后停止) | 交付方式=Issue #44 评论附件(patch+bundle)`

# 交付报告 — Issue #44 Pages 发布列收窄必须两处写出拷贝都改（#41 半修修正）

推送尝试记录（照抄 Issue 指定 askpass）：

1. `GIT_ASKPASS=/tmp/ap.sh git push origin HEAD:refs/heads/npc/44-pages-columns-publish`
   → `remote: Your token does not have the repo-code:rw scope required to push` → `HTTP 403`
2. 凭据变体（唯一 1 次）：`case "$1"` 形式 askpass（非空匹配 username）
   → 同样 `403 / repo-code:rw`

按 Issue §6.3「最多再试 1 种凭据变体，然后立即停止推送尝试」执行，未再做任何 scope 排查。
askpass 脚本用后已 `rm -f`；令牌未写入 URL、进程表、被跟踪文件或本报告。

---

## 一、根因（与 Issue 描述一致，未重复取证）

`filtered` 发布面的窄化必须落在**两份写出拷贝**上：

1. `scripts/merge_data.py` 发布段（`:17349/:17356`）—— 写出 `filtered_cars_.json/.csv`；
2. `scripts/preserve_publish_baseline.py::write_publish_assets`（`:324-327`）—— 该阶段在 `.cnb.yml`
   合并阶段紧接着无条件重写同一批文件，用 `merged` 宽行覆盖。

#41 只改了第 1 处 ⇒ 被第 2 处覆盖 ⇒ 线上仍是每行 11574 B。本单两处同改。

## 二、改动清单（实际改动文件）

| 文件 | 改动 | 行数 |
|---|---|---|
| `scripts/merge_data.py` | 新增模块级 `PAGES_IDENTITY_COLUMNS` + `resolve_pages_columns(rows)` + `narrow_pages_rows(rows)`（插在 `def collect_fields` 之前，零缩进）；发布段 `write_csv(filtered_csv_path, ...)` 前插一行 `filtered_rows = narrow_pages_rows(filtered_rows)`（缩进与目标行一致） | +23 |
| `scripts/preserve_publish_baseline.py` | `from merge_data import (...)` 内加 `narrow_pages_rows`；`filtered_rows = [row for row in rows if filter_car(row)]` 之后加收窄；filtered_csv 表头改 `collect_fields(filtered_rows)` | +3/-1 |
| `tests/test_pages_columns_narrow_publish_paths.py` | 判据文件原样落盘（新增 151 行） | +151 |
| `tests/test_debug_publish_safety.py` | **唯一被批准的测试变更**（详见下节） | +3/-2 |

列清单来源：`config/filter_conditions.json → defaultVisibleColumns`（实测 53 条，未清空、未改动），
经模块级 `FILTER_CONFIG` 读取，未新开文件、未造第二份清单。
`IDENTITY_FIELDS`（5 项语义）未改，身份列另用新常量 `PAGES_IDENTITY_COLUMNS`（7 项）。

### 唯一被批准的测试变更（改前/改后原文）

`tests/test_debug_publish_safety.py::PreservePublishBaselineTests::test_baseline_wins_and_all_publish_assets_share_one_final_row_set`

改前（`:894-895`）：
```python
        self.assertEqual(expected_filtered, outputs["filtered_json"])
        self.assertEqual(self.csv_rows(expected_filtered, header), outputs["filtered_csv"])
```

改后（`:894-896`）：
```python
        narrow_filtered = self.merge_data.narrow_pages_rows(expected_filtered)
        self.assertEqual(narrow_filtered, outputs["filtered_json"])
        self.assertEqual(self.csv_rows(narrow_filtered, self.merge_data.collect_fields(narrow_filtered)), outputs["filtered_csv"])
```

同测试内其余断言逐字保留：baseline-wins（`merged_json`/`merged_csv` 比对）、`temp_files`、
stats（`baseline_rows` 等 6 键）。除这两处外无任何其它测试文件改动（`git show --stat HEAD` 可核）。

## 三、判据运行结果原文

命令：`python -m pytest tests/test_pages_columns_narrow_publish_paths.py -q`

修复前（main = `7251ee3`，判据刚落盘）：
```
FAILED tests/test_pages_columns_narrow_publish_paths.py::test_merge_data_resolver_exists - AssertionError: merge_data.py 里没有 resolve_pages_columns(rows)：发布列集合无处收敛，现网实测 filtered 仍是 1205 列 / 每行 11574 B
FAILED tests/test_pages_columns_narrow_publish_paths.py::test_merge_data_resolver_stays_inside_declared_set - AssertionError: merge_data.py 没有 resolve_pages_columns(rows)，无法核对发布列集合（见上一条）
FAILED tests/test_pages_columns_narrow_publish_paths.py::test_preserve_write_publish_assets_output_is_narrow - AssertionError: preserve_publish_baseline.write_publish_assets 写出的 filtered_json 仍带 400 个越界列（例 ['伪造属性列0', '伪造属性列1', '伪造属性列10', '伪造属性列100', '伪造属性列101', '伪造属性列102']）：这正是覆盖 merge_data 窄化、让线上每行保持 11574 B 的那一份写出拷贝
3 failed, 3 passed in 0.20s
```

修复后：
```
......                                                                   [100%]
6 passed in 0.20s
EXIT_CODE=0
```

全量套件：`python -m pytest tests/ -x --tb=short -q` →
```
709 passed, 139 subtests passed in 30.95s
EXIT_CODE=0
```

判据文件字节未改（sha256 `5d21e5c7d1d40634fb7939337922ee711b46ee5c90f6c2dbb725c16332f0bec4`）。

## 四、能变红的证据（证明测的是行为，不是字面）

临时把 `narrow_pages_rows` 改成 `return list(rows)  # TEMP RED-EVIDENCE PROBE`（等于不收窄），
再跑判据：

```
tests/test_pages_columns_narrow_publish_paths.py:118: AssertionError
E       AssertionError: preserve_publish_baseline.write_publish_assets 写出的 filtered_json 仍带 400 个越界列（例 ['伪造属性列0', '伪造属性列1', ...]）：这正是覆盖 merge_data 窄化、让线上每行保持 11574 B 的那一份写出拷贝
FAILED tests/test_pages_columns_narrow_publish_paths.py::test_preserve_write_publish_assets_output_is_narrow - AssertionError: ...
1 failed, 5 passed in 0.12s
```

B 条（`test_preserve_write_publish_assets_output_is_narrow`）按预期变红。
随后从备份恢复，`grep -c "TEMP RED-EVIDENCE PROBE"` = 0，判据重回 6 passed。
（注意：判据对 `filtered_csv` 表头的窄化是独立断言；若只改 `write_json` 不改 `write_csv` 表头，
同一测试在 csv 段也会红——本次两处均已改。）

## 五、边界自查

- 行集合：判据 C 条 9 行宽夹具过 `filter_car()` 仍 9 行（`test_narrowing_does_not_drop_rows` PASS）；
  `narrow_pages_rows` 不做任何行过滤，只投影列。
- 全量面：判据 D 条 PASS，`merged_json`/`merged_csv` 仍写 `rows` 全列（`header = collect_fields(rows)` 未动）。
- 未触碰：`.cnb.yml`、门禁脚本、`config/filter_conditions.json`、`IDENTITY_FIELDS`、
  `write_json`/`write_csv` 本体、其它测试文件。
- 无 `--no-verify` / `SKIP_TESTS` / `SKIP_REVIEW`；提交主题不含自跳过标记字面量。
- 编辑器纪律：全部为 ≤120 行最小替换（整行做替换单位），每处改完立即 `py_compile`。
- 语法校验：4 个文件 `py_compile` 全 OK。
- 提交附带副作用已清理：pytest 运行会改写 `crawl_state/`（progress.json、target_manifest.json、pyc），
  已 `git checkout HEAD~1 -- crawl_state/` 并 amend，最终提交只含 4 个目标文件。

## 六、交付物（Issue #44 评论附件）

- `npc-44-pages-columns-publish.patch` — `git format-patch 7251ee3..HEAD`（两个补丁：代码修复 + 本报告）
- `npc-44-pages-columns-publish.bundle` — `git bundle create ... 7251ee3..HEAD`
- `_fix_report_.md` — 本报告单文件副本
- 代码修复提交：`a26aa46`（subject：`fix(pages): 发布列收窄同时落在 merge_data 与 preserve_publish_baseline 两处写出拷贝（#41 半修修正）`）
- 精确 tip SHA 见 Issue #44 最终交付评论（`--amend` 会刷新 tip，故不在此内嵌）

## 七、模型与轮数（如实申报）

- 实际使用模型：`deepseek-v4.1-flash`（提交作者 `cnb-npc-deepseek-v4.1-flash <xuerui911@gmail.com>`）。
- 会话结果：**`finish with stop`（正常写出本报告后停止）**；未触发 `reached maxTurns limit`、
  未触发 `finish with length`。
- `effective_max_turns`：本会话未获暴露该数值的环境变量/日志入口（`env` 中无 maxTurns 相关项），
  无法给出剩余值——按 Issue §6.4 要求如实说明「不可得」，不作猜测填报。
- 轮数：约 28 轮（含报告撰写，按本会话可见的工具调用计数）。写盘时尚未收到任何截断信号。

## 八、附件说明（最终）

以 Issue #44 **最终一条交付评论**的三条链接为准（此前评论链接的 tip 可能已过期）。
本地校验（本次会话实测）：`git bundle verify` 通过（requires `7251ee3`）；干净 clone 上
`git checkout 7251ee3 && git am <patch>` 两补丁无冲突应用，clone 内判据 `6 passed`。
代码改动自 `a26aa46` 起从未被后续 amend 触碰（amend 只影响 `_fix_report_.md` 与 tip 提交）。
