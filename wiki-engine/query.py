#!/usr/bin/env python3
"""
LLM Wiki — Query 流程 (biz-delivery thin wrapper)
问题 → 读 index.md → 定位相关页面 → 读页面内容 → 综合回答 → 归档有价值的回答

复用 biz-delivery 的 smart_routing (意图识别) + query_cache (缓存)
参考：Karpathy LLM Wiki 模式
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
"""

import re
import json
import time
import hashlib
import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

try:
    from .ingest import (
        WikiContext, WikiPage, read_file, write_file, extract_frontmatter,
        extract_body, extract_tags, extract_wikilinks, extract_headings,
        extract_key_concepts, find_relevant_pages, create_page, build_frontmatter,
        FRONTMATTER_RE
    )
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from ingest import (
        WikiContext, WikiPage, read_file, write_file, extract_frontmatter,
        extract_body, extract_tags, extract_wikilinks, extract_headings,
        extract_key_concepts, find_relevant_pages, create_page, build_frontmatter,
        FRONTMATTER_RE
    )

# ──────────────────────────────────────────────
# Import biz-delivery core
# ──────────────────────────────────────────────

_BD_SCRIPTS = Path(__file__).parents[1] / "scripts"
if str(_BD_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_BD_SCRIPTS.parent))

try:
    from scripts.smart_routing import extract_intent as _bd_extract_intent
    _HAS_BD = True
except ImportError:
    _HAS_BD = False

    # Fallback: inline minimal intent extraction
    def _bd_extract_intent(query: str) -> Tuple[str, float]:
        patterns = {
            "query": ["查询", "查看", "获取", "查找", "检索", "query", "search"],
            "question": ["什么", "如何", "怎么", "为什么", "what", "how", "why"],
            "explain": ["解释", "说明", "原理", "explain"],
            "compare": ["对比", "比较", "区别", "compare", "diff"],
            "debug": ["排障", "错误", "问题", "bug", "error"],
        }
        q = query.lower()
        scores = {}
        for intent, pats in patterns.items():
            s = sum(1 for p in pats if p.lower() in q)
            if s > 0:
                scores[intent] = min(s / len(pats), 1.0)
        if not scores:
            return ("unknown", 0.0)
        return max(scores, key=scores.get), scores[max(scores, key=scores.get)]


# ──────────────────────────────────────────────
# 1. Wiki 搜索 — 多层融合
# ──────────────────────────────────────────────

def search_index(query: str, wiki: WikiContext, top_k: int = 10) -> List[Path]:
    """通过 index.md 搜索相关页面"""
    scored = []
    query_lower = query.lower()
    query_words = set(re.findall(r'[\w\u4e00-\u9fff]+', query_lower))

    index_path = wiki.wiki_root / 'index.md'
    index_content = read_file(index_path) or ''

    for line in index_content.split('\n'):
        line = line.strip()
        m = re.match(r'- \[\[([^\]]+)\]\]\s*—\s*(.*)', line)
        if m:
            title = m.group(1)
            summary = m.group(2)
            title_lower = title.lower()
            hits = sum(1 for w in query_words if w in title_lower or w in summary)
            if hits > 0:
                score = hits / max(len(query_words), 1)
                scored.append((score, title))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for _, title in scored[:top_k]:
        for path, page in wiki.pages.items():
            if page.title.lower() == title.lower():
                results.append(path)
                break

    return results


def search_pages_by_content(query: str, wiki: WikiContext, top_k: int = 10) -> List[Path]:
    """通过页面内容搜索"""
    scored = []
    query_lower = query.lower()
    query_words = set(re.findall(r'[\w\u4e00-\u9fff]+', query_lower))

    for path, page in wiki.pages.items():
        search_text = f"{page.title} {' '.join(page.tags)} {' '.join(page.headings)} {page.body}".lower()
        hits = sum(1 for w in query_words if w in search_text)
        if hits > 0:
            score = hits / max(len(query_words), 1)
            type_bonus = 1.3 if page.page_type in ('entity', 'concept') else 1.0
            scored.append((score * type_bonus, path))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:top_k]]


def search_pages_by_wikilinks(query: str, wiki: WikiContext, top_k: int = 10) -> List[Path]:
    """通过 wikilinks 搜索"""
    scored = []
    query_lower = query.lower()
    query_words = set(re.findall(r'[\w\u4e00-\u9fff]+', query_lower))

    for path, page in wiki.pages.items():
        link_hits = sum(1 for link in page.wikilinks
                       if any(w in link.lower() for w in query_words))
        if link_hits > 0:
            score = link_hits / max(len(query_words), 1) * 1.5
            scored.append((score, path))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:top_k]]


def wiki_search(query: str, wiki: WikiContext, top_k: int = 10,
                cache: Optional[Any] = None, intent: str = "unknown",
                confidence: float = 0.0) -> Dict[str, Any]:
    """
    多路 wiki 搜索 — 融合 index.md + 内容 + wikilinks
    返回排序后的页面列表和详细信息
    """
    params = f"k={top_k}:intent={intent}:conf={confidence:.2f}"
    
    # 检查缓存
    if cache:
        cached = cache.get(query, ["wiki"])
        if cached and "results" in cached:
            cached["retrieved_from"] = "cache"
            return cached

    # 三路搜索
    index_results = search_index(query, wiki, top_k)
    content_results = search_pages_by_content(query, wiki, top_k)
    wikilink_results = search_pages_by_wikilinks(query, wiki, top_k)

    # RRF 融合
    all_paths = set(index_results + content_results + wikilink_results)
    scored = {}

    for i, path in enumerate(index_results):
        scored[path] = scored.get(path, 0) + 1.0 / (60 + i + 1)
    for i, path in enumerate(content_results):
        scored[path] = scored.get(path, 0) + 1.0 / (60 + i + 1)
    for i, path in enumerate(wikilink_results):
        scored[path] = scored.get(path, 0) + 1.5 / (60 + i + 1)

    scored_sorted = sorted(scored.items(), key=lambda x: x[1], reverse=True)[:top_k]

    results = []
    for path, rrf_score in scored_sorted:
        page = wiki.pages[path]
        results.append({
            'path': str(path.relative_to(wiki.wiki_root.parent)),
            'title': page.title,
            'type': page.page_type,
            'tags': page.tags,
            'wikilinks': page.wikilinks,
            'rrf_score': round(rrf_score, 6),
            'headings': page.headings[:5],
        })

    result = {
        'query': query,
        'results': results,
        'total': len(results),
        'sources': {
            'index': len(index_results),
            'content': len(content_results),
            'wikilinks': len(wikilink_results),
        }
    }

    if cache:
        cache.set(query, ["wiki"], result)

    return result


# ──────────────────────────────────────────────
# 2. Wiki 问答
# ──────────────────────────────────────────────

def synthesize_answer(query: str, search_result: Dict[str, Any], wiki: WikiContext) -> str:
    """
    基于搜索结果综合生成回答
    在实际 LLM Wiki 中，这一步由 LLM 完成
    这里我们返回结构化的信息
    """
    lines = [f'### 搜索查询: "{query}"\n']
    lines.append(f'找到 {search_result["total"]} 个相关页面\n')

    lines.append('#### 搜索结果\n')
    for i, r in enumerate(search_result['results'], 1):
        lines.append(f'**{i}. [{r["title"]}]({r["path"]})** (`{r["type"]}`)\n')
        lines.append(f'Tags: {", ".join(r["tags"])}\n')
        if r['headings']:
            lines.append(f'Headings: {" | ".join(r["headings"][:3])}\n')
        lines.append('\n')

    if search_result['results']:
        linked_pages = set()
        for r in search_result['results']:
            linked_pages.update(r['wikilinks'])
        if linked_pages:
            lines.append(f'\n#### 关联页面\n')
            for link in list(linked_pages)[:5]:
                lines.append(f'- [[{link}]]\n')

    return '\n'.join(lines)


def archive_query_result(wiki: WikiContext, question: str, answer: str) -> Optional[Path]:
    """归档有价值的问答"""
    today = wiki.log_entries[-1][:10] if wiki.log_entries else "N/A"
    tags = extract_tags(answer)
    fm = {
        'title': question[:50],
        'created': today,
        'updated': today,
        'type': 'query',
        'tags': tags if tags else ['问答'],
    }

    content = build_frontmatter(fm) + f'\n\n**问题**: {question}\n\n**回答**:\n\n{answer}'

    safe_q = question.lower().replace(' ', '-').replace('/', '-')[:40]
    path = wiki.wiki_root / 'queries' / f'{safe_q}.md'
    write_file(path, content)

    return path


# ──────────────────────────────────────────────
# 3. Query 流程入口
# ──────────────────────────────────────────────

def query(wiki_path: str, question: str, archive: bool = False) -> Dict[str, Any]:
    """
    执行 wiki query：
    1. 加载 wiki
    2. 多路搜索
    3. 综合回答
    4. （可选）归档结果
    """
    wiki = WikiContext(Path(wiki_path))
    wiki.load_all()

    # 意图识别
    if _HAS_BD:
        intent, confidence = _bd_extract_intent(question)
    else:
        intent, confidence = _bd_extract_intent(question)

    search_result = wiki_search(question, wiki, top_k=10, intent=intent, confidence=confidence)

    # 综合
    answer = synthesize_answer(question, search_result, wiki)

    # 归档（如果结果有价值）
    archived_path = None
    if archive and search_result['total'] > 0:
        archived_path = archive_query_result(wiki, question, answer)
        wiki.update_index()
        wiki.append_log('query', question,
                       [str(archived_path.relative_to(wiki.wiki_root.parent)) if archived_path else ''])

    wiki.append_log('query', question)

    result = {
        'query': question,
        'intent': intent,
        'confidence': confidence,
        'search': search_result,
        'answer': answer,
        'archived_path': str(archived_path) if archived_path else None,
        'retrieved_from': 'fresh',
    }

    return result


# ──────────────────────────────────────────────
# CLI 入口 — 带意图识别 + 缓存
# ──────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="LLM Wiki Query — biz-delivery wrapper")
    parser.add_argument("wiki_path", help="Wiki 根目录")
    parser.add_argument("question", help="查询问题")
    parser.add_argument("--archive", action="store_true", help="归档结果")
    parser.add_argument("--cache-dir", default=None, help="缓存目录")
    parser.add_argument("--clear-cache", action="store_true", help="清除缓存")

    args = parser.parse_args()

    # 缓存
    cache = None
    if args.cache_dir:
        cache_dir = Path(args.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        if args.clear_cache:
            for f in cache_dir.glob("*.json"):
                f.unlink()
            print("✅ 缓存已清除")
            sys.exit(0)

        # Try to import biz-delivery QueryCache
        try:
            from scripts.query_cache import QueryCache
            cache = QueryCache(cache_dir, ttl_seconds=3600)
        except ImportError:
            # Fallback inline cache
            class _SimpleCache:
                def __init__(self, d, ttl=3600):
                    self.d = d
                    self.ttl = ttl
                def get(self, q, scopes):
                    p = self.d / f"{hashlib.md5(f'{q}'.encode()).hexdigest()}.json"
                    if not p.exists():
                        return None
                    if time.time() - p.stat().st_mtime > self.ttl:
                        p.unlink()
                        return None
                    try:
                        return json.loads(p.read_text())
                    except Exception:
                        return None
                def set(self, q, scopes, data):
                    p = self.d / f"{hashlib.md5(f'{q}'.encode()).hexdigest()}.json"
                    data["cached_at"] = time.time()
                    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            cache = _SimpleCache(cache_dir)

    # 意图识别 + 搜索
    if _HAS_BD:
        intent, conf = _bd_extract_intent(args.question)
    else:
        intent, conf = _bd_extract_intent(args.question)
    print(f"🎯 意图: {intent} (置信度: {conf:.3f})")

    result = query(args.wiki_path, args.question, archive=args.archive)

    # 缓存最终结果
    if cache:
        cache.set(args.question, ["wiki"], result)

    print(result['answer'])
