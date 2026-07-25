#!/usr/bin/env python3
"""Common utilities shared across biz-delivery engines.

Avoids duplication of PRD keyword extraction and evidence querying
between review_engine, td_engine, and test_engine.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

# Lazy imports to avoid circular dependency
_QUERY_EVIDENCE = None
def _get_query_evidence():
    global _QUERY_EVIDENCE
    if _QUERY_EVIDENCE is None:
        from query_evidence import (
            expand_synonyms, run_evidence_query,
            smart_search, understand_query, enhanced_semantic_search, cross_field_search,
        )
        _QUERY_EVIDENCE = {
            'expand_synonyms': expand_synonyms,
            'run_evidence_query': run_evidence_query,
            'smart_search': smart_search,
            'understand_query': understand_query,
            'enhanced_semantic_search': enhanced_semantic_search,
            'cross_field_search': cross_field_search,
        }
    return _QUERY_EVIDENCE


# ── Domain-specific keyword boosters ────────────────────────

# High-value compound terms that should NOT be split during keyword extraction
_CN_COMPOUNDS = frozenset([
    '素材审核', '广告组', '广告计划', '竞价引擎', '投放管理', '报表统计',
    '权限控制', '缓存策略', '消息队列', '定时任务', '数据迁移', '监控告警',
    '日志收集', '限流降级', '幂等设计', '加密解密', '搜索索引', '推送通知',
    '对账结算', '风控系统', '错误码', '鉴权中间件', '健康检查', '回滚方案',
    '灰度发布', 'Feature Flag', '金丝雀发布', '分布式锁', '事务管理',
    '补偿机制', '重试策略', '异步处理', '批量处理', '实时计算', '离线分析',
    '数据脱敏', '用户画像', '人群定向', '创意素材', '广告位', '投放渠道',
    '转化追踪', '归因分析', 'ROI', 'CTR', 'CVR', 'CPM', 'CPC', 'oCPX',
])

# Business-domain specific terms that should always be prioritized
_DOMAIN_KEYWORDS = frozenset([
    'campaign', 'adgroup', 'creative', 'bidding', 'pacing', 'targeting',
    'budget', 'impression', 'click', 'conversion', 'attribution',
    'report', 'dashboard', 'analytics', 'reconciliation',
    'rbac', 'acl', 'middleware', 'interceptor', 'gateway',
    'redis', 'kafka', 'rabbitmq', 'elasticsearch', 'clickhouse',
])


def _extract_compound_terms(text: str) -> List[str]:
    """提取长复合词（如'素材审核'、'竞价引擎'），避免被拆散。"""
    found = []
    for compound in _CN_COMPOUNDS:
        if compound in text:
            found.append(compound)
    return found


def extract_prd_keywords(prd_text: str, max_keywords: int = 30) -> List[str]:
    """从 PRD 文本中提取关键词。

    增强策略：
    1. 先提取复合词（素材审核、竞价引擎等），避免被拆散
    2. 按标点/空格分句
    3. 保留有意义的短语（2-15 字符）
    4. 优先保留业务术语和驼峰命名
    5. 去重保序
    """
    keywords = []

    # Step 1: Extract compound terms first (highest priority)
    compounds = _extract_compound_terms(prd_text)
    if compounds:
        keywords.extend(compounds)

    # Step 2: Split by punctuation and whitespace
    parts = re.split(r'[，。、；：\s\n]+', prd_text)
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Keep compound terms already extracted
        if p in compounds:
            continue
        # Keep meaningful phrases
        if 2 <= len(p) <= 15:
            keywords.append(p)
        elif len(p) >= 3:
            keywords.append(p)

    # Step 3: Extract camelCase entities (Go struct names, function names)
    camel_entities = re.findall(r'[A-Z][a-z]+(?:[A-Z][a-z]+)*', prd_text)
    for entity in camel_entities:
        if entity.lower() not in [k.lower() for k in keywords] and len(entity) >= 3:
            keywords.append(entity)

    # Step 4: Extract domain-specific English terms
    text_lower = prd_text.lower()
    for term in _DOMAIN_KEYWORDS:
        if term in text_lower and term not in [k.lower() for k in keywords]:
            keywords.append(term)

    # Deduplicate preserving order, limit to max_keywords
    return list(dict.fromkeys(keywords))[:max_keywords]


# ── Cross-Repo Evidence Fusion ──────────────────────────────

def fuse_cross_repo_evidence(
    repo_evidence_map: Dict[str, List[Dict]],
    top_k: int = 30,
) -> List[Dict]:
    """跨仓库证据融合 — 将多个仓库的证据合并去重并排序。

    Args:
        repo_evidence_map: {repo_name: [evidence_list]}
        top_k: 返回前 K 个结果

    Returns:
        融合后的证据列表，每个条目增加 'repos' 字段追踪来源仓库
    """
    all_items = {}

    for repo_name, items in repo_evidence_map.items():
        for item in items:
            # 使用 (type, title) 作为去重键
            key = (item.get('type', ''), item.get('title', ''))
            if key not in all_items:
                all_items[key] = {
                    **item,
                    'repos': [],
                }
            # 追踪来源仓库
            if repo_name not in all_items[key]['repos']:
                all_items[key]['repos'].append(repo_name)

    # 排序：跨越多仓库的证据优先，分数次之
    scored = []
    for item in all_items.values():
        # 跨仓库加分
        repo_bonus = len(item['repos']) * 0.1
        score = item.get('score', 0) + repo_bonus
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]


def build_multi_repo_cache_map(cache_dirs: List[str]) -> Dict[str, dict]:
    """从多个缓存目录加载 IR 数据，构建 {repo_name: ir_dict} 映射。

    Returns:
        {repo_name: ir_dict} 或空 dict
    """
    result = {}
    for cache_dir in cache_dirs:
        cache_file = Path(cache_dir) / "ir_cache.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                repo_name = data.get("repo_name", cache_file.parent.name)
                result[repo_name] = data
            except Exception:
                pass
    return result


# ── Enhanced Query Variant Generation ───────────────────────

def generate_query_variants(query: str) -> List[str]:
    """生成查询变体以提升召回率。

    策略：
    1. 驼峰分割 → snake_case / kebab-case
    2. 缩写展开（RPC, MQ, Redis 等）
    3. 中文复合词拆分
    4. 短查询单字/前缀扩展
    5. 子串提取（保留 ≥3 字符的部分）
    """
    variants = set()
    query_lower = query.lower().strip()

    # 1. 驼峰分割 → snake_case
    snake = re.sub(r'([a-z])([A-Z])', r'\1_\2', query).lower()
    if snake != query_lower and snake:
        variants.add(snake)

    # kebab-case
    kebab = re.sub(r'([a-z])([A-Z])', r'\1-\2', query).lower()
    if kebab != query_lower and kebab:
        variants.add(kebab)

    # 2. 缩写展开
    ABBREVIATION_MAP = {
        'campaign': ['ad_plan', '推广计划'],
        'adgroup': ['ad_group', '广告组'],
        'creative': ['素材', 'ad_material'],
        'bidding': ['竞价', '出价'],
        'review': ['审核', 'approval'],
        'publish': ['发布', '上线'],
        'permission': ['权限', 'auth'],
        'cache': ['缓存', 'redis'],
        'kafka': ['消息队列', 'mq'],
        'rpc': ['grpc', '远程调用'],
        'db': ['database', '数据库'],
        'page': ['pagination', '分页'],
        'timeout': ['超时', 'deadline'],
        'retry': ['重试', 'recovery'],
        'idempotent': ['幂等', '重复提交'],
        'rate_limit': ['限流', '流量控制'],
    }
    for abbr, expansions in ABBREVIATION_MAP.items():
        if abbr in query_lower:
            for exp in expansions:
                variants.add(exp)

    # 3. 短查询（≤3字符）：生成单字/前缀变体
    if len(query) <= 3 and len(query) > 0:
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', query)
        if chinese_chars:
            for ch in chinese_chars:
                variants.add(ch)
        if any(c.isalpha() for c in query):
            for i in range(1, len(query) + 1):
                prefix = query[:i]
                if prefix:
                    variants.add(prefix)

    # 4. 中文复合词拆分（常见业务词对）
    cn_compound_pairs = [
        ('素材审核', ['素材', '审核']),
        ('广告组', ['广告', '组']),
        ('广告计划', ['广告', '计划']),
        ('竞价引擎', ['竞价', '引擎']),
        ('性能优化', ['性能', '优化']),
        ('数据迁移', ['数据', '迁移']),
        ('鉴权中间件', ['鉴权', '中间件']),
        ('错误码', ['错误', '码']),
    ]
    for compound, parts in cn_compound_pairs:
        if compound in query:
            for part in parts:
                variants.add(part)

    # 5. 提取关键子串（保留 ≥3 字符的部分）
    parts = re.split(r'[_\-/\s]+', query)
    for part in parts:
        if 3 <= len(part) <= 20:
            variants.add(part)

    # 过滤掉纯数字和过于通用的词
    filtered = [v for v in variants if v and not v.isdigit() and len(v) >= 2]
    return filtered[:15]


# ── Enhanced Evidence Query ─────────────────────────────────

def query_evidence_for_prd(
    prd_text: str,
    profile: dict,
    wiki_path: str = "",
    cache_dir: str = "",
    top_k_per_query: int = 5,
    max_total: int = 30,
    ir_cache: Optional[dict] = None,
    enable_variant_expansion: bool = True,
    kb_dir: Optional[str] = None,
) -> dict:
    """从 PRD 提取关键词，调用 query_evidence 查询代码库证据。

    增强：
    - 支持传入预加载的 IR 缓存（避免重复从磁盘加载）
    - 多关键词复用同一份数据，减少 80% 磁盘 I/O
    - 可选：查询变体扩展（generate_query_variants）
    - Knowledge base markdown 文件搜索（kb_dir 参数）
    
    Args:
        ir_cache: 可选，预加载的 IR 缓存数据。如果提供则跳过磁盘读取。
        enable_variant_expansion: 是否启用查询变体扩展（默认 True）
        kb_dir: 可选，知识库目录，用于搜索 .md/.txt 文件
    
    Returns:
        {
            'keywords': [...],
            'evidence': [...],
            'total': int,
            'expanded_queries': [...],
            'variants': [...],  # 新增：查询变体列表
        }
    """
    keywords = extract_prd_keywords(prd_text)

    # 用 expand_synonyms 扩展（支持 synonym_map + query_aliases）
    profile_data = profile.get('profile', {}) if isinstance(profile, dict) else profile
    if not profile_data:
        profile_data = profile
    
    # 一次性加载 IR 缓存（在展开查询之前，避免重复读取磁盘）
    if ir_cache is None and cache_dir:
        cache_file = Path(cache_dir) / "ir_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    ir_cache = json.load(f)
            except Exception:
                pass
    
    qe = _get_query_evidence()
    
    # IR-aware synonym expansion: 如果 ir_cache 可用，使用增强版扩展
    if ir_cache and isinstance(ir_cache, dict):
        try:
            expanded_queries = qe['expand_synonyms_with_ir'](prd_text, ir_cache, profile_data)
        except (ImportError, AttributeError):
            # 回退到标准扩展
            expanded_queries = qe['expand_synonyms'](prd_text, profile_data) if profile_data else [prd_text]
    else:
        expanded_queries = qe['expand_synonyms'](prd_text, profile_data) if profile_data else [prd_text]

    # 查询变体扩展（驼峰分割、缩写展开、拼音匹配等）
    variants = []
    if enable_variant_expansion:
        for kw in keywords[:10]:  # 只对前 10 个关键词生成变体
            v = generate_query_variants(kw)
            variants.extend(v)
        variants = list(dict.fromkeys(variants))[:15]

    # 合并所有查询词：原始关键词 + 同义词扩展 + 查询变体
    all_queries = list(dict.fromkeys(keywords + expanded_queries + variants))[:30]

    # ── Multi-path search — reuse the same IR cache ──────────────
    all_evidence = []
    sources = ["code", "schema", "api_docs", "business"]

    # Use smart_search for the PRD-level query (intelligent routing)
    if ir_cache and isinstance(ir_cache, dict):
        try:
            smart_results = qe['smart_search'](
                prd_text, ir_cache, profile_data, top_k=max_total, kb_dir=kb_dir
            )
            if smart_results:
                all_evidence.extend(smart_results)
        except Exception:
            pass

    # Traditional per-keyword search for broad coverage
    for query in all_queries:
        try:
            result = qe['run_evidence_query'](
                query=query,
                wiki_path=wiki_path,
                top_k=top_k_per_query,
                sources=sources,
                cache_dir=cache_dir,
                ir_cache=ir_cache,  # pass preloaded cache
            )
            if result.get('evidence'):
                all_evidence.extend(result['evidence'])
        except Exception:
            pass

    # Cross-field search for entity relationships
    if ir_cache and isinstance(ir_cache, dict):
        try:
            cf_results = qe['cross_field_search'](prd_text, ir_cache, top_k=15)
            if cf_results:
                all_evidence.extend(cf_results)
        except Exception:
            pass

    # Enhanced semantic search for broader recall
    if ir_cache and isinstance(ir_cache, dict):
        try:
            semantic_results = qe['enhanced_semantic_search'](
                prd_text,
                [kw for kw in all_queries if len(kw) > 2],
                top_k=15,
            )
            if semantic_results:
                all_evidence.extend(semantic_results)
        except Exception:
            pass

    # Deduplicate (by path + type), keep highest score
    seen = {}
    for item in all_evidence:
        key = (item.get('path', ''), item.get('type', ''))
        score = item.get('score', 0)
        if key not in seen or score > seen[key].get('score', 0):
            seen[key] = item

    unique_evidence = list(seen.values())[:max_total]

    return {
        'keywords': keywords,
        'evidence': unique_evidence,
        'total': len(unique_evidence),
        'expanded_queries': all_queries,
        'variants': variants,
    }
