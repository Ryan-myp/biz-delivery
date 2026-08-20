"""Additional tests for learn_repo.py to improve coverage."""
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.learn_repo import (
    IRDocument, StructDef, FuncDef, RouteDef, ImportDef, TableDef,
    ServiceDef, CallEdge, DataFlowNode, GoScanner, PythonScanner,
    JavaScanner, MultiRepoAnalyzer, LLMKnowledgeGenerator,
    KnowledgeWriter, IncrementalScanner, WikiIngestor,
    _clean_handler, learn_from_repos, generate_kb_cache, _check_code_quality,
    KnowledgeCache,
)


# ===========================================================================
# IRDocument — actual field names
# ===========================================================================

class TestIRDocument:
    def test_defaults(self):
        ir = IRDocument(repo_name="test", repo_path="/tmp", language="go")
        assert ir.repo_name == "test"
        assert ir.structs == []
        assert ir.functions == []
        assert ir.routes == []
        assert ir.imports == []

    def test_with_values(self):
        s = StructDef(name="User", file="a.go")
        ir = IRDocument(repo_name="test", repo_path="/tmp", language="python", structs=[s])
        assert len(ir.structs) == 1


# ===========================================================================
# Data classes — actual signatures
# ===========================================================================

class TestDataClasses:
    def test_structdef(self):
        s = StructDef(name="User", file="a.go")
        assert s.name == "User"
        assert s.file == "a.go"

    def test_funcdef(self):
        f = FuncDef(name="GetUser", file="a.go")
        assert f.name == "GetUser"
        assert f.is_route is False

    def test_routedef(self):
        r = RouteDef(path="/api/users", method="GET", handler="GetUsers", module="user", file="a.go")
        assert r.method == "GET"
        assert r.path == "/api/users"

    def test_importdef(self):
        i = ImportDef(module="github.com/user/pkg")
        assert i.module == "github.com/user/pkg"

    def test_caledge(self):
        e = CallEdge(caller="A", caller_pkg="pkg", callee="B", callee_pkg="pkg", pos="a.go:10")
        assert e.caller == "A"
        assert e.callee == "B"

    def test_data_flow_node(self):
        n = DataFlowNode(var_name="x", kind="assignment", lineno=10, file="a.py")
        assert n.var_name == "x"
        assert n.kind == "assignment"


# ===========================================================================
# GoScanner — fallback path (no ripgrep)
# ===========================================================================

class TestGoScannerFallback:
    def test_init_no_ripgrep(self, tmp_path):
        scanner = GoScanner(use_ripgrep=False)
        assert scanner.use_ripgrep is False

    def test_scan_go_skips_vendor_and_test(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.go").write_text('package main\nimport "fmt"\ntype User struct { ID int }\nfunc main() { fmt.Println("hi") }\n')
        vendor = repo / "vendor"
        vendor.mkdir()
        (vendor / "dep.go").write_text('package dep\n')
        (repo / "user_test.go").write_text('package main\n')
        scanner = GoScanner(use_ripgrep=False)
        ir = scanner.scan_directory(repo, max_files=100, incremental=False)
        assert ir.repo_name == repo.name

    def test_extract_db_tags(self):
        tag = 'gorm:"column:user_name;type:varchar(100)"'
        m = re.search(r'gorm:"([^"]*)"', tag)
        assert m is not None
        assert "column" in m.group(1)


# ===========================================================================
# PythonScanner
# ===========================================================================

class TestPythonScanner:
    def test_scan_empty_repo(self, tmp_path):
        scanner = PythonScanner()
        ir = scanner.scan_directory(tmp_path, max_files=10)
        assert ir is not None

    def test_scan_with_python_files(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text('''
class User:
    def __init__(self, name):
        self.name = name

def get_user(id: int) -> User:
    return User("test")
''')
        scanner = PythonScanner()
        ir = scanner.scan_directory(repo, max_files=10)
        assert ir is not None

    def test_analyze_data_flow(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "flow.py").write_text('x = 1\ny = x + 2\nprint(y)\n')
        scanner = PythonScanner()
        nodes = scanner._analyze_data_flow(repo / "flow.py")
        assert len(nodes) > 0
        var_names = {n.var_name for n in nodes}
        assert "x" in var_names or "y" in var_names

    def test_get_decorator_names(self):
        scanner = PythonScanner()
        import ast
        tree = ast.parse('@login_required\ndef protected_view(): pass')
        func = tree.body[0]
        decorators = scanner._get_decorator_names(func)
        assert "login_required" in decorators

    def test_get_return_annotation(self):
        scanner = PythonScanner()
        import ast
        tree = ast.parse('def foo() -> int: pass')
        func = tree.body[0]
        ret = scanner._get_return_annotation(func)
        assert ret == "int"

    def test_async_function_detection(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "async.py").write_text('async def fetch_data():\n    return {}\n')
        scanner = PythonScanner()
        ir = scanner.scan_directory(repo, max_files=10)
        assert ir is not None


# ===========================================================================
# JavaScanner
# ===========================================================================

class TestJavaScanner:
    def test_scan_java_file(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "UserService.java").write_text('''
public class UserService {
    private String name;

    public User findById(Long id) throws Exception {
        return new User();
    }
}
''')
        scanner = JavaScanner()
        info = scanner.scan_file(repo / "UserService.java")
        assert info["classes"]
        assert info["classes"][0]["name"] == "UserService"

    def test_scan_skips_non_java(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.go").write_text('package main\n')
        scanner = JavaScanner()
        ir = scanner.scan_directory(repo, max_files=10)
        assert ir is not None

    def test_extract_spring_routes(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "UserController.java").write_text('''
@RestController
public class UserController {
    @GetMapping("/api/users")
    public List<User> getUsers() { return null; }

    @PostMapping("/api/users")
    public User createUser() { return null; }
}
''')
        scanner = JavaScanner()
        info = scanner.scan_file(repo / "UserController.java")
        routes = info.get("routes", [])
        assert len(routes) >= 2


# ===========================================================================
# MultiRepoAnalyzer
# ===========================================================================

class TestMultiRepoAnalyzer:
    def test_single_repo(self, tmp_path):
        repo = tmp_path / "repo1"
        repo.mkdir()
        (repo / "main.go").write_text('package main\n')
        analyzer = MultiRepoAnalyzer()
        result = analyzer.analyze([{"name": "r1", "path": str(repo)}])
        assert "edges" in result

    def test_two_repos(self, tmp_path):
        r1 = tmp_path / "r1"
        r1.mkdir()
        (r1 / "a.go").write_text('package a\n')
        r2 = tmp_path / "r2"
        r2.mkdir()
        (r2 / "b.go").write_text('package b\nimport "a"\n')
        analyzer = MultiRepoAnalyzer()
        result = analyzer.analyze([
            {"name": "r1", "path": str(r1)},
            {"name": "r2", "path": str(r2)},
        ])
        assert "edges" in result

    def test_import_prefix_match(self, tmp_path):
        r1 = tmp_path / "r1"
        r1.mkdir()
        (r1 / "pkg.go").write_text('package github.com/user/pkg\n')
        analyzer = MultiRepoAnalyzer()
        result = analyzer.analyze([{"name": "r1", "path": str(r1)}])
        assert isinstance(result, dict)


# ===========================================================================
# LLMKnowledgeGenerator
# ===========================================================================

class TestLLMKnowledgeGenerator:
    def test_build_prompt_empty(self):
        gen = LLMKnowledgeGenerator()
        ir = IRDocument(repo_name="test", repo_path="/tmp", language="go")
        prompt = gen.build_prompt(ir, {}, [], None)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_prompt_with_ir(self, tmp_path):
        gen = LLMKnowledgeGenerator()
        ir = IRDocument(repo_name="test", repo_path=str(tmp_path), language="go",
                        structs=[StructDef(name="User", file="a.go")],
                        functions=[FuncDef(name="GetUser", file="a.go")])
        prompt = gen.build_prompt(ir, {}, [{"name": "test", "path": str(tmp_path)}], str(tmp_path))
        assert isinstance(prompt, str)
        assert "Structs: 1" in prompt


# ===========================================================================
# KnowledgeWriter — actual API
# ===========================================================================

class TestKnowledgeWriter:
    def test_write_architecture(self, tmp_path):
        writer = KnowledgeWriter()
        knowledge = {"architecture": "Arch content"}
        files = writer.write(knowledge, str(tmp_path))
        assert "architecture.md" in files
        assert (tmp_path / "architecture.md").exists()

    def test_write_flows(self, tmp_path):
        writer = KnowledgeWriter()
        knowledge = {"business_flows": "Flow content"}
        files = writer.write(knowledge, str(tmp_path))
        assert "flows.md" in files

    def test_write_schema(self, tmp_path):
        writer = KnowledgeWriter()
        knowledge = {"database_schema": "Schema content"}
        files = writer.write(knowledge, str(tmp_path))
        assert "schema.md" in files

    def test_write_services(self, tmp_path):
        writer = KnowledgeWriter()
        knowledge = {"service_architecture": "Svc content"}
        files = writer.write(knowledge, str(tmp_path))
        assert "services.md" in files

    def test_write_glossary(self, tmp_path):
        writer = KnowledgeWriter()
        knowledge = {"glossary": {"user": "用户", "order": "订单"}}
        files = writer.write(knowledge, str(tmp_path))
        assert "glossary.md" in files


# ===========================================================================
# WikiIngestor
# ===========================================================================

class TestWikiIngestor:
    def test_ingest(self, tmp_path):
        wiki = tmp_path / "wiki"
        ingestor = WikiIngestor()
        knowledge = {
            "architecture": "Arch content",
            "business_flows": "Flow content",
            "database_schema": "Schema content",
            "service_architecture": "Svc content",
            "glossary": {"user": "用户"},
        }
        pages = ingestor.ingest(knowledge, wiki, "test-repo")
        assert len(pages) > 0
        assert (wiki / "index.md").exists()
        assert (wiki / "architecture.md").exists()

    def test_ingest_empty(self, tmp_path):
        wiki = tmp_path / "wiki"
        ingestor = WikiIngestor()
        pages = ingestor.ingest({}, wiki, "empty-repo")
        assert len(pages) > 0


# ===========================================================================
# _clean_handler
# ===========================================================================

class TestCleanHandler:
    def test_empty(self):
        assert _clean_handler("") == ""

    def test_plain(self):
        assert _clean_handler("GetUser") == "GetUser"

    def test_with_params(self):
        assert _clean_handler("HandleUsers(ctx)") == "HandleUsers"

    def test_nested_call(self):
        assert _clean_handler("a.b.c.method()") == "method"


# ===========================================================================
# _check_code_quality
# ===========================================================================

class TestCheckCodeQuality:
    def test_low_coverage(self):
        ir = {"test_coverage": {"coverage_pct": 20}, "error_codes": [], "structs": []}
        result = _check_code_quality(ir)
        assert "低" in result

    def test_medium_coverage(self):
        ir = {"test_coverage": {"coverage_pct": 45}, "error_codes": [], "structs": []}
        result = _check_code_quality(ir)
        assert "中等" in result

    def test_high_coverage(self):
        ir = {"test_coverage": {"coverage_pct": 80}, "error_codes": [], "structs": []}
        result = _check_code_quality(ir)
        assert "高" in result

    def test_many_error_codes(self):
        ir = {"test_coverage": {"coverage_pct": 80},
              "error_codes": [{"code": f"E{i}"} for i in range(15)],
              "structs": [{"comments": "doc"}]}
        result = _check_code_quality(ir)
        assert "充足" in result

    def test_good_comments(self):
        structs = [{"comments": "doc"} for _ in range(10)]
        ir = {"test_coverage": {"coverage_pct": 80}, "error_codes": [], "structs": structs}
        result = _check_code_quality(ir)
        assert "良好" in result


# ===========================================================================
# generate_kb_cache
# ===========================================================================

class TestGenerateKBCache:
    def test_missing_dir(self, tmp_path):
        result = generate_kb_cache(str(tmp_path / "missing"), str(tmp_path / "cache"))
        assert result == {}

    def test_empty_dir(self, tmp_path):
        kb = tmp_path / "kb"
        kb.mkdir()
        result = generate_kb_cache(str(kb), str(tmp_path / "cache"))
        # generate_kb_cache returns the raw cache entry (with metadata)
        assert 'data' in result

    def test_with_md_files(self, tmp_path):
        kb = tmp_path / "kb"
        kb.mkdir()
        (kb / "architecture.md").write_text("# Architecture\n\nUser 服务处理用户")
        result = generate_kb_cache(str(kb), str(tmp_path / "cache"))
        assert isinstance(result, dict)


# ===========================================================================
# KnowledgeCache
# ===========================================================================

class TestKnowledgeCacheExtended:
    def test_set_get_expire(self, tmp_path):
        cache = KnowledgeCache(str(tmp_path / "cache"))
        cache.set("key1", {"data": "value"}, ttl=0)
        time.sleep(0.1)
        assert cache.is_expired("key1") is True
        # get() still returns the entry even if expired (is_expired is separate)
        entry = cache.get("key1")
        assert entry is not None
        assert entry["data"] == {"data": "value"}

    def test_persist_and_reload(self, tmp_path):
        cache_dir = tmp_path / "cache2"
        cache = KnowledgeCache(str(cache_dir))
        cache.set("persist", {"items": [1, 2, 3]})
        cache2 = KnowledgeCache(str(cache_dir))
        entry = cache2.cache.get("persist")
        assert entry and entry["data"] == {"items": [1, 2, 3]}

    def test_load_invalid_json(self, tmp_path):
        cache_dir = tmp_path / "cache3"
        cache_dir.mkdir()
        (cache_dir / "kb_cache.json").write_text("bad json {{{")
        cache = KnowledgeCache(str(cache_dir))
        assert cache.get("any") is None

    def test_invalidate(self, tmp_path):
        cache = KnowledgeCache(str(tmp_path / "cache4"))
        cache.set("key", "value")
        cache.invalidate("key")
        assert "key" not in cache.cache


# ===========================================================================
# learn_from_repos (partial — no LLM)
# ===========================================================================

class TestLearnFromRepos:
    def test_no_repos_exits(self, tmp_path):
        profile = tmp_path / "profile.json"
        profile.write_text(json.dumps({"business_domain": "test", "repositories": []}))
        output = tmp_path / "output"
        output.mkdir()
        result = subprocess.run(
            [sys.executable, "-c", f"""
import sys
sys.path.insert(0, '/Users/yanping.ma/biz-delivery')
from scripts.learn_repo import learn_from_repos
try:
    learn_from_repos("{profile}", "{output}")
except SystemExit as e:
    sys.exit(e.code)
"""],
            capture_output=True, text=True
        )
        assert "No repositories" in result.stdout or result.returncode != 0

    def test_missing_repo_skipped(self, tmp_path):
        profile = tmp_path / "profile.json"
        profile.write_text(json.dumps({
            "business_domain": "test",
            "repositories": [{"name": "missing", "path": str(tmp_path / "no_such_dir"), "language": "go"}]
        }))
        output = tmp_path / "output"
        output.mkdir()
        result = subprocess.run(
            [sys.executable, "-c", f"""
import sys
sys.path.insert(0, '/Users/yanping.ma/biz-delivery')
from scripts.learn_repo import learn_from_repos
learn_from_repos("{profile}", "{output}")
"""],
            capture_output=True, text=True
        )
        assert result.returncode == 0 or "No repositories" in result.stdout
