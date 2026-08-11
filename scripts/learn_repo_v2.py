#!/usr/bin/env python3
"""
Learn Repo - 主入口模块
重组后的代码学习引擎，模块化设计
"""

import argparse
import json
import hashlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from code_parser import IRDocument, StructDef, FuncDef, RouteDef, ImportDef
from go_scanner import GoScanner
from knowledge_extractor import KnowledgeExtractor
from graph_builder import GraphBuilder
from output_writer import OutputWriter


class CodeKnowledgeEngine:
    """代码知识提取引擎 - 模块化设计"""
    
    def __init__(self, repo_path: str, language: str = "go"):
        self.repo_path = Path(repo_path)
        self.language = language
        self.scanner = GoScanner()
        self.extractor = KnowledgeExtractor()
        self.graph_builder = GraphBuilder()
        self.output_writer = OutputWriter()
    
    def extract(self) -> Dict[str, Any]:
        """提取代码知识"""
        print(f"\n🔍 开始分析仓库: {self.repo_path}")
        print(f"   语言: {self.language}")
        
        # 1. 扫描代码
        print("\n📊 步骤1: 扫描代码...")
        ir_document = self.scanner.scan_directory(self.repo_path)
        print(f"   ✅ 扫描完成: {len(ir_document.structs)} 结构体, {len(ir_document.functions)} 函数, {len(ir_document.routes)} 路由")
        
        # 2. 提取知识
        print("\n🧠 步骤2: 提取知识...")
        ir_document = self.extractor.extract_all(ir_document, self.repo_path)
        print(f"   ✅ 知识提取完成")
        
        # 3. 构建图谱
        print("\n🕸️ 步骤3: 构建图谱...")
        graph = self.graph_builder.build_graph(ir_document)
        print(f"   ✅ 图谱构建完成: {graph['stats']['total_nodes']} 节点, {graph['stats']['total_edges']} 边")
        
        # 4. 返回结果
        return {
            "ir_document": ir_document.to_dict(),
            "graph": graph,
            "stats": {
                "structs": len(ir_document.structs),
                "functions": len(ir_document.functions),
                "routes": len(ir_document.routes),
                "nodes": graph['stats']['total_nodes'],
                "edges": graph['stats']['total_edges'],
            }
        }
    
    def run(self, output_dir: str = None) -> Dict:
        """运行完整流程"""
        result = self.extract()
        
        if output_dir:
            output_path = Path(output_dir)
            # 保存 IR Document
            self.output_writer.write_ir_document(result["ir_document"], output_path)
            # 保存图谱
            self.output_writer.write_ir_document(result["graph"], output_path / "graph")
            # 保存总结
            self.output_writer.write_summary(result["stats"], output_path)
        
        return result


def main():
    """CLI入口"""
    parser = argparse.ArgumentParser(description='代码知识提取引擎')
    parser.add_argument('--repo', required=True, help='仓库路径')
    parser.add_argument('--lang', default='go', help='编程语言 (默认: go)')
    parser.add_argument('--output', help='输出目录')
    
    args = parser.parse_args()
    
    engine = CodeKnowledgeEngine(args.repo, args.lang)
    result = engine.run(args.output)
    
    print("\n✅ 分析完成!")
    print(json.dumps(result["stats"], indent=2))


if __name__ == '__main__':
    main()
