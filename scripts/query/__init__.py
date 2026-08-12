#!/usr/bin/env python3
"""query 模块 — biz-delivery 证据查询的统一入口

包含意图识别、模糊匹配、同义词扩展、多路查询、RRF 融合、Wiki 查询等功能。

Usage:
    from scripts.query import (
        extract_intent,
        fuzzy_score,
        expand_synonyms,
        run_multi_path_query,
        rrf_fuse,
        run_evidence_query,
    )
"""

from .intent import extract_intent, get_intent_patterns, classify_intent
from .fuzzy_match import (
    fuzzy_score,
    fuzzy_match,
    levenshtein_distance,
    adaptive_threshold,
)
from .synonym_expansion import (
    expand_synonyms,
    contextual_expand,
    get_builtin_synonyms,
    get_contextual_term_map,
)
from .multi_path_query import (
    run_multi_path_query,
    search_code,
    search_schema,
    search_api_docs,
    search_by_tags,
    rrf_fuse,
)
from .rrf_fusion import (
    rrf_fuse as rrf_fuse_weighted,
    rrf_fuse_multi_source,
    fuse_results,
    fuse_weighted_results,
)
from .wiki_query import (
    query_wiki,
    query_wiki_evidence,
    load_wiki_index,
    query_cache,
    query_knowledge_graph,
    search_markdown_docs,
)
from .evidence_query import (
    run_evidence_query,
    run_evidence_query_legacy,
    smart_search,
)

__all__ = [
    # Intent
    'extract_intent',
    'get_intent_patterns',
    'classify_intent',
    # Fuzzy Match
    'fuzzy_score',
    'fuzzy_match',
    'levenshtein_distance',
    'adaptive_threshold',
    # Synonym Expansion
    'expand_synonyms',
    'contextual_expand',
    'get_builtin_synonyms',
    'get_contextual_term_map',
    # Multi-path Query
    'run_multi_path_query',
    'search_code',
    'search_schema',
    'search_api_docs',
    'search_by_tags',
    'rrf_fuse',
    # RRF Fusion
    'rrf_fuse_weighted',
    'rrf_fuse_multi_source',
    'fuse_results',
    'fuse_weighted_results',
    # Wiki Query
    'query_wiki',
    'query_wiki_evidence',
    'load_wiki_index',
    'query_cache',
    'query_knowledge_graph',
    'search_markdown_docs',
    # Evidence Query
    'run_evidence_query',
    'run_evidence_query_legacy',
    'smart_search',
]
