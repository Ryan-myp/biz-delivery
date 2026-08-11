#!/usr/bin/env python3
"""
Graphify-style Code Analysis with Tree-sitter AST
基于 Graphify 的实现思路，但更简洁、更专注
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict, Counter

try:
    import tree_sitter_go as tsgo
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False

try:
    import networkx as nx
    from networkx.algorithms.community import greedy_modularity_communities
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


class GraphNode:
    def __init__(self, node_id: str, label: str, node_type: str, 
                 source_file: str = "", source_location: str = "", properties: dict = None):
        self.id = node_id
        self.label = label
        self.type = node_type
        self.source_file = source_file
        self.source_location = source_location
        self.properties = properties or {}


class GraphEdge:
    def __init__(self, source: str, target: str, relation: str,
                 confidence: str = "EXTRACTED"):
        self.source = source
        self.target = target
        self.relation = relation
        self.confidence = confidence


class CodeGraph:
    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.adjacency: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_adj: Dict[str, Set[str]] = defaultdict(set)
    
    def add_node(self, node: GraphNode):
        self.nodes[node.id] = node
    
    def add_edge(self, edge: GraphEdge):
        self.edges.append(edge)
        self.adjacency[edge.source].add(edge.target)
        self.reverse_adj[edge.target].add(edge.source)
    
    def get_degree(self, node_id: str) -> int:
        return len(self.adjacency.get(node_id, set())) + len(self.reverse_adj.get(node_id, set()))


# 预定义类型和函数（需要过滤的噪声）
_PREDEFINED_TYPES = frozenset({
    "bool", "byte", "complex64", "complex128", "error", "float32", "float64",
    "int", "int8", "int16", "int32", "int64", "rune", "string",
    "uint", "uint8", "uint16", "uint32", "uint64", "uintptr", "any",
    "append", "cap", "clear", "close", "complex", "copy", "delete", "imag",
    "len", "make", "max", "min", "new", "panic", "print", "println", "real",
    "recover", "Context", "Options", "Option", "Handler", "Callback",
})


class GoASTParser:
    """基于 tree-sitter Go AST 的解析器（参考 Graphify 实现）"""
    
    @classmethod
    def parse_file(cls, file_path: Path, content: str) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """解析 Go 文件"""
        if not HAS_TREE_SITTER:
            return [], []
        
        try:
            language = Language(tsgo.language())
            parser = Parser(language)
            source = content.encode('utf-8')
            tree = parser.parse(source)
        except Exception as e:
            print(f"  ⚠️  解析失败 {file_path.name}: {e}")
            return [], []
        
        nodes = []
        edges = []
        seen_ids = set()
        
        # 包名
        pkg_name = cls._extract_package(tree.root_node)
        pkg_scope = file_path.parent.name
        
        # 文件节点
        file_id = cls._make_id(str(file_path))
        cls._add_node(nodes, seen_ids, file_id, file_path.name, 'FILE', str(file_path), "L1")
        
        # 模块节点
        module_id = cls._make_id(pkg_scope)
        cls._add_node(nodes, seen_ids, module_id, pkg_scope, 'MODULE', str(file_path), "L1")
        edges.append(GraphEdge(file_id, module_id, 'CONTAINS', 'EXTRACTED'))
        
        # 递归遍历 AST
        cls._walk_tree(tree.root_node, file_id, module_id, pkg_scope, nodes, edges, source, seen_ids)
        
        return nodes, edges
    
    @classmethod
    def _walk_tree(cls, node, file_id: str, module_id: str, pkg_scope: str,
                   nodes: List[GraphNode], edges: List[GraphEdge],
                   source: bytes, seen_ids: Set[str]):
        """递归遍历 AST"""
        t = node.type
        
        if t == 'function_declaration':
            cls._extract_function(node, file_id, module_id, pkg_scope, nodes, edges, source, seen_ids)
        elif t == 'method_declaration':
            cls._extract_method(node, file_id, module_id, pkg_scope, nodes, edges, source, seen_ids)
        elif t == 'type_declaration':
            cls._extract_type_declaration(node, file_id, module_id, pkg_scope, nodes, edges, source, seen_ids)
        
        # 继续递归子节点
        for child in node.children:
            cls._walk_tree(child, file_id, module_id, pkg_scope, nodes, edges, source, seen_ids)
    
    @classmethod
    def _add_node(cls, nodes: List[GraphNode], seen_ids: Set[str], 
                  node_id: str, label: str, node_type: str, source_file: str, location: str):
        """添加节点，去重"""
        if node_id not in seen_ids:
            seen_ids.add(node_id)
            nodes.append(GraphNode(node_id, label, node_type, source_file, location))
    
    @classmethod
    def _extract_function(cls, node, file_id: str, module_id: str, pkg_scope: str,
                          nodes: List[GraphNode], edges: List[GraphEdge],
                          source: bytes, seen_ids: Set[str]):
        """提取函数声明"""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return
        
        func_name = name_node.text.decode('utf-8')
        if func_name in _PREDEFINED_TYPES:
            return
        
        line = node.start_point[0] + 1
        func_id = cls._make_id(pkg_scope, func_name)
        
        cls._add_node(nodes, seen_ids, func_id, func_name, 'FUNCTION', module_id, f"L{line}")
        edges.append(GraphEdge(func_id, module_id, 'CONTAINS', 'EXTRACTED'))
    
    @classmethod
    def _extract_method(cls, node, file_id: str, module_id: str, pkg_scope: str,
                        nodes: List[GraphNode], edges: List[GraphEdge],
                        source: bytes, seen_ids: Set[str]):
        """提取方法声明"""
        receiver = node.child_by_field_name('receiver')
        receiver_type = None
        
        if receiver:
            for param in receiver.children:
                if param.type == 'parameter_declaration':
                    type_node = param.child_by_field_name('type')
                    if type_node:
                        receiver_type = type_node.text.decode('utf-8').lstrip('*').strip()
                    break
        
        name_node = node.child_by_field_name('name')
        if not name_node:
            return
        
        method_name = name_node.text.decode('utf-8')
        line = node.start_point[0] + 1
        
        if receiver_type:
            # 方法：Receiver.MethodName
            parent_id = cls._make_id(pkg_scope, receiver_type)
            cls._add_node(nodes, seen_ids, parent_id, receiver_type, 'STRUCT', module_id, f"L{line}")
            method_id = cls._make_id(parent_id, method_name)
            cls._add_node(nodes, seen_ids, method_id, f".{method_name}()", 'METHOD', module_id, f"L{line}")
            edges.append(GraphEdge(method_id, parent_id, 'IMPLEMENTS', 'EXTRACTED'))
        else:
            # 独立函数
            func_id = cls._make_id(pkg_scope, method_name)
            cls._add_node(nodes, seen_ids, func_id, method_name, 'FUNCTION', module_id, f"L{line}")
        
        edges.append(GraphEdge(method_id if receiver_type else func_id, module_id, 'CONTAINS', 'EXTRACTED'))
    
    @classmethod
    def _extract_type_declaration(cls, node, file_id: str, module_id: str, pkg_scope: str,
                                   nodes: List[GraphNode], edges: List[GraphEdge],
                                   source: bytes, seen_ids: Set[str]):
        """提取类型声明（struct/interface）"""
        # type_declaration 的子节点包含 type_spec
        for child in node.children:
            if child.type != 'type_spec':
                continue
            
            name_node = child.child_by_field_name('name')
            if not name_node:
                continue
            
            type_name = name_node.text.decode('utf-8')
            if type_name in _PREDEFINED_TYPES:
                continue
            
            line = child.start_point[0] + 1
            type_id = cls._make_id(pkg_scope, type_name)
            
            # 找到类型体
            type_body = None
            for tc in child.children:
                if tc.type in ('struct_type', 'interface_type'):
                    type_body = tc
                    break
            
            if type_body is None:
                # 基础类型（如 type Foo string），跳过
                cls._add_node(nodes, seen_ids, type_id, type_name, 'TYPE', module_id, f"L{line}")
                edges.append(GraphEdge(type_id, module_id, 'CONTAINS', 'EXTRACTED'))
                continue
            
            # 提取字段或方法
            if type_body.type == 'struct_type':
                cls._add_node(nodes, seen_ids, type_id, type_name, 'STRUCT', module_id, f"L{line}")
                edges.append(GraphEdge(type_id, module_id, 'CONTAINS', 'EXTRACTED'))
                
                # 提取字段
                for fdl in type_body.children:
                    if fdl.type != 'field_declaration_list':
                        continue
                    for field in fdl.children:
                        if field.type != 'field_declaration':
                            continue
                        field_name_node = None
                        for fc in field.children:
                            if fc.type == 'field_identifier':
                                field_name_node = fc
                                break
                        if not field_name_node:
                            continue
                        field_name = field_name_node.text.decode('utf-8')
                        
                        field_id = cls._make_id(type_id, field_name)
                        cls._add_node(nodes, seen_ids, field_id, field_name, 'FIELD', type_id, f"L{field.start_point[0]+1}")
                        edges.append(GraphEdge(field_id, type_id, 'HAS_FIELD', 'EXTRACTED'))
            
            elif type_body.type == 'interface_type':
                cls._add_node(nodes, seen_ids, type_id, type_name, 'INTERFACE', module_id, f"L{line}")
                edges.append(GraphEdge(type_id, module_id, 'CONTAINS', 'EXTRACTED'))
                
                # 提取方法
                for method in type_body.children:
                    if method.type == 'method_spec':
                        name_node = method.child_by_field_name('name')
                        if name_node:
                            method_name = name_node.text.decode('utf-8')
                            method_id = cls._make_id(type_id, method_name)
                            cls._add_node(nodes, seen_ids, method_id, method_name, 'METHOD_SIGNATURE', type_id, f"L{method.start_point[0]+1}")
                            edges.append(GraphEdge(method_id, type_id, 'HAS_METHOD', 'EXTRACTED'))
    
    @classmethod
    def _extract_package(cls, root_node) -> str:
        """提取包名"""
        for child in root_node.children:
            if child.type == 'package_clause':
                name_node = child.child_by_field_name('name')
                if name_node:
                    return name_node.text.decode('utf-8')
        return "unknown"
    
    @classmethod
    def _make_id(cls, *parts: str) -> str:
        """生成唯一 ID"""
        return '_'.join(p.replace('/', '_').replace('.', '_') for p in parts if p)


class GlobalParser:
    def __init__(self):
        self.graph = CodeGraph()
    
    def parse_directory(self, dir_path: Path, max_files: int = 100):
        """解析整个目录"""
        if not HAS_TREE_SITTER:
            return self.graph
        
        go_files = list(dir_path.rglob("*.go"))[:max_files]
        print(f"  📄 扫描 {len(go_files)} 个 Go 文件...")
        
        for i, go_file in enumerate(go_files, 1):
            if i % 20 == 0:
                print(f"     已处理 {i}/{len(go_files)} 文件...")
            
            try:
                content = go_file.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            
            nodes, edges = GoASTParser.parse_file(go_file, content)
            
            for node in nodes:
                self.graph.add_node(node)
            for edge in edges:
                self.graph.add_edge(edge)
        
        print(f"  ✅ 完成: {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")
        return self.graph


class GraphAnalyzer:
    @staticmethod
    def find_god_nodes(graph: CodeGraph, top_n: int = 10) -> List[Dict]:
        """找 god nodes"""
        node_degrees = []
        for node_id in graph.nodes:
            node = graph.nodes[node_id]
            
            # 过滤
            if node.type in ('FILE', 'MODULE'):
                continue
            if node.label in ('string', 'int', 'error', 'Context'):
                continue
            
            degree = graph.get_degree(node_id)
            if degree < 3:
                continue
            
            node_degrees.append({
                'id': node_id,
                'label': node.label,
                'type': node.type,
                'degree': degree,
                'in_degree': len(graph.reverse_adj.get(node_id, set())),
                'out_degree': len(graph.adjacency.get(node_id, set())),
                'source_file': node.source_file,
            })
        
        node_degrees.sort(key=lambda x: x['degree'], reverse=True)
        return node_degrees[:top_n]
    
    @staticmethod
    def find_communities(graph: CodeGraph) -> Dict[str, int]:
        """社区检测"""
        if not HAS_NETWORKX:
            return {}
        
        G = nx.Graph()
        for node_id in graph.nodes:
            G.add_node(node_id)
        for edge in graph.edges:
            G.add_edge(edge.source, edge.target)
        
        try:
            communities = greedy_modularity_communities(G)
            node_to_community = {}
            for cid, community in enumerate(communities):
                for node_id in community:
                    node_to_community[node_id] = cid
            return node_to_community
        except Exception:
            return {}
    
    @staticmethod
    def find_cross_community_edges(graph: CodeGraph, communities: Dict[str, int]) -> List[Dict]:
        """找跨社区边"""
        cross_edges = []
        for edge in graph.edges:
            src_comm = communities.get(edge.source)
            tgt_comm = communities.get(edge.target)
            if src_comm is not None and tgt_comm is not None and src_comm != tgt_comm:
                cross_edges.append({
                    'source': edge.source,
                    'target': edge.target,
                    'relation': edge.relation,
                    'confidence': edge.confidence,
                })
        return cross_edges[:20]


class GraphifyPromptGenerator:
    def __init__(self, project_name: str):
        self.project_name = project_name
    
    def generate(self, graph: CodeGraph, god_nodes: List[Dict], 
                 communities: Dict[str, int], cross_edges: List[Dict]) -> str:
        """生成紧凑 prompt"""
        lines = []
        
        lines.append(f"# {self.project_name} 代码图谱")
        lines.append("")
        lines.append(f"**规模**: {len(graph.nodes)} 节点, {len(graph.edges)} 边")
        lines.append(f"**社区数**: {len(set(communities.values())) if communities else 0}")
        lines.append("")
        
        # God Nodes
        if god_nodes:
            lines.append("## 🔥 核心抽象（God Nodes）")
            lines.append("")
            lines.append("| 名称 | 类型 | 度 | 入度 | 出度 | 文件 |")
            lines.append("|------|------|-----|------|------|------|")
            for n in god_nodes[:10]:
                lines.append(f"| `{n['label']}` | {n['type']} | {n['degree']} | {n['in_degree']} | {n['out_degree']} | {n['source_file']} |")
            lines.append("")
        
        # 社区
        if communities:
            lines.append("## 🏘️ 社区结构")
            lines.append("")
            comm_sizes = Counter(communities.values())
            for cid, size in sorted(comm_sizes.items())[:10]:
                rep = None
                max_deg = 0
                for nid, c in communities.items():
                    if c == cid:
                        deg = graph.get_degree(nid)
                        if deg > max_deg:
                            max_deg = deg
                            rep = graph.nodes[nid].label if nid in graph.nodes else nid
                lines.append(f"- **Community {cid}** ({size} nodes): {rep}")
            lines.append("")
        
        # 核心代码
        lines.append("## 💻 核心实现")
        lines.append("")
        lines.append("*以下是系统最核心的代码片段：*")
        lines.append("")
        
        for node in god_nodes[:5]:
            node_id = node['id']
            if node_id not in graph.nodes:
                continue
            
            graph_node = graph.nodes[node_id]
            code = self._read_code_snippet(graph_node.source_file, graph_node.source_location)
            if code:
                lines.append(f"### `{graph_node.label}`")
                lines.append(f"**文件**: `{graph_node.source_file}` {graph_node.source_location}")
                lines.append("")
                lines.append("```go")
                lines.append(code)
                lines.append("```")
                lines.append("")
        
        # 跨社区连接
        if cross_edges:
            lines.append("## 🔗 跨社区连接")
            lines.append("")
            for edge in cross_edges[:5]:
                src = edge['source'].split('_')[-1] if '_' in edge['source'] else edge['source']
                tgt = edge['target'].split('_')[-1] if '_' in edge['target'] else edge['target']
                lines.append(f"- `{src}` → `{tgt}` ({edge['relation']})")
            lines.append("")
        
        lines.append("## 📋 分析任务")
        lines.append("")
        lines.append("请基于以上代码图谱，分析：")
        lines.append("1. 系统的核心架构模式是什么？")
        lines.append("2. God nodes 承担什么角色？")
        lines.append("3. 社区之间如何交互？")
        lines.append("")
        
        return '\n'.join(lines)
    
    def _read_code_snippet(self, source_file: str, location: str = "") -> str:
        """读取代码片段"""
        try:
            # source_file 可能是 node_id，需要找到实际文件
            # 简单策略：从 ID 中提取文件名
            for part in source_file.split('_'):
                if part.endswith('.go'):
                    file_path = Path(source_file)
                    if file_path.exists():
                        content = file_path.read_text()
                        lines = content.split('\n')
                        start_line = 0
                        if location:
                            m = re.match(r'L(\d+)', location)
                            if m:
                                start_line = int(m.group(1)) - 1
                        # 取 20 行
                        return '\n'.join(lines[start_line:start_line+20])
            return ""
        except:
            return ""


def run_graphify_analysis(repo_path: str, max_files: int = 100, output_dir: str = None):
    """运行完整的 Graphify 分析"""
    repo_path = Path(repo_path)
    
    print(f"🔍 Graphify Analysis: {repo_path}")
    print(f"   使用 Tree-sitter AST 解析...\n")
    
    # 1. 解析代码
    print("📊 解析代码...")
    parser = GlobalParser()
    graph = parser.parse_directory(repo_path, max_files=max_files)
    
    # 2. 分析图
    print("\n🎯 分析图结构...")
    analyzer = GraphAnalyzer()
    
    god_nodes = analyzer.find_god_nodes(graph, top_n=15)
    print(f"  ✓ God nodes: {len(god_nodes)}")
    
    communities = analyzer.find_communities(graph)
    comm_count = len(set(communities.values())) if communities else 0
    print(f"  ✓ Communities: {comm_count}")
    
    cross_edges = analyzer.find_cross_community_edges(graph, communities)
    print(f"  ✓ Cross-community edges: {len(cross_edges)}")
    
    # 3. 生成 prompt
    print("\n📝 生成 Prompt...")
    generator = GraphifyPromptGenerator(repo_path.name)
    prompt = generator.generate(graph, god_nodes, communities, cross_edges)
    
    # 4. 保存
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        prompt_path = output_path / 'graphify_prompt.md'
        prompt_path.write_text(prompt, encoding='utf-8')
        print(f"  ✓ Prompt: {prompt_path} ({len(prompt)} chars)")
        
        graph_data = {
            'nodes': [{'id': n.id, 'label': n.label, 'type': n.type, 
                       'source_file': n.source_file, 'source_location': n.source_location}
                      for n in graph.nodes.values()],
            'edges': [{'source': e.source, 'target': e.target, 
                       'relation': e.relation, 'confidence': e.confidence}
                      for e in graph.edges],
            'god_nodes': god_nodes,
            'communities': {k: v for k, v in list(communities.items())[:100]},
        }
        graph_path = output_path / 'graph.json'
        graph_path.write_text(json.dumps(graph_data, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"  ✓ Graph: {graph_path}")
    
    print("\n" + "=" * 70)
    print("Prompt Preview:")
    print("=" * 70)
    print(prompt[:3000])
    if len(prompt) > 3000:
        print(f"\n... (total {len(prompt)} chars)")
    
    return graph, god_nodes, communities, prompt


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python graphify_analysis.py <repo_path> [max_files] [output_dir]")
        sys.exit(1)
    
    repo_path = sys.argv[1]
    max_files = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    output_dir = sys.argv[3] if len(sys.argv) > 3 else None
    
    run_graphify_analysis(repo_path, max_files, output_dir)
