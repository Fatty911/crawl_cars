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
- 新增 `crawl_zero_to_whole_ratio.py`，可抓取中保研/中保协/中汽修协公开发布的汽车零整比 PDF/HTML，并兼容本地 `zero_to_whole_manual.csv/json` 补充数据。
- 默认从中国保险行业协会/中国汽车维修行业协会公开 PDF 抽取零整比，当前本地验证可从两个 PDF 抽取 291 条来源记录。
- `merge_data.py` 新增零整比 enrichment：按车型名称、车系和包含关系匹配；同一车型匹配到多个来源时计算平均 `零整比`，并保留 `零整比来源明细` 与 `零整比匹配方式`。
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
- 将仓库根目录与 `ai_tools/opencode/` 下的 `opencode.json`、`oh-my-openagent.json` 同步为全局 OpenCode 最新配置。
- 移除 `opencode.json` 中不受支持的 `disabled_providers` 字段，继续依赖自定义 Provider + whitelist 控制可见模型。
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
- `AI_Auto_Fix_Monitor.yml` 在 `auto_fix_workflow.py` 未产出可用修复时记录为跳过并正常结束，不再把 Provider 不可用、无权限或额度耗尽变成监控工作流红叉。
- `auto_fix_workflow.py` 移除明显过时/不可用的默认模型，新增 AtomGit、NVIDIA NIM 等可靠默认 Provider，并支持 `XXXX_BASE_URL`、`XXXX_MODEL_LIST`、`XXXX_PROXY_URL`。
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
- `test_autohome.py` 的 SSL 错误重试逻辑改进：
  - 重试次数从 3 增加到 5
  - 请求超时从 15 秒增加到 20 秒
  - 退避策略改为 `min(2^(attempt+2), 20)` 秒（4/8/16/20/20）
  - 最差耗时约 148 秒，比原方案 210 秒减少 30%

### 修改18: 修复汽车之家爬虫 SSL 错误
- `test_autohome.py` 的 `download_car_pages()` 函数中，字母列表页请求 `session.get()` 添加 SSL/Connection 错误重试
- 捕获 `requests.exceptions.SSLError` 和 `requests.exceptions.ConnectionError`
- 使用指数退避策略（2/4/8秒），最多重试 3 次
- 解决 mihomo 代理节点 SSL 握手失败导致爬虫崩溃的问题

### 修改17: 更新订阅抓取 User-Agent
- `generate_clash_config.py` 默认订阅抓取 UA 改为 `mihomo/1.19.13`
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
- 新增 `.github/workflows/ci.yml`，在 push、pull_request 和手动触发时运行 Python 语法检查与 `merge_data.py` 冒烟测试。
- 新增 `.github/workflows/auto-merge.yml`，给非草稿 PR 添加 `automerge` 标签后启用 GitHub 原生自动合并。
- 自动合并使用 squash merge，并在合并后删除源分支。
- 修复 `merge_data.py` 过滤逻辑未识别归一化后的 `蓝牙/数字钥匙` 字段，避免符合条件车型被误过滤。

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
- 为 test_autohome.py 添加命令行参数支持：
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
