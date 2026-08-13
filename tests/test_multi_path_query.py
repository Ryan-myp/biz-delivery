"""
Multi-Path Query 与 RRF Fusion 深度测试套件
覆盖：search_code、search_schema、search_api_docs、search_by_tags、run_multi_path_query、rrf_fuse 全部
目标：scripts/query/multi_path_query.py ≥85%、rrf_fusion.py ≥90%
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.query.multi_path_query import (
    search_code, search_schema, search_api_docs,
    search_by_tags, run_multi_path_query,
)
from scripts.query.rrf_fusion import (
    rrf_fuse, rrf_fuse_multi_source,
    _get_rrf_k_for_label, _get_source_weight,
)


def make_ir():
    """构造完整 IR 数据"""
    return {
        "functions": [
            {"name": "PlaceBid", "signature": "func PlaceBid(ctx, req)", "file": "bid.go"},
            {"name": "GetBidStatus", "signature": "func GetBidStatus(ctx)", "file": "bid.go"},
            {"name": "UserLogin", "signature": "func UserLogin(ctx)", "file": "auth.go"},
        ],
        "routes": [
            {"method": "POST", "path": "/api/auction/bid", "handler": "PlaceBid"},
            {"method": "GET", "path": "/api/auction/status", "handler": "GetBidStatus"},
            {"method": "POST", "path": "/api/login", "handler": "UserLogin"},
        ],
        "structs": [
            {"name": "BidRequest", "fields": ["user_id", "amount", "product_id"]},
            {"name": "LoginRequest", "fields": ["email", "password"]},
        ],
        "entity_tables": [
            {"entity": "UserBid", "table": "user_bids"},
            {"entity": "User", "table": "users"},
        ],
        "error_codes": [
            {"name": "ERR_BID_DUPLICATE", "code": 4001, "message": "重复出价"},
            {"name": "ERR_LOGIN_FAILED", "code": 4002, "message": "登录失败"},
        ],
        "core_flows": [
            {"flow_name": "出价流程", "entry_point": "PlaceBid", "call_chain": ["PlaceBid", "SaveBid"]},
            {"flow_name": "登录流程", "entry_point": "UserLogin", "call_chain": ["UserLogin"]},
        ],
    }


class TestSearchCode:
    """代码搜索测试"""
    
    def test_search_functions(self):
        """测试函数搜索"""
        results = search_code(make_ir(), ["PlaceBid"], top_k=10)
        assert len(results) > 0
        # PlaceBid 应该出现在结果中（可能是 function 或 route）
        names = [r.get("name", "") + r.get("handler", "") for r in results]
        assert any("PlaceBid" in n for n in names)
    
    def test_search_routes(self):
        """测试路由搜索"""
        results = search_code(make_ir(), ["/api/login"], top_k=10)
        assert len(results) > 0
        assert results[0]["type"] == "route"
    
    def test_search_structs(self):
        """测试结构体搜索"""
        results = search_code(make_ir(), ["BidRequest"], top_k=10)
        assert len(results) > 0
        assert results[0]["type"] == "struct"
        assert results[0]["fields"] == ["user_id", "amount", "product_id"]
    
    def test_search_no_results(self):
        """测试无结果"""
        results = search_code(make_ir(), ["不存在的关键词xyz"], top_k=10)
        assert results == []
    
    def test_search_empty_ir(self):
        """测试空 IR"""
        results = search_code({}, ["PlaceBid"], top_k=10)
        assert results == []
    
    def test_search_sort_by_score(self):
        """测试按分数排序"""
        results = search_code(make_ir(), ["PlaceBid"], top_k=10)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)
    
    def test_search_top_k_limit(self):
        """测试 top_k 限制"""
        results = search_code(make_ir(), ["PlaceBid"], top_k=1)
        assert len(results) <= 1
    
    def test_search_case_insensitive(self):
        """测试大小写不敏感"""
        results = search_code(make_ir(), ["placebid"], top_k=10)
        assert len(results) > 0


class TestSearchSchema:
    """Schema 搜索测试"""
    
    def test_search_entity_tables(self):
        """测试实体表搜索"""
        results = search_schema(make_ir(), ["user_bids"], top_k=10)
        assert len(results) > 0
        assert results[0]["type"] == "entity_table"
    
    def test_search_error_codes(self):
        """测试错误码搜索"""
        results = search_schema(make_ir(), ["重复出价"], top_k=10)
        assert len(results) > 0
        assert results[0]["type"] == "error_code"
    
    def test_search_empty(self):
        """测试空 IR"""
        results = search_schema({}, ["user_bids"], top_k=10)
        assert results == []
    
    def test_search_no_results(self):
        """测试无结果"""
        results = search_schema(make_ir(), ["xyzxyz"], top_k=10)
        assert results == []


class TestSearchApiDocs:
    """API 文档搜索测试"""
    
    def test_search_routes(self):
        """测试路由搜索"""
        results = search_api_docs(make_ir(), ["/api/auction/bid"], top_k=10)
        assert len(results) > 0
        assert results[0]["type"] == "api"
        assert results[0]["source"] == "api_doc"
    
    def test_search_empty(self):
        """测试空 IR"""
        results = search_api_docs({}, ["/api/login"], top_k=10)
        assert results == []
    
    def test_search_no_results(self):
        """测试无结果"""
        results = search_api_docs(make_ir(), ["xyzxyz"], top_k=10)
        assert results == []


class TestSearchByTags:
    """标签搜索测试"""
    
    def test_search_core_flows(self):
        """测试核心流程搜索"""
        results = search_by_tags(make_ir(), ["出价流程"], top_k=10)
        assert len(results) > 0
        assert results[0]["type"] == "core_flow"
        assert results[0]["score"] == 0.8
    
    def test_search_entry_point(self):
        """测试按入口点搜索"""
        results = search_by_tags(make_ir(), ["UserLogin"], top_k=10)
        assert len(results) > 0
        assert results[0]["flow_name"] == "登录流程"
    
    def test_search_empty(self):
        """测试空 IR"""
        results = search_by_tags({}, ["出价"], top_k=10)
        assert results == []
    
    def test_search_no_results(self):
        """测试无结果"""
        results = search_by_tags(make_ir(), ["xyzxyz"], top_k=10)
        assert results == []


class TestRunMultiPathQuery:
    """多路查询主函数测试"""
    
    def test_run_full(self):
        """测试完整查询"""
        results = run_multi_path_query("PlaceBid", make_ir(), top_k=20)
        assert isinstance(results, list)
    
    def test_run_empty_ir(self):
        """测试空 IR"""
        results = run_multi_path_query("PlaceBid", {}, top_k=20)
        assert isinstance(results, list)
    
    def test_run_no_match(self):
        """测试无匹配"""
        results = run_multi_path_query("完全无关内容xyz", make_ir(), top_k=20)
        assert isinstance(results, list)


class TestRRFFusion:
    """RRF 融合测试"""
    
    def test_rrf_fuse_empty(self):
        """测试空输入"""
        assert rrf_fuse([], k=60) == []
        assert rrf_fuse([[], []], k=60) == []
    
    def test_rrf_fuse_single_source(self):
        """测试单路融合"""
        candidates = [[
            {"id": "a", "score": 0.9, "source": "code"},
            {"id": "b", "score": 0.5, "source": "code"},
        ]]
        result = rrf_fuse(candidates, k=60)
        assert len(result) == 2
        assert result[0]["id"] == "a"
        assert result[0]["rrf_score"] > 0
        assert "sources" in result[0]
    
    def test_rrf_fuse_multi_source(self):
        """测试多路融合"""
        candidates = [
            [{"name": "a", "score": 0.9, "source": "code"}],
            [{"name": "a", "score": 0.8, "source": "schema"}],
            [{"name": "b", "score": 0.7, "source": "api_docs"}],
        ]
        result = rrf_fuse_multi_source(candidates, k=60)
        assert len(result) == 2
        # a 出现在两路，分数应该更高
        a_entry = next(r for r in result if r["title"] == "a")
        assert len(a_entry["sources"]) == 2
    
    def test_rrf_fuse_dedup(self):
        """测试去重"""
        candidates = [
            [{"id": "a", "score": 0.9, "source": "code"}],
            [{"id": "a", "score": 0.8, "source": "code"}],
        ]
        result = rrf_fuse(candidates, k=60)
        assert len(result) == 1
    
    def test_rrf_fuse_multi_source_with_sources(self):
        """测试加权融合"""
        candidates = [
            [{"name": "a", "score": 0.9, "source_type": "code"}],
            [{"name": "b", "score": 0.8, "source_type": "wiki"}],
        ]
        result = rrf_fuse_multi_source(candidates, k=60)
        assert len(result) == 2
    
    def test_rrf_fuse_multi_source_empty(self):
        """测试加权融合空输入"""
        assert rrf_fuse_multi_source([], k=60) == []
    
    def test_rrf_fuse_multi_source_single(self):
        """测试加权融合单路"""
        candidates = [[
            {"id": "a", "score": 0.9, "source_type": "code"},
        ]]
        result = rrf_fuse_multi_source(candidates, k=60)
        assert len(result) == 1
    
    def test_get_rrf_k_for_label(self):
        """测试 k 值选择"""
        assert _get_rrf_k_for_label("") == 60
        assert _get_rrf_k_for_label("code_function") == 40
        assert _get_rrf_k_for_label("schema_entity") == 45
        assert _get_rrf_k_for_label("api_doc") == 50
        assert _get_rrf_k_for_label("wiki") == 70
        assert _get_rrf_k_for_label("unknown_source") == 60
    
    def test_get_rrf_k_label_heuristics(self):
        """测试 k 值启发式"""
        assert _get_rrf_k_for_label("route_handler") == 40  # code
        assert _get_rrf_k_for_label("table_struct") == 45  # schema
        assert _get_rrf_k_for_label("business_logic") == 55
    
    def test_get_source_weight(self):
        """测试来源权重"""
        assert _get_source_weight({"source_type": "code"}) == 1.5
        assert _get_source_weight({"type": "wiki"}) == 0.9
        assert _get_source_weight({"source_type": "schema"}) == 1.0
        assert _get_source_weight({}) == 1.0
    
    def test_rrf_fuse_with_items_no_id(self):
        """测试无 id 的 item"""
        candidates = [[
            {"name": "item1", "score": 0.9, "source": "code"},
        ]]
        result = rrf_fuse(candidates, k=60)
        assert len(result) == 1
