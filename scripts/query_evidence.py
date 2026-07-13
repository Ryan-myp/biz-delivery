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
import math
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



def expand_query(query: str, profile: dict = None) -> List[str]:
    """扩展查询词 — 把中文查询扩展为多个关键词
    
    策略：
    1. 从 synonyms 扩展同义词
    2. 从 query_aliases 扩展中文业务词
    3. 从 query 中提取中英文关键词
    """
    keywords = [query]
    
    # 1. 从 profile 加载 synonyms
    if profile:
        synonyms = profile.get('synonyms', {})
        for term, terms in synonyms.items():
            if term.lower() in query.lower():
                keywords.extend(terms)
    
    # 2. 从 query_aliases 扩展
    if profile:
        aliases = profile.get('query_aliases', {})
        for alias, terms in aliases.items():
            if alias.lower() in query.lower():
                keywords.extend(terms)
    
    # 3. 从 query 中提取中英文关键词 — 使用模块级 re
    camel = re.findall(r'[A-Z][a-z]+|[a-z]+', query)
    keywords.extend(camel)
    
    # 去重
    keywords = list(dict.fromkeys(keywords))
    
    return keywords[:15]  # 最多 15 个关键词


# ──────────────────────────────────────────────
# Pinyin Phonetic Matching — 拼音近似匹配
# ──────────────────────────────────────────────

# 拼音映射表（常用中文→拼音首字母）
_PINYIN_INITIALS = {
    '资': 'z', '料': 'l', '广': 'g', '告': 'a', '组': 'z', '计': 'j', '划': 'h',
    '竞': 'j', '价': 'j', '审': 's', '核': 'h', '发': 'f', '布': 'b', '上': 's',
    '线': 'x', '权': 'q', '限': 'x', '认': 'r', '证': 'z', '登': 'd', '录': 'l',
    '缓': 'h', '存': 'c', '消': 'x', '息': 'x', '队': 'd', '列': 'l', '消': 'x',
    '队': 'd', '列': 'l', '报': 'b', '表': 'b', '统': 't', '计': 'j', '分': 'f',
    '析': 'x', '预': 'y', '算': 's', '算': 's', '定': 'd', '向': 'x', '投': 't',
    '放': 'f', '监': 'j', '控': 'k', '跟': 'g', '踪': 'z', '通': 't', '知': 'z',
    '推': 't', '荐': 'j', '搜': 's', '索': 's', '查': 'c', '询': 'x', '查': 'c',
    '看': 'k', '获': 'h', '取': 'q', '添': 't', '加': 'j', '新': 'x', '建': 'j',
    '编': 'b', '辑': 'j', '修': 'x', '改': 'g', '删': 's', '除': 'c', '移': 'y',
    '动': 'd', '复': 'f', '制': 'z', '拷': 'k', '贝': 'b', '备': 'b', '同': 't',
    '步': 'b', '提': 't', '交': 'j', '付': 'f', '批': 'p', '准': 'z', '拒': 'j',
    '绝': 'j', '回': 'h', '滚': 'g', '恢': 'h', '复': 'f', '暂': 'z', '停': 't',
    '止': 'z', '恢': 'h', '活': 'h', '激': 'j', '活': 'h', '停': 't', '用': 'y',
    '禁': 'j', '止': 'z', '启': 'q', '动': 'd', '销': 'x', '毁': 'h', '灭': 'm',
    '标': 'b', '注': 'z', '解': 'j', '释': 's', '详': 'x', '细': 'x', '描': 'm',
    '述': 's', '说': 's', '明': 'm', '展': 'z', '示': 's', '曝': 'p', '光': 'g',
    '点': 'd', '击': 'j', '转': 'z', '化': 'h', '收': 's', '藏': 'c', '反': 'f',
    '馈': 'k', '评': 'p', '论': 'l', '评': 'p', '优': 'y', '化': 'h', '调': 't',
    '整': 'z', '适': 's', '配': 'p', '匹': 'p', '对': 'd', '映': 'y', '射': 's',
    '匹': 'p', '配': 'p', '平': 'p', '衡': 'h', '均': 'j', '匀': 'y', '分': 'f',
    '担': 'd', '负': 'f', '加': 'j', '载': 'z', '容': 'r', '量': 'l', '限': 'x',
    '额': 'e', '满': 'm', '足': 'z', '充': 'c', '裕': 'y', '紧': 'j', '急': 'j',
    '繁': 'f', '重': 'z', '要': 'y', '普': 'p', '通': 't', '常': 'c', '规': 'g',
    '范': 'f', '标': 'b', '准': 'z', '默': 'm', '认': 'r', '可': 'k', '选': 'x',
    '项': 'x', '目': 'm', '类': 'l', '型': 'x', '格': 'g', '式': 's', '种': 'z',
    '种': 'z', '方': 'f', '案': 'a', '策': 'c', '略': 'l', '战': 'z', '术': 's',
    '工': 'g', '程': 'c', '项': 'x', '目': 'm', '任': 'r', '务': 'w', '任': 'r',
    '务': 'w', '代': 'd', '码': 'm', '编': 'b', '写': 'x', '测': 'c', '试': 's',
    '部': 'b', '件': 'j', '模': 'm', '块': 'k', '组': 'z', '件': 'j', '服': 'f',
    '务': 'w', '端': 'd', '口': 'k', '接': 'j', '口': 'k', '数': 's', '据': 'j',
    '库': 'k', '表': 'b', '结': 'j', '构': 'g', '字': 'z', '段': 'd', '属': 's',
    '性': 'x', '主': 'z', '键': 'j', '外': 'w', '键': 'j', '索': 's', '引': 'y',
    '指': 'z', '针': 'z', '唯': 'w', '一': 'y', '检': 'j', '查': 'c', '校': 'x',
    '验': 'y', '验': 'y', '证': 'z', '密': 'm', '码': 'm', '错': 'c', '误': 'w',
    '异': 'y', '常': 'c', '超': 'c', '时': 's', '失': 's', '败': 'b', '错': 'c',
    '误': 'w', '故': 'g', '障': 'z', '排': 'p', '错': 'c', '修': 'x', '复': 'f',
    '原': 'y', '因': 'y', '根': 'g', '据': 'j', '日': 'r', '志': 'z', '记': 'j',
    '录': 'l', '操': 'c', '作': 'z', '日': 'r', '志': 'z', '操': 'c', '作': 'z',
    '操': 'c', '作': 'z', '记': 'j', '录': 'l', '审': 's', '计': 'j', '跟': 'g',
    '踪': 'z', '监': 'j', '控': 'k', '监': 'j', '测': 'c', '检': 'j', '查': 'c',
    '警': 'j', '告': 'a', '阈': 'y', '值': 'z', '阈': 'y', '值': 'z', '阈': 'y',
    '值': 'z', '阈': 'y', '值': 'z', '阈': 'y', '值': 'z',
}

def _pinyin_initial(char: str) -> str:
    """获取中文字符的拼音首字母"""
    return _PINYIN_INITIALS.get(char, '')

def _chinese_to_pinyin_initials(text: str) -> str:
    """将中文文本转换为拼音首字母序列"""
    return ''.join(_pinyin_initial(c) for c in text if _pinyin_initial(c))


# ──────────────────────────────────────────────
# Fuzzy Search — Levenshtein 编辑距离
# ──────────────────────────────────────────────

def levenshtein_distance(s1: str, s2: str) -> int:
    """计算两个字符串的 Levenshtein 编辑距离"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if not s2:
        return len(s1)
    
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    
    return prev_row[-1]


def fuzzy_match(query: str, target: str, threshold: Optional[float] = None) -> bool:
    """判断 query 和 target 是否 fuzzy 匹配"""
    if threshold is None:
        threshold = adaptive_threshold(query)
    return fuzzy_score(query, target, threshold=threshold) >= threshold


def fuzzy_score(query: str, target: str, threshold: Optional[float] = None) -> float:
    """计算两个字符串的 fuzzy 相似度 [0, 1]
    
    基于 Levenshtein 编辑距离归一化，增强中文支持。
    
    增强：
    1. 支持子串匹配（包含关系优先）
    2. 支持词级别比较（英文按空格分割）
    3. 短字符串用编辑距离，长字符串用 Jaccard 相似度
    4. 中文字符 n-gram 相似度补充
    5. 自适应阈值（精确查询 vs 宽泛查询）
    """
    if not query and not target:
        return 1.0
    if not query or not target:
        return 0.0
    
    q_lower = query.lower()
    t_lower = target.lower()
    
    if q_lower == t_lower:
        return 1.0
    
    # 子串包含优先
    if q_lower in t_lower or t_lower in q_lower:
        shorter = min(len(q_lower), len(t_lower))
        longer = max(len(q_lower), len(t_lower))
        return 0.8 + 0.2 * (shorter / longer)
    
    # 检测是否为纯中文或混合文本
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', q_lower)) or bool(re.search(r'[\u4e00-\u9fff]', t_lower))
    
    # 短字符串（<=15字符），用编辑距离
    if max(len(q_lower), len(t_lower)) <= 15:
        dist = levenshtein_distance(q_lower, t_lower)
        max_len = max(len(q_lower), len(t_lower))
        edit_score = 1.0 - dist / max_len if max_len > 0 else 1.0
        
        # 中文额外加分：n-gram 相似度
        if has_chinese:
            cn_sim = _chinese_ngram_similarity(q_lower, t_lower)
            return 0.6 * edit_score + 0.4 * cn_sim
        return edit_score
    
    # 长字符串：混合策略
    # 1. 词级别 Jaccard 相似度（英文部分）
    q_words = set(q_lower.split())
    t_words = set(t_lower.split())
    
    jaccard = 0.0
    if q_words and t_words:
        intersection = len(q_words & t_words)
        union = len(q_words | t_words)
        jaccard = intersection / union if union > 0 else 0.0
    
    # 2. 编辑距离作为辅助
    dist = levenshtein_distance(q_lower, t_lower)
    max_len = max(len(q_lower), len(t_lower))
    edit_score = 1.0 - dist / max_len if max_len > 0 else 0.0
    
    # 3. 中文 n-gram 相似度（如果有中文）
    cn_sim = _chinese_ngram_similarity(q_lower, t_lower) if has_chinese else 0.0
    
    # 加权融合 — 新增拼音相似度
    if has_chinese:
        py_sim = _pinyin_similarity(q_lower, t_lower)
        return 0.35 * jaccard + 0.20 * edit_score + 0.30 * cn_sim + 0.15 * py_sim
    return 0.7 * jaccard + 0.3 * edit_score


def _chinese_ngram_similarity(s1: str, s2: str, n: int = 2) -> float:
    """计算中文字符 n-gram 相似度"""
    if not s1 or not s2:
        return 0.0
    
    # 提取中文字符
    c1 = re.sub(r'[^\u4e00-\u9fff]', '', s1)
    c2 = re.sub(r'[^\u4e00-\u9fff]', '', s2)
    
    if not c1 or not c2:
        return 0.0
    
    grams1 = {c1[i:i+n] for i in range(max(0, len(c1) - n + 1))}
    grams2 = {c2[i:i+n] for i in range(max(0, len(c2) - n + 1))}
    
    if not grams1 or not grams2:
        return 0.0
    
    intersection = len(grams1 & grams2)
    union = len(grams1 | grams2)
    
    return intersection / union if union > 0 else 0.0


def _pinyin_similarity(s1: str, s2: str) -> float:
    """拼音首字母相似度 — 解决中文同音/近音词匹配问题。
    
    例如：'素材' (sl) vs '斯料' (sl) → 高相似度
    '竞价' (jj) vs '竟价' (jj) → 高相似度
    """
    if not s1 or not s2:
        return 0.0
    
    initials1 = _chinese_to_pinyin_initials(s1)
    initials2 = _chinese_to_pinyin_initials(s2)
    
    if not initials1 or not initials2:
        return 0.0
    
    if initials1 == initials2:
        return 1.0
    
    # 用编辑距离计算拼音首字母的相似度
    dist = levenshtein_distance(initials1, initials2)
    max_len = max(len(initials1), len(initials2))
    return 1.0 - dist / max_len if max_len > 0 else 0.0


def _char_ngrams(text: str, n: int = 2) -> set:
    """生成字符 n-gram"""
    return {text[i:i+n] for i in range(len(text) - n + 1)}


# ──────────────────────────────────────────────
# Domain Context Expansion — 领域上下文扩展增强
# ──────────────────────────────────────────────

# 更丰富的广告平台领域上下文映射
_DOMAIN_CONTEXT_MAP = {
    '素材': ['creative', 'artwork', 'ad_material', 'banner', 'video_ad', 'image_ad', 'rich_media'],
    '审核': ['review', 'audit', 'approval', 'quality_check', 'compliance', 'moderation'],
    '竞价': ['bidding', 'auction', 'pacing', 'optimization', 'rtb', 'cpm', 'cpc', 'ocpx'],
    '投放': ['delivery', 'campaign', 'pacing', 'budget', 'targeting', 'scheduling'],
    '报表': ['report', 'stats', 'analytics', 'dashboard', 'metric', 'kpi'],
    '账户': ['account', 'billing', 'payment', 'invoice', 'recharge', 'topup'],
    '权限': ['permission', 'auth', 'rbac', 'acl', 'role', 'access_control'],
    '缓存': ['cache', 'redis', 'performance', 'hit_rate', 'eviction', 'ttl'],
    '消息': ['mq', 'kafka', 'event', 'async', 'callback', 'webhook', 'notification'],
    '定时': ['cron', 'schedule', 'timer', 'trigger', 'periodic', 'batch_job'],
    '迁移': ['migration', 'data_migration', 'schema_change', 'etl', 'sync'],
    '监控': ['monitor', 'alert', 'prometheus', 'grafana', 'health_check', 'probe'],
    '日志': ['log', 'logging', 'zap', 'structured_log', 'trace_id', 'op_log'],
    '限流': ['rate_limit', 'throttle', 'token_bucket', 'leaky_bucket', 'qps_limit'],
    '幂等': ['idempotent', 'dedup', 'unique_key', 'distributed_lock', 'setnx'],
    '加密': ['encrypt', 'aes', 'rsa', 'hash', 'crypto', 'cipher'],
    '搜索': ['search', 'es', 'elasticsearch', 'full_text', 'keyword_search'],
    '推送': ['push', 'notification', 'notify', 'alert', 'webhook', 'callback'],
    '对账': ['reconcile', 'settlement', 'billing', 'finance', 'audit_trail'],
    '风控': ['risk', 'fraud', 'anti_cheat', 'security', 'waf', 'abuse_detection'],
}

def _get_domain_context(query: str) -> List[str]:
    """根据查询语义返回领域相关的上下文扩展词（增强版）。"""
    query_lower = query.lower()
    results = []
    for key, ctx_words in _DOMAIN_CONTEXT_MAP.items():
        if key in query_lower or any(k in query_lower for k in ctx_words):
            results.extend(ctx_words)
    return list(dict.fromkeys(results))[:15]  # 去重并限制数量


# ──────────────────────────────────────────────
# Synonym Expansion — 同义词扩展
# ──────────────────────────────────────────────

def expand_synonyms(query: str, profile: dict = None) -> List[str]:
    """同义词扩展 — 从 profile 的 synonym_map 和 query_aliases 扩展查询词
    
    增强版：同时支持 synonym_map（业务词→多语言同义词）和 query_aliases（中文→代码映射）。
    
    新增：上下文感知扩展 — 根据 IR 数据自动发现相关术语。
    新增：Query Variant Expansion — 生成多种查询变体提升召回率。
    
    内置同义词词典（广告平台领域）：
    - 素材/creative/ad/广告素材
    - 竞价/bidding/出价/拍卖
    - 审核/review/audit/审批
    - 发布/publish/release/上线
    - 广告组/adgroup/ad group/广告计划组
    - 广告计划/campaign/ad campaign/推广计划
    - 权限/permission/auth/access control
    - 缓存/cache/redis/memory
    - 消息队列/mq/kafka/rabbitmq/message queue
    """
    keywords = [query]
    
    # 内置广告平台同义词词典（扩展版）— 每对双向映射只保留一个方向
    builtin_synonyms = {
        '素材': ['creative', 'ad_material', '广告素材', 'asset', 'artwork'],
        'creative': ['素材', 'ad_material', '广告素材', 'asset', 'artwork'],
        '竞价': ['bidding', '出价', 'auction', 'bid', 'cpm', 'cpc', 'ocpx'],
        'bidding': ['竞价', '出价', 'auction', 'bid', 'cpm', 'cpc'],
        '审核': ['review', 'audit', '审批', 'approval', 'quality_check'],
        'review': ['审核', 'audit', '审批', 'approval', 'quality_check'],
        '发布': ['publish', 'release', '上线', 'deploy', 'go_live'],
        'publish': ['发布', 'release', '上线', 'deploy', 'go_live'],
        '广告组': ['adgroup', 'ad_group', 'ad group'],
        'adgroup': ['广告组', 'ad_group', 'ad group'],
        '广告计划': ['campaign', 'ad_campaign', '推广计划', 'ad plan'],
        'campaign': ['广告计划', 'ad_campaign', '推广计划', 'ad plan'],
        '权限': ['permission', 'auth', 'access', 'acl', 'role', 'rbac'],
        'permission': ['权限', 'auth', 'access', 'acl', 'role'],
        '缓存': ['cache', 'redis', 'memory', 'memcached', 'cdn'],
        'cache': ['缓存', 'redis', 'memory', 'memcached', 'cdn'],
        '消息队列': ['mq', 'kafka', 'rabbitmq', 'message queue', 'event bus'],
        'kafka': ['消息队列', 'mq', 'rabbitmq', 'event bus'],
        '推送': ['push', 'notification', 'notify', 'alert'],
        'push': ['推送', 'notification', 'notify', 'alert'],
        '预算': ['budget', 'spending', '花费', 'cost', 'billing'],
        'budget': ['预算', 'spending', '花费', 'cost', 'billing'],
        '定向': ['targeting', 'audience', '定向投放', 'geo', 'demographic'],
        'targeting': ['定向', 'audience', '定向投放', 'geo'],
        '展示': ['impression', 'display', '曝光', 'view'],
        'impression': ['展示', 'display', '曝光', 'view'],
        '点击': ['click', 'ctr', '点击率'],
        'click': ['点击', 'ctr', '点击率'],
        '转化': ['conversion', 'cvr', '转化事件', 'cv', 'goal'],
        'conversion': ['转化', 'cvr', '转化事件', 'cv'],
        '报表': ['report', 'stats', 'statistics', '统计', 'analytics', 'dashboard'],
        'report': ['报表', 'stats', 'statistics', '统计', 'analytics'],
        '限流': ['rate limit', 'throttle', 'qps limit', '流量控制'],
        '幂等': ['idempotent', '重复提交', 'retry safe'],
        '审计': ['audit_log', '操作日志', 'trace', 'op log'],
    }
    
    query_lower = query.lower()
    
    # 1. 从内置同义词扩展
    for term, variants in builtin_synonyms.items():
        if term.lower() in query_lower:
            keywords.extend(variants)
    
    # 2-3. 从 profile 的 synonym_map + query_aliases 扩展（合并逻辑）
    if profile:
        profile_data = profile.get('profile', profile) if isinstance(profile, dict) else profile
        for source_key in ('synonym_map', 'query_aliases'):
            mapping = profile_data.get(source_key, {})
            for term, variants in mapping.items():
                if term.lower() in query_lower:
                    keywords.extend(variants)
    
    # 4. 从 query 中提取中英文关键词（驼峰分割）— 使用模块级 re
    camel = re.findall(r'[A-Z][a-z]+|[a-z]+', query)
    keywords.extend(camel)
    
    # 5. 领域上下文扩展
    domain_context = _get_domain_context(query)
    if domain_context:
        keywords.extend(domain_context)
    
    # 6. Query Variant Expansion — 生成多种查询变体提升召回率
    variants = _generate_query_variants(query)
    if variants:
        keywords.extend(variants)
    
    # 去重，保留顺序
    keywords = list(dict.fromkeys(keywords))
    return keywords[:30]  # 最多 30 个关键词


# ──────────────────────────────────────────────
# Query Variant Expansion — 查询变体生成
# ──────────────────────────────────────────────

# 常见缩写映射表
ABBREVIATION_MAP = {
    'campaign': ['campaign', 'ad_plan', '推广计划'],
    'adgroup': ['adgroup', 'ad_group', '广告组'],
    'creative': ['creative', '素材', 'ad_material'],
    'bidding': ['bidding', '竞价', '出价'],
    'review': ['review', '审核', 'approval'],
    'publish': ['publish', '发布', '上线'],
    'permission': ['permission', '权限', 'auth'],
    'cache': ['cache', '缓存', 'redis'],
    'kafka': ['kafka', '消息队列', 'mq'],
    'rpc': ['rpc', 'grpc', '远程调用'],
    'http': ['http', 'api', 'web请求'],
    'db': ['db', 'database', '数据库'],
    'index': ['index', '索引', 'search_index'],
    'page': ['page', 'pagination', '分页'],
    'timeout': ['timeout', '超时', 'deadline'],
    'retry': ['retry', '重试', 'recovery'],
}


def _generate_query_variants(query: str) -> List[str]:
    """生成查询变体以提升召回率。
    
    策略：
    1. 短查询（≤3字符）：额外生成单字/拼音首字母变体
    2. 驼峰分割：CamelCase → camel_case / CamelCase
    3. 缩写展开：RPC → remote procedure call
    4. 大小写变换：CamelCase → camelcase
    5. 子串提取：长词 → 关键子串
    """
    variants = []
    query_lower = query.lower().strip()
    
    # 1. 驼峰分割 → snake_case 和 kebab-case
    # 将 CamelCase 转换为 camel_case
    snake_case = re.sub(r'([a-z])([A-Z])', r'\1_\2', query).lower()
    if snake_case != query_lower and snake_case:
        variants.append(snake_case)
    
    # kebab-case
    kebab_case = re.sub(r'([a-z])([A-Z])', r'\1-\2', query).lower()
    if kebab_case != query_lower and kebab_case:
        variants.append(kebab_case)
    
    # 2. 缩写展开
    for abbr, expansions in ABBREVIATION_MAP.items():
        if abbr in query_lower:
            for exp in expansions:
                if exp not in variants and exp not in query_lower:
                    variants.append(exp)
    
    # 3. 短查询（≤3字符）：生成单字变体
    if len(query) <= 3 and len(query) > 0:
        # 对中文：按字符拆分
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', query)
        if chinese_chars:
            variants.extend(chinese_chars)
        # 对英文：生成所有前缀
        if any(c.isalpha() for c in query):
            for i in range(1, len(query) + 1):
                prefix = query[:i]
                if prefix and prefix not in variants:
                    variants.append(prefix)
    
    # 4. 提取关键子串（保留 ≥3 字符的部分）
    parts = re.split(r'[_\-\s/]+', query)
    for part in parts:
        if 3 <= len(part) <= 20 and part not in variants:
            variants.append(part)
    
    # 限制变体数量，避免噪声过多
    return variants[:10]


def classify_query(query: str) -> str:
    """分类查询类型，用于自适应阈值。
    
    Returns:
        'precise' / 'general' / 'broad'
    """
    query_lower = query.lower()
    # 精确匹配：API路径、错误码、CamelCase
    if re.match(r'^/api/', query_lower):
        return 'precise'
    if re.search(r'\b\d{3,}\b', query_lower):
        return 'precise'
    if re.match(r'^[A-Z][a-z]+[A-Z]', query):
        return 'precise'
    # 宽泛：短查询
    if len(query) <= 2:
        return 'broad'
    return 'general'


def adaptive_threshold(query: str, query_type: str = None) -> float:
    """根据查询特征动态调整 fuzzy 搜索阈值。
    
    Args:
        query: 原始查询字符串
        query_type: classify_query() 返回的类型
        
    Returns:
        自适应阈值 [0.35, 0.8]
    """
    if query_type is None:
        query_type = classify_query(query)
    
    base = 0.5
    if query_type == 'precise':
        base = 0.65
    elif query_type == 'broad':
        base = 0.35
    
    # 短查询提高阈值，避免噪声
    if len(query) <= 2:
        base = max(base, 0.65)
    
    return min(base, 0.8)


# ──────────────────────────────────────────────
# Semantic Search — 轻量级 TF-IDF + Cosine Similarity
# ──────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    """轻量分词：中文按字符切分，英文按单词切分"""
    # 使用模块级 re，避免重复 import
    # 提取英文单词
    words = re.findall(r'[a-zA-Z]+', text)
    # 提取中文字符
    chars = re.findall(r'[\u4e00-\u9fff]', text)
    return words + chars


def _compute_tf(tokens: List[str]) -> Dict[str, float]:
    """计算词频 (Term Frequency)"""
    tf = {}
    if not tokens:
        return tf
    for token in tokens:
        tf[token] = tf.get(token, 0) + 1
    # 归一化
    total = len(tokens)
    for token in tf:
        tf[token] /= total
    return tf


def _compute_idf(documents: List[List[str]]) -> Dict[str, float]:
    """计算逆文档频率 (Inverse Document Frequency)"""
    n_docs = len(documents)
    if n_docs == 0:
        return {}
    
    df = {}  # document frequency
    for doc in documents:
        unique_tokens = set(doc)
        for token in unique_tokens:
            df[token] = df.get(token, 0) + 1
    
    idf = {}
    for token, freq in df.items():
        idf[token] = 1.0 + math.log(n_docs / (1 + freq))
    
    return idf


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """计算两个向量的余弦相似度"""
    if not vec_a or not vec_b:
        return 0.0
    
    # 交集
    common_keys = set(vec_a.keys()) & set(vec_b.keys())
    if not common_keys:
        return 0.0
    
    dot_product = sum(vec_a[k] * vec_b[k] for k in common_keys)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)


def semantic_search(query: str, documents: List[str], top_k: int = 10) -> List[Dict]:
    """轻量级语义搜索 — 基于 TF-IDF + Cosine Similarity
    
    Args:
        query: 查询文本
        documents: 文档列表（可以是函数签名、路由描述、struct 字段等）
        top_k: 返回前 K 个结果
    
    Returns:
        List of {doc, score, rank}
    """
    import math
    
    query_tokens = _tokenize(query)
    query_tf = _compute_tf(query_tokens)
    
    doc_tokens_list = [_tokenize(doc) for doc in documents]
    idf = _compute_idf(doc_tokens_list)
    
    # 为每个文档计算 IDF 加权的 TF 向量
    doc_vectors = []
    for tokens in doc_tokens_list:
        tf = _compute_tf(tokens)
        # IDF 加权
        weighted = {token: tf[token] * idf.get(token, 1.0) for token in tf}
        doc_vectors.append(weighted)
    
    # 计算相似度
    scores = []
    for i, doc_vec in enumerate(doc_vectors):
        sim = _cosine_similarity(query_tf, doc_vec)
        if sim > 0:
            scores.append({'doc': documents[i], 'score': sim, 'rank': i})
    
    # 排序
    scores.sort(key=lambda x: x['score'], reverse=True)
    return scores[:top_k]


def semantic_expand_query(query: str, ir_data: dict, top_k: int = 20) -> List[str]:
    """基于 IR 数据的语义查询扩展
    
    策略：
    1. 从 IR 中收集所有可搜索文本（函数名、路由、struct、描述）
    2. 用语义搜索找到与 query 最相关的 IR 条目
    3. 提取其中的关键词作为扩展查询词
    
    Returns:
        扩展后的查询词列表
    """
    searchable = []
    
    # 收集函数签名
    for func in ir_data.get('functions', []):
        sig = func.get('signature', '')
        if sig:
            searchable.append(sig)
    
    # 收集路由描述
    for route in ir_data.get('routes', []):
        route_str = f"{route.get('method', '')} {route.get('path', '')} {route.get('handler', '')}"
        if route_str:
            searchable.append(route_str)
    
    # 收集 handler 描述
    for bl in ir_data.get('business_logic', []):
        desc = bl.get('description', '')
        if desc:
            searchable.append(desc)
    
    # 收集 struct 名和字段
    for struct in ir_data.get('structs', []):
        struct_str = f"{struct.get('name', '')} {' '.join(f.get('name', '') for f in struct.get('fields', []))}"
        if struct_str:
            searchable.append(struct_str)
    
    # 语义搜索
    results = semantic_search(query, searchable, top_k=min(top_k, len(searchable)))
    
    # 提取相关关键词
    expanded = []
    for r in results:
        doc = r['doc']
        # 从匹配的文档中提取有意义的词
        tokens = _tokenize(doc)
        for t in tokens:
            if len(t) >= 2 and t not in expanded:
                expanded.append(t)
        if len(expanded) >= top_k * 2:
            break
    
    return expanded[:top_k * 2]

def search_code(
    query: str, repo_path: str, top_k: int = 10, cache_dir: str = None,
    profile: dict = None, ir_cache: Optional[dict] = None,
) -> List[Dict]:
    """搜索代码 — 从 IR 缓存中匹配函数/路由/struct
    
    增强：
    1. 使用 expand_synonyms（支持 synonym_map + query_aliases）
    2. fuzzy_score 替代精确匹配
    3. 语义搜索作为补充
    """
    # 加载 profile 获取 query_aliases
    if profile is None:
        import json
        profile_path = str(Path(__file__).parent.parent / "profiles" / "default.json")
        if Path(profile_path).exists():
            try:
                with open(profile_path) as f:
                    profile = json.load(f)
            except:
                pass
    
    # 使用 expand_synonyms 扩展查询词（替代旧的 expand_query）
    expanded_queries = expand_synonyms(query, profile) if profile else [query]

    # 优先使用传入的 ir_cache，避免重复读取磁盘
    ir_data = None
    if ir_cache is not None:
        ir_data = ir_cache
    elif cache_dir:
        cache_file = Path(cache_dir) / "ir_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    ir_data = json.load(f)
            except Exception:
                pass

    if ir_data:
        # 先用 fuzzy 搜索
        results = _search_code_fuzzy(ir_data, expanded_queries, top_k)
        
        # 如果结果太少，启用 BM25 补充
        if len(results) < top_k // 2:
            try:
                from .enhanced_search import BM25Scorer
                searchable_docs = []
                for func in ir_data.get('functions', []):
                    sig = func.get('signature', func.get('name', ''))
                    if sig:
                        searchable_docs.append(sig)
                for route in ir_data.get('routes', []):
                    rs = f"{route.get('method', '')} {route.get('path', '')} {route.get('handler', '')}"
                    if rs:
                        searchable_docs.append(rs)
                
                if searchable_docs:
                    scorer = BM25Scorer()
                    scorer.fit(searchable_docs)
                    bm25_results = scorer.search(query, top_k=top_k)
                    for doc_idx, score in bm25_results:
                        # Map back to IR entries
                        if doc_idx < len(ir_data.get('functions', [])):
                            func = ir_data['functions'][doc_idx]
                            key = (func.get('file', ''), 'function')
                            if key not in {(r.get('path'), r.get('type')) for r in results}:
                                results.append({
                                    'type': 'function',
                                    'title': func.get('name', ''),
                                    'path': func.get('file', ''),
                                    'line': func.get('line', 0),
                                    'content': func.get('signature', ''),
                                    'score': score,
                                    'source': 'bm25',
                                })
            except Exception:
                pass  # BM25 is optional enhancement
            
            # 如果结果仍然太少，启用语义搜索补充
            if len(results) < top_k // 2:
                semantic_queries = semantic_expand_query(query, ir_data, top_k=15)
                if semantic_queries:
                    semantic_results = _search_code_fuzzy(ir_data, semantic_queries, top_k)
                    # 合并去重（基于 path+type）
                    seen = {(r.get('path'), r.get('type')) for r in results}
                    for sr in semantic_results:
                        key = (sr.get('path'), sr.get('type'))
                        if key not in seen:
                            seen.add(key)
                            results.append(sr)
        
        return results[:top_k]
    
    return []


def _search_code_fuzzy(ir_data: dict, queries: List[str], top_k: int) -> List[Dict]:
    """Fuzzy 搜索 — 使用 adaptive threshold 替代固定 0.3"""
    results = []
    for q in queries:
        query_lower = q.lower()
        # Compute adaptive threshold for this query
        try:
            from .enhanced_search import classify_query, adaptive_threshold
            qtype = classify_query(q)
            min_threshold = adaptive_threshold(q, qtype)
        except Exception:
            min_threshold = 0.5  # Default safe threshold
        
        # Search functions
        for func in ir_data.get('functions', []):
            fname = func.get('name', '').lower()
            fsig = func.get('signature', '').lower()
            score = fuzzy_score(query_lower, fname)
            if score >= min_threshold:
                results.append({
                    'type': 'function',
                    'title': func['name'],
                    'path': func.get('file', ''),
                    'line': func.get('line', 0),
                    'content': func.get('signature', ''),
                    'score': score,
                })
        
        # Search routes
        for route in ir_data.get('routes', []):
            route_str = f"{route.get('method', '')} {route.get('path', '')} {route.get('handler', '')}".lower()
            score = fuzzy_score(query_lower, route_str)
            if score >= min_threshold:
                results.append({
                    'type': 'route',
                    'title': f"{route.get('method', '').upper()} {route.get('path', '')}",
                    'path': route.get('file', ''),
                    'line': route.get('line', 0),
                    'content': route.get('handler', ''),
                    'score': score,
                })
        
        # Search struct
        for struct in ir_data.get('structs', []):
            sname = struct.get('name', '').lower()
            score = fuzzy_score(query_lower, sname)
            if score >= min_threshold:
                results.append({
                    'type': 'struct',
                    'title': struct['name'],
                    'path': struct.get('file', ''),
                    'line': struct.get('line', 0),
                    'content': '\n'.join([f.get('name', str(f)) for f in struct.get('fields', [])[:5]]),
                    'score': score,
                })
        
        # Search entity-table mapping
        for et in ir_data.get('entity_tables', []):
            entity = et.get('entity', '')
            table = et.get('table', '')
            searchable = f"{entity} {table}".lower()
            score = fuzzy_score(query_lower, searchable)
            if score >= min_threshold:
                results.append({
                    'type': 'entity_table',
                    'title': f"{entity} -> {table}",
                    'path': et.get('file', ''),
                    'line': 0,
                    'content': searchable,
                    'score': score,
                })
        
        # Search business_logic
        for bl in ir_data.get('business_logic', []):
            handler = bl.get('handler', '')
            route = bl.get('route', '')
            searchable = f"{handler} {route}".lower()
            score = fuzzy_score(query_lower, searchable)
            if score >= min_threshold:
                results.append({
                    'type': 'business_logic',
                    'title': f"业务逻辑: {handler}",
                    'path': bl.get('file', ''),
                    'line': 0,
                    'content': searchable[:200],
                    'score': score,
                })
    
    # Deduplicate (based on path + type), keep highest score
    seen = {}
    for r in results:
        key = (r.get('path'), r.get('type'))
        if key not in seen or r.get('score', 0) > seen[key].get('score', 0):
            seen[key] = r
    return list(seen.values())


def search_schema(
    query: str, repo_path: str, top_k: int = 10, cache_dir: str = None,
    ir_cache: Optional[dict] = None,
) -> List[Dict]:
    """搜索 schema — 从 IR 缓存中匹配表结构/字段"""
    if cache_dir:
        cache_file = Path(cache_dir) / "ir_cache.json"
        if cache_file.exists():
            with open(cache_file) as f:
                ir_data = json.load(f)
            
            results = []
            query_lower = query.lower()
            for table in ir_data.get('tables', []):
                table_name = table.get('name', '').lower()
                entity = table.get('entity', '').lower()
                searchable = f"{table_name} {entity}"
                score = fuzzy_score(query_lower, searchable)
                if score >= 0.3:
                    results.append({
                        'type': 'table',
                        'title': table['name'],
                        'path': table.get('file', ''),
                        'line': table.get('line', 0),
                        'content': ', '.join(table.get('columns', [])[:10]),
                        'score': score,
                    })
            
            # 也 fuzzy 搜索 columns
            for table in ir_data.get('tables', []):
                for col in table.get('columns', []):
                    col_str = str(col).lower()
                    score = fuzzy_score(query_lower, col_str)
                    if score >= 0.5:
                        results.append({
                            'type': 'column',
                            'title': f"{table.get('name', '?')}.{col}",
                            'path': table.get('file', ''),
                            'line': 0,
                            'content': col_str,
                            'score': score,
                        })
            
            return results[:10]
    
    return []


def search_api_docs(
    query: str, repo_path: str, top_k: int = 10, cache_dir: str = None,
    profile: Optional[dict] = None, ir_cache: Optional[dict] = None,
) -> List[Dict]:
    """搜索 API 文档 — 从 IR 缓存中匹配路由/Request/Response
    
    增强：
    1. 使用 fuzzy_score 替代精确匹配
    2. 支持 synonym_map 扩展查询词
    3. 同时搜索 path + handler + request + response
    """
    # 扩展查询词
    expanded_queries = expand_synonyms(query, profile) if profile else [query]
    
    if cache_dir:
        cache_file = Path(cache_dir) / "ir_cache.json"
        if cache_file.exists():
            with open(cache_file) as f:
                ir_data = json.load(f)
            
            results = []
            for q in expanded_queries:
                query_lower = q.lower()
                for route in ir_data.get('routes', []):
                    route_str = f"{route.get('method', '')} {route.get('path', '')} {route.get('handler', '')} {route.get('request', '')} {route.get('response', '')}".lower()
                    score = fuzzy_score(query_lower, route_str)
                    if score >= 0.3:
                        results.append({
                            'type': 'api',
                            'title': f"{route.get('method', '').upper()} {route.get('path', '')}",
                            'path': route.get('file', ''),
                            'line': route.get('line', 0),
                            'content': f"Handler: {route.get('handler', '')}\nRequest: {route.get('request', '')}\nResponse: {route.get('response', '')}",
                            'score': score,
                        })
            
            # 去重（基于 path），保留最高分
            seen = {}
            for r in results:
                key = r.get('path', '')
                if key not in seen or r.get('score', 0) > seen[key].get('score', 0):
                    seen[key] = r
            return list(seen.values())[:top_k]
    
    return []


def search_business(
    query: str, repo_path: str, top_k: int = 10, cache_dir: str = None,
    ir_cache: Optional[dict] = None,
) -> List[Dict]:
    """搜索业务逻辑 — 从 IR 缓存中匹配 business_logic / core_flows / state machines"""
    if cache_dir:
        cache_file = Path(cache_dir) / "ir_cache.json"
        if cache_file.exists():
            with open(cache_file) as f:
                ir_data = json.load(f)
            
            results = []
            query_lower = query.lower()
            
            # 搜索 business_logic
            for bl in ir_data.get('business_logic', []):
                handler = bl.get('handler', '')
                route = bl.get('route', '')
                desc = bl.get('description', '')
                searchable = f"{handler} {route} {desc}".lower()
                score = fuzzy_score(query_lower, searchable)
                if score >= 0.3:
                    results.append({
                        'type': 'business_logic',
                        'title': f"业务逻辑: {handler}",
                        'path': bl.get('file', ''),
                        'line': 0,
                        'content': searchable[:300],
                        'score': score,
                    })
            
            # 搜索 core_flows（如果存在）
            for cf in ir_data.get('core_flows', []):
                fname = cf.get('flow_name', '')
                fprefix = cf.get('route_prefix', '')
                searchable = f"{fname} {fprefix}".lower()
                score = fuzzy_score(query_lower, searchable)
                if score >= 0.3:
                    results.append({
                        'type': 'core_flow',
                        'title': f"核心流程: {fname}",
                        'path': '',
                        'line': 0,
                        'content': searchable[:300],
                        'score': score,
                    })
            
            return results[:top_k]
    
    return []


def search_entity_relations(
    query: str, repo_path: str, top_k: int = 10, cache_dir: str = None,
    ir_cache: Optional[dict] = None,
) -> List[Dict]:
    """搜索实体关系 — 从 IR 缓存中匹配 entity_tables + conditions + relations"""
    if cache_dir:
        cache_file = Path(cache_dir) / "ir_cache.json"
        if cache_file.exists():
            with open(cache_file) as f:
                ir_data = json.load(f)
            
            results = []
            query_lower = query.lower()
            
            # 搜索 entity-table 映射
            for et in ir_data.get('entity_tables', []):
                entity = et.get('entity', '').lower()
                table = et.get('table', '').lower()
                searchable = f"{entity} {table}"
                score = fuzzy_score(query_lower, searchable)
                if score >= 0.3:
                    results.append({
                        'type': 'entity_relation',
                        'title': f"{et.get('entity', '')} → {et.get('table', '')}",
                        'path': et.get('file', ''),
                        'line': 0,
                        'content': searchable,
                        'score': score,
                    })
            
            # 搜索 conditions（查询条件）
            for cond in ir_data.get('conditions', []):
                cond_str = ' '.join(cond.get('fields', [])).lower()
                score = fuzzy_score(query_lower, cond_str)
                if score >= 0.3:
                    results.append({
                        'type': 'condition',
                        'title': f"查询条件: {cond.get('name', '')}",
                        'path': cond.get('file', ''),
                        'line': 0,
                        'content': cond_str,
                        'score': score,
                    })
            
            # 搜索 config 配置
            for cfg in ir_data.get('configs', []):
                cfg_str = f"{cfg.get('key', '')} {cfg.get('value', '')}".lower()
                score = fuzzy_score(query_lower, cfg_str)
                if score >= 0.3:
                    results.append({
                        'type': 'config',
                        'title': f"配置: {cfg.get('key', '')}",
                        'path': cfg.get('file', ''),
                        'line': 0,
                        'content': cfg_str,
                        'score': score,
                    })
            
            return results[:top_k]
    
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
    """RRF 融合多路结果 — 增强版

    改进：
    1. 使用 (type, title) 作为去重键，比纯 path 更精确
    2. 保留各路的 source 标签
    3. 融合分数 = RRF rank + 原始 score 加权
    4. **source_type 加权**: code=1.5, api_docs=1.2, schema=1.0, business=0.8
       代码匹配（function/route）应比 schema/business 匹配权重更高
    """
    # Source type weight mapping
    SOURCE_WEIGHTS = {
        "code": 1.5,
        "api_docs": 1.2,
        "schema": 1.0,
        "business": 0.8,
    }

    def _get_source_weight(item: Dict) -> float:
        """Get weight based on evidence source/type."""
        stype = item.get("source_type", "") or item.get("type", "")
        for key, weight in SOURCE_WEIGHTS.items():
            if key in str(stype).lower():
                return weight
        return 1.0

    ranked = {}
    for path_results in candidates:
        for i, item in enumerate(path_results):
            # 使用 type+title 作为去重键（比 path 更精确）
            item_type = item.get('type', '')
            item_title = item.get('title', '')
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
            w = _get_source_weight(item)
            rank_score = w * 1.0 / (k + i + 1)
            # 原始分数加权
            orig_score = item.get('score', 0.0)
            entry['score'] += rank_score * 0.6 + orig_score * 0.4
            entry['original_score'] = max(entry['original_score'], orig_score)

    sorted_items = sorted(ranked.values(), key=lambda x: x['score'], reverse=True)

    # 转换为输出格式
    result = []
    for item in sorted_items[:10]:
        result.append({
            'type': item['type'],
            'title': item['title'],
            'path': item['path'],
            'line': item['line'],
            'content': item['content'],
            'score': round(item['score'], 4),
            'sources': list(item['sources']),
        })

    return result


# ──────────────────────────────────────────────
# 5. 主流程
# ──────────────────────────────────────────────



def search_kb(query: str, kb_paths: List[str], top_k: int = 10, profile_path: str = None) -> List[Dict]:
    """搜索知识库 — 从 markdown 文件中提取相关知识"""
    results = []
    
    if not kb_paths:
        kb_paths = ["/Users/yanping.ma/ryan-personal-knowledge/knowledge"]
    
    for kb_path in kb_paths:
        kb_dir = Path(kb_path)
        if not kb_dir.exists():
            continue
        
        md_files = list(kb_dir.rglob('**/*.md'))
        for md_file in md_files[:50]:
            try:
                md_content = md_file.read_text(encoding='utf-8', errors='ignore')
            except:
                continue
            
            query_lower = query.lower()
            if query_lower in md_content.lower():
                idx = md_content.lower().find(query_lower)
                context_start = max(0, idx - 200)
                context_end = min(len(md_content), idx + 500)
                context = md_content[context_start:context_end].strip()
                
                results.append({
                    'type': 'knowledge',
                    'title': md_file.name,
                    'path': str(md_file.relative_to(kb_dir.parent)),
                    'content': context[:300],
                    'score': 1.0,
                })
    
    return results[:top_k]

def run_evidence_query(
    query: str,
    profile_path: str = None,
    wiki_path: str = None,
    top_k: int = 10,
    sources: List[str] = None,
    cache_dir: str = None,
    ir_cache: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    执行多路证据查询：
    1. 意图识别
    2. 多路搜索
    3. RRF 融合
    4. 返回结果
    
    Args:
        ir_cache: 可选，预加载的 IR 缓存数据。避免重复从磁盘读取。
    """
    intent, confidence = extract_intent(query)

    # 默认搜索源
    if not sources:
        sources = ["code", "schema", "api_docs"]

    # 多路搜索 — 传入 ir_cache 避免重复加载
    candidates = []
    path_results = {}

    if "code" in sources:
        results = search_code(query, "", top_k, cache_dir=cache_dir, ir_cache=ir_cache)
        candidates.append(results)
        path_results['code'] = results

    if "schema" in sources:
        results = search_schema(query, "", top_k, cache_dir=cache_dir, ir_cache=ir_cache)
        candidates.append(results)
        path_results['schema'] = results

    if "api_docs" in sources:
        results = search_api_docs(query, "", top_k, cache_dir=cache_dir, ir_cache=ir_cache)
        candidates.append(results)
        path_results['api_docs'] = results

    if "entity_relations" in sources:
        results = search_entity_relations(query, "", top_k, cache_dir=cache_dir, ir_cache=ir_cache)
        if results:
            candidates.append(results)
            path_results['entity_relations'] = results

    if "business" in sources:
        results = search_business(query, "", top_k, cache_dir=cache_dir, ir_cache=ir_cache)
        if results:
            candidates.append(results)
            path_results['business'] = results

    # 知识库搜索
    if "knowledge" in sources:
        kb_paths = []
        profile_path = str(Path(__file__).parent.parent / "profiles" / "default.json")
        try:
            with open(profile_path) as f:
                profile = json.load(f)
            kb_paths = profile.get("knowledge_base_paths", [])
        except:
            pass
        results = search_kb(query, kb_paths, top_k, profile_path)
        if results:
            candidates.append(results)
            path_results["knowledge"] = results

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
        'evidence': fused[:10],
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
    parser.add_argument('--cache-dir', default=None, help='IR 缓存目录（learn_repo.py 输出目录）')

    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(',')]
    result = run_evidence_query(
        query=args.query,
        profile_path=args.profile,
        wiki_path=args.wiki,
        top_k=args.top_k,
        sources=sources,
        cache_dir=args.cache_dir,
    )

    print(f"🔍 查询: {result['query']}")
    print(f"🎯 意图: {result['intent']} (置信度: {result['confidence']:.3f})")
    print(f"📊 结果: {result['total_results']} 个证据")
    print(f"📦 状态: {result['status']}")
    print()
    for i, ev in enumerate(result['evidence'][:result['top_k'] if hasattr(result, 'top_k') else 5], 1):
        print(f"  {i}. {ev.get('title', ev.get('path', 'unknown'))}")


def _infer_semantic_tags(queries: List[str]) -> List[str]:
    """从查询词推断语义标签"""
    tags = []
    cn_map = {
        'create': '创建', 'add': '新增', 'new': '新建',
        'get': '查询', 'list': '列表', 'search': '搜索',
        'delete': '删除', 'update': '更新', 'edit': '编辑',
        'share': '分享', 'publish': '发布', 'review': '审核',
        'bid': '竞价', 'price': '价格', 'cost': '成本',
        'cache': '缓存', 'index': '索引', 'sync': '同步',
        'notify': '通知', 'report': '报表', 'stat': '统计',
        # 广告平台特有
        'creative': '创意', 'adgroup': '广告组', 'campaign': '广告计划',
        'targeting': '定向', 'audience': '受众', 'placement': '广告位',
        'impression': '展示', 'click': '点击', 'conversion': '转化',
        'ctr': '点击率', 'cvr': '转化率', 'ecpm': '千次展示收益',
        'budget': '预算', 'billing': '计费', 'invoice': '发票',
        'fraud': '反作弊', 'audit': '审核', 'quality': '质量',
        'delivery': '投放', 'reach': '触达', 'frequency': '频次',
        'pacing': '投放节奏', 'optimization': '优化',
        # 技术特有
        'gateway': '网关', 'proxy': '代理', 'loadbalancer': '负载均衡',
        'monitor': '监控', 'alert': '告警', 'log': '日志',
        'pipeline': '管道', 'stream': '流', 'batch': '批量',
        'realtime': '实时', 'offline': '离线', 'online': '在线',
    }
    
    for q in queries:
        q_lower = q.lower()
        for en, cn in cn_map.items():
            if en in q_lower:
                tags.append(en)
                tags.append(cn)
    
    return list(set(tags))


def _search_by_tags(ir_data: dict, tags: List[str], top_k: int = 10) -> List[Dict]:
    """按语义标签搜索"""
    results = []
    
    # 搜索 functions
    for func in ir_data.get('functions', []):
        name = func.get('name', '').lower()
        for tag in tags:
            if tag in name:
                results.append({
                    'type': 'function',
                    'title': func.get('name', ''),
                    'path': func.get('file', ''),
                    'content': f"函数: {func.get('name', '')}",
                    'score': 1.0,
                    'source': 'semantic_tag',
                })
                break
    
    # 搜索 routes
    for route in ir_data.get('routes', []):
        path = route.get('path', '').lower()
        for tag in tags:
            if tag in path:
                results.append({
                    'type': 'route',
                    'title': route.get('path', ''),
                    'path': route.get('module', ''),
                    'content': f"路由: {route.get('method', '')} {route.get('path', '')}",
                    'score': 1.0,
                    'source': 'semantic_tag',
                })
                break
    
    return results[:top_k]


# ============================================================================
# TF-IDF 语义搜索
# ============================================================================

class SimpleVectorizer:
    """简单 TF-IDF 向量化器"""
    
    def __init__(self):
        self.idf = {}
        self.vocab = {}
    
    def fit(self, documents: List[str]):
        """构建 IDF"""
        n_docs = len(documents)
        df = {}
        
        for doc in documents:
            terms = set(doc.lower().split())
            for term in terms:
                df[term] = df.get(term, 0) + 1
        
        for term, count in df.items():
            self.idf[term] = math.log(n_docs / (1 + count))
            self.vocab[term] = len(self.vocab)
    
    def transform(self, documents: List[str]) -> List[List[float]]:
        """转换为 TF-IDF 向量"""
        vectors = []
        for doc in documents:
            terms = doc.lower().split()
            tf = {}
            for term in terms:
                tf[term] = tf.get(term, 0) + 1
            
            vector = []
            for term in self.vocab:
                tf_val = tf.get(term, 0) / max(len(terms), 1)
                vector.append(tf_val * self.idf.get(term, 0))
            
            vectors.append(vector)
        
        return vectors
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """余弦相似度"""
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot / (norm1 * norm2)


# 全局缓存
_vectorizer = None
_vectors = None


def get_vectorizer() -> SimpleVectorizer:
    """获取或创建向量器"""
    global _vectorizer, _vectors
    
    if _vectorizer is None:
        _vectorizer = SimpleVectorizer()
        _vectors = None
    
    return _vectorizer


def build_function_vectors(ir_data: dict) -> List[List[float]]:
    """构建函数/路由的 TF-IDF 向量"""
    global _vectors
    
    if _vectors is not None:
        return _vectors
    
    docs = []
    
    # 函数
    for func in ir_data.get('functions', []):
        name = func.get('name', '')
        file = func.get('file', '')
        doc = f"{name} {file}"
        docs.append(doc)
    
    # 路由
    for route in ir_data.get('routes', []):
        path = route.get('path', '')
        handler = route.get('handler', '')
        doc = f"{path} {handler}"
        docs.append(doc)
    
    if not docs:
        return []
    
    vectorizer = get_vectorizer()
    vectorizer.fit(docs)
    _vectors = vectorizer.transform(docs)
    
    return _vectors


def search_by_similarity(query: str, ir_data: dict, top_k: int = 10) -> List[Dict]:
    """基于语义相似度的搜索"""
    vectors = build_function_vectors(ir_data)
    
    if not vectors:
        return []
    
    vectorizer = get_vectorizer()
    query_vec = vectorizer.transform([query])
    
    results = []
    for i, vec in enumerate(vectors):
        sim = vectorizer.cosine_similarity(query_vec[0], vec)
        if sim > 0.1:  # 阈值
            # 判断是函数还是路由
            n_funcs = len(ir_data.get('functions', []))
            if i < n_funcs:
                func = ir_data['functions'][i]
                results.append({
                    'type': 'function',
                    'title': func.get('name', ''),
                    'path': func.get('file', ''),
                    'content': f"函数: {func.get('name', '')}",
                    'score': sim,
                    'source': 'similarity',
                })
            else:
                route_idx = i - n_funcs
                route = ir_data['routes'][route_idx]
                results.append({
                    'type': 'route',
                    'title': route.get('path', ''),
                    'path': route.get('module', ''),
                    'content': f"路由: {route.get('method', '')} {route.get('path', '')}",
                    'score': sim,
                    'source': 'similarity',
                })
    
    # 按相似度排序
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return results[:top_k]
