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
import functools
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from functools import lru_cache


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
    "relationship": ["关联", "关系", "relation", "关联到", "依赖于", "dependency"],
    "coverage": ["覆盖", "覆盖范围", "coverage", "包括哪些", "all cases"],
}

# Pre-compiled: build a reverse index for faster intent matching
_INTENT_REVERSE_INDEX: dict[str, str] = {}
for _intent, _patterns in INTENT_PATTERNS.items():
    for _p in _patterns:
        _INTENT_REVERSE_INDEX[_p] = _intent

# Chinese range regex for fuzzy matching
_RE_CHINESE_RANGE = re.compile(r'[\u4e00-\u9fff]')

# Pre-compiled regex cache — optimize repeated pattern matching
_RE_CAMEL_SPLIT = re.compile(r'(?<=[a-z])(?=[A-Z])|[_\\-\\s]')
_RE_UPPER_SEQUENCE = re.compile(r'([A-Z]+)([A-Z][a-z])')
_RE_LOWER_UPPER = re.compile(r'([a-z\\d])([A-Z])')
_ROUTE_PARAM_PATTERN = re.compile(r'\\{.*?\\}')
_WORD_NUMBER_PATTERN = re.compile(r'\\b\\d{3,}\\b')
_API_PATTERN = re.compile(r'^/api/')
_CAMEL_FIND = re.compile(r'[A-Z][a-z]+|[a-z]+')
_NUMBER_SEQ = re.compile(r'\\b\\d{3,}\\b')
_API_VERSION = re.compile(r'^[A-Z][a-z]+[A-Z]')
_CROSS_LANG_SPLIT = re.compile(r'(?<=[a-z])(?=[A-Z])|[_\\-\\s]')
_ENTITY_NAME = re.compile(r'[A-Z][a-z]+(?:[A-Z][a-z]+)*')
_CN_ENTITY = re.compile(r'[\u4e00-\u9fff]{2,6}')
_KEYWORDS = re.compile(r'[a-zA-Z]{2,}|[\u4e00-\u9fff]{2,6}')


def extract_intent(query: str) -> Tuple[str, float]:
    """意图识别 — 使用反向索引加速匹配。"""
    if not query or not query.strip():
        return ("query", 0.0)
    query_lower = query.lower()
    intent_hits: dict[str, int] = {}
    
    # Use reverse index for O(1) lookup per keyword
    for kw, intent in _INTENT_REVERSE_INDEX.items():
        if kw in query_lower:
            intent_hits[intent] = intent_hits.get(intent, 0) + 1
    
    if not intent_hits:
        return ("query", 0.0)
    
    # Convert hit counts to scores (hits / total patterns for that intent)
    scores = {intent: hits / len(INTENT_PATTERNS[intent]) 
              for intent, hits in intent_hits.items()}
    
    best_intent = max(scores, key=scores.get)
    return best_intent, scores[best_intent]


# ──────────────────────────────────────────────
# 2. 多路证据查询引擎
# ──────────────────────────────────────────────



# ──────────────────────────────────────────────
# Pinyin Phonetic Matching — 拼音近似匹配
# ──────────────────────────────────────────────

# 拼音映射表（常用中文→拼音首字母）— 已去重
_PINYIN_INITIALS = {
    '资': 'z', '料': 'l', '广': 'g', '告': 'a', '组': 'z', '计': 'j', '划': 'h',
    '竞': 'j', '价': 'j', '审': 's', '核': 'h', '发': 'f', '布': 'b', '上': 's',
    '线': 'x', '权': 'q', '限': 'x', '认': 'r', '证': 'z', '登': 'd', '录': 'l',
    '缓': 'h', '存': 'c', '消': 'x', '息': 'x', '队': 'd', '列': 'l', '报': 'b',
    '表': 'b', '统': 't', '分': 'f', '析': 'x', '预': 'y', '算': 's', '定': 'd',
    '向': 'x', '投': 't', '放': 'f', '监': 'j', '控': 'k', '跟': 'g', '踪': 'z',
    '通': 't', '知': 'z', '推': 't', '荐': 'j', '搜': 's', '索': 's', '查': 'c',
    '询': 'x', '看': 'k', '获': 'h', '取': 'q', '添': 't', '加': 'j', '新': 'x',
    '建': 'j', '编': 'b', '辑': 'j', '修': 'x', '改': 'g', '删': 's', '除': 'c',
    '移': 'y', '动': 'd', '复': 'f', '制': 'z', '拷': 'k', '贝': 'b', '备': 'b',
    '同': 't', '步': 'b', '提': 't', '交': 'j', '付': 'f', '批': 'p', '准': 'z',
    '拒': 'j', '绝': 'j', '回': 'h', '滚': 'g', '恢': 'h', '暂': 'z', '停': 't',
    '止': 'z', '活': 'h', '激': 'j', '用': 'y', '禁': 'j', '启': 'q', '销': 'x',
    '毁': 'h', '灭': 'm', '标': 'b', '注': 'z', '解': 'j', '释': 's', '详': 'x',
    '细': 'x', '描': 'm', '述': 's', '说': 's', '明': 'm', '展': 'z', '示': 's',
    '曝': 'p', '光': 'g', '点': 'd', '击': 'j', '转': 'z', '化': 'h', '收': 's',
    '藏': 'c', '反': 'f', '馈': 'k', '评': 'p', '论': 'l', '优': 'y', '调': 't',
    '整': 'z', '适': 's', '配': 'p', '匹': 'p', '对': 'd', '映': 'y', '射': 's',
    '平': 'p', '衡': 'h', '均': 'j', '匀': 'y', '担': 'd', '负': 'f', '载': 'z',
    '容': 'r', '量': 'l', '额': 'e', '满': 'm', '足': 'z', '充': 'c', '裕': 'y',
    '紧': 'j', '急': 'j', '繁': 'f', '重': 'z', '要': 'y', '普': 'p', '常': 'c',
    '规': 'g', '范': 'f', '默': 'm', '可': 'k', '选': 'x', '项': 'x', '目': 'm',
    '类': 'l', '型': 'x', '格': 'g', '式': 's', '种': 'z', '方': 'f', '案': 'a',
    '策': 'c', '略': 'l', '战': 'z', '术': 's', '工': 'g', '程': 'c', '任': 'r',
    '务': 'w', '代': 'd', '码': 'm', '写': 'x', '测': 'c', '试': 's', '部': 'b',
    '件': 'j', '模': 'm', '块': 'k', '服': 'f', '端': 'd', '口': 'k', '接': 'j',
    '数': 's', '据': 'j', '库': 'k', '结': 'j', '构': 'g', '字': 'z', '段': 'd',
    '属': 's', '性': 'x', '主': 'z', '键': 'j', '外': 'w', '引': 'y', '指': 'z',
    '针': 'z', '唯': 'w', '一': 'y', '检': 'j', '校': 'x', '验': 'y', '密': 'm',
    '错': 'c', '误': 'w', '异': 'y', '常': 'c', '超': 'c', '时': 's', '失': 's',
    '败': 'b', '故': 'g', '障': 'z', '排': 'p', '修': 'x', '原': 'y', '因': 'y',
    '根': 'g', '日': 'r', '志': 'z', '记': 'j', '操': 'c', '作': 'z', '计': 'j',
    '警': 'j', '阈': 'y', '值': 'z',
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

@lru_cache(maxsize=2048)
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


@lru_cache(maxsize=1024)
def fuzzy_match(query: str, target: str, threshold: Optional[float] = None) -> bool:
    """判断 query 和 target 是否 fuzzy 匹配"""
    if threshold is None:
        threshold = adaptive_threshold(query)
    return fuzzy_score(query, target, threshold=threshold) >= threshold


@lru_cache(maxsize=512)
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
    has_chinese = bool(_RE_CHINESE_RANGE.search(q_lower)) or bool(_RE_CHINESE_RANGE.search(t_lower))
    
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


# ── Common Chinese Compound Words for Word-Level Segmentation ──
_CN_COMPOUNDS = frozenset([
    '素材审核', '广告组', '广告计划', '竞价引擎', '投放管理', '报表统计',
    '权限控制', '缓存策略', '消息队列', '定时任务', '数据迁移', '监控告警',
    '日志收集', '限流降级', '幂等设计', '加密解密', '搜索索引', '推送通知',
    '对账结算', '风控系统', '错误码', '鉴权中间件', '健康检查', '回滚方案',
    '灰度发布', 'Feature Flag', '金丝雀发布', '分布式锁', '事务管理',
    '补偿机制', '重试策略', '异步处理', '批量处理', '实时计算', '离线分析',
])


def _chinese_word_segment(text: str) -> List[str]:
    """中文分词 — 基于词典的最大匹配 + 双字切分。
    
    策略：
    1. 优先匹配已知业务复合词（素材审核、竞价引擎等）
    2. 剩余部分按双字切分
    3. 保留单字作为兜底
    """
    words = []
    remaining = text
    
    # 1. 最大正向匹配（从长到短）
    matched_positions = set()
    for compound in _CN_COMPOUNDS:
        start = 0
        while True:
            idx = remaining.find(compound, start)
            if idx < 0:
                break
            matched_positions.update(range(idx, idx + len(compound)))
            words.append(compound)
            start = idx + len(compound)
    
    # 2. 未匹配部分按双字切分
    for i, ch in enumerate(remaining):
        if i not in matched_positions and ch in _PINYIN_INITIALS:
            # 双字组合
            if i + 1 < len(remaining) and (i + 1) not in matched_positions:
                bigram = remaining[i:i+2]
                words.append(bigram)
            else:
                words.append(ch)
    
    return words


@lru_cache(maxsize=1024)
def _chinese_ngram_similarity(s1: str, s2: str, n: int = 2) -> float:
    """计算中文字符 n-gram 相似度，增强版：支持词级别 n-gram"""
    if not s1 or not s2:
        return 0.0
    
    # 提取中文字符
    c1 = re.sub(r'[^\u4e00-\u9fff]', '', s1)
    c2 = re.sub(r'[^\u4e00-\u9fff]', '', s2)
    
    if not c1 or not c2:
        return 0.0
    
    # 字符级 n-gram
    char_grams1 = {c1[i:i+n] for i in range(max(0, len(c1) - n + 1))}
    char_grams2 = {c2[i:i+n] for i in range(max(0, len(c2) - n + 1))}
    
    if not char_grams1 or not char_grams2:
        return 0.0
    
    char_intersection = len(char_grams1 & char_grams2)
    char_union = len(char_grams1 | char_grams2)
    char_sim = char_intersection / char_union if char_union > 0 else 0.0
    
    # 词级别 n-gram（使用分词结果）
    words1 = _chinese_word_segment(c1)
    words2 = _chinese_word_segment(c2)
    
    if words1 and words2:
        word_grams1 = {tuple(words1[i:i+n]) for i in range(max(0, len(words1) - n + 1))}
        word_grams2 = {tuple(words2[i:i+n]) for i in range(max(0, len(words2) - n + 1))}
        
        if word_grams1 and word_grams2:
            word_intersection = len(word_grams1 & word_grams2)
            word_union = len(word_grams1 | word_grams2)
            word_sim = word_intersection / word_union if word_union > 0 else 0.0
            # 加权融合：词级别权重更高（业务语义更准确）
            return 0.4 * char_sim + 0.6 * word_sim
    
    return char_sim


@lru_cache(maxsize=512)
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
        '素材': ['creative', 'ad_material', '广告素材', 'asset', 'artwork', 'banner', 'video'],
        'creative': ['素材', 'ad_material', '广告素材', 'asset', 'artwork', 'banner'],
        '竞价': ['bidding', '出价', 'auction', 'bid', 'cpm', 'cpc', 'ocpx', 'pacing'],
        'bidding': ['竞价', '出价', 'auction', 'bid', 'cpm', 'cpc'],
        '审核': ['review', 'audit', '审批', 'approval', 'quality_check', 'moderation'],
        'review': ['审核', 'audit', '审批', 'approval', 'quality_check'],
        '发布': ['publish', 'release', '上线', 'deploy', 'go_live', 'launch'],
        'publish': ['发布', 'release', '上线', 'deploy', 'go_live'],
        '广告组': ['adgroup', 'ad_group', 'ad group', '广告单元'],
        'adgroup': ['广告组', 'ad_group', 'ad group', '广告单元'],
        '广告计划': ['campaign', 'ad_campaign', '推广计划', 'ad plan', '投放计划'],
        'campaign': ['广告计划', 'ad_campaign', '推广计划', 'ad plan'],
        '权限': ['permission', 'auth', 'access', 'acl', 'role', 'rbac', '授权'],
        'permission': ['权限', 'auth', 'access', 'acl', 'role'],
        '缓存': ['cache', 'redis', 'memory', 'memcached', 'cdn', 'local_cache'],
        'cache': ['缓存', 'redis', 'memory', 'memcached', 'cdn'],
        '消息队列': ['mq', 'kafka', 'rabbitmq', 'message queue', 'event bus', 'async'],
        'kafka': ['消息队列', 'mq', 'rabbitmq', 'event bus', 'streaming'],
        '推送': ['push', 'notification', 'notify', 'alert', '消息推送'],
        'push': ['推送', 'notification', 'notify', 'alert'],
        '预算': ['budget', 'spending', '花费', 'cost', 'billing', '消耗'],
        'budget': ['预算', 'spending', '花费', 'cost', 'billing'],
        '定向': ['targeting', 'audience', '定向投放', 'geo', 'demographic', '人群'],
        'targeting': ['定向', 'audience', '定向投放', 'geo'],
        '展示': ['impression', 'display', '曝光', 'view', '展现'],
        'impression': ['展示', 'display', '曝光', 'view'],
        '点击': ['click', 'ctr', '点击率', '点击量'],
        'click': ['点击', 'ctr', '点击率'],
        '转化': ['conversion', 'cvr', '转化事件', 'cv', 'goal', '转化量'],
        'conversion': ['转化', 'cvr', '转化事件', 'cv'],
        '报表': ['report', 'stats', 'statistics', '统计', 'analytics', 'dashboard', '数据报表'],
        'report': ['报表', 'stats', 'statistics', '统计', 'analytics'],
        '限流': ['rate limit', 'throttle', 'qps limit', '流量控制', '流量限制'],
        '幂等': ['idempotent', '重复提交', 'retry safe', '去重'],
        '审计': ['audit_log', '操作日志', 'trace', 'op log', '操作审计'],
        # 通用技术术语
        '事务': ['transaction', 'tx', 'commit', 'rollback', 'acidity'],
        '事务管理': ['transaction', 'tx', 'commit', 'rollback'],
        '分布式锁': ['distributed_lock', 'redis_lock', 'lock', 'mutex', 'semaphore'],
        '重试': ['retry', 'backoff', 'exponential_backoff', 'recovery'],
        '补偿': ['compensation', 'saga', 'tcc', '最终一致性'],
        '监控': ['monitor', 'observability', 'prometheus', 'grafana', 'alerting'],
        '日志': ['log', 'logging', 'structured_log', 'zap', 'logrus'],
        '健康检查': ['health_check', 'liveness', 'readiness', '/health', '/ready'],
        '迁移': ['migration', 'schema_migration', 'data_migration', 'backfill'],
        '加密': ['encryption', 'hash', 'bcrypt', 'argon2', 'sha256'],
        '搜索': ['search', 'elasticsearch', 'es', 'fulltext', 'index'],
        '定时任务': ['cron', 'scheduled_task', 'timer', 'scheduler', 'quartz'],
        '灰度发布': ['canary', 'gradual_release', 'feature_flag', 'blue_green', 'a/b_test'],
        '回滚': ['rollback', 'revert', 'undo', 'restore'],
        'API 版本': ['api_version', 'versioning', 'v1', 'v2', 'breaking_change'],
        '鉴权': ['authentication', 'jwt', 'oauth', 'token', 'sso', '单点登录'],
        '中间件': ['middleware', 'interceptor', 'filter', 'gateway'],
        '异步': ['async', 'asynchronous', 'non-blocking', 'event-driven'],
        '同步': ['sync', 'synchronous', 'blocking'],
        '批量': ['batch', 'bulk', '批量处理', '批处理'],
        '实时': ['realtime', 'real-time', 'streaming', 'live'],
        '离线': ['offline', 'batch_job', 'etl', 'spark'],
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
    
    # 7. Normalize query — 统一常见变体（adgroup→ad_group, review→审核, etc.）
    try:
        from enhanced_search import normalize_query
        normalized = normalize_query(query)
        if normalized != query and normalized not in keywords:
            keywords.append(normalized)
    except ImportError:
        pass  # enhanced_search not available, skip
    
    # 去重，保留顺序
    keywords = list(dict.fromkeys(keywords))
    return keywords[:30]  # 最多 30 个关键词


# ──────────────────────────────────────────────
# IR-Aware Synonym Expansion — 基于实际代码的同义词扩展
# ──────────────────────────────────────────────

# 从函数名/路由/struct 自动推断同义词
_CODE_SYNONYM_MAP = {
    # 素材相关
    'creative': ['素材', 'creative_material', 'artwork', 'banner', 'video_ad'],
    '素材': ['creative', 'ad_material', 'artwork'],
    # 广告组相关
    'adgroup': ['广告组', 'ad_group'],
    '广告组': ['adgroup', 'ad_group'],
    # 竞价相关
    'bidding': ['竞价', 'bidding_engine', 'bid_price', 'pacing'],
    '竞价': ['bidding', 'auction'],
    # 审核相关
    'review': ['审核', 'reviewer', 'audit', 'approval'],
    '审核': ['review', 'audit', 'approve'],
    # 投放相关
    'campaign': ['广告计划', 'campaign_manager', 'ad_plan'],
    '投放': ['delivery', 'campaign', 'pacing'],
    # 报表相关
    'report': ['报表', 'reporting', 'stats', 'analytics', 'dashboard'],
    '报表': ['report', 'stats', 'analytics'],
    # 权限相关
    'permission': ['权限', 'permission_manager', 'auth'],
    '权限': ['permission', 'auth', 'rbac'],
    # 缓存相关
    'cache': ['缓存', 'cache_manager', 'redis_client'],
    '缓存': ['cache', 'redis'],
    # 消息队列相关
    'kafka': ['Kafka', '消息队列', 'mq_consumer', 'mq_producer'],
    '消息队列': ['kafka', 'mq', 'rabbitmq'],
    # 推送相关
    'push': ['推送', 'push_notification', 'notify'],
    '推送': ['push', 'notification'],
    # 错误码相关
    'error_code': ['错误码', 'error_codes', 'err_code'],
    '错误码': ['error_code', 'err_code'],
    # 鉴权相关
    'auth': ['鉴权', 'auth_middleware', 'permission_check', 'token_verify'],
    '鉴权': ['auth', 'permission', 'token'],
    # 数据库相关
    'dao': ['DAO', 'data_access', 'repository', 'db_layer'],
    'service': ['Service', '业务层', 'business_logic'],
    'handler': ['Handler', '处理器', 'router_handler'],
}


def expand_synonyms_with_ir(query: str, ir_data: Optional[dict], profile: dict = None) -> List[str]:
    """IR-aware 同义词扩展 — 结合代码库实际数据扩展查询词
    
    策略：
    1. 标准同义词扩展（builtin + profile）
    2. IR 数据驱动的上下文扩展：从实际函数名/路由/struct 中推断相关术语
    3. 语义相关的函数名提取（如 SetStatus → approve/reject/transition）
    4. 路由路径前缀推断（如 /api/v1/adgroup → adgroup/ad_group/广告组）
    
    Args:
        query: 原始查询
        ir_data: IR 缓存数据（包含 functions/routes/structs 等）
        profile: 可选 profile 配置
        
    Returns:
        扩展后的查询词列表
    """
    keywords = expand_synonyms(query, profile)
    
    if not ir_data or not isinstance(ir_data, dict):
        return keywords
    
    query_lower = query.lower()
    
    # 1. 从函数名推断同义词
    for func in ir_data.get('functions', []):
        if isinstance(func, dict):
            fname = func.get('name', '')
            fsig = func.get('signature', '')
        else:
            fname = getattr(func, 'name', '')
            fsig = getattr(func, 'signature', '')
        
        if not fname:
            continue
            
        # 检查函数名是否包含查询关键词
        if any(term.lower() in fname.lower() for term in [query] + keywords[:5]):
            # 从函数名提取有意义的子串作为扩展词
            parts = re.split(r'[_\-\s]', fname)
            for part in parts:
                if 3 <= len(part) <= 20 and part.lower() not in [k.lower() for k in keywords]:
                    keywords.append(part)
    
    # 2. 从路由路径推断同义词
    for route in ir_data.get('routes', []):
        if isinstance(route, dict):
            rpath = route.get('path', '')
            rhandler = route.get('handler', '')
        else:
            rpath = getattr(route, 'path', '')
            rhandler = getattr(route, 'handler', '')
        
        if not rpath:
            continue
            
        # 检查路由是否匹配查询
        if any(term.lower() in rpath.lower() for term in [query] + keywords[:5]):
            # 从路由路径提取实体名
            path_parts = rpath.strip('/').split('/')
            for part in path_parts:
                if 2 <= len(part) <= 20 and part.lower() not in [k.lower() for k in keywords]:
                    keywords.append(part)
    
    # 3. 从 struct 名推断同义词
    for struct in ir_data.get('structs', []):
        if isinstance(struct, dict):
            sname = struct.get('name', '')
        else:
            sname = getattr(struct, 'name', '')
        
        if not sname:
            continue
            
        if any(term.lower() in sname.lower() for term in [query] + keywords[:5]):
            # 从 struct 名提取字段名作为扩展词
            fields = struct.get('fields', []) if isinstance(struct, dict) else getattr(struct, 'fields', [])
            if fields:
                for f in fields[:5]:
                    if isinstance(f, dict):
                        fname = f.get('name', '')
                    else:
                        fname = str(f)
                    if fname and len(fname) >= 2:
                        keywords.append(fname)
    
    # 4. 从 entity_tables 推断同义词
    for et in ir_data.get('entity_tables', []):
        if isinstance(et, dict):
            entity = et.get('entity', '')
            table = et.get('table', '')
        else:
            entity = getattr(et, 'entity', '')
            table = getattr(et, 'table', '')
            
        if entity and any(term.lower() in entity.lower() for term in [query] + keywords[:5]):
            if table and table.lower() not in [k.lower() for k in keywords]:
                keywords.append(table)
    
    # 5. 从 _CODE_SYNONYM_MAP 扩展
    for term, variants in _CODE_SYNONYM_MAP.items():
        if term.lower() in query_lower:
            keywords.extend(variants)
    
    # ── Enhancement: Cross-language term mapping ──
    # Go uses PascalCase (CreateAdGroup), Python uses snake_case (create_ad_group),
    # Java uses camelCase (createAdGroup). Map between them for better recall.
    try:
        cross_lang_terms = _cross_language_expand(query, ir_data)
        if cross_lang_terms:
            keywords.extend(cross_lang_terms)
    except Exception:
        pass

    # 去重并限制数量
    keywords = list(dict.fromkeys(keywords))
    return keywords[:50]  # 最多 50 个关键词


def _cross_language_expand(query: str, ir_data: Optional[dict]) -> List[str]:
    """Cross-language term expansion for better evidence recall.
    
    When querying for 'adgroup', also match 'ad_group' (Python) and 'AdGroup' (Go).
    Uses IR data to find actual naming conventions in the codebase.
    """
    if not ir_data or not isinstance(ir_data, dict):
        return []
    
    expanded = []
    query_lower = query.lower()
    
    # Find all entity names actually used in this codebase
    entity_names = set()
    for func in ir_data.get('functions', []):
        if isinstance(func, dict):
            name = func.get('name', '')
        else:
            name = getattr(func, 'name', '')
        if name:
            # Extract entity prefix from function names like CreateAdGroup, GetAdGroupList
            parts = re.split(r'(?<=[a-z])(?=[A-Z])|[_\-\s]', name)
            for p in parts:
                if 2 <= len(p) <= 30:
                    entity_names.add(p.lower())
    
    for route in ir_data.get('routes', []):
        if isinstance(route, dict):
            path = route.get('path', '')
        else:
            path = getattr(route, 'path', '')
        if path:
            for part in path.strip('/').split('/'):
                clean = re.sub(r'\{.*?\}', '', part)
                if clean and len(clean) > 1:
                    entity_names.add(clean.lower())
    
    # For each entity name that matches query, generate variants
    for entity in entity_names:
        if entity in query_lower or query_lower in entity:
            # Generate snake_case variant
            snake = entity.replace('-', '_')
            if snake != entity and snake not in [k.lower() for k in expanded]:
                expanded.append(snake)
            # Generate PascalCase variant
            pascal = ''.join(w.capitalize() for w in entity.split('_'))
            if pascal != entity and pascal not in [k.lower() for k in expanded]:
                expanded.append(pascal)
            # Generate kebab-case variant
            kebab = entity.replace('_', '-')
            if kebab != entity and kebab not in [k.lower() for k in expanded]:
                expanded.append(kebab)
    
    return expanded[:10]


def infer_related_terms_from_ir(query: str, ir_data: Optional[dict]) -> List[str]:
    """从 IR 数据中推断与查询相关的术语
    
    用于证据查询结果的智能排序和过滤。
    
    Returns:
        相关术语列表
    """
    if not ir_data or not isinstance(ir_data, dict):
        return []
    
    query_lower = query.lower()
    related = set()
    
    # 1. 查找包含查询关键词的函数
    for func in ir_data.get('functions', []):
        if isinstance(func, dict):
            fname = func.get('name', '').lower()
            fsig = func.get('signature', '').lower()
        else:
            fname = str(getattr(func, 'name', '')).lower()
            fsig = str(getattr(func, 'signature', '')).lower()
        
        if query_lower in fname or query_lower in fsig:
            related.add(func.get('name', '') if isinstance(func, dict) else getattr(func, 'name', ''))
    
    # 2. 查找包含查询关键词的路由
    for route in ir_data.get('routes', []):
        if isinstance(route, dict):
            rpath = route.get('path', '').lower()
            rhandler = route.get('handler', '').lower()
        else:
            rpath = str(getattr(route, 'path', '')).lower()
            rhandler = str(getattr(route, 'handler', '')).lower()
        
        if query_lower in rpath or query_lower in rhandler:
            related.add(route.get('path', '') if isinstance(route, dict) else getattr(route, 'path', ''))
    
    # 3. 查找包含查询关键词的 struct
    for struct in ir_data.get('structs', []):
        if isinstance(struct, dict):
            sname = struct.get('name', '').lower()
        else:
            sname = str(getattr(struct, 'name', '')).lower()
        
        if query_lower in sname:
            related.add(struct.get('name', '') if isinstance(struct, dict) else getattr(struct, 'name', ''))
    
    return list(related)[:20]


# ──────────────────────────────────────────────
# Query Variant Expansion — 查询变体生成（已迁移至 _common.py）
# ──────────────────────────────────────────────
# generate_query_variants is now in _common.py — import it here to avoid duplication

def _generate_query_variants(query: str) -> List[str]:
    """Generate query variants — delegates to _common.generate_query_variants."""
    from _common import generate_query_variants as gqv
    return gqv(query)


# ──────────────────────────────────────────────
# Query Variant Expansion V2 — 综合查询变体生成
# ──────────────────────────────────────────────

# 跨语言术语映射表：Go PascalCase ↔ Python snake_case ↔ Java camelCase
_CROSS_LANGUAGE_MAP = {
    # 广告平台核心实体
    'ad_group': {'go': 'AdGroup', 'java': 'adGroup', 'python': 'ad_group', 'cn': '广告组'},
    'campaign': {'go': 'Campaign', 'java': 'campaign', 'python': 'campaign', 'cn': '广告计划'},
    'creative': {'go': 'Creative', 'java': 'creative', 'python': 'creative', 'cn': '素材'},
    'bidding': {'go': 'Bidding', 'java': 'bidding', 'python': 'bidding', 'cn': '竞价'},
    'review': {'go': 'Review', 'java': 'review', 'python': 'review', 'cn': '审核'},
    'audit': {'go': 'Audit', 'java': 'audit', 'python': 'audit', 'cn': '审计'},
    'permission': {'go': 'Permission', 'java': 'permission', 'python': 'permission', 'cn': '权限'},
    'cache': {'go': 'Cache', 'java': 'cache', 'python': 'cache', 'cn': '缓存'},
    'delivery': {'go': 'Delivery', 'java': 'delivery', 'python': 'delivery', 'cn': '投放'},
    'budget': {'go': 'Budget', 'java': 'budget', 'python': 'budget', 'cn': '预算'},
    'targeting': {'go': 'Targeting', 'java': 'targeting', 'python': 'targeting', 'cn': '定向'},
    'impression': {'go': 'Impression', 'java': 'impression', 'python': 'impression', 'cn': '展示'},
    'conversion': {'go': 'Conversion', 'java': 'conversion', 'python': 'conversion', 'cn': '转化'},
    'report': {'go': 'Report', 'java': 'report', 'python': 'report', 'cn': '报表'},
    'push': {'go': 'Push', 'java': 'push', 'python': 'push', 'cn': '推送'},
    'kafka': {'go': 'Kafka', 'java': 'kafka', 'python': 'kafka', 'cn': '消息队列'},
    # 通用技术术语
    'handler': {'go': 'Handler', 'java': 'handler', 'python': 'handler', 'cn': '处理器'},
    'service': {'go': 'Service', 'java': 'service', 'python': 'service', 'cn': '服务'},
    'middleware': {'go': 'Middleware', 'java': 'middleware', 'python': 'middleware', 'cn': '中间件'},
    'repository': {'go': 'Repository', 'java': 'repository', 'python': 'repository', 'cn': '仓储'},
    'scheduler': {'go': 'Scheduler', 'java': 'scheduler', 'python': 'scheduler', 'cn': '调度器'},
    'monitor': {'go': 'Monitor', 'java': 'monitor', 'python': 'monitor', 'cn': '监控'},
    'migration': {'go': 'Migration', 'java': 'migration', 'python': 'migration', 'cn': '迁移'},
    'rollback': {'go': 'Rollback', 'java': 'rollback', 'python': 'rollback', 'cn': '回滚'},
    'health_check': {'go': 'HealthCheck', 'java': 'healthCheck', 'python': 'health_check', 'cn': '健康检查'},
    'rate_limit': {'go': 'RateLimit', 'java': 'rateLimit', 'python': 'rate_limit', 'cn': '限流'},
    'distributed_lock': {'go': 'DistributedLock', 'java': 'distributedLock', 'python': 'distributed_lock', 'cn': '分布式锁'},
    'event_bus': {'go': 'EventBus', 'java': 'eventBus', 'python': 'event_bus', 'cn': '事件总线'},
    'webhook': {'go': 'Webhook', 'java': 'webhook', 'python': 'webhook', 'cn': '回调'},
}

# 领域上下文扩展词典（按业务域分组）
_DOMAIN_CONTEXT_V2 = {
    'ad_platform': {
        'keywords': ['广告', 'ad', '投放', '素材', '创意', 'creative', 'banner', '竞价', 'bidding'],
        'related': ['adgroup', 'campaign', 'creative', 'bidding', 'pacing', 'budget', 'targeting',
                     'impression', 'click', 'conversion', 'ctr', 'cvr', 'ecpm', 'roas', 'rtb'],
    },
    'infra_tech': {
        'keywords': ['缓存', 'redis', '消息', 'mq', 'kafka', '定时', 'cron', '监控', '日志', '限流'],
        'related': ['cache', 'redis', 'kafka', 'rabbitmq', 'mq', 'cron', 'schedule', 'monitor',
                     'prometheus', 'grafana', 'rate_limit', 'throttle', 'distributed_lock', 'idempotent'],
    },
    'data_engineering': {
        'keywords': ['数据', '报表', '统计', '分析', '迁移', 'ETL', '批处理', '实时'],
        'related': ['etl', 'batch', 'streaming', 'realtime', 'migration', 'report', 'stats',
                     'analytics', 'dashboard', 'pipeline', 'warehouse', 'data_quality'],
    },
    'security_auth': {
        'keywords': ['权限', '鉴权', '认证', '安全', '风控', '加密'],
        'related': ['auth', 'permission', 'rbac', 'acl', 'jwt', 'oauth', 'token', 'sso',
                     'encrypt', 'hash', 'risk', 'fraud', 'waf', 'abuse_detection'],
    },
    'devops_release': {
        'keywords': ['发布', '部署', '灰度', '回滚', '金丝雀', '测试', 'CI/CD'],
        'related': ['deploy', 'release', 'canary', 'blue_green', 'feature_flag', 'a/b_test',
                     'rollback', 'revert', 'ci', 'cd', 'docker', 'k8s', 'container'],
    },
}

# 缩写展开表（更全面的覆盖）
_ABBREVIATION_EXPANSIONS = {
    # 广告平台缩写
    'ad': ['广告', 'advertising', 'ad_material', 'creative'],
    'creative': ['素材', 'ad_material', 'banner', 'artwork', 'video_ad', 'image_ad'],
    'adg': ['ad_group', 'adgroup', '广告组'],
    'ad_grp': ['ad_group', 'adgroup', '广告组'],
    'camp': ['campaign', '广告计划', 'ad_campaign'],
    'bid': ['bidding', '竞价', '出价', 'auction'],
    'rev': ['review', '审核', 'approval'],
    'aud': ['audit', '审计', '审核'],
    'per': ['permission', '权限', 'authorization'],
    'cach': ['cache', '缓存', 'redis'],
    'mq': ['消息队列', 'message_queue', 'kafka', 'rabbitmq'],
    'kf': ['kafka', '消息队列', 'mq'],
    'push': ['推送', 'notification', 'notify'],
    'notif': ['notification', '通知', '推送'],
    'bgt': ['budget', '预算', 'spending'],
    'tgt': ['targeting', '定向', 'audience'],
    'imp': ['impression', '展示', '曝光'],
    'disp': ['display', '展示', 'impression'],
    'clk': ['click', '点击', 'ctr'],
    'conv': ['conversion', '转化', 'cvr'],
    'rpt': ['report', '报表', 'statistics'],
    'stat': ['stats', '统计', 'analytics'],
    'tech': ['技术', 'technology', 'infra'],
    'api': ['API', '接口', 'rest_api', 'grpc'],
    'db': ['数据库', 'database', 'mysql', 'postgresql'],
    'sql': ['SQL', '数据库查询', 'sql_query'],
    'dao': ['DAO', '数据访问层', 'repository'],
    'rpc': ['RPC', '远程调用', 'grpc', 'dubbo'],
    'http': ['HTTP', 'HTTP请求', 'web_request', 'rest'],
    'tls': ['TLS', '传输层安全', 'ssl', 'encryption'],
    'dns': ['DNS', '域名解析', 'domain_name_resolution'],
    'lb': ['load_balancer', '负载均衡', 'lb_config'],
    'cdn': ['CDN', '内容分发网络', 'content_delivery'],
    'oss': ['OSS', '对象存储', 'object_storage', 'minio'],
    'ecs': ['ECS', '云服务器', 'elastic_compute'],
    'vpc': ['VPC', '虚拟私有云', 'virtual_network'],
    'k8s': ['kubernetes', 'k8s_cluster', '容器编排'],
    'docker': ['Docker', '容器', 'container', 'dockerfile'],
    'ci': ['CI', '持续集成', 'continuous_integration'],
    'cd': ['CD', '持续交付', 'continuous_delivery'],
    'sla': ['SLA', '服务等级协议', 'service_level_agreement'],
    'slo': ['SLO', '服务等级目标', 'service_level_objective'],
    'sop': ['SOP', '标准操作流程', 'standard_operating_procedure'],
    'todo': ['TODO', '待办', 'todo_list'],
    'api_ver': ['API版本', 'api_version', 'versioning'],
    'err_code': ['错误码', 'error_code', 'err_code'],
}


def _to_snake_case(name: str) -> str:
    """Convert PascalCase/camelCase to snake_case."""
    # Handle sequences of uppercase letters (e.g., "HTTPServer" → "http_server")
    s1 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    s2 = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', s1)
    return s2.lower()


def _to_pascal_case(name: str) -> str:
    """Convert snake_case to PascalCase."""
    return ''.join(word.capitalize() for word in name.split('_'))


def _to_camel_case(name: str) -> str:
    """Convert snake_case to camelCase."""
    words = name.split('_')
    if not words:
        return name
    return words[0].lower() + ''.join(w.capitalize() for w in words[1:])


def expand_query_variants_v2(
    query: str,
    ir_data: Optional[dict] = None,
    profile: Optional[dict] = None,
) -> List[str]:
    """综合查询变体生成 V2 — 四层扩展策略。

    支持：
    a) 同义词扩展：复用现有 synonym 字典（builtin_synonyms + profile synonym_map）
    b) 跨语言术语映射：Go PascalCase ↔ Python snake_case ↔ Java camelCase
    c) 查询缩写展开：如 'ad' → '广告', 'creative' → '素材'
    d) 领域上下文扩展：按业务域（广告平台/基础设施/数据安全/运维发布）自动扩展

    Args:
        query: 原始查询字符串
        ir_data: IR 缓存数据（用于跨语言映射的上下文感知）
        profile: 可选 profile 配置

    Returns:
        去重后的查询变体列表（含原始查询）
    """
    all_variants = [query]
    query_lower = query.lower().strip()

    # ── Layer A: Synonym Expansion (复用现有 synonym 字典) ──
    synonyms = expand_synonyms(query, profile)
    seen_lower = {query.lower()}
    for sv in synonyms:
        if sv != query and sv.lower() not in seen_lower:
            all_variants.append(sv)
            seen_lower.add(sv.lower())

    # ── Layer B: Cross-language Term Mapping ──
    cross_lang_terms = _expand_cross_language(query, ir_data)
    for clt in cross_lang_terms:
        if clt.lower() not in seen_lower:
            all_variants.append(clt)
            seen_lower.add(clt.lower())

    # ── Layer C: Abbreviation Expansion ──
    abbr_terms = _expand_abbreviations(query)
    for at in abbr_terms:
        if at.lower() not in seen_lower:
            all_variants.append(at)
            seen_lower.add(at.lower())

    # ── Layer D: Domain Context Expansion ──
    domain_terms = _expand_domain_context(query)
    for dt in domain_terms:
        if dt.lower() not in seen_lower:
            all_variants.append(dt)
            seen_lower.add(dt.lower())

    # 去重，保留顺序
    all_variants = list(dict.fromkeys(all_variants))
    return all_variants[:60]  # 最多 60 个变体


def _expand_cross_language(query: str, ir_data: Optional[dict]) -> List[str]:
    """跨语言术语映射：Go PascalCase ↔ Python snake_case ↔ Java camelCase。

    策略：
    1. 从 _CROSS_LANGUAGE_MAP 中查找匹配项，生成所有语言的等价形式
    2. 从 IR 数据中提取实际使用的命名约定，补充映射
    3. 对查询中的每个词自动进行格式转换
    """
    results = []
    query_lower = query.lower()

    # 1. 从预定义映射表中查找
    for key, mapping in _CROSS_LANGUAGE_MAP.items():
        if key.lower() in query_lower or mapping.get('cn', '').lower() in query_lower:
            # 添加该术语的所有语言变体
            for lang_term in mapping.values():
                if lang_term and lang_term != key and lang_term.lower() not in [r.lower() for r in results]:
                    results.append(lang_term)

    # 2. 对查询中的每个独立词做格式转换
    # 提取查询中的独立词（驼峰分割 + 下划线分割 + 空格分割）
    query_words = re.findall(r'[A-Z][a-z]+|[a-z]+|[_\u4e00-\u9fff]+', query)
    for word in query_words:
        word_clean = word.strip('_')
        if not word_clean or len(word_clean) < 2:
            continue

        wc_lower = word_clean.lower()

        # 如果这个词在映射表中，添加所有变体
        if wc_lower in _CROSS_LANGUAGE_MAP:
            for lang_term in _CROSS_LANGUAGE_MAP[wc_lower].values():
                if lang_term and lang_term not in results:
                    results.append(lang_term)
        else:
            # 尝试格式转换
            # 如果是 PascalCase，生成 snake_case 和 camelCase
            if re.match(r'^[A-Z][a-zA-Z]*$', word_clean):
                snake = _to_snake_case(word_clean)
                camel = _to_camel_case(snake)
                for fmt in [snake, camel]:
                    if fmt and fmt != word_clean and fmt.lower() not in [r.lower() for r in results]:
                        results.append(fmt)
            # 如果是 snake_case，生成 PascalCase 和 camelCase
            elif '_' in word_clean:
                pascal = _to_pascal_case(word_clean)
                camel = _to_camel_case(word_clean)
                for fmt in [pascal, camel]:
                    if fmt and fmt != word_clean and fmt.lower() not in [r.lower() for r in results]:
                        results.append(fmt)
            # 如果是 camelCase，生成 snake_case 和 PascalCase
            elif re.search(r'[a-z][A-Z]', word_clean):
                snake = _to_snake_case(word_clean)
                pascal = _to_pascal_case(snake)
                for fmt in [snake, pascal]:
                    if fmt and fmt != word_clean and fmt.lower() not in [r.lower() for r in results]:
                        results.append(fmt)

    # 3. 从 IR 数据中发现实际命名模式
    if ir_data and isinstance(ir_data, dict):
        discovered = _discover_naming_conventions(ir_data, query_lower)
        for disc in discovered:
            if disc.lower() not in [r.lower() for r in results]:
                results.append(disc)

    return results[:20]


def _discover_naming_conventions(ir_data: dict, query_lower: str) -> List[str]:
    """从 IR 数据中自动发现命名约定并生成变体。"""
    results = []

    # 收集所有函数名、路由路径中的实体名
    entity_names = set()
    for func in ir_data.get('functions', []):
        if isinstance(func, dict):
            name = func.get('name', '')
        else:
            name = getattr(func, 'name', '')
        if name:
            parts = re.split(r'(?<=[a-z])(?=[A-Z])|[_\\-\\s]', name)
            for p in parts:
                if 2 <= len(p) <= 30:
                    entity_names.add(p.lower())

    for route in ir_data.get('routes', []):
        if isinstance(route, dict):
            path = route.get('path', '')
        else:
            path = getattr(route, 'path', '')
        if path:
            for part in path.strip('/').split('/'):
                clean = re.sub(r'\{.*?\}', '', part)
                if clean and len(clean) > 1:
                    entity_names.add(clean.lower())

    # 对于与查询匹配的实体名，生成跨语言变体
    for entity in entity_names:
        if entity in query_lower or query_lower in entity:
            # snake_case
            snake = entity.replace('-', '_')
            if snake != entity:
                results.append(snake)
            # PascalCase
            pascal = ''.join(w.capitalize() for w in entity.split('_'))
            if pascal != entity:
                results.append(pascal)
            # kebab-case
            kebab = entity.replace('_', '-')
            if kebab != entity:
                results.append(kebab)

    return results[:10]


def _expand_abbreviations(query: str) -> List[str]:
    """缩写展开：将常见缩写映射到完整术语。

    如 'ad' → ['广告', 'advertising', 'ad_material', 'creative']
       'creative' → ['素材', 'ad_material', ...]
    """
    results = []
    query_lower = query.lower()

    for abbr, expansions in _ABBREVIATION_EXPANSIONS.items():
        if abbr in query_lower:
            for exp in expansions:
                if exp and exp.lower() not in [r.lower() for r in results]:
                    results.append(exp)

    return results[:15]


def _expand_domain_context(query: str) -> List[str]:
    """领域上下文扩展：根据查询关键词推断所属业务域，返回相关术语。"""
    results = []
    query_lower = query.lower()

    for domain_name, domain_info in _DOMAIN_CONTEXT_V2.items():
        # 检查查询是否属于该域
        is_relevant = False
        for kw in domain_info['keywords']:
            if kw.lower() in query_lower:
                is_relevant = True
                break
        if not is_relevant:
            continue

        # 添加该域的相关术语
        for related in domain_info['related']:
            if related.lower() not in [r.lower() for r in results]:
                results.append(related)

    return results[:20]


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
        field_names = []
        for f in struct.get('fields', []):
            if isinstance(f, dict):
                field_names.append(f.get('name', ''))
            else:
                field_names.append(str(f))
        struct_str = f"{struct.get('name', '')} {' '.join(field_names)}"
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
    2. **Query Variant Auto-Expansion V2**: 自动同义词/跨语言/缩写/领域上下文扩展
    3. fuzzy_score 替代精确匹配
    4. BM25 + 语义搜索作为补充

    Args:
        query: 原始查询字符串
        repo_path: 仓库路径（保留用于兼容，当前未强制使用）
        top_k: 返回结果数量
        cache_dir: IR 缓存目录
        profile: Profile 配置（含 synonym_map / query_aliases）
        ir_cache: 可选预加载的 IR 缓存数据

    Returns:
        搜索结果列表，每个元素为 Dict，包含 type/title/path/line/content/score
    """
    # ── Load profile if not provided ──
    if profile is None:
        import json
        profile_path = str(Path(__file__).parent.parent / "profiles" / "default.json")
        if Path(profile_path).exists():
            try:
                with open(profile_path) as f:
                    profile = json.load(f)
            except Exception:
                pass

    # ── Load IR data ──
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

    # ── Query Variant Auto-Expansion V2 ──
    # Generate comprehensive query variants using all four expansion layers:
    #   A) Synonym expansion (builtin + profile)
    #   B) Cross-language mapping (Go PascalCase ↔ Python snake_case ↔ Java camelCase)
    #   C) Abbreviation expansion ('ad' → '广告', etc.)
    #   D) Domain context expansion (ad_platform, infra_tech, security_auth, etc.)
    expanded_queries = expand_query_variants_v2(query, ir_data, profile)

    # Also keep the original expand_synonyms for backward compatibility
    if profile:
        profile_synonyms = expand_synonyms(query, profile)
        # Merge without duplication
        for ps in profile_synonyms:
            if ps not in expanded_queries:
                expanded_queries.append(ps)
    else:
        expanded_queries = list(dict.fromkeys(expanded_queries))  # deduplicate

    if not ir_data:
        return []

    # ── Primary fuzzy search with expanded queries ──
    results = _search_code_fuzzy(ir_data, expanded_queries, top_k)

    # ── Fallback: BM25 supplement ──
    if len(results) < top_k // 2:
        try:
            from enhanced_search import BM25Scorer
            searchable_docs = []
            bm25_entry_map = []  # (entry_type, entry_dict) for each doc
            for func in ir_data.get('functions', []):
                sig = func.get('signature', func.get('name', ''))
                if sig:
                    searchable_docs.append(sig)
                    bm25_entry_map.append(('function', func))
            for route in ir_data.get('routes', []):
                rs = f"{route.get('method', '')} {route.get('path', '')} {route.get('handler', '')}"
                if rs:
                    searchable_docs.append(rs)
                    bm25_entry_map.append(('route', route))

            if searchable_docs:
                scorer = BM25Scorer()
                scorer.fit(searchable_docs)
                bm25_results = scorer.search(query, top_k=top_k)
                for doc_idx, score in bm25_results:
                    if doc_idx >= len(bm25_entry_map):
                        continue
                    entry_type, entry = bm25_entry_map[doc_idx]
                    if entry_type == 'function':
                        key = (entry.get('file', ''), 'function')
                        if key not in {(r.get('path'), r.get('type')) for r in results}:
                            results.append({
                                'type': 'function',
                                'title': entry.get('name', ''),
                                'path': entry.get('file', ''),
                                'line': entry.get('line', 0),
                                'content': entry.get('signature', ''),
                                'score': score,
                                'source': 'bm25',
                            })
                    elif entry_type == 'route':
                        key = (entry.get('file', ''), 'route')
                        if key not in {(r.get('path'), r.get('type')) for r in results}:
                            results.append({
                                'type': 'route',
                                'title': f"{entry.get('method', '').upper()} {entry.get('path', '')}",
                                'path': entry.get('file', ''),
                                'line': entry.get('line', 0),
                                'content': entry.get('handler', ''),
                                'score': score,
                                'source': 'bm25',
                            })
        except Exception:
            pass  # BM25 is optional

        # ── Fallback: Semantic search supplement ──
        if len(results) < top_k // 2:
            semantic_queries = semantic_expand_query(query, ir_data, top_k=15)
            if semantic_queries:
                semantic_results = _search_code_fuzzy(ir_data, semantic_queries, top_k)
                seen = {(r.get('path'), r.get('type')) for r in results}
                for sr in semantic_results:
                    key = (sr.get('path'), sr.get('type'))
                    if key not in seen:
                        seen.add(key)
                        results.append(sr)

    return results[:top_k]


def _search_code_fuzzy(ir_data: dict, queries: List[str], top_k: int) -> List[Dict]:
    """Fuzzy 搜索 — 使用 adaptive threshold 替代固定 0.3"""
    results = []
    for q in queries:
        query_lower = q.lower()
        # Compute adaptive threshold for this query
        try:
            from enhanced_search import classify_query as es_classify, adaptive_threshold as es_threshold
            qtype = es_classify(q)
            min_threshold = es_threshold(q, qtype)
        except ImportError:
            qtype = classify_query(q)
            min_threshold = adaptive_threshold(q, qtype)
        
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
                field_texts = []
                for f in struct.get('fields', [])[:5]:
                    if isinstance(f, dict):
                        field_texts.append(f.get('name', str(f)))
                    else:
                        field_texts.append(str(f))
                results.append({
                    'type': 'struct',
                    'title': struct['name'],
                    'path': struct.get('file', ''),
                    'line': struct.get('line', 0),
                    'content': '\n'.join(field_texts),
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
    """Wiki 知识库增强证据查询。
    
    策略：
    1. 从 wiki 目录搜索 markdown 文件
    2. 使用 fuzzy_score 匹配查询词
    3. 返回前 K 个最相关的页面片段
    """
    results = []
    
    if not wiki_path or wiki_path == 'none':
        return results
    
    wiki_dir = Path(wiki_path)
    if not wiki_dir.exists():
        return results
    
    # 尝试从 wiki_engine 导入（如果可用）
    try:
        from .wiki_engine import wiki_search as ws_engine
        if hasattr(ws_engine, '__call__'):
            # wiki_engine 有搜索能力，优先使用
            pass
    except ImportError:
        pass
    
    # 降级方案：直接搜索 wiki 目录下的 markdown 文件
    md_files = list(wiki_dir.rglob('**/*.md'))[:50]
    query_lower = query.lower()
    
    for md_file in md_files:
        try:
            content = md_file.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        
        # 检查是否包含查询关键词
        if query_lower not in content.lower():
            continue
        
        # 计算匹配分数
        score = fuzzy_score(query_lower, content[:200].lower())
        
        # 提取上下文片段
        idx = content.lower().find(query_lower)
        if idx >= 0:
            context_start = max(0, idx - 150)
            context_end = min(len(content), idx + 400)
            context = content[context_start:context_end].strip()
        else:
            context = content[:500].strip()
        
        results.append({
            'type': 'wiki',
            'title': md_file.stem,
            'path': str(md_file.relative_to(wiki_dir.parent)),
            'content': context[:500],
            'score': round(score, 4),
            'source': 'wiki',
        })
    
    # 按分数排序并限制数量
    results.sort(key=lambda x: x.get('score', 0), reverse=True)
    return results[:top_k]


# ──────────────────────────────────────────────
# Query Understanding — 查询理解与重构
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
            except Exception:
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
        except Exception:
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
            # 标准 IDF 公式: log((N+1)/(df+1)) + 1，避免常见词 IDF=0
            self.idf[term] = math.log((n_docs + 1) / (count + 1)) + 1
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
    
    return results


# ──────────────────────────────────────────────
# Enhanced Semantic Search — BM25-style scoring
# ──────────────────────────────────────────────


def _bm25_score(query_terms: List[str], doc_terms: List[str], k1: float = 1.5, b: float = 0.75) -> float:
    """BM25 scoring for short-text matching (function names, routes, etc.)"""
    if not query_terms or not doc_terms:
        return 0.0
    
    doc_len = len(doc_terms)
    avg_doc_len = max(doc_len, 1)
    
    score = 0.0
    for q_term in query_terms:
        tf = sum(1 for t in doc_terms if t == q_term)
        if tf == 0:
            continue
        idf = math.log(1 + (avg_doc_len / max(tf, 1)))
        tf_score = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_doc_len))
        score += idf * tf_score
    
    # Jaccard bonus for term overlap
    query_set = set(query_terms)
    doc_set = set(doc_terms)
    overlap = len(query_set & doc_set)
    union = len(query_set | doc_set)
    if union > 0:
        score += (overlap / union) * 0.5
    
    return score


def enhanced_semantic_search(query: str, documents: List[str], top_k: int = 10) -> List[Dict]:
    """Enhanced semantic search combining BM25 + fuzzy + domain context."""
    query_tokens = _tokenize(query)
    query_lower = query.lower()
    
    results = []
    for i, doc in enumerate(documents):
        doc_tokens = _tokenize(doc)
        doc_lower = doc.lower()
        
        bm25 = _bm25_score(query_tokens, doc_tokens)
        fuzzy = fuzzy_score(query_lower, doc_lower)
        
        domain_bonus = 0.0
        for key in _DOMAIN_CONTEXT_MAP:
            if key in query_lower and key in doc_lower:
                domain_bonus += 0.3
                break
        
        combined = 0.5 * bm25 + 0.4 * fuzzy + domain_bonus
        
        if combined > 0.1:
            results.append({
                'doc': doc,
                'score': round(combined, 4),
                'rank': i,
                'bm25_score': round(bm25, 4),
                'fuzzy_score': round(fuzzy, 4),
            })
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]


def semantic_expand_query_v2(query: str, ir_data: dict, top_k: int = 20) -> List[str]:
    """Enhanced semantic query expansion using BM25 + domain context."""
    searchable = []
    
    for func in ir_data.get('functions', []):
        sig = func.get('signature', '')
        name = func.get('name', '')
        file = func.get('file', '')
        if sig:
            searchable.append(f"{name} {sig} {file}")
        elif name:
            searchable.append(name)
    
    for route in ir_data.get('routes', []):
        rs = f"{route.get('method', '')} {route.get('path', '')} {route.get('handler', '')} {route.get('request', '')} {route.get('response', '')}"
        if rs.strip():
            searchable.append(rs)
    
    for bl in ir_data.get('business_logic', []):
        desc = bl.get('description', '')
        handler = bl.get('handler', '')
        if desc:
            searchable.append(f"{handler} {desc}")
    
    for struct in ir_data.get('structs', []):
        sname = struct.get('name', '')
        fields = ', '.join(f.get('name', '') if isinstance(f, dict) else str(f) for f in struct.get('fields', []))
        if sname:
            searchable.append(f"{sname} {fields}")
    
    if not searchable:
        return []
    
    results = enhanced_semantic_search(query, searchable, top_k=min(top_k * 2, len(searchable)))
    
    expanded = []
    for r in results[:min(top_k, len(results))]:
        tokens = _tokenize(r['doc'])
        for t in tokens:
            if len(t) >= 2 and t not in expanded:
                expanded.append(t)
        if len(expanded) >= top_k * 2:
            break
    
    domain_context = _get_domain_context(query)
    for dc in domain_context:
        if dc not in expanded:
            expanded.append(dc)
    
    return expanded[:top_k * 2]

def cross_field_search(query: str, ir_data: dict, top_k: int = 10) -> List[Dict]:
    """跨字段关联搜索 — 同时搜索 struct 字段 + 路由 + 业务逻辑，找到关联证据
    
    策略：
    1. 从 query 提取实体名
    2. 搜索该实体的 struct 定义
    3. 搜索使用该 struct 的路由
    4. 搜索涉及该 struct 的业务逻辑
    5. 返回关联证据链
    
    Returns:
        [{type, title, path, content, score, chain}]
    """
    results = []
    query_lower = query.lower()
    
    # 1. 提取候选实体名
    struct_candidates = []
    for s in ir_data.get('structs', []):
        sname = s.get('name', '') if isinstance(s, dict) else getattr(s, 'name', '')
        if sname:
            score = fuzzy_score(query_lower, sname.lower())
            if score >= 0.4:
                struct_candidates.append((sname, score))
    
    # 2. 对于每个候选实体，追踪关联路由和业务逻辑
    for struct_name, struct_score in struct_candidates:
        struct_lower = struct_name.lower()
        
        # 2a. 找使用该 struct 的路由
        related_routes = []
        for route in ir_data.get('routes', []):
            route_handler = route.get('handler', '').lower()
            route_path = route.get('path', '').lower()
            route_request = route.get('request', '').lower()
            route_response = route.get('response', '').lower()
            
            if (struct_lower in route_handler or struct_lower in route_path or
                struct_lower in route_request or struct_lower in route_response):
                related_routes.append({
                    'type': 'route',
                    'title': f"{route.get('method', '')} {route.get('path', '')}",
                    'path': route.get('file', ''),
                    'content': f"Handler: {route.get('handler', '')}",
                    'score': struct_score * 0.9,
                    'chain': f"struct:{struct_name} → route:{route.get('path', '')}",
                })
        
        # 2b. 找涉及该 struct 的业务逻辑
        related_bl = []
        for bl in ir_data.get('business_logic', []):
            bl_desc = bl.get('description', '').lower()
            bl_handler = bl.get('handler', '').lower()
            
            if struct_lower in bl_desc or struct_lower in bl_handler:
                related_bl.append({
                    'type': 'business_logic',
                    'title': f"业务逻辑: {bl.get('handler', '')}",
                    'path': bl.get('file', ''),
                    'content': bl_desc[:200],
                    'score': struct_score * 0.8,
                    'chain': f"struct:{struct_name} → business_logic:{bl.get('handler', '')}",
                })
        
        # 2c. 找调用该 struct 相关方法的函数
        related_funcs = []
        for func in ir_data.get('functions', []):
            fname = func.get('name', '').lower()
            fsig = func.get('signature', '').lower()
            
            if struct_lower in fname or struct_lower in fsig:
                related_funcs.append({
                    'type': 'function',
                    'title': func.get('name', ''),
                    'path': func.get('file', ''),
                    'content': func.get('signature', ''),
                    'score': struct_score * 0.85,
                    'chain': f"struct:{struct_name} → function:{func.get('name', '')}",
                })
        
        # 合并关联证据
        all_related = related_routes + related_bl + related_funcs
        if all_related:
            results.append({
                'type': 'struct',
                'title': struct_name,
                'path': '',
                'content': f"关联路由: {len(related_routes)}, 业务逻辑: {len(related_bl)}, 函数: {len(related_funcs)}",
                'score': struct_score,
                'chain': f"struct:{struct_name} → {len(all_related)} related items",
            })
            results.extend(all_related)
    
    # 3. 如果没有找到 struct 关联，尝试 entity-table 关联
    if not results:
        for et in ir_data.get('entity_tables', []):
            entity = et.get('entity', '').lower()
            table = et.get('table', '').lower()
            searchable = f"{entity} {table}"
            score = fuzzy_score(query_lower, searchable)
            if score >= 0.4:
                # 找涉及该表的路由
                related_routes = []
                for route in ir_data.get('routes', []):
                    route_path = route.get('path', '').lower()
                    route_request = route.get('request', '').lower()
                    if entity in route_path or entity in route_request or table in route_path or table in route_request:
                        related_routes.append(route.get('path', ''))
                
                results.append({
                    'type': 'entity_table',
                    'title': f"{et.get('entity', '')} → {et.get('table', '')}",
                    'path': et.get('file', ''),
                    'content': searchable,
                    'score': score,
                    'chain': f"entity:{entity} → table:{table} → routes:{related_routes}",
                })
    
    # 去重并排序
    seen = set()
    unique = []
    for r in results:
        key = (r.get('type'), r.get('title'))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    
    unique.sort(key=lambda x: x.get('score', 0), reverse=True)
    return unique[:top_k]


# ──────────────────────────────────────────────
# Query Understanding — 查询理解与重构
# ──────────────────────────────────────────────

def understand_query(query: str, ir_data: Optional[dict] = None) -> Dict:
    """查询理解 — 分析查询意图并生成最优搜索策略
    
    Returns:
        {
            'original_query': str,
            'intent': str,
            'entities': List[str],      # 提取的实体名
            'actions': List[str],        # 提取的动作
            'search_strategy': str,      # 'precise' / 'fuzzy' / 'semantic' / 'correlation'
            'recommended_sources': List[str],
            'expanded_queries': List[str],
        }
    """
    result = {
        'original_query': query,
        'intent': 'query',
        'entities': [],
        'actions': [],
        'search_strategy': 'fuzzy',
        'recommended_sources': ['code', 'schema', 'api_docs'],
        'expanded_queries': [query],
    }
    
    query_lower = query.lower()
    
    # 1. 意图识别
    intent, _ = extract_intent(query)
    result['intent'] = intent
    
    # 2. 实体提取
    # 驼峰实体名
    camel_entities = re.findall(r'[A-Z][a-z]+(?:[A-Z][a-z]+)*', query)
    result['entities'].extend(camel_entities)
    
    # 中文实体名
    cn_entities = re.findall(r'[\u4e00-\u9fff]{2,6}', query)
    result['entities'].extend(cn_entities)
    
    # 3. 动作提取
    action_patterns = {
        'create': ['创建', '新建', 'add', 'create', 'insert'],
        'read': ['查询', '获取', 'get', 'list', 'search', '查看'],
        'update': ['更新', '修改', 'update', 'edit', 'modify'],
        'delete': ['删除', 'delete', 'remove', 'destroy'],
        'approve': ['审核', '批准', 'approve', 'review'],
        'reject': ['拒绝', 'reject'],
        'publish': ['发布', 'publish', '上线'],
        'sync': ['同步', 'sync', 'syncing'],
    }
    for action, patterns in action_patterns.items():
        if any(p in query_lower for p in patterns):
            result['actions'].append(action)
    
    # 4. 搜索策略选择
    if intent == 'impact' or intent == 'callchain':
        result['search_strategy'] = 'correlation'
        result['recommended_sources'] = ['code', 'business']
    elif intent == 'debug':
        result['search_strategy'] = 'fuzzy'
        result['recommended_sources'] = ['code', 'schema', 'business']
    elif intent == 'relationship':
        result['search_strategy'] = 'correlation'
        result['recommended_sources'] = ['code', 'entity_relations']
    elif intent == 'coverage':
        result['search_strategy'] = 'fuzzy'
        result['recommended_sources'] = ['code', 'schema', 'api_docs', 'business']
    elif re.match(r'^/api/', query_lower) or re.search(r'\b\d{3,}\b', query_lower):
        result['search_strategy'] = 'precise'
    else:
        result['search_strategy'] = 'fuzzy'
    
    # 5. 扩展查询
    expanded = [query]
    if result['entities']:
        expanded.extend(result['entities'])
    if result['actions']:
        expanded.extend(result['actions'])
    
    # 同义词扩展
    try:
        expanded = expand_synonyms(query)
    except Exception:
        pass
    
    result['expanded_queries'] = list(dict.fromkeys(expanded))[:30]
    
    return result


def smart_search(query: str, ir_data: dict, profile: dict = None, top_k: int = 20, kb_dir: Optional[str] = None) -> List[Dict]:
    """智能搜索 — 基于查询理解选择最优搜索策略，使用真正的 RRF 融合多路结果。

    增强版（RRF Fusion）：
    1. 多路并行搜索：fuzzy/code search + semantic search + BM25 search + synonym-expanded search
    2. 真正的 RRF (Reciprocal Rank Fusion) 融合，不同 source_type 使用不同的 k 值调优
    3. 跨语言 query variant 自动扩展提升召回率
    4. Knowledge base markdown 文件搜索（kb_dir 参数）
    5. 保留原有 API 兼容：参数签名向后兼容

    Args:
        query: 搜索查询
        ir_data: IR 缓存数据
        profile: 可选 profile 配置
        top_k: 返回前 K 个结果
        kb_dir: 知识库目录（可选），用于搜索 .md/.txt 文件

    Returns:
        融合搜索结果
    """
    # ── Step 1: Query Understanding ──
    understanding = understand_query(query, ir_data)
    strategy = understanding['search_strategy']

    # ── Step 2: Generate expanded query variants (cross-language + synonym + abbr) ──
    expanded_variants = expand_query_variants_v2(query, ir_data, profile)

    # ── Step 3: Multi-path parallel search ──
    # Each path produces a ranked list; we fuse them with RRF below.
    candidate_lists = []  # List[List[Dict]] — one list per search path
    path_labels = []      # Track which path each list came from

    if strategy == 'correlation':
        # Cross-field correlation search as primary path
        corr_results = cross_field_search(query, ir_data, top_k=top_k * 2)
        for r in corr_results:
            r['_path'] = 'correlation'
        candidate_lists.append(corr_results)
        path_labels.append('correlation')
    else:
        # Path A: Direct fuzzy/code search (original query)
        code_results = search_code(query, "", top_k=top_k * 2, profile=profile, ir_cache=ir_data)
        for r in code_results:
            r['_path'] = 'code_fuzzy'
        candidate_lists.append(code_results)
        path_labels.append('code_fuzzy')

        # Path B: Synonym-expanded search (uses expand_synonyms internally)
        for variant in expanded_variants[:8]:  # Limit to top 8 variants
            variant_results = search_code(variant, "", top_k=top_k, profile=profile, ir_cache=ir_data)
            if variant_results:
                for r in variant_results:
                    r['_path'] = f'synonym:{variant}'
                candidate_lists.append(variant_results)
                path_labels.append(f'synonym:{variant}')

        # Path C: Semantic expansion search
        semantic_queries = semantic_expand_query(query, ir_data, top_k=15)
        if semantic_queries:
            semantic_results = _search_code_fuzzy(ir_data, semantic_queries, top_k=top_k * 2)
            for r in semantic_results:
                r['_path'] = 'semantic'
            candidate_lists.append(semantic_results)
            path_labels.append('semantic')

        # Path D: BM25 search on IR data
        try:
            from enhanced_search import BM25Scorer
            searchable_docs = []
            bm25_index_map = []  # Map doc index back to IR entries

            for func in ir_data.get('functions', []):
                sig = func.get('signature', func.get('name', ''))
                if sig:
                    searchable_docs.append(sig)
                    bm25_index_map.append(('function', func))

            for route in ir_data.get('routes', []):
                rs = f"{route.get('method', '')} {route.get('path', '')} {route.get('handler', '')}"
                if rs:
                    searchable_docs.append(rs)
                    bm25_index_map.append(('route', route))

            if searchable_docs:
                scorer = BM25Scorer()
                scorer.fit(searchable_docs)
                bm25_results = scorer.search(query, top_k=top_k * 2)
                bm25_path_results = []
                for doc_idx, score in bm25_results:
                    entry_type, entry = bm25_index_map[doc_idx]
                    if entry_type == 'function':
                        bm25_path_results.append({
                            'type': 'function',
                            'title': entry.get('name', ''),
                            'path': entry.get('file', ''),
                            'line': entry.get('line', 0),
                            'content': entry.get('signature', ''),
                            'score': score,
                            'source': 'bm25',
                            '_path': 'bm25',
                        })
                    elif entry_type == 'route':
                        bm25_path_results.append({
                            'type': 'route',
                            'title': f"{entry.get('method', '').upper()} {entry.get('path', '')}",
                            'path': entry.get('file', ''),
                            'line': entry.get('line', 0),
                            'content': entry.get('handler', ''),
                            'score': score,
                            'source': 'bm25',
                            '_path': 'bm25',
                        })
                if bm25_path_results:
                    candidate_lists.append(bm25_path_results)
                    path_labels.append('bm25')
        except ImportError:
            pass  # BM25 is optional

    # ── Step 3.5: Knowledge Base Markdown Search (enhancement) ──
    if kb_dir and Path(kb_dir).exists():
        try:
            kb_results = _search_kb_markdown(query, kb_dir, top_k=top_k // 2)
            if kb_results:
                for r in kb_results:
                    r['_path'] = 'wiki'
                candidate_lists.append(kb_results)
                path_labels.append('wiki')
        except Exception:
            pass  # KB search is optional enhancement

    # ── Step 4: True RRF Fusion with source_type-aware k values ──
    fused = rrf_fuse_multi_source(candidate_lists, path_labels, top_k=top_k)

    # ── Step 5: Add query understanding metadata ──
    for r in fused[:top_k]:
        r['_intent'] = understanding['intent']
        r['_strategy'] = strategy

    return fused[:top_k]


def _search_kb_markdown(query: str, kb_dir: str, top_k: int = 10) -> List[Dict]:
    """Search knowledge base markdown files for relevant content.

    Uses lightweight BM25-like scoring on markdown file content.
    Returns structured evidence items compatible with the rest of the pipeline.
    """
    results = []
    kb_path = Path(kb_dir)

    # Find all markdown files
    md_files = list(kb_path.glob('**/*.md')) + list(kb_path.glob('**/*.txt'))

    if not md_files:
        return results

    # Simple tokenization for scoring
    query_terms = set(re.findall(r'[a-zA-Z]{2,}|[\u4e00-\u9fff]', query.lower()))
    if not query_terms:
        return results

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue

        # Score by term overlap
        content_lower = content.lower()
        term_hits = sum(1 for t in query_terms if t in content_lower)
        if term_hits == 0:
            continue

        # TF-like score: term hits / total terms, normalized by doc length
        doc_terms = len(re.findall(r'[a-zA-Z]{2,}|[\u4e00-\u9fff]', content_lower))
        if doc_terms == 0:
            continue

        score = (term_hits / len(query_terms)) * min(doc_terms / 1000, 5.0)

        # Extract snippet around first match
        snippet_start = max(0, content_lower.find(next(t for t in query_terms if t in content_lower)) - 100)
        snippet = content[snippet_start:snippet_start + 300].strip()

        results.append({
            'type': 'knowledge_base',
            'title': md_file.name,
            'path': str(md_file.relative_to(kb_path.parent)),
            'content': snippet,
            'score': round(score, 4),
            'source': 'wiki',
            'file_size': md_file.stat().st_size,
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]


# ──────────────────────────────────────────────
# RRF Fusion with Source-Type-Aware K Values
# ──────────────────────────────────────────────

# Per-source-type RRF k-value tuning. Lower k = faster rank decay = more emphasis on top ranks.
# code results should rank higher, so they get a slightly lower k (sharper top-rank boost).
_RRF_K_BY_SOURCE = {
    "code": 40,           # function/route/handler — strongest signal, sharper top-rank boost
    "api_docs": 50,       # API documentation — strong signal
    "schema": 60,         # struct/table/schema — neutral weight
    "business": 70,       # business rules/knowledge — lighter weight, broader recall
    "semantic": 75,       # semantic expansion — softer ranking
    "bm25": 55,           # BM25 scoring — moderate signal
    "synonym": 65,        # synonym-expanded search — moderate signal
    "correlation": 50,    # cross-field correlation — strong signal
    "wiki": 80,           # wiki knowledge — lowest priority
    "knowledge": 80,      # knowledge base — lowest priority
}

# Default RRF k when source type is unknown
_RRF_K_DEFAULT = 60


def rrf_fuse_multi_source(
    candidates: List[List[Dict]],
    path_labels: Optional[List[str]] = None,
    top_k: int = 20,
) -> List[Dict]:
    """真正的 RRF (Reciprocal Rank Fusion) 融合多路结果，支持不同 source_type 的 k 值调优。

    与简单加权融合的区别：
    - 不使用固定权重拼接分数，而是用 RRF 公式: score = Σ 1/(k + rank)
    - 每个搜索路径独立排序后，按排名位置计算融合分数
    - 不同 source_type 使用不同的 k 值：code 类用较小的 k（更强调 Top-N），
      business/wiki 类用较大的 k（更宽容的排名衰减）
    - 同一条证据在多个路径中出现时，累加所有路径的 RRF 分数

    Args:
        candidates: 多路搜索结果列表，每个元素是一个已排序的 Dict 列表
        path_labels: 每路搜索的路径标签（用于确定 k 值），与 candidates 一一对应
        top_k: 返回前 K 个融合结果

    Returns:
        融合排序后的结果列表
    """
    if not candidates:
        return []

    rank_scores = {}  # key → {"score": float, "item": Dict, "sources": set, "rrf_score": float, "orig_scores": Dict}

    for idx, result_list in enumerate(candidates):
        if not result_list:
            continue

        # Determine the k value for this path
        label = path_labels[idx] if path_labels and idx < len(path_labels) else ""
        k = _get_rrf_k_for_label(label)

        for rank, item in enumerate(result_list):
            # Unique key: (type, title) — more precise than path alone
            item_type = item.get('type', '')
            item_title = item.get('title', '')
            key = (item_type, item_title)

            if key not in rank_scores:
                rank_scores[key] = {
                    'score': 0.0,
                    'rrf_score': 0.0,
                    'item': item,
                    'sources': set(),
                    'orig_scores': {},
                }

            entry = rank_scores[key]
            entry['sources'].add(item.get('source', 'unknown'))
            entry['orig_scores'][label or f"path_{idx}"] = item.get('score', 0.0)

            # RRF contribution: 1 / (k + rank)
            # rank is 0-indexed, RRF convention uses 1-indexed: 1/(k + rank + 1)
            rrf_contribution = 1.0 / (k + rank + 1)
            entry['rrf_score'] += rrf_contribution

            # Final score = RRF score (primary) + normalized original score (secondary tie-breaker)
            max_orig = max(entry['orig_scores'].values()) if entry['orig_scores'] else 0
            entry['score'] = rrf_contribution + 0.1 * max_orig  # RRF is dominant, orig score is tie-breaker

    # Sort by fused score descending
    sorted_entries = sorted(
        rank_scores.values(),
        key=lambda x: x["score"],
        reverse=True,
    )

    # Convert to output format
    result = []
    for entry in sorted_entries[:top_k]:
        item = entry['item'].copy()
        item['score'] = round(entry['score'], 6)
        item['rrf_score'] = round(entry['rrf_score'], 6)
        item['sources'] = list(entry['sources'])
        result.append(item)

    return result


def _get_rrf_k_for_label(label: str) -> int:
    """根据路径标签确定 RRF k 值。"""
    if not label:
        return _RRF_K_DEFAULT

    label_lower = label.lower()

    # Check against known source types
    for source_type, k_val in _RRF_K_BY_SOURCE.items():
        if source_type in label_lower:
            return k_val

    # Fallback: try to infer from the label
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


# ──────────────────────────────────────────────
# NEW: Enhanced Semantic Search with Contextual Expansion
# ──────────────────────────────────────────────

# 上下文相关术语映射 — 基于业务场景的语义扩展
_CONTEXTUAL_TERM_MAP = {
    # 广告生命周期
    '创建': ['create', 'build', 'init', 'new', 'add', 'insert'],
    '删除': ['delete', 'remove', 'destroy', 'drop'],
    '更新': ['update', 'edit', 'modify', 'change', 'patch'],
    '查询': ['query', 'search', 'find', 'list', 'get', 'fetch'],
    '审核': ['review', 'audit', 'approve', 'check', 'verify'],
    '发布': ['publish', 'release', 'go_live', 'deploy', 'launch'],
    # 性能相关
    '缓存': ['cache', 'redis', 'memcached', 'hit_rate', 'local_cache'],
    '慢查询': ['slow_query', 'performance', 'index', 'optimization', 'N+1'],
    '超时': ['timeout', 'deadline', 'context_timeout', 'deadline_exceeded'],
    '并发': ['concurrent', 'goroutine', 'worker_pool', 'thread_pool', 'race_condition'],
    # 安全相关
    '权限': ['permission', 'rbac', 'acl', 'authorization', 'access_control'],
    '鉴权': ['auth', 'jwt', 'token', 'oauth', 'sso', 'login_check'],
    '注入': ['sql_injection', 'xss', 'injection', 'sanitization'],
    # 数据一致性
    '事务': ['transaction', 'commit', 'rollback', 'atomic', 'isolation'],
    '幂等': ['idempotent', 'dedup', 'unique_key', 'setnx', 'lock'],
    '最终一致性': ['eventual_consistency', 'saga', 'compensation', 'mq'],
}


def contextual_expand(query: str) -> List[str]:
    """基于业务上下文的语义扩展 — 比同义词更精准。
    
    根据查询中的关键词，自动扩展相关的业务术语。
    例如：查询"素材审核" → 自动扩展 "creative review audit approval"
    
    Returns:
        扩展后的术语列表
    """
    expanded = []
    query_lower = query.lower()
    
    for cn_term, en_terms in _CONTEXTUAL_TERM_MAP.items():
        if cn_term in query or query_lower in cn_term.lower():
            expanded.extend(en_terms)
    
    # Also expand English terms to Chinese
    for en_term, cn_terms in _CONTEXTUAL_TERM_MAP.items():
        for ct in cn_terms:
            if ct.lower() in query_lower:
                expanded.append(en_term)
                break
    
    return list(dict.fromkeys(expanded))[:20]


def smart_semantic_search(query: str, ir_data: dict, top_k: int = 20) -> List[dict]:
    """智能语义搜索 — 融合 BM25 + 模糊匹配 + 上下文扩展 + IR-aware 排序。
    
    策略：
    1. 先做 query understanding（意图识别 + 实体提取）
    2. 用 contextual_expand 生成语义扩展词
    3. 对 IR 中每个候选项计算多维度分数
    4. 返回融合排序结果
    
    This is a drop-in replacement for basic fuzzy search that provides
    much better recall for complex queries.
    """
    if not ir_data or not isinstance(ir_data, dict):
        return []
    
    query_lower = query.lower()
    candidates = []
    
    # Collect all searchable items from IR
    searchable = []
    
    # Functions
    for func in ir_data.get('functions', []):
        if isinstance(func, dict):
            searchable.append({
                'type': 'function',
                'name': func.get('name', ''),
                'signature': func.get('signature', ''),
                'file': func.get('file', ''),
                'content': f"{func.get('name', '')} {func.get('signature', '')}",
            })
    
    # Routes
    for route in ir_data.get('routes', []):
        if isinstance(route, dict):
            searchable.append({
                'type': 'route',
                'name': route.get('path', ''),
                'handler': route.get('handler', ''),
                'method': route.get('method', ''),
                'content': f"{route.get('method', '')} {route.get('path', '')} {route.get('handler', '')}",
            })
    
    # Structs
    for struct in ir_data.get('structs', []):
        if isinstance(struct, dict):
            searchable.append({
                'type': 'struct',
                'name': struct.get('name', ''),
                'fields': ', '.join(str(f) for f in struct.get('fields', [])),
                'content': f"{struct.get('name', '')} {struct.get('fields', '')}",
            })
    
    # Error codes
    for ec in ir_data.get('error_codes', []):
        if isinstance(ec, dict):
            searchable.append({
                'type': 'error_code',
                'name': ec.get('name', ''),
                'message': ec.get('message', ''),
                'code': ec.get('code', ''),
                'content': f"{ec.get('name', '')} {ec.get('message', '')}",
            })
    
    # Score each candidate
    for item in searchable:
        content = item.get('content', '').lower()
        
        # Multi-strategy scoring
        exact_score = 1.0 if query_lower in content else 0.0
        fuzzy_s = fuzzy_score(query_lower, content) if content else 0.0
        
        # Contextual boost: does this match our expanded terms?
        ctx_terms = contextual_expand(query)
        ctx_boost = 0.0
        for term in ctx_terms:
            if term.lower() in content:
                ctx_boost = max(ctx_boost, 0.3)
                break
        
        # Type priority boost (functions/routes are more relevant than error codes)
        type_boost = {'function': 0.15, 'route': 0.15, 'struct': 0.1, 'error_code': 0.05}.get(item['type'], 0.0)
        
        # Final score
        final_score = 0.5 * exact_score + 0.35 * fuzzy_s + 0.15 * ctx_boost + type_boost
        
        if final_score > 0.1:
            candidates.append({
                **item,
                'score': round(final_score, 4),
                'exact_match': exact_score > 0,
                'fuzzy_score': round(fuzzy_s, 4),
                'context_boost': round(ctx_boost, 4),
            })
    
    # Sort by score descending
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[:top_k]
