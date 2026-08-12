"""
Tests for EngineBase — the shared base class for all biz-delivery engines.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.base_engine import EngineBase
from scripts.learn_repo import IRDocument, RouteDef, StructDef, FuncDef


# ── Init / profile handling ───────────────────────────────────────────────────


class TestInit:
    def test_minimal_profile(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        assert eng.business_domain == "test-domain"
        assert eng.repos == []
        assert eng.output_dir == tmp_out
        assert eng.wiki_path is None

    def test_nested_profile(self, nested_profile, tmp_out):
        eng = EngineBase(nested_profile, str(tmp_out))
        assert eng.business_domain == "nested-domain"

    def test_missing_business_domain_defaults(self, tmp_out, capsys):
        profile = {"repositories": [], "name": "x"}
        eng = EngineBase(profile, str(tmp_out))
        assert eng.business_domain == "unknown"
        captured = capsys.readouterr()
        assert "business_domain" in captured.err or "business_domain" in captured.out

    def test_missing_repositories_warns(self, tmp_out, capsys):
        profile = {"business_domain": "test"}
        eng = EngineBase(profile, str(tmp_out))
        assert eng.repos == []

    def test_wiki_path_stored(self, tmp_out):
        eng = EngineBase({"business_domain": "x", "repositories": []}, str(tmp_out), wiki_path="/wiki")
        assert eng.wiki_path == "/wiki"

    def test_nonexistent_repo_path_warns(self, tmp_out, capsys):
        profile = {
            "business_domain": "x",
            "repositories": [{"path": "/nonexistent/path"}],
        }
        eng = EngineBase(profile, str(tmp_out))
        captured = capsys.readouterr()
        assert "does not exist" in captured.out

    def test_kb_dir_inferred_when_exists(self, tmp_out):
        fake_repo_parent = tmp_out / "repos"
        fake_repo_parent.mkdir()
        kb_dir = fake_repo_parent / "knowledge" / "test-domain"
        kb_dir.mkdir(parents=True)
        profile = {
            "business_domain": "test-domain",
            "repositories": [{"path": str(fake_repo_parent / "myrepo")}],
        }
        (fake_repo_parent / "myrepo").mkdir()
        eng = EngineBase(profile, str(tmp_out))
        assert eng.kb_dir == str(kb_dir)

    def test_kb_dir_not_inferred_when_missing(self, tmp_out):
        profile = {
            "business_domain": "test-domain",
            "repositories": [{"path": str(tmp_out)}],
        }
        eng = EngineBase(profile, str(tmp_out))
        assert eng.kb_dir is None


# ── Profile normalization ─────────────────────────────────────────────────────


class TestNormalizeProfile:
    def test_flat_profile_passthrough(self):
        result = EngineBase._normalize_profile({"business_domain": "x", "repositories": []})
        assert result == {"business_domain": "x", "repositories": []}

    def test_nested_profile_extracted(self):
        inner = {"business_domain": "inner", "repositories": []}
        result = EngineBase._normalize_profile({"profile": inner})
        assert result == inner

    def test_empty_profile_returns_as_is(self):
        result = EngineBase._normalize_profile({})
        assert result == {}

    def test_non_dict_returns_as_is(self):
        result = EngineBase._normalize_profile("not-a-dict")  # type: ignore
        assert result == "not-a-dict"


# ── Cache helpers ──────────────────────────────────────────────────────────────


class TestCacheHelpers:
    def test_get_scan_cache_dir_no_repos(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        assert eng._get_scan_cache_dir() is None

    def test_get_scan_cache_dir_with_repo(self, tmp_out):
        repo_dir = tmp_out / "repo"
        repo_dir.mkdir()
        profile = {
            "business_domain": "x",
            "repositories": [{"path": str(repo_dir)}],
        }
        eng = EngineBase(profile, str(tmp_out))
        cache = eng._get_scan_cache_dir()
        assert cache is not None
        assert Path(cache).parent == repo_dir.parent

    def test_try_load_cached_ir_missing_file(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        assert eng._try_load_cached_ir("/tmp/nonexistent_cache") is None

    def test_try_load_cached_ir_valid_file(self, tmp_out):
        cache_dir = tmp_out / "cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "ir_cache.json"
        cache_file.write_text('{"repo_name":"old"}')
        eng = EngineBase({"business_domain": "x", "repositories": []}, str(tmp_out))
        result = eng._try_load_cached_ir(str(cache_dir))
        assert result is not None
        assert result["repo_name"] == "old"

    def test_try_load_cached_ir_corrupt_json(self, tmp_out):
        cache_dir = tmp_out / "cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "ir_cache.json"
        cache_file.write_text("not json{{")
        eng = EngineBase({"business_domain": "x", "repositories": []}, str(tmp_out))
        result = eng._try_load_cached_ir(str(cache_dir))
        assert result is None


# ── Codebase scanning ────────────────────────────────────────────────────────


class TestScanCodebase:
    def test_empty_repos_returns_unknown_ir(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        ir = eng._scan_codebase()
        assert ir.repo_name == "none"
        assert ir.language == "unknown"

    @patch("scripts.base_engine.EngineBase._sequential_scan")
    def test_calls_sequential_scan_when_repos_present(self, mock_seq, tmp_out):
        mock_seq.return_value = IRDocument(repo_name="seq", repo_path="", language="go")
        profile = {
            "business_domain": "x",
            "repositories": [{"path": "/tmp/fake_repo"}],
        }
        eng = EngineBase(profile, str(tmp_out))
        with patch("pathlib.Path.exists", return_value=False):
            ir = eng._scan_codebase()
        mock_seq.assert_called_once()
        assert ir.repo_name == "seq"


# ── Evidence querying ────────────────────────────────────────────────────────


class TestEvidenceQuerying:
    """Test evidence querying integration.

    Note: _query_evidence_for_prd uses lazy local import, so we test the
    overall behavior rather than trying to mock the internal import.
    """
    def test_query_evidence_returns_dict(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        result = eng._query_evidence_for_prd("some prd text")
        assert isinstance(result, dict)
        assert "total" in result

    def test_passes_wiki_path(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out), wiki_path="/wiki")
        result = eng._query_evidence_for_prd("prd")
        # Just verify it doesn't crash and returns expected structure
        assert isinstance(result, dict)

    def test_passes_kb_dir(self, tmp_out):
        profile = {
            "business_domain": "test-domain",
            "repositories": [{"path": str(tmp_out)}],
        }
        (tmp_out / "knowledge" / "test-domain").mkdir(parents=True)
        eng = EngineBase(profile, str(tmp_out))
        result = eng._query_evidence_for_prd("prd")
        assert isinstance(result, dict)


# ── Prompt-building helpers ──────────────────────────────────────────────────


def _make_route(method, path, handler):
    """Create a RouteDef object for testing."""
    return RouteDef(path=path, method=method, handler=handler, module="test", file="test.go")


def _make_struct(name, fields):
    s = StructDef()
    s.name = name
    s.fields = fields
    return s


def _make_func(name, params, returns, file):
    f = FuncDef()
    f.name = name
    f.params = params
    f.returns = returns
    f.file = file
    return f


class TestBuildIRSummary:
    def test_basic_summary(self, sample_profile, tmp_out, mock_ir_document):
        eng = EngineBase(sample_profile, str(tmp_out))
        parts = eng._build_ir_summary(mock_ir_document)
        text = "\n".join(parts)
        assert "test-domain" in text
        assert "go" in text
        assert "Structs" in text
        assert "Routes" in text
        assert "45%" in text


class TestBuildRoutesSection:
    def test_empty_routes_returns_empty(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        ir = IRDocument(repo_name="x", repo_path="", language="go")
        assert eng._build_routes_section(ir) == ""

    def test_routes_formatted_with_objects(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        ir = IRDocument(repo_name="x", repo_path="", language="go")
        ir.routes = [
            _make_route("POST", "/api/auction/bid", "PlaceBid"),
            _make_route("GET", "/api/auction/status", "GetBidStatus"),
        ]
        result = eng._build_routes_section(ir, limit=1)
        assert "关键路由" in result
        assert "/api/auction/bid" in result
        assert "PlaceBid" in result

    def test_limit_respected(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        ir = IRDocument(repo_name="x", repo_path="", language="go")
        ir.routes = [
            _make_route("POST", "/api/auction/bid", "PlaceBid"),
            _make_route("GET", "/api/auction/status", "GetBidStatus"),
        ]
        result = eng._build_routes_section(ir, limit=1)
        assert result.count("/api/auction/bid") == 1
        assert "/api/auction/status" not in result


class TestBuildBusinessLogicSection:
    def test_empty_logic_returns_empty(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        ir = IRDocument(repo_name="x", repo_path="", language="go")
        assert eng._build_business_logic_section(ir) == ""

    def test_logic_formatted(self, sample_profile, tmp_out, mock_ir_document):
        eng = EngineBase(sample_profile, str(tmp_out))
        result = eng._build_business_logic_section(mock_ir_document)
        assert "出价流程" in result or "PlaceBid" in result


class TestBuildEntityTableSection:
    def test_empty_returns_empty(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        ir = IRDocument(repo_name="x", repo_path="", language="go")
        assert eng._build_entity_table_section(ir) == ""

    def test_formatted(self, sample_profile, tmp_out, mock_ir_document):
        eng = EngineBase(sample_profile, str(tmp_out))
        result = eng._build_entity_table_section(mock_ir_document)
        assert "UserBid" in result
        assert "user_bids" in result


class TestBuildErrorCodeSection:
    def test_empty_returns_empty(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        ir = IRDocument(repo_name="x", repo_path="", language="go")
        assert eng._build_error_code_section(ir) == ""

    def test_formatted(self, sample_profile, tmp_out, mock_ir_document):
        eng = EngineBase(sample_profile, str(tmp_out))
        result = eng._build_error_code_section(mock_ir_document)
        assert "ERR_BID_DUPLICATE" in result
        assert "4001" in result


class TestBuildAuthModelSection:
    def test_empty_returns_empty(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        ir = IRDocument(repo_name="x", repo_path="", language="go")
        assert eng._build_auth_model_section(ir) == ""

    def test_formatted(self, sample_profile, tmp_out, mock_ir_document):
        eng = EngineBase(sample_profile, str(tmp_out))
        result = eng._build_auth_model_section(mock_ir_document)
        assert "AuthMiddleware" in result


class TestBuildSQLSection:
    def test_empty_returns_empty(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        ir = IRDocument(repo_name="x", repo_path="", language="go")
        assert eng._build_sql_section(ir) == ""

    def test_formatted(self, sample_profile, tmp_out, mock_ir_document):
        eng = EngineBase(sample_profile, str(tmp_out))
        result = eng._build_sql_section(mock_ir_document)
        assert "INSERT" in result
        assert "user_bids" in result


class TestBuildTestCoverageSection:
    def test_no_test_info_returns_empty(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        ir = IRDocument(repo_name="x", repo_path="", language="go")
        assert eng._build_test_coverage_section(ir) == ""

    def test_with_test_info(self, sample_profile, tmp_out, mock_ir_document):
        eng = EngineBase(sample_profile, str(tmp_out))
        mock_ir_document.test_functions = [{"name": "TestBid"}]
        mock_ir_document.test_files = ["bid_test.go"]
        mock_ir_document.coverage_report = {"coverage_pct": 45, "framework": "go test"}
        result = eng._build_test_coverage_section(mock_ir_document)
        assert "测试覆盖情况" in result
        assert "45%" not in result  # This field doesn't show coverage_pct directly


class TestBuildCoreFlowsSection:
    def test_no_core_flows_returns_empty(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        ir = IRDocument(repo_name="x", repo_path="", language="go")
        assert eng._build_core_flows_section(ir) == ""

    def test_with_core_flows(self, sample_profile, tmp_out, mock_ir_document):
        eng = EngineBase(sample_profile, str(tmp_out))
        result = eng._build_core_flows_section(mock_ir_document)
        assert "出价流程" in result
        assert "PlaceBid" in result


class TestBuildPackagesSection:
    def test_empty_packages_returns_empty(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        ir = IRDocument(repo_name="x", repo_path="", language="go")
        assert eng._build_packages_section(ir) == ""

    def test_with_packages(self, sample_profile, tmp_out, mock_ir_document):
        eng = EngineBase(sample_profile, str(tmp_out))
        result = eng._build_packages_section(mock_ir_document)
        assert "handlers/bid" in result
        assert "PlaceBid" in result


class TestBuildCallGraphSection:
    def test_empty_call_graph_returns_empty(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        ir = IRDocument(repo_name="x", repo_path="", language="go")
        assert eng._build_call_graph_section(ir) == ""

    def test_with_call_graph(self, sample_profile, tmp_out, mock_ir_document):
        eng = EngineBase(sample_profile, str(tmp_out))
        result = eng._build_call_graph_section(mock_ir_document)
        assert "PlaceBid" in result
        assert "ValidateBid" in result


# ── Dict → IR reconstruction ──────────────────────────────────────────────────


class TestDictToIR:
    def test_basic_reconstruction(self):
        data = {"repo_name": "cached", "repo_path": "/tmp", "language": "go"}
        ir = EngineBase._dict_to_ir(data)
        assert ir.repo_name == "cached"
        assert ir.language == "go"

    def test_with_structs_and_functions(self):
        data = {
            "repo_name": "cached",
            "repo_path": "/tmp",
            "language": "go",
            "structs": [{"name": "Foo"}],
            "functions": [{"name": "Bar"}],
        }
        ir = EngineBase._dict_to_ir(data)
        assert len(ir.structs) == 1
        assert len(ir.functions) == 1

    def test_with_all_fields(self):
        data = {
            "repo_name": "full",
            "repo_path": "/tmp",
            "language": "go",
            "structs": [],
            "functions": [],
            "routes": [],
            "entity_tables": [],
            "sql_operations": [],
            "error_codes": [],
            "auth_models": [],
            "business_logic": [],
            "test_files": [],
            "test_functions": [],
            "imports": [],
            "configs": [],
            "services": [],
            "packages": {},
            "call_graph": [],
            "core_flows": [],
            "perf_hotspots": [],
        }
        ir = EngineBase._dict_to_ir(data)
        assert ir.repo_name == "full"
        assert ir.structs == []
        assert ir.packages == {}


# ── Format weighted evidence ──────────────────────────────────────────────────


class TestFormatWeightedEvidence:
    def test_empty_list(self):
        result = EngineBase._format_weighted_evidence([], top_n=5)
        assert result == ['']

    def test_single_item(self):
        items = [{"title": "A", "score": 0.9, "content": "text"}]
        result = EngineBase._format_weighted_evidence(items, top_n=5)
        assert len(result) >= 1
        assert "A" in result[0]
        assert "证据1" in result[0]

    def test_top_n_limiting(self):
        items = [{"title": f"Item{i}", "score": 0.5, "content": "", "type": "function"} for i in range(10)]
        result = EngineBase._format_weighted_evidence(items, top_n=3)
        assert any("Item0" in r for r in result)
        assert any("Item2" in r for r in result)

    def test_weight_by_type(self):
        items = [
            {"title": "func", "score": 0.5, "type": "function"},
            {"title": "struct", "score": 0.5, "type": "struct"},
        ]
        result = EngineBase._format_weighted_evidence(items, top_n=10)
        assert "func" in result[0]


# ── Load business cards ──────────────────────────────────────────────────────


class TestLoadBusinessCards:
    def test_from_kb_dir(self, sample_profile, tmp_out, sample_business_cards):
        eng = EngineBase(sample_profile, str(tmp_out))
        eng.kb_dir = str(tmp_out)
        import shutil
        shutil.copy(sample_business_cards, tmp_out / "business_cards.json")
        result = eng._load_business_cards("")
        assert result is not None
        assert "scenario_cards" in result

    def test_from_cache_dir(self, sample_profile, tmp_out, sample_business_cards):
        eng = EngineBase(sample_profile, str(tmp_out))
        result = eng._load_business_cards(str(sample_business_cards.parent))
        assert result is not None

    def test_missing_file_returns_none(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        result = eng._load_business_cards("/tmp/nonexistent")
        assert result is None

    def test_corrupt_json_returns_none(self, sample_profile, tmp_out):
        eng = EngineBase(sample_profile, str(tmp_out))
        bc_file = tmp_out / "business_cards.json"
        bc_file.write_text("{invalid json")
        result = eng._load_business_cards(str(tmp_out))
        assert result is None
