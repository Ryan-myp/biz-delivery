#!/usr/bin/env python3
"""向后兼容层 — 为旧代码提供与原始 query_evidence.py 相同的接口

此模块允许现有代码继续使用 from query_evidence import xxx 的导入方式，
同时底层已切换到新的模块化实现。
"""

# Import everything from the new query module
from scripts.query.intent import (
    extract_intent,
    get_intent_patterns,
    classify_intent,
)
from scripts.query.fuzzy_match import (
    fuzzy_score,
    fuzzy_match,
    levenshtein_distance,
    adaptive_threshold,
    char_ngrams,
)
from scripts.query.synonym_expansion import (
    expand_synonyms,
    contextual_expand,
    get_builtin_synonyms,
    get_contextual_term_map,
)
from scripts.query.multi_path_query import (
    run_multi_path_query,
    search_code,
    search_schema,
    search_api_docs,
    search_by_tags,
    rrf_fuse,
)

# Aliases for compatibility
INTENT_PATTERNS = get_intent_patterns()
_CN_COMPOUNDS = frozenset([
    '素材审核', '广告组', '广告计划', '竞价引擎', '投放管理', '报表统计',
])

# Re-export all functions with original names
__all__ = [
    # Intent
    'extract_intent',
    'INTENT_PATTERNS',
    # Fuzzy Match
    'fuzzy_score',
    'fuzzy_match',
    'levenshtein_distance',
    'adaptive_threshold',
    # Synonym Expansion
    'expand_synonyms',
    'contextual_expand',
    # Multi-path Query
    'run_multi_path_query',
    'search_code',
    'search_schema',
    'search_api_docs',
    'search_by_tags',
    'rrf_fuse',
]
