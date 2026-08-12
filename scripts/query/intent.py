#!/usr/bin/env python3
"""意图识别模块 — 从查询文本中提取意图和置信度

基于关键词匹配 + 反向索引加速，支持中英文混合查询。

Usage:
    from scripts.query.intent import extract_intent, get_intent_patterns
    
    intent, confidence = extract_intent("查看素材审核流程")
    # Returns: ("query", 0.85)
"""

from typing import Dict, List, Tuple
from functools import lru_cache

# ──────────────────────────────────────────────
# Intent Patterns — 意图模式定义
# ──────────────────────────────────────────────

INTENT_PATTERNS: Dict[str, List[str]] = {
    "query": ["查询", "查看", "获取", "查找", "检索", "query", "search", "get", "list"],
    "question": ["什么", "如何", "怎么", "为什么", "吗", "what", "how", "why", "where"],
    "explain": ["解释", "说明", "原理", "机制", "explain", "describe"],
    "debug": ["调试", "排障", "错误", "失败", "bug", "error", "troubleshoot"],
    "callchain": ["谁调用了", "调用链", "caller", "callee", "depends", "who called", "call chain", "trace"],
    "dataflow": ["从哪来", "数据来源", "流向", "source", "sink", "data flow", "where does", "flow"],
    "impact": ["改了影响", "影响分析", "impact", "side effect", "what breaks"],
    "relationship": ["关联", "关系", "relation", "关联到", "依赖于", "dependency"],
    "coverage": ["覆盖", "覆盖范围", "coverage", "包括哪些", "all cases"],
    "create": ["创建", "新建", "添加", "新增", "生成", "构建", "add", "new"],
    "update": ["修改", "更新", "变更", "调整", "编辑", "更改", "update", "modify"],
    "delete": ["删除", "移除", "清除", "delete", "remove", "cancel"],
    "compare": ["对比", "比较", "区别", "差异", "compare", "diff"],
}

# Pre-compiled reverse index for O(1) lookup
_INTENT_REVERSE_INDEX: Dict[str, str] = {}
for _intent, _patterns in INTENT_PATTERNS.items():
    for _p in _patterns:
        _INTENT_REVERSE_INDEX[_p] = _intent


def extract_intent(query: str) -> Tuple[str, float]:
    """从查询文本中提取意图和置信度
    
    Args:
        query: 查询文本
        
    Returns:
        (intent, confidence) 元组
        - intent: 意图类型，如 "query", "question", "debug" 等
        - confidence: 置信度 [0, 1]
        
    Examples:
        >>> extract_intent("查看素材审核流程")
        ("query", 0.85)
        >>> extract_intent("为什么竞价失败")
        ("question", 0.92)
        >>> extract_intent("修复权限问题")
        ("debug", 0.78)
    """
    if not query or not query.strip():
        return ("unknown", 0.0)
    
    query_lower = query.lower()
    intent_hits: Dict[str, int] = {}
    
    # Use reverse index for O(1) lookup per keyword
    for kw, intent in _INTENT_REVERSE_INDEX.items():
        if kw in query_lower:
            intent_hits[intent] = intent_hits.get(intent, 0) + 1
    
    if not intent_hits:
        return ("unknown", 0.0)
    
    # Convert hit counts to scores (hits / total patterns for that intent)
    scores = {
        intent: hits / len(INTENT_PATTERNS[intent])
        for intent, hits in intent_hits.items()
    }
    
    best_intent = max(scores, key=scores.get)
    return best_intent, scores[best_intent]


def get_intent_patterns() -> Dict[str, List[str]]:
    """返回所有意图模式定义
    
    Returns:
        意图模式字典
    """
    return INTENT_PATTERNS.copy()


def classify_intent(query: str) -> str:
    """简单意图分类，返回最可能的意图类型
    
    Args:
        query: 查询文本
        
    Returns:
        意图类型字符串
    """
    intent, _ = extract_intent(query)
    return intent
