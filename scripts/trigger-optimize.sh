#!/bin/bash
# ============================================================
# biz-delivery 智能优化触发脚本
# 功能: 创建触发文件供 Pi 扩展检测
# ============================================================

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRIGGER_DIR="$REPO_DIR/listener/triggers"
LOG_FILE="$REPO_DIR/logs/cron-trigger.log"

mkdir -p "$TRIGGER_DIR"
mkdir -p "$(dirname $LOG_FILE)"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🚀 biz-delivery 优化触发"

# 创建触发文件
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
cat > "$TRIGGER_DIR/optimize-$TIMESTAMP.json" << INNER_EOF
{
    "type": "hourly",
    "message": "biz-delivery 智能优化任务",
    "timestamp": "$(date -Iseconds)",
    "triggered_by": "cron",
    "auto_execute": true
}
INNER_EOF

log "✅ 触发文件已创建: optimize-$TIMESTAMP.json"
log "📝 日志文件: $LOG_FILE"
log "=========================================="
