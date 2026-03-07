FROM python:3.12-alpine

LABEL maintainer="crawl_cars"
LABEL description="汽车数据爬虫"

# 安装系统依赖
RUN apk add --no-cache \
    chromium \
    chromium-chromedriver \
    git \
    bash \
    curl \
    tzdata

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

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
CMD ["python", "test_autohome.py"]
