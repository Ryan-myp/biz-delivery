#!/usr/bin/env python3
"""RRF 融合模块 — Reciprocal Rank Fusion 算法实现

支持多路搜索结果融合，基于排名加权融合分数。

Usage:
    from scripts.query.rrf_fusion import rrf_fuse, rrf_fuse_multi_source
"""

from typing import Dict, List
from functools import lru_cache


# ──────────────────────────────────────────────
# RRF Constants
# ──────────────────────────────────────────────

_RRF_K_DEFAULT = 60
_RRF_K_BY_SOURCE = {
    "code": 40,
    "api_docs": 50,
    "schema": 45,
    "business": 55,
    "semantic": 60,
    "bm25": 55,
    "wiki": 70,
    "cache": 65,
    "markdown": 70,
    "entity": 60,
    "relation": 55,
}

# Source type weight mapping
SOURCE_WEIGHTS = {
    "code": 1.5,
    "api_docs": 1.2,
    "schema": 1.0,
    "business": 0.8,
    "wiki": 0.9,
    "semantic": 0.85,
    "bm25": 0.85,
}


# ──────────────────────────────────────────────
# Core RRF Functions
# ──────────────────────────────────────────────

def _get_rrf_k_for_label(label: str) -> int:
    """根据路径标签确定 RRF k 值"""
    if not label:
        return _RRF_K_DEFAULT
    
    label_lower = label.lower()
    for source_type, k_val in _RRF_K_BY_SOURCE.items():
        if source_type in label_lower:
            return k_val
    
    # 启发式匹配：根据路径关键词选择最合适的 k 值
    if any(kw in label_lower for kw in ['code', 'function', 'route', 'handler']):
        return _RRF_K_BY_SOURCE["code"]
    elif any(kw in label_lower for kw in ['api', 'doc']):
        return _RRF_K_BY_SOURCE["api_docs"]
    elif any(kw in label_lower for kw in ['schema', 'table', 'struct', 'column']):
        return _RRF_K_BY_SOURCE["schema"]
    elif any(kw in label_lower for kw in ['business', 'logic', 'flow']):
        return _RRF_K_BY_SOURCE["business"]
    elif any(kw in label_lower for kw in ['semantic', 'similarity', 'tfidf']):
        return _RRF_K_BY_SOURCE["semantic"]
    elif any(kw in label_lower for kw in ['bm25']):
        return _RRF_K_BY_SOURCE["bm25"]
    elif any(kw in label_lower for kw in ['wiki', 'knowledge', 'md']):
        return _RRF_K_BY_SOURCE["wiki"]
    
    return _RRF_K_DEFAULT


def _get_source_weight(item: Dict) -> float:
    """根据证据来源/类型获取权重"""
    stype = item.get("source_type", "") or item.get("type", "") or ""
    for key, weight in SOURCE_WEIGHTS.items():
        if key in str(stype).lower():
            return weight
    return 1.0


@lru_cache(maxsize=128)
def _rrf_k_choices():
    """缓存 k 值选项（无参数的辅助函数，避免 lru_cache 作用于不可哈希参数）"""
    return _RRF_K_BY_SOURCE


def rrf_fuse(candidates: List[List[Dict]], k: int = _RRF_K_DEFAULT) -> List[Dict]:
    """RRF 融合多路结果 — 基础版
    
    基于 Reciprocal Rank Fusion 算法，融合多个搜索结果列表。
    
    Args:
        candidates: 多个搜索结果的列表，每个结果是 dict 列表
        k: RRF 常数，默认 60
        
    Returns:
        融合后的排序结果列表
    """
    if not candidates:
        return []
    
    # Collect all unique items with their ranks
    item_scores: Dict[str, Dict] = {}
    
    for i, result_list in enumerate(candidates):
        if not result_list:
            continue
        for rank, item in enumerate(result_list, 1):
            # Use a unique key for each item
            item_id = f"{i}:{item.get('id', item.get('path', item.get('name', str(rank))))}"
            
            if item_id not in item_scores:
                item_scores[item_id] = {
                    'item': item,
                    'score': 0.0,
                    'rrf_score': 0.0,
                    'sources': set(),
                    'rank': rank,
                }
            
            # RRF contribution
            source_key = item.get('source', item.get('label', ''))
            source_k = _get_rrf_k_for_label(source_key)
            rrf_contribution = 1.0 / (source_k + rank)
            
            item_scores[item_id]['score'] += item.get('score', 0.0)
            item_scores[item_id]['rrf_score'] += rrf_contribution
            item_scores[item_id]['sources'].add(source_key if source_key else f"source_{i}")
    
    # Sort by RRF score
    sorted_items = sorted(
        item_scores.values(),
        key=lambda x: x['rrf_score'],
        reverse=True
    )
    
    # Convert to output format
    result = []
    for entry in sorted_items[:len(candidates[0]) if candidates else 0]:
        item = entry['item'].copy()
        item['score'] = round(entry['score'], 6)
        item['rrf_score'] = round(entry['rrf_score'], 6)
        item['sources'] = list(entry['sources'])
        result.append(item)
    
    return result


def rrf_fuse_multi_source(
    candidates: List[List[Dict]],
    k: int = _RRF_K_DEFAULT,
    use_source_weight: bool = True
) -> List[Dict]:
    """RRF 融合多路结果 — 增强版（支持 source_type 加权）
    
    改进：
    1. 使用 (type, title) 作为去重键，比纯 path 更精确
    2. 保留各路的 source 标签
    3. 融合分数 = RRF rank + 原始 score 加权
    4. **source_type 加权**: code=1.5, api_docs=1.2, schema=1.0, business=0.8
       代码匹配（function/route）应比 schema/business 匹配权重更高
    """
    if not candidates:
        return []
    
    ranked: Dict[tuple, Dict] = {}
    
    for i, path_results in enumerate(candidates):
        if not path_results:
            continue
        for rank, item in enumerate(path_results, 1):
            # 使用 type+title 作为去重键
            item_type = item.get('type', '')
            item_title = item.get('title', '') or item.get('name', '')
            key = (item_type, item_title)
            
            if key not in ranked:
                ranked[key] = {
                    'type': item_type,
                    'title': item_title,
                    'path': item.get('path', ''),
                    'line': item.get('line', 0),
                    'content': item.get('content', ''),
                    'score': 0.0,
                    'sources': set(),
                    'original_score': 0.0,
                }
            
            entry = ranked[key]
            entry['sources'].add(item.get('source', 'unknown'))
            
            # RRF 排名分 × source_type 权重
            w = _get_source_weight(item) if use_source_weight else 1.0
            rank_score = w * 1.0 / (k + rank)
            
            # 原始分数加权
            orig_score = item.get('score', 0.0)
            entry['score'] += rank_score * 0.6 + orig_score * 0.4
            entry['original_score'] = max(entry['original_score'], orig_score)
    
    # Sort by score
    sorted_items = sorted(ranked.values(), key=lambda x: x['score'], reverse=True)
    
    # Convert to output format
    result = []
    for item in sorted_items[:10]:
        result.append({
            'type': item['type'],
            'title': item['title'],
            'path': item['path'],
            'line': item.get('line', 0),
            'content': item['content'],
            'score': round(item['score'], 4),
            'sources': list(item['sources']),
        })
    
    return result


# ──────────────────────────────────────────────
# Convenience Functions
# ──────────────────────────────────────────────

def fuse_results(*result_lists: List[Dict], k: int = _RRF_K_DEFAULT) -> List[Dict]:
    """便捷函数：融合多个结果列表
    
    Args:
        *result_lists: 可变数量的结果列表
        k: RRF 常数
        
    Returns:
        融合后的结果列表
    """
    return rrf_fuse(list(result_lists), k)


def fuse_weighted_results(*result_lists: List[Dict], k: int = _RRF_K_DEFAULT) -> List[Dict]:
    """便捷函数：融合多个结果列表（支持 source 加权）
    
    Args:
        *result_lists: 可变数量的结果列表
        k: RRF 常数
        
    Returns:
        融合后的结果列表
    """
    return rrf_fuse_multi_source(list(result_lists), k)


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # 简单测试
    candidates = [
        [{"name": "A", "score": 0.9, "type": "function"}],
        [{"name": "B", "score": 0.8, "type": "route"}],
    ]
    result = rrf_fuse(candidates)
    print(f"RRF fusion result: {len(result)} items")
    for r in result:
        print(f"  {r['name']}: rrf={r['rrf_score']:.4f}")
    
    result = rrf_fuse_multi_source(candidates)
    print(f"\nWeighted fusion result: {len(result)} items")
    for r in result:
        print(f"  {r.get('title', r.get('name', ''))}: score={r['score']:.4f}")
