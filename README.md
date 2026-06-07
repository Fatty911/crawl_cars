# 汽车配置数据爬虫项目

## 项目概述

自动爬取汽车之家和懂车帝的车型配置数据，过滤出符合高配条件的车型，并生成数据文件供Release使用。

## 目录结构

```
crawl_cars/
├── test_autohome.py          # 汽车之家爬虫脚本
├── crawl_dongchedi.py        # 懂车帝爬虫脚本
├── merge_data.py             # 数据合并与过滤脚本
├── proxy_manager.py          # 代理管理器
├── run_with_proxy.py         # 带代理的启动脚本
├── generate_clash_config.py  # Clash/Mihomo 配置生成器
├── auto_fix_workflow.py      # 大模型自动修复工作流错误
├── fix_files.py              # 代码修复工具
├── docs/                     # GitHub Pages 静态网页表格查看器
│   ├── index.html            # 页面结构
│   ├── styles.css            # 表格工作台样式
│   ├── app.js                # 数据加载、搜索、筛选、排序、分页、导出逻辑
│   ├── CNAME                 # GitHub Pages 自定义域名
│   └── data/                 # 发布时自动生成的数据目录
├── custom_scripts/           # 工作流校验、失败分类、进度同步等辅助脚本
│   ├── classify_crawl_failure.py  # 爬虫失败分类
│   ├── git_sync_progress.sh       # 进度同步脚本
│   ├── reset_dongchedi_progress.py # 懂车帝进度重置
│   ├── setup_proxy_runtime.py     # 代理运行时配置
│   └── validate_syntax.py         # 语法校验
├── crawl_state/              # 半月爬取完成标记目录
├── CRAWL_SCOPE.md            # 爬取车型范围与排除类型记录
├── deploy_vps.sh             # VPS 一键部署脚本
├── start_with_clash.sh       # 带 Clash 代理的启动脚本
├── VPS_DEPLOY.md             # VPS 部署指南
├── DOCKER_DEPLOY.md          # Docker 部署指南
├── CHANGELOG.md              # 变更记录
├── HISTORY.md                # 对话历史总结
├── AGENTS.md                 # AI Agent 全局规则
├── .gitignore                # Git 忽略配置
├── .github/workflows/
│   ├── crawl-autohome.yml    # 汽车之家爬虫工作流
│   ├── crawl-dongchedi.yml   # 懂车帝爬虫工作流
│   ├── crawl-trigger.yml     # 随机触发器工作流
│   ├── merge-and-filter.yml  # 合并过滤、Release、GitHub Pages 发布工作流
│   ├── deploy-pages.yml      # 静态网页独立发布工作流
│   ├── AI_Auto_Fix_Monitor.yml # AI 自动修复监控工作流
│   ├── ci.yml                # CI 语法校验和冒烟测试
│   └── auto-merge.yml        # PR 自动合并
├── docker-compose.yaml       # Docker Compose 配置
├── Dockerfile                # Docker 镜像构建
├── docker-cron.sh            # Docker 容器定时任务
└── README.md                 # 本文件
```

---

## 文件详解

### 1. test_autohome.py

**功能**：爬取汽车之家的车型配置数据，共6个步骤

**核心变量**：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `working_dir` | 脚本所在目录 | 当前文件目录 |
| `html_dir` | 存储下载的车型HTML页面 | `html/` |
| `newhtml_dir` | 存储解析后的JS拼装HTML | `newhtml/` |
| `json_dir` | 存储提取的JSON数据 | `json/` |
| `content_dir` | 存储浏览器执行后的内容 | `content/` |
| `newjson_dir` | 存储最终处理后的JSON | `newjson/` |
| `exception_dir` | 存储解析异常记录 | `exception/` |
| `progress_file` | 进度记录文件 | `progress.json` |
| `CURRENT_YEAR` | 当前年份 | 2026 |
| `MIN_YEAR` | 最小年份限制，0=所有车型 | 0 |
| `EV_RANGE_KEYWORDS` | 纯电续航字段关键词 | ['纯电续航', 'CLTC纯电续航', 'NEDC纯电续航'] |
| `HEAT_PUMP_KEYWORDS` | 热泵空调字段关键词 | ['热泵'] |
| `FUEL_TYPE_KEYWORDS` | 燃油类型字段关键词 | ['燃油类型', '燃料类型', '燃料形式', '能源类型'] |
| `LEVEL_FIELD_KEYWORDS` | 车型级别/车身结构字段关键词 | ['级别', '车身结构', ...] |
| `MAX_TIME_PER_STEP` | 每步最大运行秒数 | 命令行参数 |
| `MAX_CARS_PER_RUN` | 每轮最多下载车型数 | 命令行参数 |
| `AUTO_MODE` | 自动模式，未完成返回exit code 10 | 命令行参数 |

**命令行参数**：

| 参数 | 说明 | 示例 |
|------|------|------|
| `--step N` | 运行指定步骤(1-6) | `--step 1` |
| `--time-limit N` | 每步最大运行秒数，0=不限制 | `--time-limit 7200` |
| `--max-cars N` | 第一步最多下载车型数 | `--max-cars 500` |
| `--auto` | 自动模式：未完成则exit code 10 | `--auto` |
| `--restart` | 重置进度，从头开始 | `--restart` |

**步骤说明**：

| 步骤 | 函数名 | 功能 | 耗时 |
|------|--------|------|------|
| 1 | `download_car_pages()` | 按字母(A-Z)下载车型页面 | 最长 |
| 2 | `parse_js_to_html()` | 解析JS拼装HTML | 短 |
| 3 | `parse_json_data()` | 提取JSON数据 | 短 |
| 4 | `crack_html_files()` | 浏览器执行JS获取内容 | 中等 |
| 5 | `generate_data_files()` | 匹配样式与JSON | 短 |
| 6 | `generate_csv()` | 生成CSV/JSON输出 | 短 |

**输出文件**：`autoHome_YYYYMMDD.json` (只保留轿车、跑车、SUV，排除 MPV、房车和各类货车/商用车)

**进度记录** (progress.json)：

| 字段 | 说明 |
|------|------|
| `download_car_pages` | 已完成的字母列表，如 ["A", "B", "C"] |
| `cars_downloaded` | 已下载的车型总数 |
| `current_letter` | 当前正在爬取的字母 |
| `current_car_idx` | 当前字母内的车型索引 |
| `parse_js_to_html` | 已解析的文件列表 |
| `parse_json_data` | 已提取JSON的文件列表 |
| `crack_html_files` | 已执行JS的文件列表 |
| `generate_data_files` | 已生成数据的文件列表 |

---

### 2. crawl_dongchedi.py

**功能**：爬取懂车帝的车型配置数据，共4个步骤

**核心变量**：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `working_dir` | 脚本所在目录 | 当前文件目录 |
| `dcd_dir` | 懂车帝数据存储目录 | `dongchedi/` |
| `dcd_json_dir` | 懂车帝JSON存储目录 | `dongchedi/json/` |
| `dcd_exception_dir` | 懂车帝异常记录目录 | `dongchedi/exception/` |
| `progress_file` | 进度记录文件 | `dongchedi/progress.json` |
| `MIN_YEAR` | 最小年份限制，0=所有车型 | 0 |
| `EV_RANGE_KEYWORDS` | 纯电续航字段关键词 | ['纯电续航', 'CLTC纯电续航', 'NEDC纯电续航'] |
| `HEAT_PUMP_KEYWORDS` | 热泵空调字段关键词 | ['热泵'] |
| `FUEL_TYPE_KEYWORDS` | 燃油类型字段关键词 | ['燃油类型', '燃料类型', '燃料形式', '能源类型'] |
| `MAX_TIME_PER_STEP` | 每步最大运行秒数 | 命令行参数 |
| `MAX_SERIES_PER_RUN` | 每轮最多爬取车系数 | 命令行参数 |
| `AUTO_MODE` | 自动模式，未完成返回exit code 10 | 命令行参数 |
| `DCD_PAGE_LOAD_TIMEOUT` | Selenium 页面加载超时秒数，避免单页卡住 | 60 |

**命令行参数**：

| 参数 | 说明 | 示例 |
|------|------|------|
| `--step N` | 运行指定步骤(1-4) | `--step 2` |
| `--time-limit N` | 每步最大运行秒数，0=不限制 | `--time-limit 7200` |
| `--max-series N` | 第二步最多爬取车系数 | `--max-series 500` |
| `--auto` | 自动模式：未完成则exit code 10 | `--auto` |
| `--restart` | 重置进度，从头开始 | `--restart` |

**步骤说明**：

| 步骤 | 函数名 | 功能 | 耗时 |
|------|--------|------|------|
| 1 | `get_series_list()` | 获取所有车系列表 | 短 |
| 2 | `crawl_series_config()` | 爬取车系配置页面 | 最长 |
| 3 | `parse_config_pages()` | 解析配置页面提取数据 | 中等 |
| 4 | `generate_output()` | 生成CSV/JSON输出 | 短 |

**输出文件**：`dongchedi_YYYYMMDD.json`

**进度记录** (dongchedi/progress.json)：

| 字段 | 说明 |
|------|------|
| `series_list` | 车系列表 [{id, name, brand}, ...] |
| `excluded_series` | 列表阶段可明确识别并跳过的非目标车系 |
| `processed_brands` | 已处理品牌列表 |
| `crawled_series` | 已爬取的车系ID列表 |

---

### 3. merge_data.py

**功能**：合并两个数据源，过滤符合条件的车型

**核心常量**：

| 常量名 | 说明 |
|--------|------|
| `HEADER_MAP` | 字段名映射表，统一不同数据源的字段名 |
| `FIXED` | 固定字段列表 ['车系ID', '车型名称', '年款'] |
| `FILTER_CONDITIONS` | 过滤条件配置 |

**过滤条件 (FILTER_CONDITIONS)**：

| 条件名 | 字段 | 阈值/值 |
|--------|------|---------|
| `zero_to_hundred` | 百公里加速(s) | ≤7.0秒 |
| `ev_range` | 纯电续航(km) | ≥150km |
| `city_navigation` | NOA城市领航等 | 存在任一字段 |
| `remote_start` | 远程启动等 | 存在任一字段 |
| `remote_control` | 远程控制等 | 存在任一字段 |
| `bluetooth_key` | 蓝牙/数字/UWB钥匙 | 存在任一字段 |
| `seat_memory` | 座椅记忆 | 存在任一字段 |
| `mirror_memory` | 后视镜记忆 | 存在任一字段 |

**函数**：

| 函数名 | 功能 |
|--------|------|
| `norm()` | 标准化字段名 |
| `find_latest()` | 查找最新数据文件 |
| `load()` | 加载JSON文件 |
| `norm_rows()` | 规范化数据行 |
| `diff()` | 对比两个数据源差异 |
| `parse_number()` | 解析数值 |
| `check_condition()` | 检查单条件 |
| `check_multi_values()` | 检查多值条件 |
| `filter_car()` | 过滤符合条件的车型 |

**输出文件**：

| 文件名 | 内容 |
|--------|------|
| `merged_YYYYMMDD.csv` | 全部合并数据 |
| `merged_YYYYMMDD.json` | 全部合并数据 |
| `filtered_cars_YYYYMMDD.csv` | 符合条件车型 |
| `filtered_cars_YYYYMMDD.json` | 符合条件车型 |
| `diff_YYYYMMDD.csv` | 数据源差异 |

---

### 4. docs/

**功能**：GitHub Pages 静态网页表格查看器，用浏览器像 Excel 一样查看车型配置。

**文件**：

| 文件 | 说明 |
|------|------|
| `docs/index.html` | 页面结构 |
| `docs/styles.css` | 表格工作台样式 |
| `docs/app.js` | 数据加载、搜索、筛选、排序、分页、导出逻辑 |

**数据来源**：
- 合并工作流成功后，会把 `merged_YYYYMMDD.json` 复制为 `data/latest.json`。
- 会把 `filtered_cars_YYYYMMDD.json` 复制为 `data/filtered.json`。
- 同时生成 `data/manifest.json`，记录数据日期、行数和 CSV/JSON 下载链接。

**主要功能**：
- 全局搜索品牌、车系、车型名称和任意配置值。
- 点击表头按列升序/降序排序。
- 表头第二行支持每列关键字筛选。
- 支持按数据来源、品牌、车系快速筛选。
- 默认打开“符合条件”数据集，并支持切换“全部车型”和“符合条件”。
- 网页展示时会把 `长宽高` / `长*宽*高(mm)` / `车身尺寸` 这类合并字段拆成 `长度(mm)`、`宽度(mm)`、`高度(mm)` 三列。
- 支持选择显示列、分页查看、导出当前筛选结果为 CSV/JSON。

---

### 5. fix_files.py

**功能**：代码修复工具，用于修复test_autohome.py中的缩进问题

---

### 6. generate_clash_config.py

**功能**：Clash/Mihomo 配置生成器，从订阅链接生成 Clash 配置文件

**核心特性**：
- 支持 VMess、VLESS、Trojan、SS、Hysteria2、TUIC、WireGuard 等协议
- 自动下载并启动 mihomo 本地代理
- 订阅地址脱敏日志，避免泄露 token
- 支持通过 `PROXY_SUBSCRIPTION_USER_AGENT` 环境变量覆盖默认 UA

---

### 7. auto_fix_workflow.py

**功能**：通用多Provider工作流错误自动修复系统（Lobe-Chat 风格配置）

**核心规则**：
- `XXXX_API_KEY` 存在 → 尝试启用该 Provider
- `XXXX_BASE_URL` **非必填**：用于覆盖或补充 OpenAI-compatible API 地址；没有内置地址的 Provider 必须显式配置
- `XXXX_MODEL_LIST` **非必填**：
  - 未配置 → 只使用仓库内置且已确认的默认模型
  - 已配置 → 使用显式配置的模型列表
- `XXXX_PROXY_URL` **非必填**：该 Provider 的请求走指定 HTTP/HTTPS 代理
- 未读取到 `XXXX_MODEL_LIST` 时**不报错**；没有可靠默认模型的 Provider 会跳过，避免无意义调用不存在或无权限模型

**支持的 Provider**（按环境变量自动发现）：

| 环境变量前缀 | Provider | base_url |
|-------------|----------|----------|
| `OPENROUTER` | OpenRouter | openrouter.ai |
| `OPENAI` | OpenAI | api.openai.com |
| `XAI` | xAI | api.x.ai |
| `ATOMGIT` | AtomGit | api-ai.gitcode.com |
| `MINIMAX` | MiniMax | api.minimax.io |
| `MINIMAX_CODING_PLAN` | MiniMax Coding Plan | api.minimax.io |
| `ZEN` | OpenCode Zen | 需配置 `ZEN_BASE_URL` |
| `NVIDIA_NIM` | NVIDIA NIM | integrate.api.nvidia.com |
| `MOONSHOT` | Moonshot/Kimi | api.moonshot.cn |
| `DEEPSEEK` | DeepSeek | api.deepseek.com |
| `MODELSCOPE` | ModelScope | 需配置 `MODELSCOPE_BASE_URL` |
| `MODAL` | Modal | 需配置 `MODAL_BASE_URL` |

**使用方式**：

```bash
# 手动运行
python auto_fix_workflow.py error.log test_autohome.py

# 在 workflow 中自动调用（已集成）
```

**触发前分类**：
- 爬虫日志出现 `exit code 10`、达到时间/数量上限、保存进度继续下次、已处理数百条等主动分段退出特征时，跳过大模型修复。
- 完整工作流日志或爬虫日志出现 git push/rebase 冲突、非快进、权限拒绝、Runner/浏览器临时异常等基础设施问题时，跳过大模型修复。
- 日志显示输出行数过少、少量车型 `无法解析config或option`、拒绝上传/合并等数据质量保护时，跳过大模型修复，避免把正常保护机制误判为代码需要改。
- 日志显示 AI Provider 自身 SSL、401、403、证书或网络异常时，跳过再次自动修复，避免监控工作流围绕自动修复失败产生噪音。
- 只有日志显示未生成数据、完全解析不到车型数据、配置页/接口致命异常等站点结构或链接异常时，才调用大模型修复。
- `AI_Auto_Fix_Monitor.yml` 会优先抓取完整失败日志，再结合 error-log artifact 分类，避免只看 step 日志造成误判。
- `auto_fix_workflow.py` 未能产出可用修复时，监控工作流记录为跳过并正常结束；只有真正生成改动、语法校验通过、提交并推送成功后才标记 `fixed=true`。
- 分类逻辑位于 `custom_scripts/classify_crawl_failure.py`，两个爬虫 workflow 和 `AI_Auto_Fix_Monitor.yml` 都会调用。

**当前已配置的 GitHub Secrets**：

`ACTION_PAT`、`ATOMGIT_API_KEY`、`MINIMAX_API_KEY`、`MINIMAX_CODING_PLAN_API_KEY`、`MODAL_API_KEY`、`MODELSCOPE_API_KEY`、`MOONSHOT_API_KEY`、`NVIDIA_NIM_API_KEY`、`OPENROUTER_API_KEY`、`PROXY_SUBSCRIPTIONS`、`XAI_API_KEY`、`ZEN_API_KEY`

**工作原理**：
1. 自动发现所有 `_API_KEY` 环境变量
2. 解析对应 `BASE_URL`、`MODEL_LIST`、`PROXY_URL`；没有可用 base_url 或模型的 Provider 会跳过
3. 依次尝试各 Provider 的模型，生成修复方案
4. 置信度 ≥ 0.6 时自动应用修复并提交推送

---

### 8. .github/workflows/

**功能**：GitHub Actions 自动化工作流

**工作流文件**：

| 文件 | 功能 |
|------|------|
| `crawl-autohome.yml` | 汽车之家爬虫，上午/下午两个运行窗口 |
| `crawl-dongchedi.yml` | 懂车帝爬虫，上午/下午两个运行窗口 |
| `crawl-trigger.yml` | 随机触发器，仅在指定时间窗口触发目标爬虫 |
| `merge-and-filter.yml` | 合并过滤、Release、GitHub Pages 发布 |
| `deploy-pages.yml` | 静态网页独立发布 |
| `AI_Auto_Fix_Monitor.yml` | AI 自动修复监控 |
| `ci.yml` | CI 语法校验和冒烟测试 |
| `auto-merge.yml` | PR 自动合并（squash） |

**环境变量**：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `RUN_TIME` | 每轮运行最大秒数；上午窗口为 10800，下午窗口为 21000 | 10800 |
| `MAX_CARS` | 每轮最多爬取车型/车系数；0 表示不按数量截断 | 0 |
| `MORNING_RUN_TIME` | 上午窗口运行秒数 | 10800 |
| `AFTERNOON_RUN_TIME` | 下午窗口目标运行秒数；step2 会按 workflow 已耗时再次缩短 | 21000 |
| `MAX_WORKFLOW_SECONDS` | 单次 workflow 按 GitHub 6 小时硬限制计算的总秒数 | 21600 |
| `PROGRESS_COMMIT_BUFFER_SECONDS` | step2 结束后提交进度预留秒数 | 1800 |
| `CRAWL_MIN_DELAY_SECONDS` | 两次访问之间最小等待秒数 | 3 |
| `CRAWL_MAX_DELAY_SECONDS` | 两次访问之间最大等待秒数 | 8 |

**Job结构**（crawl-autohome.yml / crawl-dongchedi.yml）：

| Job名 | 功能 | 超时 | 依赖 |
|-------|------|------|------|
| `crawl-autohome` | 爬取汽车之家 | 390分钟 | 无 |
| `crawl-dongchedi` | 爬取懂车帝 | 390分钟 | 无 |
| `merge-and-filter` | 合并过滤、Release、发布 GitHub Pages | 10/30/15分钟 | 爬虫 artifact |

**触发条件**（crawl-autohome.yml / crawl-dongchedi.yml）：
- 汽车之家、懂车帝：每天 UTC 01:07-03:52（北京时间 09:07-11:52）多次备用触发上午窗口，约 3 小时
- 汽车之家、懂车帝：每天 UTC 05:07/05:17/05:27（北京时间 13:07/13:17/13:27）备用触发下午窗口，约 5 小时 50 分钟
- 合并分析：每天 UTC 12:30（北京时间 20:30），等待下午爬虫窗口结束后再合并；如果两份爬虫数据尚未完整生成，会成功跳过且不发布不完整数据
- 随机触发器只在北京时间 09:00-12:30 或 13:00-13:30 触发爬虫
- 手动触发 (workflow_dispatch)

**自动运行逻辑**：
1. 上午窗口不做随机启动延迟；下午窗口随机延迟 0-10 分钟但会封顶到 13:30 前；外部随机触发最多补足到30分钟，并会封顶在当前运行窗口结束前
2. 爬取循环：
   - 按当前运行窗口运行指定时长
   - 未完成：commit进度 → pull --rebase + push 重试同步 → 正常结束本次 workflow，等待下一次备用触发/下一天继续
   - 完成：生成数据并写入当前半月的 `crawl_state/*_YYYYMM_H1.done` 或 `crawl_state/*_YYYYMM_H2.done` 标记
3. 每个主爬虫 workflow 按上午/下午窗口分别加并发锁：同一窗口备用触发不会并发重复爬，但上午不会阻塞下午
4. 同一个半月周期内如果已完成全量爬取，后续自动触发会直接跳过；进入新半月周期时自动重置对应爬虫进度
5. 如果 GitHub Actions schedule 被延迟到北京时间 12:30 以后或 13:30 以后，工作流会直接跳过，不在傍晚补跑
6. 进度提交通过 `custom_scripts/git_sync_progress.sh` 同步；若多个 workflow 同时更新 `progress.json` / `dongchedi/progress.json`，会合并 JSON 进度，避免远端覆盖本地已爬进度
7. 懂车帝重置进度时会保留车系列表缓存，接口短暂返回非 JSON 或空响应时可回退继续爬取
8. 每两次网络访问之间默认等待3-8秒，模拟人工浏览动作速率

**车型范围**：当前只保留轿车、跑车、SUV；MPV、房车、皮卡、微面、轻客、货车、卡车等会被排除。详见 `CRAWL_SCOPE.md`。

---

## 代理配置

### 为什么需要代理

- 避免IP被封
- 分散请求来源
- 提高爬取成功率

### 代理管理器 (proxy_manager.py)

**功能**：
- ✅ 支持多个机场订阅URL
- ✅ 排除特定关键字节点
- ✅ 解析 V2Ray/Clash 订阅
- ✅ 手动添加 HTTP/SOCKS5 代理
- ✅ 负载均衡策略
- ✅ 节点统计与筛选

**订阅管理**：
```bash
# 添加订阅
python proxy_manager.py --add-sub "https://订阅1"
python proxy_manager.py --add-sub "https://订阅2"

# 列出所有订阅
python proxy_manager.py --list-subs

# 刷新所有订阅
python proxy_manager.py --refresh
```

**排除关键字**：
```bash
# 添加排除关键字（逗号分隔）
python proxy_manager.py --exclude "过期,测试,expire,test"

# 列出排除关键字
python proxy_manager.py --list-exclude

# 移除排除关键字
python proxy_manager.py --remove-exclude "test"
```

**手动添加代理**：
```bash
# HTTP代理
python proxy_manager.py --add-http "节点1" "proxy.example.com" "8080" "user:pass"

# SOCKS5代理
python proxy_manager.py --add-socks5 "节点2" "127.0.0.1" "1080" ""
```

**查看和测试**：
```bash
# 查看统计
python proxy_manager.py --stats

# 列出代理
python proxy_manager.py --list

# 测试前5个代理
python proxy_manager.py --test 5

# 清空所有代理
python proxy_manager.py --clear
```

**配置文件** (proxies.json)：
```json
{
  "proxies": [],
  "stats": {},
  "exclude_keywords": ["过期", "测试", "expire"],
  "subscriptions": [
    "https://订阅1",
    "https://订阅2"
  ]
}
```

**负载均衡策略**：
- `random`: 随机选择
- `round_robin`: 轮询
- `least_used`: 最少使用
- `best_performance`: 最佳性能

**注意**：
- SS/VMess/Trojan 需要本地客户端转为 HTTP
- 推荐使用 Clash/V2Ray 监听本地端口
- 或直接购买 HTTP/SOCKS5 代理

---

## 数据字段映射 (HEADER_MAP)

汽车之家和懂车帝同一配置项的字段名不同，已在merge_data.py中统一：

| 汽车之家 | 懂车帝 | 统一后 |
|----------|--------|--------|
| 全速自适应巡航控制_ACC_ | 自适应巡航 | 全速自适应巡航 |
| NOA城市路段 | 城市辅助驾驶 | NOA城市领航 |
| 官方0-100km_h加速_s_ | 百公里加速时间 | 百公里加速(s) |
| 远程启动功能 | 远程启动 | 远程启动 |
| 蓝牙钥匙/NFC钥匙/UWB钥匙 | 数字钥匙 | 蓝牙/数字钥匙 |
| CLTC纯电续航/NEDC纯电续航 | 纯电续航 | 纯电续航(km) |

---

## 部署方案

### Docker 部署 (推荐)

**优势**：
- ✅ 完全隔离，不影响主机
- ✅ 一键部署
- ✅ 数据持久化
- ✅ 环境一致

**快速开始**：
```bash
# 克隆代码
git clone https://github.com/Fatty911/crawl_cars.git
cd crawl_cars

# 创建目录
mkdir -p data html json output dongchedi

# 构建并启动
docker compose up -d crawl-cron

# 查看日志
docker compose logs -f crawl-cron
```

**详细文档**：见 [DOCKER_DEPLOY.md](DOCKER_DEPLOY.md)

### GitHub Actions (有限使用)

**限制**：免费版每月 2000 分钟

**当前配置**（按最长运行时长估算，实际会因半月完成标记提前跳过）：

| 爬虫 | 定时 | 次数/月 | 分钟数 |
|------|------|---------|--------|
| 汽车之家 | 上午 UTC 01:07-03:52 多次备用触发；下午 UTC 05:07/05:17/05:27 | 备用触发较多但有并发锁 | 半月全量完成后跳过 |
| 懂车帝 | 上午 UTC 01:07-03:52 多次备用触发；下午 UTC 05:07/05:17/05:27 | 备用触发较多但有并发锁 | 半月全量完成后跳过 |
| 合并 | 每天 UTC 12:30（北京时间 20:30） | 30 | <300 |

**半月跳过**：每个爬虫在当月 1-15 日、16-月底两个周期内全量完成后，会写入 `crawl_state/` 完成标记；同一周期后续自动触发直接跳过，不再重复爬。

**合并保护**：合并分析只在汽车之家和懂车帝两份数据都存在且各不少于 50 行时发布 Release/Pages；定时运行遇到数据未就绪会成功跳过，手动 `force_merge=true` 仍会按失败处理。

**随机延迟**：上午不做启动随机延迟；下午随机等待 0-10 分钟但封顶到北京时间 13:30 前；两次网络访问之间默认等待 3-8 秒，可通过 `CRAWL_MIN_DELAY_SECONDS` / `CRAWL_MAX_DELAY_SECONDS` 调整。

**分段续爬**：爬虫脚本返回 `exit code 10` 时表示本次时间预算用完但还没全量完成。workflow 会提交进度并正常结束本次运行，不会在同一个 job 内再次重启长步骤，避免实际运行时间超过上午/下午窗口。懂车帝 step2 会在启动前按 workflow 已耗时重新缩短 `RUN_TIME`，并预留提交缓冲，防止 GitHub 6 小时硬超时直接取消导致进度无法推送。

**手动触发**：在 Actions 页面点击 "Run workflow"

### GitHub Pages 网页查看器

**用途**：免费托管静态网页，直接在浏览器中筛选、排序、分页查看车型配置，不再只依赖下载 Release 表格文件。

**发布方式**：
1. `deploy-pages.yml` 可独立发布 `docs/` 网页，并自动使用最近一份带 `merged_*.json` 的 Release 数据。
2. `merge-and-filter.yml` 在合并数据通过完整性检查后，也会把 `docs/` 静态页面和最新 JSON/CSV 打包为 Pages artifact；这条链路仍会拒绝发布明显不完整的数据。
3. 两个工作流都使用 GitHub 官方 `actions/upload-pages-artifact` 与 `actions/deploy-pages` 发布。

**首次启用**：
- 在仓库 **Settings → Pages → Build and deployment** 中选择 **GitHub Actions**。
- 之后每次“合并分析”工作流成功，网页会自动更新到最新数据。
- 自定义域名已预置为 `cars.jiucai.eu.org`，发布产物会包含 `docs/CNAME`。

**本地预览**：

```bash
python -m http.server 8000 -d docs
```

然后访问 `http://localhost:8000`。本地没有 `docs/data/manifest.json` 时会显示内置示例数据；GitHub Pages 发布后会自动加载最新合并数据。

### VPS 部署 (推荐)

**优势**：
- 无时长限制
- 完全可控
- 支持代理
- 性价比高 ($3-5/月)

**一键部署**：
```bash
curl -fsSL https://raw.githubusercontent.com/Fatty911/crawl_cars/main/deploy_vps.sh | bash
```

**详细文档**：见 [VPS_DEPLOY.md](VPS_DEPLOY.md)

### Railway 部署

**费用**：
- Free: 30天试用，$5一次性额度（之后$1/月）
- Hobby: $5/月最低消费（包含$5额度）

**估算**：每月16次×2小时 ≈ $1.28（额度够用）

**部署**：
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

---

## 运行流程

### 本地运行

```bash
# 1. 安装依赖
pip install requests beautifulsoup4 selenium lxml

# 2. 运行汽车之家爬虫（完整流程）
python test_autohome.py

# 3. 运行懂车帝爬虫（完整流程）
python crawl_dongchedi.py

# 4. 合并并过滤数据
python merge_data.py
```

### 分步运行

```bash
# 汽车之家 - 只爬取第一步（最多6小时，400个车型）
python test_autohome.py --step 1 --time-limit 21600 --max-cars 400 --auto

# 汽车之家 - 从断点继续
python test_autohome.py --step 1 --auto

# 汽车之家 - 后续步骤
python test_autohome.py --step 2
python test_autohome.py --step 3
python test_autohome.py --step 4
python test_autohome.py --step 5
python test_autohome.py --step 6

# 懂车帝 - 只爬取第二步
python crawl_dongchedi.py --step 2 --time-limit 21600 --max-series 400 --auto
```

### GitHub Actions运行

**当前调度**（UTC时间）：
- 汽车之家：上午 01:07-03:52 多次备用触发（北京时间 09:07-11:52，约 3 小时）；下午 05:07/05:17/05:27 备用触发（北京时间 13:07-13:27，约 5 小时 50 分钟）
- 懂车帝：上午 01:07-03:52 多次备用触发（北京时间 09:07-11:52，约 3 小时）；下午 05:07/05:17/05:27 备用触发（北京时间 13:07-13:27，约 5 小时 50 分钟）
- 数据合并：每天 12:30（北京时间 20:30）
- 随机触发器：仅北京时间 09:00-12:00 或 13:00-13:30 触发目标爬虫

**代理配置（强烈推荐）**

在 **Repository Settings → Secrets and variables → Actions** 中添加以下变量：

| Secret 名称              | 说明                              | 示例格式 |
|-------------------------|-----------------------------------|----------|
| `PROXY_SUBSCRIPTIONS`   | 机场订阅地址（支持多条）           | JSON对象、JSON数组或每行一个URL |
| `OPENROUTER_API_KEY`    | 用于错误自动修复                   | sk-... |
| `MINIMAX_API_KEY`       | 用于错误自动修复                   | mm-... |
| `XAI_API_KEY`           | 用于错误自动修复                   | xai-... |

**`PROXY_SUBSCRIPTIONS` 格式示例**（支持VMess、VLESS、Trojan、Hysteria2等）：

推荐使用 JSON 对象；多个订阅地址在 `subscriptions` 数组里用英文逗号分隔：

```json
{
  "subscriptions": [
    "https://你的机场订阅地址1",
    "https://你的机场订阅地址2",
    "https://你的机场订阅地址3"
  ],
  "exclude_keywords": ["过期", "测试", "香港", "台湾", "到期"]
}
```

也支持简单写法：每行一个订阅地址，或用英文分号 `;`、竖线 `|` 分隔。不要用空格分隔 URL。

**代理工作原理**：
- 工作流启动时检测 `PROXY_SUBSCRIPTIONS`
- 有配置时会先拉取订阅、解析节点、生成 mihomo 配置并启动本地代理
- 只有本地代理连通性测试通过后才设置 `PROXY_ENABLED=true`，爬虫请求和 Chrome 都走 `http://127.0.0.1:7890`
- 没配置、订阅拉取失败、解析不到节点、或所有节点不可用时，自动降级为无代理直连，不影响流程
- workflow 不把订阅内容写入仓库目录，避免 `git add -A` 误提交订阅 token

---

## 对话历史记录

所有对话历史已合并为单一文件：

| 文件 | 说明 |
|------|------|
| [HISTORY.md](HISTORY.md) | 从 2026-02-22 到最新的完整对话历史总结 |

**HISTORY.md 包含内容**：
- 2026-02-22：项目初始化、爬虫逻辑、Action拆分
- 2026-02-26：断点续传、自动爬取、频率调整
- 2026-03-04：断点续传逻辑深度修复
- 2026-03-07：部署方案探索（VPS/Docker/Railway）、代理管理器
- 2026-03-29：公开仓库安全检查、代理支持、大模型自动修复功能
