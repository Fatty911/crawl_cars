# Docker 部署指南

## 优势

- ✅ 完全隔离，不影响主机目录结构
- ✅ 环境一致，避免依赖冲突
- ✅ 一键部署，简单快速
- ✅ 数据持久化，容器重启不丢失

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

# 创建代理配置示例
cat > proxies.json << 'EOF'
{
  "proxies": [],
  "stats": {}
}
EOF
```

### 3. 构建镜像

```bash
docker-compose build
```

### 4. 启动定时任务

```bash
# 后台运行定时任务
docker-compose up -d crawl-cron

# 查看日志
docker-compose logs -f crawl-cron
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
docker-compose --profile manual up -d crawl-manual

# 进入容器
docker-compose exec crawl-manual bash

# 手动运行爬虫
python test_autohome.py --step 1 --auto --time-limit 7200 --max-cars 500

# 运行懂车帝
python crawl_dongchedi.py --step 2 --auto --time-limit 7200 --max-series 500

# 合并数据
python merge_data.py

# 退出容器
exit
```

## 定时任务配置

`docker-cron.sh` 定时规则：

| 时间 | 任务 |
|------|------|
| 周一 2:00+随机延迟 | 汽车之家 |
| 周二 2:00+随机延迟 | 懂车帝 |
| 周三 3:00+随机延迟 | 合并数据 |
| 周四 2:00+随机延迟 | 汽车之家 |
| 周五 2:00+随机延迟 | 懂车帝 |
| 周六 3:00+随机延迟 | 合并数据 |

**随机延迟**：0-60分钟，模拟人类行为

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

### 方式一：环境变量

编辑 `docker-compose.yaml`：

```yaml
environment:
  - HTTP_PROXY=http://host.docker.internal:7890
  - HTTPS_PROXY=http://host.docker.internal:7890
```

### 方式二：代理配置文件

```bash
# 添加代理
python proxy_manager.py --add-http "proxy1" "proxy.example.com" "8080" "user:pass"

# 或编辑 proxies.json
```

## 常用命令

```bash
# 查看运行状态
docker-compose ps

# 查看日志
docker-compose logs -f crawl-cron

# 重启服务
docker-compose restart crawl-cron

# 停止服务
docker-compose down

# 清理数据重新开始
docker-compose down
rm -rf data html newhtml json content newjson exception dongchedi output
mkdir -p data html newhtml json content newjson exception dongchedi output

# 更新代码后重建
git pull
docker-compose build
docker-compose up -d crawl-cron
```

## 资源限制

默认配置：
- CPU: 最大2核
- 内存: 最大2GB

修改 `docker-compose.yaml`：

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
docker-compose logs crawl-cron

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
# 编辑 docker-compose.yaml 中的 memory
docker-compose up -d crawl-cron
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

# 创建代理配置
if [ ! -f "proxies.json" ]; then
    echo '{"proxies":[],"stats":{}}' > proxies.json
fi

# 构建并启动
docker-compose build
docker-compose up -d crawl-cron

echo "=== 部署完成 ==="
echo "查看日志: docker-compose logs -f crawl-cron"
echo "停止服务: docker-compose down"
```

保存为 `deploy-docker.sh`，运行：

```bash
chmod +x deploy-docker.sh
./deploy-docker.sh
```
