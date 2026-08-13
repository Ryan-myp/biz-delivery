"""
Query Evidence 单文件版深度测试套件
覆盖：fuzzy 匹配、同义词扩展、语义搜索、多路搜索、RRF 融合、smart_search
目标：scripts/query_evidence.py 覆盖率 ≥60%
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import scripts.query_evidence as qe


SAMPLE_IR = {
    "functions": [
        {"name": "PlaceBid", "params": "ctx, req", "returns": "*Response",
         "file": "bid.go", "comment": "用户出价"},
        {"name": "GetBidStatus", "params": "ctx", "returns": "*StatusResponse",
         "file": "bid.go", "comment": "查询出价状态"},
        {"name": "UserLogin", "params": "ctx", "returns": "*Response",
         "file": "auth.go", "comment": "用户登录"},
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
    ],
    "error_codes": [
        {"name": "ERR_BID_DUPLICATE", "code": 4001, "message": "重复出价"},
    ],
    "business_logic": [
        {"handler": "PlaceBid", "description": "用户提交出价", "calls": ["ValidateBid", "SaveBid"]},
    ],
    "core_flows": [
        {"flow_name": "出价流程", "entry_point": "PlaceBid", "call_chain": ["PlaceBid", "SaveBid"]},
    ],
}


class TestFuzzyMatch:
    """模糊匹配测试"""
    
    def test_extract_intent(self):
        """测试意图提取"""
        intent, conf = qe.extract_intent("查询用户")
        assert isinstance(intent, str)
        assert isinstance(conf, float)
    
    def test_extract_intent_empty(self):
        """测试空查询"""
        intent, conf = qe.extract_intent("")
        assert intent == "unknown" or conf == 0.0
    
    def test_pinyin_initial(self):
        """测试拼音首字母"""
        assert isinstance(qe._pinyin_initial("中"), str)
    
    def test_chinese_to_pinyin_initials(self):
        """测试中文转拼音"""
        initials = qe._chinese_to_pinyin_initials("查询")
        assert isinstance(initials, str)
    
    def test_levenshtein_distance(self):
        """测试编辑距离"""
        assert qe.levenshtein_distance("kitten", "sitting") >= 0
        assert qe.levenshtein_distance("abc", "abc") == 0
    
    def test_fuzzy_match_true(self):
        """测试模糊匹配成功"""
        assert qe.fuzzy_match("placebid", "PlaceBid") is True
    
    def test_fuzzy_match_false(self):
        """测试模糊匹配失败"""
        assert qe.fuzzy_match("xyzxyz", "PlaceBid") is False
    
    def test_fuzzy_score(self):
        """测试模糊分数"""
        score = qe.fuzzy_score("placebid", "PlaceBid")
        assert isinstance(score, float)
    
    def test_chinese_word_segment(self):
        """测试中文分词"""
        words = qe._chinese_word_segment("用户出价")
        assert isinstance(words, list)
    
    def test_chinese_ngram_similarity(self):
        """测试 ngram 相似度"""
        sim = qe._chinese_ngram_similarity("出价", "出价功能")
        assert isinstance(sim, float)
    
    def test_pinyin_similarity(self):
        """测试拼音相似度"""
        sim = qe._pinyin_similarity("chujia", "出价")
        assert isinstance(sim, float)
    
    def test_char_ngrams(self):
        """测试字符 ngram"""
        ngrams = qe._char_ngrams("出价功能")
        assert isinstance(ngrams, set)
    
    def test_get_domain_context(self):
        """测试领域上下文"""
        ctx = qe._get_domain_context("用户出价")
        assert isinstance(ctx, list)


class TestSynonymExpansion:
    """同义词扩展测试"""
    
    def test_expand_synonyms(self):
        """测试同义词扩展"""
        result = qe.expand_synonyms("用户出价", profile=None)
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_expand_synonyms_with_profile(self):
        """测试带 profile 扩展"""
        profile = {"synonyms": {"用户": ["user", "客户"]}}
        result = qe.expand_synonyms("用户出价", profile=profile)
        assert isinstance(result, list)
    
    def test_expand_synonyms_with_ir(self):
        """测试带 IR 扩展"""
        result = qe.expand_synonyms_with_ir("出价", SAMPLE_IR)
        assert isinstance(result, list)
    
    def test_cross_language_expand(self):
        """测试跨语言扩展"""
        result = qe._cross_language_expand("出价", SAMPLE_IR)
        assert isinstance(result, list)
    
    def test_infer_related_terms(self):
        """测试相关词推断"""
        result = qe.infer_related_terms_from_ir("出价", SAMPLE_IR)
        assert isinstance(result, list)
    
    def test_generate_query_variants(self):
        """测试查询变体"""
        variants = qe._generate_query_variants("create_user")
        assert isinstance(variants, list)
    
    def test_to_snake_case(self):
        """测试蛇形命名"""
        assert qe._to_snake_case("CreateUser") == "create_user"
    
    def test_to_pascal_case(self):
        """测试帕斯卡命名"""
        assert qe._to_pascal_case("create_user") == "CreateUser"
    
    def test_to_camel_case(self):
        """测试驼峰命名"""
        assert qe._to_camel_case("create_user") == "createUser"
    
    def test_expand_query_variants_v2(self):
        """测试变体扩展 v2"""
        variants = qe.expand_query_variants_v2("create user")
        assert isinstance(variants, list)
    
    def test_expand_cross_language(self):
        """测试跨语言扩展"""
        variants = qe._expand_cross_language("用户", SAMPLE_IR)
        assert isinstance(variants, list)
    
    def test_discover_naming_conventions(self):
        """测试命名规范发现"""
        conventions = qe._discover_naming_conventions(SAMPLE_IR, "placebid")
        assert isinstance(conventions, list)
    
    def test_expand_abbreviations(self):
        """测试缩写扩展"""
        variants = qe._expand_abbreviations("api")
        assert isinstance(variants, list)
    
    def test_expand_domain_context(self):
        """测试领域上下文扩展"""
        variants = qe._expand_domain_context("出价")
        assert isinstance(variants, list)


class TestQueryClassification:
    """查询分类测试"""
    
    def test_classify_query(self):
        """测试查询分类"""
        qtype = qe.classify_query("查询用户")
        assert isinstance(qtype, str)
    
    def test_adaptive_threshold(self):
        """测试自适应阈值"""
        threshold = qe.adaptive_threshold("查询用户")
        assert 0 <= threshold <= 1


class TestSemanticSearch:
    """语义搜索测试"""
    
    def test_tokenize(self):
        """测试分词"""
        tokens = qe._tokenize("hello world")
        assert isinstance(tokens, list)
    
    def test_compute_tf(self):
        """测试 TF 计算"""
        tf = qe._compute_tf(["a", "b", "a"])
        assert tf["a"] == 2 / 3
    
    def test_compute_idf(self):
        """测试 IDF 计算"""
        idf = qe._compute_idf([["a", "b"], ["a", "c"]])
        assert isinstance(idf, dict)
    
    def test_cosine_similarity(self):
        """测试余弦相似度"""
        sim = qe._cosine_similarity({"a": 1}, {"a": 1})
        assert sim == 1.0
    
    def test_semantic_search(self):
        """测试语义搜索"""
        docs = ["用户出价功能", "用户登录功能", "广告组管理"]
        results = qe.semantic_search("出价", docs, top_k=2)
        assert isinstance(results, list)
    
    def test_semantic_expand_query(self):
        """测试语义扩展"""
        result = qe.semantic_expand_query("出价", SAMPLE_IR, top_k=5)
        assert isinstance(result, list)


class TestMultiPathSearch:
    """多路搜索测试"""
    
    def test_search_code(self):
        """测试代码搜索（真实签名：query + repo_path）"""
        results = qe.search_code("PlaceBid", "/tmp/repo", top_k=10, ir_cache=SAMPLE_IR)
        assert isinstance(results, list)
    
    def test_search_code_with_ir_cache(self):
        """测试带 IR 缓存的代码搜索"""
        results = qe.search_code("出价", "/tmp/repo", top_k=10, ir_cache=SAMPLE_IR)
        assert isinstance(results, list)
    
    def test_search_code_fuzzy(self):
        """测试模糊代码搜索"""
        results = qe._search_code_fuzzy(SAMPLE_IR, ["placebid"], top_k=10)
        assert isinstance(results, list)
    
    def test_search_schema(self):
        """测试 Schema 搜索"""
        results = qe.search_schema(SAMPLE_IR, ["user_bids"], top_k=10)
        assert isinstance(results, list)
    
    def test_search_api_docs(self):
        """测试 API 文档搜索"""
        results = qe.search_api_docs(SAMPLE_IR, ["/api/login"], top_k=10)
        assert isinstance(results, list)
    
    def test_search_business(self):
        """测试业务搜索"""
        results = qe.search_business(SAMPLE_IR, ["出价"], top_k=10)
        assert isinstance(results, list)
    
    def test_search_entity_relations(self):
        """测试实体关系搜索"""
        results = qe.search_entity_relations(SAMPLE_IR, ["UserBid"], top_k=10)
        assert isinstance(results, list)
    
    def test_query_wiki_evidence(self, tmp_path):
        """测试 Wiki 证据查询"""
        results = qe.query_wiki_evidence("出价", wiki_path=str(tmp_path), top_k=5)
        assert isinstance(results, list)


class TestRRFFusion:
    """RRF 融合测试"""
    
    def test_rrf_fuse(self):
        """测试基础融合"""
        candidates = [
            [{"id": "a", "score": 0.9, "source": "code"}],
            [{"id": "b", "score": 0.8, "source": "schema"}],
        ]
        result = qe.rrf_fuse(candidates, k=60)
        assert isinstance(result, list)
    
    def test_rrf_fuse_empty(self):
        """测试空输入"""
        assert qe.rrf_fuse([], k=60) == []
    
    def test_rrf_fuse_multi_source(self):
        """测试多源融合"""
        candidates = [
            [{"id": "a", "score": 0.9, "source_type": "code"}],
            [{"id": "b", "score": 0.8, "source_type": "wiki"}],
        ]
        result = qe.rrf_fuse_multi_source(candidates)
        assert isinstance(result, list)
    
    def test_get_rrf_k_for_label(self):
        """测试 k 值"""
        assert isinstance(qe._get_rrf_k_for_label("code"), int)


class TestVectorSearch:
    """向量搜索测试"""
    
    def test_simple_vectorizer(self):
        """测试向量化器"""
        vec = qe.SimpleVectorizer()
        docs = ["用户出价", "用户登录"]
        vec.fit(docs)
        vector = vec.transform("出价")
        assert len(vector) > 0
    
    def test_vectorizer_cosine(self):
        """测试向量化器余弦相似度"""
        vec = qe.SimpleVectorizer()
        vec.fit(["出价功能", "登录功能"])
        v1 = vec.transform(["出价功能"])[0]
        v2 = vec.transform(["出价功能"])[0]
        v3 = vec.transform(["登录功能"])[0]
        assert vec.cosine_similarity(v1, v2) > 0.9
        assert vec.cosine_similarity(v1, v3) < 1.0
    
    def test_get_vectorizer(self):
        """测试获取向量化器"""
        vec = qe.get_vectorizer()
        assert vec is not None
    
    def test_build_function_vectors(self):
        """测试函数向量构建"""
        vectors = qe.build_function_vectors(SAMPLE_IR)
        assert isinstance(vectors, list)
    
    def test_search_by_similarity(self):
        """测试相似度搜索"""
        results = qe.search_by_similarity("出价", SAMPLE_IR, top_k=5)
        assert isinstance(results, list)
    
    def test_bm25_score(self):
        """测试 BM25"""
        score = qe._bm25_score(["出价"], ["出价", "功能"])
        assert isinstance(score, float)
    
    def test_enhanced_semantic_search(self):
        """测试增强语义搜索"""
        results = qe.enhanced_semantic_search("出价", ["出价功能", "登录功能"], top_k=5)
        assert isinstance(results, list)
    
    def test_cross_field_search(self):
        """测试跨字段搜索"""
        results = qe.cross_field_search("出价", SAMPLE_IR, top_k=5)
        assert isinstance(results, list)


class TestSmartSearch:
    """智能搜索测试"""
    
    def test_understand_query(self):
        """测试查询理解"""
        result = qe.understand_query("查询用户出价")
        assert isinstance(result, dict)
    
    def test_smart_search(self):
        """测试智能搜索"""
        results = qe.smart_search("出价", SAMPLE_IR, profile=None, top_k=5)
        assert isinstance(results, list)
    
    def test_smart_search_with_kb(self, tmp_path):
        """测试带知识库搜索"""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "doc.md").write_text("# 出价\n用户出价功能说明\n", encoding="utf-8")
        
        results = qe.smart_search("出价", SAMPLE_IR, kb_dir=str(kb_dir), top_k=5)
        assert isinstance(results, list)
    
    def test_contextual_expand(self):
        """测试上下文扩展"""
        variants = qe.contextual_expand("出价")
        assert isinstance(variants, list)
    
    def test_smart_semantic_search(self):
        """测试智能语义搜索"""
        results = qe.smart_semantic_search("出价", SAMPLE_IR, top_k=5)
        assert isinstance(results, list)
