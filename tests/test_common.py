"""Tests for scripts/_common.py functions to improve coverage."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts._common import (
    _extract_compound_terms,
    extract_prd_keywords,
    fuse_cross_repo_evidence,
    build_multi_repo_cache_map,
    generate_query_variants,
    query_evidence_for_prd,
)


# ===========================================================================
# _extract_compound_terms
# ===========================================================================

class TestExtractCompoundTerms:
    def test_no_compounds(self):
        result = _extract_compound_terms("hello world")
        assert result == []

    def test_with_compounds(self):
        text = "素材审核流程和竞价引擎配置"
        result = _extract_compound_terms(text)
        assert "素材审核" in result
        assert "竞价引擎" in result

    def test_partial_match(self):
        text = "这里有广告组和广告计划的相关说明"
        result = _extract_compound_terms(text)
        assert "广告组" in result
        assert "广告计划" in result


# ===========================================================================
# extract_prd_keywords
# ===========================================================================

class TestExtractPrdKeywords:
    def test_empty_text(self):
        result = extract_prd_keywords("")
        assert result == []

    def test_chinese_text(self):
        text = "创建广告组，支持素材审核和竞价引擎"
        result = extract_prd_keywords(text)
        assert len(result) > 0
        assert "素材审核" in result or "竞价引擎" in result

    def test_camelcase_entities(self):
        text = "用户需要通过 CreateUser 接口调用 AdGroupManager"
        result = extract_prd_keywords(text)
        assert any("CreateUser" in k for k in result) or any("AdGroupManager" in k for k in result)

    def test_domain_keywords(self):
        text = "campaign budget and impression tracking"
        result = extract_prd_keywords(text)
        assert "campaign" in result
        assert "budget" in result

    def test_max_keywords_limit(self):
        text = "a b c d e f g h i j k l m n o p q r s t u v w x y z"
        result = extract_prd_keywords(text, max_keywords=5)
        assert len(result) <= 5

    def test_deduplication(self):
        text = "user user User USER"
        result = extract_prd_keywords(text)
        # Keeps first occurrence per lowercase form
        lower = [k.lower() for k in result]
        assert "user" in lower
        assert len(result) <= 3


# ===========================================================================
# fuse_cross_repo_evidence
# ===========================================================================

class TestFuseCrossRepoEvidence:
    def test_empty_map(self):
        result = fuse_cross_repo_evidence({})
        assert result == []

    def test_single_repo(self):
        evidence = [{"type": "code", "title": "User", "score": 0.9}]
        result = fuse_cross_repo_evidence({"repo1": evidence})
        assert len(result) == 1
        assert result[0]["repos"] == ["repo1"]

    def test_multi_repo_dedup(self):
        item = {"type": "code", "title": "User", "score": 0.8}
        result = fuse_cross_repo_evidence({"repo1": [item], "repo2": [item]})
        assert len(result) == 1
        assert set(result[0]["repos"]) == {"repo1", "repo2"}

    def test_multi_item_sorting(self):
        result = fuse_cross_repo_evidence({
            "repo1": [
                {"type": "code", "title": "A", "score": 0.3},
                {"type": "code", "title": "B", "score": 0.9},
            ],
        })
        assert result[0]["title"] == "B"
        assert result[1]["title"] == "A"

    def test_top_k_limit(self):
        items = [{"type": "code", "title": f"item{i}", "score": 0.5} for i in range(10)]
        result = fuse_cross_repo_evidence({"repo": items}, top_k=3)
        assert len(result) == 3

    def test_cross_repo_bonus_priority(self):
        single = {"type": "code", "title": "single", "score": 0.9}
        multi = {"type": "code", "title": "multi", "score": 0.7}
        result = fuse_cross_repo_evidence({
            "repo1": [single], "repo2": [single],
            "repo3": [multi], "repo4": [multi],
        })
        # single: 0.9+0.2=1.1, multi: 0.7+0.2=0.9
        assert result[0]["title"] == "single"


# ===========================================================================
# build_multi_repo_cache_map
# ===========================================================================

class TestBuildMultiRepoCacheMap:
    def test_empty_list(self):
        assert build_multi_repo_cache_map([]) == {}

    def test_missing_dir(self, tmp_path):
        assert build_multi_repo_cache_map([str(tmp_path / "missing")]) == {}

    def test_valid_cache_file(self, tmp_path):
        cache_dir = tmp_path / "cache1"
        cache_dir.mkdir()
        (cache_dir / "ir_cache.json").write_text(json.dumps({
            "repo_name": "svc-a", "structs": [{"name": "User"}],
        }))
        result = build_multi_repo_cache_map([str(cache_dir)])
        assert "svc-a" in result
        assert result["svc-a"]["structs"][0]["name"] == "User"

    def test_corrupt_cache_file(self, tmp_path):
        cache_dir = tmp_path / "cache2"
        cache_dir.mkdir()
        (cache_dir / "ir_cache.json").write_text("bad json {{{")
        assert build_multi_repo_cache_map([str(cache_dir)]) == {}

    def test_multiple_caches(self, tmp_path):
        for i in range(3):
            cache_dir = tmp_path / f"cache{i}"
            cache_dir.mkdir()
            (cache_dir / "ir_cache.json").write_text(json.dumps({
                "repo_name": f"svc-{i}", "structs": [],
            }))
        dirs = [str(tmp_path / f"cache{i}") for i in range(3)]
        result = build_multi_repo_cache_map(dirs)
        assert len(result) == 3
        assert "svc-0" in result and "svc-2" in result


# ===========================================================================
# generate_query_variants (direct from _common)
# ===========================================================================

class TestGenerateQueryVariants:
    def test_camelcase_split(self):
        variants = generate_query_variants("CreateUser")
        assert "create_user" in variants
        assert "create-user" in variants

    def test_abbreviation_expansion(self):
        variants = generate_query_variants("campaign review")
        assert "ad_plan" in variants or "推广计划" in variants
        assert "审核" in variants or "approval" in variants

    def test_short_query_prefixes(self):
        variants = generate_query_variants("AB")
        assert "A" in variants or "AB" in variants

    def test_chinese_compound_split(self):
        variants = generate_query_variants("素材审核流程")
        assert "素材" in variants
        assert "审核" in variants

    def test_multi_word_split(self):
        variants = generate_query_variants("ad_group_campaign")
        assert "campaign" in variants
        assert "group" in variants

    def test_filters_numbers_and_short(self):
        variants = generate_query_variants("a1")
        for v in variants:
            assert not v.isdigit()

    def test_limit_15(self):
        variants = generate_query_variants("a very long query with many words here to trigger all expansion paths")
        assert len(variants) <= 15

    def test_empty_query(self):
        assert generate_query_variants("") == []


# ===========================================================================
# query_evidence_for_prd
# ===========================================================================

class TestQueryEvidenceForPrd:
    def _mock_qe(self):
        return {
            'expand_synonyms': lambda *a, **kw: [a[0] if a else 'default'],
            'expand_synonyms_with_ir': lambda *a, **kw: [a[0] if a else 'default'],
            'run_evidence_query': lambda **kw: {'evidence': []},
            'smart_search': lambda *a, **kw: [],
            'understand_query': lambda *a, **kw: 'query',
            'enhanced_semantic_search': lambda *a, **kw: [],
            'cross_field_search': lambda *a, **kw: [],
        }

    @patch('scripts._common._get_query_evidence')
    def test_no_ir_cache_no_profile(self, mock_qe):
        mock_qe.return_value = self._mock_qe()
        result = query_evidence_for_prd(prd_text="test query", profile={})
        assert "keywords" in result
        assert "evidence" in result
        assert result["total"] >= 0

    @patch('scripts._common._get_query_evidence')
    def test_with_ir_cache_dict(self, mock_qe):
        mock_qe.return_value = self._mock_qe()
        ir_cache = {"repo_name": "test", "structs": [], "functions": []}
        result = query_evidence_for_prd(
            prd_text="test query", profile={"business_domain": "test"}, ir_cache=ir_cache,
        )
        assert "keywords" in result

    @patch('scripts._common._get_query_evidence')
    def test_with_cache_dir(self, mock_qe, tmp_path):
        mock_qe.return_value = self._mock_qe()
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "ir_cache.json").write_text(json.dumps({
            "repo_name": "my-repo", "structs": [{"name": "User"}],
        }))
        result = query_evidence_for_prd(
            prd_text="test query", profile={"business_domain": "test"}, cache_dir=str(cache_dir),
        )
        assert "keywords" in result

    @patch('scripts._common._get_query_evidence')
    def test_enable_variant_expansion(self, mock_qe):
        mock_qe.return_value = self._mock_qe()
        result = query_evidence_for_prd(
            prd_text="CreateUser 接口测试", profile={"business_domain": "test"},
            enable_variant_expansion=True,
        )
        assert "variants" in result
        assert isinstance(result["variants"], list)

    @patch('scripts._common._get_query_evidence')
    def test_profile_with_inner_key(self, mock_qe):
        mock_qe.return_value = self._mock_qe()
        result = query_evidence_for_prd(
            prd_text="test", profile={"profile": {"business_domain": "inner"}},
        )
        assert "keywords" in result
