#!/usr/bin/env python3
"""
Graph Builder - 图谱构建器模块
从 learn_repo.py 拆分出来的图谱构建逻辑
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from code_parser import IRDocument


class GraphBuilder:
    """构建代码知识图谱"""
    
    def build_graph(self, ir: IRDocument) -> Dict:
        """构建完整图谱"""
        nodes = []
        edges = []
        
        # 添加结构体节点
        for struct in ir.structs:
            nodes.append({
                "id": f"struct_{struct.name}",
                "label": struct.name,
                "type": "struct",
                "file": struct.file,
                "properties": {
                    "fields": len(struct.fields),
                    "table_name": struct.table_name,
                }
            })
        
        # 添加函数节点
        for func in ir.functions:
            nodes.append({
                "id": f"func_{func.name}",
                "label": func.name,
                "type": "function",
                "file": func.file,
                "properties": {
                    "params": len(func.params),
                    "returns": func.returns,
                    "is_route": func.is_route,
                }
            })
        
        # 添加路由节点
        for route in ir.routes:
            nodes.append({
                "id": f"route_{route.path}",
                "label": f"{route.method} {route.path}",
                "type": "route",
                "file": route.file,
                "properties": {
                    "handler": route.handler,
                }
            })
        
        # 构建边
        for struct in ir.structs:
            for func in ir.functions:
                if struct.name in func.file or struct.name.lower() in func.name.lower():
                    edges.append({
                        "source": f"struct_{struct.name}",
                        "target": f"func_{func.name}",
                        "type": "USED_BY",
                    })
        
        for route in ir.routes:
            if route.handler:
                edges.append({
                    "source": f"route_{route.path}",
                    "target": f"func_{route.handler}",
                    "type": "CALLS",
                })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "structs": len(ir.structs),
                "functions": len(ir.functions),
                "routes": len(ir.routes),
            }
        }
    
    def save_graph(self, graph: Dict, output_path: Path):
        """保存图谱到文件"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(graph, f, indent=2, ensure_ascii=False)
        print(f"  ✅ Graph saved: {output_path}")
    
    def generate_prompt(self, graph: Dict, ir: IRDocument) -> str:
        """生成紧凑的 Prompt"""
        lines = []
        lines.append(f"# {ir.repo_name} 代码图谱")
        lines.append("")
        lines.append(f"**规模**: {graph['stats']['total_nodes']} 节点, {graph['stats']['total_edges']} 边")
        lines.append("")
        
        # 核心结构体
        lines.append("## 🔷 核心结构体")
        lines.append("")
        lines.append("| 名称 | 文件 | 字段数 | 表名 |")
        lines.append("|------|------|--------|------|")
        for struct in ir.structs[:20]:
            lines.append(f"| `{struct.name}` | {struct.file} | {len(struct.fields)} | {struct.table_name or '-'} |")
        lines.append("")
        
        # 核心函数
        lines.append("## 🔧 核心函数")
        lines.append("")
        lines.append("| 名称 | 文件 | 参数 | 返回 | 路由 |")
        lines.append("|------|------|------|------|------|")
        for func in ir.functions[:20]:
            lines.append(f"| `{func.name}` | {func.file} | {len(func.params)} | {func.returns or '-'} | {'✅' if func.is_route else ''} |")
        lines.append("")
        
        # 路由
        lines.append("## 🌐 路由列表")
        lines.append("")
        lines.append("| 方法 | 路径 | Handler |")
        lines.append("|------|------|---------|")
        for route in ir.routes[:20]:
            lines.append(f"| {route.method} | `{route.path}` | {route.handler} |")
        lines.append("")
        
        return '\n'.join(lines)
