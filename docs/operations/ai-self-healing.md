# Pages 发布前审计与 AI 自愈设计

> 状态：设计文档；最后核验日期：2026-07-28
> 本文同时记录 2026-07-28 易车合并/发布链调查结论。文中明确区分“已验证”“待修”“待核实”。本次文档提交不修改任何生产 workflow、模型配置或发布门禁。

## 1. 本次调查摘要

### 1.1 已验证：第一层易车合并缺陷已修复

`b33e85a`（`fix: safely merge high-confidence Yiche rows`）修复了 `scripts/merge_data.py` 的易车高置信匹配控制流，包括双边一对一约束、年款/能源/级别冲突拒绝、来源前缀原子化和三源字段保真。

验证记录：

- 定向测试：42 passed。
- 全套测试：222 passed，另有 23 个 subtests passed。
- 合并分析 run `30316322071` 成功，生成 Release `v20260728-0807-30316322071-a1`。
- 对应 Pages run `30316931670` 成功。
- 实际合并日志记录“易车补充 512”。

### 1.2 已验证：旧线上 2,059 条“仅易车”漏斗

| 互斥分类 | 数量 | 含义 |
|---|---:|---|
| A | 445 | 其他来源没有候选 |
| D | 349 | 候选低于当时的匹配阈值 |
| E | 196 | 一对多或并列歧义，安全拒绝 |
| F | 1,013 | 旧控制流中存在唯一高置信候选但未合并 |
| H | 56 | 年款错位 |
| B / G | 0 | 未发现 artifact 陈旧或发布门禁直接导致 |
| **合计** | **2,059** | 与调查输入总数一致 |

> 注意：这套 A–H 分类描述的是修复前的旧漏斗；生产运行的“512 条接受结果”来自修复后的更严格 matcher。不能用 `2059 - 512` 给剩余记录擅自赋予旧分类语义。

### 1.3 待修：发布基线保护器吞掉来源富化

合并器接受了 512 条易车补充，但最终 Release 中只有 165 条记录同时包含易车和汽车之家/懂车帝来源，差额为 347。

已验证根因在 `scripts/preserve_publish_baseline.py`：`preserve_rows()` 先复制旧 baseline；candidate identity 若已存在，就计入 `overlap_kept_baseline` 并跳过。因此同 identity 的新来源、`易车匹配方式`及空字段补全被旧 baseline 行覆盖。

当前状态：

- 第一层 `merge_data.py` 修复已经部署。
- 第二层 `preserve_publish_baseline.py` 修复尚未编写、评审或部署，不能视为闭环。
- 对最终已发布 165 条多源易车记录的流式审计未发现年款、能源、级别冲突或嵌套来源前缀。

### 1.4 来源排序结论

- **已验证**：汽车之家入口使用动态月销量数据排序。
- **已验证**：易车当前按接口返回原始顺序消费，缺少可靠的跨 run 游标。
- **待核实**：懂车帝当前品牌顺序没有证据证明是动态销量或动态热度，因此文档和 UI 不应把它称为“实时热度”。

### 1.5 Modal Sandbox 与排名 API 探测

- **已验证**：Modal Sandbox 以 20 秒间隔连续完成 `probe-0` 到 `probe-18`，长时间执行期间未中断。
- **已验证**：worker 结束并 cleanup 后 Sandbox 进入 detached 状态，随后 3 次 `sync_back` 都返回 `Unable to perform operation on a detached sandbox`。因此自愈 worker 必须在 Sandbox 终止前完成 commit/push、artifact 上传或显式结果回传，不能依赖结束后的补同步。
- **已验证**：易车排名 API 探测成功生成 69,495 字节报告，包含车系 ID、名称和品牌信息。
- **待核实**：这份报告只证明接口可返回排名列表，不能单独证明排序依据、实时性或跨 run 稳定性。

## 2. 当前自动化的真实状态

| 组件 | 当前行为 | 缺口 |
|---|---|---|
| `AI_Auto_Fix_Monitor.yml` | 只监听“汽车之家爬虫”“懂车帝爬虫”；优先调用 `openai/codex-action@v1`，失败后才调用 `scripts/auto_fix_workflow.py` | 不监听易车、合并分析、Release 或 Pages；不能发现 512→165 这类发布链问题 |
| OpenCode / OMO 配置 | 仓库包含 `config/opencode.json`、`config/oh-my-openagent.json` 及 `ai_tools/opencode/` 副本 | 当前 workflow 没有安装或调用 OpenCode/OMO；“有配置”不等于“Action 已使用” |
| `merge-and-filter.yml` | 串行完成合并、创建 Release、Pages 部署和单源审计；支持精确 Release tag 与部署模式 | 没有 accepted-match disposition、来源富化、排序/游标、浏览器 smoke 等发布前审计 |

## 3. 目标和非目标

目标：每次正式 Release/Pages 发布之前先生成候选产物，运行确定性审计；审计失败时只对明确的代码缺陷调用 AI，修复后的新提交重新走完整链，直到通过或触发硬熔断。

非目标：

- 不允许同一个 workflow run 内无界递归“修复→重跑→修复”。
- 不允许大模型通过修改审计器、scope guard 或部署门禁让自己通过。
- 不把临时 runner 的聊天 session 当作唯一记忆。
- 网络、Provider、配额和 Runner 临时故障不应触发代码修改。

## 4. 推荐状态机

```text
main commit
   │
   ▼
构建 candidate artifact（尚未创建正式 Release）
   │
   ▼
确定性发布前审计
   ├── PASS ──► 创建精确 tag Release ──► 部署 Pages ──► post-deploy smoke
   ├── 可修代码问题 ──► AI 最小修复并提交 main ──► 原 run 结束
   │                                          └── 新 push 触发全新 candidate run
   ├── 网络/Provider/配额临时问题 ──► 有界重试，不改代码
   └── 不确定/不可修/超过轮次 ──► 冻结发布，创建或更新 GitHub Issue 并告警
```

### 4.1 有界修复

incident fingerprint 由以下规范化字段组成：

```text
审计规则 ID + 错误类型 + 首个责任文件/函数 + 数据源 + candidate commit SHA
```

candidate 阶段使用被审计的 commit SHA；正式 Release 创建后使用精确 tag 指向的 commit SHA。指纹必须去除时间戳、run ID 和具体车型值，避免同一根因因输入抖动生成新 incident。

相同 fingerprint 最多允许 2 个 AI 修复提交；第三次审计仍失败时硬冻结，不再调用 AI，只保留证据、更新 Issue 并通知用户。单次 AI job 沿用当前 25 分钟上限。

GitHub 官方还限制 `workflow_run` 最多串联三层，且有 Secrets/写权限的后续 workflow 处理不可信内容存在安全风险。因此实现应让修复提交触发新的正常 push run，而不是堆叠无界 `workflow_run` 链。

## 5. 发布前确定性审计契约

AI 只能消费审计结果，不能替代审计器。建议每项审计都输出稳定 `rule_id`、机器可读 JSON 和非零退出码。

| 规则 | 必须验证的内容 | 失败行为 |
|---|---|---|
| 身份超集 | candidate 不得丢失 last-known-good baseline identity | 阻断 |
| 匹配 disposition | 每条 accepted match 必须恰好归入一个互斥结果桶 | 未归类、重复归类或 baseline 冲突均阻断 |
| A–H 漏斗 | 分类互斥、总和等于输入，保留 row-level 证据 | 阻断 |
| 硬冲突 | 年款、能源、级别、车型关键 token 不冲突 | 阻断 |
| 来源语义 | 无嵌套来源前缀；新增来源必须在最终行和 manifest 中可追踪 | 阻断 |
| 来源覆盖 | 单源/多源数量、增量、突然下降和异常集中度 | 超阈值阻断或人工复核 |
| 排序与游标 | 排序依据有证据；游标持续前进；artifact 不陈旧 | 陈旧/停滞阻断发布并分类 |
| 发布一致性 | candidate SHA、Release tag、文件 SHA-256、rowCount、Pages manifest 完全一致 | 阻断 |
| 前端 smoke | 页面和资源正常加载，默认筛选生效，多源样本可检索 | 回滚/阻断 |

### 5.1 disposition ledger

每条 accepted match 至少输出：

```text
record_id, bucket, rule_id, source, candidate_sha
```

建议结果桶：

- `published_enriched`
- `approved_publish_exclusion`
- `identity_dedup`
- `baseline_preservation_conflict`

必须满足：互斥、无遗漏、各桶总和等于 accepted 数量。`baseline_preservation_conflict` 默认阻断，除非存在人工评审过的规则豁免。

本次 incident 的回溯验收是：512 条 accepted match 中，当前 165 条应由审计器给出 `published_enriched` 行级证据；其余 347 条应由规则自动识别为 `baseline_preservation_conflict` 并阻止正式发布。这里描述的是未来审计器必须达到的行为，不表示审计器已经实现。

### 5.2 前端 smoke 的最低标准

- manifest 写入精确 Release tag 和 candidate SHA。
- HTTP 200；manifest `rowCount` 与 payload 流式计数一致。
- 核心 JavaScript/CSS 成功加载；浏览器无 uncaught exception 和 error 级 console 消息。
- 首次加载和恢复默认实际应用：百公里加速 ≤ 7 秒、最高车速 ≥ 180 km/h、纯电续航 ≥ 150 km 且无上限。
- 抽样多源记录可通过页面筛选/搜索检索。

浏览器和大数据验证在 GitHub Actions 或 Modal 中执行；RackNerd 宿主机只做编排、轻量检查和 CI 闭环监控。

## 6. AI 修复安全边界

### 6.1 哪些问题才允许修

只有确定性审计能定位到责任文件/函数、且分类为可修代码问题时才调用 AI。临时网络、Provider、配额、GitHub Runner、权限和上游站点限流问题不允许改代码。

Phase 2 中“AI”特指当前已有的 `openai/codex-action@v1`。OpenCode+OMO 只有完成 GitHub-hosted runner 的非交互 E2E 后，才能成为替换或补充候选。

### 6.2 最小修改范围

允许路径按 `rule_id` 动态映射到最小集合。例如：

- matcher/publish enrichment：`scripts/merge_data.py`、`scripts/preserve_publish_baseline.py` 和对应 tests。
- 单一爬虫：仅该爬虫脚本、解析 fixture 和对应 tests。
- 未分类问题：空 allowlist，直接冻结。

### 6.3 不可信工作区与信任根

以下属于保护信任根，自动修复不得修改：

- 发布前审计器及其基准策略；
- AI scope guard；
- review gate、marker 和候选 diff hash 逻辑；
- workflow 权限、Secrets 配置与部署门禁；
- `AGENTS.md` 和自动修复权限策略。

scope guard 必须从 incident 起始的 known-good commit blob 读取并校验 SHA，不能执行 AI 可修改的工作区版本。信任根变更只能作为独立用户任务，重新经过两家不同模型家族评审。

本仓库是用户自有、非 fork，遵循仓库规则：不创建功能分支或 PR；AI 修复只有在测试、最小 scope、两家独立最终评审和 review gate 全部通过后，才可提交到默认分支。禁止 force push、禁止 `--no-verify`。

### 6.4 密钥和权限

- API key 仅通过 GitHub Secrets 注入；不得进入 prompt、artifact、cache、日志、diff 或 commit。
- 使用最小 `GITHUB_TOKEN` 权限；修复 job 与发布 job 分离。
- 使用 `concurrency` 串行化同一数据源/incident，避免并行修复互相覆盖。
- AI 不得删除失败测试、降低阈值或扩大豁免范围来“修复”问题。

## 7. Action AI 怎样拥有记忆

GitHub-hosted runner 是临时环境，因此模型不会天然跨 run 记住前一次对话。正确做法是把记忆外置为可审计数据，而不是依赖某个 CLI session。

| 层级 | 载体 | 用途 | 是否是真相来源 |
|---|---|---|---|
| 长期项目知识 | 版本化、脱敏的仓库文档和回归 fixture | 数据流、已知根因、不可变约束、测试样例 | 是，需评审 |
| incident 状态 | GitHub Issue 中的结构化 ledger | fingerprint、尝试次数、责任规则、run/commit、当前状态 | 是，跨 run |
| 单次证据 | Actions artifact | 审计 JSON、日志摘要、测试报告、diff hash | 否；设置明确 retention |
| 可重建加速 | Actions cache | 依赖、浏览器和可重建下载 | 否；可能 miss/淘汰，禁止存密钥 |
| Agent session | Codex/OpenCode/OMO session | 单次推理上下文 | 否，不能作为唯一记忆 |
| 外部持久 Agent | RackNerd Hermes memory/skills | 跨 run 编排和程序性经验 | 辅助；不能覆盖仓库事实与审计结果 |

建议 incident Issue 至少保存：fingerprint、`rule_id`、candidate SHA、失败桶统计、最多两次修复 commit、测试/评审链接、last-known-good tag 和最终状态。这样即使换模型、换 Runner 或会话损坏，下一次 agent 仍可重建上下文。

GitHub cache 只用于依赖和可重建内容。GitHub 官方说明缓存不可原地修改、存在访问边界和淘汰策略，并明确不应缓存访问令牌或登录凭据。

## 8. OpenCode+OMO 与 Hermes 的选择

### 8.1 当前 OpenCode+OMO 是否“已经够用”

不能把当前状态称为“Action 已安装且够用”：

- 仓库只有 OpenCode/OMO 配置文件；当前 workflow 没有安装或调用它们。
- 当前真正使用的是 Codex Action，已经具备一次性代码修复入口。
- 第一阶段的确定性审计完全不需要大模型。
- OpenCode+OMO 若要接管修复或多模型评审，仍需在 GitHub-hosted runner 做非交互安装、凭据注入、超时、scope guard、diff 导出和清理的 E2E 验证。
- 即使 OpenCode+OMO E2E 通过，跨 run 记忆仍必须按第 7 节外置。

结论：Phase 1 使用确定性脚本；Phase 2 先复用现有 Codex Action。暂时没有必要为了“记忆”在 Action 中增加 OpenCode+OMO。

### 8.2 是否在 Action 中安装 Hermes-Agent

不建议。每个 GitHub-hosted runner 都是临时机，安装 Hermes 只增加启动时间、依赖面和凭据面；如果不额外恢复状态，它的 memory/skills 同样不会凭空跨 run 持久化。

若未来需要真正持久控制面，推荐把现有 RackNerd Hermes 作为可选 Phase 3：

- GitHub 通过 Hermes 官方 HMAC webhook，或 Hermes 定时轮询，发送 workflow/incident 事件；
- Hermes 使用持久 memory/skills 汇总历史，将重型测试、浏览器和大 artifact 任务下发 Modal/GitHub Actions；
- Hermes 不可达时 Action 必须 fail closed：冻结发布、创建/更新 Issue，不等待也不绕过审计；
- Phase 2 不依赖 Hermes；Phase 3 未上线不阻塞前两阶段；
- Hermes 活配置不能由本仓库 Action 修改，仍须在私有配置仓库形成候选并原子应用。

## 9. 分阶段落地

### Phase 1：只读审计与发布阻断

1. 从合并结果生成 candidate artifact，不先创建正式 Release。
2. 增加流式发布前审计器和 disposition ledger。
3. 将本次 512→165 incident 固化为回归 fixture/测试。
4. 审计通过后才创建精确 tag Release 和部署 Pages。
5. 审计失败时上传 artifact、创建/更新 Issue，暂不自动改代码。

### Phase 2：接入现有 Codex Action

1. 只对明确 `rule_id` 调用 Codex。
2. 将审计 JSON、最小代码路径和验收测试注入 prompt。
3. 从 known-good commit 执行 scope guard。
4. 运行 TDD、语法/配置校验和两家最终评审。
5. 修复 push 后结束原 run，由新 push 重走 Phase 1。

### Phase 3：可选外部 Hermes 控制面

1. 配置 HMAC webhook 或有界轮询；定义健康检查和告警。
2. 恢复脱敏 memory/skills，但把仓库文档、fixture 和审计 JSON作为事实源。
3. Hermes 只做跨 run 编排、轻量检查和调度；重型任务继续交给 Modal/GitHub Actions。
4. Hermes 不可用时回退到 Phase 2 的冻结+Issue，不降低门禁。

## 10. 回滚和故障响应

last-known-good 必须是最近一次满足以下条件的精确 Release tag：发布前审计全绿、disposition 无未批准冲突、Pages smoke 通过、manifest 与 payload SHA/rowCount 一致。

若部署后才发现异常：

1. 冻结新的正式发布。
2. 使用 last-known-good 精确 tag 重新运行 `merge-and-filter.yml` 的 `deploy_and_audit` 模式。
3. 不删除坏 Release；在 incident Issue 中记录 tag、SHA、审计结果和回滚 run。
4. 修复后重新从 candidate 开始，不直接覆盖旧产物。

告警以 GitHub Issue 为持久入口；外部消息只作为通知，不作为唯一 incident 记录。

## 11. 一手参考资料

核验日期：2026-07-28。

- Hermes Persistent Memory：<https://hermes-agent.nousresearch.com/docs/user-guide/features/memory>
- Hermes Cron：<https://hermes-agent.nousresearch.com/docs/user-guide/features/cron>
- Hermes Webhooks（HMAC、过滤、持久订阅）：<https://hermes-agent.nousresearch.com/docs/user-guide/messaging/webhooks>
- GitHub `workflow_run`（最多三层及权限风险）：<https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run>
- GitHub workflow artifacts：<https://docs.github.com/en/actions/tutorials/store-and-share-data>
- GitHub dependency cache 安全与淘汰：<https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching>
