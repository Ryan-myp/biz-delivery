#!/bin/bash
# 停止守护进程

pkill -f "watcher.sh" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ 守护进程已停止"
else
    echo "⚠️  守护进程未运行"
fi
