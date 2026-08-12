"""End-to-end tests for biz-delivery pipeline."""

import pytest
import json
from pathlib import Path
from scripts.query import run_evidence_query, extract_intent, expand_synonyms


class TestEvidenceQueryE2E:
    """Evidence query end-to-end tests."""
    
    def test_full_query_pipeline(self):
        """Test complete query pipeline."""
        # 准备测试数据
        ir_data = {
            "functions": [
                {"name": "PlaceBid", "signature": "ctx, req *BidRequest", "file": "bid.go"},
                {"name": "ReviewCreative", "signature": "ctx, req *ReviewRequest", "file": "review.go"},
            ],
            "routes": [
                {"method": "POST", "path": "/api/bid", "handler": "PlaceBid"},
                {"method": "POST", "path": "/api/review", "handler": "ReviewCreative"},
            ],
            "entity_tables": [
                {"entity": "AdGroup", "table": "ad_groups", "file": "schema.go"},
            ],
            "error_codes": [
                {"name": "BID_FAILED", "code": "1001", "message": "Bid processing failed"},
            ]
        }
        
        # 执行查询
        result = run_evidence_query(
            query="素材审核流程",
            ir_data=ir_data,
            top_k=10
        )
        
        # 验证结果
        assert "intent" in result
        assert "results" in result
        assert isinstance(result["results"], list)
        assert result["stats"]["total_results"] >= 0
    
    def test_multilingual_query(self):
        """Test queries in different languages."""
        ir_data = {
            "functions": [
                {"name": "GetCampaign", "signature": "ctx, id", "file": "campaign.go"},
            ]
        }
        
        # 中文查询
        result_cn = run_evidence_query(
            query="获取广告计划",
            ir_data=ir_data,
            top_k=5
        )
        assert result_cn["intent"] in ["query", "question"]
        
        # 英文查询
        result_en = run_evidence_query(
            query="Get campaign info",
            ir_data=ir_data,
            top_k=5
        )
        assert result_en["intent"] == "query"
    
    def test_query_with_profile(self):
        """Test query with custom profile."""
        ir_data = {
            "functions": [
                {"name": "ShareCreative", "signature": "ctx, req", "file": "share.go"},
            ]
        }
        
        profile = {
            "query_aliases": {
                "素材分享": ["share", "share_new", "share_addon"]
            }
        }
        
        result = run_evidence_query(
            query="素材分享功能",
            ir_data=ir_data,
            profile=profile,
            top_k=5
        )
        
        # 验证使用了 profile 中的别名
        assert "素材分享" in result["expanded_queries"] or "share" in result["expanded_queries"]


class TestIntentRecognition:
    """Intent recognition tests."""
    
    def test_chinese_query_intent(self):
        """Test Chinese query intent extraction."""
        test_cases = [
            ("查看素材", "query"),
            ("为什么竞价失败", "question"),
            ("调试权限问题", "debug"),
            ("谁调用了 PlaceBid", "callchain"),
            ("数据流向哪里", "dataflow"),
            ("改了缓存影响分析", "impact"),
        ]
        
        for query, expected_intent in test_cases:
            intent, confidence = extract_intent(query)
            assert intent == expected_intent, f"Expected {expected_intent} for '{query}', got {intent}"
    
    def test_english_query_intent(self):
        """Test English query intent extraction."""
        test_cases = [
            ("Get creative info", "query"),
            ("How does bidding work", "question"),
            ("Fix permission error", "debug"),
            ("Who called PlaceBid", "callchain"),
        ]
        
        for query, expected_intent in test_cases:
            intent, confidence = extract_intent(query)
            assert intent == expected_intent, f"Expected {expected_intent} for '{query}', got {intent}"


class TestSynonymExpansion:
    """Synonym expansion tests."""
    
    def test_basic_expansion(self):
        """Test basic synonym expansion."""
        keywords = expand_synonyms("素材")
        assert "素材" in keywords
        assert "creative" in keywords
    
    def test_profile_expansion(self):
        """Test expansion with profile aliases."""
        profile = {
            "query_aliases": {
                "自定义术语": ["custom_term1", "custom_term2"]
            }
        }
        keywords = expand_synonyms("自定义术语", profile)
        assert "custom_term1" in keywords
        assert "custom_term2" in keywords


class TestQueryPerformance:
    """Query performance tests."""
    
    def test_query_speed(self):
        """Test that query executes within reasonable time."""
        import time
        
        ir_data = {
            "functions": [
                {"name": f"Func{i}", "signature": "ctx", "file": f"file{i}.go"}
                for i in range(100)
            ]
        }
        
        start = time.time()
        for _ in range(10):
            run_evidence_query(
                query="测试查询",
                ir_data=ir_data,
                top_k=10
            )
        elapsed = time.time() - start
        
        assert elapsed < 5.0, f"Query too slow: {elapsed}s for 10 iterations"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
