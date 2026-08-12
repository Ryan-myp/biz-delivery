#!/usr/bin/env python3
"""PRD 审查演示脚本

演示如何使用 biz-delivery 进行 PRD 审查。
"""

import json
import sys
from pathlib import Path

# 添加 scripts 到路径
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from review_engine import ReviewEngine


def demo_review():
    """演示 PRD 审查流程"""
    
    print("=" * 60)
    print("  biz-delivery PRD 审查演示")
    print("=" * 60)
    print()
    
    # 示例 PRD
    sample_prd = """
# 素材批量审核功能优化

## 背景
当前素材审核流程支持单个素材审核，效率较低。
本需求旨在优化批量审核功能，提升运营效率。

## 需求描述
1. 支持一次性选择多个素材进行批量审核
2. 批量审核结果通过消息队列异步通知
3. 审核结果写入数据库，支持查询历史记录
4. 新增审核历史记录查询接口

## 业务流程
1. 用户选择多个素材 ID
2. 系统批量验证素材状态
3. 调用审核服务进行处理
4. 通过 MQ 推送审核结果
5. 更新数据库中的素材状态
6. 返回审核结果给前端

## 数据变更
- 新增审核历史记录表 audit_history
- Creative 表新增 batch_id 字段
- 删除 Creative 表的 old_status 字段（已废弃）

## 性能要求
- 支持每秒 1000 次并发审核请求
- 批量审核单次最多支持 100 个素材
"""
    
    print("【输入】PRD 内容预览:")
    print("-" * 60)
    print(sample_prd[:500] + "...")
    print()
    
    # 模拟 IR 数据（实际使用时从 learn_repo 获取）
    sample_ir = {
        "functions": [
            {"name": "ReviewCreative", "file": "review.go", "signature": "ctx, req *ReviewRequest"},
            {"name": "BatchReview", "file": "batch_review.go", "signature": "ctx, req *BatchReviewRequest"},
            {"name": "GetAuditHistory", "file": "audit.go", "signature": "ctx, req *HistoryRequest"},
            {"name": "SaveToDB", "file": "db.go", "signature": "ctx, data *Creative"},
            {"name": "PublishMQ", "file": "mq.go", "signature": "ctx, topic, msg"},
        ],
        "routes": [
            {"path": "/api/review", "method": "POST", "handler": "ReviewCreative"},
            {"path": "/api/batch-review", "method": "POST", "handler": "BatchReview"},
            {"path": "/api/audit/history", "method": "GET", "handler": "GetAuditHistory"},
        ],
        "structs": [
            {"name": "Creative", "fields": ["ID", "URL", "Type", "Status", "CreatedAt"]},
            {"name": "ReviewRequest", "fields": ["CreativeID", "Result", "Remark"]},
        ],
        "entity_tables": [
            {"entity": "Creative", "table": "creatives"},
        ],
        "error_codes": [
            {"name": "CREATIVE_NOT_FOUND", "code": "2001"},
            {"name": "REVIEW_FAILED", "code": "2002"},
        ],
        "core_flows": [
            {
                "flow_name": "素材审核",
                "entry_point": "ReviewCreative",
                "call_chain": ["ReviewCreative", "ValidateCreative", "SaveToDB"],
            }
        ]
    }
    
    sample_profile = {
        "business_domain": "creative-platform",
        "modules": [
            {
                "name": "Creative / 素材",
                "keywords": ["creative", "素材", "review", "审核"],
                "goal": "素材的审核、发布、分享"
            },
            {
                "name": "MQ / 消息队列",
                "keywords": ["mq", "kafka", "消息", "队列"],
                "goal": "异步消息处理"
            }
        ]
    }
    
    print("【分析】PRD 审查结果:")
    print("-" * 60)
    
    # 这里只是演示，实际需要使用 ReviewEngine
    issues = []
    
    # 1. 检查缺失的实体
    prd_entities = ["audit_history", "batch_id", "old_status"]
    code_entities = ["Creative", "ReviewRequest"]
    missing_entities = [e for e in prd_entities if e not in code_entities]
    if missing_entities:
        issues.append({
            "severity": "HIGH",
            "type": "missing_entity",
            "message": f"PRD 提到的实体在代码中未找到: {', '.join(missing_entities)}"
        })
    
    # 2. 检查接口缺失
    prd_routes = ["/api/audit/history"]
    code_routes = ["/api/review", "/api/batch-review"]
    missing_routes = [r for r in prd_routes if r not in code_routes]
    if missing_routes:
        issues.append({
            "severity": "MEDIUM",
            "type": "missing_route",
            "message": f"PRD 提到的路由在代码中未实现: {', '.join(missing_routes)}"
        })
    
    # 3. 检查数据变更风险
    issues.append({
        "severity": "CRITICAL",
        "type": "breaking_change",
        "message": "PRD 要求删除 Creative 表的 old_status 字段，但未确认该字段是否仍被使用"
    })
    
    # 4. 检查性能需求
    issues.append({
        "severity": "HIGH",
        "type": "performance_risk",
        "message": "PRD 要求支持 1000 QPS 并发审核，但代码中未发现限流/降级机制"
    })
    
    # 5. 检查跨模块影响
    issues.append({
        "severity": "MEDIUM",
        "type": "cross_module",
        "message": "批量审核涉及 Creative 模块和 MQ 模块，需评估跨模块协调方案"
    })
    
    # 输出结果
    for i, issue in enumerate(issues, 1):
        severity_color = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(issue["severity"], "⚪")
        print(f"{severity_color} [{issue['severity']}] {issue['message']}")
    
    print()
    print("=" * 60)
    print("【总结】发现 {} 个问题".format(len(issues)))
    print("  - CRITICAL: {}".format(len([i for i in issues if i['severity'] == 'CRITICAL'])))
    print("  - HIGH: {}".format(len([i for i in issues if i['severity'] == 'HIGH'])))
    print("  - MEDIUM: {}".format(len([i for i in issues if i['severity'] == 'MEDIUM'])))
    print("=" * 60)


if __name__ == "__main__":
    demo_review()
