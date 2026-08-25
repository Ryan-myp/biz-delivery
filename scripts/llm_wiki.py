#!/usr/bin/env python3
"""
LLM Wiki — Karpathy 风格知识库系统

核心设计（来自 Andrej Karpathy 的 Gist）:
  - Markdown 文件存储（不是 JSON）
  - index.md 作为导航目录
  - log.md 记录操作历史
  - [[双向链接]] 关联知识页
  - LLM 增量维护（更新已有页面）

架构:
  Layer 1: MarkdownStore — Markdown 文件存储
  Layer 2: KnowledgeGraph — 知识图谱（双向链接）
  Layer 3: RAGEngine — 检索增强生成引擎
"""

import json
import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import Counter


# ──────────────────────────────────────────────
# Layer 1: Markdown Storage
# ──────────────────────────────────────────────

class MarkdownStore:
    """Markdown 文件存储 — 替代 JSON 存储"""
    
    # 目录结构
    WIKI_DIR = Path("/tmp/biz-delivery/wiki")
    ENTITIES_DIR = WIKI_DIR / "entities"
    CONCEPTS_DIR = WIKI_DIR / "concepts"
    SOURCES_DIR = WIKI_DIR / "sources"
    INDEX_FILE = WIKI_DIR / "index.md"
    LOG_FILE = WIKI_DIR / "log.md"
    
    def __init__(self):
        self._init_dirs()
    
    def _init_dirs(self):
        """初始化目录结构"""
        for d in [self.WIKI_DIR, self.ENTITIES_DIR, self.CONCEPTS_DIR, self.SOURCES_DIR]:
            d.mkdir(parents=True, exist_ok=True)
        
        # 初始化 index.md
        if not self.INDEX_FILE.exists():
            self.INDEX_FILE.write_text("# LLM Wiki\n\n## 实体\n\n## 概念\n\n## 来源\n", encoding="utf-8")
        
        # 初始化 log.md
        if not self.LOG_FILE.exists():
            self.LOG_FILE.write_text("# Wiki Log\n\n> 知识库操作日志\n\n", encoding="utf-8")
    
    def save_entity(self, entity_id: str, title: str, content: str, tags: List[str] = None):
        """保存实体页面"""
        page = self._build_markdown_page(entity_id, title, content, tags)
        page_path = self.ENTITIES_DIR / f"{entity_id}.md"
        page_path.write_text(page, encoding="utf-8")
        
        # 更新 index.md
        self._update_index()
        
        # 记录日志
        self._log("ingest", entity_id, title)
        
        return str(page_path)
    
    def save_concept(self, concept_id: str, title: str, content: str, tags: List[str] = None):
        """保存概念页面"""
        page = self._build_markdown_page(concept_id, title, content, tags)
        page_path = self.CONCEPTS_DIR / f"{concept_id}.md"
        page_path.write_text(page, encoding="utf-8")
        
        self._update_index()
        self._log("ingest", concept_id, title)
        
        return str(page_path)
    
    def save_source(self, source_id: str, title: str, content: str, source_file: str = "", tags: List[str] = None):
        """保存来源页面"""
        tags_str = "\n".join(f"- #{tag}" for tag in (tags or []))
        page = f"""# {title}

{tags_str}

> 来源: {source_file}

---

{content}

---

*创建于 {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
        page_path = self.SOURCES_DIR / f"{source_id}.md"
        page_path.write_text(page, encoding="utf-8")
        
        self._log("source", source_id, title)
        
        return str(page_path)
    
    def _build_markdown_page(self, entity_id: str, title: str, content: str, tags: List[str] = None) -> str:
        """构建 Markdown 页面"""
        tags_str = "\n".join(f"- #{tag}" for tag in (tags or []))
        
        return f"""# {title}

{tags_str}

---

{content}

---

*创建于 {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
    
    def _update_index(self):
        """更新 index.md"""
        index_content = "# LLM Wiki\n\n"
        
        # 实体索引
        index_content += "## 实体\n\n"
        for f in sorted(self.ENTITIES_DIR.glob("*.md")):
            name = f.stem
            title = self._extract_title(f.read_text(encoding="utf-8"))
            index_content += f"- [[{name}]] - {title}\n"
        
        index_content += "\n## 概念\n\n"
        for f in sorted(self.CONCEPTS_DIR.glob("*.md")):
            name = f.stem
            title = self._extract_title(f.read_text(encoding="utf-8"))
            index_content += f"- [[{name}]] - {title}\n"
        
        index_content += "\n## 来源\n\n"
        for f in sorted(self.SOURCES_DIR.glob("*.md")):
            name = f.stem
            title = self._extract_title(f.read_text(encoding="utf-8"))
            index_content += f"- [[{name}]] - {title}\n"
        
        self.INDEX_FILE.write_text(index_content, encoding="utf-8")
    
    def _extract_title(self, content: str) -> str:
        """从 Markdown 内容提取标题"""
        match = re.search(r'^# (.+)$', content, re.MULTILINE)
        return match.group(1) if match else "Untitled"
    
    def _log(self, action: str, entity_id: str, title: str):
        """记录操作日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        log_entry = f"## [{timestamp}] {action} | {title}\n\n- ID: {entity_id}\n\n"
        
        with open(self.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    
    def get_page(self, entity_id: str) -> Optional[str]:
        """获取页面内容"""
        for d in [self.ENTITIES_DIR, self.CONCEPTS_DIR, self.SOURCES_DIR]:
            page = d / f"{entity_id}.md"
            if page.exists():
                return page.read_text(encoding="utf-8")
        return None
    
    def get_all_pages(self) -> List[Dict]:
        """获取所有页面"""
        pages = []
        for d in [self.ENTITIES_DIR, self.CONCEPTS_DIR, self.SOURCES_DIR]:
            for f in d.glob("*.md"):
                content = f.read_text(encoding="utf-8")
                title = self._extract_title(content)
                pages.append({
                    "id": f.stem,
                    "type": d.name,
                    "title": title,
                    "path": str(f),
                    "content": content
                })
        return pages
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """简单关键词搜索"""
        query_terms = set(query.lower().split())
        scores = {}
        
        for page in self.get_all_pages():
            content = page["content"].lower()
            score = sum(1 for term in query_terms if term in content)
            if score > 0:
                scores[page["id"]] = score
        
        return sorted(scores.items(), key=lambda x: -x[1])[:top_k]
    
    def find_links(self, entity_id: str) -> List[str]:
        """查找链接到此页面的其他页面"""
        linked = []
        for page in self.get_all_pages():
            if page["id"] != entity_id:
                content = page["content"]
                if f"[[{entity_id}]]" in content:
                    linked.append(page["id"])
        return linked


# ──────────────────────────────────────────────
# Layer 2: Knowledge Graph
# ──────────────────────────────────────────────

class KnowledgeGraph:
    """知识图谱 — 管理 [[双向链接]]"""
    
    def __init__(self, store: MarkdownStore):
        self.store = store
        self.links: Dict[str, List[str]] = {}  # id -> [linked_ids]
        self._build_graph()
    
    def _build_graph(self):
        """从所有页面构建链接图"""
        pages = self.store.get_all_pages()
        
        for page in pages:
            links = re.findall(r'\[\[(\w+)\]\]', page["content"])
            self.links[page["id"]] = links
    
    def get_connections(self, entity_id: str, depth: int = 2) -> Dict[str, int]:
        """查找连接节点"""
        connected = {entity_id: 0}
        current = {entity_id}
        
        for d in range(1, depth + 1):
            next_layer = set()
            for node in current:
                for link in self.links.get(node, []):
                    if link not in connected:
                        connected[link] = d
                        next_layer.add(link)
            current = next_layer
        
        return connected
    
    def get_related(self, entity_id: str) -> List[Dict]:
        """获取相关页面"""
        related = []
        for link_id in self.links.get(entity_id, []):
            page = self.store.get_page(link_id)
            if page:
                title = self.store._extract_title(page)
                related.append({"id": link_id, "title": title})
        return related


# ──────────────────────────────────────────────
# Layer 3: RAG Engine
# ──────────────────────────────────────────────

class RAGEngine:
    """检索增强生成引擎"""
    
    RETRIEVAL_PROMPT = """你是一位技术专家，请基于以下知识库内容回答用户问题。

【知识库内容】
{context}

【用户问题】
{question}

请提供准确、简洁的回答，并在回答中标注引用的知识来源。"""
    
    def __init__(self, wiki_path: str = None):
        self.store = MarkdownStore()
        self.graph = KnowledgeGraph(self.store)
    
    def stats(self) -> Dict:
        """获取统计"""
        pages = self.store.get_all_pages()
        return {
            "total_entries": len([p for p in pages if p["type"] == "entities"]),
            "total_concepts": len([p for p in pages if p["type"] == "concepts"]),
            "total_sources": len([p for p in pages if p["type"] == "sources"]),
            "total_pages": len(pages),
        }
    
    def build_from_repo(self, repo_path: str, language: str = "python") -> Dict:
        """从仓库构建知识库（扩展点）"""
        # TODO: 实现代码扫描和知识提取
        return {"total_entries": 0, "status": "not implemented"}
    
    def ingest_document(self, doc_id: str, title: str, content: str, 
                        doc_type: str = "source", tags: List[str] = None) -> Dict:
        """导入文档到知识库"""
        if doc_type == "source":
            path = self.store.save_source(doc_id, title, content, tags=tags or [])
            entry_type = "sources"
        elif doc_type == "concept":
            path = self.store.save_concept(doc_id, title, content, tags=tags or [])
            entry_type = "concepts"
        else:
            path = self.store.save_entity(doc_id, title, content, tags=tags or [])
            entry_type = "entities"
        
        # 更新图
        self.graph._build_graph()
        
        return {
            "success": True,
            "id": doc_id,
            "type": doc_type,
            "path": path
        }
    
    def query(self, question: str, top_k: int = 5) -> Dict:
        """查询知识库"""
        # 搜索
        search_results = self.store.search(question, top_k=top_k)
        
        # 构建上下文
        context_parts = []
        for doc_id, score in search_results:
            doc = self.store.get_page(doc_id)
            title = self.store._extract_title(doc) if doc else doc_id
            context_parts.append(f"[{score}] {title}\n{doc}")
        
        context = "\n\n---\n\n".join(context_parts) if context_parts else "无相关知识点"
        
        return {
            "question": question,
            "context": context,
            "results": [{"id": doc_id, "score": score} for doc_id, score in search_results],
            "rag_prompt": self.RETRIEVAL_PROMPT.format(context=context, question=question)
        }
    
    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """获取实体详情"""
        content = self.store.get_page(entity_id)
        if not content:
            return None
        
        title = self.store._extract_title(content)
        related = self.graph.get_connections(entity_id, depth=1)
        
        return {
            "id": entity_id,
            "title": title,
            "content": content,
            "related_entities": [k for k, v in related.items() if v > 0][:5]
        }
    
    def list_entities(self) -> List[Dict]:
        """列出所有实体"""
        return self.store.get_all_pages()


# ──────────────────────────────────────────────
# 用法示例
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="LLM Wiki 知识库工具")
    parser.add_argument("--action", choices=["build", "query", "list", "stats"], required=True)
    parser.add_argument("--repo", help="代码仓库路径（build 模式）")
    parser.add_argument("--lang", default="python", choices=["python", "go", "java"])
    parser.add_argument("--query", help="查询问题（query 模式）")
    args = parser.parse_args()
    
    rag = RAGEngine()
    
    if args.action == "stats":
        print(f"📊 知识库统计: {json.dumps(rag.stats(), indent=2)}")
    
    elif args.action == "query" and args.query:
        result = rag.query(args.query)
        print(f"🔍 查询: {args.query}")
        print(f"找到 {len(result['results'])} 条结果")
        for r in result['results']:
            print(f"  - {r['id']} (score: {r['score']})")
    
    elif args.action == "list":
        pages = rag.list_entities()
        print(f"📚 共 {len(pages)} 个页面")
        for p in pages[:10]:
            print(f"  [{p['type']}] {p['title']}")
    
    elif args.action == "build" and args.repo:
        result = rag.build_from_repo(args.repo, args.lang)
        print(f"✅ 构建完成: {result}")
