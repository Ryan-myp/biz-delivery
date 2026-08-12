#!/usr/bin/env python3
"""多路查询引擎 — 融合代码、API文档、Schema、Wiki等多路搜索结果

Usage:
    from scripts.query.multi_path_query import run_multi_path_query
"""

from typing import Dict, List, Optional
from pathlib import Path
import json

from .intent import extract_intent
from .fuzzy_match import fuzzy_score
from .synonym_expansion import expand_synonyms


# RRF fusion constant
_RRF_K_DEFAULT = 60
_RRF_K_BY_SOURCE = {
    "code": 40,
    "api_docs": 50,
    "schema": 45,
    "business": 55,
    "semantic": 60,
    "bm25": 55,
    "wiki": 70,
}


def _get_rrf_k_for_label(label: str) -> int:
    """根据路径标签确定 RRF k 值"""
    if not label:
        return _RRF_K_DEFAULT
    
    label_lower = label.lower()
    for source_type, k_val in _RRF_K_BY_SOURCE.items():
        if source_type in label_lower:
            return k_val
    
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


def rrf_fuse(candidates: List[List[Dict]], k: int = _RRF_K_DEFAULT) -> List[Dict]:
    """Reciprocal Rank Fusion (RRF) 融合多个搜索结果
    
    Args:
        candidates: 多个搜索结果的列表，每个结果是 dict 列表
        k: RRF 常数，默认 60
        
    Returns:
        融合后的排序结果
    """
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
            rrf_contribution = 1.0 / (k + rank)
            
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
    for entry in sorted_items[:len(candidates[0])] if candidates else []:
        item = entry['item'].copy()
        item['score'] = round(entry['score'], 6)
        item['rrf_score'] = round(entry['rrf_score'], 6)
        item['sources'] = list(entry['sources'])
        result.append(item)
    
    return result


def search_code(ir_data: dict, queries: List[str], top_k: int = 10) -> List[Dict]:
    """在 IR 数据中搜索代码相关内容
    
    Args:
        ir_data: IR 文档数据
        queries: 查询词列表
        top_k: 返回数量
        
    Returns:
        搜索结果列表
    """
    results = []
    
    if not ir_data:
        return results
    
    # Search functions
    for func in ir_data.get('functions', []):
        if isinstance(func, dict):
            content = f"{func.get('name', '')} {func.get('signature', '')} {func.get('file', '')}"
            for q in queries:
                score = fuzzy_score(q.lower(), content.lower())
                if score > 0.3:
                    results.append({
                        'type': 'function',
                        'name': func.get('name', ''),
                        'file': func.get('file', ''),
                        'signature': func.get('signature', ''),
                        'score': round(score, 4),
                        'source': 'code_function',
                    })
                    break
    
    # Search routes
    for route in ir_data.get('routes', []):
        if isinstance(route, dict):
            content = f"{route.get('method', '')} {route.get('path', '')} {route.get('handler', '')}"
            for q in queries:
                score = fuzzy_score(q.lower(), content.lower())
                if score > 0.3:
                    results.append({
                        'type': 'route',
                        'path': route.get('path', ''),
                        'method': route.get('method', ''),
                        'handler': route.get('handler', ''),
                        'score': round(score, 4),
                        'source': 'code_route',
                    })
                    break
    
    # Search structs
    for struct in ir_data.get('structs', []):
        if isinstance(struct, dict):
            content = f"{struct.get('name', '')} {' '.join(str(f) for f in struct.get('fields', []))}"
            for q in queries:
                score = fuzzy_score(q.lower(), content.lower())
                if score > 0.3:
                    results.append({
                        'type': 'struct',
                        'name': struct.get('name', ''),
                        'fields': struct.get('fields', []),
                        'score': round(score, 4),
                        'source': 'code_struct',
                    })
                    break
    
    # Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]


def search_schema(ir_data: dict, queries: List[str], top_k: int = 10) -> List[Dict]:
    """在 IR 数据中搜索 Schema 相关内容
    
    Args:
        ir_data: IR 文档数据
        queries: 查询词列表
        top_k: 返回数量
        
    Returns:
        搜索结果列表
    """
    results = []
    
    if not ir_data:
        return results
    
    # Search entity tables
    for entity in ir_data.get('entity_tables', []):
        if isinstance(entity, dict):
            content = f"{entity.get('entity', '')} {entity.get('table', '')}"
            for q in queries:
                score = fuzzy_score(q.lower(), content.lower())
                if score > 0.3:
                    results.append({
                        'type': 'entity_table',
                        'entity': entity.get('entity', ''),
                        'table': entity.get('table', ''),
                        'score': round(score, 4),
                        'source': 'schema_entity',
                    })
                    break
    
    # Search error codes
    for ec in ir_data.get('error_codes', []):
        if isinstance(ec, dict):
            content = f"{ec.get('name', '')} {ec.get('message', '')} {ec.get('code', '')}"
            for q in queries:
                score = fuzzy_score(q.lower(), content.lower())
                if score > 0.3:
                    results.append({
                        'type': 'error_code',
                        'name': ec.get('name', ''),
                        'code': ec.get('code', ''),
                        'message': ec.get('message', ''),
                        'score': round(score, 4),
                        'source': 'schema_error',
                    })
                    break
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]


def search_api_docs(ir_data: dict, queries: List[str], top_k: int = 10) -> List[Dict]:
    """在 IR 数据中搜索 API 文档相关内容
    
    Args:
        ir_data: IR 文档数据
        queries: 查询词列表
        top_k: 返回数量
        
    Returns:
        搜索结果列表
    """
    results = []
    
    if not ir_data:
        return results
    
    # Search routes as API docs
    for route in ir_data.get('routes', []):
        if isinstance(route, dict):
            content = f"{route.get('method', '')} {route.get('path', '')} {route.get('handler', '')}"
            for q in queries:
                score = fuzzy_score(q.lower(), content.lower())
                if score > 0.3:
                    results.append({
                        'type': 'api',
                        'path': route.get('path', ''),
                        'method': route.get('method', ''),
                        'handler': route.get('handler', ''),
                        'score': round(score, 4),
                        'source': 'api_doc',
                    })
                    break
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]


def search_by_tags(ir_data: dict, tags: List[str], top_k: int = 10) -> List[Dict]:
    """基于标签搜索
    
    Args:
        ir_data: IR 文档数据
        tags: 标签列表
        top_k: 返回数量
        
    Returns:
        搜索结果列表
    """
    results = []
    
    if not ir_data:
        return results
    
    # Search core flows by tags
    for flow in ir_data.get('core_flows', []):
        if isinstance(flow, dict):
            flow_name = flow.get('flow_name', '')
            entry_point = flow.get('entry_point', '')
            
            for tag in tags:
                if tag.lower() in flow_name.lower() or tag.lower() in entry_point.lower():
                    results.append({
                        'type': 'core_flow',
                        'flow_name': flow_name,
                        'entry_point': entry_point,
                        'call_chain': flow.get('call_chain', []),
                        'score': 0.8,
                        'source': 'tag_flow',
                    })
                    break
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]


def run_multi_path_query(
    query: str,
    ir_data: dict,
    profile: dict = None,
    wiki_path: str = None,
    top_k: int = 20
) -> List[Dict]:
    """执行多路查询并融合结果
    
    Args:
        query: 查询文本
        ir_data: IR 文档数据
        profile: 业务 Profile
        wiki_path: Wiki 路径
        top_k: 返回数量
        
    Returns:
        融合后的搜索结果列表
    """
    # 1. 意图识别
    intent, confidence = extract_intent(query)
    
    # 2. 同义词扩展
    queries = expand_synonyms(query, profile)
    
    # 3. 多路搜索
    code_results = search_code(ir_data, queries, top_k)
    schema_results = search_schema(ir_data, queries, top_k)
    api_results = search_api_docs(ir_data, queries, top_k)
    
    # 4. 标签搜索
    tags = [q for q in queries[:5]]  # 使用前 5 个查询词作为标签
    tag_results = search_by_tags(ir_data, tags, top_k)
    
    # 5. RRF 融合
    all_candidates = [code_results, schema_results, api_results, tag_results]
    fused = rrf_fuse(all_candidates, k=_RRF_K_DEFAULT)
    
    return fused[:top_k]
