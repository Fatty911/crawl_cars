分支 `npc/81-a-class-synonym-fold`（本地就绪，提交 `1a5fe24` + `973ecef`，基线 `main@6e25916`）｜推送 HTTP 403（`Your token does not have the repo-code:rw scope required to push to this repository.`）｜`POST /-/pulls` 另返 403（`Missing required scopes: repo-pr:rw`）｜交付方式：按 Issue 口径改走 Issue #81 评论附件交付（patch + bundle，官方 `comment-file-asset-upload-url` 通道）｜实际模型 `deepseek-v4.1-flash`（npc:go，maxTurns=150）

# Issue #81 修复报告：A 类判异同族折一（悬架/悬挂、万/万元）

## 1. 根因

`canonical_compare`（`scripts/merge_data.py`）的归一表不闭环：

- **拼写族缺失**：`麦弗逊式独立悬架` 与 `麦弗逊式独立悬挂` 是同一个词两种写法，比较键不折叠 ⇒ 两源值被判异 ⇒ `merge_source_rows` 走冲突分支写成 `汽车之家:…|懂车帝:…`（现网 150+99 行）。
- **单位后缀不闭环**：`万元` 在 `_VALUE_UNIT_SUFFIX` 里、`万` 不在 ⇒ `59.88万元` 折成 `num:59.88`，`59.88万` 不折 ⇒ 同一价格的两种写法折叠程度不一致。

两处都只涉及**比较键**，不涉及存储值——`canonical_compare` 的 docstring 已声明 "without changing the stored value"。

## 2. 实际改动（1 个文件、3 行）

`scripts/merge_data.py`，`canonical_compare` 函数体入口（`text = str(value or "").strip()` 之后、
`compact = re.sub(...)` 之前）新增 3 行：

```python
    # A 类归一：只折比较键，不改存储值——悬架/悬挂 同词异写，万元/万 同单位异写
    text = text.replace("悬挂", "悬架")
    text = re.sub(r"万元$", "万", text)
```

加在 `text` 上而不是 `compact` 上（监工提示的坑①：`前悬挂形式` 这类字段的比较键不走 `compact` 那条返回路径）；
`万元$ → 万` 用后缀正则而非 `(\d)元$`（坑②：`59.88万元` 结尾是"万+元"）。

新增判据文件 `tests/test_value_synonym_and_granularity.py`（**原样落盘**，含 docstring 口径说明，未改一字）。

| 文件 | 改动 |
|---|---|
| `scripts/merge_data.py` | +3 行（`canonical_compare` 入口两条归一） |
| `tests/test_value_synonym_and_granularity.py` | 新增，判据原样落盘 |

范围外一律未动：`.cnb.yml`、`config/`、其它 `tests/`、`VALUE_SYNONYMS` 均未改。

## 3. 判据运行结果原文

```
$ python -m pytest tests/test_value_synonym_and_granularity.py -q
......                                                                   [100%]
6 passed in 0.03s

$ python -m pytest tests/ -q --tb=line
785 passed, 139 subtests passed in 36.81s
```

判据落地时的红样（修复前，作为缺陷存在的证据）：
`2 failed, 4 passed` ——
`test_suspension_spelling_family_is_folded`（悬架/悬挂 仍判异）、
`test_price_unit_suffix_folds_to_one_shape`（`'59.88万'` vs `'num:59.88'`）；4 条红线当时即绿。

红线守卫组（修复前基线 `68 passed` → 修复后）：
`test_merge_matching` / `test_merge_data_aliases` / `test_spu_duplicate_sku` /
`test_pages_columns_narrow_publish_paths` / `test_pages_filter_defaults_not_hard_drops` = `68 passed`，新增红 0。

判定形状（修复后实测）：

```
麦弗逊式独立悬架 vs 麦弗逊式独立悬挂 判同=True      五连杆 vs 多连杆 判同=False
多连杆式独立悬架 vs 多连杆式独立悬挂 判同=True      标配 vs 选装     判同=False
59.88万 vs 59.88万元 判同=True                     6 vs 5.815m     判同=False
59.88万 vs 60.88万 判同=False
```

## 4. 红线自查

1. **只改比较键、不改存储值**：改动只在 `canonical_compare` 内；`canonical_value`（存储用）未动，
   `merge_source_rows` / `_merge_existing_with_source` 写出仍取各源原值（如 `59.88万元` 保留原文写入）。
2. **没丢行、没删列**：未触碰任何行级/列级逻辑。
3. **没有按车系/品牌白名单**：无任何白名单分支。
4. **未动 `.cnb.yml`**，改动面 = `scripts/merge_data.py` + 新增判据文件。
5. **凭据**：仅 `GIT_ASKPASS` 临时脚本，已 `rm -f`；未进 URL/进程表/被跟踪文件/本报告。
6. **未用** `--no-verify` / `SKIP_TESTS` / `SKIP_REVIEW`；判据文件未被修改凑绿。
7. **`上市时间` 未加特判**（Issue 明令）：`merge_source_rows` 的 `_DATE_FIELDS` 精细取值路径本来就绿，
   判据第 3 条实测通过；288 行属上一轮产物滞后，新一轮全量重合并消掉。

## 5. 交付产物与验证

- `git format-patch 6e25916..HEAD` → `issue81-a-class-synonym-fold.patch`
- `git bundle create ... 6e25916..HEAD` → `issue81-a-class-synonym-fold.bundle`
- 同一对文件随后经 Issue 资产通道**回读校验**（GET 首跳带凭据、不自动跟跳转）：
  `patch http=200 bytes=8229 sha256 一致=True`、`bundle http=200 bytes=3883 sha256 一致=True`。
- 链接见 Issue #81 最新评论（官方 `comment-file-asset-upload-url` 通道上传，PUT 200）。

`effective_max_turns`：本会话上限 150，已用约 27 轮，**剩余约 123 轮**。
