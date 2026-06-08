# Docker 部署指南

## 优势

- ✅ 完全隔离，不影响主机目录结构
- ✅ 环境一致，避免依赖冲突
- ✅ 一键部署，简单快速
- ✅ 数据持久化，容器重启不丢失
- ✅ 内置Mihomo代理，支持所有主流协议
- ✅ 多订阅支持，自动选择最快节点

## 快速开始

### 1. 克隆代码

```bash
git clone https://github.com/Fatty911/crawl_cars.git
cd crawl_cars
```

### 2. 创建目录结构

```bash
# 创建数据目录
mkdir -p data html newhtml json content newjson exception dongchedi output

# 创建代理配置（可选）
cat > proxies.json << 'EOF'
{
  "proxies": [],
  "stats": {},
  "exclude_keywords": ["过期", "测试", "expire"],
  "subscriptions": [
    "https://你的订阅链接"
  ]
}
EOF
```

**说明**：
- 如果不需要代理，可以跳过创建 `proxies.json`
- 支持多个订阅链接，自动合并节点
- `exclude_keywords` 用于过滤不需要的节点

### 3. 构建镜像

```bash
docker compose build
```

### 4. 启动定时任务

```bash
# 后台运行定时任务
docker compose up -d crawl-cron

# 查看日志
docker compose logs -f crawl-cron
```

## 数据持久化

所有数据存储在当前目录的子目录中：

| 目录 | 内容 |
|------|------|
| `./data` | 进度文件、配置 |
| `./html` | 汽车之家HTML缓存 |
| `./newhtml` | 解析后的HTML |
| `./json` | JSON数据 |
| `./content` | 浏览器执行结果 |
| `./newjson` | 最终JSON数据 |
| `./exception` | 异常记录 |
| `./dongchedi` | 懂车帝数据 |
| `./output` | 输出文件(CSV/JSON) |

**删除容器不会丢失数据**，删除这些目录才会。

## 手动运行

```bash
# 启动手动运行容器
docker compose --profile manual up -d crawl-manual

# 进入容器
docker compose exec crawl-manual bash

# 手动运行爬虫
python test_autohome.py --step 1 --auto --time-limit 7200 --max-cars 500

# 运行懂车帝
python crawl_dongchedi.py --step 2 --auto --time-limit 7200 --max-series 500

# 合并数据
python crawl_zero_to_whole_ratio.py
python merge_data.py

# 退出容器
exit
```

## 定时任务配置

`docker-cron.sh` 定时规则：

| 时间 | 任务 |
|------|------|
| 每天 08:00-12:30（北京时间） | 汽车之家 + 懂车帝爬虫 |
| 每天 13:00-13:30（北京时间） | 汽车之家 + 懂车帝爬虫 |
| 每天 20:30（北京时间） | 合并数据 |

**说明**：
- 上午窗口动态缩短，确保 12:30 前结束（模拟午饭时间）
- 两次网络访问之间等待 3-8 秒，模拟人工浏览节奏
- 每半月完成全量爬取后自动跳过，进入新半月周期时自动重置

## 代理配置

### 为什么需要代理

- 避免IP被封
- 分散请求来源
- 提高爬取成功率

### 内置Clash代理支持 🎉

**Docker容器已内置 Mihomo (Clash.Meta)，支持自动将订阅转为HTTP代理！**

**支持的协议**：
- ✅ VMess
- ✅ VLESS
- ✅ Trojan
- ✅ Shadowsocks (SS)
- ✅ ShadowsocksR (SSR)
- ✅ Hysteria / Hysteria2
- ✅ TUIC
- ✅ WireGuard

**自动启动流程**：
1. 容器启动时检查 `proxies.json` 中的订阅
2. 自动生成Clash配置
3. 启动Mihomo进程
4. 设置 `HTTP_PROXY` 环境变量
5. 自动选择最快节点

### 快速配置代理

**步骤1：创建代理配置文件**

```bash
cat > proxies.json << 'EOF'
{
  "proxies": [],
  "stats": {},
  "exclude_keywords": ["过期", "测试", "expire", "trial"],
  "subscriptions": [
    "https://你的订阅链接1",
    "https://你的订阅链接2"
  ]
}
EOF
```

**步骤2：启动容器**

```bash
docker compose up -d crawl-cron
```

**步骤3：查看代理状态**

```bash
# 进入容器
docker compose exec crawl-cron bash

# 查看Clash状态
python proxy_manager.py --clash-status

# 列出所有代理节点
python proxy_manager.py --clash-proxies

# 自动选择最快节点
python proxy_manager.py --auto-select

# 手动选择特定节点
python proxy_manager.py --select-proxy "节点名称"
```

### 多订阅配置示例

```json
{
  "proxies": [],
  "stats": {},
  "exclude_keywords": ["过期", "到期", "expire", "test", "测试", "试用"],
  "subscriptions": [
    "https://机场1的订阅链接",
    "https://机场2的订阅链接",
    "https://机场3的订阅链接"
  ]
}
```

**说明**：
- 支持添加多个订阅，自动合并节点
- `exclude_keywords` 用于排除不需要的节点
- 容器启动时会自动选择延迟最低的节点

### 代理管理器 (proxy_manager.py)

**功能**：
- ✅ 支持多个机场订阅URL
- ✅ 排除特定关键字节点
- ✅ 解析 V2Ray/Clash 订阅
- ✅ 手动添加 HTTP/SOCKS5 代理
- ✅ 负载均衡策略
- ✅ 节点统计与筛选
- ✅ 内置Clash进程管理
- ✅ 自动选择最快节点

**Clash管理命令**：
```bash
# 启动Clash
python proxy_manager.py --start-clash

# 停止Clash
python proxy_manager.py --stop-clash

# 查看Clash状态
python proxy_manager.py --clash-status

# 列出Clash代理节点
python proxy_manager.py --clash-proxies

# 选择代理节点
python proxy_manager.py --select-proxy "节点名称"

# 自动选择最快节点
python proxy_manager.py --auto-select

# 测试节点延迟
python proxy_manager.py --test-delay "节点名称"
```

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

### 方式一：内置Clash（推荐）

容器内置Mihomo，自动将订阅转为HTTP代理：

```bash
# 1. 配置订阅
cat > proxies.json << 'EOF'
{
  "subscriptions": ["https://你的订阅链接"]
}
EOF

# 2. 启动容器（自动启动Clash）
docker compose up -d crawl-cron
```

### 方式二：外部代理

如果已有外部代理服务：

```bash
# 环境变量方式
docker compose.yaml:
  environment:
    - HTTP_PROXY=http://host.docker.internal:7890
    - HTTPS_PROXY=http://host.docker.internal:7890
```

### 方式三：手动添加HTTP/SOCKS5代理

```bash
# 添加代理
python proxy_manager.py --add-http "proxy1" "proxy.example.com" "8080" "user:pass"

# 或编辑 proxies.json
```

## 常用命令

```bash
# 查看运行状态
docker compose ps

# 查看日志
docker compose logs -f crawl-cron

# 重启服务
docker compose restart crawl-cron

# 停止服务
docker compose down

# 清理数据重新开始
docker compose down
rm -rf data html newhtml json content newjson exception dongchedi output
mkdir -p data html newhtml json content newjson exception dongchedi output

# 更新代码后重建
git pull
docker compose build
docker compose up -d crawl-cron
```

## 资源限制

默认配置：
- CPU: 最大2核
- 内存: 最大2GB

修改 `docker compose.yaml`：

```yaml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 4G
```

## 故障排查

### 1. 容器无法启动

```bash
# 查看详细日志
docker compose logs crawl-cron

# 检查镜像
docker images | grep crawl
```

### 2. 数据未持久化

```bash
# 检查目录权限
ls -la

# 修复权限
sudo chown -R $USER:$USER data html json output
```

### 3. 内存不足

```bash
# 查看容器资源使用
docker stats crawl-cron

# 增加内存限制
# 编辑 docker compose.yaml 中的 memory
docker compose up -d crawl-cron
```

## Docker vs VPS

| 特性 | Docker | VPS直接部署 |
|------|--------|-------------|
| 环境隔离 | ✅ 完全隔离 | ❌ 共享环境 |
| 部署难度 | ⭐ 简单 | ⭐⭐ 中等 |
| 资源开销 | 略高 | 最低 |
| 数据管理 | 目录映射 | 直接访问 |
| 推荐场景 | 推荐 | 已有环境 |

## 一键部署脚本

```bash
#!/bin/bash
set -e

echo "=== Docker 部署汽车数据爬虫 ==="

# 克隆代码
if [ ! -d "crawl_cars" ]; then
    git clone https://github.com/Fatty911/crawl_cars.git
fi
cd crawl_cars

# 创建目录
mkdir -p data html newhtml json content newjson exception dongchedi output

# 创建代理配置（可选）
if [ ! -f "proxies.json" ]; then
    echo "是否配置代理？(y/N)"
    read -r use_proxy
    if [ "$use_proxy" = "y" ] || [ "$use_proxy" = "Y" ]; then
        echo "请输入订阅链接（多个用空格分隔）:"
        read -r subs
        sub_json=$(echo "$subs" | tr ' ' '\n' | sed 's/^/"/;s/$/",/' | tr -d '\n' | sed 's/,$//')
        cat > proxies.json << EOF
{
  "proxies": [],
  "stats": {},
  "exclude_keywords": ["过期", "测试", "expire"],
  "subscriptions": [$sub_json]
}
EOF
        echo "代理配置已保存到 proxies.json"
    else
        echo '{"proxies":[],"stats":{},"subscriptions":[]}' > proxies.json
    fi
fi

# 构建并启动
docker compose build
docker compose up -d crawl-cron

echo ""
echo "=== 部署完成 ==="
echo "查看日志: docker compose logs -f crawl-cron"
echo "停止服务: docker compose down"
echo ""
echo "代理管理:"
echo "  进入容器: docker compose exec crawl-cron bash"
echo "  查看代理: python proxy_manager.py --clash-proxies"
echo "  选择节点: python proxy_manager.py --auto-select"
```

保存为 `deploy-docker.sh`，运行：

```bash
chmod +x deploy-docker.sh
./deploy-docker.sh
```
