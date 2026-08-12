#!/bin/bash
# 触发优化通知（仅创建通知文件，不执行优化）
# 由 cron 调用，pi agent 扩展负责执行

NOTIFY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../listener/notifications" && pwd)"
LOG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../logs" && pwd)"
LOG_FILE="$LOG_DIR/trigger-$(date +%Y%m%d).log"

mkdir -p "$NOTIFY_DIR"
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 生成唯一通知 ID
NOTIFY_ID="biz-delivery-$(date +%s)"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 检测需要优化的项
OPPORTUNITIES=()

# 检查 PRD Review 规则数量
RULES_COUNT=$(grep -c '"name":' /Users/yanping.ma/biz-delivery/skills/prd_review/review_skill.py 2>/dev/null || echo 0)
if [ "$RULES_COUNT" -lt 20 ]; then
    OPPORTUNITIES+=("扩展PRD Review规则到20条")
fi

# 检查测试文件数量
TEST_COUNT=$(find /Users/yanping.ma/biz-delivery/tests -name "test_*.py" 2>/dev/null | wc -l | tr -d ' ')
if [ "$TEST_COUNT" -lt 20 ]; then
    OPPORTUNITIES+=("补充测试用例到20个文件")
fi

# 检查模板数量
TEMPLATE_COUNT=$(find /Users/yanping.ma/biz-delivery/templates -name "*.j2" 2>/dev/null | wc -l | tr -d ' ')
if [ "$TEMPLATE_COUNT" -lt 3 ]; then
    OPPORTUNITIES+=("添加更多语言模板")
fi

# 创建通知文件
if [ ${#OPPORTUNITIES[@]} -gt 0 ]; then
    # 构建 opportunities JSON 数组
    OPP_json=""
    for i in "${!OPPORTUNITIES[@]}"; do
        if [ $i -gt 0 ]; then
            OPP_json="$OPP_json,"
        fi
        OPP_json="$OPP_json
        \"${OPPORTUNITIES[$i]}\""
    done
    
    cat > "$NOTIFY_DIR/${NOTIFY_ID}.json" << NOTIFY_EOF
{
    "id": "$NOTIFY_ID",
    "type": "hourly",
    "timestamp": "$TIMESTAMP",
    "message": "biz-delivery 智能优化代理检测到优化机会",
    "opportunities": [$OPP_json
    ],
    "action": "run_optimize_agent"
}
NOTIFY_EOF
    
    log "✅ 创建通知: $NOTIFY_ID (${#OPPORTUNITIES[@]} 个机会)"
    echo "📬 已创建优化通知: $NOTIFY_ID"
else
    log "ℹ️  无优化机会"
    echo "✅ 暂无优化机会"
fi
