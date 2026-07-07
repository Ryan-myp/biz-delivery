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
    1. 从 query_aliases 扩展中文业务词
    2. 从业务术语表扩展同义词
    3. 从 IR 缓存的 functions/route handler 扩展匹配项
    """
    keywords = [query]
    
    # 1. 从 profile 加载 query_aliases
    if profile:
        aliases = profile.get('query_aliases', {})
        expanded = []
        for alias, terms in aliases.items():
            if alias.lower() in query.lower():
                expanded.extend(terms)
        keywords.extend(expanded)
    
    # 2. 从 business_terminology 扩展
    # 这个需要 IR 缓存，暂时跳过
    
    # 3. 从 query 中提取中英文关键词
    # 中文：直接分词
    # 英文：按驼峰/下划线分割
    import re
    # 提取驼峰命名
    camel = re.findall(r'[A-Z][a-z]+|[a-z]+', query)
    keywords.extend(camel)
    
    # 去重
    keywords = list(dict.fromkeys(keywords))
    
    return keywords[:10]  # 最多 10 个关键词


# ──────────────────────────────────────────────
# Semantic Search — 轻量级 TF-IDF + Cosine Similarity
# ──────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    """轻量分词：中文按字符切分，英文按单词切分"""
    import re
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

def search_code(query: str, repo_path: str, top_k: int = 10, cache_dir: str = None, profile: dict = None) -> List[Dict]:
    """搜索代码 — 从 IR 缓存中匹配函数/路由/struct
    
    复用 learn_repo.py 扫描后的 IR 缓存
    
    增强：语义搜索作为精确匹配的补充
    """
    # 加载 profile 获取 query_aliases
    if profile is None:
        import json
        profile_path = str(Path(__file__).parent.parent / "profiles" / "default.json")
        profile = {}
        try:
            with open(profile_path) as f:
                profile = json.load(f)
        except:
            pass
    
    # 使用 query_expander 扩展查询词
    expanded_queries = expand_query(query, profile)
    
    if cache_dir:
        cache_file = Path(cache_dir) / "ir_cache.json"
        if cache_file.exists():
            with open(cache_file) as f:
                ir_data = json.load(f)

            # 先用精确 + fuzzy 搜索
            results = _search_code_exact(ir_data, expanded_queries, top_k)
            
            # 如果结果太少，启用语义搜索补充
            if len(results) < top_k // 2:
                semantic_queries = semantic_expand_query(query, ir_data, top_k=15)
                if semantic_queries:
                    semantic_results = _search_code_exact(ir_data, semantic_queries, top_k)
                    # 合并去重（基于 path+type）
                    seen = {(r.get('path'), r.get('type')) for r in results}
                    for sr in semantic_results:
                        key = (sr.get('path'), sr.get('type'))
                        if key not in seen:
                            seen.add(key)
                            results.append(sr)
            
            return results[:top_k]
    
    return []


def _search_code_exact(ir_data: dict, queries: List[str], top_k: int) -> List[Dict]:
    """精确搜索 — 复用原有的 fuzzy + synonym 搜索逻辑"""
    results = []
    for q in queries:
        query_lower = q.lower()
        
        # 搜索函数
        for func in ir_data.get('functions', []):
            fname = func.get('name', '').lower()
            fsig = func.get('signature', '').lower()
            score = fuzzy_score(query_lower, fname)
            if score >= 0.3:
                results.append({
                    'type': 'function',
                    'title': func['name'],
                    'path': func.get('file', ''),
                    'line': func.get('line', 0),
                    'content': func.get('signature', ''),
                    'score': score,
                })
        
        # 搜索路由
        for route in ir_data.get('routes', []):
            route_str = f"{route.get('method', '')} {route.get('path', '')} {route.get('handler', '')}".lower()
            score = fuzzy_score(query_lower, route_str)
            if score >= 0.3:
                results.append({
                    'type': 'route',
                    'title': f"{route.get('method', '').upper()} {route.get('path', '')}",
                    'path': route.get('file', ''),
                    'line': route.get('line', 0),
                    'content': route.get('handler', ''),
                    'score': score,
                })
        
        # 搜索 struct
        for struct in ir_data.get('structs', []):
            sname = struct.get('name', '').lower()
            score = fuzzy_score(query_lower, sname)
            if score >= 0.3:
                results.append({
                    'type': 'struct',
                    'title': struct['name'],
                    'path': struct.get('file', ''),
                    'line': struct.get('line', 0),
                    'content': '\n'.join([f.get('name', str(f)) for f in struct.get('fields', [])[:5]]),
                    'score': score,
                })
        
        # 搜索 entity-table 映射
        for et in ir_data.get('entity_tables', []):
            entity = et.get('entity', '')
            table = et.get('table', '')
            searchable = f"{entity} {table}".lower()
            score = fuzzy_score(query_lower, searchable)
            if score >= 0.3:
                results.append({
                    'type': 'entity_table',
                    'title': f"{entity} -> {table}",
                    'path': et.get('file', ''),
                    'line': 0,
                    'content': searchable,
                    'score': score,
                })
        
        # 搜索 business_logic
        for bl in ir_data.get('business_logic', []):
            handler = bl.get('handler', '')
            route = bl.get('route', '')
            searchable = f"{handler} {route}".lower()
            score = fuzzy_score(query_lower, searchable)
            if score >= 0.3:
                results.append({
                    'type': 'business_logic',
                    'title': f"业务逻辑: {handler}",
                    'path': bl.get('file', ''),
                    'line': 0,
                    'content': searchable[:200],
                    'score': score,
                })
    
    # 去重（基于 path + type），保留最高分
    seen = {}
    for r in results:
        key = (r.get('path'), r.get('type'))
        if key not in seen or r.get('score', 0) > seen[key].get('score', 0):
            seen[key] = r
    return list(seen.values())


def search_schema(query: str, repo_path: str, top_k: int = 10, cache_dir: str = None) -> List[Dict]:
    """搜索 schema — 从 IR 缓存中匹配表结构/字段"""
    if cache_dir:
        cache_file = Path(cache_dir) / "ir_cache.json"
        if cache_file.exists():
            import json
            with open(cache_file) as f:
                ir_data = json.load(f)
            
            results = []
            query_lower = query.lower()
            for table in ir_data.get('tables', []):
                if query_lower in table.get('name', '').lower():
                    results.append({
                        'type': 'table',
                        'title': table['name'],
                        'path': table.get('file', ''),
                        'line': table.get('line', 0),
                        'content': ', '.join(table.get('columns', [])[:10]),
                        'score': 1.0,
                    })
            
            return results[:10]
    
    return []


def search_api_docs(query: str, repo_path: str, top_k: int = 10, cache_dir: str = None) -> List[Dict]:
    """搜索 API 文档 — 从 IR 缓存中匹配路由/Request/Response"""
    if cache_dir:
        cache_file = Path(cache_dir) / "ir_cache.json"
        if cache_file.exists():
            import json
            with open(cache_file) as f:
                ir_data = json.load(f)
            
            results = []
            query_lower = query.lower()
            for route in ir_data.get('routes', []):
                route_str = f"{route.get('method', '')} {route.get('path', '')} {route.get('handler', '')} {route.get('request', '')} {route.get('response', '')}".lower()
                if query_lower in route_str:
                    results.append({
                        'type': 'api',
                        'title': f"{route.get('method', '').upper()} {route.get('path', '')}",
                        'path': route.get('file', ''),
                        'line': route.get('line', 0),
                        'content': f"Handler: {route.get('handler', '')}\nRequest: {route.get('request', '')}\nResponse: {route.get('response', '')}",
                        'score': 1.0,
                    })
            
            return results[:10]
    
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
    return [item for item_list in [x['items'] for x in sorted_items] for item in item_list][:10]


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

def run_evidence_query(query: str, profile_path: str = None, wiki_path: str = None,
                       top_k: int = 10, sources: List[str] = None, cache_dir: str = None) -> Dict[str, Any]:
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
        results = search_code(query, "", top_k, cache_dir=cache_dir)
        candidates.append(results)
        path_results['code'] = results

    if "schema" in sources:
        results = search_schema(query, "", top_k, cache_dir=cache_dir)
        candidates.append(results)
        path_results['schema'] = results

    if "api_docs" in sources:
        results = search_api_docs(query, "", top_k, cache_dir=cache_dir)
        candidates.append(results)
        path_results['api_docs'] = results
    
    if "business" in sources:
        results = search_business(query, "", top_k, cache_dir=cache_dir)
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
