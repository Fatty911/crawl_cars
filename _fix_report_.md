分支 `npc/104-degrade-cause-readout`（本地提交 `4958e1e`，基线 `main@ab54abe`）｜实测模型 `deepseek-v4.1-flash`（npc:go）｜推送 HTTP 403（`repo-code:rw` 缺失，remote 原文见下）｜开 PR HTTP 403（`POST /-/pulls` errcode 10023，缺 `repo-pr:rw`）⇒ 按 Issue 口径走附件交付。

# Issue #104 修复报告：易车降级身份/403 成因分类读数

## 1. 根因

`scripts/crawl_yiche.py` 走到「仅降级身份」与「403 后无真实配置」两条分支时只累加计数
（`stats["degraded_identity"]` / `stats["failed"]`），不记录成因。每轮 471 次降级身份
死在哪一环不可见。修复=在这两条分支各按代码已有环节记一个成因码，只进「易车抓取统计」打印行。

## 2. 改动清单（2 文件，214 增 / 0 删，未动任何既有行）

| 文件 | 改动 |
|---|---|
| `scripts/crawl_yiche.py` | 新增 75 行：`DEGRADE_CAUSE_CODES`（10 码，`:1608`）、`classify_degraded_identity_cause`（`:1622`）、`classify_after_403_cause`（`:1643`）、`degrade_cause_counts` 局部初始化（`:1677`）、两分支累加（`:1906`/`:1945`）、打印行追加（`:2022-2023`） |
| `tests/test_yiche_crawler.py` | 尾部新增 3 例（139 行，纯追加，既有 1168 行逐字节未动） |

成因码（10 个）：

- 降级身份分支 6 个：`waf_shell_page`（200 但壳页）、`validate_rejected`（页面有行但全员校验否）、`serial_id_missing`（无 serial ⇒ API 未调用）、`config_api_error`（API 请求失败）、`config_api_empty`（API 0 条）、`sale_page_rejected`（API 给过行、裁决全否）
- 403/429 后分支 4 个：`after_403_no_serial_id`、`after_403_config_api_error`、`after_403_api_empty`、`after_403_sale_page_rejected`

分类函数用关键字参数，调用点显式传各环节证据；`degrade_cause_counts` 是 `crawl()` 局部 dict，
**不进 `stats`、不进断点文件** `crawl_state/yiche_frontier.json`（守住 5MB 回推体积闸）。

## 3. 判据运行结果原文

```
$ python -m pytest tests/test_yiche_crawler.py -q        # 改前
62 passed in 4.67s
$ python -m pytest tests/test_yiche_crawler.py -q        # 改后
65 passed in 4.83s
```

新增 3 例注入 HEAD 源码（去掉改动）全部转红（`统计行里没有 degrade_cause.* 读数`），
带改动全绿 ⇒ 非恒绿用例、双向成立。

## 4. 全量套件失败集合差异

- 改前：`801 passed, 139 subtests passed in 31.05s`，失败集合 `{}`
- 改后：`804 passed, 139 subtests passed in 31.80s`，失败集合 `{}`（+3 即新增用例）
⇒ 新增红 0，消失红 0。

## 5. 顺带发现（本单不要求修，点名）

`scripts/crawl_yiche.py:1462`（HEAD 原文）：`approve_rows_from_sale_page` 的回退分支里
`sale_ids.update(ids)` / `:1463 sale_names.update(names)` 引用了未定义变量 `ids`/`names`
（上一行只算了 `page_html`，从未调用 `extract_sale_model_refs(page_html)`）。触发条件=
必须走到在售页回退（`serial_id` 缺失或状态 unknown 且有 200 响应），一旦触发是 `NameError`，
会被外层 `requests.RequestException` 之外的 except 链漏接。属代码缺陷非风控，本单按边界未动。

## 6. 交付实况

- 分支 `npc/104-degrade-cause-readout`（提交 `4958e1e`）本地已存在；push 实测 remote 原文：
  `Your token does not have the repo-code:rw scope required to push to this repository.`
- `POST /-/pulls` → `{"errcode":10023,...,"Missing required scopes: repo-pr:rw"}` ⇒ 403
- 附件（`.patch` / `.bundle` / `.tar.gz`）+ 本报告贴在 Issue #104 评论（首行 `## NPC 交付：#104 …`）

## 7. effective_max_turns

本会话 `maxTurns=150`，当前约第 95 轮，**剩余约 55 轮**。
