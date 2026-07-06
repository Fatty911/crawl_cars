# 汽车配置数据爬虫项目

## 项目概述

自动爬取汽车之家和懂车帝的车型配置数据，补充中保研/中保协/中汽修协等公开发布的汽车零整比数据，过滤出符合高配条件的车型，并生成数据文件供 Release 和 GitHub Pages 使用。

## 目录结构

```
crawl_cars/
├── scripts/test_autohome.py          # 汽车之家爬虫脚本
├── crawl_dongchedi.py        # 懂车帝爬虫脚本
├── scripts/crawl_zero_to_whole_ratio.py # 零整比公开数据抓取脚本
├── scripts/merge_data.py             # 数据合并与过滤脚本
├── scripts/proxy_manager.py          # 代理管理器
├── scripts/run_with_proxy.py         # 带代理的启动脚本
├── scripts/generate_clash_config.py  # Clash/Mihomo 配置生成器
├── scripts/auto_fix_workflow.py      # 大模型自动修复工作流错误
├── scripts/fix_files.py              # 代码修复工具
├── docs/                     # GitHub Pages 静态网页表格查看器
│   ├── index.html            # 页面结构
│   ├── styles.css            # 表格工作台样式
│   ├── app.js                # 数据加载、搜索、筛选、排序、分页、导出逻辑
│   ├── config.js             # Pages 前端运行配置
│   ├── config/filter_conditions.json # 网页筛选条件配置副本
│   ├── CNAME                 # GitHub Pages 自定义域名
│   └── data/                 # 发布时自动生成的数据目录
├── config/filter_conditions.json    # 合并脚本和网页共用筛选条件
├── cloudflare/
│   └── filter-history-worker.js # Cloudflare Worker 筛选历史 API
├── wrangler.toml             # Cloudflare Worker 部署配置
├── custom_scripts/           # 工作流校验、失败分类、进度同步等辅助脚本
│   ├── classify_crawl_failure.py  # 爬虫失败分类
│   ├── check_workflow_expectations.py # workflow 成功/失败预期检查
│   ├── configure_cron_job_org.py  # 配置 cron-job.org 外部触发
│   ├── crawl_budget.py            # 计算北京时间窗口和 Actions 6 小时预算
│   ├── download_latest_crawler_artifact.py # 合并前扫描最近有效爬虫 artifact
│   ├── ensure_codex_autofix_scope.py  # Codex 自动修复文件范围检查
│   ├── git_sync_progress.sh       # 进度同步脚本
│   ├── reset_dongchedi_progress.py # 懂车帝进度重置
│   ├── setup_proxy_runtime.py     # 代理运行时配置
│   ├── validate_workflow_expectations.py # 爬虫调度与自修复静态校验
│   └── validate_syntax.py         # 语法校验
├── crawl_state/              # 半月爬取完成标记目录
├── config/CRAWL_SCOPE.md            # 爬取车型范围与排除类型记录
├── scripts/deploy_vps.sh             # VPS 一键部署脚本
├── scripts/start_with_clash.sh       # 带 Clash 代理的启动脚本
├── VPS_DEPLOY.md             # VPS 部署指南
├── DOCKER_DEPLOY.md          # Docker 部署指南
├── CHANGELOG.md              # 变更记录
├── HISTORY.md                # 对话历史总结
├── AGENTS.md                 # AI Agent 全局规则
├── .gitignore                # Git 忽略配置
├── .github/workflows/
│   ├── crawl-autohome.yml    # 汽车之家爬虫工作流
│   ├── crawl-dongchedi.yml   # 懂车帝爬虫工作流
│   ├── crawl-trigger.yml     # cron-job.org 外部触发器工作流
│   ├── merge-and-filter.yml  # 合并过滤、Release、GitHub Pages 发布工作流
│   ├── deploy-pages.yml      # 静态网页独立发布工作流
│   ├── AI_Auto_Fix_Monitor.yml # AI 自动修复监控工作流
│   ├── ci.yml                # CI 语法校验和冒烟测试
│   └── auto-merge.yml        # PR 自动合并
├── docker-compose.yaml       # Docker Compose 配置
├── Dockerfile                # Docker 镜像构建
├── scripts/docker-cron.sh            # Docker 容器定时任务
└── README.md                 # 本文件
```

---

## 文件详解

### 1. scripts/test_autohome.py

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

**环境变量（通过 GitHub Secrets 或运行环境配置，无需改代码）**：

| 环境变量名 | 说明 | 默认值 |
|-----------|------|--------|
| `BRAND_HEAT_ORDER` | 逗号分隔的品牌热度排行榜，按热度从高到低排列。用于决定爬取顺序，热门品牌优先 | 内置默认列表（含比亚迪/吉利/长安/特斯拉/理想/蔚来/问界/小米/小鹏等90+品牌） |
| `BRAND_NAME_MAP` | 品牌名标准化映射，格式 `汽车之家名:标准名,汽车之家名:标准名`。解决不同网站品牌名不一致 | 内置默认映射（长安→长安汽车, AITO问界→问界 等） |
| `SORT_CONFIG` | 多关键字排序配置，格式 `字段:asc\|desc,字段:asc\|desc,...`。类似 Excel 自定义排序 | `heat:asc,salecount:desc,series:asc` |
| `SALES_RANK_DATE` | 销量榜日期，格式 `YYYY-MM`（如 `2026-05`） | 自动获取最新可用月份 |
| `SALES_RANK_SUBRANKS` | 销量榜子榜ID，逗号分隔（1=销量榜,2=新能源,3=智测,4=关注,5=保值,6=降价,7=科技,8=实测） | `1,2,3,4,5,6,7,8` |

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
| `DCD_RENDERER_TIMEOUT_RESTART_THRESHOLD` | 连续 Chrome renderer 超时多少次后重启浏览器，0 表示不自动重启 | 3 |
| `DCD_NETWORK_ERROR_RESTART_THRESHOLD` | 连续 `net::ERR_CONNECTION_*` 这类导航网络异常多少次后重启浏览器，0 表示不自动重启 | 5 |

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

`dongchedi/json/*.html` 是 step2 的真实页面缓存，文件较大且不提交到 git；GitHub Actions 通过 `actions/cache` 按半月周期恢复该目录。`crawled_series` 只在对应 HTML 文件真实存在时才会被视为有效，避免进度记录存在但页面缓存丢失时生成空数据。

---

### 3. scripts/merge_data.py

**功能**：合并汽车之家、懂车帝和零整比数据源，过滤符合条件的车型

**核心常量**：

| 常量名 | 说明 |
|--------|------|
| `HEADER_MAP` | 字段名映射表，统一不同数据源的字段名 |
| `FIXED` | 固定字段列表 ['车系ID', '车型名称', '年款'] |
| `FILTER_CONFIG_PATH` | 筛选条件配置文件路径：`config/filter_conditions.json` |
| `ZERO_RATIO_FIELDS` | 零整比输出字段：`零整比`、`零整比来源明细`、`零整比匹配方式` |

**过滤条件 (`config/filter_conditions.json`)**：

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

修改筛选条件时优先改 `config/filter_conditions.json`；网页发布时会把该文件复制到站点根目录，前端条件栏和 `scripts/merge_data.py` 默认筛选共用同一份配置。

**函数**：

| 函数名 | 功能 |
|--------|------|
| `norm()` | 标准化字段名 |
| `find_latest()` | 查找最新数据文件 |
| `load()` | 加载JSON文件 |
| `norm_rows()` | 规范化数据行 |
| `load_zero_ratio_rows()` | 加载最新零整比 JSON |
| `enrich_zero_ratio()` | 按车型名/车系匹配零整比，多来源取平均 |
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

**零整比字段**：
- `零整比`：同一车型匹配到多个来源时取算术平均值，格式如 `330.50%`。
- `零整比来源明细`：列出每个来源、发布日期、来源车型和对应零整比，便于核对不同来源差异。
- `零整比匹配方式`：记录使用 `车型名称`、`车系` 或包含关系完成匹配。

---

### 4. scripts/crawl_zero_to_whole_ratio.py

**功能**：抓取汽车零整比公开发布数据，生成 `zero_to_whole_ratios_YYYYMMDD.json` 和 `zero_to_whole_ratios.json`。

**默认来源**：
- 中国保险行业协会/中国汽车维修行业协会公开 PDF（汽车零整比体系、汽车零整比 100 指数体系）。
- 中保研发布的零整比研究成果通常由中保协指导，很多新闻稿只摘要展示；可把能直接下载表格/PDF 的新 URL 加到配置里。

**可扩展来源**：
- 仓库根目录可新增 `zero_to_whole_sources.json`：

```json
{
  "sources": [
    {
      "source": "中保研第18期汽车零整比",
      "published_at": "2024-10",
      "url": "https://example.com/zero-ratio.pdf"
    }
  ]
}
```

- GitHub Actions 可通过 Repository Variable `ZERO_TO_WHOLE_RATIO_URLS` 追加来源，支持 JSON 数组、换行、英文分号或竖线分隔。
- 如果某个 PDF 是扫描版或表格抽取失败，可放置 `zero_to_whole_manual.csv` / `zero_to_whole_manual.json` 手工补充，字段使用 `数据来源`、`发布日期`、`品牌`、`车系`、`车型名称`、`零整比`。

**输出文件**：

| 文件名 | 内容 |
|--------|------|
| `zero_to_whole_ratios_YYYYMMDD.json` | 当日零整比来源明细 |
| `zero_to_whole_ratios.json` | 最新零整比来源明细 |

---

### 5. docs/

**功能**：GitHub Pages 静态网页表格查看器，用浏览器像 Excel 一样查看车型配置。

**文件**：

| 文件 | 说明 |
|------|------|
| `docs/index.html` | 页面结构 |
| `docs/styles.css` | 表格工作台样式 |
| `docs/app.js` | 数据加载、搜索、筛选、排序、分页、导出逻辑 |
| `docs/config.js` | 前端运行配置，默认优先使用 `Personal_commonly_used` 私有仓库内的历史文件，保留 `/api/filter-history` 作为 Worker 后端路径 |
| `docs/config/filter_conditions.json` | 网页筛选条件配置副本 |
| `config/filter_conditions.json` | 合并脚本和网页共用的筛选条件配置 |
| `cloudflare/filter-history-worker.js` | Cloudflare Worker 筛选历史 API |

**数据来源**：
- 合并工作流成功后，会把 `merged_YYYYMMDD.json` 复制为 `data/latest.json`。
- 会把 `filtered_cars_YYYYMMDD.json` 复制为 `data/filtered.json`。
- 会把 `zero_to_whole_ratios_YYYYMMDD.json` 复制为 `data/zero_to_whole_ratios.json`。
- 同时生成 `data/manifest.json`，记录数据日期、行数和 CSV/JSON 下载链接。

**主要功能**：
- 全局搜索品牌、车系、车型名称和任意配置值。
- 点击表头按列升序/降序排序。
- 表头第二行支持每列关键字筛选，并优化中文输入法输入期间的光标稳定性。
- 支持按品牌、车系快速筛选；网页不再提供数据来源筛选，改为展示 `交叉核验` 和 `核验来源`。
- 条件筛选栏由 `config/filter_conditions.json` 生成，支持功能勾选和数值范围筛选，不再把筛选条件写死在前端代码里。
- 筛选历史可通过同步码保存到服务端；当前默认使用私有仓库 `Fatty911/Personal_commonly_used` 的 `cars/filter-history/history.json`，浏览器端需要用户在本机保存具备该仓库 Contents 读写权限的 GitHub Token。
- 不填写 GitHub Token 时网页仍可匿名使用，筛选历史只保存在当前浏览器本机缓存中，不会读取或覆盖已填写 Token 的远端历史。
- 如果切回 Worker 后端，默认 API 路径为 `/api/filter-history`，需要 Cloudflare Worker 路由到该路径。
- 双源核验按归一化后的“车系 + 年款 + 车型名称”匹配，兼容汽车之家把车系/年款写在 `车型名称`、懂车帝拆分到 `车系` / `年款` 字段的格式差异。
- 网页展示时会把 `长宽高` / `长*宽*高(mm)` / `车身尺寸` 这类合并字段拆成 `长度(mm)`、`宽度(mm)`、`高度(mm)` 三列。
- 常用列包含 `零整比` 和 `零整比来源明细`；多个来源匹配同一车型时页面展示平均值，并保留来源明细。
- 支持选择显示列、分页查看、导出当前筛选结果为 CSV/JSON。

**筛选历史后端**：

当前 Pages 前端默认配置：

```js
window.CARS_FILTER_HISTORY_PROVIDER = "github";
window.CARS_GITHUB_HISTORY = {
  owner: "Fatty911",
  repo: "Personal_commonly_used",
  path: "cars/filter-history/history.json",
  branch: "main"
};
```

历史文件在 `Personal_commonly_used` 仓库内通过 GitHub Contents API 初始化，初始内容为：

```json
{"version":1,"updatedAt":"2026-06-15T00:00:00.000Z","profiles":{}}
```

网页不会把 GitHub Token 写入公开仓库；Token 只保存在当前浏览器本机存储中。跨设备时使用同一同步码和一个只授权 `Personal_commonly_used` 仓库 Contents 读写权限的 fine-grained token 即可读取和保存同一份筛选历史。未填写 Token 的访客只使用本机匿名缓存。

Cloudflare Worker 后端仍保留：

```bash
wrangler deploy
```

Cloudflare 需要把 `cars.jiucai.eu.org/api/filter-history` 路由到 `cars-filter-history` Worker，并绑定 KV namespace `FILTER_HISTORY`。当前仓库已包含 `wrangler.toml` 和 Worker 代码。

---

### 6. scripts/fix_files.py

**功能**：代码修复工具，用于修复scripts/test_autohome.py中的缩进问题

---

### 7. scripts/generate_clash_config.py

**功能**：Clash/Mihomo 配置生成器，从订阅链接生成 Clash 配置文件

**核心特性**：
- 支持 VMess、VLESS、Trojan、SS、Hysteria2、TUIC、WireGuard 等协议
- 自动下载并启动 mihomo 本地代理
- 订阅地址脱敏日志，避免泄露 token
- 支持通过 `PROXY_SUBSCRIPTION_USER_AGENT` 环境变量覆盖默认 UA

---

### 8. scripts/auto_fix_workflow.py

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
python scripts/auto_fix_workflow.py error.log scripts/test_autohome.py

# 在 workflow 中自动调用（已集成）
```

**触发前分类**：
- 爬虫日志出现 `exit code 10`、达到时间/数量上限、保存进度继续下次、已处理数百条等主动分段退出特征时，跳过大模型修复。
- 完整工作流日志或爬虫日志出现 git push/rebase 冲突、非快进、权限拒绝、Runner/浏览器临时异常等基础设施问题时，跳过大模型修复。
- 日志显示输出行数过少、少量车型 `无法解析config或option`、拒绝上传/合并等数据质量保护时，跳过大模型修复，避免把正常保护机制误判为代码需要改。
- 日志显示 AI Provider 自身 SSL、401、403、证书或网络异常时，跳过再次自动修复，避免监控工作流围绕自动修复失败产生噪音。
- 只有日志显示未生成数据、完全解析不到车型数据、配置页/接口致命异常等站点结构或链接异常时，才调用大模型修复。
- `AI_Auto_Fix_Monitor.yml` 会优先抓取完整失败日志，再静默尝试下载 `error-log` artifact 参与分类；成功的爬虫 run 通常没有该 artifact，不会因此产生红色 annotation。
- `AI_Auto_Fix_Monitor.yml` 会先用 `custom_scripts/check_workflow_expectations.py` 判断是否需要代码修复：失败日志属于站点结构/解析异常或未知代码问题时才修，成功但长爬虫跑到允许窗口外时也会触发修复。
- 监控工作流优先调用官方 `openai/codex-action@v1` 作为 Codex 自修复代理；需要仓库 Secret `OPENAI_API_KEY`。Codex 修完后必须通过 `ensure_codex_autofix_scope.py`、`validate_syntax.py` 和 `validate_workflow_expectations.py`，才会提交并推送到 `main`。
- 未配置 `OPENAI_API_KEY` 或 Codex 执行失败时，监控工作流才退回 `scripts/auto_fix_workflow.py` 多 Provider 旧修复器兜底。
- `scripts/auto_fix_workflow.py` 未能产出可用修复时，监控工作流记录为跳过并正常结束；只有真正生成改动、语法校验通过、提交并推送成功后才标记 `fixed=true`。
- 分类逻辑位于 `custom_scripts/classify_crawl_failure.py`，两个爬虫 workflow 和 `AI_Auto_Fix_Monitor.yml` 都会调用。

**当前已配置的 GitHub Secrets**：

`ACTION_PAT`、`ATOMGIT_API_KEY`、`MINIMAX_API_KEY`、`MINIMAX_CODING_PLAN_API_KEY`、`MODAL_API_KEY`、`MODELSCOPE_API_KEY`、`MOONSHOT_API_KEY`、`NVIDIA_NIM_API_KEY`、`OPENAI_API_KEY`、`OPENROUTER_API_KEY`、`PROXY_SUBSCRIPTIONS`、`XAI_API_KEY`、`ZEN_API_KEY`

**工作原理**：
1. 自动发现所有 `_API_KEY` 环境变量
2. 解析对应 `BASE_URL`、`MODEL_LIST`、`PROXY_URL`；没有可用 base_url 或模型的 Provider 会跳过
3. 依次尝试各 Provider 的模型，生成修复方案
4. 置信度 ≥ 0.6 时自动应用修复并提交推送

---

### 9. .github/workflows/

**功能**：GitHub Actions 自动化工作流

**工作流文件**：

| 文件 | 功能 |
|------|------|
| `crawl-autohome.yml` | 汽车之家爬虫，上午/下午两个运行窗口 |
| `crawl-dongchedi.yml` | 懂车帝爬虫，上午/下午两个运行窗口 |
| `crawl-trigger.yml` | cron-job.org 外部触发器，仅在指定时间窗口触发目标爬虫 |
| `merge-and-filter.yml` | 抓取零整比、合并过滤、Release、GitHub Pages 发布 |
| `deploy-pages.yml` | 静态网页独立发布 |
| `AI_Auto_Fix_Monitor.yml` | Codex 优先的 AI 自动修复监控 |
| `ci.yml` | CI 语法校验和冒烟测试 |
| `auto-merge.yml` | PR 自动合并（squash） |

**环境变量**：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `RUN_TIME` | 每轮运行最大秒数；上午窗口为 10800，下午窗口为 21000 | 10800 |
| `MAX_CARS` | 每轮最多爬取车型/车系数；0 表示不按数量截断 | 0 |
| `MORNING_RUN_TIME` | 上午窗口运行秒数 | 10800 |
| `AFTERNOON_RUN_TIME` | 下午窗口目标运行秒数；长步骤会按 workflow 已耗时再次缩短 | 21000 |
| `MAX_WORKFLOW_SECONDS` | 单次 workflow 按 GitHub 6 小时硬限制计算的总秒数 | 21600 |
| `PROGRESS_COMMIT_BUFFER_SECONDS` | 长步骤结束后提交进度预留秒数 | 1800 |
| `WINDOW_END_BUFFER_SECONDS` | 当前北京时间窗口结束前预留秒数 | 900 |
| `CRAWL_MIN_DELAY_SECONDS` | 两次访问之间最小等待秒数 | 3 |
| `CRAWL_MAX_DELAY_SECONDS` | 两次访问之间最大等待秒数 | 8 |

**Job结构**（crawl-autohome.yml / crawl-dongchedi.yml）：

| Job名 | 功能 | 超时 | 依赖 |
|-------|------|------|------|
| `crawl-autohome` | 爬取汽车之家 | 390分钟 | 无 |
| `crawl-dongchedi` | 爬取懂车帝 | 390分钟 | 无 |
| `merge-data` / `create-release` | 抓取零整比、合并过滤、上传合并产物、创建 Release | 60/60分钟 | 爬虫 artifact |
| `deploy` | 发布 GitHub Pages 静态站点 | 30分钟 | 最新 Release |

**触发条件**（crawl-autohome.yml / crawl-dongchedi.yml）：
- 主爬虫 workflow 不再依赖 GitHub Actions `schedule`，只作为手动或外部入口的目标 workflow。
- cron-job.org 在北京时间约 08:30 和 13:30 调用 `crawl-trigger.yml` 的 `repository_dispatch`，默认同时拉起汽车之家和懂车帝。
- 有效爬取窗口为北京时间 08:00-12:30 和 13:00-22:00，窗口外启动会成功跳过。
- 合并分析：每天 UTC 12:30（北京时间 20:30），等待下午爬虫窗口结束后再合并；如果两份爬虫数据尚未完整生成，会成功跳过且不发布不完整数据
- 手动触发 (workflow_dispatch)：默认 `run_profile=auto` 时也会检查当前北京时间，只在 08:00-12:30 或 13:00-22:00 内运行长步骤

cron-job.org 配置脚本：

```bash
CRON_JOB_ORG_API_KEY=... GITHUB_DISPATCH_TOKEN=... python custom_scripts/configure_cron_job_org.py
```

该脚本会创建或更新两个 Asia/Shanghai 定时任务：08:30 和 13:30，POST 到 GitHub `repository_dispatch`，payload 为 `event_type=trigger-crawl`。

**自动运行逻辑**：
1. 外部触发已经固定在北京时间约 08:30 和 13:30，主爬虫 workflow 不再追加随机启动延迟。
2. 爬取循环：
   - 按当前运行窗口运行指定时长
   - 未完成：commit进度 → pull --rebase + push 重试同步 → 正常结束本次 workflow，等待下一次 cron-job.org 外部触发继续
   - 完成：生成数据并写入当前半月的 `crawl_state/*_YYYYMM_H1.done` 或 `crawl_state/*_YYYYMM_H2.done` 标记
3. 每个主爬虫 workflow 按上午/下午窗口分别加并发锁：同一窗口备用触发不会并发重复爬，但上午不会阻塞下午
4. 同一个半月周期内如果已完成全量爬取，后续自动触发会直接跳过；进入新半月周期时自动重置对应爬虫进度
5. `custom_scripts/crawl_budget.py` 会取“当前窗口结束前预留 900 秒”和“GitHub Actions 6 小时限制前预留 1800 秒”两者中更早的截止时间来缩短 `RUN_TIME`；不足 5 分钟会成功跳过，避免进度来不及提交
6. 进度提交通过 `custom_scripts/git_sync_progress.sh` 同步；脚本使用 `fetch → rebase → push` 并打印脱敏后的 Git 错误，直连重试会显式清除代理环境，遇到空 rebase/进度冲突会自动 skip 或合并 JSON 进度，避免远端覆盖本地已爬进度
7. 懂车帝重置进度时会保留车系列表缓存，接口短暂返回非 JSON 或空响应时可回退继续爬取
8. 懂车帝 step2 的 `dongchedi/json/*.html` 页面缓存通过 `actions/cache` 按半月周期恢复；强制重跑或进入新半月周期会清空旧 HTML，普通分段续爬会先恢复缓存再校验 `crawled_series`
9. 每两次网络访问之间默认等待3-8秒，模拟人工浏览动作速率
10. 合并分析通过 `custom_scripts/download_latest_crawler_artifact.py` 向前扫描当前半月内最近的有效爬虫 artifact；会跳过半月完成后的短跳过 run、空/过小 artifact 和行数少于 50 的 JSON，再运行 `scripts/crawl_zero_to_whole_ratio.py` 与 `scripts/merge_data.py`
11. 合并分析会先安装 `requests`、`beautifulsoup4`、`lxml`、`pdfplumber`、`pypdf`，确保零整比 PDF/HTML 抓取脚本可运行
12. 主爬虫 workflow 上传 error-log 或数据 artifact 前会清空代理环境，避免 GitHub artifact API 请求被本地 mihomo 代理断流影响

**车型范围**：当前只保留轿车、跑车、SUV；MPV、房车、皮卡、微面、轻客、货车、卡车等会被排除。详见 `config/CRAWL_SCOPE.md`。

---

## 代理配置

### 为什么需要代理

- 避免IP被封
- 分散请求来源
- 提高爬取成功率

### 代理管理器 (scripts/proxy_manager.py)

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
python scripts/proxy_manager.py --add-sub "https://订阅1"
python scripts/proxy_manager.py --add-sub "https://订阅2"

# 列出所有订阅
python scripts/proxy_manager.py --list-subs

# 刷新所有订阅
python scripts/proxy_manager.py --refresh
```

**排除关键字**：
```bash
# 添加排除关键字（逗号分隔）
python scripts/proxy_manager.py --exclude "过期,测试,expire,test"

# 列出排除关键字
python scripts/proxy_manager.py --list-exclude

# 移除排除关键字
python scripts/proxy_manager.py --remove-exclude "test"
```

**手动添加代理**：
```bash
# HTTP代理
python scripts/proxy_manager.py --add-http "节点1" "proxy.example.com" "8080" "user:pass"

# SOCKS5代理
python scripts/proxy_manager.py --add-socks5 "节点2" "127.0.0.1" "1080" ""
```

**查看和测试**：
```bash
# 查看统计
python scripts/proxy_manager.py --stats

# 列出代理
python scripts/proxy_manager.py --list

# 测试前5个代理
python scripts/proxy_manager.py --test 5

# 清空所有代理
python scripts/proxy_manager.py --clear
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

汽车之家和懂车帝同一配置项的字段名不同，已在scripts/merge_data.py中统一：

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
| 汽车之家 | cron-job.org 北京时间 08:30/13:30 外部触发 | 约 60 | 半月全量完成后跳过 |
| 懂车帝 | cron-job.org 北京时间 08:30/13:30 外部触发 | 约 60 | 半月全量完成后跳过 |
| 合并 | 每天 UTC 12:30（北京时间 20:30） | 30 | <300 |

**半月跳过**：每个爬虫在当月 1-15 日、16-月底两个周期内全量完成后，会写入 `crawl_state/` 完成标记；同一周期后续自动触发直接跳过，不再重复爬。

**合并保护**：合并分析只在汽车之家和懂车帝两份数据都存在且各不少于 50 行时发布 Release/Pages；定时运行遇到数据未就绪会成功跳过，手动 `force_merge=true` 仍会按失败处理。下载爬虫数据时不会只取最近一次成功 run，而是扫描当前半月内最近的有效 artifact，避免半月完成后的“跳过 run”没有数据 artifact 却挡住发布。

**零整比来源**：合并分析会抓取公开零整比 PDF/HTML，并输出 `zero_to_whole_ratios_YYYYMMDD.json`；可用 Repository Variable `ZERO_TO_WHOLE_RATIO_URLS` 补充中保研、中保协、中汽修协或媒体转载的可下载来源。

**启动与窗口预算**：外部触发固定在北京时间约 08:30 和 13:30，主爬虫不再增加随机等待；长步骤按 08:00-12:30、13:00-22:00 两个窗口动态缩短运行时长，并同时扣减 GitHub Actions 6 小时硬限制。两次网络访问之间默认等待 3-8 秒，可通过 `CRAWL_MIN_DELAY_SECONDS` / `CRAWL_MAX_DELAY_SECONDS` 调整。

**分段续爬**：爬虫脚本返回 `exit code 10` 时表示本次时间预算用完但还没全量完成。workflow 会提交进度并正常结束本次运行，不会在同一个 job 内再次重启长步骤，避免实际运行时间超过上午/下午窗口。汽车之家 step1 与懂车帝 step2 都会在长步骤启动前按 workflow 已耗时重新缩短 `RUN_TIME`，并预留提交缓冲，防止 GitHub 6 小时硬超时直接取消导致进度无法推送。

**Hermes/Codex 持续调试闭环**：当用户要求“完全达到预期前持续调试”时，不能只看 `github-actions[bot]` 的进度提交，也不能只汇报 Actions 仍在运行。有效进展必须至少包含一次人工或 Hermes/Codex 产生的源码、workflow 或 Pages 修复提交，并继续完成以下闭环：

1. 用 `gh run list --all`、`gh run view --log`、Release artifact 和 `https://cars.jiucai.eu.org/data/latest.json` 同时确认当前失败点。
2. 在本地或干净临时 clone 中修改源码、workflow 或 Pages 前端，并运行适用的静态检查、脚本测试和 workflow 护栏。
3. 提交并推送非 bot 修复提交，避免只留下进度 JSON 或 done marker 变化。
4. 手动触发 debug 模式爬虫 workflow，样本量控制在二三十条，验证“爬虫 -> artifact -> merge-and-filter -> deploy-pages -> Pages 数据”的短链路。
5. 若已有 schedule/外部触发 workflow 正在运行，按北京时间 08:00-12:30、13:00-22:00 窗口、GitHub Actions 6 小时限制和合并/部署预计耗时估算下一次检查时间，不要重复抢跑长任务。
6. Pages 验证不只看 HTTP 200；要检查 `latest.json` 行数、双源/验证字段、关键字段覆盖率和前端显示是否符合预期。

2026-07-04 的治理结论是：远程仓库长时间只有 `github-actions[bot]` 提交时，应视为持续调试闭环没有形成，监控器必须继续定位并修复源码或 workflow，而不是仅写状态报告。

**懂车帝 HTML 缓存**：懂车帝 step2 的 HTML 页面不提交到 git，而是由 `crawl-dongchedi.yml` 在 step1 前恢复 `dongchedi/json/` Actions cache。日志中的 `已有HTML` 代表本次 runner 实际恢复到的页面数；如果缓存缺失，脚本会重置缺少 HTML 的 `crawled_series`，防止只保存进度却没有页面数据。

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
python scripts/test_autohome.py

# 3. 运行懂车帝爬虫（完整流程）
python crawl_dongchedi.py

# 4. 合并并过滤数据
python scripts/crawl_zero_to_whole_ratio.py
python scripts/merge_data.py
```

### 分步运行

```bash
# 汽车之家 - 只爬取第一步（最多6小时，400个车型）
python scripts/test_autohome.py --step 1 --time-limit 21600 --max-cars 400 --auto

# 汽车之家 - 从断点继续
python scripts/test_autohome.py --step 1 --auto

# 汽车之家 - 后续步骤
python scripts/test_autohome.py --step 2
python scripts/test_autohome.py --step 3
python scripts/test_autohome.py --step 4
python scripts/test_autohome.py --step 5
python scripts/test_autohome.py --step 6

# 懂车帝 - 只爬取第二步
python crawl_dongchedi.py --step 2 --time-limit 21600 --max-series 400 --auto
```

### GitHub Actions运行

**当前调度**（UTC时间）：
- 汽车之家：由 cron-job.org 在北京时间约 08:30 和 13:30 外部触发 `crawl-trigger.yml` 后拉起
- 懂车帝：由 cron-job.org 在北京时间约 08:30 和 13:30 外部触发 `crawl-trigger.yml` 后拉起
- 数据合并：每天 12:30（北京时间 20:30）
- 外部触发器：仅北京时间 08:00-12:30 或 13:00-22:00 触发目标爬虫

**代理配置（强烈推荐）**

在 **Repository Settings → Secrets and variables → Actions** 中添加以下变量：

| Secret 名称              | 说明                              | 示例格式 |
|-------------------------|-----------------------------------|----------|
| `PROXY_SUBSCRIPTIONS`   | 机场订阅地址（支持多条）           | JSON对象、JSON数组或每行一个URL |
| `OPENROUTER_API_KEY`    | 用于错误自动修复                   | sk-... |
| `OPENAI_API_KEY`        | 用于 Codex 自修复监控               | sk-... |
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
