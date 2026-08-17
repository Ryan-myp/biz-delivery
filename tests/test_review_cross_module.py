"""Tests for review_engine cross-module analysis, data flow conflicts, and
precheck logic that was previously uncovered."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.review_engine import ReviewEngine


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def engine(tmp_path):
    """Create a minimal ReviewEngine with empty profile."""
    profile = {
        "business_domain": "test",
        "repositories": [],
        "learn_config": {"max_files_per_lang": 100},
        "modules": [], "query_aliases": {}, "state_machines": {},
        "business_rules": {"general_errors": [], "database_errors": [], "redis_errors": [], "http_errors": []},
        "service_topology": {"services": []},
    }
    return ReviewEngine(profile, str(tmp_path), None)


@pytest.fixture
def mock_ir():
    """Mock IRDocument with dict-based items."""
    class MockIR:
        functions = [
            {"name": "CreateUser", "file": "handler.go", "calls": ["UserDAO.Insert"]},
            {"name": "GetUser", "file": "handler.go", "calls": ["UserDAO.Find"]},
        ]
        structs = [
            {"name": "User", "fields": ["ID", "Name", "Email"]},
            {"name": "CreateUserRequest", "fields": ["Name", "Email"]},
        ]
        routes = [
            {"path": "/api/v1/users", "method": "POST"},
            {"path": "/api/v1/users/{id}", "method": "GET"},
        ]
        imports = [
            {"module": "github.com/user/service"},
            {"module": "redis"},
        ]
        entity_tables = [{"name": "users", "columns": ["id", "name", "email"]}]
        core_flows = []
        call_graph = [
            {"caller": "CreateUser", "callee": "UserDAO.Insert"},
            {"caller": "GetUser", "callee": "UserDAO.Find"},
        ]
    return MockIR()


# ===========================================================================
# _analyze_cross_module_impact
# ===========================================================================

class TestCrossModuleImpact:
    def test_empty_ir(self, engine):
        class EmptyIR:
            functions = []
            structs = []
            routes = []
            imports = []
            entity_tables = []
            core_flows = []
            call_graph = []
        checks = engine._analyze_cross_module_impact(EmptyIR(), "测试")
        assert isinstance(checks, list)

    def test_dict_based_ir(self, engine, mock_ir):
        """IR with dict-based items should not crash (regression test)."""
        checks = engine._analyze_cross_module_impact(mock_ir, "测试")
        assert isinstance(checks, list)

    def test_with_prd_entities(self, engine, mock_ir):
        checks = engine._analyze_cross_module_impact(mock_ir, "CreateUser GetUser")
        assert isinstance(checks, list)


# ===========================================================================
# _detect_field_conflicts
# ===========================================================================

class TestFieldConflicts:
    def test_empty_ir(self, engine):
        class EmptyIR:
            functions = []
            structs = []
            entity_tables = []
        checks = engine._detect_field_conflicts(EmptyIR(), "测试")
        assert isinstance(checks, list)

    def test_dict_based_ir(self, engine, mock_ir):
        """IR with dict-based items should not crash."""
        checks = engine._detect_field_conflicts(mock_ir, "测试")
        assert isinstance(checks, list)

    def test_with_field_keywords(self, engine, mock_ir):
        checks = engine._detect_field_conflicts(
            mock_ir, "需要修改 User 表的 name 字段")
        assert isinstance(checks, list)


# ===========================================================================
# _detect_data_flow_conflicts
# ===========================================================================

class TestDataFlowConflicts:
    def test_no_data_source_keywords(self, engine, mock_ir):
        checks = engine._detect_data_flow_conflicts(mock_ir, "创建一个用户列表")
        assert checks == []

    def test_missing_data_source(self, engine, mock_ir):
        """PRD mentions Kafka but code has no Kafka import."""
        checks = engine._detect_data_flow_conflicts(
            mock_ir, "数据通过 Kafka 同步到下游系统")
        assert len(checks) > 0
        assert any(c.get('rule') == 'missing_data_source' for c in checks)

    def test_has_data_source(self, engine, mock_ir):
        """PRD mentions Redis which is in imports."""
        checks = engine._detect_data_flow_conflicts(
            mock_ir, "使用 Redis 缓存用户数据")
        # Should not flag Redis as missing
        assert not any(c.get('rule') == 'missing_data_source' for c in checks)

    def test_aggregation_without_impl(self, engine):
        """PRD mentions data source + aggregation but no aggregate functions → should flag."""
        class IR:
            functions = [{"name": "create_user"}, {"name": "get_user"}]
            imports = []
        checks = engine._detect_data_flow_conflicts(IR(), "数据通过 Kafka 同步，需要聚合统计用户数据")
        assert len(checks) > 0
        assert any(c.get('rule') == 'no_aggregation_impl' for c in checks)

    def test_aggregation_with_impl(self, engine):
        """PRD mentions aggregation and IR HAS aggregate function → no flag."""
        class IR:
            functions = [{"name": "aggregate_users"}]
            imports = []
        checks = engine._detect_data_flow_conflicts(IR(), "需要聚合统计用户数据")
        assert not any(c.get('rule') == 'no_aggregation_impl' for c in checks)


# ===========================================================================
# _run_prechecks — entity detection
# ===========================================================================

class TestPrechecksEntities:
    def test_entity_exists(self, engine, mock_ir):
        checks = engine._run_prechecks(mock_ir, "CreateUser 和 GetUser", [])
        assert any(c.get('check') == 'entity_exists' for c in checks)

    def test_entity_missing(self, engine, mock_ir):
        checks = engine._run_prechecks(mock_ir, "NoSuchEntity 和 AnotherThing", [])
        assert any(c.get('check') == 'entity_missing' for c in checks)

    def test_no_entities(self, engine, mock_ir):
        checks = engine._run_prechecks(mock_ir, "hello world", [])
        # Should not crash
        assert isinstance(checks, list)


# ===========================================================================
# _run_prechecks — route detection
# ===========================================================================

class TestPrechecksRoutes:
    def test_route_exists(self, engine, mock_ir):
        # /api/v1/users exists in mock_ir.routes, so no route_missing check
        checks = engine._run_prechecks(mock_ir, "/api/v1/users", [])
        assert not any(c.get('check') == 'route_missing' for c in checks)

    def test_route_missing(self, engine, mock_ir):
        checks = engine._run_prechecks(mock_ir, "/api/v1/nonexistent", [])
        assert any(c.get('check') == 'route_missing' for c in checks)


# ===========================================================================
# _run_prechecks — performance risk
# ===========================================================================

class TestPrechecksPerformance:
    def test_perf_risk_detected(self, engine, mock_ir):
        checks = engine._run_prechecks(mock_ir, "高并发场景 QPS 10000", [])
        assert any(c.get('check') == 'performance_risk' for c in checks)

    def test_no_perf_risk_with_cache(self, engine, mock_ir):
        """If a struct mentions Redis, no performance risk."""
        ir = MagicMock()
        ir.functions = []
        ir.structs = [{"name": "UserCache"}, {"name": "RedisClient"}]
        ir.routes = []
        ir.imports = []
        ir.entity_tables = []
        ir.core_flows = []
        ir.call_graph = []
        checks = engine._run_prechecks(ir, "高并发场景 QPS 10000", [])
        assert not any(c.get('check') == 'performance_risk' for c in checks)


# ===========================================================================
# _validate_business_rules
# ===========================================================================

class TestValidateBusinessRules:
    def test_no_rules(self, engine, mock_ir):
        profile = {
            "business_rules": {
                "general_errors": [],
                "database_errors": [],
                "redis_errors": [],
                "http_errors": [],
            }
        }
        engine.profile = profile
        checks = engine._validate_business_rules(mock_ir, "测试", profile)
        assert checks == []

    def test_with_general_errors(self, engine, mock_ir):
        profile = {
            "business_rules": {
                "general_errors": [{"code": "ERR_001", "message": "Test error"}],
                "database_errors": [],
                "redis_errors": [],
                "http_errors": [],
            }
        }
        engine.profile = profile
        checks = engine._validate_business_rules(mock_ir, "测试", profile)
        assert isinstance(checks, list)


# ===========================================================================
# _check_module_boundaries
# ===========================================================================

class TestCheckModuleBoundaries:
    def test_empty_profile(self, engine, mock_ir):
        checks = engine._check_module_boundaries(mock_ir, "测试", {})
        assert isinstance(checks, list)

    def test_with_modules(self, engine, mock_ir):
        profile = {
            "modules": [
                {"name": "user", "files": ["user.go"]},
                {"name": "payment", "files": ["payment.go"]},
            ]
        }
        checks = engine._check_module_boundaries(mock_ir, "测试", profile)
        assert isinstance(checks, list)


# ===========================================================================
# _query_and_validate
# ===========================================================================

class TestQueryAndValidate:
    def test_basic_query(self, engine, mock_ir, tmp_path):
        cache_dir = str(tmp_path / "cache")
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        result = engine._query_and_validate(mock_ir, "CreateUser", cache_dir)
        assert "evidence" in result
        assert "prechecks" in result
        assert "total" in result
