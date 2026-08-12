#!/bin/bash
# 启动守护进程（后台运行）

WATCHER_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/listener/watcher.sh"
LOG_FILE="$HOME/.biz-delivery-watcher.log"

# 检查是否已运行
if pgrep -f "watcher.sh" > /dev/null; then
    echo "⚠️  守护进程已在运行"
    exit 0
fi

# 后台启动
nohup bash "$WATCHER_SCRIPT" > "$LOG_FILE" 2>&1 &
WATCHER_PID=$!

echo "✅ 守护进程已启动"
echo "   PID: $WATCHER_PID"
echo "   日志: $LOG_FILE"
echo "   监控目录: $(dirname "$WATCHER_SCRIPT")/notifications"
