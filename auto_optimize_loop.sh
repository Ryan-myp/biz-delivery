#!/bin/bash
# 每小时自动运行优化代理（后台循环）

LOG_FILE="/tmp/biz-delivery-optimize-loop.log"
echo "[$(date)] 优化循环启动" >> "$LOG_FILE"

while true; do
    # 等待到下一个整点
    sleep_until_next_hour() {
        now=$(date +%s)
        next_hour=$(date -v+1H +%s)
        sleep $((next_hour - now))
    }
    
    sleep_until_next_hour
    echo "[$(date)] 开始执行优化..." >> "$LOG_FILE"
    
    # 执行优化
    cd /Users/yanping.ma/biz-delivery
    python3 scripts/optimize_agent.py >> "$LOG_FILE" 2>&1
    
    echo "[$(date)] 优化完成" >> "$LOG_FILE"
    
    # 等待 59 分钟后再次运行
    sleep 3540  # 59分钟
done
