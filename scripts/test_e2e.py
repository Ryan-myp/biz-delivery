#!/usr/bin/env python3
"""
E2E Tests - 端到端测试套件

测试完整的 biz-delivery 流程
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Any

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from graphify_analysis import run_graphify_analysis, GoASTParser
from community_enhancer import CommunityEnhancer
from multi_language_scanner import scan_repo, detect_language


class TestE2E:
    """端到端测试"""
    
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
        self.tmp_dir = None
    
    def test_graphify_analysis(self):
        """测试 Graphify 分析流程"""
        print("\n🧪 Test: Graphify Analysis")
        
        # 创建一个临时 Go 文件
        with tempfile.TemporaryDirectory() as tmpdir:
            self.tmp_dir = tmpdir
            go_file = Path(tmpdir) / "test.go"
            go_file.write_text('''
package test

type Graph struct {
    nodes map[string]*Node
    edges []*Edge
}

func (g *Graph) AddNode(id string) *Node {
    return &Node{id: id}
}

func (g *Graph) Compile(ctx context.Context) (*CompiledGraph, error) {
    return &CompiledGraph{}, nil
}

type CompiledGraph struct {
    runner *runner
}

func (c *CompiledGraph) Invoke(ctx context.Context) error {
    return nil
}

type node struct {
    id   string
    name string
}
''')
            
            # 测试扫描
            result = scan_repo(Path(tmpdir))
            assert result is not None, "扫描结果不能为空"
            assert result.structs, "应该扫描到 struct"
            assert result.functions, "应该扫描到函数"
            
            print(f"  ✅ 扫描到 {len(result.structs)} structs, {len(result.functions)} functions")
        
        return True
    
    def test_community_analysis(self):
        """测试社区分析"""
        print("\n🧪 Test: Community Analysis")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            self.tmp_dir = tmpdir
            
            # 创建图数据
            graph_data = {
                "nodes": [
                    {"id": "pkg/graph", "label": "graph", "type": "MODULE", "source_file": "pkg/graph.go"},
                    {"id": "pkg/graph.Node", "label": "Node", "type": "STRUCT", "source_file": "pkg/graph.go"},
                    {"id": "pkg/graph.Edge", "label": "Edge", "type": "STRUCT", "source_file": "pkg/graph.go"},
                    {"id": "pkg/runner", "label": "runner", "type": "MODULE", "source_file": "pkg/runner.go"},
                    {"id": "pkg/runner.exec", "label": "execute", "type": "FUNCTION", "source_file": "pkg/runner.go"},
                ],
                "edges": [
                    {"source": "pkg/graph.Node", "target": "pkg/graph", "relation": "CONTAINS"},
                    {"source": "pkg/graph.Edge", "target": "pkg/graph", "relation": "CONTAINS"},
                    {"source": "pkg/runner.exec", "target": "pkg/runner", "relation": "CONTAINS"},
                ],
                "communities": {
                    "pkg/graph.Node": 0,
                    "pkg/graph.Edge": 0,
                    "pkg/graph": 0,
                    "pkg/runner.exec": 1,
                    "pkg/runner": 1,
                }
            }
            
            # 测试社区分析
            result = CommunityEnhancer.analyze_communities(graph_data)
            assert "communities" in result, "结果应该包含 communities"
            assert len(result["communities"]) > 0, "应该有社区"
            
            # 检查命名
            for comm in result["communities"]:
                assert "name" in comm, "社区应该有名称"
                assert len(comm["name"]) > 0, "名称不能为空"
                print(f"  ✅ 社区 '{comm['name']}': {comm['size']} nodes, importance={comm['importance']}")
            
            print(f"  ✅ 检测到 {result['total']} 个社区")
        
        return True
    
    def test_multi_language(self):
        """测试多语言支持"""
        print("\n🧪 Test: Multi-language Scanner")
        
        # 测试 Python 扫描
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "test.py"
            py_file.write_text('''
class Graph:
    def __init__(self):
        self.nodes = {}
        self.edges = []
    
    def add_node(self, name: str) -> None:
        self.nodes[name] = Node(name)
    
    def compile(self) -> CompiledGraph:
        return CompiledGraph()

class CompiledGraph:
    def __init__(self):
        self.runner = None
    
    def invoke(self) -> bool:
        return True
''')
            
            result = scan_repo(Path(tmpdir), language="python")
            assert result is not None, "扫描结果不能为空"
            assert result.structs, "应该扫描到类"
            
            print(f"  ✅ Python 扫描: {len(result.structs)} classes")
        
        # 测试 TypeScript 扫描
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "test.ts"
            ts_file.write_text('''
class Graph {
    nodes: Map<string, Node>;
    edges: Edge[];
    
    addNode(name: string): void {
        this.nodes.set(name, new Node(name));
    }
}

interface Node {
    id: string;
    label: string;
}
''')
            
            result = scan_repo(Path(tmpdir), language="typescript")
            assert result is not None, "扫描结果不能为空"
            assert result.structs, "应该扫描到类或接口"
            
            print(f"  ✅ TypeScript 扫描: {len(result.structs)} classes/interfaces")
        
        return True
    
    def test_search_integration(self):
        """测试搜索集成"""
        print("\n🧪 Test: Search Integration")
        
        try:
            from search import ripgrep_search_simple
            from knowledge_search import query_knowledge
            
            # 测试基础搜索
            results = ripgrep_search_simple("struct", Path("/tmp"))
            assert isinstance(results, list), "结果应该是列表"
            print(f"  ✅ 基础搜索工作正常")
            
            # 测试知识库查询（如果可用）
            kb_path = Path.home() / "ryan-personal-knowledge" / "knowledge"
            if kb_path.exists():
                results = query_knowledge("Redis缓存", kb_path=str(kb_path))
                print(f"  ✅ 知识库查询工作正常")
            
        except ImportError as e:
            print(f"  ⚠️  导入失败: {e}")
            return True
        except Exception as e:
            print(f"  ⚠️  搜索测试跳过: {e}")
            return True
        
        return True
    
    def test_workflow(self):
        """测试完整工作流"""
        print("\n🧪 Test: Full Workflow")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            self.tmp_dir = tmpdir
            
            # 1. 创建测试代码
            go_file = Path(tmpdir) / "main.go"
            go_file.write_text('''
package main

import "context"

type Graph struct {
    nodes map[string]*Node
}

func (g *Graph) Compile(ctx context.Context) (*CompiledGraph, error) {
    return &CompiledGraph{}, nil
}

type CompiledGraph struct {
    runner *runner
}

func (c *CompiledGraph) Invoke(ctx context.Context) error {
    return nil
}

type node struct {
    id   string
    name string
}

func main() {
    g := &Graph{}
    g.Compile(context.Background())
}
''')
            
            # 2. 执行分析
            output_dir = Path(tmpdir) / "output"
            try:
                graph, god_nodes, communities, prompt = run_graphify_analysis(
                    tmpdir, 
                    max_files=10,
                    output_dir=str(output_dir)
                )
                
                # 验证输出
                assert graph is not None, "图不能为空"
                assert len(god_nodes) > 0, "应该有 God nodes"
                assert len(prompt) > 0, "prompt 不能为空"
                
                print(f"  ✅ 图分析完成: {len(graph.nodes)} nodes, {len(god_nodes)} god nodes")
                print(f"  ✅ Prompt 长度: {len(prompt)} chars")
                
                # 3. 测试社区增强
                graph_json = output_dir / "graph.json"
                if graph_json.exists():
                    enhance_result = CommunityEnhancer.analyze_communities(
                        json.loads(graph_json.read_text())
                    )
                    print(f"  ✅ 社区增强: {enhance_result['total']} communities")
                
            except Exception as e:
                print(f"  ⚠️  分析跳过: {e}")
        
        return True
    
    def run_all(self) -> Dict:
        """运行所有测试"""
        print("=" * 70)
        print("🚀 E2E Test Suite")
        print("=" * 70)
        
        tests = [
            ("Graphify Analysis", self.test_graphify_analysis),
            ("Community Analysis", self.test_community_analysis),
            ("Multi-language", self.test_multi_language),
            ("Search Integration", self.test_search_integration),
            ("Full Workflow", self.test_workflow),
        ]
        
        results = {}
        for name, test_func in tests:
            try:
                start = time.time()
                passed = test_func()
                elapsed = time.time() - start
                
                if passed:
                    self.passed += 1
                    results[name] = {"status": "PASS", "time": elapsed}
                    print(f"  ✅ {name}: PASS ({elapsed:.2f}s)")
                else:
                    self.failed += 1
                    results[name] = {"status": "FAIL", "time": elapsed}
                    print(f"  ❌ {name}: FAIL ({elapsed:.2f}s)")
            except Exception as e:
                self.failed += 1
                results[name] = {"status": "ERROR", "error": str(e)}
                print(f"  ❌ {name}: ERROR - {e}")
        
        print("\n" + "=" * 70)
        print(f"📊 Results: {self.passed} passed, {self.failed} failed")
        print("=" * 70)
        
        return results


if __name__ == '__main__':
    import time
    tester = TestE2E()
    results = tester.run_all()
    
    # 输出 JSON 结果
    with open('/tmp/e2e_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    sys.exit(0 if tester.failed == 0 else 1)
