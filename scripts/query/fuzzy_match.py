#!/usr/bin/env python3
"""模糊匹配模块 — 中英文 fuzzy matching

基于 Levenshtein 编辑距离 + 中文 n-gram + 拼音相似度

Usage:
    from scripts.query.fuzzy_match import fuzzy_score, fuzzy_match, levenshtein_distance
"""

import re
from typing import Optional
from functools import lru_cache


# Chinese character range regex
_RE_CHINESE_RANGE = re.compile(r'[\u4e00-\u9fff]')

# Common Chinese compound words for word-level segmentation
_CN_COMPOUNDS = frozenset([
    '素材审核', '广告组', '广告计划', '竞价引擎', '投放管理', '报表统计',
    '权限控制', '缓存策略', '消息队列', '定时任务', '数据迁移', '监控告警',
    '日志收集', '限流降级', '幂等设计', '加密解密', '搜索索引', '推送通知',
    '对账结算', '风控系统', '错误码', '鉴权中间件', '健康检查', '回滚方案',
    '灰度发布', 'Feature Flag', '金丝雀发布', '分布式锁', '事务管理',
    '补偿机制', '重试策略', '异步处理', '批量处理', '实时计算', '离线分析',
])

# Pinyin initials mapping
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
}


@lru_cache(maxsize=2048)
def levenshtein_distance(s1: str, s2: str) -> int:
    """计算两个字符串的 Levenshtein 编辑距离
    
    Args:
        s1: 第一个字符串
        s2: 第二个字符串
        
    Returns:
        编辑距离
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if not s2:
        return len(s1)
    
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    
    return prev_row[-1]


def _chinese_to_pinyin_initials(text: str) -> str:
    """将中文文本转换为拼音首字母序列"""
    return ''.join(_PINYIN_INITIALS.get(c, '') for c in text if c in _PINYIN_INITIALS)


def _pinyin_similarity(s1: str, s2: str) -> float:
    """拼音首字母相似度"""
    if not s1 or not s2:
        return 0.0
    
    initials1 = _chinese_to_pinyin_initials(s1)
    initials2 = _chinese_to_pinyin_initials(s2)
    
    if not initials1 or not initials2:
        return 0.0
    
    if initials1 == initials2:
        return 1.0
    
    dist = levenshtein_distance(initials1, initials2)
    max_len = max(len(initials1), len(initials2))
    return 1.0 - dist / max_len if max_len > 0 else 0.0


def _chinese_ngram_similarity(s1: str, s2: str, n: int = 2) -> float:
    """计算中文字符 n-gram 相似度"""
    if not s1 or not s2:
        return 0.0
    
    # Extract Chinese characters
    c1 = re.sub(r'[^\u4e00-\u9fff]', '', s1)
    c2 = re.sub(r'[^\u4e00-\u9fff]', '', s2)
    
    if not c1 or not c2:
        return 0.0
    
    # Character level n-gram
    char_grams1 = {c1[i:i+n] for i in range(max(0, len(c1) - n + 1))}
    char_grams2 = {c2[i:i+n] for i in range(max(0, len(c2) - n + 1))}
    
    if not char_grams1 or not char_grams2:
        return 0.0
    
    char_intersection = len(char_grams1 & char_grams2)
    char_union = len(char_grams1 | char_grams2)
    char_sim = char_intersection / char_union if char_union > 0 else 0.0
    
    # Word level n-gram
    words1 = _chinese_word_segment(c1)
    words2 = _chinese_word_segment(c2)
    
    if words1 and words2:
        word_grams1 = {tuple(words1[i:i+n]) for i in range(max(0, len(words1) - n + 1))}
        word_grams2 = {tuple(words2[i:i+n]) for i in range(max(0, len(words2) - n + 1))}
        
        if word_grams1 and word_grams2:
            word_intersection = len(word_grams1 & word_grams2)
            word_union = len(word_grams1 | word_grams2)
            word_sim = word_intersection / word_union if word_union > 0 else 0.0
            return 0.4 * char_sim + 0.6 * word_sim
    
    return char_sim


def _chinese_word_segment(text: str) -> list:
    """中文分词 — 基于词典的最大匹配 + 双字切分"""
    words = []
    remaining = text
    matched_positions = set()
    
    # 1. Maximum forward matching
    for compound in _CN_COMPOUNDS:
        start = 0
        while True:
            idx = remaining.find(compound, start)
            if idx < 0:
                break
            matched_positions.update(range(idx, idx + len(compound)))
            words.append(compound)
            start = idx + len(compound)
    
    # 2. Unmatched parts use bigram splitting
    for i, ch in enumerate(remaining):
        if i not in matched_positions and ch in _PINYIN_INITIALS:
            if i + 1 < len(remaining) and (i + 1) not in matched_positions:
                bigram = remaining[i:i+2]
                words.append(bigram)
            else:
                words.append(ch)
    
    return words


def adaptive_threshold(query: str, query_type: str = None) -> float:
    """根据查询类型自适应调整阈值
    
    Args:
        query: 查询文本
        query_type: 查询类型
        
    Returns:
        自适应阈值 [0, 1]
    """
    # Short queries need higher threshold
    if len(query) <= 3:
        return 0.8
    elif len(query) <= 10:
        return 0.6
    else:
        return 0.5


@lru_cache(maxsize=1024)
def fuzzy_score(query: str, target: str, threshold: Optional[float] = None) -> float:
    """计算两个字符串的 fuzzy 相似度 [0, 1]
    
    基于 Levenshtein 编辑距离归一化，增强中文支持。
    
    Args:
        query: 查询文本
        target: 目标文本
        threshold: 可选，阈值（用于缓存键）
        
    Returns:
        相似度分数 [0, 1]
    """
    if not query and not target:
        return 1.0
    if not query or not target:
        return 0.0
    
    q_lower = query.lower()
    t_lower = target.lower()
    
    if q_lower == t_lower:
        return 1.0
    
    # Substring match priority
    if q_lower in t_lower or t_lower in q_lower:
        shorter = min(len(q_lower), len(t_lower))
        longer = max(len(q_lower), len(t_lower))
        return 0.8 + 0.2 * (shorter / longer)
    
    # Detect if contains Chinese
    has_chinese = bool(_RE_CHINESE_RANGE.search(q_lower)) or bool(_RE_CHINESE_RANGE.search(t_lower))
    
    # Short strings (<=15 chars): use edit distance
    if max(len(q_lower), len(t_lower)) <= 15:
        dist = levenshtein_distance(q_lower, t_lower)
        max_len = max(len(q_lower), len(t_lower))
        edit_score = 1.0 - dist / max_len if max_len > 0 else 1.0
        
        if has_chinese:
            cn_sim = _chinese_ngram_similarity(q_lower, t_lower)
            return 0.6 * edit_score + 0.4 * cn_sim
        return edit_score
    
    # Long strings: hybrid strategy
    # 1. Word-level Jaccard similarity
    q_words = set(q_lower.split())
    t_words = set(t_lower.split())
    
    jaccard = 0.0
    if q_words and t_words:
        intersection = len(q_words & t_words)
        union = len(q_words | t_words)
        jaccard = intersection / union if union > 0 else 0.0
    
    # 2. Edit distance as auxiliary
    dist = levenshtein_distance(q_lower, t_lower)
    max_len = max(len(q_lower), len(t_lower))
    edit_score = 1.0 - dist / max_len if max_len > 0 else 0.0
    
    # 3. Chinese n-gram similarity
    cn_sim = _chinese_ngram_similarity(q_lower, t_lower) if has_chinese else 0.0
    
    # 4. Pinyin similarity
    py_sim = _pinyin_similarity(q_lower, t_lower) if has_chinese else 0.0
    
    if has_chinese:
        return 0.35 * jaccard + 0.20 * edit_score + 0.30 * cn_sim + 0.15 * py_sim
    return 0.7 * jaccard + 0.3 * edit_score


def fuzzy_match(query: str, target: str, threshold: Optional[float] = None) -> bool:
    """判断 query 和 target 是否 fuzzy 匹配
    
    Args:
        query: 查询文本
        target: 目标文本
        threshold: 可选，阈值
        
    Returns:
        是否匹配
    """
    if threshold is None:
        threshold = adaptive_threshold(query)
    return fuzzy_score(query, target, threshold=threshold) >= threshold


def char_ngrams(text: str, n: int = 2) -> set:
    """生成字符 n-gram"""
    return {text[i:i+n] for i in range(len(text) - n + 1)}
