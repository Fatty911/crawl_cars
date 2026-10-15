# 交付报告 — SKU 归并：车款ID 进键 + 归并逻辑接入合并主链路

**状态**：`PUSHED agent/sku-dedupe-by-id -> <sha>`（GitHub `Fatty911/crawl_cars`）。
说明：CNB 本月核时限额已用完，本单不走 CNB 派发链，直接在工作克隆上改、在 GitHub 提 PR；
判据三向自校与全套回归均在本地实跑。

## 一、根因（全部线上实测，2026-10-15 发布面 filtered，14097 行）

1. **`identity_key` 里没有车款ID**：`scripts/publish_identity.py:153` 的
   `identity_key` 返回 `("series_id", 车系ID, 车型名称, 年款)`，而合并主链路的去重
   （`scripts/merge_data.py` main）就按它判重。同一 SKU 跨源时**车系ID 不同、名称写法不同**，
   于是各成一行 ⇒ 发布面 **1095 个车款ID 出现多行、涉及 2327 行**。
2. **`dedupe_merged_rows` 从未被主链路调用**：grep 全仓，它只在
   `scripts/audit_pages_payload.py:83` 和 `scripts/verify_publish_superset.py:32`
   （审计/校验脚本）里被调用；合并主链路一次都没调用过——真正该归并的地方没归并。
3. **模糊键 `core_name` 三重脆弱**（`_sku_core_name` 返回字符串）：
   - 词序：`六座版Pro` → `六座版pro` vs `…Pro 六座版` → `pro六座版`
   - 数字：`1.5T Halo 六座` → `thalo六座` vs `…1.5T Halo 6座` → `thalo 座`（6 被当裸数字剥掉）
   - 前缀：`腾势N9 2026款…` vs `腾势N9 DM 2026款…`（同 ID 挂在两个车系名下）

## 二、改动清单（4 处，全部在 `scripts/merge_data.py`）

| 位置 | 改动 |
|---|---|
| `_sku_core_name` → `_sku_core_tokens` | 字符串 core 改为 **frozenset**；年款及其之前的前缀整段丢（只认四位年份或"两位+款"，防 `1.5T` 被小数点归一化后当成款吃掉的坑）；阿拉伯数字翻中文再比（6座==六座，1.5T != 2.0T）；按 CJK/拉丁边界切词，CJK 段再按"版/型"切子词并去尾缀 ⇒ 词序无关 |
| `dedupe_merged_rows` 的键 | 有 `车款ID` 时键 = `("sku", 车款ID, 年款, 价格, tier, seat, trims, core_tokens)`，**不再带车系**（同 ID 会挂两个车系名）；无 ID 时保持原键（带车系）。**年款按用户裁定始终在键里：年款不同 = 不同 SKU** |
| base 选择 | 并列时优先"价格干净"（不带 `|` 合并串）的那一行，否则合并串价格会盖掉规范化单价 |
| `main()` | 在 identity_key 去重之后**补上从未被调用的** `dedupe_merged_rows(all_rows)`，并打印归并前后行数 |

## 三、判据与三向自校

新增 `tests/test_sku_dedupe_by_id.py`（6 条）：

| 方向 | 结果 |
|---|---|
| ① 补丁后 | **6 passed** |
| ② 未打补丁（pristine） | **2 failed**（A 条同 ID 归并不成立 + token 口径函数不存在） |
| ③ 变异：键里去掉车款ID | A 条 **变红** |
| ③ 变异：键里去掉年款 | B 条（年款不同必须分开）**变红** —— 锁定用户裁定 |

夹具全部取**现网真实形状**：乐道L90 76215（三行同名异源）、领克900 72145（异名异车系ID）、
腾势N9 77164（同 ID 两个车系名）、乐道L90 76423（CJK 段内词序）、凯翼昆仑L8 74526（同 ID 跨年款）、
奥迪Q5 e-tron 52586（同 ID 异配置异价）、阿维塔07 74558/74885（增程版 vs 增程版 52.01kWh）。

## 四、现网复算（补丁后的 `dedupe_merged_rows` 跑在发布面 14097 行上）

| 指标 | 补丁前 | 补丁后 |
|---|---|---|
| 行数 | 14097 | **13395**（移除 702 行同 SKU 多行） |
| 重复车款ID 组 | 1095 组 / 2327 行 | **524 组 / 1140 行** |
| 领克900 | 15 行 / 7 组重复 | **8 行 / 0 组** |
| 乐道L90 | 32 行 / 13 组重复 | **15 行 / 0 组** |
| 阿维塔07 | 11 行 / 0 组 | 11 行 / 0 组（其 52.01kWh、四驱变体异价异配置，本就不能并） |
| 幂等 | — | **OK**（一遍 13395 = 二遍 13395） |

剩余 524 组是同 ID 但核心 token 不同（异配置/异价，如奥迪Q5 的机甲/锦衣套装）——按 C 条故意保留。

## 五、边界与未做

- **年款不同绝不相较**（用户裁定）：凯翼昆仑L8 74526 的 2025/2026 两行保持两行。
- 不动 `identity_key`（它还承担发布边界校验与账本口径），只在合并去重处加 SKU 级键。
- 无车款ID 的 6443 行保持原行为（键里带车系）。
- 归并后同 ID 多车系名 16 组，逐条核过全是写法变体（腾势N9/N9 DM、小鹏/小鹏汽车、AITO 问界/AITO问界），不是跨品牌误并。
- 本单不改爬取、不改发布链、不新爬数据；只处理已爬数据的合并/关联逻辑。

## 六、被显式批准的测试契约变更（1 处，范围外零改动）

`tests/test_debug_publish_safety.py::test_dedupe_key_ignores_car_id_known_limitation`
原本**记录的就是本单要修的缺陷本身**：它断言"同价同配置的不同车款ID 会被合并成 1 行"，
并称之为已知限制。键加入车款ID 后该断言反转，故按纪律显式更新：

- 更名为 `test_dedupe_key_separates_distinct_car_ids`，改为断言
  **不同车款ID 不再被无脑合并（2 行）、同车款ID 同配置仍合并**，并留下语义变更记录与指向
  `tests/test_sku_dedupe_by_id.py` 的引用；
- 同文件 `test_row_count_decrease_fails_closed` 里一段因此过期的注释（"键不含车款ID…
  只改车款ID 会被合并成 1 行"）一并改正；
- 除上述一处用例外，`tests/` 下无任何其它改动。

## 七、全套回归

`python -m pytest tests -q`（在 origin/main=024125f 上含本单改动）：**949 tests / 1 failed / 3 skipped**。
唯一失败为 `tests/test_codeberg_publish_proxy.py::test_codeberg_push_uses_validated_proxy`——
本机无已验证代理的环境专属红，在未打补丁的基线上同样失败（本会话已在 ea2a67c 与 024125f 上实测同红），
**零新增红**。
