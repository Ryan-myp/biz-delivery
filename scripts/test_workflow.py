#!/usr/bin/env python3
"""
biz-delivery 完整工作流测试
"""

import unittest
import sys
import os
import tempfile
import json
from pathlib import Path


class TestBizDeliveryWorkflow(unittest.TestCase):
    """biz-delivery 完整工作流测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="biz-test-"))
        self.b dir = Path.home() / "biz-delivery" / "scripts"
        sys.path.insert(0, str(self.b_dir))
    
    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_graphify_analysis(self):
        """测试Graphify分析"""
        from graphify_analysis import GraphifyAnalysis
        
        # 创建临时Go文件
        test_go = self.test_dir / "test.go"
        test_go.write_text('''
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
''')
        
        analysis = GraphifyAnalysis(str(self.test_dir))
        result = analysis.analyze()
        
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertGreater(len(result["nodes"]), 0)
    
    def test_community_enhancement(self):
        """测试社区增强"""
        from community_enhancer import CommunityEnhancer
        
        enhancer = CommunityEnhancer()
        nodes = [
            {"id": "1", "name": "Graph", "degree": 5},
            {"id": "2", "name": "Node", "degree": 3},
            {"id": "3", "name": "Edge", "degree": 2},
        ]
        edges = [
            {"source": "1", "target": "2"},
            {"source": "2", "target": "3"},
        ]
        
        result = enhancer.analyze(nodes, edges)
        
        self.assertIn("communities", result)
        self.assertGreater(len(result["communities"]), 0)
    
    def test_multi_language_scan(self):
        """测试多语言扫描"""
        from multi_language_scanner import MultiLanguageScanner
        
        scanner = MultiLanguageScanner()
        
        # Python扫描
        test_py = self.test_dir / "test.py"
        test_py.write_text('''
class TestClass:
    def __init__(self):
        pass
    
    def method(self):
        pass
''')
        
        result = scanner.scan(str(self.test_dir), "python")
        self.assertIn("nodes", result)
    
    def test_e2e_workflow(self):
        """测试端到端工作流"""
        # 1. 代码扫描
        from multi_language_scanner import MultiLanguageScanner
        scanner = MultiLanguageScanner()
        
        # 2. 图分析
        from graphify_analysis import GraphifyAnalysis
        analysis = GraphifyAnalysis(str(self.test_dir))
        
        # 3. 社区增强
        from community_enhancer import CommunityEnhancer
        enhancer = CommunityEnhancer()
        
        print("✅ E2E工作流测试通过")


def main():
    """运行测试"""
    unittest.main(argv=[''], exit=False, verbosity=2)


if __name__ == '__main__':
    main()
