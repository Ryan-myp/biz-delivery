#!/usr/bin/env python3
"""
Graphify-style Learn Pipeline — 图谱 + 关键代码片段
核心思路：
1. 构建代码图谱（节点 + 边）
2. 用图中心性识别关键节点（不是所有节点都重要）
3. 只提取关键节点的代码片段（节省 70% token）
4. 生成紧凑的 prompt（图结构 + 少量关键代码）
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter

from learn_repo import GoScanner, IRDocument
from code_graph_builder import CodeGraphBuilder, CodeGraph


class GraphifyLearnPipeline:
    """Graphify 风格学习管道"""

    def __init__(self, repo_path: str, project_name: Optional[str] = None):
        self.repo_path = Path(repo_path)
        self.project_name = project_name or self.repo_path.name
        self.scanner = GoScanner()
        self.graph_builder = CodeGraphBuilder(self.project_name, repo_path)

    def run(self, max_files: int = 100, key_node_budget: int = 15) -> Tuple[IRDocument, CodeGraph, List[Dict]]:
        """运行 Graphify 学习管道

        Args:
            max_files: 扫描的最大文件数
            key_node_budget: 最多提取多少个关键节点的代码
        """
        print(f"🔍 Graphify Learn: {self.repo_path}")

        # 1. 提取 IR（结构信息）
        ir = self.scanner.scan_directory(self.repo_path, max_files=max_files)
        print(f"  ✓ IR: {len(ir.structs)} structs, {len(ir.functions)} functions")

        # 2. 构建代码图谱
        print(f"🕸️  构建代码图谱...")
        graph = self.graph_builder.build(lang='go', max_files=max_files)
        print(f"  ✓ 图谱: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

        # 3. 识别关键节点（图中心性）
        print(f"🎯 识别关键节点 (budget={key_node_budget})...")
        key_nodes = self._identify_key_nodes(graph, ir, max_count=key_node_budget)
        print(f"  ✓ 关键节点: {len(key_nodes)}")

        # 4. 提取关键代码片段
        print(f"📝 提取关键代码片段...")
        snippets = self._extract_key_snippets(graph, ir, key_nodes)
        print(f"  ✓ 代码片段: {len(snippets)}")

        return ir, graph, snippets

    def _identify_key_nodes(self, graph: CodeGraph, ir: IRDocument, max_count: int = 15) -> List[Dict]:
        """用图中心性识别关键节点

        策略：
        1. 出度高的节点（被很多人调用）= 核心接口
        2. 入度高的节点（调用很多人）= 业务逻辑入口
        3. 有方法的 struct = 核心领域对象
        """
        # 计算度中心性
        in_degree = defaultdict(int)
        out_degree = defaultdict(int)
        for edge in graph.edges:
            out_degree[edge.source_id] += 1
            in_degree[edge.target_id] += 1

        # 计算综合评分
        node_scores = []
        for node in graph.nodes:
            if node.label not in ('Function', 'Method', 'Struct', 'Interface'):
                continue

            nid = node.id
            in_d = in_degree[nid]
            out_d = out_degree[nid]

            # 核心接口：出度 > 入度（被很多人用）
            # 业务入口：入度 > 出度（调用很多人）
            # 核心领域：有方法 + 有字段
            score = 0
            node_type = 'unknown'

            if out_d >= 3 and out_d > in_d:
                score = out_d * 2  # 核心接口权重高
                node_type = 'core_interface'
            elif in_d >= 2 and in_d > out_d:
                score = in_d * 1.5  # 业务入口
                node_type = 'business_entry'
            elif node.label in ('Struct', 'Interface'):
                # 找对应的 IR struct
                ir_struct = next((s for s in ir.structs if s.name == node.name), None)
                if ir_struct:
                    method_count = len(ir_struct.methods) if ir_struct.methods else 0
                    field_count = len(ir_struct.fields) if ir_struct.fields else 0
                    if method_count >= 2:
                        score = method_count * 2 + field_count
                        node_type = 'domain_object'

            if score > 0:
                node_scores.append({
                    'id': nid,
                    'name': node.name,
                    'label': node.label,
                    'file': node.file_path,
                    'in_degree': in_d,
                    'out_degree': out_d,
                    'score': score,
                    'type': node_type,
                })

        # 按评分排序，取 top N
        node_scores.sort(key=lambda x: x['score'], reverse=True)
        return node_scores[:max_count]

    def _extract_key_snippets(self, graph: CodeGraph, ir: IRDocument, key_nodes: List[Dict]) -> List[Dict]:
        """提取关键节点的代码片段"""
        snippets = []
        seen = set()

        for node in key_nodes:
            name = node['name']
            if name in seen:
                continue
            seen.add(name)

            file_path = node.get('file', '')
            if not file_path:
                continue

            # 解析路径（处理可能的重复前缀）
            full_path = self._resolve_path(file_path)
            if not full_path.exists():
                continue

            try:
                content = full_path.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue

            # 根据节点类型提取代码
            snippet = self._extract_by_type(content, node, ir)
            if snippet and snippet.get('code'):
                snippets.append(snippet)

        return snippets

    def _resolve_path(self, file_path: str) -> Path:
        """解析文件路径，处理重复前缀"""
        if not file_path:
            return Path()

        # 尝试直接拼接
        filepath = self.repo_path / file_path
        if filepath.exists():
            return filepath

        # 尝试去掉仓库名前缀
        parts = Path(file_path).parts
        if len(parts) > 1:
            filepath2 = self.repo_path / Path(*parts[1:])
            if filepath2.exists():
                return filepath2

        return filepath

    def _extract_by_type(self, content: str, node: Dict, ir: IRDocument) -> Optional[Dict]:
        """根据节点类型提取代码"""
        name = node['name']
        node_type = node.get('type', '')

        # 1. 核心接口/领域对象：提取 struct 定义 + 方法
        if node_type in ('core_interface', 'domain_object'):
            # 找 struct 定义
            struct_pattern = rf'type\s+{re.escape(name)}\s+struct\s*\{{'
            struct_match = re.search(struct_pattern, content)

            # 找 interface 定义
            interface_pattern = rf'type\s+{re.escape(name)}\s+interface\s*\{{'
            interface_match = re.search(interface_pattern, content)

            if struct_match:
                return self._extract_struct_snippet(content, struct_match, name, node, ir)
            elif interface_match:
                return self._extract_interface_snippet(content, interface_match, name, node, ir)

        # 2. 业务入口：提取函数实现
        elif node_type == 'business_entry':
            # 找 func Name( 或 func (receiver) Name(
            func_pattern = rf'func\s+\(.*?\){re.escape(name)}\s*\(|func\s+{re.escape(name)}\s*\('
            func_match = re.search(func_pattern, content)
            if func_match:
                start = func_match.start()
                end = self._find_func_end(content, start)
                return {
                    'name': name,
                    'type': 'function',
                    'file': node.get('file', ''),
                    'code': content[start:end].strip(),
                    'docstring': self._extract_docstring(content, start),
                }

        return None

    def _extract_struct_snippet(self, content: str, match, name: str, node: Dict, ir: IRDocument) -> Dict:
        """提取 struct 定义 + 方法"""
        start = match.start()

        # 找 struct 结束
        brace_count = 0
        end = start
        for i, c in enumerate(content[start:], start):
            if c == '{':
                brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break

        # 找该方法的所有方法
        methods = []
        method_code = []
        method_pattern = rf'func\s+\(\s*\*?\s*{re.escape(name)}\s+\w+\s*\)\s+(\w+)\s*\('
        for m in re.finditer(method_pattern, content):
            methods.append(m.group(1))
            method_start = m.start()
            method_end = self._find_func_end(content, method_start)
            method_code.append(content[method_start:method_end].strip())

        # 从 IR 获取字段信息
        ir_struct = next((s for s in ir.structs if s.name == name), None)
        fields = ir_struct.fields if ir_struct and ir_struct.fields else []

        # 组合代码：struct 定义 + 前3个方法
        full_code = content[start:end]
        if method_code[:3]:
            full_code += '\n\n' + '\n\n'.join(method_code[:3])

        return {
            'name': name,
            'type': 'struct',
            'file': node.get('file', ''),
            'fields': fields[:8],
            'methods': methods[:10],
            'code': full_code[:1500],  # 限制长度
        }

    def _extract_interface_snippet(self, content: str, match, name: str, node: Dict, ir: IRDocument) -> Dict:
        """提取 interface 定义"""
        start = match.start()

        # 找 interface 结束
        brace_count = 0
        end = start
        for i, c in enumerate(content[start:], start):
            if c == '{':
                brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break

        # 找实现该 interface 的 struct
        impl_pattern = rf'func\s+\(.*?\)\s+{name}\s*\('
        implementations = []
        for m in re.finditer(impl_pattern, content):
            # 找方法名
            method_match = re.search(r'func\s+\(.*?\)\s+(\w+)\s*\(', content[m.start():m.start()+100])
            if method_match:
                implementations.append(method_match.group(1))

        return {
            'name': name,
            'type': 'interface',
            'file': node.get('file', ''),
            'methods': implementations[:10],
            'code': content[start:end].strip(),
        }

    def _find_func_end(self, content: str, start: int) -> int:
        """找到函数体结束位置"""
        brace_pos = content.find('{', start)
        if brace_pos == -1:
            return min(start + 300, len(content))

        brace_count = 0
        for i in range(brace_pos, len(content)):
            if content[i] == '{':
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    return i + 1

        return min(start + 500, len(content))

    def _extract_docstring(self, content: str, pos: int) -> str:
        """提取注释"""
        # 向前查找注释
        for i in range(pos - 1, max(0, pos - 50), -1):
            if content[i:i+2] == '//':
                end = content.find('\n', i)
                return content[i:end].strip()
        return ''

    def generate_compact_prompt(self, ir: IRDocument, graph: CodeGraph, snippets: List[Dict]) -> str:
        """生成紧凑 prompt（节省 70% token）

        策略：
        1. 只保留图结构摘要（不保留完整代码）
        2. 只保留关键节点的代码片段
        3. 移除冗余信息
        """
        lines = []

        # 头部（精简）
        lines.append(f"# {self.project_name} 代码分析")
        lines.append("")
        lines.append(f"**图谱规模**: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        lines.append(f"**代码库规模**: {len(ir.structs)} structs, {len(ir.functions)} functions")
        lines.append("")

        # 1. 图结构摘要（压缩表示）
        lines.append("## 📊 核心架构")
        lines.append("")

        # 节点类型统计
        label_counts = Counter(n.label for n in graph.nodes)
        lines.append("**节点类型**: " + ", ".join(f"{k}({v})" for k, v in list(label_counts.items())[:5]))

        # 边类型统计
        edge_counts = Counter(e.type for e in graph.edges)
        lines.append("**连接关系**: " + ", ".join(f"{k}({v})" for k, v in list(edge_counts.items())))
        lines.append("")

        # 2. 关键接口（只列名字，不展开）
        lines.append("## 🔑 核心接口与领域对象")
        lines.append("")

        # 找出有方法的 struct
        important = []
        for s in ir.structs:
            if s.methods and len(s.methods) >= 2:
                important.append({
                    'name': s.name,
                    'methods': [m['name'] for m in s.methods[:3]],
                    'fields': len(s.fields),
                })

        important.sort(key=lambda x: len(x['methods']), reverse=True)

        for item in important[:8]:
            lines.append(f"- **`{item['name']}`**: {', '.join(item['methods'])} ({item['fields']} fields)")
        lines.append("")

        # 3. 关键代码片段（只保留最核心的）
        if snippets:
            lines.append("## 💻 关键实现")
            lines.append("")
            lines.append("*以下是系统核心实现，仔细阅读：*")
            lines.append("")

            for i, s in enumerate(snippets[:6], 1):
                lines.append(f"### {i}. `{s['name']}` ({s['type']})")
                lines.append(f"**File**: `{s['file']}`")
                lines.append("")

                # 只展示字段和方法签名（不展示实现细节）
                if s.get('fields'):
                    lines.append("**Fields**:")
                    for f in s['fields'][:5]:
                        lines.append(f"- `{f['name']}`: `{f['type']}`")
                    lines.append("")

                if s.get('methods'):
                    lines.append("**Methods**:")
                    for m in s['methods'][:5]:
                        lines.append(f"- `{m}`")
                    lines.append("")

                # 只展示核心代码片段（限制长度）
                if s.get('code'):
                    code = s['code'][:800]  # 限制 800 字符
                    lines.append("**Core Code**:")
                    lines.append("```go")
                    lines.append(code)
                    lines.append("```")
                    lines.append("")

        # 4. 任务（精简）
        lines.append("## 📋 分析任务")
        lines.append("")
        lines.append("请基于以上代码图谱和关键实现，回答以下问题：")
        lines.append("1. 系统的核心架构模式是什么？")
        lines.append("2. 数据如何流转？关键流程有哪些？")
        lines.append("3. 系统的扩展点在哪里？")
        lines.append("")

        return '\n'.join(lines)


def main():
    """主函数"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python graphify_learn.py <repo_path> [max_files]")
        sys.exit(1)

    repo_path = sys.argv[1]
    max_files = int(sys.argv[2]) if len(sys.argv) > 2 else 100

    pipeline = GraphifyLearnPipeline(repo_path)
    ir, graph, snippets = pipeline.run(max_files=max_files, key_node_budget=15)

    # 生成紧凑 prompt
    prompt = pipeline.generate_compact_prompt(ir, graph, snippets)

    # 输出统计
    print("\n" + "=" * 70)
    print("Graphify Learn 完成")
    print("=" * 70)
    print(f"Structs: {len(ir.structs)}, Functions: {len(ir.functions)}")
    print(f"Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    print(f"Key snippets: {len(snippets)}")
    print(f"Prompt length: {len(prompt)} chars")

    # 保存到文件
    output_path = Path(repo_path) / 'graphify_prompt.md'
    output_path.write_text(prompt, encoding='utf-8')
    print(f"\nSaved to: {output_path}")

    # 打印 prompt 预览
    print("\n" + "=" * 70)
    print("Prompt Preview:")
    print("=" * 70)
    print(prompt[:2000])
    if len(prompt) > 2000:
        print(f"\n... (truncated, total {len(prompt)} chars)")


if __name__ == '__main__':
    main()
