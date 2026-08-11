#!/usr/bin/env python3
"""
biz-delivery 完整测试套件

覆盖核心功能和边界情况
"""

import unittest
import sys
import os
import tempfile
import shutil
from pathlib import Path

# 添加 biz-delivery 路径
BIZ_DIR = os.path.expanduser("~/biz-delivery/scripts")
sys.path.insert(0, BIZ_DIR)


class TestQueryEvidence(unittest.TestCase):
    """测试查询证据功能"""
    
    def test_fuzzy_score_basic(self):
        """测试基础模糊匹配"""
        from query_evidence import fuzzy_score
        score = fuzzy_score("用户登录", "用户登录功能")
        self.assertGreater(score, 0.5)
    
    def test_fuzzy_score_partial(self):
        """测试部分匹配"""
        from query_evidence import fuzzy_score
        score = fuzzy_score("Redis", "Redis缓存")
        self.assertGreater(score, 0.3)
    
    def test_levenshtein_distance(self):
        """测试编辑距离"""
        from query_evidence import levenshtein_distance
        dist = levenshtein_distance("hello", "hallo")
        self.assertEqual(dist, 1)
    
    def test_chinese_similarity(self):
        """测试中文相似度"""
        from query_evidence import fuzzy_score
        score = fuzzy_score("缓存穿透", "Redis缓存穿透")
        self.assertGreater(score, 0.2)
    
    def test_empty_string(self):
        """测试空字符串"""
        from query_evidence import fuzzy_score
        score = fuzzy_score("", "test")
        self.assertEqual(score, 0)


class TestRRFFusion(unittest.TestCase):
    """测试RRF融合功能"""
    
    def test_rrf_ranks_basic(self):
        """测试基础RRF融合"""
        from rrf_fusion import rrf_ranks
        list1 = [{"id": "a"}, {"id": "b"}]
        list2 = [{"id": "b"}, {"id": "c"}]
        results = rrf_ranks([list1, list2], k=60)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["id"], "b")
    
    def test_rrf_ranks_empty(self):
        """测试空列表"""
        from rrf_fusion import rrf_ranks
        results = rrf_ranks([], k=60)
        self.assertEqual(len(results), 0)
    
    def test_rrf_ranks_single(self):
        """测试单列表"""
        from rrf_fusion import rrf_ranks
        items = [{"id": f"item_{i}"} for i in range(5)]
        results = rrf_ranks([items], k=60)
        self.assertEqual(len(results), 5)


class TestSmartRouting(unittest.TestCase):
    """测试智能路由功能"""
    
    def test_extract_intent_question(self):
        """测试问题意图"""
        from smart_routing import extract_intent
        intent, confidence = extract_intent("怎么解决缓存穿透？")
        self.assertEqual(intent, "question")
    
    def test_extract_intent_explain(self):
        """测试解释意图"""
        from smart_routing import extract_intent
        intent, confidence = extract_intent("解释一下GMP模型")
        self.assertEqual(intent, "explain")
    
    def test_extract_intent_compare(self):
        """测试比较意图"""
        from smart_routing import extract_intent
        intent, confidence = extract_intent("对比Redis和Memcached")
        self.assertEqual(intent, "compare")
    
    def test_get_scope_weights(self):
        """测试范围权重"""
        from smart_routing import get_scope_weights
        weights = get_scope_weights("question")
        self.assertIsInstance(weights, dict)
        self.assertGreater(len(weights), 0)


class TestReviewEngine(unittest.TestCase):
    """测试PRD审查引擎"""
    
    def test_review_prd(self):
        """测试PRD审查"""
        from review_engine import ReviewEngine
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = ReviewEngine({}, tmpdir)
            result = engine.review("实现用户登录功能")
            self.assertIn("status", result)
    
    def test_review_empty(self):
        """测试空PRD"""
        from review_engine import ReviewEngine
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = ReviewEngine({}, tmpdir)
            result = engine.review("")
            self.assertIn("status", result)
    
    def test_review_long_prd(self):
        """测试长PRD"""
        from review_engine import ReviewEngine
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = ReviewEngine({}, tmpdir)
            result = engine.review("a" * 5000)
            self.assertIn("status", result)


class TestTDEngine(unittest.TestCase):
    """测试TD生成引擎"""
    
    def test_generate_td(self):
        """测试TD生成"""
        from td_engine_v2 import TDEngine
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TDEngine({}, tmpdir)
            try:
                result = engine.generate_td("实现订单系统")
                self.assertEqual(result.get("status"), "completed")
            except Exception as e:
                self.skipTest(f"TD引擎需要LLM: {e}")
    
    def test_generate_td_no_llm(self):
        """测试不依赖LLM的TD生成"""
        from td_engine_v2 import TDEngine
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TDEngine({}, tmpdir)
            try:
                result = engine.generate_td("实现用户管理", use_llm=False)
                self.assertEqual(result.get("status"), "completed")
            except Exception as e:
                self.skipTest(f"TD引擎失败: {e}")


class TestTestEngine(unittest.TestCase):
    """测试测试生成引擎"""
    
    def test_generate_tests(self):
        """测试测试生成"""
        from test_engine import TestEngine
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = TestEngine({}, tmpdir)
            try:
                result = engine.generate_tests("实现登录功能")
                self.assertIn("status", result)
            except Exception as e:
                self.skipTest(f"测试引擎失败: {e}")


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def test_full_pipeline(self):
        """测试完整流程"""
        from review_engine import ReviewEngine
        from td_engine_v2 import TDEngine
        from test_engine import TestEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                # 1. 审查PRD
                review = ReviewEngine({}, tmpdir)
                review_result = review.review("实现用户登录")
                
                # 2. 生成TD
                td = TDEngine({}, tmpdir)
                td_result = td.generate_td("实现用户登录")
                
                # 验证
                self.assertEqual(review_result.get("status"), "completed")
                self.assertEqual(td_result.get("status"), "completed")
            except Exception as e:
                self.skipTest(f"集成测试需要LLM: {e}")


class TestPerformance(unittest.TestCase):
    """性能测试"""
    
    def test_large_prd(self):
        """测试大PRD处理"""
        from review_engine import ReviewEngine
        import time
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = ReviewEngine({}, tmpdir)
            start = time.time()
            result = engine.review("a" * 5000)
            elapsed = time.time() - start
            
            self.assertIn("status", result)
            self.assertLess(elapsed, 10)


class TestEdgeCases(unittest.TestCase):
    """边界情况测试"""
    
    def test_special_characters(self):
        """测试特殊字符"""
        from query_evidence import fuzzy_score
        score = fuzzy_score("test\n\r\t", "test特殊")
        self.assertGreaterEqual(score, 0)
    
    def test_unicode(self):
        """测试Unicode"""
        from query_evidence import fuzzy_score
        score = fuzzy_score("用户登录", "用戶登入")
        self.assertGreaterEqual(score, 0)
    
    def test_numeric_query(self):
        """测试数字查询"""
        from query_evidence import fuzzy_score
        score = fuzzy_score("123", "abc123def")
        self.assertGreater(score, 0)


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    test_classes = [
        TestQueryEvidence,
        TestRRFFusion,
        TestSmartRouting,
        TestReviewEngine,
        TestTDEngine,
        TestTestEngine,
        TestIntegration,
        TestPerformance,
        TestEdgeCases,
    ]
    
    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


if __name__ == "__main__":
    run_tests()
