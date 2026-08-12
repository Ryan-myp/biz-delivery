#!/bin/bash
# ============================================================
# biz-delivery 智能优化触发脚本
# 功能: Cron 创建通知文件 + 直接执行优化（双保险）
# ============================================================

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NOTIFY_DIR="$REPO_DIR/listener/notifications"
LOG_FILE="$REPO_DIR/logs/cron-trigger.log"

mkdir -p "$NOTIFY_DIR"
mkdir -p "$(dirname $LOG_FILE)"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🚀 biz-delivery 优化触发"

# 创建通知文件
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
cat > "$NOTIFY_DIR/optimize-$TIMESTAMP.json" << INNER_EOF
{
    "type": "hourly",
    "message": "biz-delivery 智能优化任务",
    "timestamp": "$(date -Iseconds)",
    "triggered_by": "cron",
    "auto_execute": true
}
INNER_EOF

log "✅ 通知文件已创建: optimize-$TIMESTAMP.json"

# 直接执行优化（后台）
log "⚡ 开始执行优化..."
cd "$REPO_DIR"
python3 scripts/optimize_agent.py >> "$REPO_DIR/logs/cron-auto.log" 2>&1 &
OPTIMIZE_PID=$!

log "📝 优化进程 PID: $OPTIMIZE_PID"
log "📝 日志文件: $REPO_DIR/logs/cron-auto.log"
log "=========================================="
