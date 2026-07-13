#!/usr/bin/env python3
"""Enhanced search utilities for biz-delivery query_evidence.

Provides:
1. BM25-inspired scoring (better than pure TF-IDF for short texts)
2. Character-level Chinese similarity (n-gram based)
3. Query normalization (common variation handling)
4. Adaptive threshold tuning based on query length
"""

import math
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple


# ──────────────────────────────────────────────
# BM25 Scoring
# ──────────────────────────────────────────────

class BM25Scorer:
    """Lightweight BM25 scorer — no external dependencies.
    
    Better than TF-IDF for short document matching (function names, routes, etc.)
    """
    
    # BM25 hyperparameters (standard values)
    K1 = 1.5  # Term frequency saturation
    B = 0.75  # Length normalization
    
    def __init__(self):
        self.documents: List[str] = []
        self.avg_doc_length: float = 0.0
        self.idf_cache: Dict[str, float] = {}
        self.doc_freq: Dict[str, int] = {}
    
    def fit(self, documents: List[str]):
        """Build index from documents."""
        self.documents = documents
        if not documents:
            return
        
        n_docs = len(documents)
        total_length = 0
        self.doc_freq = {}
        
        for doc in documents:
            tokens = self._tokenize(doc)
            total_length += len(tokens)
            # Document frequency
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freq[token] = self.doc_freq.get(token, 0) + 1
        
        self.avg_doc_length = total_length / n_docs if n_docs > 0 else 1.0
        
        # Pre-compute IDF
        for term, df in self.doc_freq.items():
            self.idf_cache[term] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
    
    def score(self, query: str, doc_index: int) -> float:
        """Score query against a specific document."""
        if not self.documents:
            return 0.0
        
        query_tokens = Counter(self._tokenize(query))
        doc_tokens = Counter(self._tokenize(self.documents[doc_index]))
        doc_length = len(doc_tokens)
        
        score = 0.0
        for term, qtf in query_tokens.items():
            idf = self.idf_cache.get(term, 0.0)
            if idf <= 0:
                continue
            
            # Term frequency in document (with BM25 saturation)
            dtf = doc_tokens.get(term, 0)
            tf = dtf / (self.K1 * (doc_length / self.avg_doc_length) + dtf + 1e-10)
            
            score += idf * tf * qtf
        
        return score
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Search all documents, return (index, score) sorted by score descending."""
        if not self.documents:
            return []
        
        scores = []
        for i in range(len(self.documents)):
            s = self.score(query, i)
            if s > 0:
                scores.append((i, s))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
    
    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenize: split Chinese chars individually, English words separately."""
        words = re.findall(r'[a-zA-Z]+', text)
        chars = re.findall(r'[\u4e00-\u9fff]', text)
        return words + chars


# ──────────────────────────────────────────────
# Chinese Character-level Similarity
# ──────────────────────────────────────────────

def char_ngrams(text: str, n: int = 2) -> set:
    """Generate character n-grams for Chinese text."""
    return {text[i:i+n] for i in range(max(0, len(text) - n + 1))}


def chinese_similarity(s1: str, s2: str, n: int = 2) -> float:
    """Compute character n-gram similarity between two Chinese strings.
    
    Good for comparing Chinese business terms that might have slight variations.
    E.g., "广告组" vs "广告组管理" → high similarity
    """
    if not s1 or not s2:
        return 0.0
    
    if s1 == s2:
        return 1.0
    
    grams1 = char_ngrams(s1, n)
    grams2 = char_ngrams(s2, n)
    
    if not grams1 or not grams2:
        return 0.0
    
    intersection = len(grams1 & grams2)
    union = len(grams1 | grams2)
    
    return intersection / union if union > 0 else 0.0


def mixed_similarity(query: str, target: str) -> float:
    """Combined similarity: fuzzy_score + BM25 + Chinese n-gram.
    
    Adaptive weighting based on query composition:
    - Pure Chinese: higher weight on n-gram
    - Mixed: balanced
    - Pure English: higher weight on fuzzy + BM25
    """
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', query))
    has_english = bool(re.search(r'[a-zA-Z]', query))
    
    # Base fuzzy score (already defined in query_evidence.py)
    from query_evidence import fuzzy_score
    base = fuzzy_score(query, target)
    
    # Chinese n-gram similarity
    cn_sim = chinese_similarity(query, target) if has_chinese else 0.0
    
    # BM25 score (need to build index first for best results)
    bm25_sim = 0.0  # Will be computed when BM25Scorer is available
    
    if has_chinese and not has_english:
        # Pure Chinese: trust n-gram more
        return 0.4 * base + 0.6 * cn_sim
    elif has_chinese and has_english:
        # Mixed: balanced
        return 0.45 * base + 0.35 * cn_sim + 0.2 * bm25_sim
    else:
        # Pure English: trust fuzzy + BM25
        return 0.6 * base + 0.4 * bm25_sim


# ──────────────────────────────────────────────
# Query Normalization
# ──────────────────────────────────────────────

QUERY_NORMALIZATIONS = {
    # Common abbreviations → full forms
    'adgroup': 'ad_group',
    'ad group': 'ad_group',
    'creative': '素材',
    'ad material': '素材',
    'bidding': '竞价',
    'bid': '竞价',
    'review': '审核',
    'audit': '审核',
    'publish': '发布',
    'deploy': '发布',
    'campaign': '广告计划',
    'targeting': '定向',
    'impression': '展示',
    'display': '展示',
    'click': '点击',
    'ctr': '点击率',
    'conversion': '转化',
    'cvr': '转化率',
    'report': '报表',
    'stats': '统计',
    'cache': '缓存',
    'redis': '缓存',
    'kafka': '消息队列',
    'mq': '消息队列',
    'push': '推送',
    'notification': '推送',
    'budget': '预算',
    'spending': '花费',
    'permission': '权限',
    'auth': '权限',
    'acl': '权限',
    'rate limit': '限流',
    'throttle': '限流',
    'qps': '每秒请求数',
    'tps': '每秒事务数',
    'latency': '延迟',
    'timeout': '超时',
    'retry': '重试',
    'rollback': '回滚',
    'migration': '迁移',
    'schema': '表结构',
    'index': '索引',
    'primary key': '主键',
    'foreign key': '外键',
    'unique key': '唯一键',
    'go test': '单元测试',
    'unit test': '单元测试',
    'integration test': '集成测试',
    'e2e': '端到端测试',
    'ci/cd': '持续集成',
    'docker': '容器',
    'k8s': 'kubernetes',
    'kubernetes': 'k8s',
}


def normalize_query(query: str) -> str:
    """Normalize common query variations.
    
    E.g., "adgroup permission" → "ad_group 权限"
    """
    query_lower = query.lower()
    result = query
    
    for pattern, replacement in QUERY_NORMALIZATIONS.items():
        result = result.replace(pattern, replacement)
    
    return result.strip()


def expand_query_variants(query: str) -> List[str]:
    """Generate query variants for broader matching.
    
    Strategies:
    1. Normalize common abbreviations
    2. Split compound terms
    3. Add English/Chinese alternates
    """
    variants = [query]
    
    # 1. Normalized form
    normalized = normalize_query(query)
    if normalized != query:
        variants.append(normalized)
    
    # 2. Split CamelCase
    camel_parts = re.findall(r'[A-Z][a-z]*|[a-z]+', query)
    if len(camel_parts) > 1:
        variants.extend(camel_parts)
    
    # 3. Split Chinese compound words (simple heuristic)
    # e.g., "广告组管理" → "广告组", "管理"
    if re.search(r'[\u4e00-\u9fff]{3,}', query):
        # Try splitting at common boundaries
        for i in range(2, len(query)):
            chunk = query[max(0,i-2):i]
            if 2 <= len(chunk) <= 4 and re.match(r'^[\u4e00-\u9fff]+$', chunk):
                variants.append(chunk)
    
    # Deduplicate
    return list(dict.fromkeys(variants))


# ──────────────────────────────────────────────
# Adaptive Threshold Tuning
# ──────────────────────────────────────────────

def adaptive_threshold(query: str, query_type: str = "general") -> float:
    """Adaptive similarity threshold based on query characteristics.
    
    Higher thresholds for precise queries, lower for broad ones.
    
    Args:
        query: The search query
        query_type: 'precise' (specific entity), 'general' (concept), 'broad' (domain)
    
    Returns:
        Recommended minimum similarity threshold [0.3, 0.8]
    """
    base_threshold = {
        'precise': 0.6,
        'general': 0.5,
        'broad': 0.35,
    }.get(query_type, 0.5)
    
    # Adjust based on query length
    query_len = len(query)
    if query_len <= 2:
        # Very short query: raise threshold to avoid noise
        base_threshold = max(base_threshold, 0.6)
    elif query_len >= 10:
        # Long query: can be more flexible
        base_threshold = max(0.0, base_threshold - 0.05)
    
    # Adjust based on whether query has special chars
    if re.search(r'[A-Z]', query):
        # Contains CamelCase → likely a specific entity
        base_threshold = max(base_threshold, 0.55)
    
    return min(base_threshold, 0.8)


def classify_query(query: str) -> str:
    """Classify query type for threshold tuning."""
    # Precise: looks like a specific entity name
    if re.match(r'^[A-Z][a-z]+[A-Z]', query):  # CamelCase entity
        return 'precise'
    if re.search(r'/api/\w+', query):  # API path
        return 'precise'
    if re.search(r'\b\d{3,}\b', query):  # Has numbers (error codes, etc.)
        return 'precise'
    
    # Broad: domain-level concepts
    if len(query) >= 10:
        return 'broad'
    
    return 'general'
