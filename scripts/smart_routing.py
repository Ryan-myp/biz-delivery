#!/usr/bin/env python3
"""意图识别 + 路由模块 - 增强查询意图理解"""

from typing import Tuple, Optional, Dict, List
try:
    from query_cache import QueryCache
except ImportError:
    from .query_cache import QueryCache

INTENT_PATTERNS = {
    "create": ["创建", "新建", "添加", "新增", "生成", "构建", "add", "new"],
    "update": ["修改", "更新", "变更", "调整", "编辑", "更改", "update", "modify", "edit"],
    "query": ["查询", "查看", "获取", "查找", "检索", "显示", "query", "search", "get", "list"],
    "delete": ["删除", "移除", "清除", "delete", "remove", "cancel"],
    "sync": ["同步", "数据同步", "回流", "sync", "syncing"],
    "config": ["配置", "设置", "参数", "选项", "config", "setting", "parameter"],
    "question": ["什么", "如何", "怎么", "为什么", "吗", "what", "how", "why", "where"],
    "explain": ["解释", "说明", "原理", "机制", "explain", "describe", "how it works"],
    "debug": ["调试", "排障", "错误", "问题", "失败", "bug", "error", "fix", "troubleshoot"],
    "optimize": ["优化", "性能", "效率", "optimize", "performance", "improve"],
    "review": ["评审", "审核", "检查", "review", "audit", "inspect"],
    "compare": ["对比", "比较", "区别", "差异", "compare", "diff", "difference"],
    "migrate": ["迁移", "升级", "转换", "migrate", "upgrade", "convert"],
    "integrate": ["集成", "对接", "连接", "integrate", "connect", "bridge"],
    "callchain": ["谁调用了", "调用链", "caller", "callee", "depends on", "depends_on"],
    "dataflow": ["从哪来", "数据来源", "流向", "source", "sink", "data flow"],
    "impact": ["改了影响", "影响分析", "impact", "side effect", "what breaks"],
}

# 意图 → 查询类型映射
INTENT_TO_QUERY_TYPE = {
    "create": "code",
    "update": "code",
    "query": "api_docs",
    "delete": "code",
    "sync": "schema",
    "config": "api_docs",
    "question": "api_docs",
    "explain": "code",
    "debug": "code",
    "optimize": "code",
    "review": "api_docs",
    "compare": "api_docs",
    "migrate": "schema",
    "integrate": "code",
    "callchain": "callgraph",  # 调用图查询
    "dataflow": "dataflow",    # 数据流查询
    "impact": "impact",        # 影响分析查询
}

# 范围权重 - 每个意图对应不同 scope 的权重
SCOPE_WEIGHTS = {
    "create": {"code": 0.8, "api_docs": 0.6, "schema": 0.4, "callgraph": 0.3, "dataflow": 0.3},
    "update": {"code": 0.8, "api_docs": 0.5, "schema": 0.5, "callgraph": 0.4, "dataflow": 0.3},
    "query": {"code": 0.6, "api_docs": 0.8, "schema": 0.7, "callgraph": 0.2, "dataflow": 0.3},
    "delete": {"code": 0.7, "api_docs": 0.5, "schema": 0.4, "callgraph": 0.3, "dataflow": 0.2},
    "sync": {"code": 0.8, "api_docs": 0.5, "schema": 0.8, "callgraph": 0.4, "dataflow": 0.7},
    "config": {"code": 0.5, "api_docs": 0.8, "schema": 0.6, "callgraph": 0.2, "dataflow": 0.3},
    "question": {"code": 0.5, "api_docs": 0.8, "schema": 0.6, "callgraph": 0.3, "dataflow": 0.3},
    "explain": {"code": 0.7, "api_docs": 0.8, "schema": 0.5, "callgraph": 0.5, "dataflow": 0.4},
    "debug": {"code": 0.9, "api_docs": 0.6, "schema": 0.7, "callgraph": 0.7, "dataflow": 0.6},
    "optimize": {"code": 0.9, "api_docs": 0.5, "schema": 0.7, "callgraph": 0.4, "dataflow": 0.5},
    "review": {"code": 0.6, "api_docs": 0.7, "schema": 0.5, "callgraph": 0.4, "dataflow": 0.4},
    "compare": {"code": 0.5, "api_docs": 0.7, "schema": 0.5, "callgraph": 0.3, "dataflow": 0.5},
    "migrate": {"code": 0.8, "api_docs": 0.6, "schema": 0.8, "callgraph": 0.3, "dataflow": 0.7},
    "integrate": {"code": 0.7, "api_docs": 0.8, "schema": 0.6, "callgraph": 0.5, "dataflow": 0.4},
    "callchain": {"code": 0.6, "api_docs": 0.3, "schema": 0.2, "callgraph": 0.9, "dataflow": 0.2},
    "dataflow": {"code": 0.5, "api_docs": 0.3, "schema": 0.7, "callgraph": 0.3, "dataflow": 0.9},
    "impact": {"code": 0.7, "api_docs": 0.3, "schema": 0.4, "callgraph": 0.8, "dataflow": 0.6},
}


def extract_intent(query: str) -> Tuple[str, float]:
    """从查询文本中提取意图和置信度"""
    query_lower = query.lower()
    scores = {}
    
    for intent, patterns in INTENT_PATTERNS.items():
        score = sum(1 for pattern in patterns if pattern.lower() in query_lower)
        if score > 0:
            # 考虑模式长度 - 长模式更精确
            avg_pattern_len = sum(len(p) for p in patterns) / len(patterns)
            normalized_score = score / len(patterns) * (avg_pattern_len / 10)
            scores[intent] = min(normalized_score, 1.0)
    
    if not scores:
        return ("unknown", 0.0)
    
    max_intent = max(scores, key=scores.get)
    return (max_intent, scores[max_intent])


def get_scope_weights(intent: str) -> Dict[str, float]:
    """获取意图对应的范围权重"""
    return SCOPE_WEIGHTS.get(intent, {"code": 0.7, "api_docs": 0.7, "schema": 0.6, "callgraph": 0.4, "dataflow": 0.4})


def get_query_type(intent: str) -> str:
    """获取意图对应的查询类型"""
    return INTENT_TO_QUERY_TYPE.get(intent, "code")


def select_scopes(query: str, available_scopes: List[str], top_n: int = 3) -> List[str]:
    """基于意图选择最佳 scope 组合"""
    intent, confidence = extract_intent(query)
    weights = get_scope_weights(intent)
    
    # 计算每个可用 scope 的得分
    scores = {}
    for scope in available_scopes:
        base_weight = weights.get(scope, 0.5)
        scores[scope] = base_weight * (0.5 + 0.5 * confidence)
    
    # 添加查询类型得分（如果是特殊查询类型）
    query_type = get_query_type(intent)
    if query_type in scores and query_type not in available_scopes:
        scores[query_type] = 0.8 * confidence
    
    # 排序返回 top_n
    sorted_scopes = sorted(scores.keys(), key=lambda s: scores[s], reverse=True)
    return sorted_scopes[:top_n]


class SmartRouter:
    """智能查询路由 - 结合意图识别、缓存和 scope 选择"""
    
    def __init__(self, cache_dir=None):
        self.cache = QueryCache(cache_dir) if cache_dir else None
    
    def route_query(self, query: str, available_scopes: List[str]) -> Tuple[List[str], dict]:
        """路由查询，返回 (选定的 scopes, 元数据)"""
        # 检查缓存
        if self.cache:
            key = f"{query}:{','.join(sorted(available_scopes))}"
            cached = self.cache.get(key, available_scopes)
            if cached:
                return cached["scopes"], {"from_cache": True}
        
        # 执行路由
        scopes = select_scopes(query, available_scopes)
        intent, confidence = extract_intent(query)
        
        # 缓存结果
        if self.cache:
            self.cache.set(key, available_scopes, {"scopes": scopes})
        
        return scopes, {
            "from_cache": False,
            "intent": intent,
            "confidence": confidence,
            "query_type": get_query_type(intent),
        }
