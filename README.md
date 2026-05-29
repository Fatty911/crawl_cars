# 汽车配置数据爬虫项目

## 项目概述

自动爬取汽车之家和懂车帝的车型配置数据，过滤出符合高配条件的车型，并生成数据文件供Release使用。

## 目录结构

```
crawl_cars/
├── test_autohome.py          # 汽车之家爬虫脚本
├── crawl_dongchedi.py        # 懂车帝爬虫脚本
├── merge_data.py             # 数据合并与过滤脚本
├── docs/                     # GitHub Pages 静态网页表格查看器
├── proxy_manager.py          # 代理管理器
├── run_with_proxy.py         # 带代理的启动脚本
├── auto_fix_workflow.py      # 大模型自动修复工作流错误
├── deploy_vps.sh             # VPS 一键部署脚本
├── VPS_DEPLOY.md             # VPS 部署指南
├── DOCKER_DEPLOY.md          # Docker 部署指南
├── HISTORY.md                # 对话历史总结
├── .gitignore                # Git 忽略配置
├── .github/workflows/
│   ├── crawl-autohome.yml    # 汽车之家工作流
│   ├── crawl-dongchedi.yml   # 懂车帝工作流
│   ├── deploy-pages.yml      # 静态网页独立发布工作流
│   └── merge-and-filter.yml  # 合并过滤、Release、GitHub Pages 发布工作流
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

**输出文件**：`autoHome_YYYYMMDD.json` (包含全部车型配置)

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
- 支持切换“全部车型”和“符合条件”数据集。
- 支持选择显示列、分页查看、导出当前筛选结果为 CSV/JSON。

---

### 5. fix_files.py

**功能**：代码修复工具，用于修复test_autohome.py中的缩进问题

---

### 6. auto_fix_workflow.py

**功能**：通用多Provider工作流错误自动修复系统（Lobe-Chat 风格配置）

**核心规则**：
- `XXXX_API_KEY` 存在 → 启用该 Provider
- `XXXX_MODEL_LIST` **非必填**：
  - 未配置 → 只使用排行榜前10且 context ≥ 1M 的模型
  - 已配置 → 使用排行榜前10(1M+) 与 MODEL_LIST 的**并集**
- `XXXX_PROXY_URL` **非必填**
- 未读取到 `XXXX_MODEL_LIST` 时**不报错**

**支持的 Provider**（按环境变量自动发现）：

| 环境变量前缀 | Provider | base_url |
|-------------|----------|----------|
| `OPENROUTER` | OpenRouter | openrouter.ai |
| `OPENAI` | OpenAI | api.openai.com |
| `ANTHROPIC` | Anthropic | api.anthropic.com |
| `XAI` | xAI | api.x.ai |
| `ATOMGIT` | AtomGit | api-ai.gitcode.com |
| `MINIMAX` | MiniMax | api.minimax.io |
| `ZEN` | OpenCode Zen | opencode.ai/zen |
| `NVIDIA_NIM` | NVIDIA NIM | integrate.api.nvidia.com |
| `MOONSHOT` | Moonshot/Kimi | api.moonshot.cn |
| `DEEPSEEK` | DeepSeek | api.deepseek.com |
| `MODELSCOPE` | ModelScope | dashscope.aliyuncs.com |
| `MODAL` | Modal | modal.labs |

**使用方式**：

```bash
# 手动运行
python auto_fix_workflow.py error.log test_autohome.py

# 在 workflow 中自动调用（已集成）
```

**当前已配置的 GitHub Secrets**：

`ACTION_PAT`、`ATOMGIT_API_KEY`、`MINIMAX_API_KEY`、`MINIMAX_CODING_PLAN_API_KEY`、`MODAL_API_KEY`、`MODELSCOPE_API_KEY`、`MOONSHOT_API_KEY`、`NVIDIA_NIM_API_KEY`、`OPENROUTER_API_KEY`、`PROXY_SUBSCRIPTIONS`、`XAI_API_KEY`、`ZEN_API_KEY`

**工作原理**：
1. 自动发现所有 `_API_KEY` 环境变量
2. 有 `MODEL_LIST` → 与排行榜并集；无 → 使用排行榜模型
3. 依次尝试各 Provider 的模型，生成修复方案
4. 置信度 ≥ 0.6 时自动应用修复并提交推送

---

### 5. .github/workflows/crawl.yml

**功能**：GitHub Actions自动化工作流

**环境变量**：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `RUN_TIME` | 每轮运行最大秒数 | 7200 (2小时) |
| `MAX_CARS` | 每轮最多爬取车型/车系数 | 500 |

**Job结构**：

| Job名 | 功能 | 超时 | 依赖 |
|-------|------|------|------|
| `crawl-autohome` | 爬取汽车之家 | 130分钟 | 无 |
| `crawl-dongchedi` | 爬取懂车帝 | 130分钟 | 无 |
| `merge-and-filter` | 合并过滤、Release、发布 GitHub Pages | 360分钟 | 前两者 |

**触发条件**：
- 每天02:00和14:00自动执行（cron: `0 2 * * *` 和 `0 14 * * *`）
- 手动触发 (workflow_dispatch)

**自动运行逻辑**：
1. 开始前随机延迟10-40分钟
2. 爬取循环：
   - 运行指定时间或达到数量上限
   - 未完成：commit进度 → push → 随机等待 → 重新运行
   - 完成：标记完成，运行后续步骤
3. 每次commit前随机延迟30-90秒

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

**当前配置**（适合免费层级）：

| 爬虫 | 定时 | 次数/月 | 分钟数 |
|------|------|---------|--------|
| 汽车之家 | 周一 2:00, 周四 14:00 | 8 | 960 |
| 懂车帝 | 周二 2:00, 周五 14:00 | 8 | 960 |
| 合并 | 周三 3:00, 周六 3:00 | 8 | <10 |
| **总计** | - | **24** | **~1930** |

**随机延迟**：开始前随机等待 1-2 小时

**手动触发**：在 Actions 页面点击 "Run workflow"

**结论**：⚠️ 勉强够用，推荐 VPS

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
# 汽车之家 - 只爬取第一步（2小时，500个车型）
python test_autohome.py --step 1 --time-limit 7200 --max-cars 500 --auto

# 汽车之家 - 从断点继续
python test_autohome.py --step 1 --auto

# 汽车之家 - 后续步骤
python test_autohome.py --step 2
python test_autohome.py --step 3
python test_autohome.py --step 4
python test_autohome.py --step 5
python test_autohome.py --step 6

# 懂车帝 - 只爬取第二步
python crawl_dongchedi.py --step 2 --time-limit 7200 --max-series 500 --auto
```

### GitHub Actions运行

**当前调度**（UTC时间）：
- 汽车之家：每周一 02:00、周四 14:00
- 懂车帝：每周二 02:00、周五 14:00
- 数据合并：每周三 03:00、周六 03:00

**代理配置（强烈推荐）**

在 **Repository Settings → Secrets and variables → Actions** 中添加以下变量：

| Secret 名称              | 说明                              | 示例格式 |
|-------------------------|-----------------------------------|----------|
| `PROXY_SUBSCRIPTIONS`   | 机场订阅地址（支持多条）           | JSON数组 |
| `OPENROUTER_API_KEY`    | 用于错误自动修复                   | sk-... |
| `MINIMAX_API_KEY`       | 用于错误自动修复                   | mm-... |
| `XAI_API_KEY`           | 用于错误自动修复                   | xai-... |

**`PROXY_SUBSCRIPTIONS` 格式示例**（支持VMess、VLESS、Trojan、Hysteria2等）：

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

**代理工作原理**：
- 工作流启动时检测 `PROXY_SUBSCRIPTIONS`
- 有配置则自动生成 Clash 配置并启动
- 使用 `round_robin` 负载均衡模式，让各节点尽量平均使用
- 无配置则直接爬取，不影响流程

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
