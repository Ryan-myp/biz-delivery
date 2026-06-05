#!/usr/bin/env python3
"""RRF 融合查询引擎 - 多路查询 + 结果融合"""

from typing import Any, Dict, List, Tuple
from .smart_routing import SmartRouter, extract_intent


# RRF 融合参数
RRF_K = 60


def rrf_ranks(candidates: List[Dict[str, Any]], k: int = RRF_K) -> List[Dict[str, Any]]:
    """Reciprocal Rank Fusion 融合多个排序结果"""
    rank_scores = {}
    
    for result_list in candidates:
        for rank, item in enumerate(result_list):
            item_id = item.get("id") or str(item)
            if item_id not in rank_scores:
                rank_scores[item_id] = {"score": 0, "item": item, "sources": []}
            rank_scores[item_id]["score"] += 1.0 / (k + rank + 1)
            rank_scores[item_id]["sources"].append("query")
    
    # 排序
    ranked = sorted(
        rank_scores.values(),
        key=lambda x: x["score"],
        reverse=True,
    )
    
    return [r["item"] for r in ranked]


def multi_path_query(
    query: str,
    available_scopes: List[str],
    query_engine: callable,
    top_k: int = 10,
) -> Dict[str, Any]:
    """
    多路径查询 + RRF 融合
    
    根据意图识别，对不同类型的问题走不同的查询路径，
    然后用 RRF 融合结果。
    """
    router = SmartRouter()
    scopes, metadata = router.route_query(query, available_scopes)
    
    # 多路查询
    query_type = metadata.get("query_type", "code")
    candidates = []
    source_metadata = []
    
    # 执行每路查询
    for scope in scopes[:3]:  # 最多3路
        results = query_engine(query, scope=scope, top_k=top_k)
        candidates.append(results)
        source_metadata.append({"scope": scope, "count": len(results)})
    
    # RRF 融合
    if candidates:
        fused = rrf_ranks(candidates)
    else:
        fused = []
    
    intent, confidence = extract_intent(query)
    
    return {
        "query": query,
        "intent": intent,
        "confidence": confidence,
        "query_type": query_type,
        "scopes": scopes,
        "source_metadata": source_metadata,
        "results": fused[:top_k],
        "total_results": len(fused),
    }
