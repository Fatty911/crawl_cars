## 2026-07-05

### Fixed
- mihomo 控制端口超时 15s→30s，解决 420 节点加载慢导致的代理未就绪
- health-check URL `gstatic.com/generate_204`（被墙）→ `baidu.com`
- 代理连通性测试增加重试机制，避免首次连接失败
- GITHUB_TOKEN 无 workflows 权限时 push 被拒——用 temp-dir 保留本地 workflow

### Changed
- 仓库目录整理：Python 脚本→`scripts/`，配置文件→`config/`
- 上游同步工作流：改用纯 git 方案替代第三方 action

# 对话历史

## 2026-06-15

### 修改38: 筛选历史迁移到 Personal_commonly_used 并修复双源核验
- 不再使用新建的 `cars-filter-history` 独立仓库，改为在 `Fatty911/Personal_commonly_used` 的 `cars/filter-history/history.json` 保存筛选历史。
- `docs/config.js` 指向 `Personal_commonly_used` 内部历史文件，默认同步码改为 `personal-cars-filter-history`。
- 未填写 GitHub Token 的陌生访客继续匿名使用本机缓存，不会读取、写入或覆盖远端历史。
- `docs/app.js` 的双源核验键从“品牌 + 车系 + 车型名称 + 年款”改为归一化“车系 + 年款 + 车型名称”，兼容汽车之家和懂车帝字段拆分差异。
- 通过 20260615 Release 数据排查确认两源数据存在：懂车帝 7507 行、汽车之家 1123 行；原先显示 0 是前端合并键过严导致。
- 由于当前 `gh` token 缺少 `delete_repo` scope，无法删除上一轮新建的 `cars-filter-history` 仓库，已改为归档并停止使用。

### 修改37: 筛选历史改用 GitHub 私有仓库可选同步
- 使用 `gh repo create Fatty911/cars-filter-history --private --add-readme` 创建私有历史仓库，并通过 GitHub Contents API 初始化 `history.json`。
- `docs/config.js` 默认把筛选历史后端切到 GitHub 私有仓库，保留 Cloudflare Worker API 路径作为可切换后端。
- `docs/app.js` 新增 GitHub Contents API 读写逻辑：按同步码把历史保存在 `history.json` 的 `profiles` 中，保存时处理文件 SHA 与一次 409 重试。
- 网页筛选历史区新增 GitHub Token 输入、保存和清除按钮；Token 只存当前浏览器本机，不提交到公开仓库或 Pages 配置。
- README 同步说明 GitHub 私有仓库历史后端、Token 权限边界和 Cloudflare Worker 备用路径。

### 修改36: 合并发布扫描当前半月有效爬虫 artifact
- 复查最新 Release 和 Pages 未更新的原因：`merge-and-filter.yml` 只下载最近一次成功的汽车之家/懂车帝 run；两个爬虫完成半月任务后后续自动触发会成功跳过且没有数据 artifact，导致合并分析下载不到 `autoHome_*.json` / `dongchedi_*.json` 后成功跳过发布。
- 新增 `custom_scripts/download_latest_crawler_artifact.py`：按 workflow 向前扫描成功 run 的 artifacts，跳过缺失、过期、过小、非当前半月或 JSON 行数少于 50 的 artifact，只把真正可合并的数据复制到工作目录。
- `merge-and-filter.yml` 改用该脚本分别下载汽车之家和懂车帝当前半月有效数据，不再被最新的短跳过 run 挡住。
- `merge-and-filter.yml` 在合并前安装 `requests`、`beautifulsoup4`、`lxml`、`pdfplumber`、`pypdf`，避免零整比抓取步骤因缺少依赖中断。
- 由于 2026-06-15 合并产物较大，`merge-data` / `create-release` 超时放宽到 60 分钟，`deploy-pages.yml` 放宽到 30 分钟，避免合并或上传阶段被取消。
- `validate_workflow_expectations.py` 增加静态检查，防止合并工作流退回“只取最近一次成功 run”的旧逻辑。
- README 同步记录合并发布的数据 artifact 选择规则。

## 2026-06-11

### 修改35: 恢复懂车帝 step2 HTML 跨 runner 缓存
- 复查远端 `dongchedi/progress.json` 和最新 Actions 日志，确认懂车帝车系列表已缓存，但 `dongchedi/json/*.html` 被 `.gitignore` 排除且没有跨 GitHub runner 恢复，导致每次普通续爬时 `crawled_series` 被一致性检查重置，看起来总从 0 开始。
- `crawl-dongchedi.yml` 在 step1 前新增 `actions/cache` 恢复 `dongchedi/json/`，cache key 按当前半月周期加 run id 保存，restore key 按半月周期回退到最近一次缓存。
- 强制重跑或进入新半月周期仍会清空旧 HTML，不会把上一周期页面误用于新一轮；普通分段续爬会先恢复 HTML，再校验 `crawled_series`。
- 新增缓存文件数日志，方便从 Actions 日志直接判断本次 runner 是否恢复到 HTML 页面缓存。
- README 同步说明懂车帝 step2 HTML 缓存与 `crawled_series` 的关系。

### 修改34: 增强爬虫 workflow 进度同步、artifact 上传和网络异常恢复
- 复查最近 40 条 workflow：当前源码后的 CI、Pages、合并分析、外部触发器和汽车之家均成功；唯一失败的懂车帝 run 是旧提交上 step2 正常 `exit code 10` 后进度同步失败。
- `custom_scripts/git_sync_progress.sh` 的直连重试现在会显式清除 `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` 环境变量，避免日志显示直连但 Git 仍走 mihomo。
- 进度 rebase 失败时新增空提交/空 rebase 自动 `rebase --skip` 处理，并保留进度 JSON 冲突合并逻辑。
- 汽车之家、懂车帝 workflow 在上传 error-log 或数据 artifact 前清空代理环境，避免 `actions/upload-artifact` 经本地代理请求 GitHub API 时 `ECONNRESET`。
- `crawl_dongchedi.py` 新增 `DCD_NETWORK_ERROR_RESTART_THRESHOLD`，连续 `net::ERR_CONNECTION_*` 导航异常默认 5 次后重启 Chrome，减少坏浏览器/坏代理链路持续浪费运行窗口。

## 2026-06-11

### 修改33: 配置 cron-job.org 并增强进度同步诊断
- 使用 cron-job.org API 创建/更新汽车爬虫外部触发任务：北京时间 08:30 和 13:30。
- `custom_scripts/configure_cron_job_org.py` 增加 API/network 短暂失败重试，避免连接超时导致只配置一半。
- `custom_scripts/git_sync_progress.sh` 改为显式 `fetch → rebase → push`，失败时打印脱敏后的 Git 错误，便于定位进度同步失败。

## 2026-06-10

### 修改32: 改为 cron-job.org 外部触发并统一长窗口预算
- 移除汽车之家、懂车帝主爬虫 workflow 对 GitHub Actions `schedule` 的依赖。
- `crawl-trigger.yml` 改为 cron-job.org 外部入口，接受 `trigger-crawl` 后默认同时拉起汽车之家和懂车帝。
- 爬取窗口统一为北京时间 `08:00-12:30`、`13:00-22:00`，并移除额外随机启动延迟。
- 新增 `custom_scripts/crawl_budget.py`，长步骤按当前窗口剩余时间和 GitHub Actions 6 小时剩余时间取更早截止点，预留进度提交缓冲。
- 新增 `custom_scripts/configure_cron_job_org.py`，用于创建或更新北京时间 08:30、13:30 两个 cron-job.org `repository_dispatch` 任务。

## 2026-06-08

### 修改31: 增加零整比属性、来源明细和 Pages 展示
- 新增 `scripts/crawl_zero_to_whole_ratio.py`，可抓取中保研/中保协/中汽修协公开发布的汽车零整比 PDF/HTML，并兼容本地 `zero_to_whole_manual.csv/json` 补充数据。
- 默认从中国保险行业协会/中国汽车维修行业协会公开 PDF 抽取零整比，当前本地验证可从两个 PDF 抽取 291 条来源记录。
- `scripts/merge_data.py` 新增零整比 enrichment：按车型名称、车系和包含关系匹配；同一车型匹配到多个来源时计算平均 `零整比`，并保留 `零整比来源明细` 与 `零整比匹配方式`。
- `docs/app.js` 把 `零整比`、`零整比来源明细` 加入 Pages 常用列，下载区增加零整比来源 JSON。
- `merge-and-filter.yml` 在合并前运行零整比抓取，并把 `zero_to_whole_ratios_YYYYMMDD.json` 纳入 artifact、Release 和 Pages 产物。
- CI 冒烟测试增加两来源零整比平均值断言，确保 `330.50%` 这类平均结果写入筛选车型。
- README、DOCKER_DEPLOY 同步记录零整比脚本、来源配置、工作流和 Pages 字段。

## 2026-06-08

### 修改30: 懂车帝连续 renderer timeout 后自动重启 Chrome
- 复查懂车帝长跑日志发现 `Timed out receiving message from renderer` 被脚本捕获后会继续爬取，属于单车系页面加载异常，不是 workflow 失败。
- 当前长跑 `27117329232` 最后因 `exit code 10` 正常提交进度；远端进度显示 `series_list=4692`、`crawled_series=131`，懂车帝本半月还没全量完成。
- 为避免 Chrome renderer 连续超时后进入坏状态拖慢 step2，`crawl_dongchedi.py` 新增 `DCD_RENDERER_TIMEOUT_RESTART_THRESHOLD`，默认连续 3 次 renderer timeout 后重启 Chrome 并继续。
- `crawl_series_config()` 现在返回当前活动 browser，外层会关闭重启后的新 browser，避免 runner 残留浏览器进程。
- CI 中 `actions/checkout`、`actions/setup-python`、`actions/setup-node` 升级到官方最新 v6 版本，消除 GitHub Actions Node.js 20 deprecation annotation。
- README 同步记录新环境变量。

## 2026-06-08

### 修改29: 消除 AI Auto Fix Monitor 缺少 error-log artifact 的误报注解
- `AI_Auto_Fix_Monitor.yml` 不再使用 `actions/download-artifact` 下载可选的 `error-log`，避免成功爬虫 run 没有错误日志 artifact 时产生 `Artifact not found` annotation。
- 改为通过 `gh run download --name error-log` 在 shell 中静默尝试；找不到 artifact 时继续使用 `gh run view --log` / `--log-failed` 抓取日志，不影响分类和 Codex 自修复。
- README 同步说明成功 run 缺少 `error-log` 属于正常情况。

## 2026-06-08

### 修改28: 上午窗口前移到 8 点并接入 Codex 自修复
- `crawl-autohome.yml`、`crawl-dongchedi.yml` 的上午备用 schedule 从 UTC `01:07-03:52` 前移为 UTC `00:07-03:52`，对应北京时间 `08:07-11:52`。
- 两个主爬虫 workflow、`crawl-trigger.yml` 和手动 `run_profile=auto` 的上午启动窗口统一改为北京时间 `08:00-12:30`；下午 `13:00-13:30`、下午长跑预算和半月完成后跳过规则保持不变。
- `AI_Auto_Fix_Monitor.yml` 改为 Codex 优先的自修复监控：失败时先分类，成功时也检查是否出现长爬虫窗口外启动；需要修代码时优先调用 `openai/codex-action@v1`，未配置 `OPENAI_API_KEY` 或 Codex 执行失败时再回退旧版多 Provider 修复器。
- 新增 `custom_scripts/check_workflow_expectations.py`、`ensure_codex_autofix_scope.py`、`validate_workflow_expectations.py`，分别负责运行结果预期检查、Codex 修改范围白名单、静态 workflow 规则校验。
- CI 新增 workflow 预期校验，防止上午 8 点窗口、Codex 自修复护栏或关键 schedule 后续被误改。
- `validate_syntax.py` 在 Windows 控制台下强制使用 UTF-8/替换错误输出，并修复显式传入相对路径文件时的仓库根目录解析，避免校验脚本自身失败。
- README 与 DOCKER_DEPLOY 同步更新上午窗口、Codex 自修复、`OPENAI_API_KEY` 和新增辅助脚本说明。

## 2026-06-07

### 修改27: 阻止手动默认触发在窗口外启动爬虫
- 复查最新运行发现懂车帝 `workflow_dispatch` 可在北京时间 18:31 以默认 `run_profile=auto` 落到 afternoon 并运行长步骤。
- `crawl-autohome.yml`、`crawl-dongchedi.yml` 的 `Configure crawl window` 增加 `id: window`，后续长步骤统一检查 `steps.window.outputs.skip`。
- 两个主爬虫 workflow 现在对 schedule、随机触发和手动默认触发都执行 09:00-12:30 / 13:00-13:30 时间窗守卫，窗口外直接成功跳过；`auto` 在 13:00-13:30 会正确归为 afternoon。
- README 同步补充手动默认触发也受时间窗约束。

### 修改26: 修正上午截止时间并补齐汽车之家超时缓冲
- 复查最新 Actions 日志确认懂车帝失败 run 发生在旧提交，当前源码已具备进度 JSON 冲突合并能力。
- 修复两个主爬虫 workflow 的上午动态缩短误算到北京时间 14:30 的问题，恢复为 12:30 截止并预留 15 分钟缓冲。
- 汽车之家 step1 增加与懂车帝 step2 同类的 workflow 总时长预算扣减，避免下午长跑因 checkout/setup/proxy 耗时贴近 GitHub 6 小时边界。
- README 同步更新上午截止、随机触发窗口和长步骤提交缓冲说明。

### 修改25: 对齐并清理 OpenCode 配置
- 确认当前 `main` 与 `origin/main` 没有未推送提交，待处理的是本地未提交配置改动。
- 将仓库根目录与 `ai_tools/opencode/` 下的 `config/opencode.json`、`config/oh-my-openagent.json` 同步为全局 OpenCode 最新配置。
- 移除 `config/opencode.json` 中不受支持的 `disabled_providers` 字段，继续依赖自定义 Provider + whitelist 控制可见模型。
- 移除 Copilot Haiku 相关条目，避免 TUI 显示已要求隐藏的弱模型。
- 在 `AGENTS.md` 固化仓库 OpenCode 配置必须与全局配置对齐的规则。

### 修改24: 恢复爬虫调度窗口并修复进度同步冲突
- `crawl-autohome.yml`、`crawl-dongchedi.yml` 恢复上午 `01:07-03:52 UTC`、下午 `05:07/05:17/05:27 UTC` 的备用触发，避免每 3 小时 schedule 导致下午 14 点多才启动。
- 两个主爬虫 workflow 的 schedule 守卫恢复为上午 09:00-12:30、下午 13:00-13:30；并发组重新按运行窗口区分，避免上午和下午互相阻塞。
- 汽车之家 step1 和修复后重试改用运行时 `$RUN_TIME` / `$MAX_CARS`，确保上午动态缩短真正生效。
- `crawl-trigger.yml` 对 `repository_dispatch` 也执行时间窗检查，外部触发不再绕过 09:00-12:30 / 13:00-13:30 限制。
- 完成半月全量爬取后恢复直接跳过，不再进入增量模式继续爬新增车系。
- 新增 `custom_scripts/merge_progress_json.py`，`git_sync_progress.sh` 遇到 `progress.json` / `dongchedi/progress.json` rebase 冲突时合并进度列表，避免远端版本覆盖本地刚保存的爬虫进度。
- README 同步更新进度同步冲突合并说明。

## 2026-06-04

### 修改23: 防止懂车帝 step2 触发 6 小时取消后丢失进度
- `crawl-dongchedi.yml` 记录 workflow 启动时间，并在 step2 前按 GitHub 6 小时硬限制重新缩短 `RUN_TIME`，预留 1800 秒用于提交进度。
- 懂车帝 step1、step2、修复后重试统一使用运行时 `$RUN_TIME`，确保前置步骤写入的动态时长生效。
- `crawl_dongchedi.py` 为 Selenium 页面加载设置 `DCD_PAGE_LOAD_TIMEOUT=60` 秒，避免单页卡住导致越过提交缓冲。
- README 同步更新懂车帝运行时长、页面加载超时和分段续爬说明。

### 修改22: 优化 AI 自动修复器 Provider 策略和监控工作流退出逻辑
- `AI_Auto_Fix_Monitor.yml` 在 `scripts/auto_fix_workflow.py` 未产出可用修复时记录为跳过并正常结束，不再把 Provider 不可用、无权限或额度耗尽变成监控工作流红叉。
- `scripts/auto_fix_workflow.py` 移除明显过时/不可用的默认模型，新增 AtomGit、NVIDIA NIM 等可靠默认 Provider，并支持 `XXXX_BASE_URL`、`XXXX_MODEL_LIST`、`XXXX_PROXY_URL`。
- 默认关闭 OpenRouter 动态排行榜模型抓取，修复排行榜映射中 `glm` 触发 KeyError 的问题。
- README 同步更新 AI 自动修复 Provider、模型和跳过规则说明。

### 修改21: 收紧爬虫失败分类，减少 AI 自动修复误触发
- `custom_scripts/classify_crawl_failure.py` 将低行数、少量车型 `无法解析config或option`、拒绝上传/合并等数据质量保护归类为 `data_quality_guard`，默认跳过 AI 修复。
- 将 AI Provider 自身 SSL 证书、401/403 权限、`/chat/completions` 调用失败等归类为 `auto_fix_provider_failure`，避免监控工作流围绕自动修复失败再次触发修复。
- 保留 `site_breakage` 对未生成数据、完全解析不到车型、配置页/接口致命异常的自动修复入口。
- 更新 README 中“触发前分类”的说明。

## 2026-06-02

### 修改20: 修复爬虫分段退出后同一 job 内反复重启
- `crawl-autohome.yml` 的 step1 收到 `exit code 10` 后只提交进度并结束本次 workflow，不再立刻重跑 step1。
- `crawl-dongchedi.yml` 的 step2 收到 `exit code 10` 后只提交进度并结束本次 workflow，不再循环到 6 小时超时或取消。
- 汽车之家剩余步骤、懂车帝 step3/4、输出校验、半月完成标记和 artifact 上传，都只在对应长步骤真正完成后执行。
- 保留真实错误的分类/自动修复入口；未完成分段退出不会触发 AI 修复。
- `merge-and-filter.yml` 在定时合并时如果两份爬虫数据尚未完整生成，会成功跳过 Release/Pages，不再用红叉表示“暂无完整数据”；手动强制合并仍保持严格失败保护。

### 修改19: 增加汽车之家爬虫 SSL 重试次数和超时
- `scripts/test_autohome.py` 的 SSL 错误重试逻辑改进：
  - 重试次数从 3 增加到 5
  - 请求超时从 15 秒增加到 20 秒
  - 退避策略改为 `min(2^(attempt+2), 20)` 秒（4/8/16/20/20）
  - 最差耗时约 148 秒，比原方案 210 秒减少 30%

### 修改18: 修复汽车之家爬虫 SSL 错误
- `scripts/test_autohome.py` 的 `download_car_pages()` 函数中，字母列表页请求 `session.get()` 添加 SSL/Connection 错误重试
- 捕获 `requests.exceptions.SSLError` 和 `requests.exceptions.ConnectionError`
- 使用指数退避策略（2/4/8秒），最多重试 3 次
- 解决 mihomo 代理节点 SSL 握手失败导致爬虫崩溃的问题

### 修改17: 更新订阅抓取 User-Agent
- `scripts/generate_clash_config.py` 默认订阅抓取 UA 改为 `mihomo/1.19.13`
- 支持通过 `PROXY_SUBSCRIPTION_USER_AGENT` 环境变量覆盖默认 UA
- 避免旧客户端 UA 触发服务商安全拦截

### 修改16: 按上午/下午窗口拆分并发锁
- `crawl-autohome.yml` 和 `crawl-dongchedi.yml` 的 `concurrency.group` 改为包含 `github.event.schedule` 或 `run_profile`
- 上午和下午各自独立并发锁，上午不会再阻塞下午
- 上午窗口不再做随机启动延迟
- 上午动态 RUN_TIME 增加 15 分钟缓冲，避免拖过 12:30

### 修改15: 上午爬虫动态缩短
- 上午窗口结束时间从 12:00 改为 12:30
- 新增上午动态 RUN_TIME 计算，确保 12:30 前结束
- 下午保持固定 AFTERNOON_RUN_TIME = 21000 秒（5h50m）

### 修改14: 备用调度修复
- 上午单点定时改为 UTC `7,22,37,52 1-3 * * *`，即北京时间 09:07-11:52 多次备用触发
- 下午单点定时改为 UTC `7,17,27 5 * * *`，即北京时间 13:07/13:17/13:27 备用触发
- 增加顶层 `concurrency`，避免备用触发造成并发重复爬

### 修改13: 避免延迟 schedule 傍晚补跑
- 定时从 UTC 01:00/05:00 调整为 UTC 01:07/05:07，避开整点调度高峰
- 增加 schedule 时间窗守卫，不在允许时间窗口内直接跳过
- 懂车帝浏览器初始化增加最多 3 次重试

## 2026-05-28

### 修改12: 修复过滤逻辑和不完整爬虫数据误发布
- 修复 `纯电续航(km)` 过滤方向，改为 `>= 150`，不再和百公里加速共用 `<=` 判断。
- 增强配置字段识别，支持 `手机APP远程功能`、`钥匙类型`、`电动座椅记忆功能`、`外后视镜功能` 等汽车之家/懂车帝常见字段。
- 修复 GitHub Actions 中 `python ... | tee` 掩盖 Python 退出码的问题，避免未完成爬取被误判为完成。
- 修复懂车帝配置页超时时仍把车系记为已爬的问题，避免没有 HTML 却生成 0 行数据。
- 爬虫 artifact 和 Release 发布前增加行数校验，拒绝上传/发布明显不完整的数据。

### 修改11: 修复 Release CSV 过小
- `merged_日期.csv` 改为输出全部合并后的车型数据，不再误写过滤后的空结果。
- 新增 `merged_日期.json`，Release 同时上传完整合并数据和过滤结果。
- 发布前检查 `merged_日期.csv` 至少包含一行数据，避免继续发布只有表头的小文件。

### 修改10: 添加CI测试和PR自动合并工作流
- 新增 `.github/workflows/ci.yml`，在 push、pull_request 和手动触发时运行 Python 语法检查与 `scripts/merge_data.py` 冒烟测试。
- 新增 `.github/workflows/auto-merge.yml`，给非草稿 PR 添加 `automerge` 标签后启用 GitHub 原生自动合并。
- 自动合并使用 squash merge，并在合并后删除源分支。
- 修复 `scripts/merge_data.py` 过滤逻辑未识别归一化后的 `蓝牙/数字钥匙` 字段，避免符合条件车型被误过滤。

## 2026-02-23

### 修改4: 优化为更人性化的间隔运行
- 调度频率：每天2次（02:00、14:00，间隔12小时）
- 运行时间：2小时（7200秒）
- 车型数量：500个
- 更像人类操作：每次爬取后有充足间隔时间

### 修改6: 懂车帝与汽车之家并行爬取
- 懂车帝不再依赖汽车之家完成，独立并行运行
- 两家网站风控分开，同时爬取提高效率
- merge步骤等待两者都完成后执行

### 修改7: 懂车帝爬虫添加分步运行和循环逻辑
- 添加命令行参数支持：--step, --time-limit, --max-series, --auto
- 第二步支持时间限制和车系数量限制
- 自动模式：未完成返回exit code 10
- GitHub Actions循环运行，每次2小时爬500个车系
- 和汽车之家保持一致的节奏和逻辑

### 修改9: 修复懂车帝第二步缺少车系列表问题
- 如果没有车系列表，自动运行第一步获取
- 避免因进度文件不完整导致报错

### 修改8: 修复断点续传bug
- 修复：每个字母内没有断点续传的问题
- 添加：current_letter 和 current_car_idx 记录进度
- 添加：文件存在性检查，避免重复下载
- 懂车帝也添加文件存在性检查

### 修改5: 添加随机延迟更像人类
- 开始前随机延迟10-40分钟
- 每次commit前随机延迟30-90秒
- 每次重新运行前随机延迟1-3分钟
- 完全模拟人类不规律的操作时间

---

### 修改3: 添加分步运行和时间限制功能
- 为 scripts/test_autohome.py 添加命令行参数支持：
  - `--step N`: 运行指定步骤(1-6)
  - `--time-limit N`: 每步最大运行秒数
  - `--max-cars N`: 第一步最多下载车型数
  - `--auto`: 自动模式
- 为每个步骤添加 `check_time_limit()` 函数，到时自动保存进度
- 第一步额外添加 `check_car_limit()` 支持车型数量限制
- 修改 main() 函数支持单独运行某个步骤

### 修改2: GitHub Actions 自动化改进
- 将爬虫拆分为多个Job逐步执行
- 第一步支持循环运行：未完成则自动commit进度、push、然后重新运行
- 添加 `step1_done` 标记文件，完成后运行步骤2-6
- 支持 `force_restart` 参数强制重头开始
- 参数可配置：RUN_TIME(7200秒)、MAX_CARS(300个)

### 修改3: README文档更新
- 添加高级参数说明表格
- 添加步骤说明
- 添加GitHub Actions自动运行逻辑说明
- 添加手动触发说明

---

## 历史记录结束
## 2026-07-05 — 代理修复 + 目录整理

### 代理连通性修复
- `custom_scripts/setup_proxy_runtime.py`: mihomo 控制端口超时 15s→30s，失败时打印日志诊断
- `custom_scripts/generate_clash_config.py`: health-check URL 改为 `https://www.baidu.com`（原 `gstatic.com/generate_204` 被墙），interval 300→60s
- `custom_scripts/setup_proxy_runtime.py`: `test_local_proxy` 增加重试（3次/5秒间隔），`session.trust_env=False`，timeout 12→15
- `proxy_manager.py`: `get_clash_delay` 默认 URL 改为 `baidu.com`

### 仓库目录整理
- 19个 .py/.sh/.json 文件从根目录移入 `scripts/` 和 `config/`
- 所有引用路径已更新（Dockerfile、workflows、deploy_vps.sh 等）
- 根目录文件数：33→14

### 上游同步工作流
- 新增健壮的 `sync-upstream.yml`：temp-dir 方案保留本地 workflow 文件
- 解决 GITHUB_TOKEN 无 workflows 写权限导致的 push 被拒问题

# 对话历史总结

> 最后更新：2026-06-15 18:35
> 
> 本文档记录了汽车数据爬虫项目从创建到最新的所有对话历史，融合了所有历史文件的内容。

---

## 2026-06-15：筛选历史迁移到 Personal_commonly_used 并修复双源核验

### 用户诉求
- 不要新建独立仓库保存筛选历史，改为放在 `Personal_commonly_used` 仓库的某个文件夹内。
- 陌生人访问网站时，即使不填写 Gist 或 GitHub Token，也要能匿名使用；填写了远端同步信息的用户数据不能被匿名状态影响。
- 解释并修复网页“双源核验”显示 0 的问题。

### 排查
- `Fatty911/Personal_commonly_used` 是私有仓库，默认分支 `main`。
- 目标历史文件 `cars/filter-history/history.json` 原本不存在，已通过 GitHub Contents API 初始化。
- 20260615 Release 的 `merged_20260615.json` 实际包含两源数据：懂车帝 7507 行、汽车之家 1123 行。
- 双源核验显示 0 的原因是前端原本用 `品牌 + 车系 + 车型名称 + 年款` 做合并键；汽车之家行里 `品牌`/`车系` 多数为空、`年款` 也常为空，而懂车帝把车型拆在 `车系`、`年款`、`车型名称` 三列，导致同一车型无法对上。

### 修改
- `docs/config.js` 将默认 GitHub 历史后端改为：
  - owner: `Fatty911`
  - repo: `Personal_commonly_used`
  - path: `cars/filter-history/history.json`
  - branch: `main`
- `docs/app.js` 保持未填写 Token 时的匿名本机缓存模式；匿名访客不会读取、写入或覆盖远端历史。
- `docs/app.js` 新增车型名归一化：把懂车帝的 `车系 + 年款 + 车型名称` 与汽车之家的完整 `车型名称` 合成同一类 key，再去掉空白、`改款` 和常见标点后匹配双源。
- README、CHANGELOG 同步记录新后端路径、匿名使用逻辑和双源核验口径。
- 尝试删除上一轮新建的 `Fatty911/cars-filter-history` 仓库，但当前 `gh` token 缺少 `delete_repo` scope；随后通过 GitHub API 将该仓库设为 `archived=true`，并确保网站配置不再引用它。

### 结果
- 筛选历史不再依赖新建的 `cars-filter-history` 仓库，改为存储在 `Personal_commonly_used/cars/filter-history/history.json`。
- 匿名访问网站不需要填写任何 Token，筛选历史只存在当前设备本机；填写 GitHub Token 的用户使用私有仓库远端历史，两者互不覆盖。
- 按 20260615 数据离线试算，修复后的精确双源核验可识别约 290 个车型配置组，不再显示为 0。

---

## 2026-06-15：筛选历史改用 GitHub 私有仓库可选同步

### 用户诉求
- Cloudflare Worker 服务端历史暂不可用时，确认能否改用私有仓库或 Gist 同步，并直接调用 `gh` 完成可用路径。

### 修改
- 使用 `gh auth status` 确认当前 GitHub CLI 登录账号 `Fatty911` 具备 `gist`、`repo`、`workflow` 权限。
- 未选择 Gist 作为默认后端，因为 Gist 的 secret 只是未列出链接，不是真正私有；改用 `gh repo create Fatty911/cars-filter-history --private --add-readme` 创建 GitHub 私有仓库。
- 通过 GitHub Contents API 初始化私有仓库 `history.json`，结构为 `version`、`updatedAt`、`profiles`。
- `docs/config.js` 默认将历史后端切到 GitHub 私有仓库，同时保留 `/api/filter-history` 作为 Cloudflare Worker 备用路径。
- `docs/app.js` 新增 GitHub Contents API 读写：按同步码保存到 `profiles[syncId]`，保存时带 SHA，遇到一次 409 冲突会重新读取后重试。
- 网页筛选历史区新增 GitHub Token 输入、保存和清除按钮；Token 只保存在当前浏览器本机 `localStorage`，不会写入公开仓库。
- README、CHANGELOG 同步记录私有仓库后端、Token 权限边界和 Worker 备用路径。

### 结果
- 筛选历史现在具备 GitHub 私有仓库同步能力；跨电脑或手机时，只要使用同一同步码并在该设备本机保存具备私有历史仓库 Contents 读写权限的 GitHub Token，就能读取和保存同一份筛选历史。
- 公开 Pages 配置只暴露私有仓库名称和默认同步码，不包含可写密钥。

---

## 2026-06-15：网页筛选条件配置化与筛选历史后端

### 用户诉求
- 网页筛选条件不要写死在代码里，要像汽车之家、懂车帝一样在页面条件栏勾选功能或设置属性数值范围。
- 关闭浏览器、换电脑或手机后，能通过服务端记住筛选历史，并点击历史恢复当次筛选车型。
- 修复筛选框输入一个字符后光标消失的问题，兼容中文输入法；筛选框既能输入也能鼠标点击筛选。
- 数据来源筛选只有懂车帝时没有意义；希望网页数据表现为汽车之家和懂车帝综合交叉验证。
- ABS 防抱死这类若为标配或近似全量存在，就不要作为显著筛选项。

### 修改
- 新增 `config/filter_conditions.json`，将默认筛选条件从 `scripts/merge_data.py` 和前端代码中抽出，支持功能条件和数值范围条件。
- `scripts/merge_data.py` 改为读取 `config/filter_conditions.json` 计算默认 `filtered_cars_*` 输出。
- 重构 `docs/app.js`：加载全量合并数据后，在前端按品牌、车系、条件栏、字段筛选、表头筛选实时计算结果。
- 网页移除“数据来源”筛选，改为按品牌/车系筛选，并把同一品牌、车系、车型、年款的多来源记录合并为一行，展示 `交叉核验` 与 `核验来源`。
- 表头筛选和全局搜索输入时不再整页重绘输入框，中文输入法组合输入期间保持焦点，避免输入一个字符后光标丢失。
- 新增筛选历史区域：生成同步码、保存当前筛选、加载服务端历史、点击历史恢复筛选状态。
- 新增 `cloudflare/filter-history-worker.js` 和 `wrangler.toml`，作为 Cloudflare Worker + KV 的筛选历史后端。
- `docs/config.js` 默认将历史 API 指向 `/api/filter-history`，便于后续把 `cars.jiucai.eu.org/api/*` 路由到 Worker。
- `docs/config/filter_conditions.json` 随静态页面发布；`deploy-pages.yml` 发布时也会复制根目录 `config/filter_conditions.json`，避免配置不同步。
- `config/filter_conditions.json` 将 ABS/制动防抱死类字段列入默认隐藏和全量阳性时自动降噪字段。
- `.gitignore` 新增 `merged_*.json`，避免合并冒烟测试产物误入仓库。

### 结果
- 网页从“固定条件结果表”升级为可交互车型库筛选页。
- 筛选条件后续改 JSON 即可，不必改 Python/JavaScript 逻辑。
- 当前环境 Cloudflare API 可创建 KV，但没有上传 Worker 脚本权限；本地 `wrangler deploy` 也缺少 `CLOUDFLARE_API_TOKEN`，因此后端代码已就绪但尚未成功部署到 Cloudflare。

---

## 2026-06-15：修复半月完成后 Release 和 Pages 不更新

### 排查
- 最近 Release 仍停在 `v20260528`，说明 6 月上半月数据没有发布。
- 6 月 14 日两次 `合并分析` 都显示成功，但日志中实际写明：`下载汽车之家 artifact 失败`、`下载懂车帝 artifact 失败`，随后 `汽车之家 未找到 autoHome_*.json 数据文件`、`懂车帝 未找到 dongchedi_*.json 数据文件`，所以合并发布被保护逻辑成功跳过。
- 根因是合并工作流只取最近一次成功爬虫 run；半月完成后后续自动触发的爬虫 run 会快速成功跳过且不上传数据 artifact，于是“最近成功 run”反而没有可发布数据。
- artifact 列表显示懂车帝有 2026-06-14 的有效 `dongchedi-data-20260614`，汽车之家最近有效 artifact 是 2026-06-04 的 `autohome-data-20260604`，但后续跳过 run 把它们挡住了。

### 修改
- 新增 `custom_scripts/download_latest_crawler_artifact.py`，按 workflow 向前扫描成功 run 的 artifacts，跳过缺失、过期、过小、非当前半月和 JSON 行数少于 50 的 artifact。
- `merge-and-filter.yml` 改用该脚本下载汽车之家和懂车帝当前半月有效数据，再执行零整比抓取、合并、Release 和 Pages 发布。
- 手动触发新合并 run `27516553176` 后，数据下载和完整性校验已经通过：汽车之家 `autoHome_20260604.json` 1123 行，懂车帝 `dongchedi_20260614.json` 7507 行；随后失败在零整比脚本缺少 `requests`。
- `merge-and-filter.yml` 增加合并依赖安装：`requests`、`beautifulsoup4`、`lxml`、`pdfplumber`、`pypdf`。
- 第二次手动合并 run `27516642745` 已成功生成 `merged_20260615.*` 和 `filtered_cars_20260615.*`，但 `merge-data` 只有 10 分钟超时，检查结果阶段被取消；因此把 `merge-data` / `create-release` 放宽到 60 分钟，并把 `deploy-pages.yml` 放宽到 30 分钟。
- `custom_scripts/validate_workflow_expectations.py` 增加合并工作流静态校验，避免后续退回只取最新成功 run。
- README、CHANGELOG 同步记录。

### 结果
- 半月完成后的短跳过 run 不再阻挡合并发布。
- 合并工作流会优先使用当前半月内最近的真实数据 artifact；如果没有完整数据，仍会成功跳过或在手动强制合并时失败，避免发布空数据。

---

## 2026-06-11：修复懂车帝 step2 HTML 缓存未跨 runner 保存

### 排查
- 远端 `origin/main:dongchedi/progress.json` 只有 `series_list`，`crawled_series` 为 0；说明车系列表被提交保存了，但 step2 完成车系没有留下可复用进度。
- 最新懂车帝 Actions 日志出现 `发现 1327 条 step2 进度缺少对应 HTML，已重置为未爬取`，随后打印 `车系总数: 4681，已有HTML: 0，需爬取: 4681`。
- 根因是 `dongchedi/json/` 被 `.gitignore` 排除，GitHub Actions 新 runner checkout 后没有 step2 HTML 页面缓存；`crawl_dongchedi.py` 的一致性检查会把没有对应 HTML 的 `crawled_series` 移除，避免生成空数据。

### 修改
- `crawl-dongchedi.yml` 在 step1 前新增 `actions/cache` 恢复 `dongchedi/json/`，按当前半月周期保存和恢复 HTML 页面缓存。
- `Prepare crawl period` 输出 `crawl_period` 供 cache key 使用，避免依赖运行时写入的 `$GITHUB_ENV` 做表达式展开。
- 强制重跑或进入新半月周期仍会清理旧 HTML，普通分段续爬才恢复同半月周期缓存。
- 新增 `Report Dongchedi HTML cache` 步骤，在日志中打印恢复到的 HTML 文件数。
- README、CHANGELOG 同步解释 `crawled_series` 与 HTML 页面缓存的关系。

### 结果
- 后续懂车帝普通分段续爬不应再因为 runner 换机而总显示 `已有HTML: 0`。
- 如果日志继续显示 `已有HTML: 0`，可以直接看新增的 `Dongchedi HTML cache files` 日志判断是 cache 未命中、cache 过期，还是上一轮没有成功保存缓存。

---

## 2026-06-11：增强爬虫 workflow 进度同步、artifact 上传和网络异常恢复

### 排查
- 最近 40 条 GitHub Actions 中，当前源码后的 CI、Pages、合并分析、外部触发器和汽车之家均成功。
- 唯一失败的懂车帝 run `27246666876` 位于旧提交 `3759cd0`：step2 正常达到时间限制并返回 `exit code 10`，但进度同步阶段连续 rebase/push 失败；随后 error-log artifact 上传经代理访问 GitHub API 又出现 `ECONNRESET`。
- 该失败日志还显示大量连续 `net::ERR_CONNECTION_CLOSED`，说明浏览器或代理链路进入坏状态后会持续浪费爬取窗口。

### 修改
- `custom_scripts/git_sync_progress.sh`：
  - 直连重试时显式清除 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 及小写变量，确保真正不走 mihomo。
  - rebase 失败后除进度 JSON 冲突合并外，增加空提交/空 rebase 自动 `rebase --skip` 恢复。
- `crawl-autohome.yml`、`crawl-dongchedi.yml`：
  - 上传 error-log 或数据 artifact 前清空代理环境，避免 GitHub artifact API 请求被本地代理断流影响。
- `crawl_dongchedi.py`：
  - 新增 `DCD_NETWORK_ERROR_RESTART_THRESHOLD`，连续 `net::ERR_CONNECTION_*` 导航异常默认 5 次后重启 Chrome。
- README、CHANGELOG 同步记录。

### 结果
- 后续分段退出的进度提交更能抵抗远端进度提交竞态、空 rebase 和代理异常。
- artifact 上传不再继承爬虫代理环境。
- 懂车帝遇到连续连接关闭时会主动恢复浏览器状态，而不是在同一坏链路上继续消耗时间。

---

## 2026-06-11：配置 cron-job.org 并增强进度同步诊断

### 排查
- 最近汽车爬虫外部触发器已经能通过 `repository_dispatch` 拉起主爬虫。
- 旧的懂车帝失败不是爬虫逻辑失败，而是长跑正常 `exit code 10` 后，`git_sync_progress.sh` 在同步进度时多次 `pull --rebase` 失败且隐藏了真实原因。

### 修改
- 使用 cron-job.org API 配置 `Fatty911/crawl_cars` 的 08:30、13:30 两个外部触发任务。
- `custom_scripts/configure_cron_job_org.py` 增加短暂 API/network 失败重试。
- `custom_scripts/git_sync_progress.sh` 改为显式 `fetch → rebase → push`，失败时打印脱敏后的 Git 错误，后续进度同步失败能直接看到根因。

## 2026-06-10：改为 cron-job.org 外部触发并统一长窗口预算

### 用户诉求
- 手机配置和汽车配置爬虫都只在北京时间 `08:00-12:30`、`13:00-22:00` 窗口内长跑。
- 无论从什么入口启动，都要自动判断先撞上 GitHub Actions 6 小时限制还是当前时间窗口限制，并提前几分钟结束。
- 不再相信 GitHub Actions cron schedule；手机爬虫也要像汽车爬虫一样通过 cron-job.org API 配置触发；cron-job.org 触发时间改为北京时间约 08:30 和 13:30。

### 修改
- 主爬虫 `crawl-autohome.yml`、`crawl-dongchedi.yml` 不再依赖 GitHub Actions `schedule` 准点触发。
- `crawl-trigger.yml` 改为外部触发入口，接受 `trigger-crawl` 后默认同时拉起汽车之家和懂车帝。
- 新增 `custom_scripts/crawl_budget.py`，长步骤启动前按当前窗口剩余时间与 GitHub Actions 6 小时剩余时间取更早截止点，并保留进度提交缓冲。
- 新增 `custom_scripts/configure_cron_job_org.py`，用于创建或更新 cron-job.org 的 08:30、13:30 两个 `repository_dispatch` 任务。
- README、CHANGELOG、CI 预期校验同步更新，避免后续误回退到只靠 GitHub cron schedule。

## 2026-06-08：增加零整比属性、来源明细和 Pages 展示

### 用户诉求
- 希望 Pages 页面增加“零整比”属性。
- 想从中保研、中保协、中汽修协等公开来源爬取零整比；多个来源给同一车型不同数值时取平均值，同时列出不同来源分别多少。

### 排查
- 公开可抓来源主要是中国保险行业协会/中国汽车维修行业协会联合发布的汽车零整比体系 PDF，以及中保研在中保协指导下发布的汽车零整比研究成果。
- 部分媒体稿只给摘要，完整可落地的数据通常要从 PDF/HTML 表格抽取；因此更适合独立成零整比来源脚本，再由合并层统一给车型补字段。

### 修改
- 新增 `scripts/crawl_zero_to_whole_ratio.py`：
  - 支持默认公开 PDF 来源、`zero_to_whole_sources.json`、`ZERO_TO_WHOLE_RATIO_URLS` 和本地 `zero_to_whole_manual.csv/json`。
  - 使用 `pdfplumber` 优先抽取 PDF 表格，失败时回退文本/HTML 解析。
  - 输出 `zero_to_whole_ratios_YYYYMMDD.json` 和 `zero_to_whole_ratios.json`。
- `scripts/merge_data.py`：
  - 新增 `零整比`、`零整比来源明细`、`零整比匹配方式`。
  - 按车型名称、车系和包含关系匹配零整比来源，同一车型多来源取算术平均。
- `docs/app.js`：
  - 把 `零整比` 和 `零整比来源明细` 加入常用列。
  - 下载区展示零整比来源 JSON。
- `merge-and-filter.yml`：
  - 合并前先运行零整比抓取。
  - Release、artifact、Pages 产物新增 `zero_to_whole_ratios_YYYYMMDD.json`。
- CI 冒烟测试补充两来源平均值断言。
- README、DOCKER_DEPLOY、CHANGELOG 同步记录。

### 验证
- 本地运行 `python scripts/crawl_zero_to_whole_ratio.py`，从两个公开 PDF 抽取 291 条零整比来源记录。
- 小型端到端合并测试确认两来源 `320.50%` 与 `340.50%` 会写成平均 `330.50%`，并保留来源明细。

---

## 2026-06-08：解释懂车帝 renderer timeout 并优化连续超时处理

### 用户反馈
- 懂车帝日志里出现 `Timed out receiving message from renderer` / `爬取异常` 堆栈，但后面还能继续爬。
- 用户感觉懂车帝还没爬完，汽车之家总用时比懂车帝少不少。

### 排查
- 最新懂车帝长跑 `27117329232` 从北京时间 2026-06-08 13:10 跑到 18:41，workflow 结论 success。
- 日志显示代理已启用：解析到 52 个节点，`PROXY_ENABLED=true`，step1/step2 使用 mihomo。
- step2 因 workflow 已耗时扣减，从 `RUN_TIME=21000` 缩短到 `17635` 秒，并在最后以 `Exit code: 10` 正常提交 `Update dongchedi progress - 10:41`。
- `Timed out receiving message from renderer` 是 Selenium/Chrome 单页加载超时，代码会记录到 `dongchedi/exception/exception.txt`，不把该车系加入 `crawled_series`，然后继续下一个车系。
- 远端 `origin/main:dongchedi/progress.json` 显示 `series_list=4692`、`crawled_series=131`，且 `crawl_state/` 只有汽车之家 done 标记，没有 `dongchedi_202606_H1.done`，所以懂车帝确实还没全量完成。
- 汽车之家最新短 run 只是因为 `autohome_202606_H1.done` 已存在，7 秒内成功跳过，不能直接和懂车帝长跑耗时比较。

### 修改
- `crawl_dongchedi.py` 新增 `DCD_RENDERER_TIMEOUT_RESTART_THRESHOLD`，默认值 3。
- step2 遇到连续 renderer timeout 时会关闭旧 Chrome、重新创建浏览器后继续，避免一个坏掉的 renderer 让后续车系连续快速 timeout。
- `crawl_series_config()` 返回当前活动 browser，外层 finally 会关闭重启后的新 browser，避免残留进程。
- 推送后 CI 成功，但 GitHub 对 `actions/checkout@v4`、`actions/setup-python@v5`、`actions/setup-node@v4` 给出 Node.js 20 deprecation annotation；通过 GitHub API 确认最新 tag 后，将三者升级为 `v6.0.3`、`v6.2.0`、`v6.4.0`。
- README、CHANGELOG、HISTORY 同步记录。

### 结果
- 单个车系 renderer timeout 仍不会中断整个 workflow；连续 timeout 会主动重启 Chrome，提高懂车帝 step2 后续续爬效率。
- 现有半月完成标记逻辑保持不变：懂车帝完整成功后才写 `dongchedi_202606_H1.done`，之后本半月自动跳过。

---

## 2026-06-08：消除 AI Auto Fix Monitor 缺少 error-log artifact 的误报注解

### 用户反馈
- `AI Auto Fix Monitor #281` 虽然 job 成功，但 Annotations 中出现 `Unable to download artifact(s): Artifact not found for name: error-log`。

### 根因
- `actions/download-artifact` 即使设置了 `continue-on-error: true`，找不到 artifact 时也会在 GitHub UI 里留下红色 annotation。
- 成功的爬虫 workflow 通常不会上传 `error-log`，所以这是可选 artifact 下载方式导致的噪音，不是爬虫或 Codex 修复逻辑失败。

### 修改
- `AI_Auto_Fix_Monitor.yml` 删除 `actions/download-artifact` 步骤。
- 改用 `gh run download --name error-log` 在 shell 中静默尝试下载；找不到时只输出普通日志并继续。
- README 同步说明成功 run 缺少 `error-log` 属于正常情况，不再产生红色 annotation。

### 结果
- 后续成功爬虫触发的监控工作流不会再因为没有 `error-log` artifact 挂红色注解。
- 真正失败时仍会优先使用完整 workflow log，并在存在 `error-log` artifact 时合并分类。

---

## 2026-06-08：上午窗口前移到 8 点并集成 Codex 自修复

### 用户诉求
- 上午爬虫时间范围从 9 点开始改为 8 点开始。
- 按前面方案把 Codex 集成进 GitHub workflow，让爬虫工作流报错或不符合预期时能自助修复。

### 修改
- `crawl-autohome.yml`、`crawl-dongchedi.yml`：
  - 上午备用 cron 从 `7,22,37,52 1-3 * * *` 改为 `7,22,37,52 0-3 * * *`，对应北京时间 `08:07-11:52`。
  - schedule 守卫、`run_profile=auto` 识别和显式 morning 窗口统一改为北京时间 `08:00-12:30`。
  - 下午 `13:00-13:30` 启动窗口、`AFTERNOON_RUN_TIME=21000`、6 小时提交缓冲和半月完成标记逻辑保持不变。
- `crawl-trigger.yml`：
  - 外部随机触发与手动触发的上午窗口改为北京时间 `08:00-12:30`。
- `AI_Auto_Fix_Monitor.yml`：
  - 从单纯失败触发，改为监听主爬虫 completed 结果；失败时分类，成功时也检查是否出现窗口外长爬虫运行。
  - 需要修复时优先调用官方 `openai/codex-action@v1`，通过仓库 Secret `OPENAI_API_KEY` 授权。
  - Codex 修改后必须通过文件白名单、语法校验和 workflow 预期校验，才自动 commit + push 到 `main`。
  - 未配置 `OPENAI_API_KEY` 或 Codex 执行失败时，回退旧版 `scripts/auto_fix_workflow.py` 多 Provider 修复器。
  - 不再 rerun 原失败 run，避免旧 commit 重跑导致修复循环。
- 新增 `custom_scripts/check_workflow_expectations.py`、`custom_scripts/ensure_codex_autofix_scope.py`、`custom_scripts/validate_workflow_expectations.py`。
- `custom_scripts/validate_syntax.py` 在 Windows 控制台下强制使用 UTF-8/替换错误输出，并修复显式传入相对路径文件时的仓库根目录解析，避免校验脚本自身失败。
- `ci.yml` 增加 workflow 预期静态校验，确保上午 8 点窗口和 Codex 护栏后续不会被误改。
- README、DOCKER_DEPLOY、CHANGELOG 同步更新。

### 结果
- 两个主爬虫的上午可启动窗口前移到北京时间 8 点，上午备用 schedule 每天 08:07 起尝试。
- Codex 自修复被接到 Actions：有代码修复价值时自动修，临时网络/代理订阅/正常跳过类情况不改仓库。

---

## 2026-06-08：复查最新 workflow 并阻止窗口外手动默认触发

### 用户诉求
- 再看最新工作流运行情况。
- 判断是否符合预期；有问题直接修复。

### 排查
- 本地同步到远端最新 `cc7bf56 Update dongchedi progress - 16:02`，说明昨晚懂车帝分段运行成功提交了进度。
- 最新 40 个 workflow run 中，当前源码之后没有失败 run；`合并分析` 成功跳过未就绪数据，`AI Auto Fix Monitor` 对进度提交触发为 skipped。
- 重点检查最新懂车帝成功 run `27089991071`：
  - 事件类型是 `workflow_dispatch`，北京时间 2026-06-07 18:31 启动。
  - `trigger_time` 为空，说明不是 `crawl-trigger.yml` 正常传参触发。
  - 默认 `run_profile=auto` 在窗口外落到 `afternoon`，随后运行 step1/step2。
  - step2 启动前按 workflow 已耗时把 `RUN_TIME` 从 21000 缩短到 18821 秒，最终主动 `exit code 10`，提交 `cc7bf56` 并同步成功；进度保护本身有效。
- 源码问题是两个主爬虫只对 `schedule` 做了窗口守卫，`workflow_dispatch` 默认触发可绕过窗口；同时 `Configure crawl window` 里写 `skip=true` 但该 step 没有 `id`，后续步骤不会读取这个 skip 输出。

### 修改
- `crawl-autohome.yml`、`crawl-dongchedi.yml`：
  - 给 `Configure crawl window` 增加 `id: window`。
  - 修正 `run_profile=auto` 的选择顺序，13:00-13:30 会正确归为 `afternoon`，窗口外不会再默认落到 `afternoon`。
  - 统一计算当前北京时间，`morning` 只允许 09:00-12:30，`afternoon` 只允许 13:00-13:30。
  - 窗口外写入 `steps.window.outputs.skip=true` 并成功结束。
  - 后续安装依赖、代理、爬虫长步骤、自动修复、校验和 artifact 步骤都同时检查 `steps.period.outputs.skip` 与 `steps.window.outputs.skip`。
- `README.md`、`CHANGELOG.md` 同步记录：手动默认触发和随机触发一样受时间窗约束，不会在傍晚补跑。

### 结果
- 昨晚 18:31 这类直接 `workflow_dispatch` 默认触发后续会成功跳过，不再启动长爬虫。
- schedule、随机触发、手动默认触发均收敛到上午 09:00-12:30 或下午 13:00-13:30 的启动窗口。
- 当前进度提交与 6 小时前缓冲逻辑仍保持有效。

---

## 2026-06-07：复查最新 workflow 运行并修正上午截止时间

### 用户诉求
- 查看最新工作流运行情况和最新源码。
- 判断 workflow 是否符合预期；如果有问题直接修复。

### 排查
- 最新 `CI` run `27086740294` 已成功，`main` 与 `origin/main` 同步。
- 最近 30 个 workflow run 中，最新爬虫失败/取消发生在旧提交：
  - 懂车帝 workflow_dispatch run `27083453452` 位于 `b60a51c`，失败点是旧版 `git_sync_progress.sh` 遇到 `dongchedi/progress.json` rebase 冲突后仍“使用远程版本解决”，6 次重试失败。
  - 懂车帝 schedule run `27083369318` 位于 `a9c6aad`，被后续运行/修复链路取消，不代表当前源码失败。
- 当前源码已经包含 `custom_scripts/merge_progress_json.py` 和新版 `git_sync_progress.sh`，进度冲突会合并 JSON 进度，不再使用远程版本覆盖本地进度。
- 继续检查源码发现新问题：两个主爬虫的上午动态缩短误算到北京时间 14:30，而历史规则和用户预期是上午窗口应在 12:30 前收口。
- 汽车之家下午长跑还缺少 workflow 总耗时扣减；如果 checkout、依赖安装和代理初始化耗时较长，step1 跑满 21000 秒后仍可能贴近 GitHub 6 小时边界。

### 修改
- `crawl-autohome.yml`、`crawl-dongchedi.yml`：
  - 上午动态 `RUN_TIME` 截止从 UTC 06:30（北京时间 14:30）修正为 UTC 04:30（北京时间 12:30）。
  - 继续扣除 15 分钟缓冲，上午 late start 会尽量在 12:15 前结束。
- `crawl-autohome.yml`：
  - 新增 `WORKFLOW_START_EPOCH`、`MAX_WORKFLOW_SECONDS=21600`、`PROGRESS_COMMIT_BUFFER_SECONDS=1800`。
  - 在 step1 前按 workflow 已耗时缩短 `RUN_TIME`，剩余安全时间不足时跳过长步骤，避免 GitHub 硬超时导致进度无法提交。
- `README.md`、`CHANGELOG.md` 同步记录本次修正。

### 结果
- 上午备用触发不会再把爬虫带到下午两点多。
- 汽车之家和懂车帝都具备长步骤启动前的总时长预算保护。
- 旧失败 run 已由当前源码覆盖，不需要按旧日志再次修复爬虫业务逻辑。

---

## 2026-06-07：检查未推送提交并对齐 OpenCode 配置

### 用户诉求
- 查看所有未推送提交，判断哪些正确、哪些有误。
- 有误的改正确，没问题后全部推送。

### 排查
- `main` 与 `origin/main` 没有未推送提交，当前待处理内容是 5 个未提交文件改动：`AGENTS.md`、根目录与 `ai_tools/opencode/` 下的 OpenCode/oh-my-openagent 配置。
- 这些配置改动的大方向正确：同步新的多 Provider/多模型配置，并新增仓库配置必须对齐全局配置的长期规则。
- 发现两类需要修正的问题：
  - `config/opencode.json` 仍带有 AGENTS 明确说明不支持的 `disabled_providers` 字段。
  - 配置里仍包含 Copilot Haiku 模型，违反“隐藏旧模型/弱模型”的规则。

### 修改
- 将仓库根目录与 `ai_tools/opencode/` 下的 `config/opencode.json`、`config/oh-my-openagent.json` 同步为全局 OpenCode 最新配置。
- 同步清理全局和仓库配置中的 `disabled_providers` 字段与 Haiku 模型条目，避免之后再次复制全局配置时把错误带回仓库。
- 保留 `config/opencode.json` 的合法单数字段 `provider`、`agent`；`config/oh-my-openagent.json` 的 `agents` 属于插件自身配置结构。
- `AGENTS.md` 保留并提交“配置对齐（关键）”规则。
- `CHANGELOG.md` 与本文件同步记录本次配置修正。

### 结果
- 仓库两处 OpenCode 配置与全局配置哈希一致。
- `config/opencode.json` 不再包含 `disabled_providers`、Haiku 或非法复数字段。
- 后续在本仓库开启 OpenCode 时，配置与全局源保持一致，并避开已知 schema/模型显示问题。

---

## 2026-06-07：检查 GitHub Actions 运行并修复调度与进度同步

### 用户诉求
- 用 GitHub CLI 查看 workflow 运行情况和最新源码。
- 判断当前 workflow 运行是否符合预期；如果有问题就直接修复。

### 排查
- 远端 main 已前进到 `af13b0a Dongchedi step1 - series list - 05:27`，包含 OpenCode/其它模型后续推送的调度和同步脚本变更。
- 最新运行中：
  - 懂车帝 schedule run `27083369318` 仍在 step2 运行。
  - 懂车帝 workflow_dispatch run `27083453452` 失败在 `Run step2 loop`。
  - 汽车之家 workflow_dispatch run `27078846416` 失败在旧提交 `c1e19c9` 上，后续汽车之家同类 schedule/manual 已成功，优先不按旧源码误修。
- 懂车帝失败 run 的日志显示，step2 已正常达到 `time-limit 3877`，保存进度并返回 `Exit code: 10`，但 `git_sync_progress.sh` 在同步 `dongchedi/progress.json` 时和远端进度提交发生 rebase 冲突。
- 现有 `git_sync_progress.sh` 冲突处理使用“远程版本解决”，导致本地刚保存的 `crawled_series` 进度被丢弃，6 次重试都重复冲突，最终 workflow failure。
- 最新源码还存在两处与用户预期不符：
  - 两个主爬虫 schedule 被改为每 3 小时一次，下午直接 schedule 会在北京时间 14:27 才触发，不符合 13:00-13:30 启动要求。
  - 半月完成标记存在时被改成进入增量模式继续跑新增车系，不符合“每半个月完整成功后就不再爬”的限制。

### 修改
- `crawl-autohome.yml`、`crawl-dongchedi.yml`：
  - 恢复上午 `7,22,37,52 1-3 * * *` 和下午 `7,17,27 5 * * *` 两组备用 schedule。
  - schedule 守卫恢复为上午 09:00-12:30、下午 13:00-13:30；延迟到其它时间直接跳过。
  - 并发组恢复按 `schedule` / `run_profile` 区分，避免上午窗口阻塞下午窗口。
  - 汽车之家 step1 和修复后重试改用运行时 `$RUN_TIME` / `$MAX_CARS`，确保上午动态缩短生效。
  - 发现半月 done 标记后直接跳过，本半月不再继续爬。
- `crawl-trigger.yml`：
  - `repository_dispatch` 外部触发也执行时间窗检查，不再任意时间触发目标爬虫。
- `custom_scripts/merge_progress_json.py`：
  - 新增进度 JSON 合并工具，支持合并 `series_list`、`crawled_series` 等列表。
- `custom_scripts/git_sync_progress.sh`：
  - rebase 冲突发生在 `progress.json` 或 `dongchedi/progress.json` 时，调用合并工具保留两边进度后继续 rebase/push。
- `README.md`、`CHANGELOG.md` 同步记录本次变更。

### 结果
- 后续懂车帝 step2 达到时间限制后，进度同步冲突会合并本地与远端进度，不会再因为选择远程版本而丢进度。
- 主爬虫恢复到上午多备用触发、下午 13:07/13:17/13:27 备用触发；傍晚或 14 点多延迟 schedule 不会实际爬取。
- 半月完成后恢复自动跳过，保留“半个月完整成功后不再爬”的限制。

---

## 2026-06-04：解释并收紧爬虫失败分类与 AI 自动修复触发

### 用户诉求
- 解释 `Classify step1 failure` 和 `Auto-fix step1 error` 两步中的报错。
- 如果有修复必要就修复；如果没有修复必要，需要说明为什么还要保留这两步。
- 继续检查懂车帝爬虫，确认 6 小时取消时是否没有保存 step2 进度，并修复导致进度无法提交的问题。

### 排查
- Racknerd 机器 `/root/crawl_cars` 的 OpenCode 最新会话显示，汽车之家运行中出现过：
  - `classification=site_breakage`
  - `should_fix=true`
  - AI Provider 调用失败，包括 Zen SSL 证书错误、OpenRouter 403/SSL EOF、XAI 403、Minimax 401。
- 爬虫后续仍正常获取车型配置，说明这类报错主要来自失败分类/自动修复的防御性步骤，而不是车型抓取整体不可用。
- 现有分类规则把“低行数保护”和“少量车型无法解析config或option”归进 `site_breakage`，过于宽泛，容易误触发 AI 修复。
- 完整 workflow 日志如果包含 AI Provider 自身失败，也可能被监控工作流再次分类为需要修复，产生噪音。
- 懂车帝 workflow_dispatch run `26933831918` 从 2026-06-04 13:58:20 北京时间启动，step2 从 14:15:57 开始，传入 `--time-limit 21000`。
- 该 run 在 2026-06-04 19:58:36 北京时间被 GitHub 直接取消，最后日志停在保存单个车型页面后等待，没有出现 `Exit code: 10`，也没有执行 `Update dongchedi progress` 提交。
- 远端只出现 `a93171a Dongchedi step1 - series list - 06:15`，说明 step1 列表已保存，step2 本地 HTML/进度没有在超时前推送。
- 根因是下午 step2 的 21000 秒预算没有扣除 checkout、环境初始化、step1 的耗时，导致 GitHub 6 小时硬限制先于爬虫自身 time-limit 触发。

### 修改
- `custom_scripts/classify_crawl_failure.py`：
  - 新增 `data_quality_guard` 分类：低行数、疑似未完整爬取、拒绝上传/合并、少量车型 `无法解析config或option` 时跳过 AI 修复。
  - 新增 `auto_fix_provider_failure` 分类：自动修复 Provider 的 SSL 证书、401/403、`/chat/completions` 网络/权限异常时跳过再次自动修复。
  - 保留 `site_breakage`：未生成数据、完全解析不到车型、配置页/接口致命异常仍允许自动修复。
- `AI_Auto_Fix_Monitor.yml`：
  - `scripts/auto_fix_workflow.py` 没有产出可用修复时，记录为跳过并让监控工作流正常结束，不再把 Provider 失败变成新的红叉。
  - 补充各 Provider 的可选 `BASE_URL`、`MODEL_LIST`、`PROXY_URL` 环境变量透传。
- `scripts/auto_fix_workflow.py`：
  - 移除 OpenRouter/XAI/Zen/MiniMax 等明显过时或无权限的默认模型，避免反复调用不存在模型。
  - AtomGit 和 NVIDIA NIM 使用仓库规则中已知可用的默认模型。
  - 支持 `XXXX_BASE_URL` 覆盖、`XXXX_MODEL_LIST` 显式模型、`XXXX_PROXY_URL` Provider 代理。
  - 默认关闭 OpenRouter 动态排行榜模型抓取，并修复排行榜映射中 `glm` KeyError。
- `crawl-dongchedi.yml`：
  - 在 `Prepare crawl period` 记录 `WORKFLOW_START_EPOCH`。
  - 在 step2 前新增安全时长计算：`MAX_WORKFLOW_SECONDS=21600` 扣除已耗时和 `PROGRESS_COMMIT_BUFFER_SECONDS=1800` 后，再缩短 `RUN_TIME`。
  - step1、step2、修复后重试改用运行时 `$RUN_TIME` / `$MAX_CARS`，确保前置步骤写入的动态环境变量生效。
- `crawl_dongchedi.py`：
  - 新增 `DCD_PAGE_LOAD_TIMEOUT`，默认 60 秒。
  - Chrome driver 初始化后设置页面加载和脚本超时，避免单页卡住越过提交缓冲。
- `README.md` 更新“触发前分类”说明。
- `CHANGELOG.md` 记录本次变更。

### 结果
- `Classify step1 failure` 和 `Auto-fix step1 error` 仍保留，作为真正站点结构变化或致命解析失败时的自动修复入口。
- 对正常爬取中的小批量数据保护、局部车型跳过、AI Provider 自身不可用等情况，不再调用 AI 修复，减少误报和日志噪音。
- 对确实需要 AI 修复但 Provider 暂时不可用的情况，监控工作流会清晰记录“未产出可用改动”，不会继续制造 AI Monitor failure。
- 懂车帝下午长跑会在 step2 启动前按 job 剩余安全时间缩短运行时长，优先让爬虫主动 `exit code 10` 并提交进度，而不是等 GitHub 6 小时取消。

---

## 2026-06-03：修复爬虫分段退出后同一 job 内反复重启

### 用户诉求
- 之前提交的代码仍有问题，用户用 OpenCode 调用其它模型改过后，要求查看 git 提交历史、当前爬虫 workflow 运行情况，并继续优化。

### 排查
- 最新提交历史显示 OpenCode 已推送：
  - `1a537b4`：为汽车之家字母列表页添加 SSL/Connection 错误重试。
  - `c0b14eb`：将汽车之家 SSL 重试提高到 5 次、请求超时提高到 20 秒。
- GitHub Actions 中最新汽车之家手动运行 `26815455208` 仍在 `Run step1 loop` 中长时间运行，已接近 6 小时。
- 之前懂车帝手动运行 `26813778162` 被取消在 6 小时附近。
- 修复推送后，定时 `合并分析` run `26835118168` 失败在完整性校验，原因是当前还没有 `autoHome_*.json` 和 `dongchedi_*.json` 两份完整爬虫产物；这是保护逻辑，但用 failure 表示“暂无完整数据”会制造红叉和 AI 监控噪音。
- 根因不是 schedule 时区错误：当前 workflow 的上午 cron 是北京时间 09:07-11:52，下午 cron 是北京时间 13:07/13:17/13:27。
- 真正的问题是两个 workflow 收到爬虫脚本的 `exit code 10`（表示本次时间预算用完、未完成、下次继续）后，会在同一个 GitHub Actions job 内立即重新启动长步骤：
  - 汽车之家 `Run step1 loop` 会反复运行 step1。
  - 懂车帝 `Run step2 loop` 会反复运行 step2，最多到 50 轮或 job 超时。
- 这会把“上午约 3 小时/下午约 5 小时 50 分钟”的脚本级预算叠加成接近 GitHub job 超时，导致运行时间不符合预期。

### 修改
- `crawl-autohome.yml`：
  - step1 收到 `exit code 10` 后提交进度并正常结束本次 workflow，不再立即重跑。
  - 只有 step1 真正完成后，才运行 step2-6、输出校验、半月完成标记和 artifact 上传。
  - 真实错误仍进入失败分类和自动修复入口；修复后重试也遵守同样的分段退出规则。
- `crawl-dongchedi.yml`：
  - step2 收到 `exit code 10` 后提交进度并正常结束本次 workflow，不再在同一 job 内循环。
  - 只有 step2 真正完成后，才运行 step3/4、输出校验、半月完成标记和 artifact 上传。
  - 真实错误仍保留分类和自动修复入口。
- `README.md` 补充分段续爬说明：`exit code 10` 表示时间预算用完，workflow 会保存进度并等待下一次触发继续。
- `merge-and-filter.yml` 增加 `ready` 输出：定时合并遇到爬虫数据缺失或少于 50 行时成功跳过 Release/Pages，不再把“数据未就绪”标成工作流失败；手动 `force_merge=true` 仍保持严格失败。
- `CHANGELOG.md` 记录本次 workflow 优化。

### 结果
- 单次 workflow run 不会再因为分段未完成而自我重启到 6 小时超时。
- 上午、下午窗口的实际运行时长会更接近配置的 `MORNING_RUN_TIME=10800` 和 `AFTERNOON_RUN_TIME=21000`。
- 半月完成后跳过机制仍保留，未完成进度仍会提交到仓库供下次继续。
- 合并分析不会因为当前半月爬虫尚未完成而每天产生失败红叉，但仍不会发布不完整数据。

---

## 2026-06-02：修复汽车之家爬虫 SSL 错误

### 用户诉求
- 汽车之家爬虫报错，需要排查并修复。

### 排查
- GitHub Actions 运行 `26813787152` 失败，错误日志显示 SSL 握手失败：
  ```
  requests.exceptions.SSLError: HTTPSConnectionPool(host='www.autohome.com.cn', port=443): Max retries exceeded with url: /grade/carhtml/A.html (Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1010)')))
  ```
- 根因：`scripts/test_autohome.py` 第 256 行 `session.get()` 没有捕获 SSL 错误，当前重试策略只针对 HTTP 状态码 `[429, 500, 503, 504]`，不包括 SSL 连接层错误。
- mihomo 代理节点 SSL 握手失败时，程序直接崩溃。

### 修改
- `scripts/test_autohome.py` 的 `download_car_pages()` 函数中，字母列表页请求添加 SSL/Connection 错误重试。
- 捕获 `requests.exceptions.SSLError` 和 `requests.exceptions.ConnectionError`。
- 使用指数退避策略（2/4/8秒），最多重试 3 次。
- 添加 `resp = None` 初始化和 `if resp is None` 检查，消除 Pyright 警告。

### 评审
- 启动 3 个 Oracle 并行评审（均 fallback 到 glm-5.1）。
- 3/3 通过，建议扩大异常捕获范围和使用指数退避。

### 结果
- 代理节点 SSL 握手失败时会自动重试，不再直接崩溃。
- 语法校验通过。

---

## 2026-06-02：GitHub Actions 爬虫代理订阅运行时修复

### 用户诉求
- 爬虫运行日志显示“无代理”，希望从 GitHub Secrets 的 `PROXY_SUBSCRIPTIONS` 读取多个机场订阅。
- 如果没配置订阅、订阅拉不到节点、或节点全不可用，再降级为无代理直连。
- 询问多个订阅地址在 `PROXY_SUBSCRIPTIONS` 中应如何分隔。

### 排查
- 两个爬虫 workflow 之前只把 secret 写入 `/tmp/proxies.json`，但后续运行判断的是仓库根目录 `proxies.json`，因此始终走“无代理”分支。
- `scripts/run_with_proxy.py` 当前没有 workflow 传入的 `--step`、`--max-series` 参数，且底层爬虫脚本也没有 `--proxy` 参数；即使进入代理分支也不可靠。
- Chrome/Selenium 不一定自动继承 `HTTP_PROXY`，需要显式设置 Chrome 的 `--proxy-server`。
- 订阅 URL 或节点链接可能包含敏感 token，日志中不能打印原始订阅地址或订阅内容。

### 修改
- 新增 `custom_scripts/setup_proxy_runtime.py`：
  - 支持 `PROXY_SUBSCRIPTIONS` 为 JSON 对象、JSON 数组、每行一个 URL，或用英文分号/竖线/逗号分隔的 URL 列表。
  - 只在代理准备步骤读取 secret，不再写入 `$GITHUB_ENV` 传播原始订阅。
  - 拉取订阅并解析 VMess、VLESS、Trojan、SS、Hysteria2、TUIC、WireGuard、Clash YAML 等节点。
  - 自动下载并启动 mihomo，生成本地 `http://127.0.0.1:7890` / `socks5://127.0.0.1:7891` 代理。
  - 通过 `http://www.gstatic.com/generate_204` 等地址做连通性测试，测试通过才写入 `PROXY_ENABLED=true`。
  - 未配置、拉取失败、解析不到节点、mihomo 不可用或全部节点测试失败时，写入 `PROXY_ENABLED=false` 并直连。
- `crawl-autohome.yml`、`crawl-dongchedi.yml` 改为根据 `PROXY_ENABLED` 决定日志和运行分支，代理启用时直接运行原爬虫脚本，由环境变量统一接管请求代理。
- `scripts/test_autohome.py`、`crawl_dongchedi.py` 在 `PROXY_ENABLED=true` 时为 Chrome 增加 `--proxy-server=http://127.0.0.1:7890`。
- `scripts/generate_clash_config.py` 增加订阅地址脱敏日志，并避免打印订阅内容片段。
- 更新 `README.md` 说明 `PROXY_SUBSCRIPTIONS` 支持的格式和降级逻辑。

### 结果
- workflow 不再因为 `/tmp/proxies.json` 与根目录 `proxies.json` 不一致而误判为“无代理”。
- 代理只有在确实可用时启用；不可用时自动直连，不会阻塞爬虫。
- 订阅 token 不会写入仓库目录，也不会在日志中直接打印。

---

## 2026-06-02：修复明文 Clash 订阅被误判为无节点

### 用户诉求
- `PROXY_SUBSCRIPTIONS` 直接填两行 URL 后，重新运行爬虫仍显示无代理。

### 排查
- 最新手动运行已经在 `67dc86c` 上，说明不是旧 commit rerun。
- 本地复现两行 URL：
  - 第一条订阅在当前网络环境返回 HTTP 421。
  - 第二条订阅可下载，但内容是非 ASCII 明文 Clash YAML；`scripts/generate_clash_config.py` 尝试按 Base64 解码时抛出 `ValueError: string argument should contain only ASCII characters`，导致订阅内容被丢弃，最终节点数为 0。
- 因节点数为 0，`setup_proxy_runtime.py` 按设计降级为无代理直连。

### 修改
- `scripts/generate_clash_config.py` 的订阅 Base64 解码失败处理增加 `ValueError` 捕获。
- 非 Base64 内容现在会按原文继续解析，可正常识别明文 Clash YAML。
- 取消了两个已按旧逻辑降级为直连的手动爬虫运行，避免继续无代理消耗 Actions。

### 结果
- 两行 URL 本地复测可解析出第二条订阅中的 Clash YAML 节点。
- 第一条 HTTP 421 仍会被跳过，但不会影响后续可用订阅。

---

## 2026-06-02：更换订阅抓取 User-Agent，避免旧客户端风控

### 用户诉求
- 更新 `PROXY_SUBSCRIPTIONS` 后重新运行仍显示无代理。
- 服务商后台提示订阅被 `clashforwindows/0.20.39` 旧客户端请求触发安全拦截并重置订阅。
- 要持续监控工作流，直到看到爬虫通过代理启动。

### 排查
- 当前 `scripts/generate_clash_config.py` 抓取订阅时使用 `ClashForWindows/0.20.39`，与服务商提示的异常客户端一致。
- 两个最新手动爬虫 run 已经运行在代理逻辑 commit 上，但仍会因为旧 UA 抓订阅而降级直连。
- 本地将订阅抓取 UA 改为新版客户端标识后，RioLU 订阅可成功返回明文 Clash YAML，并解析出 51 个节点。

### 修改
- `scripts/generate_clash_config.py` 默认订阅抓取 UA 改为 `mihomo/1.19.13`。
- 支持通过 `PROXY_SUBSCRIPTION_USER_AGENT` 环境变量覆盖默认 UA。
- 取消已用旧 UA 启动并降级直连的两个手动爬虫 run。

### 结果
- RioLU 订阅本地复测：`ClashVergeRev` 常见格式返回 406，`mihomo/1.19.13` 可解析出 51 个节点。
- 后续 workflow 会用新版 UA 获取订阅，避免继续触发旧客户端风控。

---

## 2026-06-02：按上午/下午窗口拆分并发锁并收紧延迟

### 用户诉求
- 查看本机 OpenCode 最新会话，并用 GitHub CLI 对照实际工作流运行情况。
- 如果工作流仍不符合“上午 9-12、下午 13:00-13:30、半月完成跳过”的预期，就继续修复、推送并监控。

### 排查
- OpenCode 最新主会话为 `ses_179f955e3ffeV8j3F18P25pDAx`，主题是审查 GPT-5.5 的 `b32cf40` 备用 schedule 修复，并继续提交了 `e69f860`：上午动态缩短，目标是 12:30 前结束。
- GitHub Actions 现状显示：
  - 懂车帝上午手动补跑 `26793433837` 仍在运行，它是在 `e69f860` 推送前启动的旧逻辑，不受动态缩短约束。
  - 下午懂车帝 schedule `26802472704` 处于 pending，因为顶层 `concurrency` 只按爬虫+分支分组，上午运行挡住了下午窗口。
  - 汽车之家下午 schedule `26802487516` 8 秒成功，属于启动时已错过允许窗口后快速跳过。
  - 汽车之家上午手动补跑 `26793432477` 失败在保存进度阶段：本地提交 `Update progress - 04:52` 后直接 `git push`，远端已有懂车帝进度提交，导致 push 被拒绝。
  - AI Auto Fix Monitor `26799197255` 因只读取 `step1_error.log`，没有优先看完整失败日志，把 git push 竞态误判为站点结构异常并调用模型，造成不必要的 AI 修复失败。
- OpenCode 动态缩短逻辑本身能计算到 12:30，但它发生在随机延迟前；若上午仍有 0-10 分钟随机延迟，实际结束仍可能越过 12:30。下午 13:27 的备用触发也可能被随机延迟拖过 13:30。

### 修改
- `crawl-autohome.yml` 和 `crawl-dongchedi.yml` 的 `concurrency.group` 改为包含 `github.event.schedule` 或 `run_profile`，上午和下午各自独立并发锁。
- 同一窗口的备用触发仍不会并发重复跑，但上午不会再阻塞下午。
- 上午窗口不再做随机启动延迟。
- 上午动态 RUN_TIME 从“到 12:30 的剩余时间”改为“到 12:30 的剩余时间再扣 15 分钟缓冲”，避免初始化和步骤切换把结束时间拖过午间。
- 下午窗口继续 0-10 分钟随机延迟，但延迟会封顶到北京时间 13:30 前。
- 新增 `custom_scripts/git_sync_progress.sh`，爬虫工作流所有进度/完成标记提交都改为 `pull --rebase` 后 `push`，最多重试 3 次，避免两个爬虫同时写进度时因远端更新导致失败。
- `AI_Auto_Fix_Monitor.yml` 改为优先抓取完整失败日志，再合并 error-log artifact 一起分类。
- `classify_crawl_failure.py` 新增 git push/rebase 非快进、权限拒绝等基础设施异常识别，命中后跳过大模型修复。
- 更新 `README.md` 和本记录。

### 结果
- 上午 late start 会缩短并尽量在 12:15 前收口，保留午间缓冲。
- 下午 schedule 不会被上午窗口占住，也不会随机延迟到 13:30 之后才开始。
- 汽车之家和懂车帝保存进度、写入完成标记时都会先同步远端再推送，降低进度提交竞态导致的失败概率。
- AI 修复监控不再因为进度同步或 GitHub 基础设施问题误调模型，减少“失败后又触发一串 AI 修复运行”的噪声。

---

## 2026-06-02：上午爬虫动态缩短，12:30 前必须结束

### 用户诉求
- 上午 cron 最晚触发 11:52，如果还跑满 3 小时会到 14:52，和下午 13:07 的触发冲突
- 北京时间 12:30 前上午爬虫必须结束
- 12:30-13:00 之间不跑爬虫（模拟午饭时间）
- 上午启动得晚 → 爬虫时间要缩短
- 下午启动得晚 → 爬虫时间不用缩短

### 修改
- `crawl-autohome.yml` 和 `crawl-dongchedi.yml`：
  - "Calculate delay from trigger time" 步骤：上午窗口结束时间从 12:00 改为 12:30
  - "Configure crawl window" 步骤：新增上午动态 RUN_TIME 计算
    - `NOW_UTC_SECONDS = $(date -u +%s) % 86400`（当前 UTC 时间的当日秒数）
    - `REMAIN = 16200 - NOW_UTC_SECONDS`（到 UTC 04:30 = 北京 12:30 的剩余秒数；后续已改为再扣 900 秒缓冲）
    - REMAIN < 300 → 跳过（不足 5 分钟）
    - REMAIN < RUN_SECONDS → RUN_TIME 缩短为 REMAIN
    - 否则 → 保持原 RUN_TIME（10800 秒 = 3 小时）
  - 下午保持固定 AFTERNOON_RUN_TIME = 21000 秒（5h50m）不变

### 效果
| 触发时间 (UTC) | 北京时间 | 到 12:30 剩余 | RUN_TIME | 结束时间 |
|---|---|---|---|---|
| 01:07 | 09:07 | 3h23m | 10800 (3h) | 12:07 |
| 02:22 | 10:22 | 2h6m | 6660 (扣 15m 缓冲后 1h51m) | 12:13 |
| 03:37 | 11:37 | 55m | 2400 (扣 15m 缓冲后 40m) | 12:17 |
| 03:52 | 11:52 | 38m | 1380 (扣 15m 缓冲后 23m) | 12:15 |

---

## 2026-06-02：上午 schedule 未触发的备用调度修复

### 用户诉求
- 上午 09 点多还没有看到爬虫开始运行，需要检查原因并修复。

### 排查
- 北京时间 2026-06-02 09:45 检查远端 Actions，`main` 已是最新 commit `0b355ea`。
- 两个主爬虫 workflow 的远端 YAML 已包含 UTC 01:07（北京时间 09:07）上午定时。
- 但远端 run 列表中没有 2026-06-02 上午的 `汽车之家爬虫` 或 `懂车帝爬虫` run，说明这次不是被 workflow 内部时间窗守卫跳过，而是 GitHub Actions schedule 本身没有按时投递。

### 修改
- `crawl-autohome.yml` 和 `crawl-dongchedi.yml` 的上午单点定时改为 UTC `7,22,37,52 1-3 * * *`，即北京时间 09:07-11:52 多次备用触发。
- 下午单点定时改为 UTC `7,17,27 5 * * *`，即北京时间 13:07/13:17/13:27 备用触发。
- 两个主爬虫 workflow 增加顶层 `concurrency`，同一爬虫同一分支只允许一个运行，避免备用触发造成并发重复爬。
- 时间窗守卫改为识别当前 schedule 属于 `morning` 还是 `afternoon`，延迟到其它窗口时直接跳过，避免上午备用触发被拖到下午后误当下午任务运行。
- `README.md` 同步更新备用触发、并发锁和运行窗口说明。

### 结果
- 后续即使 GitHub 漏掉单个 schedule，也还有多个备用触发机会。
- 如果多个备用触发都到达，只有一个同源爬虫会实际运行，其它会排队后因错过窗口而跳过。

---

## 2026-06-01：避免 GitHub 延迟 schedule 傍晚补跑

### 用户诉求
- 检查为什么下午爬虫实际到傍晚六点多才开始。
- 继续排查其它工作流问题并一并修复。

### 排查
- 远端 `汽车之家爬虫` run `26748553224` 与 `懂车帝爬虫` run `26748749321` 都是 `schedule` 事件，但创建时间分别为 UTC 10:09/10:13，即北京时间 18:09/18:13。
- 当前 workflow 配置是 UTC 05:00（北京时间 13:00），说明不是时区写错，而是 GitHub Actions schedule 被延迟执行。
- 已取消仍在傍晚运行的汽车之家 run，避免继续在错误时间段爬取。
- 懂车帝本次失败发生在 Selenium/Chrome 初始化阶段，`execute_cdp_cmd` 对本地 chromedriver 读超时，属于 runner/浏览器临时异常。

### 修改
- `crawl-autohome.yml` 与 `crawl-dongchedi.yml` 的定时从 UTC 01:00/05:00 调整为 UTC 01:07/05:07，避开 GitHub Actions 整点调度高峰。
- 两个主爬虫 workflow 增加 schedule 时间窗守卫：如果实际启动时已不在北京时间 09:00-12:00 或 13:00-13:30 内，直接跳过，不再傍晚补跑。
- 直接 schedule 的随机启动延迟从 5-20 分钟缩短为 0-10 分钟，下午窗口更稳定落在 13 点多。
- `crawl_dongchedi.py` 的浏览器初始化增加最多 3 次重试、失败后清理浏览器实例，并补充 headless/remote debugging 参数，降低 GitHub runner 抖动导致的失败。
- `custom_scripts/classify_crawl_failure.py` 新增 `transient_infra` 分类，遇到 localhost chromedriver 读超时、Chrome 启动类临时异常时跳过 AI 自动修复，避免无意义的大模型修复运行。
- 更新 `README.md` 中的调度、延迟和延迟 schedule 跳过说明。

### 结果
- 后续即使 GitHub 把 13 点的 schedule 拖到傍晚，也只会跳过，不会在错误时间段实际爬取。
- 懂车帝浏览器启动超时会先自动重试；若仍失败，会被分类为临时基础设施问题，不再触发 AI 修复循环。

---

## 2026-06-01：修复爬虫工作流调度与分段退出处理

### 用户诉求
- 检查当前 GitHub Actions 工作流运行情况，发现 bug 直接修复。
- 爬虫工作流每天上午 9 点到 12 点左右运行约 3 小时，下午 13:00-13:30 之间运行一次约 6 小时但避开 6 小时超时限制。
- 不再隔一天运行，但保留每半个月完整成功后本周期不再爬取的限制。
- 完成后自动推送。

### 修改
- `crawl-autohome.yml` 和 `crawl-dongchedi.yml` 改为每天 UTC 01:00 与 05:00 触发，对应北京时间上午与下午两个运行窗口。
- 上午窗口使用 `RUN_TIME=10800`，下午窗口使用 `RUN_TIME=21000`，job 超时提高到 390 分钟，避免脚本运行时间贴住 6 小时边界。
- 移除两个主爬虫 workflow 和 `crawl-trigger.yml` 中的奇偶日跳过逻辑，继续保留 `crawl_state/*_YYYYMM_H1.done` / `*_H2.done` 半月完成标记。
- 修复爬虫 step 中 `python ... | tee log` 在 `pipefail` + `bash -e` 下会提前中断的问题，让 `exit 10` 能正确进入“提交进度并等待下次”的分支，而不是误判为 workflow failure。
- `crawl-trigger.yml` 改为只在北京时间 09:00-12:00 或 13:00-13:30 触发，并把 `run_profile` 传给目标爬虫；外部触发补足延迟时会封顶到当前运行窗口结束前。
- `merge-and-filter.yml` 改到北京时间 20:30 运行，并在合并前先校验两份爬虫 artifact 的行数，拒绝 0 行或明显不完整的旧数据。
- `crawl_dongchedi.py` 获取车系列表时优先刷新，若源站返回非 JSON 或空结果则回退使用缓存；新增 `custom_scripts/reset_dongchedi_progress.py`，新半月重置时保留懂车帝车系列表缓存。
- 更新 `README.md` 中的调度、运行时长、超时和半月跳过说明。

### 结果
- 当前工作流运行异常主要来自“懂车帝源站接口拿不到车系列表”和“分段退出码被 shell 提前打断”；后者已修复，前者会在后续每日窗口继续重试并保留 AI 修复入口。
- 爬虫现在每天运行两段，完整成功后仍会在本半月周期内自动跳过。

---

## 2026-05-29：更新默认推送规则

### 用户诉求
- 不要再询问是否自动推送。

### 修改
- 更新 `AGENTS.md`：完成代码、工作流或文档改动并提交后，默认自动 push 到远端，不再单独询问用户。
- 将上一次本地提交的 AI 修复分类逻辑与本次规则更新一起推送到远端。

### 结果
- 后续任务完成并提交后会默认自动推送。

---

## 2026-05-29：AI 修复前区分主动分段退出与真实爬取异常

### 用户诉求
- AI 修复监控不能把“爬了几百个车型配置后主动退出/等待下次继续”误判为需要修复。
- 只有当网站链接或页面结构变化，导致拿不到车型配置时，才调用大模型修复。

### 修改
- 新增 `custom_scripts/classify_crawl_failure.py`，对爬虫日志做规则分类。
- 分类为 `progress_exit` 时跳过 AI 修复：包括 `exit code 10`、达到时间/数量限制、保存进度、循环保护退出、已处理数百条等特征。
- 分类为 `site_breakage` 或 `unknown` 时才允许调用 `scripts/auto_fix_workflow.py`：包括未生成数据、解析不到配置、输出行数过少、接口/页面异常等特征。
- `crawl-autohome.yml` 和 `crawl-dongchedi.yml` 的内联 Auto-fix 步骤前增加分类步骤，主动分段退出不再重试修复。
- `AI_Auto_Fix_Monitor.yml` 在下载 artifact 或读取失败 run 日志后，先调用分类脚本；若是分段退出，则直接报告跳过，不再调用大模型。
- 两个爬虫 workflow 失败时上传 `error-log` artifact，方便监控工作流拿到更精确的日志。
- 更新 `README.md` 中的自动修复触发前分类说明。

### 结果
- 正常的分批爬取/主动保存进度不会浪费大模型修复额度。
- 真正疑似站点结构变化、链接失效或配置解析失败时，仍会进入 AI 修复流程。

---

## 2026-05-29：每隔一天运行、半月完成跳过与车型范围收窄

### 用户诉求
- 汽车之家和懂车帝都改为每隔一天运行一次。
- 每半个月内爬取全部车型完成后，本半月不再继续爬取。
- 暂时只看轿车、跑车和 SUV，不看 MPV、房车和各种货车。
- 如果 MPV、房车和各种货车有明确链接范围，要记录下来并不爬它们。

### 修改
- `crawl-autohome.yml` 和 `crawl-dongchedi.yml` 的定时改为北京时间奇数日白天运行，即每隔一天触发一次。
- `crawl-trigger.yml` 同步限制为北京时间 09:00-17:00 且奇数日才触发目标爬虫。
- 新增 `crawl_state/` 半月状态目录，主爬虫完成并通过输出完整性校验后写入 `*_YYYYMM_H1.done` 或 `*_YYYYMM_H2.done`。
- 同一个半月周期内发现完成标记时直接跳过爬虫；进入新半月周期且未完成时自动重置对应进度，从头开始本周期全量爬取。
- `scripts/test_autohome.py` 和 `crawl_dongchedi.py` 新增车型级别过滤：输出阶段排除 MPV、房车、皮卡、微面、轻客、客车、货车、卡车、微卡、轻卡等非目标类型。
- 懂车帝列表接口如果返回明确级别字段，会在车系列表阶段先跳过非目标车系，并把跳过记录写入 `progress["excluded_series"]`。
- 新增 `config/CRAWL_SCOPE.md`，记录当前目标车型、排除车型，以及源站明确链接/级别范围的处理方式。
- 更新 `README.md` 中的目录、调度、半月跳过和车型范围说明。

### 结果
- 两个爬虫自动运行频率降为每隔一天一次。
- 每个半月周期内完成全量数据后不再重复消耗 Actions 分钟。
- 发布数据默认只保留轿车、跑车和 SUV 相关车型。

---

## 2026-05-29：调整爬虫白天运行与人工访问节奏

### 用户诉求
- 汽车之家和懂车帝爬虫都在白天运行。
- 模拟人类作息时间和动作速率，两次访问之间间隔几秒。
- 单次总运行时长不超过 6 小时。

### 修改
- `crawl-autohome.yml` 调整为每周一、周四 UTC 02:00（北京时间 10:00）运行，避免原周四 UTC 14:00 对应北京时间 22:00。
- `crawl-dongchedi.yml` 保持每天 UTC 05:30（北京时间 13:30）运行，并补充白天运行说明。
- 两个主爬虫 workflow 都显式配置 `RUN_TIME=21600`、`timeout-minutes=360`，把单次运行上限控制在 6 小时内。
- 新增 `CRAWL_MIN_DELAY_SECONDS=3`、`CRAWL_MAX_DELAY_SECONDS=8`，并在 `scripts/test_autohome.py`、`crawl_dongchedi.py` 的网络访问之间使用随机等待，模拟人工浏览节奏。
- `crawl-trigger.yml` 的随机触发窗口从北京时间 8-22 点收紧到 9-17 点，避免外部随机触发在夜间拉起爬虫。
- 更新 `README.md` 中的调度、运行上限和访问节奏说明。

### 结果
- 自动爬取任务默认集中在北京时间白天运行。
- 两个数据源的网络访问默认间隔 3-8 秒，可通过环境变量调整。
- GitHub Actions job 与脚本级 `--time-limit` 都不会超过 6 小时。

---

## 2026-05-29：新增 GitHub Pages 车型配置网页查看器

### 用户诉求
- 除了 Release 表格文件，希望有一个免费的网页，可以访问网站后像操作 Excel 一样筛选、排序、查看车型配置。

### 修改
- 新增 `docs/index.html`、`docs/styles.css`、`docs/app.js`，实现纯静态表格工作台。
- 网页支持“全部车型/符合条件”数据集切换、全局搜索、表头排序、每列筛选、按数据来源/品牌/车系快速筛选、列显示控制、分页和当前结果 CSV/JSON 导出。
- 在 `merge-and-filter.yml` 新增 `deploy-pages` job：合并产物生成后，把 `docs/` 与最新 `merged_YYYYMMDD.json`、`filtered_cars_YYYYMMDD.json`、CSV 文件打包并部署到 GitHub Pages。
- 新增 `deploy-pages.yml` 独立发布网页工作流：即使当前合并因爬虫数据不足被保护规则拦截，也可以先部署网页，并使用最近一份带 `merged_*.json` 的 Release 数据。
- 生成 `data/manifest.json`，让网页能显示数据日期、行数和原始文件下载入口。
- 新增 `docs/CNAME`，将 GitHub Pages 自定义域名固定为 `cars.jiucai.eu.org`。
- 网页默认打开“符合条件”数据集，并将合并的长宽高/车身尺寸字段拆成 `长度(mm)`、`宽度(mm)`、`高度(mm)` 三列展示。
- 删除未跟踪的 `.github/workflows/pr-auto-merge.yml`，保留已有 `auto-merge.yml`，避免重复自动合并工作流和 `pull_request_target` 权限面。
- 修复本地遗留的 `scripts/merge_data.py` 与 `.github/workflows/ci.yml` 合并冲突标记，恢复语法校验和 CI 冒烟测试可运行状态。
- 更新 `README.md`，补充网页查看器目录、功能、发布方式和本地预览方法。

### 结果
- 仓库启用 GitHub Pages 的 GitHub Actions 发布源后，每次“合并分析”工作流成功都会自动更新网页。
- 静态网页不需要服务器和数据库，适合 GitHub Pages 免费托管。

---

## 2026-05-28：修复过滤逻辑和不完整数据误发布

### 问题
- `scripts/merge_data.py` 对数值条件统一使用 `<=`，导致 `纯电续航(km)` 被按 `<= 150` 判断，和高级筛选中常见的 `>= 150` 语义相反。
- 部分配置字段在源数据中叫 `手机APP远程功能`、`钥匙类型`、`电动座椅记忆功能`、`外后视镜功能`，旧过滤逻辑没有完整识别。
- 爬虫 workflow 使用 `python ... | tee log` 时没有启用 `pipefail`，Python 返回未完成的 exit code 10 会被 `tee` 的 0 掩盖，导致不完整数据被上传并进入 Release。

### 修改
- 将百公里加速改为独立 `<= 7` 判断，纯电续航改为独立 `>= 150` 判断。
- 增强功能项匹配，支持字段名归一化和字段值关键字匹配。
- 为爬虫 workflow 的 `tee` 管道启用 `pipefail`，并且只有确认步骤完成后才写入完成标记。
- 懂车帝配置页加载超时时不再把对应车系加入 `crawled_series`，避免没有 HTML 文件却把步骤判为完成。
- 为汽车之家、懂车帝 artifact 以及合并发布增加最小行数检查，避免继续发布空数据或明显不完整数据。

---

## 2026-05-28：修复 Release CSV 过小

### 问题
- 最新 Release 的 `filtered_cars_20260527.csv` 只有表头，`filtered_cars_20260527.json` 是空数组。
- `scripts/merge_data.py` 里的 `merged_*.csv` 实际写入的是过滤结果，不是全部合并数据；当过滤结果为空时，Release 没有可查看的 CSV。

### 修改
- `merged_*.csv` 改为写入全部归一化后的汽车之家 + 懂车帝数据。
- 新增 `merged_*.json`，与完整 CSV 一起上传到合并产物和 GitHub Release。
- `filtered_cars_*` 保持过滤结果语义；即使过滤为空，Release 仍会提供有数据行的 `merged_*.csv`。
- 发布前增加 `merged_*.csv` 数据行检查，避免继续发布只有表头的小文件。

---

## 2026-05-28：添加 CI 与 PR 自动合并

### 问题
- 本地环境之前没有 GitHub remote，导致 CI/自动合并工作流只提交在临时工作区，未真正推送到 GitHub。
- PR 缺少基础自动测试和自动合并入口。

### 修改
- 新增 `ci.yml`，在 `push`、`pull_request` 和手动触发时安装依赖、编译 Python 文件、调用 `custom_scripts/validate_syntax.py` 校验变更文件，并对 `scripts/merge_data.py` 做样本冒烟测试。
- 新增 `auto-merge.yml`，当非草稿 PR 带有 `automerge` 标签时启用 GitHub 原生 squash auto-merge。
- 修复 `scripts/merge_data.py` 过滤条件未识别归一化后的 `蓝牙/数字钥匙` 字段，避免符合条件车型被误过滤。

---

## 2026-04-15 12:00：修复 workflow + 随机触发器 + opencode 配置

### 问题1：PROXY_SUBSCRIPTIONS JSON 格式损坏
- **原因**：`echo '${{ secrets.PROXY_SUBSCRIPTIONS }}'` 单引号包裹导致 JSON 内容被额外引号包围
- **修复**：使用 `cat <<'INNER_EOF'` 直接写入 secret 内容，不加额外引号
- **验证**：添加 JSON 格式验证步骤 `python3 -c "import sys,json; json.load(sys.stdin)"`

### 问题2：爬虫随机延迟占用工作流时间
- **需求**：东八区 8~22 点之间每周几随机触发，不占用工作流时间
- **方案**：创建 `crawl-trigger.yml` wrapper workflow
  - 支持 `repository_dispatch` 触发（可由 cron-job.org 调用）
  - 随机选择 autohome 或 dongchedi
  - 计算触发时间戳，实现延迟不占用工作流分钟

### 问题3：免费模型优先逻辑
- **修改**：`scripts/auto_fix_workflow.py` 排序算法改为免费 Provider 优先
- **顺序**：AtomGit → ZEN → NVIDIA NIM → Modal → OpenRouter → 其他

### 问题4：TUI 显示旧模型
- **方案**：创建 `config/opencode.json` 配置文件
- **使用**：`provider`（单数）和 `whitelist` 控制显示的模型
- **隐藏**：Haiku、4.5 前代、mini/low/medium 等弱模型

### 问题5：追加全局规则
- **新增**：AGENTS.md 添加"执行风格"章节
- **规则**：一次性完成全部任务、不等待确认、全面覆盖、禁止拖延

### 完成修改

| 文件 | 修改内容 |
|------|----------|
| `crawl-autohome.yml` | 修复 PROXY_SUBSCRIPTIONS、添加 repository_dispatch 支持、延迟计算 |
| `crawl-dongchedi.yml` | 修复 PROXY_SUBSCRIPTIONS、添加 repository_dispatch 支持、延迟计算 |
| `crawl-trigger.yml` | **新增** 随机触发 wrapper workflow |
| `scripts/auto_fix_workflow.py` | 免费模型优先排序算法 |
| `config/opencode.json` | **新增** TUI 模型 whitelist 配置 |
| `AGENTS.md` | 添加"执行风格"全局规则 |

---

## 2026-03-29 18:00：修复 workflow 报错 + actions 版本升级 + AI 监控

### 问题1：PROXY_SUBSCRIPTIONS 多行 JSON 写入 $GITHUB_ENV 格式损坏
- **原因**：`echo "KEY=value" >> $GITHUB_ENV` 不支持多行值
- **修复**：使用 GitHub 官方 heredoc 语法 `echo "KEY<<EOF" >> $GITHUB_ENV` ... `echo "EOF" >> $GITHUB_ENV`
- **安全加固**：proxies.json 改写入 `/tmp/proxies.json`（不在仓库目录内，公开仓库也不会泄露）

### 问题2：Actions 版本 @v* 写死 → Node 20 弃用警告
- `actions/checkout`, `actions/setup-python`, `actions/upload-artifact`, `actions/download-artifact` → `@main`
- `browser-actions/setup-chrome`, `nanasess/setup-chromedriver`, `softprops/action-gh-release` → `@master`
- 已确认各仓库默认分支

### 问题3：新增 AI_Auto_Fix_Monitor.yml
- 参考AutobiaoMi_R4项目，为爬虫项目创建独立监控修复 workflow
- 当爬虫 workflow 失败时自动触发
- 支持所有已配置的 Provider（AtomGit/Minimax/Modal/ModelScope/NVIDIA/OpenRouter/XAI/ZEN）
- 修复成功后自动重触发失败的工作流

---

## 2026-03-29 17:30：GitHub Actions 免费额度优化

### 问题
免费账户每月 2000 分钟，ubuntu-latest 按 2x 计费，实际只有 1000 等效分钟。
之前每月消耗约 1754 等效分钟，严重超标。

### 优化措施

| 优化项 | 修改前 | 修改后 | 节省 |
|--------|--------|--------|------|
| 随机延迟 | 1~2小时 | 5~20分钟 | ~960分钟/月 |
| step2-6 超时 | 120分钟 | 30分钟 | 防止浪费 |
| step3-4 超时 | 60分钟 | 15分钟 | 防止浪费 |
| merge 超时 | 120分钟 | 10分钟 | 防止浪费 |
| step1 commit 延迟 | 30~90秒 | 15~45秒 | 减少等待 |
| 旧 crawl.yml | 重复运行 | 已删除 | 消除重复 |

### 优化后月消耗（2x计费后）

| Workflow | 次数/月 | 估算分钟 | 2x计费 |
|----------|---------|----------|--------|
| autohome-step1 | 8 | ~150 | ~300 |
| autohome-step2-6 | 8 | ~20 | ~40 |
| dongchedi-step1 | 8 | ~60 | ~120 |
| dongchedi-step2 | 8 | ~90 | ~180 |
| dongchedi-step3-4 | 8 | ~10 | ~20 |
| merge+release | 8 | ~5 | ~10 |
| **合计** | | | **~670** |

✅ 从 1754 降到约 670 等效分钟，节省 62%，安全在免费额度内。

---

## 2026-03-29 17:00：全局规则 + 通用多Provider自动修复系统重构

### 用户需求
1. 将全局规则写入 `AGENTS.md`
2. 重构 `scripts/auto_fix_workflow.py` 支持 Lobe-Chat 风格的动态 Provider 发现
3. `XXXX_MODEL_LIST` 和 `XXXX_PROXY_URL` 非必填，未配置不报错
4. 未配置 `MODEL_LIST` 则使用排行榜前10(1M+)模型，已配置则取并集
5. 更新 README.md 和 HISTORY.md

### 完成修改

| 文件 | 修改内容 |
|------|----------|
| `AGENTS.md` | **新增** 全局规则文件（语言、提交、模型选择、opencode 配置等） |
| `scripts/auto_fix_workflow.py` | 重构为通用多Provider系统，动态发现 `_API_KEY`，支持12+ Provider |
| `README.md` | 更新 scripts/auto_fix_workflow.py 文档、Provider 列表、Secrets 列表 |

### 新增 AGENTS.md 关键规则
- 所有回复使用中文
- 临时文件验证后删除
- 每次修改代码后必须语法校验
- 优先选择排行榜前25且有免费资源的模型
- `XXXX_MODEL_LIST` 未配置不报错
- 旧模型必须隐藏（Haiku、4.5前代、mini/low/medium 等）

### 当前已配置的 GitHub Secrets
ACTION_PAT、ATOMGIT_API_KEY、MINIMAX_API_KEY、MINIMAX_CODING_PLAN_API_KEY、MODAL_API_KEY、MODELSCOPE_API_KEY、MOONSHOT_API_KEY、NVIDIA_NIM_API_KEY、OPENROUTER_API_KEY、PROXY_SUBSCRIPTIONS、XAI_API_KEY、ZEN_API_KEY

---

## 2026-03-29 16:00：清理 git 历史敏感数据

### 用户需求
将仓库转为公开，检查并清理 git 历史中的敏感数据。

### 发现问题
- `onekey-aider` 文件包含 API key

### 解决方案
- 使用 git-filter-repo 从历史中彻底删除该文件
- 强制推送到远程仓库

### 结果
- ✅ 敏感数据已从 git 历史中清除
- ✅ 仓库可安全转为公开

---

## 2026-03-29 15:40：集成大模型自动修复功能

### 用户需求
在 workflow 中集成 scripts/auto_fix_workflow.py，实现错误自动修复。

### 完成修改

| 文件 | 修改内容 |
|------|----------|
| `crawl-autohome.yml` | 集成错误自动修复，step1 和 remaining steps 失败时自动调用大模型 |
| `crawl-dongchedi.yml` | 集成错误自动修复，step2 失败时自动调用大模型 |
| `README.md` | 更新目录结构、添加 scripts/auto_fix_workflow.py 说明 |

### 工作流错误处理流程
1. 步骤执行失败，错误日志保存到 `*_error.log`
2. 检查是否有 API Key 配置
3. 调用 `scripts/auto_fix_workflow.py` 分析错误
4. 依次尝试三个模型：Minimax m2.7 → Zen MiMo v2 pro free → Grok 4.2 beta reasoning
5. 置信度 ≥ 0.7 时自动应用修复并提交推送
6. 重新运行失败的步骤

---

## 2026-03-29 15:30：公开仓库安全检查与代理支持

### 用户需求
将仓库从私有转为公开，检查敏感数据泄露风险，并添加代理支持和大模型自动修复功能。

### 完成修改

| 文件 | 修改内容 |
|------|----------|
| `.gitignore` | 添加敏感文件、临时数据忽略；保留进度文件追踪 |
| `crawl-autohome.yml` | 添加代理配置步骤；支持 `scripts/run_with_proxy.py --proxy random` |
| `crawl-dongchedi.yml` | 添加代理配置步骤；设置 http_proxy/https_proxy |
| `merge-and-filter.yml` | 删除重复的 checkout 和 setup-python |
| `scripts/auto_fix_workflow.py` | **新增** 大模型自动修复工作流错误脚本 |
| `HISTORY.md` | **新增** 合并所有历史文件为单一总结 |

### 代理使用说明
GitHub Secrets 中添加 `PROXY_SUBSCRIPTIONS`，格式：
```json
{
  "subscriptions": ["https://订阅链接1", "https://订阅链接2"],
  "exclude_keywords": ["过期", "测试"]
}
```

### 大模型自动修复功能
新增 `scripts/auto_fix_workflow.py`，支持：
- 捕获工作流错误
- 依次尝试三个模型：Minimax m2.7 → Zen MiMo v2 pro free → Grok 4.2 beta reasoning
- 自动生成修复代码并提交推送

所需 Secrets：`MINIMAX_API_KEY`, `ZEN_API_KEY`, `XAI_API_KEY`, `ACTION_PAT`

---

## 2026-02-22：项目初始化

### 需求1：修改爬虫逻辑 + 优化超时

**用户需求**：
- 已有代码爬取3年内上市的车型配置，改为爬取所有车型
- 过滤条件：零百7秒内、纯电续航150KM以上、智驾领航支持城市路段、远程启动、远程控车、手机蓝牙/UWB钥匙、座椅记忆、后视镜记忆
- 解决action爬取测试超时问题

**完成内容**：
1. `scripts/test_autohome.py`: MIN_YEAR从3改为0
2. `crawl_dongchedi.py`: MIN_YEAR从3改为0
3. `scripts/merge_data.py`: 添加过滤功能FILTER_CONDITIONS（8个条件）
4. `crawl.yml`: timeout改为360分钟

### 需求2：拆分Action步骤

**完成内容**：
- 重写`crawl.yml`，拆分为3个job：
  - `crawl-autohome`: 爬取汽车之家
  - `crawl-dongchedi`: 爬取懂车帝
  - `merge-and-filter`: 合并过滤并release

### 需求3：生成文档

**完成内容**：
- 创建`README.md`
- 创建对话历史文件

---

## 2026-02-26：断点续传与自动爬取

### 问题1: 爬取6小时没爬完
- 添加命令行参数：`--step`, `--time-limit`, `--max-cars`, `--auto`
- 为每个步骤添加时间限制检查

### 问题2: GitHub Actions自动爬取
- 添加`--auto`参数，未完成返回exit code 10
- Workflow支持循环运行：未完成则commit进度、push、重新运行

### 问题3: 调度频率调整
- 从每月1次改为每天2次（02:00、14:00）
- 每次运行2小时，爬500个车型

### 问题4: 添加随机延迟
- 开始前随机延迟10-40分钟
- commit前随机延迟30-90秒
- 重新运行前随机延迟1-3分钟

### 问题5: 懂车帝与汽车之家并行
- 懂车帝不再依赖汽车之家，独立并行运行

### 问题6: 懂车帝分步运行
- 添加命令行参数支持
- 支持时间限制和车系数量限制

### 问题7: 断点续传bug修复
- 问题：每次爬取内容重复
- 修复：添加`current_letter`和`current_car_idx`记录进度
- 添加文件存在性检查，避免重复下载

### 问题8: 懂车帝step2报错
- 修复：如果没有车系列表，自动运行第一步获取

---

## 2026-03-04：断点续传逻辑深度修复

### 汽车之家问题
- 每次爬取都是重复的，总是在同一个位置停止
- `start_car_idx` 未被使用
- `current_letter` 错误追加

### 懂车帝问题
- step 3 和 step 4 都调用 `parse_config_pages`，导致重复解析

### 解决方案

**汽车之家修复**：
```python
# 使用 skip_until_idx 正确跳过已处理的车型
skip_until_idx = start_car_idx if current_letter else 0
for letter in all_letters:
    should_process = (letter == current_letter) or (letter not in letters and current_letter is None)
    if should_process:
        car_start_idx = skip_until_idx if letter == current_letter else 0
        for car_idx, car in enumerate(cars):
            if car_idx < car_start_idx:
                continue
```

**懂车帝修复**：
```python
# step 3: 解析并保存结果
progress['parsed_data'] = {'rows': all_rows, 'headers': all_headers}
# step 4: 使用缓存或重新解析
parsed_data = progress.get('parsed_data')
```

---

## 2026-03-07：部署方案探索

### 问题：GitHub Actions免费额度不够
- 免费版每月2000分钟
- 实际需求：28800分钟/月

### 解决方案

#### 1. 频率调整（适合免费层级）
- 汽车之家：每周一、四各一次（960分钟/月）
- 懂车帝：每周二、五各一次（960分钟/月）
- 合并：每周三、六各一次
- 总计：1920分钟/月（安全范围内）

#### 2. 代理管理器 (scripts/proxy_manager.py)
- 支持多机场订阅URL
- 支持 V2Ray/Clash 配置解析
- 负载均衡策略：random, round_robin, least_used, best_performance
- 排除关键字过滤（过期、测试等）
- 节点统计与筛选

#### 3. VPS部署
- `scripts/deploy_vps.sh`: 一键部署脚本
- `VPS_DEPLOY.md`: 部署指南

#### 4. Docker部署
- `Dockerfile`: 基于Python 3.12 Alpine + Chromium
- `docker compose.yaml`: 服务定义、卷映射、资源限制
- `scripts/docker-cron.sh`: 容器内定时任务
- `DOCKER_DEPLOY.md`: 详细部署指南

---

## 2026-03-29：公开仓库安全检查与优化

### 用户需求
将仓库从私有转为公开，检查敏感数据泄露风险

### 问题分析
1. `proxies.json` 包含代理订阅token（**敏感**）
2. `__pycache__/` 被git追踪
3. `merge-and-filter.yml` 有重复的checkout步骤
4. `.gitignore` 不完整

### 完成修改

| 文件 | 修改内容 |
|------|----------|
| `.gitignore` | 添加敏感文件、临时数据忽略；保留进度文件追踪 |
| `crawl-autohome.yml` | 添加代理配置步骤；支持`scripts/run_with_proxy.py --proxy random` |
| `crawl-dongchedi.yml` | 添加代理配置步骤；设置http_proxy/https_proxy |
| `merge-and-filter.yml` | 删除重复的checkout和setup-python |
| `__pycache__/` | 从git追踪中移除 |

### 代理使用说明
GitHub Secrets 中添加 `PROXY_SUBSCRIPTIONS`，格式：
```json
{
  "subscriptions": ["https://订阅链接1", "https://订阅链接2"],
  "exclude_keywords": ["过期", "测试"]
}
```

---

## 项目当前状态

### 文件结构
```
crawl_cars/
├── scripts/test_autohome.py          # 汽车之家爬虫
├── crawl_dongchedi.py        # 懂车帝爬虫
├── scripts/merge_data.py             # 数据合并过滤
├── scripts/proxy_manager.py          # 代理管理器
├── scripts/run_with_proxy.py         # 带代理启动脚本
├── scripts/generate_clash_config.py  # Clash/Mihomo 配置生成器
├── scripts/auto_fix_workflow.py      # 大模型自动修复工作流错误
├── scripts/fix_files.py              # 代码修复工具
├── scripts/deploy_vps.sh             # VPS一键部署
├── scripts/start_with_clash.sh       # 带 Clash 代理的启动脚本
├── docker-compose.yaml       # Docker配置
├── Dockerfile                # Docker镜像构建
├── scripts/docker-cron.sh            # Docker容器定时任务
├── docs/                     # GitHub Pages 静态网页查看器
├── custom_scripts/           # 辅助脚本
├── config/CRAWL_SCOPE.md            # 爬取范围记录
├── CHANGELOG.md              # 变更记录
├── AGENTS.md                 # 全局规则
├── HISTORY.md                # 对话历史
└── .github/workflows/
    ├── crawl-autohome.yml    # 汽车之家爬虫工作流
    ├── crawl-dongchedi.yml   # 懂车帝爬虫工作流
    ├── crawl-trigger.yml     # 随机触发器工作流
    ├── merge-and-filter.yml  # 合并过滤工作流
    ├── deploy-pages.yml      # 静态网页发布工作流
    ├── AI_Auto_Fix_Monitor.yml # AI自动修复监控工作流
    ├── ci.yml                # CI语法校验和冒烟测试
    └── auto-merge.yml        # PR自动合并
```

### 工作流调度（北京时间）
| 时间 | 任务 | 说明 |
|------|------|------|
| 每天 09:07-11:52 | 汽车之家 + 懂车帝爬虫 | 上午窗口，多次备用触发，动态缩短确保 12:30 前结束 |
| 每天 13:07-13:27 | 汽车之家 + 懂车帝爬虫 | 下午窗口，备用触发，约 5 小时 50 分钟 |
| 每天 20:30 | 合并数据 | 等待下午爬虫窗口结束后合并 |

### 半月跳过机制
- 每个爬虫在当月 1-15 日、16-月底两个周期内全量完成后，写入 `crawl_state/*_YYYYMM_H1.done` 或 `*_H2.done` 标记
- 同一周期后续自动触发直接跳过，进入新半月周期时自动重置对应爬虫进度

### 过滤条件
- 零百7秒内
- 纯电续航150KM以上
- 智驾领航支持城市路段
- 远程启动
- 远程控车
- 手机蓝牙/UWB钥匙
- 座椅记忆
- 后视镜记忆

---

## 2026-04-20：修复 Actions 工作流执行环境
- 修复了因为 `browser-actions/setup-chrome@master` 引发的 "File not found: index.js" 构建失败问题，将所有的版本引用由 `@master` 替换为稳定的 `@v2` 版本。
- 同样为了防止上游不兼容更新，将 `nanasess/setup-chromedriver` 从 `@master` 修改为了 `@v2`。

## 2026-05-28：修复 Release CSV 体积过小与过滤逻辑错误

### 问题现象
- Release 产出的 `merged_YYYYMMDD.csv` 文件异常偏小，基本只有表头或极少数据，无法反映完整车型数据。

### 根因定位
1. `scripts/merge_data.py` 中 `merged_YYYYMMDD.csv` 实际写入的是 `filtered_rows`，而不是 `all_rows`，导致文件只包含“满足高配筛选条件”的车型。
2. 过滤条件里 `纯电续航(km)` 使用了 `<= 150`，与需求“150km 以上”相反，进一步导致可入选车型数量异常减少。

### 修复内容
- 新增 `check_condition_gte()` 用于“数值 >= 阈值”判断。
- 将纯电续航条件改为使用 `>= 150`。
- 将 `merged_YYYYMMDD.csv` 改为输出全部合并数据（`all_rows`），并按全部数据动态收集字段。
- 保持 `filtered_cars_YYYYMMDD.csv/json` 继续输出筛选结果，不影响下游使用。

### 结果
- `merged_YYYYMMDD.csv` 恢复为“全量合并数据”，文件体积与记录数将显著增加并符合预期。
- 筛选逻辑与文档条件（纯电续航 150km 以上）一致。

## 2026-05-28：新增 CI 与 PR 自动合并工作流

### 用户诉求
- 希望不是“草稿PR”，而是有可执行的 CI 校验和可自动合并的 PR 流程。

### 本次新增
- 新增 `.github/workflows/ci.yml`
  - 在 `pull_request` 与 `push` 触发；
  - 执行依赖安装、`custom_scripts/validate_syntax.py` 语法校验、`scripts/merge_data.py` 冒烟运行。
- 新增 `.github/workflows/pr-auto-merge.yml`
  - 当 PR 打上 `automerge` 标签后，自动启用 GitHub 原生 Auto-merge（squash）。
  - 只有在必需检查（如 CI）通过后才会真正合并。

## 2026-05-28：监测 GitHub Actions 工作流运行状态

### 检查结果
- GitHub 远端 `Fatty911/crawl_cars` 与 `gh` 鉴权正常。
- 远端共有 7 个 active 工作流：`AI Auto Fix Monitor`、`PR 自动合并`、`CI`、`汽车之家爬虫`、`懂车帝爬虫`、`爬虫随机触发器`、`合并分析`。
- 最新 `CI` 运行成功，最新 `AI Auto Fix Monitor` 运行成功。
- `汽车之家爬虫` 与 `懂车帝爬虫` 仍在运行中；前者已进入 `Run step1 loop`，后者仍在 `Random delay`。
- 最新 `合并分析` 手动运行失败，原因是 `merged_20260528.json` 仅 13 行，低于工作流设置的 50 行发布阈值，触发“疑似爬虫数据不完整，拒绝发布”的保护。

### 本地状态提醒
- 本地工作区已有未提交改动，且 `.github/workflows/ci.yml` 当前包含合并冲突标记；这不是远端当前运行结果，但直接推送会导致 CI YAML 无效。

## 2026-05-28：修复 AI Auto Fix Monitor 频繁循环触发

### 问题现象
- `AI Auto Fix Monitor` 在几分钟内连续产生大量运行，异常消耗 GitHub Actions 资源。

### 根因定位
- 监控工作流在无法下载 `error-log`、也无法通过 `gh run view --log-failed` 获取失败日志时，仍因 `|| echo "AI 修复失败"` 返回成功。
- 后续 `Re-run failed workflow` 只判断步骤成功，于是把旧失败 run 重新执行；旧 run 使用原始 commit，即使后来有修复提交也不会生效，容易形成“失败 -> AI Monitor -> rerun -> 再失败”的循环。
- `scripts/auto_fix_workflow.py` 主程序没有根据修复结果设置退出码，导致“未修复”也可能被工作流误判为成功。

### 修复内容
- 为 `AI_Auto_Fix_Monitor.yml` 增加 `concurrency`，同一爬虫/分支的 AI 修复任务只保留一个活跃运行。
- 移除 AI 修复步骤的 `continue-on-error` 和吞错写法，拿不到日志或修复失败时直接失败退出。
- 移除自动 `gh run rerun`，避免重新运行旧 commit 上的失败 workflow。
- `scripts/auto_fix_workflow.py` 根据是否真正修复返回进程退出码。
- AI 修复脚本只有在产生实际文件改动、语法校验通过、提交和推送成功后才返回成功。
- 已取消当时仍在运行中的两个异常链路爬虫 run，停止继续触发循环。

## 2026-05-28：复查 GitHub Actions 运行状态

### 检查结果
- 7 个远端工作流均为 active。
- 当前没有正在运行的 workflow。
- `Stop AI auto-fix rerun loop` 推送触发的 `CI` 已成功。
- 最新 `懂车帝爬虫` 由 schedule 触发后失败，失败点为 `Verify Dongchedi output`：`dongchedi_20260528.json` 只有 0 行，触发“拒绝上传空/不完整 artifact”的保护。
- 最新 `AI Auto Fix Monitor` 被该爬虫失败触发了一次，但因拿不到 `error-log` 且 `gh run view --log-failed` 失败，按新逻辑直接 failure 退出；没有再自动 rerun 原失败工作流，循环已停止。

## 2026-05-28：修复懂车帝爬虫 0 行输出

### 根因
- `dongchedi/progress.json` 中 `crawled_series` 已记录 4632 个车系完成，但 `dongchedi/json/*.html` 是被 `.gitignore` 忽略的临时缓存，新的 GitHub Actions runner checkout 后没有这些 HTML 文件。
- step2 只根据 `progress.json` 判断完成，导致没有重新下载 HTML；step3 无页面可解析，最终生成 0 行 `dongchedi_YYYYMMDD.json`。

### 修复
- `crawl_dongchedi.py` 新增 HTML 缓存一致性检查：只有当前工作区真实存在且非空的 `dongchedi/json/{series_id}.html` 才算已爬取。
- step2 启动时会自动丢弃缺少 HTML 的旧 `crawled_series` 记录，避免被仓库里持久化的旧进度误导。
- step3/step4 若解析结果为 0 行，直接失败退出，拒绝生成空结果。
- Selenium 改为在 step2 需要浏览器时懒加载，使 step3/step4 可在无 Selenium 环境下独立运行解析校验。
