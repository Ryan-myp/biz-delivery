#!/usr/bin/env python3
"""Wiki 知识查询模块 — 从编译式知识库中检索证据

支持 Markdown 知识库、JSON 缓存、知识图谱等多种数据源。

Usage:
    from scripts.query.wiki_query import query_wiki, load_wiki_index
"""

from typing import Dict, List, Optional
from pathlib import Path
import json
import re


# ──────────────────────────────────────────────
# Wiki Index — 知识库索引
# ──────────────────────────────────────────────

class WikiIndex:
    """Wiki 知识库索引"""
    
    def __init__(self, wiki_path: str):
        self.wiki_path = Path(wiki_path)
        self.index: Dict[str, Dict] = {}
        self._load_index()
    
    def _load_index(self):
        """加载知识库索引"""
        index_file = self.wiki_path / 'index.json'
        if index_file.exists():
            with open(index_file) as f:
                self.index = json.load(f)
    
    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """搜索知识库"""
        results = []
        query_lower = query.lower()
        
        for name, info in self.index.items():
            content = info.get('content', '')
            score = self._calculate_score(query, content, query_lower)
            if score > 0.3:
                results.append({
                    'type': 'wiki',
                    'name': name,
                    'path': info.get('path', ''),
                    'score': round(score, 4),
                    'content': content[:500],
                })
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]
    
    def _calculate_score(self, query: str, content: str, query_lower: str) -> float:
        """计算搜索相关性分数"""
        if not content:
            return 0.0
        
        # 精确匹配
        if query_lower in content.lower():
            return 0.9
        
        # 词级别匹配
        query_words = set(query_lower.split())
        content_words = set(re.findall(r'[a-zA-Z]+|[\u4e00-\u9fff]{2,}', content))
        
        if query_words and content_words:
            intersection = len(query_words & content_words)
            union = len(query_words | content_words)
            return intersection / union if union > 0 else 0.0
        
        return 0.0


def load_wiki_index(wiki_path: str) -> WikiIndex:
    """加载 Wiki 知识库索引
    
    Args:
        wiki_path: 知识库路径
        
    Returns:
        WikiIndex 实例
    """
    return WikiIndex(wiki_path)


def query_wiki(
    query: str,
    wiki_path: Optional[str] = None,
    top_k: int = 5
) -> List[Dict]:
    """查询 Wiki 知识库
    
    Args:
        query: 查询文本
        wiki_path: 知识库路径
        top_k: 返回数量
        
    Returns:
        搜索结果列表
    """
    if not wiki_path:
        # 默认路径
        wiki_path = str(Path(__file__).parent.parent / 'knowledge')
    
    index = load_wiki_index(wiki_path)
    return index.search(query, top_k)


# ──────────────────────────────────────────────
# Knowledge Cache — 知识缓存查询
# ──────────────────────────────────────────────

def query_cache(query: str, cache_dir: str = None, top_k: int = 10) -> List[Dict]:
    """从缓存目录查询知识
    
    Args:
        query: 查询文本
        cache_dir: 缓存目录
        top_k: 返回数量
        
    Returns:
        搜索结果列表
    """
    results = []
    
    if not cache_dir:
        cache_dir = str(Path(__file__).parent.parent / '.cache')
    
    cache_path = Path(cache_dir)
    if not cache_path.exists():
        return results
    
    # 搜索所有 JSON 文件
    for json_file in cache_path.rglob('*.json'):
        try:
            with open(json_file) as f:
                data = json.load(f)
            
            content = json.dumps(data, ensure_ascii=False)
            query_lower = query.lower()
            
            if query_lower in content.lower():
                results.append({
                    'type': 'cache',
                    'name': json_file.name,
                    'path': str(json_file.relative_to(cache_path)),
                    'score': 0.8,
                    'content': content[:500],
                })
        except Exception:
            continue
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]


# ──────────────────────────────────────────────
# Knowledge Graph — 知识图谱查询
# ──────────────────────────────────────────────

def query_knowledge_graph(query: str, graph_data: Optional[dict] = None, top_k: int = 10) -> List[Dict]:
    """查询知识图谱
    
    Args:
        query: 查询文本
        graph_data: 知识图谱数据
        top_k: 返回数量
        
    Returns:
        搜索结果列表
    """
    results = []
    
    if not graph_data or not isinstance(graph_data, dict):
        return results
    
    # 搜索实体
    entities = graph_data.get('entities', [])
    query_lower = query.lower()
    
    for entity in entities:
        if isinstance(entity, dict):
            name = entity.get('name', '')
            if query_lower in name.lower():
                results.append({
                    'type': 'entity',
                    'name': name,
                    'description': entity.get('description', ''),
                    'score': 0.9,
                })
    
    # 搜索关系
    relations = graph_data.get('relations', [])
    for relation in relations:
        if isinstance(relation, dict):
            src = relation.get('source', '')
            tgt = relation.get('target', '')
            if query_lower in src.lower() or query_lower in tgt.lower():
                results.append({
                    'type': 'relation',
                    'source': src,
                    'target': tgt,
                    'relation': relation.get('type', ''),
                    'score': 0.7,
                })
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]


# ──────────────────────────────────────────────
# Markdown Search — Markdown 文件搜索
# ──────────────────────────────────────────────

def search_markdown_docs(query: str, docs_dir: Optional[str] = None, top_k: int = 10) -> List[Dict]:
    """搜索 Markdown 文档
    
    Args:
        query: 查询文本
        docs_dir: 文档目录
        top_k: 返回数量
        
    Returns:
        搜索结果列表
    """
    results = []
    
    if not docs_dir:
        docs_dir = str(Path(__file__).parent.parent / 'docs')
    
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        return results
    
    # 搜索所有 Markdown 文件
    for md_file in docs_path.rglob('*.md'):
        try:
            content = md_file.read_text(encoding='utf-8', errors='ignore')
            query_lower = query.lower()
            
            # 计算相关性分数
            score = 0.0
            if query_lower in content.lower():
                score = 0.8
            
            # 提取上下文
            context_start = max(0, content.lower().find(query_lower) - 200)
            context_end = min(len(content), context_start + 500)
            context = content[context_start:context_end].strip()
            
            if score > 0:
                results.append({
                    'type': 'markdown',
                    'name': md_file.name,
                    'path': str(md_file.relative_to(docs_path)),
                    'score': round(score, 4),
                    'content': context[:300],
                })
        except Exception:
            continue
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]


# ──────────────────────────────────────────────
# Unified Wiki Query — 统一 Wiki 查询入口
# ──────────────────────────────────────────────

def query_wiki_evidence(
    query: str,
    wiki_path: Optional[str] = None,
    cache_dir: Optional[str] = None,
    graph_data: Optional[dict] = None,
    top_k: int = 10
) -> List[Dict]:
    """统一 Wiki 证据查询 — 融合多种知识源
    
    Args:
        query: 查询文本
        wiki_path: 知识库路径
        cache_dir: 缓存目录
        graph_data: 知识图谱数据
        top_k: 返回数量
        
    Returns:
        融合后的搜索结果列表
    """
    all_results = []
    
    # 1. Wiki 索引搜索
    if wiki_path:
        wiki_results = query_wiki(query, wiki_path, top_k)
        all_results.extend(wiki_results)
    
    # 2. 缓存搜索
    if cache_dir:
        cache_results = query_cache(query, cache_dir, top_k)
        all_results.extend(cache_results)
    
    # 3. 知识图谱搜索
    if graph_data:
        graph_results = query_knowledge_graph(query, graph_data, top_k)
        all_results.extend(graph_results)
    
    # 4. Markdown 文档搜索
    docs_results = search_markdown_docs(query, top_k=top_k)
    all_results.extend(docs_results)
    
    # 去重并排序
    seen = set()
    unique = []
    for r in all_results:
        key = (r.get('type'), r.get('name', r.get('path', '')))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    
    unique.sort(key=lambda x: x['score'], reverse=True)
    return unique[:top_k]
