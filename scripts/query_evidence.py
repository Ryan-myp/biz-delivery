#!/usr/bin/env python3
"""
通用证据查询 — 多路融合 + Wiki 增强

复用 biz-delivery 核心能力：
- smart_routing.py 的意图识别
- rrf_fusion.py 的 RRF 融合
- wiki-engine 的知识编译

用法:
    python3 query_evidence.py --query "Redis 的持久化机制" --profile profiles/my-service.json
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────
# 1. 意图识别 (复用 smart_routing.py)
# ──────────────────────────────────────────────

INTENT_PATTERNS = {
    "query": ["查询", "查看", "获取", "查找", "检索", "query", "search", "get", "list"],
    "question": ["什么", "如何", "怎么", "为什么", "吗", "what", "how", "why", "where"],
    "explain": ["解释", "说明", "原理", "机制", "explain", "describe"],
    "debug": ["调试", "排障", "错误", "失败", "bug", "error", "troubleshoot"],
    "callchain": ["谁调用了", "调用链", "caller", "callee", "depends"],
    "dataflow": ["从哪来", "数据来源", "流向", "source", "sink", "data flow"],
    "impact": ["改了影响", "影响分析", "impact", "side effect", "what breaks"],
}


def extract_intent(query: str) -> Tuple[str, float]:
    """意图识别"""
    query_lower = query.lower()
    scores = {}
    for intent, patterns in INTENT_PATTERNS.items():
        hits = sum(1 for p in patterns if p in query_lower)
        if hits > 0:
            scores[intent] = hits / len(patterns)

    if not scores:
        return ("query", 0.0)

    best_intent = max(scores, key=scores.get)
    return best_intent, scores[best_intent]


# ──────────────────────────────────────────────
# 2. 多路证据查询引擎
# ──────────────────────────────────────────────

def search_code(query: str, repo_path: str, top_k: int = 10) -> List[Dict]:
    """搜索代码（复用 knowledge_extractor.py）"""
    # TODO: 集成 AST 提取
    return []


def search_schema(query: str, repo_path: str, top_k: int = 10) -> List[Dict]:
    """搜索 schema 定义"""
    # TODO: 搜索数据库 schema
    return []


def search_api_docs(query: str, repo_path: str, top_k: int = 10) -> List[Dict]:
    """搜索 API 文档"""
    # TODO: 搜索 API 文档
    return []


# ──────────────────────────────────────────────
# 3. Wiki 增强证据查询
# ──────────────────────────────────────────────

def query_wiki_evidence(query: str, wiki_path: str = None, top_k: int = 5) -> List[Dict]:
    """
    用 LLM Wiki 增强证据查询：
    1. 先搜 wiki 页面
    2. 返回页面作为证据
    """
    from .wiki_engine import query as wiki_query, wiki_search as wiki_search_engine

    if wiki_path and wiki_path != 'none':
        try:
            result = wiki_search_engine(query, wiki=wiki_search_engine.__globals__.get('wiki'))
            # 实际调用需要正确初始化
            pass
        except Exception:
            pass

    # 如果 wiki 不可用，返回空
    return []


# ──────────────────────────────────────────────
# 4. RRF 融合
# ──────────────────────────────────────────────

def rrf_fuse(candidates: List[List[Dict]], k: int = 60) -> List[Dict]:
    """RRF 融合多路结果"""
    ranked = {}
    for path_results in candidates:
        for i, item in enumerate(path_results):
            path = item.get('path', item.get('file_path', ''))
            if path not in ranked:
                ranked[path] = {
                    'path': path,
                    'score': 0,
                    'items': [],
                }
            ranked[path]['score'] += 1.0 / (k + i + 1)
            ranked[path]['items'].append(item)

    sorted_items = sorted(ranked.values(), key=lambda x: x['score'], reverse=True)
    return [item for item_list in [x['items'] for x in sorted_items] for item in item_list][:top_k]


# ──────────────────────────────────────────────
# 5. 主流程
# ──────────────────────────────────────────────

def run_evidence_query(query: str, profile_path: str = None, wiki_path: str = None,
                       top_k: int = 10, sources: List[str] = None) -> Dict[str, Any]:
    """
    执行多路证据查询：
    1. 意图识别
    2. 多路搜索
    3. RRF 融合
    4. 返回结果
    """
    intent, confidence = extract_intent(query)

    # 默认搜索源
    if not sources:
        sources = ["code", "schema", "api_docs"]

    # 多路搜索
    candidates = []
    path_results = {}

    if "code" in sources:
        results = search_code(query, "", top_k)
        candidates.append(results)
        path_results['code'] = results

    if "schema" in sources:
        results = search_schema(query, "", top_k)
        candidates.append(results)
        path_results['schema'] = results

    if "api_docs" in sources:
        results = search_api_docs(query, "", top_k)
        candidates.append(results)
        path_results['api_docs'] = results

    # Wiki 增强
    if wiki_path and wiki_path != 'none':
        wiki_results = query_wiki_evidence(query, wiki_path, top_k)
        if wiki_results:
            candidates.append(wiki_results)
            path_results['wiki'] = wiki_results

    # RRF 融合
    if candidates:
        fused = rrf_fuse(candidates, k=60)
    else:
        fused = []

    result = {
        'query': query,
        'intent': intent,
        'confidence': confidence,
        'sources': sources,
        'total_results': len(fused),
        'evidence': fused[:top_k],
        'status': 'ready' if fused else 'partial',
    }

    return result


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="通用证据查询 — 多路融合 + Wiki 增强")
    parser.add_argument('--query', required=True, help='查询语句')
    parser.add_argument('--profile', default=None, help='Profile 配置文件')
    parser.add_argument('--wiki', default='none', help='Wiki 目录路径（设为 none 禁用）')
    parser.add_argument('--sources', default='code,schema,api_docs', help='搜索源逗号分隔')
    parser.add_argument('--top-k', type=int, default=10)

    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(',')]
    result = run_evidence_query(
        query=args.query,
        profile_path=args.profile,
        wiki_path=args.wiki,
        top_k=args.top_k,
        sources=sources,
    )

    print(f"🔍 查询: {result['query']}")
    print(f"🎯 意图: {result['intent']} (置信度: {result['confidence']:.3f})")
    print(f"📊 结果: {result['total_results']} 个证据")
    print(f"📦 状态: {result['status']}")
    print()
    for i, ev in enumerate(result['evidence'][:result['top_k'] if hasattr(result, 'top_k') else 5], 1):
        print(f"  {i}. {ev.get('title', ev.get('path', 'unknown'))}")
