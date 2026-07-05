#!/bin/bash
# VPS 一键部署脚本

set -e

echo "=== 汽车数据爬虫 VPS 部署 ==="

# 检测系统
if [ -f /etc/debian_version ]; then
    PKG_MANAGER="apt"
elif [ -f /etc/redhat-release ]; then
    PKG_MANAGER="yum"
else
    echo "不支持的系统"
    exit 1
fi

# 安装系统依赖
echo "[1/5] 安装系统依赖..."
if [ "$PKG_MANAGER" = "apt" ]; then
    sudo apt update
    sudo apt install -y python3 python3-pip git chromium-browser chromium-chromedriver
elif [ "$PKG_MANAGER" = "yum" ]; then
    sudo yum install -y python3 python3-pip git chromium chromium-driver
fi

# 安装 Python 依赖
echo "[2/5] 安装 Python 依赖..."
pip3 install --user requests beautifulsoup4 selenium lxml pyyaml

# 创建工作目录
WORK_DIR="$HOME/crawl_cars"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# 创建启动脚本
echo "[3/5] 创建启动脚本..."
cat > run.sh << 'EOF'
#!/bin/bash
cd "$HOME/crawl_cars"

# 配置参数
RUN_TIME=${RUN_TIME:-7200}
MAX_CARS=${MAX_CARS:-500}

# 运行汽车之家
echo "$(date) 开始爬取汽车之家..."
python3 test_autohome.py --step 1 --auto --time-limit $RUN_TIME --max-cars $MAX_CARS
EXIT_CODE=$?

if [ $EXIT_CODE -eq 10 ]; then
    echo "$(date) 汽车之家未完成，等待下次运行"
    git add -A
    git diff --staged --quiet || git commit -m "Progress: $(date +%Y%m%d_%H%M%S)"
    git push 2>/dev/null || true
elif [ $EXIT_CODE -eq 0 ]; then
    echo "$(date) 汽车之家第一步完成，运行后续步骤..."
    python3 test_autohome.py --step 2
    python3 test_autohome.py --step 3
    python3 test_autohome.py --step 4
    python3 test_autohome.py --step 5
    python3 test_autohome.py --step 6
fi

# 运行懂车帝
echo "$(date) 开始爬取懂车帝..."
python3 crawl_dongchedi.py --step 2 --auto --time-limit $RUN_TIME --max-series $MAX_CARS
EXIT_CODE=$?

if [ $EXIT_CODE -eq 10 ]; then
    echo "$(date) 懂车帝未完成，等待下次运行"
elif [ $EXIT_CODE -eq 0 ]; then
    echo "$(date) 懂车帝第二步完成，运行后续步骤..."
    python3 crawl_dongchedi.py --step 3
    python3 crawl_dongchedi.py --step 4
fi

# 合并数据
if [ -f autoHome_*.json ] && [ -f dongchedi_*.json ]; then
    echo "$(date) 合并数据..."
    python3 merge_data.py
    git add -A
    git commit -m "Data: $(date +%Y%m%d)"
    git push 2>/dev/null || true
fi

echo "$(date) 本次运行结束"
EOF
chmod +x run.sh

# 创建 systemd 服务
echo "[4/5] 创建 systemd 定时任务..."
sudo tee /etc/systemd/system/crawl-cars.service << EOF
[Unit]
Description=Crawl Cars Data
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORK_DIR
ExecStart=$WORK_DIR/run.sh
Restart=on-failure
RestartSec=300

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/crawl-cars.timer << EOF
[Unit]
Description=Crawl Cars Timer

[Timer]
OnCalendar=*-*-* 02:00:00
OnCalendar=*-*-* 14:00:00
RandomizedDelaySec=3600
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable crawl-cars.timer
sudo systemctl start crawl-cars.timer

# 创建代理配置示例
echo "[5/5] 创建代理配置示例..."
cat > proxies.json.example << 'EOF'
{
  "proxies": [
    {
      "name": "proxy1",
      "type": "http",
      "host": "127.0.0.1",
      "port": 7890,
      "username": null,
      "password": null
    }
  ],
  "stats": {}
}
EOF

echo ""
echo "=== 部署完成 ==="
echo ""
echo "使用方法:"
echo "  手动运行: ~/crawl_cars/run.sh"
echo "  查看定时: systemctl list-timers crawl-cars.timer"
echo "  查看日志: journalctl -u crawl-cars.service -f"
echo ""
echo "代理配置:"
echo "  1. 编辑 proxies.json 添加代理"
echo "  2. 或使用: python3 proxy_manager.py --sub '你的订阅链接'"
echo ""
