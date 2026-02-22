# 汽车配置数据爬虫项目

## 项目概述

自动爬取汽车之家和懂车帝的车型配置数据，过滤出符合高配条件的车型，并生成数据文件供Release使用。

## 目录结构

```
test_crawl/
├── test_autohome.py      # 汽车之家爬虫脚本
├── crawl_dongchedi.py   # 懂车帝爬虫脚本
├── merge_data.py        # 数据合并与过滤脚本
├── fix_files.py        # 代码修复工具脚本
├── .github/workflows/
│   └── crawl.yml        # GitHub Actions工作流配置
└── README.md            # 本文件
```

---

## 文件详解

### 1. test_autohome.py

**功能**：爬取汽车之家的车型配置数据

**核心变量**：

| 变量名 | 说明 |
|--------|------|
| `working_dir` | 脚本所在目录 |
| `html_dir` | 存储下载的车型HTML页面 |
| `newhtml_dir` | 存储解析后的JS拼装HTML |
| `json_dir` | 存储提取的JSON数据 |
| `content_dir` | 存储浏览器执行后的内容 |
| `newjson_dir` | 存储最终处理后的JSON |
| `exception_dir` | 存储解析异常记录 |
| `progress_file` | 进度记录文件 `progress.json` |
| `CURRENT_YEAR` | 当前年份 (2026) |
| `MIN_YEAR` | 最小年份限制 (0=所有车型) |
| `EV_RANGE_KEYWORDS` | 纯电续航字段关键词列表 |
| `HEAT_PUMP_KEYWORDS` | 热泵空调字段关键词列表 |
| `FUEL_TYPE_KEYWORDS` | 燃油类型字段关键词列表 |

**函数**：

| 函数名 | 功能 |
|--------|------|
| `find_chrome_binary()` | 查找Chrome浏览器路径 |
| `find_chromedriver()` | 查找ChromeDriver路径 |
| `is_pure_gas_car()` | 判断是否为纯油车 |
| `fill_pure_gas_defaults()` | 纯油车填充默认值(纯电续航999,热泵"是") |
| `download_car_pages()` | 第一步：按字母下载车型页面 |
| `parse_js_to_html()` | 第二步：解析JS拼装HTML |
| `parse_json_data()` | 第三步：提取JSON数据 |
| `crack_html_files()` | 第四步：浏览器执行JS获取内容 |
| `generate_data_files()` | 第五步：匹配样式与JSON生成数据 |
| `generate_csv()` | 第六步：生成CSV/JSON输出 |

**输出文件**：`autoHome_YYYYMMDD.json` (包含全部车型配置)

---

### 2. crawl_dongchedi.py

**功能**：爬取懂车帝的车型配置数据

**核心变量**：

| 变量名 | 说明 |
|--------|------|
| `dcd_dir` | 懂车帝数据存储目录 |
| `dcd_json_dir` | 懂车帝JSON存储目录 |
| `dcd_exception_dir` | 懂车帝异常记录目录 |
| `progress_file` | 进度记录文件 |
| `MIN_YEAR` | 最小年份限制 (0=所有车型) |
| `EV_RANGE_KEYWORDS` | 纯电续航字段关键词 |
| `HEAT_PUMP_KEYWORDS` | 热泵空调字段关键词 |
| `FUEL_TYPE_KEYWORDS` | 燃油类型字段关键词 |

**函数**：

| 函数名 | 功能 |
|--------|------|
| `create_browser()` | 创建Selenium浏览器实例 |
| `get_series_list()` | 获取所有车系列表 |
| `crawl_series_config()` | 爬取车系配置页面 |
| `parse_config_pages()` | 解析配置页面提取数据 |
| `generate_output()` | 生成CSV/JSON输出 |

**输出文件**：`dongchedi_YYYYMMDD.json`

---

### 3. merge_data.py

**功能**：合并两个数据源，过滤符合条件的车型

**核心常量**：

| 常量名 | 说明 |
|--------|------|
| `HEADER_MAP` | 字段名映射表，统一不同数据源的字段名 |
| `FIXED` | 固定字段列表 |
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

### 4. fix_files.py

**功能**：代码修复工具，用于修复test_autohome.py中的缩进问题

---

### 5. .github/workflows/crawl.yml

**功能**：GitHub Actions自动化工作流

**Job结构**：

| Job名 | 功能 | 超时 |
|-------|------|------|
| `crawl-autohome` | 爬取汽车之家 | 6小时 |
| `crawl-dongchedi` | 爬取懂车帝 | 6小时 |
| `merge-and-filter` | 合并过滤并Release | 6小时 |

**触发条件**：
- 每月1日凌晨2点自动执行
- 手动触发 (workflow_dispatch)

---

## 运行流程

### 本地运行

```bash
# 1. 安装依赖
pip install requests beautifulsoup4 selenium lxml

# 2. 运行汽车之家爬虫
python test_autohome.py

# 3. 运行懂车帝爬虫
python crawl_dongchedi.py

# 4. 合并并过滤数据
python merge_data.py
```

### GitHub Actions运行

1. 手动触发：在GitHub页面点击 "Run workflow"
2. 自动触发：每月1日凌晨2点

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
