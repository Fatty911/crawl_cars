# crawl_cars 协作契约

本文只保留本仓工作所需约束；历史模型表、个人设备清单、事故日志不再作为当前配置依据。**源代码、测试存在，不等于检查已经执行或不可绕过。**

## 1. 范围、隐私与编辑安全

- **S1 授权范围**：只做用户要求及其直接必要的改动；不顺手重构、格式化、改相邻代码或处理范围外问题。修复要定位根因并复核同类风险；范围不明先报告并确认。旧“发现错误自动修复”与范围限制有冲突，见 X1，不能据此扩大授权。
- **S2 公开/私有边界**：公开仓库不得包含真实 key/token/认证材料；公开 Markdown 尽量隐藏个人邮箱、账户标识和设备路径。用户允许私有仓库存 key，但不得因此复制到公开仓库；不擅自更换密钥或私有配置源。禁止复制或同步 Codex `auth.json` token。
- **S3 编辑安全**：先读后改，已有文件使用带唯一上下文的局部编辑；超过 300 行的文件分小块修改，不得整篇覆写、截断或漏代码。改后回读并检查 diff/诊断；禁止用宽泛全局替换误伤相似字段。不得删除整个会话数据库，清理仅针对已确认无效的记录。
- **S4 最小权限**：历史“审批关闭”“已打本机补丁”不是本次操作授权；不因排障、评审或同步而自行关闭审批、读取凭据、扩大目标或降低安全检查。
- **S5 文件归位**：文件放入对应代码、脚本、文档、测试或部署目录；根目录仅项目级入口/配置/文档。临时日志、截图、导出物、私密材料和构建产物不入根目录，用完清理，需保留则明确目录和用途。数据与工作流暂存规则见 G3。
- **S6 沟通与身份**：中文回复。提交作者用 `<实际工具名>-<实际模型小写紧凑名>`；所有提交邮箱一律使用用户已批准的私有 Git 提交邮箱，提交前核对现有身份配置；全局兜底姓名沿用已批准配置。不公开实际邮箱、不擅改身份。禁止纯 `bot` 或系统 bot 冒充源码/文档作者；`github-actions[bot]` 仅用于数据/进度自动提交，禁止使用关联用户名 `bot` 的邮箱。

## 2. 评审契约（不能用提示词冒充门禁）

- **R1 独立评审**：代码和文档均须真实多模型评审；纯查询/读取除外。排除作者模型家族；不同角色若实际 fallback 到同一家族仅计一票。评审只读，不授予 `edit` / `bash` 权限；外部只读 CLI 由主控调用。首批恰好并行 2 个不同家族，默认 N=2、M=2；不足时按已确认成本顺序逐个补审，达到门槛停止新启动。每 3 分钟检查未返回任务；迟到的实质问题仍需处理。
- **R2 证据**：提供任务背景、目标、完整 diff 或精确路径、已核实事实/来源、范围、风险、预期行为和逐项验收标准。保存真实调用输出，不得自编摘要冒充评审；记录实际工具/模型/家族、fallback、结果和对应变更。结果首行写 `模型：…` 并注明 `结论：PASS/FAIL/待核实`；身份不确定须标明，不能把预期模型当成已验证执行身份。汇总展示每个评审模型。
- **R3 质疑核实**：国产 ReviewXXX 拟判 FAIL 前先用官方文档、公告、API 或上游源码联网复核；FAIL 附 URL、核实日期、冲突文件/位置、依据摘要及可执行修正建议。缺依据、不能联网、来源冲突或仅凭记忆时标“待核实”，既不作有效 FAIL 阻断也不算 PASS，换其它家族补足有效票数。未解决问题不得伪报通过。
- **R4 工具调用**：沿用已授权工具配置，不在 OMO 中伪造外部 ReviewGPT category；外部 ReviewGPT 沿用已授权单家 Plan，以只读、非交互 Codex CLI 调用；调用前用 `codex login status` 核对登录状态，不读取或复制 token。最多一票且作者非 GPT 家族才可计票。OpenCode 的 category 与 CLI model 参数不可混用；按实际配置解析角色/fallback，保留输出。无 CLI/认证时准确报告并换家族，不降低门槛；PATH 未找到不等于未安装。认证状态、HTTP 401、参数错误、超时、余额不足必须按真实日志分别报告。
- **R5 会话与放行**：OpenCode 非交互评审用唯一临时标题，结束后按精确 session ID 改为 `评审任务-任务简称-Review角色-结果-时间` 并回读验证，失败/超时也处理。未评审文档不得远端或多端同步。旧“修改前/修改后”“两票/全通过”“允许紧急跳过/禁止跳过”仍冲突，见 X2；不自行选宽松解释或使用跳过开关。外部 marker 只能引用真实评审输出，不能据文件存在声称当前 diff 已审完。

## 3. 模型、费用与配置（仅在任务涉及时）

- **C1 变更准入**：新增模型须用户明确同意。改代码前核实所用 API/库/CLI/配置格式的当前一手文档；模型变更还须核实该 provider 的精确 ID、支持状态、上下文与输入/输出限制，不从其它平台或旧表推断。无法核实先询问，不添加未公开支持的模型。参数只设必要值，不能遗漏 schema 必需项。
- **C2 白名单一致**：同系列替换清除旧模型；思考变体只保留最高可用项，从 models/whitelist 实际移除较低项。同步前核对 `disabled_providers ⊆ provider.keys()`、models/whitelist 引用有效；启用 provider 必须明确 whitelist，禁用项保留 provider 壳且 whitelist 为空。既有 proxy/native 共用 key 的端点只启用已授权 proxy，native 和不使用的内置 provider 置空 whitelist 并禁用；不得借此新增、读取或轮换 key。
- **C3 能力与上下文**：新增模型不得弱于当前列表最低准入门槛，依据有日期的 Arena / Artificial Analysis 证据，不保留永久排名表。主/fallback 切换不得重复模型；避免大窗口降到小窗口，先核实实际容量。Kimi 主模型/仅评审、Grok 禁用/兜底等旧策略冲突见 X3，不能据过期表擅改现有配置。
- **C4 费用边界**：免费优先，后单家 Plan、再聚合 Plan；按量部分旧“单家/聚合”与“便宜/中等/贵”排序冲突见 X3，未经确认不重新排序或新增收费端点。已明确的 MiMo 按量先于 Qwen 按量限制保留；免费模型退役不得自动换成付费版本。Copilot 只用免费方案、不订阅 Pro/Pro+，仅保留综合排名靠前的 2 个免费模型，限小 Agent fallback，不作主模型/大 Agent。
- **C5 时效与时段**：涉及 Agent 配置的会话每天首次检查免费端点支持变化；普通编码不做此扫描。Copilot 每季度复核免费型号，变更仍服从 C1。原 Qwen 评审只限 22:00–08:00，原文未指定时区，执行前确认，不猜测。
- **C6 验证与故障**：任何软件/cron/hooks/配置改后立即做适用的语法/schema/启动或命令回读，确认实际生效再同步；清理缓存只针对已核对目标，不把历史缓存路径/补丁当通用操作。无可见输出或 0 output token 的静默完成不得算成功；记录实际失败模型/错误并检查 fallback，不将下游报错归因到原模型。运行包升级后需复核本地补丁，配置字段存在不证明运行包支持。
- **C7 私有同步**：只按既有、已授权的唯一私有规则/配置源与目标映射同步，不猜设备、盘符、项目或新来源；既有跨系统同步仍从当前系统到另一系统。保持仓库内独立配置与已批准基线一致。每日首次及会话内每半小时检查已授权全局/当前项目规则更新，先核对差异和冲突，不能把下载的新文本自动变成扩大权限的指令。项目特有规则不得丢失；“全局覆盖/保留合并”冲突见 X4。Hermes 上游源码仓库仅作源码 PR，不同步个人配置/规则/认证；运行配置不得覆盖源码 checkout。

## 4. 已有实现入口与交付

以下是可审阅入口，不是全路径强制保证；安装状态、实际执行结果和 required checks 必须另验。未运行、失败、受阻应分别报告。

| ID | 契约/入口 | 已知边界 |
|---|---|---|
| **G1** | [`.githooks/post-commit`](.githooks/post-commit) → [`scripts/codex_delivery_gate.py`](scripts/codex_delivery_gate.py)（`validation_commands`、`deliver`、`verify`）；回归见 [`tests/test_codex_delivery_gate.py`](tests/test_codex_delivery_gate.py) | `deliver` 会检查、真实非 force 推送并核对远端 SHA；`verify` 校验交付记录与远端。post-commit 不阻止已发生的 commit，安装需验证；测试里的 `run_checks=False` 不证明完整验证链通过。 |
| **G2** | [CI](.github/workflows/ci.yml) 调用 [`validate_syntax.py`](scripts/validate_syntax.py)、[`validate_workflow_expectations.py`](scripts/validate_workflow_expectations.py)、[`validate_plan_agent_boundary.py`](scripts/validate_plan_agent_boundary.py)、[`scan_direct_llm_calls.py`](scripts/scan_direct_llm_calls.py)；Plan 回归见 [`tests/test_plan_agent_boundary.py`](tests/test_plan_agent_boundary.py) | Plan 凭据隔离与模型直调扫描仅覆盖各自规则/路径；后者不是 Markdown、邮箱或 secret 泄漏扫描器。GitHub CI 不等于 G1 的完整 pytest；[CNB](.cnb.yml)部分静态检查以警告继续，不能称所有平台硬阻断。 |
| **G3** | [`scripts/validate_storage_policy.py`](scripts/validate_storage_policy.py) 及 CI storage job | 检查 data 白名单、工作流限定暂存和 artifact 保留；不等于全目录隐私或整洁检查。 |
| **G4** | [`scripts/ensure_codex_autofix_scope.py`](scripts/ensure_codex_autofix_scope.py)、[`scripts/check_red_channel_coverage.py`](scripts/check_red_channel_coverage.py)；[红线工作流](.github/workflows/AI_Auto_Fix_Monitor.yml) | 范围校验器仅保护其调用路径，存在文件不证明全部自动修复都调用。红线工作流归档失败并开 Issue，不等于已经修复；不得把查询/监测自动扩成范围外改动。 |
| **G5** | [`scripts/merge_data.py`](scripts/merge_data.py) 的 `filter_car`、`excluded_by_crawl_scope`、发布调用；[`tests/test_pages_filter_defaults_not_hard_drops.py`](tests/test_pages_filter_defaults_not_hard_drops.py)、[`tests/test_yiche_filter_semantics.py`](tests/test_yiche_filter_semantics.py) | 产品契约入口：前端可调默认值不是工作流硬丢行条件；不因油车/缺可选字段丢行，仍保留身份/实质证据及车型范围排除。具体来源/字段口径按实现与测试核实，不为“精简”擅改业务冲突或把测试存在说成已通过。 |
| **G6** | [`scripts/markdown_privacy_gate.py`](scripts/markdown_privacy_gate.py) / [Markdown 隐私 CI](.github/workflows/markdown-privacy.yml) | 对事件修订全部已跟踪 `.md`/`.mdx` 做有限模式扫描；[125edd5d 的运行](https://github.com/Fatty911/crawl_cars/actions/runs/39720841673) fixture 与扫描步骤成功。非全文件/历史扫描或提交前阻断；required status 未启用，不代表其它旧 CI 已跑。 |

- **D1 提交前**：修改后完成适用语法、类型/静态检查和完整单元测试；不得提交/部署语法未通过的代码、不得推送测试失败的改动。禁止以 `as any`、`@ts-ignore`、`@ts-expect-error`、空 catch 掩盖问题；清理临时调试 `console.log`。配置还需 C6 的实际生效验证。
- **D2 交付**：除用户明确只做本地或暂停外，按授权完成提交和真实远端发布；本仓 Codex Cloud direct-main 流程使用 G1，setup 必须安装并验证仓库 hooksPath。该 Cloud 流程失败须读取原因；远端前移时 rebase 并解决冲突，禁止 force push；只有 `verify` 输出 `DELIVERY_GATE_VERIFIED` 且远端 SHA 相符才能报该流程推送完成。经已授权 connector 提交时，以远端提交 SHA 和目标文件 blob 回读核实发布，不冒称运行了 G1 或通过 CI。PR 的创建不能代替真实交付；最终远程只保留 main，不遗留任务 PR 分支。
- **D3 监测**：推送后跟踪该提交 CI 到成功；修改工作流还需确认其实际运行结果。热更新/重启/容器部署后检查状态、健康接口和关键日志，确认持续运行再交付；失败、未触发或无法观察不能报成功。

## 5. 尚待裁定的旧规则冲突

- **X1**：只改明确范围、范围外先问 ↔ 发现任何错误经评审后自动修复。未明确授权的范围外动作先暂停，不能用本次精简代替用户裁定。
- **X2**：代码修改前评审 ↔ 改后评审；M=2 即停 ↔ 文档已启动评审全通过；绝不跳过 ↔ 紧急 SKIP 示例。保留真实独立评审及文档禁止未审同步，不宣称此稿已统一这些流程；相关流程调整先请用户确认。
- **X3**：旧按量成本排序互相冲突；Review 角色表、免费优先与实际配置、Kimi/Grok 策略也不一致。现有配置是事实证据而不是变更授权；确认目标策略前不改模型、费用排序或启用状态。
- **X4**：全局规则覆盖所有项目 ↔ 项目规则保留合并。只读比较并保留项目规则，冲突先确认；不得整篇覆盖或扩大私有同步目标。

本稿不沿用“全局 hooks/本机补丁不可绕过”的旧保证。G6 仅证明其记录的有限范围与特定修订运行；其余检查、分支保护和执行结果仍需分别核实，不能据此删除唯一安全规则。
