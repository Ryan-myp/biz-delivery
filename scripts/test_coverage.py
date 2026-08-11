#!/usr/bin/env python3
"""
Phase 3: biz-delivery 测试覆盖提升至80%
"""

import unittest
import sys
import tempfile
import json
from pathlib import Path


class TestGraphifyAnalysis(unittest.TestCase):
    """测试Graphify分析功能"""
    
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="graphify-test-"))
        # 创建测试Go文件
        self.test_go = self.test_dir / "test.go"
        self.test_go.write_text('''
package test

type Graph struct {
    Nodes []Node
    Edges []Edge
}

type Node struct {
    ID   string
    Name string
}

type Edge struct {
    Source string
    Target string
}

func (g *Graph) AddNode(id, name string) {
    g.Nodes = append(g.Nodes, Node{ID: id, Name: name})
}

func (g *Graph) AddEdge(src, tgt string) {
    g.Edges = append(g.Edges, Edge{Source: src, Target: tgt})
}
''')
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_graphify_basic(self):
        """测试基础图谱构建"""
        sys.path.insert(0, str(Path(__file__).parent))
        from graphify_analysis import run_graphify_analysis
        
        result = run_graphify_analysis(str(self.test_dir))
        
        # result是一个tuple: (graph, edges, communities, prompt)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 4)
        
        graph, edges, communities, prompt = result
        
        self.assertGreater(len(graph.nodes), 0)
        self.assertGreater(len(edges), 0)
    
    def test_graphify_nodes(self):
        """测试节点提取"""
        sys.path.insert(0, str(Path(__file__).parent))
        from graphify_analysis import run_graphify_analysis
        
        graph, _, _, _ = run_graphify_analysis(str(self.test_dir))
        
        node_ids = [n.id for n in graph.nodes]
        self.assertIn("Graph", node_ids)
        self.assertIn("Node", node_ids)
        self.assertIn("Edge", node_ids)
    
    def test_graphify_edges(self):
        """测试边提取"""
        sys.path.insert(0, str(Path(__file__).parent))
        from graphify_analysis import run_graphify_analysis
        
        _, edges, _, _ = run_graphify_analysis(str(self.test_dir))
        
        self.assertGreater(len(edges), 0)


class TestCommunityDetection(unittest.TestCase):
    """测试社区检测功能"""
    
    def test_community_enhancer(self):
        """测试社区增强器"""
        sys.path.insert(0, str(Path(__file__).parent))
        from community_enhancer import CommunityEnhancer
        
        enhancer = CommunityEnhancer()
        
        nodes = [{"id": f"node_{i}", "label": f"Node{i}"} for i in range(10)]
        edges = [{"source": f"node_{i}", "target": f"node_{(i+1)%10}"} for i in range(10)]
        
        result = enhancer.analyze_communities({
            "nodes": nodes,
            "edges": edges,
            "communities": {}
        })
        
        self.assertIn("communities", result)
        self.assertGreater(len(result["communities"]), 0)


class TestMultiLanguageScanner(unittest.TestCase):
    """测试多语言扫描功能"""
    
    def test_go_scanner(self):
        """测试Go扫描器"""
        sys.path.insert(0, str(Path(__file__).parent))
        from multi_language_scanner import MultiLanguageScanner
        
        scanner = MultiLanguageScanner()
        result = scanner.scan(".", "go")
        
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
    
    def test_python_scanner(self):
        """测试Python扫描器"""
        sys.path.insert(0, str(Path(__file__).parent))
        from multi_language_scanner import MultiLanguageScanner
        
        scanner = MultiLanguageScanner()
        result = scanner.scan(".", "python")
        
        self.assertIn("nodes", result)
        self.assertIn("edges", result)


class TestQueryEvidence(unittest.TestCase):
    """测试查询证据功能"""
    
    def test_fuzzy_score(self):
        """测试模糊匹配"""
        sys.path.insert(0, str(Path(__file__).parent))
        from query_evidence import fuzzy_score
        
        score = fuzzy_score("Go调度器", "Go scheduler实现")
        self.assertGreater(score, 0.3)
    
    def test_rrf_fusion(self):
        """测试RRF融合"""
        sys.path.insert(0, str(Path(__file__).parent))
        from rrf_fusion import rrf_fuse
        
        lists = [
            ["A", "B", "C"],
            ["B", "C", "D"],
            ["C", "D", "E"]
        ]
        
        result = rrf_fuse(lists)
        self.assertIn("C", result)


class TestWorkflowIntegration(unittest.TestCase):
    """测试完整工作流"""
    
    def test_full_pipeline(self):
        """测试完整pipeline"""
        sys.path.insert(0, str(Path(__file__).parent))
        from unified_api import run_pipeline
        
        # 使用现有的Eino项目
        eino_path = Path("/tmp/eino")
        if not eino_path.exists():
            self.skipTest("Eino项目不存在")
        
        result = run_pipeline(str(eino_path))
        
        self.assertGreater(len(result.nodes), 0)
        self.assertGreater(len(result.edges), 0)


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = loader.discover('scripts', pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
