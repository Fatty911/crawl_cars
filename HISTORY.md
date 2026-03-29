# 对话历史总结

> 最后更新：2026-03-29
> 
> 本文档记录了汽车数据爬虫项目从创建到最新的所有对话历史，融合了所有历史文件的内容。

---

## 2026-02-22：项目初始化

### 需求1：修改爬虫逻辑 + 优化超时

**用户需求**：
- 已有代码爬取3年内上市的车型配置，改为爬取所有车型
- 过滤条件：零百7秒内、纯电续航150KM以上、智驾领航支持城市路段、远程启动、远程控车、手机蓝牙/UWB钥匙、座椅记忆、后视镜记忆
- 解决action爬取测试超时问题

**完成内容**：
1. `test_autohome.py`: MIN_YEAR从3改为0
2. `crawl_dongchedi.py`: MIN_YEAR从3改为0
3. `merge_data.py`: 添加过滤功能FILTER_CONDITIONS（8个条件）
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

#### 2. 代理管理器 (proxy_manager.py)
- 支持多机场订阅URL
- 支持 V2Ray/Clash 配置解析
- 负载均衡策略：random, round_robin, least_used, best_performance
- 排除关键字过滤（过期、测试等）
- 节点统计与筛选

#### 3. VPS部署
- `deploy_vps.sh`: 一键部署脚本
- `VPS_DEPLOY.md`: 部署指南

#### 4. Docker部署
- `Dockerfile`: 基于Python 3.12 Alpine + Chromium
- `docker compose.yaml`: 服务定义、卷映射、资源限制
- `docker-cron.sh`: 容器内定时任务
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
| `crawl-autohome.yml` | 添加代理配置步骤；支持`run_with_proxy.py --proxy random` |
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
├── test_autohome.py      # 汽车之家爬虫
├── crawl_dongchedi.py    # 懂车帝爬虫
├── merge_data.py         # 数据合并过滤
├── proxy_manager.py      # 代理管理器
├── run_with_proxy.py     # 带代理启动脚本
├── generate_clash_config.py  # Clash配置生成器
├── deploy_vps.sh         # VPS一键部署
├── docker compose.yaml   # Docker配置
└── .github/workflows/
    ├── crawl-autohome.yml    # 汽车之家工作流
    ├── crawl-dongchedi.yml   # 懂车帝工作流
    └── merge-and-filter.yml  # 合并工作流
```

### 工作流调度（UTC时间）
| 周一 | 周二 | 周三 | 周四 | 周五 | 周六 |
|------|------|------|------|------|------|
| 汽车之家 2:00 | 懂车帝 2:00 | 合并 3:00 | 汽车之家 14:00 | 懂车帝 14:00 | 合并 3:00 |

### 过滤条件
- 零百7秒内
- 纯电续航150KM以上
- 智驾领航支持城市路段
- 远程启动
- 远程控车
- 手机蓝牙/UWB钥匙
- 座椅记忆
- 后视镜记忆
