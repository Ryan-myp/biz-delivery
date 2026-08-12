"""Comprehensive tests for the query module."""

import pytest
from scripts.query import (
    extract_intent,
    fuzzy_score,
    expand_synonyms,
    run_multi_path_query,
    search_code,
    rrf_fuse,
)


class TestQueryModuleIntegration:
    """Integration tests for the query module."""
    
    def test_full_query_pipeline(self):
        """Test the full query pipeline from intent to results."""
        query = "查看素材审核流程"
        
        # Step 1: Intent recognition
        intent, confidence = extract_intent(query)
        assert intent == "query"
        assert 0 < confidence <= 1.0
        
        # Step 2: Synonym expansion
        keywords = expand_synonyms(query)
        assert len(keywords) > 0
        assert "素材" in keywords or "creative" in keywords
        
        # Step 3: Code search
        ir_data = {
            "functions": [
                {"name": "ReviewCreative", "signature": "ctx, req", "file": "review.go"},
                {"name": "PlaceBid", "signature": "ctx, req", "file": "bid.go"}
            ],
            "routes": [
                {"method": "POST", "path": "/api/review", "handler": "ReviewCreative"},
                {"method": "POST", "path": "/api/bid", "handler": "PlaceBid"}
            ]
        }
        results = search_code(ir_data, keywords)
        assert len(results) > 0
    
    def test_multilingual_query(self):
        """Test queries in both Chinese and English."""
        # Chinese query
        cn_intent, _ = extract_intent("查看广告组")
        assert cn_intent == "query"
        
        # English query
        en_intent, _ = extract_intent("Get ad group info")
        assert en_intent == "query"
    
    def test_synonym_expansion_with_profile(self):
        """Test synonym expansion with custom profile."""
        profile = {
            "query_aliases": {
                "自定义术语": ["custom_term1", "custom_term2"]
            }
        }
        keywords = expand_synonyms("自定义术语", profile)
        assert "custom_term1" in keywords
        assert "custom_term2" in keywords
    
    def test_rrf_fusion(self):
        """Test RRF fusion of multiple result lists."""
        candidates = [
            [
                {"name": "A", "score": 0.9, "type": "function"},
                {"name": "B", "score": 0.8, "type": "route"},
            ],
            [
                {"name": "B", "score": 0.85, "type": "route"},
                {"name": "C", "score": 0.7, "type": "struct"},
            ],
            [
                {"name": "A", "score": 0.95, "type": "function"},
            ]
        ]
        result = rrf_fuse(candidates)
        assert len(result) > 0
        # A should rank highest (appears in 2 lists with high scores)
        assert result[0]["name"] == "A"
    
    def test_empty_inputs(self):
        """Test handling of empty inputs."""
        intent, confidence = extract_intent("")
        assert intent == "unknown"
        assert expand_synonyms("") == [""]
        assert search_code({}, []) == []
        assert rrf_fuse([]) == []


class TestQueryEdgeCases:
    """Edge case tests for query module."""
    
    def test_unicode_in_query(self):
        """Test queries with Unicode characters."""
        intent, _ = extract_intent("查看🎯素材")
        assert intent in ["query", "unknown"]
    
    def test_numeric_query(self):
        """Test queries with numbers."""
        score = fuzzy_score("bid123", "bid456")
        assert 0 <= score <= 1.0
    
    def test_mixed_language_query(self):
        """Test mixed Chinese-English queries."""
        keywords = expand_synonyms("素材 creative review")
        assert "creative" in keywords
    
    def test_very_long_query(self):
        """Test very long query text."""
        long_query = "这是一个非常长的查询文本，包含了多个关键词和术语，用于测试系统对于长文本的处理能力。" * 10
        intent, confidence = extract_intent(long_query)
        assert isinstance(intent, str)
        assert 0 <= confidence <= 1.0


class TestQueryPerformance:
    """Performance-related tests."""
    
    def test_intent_extraction_speed(self):
        """Test that intent extraction is fast."""
        import time
        query = "查看素材审核流程的实现细节"
        
        start = time.time()
        for _ in range(1000):
            extract_intent(query)
        elapsed = time.time() - start
        
        # Should complete 1000 extractions in less than 1 second
        assert elapsed < 1.0, f"Intent extraction too slow: {elapsed}s for 1000 calls"
    
    def test_fuzzy_score_caching(self):
        """Test that fuzzy score caching works."""
        # First call
        score1 = fuzzy_score("素材", "creative")
        # Second call (should be cached)
        score2 = fuzzy_score("素材", "creative")
        
        assert score1 == score2
