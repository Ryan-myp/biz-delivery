#!/bin/bash
# 设置定时优化任务
# 每小时运行一次优化

CRON_CMD="0 * * * * cd /Users/yanping.ma/biz-delivery && python3 scripts/auto_optimize.py >> /tmp/biz-delivery-optimize.log 2>&1"

# 检查是否已存在
if crontab -l 2>/dev/null | grep -q "biz-delivery"; then
    echo "⚠️  定时任务已存在"
    exit 0
fi

# 添加新任务
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

echo "✅ 已设置每小时优化任务"
echo "   查看日志: tail -f /tmp/biz-delivery-optimize.log"
echo "   取消任务: crontab -e 并删除对应行"
