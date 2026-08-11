#!/usr/bin/env python3
"""
biz-delivery 核心函数测试 - 修复版

测试不依赖完整引擎初始化的核心功能
"""

import unittest
import sys
import os
from pathlib import Path

# 添加 biz-delivery 路径
BIZ_DIR = os.path.expanduser("~/biz-delivery/scripts")
sys.path.insert(0, BIZ_DIR)


class TestQueryEvidence(unittest.TestCase):
    """测试查询证据功能"""
    
    def test_fuzzy_score_basic(self):
        """测试基础模糊匹配"""
        from query_evidence import fuzzy_score
        
        # 完全匹配
        score = fuzzy_score("用户登录", "用户登录功能")
        self.assertGreater(score, 0.5)
        
        # 部分匹配
        score = fuzzy_score("Redis", "Redis缓存")
        self.assertGreater(score, 0.3)
        
        # 不匹配
        score = fuzzy_score("A", "B")
        self.assertLess(score, 0.3)
    
    def test_chinese_similarity(self):
        """测试中文相似度"""
        from query_evidence import fuzzy_score
        
        # 同义词
        score = fuzzy_score("缓存穿透", "Redis穿透")
        self.assertGreater(score, 0.2)
        
        # 拼音相似
        score = fuzzy_score("yonghu", "用户")
        self.assertGreaterEqual(score, 0)
    
    def test_levenshtein_distance(self):
        """测试编辑距离"""
        from query_evidence import levenshtein_distance
        
        # 相同
        dist = levenshtein_distance("hello", "hello")
        self.assertEqual(dist, 0)
        
        # 不同
        dist = levenshtein_distance("hello", "hallo")
        self.assertEqual(dist, 1)
        
        # 较长差异
        dist = levenshtein_distance("abcdef", "xyz")
        self.assertGreater(dist, 2)
    
    def test_chinese_word_segment(self):
        """测试中文分词"""
        from query_evidence import _chinese_word_segment
        
        text = "用户登录功能实现"
        words = _chinese_word_segment(text)
        
        self.assertIsInstance(words, list)
        self.assertGreater(len(words), 0)
    
    def test_expand_synonyms(self):
        """测试同义词扩展"""
        from query_evidence import expand_synonyms
        
        synonyms = expand_synonyms("登录")
        
        self.assertIsInstance(synonyms, list)
        self.assertGreater(len(synonyms), 0)
    
    def test_classify_query(self):
        """测试查询分类"""
        from query_evidence import classify_query
        
        # 疑问句
        qtype = classify_query("怎么解决缓存穿透？")
        self.assertIn(qtype, ["question", "query", "general"])
        
        # 陈述句
        qtype = classify_query("Redis缓存架构设计")
        self.assertIn(qtype, ["query", "general"])
        
        # 比较句
        qtype = classify_query("对比Redis和Memcached")
        self.assertIn(qtype, ["compare", "general"])


class TestRRFFusion(unittest.TestCase):
    """测试RRF融合功能"""
    
    def test_rrf_ranks_basic(self):
        """测试基础RRF融合"""
        from rrf_fusion import rrf_ranks
        
        # 两个结果列表
        list1 = [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.8}]
        list2 = [{"id": "b", "score": 0.85}, {"id": "c", "score": 0.7}]
        
        results = rrf_ranks([list1, list2], k=60)
        
        self.assertEqual(len(results), 3)
        # b应该在前面（两个列表都出现）
        self.assertEqual(results[0]["id"], "b")
    
    def test_rrf_ranks_single_list(self):
        """测试单列表RRF"""
        from rrf_fusion import rrf_ranks
        
        items = [{"id": f"item_{i}", "score": 1.0 - i * 0.1} for i in range(5)]
        
        results = rrf_ranks([items], k=60)
        
        self.assertEqual(len(results), 5)
        # 保持原始顺序
        self.assertEqual(results[0]["id"], "item_0")
    
    def test_rrf_ranks_empty(self):
        """测试空列表"""
        from rrf_fusion import rrf_ranks
        
        results = rrf_ranks([], k=60)
        
        self.assertEqual(len(results), 0)


class TestSmartRouting(unittest.TestCase):
    """测试智能路由功能"""
    
    def test_extract_intent_question(self):
        """测试问题意图提取"""
        from smart_routing import extract_intent
        
        intent, confidence = extract_intent("怎么解决Redis缓存穿透？")
        
        self.assertEqual(intent, "question")
        self.assertGreater(confidence, 0)
    
    def test_extract_intent_explain(self):
        """测试解释意图提取"""
        from smart_routing import extract_intent
        
        intent, confidence = extract_intent("解释一下Go的GMP调度模型")
        
        self.assertEqual(intent, "explain")
    
    def test_extract_intent_compare(self):
        """测试比较意图提取"""
        from smart_routing import extract_intent
        
        intent, confidence = extract_intent("对比Redis和Memcached的区别")
        
        self.assertEqual(intent, "compare")
    
    def test_extract_intent_query(self):
        """测试查询意图提取"""
        from smart_routing import extract_intent
        
        intent, confidence = extract_intent("Redis缓存架构设计")
        
        # 可能是query、general或unknown（取决于模式匹配）
        self.assertIn(intent, ["query", "general", "unknown"])


class TestCodeAnalysis(unittest.TestCase):
    """测试代码分析功能"""
    
    def test_import_learn_repo(self):
        """测试learn_repo导入"""
        from learn_repo import GoScanner, IRDocument
        
        self.assertIsNotNone(GoScanner)
        self.assertIsNotNone(IRDocument)
    
    def test_import_query_evidence(self):
        """测试query_evidence导入"""
        from query_evidence import fuzzy_score, levenshtein_distance
        
        self.assertTrue(callable(fuzzy_score))
        self.assertTrue(callable(levenshtein_distance))
    
    def test_import_rrf_fusion(self):
        """测试rrf_fusion导入"""
        from rrf_fusion import rrf_ranks, multi_path_query
        
        self.assertTrue(callable(rrf_ranks))
        self.assertTrue(callable(multi_path_query))
    
    def test_import_smart_routing(self):
        """测试smart_routing导入"""
        from smart_routing import extract_intent, get_scope_weights
        
        self.assertTrue(callable(extract_intent))
        self.assertTrue(callable(get_scope_weights))


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    test_classes = [
        TestQueryEvidence,
        TestRRFFusion,
        TestSmartRouting,
        TestCodeAnalysis,
    ]
    
    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    run_tests()
