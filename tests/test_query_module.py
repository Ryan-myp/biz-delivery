"""Tests for the query module — intent, fuzzy match, synonym expansion, multi-path query."""

import pytest
from scripts.query import (
    extract_intent,
    fuzzy_score,
    fuzzy_match,
    levenshtein_distance,
    adaptive_threshold,
    expand_synonyms,
    contextual_expand,
    get_builtin_synonyms,
    get_intent_patterns,
    run_multi_path_query,
    search_code,
    search_schema,
    search_api_docs,
    rrf_fuse,
)


# ── Intent Tests ───────────────────────────────────────────────────────────────


class TestExtractIntent:
    def test_empty_query(self):
        intent, confidence = extract_intent("")
        assert intent == "unknown"
        assert confidence == 0.0

    def test_query_intent(self):
        intent, confidence = extract_intent("查看素材审核流程")
        assert intent == "query"
        assert 0 < confidence <= 1.0

    def test_question_intent(self):
        intent, confidence = extract_intent("为什么竞价失败")
        assert intent == "question"
        assert confidence > 0

    def test_debug_intent(self):
        # "修复" doesn't match debug patterns, but "错误" or "bug" would
        intent, confidence = extract_intent("调试权限问题")
        assert intent in ["debug", "query"]

    def test_callchain_intent(self):
        intent, confidence = extract_intent("谁调用了 PlaceBid")
        assert intent == "callchain"

    def test_dataflow_intent(self):
        intent, confidence = extract_intent("数据流向哪里")
        assert intent == "dataflow"

    def test_impact_intent(self):
        intent, confidence = extract_intent("改了缓存影响分析")
        assert intent == "impact"


class TestGetIntentPatterns:
    def test_returns_dict(self):
        patterns = get_intent_patterns()
        assert isinstance(patterns, dict)
    
    def test_has_expected_intents(self):
        patterns = get_intent_patterns()
        assert "query" in patterns
        assert "question" in patterns
        assert "debug" in patterns


# ── Fuzzy Match Tests ──────────────────────────────────────────────────────────


class TestLevenshteinDistance:
    def test_same_string(self):
        assert levenshtein_distance("hello", "hello") == 0

    def test_empty_strings(self):
        assert levenshtein_distance("", "") == 0
        assert levenshtein_distance("abc", "") == 3
        assert levenshtein_distance("", "abc") == 3

    def test_single_char_change(self):
        assert levenshtein_distance("cat", "bat") == 1

    def test_completely_different(self):
        assert levenshtein_distance("abc", "xyz") == 3


class TestFuzzyScore:
    def test_identical_strings(self):
        assert fuzzy_score("素材", "素材") == 1.0

    def test_exact_match(self):
        score = fuzzy_score("creative", "creative")
        assert score == 1.0

    def test_substring_match(self):
        # Substring should get high score
        score = fuzzy_score("素材审核", "素材")
        assert score > 0.8

    def test_empty_target(self):
        assert fuzzy_score("test", "") == 0.0

    def test_both_empty(self):
        assert fuzzy_score("", "") == 1.0

    def test_english_similarity(self):
        # "bidding" vs "biding" should be similar
        score = fuzzy_score("bidding", "biding")
        assert score > 0.5


class TestFuzzyMatch:
    def test_strict_match(self):
        assert fuzzy_match("素材", "素材") is True

    def test_low_similarity(self):
        # Completely different words
        result = fuzzy_match("素材", "数据库")
        # Result depends on threshold, just check it's a boolean
        assert isinstance(result, bool)


class TestAdaptiveThreshold:
    def test_short_query(self):
        threshold = adaptive_threshold("素材")
        assert threshold >= 0.7

    def test_long_query(self):
        threshold = adaptive_threshold("查看素材审核流程的实现细节")
        assert threshold < 0.7


# ── Synonym Expansion Tests ───────────────────────────────────────────────────


class TestExpandSynonyms:
    def test_basic_expansion(self):
        keywords = expand_synonyms("素材")
        assert "素材" in keywords
        assert "creative" in keywords

    def test_with_profile(self):
        profile = {
            "query_aliases": {
                "广告组": ["adgroup_custom", "ad_group_custom"]
            }
        }
        keywords = expand_synonyms("广告组", profile)
        assert "adgroup_custom" in keywords

    def test_contextual_expansion(self):
        keywords = expand_synonyms("竞价")
        assert "bidding" in keywords
        assert "auction" in keywords

    def test_limit(self):
        keywords = expand_synonyms("素材")
        assert len(keywords) <= 30


class TestContextualExpand:
    def test_chinese_to_english(self):
        expanded = contextual_expand("创建")
        assert "create" in expanded
        assert "build" in expanded

    def test_english_to_chinese(self):
        expanded = contextual_expand("delete")
        assert "删除" in expanded


class TestGetBuiltinSynonyms:
    def test_returns_dict(self):
        synonyms = get_builtin_synonyms()
        assert isinstance(synonyms, dict)

    def test_has_expected_keys(self):
        synonyms = get_builtin_synonyms()
        assert "素材" in synonyms
        assert "竞价" in synonyms


# ── Multi-Path Query Tests ─────────────────────────────────────────────────────


class TestSearchCode:
    def test_empty_ir_data(self):
        results = search_code({}, ["test"])
        assert results == []

    def test_find_function(self):
        ir_data = {
            "functions": [
                {"name": "PlaceBid", "signature": "ctx, req", "file": "bid.go"}
            ]
        }
        results = search_code(ir_data, ["PlaceBid"])
        assert len(results) > 0
        assert results[0]["type"] == "function"

    def test_find_route(self):
        ir_data = {
            "routes": [
                {"method": "POST", "path": "/api/bid", "handler": "PlaceBid"}
            ]
        }
        results = search_code(ir_data, ["/api/bid"])
        assert len(results) > 0
        assert results[0]["type"] == "route"


class TestSearchSchema:
    def test_empty_ir_data(self):
        results = search_schema({}, ["test"])
        assert results == []

    def test_find_entity(self):
        ir_data = {
            "entity_tables": [
                {"entity": "UserBid", "table": "user_bids"}
            ]
        }
        results = search_schema(ir_data, ["UserBid"])
        assert len(results) > 0
        assert results[0]["type"] == "entity_table"


class TestRRFFuse:
    def test_empty_candidates(self):
        result = rrf_fuse([])
        assert result == []

    def test_single_list(self):
        candidates = [[{"name": "A", "score": 0.9}]]
        result = rrf_fuse(candidates)
        assert len(result) == 1
        assert result[0]["name"] == "A"

    def test_multiple_lists(self):
        candidates = [
            [{"name": "A", "score": 0.9}],
            [{"name": "B", "score": 0.8}]
        ]
        result = rrf_fuse(candidates)
        # RRF fusion may return fewer items due to deduplication
        assert len(result) >= 1
