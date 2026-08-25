#!/usr/bin/env python3
"""
LLM Wiki — 智能知识库系统

职责：
  - 自动从代码仓库提取知识
  - 构建知识图谱和向量索引
  - RAG 检索增强生成
  - 多语言支持（Go/Python/Java）

架构：
  Layer 1: CodeScanner — 代码解析器
  Layer 2: KnowledgeExtractor — 知识提取器
  Layer 3: VectorIndex — 向量索引（TF-IDF）
  Layer 4: KnowledgeGraph — 知识图谱
  Layer 5: RAGEngine — 检索增强生成引擎

设计原则：
  - 纯 Python 实现，无外部依赖
  - 增量更新机制
  - 支持多仓库知识融合
  - 可扩展的插件架构
"""

import json
import hashlib
import math
import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import collections


# ──────────────────────────────────────────────
# Layer 1: Code Scanner
# ──────────────────────────────────────────────

@dataclass
class CodeElement:
    """代码元素"""
    name: str
    type: str  # "class", "function", "interface", "struct", "module"
    file_path: str
    line_start: int
    line_end: int
    signature: str
    docstring: str = ""
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


class CodeScanner:
    """代码扫描器 — 解析源代码提取结构化信息"""
    
    LANGUAGE_PATTERNS = {
        "python": {
            "class": re.compile(r'^class\s+(\w+)'),
            "function": re.compile(r'^def\s+(\w+)\s*\('),
            "import": re.compile(r'^(?:import|from)\s+([\w.]+)'),
            "docstring": re.compile(r'"""(.*?)"""', re.DOTALL),
        },
        "go": {
            "class": re.compile(r'^type\s+(\w+)\s+struct'),
            "function": re.compile(r'^func\s+(\w+)\s*\('),
            "interface": re.compile(r'^type\s+(\w+)\s+interface'),
            "import": re.compile(r'"([^"]+)"'),
            "docstring": re.compile(r'//[^\n]*'),
        },
        "java": {
            "class": re.compile(r'(?:public|private|protected)?\s*class\s+(\w+)'),
            "function": re.compile(r'(?:public|private|protected)?\s*\w+\s+(\w+)\s*\('),
            "interface": re.compile(r'interface\s+(\w+)'),
            "import": re.compile(r'import\s+([\w.]+);'),
        },
    }
    
    def __init__(self, repo_path: str, language: str = "go"):
        self.repo_path = Path(repo_path)
        self.language = language
        self.elements: List[CodeElement] = []
        self.imports: Dict[str, List[str]] = {}  # module -> [imports]
        self.dependencies: Dict[str, List[str]] = {}  # module -> [depends]
    
    def scan(self, max_files: int = 1000) -> Dict[str, Any]:
        """扫描代码库"""
        self.elements = []
        extensions = {
            "python": [".py"],
            "go": [".go"],
            "java": [".java"],
        }.get(self.language, [".go", ".py", ".java"])
        
        files = list(self.repo_path.rglob("*"))
        code_files = [f for f in files if f.suffix in extensions][:max_files]
        
        for file_path in code_files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                self._parse_file(file_path, content)
            except Exception as e:
                continue
        
        return {
            "total_elements": len(self.elements),
            "total_files": len(code_files),
            "elements": [e.to_dict() for e in self.elements[:100]],  # 限制返回数量
            "imports": self.imports,
            "dependencies": self.dependencies,
        }
    
    def _parse_file(self, file_path: Path, content: str):
        """解析单个文件"""
        lines = content.split('\n')
        module_name = str(file_path.relative_to(self.repo_path))
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 提取类定义
            if self.language == "python" and self.LANGUAGE_PATTERNS["python"]["class"].match(stripped):
                match = self.LANGUAGE_PATTERNS["python"]["class"].match(stripped)
                if match:
                    self.elements.append(CodeElement(
                        name=match.group(1),
                        type="class",
                        file_path=str(file_path),
                        line_start=i+1,
                        line_end=self._find_block_end(lines, i),
                        signature=stripped,
                        dependencies=self._extract_dependencies(content),
                    ))
            
            # 提取函数定义
            elif self.language == "python" and self.LANGUAGE_PATTERNS["python"]["function"].match(stripped):
                match = self.LANGUAGE_PATTERNS["python"]["function"].match(stripped)
                if match:
                    self.elements.append(CodeElement(
                        name=match.group(1),
                        type="function",
                        file_path=str(file_path),
                        line_start=i+1,
                        line_end=self._find_block_end(lines, i),
                        signature=stripped,
                    ))
            
            # 提取 import
            elif self.LANGUAGE_PATTERNS[self.language]["import"].search(stripped):
                matches = self.LANGUAGE_PATTERNS[self.language]["import"].findall(stripped)
                if module_name not in self.imports:
                    self.imports[module_name] = []
                self.imports[module_name].extend(matches)
    
    def _find_block_end(self, lines: List[str], start: int) -> int:
        """查找代码块结束行"""
        if start >= len(lines):
            return start + 1
        indent = len(lines[start]) - len(lines[start].lstrip())
        for i in range(start + 1, min(start + 50, len(lines))):
            line = lines[i]
            if line.strip() and len(line) - len(line.lstrip()) <= indent:
                return i
        return start + 10
    
    def _extract_dependencies(self, content: str) -> List[str]:
        """提取依赖"""
        deps = []
        for match in self.LANGUAGE_PATTERNS[self.language]["import"].findall(content):
            deps.append(match)
        return deps[:5]  # 限制依赖数量


# ──────────────────────────────────────────────
# Layer 2: Knowledge Extractor
# ──────────────────────────────────────────────

@dataclass
class KnowledgeEntry:
    """知识条目"""
    id: str
    type: str  # "function", "class", "module", "concept"
    title: str
    content: str
    source_file: str
    source_line: int
    tags: List[str] = field(default_factory=list)
    embedding: List[float] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d.pop('embedding', None)  # 不序列化 embedding
        return d


class KnowledgeExtractor:
    """知识提取器 — 将代码元素转化为知识条目"""
    
    def __init__(self, repo_path: str, language: str = "go"):
        self.scanner = CodeScanner(repo_path, language)
        self.entries: List[KnowledgeEntry] = []
    
    def extract(self) -> List[KnowledgeEntry]:
        """提取知识"""
        scan_result = self.scanner.scan()
        
        for elem_data in scan_result.get("elements", []):
            entry = self._create_entry(elem_data, scan_result)
            if entry:
                self.entries.append(entry)
        
        return self.entries
    
    def _create_entry(self, elem: Dict, scan_result: Dict) -> Optional[KnowledgeEntry]:
        """创建知识条目"""
        # 生成唯一 ID
        content_hash = hashlib.md5(
            f"{elem['type']}:{elem['name']}:{elem['file_path']}".encode()
        ).hexdigest()[:8]
        
        # 构建内容
        content = self._build_content(elem, scan_result)
        
        # 提取标签
        tags = self._extract_tags(elem)
        
        return KnowledgeEntry(
            id=f"know_{content_hash}",
            type=elem.get("type", "unknown"),
            title=f"{elem.get('type', '').title()}: {elem.get('name', '')}",
            content=content,
            source_file=elem.get("file_path", ""),
            source_line=elem.get("line_start", 0),
            tags=tags,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
    
    def _build_content(self, elem: Dict, scan_result: Dict) -> str:
        """构建知识内容"""
        lines = []
        lines.append(f"【类型】{elem.get('type', 'unknown')}")
        lines.append(f"【名称】{elem.get('name', '')}")
        lines.append(f"【签名】{elem.get('signature', '')}")
        lines.append(f"【文件】{elem.get('file_path', '')}")
        lines.append(f"【行号】{elem.get('line_start', 0)}-{elem.get('line_end', 0)}")
        
        if elem.get("dependencies"):
            lines.append(f"【依赖】{', '.join(elem['dependencies'])}")
        
        return "\n".join(lines)
    
    def _extract_tags(self, elem: Dict) -> List[str]:
        """提取标签"""
        tags = []
        name = elem.get("name", "").lower()
        
        # 基于名称提取标签
        if "api" in name or "handler" in name or "controller" in name:
            tags.append("api")
        if "model" in name or "entity" in name or "dto" in name:
            tags.append("data_model")
        if "service" in name or "manager" in name:
            tags.append("service")
        if "test" in name or "spec" in name:
            tags.append("test")
        if "utils" in name or "helper" in name or "tool" in name:
            tags.append("utility")
        
        return tags[:5]


# ──────────────────────────────────────────────
# Layer 3: Vector Index (TF-IDF)
# ──────────────────────────────────────────────

class VectorIndex:
    """TF-IDF 向量索引"""
    
    def __init__(self):
        self.documents: Dict[str, str] = {}  # id -> content
        self.term_freq: Dict[str, Dict[str, int]] = {}  # doc_id -> {term: count}
        self.document_freq: Dict[str, int] = {}  # term -> doc_count
        self.total_docs = 0
    
    def add_document(self, doc_id: str, content: str):
        """添加文档到索引"""
        self.documents[doc_id] = content
        self.term_freq[doc_id] = self._tokenize_and_count(content)
        self.total_docs += 1
        
        # 更新 document frequency
        for term in self.term_freq[doc_id]:
            if term not in self.document_freq:
                self.document_freq[term] = 0
            self.document_freq[term] += 1
    
    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        # 简单分词：提取英文单词和中文词组
        words = re.findall(r'[a-zA-Z]+|[\u4e00-\u9fff]{2,}', text.lower())
        return words
    
    def _tokenize_and_count(self, text: str) -> Dict[str, int]:
        """分词并统计词频"""
        words = self._tokenize(text)
        return collections.Counter(words)
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """搜索文档，返回 (doc_id, score) 列表"""
        query_terms = set(self._tokenize(query))
        if not query_terms:
            return []
        
        scores = {}
        n_docs = self.total_docs
        
        for doc_id, term_counts in self.term_freq.items():
            score = 0.0
            for term in query_terms:
                if term in term_counts:
                    # TF-IDF 计算
                    tf = term_counts[term] / max(1, sum(term_counts.values()))
                    idf = math.log((1 + n_docs) / (1 + self.document_freq.get(term, 0))) + 1
                    score += tf * idf
            
            if score > 0:
                scores[doc_id] = score
        
        # 按分数排序
        sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
        return sorted_scores[:top_k]
    
    def get_document(self, doc_id: str) -> Optional[str]:
        """获取文档内容"""
        return self.documents.get(doc_id)


# ──────────────────────────────────────────────
# Layer 4: Knowledge Graph
# ──────────────────────────────────────────────

@dataclass
class GraphNode:
    """图节点"""
    id: str
    label: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """图边"""
    source: str
    target: str
    relation: str
    weight: float = 1.0


class KnowledgeGraph:
    """知识图谱"""
    
    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
    
    def add_node(self, node: GraphNode):
        """添加节点"""
        self.nodes[node.id] = node
    
    def add_edge(self, edge: GraphEdge):
        """添加边"""
        self.edges.append(edge)
    
    def find_connections(self, node_id: str, depth: int = 2) -> Dict[str, Any]:
        """查找节点连接"""
        connections = {node_id: {"depth": 0}}
        current_layer = {node_id}
        
        for d in range(1, depth + 1):
            next_layer = set()
            for node_id in current_layer:
                for edge in self.edges:
                    if edge.source == node_id and edge.target not in connections:
                        connections[edge.target] = {"depth": d, "relation": edge.relation}
                        next_layer.add(edge.target)
                    elif edge.target == node_id and edge.source not in connections:
                        connections[edge.source] = {"depth": d, "relation": edge.relation}
                        next_layer.add(edge.source)
            current_layer = next_layer
        
        return connections
    
    def get_related_nodes(self, node_id: str) -> List[Dict]:
        """获取相关节点"""
        related = []
        for edge in self.edges:
            if edge.source == node_id:
                target = self.nodes.get(edge.target)
                if target:
                    related.append({
                        "id": edge.target,
                        "label": target.label,
                        "type": target.type,
                        "relation": edge.relation,
                    })
            elif edge.target == node_id:
                source = self.nodes.get(edge.source)
                if source:
                    related.append({
                        "id": edge.source,
                        "label": source.label,
                        "type": source.type,
                        "relation": f"related_to_{edge.relation}",
                    })
        return related


# ──────────────────────────────────────────────
# Layer 5: RAG Engine
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
        self.wiki_path = Path(wiki_path) if wiki_path else Path("/tmp/biz-delivery/wiki")
        self.index = VectorIndex()
        self.graph = KnowledgeGraph()
        self.entries: List[KnowledgeEntry] = []
        self._load_wiki()
    
    def _load_wiki(self):
        """加载知识库"""
        index_file = self.wiki_path / "index.json"
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text())
                self.entries = [KnowledgeEntry(**e) for e in data.get("entries", [])]
                for entry in self.entries:
                    self.index.add_document(entry.id, entry.content)
            except Exception as e:
                print(f"Failed to load wiki: {e}")
    
    def build_from_repo(self, repo_path: str, language: str = "go"):
        """从仓库构建知识库"""
        extractor = KnowledgeExtractor(repo_path, language)
        self.entries = extractor.extract()
        
        # 添加到向量索引
        for entry in self.entries:
            self.index.add_document(entry.id, entry.content)
            # 添加到知识图谱
            self.graph.add_node(GraphNode(
                id=entry.id,
                label=entry.title,
                type=entry.type,
                properties={"source": entry.source_file},
            ))
        
        # 保存知识库
        self._save_wiki()
        
        return {
            "total_entries": len(self.entries),
            "total_files": len(set(e.source_file for e in self.entries)),
        }
    
    def _save_wiki(self):
        """保存知识库"""
        self.wiki_path.mkdir(parents=True, exist_ok=True)
        data = {
            "entries": [e.to_dict() for e in self.entries],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        (self.wiki_path / "index.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2)
        )
    
    def query(self, question: str, top_k: int = 5) -> Dict:
        """查询知识库"""
        # 检索相关文档
        search_results = self.index.search(question, top_k=top_k)
        
        # 构建上下文
        context_parts = []
        for doc_id, score in search_results:
            doc = self.index.get_document(doc_id)
            entry = next((e for e in self.entries if e.id == doc_id), None)
            if doc and entry:
                context_parts.append(f"[{score:.2f}] {entry.title}\n{doc}")
        
        context = "\n\n".join(context_parts) if context_parts else "无相关知识点"
        
        return {
            "question": question,
            "context": context,
            "results": [
                {"id": doc_id, "score": round(score, 4)}
                for doc_id, score in search_results
            ],
            "rag_prompt": self.RETRIEVAL_PROMPT.format(
                context=context,
                question=question,
            ),
        }
    
    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """获取实体详情"""
        for entry in self.entries:
            if entry.id == entity_id:
                related = self.graph.find_connections(entity_id, depth=1)
                return {
                    **entry.to_dict(),
                    "related_entities": list(related.keys())[1:],  # 排除自己
                }
        return None
    
    def stats(self) -> Dict:
        """获取知识库统计"""
        return {
            "total_entries": len(self.entries),
            "total_nodes": len(self.graph.nodes),
            "total_edges": len(self.graph.edges),
            "index_size": self.index.total_docs,
        }


# ──────────────────────────────────────────────
# 用法示例
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="LLM Wiki 知识库构建工具")
    parser.add_argument("--repo", required=True, help="代码仓库路径")
    parser.add_argument("--lang", default="go", choices=["go", "python", "java"])
    parser.add_argument("--output", default="/tmp/biz-delivery/wiki")
    args = parser.parse_args()
    
    # 构建知识库
    rag = RAGEngine(args.output)
    result = rag.build_from_repo(args.repo, args.lang)
    
    print(f"✅ 知识库构建完成")
    print(f"   - 知识条目: {result['total_entries']}")
    print(f"   - 源文件数: {result['total_files']}")
    print(f"   - 存储路径: {args.output}")
    
    # 测试查询
    print("\n🔍 测试查询:")
    test_queries = ["API", "handler", "接口"]
    for q in test_queries:
        result = rag.query(q)
        print(f"  '{q}': 找到 {len(result['results'])} 条结果")
    
    print(f"\n📊 统计: {json.dumps(rag.stats(), indent=2, ensure_ascii=False)}")
