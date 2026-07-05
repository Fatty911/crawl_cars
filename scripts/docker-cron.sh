#!/bin/bash
# Docker 容器内的定时任务脚本

set -e

echo "Starting crawl scheduler..."

# 配置参数
RUN_TIME=${RUN_TIME:-7200}
MAX_CARS=${MAX_CARS:-500}

# 随机延迟函数
random_delay() {
    local max_minutes=$1
    local delay=$((RANDOM % (max_minutes * 60)))
    echo "$(date): Waiting $((delay / 60)) minutes before starting..."
    sleep $delay
}

# 主循环
while true; do
    CURRENT_HOUR=$(date +%H)
    CURRENT_DOW=$(date +%u)  # 1=周一, 7=周日
    CURRENT_MIN=$(date +%M)
    
    echo "$(date): Checking schedule... Hour=$CURRENT_HOUR, Day=$CURRENT_DOW"
    
    # 周一、周四 2:00 运行汽车之家
    if [ $CURRENT_DOW -eq 1 ] || [ $CURRENT_DOW -eq 4 ]; then
        if [ $CURRENT_HOUR -eq 2 ] && [ $CURRENT_MIN -lt 60 ]; then
            random_delay 60
            echo "$(date): Running Autohome crawler..."
            python test_autohome.py --auto --time-limit $RUN_TIME --max-cars $MAX_CARS || true
            
            # 运行后续步骤
            if [ -f step1_done ]; then
                echo "$(date): Running Autohome remaining steps..."
                python test_autohome.py --step 2 || true
                python test_autohome.py --step 3 || true
                python test_autohome.py --step 4 || true
                python test_autohome.py --step 5 || true
                python test_autohome.py --step 6 || true
            fi
        fi
    fi
    
    # 周二、周五 2:00 运行懂车帝
    if [ $CURRENT_DOW -eq 2 ] || [ $CURRENT_DOW -eq 5 ]; then
        if [ $CURRENT_HOUR -eq 2 ] && [ $CURRENT_MIN -lt 60 ]; then
            random_delay 60
            echo "$(date): Running Dongchedi crawler..."
            python crawl_dongchedi.py --step 1 --auto --time-limit $RUN_TIME || true
            python crawl_dongchedi.py --step 2 --auto --time-limit $RUN_TIME --max-series $MAX_CARS || true
            
            # 运行后续步骤
            if [ -f dcd_step2_done ]; then
                echo "$(date): Running Dongchedi remaining steps..."
                python crawl_dongchedi.py --step 3 || true
                python crawl_dongchedi.py --step 4 || true
            fi
        fi
    fi
    
    # 周三、周六 3:00 合并数据
    if [ $CURRENT_DOW -eq 3 ] || [ $CURRENT_DOW -eq 6 ]; then
        if [ $CURRENT_HOUR -eq 3 ] && [ $CURRENT_MIN -lt 60 ]; then
            random_delay 30
            echo "$(date): Merging data..."
            python merge_data.py || true
        fi
    fi
    
    # 每小时检查一次
    sleep 3600
done
