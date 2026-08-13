#!/usr/bin/env python3
"""证据查询主入口 — 整合所有查询模块的统一接口

提供 run_evidence_query 作为主入口函数，整合代码搜索、Schema 搜索、
API 文档搜索、Wiki 搜索、RRF 融合等所有查询能力。

Usage:
    from scripts.query.evidence_query import run_evidence_query
    
    result = run_evidence_query(
        query="素材审核流程",
        ir_data=ir,
        profile=profile,
        top_k=20
    )
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import json

from .intent import extract_intent
from .fuzzy_match import fuzzy_score, fuzzy_match
from .synonym_expansion import expand_synonyms
from .multi_path_query import run_multi_path_query, search_code, search_schema, search_api_docs, search_by_tags
from .rrf_fusion import rrf_fuse, rrf_fuse_multi_source
from .wiki_query import query_wiki_evidence


# ──────────────────────────────────────────────
# Evidence Query — 主查询入口
# ──────────────────────────────────────────────

def run_evidence_query(
    query: str,
    ir_data: Optional[dict] = None,
    profile: Optional[dict] = None,
    wiki_path: Optional[str] = None,
    top_k: int = 20,
    sources: Optional[List[str]] = None,
    cache_dir: Optional[str] = None,
    use_weighted_fusion: bool = True,
) -> Dict[str, Any]:
    """执行多路证据查询并返回融合结果
    
    这是证据查询的主入口函数，整合了：
    1. 意图识别
    2. 同义词扩展
    3. 多路搜索（代码、Schema、API、Wiki）
    4. RRF 融合
    5. 结果返回
    
    Args:
        query: 查询文本
        ir_data: IR 文档数据
        profile: 业务 Profile
        wiki_path: Wiki 知识库路径
        top_k: 返回数量
        sources: 搜索源列表，如 ["code", "schema", "api_docs", "wiki"]
        cache_dir: 缓存目录
        use_weighted_fusion: 是否使用加权融合（考虑 source_type 权重）
        
    Returns:
        包含以下字段的字典：
        - intent: 识别的意图
        - confidence: 置信度
        - expanded_queries: 扩展后的查询词列表
        - results: 融合后的搜索结果列表
        - sources: 使用的搜索源
        - stats: 统计信息
    """
    # 1. 意图识别
    intent, confidence = extract_intent(query)
    
    # 2. 同义词扩展
    expanded_queries = expand_synonyms(query, profile)
    
    # 3. 确定搜索源
    if sources is None:
        sources = ["code", "schema", "api_docs", "wiki"]
    
    # 4. 多路搜索
    candidates = []
    path_results = {}
    
    if "code" in sources and ir_data:
        results = search_code(ir_data, expanded_queries, top_k)
        candidates.append(results)
        path_results['code'] = results
    
    if "schema" in sources and ir_data:
        results = search_schema(ir_data, expanded_queries, top_k)
        candidates.append(results)
        path_results['schema'] = results
    
    if "api_docs" in sources and ir_data:
        results = search_api_docs(ir_data, expanded_queries, top_k)
        candidates.append(results)
        path_results['api_docs'] = results
    
    if "wiki" in sources:
        wiki_results = query_wiki_evidence(query, wiki_path=wiki_path, cache_dir=cache_dir, top_k=top_k)
        if wiki_results:
            candidates.append(wiki_results)
            path_results['wiki'] = wiki_results
    
    # 5. RRF 融合
    if use_weighted_fusion and candidates:
        fused_results = rrf_fuse_multi_source(candidates, k=60)
    elif candidates:
        fused_results = rrf_fuse(candidates, k=60)
    else:
        fused_results = []
    
    # 6. 构建返回结果
    result = {
        'intent': intent,
        'confidence': confidence,
        'query': query,
        'expanded_queries': expanded_queries[:10],
        'results': fused_results,
        'sources': sources,
        'path_results': path_results,
        'stats': {
            'total_results': len(fused_results),
            'sources_used': len([s for s in sources if path_results.get(s)]),
            'intent': intent,
            'confidence': round(confidence, 4),
        }
    }
    
    return result


# ──────────────────────────────────────────────
# Evidence Query (Legacy) — 兼容旧接口
# ──────────────────────────────────────────────

def run_evidence_query_legacy(
    query: str,
    profile_path: str = None,
    wiki_path: str = None,
    top_k: int = 10,
    sources: List[str] = None,
    cache_dir: str = None,
    ir_cache: Optional[dict] = None,
) -> Dict[str, Any]:
    """Legacy 证据查询接口 — 兼容旧代码
    
    Args:
        query: 查询文本
        profile_path: Profile 文件路径
        wiki_path: Wiki 路径
        top_k: 返回数量
        sources: 搜索源列表
        cache_dir: 缓存目录
        ir_cache: 预加载的 IR 缓存
        
    Returns:
        查询结果字典
    """
    # 加载 profile
    profile = None
    if profile_path:
        profile_file = Path(profile_path)
        if profile_file.exists():
            with open(profile_file) as f:
                profile = json.load(f)
    
    # 加载 IR 缓存
    ir_data = ir_cache
    if ir_data is None and profile:
        ir_cache_path = Path(profile.get('ir_cache_path', ''))
        if ir_cache_path and ir_cache_path.exists() and ir_cache_path.is_file():
            with open(ir_cache_path) as f:
                ir_data = json.load(f)
    
    # 调用新接口
    return run_evidence_query(
        query=query,
        ir_data=ir_data,
        profile=profile,
        wiki_path=wiki_path,
        top_k=top_k,
        sources=sources,
        cache_dir=cache_dir,
    )


# ──────────────────────────────────────────────
# Smart Search — 智能搜索入口
# ──────────────────────────────────────────────

def smart_search(
    query: str,
    ir_data: dict,
    profile: dict = None,
    top_k: int = 20,
    kb_dir: Optional[str] = None,
) -> List[Dict]:
    """智能搜索 — 整合多路搜索并融合结果
    
    这是向后兼容的接口，内部调用 run_evidence_query。
    
    Args:
        query: 查询文本
        ir_data: IR 文档数据
        profile: 业务 Profile
        top_k: 返回数量
        kb_dir: 知识库目录
        
    Returns:
        搜索结果列表
    """
    result = run_evidence_query(
        query=query,
        ir_data=ir_data,
        profile=profile,
        wiki_path=kb_dir,
        top_k=top_k,
        sources=["code", "schema", "api_docs", "wiki"],
    )
    return result['results']


# ──────────────────────────────────────────────
# Export
# ──────────────────────────────────────────────

__all__ = [
    'run_evidence_query',
    'run_evidence_query_legacy',
    'smart_search',
]
