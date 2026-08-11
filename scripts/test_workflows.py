#!/usr/bin/env python3
"""
集成测试 - 5个工作流
"""

import unittest
import tempfile
import json
from pathlib import Path
import sys


class TestWorkflow(unittest.TestCase):
    """测试完整工作流"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="workflow-test-"))
        self.bsd_dir = Path(__file__).parent.parent / "scripts"
        sys.path.insert(0, str(self.bsd_dir))
    
    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_workflow_graphify_analysis(self):
        """工作流1: Graphify分析"""
        from graphify_analysis import run_graphify_analysis
        
        # 使用已有的Eino项目
        eino_path = Path("/tmp/eino")
        if not eino_path.exists():
            self.skipTest("Eino项目不存在")
        
        result = run_graphify_analysis(str(eino_path))
        
        # 验证结果
        self.assertIsInstance(result, tuple)
        graph, edges, communities, prompt = result
        
        self.assertGreater(len(graph.nodes), 0)
        self.assertGreater(len(graph.edges), 0)
        self.assertGreater(len(communities), 0)
    
    def test_workflow_community_detection(self):
        """工作流2: 社区检测"""
        from community_enhancer import CommunityEnhancer
        
        enhancer = CommunityEnhancer()
        
        # 创建测试图数据
        nodes = [{"id": f"node_{i}", "label": f"Node{i}"} for i in range(10)]
        edges = [{"source": f"node_{i}", "target": f"node_{(i+1)%10}"} for i in range(10)]
        
        result = enhancer.analyze_communities({
            "nodes": nodes,
            "edges": edges,
            "communities": {}
        })
        
        self.assertIn("communities", result)
        self.assertGreater(len(result["communities"]), 0)
    
    def test_workflow_multi_language_scan(self):
        """工作流3: 多语言扫描"""
        from multi_language_scanner import MultiLanguageScanner
        
        scanner = MultiLanguageScanner()
        
        # 测试Go扫描
        go_result = scanner.scan(".", "go")
        self.assertIn("nodes", go_result)
        self.assertIn("edges", go_result)
    
    def test_workflow_html_visualization(self):
        """工作流4: HTML可视化"""
        from html_visualizer import generate_network_graph
        
        # 创建测试数据
        nodes = [{"id": "1", "label": "Node1", "type": "struct"}]
        edges = [{"source": "1", "target": "2", "type": "CALLS"}]
        
        html = generate_network_graph(nodes, edges)
        
        self.assertIn("<html>", html)
        self.assertIn("d3.", html)
    
    def test_workflow_query_evidence(self):
        """工作流5: 查询证据"""
        from query_evidence import QueryEvidenceEngine
        
        engine = QueryEvidenceEngine()
        
        # 测试查询
        results = engine.query("什么是Go的scheduler")
        
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)


def run_all_workflows():
    """运行所有工作流测试"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestWorkflow)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_workflows()
    sys.exit(0 if success else 1)
