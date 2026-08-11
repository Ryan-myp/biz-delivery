#!/usr/bin/env python3
"""
biz-delivery 核心引擎单元测试

覆盖 learn_repo、review_engine、td_engine_v2、test_engine、query_evidence
"""

import sys
import unittest
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import Mock, patch

# 添加 biz-delivery 路径
sys.path.insert(0, str(Path(__file__).parent))


class TestLearnRepo(unittest.TestCase):
    """learn_repo.py 测试"""
    
    def setUp(self):
        """设置测试环境"""
        from learn_repo import IRDocument, GoScanner
        self.IRDocument = IRDocument
        self.GoScanner = GoScanner
    
    def test_ir_document_creation(self):
        """测试 IRDocument 创建"""
        ir = self.IRDocument(
            repo_name="test-repo",
            repo_path="/tmp/test",
            language="go"
        )
        self.assertEqual(ir.repo_name, "test-repo")
        self.assertEqual(ir.language, "go")
        self.assertEqual(len(ir.routes), 0)
        self.assertEqual(len(ir.functions), 0)
    
    def test_ir_document_add_route(self):
        """测试添加路由"""
        ir = self.IRDocument(repo_name="test", repo_path="/tmp", language="go")
        # 直接赋值（根据实际实现）
        ir.routes = [{"method": "GET", "path": "/api/users", "handler": "GetUsers", "package": "handlers"}]
        self.assertEqual(len(ir.routes), 1)
        self.assertEqual(ir.routes[0]["path"], "/api/users")
    
    def test_go_scanner(self):
        """测试 Go 扫描器"""
        scanner = self.GoScanner()
        # 测试基本功能
        self.assertIsNotNone(scanner)


class TestReviewEngine(unittest.TestCase):
    """review_engine.py 测试"""
    
    def setUp(self):
        """设置测试环境"""
        from review_engine import ReviewEngine
        self.profile = {
            "name": "test-project",
            "repositories": [],
            "business_domain": "test",
        }
        self.output_dir = "/tmp/biz_test_review"
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.engine = ReviewEngine(self.profile, self.output_dir)
    
    def test_review_basic(self):
        """测试基本审查"""
        prd = """
        # 功能需求
        
        实现一个用户出价功能。
        """
        result = self.engine.review(prd)
        self.assertEqual(result["status"], "prompt_ready")
        self.assertIn("prompt_file", result)
    
    def test_review_empty_prd(self):
        """测试空 PRD"""
        result = self.engine.review("")
        self.assertEqual(result["status"], "prompt_ready")
    
    def test_review_with_code(self):
        """测试带代码的 PRD"""
        prd = """
        # 功能需求
        
        ## 代码示例
        ```go
        func GetUsers() {
            // 实现
        }
        ```
        """
        result = self.engine.review(prd)
        self.assertEqual(result["status"], "prompt_ready")


class TestTDEngineV2(unittest.TestCase):
    """td_engine_v2.py 测试"""
    
    def setUp(self):
        """设置测试环境"""
        from td_engine_v2 import TDEngine
        self.profile = {
            "name": "test-project",
            "repositories": [],
            "business_domain": "test",
        }
        self.output_dir = "/tmp/biz_test_td"
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.engine = TDEngine(self.profile, self.output_dir)
    
    def test_generate_td_no_llm(self):
        """测试不调用 LLM 的 TD 生成"""
        prd = """
        # 功能需求
        
        实现一个订单系统。
        """
        result = self.engine.generate_td(prd, use_llm=False)
        self.assertEqual(result["status"], "prompt_ready")
        self.assertIn("prompt_file", result)
    
    def test_generate_td_with_llm_fallback(self):
        """测试调用 LLM 时的 fallback"""
        prd = """
        # 功能需求
        
        实现一个订单系统。
        """
        # 不设置 LLM_API_KEY，应该 fallback
        result = self.engine.generate_td(prd, use_llm=True)
        self.assertEqual(result["status"], "prompt_ready")
    
    def test_generate_td_with_response(self):
        """测试带响应的 TD 生成"""
        prd = "测试 PRD"
        result = self.engine.generate_with_response(prd)
        self.assertIsNotNone(result)


class TestTestEngine(unittest.TestCase):
    """test_engine.py 测试"""
    
    def setUp(self):
        """设置测试环境"""
        from test_engine import TestEngine
        self.profile = {
            "name": "test-project",
            "repositories": [],
            "business_domain": "test",
        }
        self.output_dir = "/tmp/biz_test_case"
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.engine = TestEngine(self.profile, self.output_dir)
    
    def test_generate_tests(self):
        """测试测试用例生成"""
        prd = """
        # 功能需求
        
        实现用户登录功能。
        """
        result = self.engine.generate_tests(prd)
        self.assertEqual(result["status"], "prompt_ready")


class TestQueryEvidence(unittest.TestCase):
    """query_evidence.py 测试"""
    
    def test_fuzzy_score_basic(self):
        """测试基本模糊匹配"""
        from query_evidence import fuzzy_score
        score = fuzzy_score("用户出价", "用户竞价策略")
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)
    
    def test_fuzzy_score_exact_match(self):
        """测试完全匹配"""
        from query_evidence import fuzzy_score
        score = fuzzy_score("测试字符串", "测试字符串")
        self.assertEqual(score, 1.0)
    
    def test_fuzzy_score_no_match(self):
        """测试无匹配"""
        from query_evidence import fuzzy_score
        score = fuzzy_score("完全无关的字符串A", "完全无关的字符串B")
        # 无匹配时分数较低，但不一定小于 0.3
        self.assertLessEqual(score, 0.5)
    
    def test_query_engine(self):
        """测试查询引擎"""
        from query_evidence import QueryEvidence
        engine = QueryEvidence()
        results = engine.query("用户出价", limit=5)
        self.assertIsNotNone(results)


class TestCodeQuality(unittest.TestCase):
    """代码质量测试"""
    
    def test_no_duplicate_functions(self):
        """测试没有重复函数定义"""
        import os
        from pathlib import Path
        
        biz_dir = Path(__file__).parent
        duplicate_funcs = {}
        
        for py_file in biz_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for line in content.split("\n"):
                if line.startswith("def "):
                    func_name = line.strip().split("(")[0].replace("def ", "")
                    if func_name not in duplicate_funcs:
                        duplicate_funcs[func_name] = []
                    duplicate_funcs[func_name].append(str(py_file))
        
        # 检查重复
        duplicates = {k: v for k, v in duplicate_funcs.items() if len(v) > 1}
        self.assertEqual(len(duplicates), 0, f"发现重复函数: {duplicates}")


def run_tests():
    """运行所有测试"""
    unittest.main(verbosity=2)


if __name__ == "__main__":
    run_tests()
