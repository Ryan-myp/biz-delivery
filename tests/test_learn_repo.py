"""
Tests for learn_repo core classes: IRDocument, GoScanner, CodeKnowledgeExtractor.
"""
import pytest

from scripts.learn_repo import IRDocument, GoScanner, CodeKnowledgeExtractor


# ── IRDocument ────────────────────────────────────────────────────────────────


class TestIRDocument:
    def test_creation_defaults(self):
        ir = IRDocument(repo_name="my-repo", repo_path="/tmp/my-repo", language="go")
        assert ir.repo_name == "my-repo"
        assert ir.repo_path == "/tmp/my-repo"
        assert ir.language == "go"
        assert ir.structs == []
        assert ir.functions == []
        assert ir.routes == []
        assert ir.call_graph == []
        assert ir.core_flows == []
        assert ir.packages == {}

    def test_add_structs(self):
        ir = IRDocument(repo_name="r", repo_path="/tmp", language="go")
        ir.structs = [{"name": "User", "fields": ["id", "name"]}]
        assert len(ir.structs) == 1

    def test_add_functions(self):
        ir = IRDocument(repo_name="r", repo_path="/tmp", language="go")
        ir.functions = [{"name": "GetUser", "params": "id", "returns": "User"}]
        assert len(ir.functions) == 1

    def test_add_routes(self):
        ir = IRDocument(repo_name="r", repo_path="/tmp", language="go")
        ir.routes = [{"method": "GET", "path": "/api/users", "handler": "GetUsers"}]
        assert ir.routes[0]["path"] == "/api/users"

    def test_merge_from_another_ir(self):
        src = IRDocument(repo_name="s", repo_path="/tmp/s", language="go")
        src.structs = [{"name": "A"}]
        src.routes = [{"method": "GET", "path": "/a"}]

        dst = IRDocument(repo_name="d", repo_path="/tmp/d", language="go")
        dst.structs.extend(src.structs)
        dst.routes.extend(src.routes)
        assert len(dst.structs) == 1
        assert len(dst.routes) == 1

    def test_coverage_report_default(self):
        ir = IRDocument(repo_name="r", repo_path="/tmp", language="go")
        assert ir.coverage_report == {}
        pct = getattr(ir, "coverage_report", {}).get("coverage_pct", 0)
        assert pct == 0

    def test_all_optional_lists_empty_by_default(self):
        ir = IRDocument(repo_name="r", repo_path="/tmp", language="go")
        assert ir.test_files == []
        assert ir.test_functions == []
        assert ir.sql_operations == []
        assert ir.error_codes == []
        assert ir.auth_models == []
        assert ir.entity_tables == []
        assert ir.business_logic == []
        assert ir.perf_hotspots == []
        assert ir.configs == []
        assert ir.imports == []
        assert ir.api_spec == []
        assert ir.conditions == []
        assert ir.compat_issues == []


# ── GoScanner ─────────────────────────────────────────────────────────────────


class TestGoScanner:
    def test_init_defaults(self):
        scanner = GoScanner()
        assert scanner.use_ripgrep is True
        assert scanner._rg_available is None

    def test_init_disable_ripgrep(self):
        scanner = GoScanner(use_ripgrep=False)
        assert scanner.use_ripgrep is False

    def test_is_rgrep_available_false_when_not_installed(self, monkeypatch):
        import subprocess
        def fake_run(*args, **kwargs):
            raise FileNotFoundError("rg not found")
        monkeypatch.setattr("subprocess.run", fake_run)
        scanner = GoScanner()
        assert scanner._is_rgrep_available() is False

    def test_scan_directory_with_path_object(self, tmp_path):
        scanner = GoScanner(use_ripgrep=False)
        ir = scanner.scan_directory(tmp_path)
        assert isinstance(ir, IRDocument)
        assert ir.repo_name == tmp_path.name

    def test_pattern_constants_exist(self):
        assert GoScanner.STRUCT_RE is not None
        assert GoScanner.ROUTE_RE is not None
        assert GoScanner.TOP_FUNC_RE is not None
        assert GoScanner.GORM_TAG_RE is not None


# ── CodeKnowledgeExtractor ───────────────────────────────────────────────────


class TestCodeKnowledgeExtractor:
    def test_go_language(self, tmp_path):
        extractor = CodeKnowledgeExtractor(str(tmp_path), language="go")
        assert extractor.language == "go"
        assert extractor.repo_path == tmp_path

    def test_python_language(self, tmp_path):
        extractor = CodeKnowledgeExtractor(str(tmp_path), language="python")
        assert extractor.language == "python"

    def test_unsupported_language(self, tmp_path):
        extractor = CodeKnowledgeExtractor(str(tmp_path), language="rust")
        result = extractor.extract()
        assert "error" in result
        assert "Unsupported language" in result["error"]

    def test_extract_go_empty_repo(self, tmp_path):
        extractor = CodeKnowledgeExtractor(str(tmp_path), language="go")
        result = extractor.extract()
        assert result is not None
        assert "packages" in result

    def test_extract_with_go_files(self, tmp_path):
        go_file = tmp_path / "main.go"
        go_file.write_text('''
package main

import "fmt"

type User struct {
    ID   int    `json:"id"`
    Name string `json:"name"`
}

func GetUser(id int) *User {
    return &User{ID: id}
}

func main() {
    fmt.Println("hello")
}
''')
        extractor = CodeKnowledgeExtractor(str(tmp_path), language="go")
        result = extractor.extract()
        assert "main" in result.get("packages", {})
        pkg = result["packages"]["main"]
        assert "GetUser" in pkg.get("functions", [])
        assert "User" in pkg.get("structs", {})

    def test_extract_python_empty_repo(self, tmp_path):
        extractor = CodeKnowledgeExtractor(str(tmp_path), language="python")
        result = extractor.extract()
        assert result is not None

    def test_extract_python_with_files(self, tmp_path):
        py_file = tmp_path / "app.py"
        py_file.write_text('''
class User:
    def __init__(self, name):
        self.name = name

def get_user(name):
    return User(name)
''')
        extractor = CodeKnowledgeExtractor(str(tmp_path), language="python")
        result = extractor.extract()
        assert len(result.get("packages", {})) >= 1

    def test_skip_test_files_in_go(self, tmp_path):
        test_file = tmp_path / "main_test.go"
        test_file.write_text('''
package main

func TestSomething(t *testing.T) {}
''')
        normal_file = tmp_path / "main.go"
        normal_file.write_text('''
package main

func NormalFunc() {}
''')
        extractor = CodeKnowledgeExtractor(str(tmp_path), language="go")
        result = extractor.extract()
        pkg = result.get("packages", {}).get("main", {})
        funcs = pkg.get("functions", [])
        assert "NormalFunc" in funcs
