"""
Query 模块深度测试套件
覆盖：evidence_query 主入口、wiki_query 全部函数
目标：scripts/query/ 覆盖率 ≥85%
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# Wiki Query 测试
# ============================================================

class TestWikiQuery:
    """Wiki 查询测试"""
    
    def _make_wiki(self, tmp_path):
        """创建 wiki 知识库"""
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        
        # 创建索引
        index = {
            "登录流程": {
                "path": "auth/login.md",
                "content": "用户登录流程：输入邮箱密码，验证后发放 token",
            },
            "出价功能": {
                "path": "auction/bid.md",
                "content": "用户出价功能：支持竞价，防止超卖",
            },
        }
        (wiki_dir / "index.json").write_text(
            json.dumps(index, ensure_ascii=False), encoding="utf-8"
        )
        
        # 创建文档目录
        docs_dir = wiki_dir / "docs"
        docs_dir.mkdir()
        (docs_dir / "login.md").write_text(
            "# 登录流程\n\n用户使用邮箱密码登录，包含验证码校验。\n", encoding="utf-8"
        )
        (docs_dir / "bid.md").write_text(
            "# 出价\n\n用户出价时校验库存。\n", encoding="utf-8"
        )
        
        return wiki_dir
    
    def test_wiki_index_load(self, tmp_path):
        """测试索引加载"""
        from scripts.query.wiki_query import WikiIndex
        wiki_dir = self._make_wiki(tmp_path)
        
        idx = WikiIndex(str(wiki_dir))
        assert len(idx.index) == 2
        assert "登录流程" in idx.index
    
    def test_wiki_index_no_index_file(self, tmp_path):
        """测试无索引文件"""
        from scripts.query.wiki_query import WikiIndex
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        idx = WikiIndex(str(empty_dir))
        assert idx.index == {}
    
    def test_wiki_index_search(self, tmp_path):
        """测试搜索"""
        from scripts.query.wiki_query import WikiIndex
        wiki_dir = self._make_wiki(tmp_path)
        
        idx = WikiIndex(str(wiki_dir))
        results = idx.search("登录", top_k=5)
        
        assert len(results) > 0
        assert results[0]["type"] == "wiki"
        assert "score" in results[0]
    
    def test_wiki_index_search_no_match(self, tmp_path):
        """测试无匹配结果"""
        from scripts.query.wiki_query import WikiIndex
        wiki_dir = self._make_wiki(tmp_path)
        
        idx = WikiIndex(str(wiki_dir))
        results = idx.search("完全不相关的内容xyz", top_k=5)
        assert len(results) == 0
    
    def test_calculate_score_empty(self, tmp_path):
        """测试空内容分数"""
        from scripts.query.wiki_query import WikiIndex
        wiki_dir = self._make_wiki(tmp_path)
        
        idx = WikiIndex(str(wiki_dir))
        score = idx._calculate_score("登录", "", "登录")
        assert score == 0.0
    
    def test_load_wiki_index(self, tmp_path):
        """测试 load_wiki_index"""
        from scripts.query.wiki_query import load_wiki_index
        wiki_dir = self._make_wiki(tmp_path)
        
        idx = load_wiki_index(str(wiki_dir))
        assert len(idx.index) == 2
    
    def test_query_wiki(self, tmp_path):
        """测试 query_wiki"""
        from scripts.query.wiki_query import query_wiki
        wiki_dir = self._make_wiki(tmp_path)
        
        results = query_wiki("登录", wiki_path=str(wiki_dir), top_k=5)
        assert isinstance(results, list)
    
    def test_query_wiki_missing_path(self, tmp_path):
        """测试路径不存在"""
        from scripts.query.wiki_query import query_wiki
        results = query_wiki("登录", wiki_path=str(tmp_path / "missing"), top_k=5)
        assert results == []
    
    def test_query_cache(self, tmp_path):
        """测试缓存查询"""
        from scripts.query.wiki_query import query_cache
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        
        # 创建缓存文件
        cache = {
            "登录": [
                {"type": "wiki", "name": "登录流程", "score": 0.9, "content": "登录"}
            ]
        }
        (cache_dir / "wiki_cache.json").write_text(
            json.dumps(cache, ensure_ascii=False), encoding="utf-8"
        )
        
        results = query_cache("登录", cache_dir=str(cache_dir), top_k=5)
        assert len(results) > 0
    
    def test_query_cache_missing(self, tmp_path):
        """测试缓存不存在"""
        from scripts.query.wiki_query import query_cache
        results = query_cache("登录", cache_dir=str(tmp_path / "missing"), top_k=5)
        assert results == []
    
    def test_query_knowledge_graph(self, tmp_path):
        """测试知识图谱查询"""
        from scripts.query.wiki_query import query_knowledge_graph
        
        graph = {
            "nodes": [
                {"id": "登录", "type": "feature", "description": "用户登录"},
                {"id": "出价", "type": "feature", "description": "用户出价"},
            ],
            "edges": [
                {"from": "登录", "to": "出价", "relation": "前置"},
            ],
        }
        
        results = query_knowledge_graph("登录", graph_data=graph, top_k=5)
        assert isinstance(results, list)
    
    def test_query_knowledge_graph_empty(self, tmp_path):
        """测试空图谱"""
        from scripts.query.wiki_query import query_knowledge_graph
        results = query_knowledge_graph("登录", graph_data={}, top_k=5)
        assert isinstance(results, list)
    
    def test_search_markdown_docs(self, tmp_path):
        """测试 Markdown 文档搜索"""
        from scripts.query.wiki_query import search_markdown_docs
        wiki_dir = self._make_wiki(tmp_path)
        docs_dir = wiki_dir / "docs"
        
        results = search_markdown_docs("登录", docs_dir=str(docs_dir), top_k=5)
        assert len(results) > 0
    
    def test_search_markdown_docs_missing(self, tmp_path):
        """测试文档目录不存在"""
        from scripts.query.wiki_query import search_markdown_docs
        results = search_markdown_docs("登录", docs_dir=str(tmp_path / "missing"), top_k=5)
        assert results == []
    
    def test_query_wiki_evidence(self, tmp_path):
        """测试 wiki 证据查询主入口"""
        from scripts.query.wiki_query import query_wiki_evidence
        wiki_dir = self._make_wiki(tmp_path)
        
        results = query_wiki_evidence("登录", wiki_path=str(wiki_dir), top_k=5)
        assert isinstance(results, list)
    
    def test_query_wiki_evidence_no_path(self, tmp_path):
        """测试无 wiki 路径"""
        from scripts.query.wiki_query import query_wiki_evidence
        results = query_wiki_evidence("登录", wiki_path=None, top_k=5)
        assert results == []


# ============================================================
# Evidence Query 主入口测试
# ============================================================

class TestEvidenceQuery:
    """证据查询主入口测试"""
    
    def _make_ir(self):
        """构造 IR 数据"""
        return {
            "functions": [
                {"name": "PlaceBid", "params": "ctx, req", "returns": "*Response",
                 "file": "bid.go", "comment": "用户出价"},
                {"name": "GetBidStatus", "params": "ctx", "returns": "*StatusResponse",
                 "file": "bid.go", "comment": "查询出价状态"},
            ],
            "routes": [
                {"method": "POST", "path": "/api/auction/bid", "handler": "PlaceBid",
                 "comment": "提交出价"},
                {"method": "GET", "path": "/api/auction/status", "handler": "GetBidStatus",
                 "comment": "查询状态"},
            ],
            "entity_tables": [
                {"entity": "UserBid", "table": "user_bids", "fields": ["user_id", "amount"]},
            ],
            "error_codes": [
                {"name": "ERR_BID_DUPLICATE", "code": 4001, "message": "重复出价"},
            ],
        }
    
    def test_run_evidence_query_full(self, tmp_path):
        """测试完整查询"""
        from scripts.query.evidence_query import run_evidence_query
        ir = self._make_ir()
        
        result = run_evidence_query(
            query="用户出价",
            ir_data=ir,
            profile=None,
            wiki_path=None,
            top_k=10,
        )
        
        assert "intent" in result
        assert "results" in result
        assert "expanded_queries" in result
        assert "stats" in result
        assert "sources" in result
    
    def test_run_evidence_query_no_ir(self):
        """测试无 IR 数据"""
        from scripts.query.evidence_query import run_evidence_query
        
        result = run_evidence_query(
            query="用户出价",
            ir_data=None,
            sources=["code"],
        )
        
        assert result["stats"]["total_results"] >= 0
    
    def test_run_evidence_query_code_only(self, tmp_path):
        """测试仅代码源"""
        from scripts.query.evidence_query import run_evidence_query
        ir = self._make_ir()
        
        result = run_evidence_query(
            query="PlaceBid",
            ir_data=ir,
            sources=["code"],
            top_k=5,
        )
        
        assert "code" in result["path_results"]
        assert result["sources"] == ["code"]
    
    def test_run_evidence_query_unweighted(self, tmp_path):
        """测试非加权融合"""
        from scripts.query.evidence_query import run_evidence_query
        ir = self._make_ir()
        
        result = run_evidence_query(
            query="出价",
            ir_data=ir,
            sources=["code", "schema"],
            top_k=5,
            use_weighted_fusion=False,
        )
        
        assert "code" in result["path_results"]
        assert "schema" in result["path_results"]
    
    def test_run_evidence_query_legacy(self, tmp_path):
        """测试 legacy 接口"""
        from scripts.query.evidence_query import run_evidence_query_legacy
        
        result = run_evidence_query_legacy(
            query="出价",
            profile_path=None,
            wiki_path=None,
            top_k=5,
            ir_cache=self._make_ir(),
        )
        
        assert "results" in result
    
    def test_run_evidence_query_legacy_with_profile(self, tmp_path):
        """测试 legacy 带 profile"""
        from scripts.query.evidence_query import run_evidence_query_legacy
        
        # 创建 profile 文件
        profile_file = tmp_path / "profile.json"
        profile_file.write_text(json.dumps({"name": "test"}), encoding="utf-8")
        
        result = run_evidence_query_legacy(
            query="出价",
            profile_path=str(profile_file),
            top_k=5,
        )
        
        assert "results" in result
    
    def test_smart_search(self, tmp_path):
        """测试智能搜索"""
        from scripts.query.evidence_query import smart_search
        ir = self._make_ir()
        
        results = smart_search("出价", ir, profile=None, top_k=5)
        assert isinstance(results, list)
    
    def test_smart_search_with_kb(self, tmp_path):
        """测试智能搜索带知识库"""
        from scripts.query.evidence_query import smart_search
        ir = self._make_ir()
        
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        (wiki_dir / "index.json").write_text(
            json.dumps({"出价": {"path": "bid.md", "content": "出价功能"}}, ensure_ascii=False),
            encoding="utf-8",
        )
        
        results = smart_search("出价", ir, profile=None, top_k=5, kb_dir=str(wiki_dir))
        assert isinstance(results, list)
