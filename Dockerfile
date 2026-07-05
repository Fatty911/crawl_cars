FROM python:3.12-alpine

LABEL maintainer="crawl_cars"
LABEL description="汽车数据爬虫 - 集成Mihomo代理"

# 安装系统依赖
RUN apk add --no-cache \
    chromium \
    chromium-chromedriver \
    git \
    bash \
    curl \
    tzdata \
    ca-certificates

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装 Mihomo (Clash.Meta) - 使用compatible版本以支持更多CPU
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then MIHOMO_ARCH="amd64-compatible"; \
    elif [ "$ARCH" = "aarch64" ]; then MIHOMO_ARCH="arm64"; \
    else echo "Unsupported architecture: $ARCH" && exit 1; fi && \
    curl -L -o /tmp/mihomo.gz "https://github.com/MetaCubeX/mihomo/releases/download/v1.19.20/mihomo-linux-${MIHOMO_ARCH}-v1.19.20.gz" && \
    gunzip /tmp/mihomo.gz && \
    mv /tmp/mihomo /usr/local/bin/mihomo && \
    chmod +x /usr/local/bin/mihomo && \
    ln -s /usr/local/bin/mihomo /usr/local/bin/clash

# 创建Clash配置目录
RUN mkdir -p /root/.config/mihomo

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置Chromium环境变量
ENV CHROME_BIN=/usr/bin/chromium-browser
ENV CHROMIUM_FLAGS="--no-sandbox --disable-gpu --disable-dev-shm-usage"

# 复制代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/html /app/newhtml /app/json /app/content /app/newjson /app/exception /app/dongchedi

# 设置权限
RUN chmod +x /app/*.sh 2>/dev/null || true

# 默认命令
CMD ["python", "scripts/test_autohome.py"]
