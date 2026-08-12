#!/usr/bin/env python3
"""Hook: 评审后处理

对 PRD 审查结果进行后处理，如提取关键信息、生成摘要等。

Usage:
    from hooks.post_review import post_review
    
    result = post_review(review_result, profile)
"""

from typing import Dict, List, Any


def post_review(review_result: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    """对审查结果进行后处理
    
    Args:
        review_result: 审查结果
        profile: 业务 Profile
        
    Returns:
        处理后的结果
    """
    processed = review_result.copy()
    
    # 1. 提取关键术语
    processed["keywords"] = extract_keywords(review_result)
    
    # 2. 生成执行摘要
    processed["summary"] = generate_summary(review_result)
    
    # 3. 识别风险等级
    processed["risk_level"] = assess_risk(review_result)
    
    return processed


def extract_keywords(review_result: Dict[str, Any]) -> List[str]:
    """从审查结果中提取关键词"""
    keywords = []
    
    # 从 P0 问题提取
    for issue in review_result.get("p0_issues", []):
        keywords.extend(issue.get("keywords", []))
    
    # 从 P1 问题提取
    for issue in review_result.get("p1_issues", []):
        keywords.extend(issue.get("keywords", []))
    
    return list(set(keywords))[:20]  # 最多返回 20 个关键词


def generate_summary(review_result: Dict[str, Any]) -> str:
    """生成审查摘要"""
    p0_count = len(review_result.get("p0_issues", []))
    p1_count = len(review_result.get("p1_issues", []))
    p2_count = len(review_result.get("p2_issues", []))
    
    if p0_count > 0:
        return f"审查发现 {p0_count} 个 P0 问题，{p1_count} 个 P1 问题，{p2_count} 个 P2 问题。需要先解决 P0 问题才能进入开发。"
    elif p1_count > 0:
        return f"审查发现 {p1_count} 个 P1 问题，{p2_count} 个 P2 问题。建议解决 P1 问题后再进入开发。"
    else:
        return f"审查通过，发现 {p2_count} 个建议改进项。可以进入开发阶段。"


def assess_risk(review_result: Dict[str, Any]) -> str:
    """评估风险等级"""
    p0_count = len(review_result.get("p0_issues", []))
    p1_count = len(review_result.get("p1_issues", []))
    
    if p0_count >= 3:
        return "high"
    elif p0_count >= 1 or p1_count >= 3:
        return "medium"
    else:
        return "low"
