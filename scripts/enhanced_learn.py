#!/usr/bin/env python3
"""
Enhanced Learn Pipeline — 基于代码图谱的智能学习
整合 Graphify 思路：
1. 构建代码图谱（Nodes + Edges）
2. 识别关键节点（高中心性、入口点）
3. 提取关键代码片段
4. 生成增强 prompt
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter

# 导入现有组件
from learn_repo import GoScanner, IRDocument, StructDef, FuncDef
from code_graph_builder import CodeGraphBuilder, GoParser


class EnhancedLearnPipeline:
    """增强版学习管道 — 图谱 + 代码片段"""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.scanner = GoScanner()
        self.graph_builder = CodeGraphBuilder()

    def run(self, max_files: int = 100) -> Tuple[IRDocument, CodeGraphBuilder, List[Dict]]:
        """运行增强学习管道
        
        Returns:
            (ir_document, graph, key_snippets)
        """
        print(f"🔍 扫描代码库: {self.repo_path}")
        
        # 1. 提取 IR
        ir = self.scanner.scan_directory(self.repo_path, max_files=max_files)
        print(f"  ✓ IR: {len(ir.structs)} structs, {len(ir.functions)} functions")
        
        # 2. 构建代码图谱
        print(f"🕸️  构建代码图谱...")
        graph = self.graph_builder.build_graph(self.repo_path, max_files=max_files)
        print(f"  ✓ 图谱: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        
        # 3. 识别关键节点
        print(f"🎯 识别关键节点...")
        key_nodes = self._identify_key_nodes(graph, ir)
        print(f"  ✓ 关键节点: {len(key_nodes)}")
        
        # 4. 提取关键代码片段
        print(f"📝 提取关键代码片段...")
        snippets = self._extract_key_snippets(graph, ir, key_nodes)
        print(f"  ✓ 代码片段: {len(snippets)}")
        
        return ir, graph, snippets

    def _identify_key_nodes(self, graph, ir: IRDocument) -> List[Dict]:
        """识别关键节点（高中心性、入口点）"""
        # 计算节点度中心性
        node_degree = defaultdict(int)
        for edge in graph.edges:
            node_degree[edge.source_id] += 1
            node_degree[edge.target_id] += 1
        
        # 找入口点（出度 > 入度）
        in_degree = defaultdict(int)
        out_degree = defaultdict(int)
        for edge in graph.edges:
            out_degree[edge.source_id] += 1
            in_degree[edge.target_id] += 1
        
        entry_points = []
        for nid in node_degree:
            node = graph.find_by_id(nid)
            if not node:
                continue
            
            # 入口点：出度 > 入度 且 是 Function/Method
            if (node.label in ('Function', 'Method') and 
                out_degree[nid] > in_degree[nid] and
                out_degree[nid] >= 2):
                entry_points.append({
                    'id': nid,
                    'name': node.name,
                    'label': node.label,
                    'file': node.file_path,
                    'out_degree': out_degree[nid],
                    'in_degree': in_degree[nid],
                    'type': 'entry_point',
                })
        
        # 找高连接度节点（hub）
        hubs = []
        for nid, degree in sorted(node_degree.items(), key=lambda x: x[1], reverse=True)[:15]:
            node = graph.find_by_id(nid)
            if not node or node.label not in ('Function', 'Method', 'Struct'):
                continue
            hubs.append({
                'id': nid,
                'name': node.name,
                'label': node.label,
                'file': node.file_path,
                'degree': degree,
                'type': 'hub',
            })
        
        # 找核心接口（有方法的 struct）
        interfaces = []
        for s in ir.structs:
            if s.methods and len(s.methods) >= 2:
                interfaces.append({
                    'name': s.name,
                    'label': 'Interface',
                    'file': s.file,
                    'methods': len(s.methods),
                    'fields': len(s.fields),
                    'type': 'interface',
                })
        
        # 合并并去重
        seen = set()
        key_nodes = []
        for node in entry_points + hubs[:5] + interfaces[:5]:
            key = node.get('name') or node.get('id')
            if key not in seen:
                seen.add(key)
                key_nodes.append(node)
        
        return key_nodes[:20]

    def _extract_key_snippets(self, graph, ir: IRDocument, key_nodes: List[Dict]) -> List[Dict]:
        """提取关键节点的代码片段"""
        snippets = []
        seen = set()
        
        for node in key_nodes:
            name = node.get('name') or str(node.get('id'))
            if name in seen:
                continue
            seen.add(name)
            
            file_path = node.get('file')
            if not file_path:
                continue
            
            full_path = self.repo_path / file_path
            if not full_path.exists():
                # 尝试去掉仓库名前缀
                parts = Path(file_path).parts
                if len(parts) > 1:
                    full_path = self.repo_path / Path(*parts[1:])
                if not full_path.exists():
                    continue
            
            try:
                content = full_path.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            
            # 提取代码片段
            snippet = self._extract_node_snippet(content, node, ir)
            if snippet and snippet['code']:
                snippets.append(snippet)
        
        return snippets

    def _extract_node_snippet(self, content: str, node: Dict, ir: IRDocument) -> Optional[Dict]:
        """从源码中提取节点对应的代码片段"""
        name = node.get('name', '')
        node_type = node.get('type', '')
        
        if not name:
            return None
        
        # 1. 提取 struct 定义
        if node_type == 'interface' or (node.get('fields') and node.get('methods')):
            # 找 type XXX struct { ... }
            pattern = rf'type\s+{re.escape(name)}\s+struct\s*\{{'
            match = re.search(pattern, content)
            if match:
                start = match.start()
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
                
                # 提取方法
                methods = []
                for m in re.finditer(r'func\s+\(\s*\*?\s*' + re.escape(name) + r'\s+\w+\s*\)\s+(\w+)\s*\(', content):
                    methods.append(m.group(1))
                
                return {
                    'name': name,
                    'type': 'struct',
                    'file': node.get('file', ''),
                    'fields': node.get('fields', []),
                    'methods': methods,
                    'code': content[start:end].strip(),
                }
        
        # 2. 提取 interface 定义
        if node_type == 'interface' or (node.get('methods') and not node.get('fields')):
            pattern = rf'type\s+{re.escape(name)}\s+interface\s*\{{'
            match = re.search(pattern, content)
            if match:
                start = match.start()
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
                return {
                    'name': name,
                    'type': 'interface',
                    'file': node.get('file', ''),
                    'methods': node.get('methods', []),
                    'code': content[start:end].strip(),
                }
        
        # 3. 提取方法实现
        if node_type in ('entry_point', 'hub'):
            # 找 func (receiver) Method( 或 func Method(
            pattern = rf'func\s+\(.*?\{re.escape(name)}\s+.*?\)\s+{re.escape(name)}\s*\(|func\s+{re.escape(name)}\s*\('
            match = re.search(pattern, content)
            if match:
                start = match.start()
                # 找函数体结束
                end = self._find_func_end(content, start)
                return {
                    'name': name,
                    'type': 'function',
                    'file': node.get('file', ''),
                    'code': content[start:end].strip(),
                }
        
        return None

    def _find_func_end(self, content: str, start: int) -> int:
        """找到函数体结束位置"""
        # 找 Opening brace
        brace_pos = content.find('{', start)
        if brace_pos == -1:
            return start + 200
        
        brace_count = 0
        for i in range(brace_pos, len(content)):
            if content[i] == '{':
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    return i + 1
        
        return min(start + 500, len(content))

    def generate_enhanced_prompt(self, ir: IRDocument, graph, snippets: List[Dict]) -> str:
        """生成增强版 prompt"""
        lines = []
        
        # 头部
        lines.append("# 代码库深度学习任务")
        lines.append("")
        lines.append("你是一个资深软件架构师。请基于以下**代码图谱**和**关键代码片段**，")
        lines.append("深入理解这个系统的架构、核心流程和关键实现。")
        lines.append("")
        
        # 1. 图谱概览
        lines.append("## 📊 代码图谱概览")
        lines.append("")
        lines.append(f"- **Nodes**: {len(graph.nodes)}")
        lines.append(f"- **Edges**: {len(graph.edges)}")
        
        # 节点类型统计
        label_counts = Counter(n.label for n in graph.nodes)
        lines.append(f"- **Node types**: {dict(label_counts)}")
        
        # 边类型统计
        edge_counts = Counter(e.type for e in graph.edges)
        lines.append(f"- **Edge types**: {dict(edge_counts)}")
        lines.append("")
        
        # 2. 核心接口/结构体
        lines.append("## 🔑 核心接口与结构体")
        lines.append("")
        
        # 找有方法的 struct
        important_structs = [s for s in ir.structs if s.methods and len(s.methods) >= 2]
        important_structs.sort(key=lambda x: len(x.methods), reverse=True)
        
        for s in important_structs[:5]:
            lines.append(f"### `{s.name}`")
            lines.append(f"- File: `{s.file}`")
            if s.fields:
                field_names = [f['name'] for f in s.fields[:5]]
                lines.append(f"- Fields: {', '.join(field_names)}")
            if s.methods:
                method_names = [m['name'] for m in s.methods[:5]]
                lines.append(f"- Methods: {', '.join(method_names)}")
            lines.append("")
        
        # 3. 关键代码片段
        if snippets:
            lines.append("## 💻 关键代码片段")
            lines.append("")
            lines.append("**以下是系统中最重要的代码实现，请仔细阅读：**")
            lines.append("")
            
            for i, s in enumerate(snippets[:8], 1):
                lines.append(f"### {i}. {s['name']} ({s['type']})")
                lines.append(f"**File:** `{s['file']}`")
                lines.append("")
                
                if s.get('fields'):
                    lines.append("**Fields:**")
                    for f in s['fields'][:6]:
                        tag = f" `{f.get('tag', '')}`" if f.get('tag') else ""
                        lines.append(f"- `{f['name']}`: {f['type']}{tag}")
                    lines.append("")
                
                if s.get('methods'):
                    lines.append("**Methods:**")
                    for m in s['methods'][:5]:
                        lines.append(f"- `{m}`")
                    lines.append("")
                
                if s.get('code'):
                    lines.append("**Code:**")
                    lines.append("```go")
                    lines.append(s['code'])
                    lines.append("```")
                    lines.append("")
        
        # 4. 任务要求
        lines.append("## 📋 任务要求")
        lines.append("")
        lines.append("基于以上代码图谱和关键实现，请深入分析：")
        lines.append("")
        lines.append("1. **架构设计**：系统采用什么架构模式？核心组件如何交互？")
        lines.append("2. **核心流程**：关键业务流程是什么？数据如何流转？")
        lines.append("3. **扩展点**：系统的扩展机制是什么？如何添加新功能？")
        lines.append("4. **设计决策**：有哪些值得注意的技术选型和权衡？")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("**重要**：以上代码片段是系统的核心实现，请仔细理解后再进行分析。")
        
        return '\n'.join(lines)


def main():
    """主函数"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python enhanced_learn.py <repo_path>")
        sys.exit(1)
    
    repo_path = sys.argv[1]
    max_files = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    
    pipeline = EnhancedLearnPipeline(repo_path)
    ir, graph, snippets = pipeline.run(max_files=max_files)
    
    # 生成 prompt
    prompt = pipeline.generate_enhanced_prompt(ir, graph, snippets)
    
    # 输出
    print("\n" + "=" * 70)
    print("增强版 Prompt 生成完成")
    print("=" * 70)
    print(f"Structs: {len(ir.structs)}, Functions: {len(ir.functions)}")
    print(f"Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    print(f"Snippets: {len(snippets)}")
    print(f"\nPrompt length: {len(prompt)} chars")
    
    # 保存到文件
    output_path = Path(repo_path).parent / 'enhanced_prompt.md'
    output_path.write_text(prompt, encoding='utf-8')
    print(f"\nSaved to: {output_path}")


if __name__ == '__main__':
    main()
