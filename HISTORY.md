# 对话历史总结

> 最后更新：2026-05-29 19:34
> 
> 本文档记录了汽车数据爬虫项目从创建到最新的所有对话历史，融合了所有历史文件的内容。

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
- 新增 `CRAWL_MIN_DELAY_SECONDS=3`、`CRAWL_MAX_DELAY_SECONDS=8`，并在 `test_autohome.py`、`crawl_dongchedi.py` 的网络访问之间使用随机等待，模拟人工浏览节奏。
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
- 修复本地遗留的 `merge_data.py` 与 `.github/workflows/ci.yml` 合并冲突标记，恢复语法校验和 CI 冒烟测试可运行状态。
- 更新 `README.md`，补充网页查看器目录、功能、发布方式和本地预览方法。

### 结果
- 仓库启用 GitHub Pages 的 GitHub Actions 发布源后，每次“合并分析”工作流成功都会自动更新网页。
- 静态网页不需要服务器和数据库，适合 GitHub Pages 免费托管。

---

## 2026-05-28：修复过滤逻辑和不完整数据误发布

### 问题
- `merge_data.py` 对数值条件统一使用 `<=`，导致 `纯电续航(km)` 被按 `<= 150` 判断，和高级筛选中常见的 `>= 150` 语义相反。
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
- `merge_data.py` 里的 `merged_*.csv` 实际写入的是过滤结果，不是全部合并数据；当过滤结果为空时，Release 没有可查看的 CSV。

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
- 新增 `ci.yml`，在 `push`、`pull_request` 和手动触发时安装依赖、编译 Python 文件、调用 `custom_scripts/validate_syntax.py` 校验变更文件，并对 `merge_data.py` 做样本冒烟测试。
- 新增 `auto-merge.yml`，当非草稿 PR 带有 `automerge` 标签时启用 GitHub 原生 squash auto-merge。
- 修复 `merge_data.py` 过滤条件未识别归一化后的 `蓝牙/数字钥匙` 字段，避免符合条件车型被误过滤。

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
- **修改**：`auto_fix_workflow.py` 排序算法改为免费 Provider 优先
- **顺序**：AtomGit → ZEN → NVIDIA NIM → Modal → OpenRouter → 其他

### 问题4：TUI 显示旧模型
- **方案**：创建 `opencode.json` 配置文件
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
| `auto_fix_workflow.py` | 免费模型优先排序算法 |
| `opencode.json` | **新增** TUI 模型 whitelist 配置 |
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
2. 重构 `auto_fix_workflow.py` 支持 Lobe-Chat 风格的动态 Provider 发现
3. `XXXX_MODEL_LIST` 和 `XXXX_PROXY_URL` 非必填，未配置不报错
4. 未配置 `MODEL_LIST` 则使用排行榜前10(1M+)模型，已配置则取并集
5. 更新 README.md 和 HISTORY.md

### 完成修改

| 文件 | 修改内容 |
|------|----------|
| `AGENTS.md` | **新增** 全局规则文件（语言、提交、模型选择、opencode 配置等） |
| `auto_fix_workflow.py` | 重构为通用多Provider系统，动态发现 `_API_KEY`，支持12+ Provider |
| `README.md` | 更新 auto_fix_workflow.py 文档、Provider 列表、Secrets 列表 |

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
在 workflow 中集成 auto_fix_workflow.py，实现错误自动修复。

### 完成修改

| 文件 | 修改内容 |
|------|----------|
| `crawl-autohome.yml` | 集成错误自动修复，step1 和 remaining steps 失败时自动调用大模型 |
| `crawl-dongchedi.yml` | 集成错误自动修复，step2 失败时自动调用大模型 |
| `README.md` | 更新目录结构、添加 auto_fix_workflow.py 说明 |

### 工作流错误处理流程
1. 步骤执行失败，错误日志保存到 `*_error.log`
2. 检查是否有 API Key 配置
3. 调用 `auto_fix_workflow.py` 分析错误
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
| `crawl-autohome.yml` | 添加代理配置步骤；支持 `run_with_proxy.py --proxy random` |
| `crawl-dongchedi.yml` | 添加代理配置步骤；设置 http_proxy/https_proxy |
| `merge-and-filter.yml` | 删除重复的 checkout 和 setup-python |
| `auto_fix_workflow.py` | **新增** 大模型自动修复工作流错误脚本 |
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
新增 `auto_fix_workflow.py`，支持：
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
├── auto_fix_workflow.py  # 大模型自动修复工作流错误
├── generate_clash_config.py  # Clash配置生成器
├── deploy_vps.sh         # VPS一键部署
├── docker compose.yaml   # Docker配置
├── opencode.json         # TUI 模型配置
├── AGENTS.md             # 全局规则
├── HISTORY.md            # 对话历史
└── .github/workflows/
    ├── crawl-autohome.yml    # 汽车之家工作流
    ├── crawl-dongchedi.yml   # 懂车帝工作流
    ├── crawl-trigger.yml     # 随机触发器
    ├── merge-and-filter.yml  # 合并工作流
    └── AI_Auto_Fix_Monitor.yml  # AI 自动修复监控
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

---

## 2026-04-20：修复 Actions 工作流执行环境
- 修复了因为 `browser-actions/setup-chrome@master` 引发的 "File not found: index.js" 构建失败问题，将所有的版本引用由 `@master` 替换为稳定的 `@v2` 版本。
- 同样为了防止上游不兼容更新，将 `nanasess/setup-chromedriver` 从 `@master` 修改为了 `@v2`。

## 2026-05-28：修复 Release CSV 体积过小与过滤逻辑错误

### 问题现象
- Release 产出的 `merged_YYYYMMDD.csv` 文件异常偏小，基本只有表头或极少数据，无法反映完整车型数据。

### 根因定位
1. `merge_data.py` 中 `merged_YYYYMMDD.csv` 实际写入的是 `filtered_rows`，而不是 `all_rows`，导致文件只包含“满足高配筛选条件”的车型。
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
  - 执行依赖安装、`custom_scripts/validate_syntax.py` 语法校验、`merge_data.py` 冒烟运行。
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
- `auto_fix_workflow.py` 主程序没有根据修复结果设置退出码，导致“未修复”也可能被工作流误判为成功。

### 修复内容
- 为 `AI_Auto_Fix_Monitor.yml` 增加 `concurrency`，同一爬虫/分支的 AI 修复任务只保留一个活跃运行。
- 移除 AI 修复步骤的 `continue-on-error` 和吞错写法，拿不到日志或修复失败时直接失败退出。
- 移除自动 `gh run rerun`，避免重新运行旧 commit 上的失败 workflow。
- `auto_fix_workflow.py` 根据是否真正修复返回进程退出码。
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
