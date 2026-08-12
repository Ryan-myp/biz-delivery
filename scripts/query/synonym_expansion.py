#!/usr/bin/env python3
"""同义词扩展模块 — 多路查询中的查询词扩展

支持内置词典、Profile 配置、领域上下文、Query Variant 等多种扩展策略。

Usage:
    from scripts.query.synonym_expansion import expand_synonyms, contextual_expand
"""

from typing import Dict, List, Optional


# ──────────────────────────────────────────────
# Built-in Synonym Dictionary — 广告平台领域
# ──────────────────────────────────────────────

_BUILTIN_SYNONYMS: Dict[str, List[str]] = {
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
    '事务': ['transaction', 'tx', 'commit', 'rollback', 'acidity'],
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
    '鉴权': ['authentication', 'jwt', 'oauth', 'token', 'sso', '单点登录'],
    '中间件': ['middleware', 'interceptor', 'filter', 'gateway'],
    '异步': ['async', 'asynchronous', 'non-blocking', 'event-driven'],
    '同步': ['sync', 'synchronous', 'blocking'],
    '批量': ['batch', 'bulk', '批量处理', '批处理'],
    '实时': ['realtime', 'real-time', 'streaming', 'live'],
    '离线': ['offline', 'batch_job', 'etl', 'spark'],
}

# ──────────────────────────────────────────────
# Domain Context Map — 领域上下文扩展
# ──────────────────────────────────────────────

_DOMAIN_CONTEXT_MAP: Dict[str, List[str]] = {
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

# ──────────────────────────────────────────────
# Contextual Term Map — 业务上下文术语映射
# ──────────────────────────────────────────────

_CONTEXTUAL_TERM_MAP: Dict[str, List[str]] = {
    '创建': ['create', 'build', 'init', 'new', 'add', 'insert'],
    '删除': ['delete', 'remove', 'destroy', 'drop'],
    '更新': ['update', 'edit', 'modify', 'change', 'patch'],
    '查询': ['query', 'search', 'find', 'list', 'get', 'fetch'],
    '审核': ['review', 'audit', 'approve', 'check', 'verify'],
    '发布': ['publish', 'release', 'go_live', 'deploy', 'launch'],
    '缓存': ['cache', 'redis', 'memcached', 'hit_rate', 'local_cache'],
    '慢查询': ['slow_query', 'performance', 'index', 'optimization', 'N+1'],
    '超时': ['timeout', 'deadline', 'context_timeout', 'deadline_exceeded'],
    '并发': ['concurrent', 'goroutine', 'worker_pool', 'thread_pool', 'race_condition'],
    '权限': ['permission', 'rbac', 'acl', 'authorization', 'access_control'],
    '鉴权': ['auth', 'jwt', 'token', 'oauth', 'sso', 'login_check'],
    '注入': ['sql_injection', 'xss', 'injection', 'sanitization'],
    '事务': ['transaction', 'commit', 'rollback', 'atomic', 'isolation'],
    '幂等': ['idempotent', 'dedup', 'unique_key', 'setnx', 'lock'],
    '最终一致性': ['eventual_consistency', 'saga', 'compensation', 'mq'],
}


def expand_synonyms(query: str, profile: dict = None) -> List[str]:
    """同义词扩展 — 从多种来源扩展查询词
    
    Args:
        query: 查询文本
        profile: 可选，业务 Profile（用于读取自定义同义词）
        
    Returns:
        扩展后的关键词列表
    """
    keywords = [query]
    query_lower = query.lower()
    
    # 1. 从内置同义词扩展
    for term, variants in _BUILTIN_SYNONYMS.items():
        if term.lower() in query_lower:
            keywords.extend(variants)
    
    # 2. 从 profile 的 query_aliases 扩展
    if profile:
        profile_data = profile.get('profile', profile) if isinstance(profile, dict) else profile
        for source_key in ('synonym_map', 'query_aliases'):
            mapping = profile_data.get(source_key, {})
            for term, variants in mapping.items():
                if term.lower() in query_lower:
                    keywords.extend(variants)
    
    # 3. 领域上下文扩展
    domain_context = _get_domain_context(query)
    if domain_context:
        keywords.extend(domain_context)
    
    # 4. 上下文术语扩展
    ctx_terms = contextual_expand(query)
    if ctx_terms:
        keywords.extend(ctx_terms)
    
    # 去重，保留顺序
    keywords = list(dict.fromkeys(keywords))
    return keywords[:30]  # 最多 30 个关键词


def _get_domain_context(query: str) -> List[str]:
    """根据查询语义返回领域相关的上下文扩展词"""
    query_lower = query.lower()
    results = []
    for key, ctx_words in _DOMAIN_CONTEXT_MAP.items():
        if key in query_lower or any(k in query_lower for k in ctx_words):
            results.extend(ctx_words)
    return list(dict.fromkeys(results))[:15]


def contextual_expand(query: str) -> List[str]:
    """基于业务上下文的语义扩展
    
    Args:
        query: 查询文本
        
    Returns:
        扩展后的术语列表
    """
    expanded = []
    query_lower = query.lower()
    
    # Chinese to English
    for cn_term, en_terms in _CONTEXTUAL_TERM_MAP.items():
        if cn_term in query:
            expanded.extend(en_terms)
    
    # English to Chinese
    for en_term, cn_terms in _CONTEXTUAL_TERM_MAP.items():
        for ct in cn_terms:
            if ct.lower() in query_lower:
                expanded.append(en_term)
                break
    
    return list(dict.fromkeys(expanded))[:20]


def get_builtin_synonyms() -> Dict[str, List[str]]:
    """返回内置同义词词典
    
    Returns:
        同义词词典
    """
    return _BUILTIN_SYNONYMS.copy()


def get_contextual_term_map() -> Dict[str, List[str]]:
    """返回上下文术语映射
    
    Returns:
        上下文术语映射
    """
    return _CONTEXTUAL_TERM_MAP.copy()
