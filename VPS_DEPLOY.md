# VPS 部署指南

## 方案对比

| Platform | Free/Cost | Timeout | For Crawling | Recommend |
|----------|-----------|---------|--------------|-----------|
| GitHub Actions | 2000 min/month | 6 hours | ❌ Not enough | - |
| VPS (Bandwagon/Vultr) | $3-5/month | Unlimited | ✅ Best | ⭐⭐⭐⭐⭐ |
| Railway | $5 one-time trial, then $1/month or $5/month | Reasonable | ✅ Works | ⭐⭐⭐⭐ |
| Vercel | 6000 sec/month | 10-60 sec | ❌ Not suitable | - |
| Zeabur | Has limits | Yes | ⚠️ Barely | ⭐⭐ |

## 快速部署（VPS）

### 方式一：一键脚本

```bash
# 下载并运行部署脚本
curl -fsSL https://raw.githubusercontent.com/Fatty911/test_crawl/main/deploy_vps.sh | bash
```

### 方式二：手动部署

```bash
# 1. 安装依赖
sudo apt update
sudo apt install -y python3 python3-pip git chromium-browser chromium-chromedriver

# 2. 安装 Python 依赖
pip3 install --user requests beautifulsoup4 selenium lxml pyyaml

# 3. 克隆代码
git clone https://github.com/Fatty911/test_crawl.git ~/crawl_cars
cd ~/crawl_cars

# 4. 手动运行
python3 test_autohome.py --step 1 --auto --time-limit 7200 --max-cars 500
```

## 代理配置

### 方式一：使用机场订阅

```bash
# 解析 V2Ray 订阅链接
python3 proxy_manager.py --sub "https://你的订阅链接"

# 解析 Clash 配置文件
python3 proxy_manager.py --clash ~/.config/clash/config.yaml

# 测试代理
python3 proxy_manager.py --test

# 查看代理列表
python3 proxy_manager.py --list
```

### 方式二：手动添加代理

```bash
# 添加 HTTP 代理
python3 proxy_manager.py --add-http "proxy1" "127.0.0.1" "7890" "user:pass"

# 添加 SOCKS5 代理
python3 proxy_manager.py --add-socks5 "proxy2" "127.0.0.1" "1080" ""
```

### 方式三：编辑配置文件

编辑 `proxies.json`：

```json
{
  "proxies": [
    {
      "name": "节点1",
      "type": "http",
      "host": "127.0.0.1",
      "port": 7890,
      "username": null,
      "password": null
    },
    {
      "name": "节点2",
      "type": "socks5",
      "host": "127.0.0.1",
      "port": 1080,
      "username": "user",
      "password": "pass"
    }
  ],
  "stats": {}
}
```

### 注意事项

⚠️ **SS/VMess/Trojan 代理需要本地客户端转换**

机场订阅的节点通常是 SS/VMess/Trojan 协议，Python requests 无法直接使用。需要：

1. **方案一：使用 Clash/V2Ray 本地客户端**
   - 启动 Clash/V2Ray，监听本地 HTTP 端口
   - 添加 `http://127.0.0.1:端口` 到代理配置

2. **方案二：使用 privoxy 转换**
   ```bash
   sudo apt install privoxy
   # 配置 privoxy 将 SOCKS5 转为 HTTP
   ```

3. **方案三：使用独立 HTTP 代理**
   - 购买或自建 HTTP/SOCKS5 代理
   - 直接添加到配置文件

## 定时任务

部署脚本已自动创建 systemd 定时器：

```bash
# 查看定时任务状态
systemctl list-timers crawl-cars.timer

# 手动运行一次
systemctl start crawl-cars.service

# 查看运行日志
journalctl -u crawl-cars.service -f

# 停止定时任务
sudo systemctl stop crawl-cars.timer
```

定时规则：
- 每天 02:00 和 14:00 运行
- 随机延迟 0-60 分钟
- 每次运行 2 小时，爬取 500 个车型

## 手动运行

```bash
cd ~/crawl_cars

# 运行一次完整流程
./run.sh

# 或分步运行
python3 test_autohome.py --step 1 --auto --time-limit 7200 --max-cars 500
python3 test_autohome.py --step 2
python3 test_autohome.py --step 3
python3 test_autohome.py --step 4
python3 test_autohome.py --step 5
python3 test_autohome.py --step 6
```

## 数据同步

数据会自动保存到本地，建议定期推送到 GitHub：

```bash
# 在 run.sh 中已包含自动 commit/push
# 或手动推送
git add -A
git commit -m "Update data"
git push
```

## Railway 部署

**定价**：
- Free: 30天试用，$5一次性额度（之后$1/月订阅费）
- Hobby: $5/月最低消费（包含$5每月额度）

**费用估算**：
- CPU: $0.00000772/vCPU/sec
- 内存: $0.00000386/GB/sec
- 每小时约: $0.04
- 每月16次×2小时 = $1.28

**结论**: $5额度足够，但需注意Free Plan只有30天试用期

**部署**：
```bash
# 1. 安装 Railway CLI
npm install -g @railway/cli

# 2. 登录
railway login

# 3. 初始化项目
railway init

# 4. 部署
railway up

# 5. 设置定时任务（需要Hobby Plan）
railway run cron "0 2 * * 1,4" python test_autohome.py --auto
```

## 费用估算

| 方案 | 月费用 | 说明 |
|------|--------|------|
| VPS (搬瓦工) | $3-5 | 最便宜，推荐 |
| VPS (Vultr) | $2.5-5 | 按小时计费 |
| Railway Free | $0 (30天), then $1 | $5试用额度够用1-2个月 |
| Railway Hobby | $5 | 包含$5额度，适合长期使用 |
| 自有服务器 | $0 | 已有 VPS 的话免费 |
