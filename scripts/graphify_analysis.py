#!/usr/bin/env python3
"""
Graphify-style Code Analysis for biz-delivery
借鉴 Graphify 的核心思想：
1. Tree-sitter AST 解析（确定性提取）
2. 标准化节点/边 schema
3. 社区检测（Leiden/Louvain）
4. 图分析（god nodes, surprising connections）
5. 紧凑 prompt 生成（节省 70% token）
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict, Counter

try:
    import networkx as nx
    from networkx.algorithms.community import greedy_modularity_communities
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


class GraphNode:
    """图节点"""
    def __init__(self, node_id: str, label: str, node_type: str, 
                 source_file: str = "", source_location: str = "",
                 properties: dict = None):
        self.id = node_id
        self.label = label
        self.type = node_type  # FUNCTION, METHOD, STRUCT, INTERFACE, FILE, MODULE
        self.source_file = source_file
        self.source_location = source_location
        self.properties = properties or {}


class GraphEdge:
    """图边"""
    def __init__(self, source: str, target: str, relation: str,
                 confidence: str = "EXTRACTED", properties: dict = None):
        self.source = source
        self.target = target
        self.relation = relation  # CALLS, IMPORTS, REFERENCES, IMPLEMENTS, CONTAINS
        self.confidence = confidence  # EXTRACTED, INFERRED, AMBIGUOUS
        self.properties = properties or {}


class CodeGraph:
    """代码图谱"""
    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.adjacency: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_adj: Dict[str, Set[str]] = defaultdict(set)
    
    def add_node(self, node: GraphNode):
        """添加节点"""
        self.nodes[node.id] = node
    
    def add_edge(self, edge: GraphEdge):
        """添加边"""
        self.edges.append(edge)
        self.adjacency[edge.source].add(edge.target)
        self.reverse_adj[edge.target].add(edge.source)
    
    def get_out_degree(self, node_id: str) -> int:
        """出度"""
        return len(self.adjacency.get(node_id, set()))
    
    def get_in_degree(self, node_id: str) -> int:
        """入度"""
        return len(self.reverse_adj.get(node_id, set()))
    
    def get_degree(self, node_id: str) -> int:
        """总度"""
        return self.get_out_degree(node_id) + self.get_in_degree(node_id)


class GoASTParser:
    """Go AST 解析器（简化版，基于正则）"""
    
    # 函数签名匹配
    FUNC_SIG_RE = re.compile(
        r'func\s+'
        r'(?:\(\s*(\w+)\s+\*?(\w+)\s*\)\s+)?'  # receiver
        r'(\w+)\s*'                              # func name
        r'\('                                    # opening paren
    )
    
    # 结构体定义
    STRUCT_RE = re.compile(r'type\s+(\w+)\s+struct\s*\{')
    
    # 接口定义
    INTERFACE_RE = re.compile(r'type\s+(\w+)\s+interface\s*\{')
    
    # import
    IMPORT_RE = re.compile(r'import\s+(?:\(\s*([^)]+)\s*\)|\s*"([^"]+)"|\s+(\w+)\s+"([^"]+)")')
    
    # 方法调用
    CALL_RE = re.compile(r'(\w+(?:\.\w+)*)\s*\(')
    
    @classmethod
    def parse_file(cls, file_path: Path, content: str) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """解析 Go 文件，返回节点和边"""
        nodes = []
        edges = []
        
        lines = content.split('\n')
        pkg_name = cls._extract_package(content)
        
        # 文件节点
        file_id = cls._make_id(str(file_path))
        nodes.append(GraphNode(
            node_id=file_id,
            label=file_path.name,
            node_type='FILE',
            source_file=str(file_path),
        ))
        
        # 模块节点
        module_id = cls._make_id(pkg_name)
        nodes.append(GraphNode(
            node_id=module_id,
            label=pkg_name,
            node_type='MODULE',
            source_file=str(file_path),
        ))
        
        # 文件 → 模块
        edges.append(GraphEdge(
            source=file_id,
            target=module_id,
            relation='CONTAINS',
            confidence='EXTRACTED',
        ))
        
        # 解析 struct
        struct_names = {}
        for i, line in enumerate(lines, 1):
            m = cls.STRUCT_RE.match(line.strip())
            if m:
                name = m.group(1)
                struct_id = cls._make_id(pkg_name, name)
                nodes.append(GraphNode(
                    node_id=struct_id,
                    label=name,
                    node_type='STRUCT',
                    source_file=str(file_path),
                    source_location=f"L{i}",
                ))
                struct_names[name] = struct_id
                
                # struct → module
                edges.append(GraphEdge(
                    source=struct_id,
                    target=module_id,
                    relation='CONTAINS',
                    confidence='EXTRACTED',
                ))
        
        # 解析 interface
        interface_names = {}
        for i, line in enumerate(lines, 1):
            m = cls.INTERFACE_RE.match(line.strip())
            if m:
                name = m.group(1)
                iface_id = cls._make_id(pkg_name, name)
                nodes.append(GraphNode(
                    node_id=iface_id,
                    label=name,
                    node_type='INTERFACE',
                    source_file=str(file_path),
                    source_location=f"L{i}",
                ))
                interface_names[name] = iface_id
                
                # interface → module
                edges.append(GraphEdge(
                    source=iface_id,
                    target=module_id,
                    relation='CONTAINS',
                    confidence='EXTRACTED',
                ))
        
        # 解析函数/方法
        func_stack = []  # [(func_id, start_line, body_lines)]
        for i, line in enumerate(lines, 1):
            m = cls.FUNC_SIG_RE.match(line.strip())
            if m:
                receiver = m.group(1) or ''
                receiver_type = m.group(2) or ''
                func_name = m.group(3)
                
                # 确定节点 ID 和类型
                if receiver_type:
                    func_id = cls._make_id(pkg_name, receiver_type, func_name)
                    node_type = 'METHOD'
                else:
                    func_id = cls._make_id(pkg_name, func_name)
                    node_type = 'FUNCTION'
                
                nodes.append(GraphNode(
                    node_id=func_id,
                    label=f"{func_name}()" if receiver_type else func_name,
                    node_type=node_type,
                    source_file=str(file_path),
                    source_location=f"L{i}",
                ))
                
                # 方法 → 结构体
                if receiver_type and receiver_type in struct_names:
                    edges.append(GraphEdge(
                        source=func_id,
                        target=struct_names[receiver_type],
                        relation='IMPLEMENTS',
                        confidence='EXTRACTED',
                    ))
                
                # 函数 → 模块
                edges.append(GraphEdge(
                    source=func_id,
                    target=module_id,
                    relation='CONTAINS',
                    confidence='EXTRACTED',
                ))
                
                func_stack.append((func_id, i, []))
                continue
            
            # 收集函数体
            if func_stack:
                func_stack[-1][2].append((i, line))
                
                # 检测函数结束（简单判断：行首无缩进且不是注释）
                if line.strip() and not line.startswith('\t') and not line.startswith('//'):
                    if line.strip() == '}':
                        func_id, start_line, body = func_stack.pop()
                        
                        # 提取调用（传入已知节点）
                        body_text = '\n'.join(l for _, l in body)
                        cls._extract_calls(body_text, func_id, edges, file_path,
                                          {n.id: n for n in nodes})
        
        # 解析 import
        import_blocks = re.findall(r'import\s*\(([^)]+)\)', content)
        for block in import_blocks:
            for line in block.split('\n'):
                line = line.strip()
                if not line or line.startswith('//'):
                    continue
                # 匹配 "path" 或 alias "path"
                m = re.match(r'(?:\w+\s+)?"([^"]+)"', line)
                if m:
                    import_path = m.group(1)
                    
                    # 创建模块节点
                    mod_id = cls._make_id("module", import_path.split('/')[-1])
                    nodes.append(GraphNode(
                        node_id=mod_id,
                        label=import_path,
                        node_type='MODULE',
                        source_file=str(file_path),
                    ))
                    
                    # 文件 → 导入模块
                    edges.append(GraphEdge(
                        source=file_id,
                        target=mod_id,
                        relation='IMPORTS',
                        confidence='EXTRACTED',
                    ))
        
        return nodes, edges
    
    @classmethod
    def _extract_package(cls, content: str) -> str:
        """提取包名"""
        for line in content.split('\n')[:10]:
            m = re.match(r'^\s*package\s+(\w+)', line)
            if m:
                return m.group(1)
        return "unknown"
    
    @classmethod
    def _extract_calls(cls, body_text: str, func_id: str, edges: List[GraphEdge], 
                       source_file: Path, known_nodes: Dict[str, GraphNode] = None):
        """提取函数体内的调用"""
        if known_nodes is None:
            known_nodes = {}
            
        for m in cls.CALL_RE.finditer(body_text):
            call = m.group(1)
            # 过滤掉关键字
            if call in ('if', 'for', 'switch', 'return', 'defer', 'go', 'select',
                       'make', 'new', 'append', 'len', 'cap', 'close', 'copy',
                       'delete', 'panic', 'recover', 'fmt', 'log', 'err', 'nil',
                       'string', 'int', 'bool', 'ctx', 'c', 'w', 'r', 'req', 'rsp'):
                continue
            
            # 简化调用名（去掉包前缀）
            call_name = call.split('.')[-1] if '.' in call else call
            
            # 尝试匹配已知节点
            for node_id, node in known_nodes.items():
                if node.label == call_name and node.source_file != str(source_file):
                    edges.append(GraphEdge(
                        source=func_id,
                        target=node_id,
                        relation='CALLS',
                        confidence='INFERRED',
                    ))
                    break
    
    @classmethod
    def _make_id(cls, *parts: str) -> str:
        """生成唯一 ID"""
        return '_'.join(p.replace('/', '_').replace('.', '_') for p in parts if p)


class GlobalParser:
    """全局解析器"""
    def __init__(self):
        self.graph = CodeGraph()
        self.file_cache = {}
    
    def parse_directory(self, dir_path: Path, max_files: int = 100):
        """解析整个目录"""
        go_files = list(dir_path.rglob("*.go"))[:max_files]
        
        all_nodes = []
        all_edges = []
        
        for go_file in go_files:
            try:
                content = go_file.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            
            nodes, edges = GoASTParser.parse_file(go_file, content)
            all_nodes.extend(nodes)
            all_edges.extend(edges)
        
        # 构建图
        for node in all_nodes:
            self.graph.add_node(node)
        for edge in all_edges:
            self.graph.add_edge(edge)
        
        return self.graph


# 全局解析器实例
global_parser = GlobalParser()


class GraphAnalyzer:
    """图分析器"""
    
    @staticmethod
    def find_god_nodes(graph: CodeGraph, top_n: int = 10) -> List[Dict]:
        """找 god nodes（连接度最高的节点）"""
        node_degrees = []
        for node_id in graph.nodes:
            degree = graph.get_degree(node_id)
            node = graph.nodes[node_id]
            
            # 过滤文件节点和内置类型
            if node.type in ('FILE', 'MODULE'):
                continue
            if node.label in ('string', 'int', 'error', 'Context'):
                continue
            
            node_degrees.append({
                'id': node_id,
                'label': node.label,
                'type': node.type,
                'degree': degree,
                'in_degree': graph.get_in_degree(node_id),
                'out_degree': graph.get_out_degree(node_id),
                'source_file': node.source_file,
            })
        
        # 按度排序
        node_degrees.sort(key=lambda x: x['degree'], reverse=True)
        return node_degrees[:top_n]
    
    @staticmethod
    def find_communities(graph: CodeGraph) -> Dict[str, int]:
        """社区检测（Louvain 算法）"""
        if not HAS_NETWORKX:
            return {}
        
        # 构建 NetworkX 图
        G = nx.Graph()
        for node_id in graph.nodes:
            G.add_node(node_id)
        for edge in graph.edges:
            G.add_edge(edge.source, edge.target)
        
        # 运行 Louvain
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
        """找跨社区边（surprising connections）"""
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
                    'source_community': src_comm,
                    'target_community': tgt_comm,
                })
        return cross_edges[:20]  # 只返回前20个


class GraphifyPromptGenerator:
    """Graphify 风格 Prompt 生成器"""
    
    def __init__(self, project_name: str):
        self.project_name = project_name
    
    def generate(self, graph: CodeGraph, god_nodes: List[Dict], 
                 communities: Dict[str, int], cross_edges: List[Dict]) -> str:
        """生成紧凑 prompt"""
        lines = []
        
        # 头部
        lines.append(f"# {self.project_name} 代码图谱")
        lines.append("")
        lines.append(f"**规模**: {len(graph.nodes)} 节点, {len(graph.edges)} 边")
        lines.append(f"**社区数**: {len(set(communities.values())) if communities else 0}")
        lines.append("")
        
        # 1. God Nodes（核心抽象）
        if god_nodes:
            lines.append("## 🔥 核心抽象（God Nodes）")
            lines.append("")
            lines.append("| 名称 | 类型 | 度 | 入度 | 出度 | 文件 |")
            lines.append("|------|------|-----|------|------|------|")
            for n in god_nodes[:10]:
                lines.append(f"| `{n['label']}` | {n['type']} | {n['degree']} | {n['in_degree']} | {n['out_degree']} | {n['source_file']} |")
            lines.append("")
        
        # 2. 社区概览
        if communities:
            lines.append("## 🏘️ 社区结构")
            lines.append("")
            comm_sizes = Counter(communities.values())
            for cid, size in sorted(comm_sizes.items())[:10]:
                # 找社区的 representative（度最高的节点）
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
        
        # 3. 关键代码片段（只保留 god nodes 的代码）
        lines.append("## 💻 核心实现")
        lines.append("")
        lines.append("*以下是系统最核心的代码片段：*")
        lines.append("")
        
        for node in god_nodes[:5]:
            node_id = node['id']
            if node_id not in graph.nodes:
                continue
            
            graph_node = graph.nodes[node_id]
            if not graph_node.source_file:
                continue
            
            # 读取代码
            code = self._read_code_snippet(graph_node.source_file, graph_node.source_location)
            if not code:
                continue
            
            lines.append(f"### `{graph_node.label}`")
            lines.append(f"**文件**: `{graph_node.source_file}` {graph_node.source_location}")
            lines.append("")
            lines.append("```go")
            lines.append(code)
            lines.append("```")
            lines.append("")
        
        # 4. 跨社区连接（架构洞察）
        if cross_edges:
            lines.append("## 🔗 跨社区连接（架构洞察）")
            lines.append("")
            lines.append("以下连接跨越了不同模块，可能是架构关键路径：")
            lines.append("")
            for edge in cross_edges[:5]:
                src = edge['source'].split('_')[-1] if '_' in edge['source'] else edge['source']
                tgt = edge['target'].split('_')[-1] if '_' in edge['target'] else edge['target']
                lines.append(f"- `{src}` → `{tgt}` ({edge['relation']}, {edge['confidence']})")
            lines.append("")
        
        # 5. 任务
        lines.append("## 📋 分析任务")
        lines.append("")
        lines.append("请基于以上代码图谱，分析：")
        lines.append("1. 系统的核心架构模式是什么？")
        lines.append("2. God nodes 承担什么角色？")
        lines.append("3. 社区之间如何交互？")
        lines.append("")
        
        return '\n'.join(lines)
    
    def _read_code_snippet(self, file_path: str, location: str = "") -> str:
        """读取代码片段"""
        try:
            full_path = Path(file_path)
            if not full_path.exists():
                return ""
            
            content = full_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
            
            # 解析行号
            start_line = 0
            if location:
                m = re.match(r'L(\d+)', location)
                if m:
                    start_line = int(m.group(1)) - 1
            
            # 提取函数体（向前找 func 开始，向后找 } 结束）
            func_start = start_line
            for i in range(start_line, max(-1, start_line - 20), -1):
                if lines[i].strip().startswith('func '):
                    func_start = i
                    break
            
            brace_count = 0
            func_end = start_line
            for i in range(func_start, min(len(lines), func_start + 50)):
                for c in lines[i]:
                    if c == '{':
                        brace_count += 1
                    elif c == '}':
                        brace_count -= 1
                        if brace_count == 0 and i > func_start:
                            func_end = i + 1
                            break
                if brace_count == 0 and func_end > func_start:
                    break
            
            return '\n'.join(lines[func_start:func_end])
        except Exception:
            return ""


def run_graphify_analysis(repo_path: str, max_files: int = 100, output_dir: str = None):
    """运行完整的 Graphify 分析"""
    repo_path = Path(repo_path)
    
    print(f"🔍 Graphify Analysis: {repo_path}")
    
    # 1. 解析代码
    print("📊 解析代码...")
    parser = GlobalParser()
    graph = parser.parse_directory(repo_path, max_files=max_files)
    print(f"  ✓ {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    
    # 2. 分析图
    print("🎯 分析图结构...")
    analyzer = GraphAnalyzer()
    
    god_nodes = analyzer.find_god_nodes(graph, top_n=15)
    print(f"  ✓ God nodes: {len(god_nodes)}")
    
    communities = analyzer.find_communities(graph)
    print(f"  ✓ Communities: {len(set(communities.values())) if communities else 0}")
    
    cross_edges = analyzer.find_cross_community_edges(graph, communities)
    print(f"  ✓ Cross-community edges: {len(cross_edges)}")
    
    # 3. 生成 prompt
    print("📝 生成 Prompt...")
    generator = GraphifyPromptGenerator(repo_path.name)
    prompt = generator.generate(graph, god_nodes, communities, cross_edges)
    
    # 4. 保存结果
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 保存 prompt
        prompt_path = output_path / 'graphify_prompt.md'
        prompt_path.write_text(prompt, encoding='utf-8')
        print(f"  ✓ Prompt: {prompt_path} ({len(prompt)} chars)")
        
        # 保存 graph JSON
        graph_data = {
            'nodes': [
                {
                    'id': n.id,
                    'label': n.label,
                    'type': n.type,
                    'source_file': n.source_file,
                    'source_location': n.source_location,
                }
                for n in graph.nodes.values()
            ],
            'edges': [
                {
                    'source': e.source,
                    'target': e.target,
                    'relation': e.relation,
                    'confidence': e.confidence,
                }
                for e in graph.edges
            ],
            'god_nodes': god_nodes,
            'communities': {k: v for k, v in list(communities.items())[:100]},
        }
        graph_path = output_path / 'graph.json'
        graph_path.write_text(json.dumps(graph_data, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"  ✓ Graph: {graph_path}")
    
    # 打印预览
    print("\n" + "=" * 70)
    print("Prompt Preview:")
    print("=" * 70)
    print(prompt[:2000])
    if len(prompt) > 2000:
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
