"""
Mermaid Generator 与 Enhanced Search 深度测试套件
目标：mermaid_generator.py ≥85%、enhanced_search.py ≥80%
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scripts.mermaid_generator import MermaidGenerator
from scripts.enhanced_search import (
    BM25Scorer, char_ngrams, chinese_similarity, mixed_similarity,
    normalize_query, expand_query_variants, adaptive_threshold, classify_query,
)


def make_ir():
    """构造 IR 数据"""
    return {
        "packages": {
            "handler": {"files": ["auth.go"], "functions": ["LoginHandler"]},
            "service": {"files": ["auth_service.go"], "functions": ["AuthService"]},
            "dao": {"files": ["user_dao.go"], "functions": ["UserDAO"]},
        },
        "call_graph": [
            {"caller": "LoginHandler", "callee": "AuthService"},
            {"caller": "AuthService", "callee": "UserDAO"},
        ],
        "entity_tables": [
            {"entity": "User", "table": "users", "fields": ["id", "email", "password"]},
        ],
        "routes": [
            {"method": "POST", "path": "/api/login", "handler": "LoginHandler"},
        ],
        "functions": [
            {"name": "LoginHandler", "file": "auth.go"},
            {"name": "AuthService", "file": "auth_service.go"},
        ],
        "services": [
            {"name": "user-service", "port": 8080},
        ],
        "core_flows": [
            {"flow_name": "登录流程", "entry_point": "LoginHandler",
             "call_chain": ["LoginHandler", "AuthService", "UserDAO"],
             "data_flow": "request -> auth -> db"},
        ],
        "structs": [
            {"name": "LoginRequest", "fields": ["email", "password"]},
        ],
        "sql_operations": [
            {"func": "UserDAO", "table": "users", "operation": "SELECT"},
        ],
        "error_codes": [
            {"name": "ERR_LOGIN", "code": "AUTH_001", "category": "auth", "message": "登录失败"},
        ],
        "auth_models": [
            {"middleware": "AuthMiddleware", "protected_routes": ["/api/login"]},
        ],
        "configs": [
            {"key": "DB_HOST", "value": "localhost"},
        ],
    }


class TestMermaidGenerator:
    """Mermaid 图生成器测试"""
    
    def _make_gen(self):
        return MermaidGenerator(make_ir())
    
    def test_init(self):
        """测试初始化"""
        gen = self._make_gen()
        assert gen.ir is not None
        assert gen.packages != {}
    
    def test_init_empty(self):
        """测试空 IR"""
        gen = MermaidGenerator({})
        assert gen.ir == {}
        assert gen.packages == {}
    
    def test_architecture_diagram(self):
        """测试架构图"""
        gen = self._make_gen()
        diagram = gen.generate_architecture_diagram()
        assert isinstance(diagram, str)
        assert "graph" in diagram.lower() or "flowchart" in diagram.lower()
    
    def test_data_model_diagram(self):
        """测试数据模型图"""
        gen = self._make_gen()
        diagram = gen.generate_data_model_diagram()
        assert isinstance(diagram, str)
    
    def test_deployment_diagram(self):
        """测试部署图"""
        gen = self._make_gen()
        diagram = gen.generate_deployment_diagram()
        assert isinstance(diagram, str)
    
    def test_sequence_diagram(self):
        """测试时序图"""
        gen = self._make_gen()
        diagram = gen.generate_sequence_diagram()
        assert isinstance(diagram, str)
    
    def test_sequence_diagram_with_flow(self):
        """测试带流程的时序图"""
        gen = self._make_gen()
        flow = {
            "flow_name": "出价流程",
            "call_chain": ["PlaceBid", "SaveBid"],
        }
        diagram = gen.generate_sequence_diagram(flow)
        assert isinstance(diagram, str)
    
    def test_generate_all_diagrams(self):
        """测试生成所有图"""
        gen = self._make_gen()
        diagrams = gen.generate_all_diagrams()
        assert isinstance(diagrams, dict)
        assert "architecture" in diagrams
    
    def test_activity_diagram(self):
        """测试活动图"""
        gen = self._make_gen()
        diagram = gen.generate_activity_diagram()
        assert isinstance(diagram, str)
    
    def test_state_machine_diagram(self):
        """测试状态机图"""
        gen = self._make_gen()
        diagram = gen.generate_state_machine_diagram()
        assert isinstance(diagram, str)
    
    def test_dependency_diagram(self):
        """测试依赖图"""
        gen = self._make_gen()
        diagram = gen.generate_dependency_diagram()
        assert isinstance(diagram, str)
    
    def test_api_flow_diagram(self):
        """测试 API 流程图"""
        gen = self._make_gen()
        diagram = gen.generate_api_flow_diagram()
        assert isinstance(diagram, str)
    
    def test_error_code_matrix_diagram(self):
        """测试错误码矩阵图（使用数字错误码）"""
        ir = make_ir()
        ir["error_codes"] = [
            {"name": "ERR_LOGIN", "code": "4001", "category": "auth", "message": "登录失败"},
            {"name": "ERR_TIMEOUT", "code": "5001", "category": "system", "message": "超时"},
        ]
        gen = MermaidGenerator(ir)
        diagram = gen.generate_error_code_matrix_diagram()
        assert isinstance(diagram, str)


class TestBM25Scorer:
    """BM25 打分器测试"""
    
    def test_fit_and_score(self):
        """测试拟合和打分"""
        scorer = BM25Scorer()
        scorer.fit(["用户出价功能", "用户登录功能", "广告组管理"])
        score = scorer.score("出价", 0)
        assert isinstance(score, float)
        assert score >= 0
    
    def test_search(self):
        """测试搜索"""
        scorer = BM25Scorer()
        scorer.fit(["用户出价功能", "用户登录功能"])
        results = scorer.search("出价", top_k=2)
        assert isinstance(results, list)
        assert len(results) <= 2
    
    def test_tokenize(self):
        """测试分词"""
        tokens = BM25Scorer._tokenize("hello world")
        assert isinstance(tokens, list)
    
    def test_empty_fit(self):
        """测试空拟合"""
        scorer = BM25Scorer()
        scorer.fit([])
        results = scorer.search("测试", top_k=5)
        assert results == []


class TestSimilarityFunctions:
    """相似度函数测试"""
    
    def test_char_ngrams(self):
        """测试字符 ngram"""
        ngrams = char_ngrams("出价")
        assert isinstance(ngrams, set)
    
    def test_char_ngrams_n(self):
        """测试指定 n"""
        ngrams = char_ngrams("abcd", n=3)
        assert len(ngrams) >= 1
    
    def test_chinese_similarity(self):
        """测试中文相似度"""
        sim = chinese_similarity("出价", "出价功能")
        assert isinstance(sim, float)
        assert 0 <= sim <= 1
    
    def test_chinese_similarity_empty(self):
        """测试空输入"""
        assert chinese_similarity("", "") == 0.0
    
    def test_mixed_similarity(self):
        """测试混合相似度"""
        sim = mixed_similarity("用户出价", "用户出价功能")
        assert isinstance(sim, float)
    
    def test_mixed_similarity_exact(self):
        """测试精确匹配"""
        assert mixed_similarity("出价", "出价") >= 0.9
    
    def test_normalize_query(self):
        """测试查询规范化"""
        norm = normalize_query("  User Login  ")
        assert isinstance(norm, str)
        assert norm == norm.strip()
    
    def test_expand_query_variants(self):
        """测试查询变体"""
        variants = expand_query_variants("create_user")
        assert isinstance(variants, list)
        assert "create_user" in variants
    
    def test_adaptive_threshold(self):
        """测试自适应阈值"""
        threshold = adaptive_threshold("查询用户")
        assert 0 <= threshold <= 1
    
    def test_adaptive_threshold_general(self):
        """测试通用阈值"""
        threshold = adaptive_threshold("测试", "general")
        assert 0 <= threshold <= 1
    
    def test_classify_query(self):
        """测试查询分类"""
        qtype = classify_query("查询用户")
        assert isinstance(qtype, str)
    
    def test_classify_query_code(self):
        """测试代码查询"""
        qtype = classify_query("创建用户")
        assert isinstance(qtype, str)
