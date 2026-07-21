#!/usr/bin/env python3
"""
Codebase Graph Builder — 基于 Python 的代码图谱构建器

借鉴 codebase-memory-mcp 的多层管道思想：
1. pass_definitions: 提取函数/类/方法定义
2. pass_calls: 解析函数调用，提取 callee, args
3. pass_imports: 解析 import 语句，构建模块映射
4. pass_routes: 提取 HTTP 路由节点
5. pass_data_flow: 提取数据流（变量赋值、读写）
6. pass_semantic_edges: 计算函数间语义关联

输出: 图数据结构（Nodes + Edges），持久化为 JSON/SQLite
"""

import re
import json
import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict


# ============================================================================
# 图数据结构（对标 cbm_gbuf_node_t / cbm_gbuf_edge_t）
# ============================================================================

@dataclass
class GraphNode:
    """图节点 — 对标 cbm_node_t"""
    id: int = 0
    label: str = ""  # Function, Class, Method, Module, File, Route, Variable
    name: str = ""
    qualified_name: str = ""  # project.module.Class.method
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    properties: dict = field(default_factory=dict)  # JSON-serializable


@dataclass
class GraphEdge:
    """图边 — 对标 cbm_edge_t"""
    id: int = 0
    source_id: int = 0
    target_id: int = 0
    type: str = ""  # CALLS, HTTP_CALLS, IMPORTS, HANDLES, DATA_FLOW, SEMANTIC
    properties: dict = field(default_factory=dict)


@dataclass
class CodeGraph:
    """代码图谱 — 对标 cbm_gbuf_t"""
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)
    node_by_qn: Dict[str, int] = field(default_factory=dict)  # QN → node_id
    node_by_id: Dict[int, GraphNode] = field(default_factory=dict)  # id → node
    next_node_id: int = 1
    next_edge_id: int = 1

    def add_node(self, label: str, name: str, qn: str, file_path: str,
                 start_line: int = 0, end_line: int = 0,
                 properties: dict = None) -> int:
        """添加节点，返回 node_id"""
        node = GraphNode(
            id=self.next_node_id,
            label=label,
            name=name,
            qualified_name=qn,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            properties=properties or {},
        )
        self.nodes.append(node)
        self.node_by_qn[qn] = self.next_node_id
        self.node_by_id[self.next_node_id] = node
        nid = self.next_node_id
        self.next_node_id += 1
        return nid

    def add_edge(self, source_id: int, target_id: int, edge_type: str,
                 properties: dict = None) -> int:
        """添加边，返回 edge_id"""
        edge = GraphEdge(
            id=self.next_edge_id,
            source_id=source_id,
            target_id=target_id,
            type=edge_type,
            properties=properties or {},
        )
        self.edges.append(edge)
        eid = self.next_edge_id
        self.next_edge_id += 1
        return eid

    def find_by_qn(self, qn: str) -> Optional[GraphNode]:
        """通过 QN 查找节点"""
        nid = self.node_by_qn.get(qn)
        return self.node_by_id.get(nid) if nid else None

    def find_by_id(self, nid: int) -> Optional[GraphNode]:
        """通过 ID 查找节点"""
        return self.node_by_id.get(nid)

    def get_outgoing_edges(self, source_id: int, edge_type: str = None) -> List[GraphEdge]:
        """获取从 source_id 出发的边"""
        result = []
        for edge in self.edges:
            if edge.source_id == source_id:
                if edge_type is None or edge.type == edge_type:
                    result.append(edge)
        return result

    def get_incoming_edges(self, target_id: int, edge_type: str = None) -> List[GraphEdge]:
        """获取指向 target_id 的边"""
        result = []
        for edge in self.edges:
            if edge.target_id == target_id:
                if edge_type is None or edge.type == edge_type:
                    result.append(edge)
        return result

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
        }

    def save_json(self, path: str):
        """保存为 JSON"""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


# ============================================================================
# Go 语言解析器（对标 tree-sitter Go grammar）
# ============================================================================

class GoParser:
    """Go 代码解析器 — 基于正则的 AST 近似"""

    # 函数/方法定义
    # 修复：params 可能有嵌套括号（如 *ginweb.Context），不能用 [^)]*
    FUNC_SIG_RE = re.compile(
        r'func\s+'
        r'(?:\(\s*(\w+)\s+\*?(\w+)\s*\)\s+)?'  # receiver: (m *Module)
        r'(\w+)\s*'                              # func name
        r'\('                                    # opening paren (params 用非贪婪匹配)
    )
    # 单独匹配 return type
    FUNC_RETURN_RE = re.compile(
        r'\)\s*(\w+(?:\s*\[\s*\d+\s*\])?(?:\s*\*)?(?:\s*&)?(?:\s*\w+(?:\s*\[[^\]]*\])?)*)\s*\{'
    )

    # 结构体定义
    STRUCT_RE = re.compile(
        r'type\s+(\w+)\s+struct\s*\{'
    )

    # 路由注册
    ROUTE_RE = re.compile(
        r'(?:group|groupPermission|r|engine)\.(GET|POST|PUT|DELETE|PATCH|Any|Handle)\s*\(\s*["\']([^"\']+)["\']'
        r'(?:\s*,\s*(.+?))?\s*\)'
    )

    # 调用表达式
    CALL_RE = re.compile(
        r'(?:([\w.]+)\.)?(\w+)\s*\('
    )

    # import 语句
    IMPORT_RE = re.compile(
        r'import\s+(?:\(([^)]+)\)|(\S+))'
    )

    # 变量/常量声明
    VAR_RE = re.compile(
        r'(?:var|const)\s+(\w+)\s+'
    )

    # interface 定义
    INTERFACE_RE = re.compile(
        r'type\s+(\w+)\s+interface\s*\{'
    )

    # 包级别函数（无 receiver）
    PKG_FUNC_RE = re.compile(
        r'^func\s+(\w+)\s*\(([^)]*)\)'
    )

    @staticmethod
    def extract_file_info(source: str, file_path: str) -> dict:
        """从 Go 源码提取文件级信息"""
        lines = source.split('\n')
        result = {
            'file_path': file_path,
            'package': '',
            'imports': [],
            'functions': [],
            'structs': [],
            'interfaces': [],
            'routes': [],
            'variables': [],
        }

        # 包名
        for line in lines[:20]:
            m = re.match(r'^\s*package\s+(\w+)', line)
            if m:
                result['package'] = m.group(1)
                break

        # imports
        import_blocks = re.findall(r'import\s*\(([^)]+)\)', source)
        for block in import_blocks:
            for line in block.split('\n'):
                line = line.strip()
                if not line or line.startswith('//'):
                    continue
                # 格式: alias "path" 或 "path"
                m = re.match(r'(\w+)\s+"([^"]+)"', line)
                if m:
                    result['imports'].append({'alias': m.group(1), 'path': m.group(2)})
                else:
                    m = re.match(r'"([^"]+)"', line)
                    if m:
                        result['imports'].append({'alias': None, 'path': m.group(1)})

        # 逐行解析
        for i, line in enumerate(lines, 1):
            # 结构体
            m = GoParser.STRUCT_RE.match(line)
            if m:
                result['structs'].append({
                    'name': m.group(1),
                    'line': i,
                })

            # 接口
            m = GoParser.INTERFACE_RE.match(line)
            if m:
                result['interfaces'].append({
                    'name': m.group(1),
                    'line': i,
                })

            # 变量/常量
            m = GoParser.VAR_RE.match(line)
            if m:
                result['variables'].append({
                    'name': m.group(1),
                    'line': i,
                })

            # 路由注册
            for rm in GoParser.ROUTE_RE.finditer(line):
                result['routes'].append({
                    'method': rm.group(1),
                    'path': rm.group(2),
                    'handler': rm.group(3).strip() if rm.group(3) else '',
                    'line': i,
                })

        # 函数/方法（需要找函数体边界）
        for i, line in enumerate(lines):
            m = GoParser.FUNC_SIG_RE.match(line)
            if not m:
                continue
            receiver = m.group(1) or ''
            receiver_type = m.group(2) or ''
            func_name = m.group(3)

            # 提取 params — 找到 func name 后面的 (
            func_name_pos = line.index(func_name)
            paren_start = line.index('(', func_name_pos)
            depth = 0
            params_end = paren_start
            for j in range(paren_start, len(line)):
                if line[j] == '(':
                    depth += 1
                elif line[j] == ')':
                    depth -= 1
                    if depth == 0:
                        params_end = j
                        break
            params = line[paren_start+1:params_end] if params_end > paren_start else ''

            # 提取 return type
            rest = line[params_end+1:].strip()
            return_type = ''
            rm = re.match(r'(\w+)', rest)
            if rm and rm.group(1) not in ('{', 'nil', 'bool', 'int', 'string', 'error'):
                return_type = rm.group(1)

                # 提取函数体（简化：取接下来 50 行）
                body_lines = lines[i:i+50]
                body_text = '\n'.join(body_lines)

                # 提取调用
                calls = []
                for cm in GoParser.CALL_RE.finditer(body_text):
                    prefix = cm.group(1) or ''
                    callee = cm.group(2)
                    if callee not in ('if', 'for', 'switch', 'return', 'defer',
                                      'go', 'select', 'make', 'new', 'append',
                                      'len', 'cap', 'close', 'copy', 'delete',
                                      'panic', 'recover', 'fmt', 'log', 'err',
                                      'nil', 'string', 'int', 'bool', 'ctx', 'c',
                                      'w', 'r', 'req', 'rsp', 'res'):
                        calls.append({
                            'prefix': prefix,
                            'name': callee,
                            'full_name': f"{prefix}.{callee}" if prefix else callee,
                        })

                result['functions'].append({
                    'name': func_name,
                    'receiver_type': receiver_type,
                    'receiver': receiver,
                    'params': params,
                    'return_type': return_type,
                    'line': i + 1,
                    'calls': calls[:20],
                })

        return result

    @staticmethod
    def compute_fqn(package: str, file_path: str, func_name: str,
                    receiver_type: str = '') -> str:
        """计算完全限定名（QN）"""
        # Go 的 QN 格式: package/path.Type.Method
        if receiver_type:
            return f"{package}/{file_path}.{receiver_type}.{func_name}"
        return f"{package}/{file_path}.{func_name}"


# ============================================================================
# 管道（Pipeline）— 对标 cbm_pipeline
# ============================================================================

class PassDefinitions:
    """Pass 1: 提取定义（函数、类、方法、模块、文件、路由）"""

    def __init__(self, graph: CodeGraph):
        self.graph = graph

    def run(self, file_path: str, source: str, lang: str = 'go') -> List[int]:
        """运行提取，返回创建的节点 ID 列表"""
        node_ids = []

        if lang == 'go':
            info = GoParser.extract_file_info(source, file_path)

            # 文件节点
            file_qn = f"file:{file_path}"
            file_id = self.graph.add_node(
                label='File',
                name=file_path,
                qn=file_qn,
                file_path=file_path,
            )
            node_ids.append(file_id)

            # 路由节点
            for route in info.get('routes', []):
                route_qn = f"route:{route['method']}_{route['path']}"
                handler_name = route.get('handler', '')
                route_id = self.graph.add_node(
                    label='Route',
                    name=f"{route['method']} {route['path']}",
                    qn=route_qn,
                    file_path=file_path,
                    start_line=route['line'],
                    end_line=route['line'],
                    properties={
                        'http_method': route['method'],
                        'path': route['path'],
                        'handler_name': handler_name,  # 用于后续匹配
                    },
                )
                node_ids.append(route_id)

            # 函数/方法节点
            for func in info.get('functions', []):
                fqn = GoParser.compute_fqn(
                    info.get('package', ''),
                    file_path,
                    func['name'],
                    func.get('receiver_type', '')
                )
                func_id = self.graph.add_node(
                    label='Method' if func.get('receiver_type') else 'Function',
                    name=func['name'],
                    qn=fqn,
                    file_path=file_path,
                    start_line=func['line'],
                    properties={
                        'params': func['params'],
                        'return_type': func['return_type'],
                        'receiver_type': func.get('receiver_type', ''),
                    },
                )
                node_ids.append(func_id)

                # 连接 File → Function
                file_qn = f"file:{file_path}"
                file_node = self.graph.find_by_qn(file_qn)
                if file_node:
                    self.graph.add_edge(
                        source_id=file_node.id,
                        target_id=func_id,
                        edge_type='CONTAINS',
                    )

        return node_ids


class PassCalls:
    """Pass 2: 解析函数调用，构建 CALLS 边"""

    def __init__(self, graph: CodeGraph):
        self.graph = graph

    def run(self, file_path: str, source: str, lang: str = 'go'):
        """运行调用边提取"""
        if lang != 'go':
            return

        info = GoParser.extract_file_info(source, file_path)

        for func_info in info.get('functions', []):
            fqn = GoParser.compute_fqn(
                info.get('package', ''),
                file_path,
                func_info['name'],
                func_info.get('receiver_type', '')
            )
            caller_node = self.graph.find_by_qn(fqn)
            if not caller_node:
                continue

            for call in func_info.get('calls', []):
                callee_name = call['name']
                prefix = call.get('prefix', '')

                # 尝试通过 name 匹配到已知节点
                target_node = None
                for node in self.graph.nodes:
                    if node.name == callee_name and node.label in ('Function', 'Method'):
                        target_node = node
                        break

                if target_node:
                    self.graph.add_edge(
                        source_id=caller_node.id,
                        target_id=target_node.id,
                        edge_type='CALLS',
                        properties={
                            'callee_args': json.dumps(call),
                            'confidence': 0.9,
                        },
                    )


class PassImports:
    """Pass 3: 解析 import 语句，构建 IMPORTS 边"""

    def __init__(self, graph: CodeGraph):
        self.graph = graph

    def run(self, file_path: str, source: str, lang: str = 'go'):
        if lang != 'go':
            return

        info = GoParser.extract_file_info(source, file_path)

        file_qn = f"file:{file_path}"
        file_node = self.graph.find_by_qn(file_qn)
        if not file_node:
            return

        for imp in info.get('imports', []):
            # 创建 Module 节点
            module_qn = f"module:{imp['path']}"
            module_id = self.graph.add_node(
                label='Module',
                name=imp['path'],
                qn=module_qn,
                file_path=file_path,
                properties={'import_path': imp['path']},
            )

            self.graph.add_edge(
                source_id=file_node.id,
                target_id=module_id,
                edge_type='IMPORTS',
                properties={'alias': imp.get('alias')},
            )


class PassRoutes:
    """Pass 4: 提取 HTTP 路由节点"""

    def __init__(self, graph: CodeGraph):
        self.graph = graph

    def run(self, file_path: str, source: str, lang: str = 'go'):
        if lang != 'go':
            return

        info = GoParser.extract_file_info(source, file_path)

        for route in info.get('routes', []):
            route_qn = f"route:{route['method']}_{route['path']}"
            route_node = self.graph.find_by_qn(route_qn)
            if not route_node:
                continue

            # 通过 Route 节点的 properties['handler_name'] 匹配 Handler 函数
            handler_full = route_node.properties.get('handler_name', '')
            if not handler_full:
                continue

            # 提取纯函数名：去掉 receiver 前缀（如 m.CreateAdGroup → CreateAdGroup）
            handler_name = handler_full.split('.')[-1].split('(')[0].strip()
            if not handler_name or handler_name == 'func':
                continue

            # 在所有节点中查找同名函数
            for node in self.graph.nodes:
                if (node.name == handler_name and
                    node.label in ('Function', 'Method')):
                    self.graph.add_edge(
                        source_id=route_node.id,
                        target_id=node.id,
                        edge_type='HANDLES',
                        properties={
                            'http_method': route['method'],
                            'path': route['path'],
                        },
                    )
                    break


class CodeGraphBuilder:
    """代码图谱构建器 — 对标 cbm_pipeline"""

    def __init__(self, project_name: str, repo_path: str):
        self.project_name = project_name
        self.repo_path = Path(repo_path)
        self.graph = CodeGraph()

    def build(self, lang: str = 'go', max_files: int = 500):
        """构建完整图谱"""
        # 收集所有源文件
        go_files = list(self.repo_path.rglob("*.go"))[:max_files]

        # Pass 1: 提取定义
        defs_pass = PassDefinitions(self.graph)
        for go_file in go_files:
            try:
                source = go_file.read_text(encoding='utf-8', errors='ignore')
                rel_path = str(go_file.relative_to(self.repo_path.parent))
                defs_pass.run(rel_path, source, lang)
            except Exception:
                continue

        # Pass 2: 解析调用
        calls_pass = PassCalls(self.graph)
        for go_file in go_files:
            try:
                source = go_file.read_text(encoding='utf-8', errors='ignore')
                rel_path = str(go_file.relative_to(self.repo_path.parent))
                calls_pass.run(rel_path, source, lang)
            except Exception:
                continue

        # Pass 3: 解析 import
        imports_pass = PassImports(self.graph)
        for go_file in go_files:
            try:
                source = go_file.read_text(encoding='utf-8', errors='ignore')
                rel_path = str(go_file.relative_to(self.repo_path.parent))
                imports_pass.run(rel_path, source, lang)
            except Exception:
                continue

        # Pass 4: 提取路由
        routes_pass = PassRoutes(self.graph)
        for go_file in go_files:
            try:
                source = go_file.read_text(encoding='utf-8', errors='ignore')
                rel_path = str(go_file.relative_to(self.repo_path.parent))
                routes_pass.run(rel_path, source, lang)
            except Exception:
                continue

        return self.graph

    def save(self, output_path: str):
        """保存图谱为 JSON"""
        self.graph.save_json(output_path)
        print(f"Graph saved to {output_path}")
        print(f"  Nodes: {len(self.graph.nodes)}")
        print(f"  Edges: {len(self.graph.edges)}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Build code knowledge graph")
    parser.add_argument('--repo-path', required=True, help='Repository root path')
    parser.add_argument('--project-name', default='default', help='Project name')
    parser.add_argument('--output', default='code_graph.json', help='Output file')
    parser.add_argument('--lang', default='go', help='Language (go, python, java)')
    parser.add_argument('--max-files', type=int, default=500, help='Max files to scan')
    args = parser.parse_args()

    builder = CodeGraphBuilder(args.project_name, args.repo_path)
    graph = builder.build(lang=args.lang, max_files=args.max_files)
    builder.save(args.output)

    # 打印统计
    labels = defaultdict(int)
    for node in graph.nodes:
        labels[node.label] += 1
    print("\nNode labels:")
    for label, count in sorted(labels.items()):
        print(f"  {label}: {count}")

    edge_types = defaultdict(int)
    for edge in graph.edges:
        edge_types[edge.type] += 1
    print("\nEdge types:")
    for etype, count in sorted(edge_types.items()):
        print(f"  {etype}: {count}")
