#!/bin/bash
# ============================================================
# biz-delivery 智能优化守护进程
# 功能: 每 10 秒检查通知文件，发现后自动执行优化
# ============================================================

NOTIFY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../listener/notifications" && pwd)"
LOG_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../logs/watcher.log"
PROCESS_DIR="$NOTIFY_DIR/processed"

mkdir -p "$PROCESS_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log "🚀 守护进程启动，监听目录: $NOTIFY_DIR"
log "📁 检查间隔: 10 秒"

while true; do
    # 查找待处理的通知文件
    NOTIFICATION_FILES=$(find "$NOTIFY_DIR" -name "*.json" ! -path "*/processed/*" 2>/dev/null | head -1)
    
    if [ -n "$NOTIFICATION_FILES" ]; then
        NOTIFICATION_FILE=$(echo "$NOTIFICATION_FILES" | tr -d '[:space:]')
        log "📬 发现通知文件: $NOTIFICATION_FILE"
        
        # 移动到处理目录
        mv "$NOTIFICATION_FILE" "$PROCESS_DIR/" 2>/dev/null
        
        # 执行优化
        log "⚡ 开始执行优化..."
        cd "$(dirname "${BASH_SOURCE[0]}")/.."
        python3 scripts/optimize_agent.py >> "$LOG_FILE" 2>&1
        
        if [ $? -eq 0 ]; then
            log "✅ 优化执行完成"
        else
            log "❌ 优化执行失败"
        fi
    fi
    
    # 等待 10 秒
    sleep 10
done
