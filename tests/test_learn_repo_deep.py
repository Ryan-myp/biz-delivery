"""
Learn Repo 深度测试套件
覆盖：CodeKnowledgeExtractor、数据类、KnowledgeCache、KnowledgeWriter、IncrementalScanner
目标：scripts/learn_repo.py 覆盖率 ≥60%
"""
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scripts.learn_repo import (
    CodeKnowledgeExtractor, IRDocument, StructDef, FuncDef, RouteDef,
    ImportDef, TableDef, ServiceDef, CallEdge, DataFlowNode,
    KnowledgeCache, KnowledgeWriter, IncrementalScanner,
    _generate_enhanced_summary, generate_kb_cache,
)


# ─── 数据类测试 ──────────────────────────────────────────────

class TestDataClasses:
    """IR 数据类测试"""

    def test_ir_document_defaults(self):
        """测试 IRDocument 默认值"""
        doc = IRDocument(repo_name="test", repo_path="/tmp", language="go")
        assert doc.structs == []
        assert doc.functions == []
        assert doc.routes == []
        assert doc.call_graph == []
        assert doc.test_files == []

    def test_ir_document_with_data(self):
        """测试 IRDocument 带数据"""
        doc = IRDocument(
            repo_name="ad-service",
            repo_path="/tmp/ad",
            language="go",
            structs=[StructDef(name="BidRequest", file="bid.go")],
            functions=[FuncDef(name="PlaceBid", file="bid.go")],
            routes=[RouteDef(path="/api/bid", method="POST", handler="PlaceBid", module="handler", file="bid.go")],
        )
        assert len(doc.structs) == 1
        assert len(doc.functions) == 1
        assert doc.structs[0].name == "BidRequest"

    def test_structdef(self):
        """测试 StructDef"""
        s = StructDef(name="User", file="user.go", fields=[{"name": "id", "type": "int"}])
        assert s.name == "User"
        assert s.fields[0]["name"] == "id"

    def test_funcdef(self):
        """测试 FuncDef"""
        f = FuncDef(name="PlaceBid", file="bid.go", params=[{"name": "ctx", "type": "context.Context"}], returns="error")
        assert f.name == "PlaceBid"
        assert f.returns == "error"

    def test_routedef(self):
        """测试 RouteDef"""
        r = RouteDef(path="/api/bid", method="POST", handler="PlaceBid", module="handler", file="bid.go")
        assert r.method == "POST"
        assert r.handler == "PlaceBid"

    def test_importdef(self):
        """测试 ImportDef"""
        imp = ImportDef(module="fmt", names=["Println"])
        assert imp.module == "fmt"

    def test_caledge(self):
        """测试 CallEdge"""
        edge = CallEdge(caller="PlaceBid", caller_pkg="handler", callee="SaveBid", callee_pkg="service", pos="bid.go:42")
        assert edge.caller == "PlaceBid"
        assert edge.callee == "SaveBid"

    def test_data_flow_node(self):
        """测试 DataFlowNode"""
        node = DataFlowNode(var_name="bid", kind="definition", lineno=42, file="bid.go")
        assert node.var_name == "bid"
        assert node.lineno == 42


# ─── CodeKnowledgeExtractor 测试 ─────────────────────────────

class TestCodeKnowledgeExtractor:
    """代码知识提取器测试"""

    def test_init_go(self, tmp_path):
        ext = CodeKnowledgeExtractor(str(tmp_path), "go")
        assert ext.language == "go"
        assert ext.repo_path == tmp_path

    def test_init_python(self, tmp_path):
        ext = CodeKnowledgeExtractor(str(tmp_path), "python")
        assert ext.language == "python"

    def test_init_java(self, tmp_path):
        ext = CodeKnowledgeExtractor(str(tmp_path), "java")
        assert ext.language == "java"

    def test_extract_unsupported_language(self, tmp_path):
        ext = CodeKnowledgeExtractor(str(tmp_path), "rust")
        result = ext.extract()
        assert "error" in result
        assert "rust" in result["error"].lower()

    def test_extract_go_empty_repo(self, tmp_path):
        ext = CodeKnowledgeExtractor(str(tmp_path), "go")
        result = ext.extract()
        assert isinstance(result, dict)

    def test_extract_go_with_files(self, tmp_path):
        go_file = tmp_path / "main.go"
        go_file.write_text("""package main\nimport "fmt"\nfunc main() { fmt.Println("hello") }\nfunc PlaceBid(ctx string) error { return nil }\n""")
        ext = CodeKnowledgeExtractor(str(tmp_path), "go")
        result = ext.extract()
        assert isinstance(result, dict)

    def test_extract_python_empty_repo(self, tmp_path):
        ext = CodeKnowledgeExtractor(str(tmp_path), "python")
        result = ext.extract()
        assert isinstance(result, dict)

    def test_extract_python_with_files(self, tmp_path):
        py_file = tmp_path / "app.py"
        py_file.write_text("def place_bid(request):\n    return {'status': 'ok'}\nclass BidService:\n    def save(self, bid):\n        pass\n")
        ext = CodeKnowledgeExtractor(str(tmp_path), "python")
        result = ext.extract()
        assert isinstance(result, dict)


# ─── KnowledgeCache 测试 ────────────────────────────────────

class TestKnowledgeCache:
    """知识库缓存测试"""

    def test_cache_init(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache = KnowledgeCache(str(cache_dir))
        assert cache.cache == {}
        # cache_file 在 __init__ 时设置，但不一定存在（mkdir 只创建目录）
        assert "kb_cache.json" in str(cache.cache_file)

    def test_set_and_get(self, tmp_path):
        cache = KnowledgeCache(str(tmp_path / "cache"))
        cache.set("key1", {"data": "value"})
        # get 返回的是完整 entry（含 timestamp/ttl）
        entry = cache.get("key1")
        assert entry is not None
        assert entry["data"] == {"data": "value"}
        assert "timestamp" in entry
        assert "ttl" in entry

    def test_get_missing_key(self, tmp_path):
        cache = KnowledgeCache(str(tmp_path / "cache"))
        assert cache.get("missing") is None
        assert cache.get("missing", "default") == "default"

    def test_is_expired_new(self, tmp_path):
        cache = KnowledgeCache(str(tmp_path / "cache"))
        cache.set("key1", {"data": "value"}, ttl=3600)
        assert cache.is_expired("key1") is False

    def test_is_expired_old(self, tmp_path):
        cache = KnowledgeCache(str(tmp_path / "cache"))
        cache.set("key1", {"data": "value"}, ttl=0)
        time.sleep(0.1)
        assert cache.is_expired("key1") is True

    def test_invalidate(self, tmp_path):
        cache = KnowledgeCache(str(tmp_path / "cache"))
        cache.set("key1", {"data": "value"})
        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_persistence(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        cache = KnowledgeCache(cache_dir)
        cache.set("key1", {"data": "value"})
        cache2 = KnowledgeCache(cache_dir)
        entry = cache2.get("key1")
        assert entry is not None
        assert entry["data"] == {"data": "value"}

    def test_load_invalid_json(self, tmp_path):
        cache_file = tmp_path / "cache" / "kb_cache.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("not valid json {{{")
        cache = KnowledgeCache(str(tmp_path / "cache"))
        assert cache.cache == {}


# ─── KnowledgeWriter 测试 ────────────────────────────────────

class TestKnowledgeWriter:
    """知识库写入器测试"""

    def test_write_architecture(self, tmp_path):
        writer = KnowledgeWriter()
        files = writer.write({"architecture": "# 架构总览"}, str(tmp_path / "kb"))
        assert "architecture.md" in files
        assert (tmp_path / "kb" / "architecture.md").exists()

    def test_write_flows(self, tmp_path):
        writer = KnowledgeWriter()
        files = writer.write({"business_flows": "# 业务流程"}, str(tmp_path / "kb"))
        assert "flows.md" in files

    def test_write_multiple(self, tmp_path):
        writer = KnowledgeWriter()
        files = writer.write({"architecture": "arch", "business_flows": "flows", "database_schema": "schema"}, str(tmp_path / "kb"))
        assert len(files) == 3

    def test_write_empty(self, tmp_path):
        writer = KnowledgeWriter()
        files = writer.write({}, str(tmp_path / "kb"))
        assert files == []

    def test_write_glossary(self, tmp_path):
        writer = KnowledgeWriter()
        files = writer.write({"glossary": {"出价": "Bid", "广告组": "AdGroup"}}, str(tmp_path / "kb"))
        assert "glossary.md" in files
        content = (tmp_path / "kb" / "glossary.md").read_text()
        assert "出价" in content
        assert "Bid" in content


# ─── IncrementalScanner 测试 ─────────────────────────────────

class TestIncrementalScanner:
    """增量扫描器测试"""

    def test_find_changed_files_empty_repo(self, tmp_path):
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir(parents=True, exist_ok=True)
        scanner = IncrementalScanner(str(kb_dir))
        result = scanner.find_changed_files(tmp_path)
        assert isinstance(result, list)

    def test_find_changed_files_no_kb(self, tmp_path):
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir(parents=True, exist_ok=True)
        scanner = IncrementalScanner(str(kb_dir))
        result = scanner.find_changed_files(tmp_path)
        assert isinstance(result, list)


# ─── 辅助函数测试 ─────────────────────────────────────────────

class TestHelpers:
    """辅助函数测试"""

    def test_generate_enhanced_summary(self, tmp_path):
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir(parents=True, exist_ok=True)
        ir = {"functions": [{"name": "PlaceBid"}], "routes": [{"path": "/api/bid"}]}
        summary = _generate_enhanced_summary(ir, str(kb_dir))
        assert isinstance(summary, str)

    def test_generate_enhanced_summary_empty(self, tmp_path):
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir(parents=True, exist_ok=True)
        summary = _generate_enhanced_summary({}, str(kb_dir))
        assert isinstance(summary, str)

    def test_generate_kb_cache_missing_dir(self, tmp_path):
        result = generate_kb_cache(str(tmp_path / "nonexistent"), str(tmp_path / "cache"))
        assert result == {}

    def test_generate_kb_cache_empty(self, tmp_path):
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        result = generate_kb_cache(str(kb_dir), str(tmp_path / "cache"))
        assert isinstance(result, dict)
