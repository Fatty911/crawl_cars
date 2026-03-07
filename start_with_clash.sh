#!/bin/bash
# 代理启动脚本 - 启动Clash并设置环境变量

set -e

PROXY_CONFIG="/app/proxies.json"
CLASH_CONFIG="/root/.config/mihomo/config.yaml"
CLASH_DIR="/root/.config/mihomo"

echo "=== 代理启动脚本 ==="

# 检查proxies.json是否存在
if [ ! -f "$PROXY_CONFIG" ]; then
    echo "警告: proxies.json 不存在，跳过代理启动"
    echo "如需使用代理，请创建 proxies.json 并添加订阅"
    export PROXY_ENABLED=false
    exec "$@"
fi

# 检查是否有订阅
HAS_SUBSCRIPTION=$(python3 -c "
import json
try:
    with open('$PROXY_CONFIG') as f:
        config = json.load(f)
    subs = config.get('subscriptions', [])
    print('true' if subs else 'false')
except:
    print('false')
")

if [ "$HAS_SUBSCRIPTION" != "true" ]; then
    echo "警告: 没有配置订阅，跳过代理启动"
    echo "请使用以下命令添加订阅:"
    echo "  python proxy_manager.py --add-sub 'https://your-subscription-url'"
    export PROXY_ENABLED=false
    exec "$@"
fi

echo "检测到订阅配置，正在启动代理..."

# 创建Clash配置目录
mkdir -p "$CLASH_DIR"

# 生成Clash配置
echo "生成Clash配置..."
python3 /app/generate_clash_config.py \
    --subs $(python3 -c "
import json
with open('$PROXY_CONFIG') as f:
    config = json.load(f)
print(' '.join(config.get('subscriptions', [])))
") \
    --exclude $(python3 -c "
import json
with open('$PROXY_CONFIG') as f:
    config = json.load(f)
print(' '.join(config.get('exclude_keywords', [])))
") \
    --output "$CLASH_CONFIG" \
    --mixed-port 7890 \
    --socks-port 7891

if [ $? -ne 0 ]; then
    echo "错误: 生成Clash配置失败"
    export PROXY_ENABLED=false
    exec "$@"
fi

# 启动Clash
echo "启动Clash..."
mihomo -d "$CLASH_DIR" -f "$CLASH_CONFIG" &

# 等待Clash启动
sleep 3

# 检查Clash是否启动成功
if curl -s "http://127.0.0.1:9090/version" > /dev/null 2>&1; then
    echo "✓ Clash启动成功"
    echo "  HTTP代理: http://127.0.0.1:7890"
    echo "  SOCKS5代理: socks5://127.0.0.1:7891"
    echo "  API地址: http://127.0.0.1:9090"
    
    # 设置环境变量
    export HTTP_PROXY=http://127.0.0.1:7890
    export HTTPS_PROXY=http://127.0.0.1:7890
    export ALL_PROXY=socks5://127.0.0.1:7891
    export PROXY_ENABLED=true
    
    # 自动选择最快代理
    echo "自动选择最快代理..."
    python3 /app/proxy_manager.py --auto-select 2>/dev/null || true
else
    echo "✗ Clash启动失败"
    export PROXY_ENABLED=false
fi

echo "=== 代理设置完成 ==="
echo ""

# 执行传入的命令
exec "$@"
