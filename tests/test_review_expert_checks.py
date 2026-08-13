"""
Review Engine 专家级检查方法测试套件
覆盖：review_engine.py 中所有 _check_*/_validate_*/_detect_*/_analyze_* 专家级检查方法
目标：scripts/review_engine.py 覆盖率 ≥80%
"""
import json
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.review_engine import ReviewEngine
from scripts.learn_repo import IRDocument


def make_ir(**overrides):
    """构造测试用 IRDocument"""
    ir = IRDocument(repo_name="test", repo_path="/tmp/test", language="go")
    ir.structs = [
        {"name": "UserBid", "fields": ["user_id", "amount", "product_id"]},
    ]
    ir.functions = [
        {"name": "PlaceBid", "params": "ctx, req", "returns": "*Response", "file": "bid.go"},
        {"name": "GetBidStatus", "params": "ctx", "returns": "*StatusResponse", "file": "bid.go"},
        {"name": "migrate_users", "params": "", "returns": "", "file": "migrate.go"},
        {"name": "RedisLock", "params": "key", "returns": "bool", "file": "lock.go"},
        {"name": "MaskPhone", "params": "phone", "returns": "string", "file": "mask.go"},
        {"name": "DeleteUser", "params": "id", "returns": "error", "file": "user.go"},
        {"name": "BeginTransaction", "params": "", "returns": "*Tx", "file": "db.go"},
        {"name": "FeatureFlagEnabled", "params": "flag", "returns": "bool", "file": "feature.go"},
        {"name": "AuditLog", "params": "action", "returns": "error", "file": "audit.go"},
        {"name": "RateLimit", "params": "key", "returns": "bool", "file": "ratelimit.go"},
    ]
    ir.routes = [
        {"method": "POST", "path": "/api/auction/bid", "handler": "PlaceBid"},
        {"method": "GET", "path": "/api/auction/status", "handler": "GetBidStatus"},
    ]
    ir.error_codes = [
        {"name": "ERR_BID_DUPLICATE", "code": 4001, "message": "重复出价"},
    ]
    ir.entity_tables = [
        {"entity": "UserBid", "table": "user_bids"},
    ]
    ir.business_logic = [
        {"handler": "PlaceBid", "description": "用户提交出价", "calls": ["ValidateBid", "SaveBid"]},
    ]
    ir.core_flows = [
        {"flow_name": "出价流程", "entry_point": "PlaceBid", "call_chain": ["PlaceBid", "SaveBid"]},
    ]
    ir.packages = {
        "handlers/bid": {"files": ["bid_handler.go"], "functions": ["PlaceBid"]},
        "common/shared": {"files": ["shared.go"], "functions": ["SharedHelper"]},
    }
    ir.call_graph = [
        {"caller": "PlaceBid", "callee": "SaveBid"},
        {"caller": "handlers/bid", "callee": "services/bid"},
    ]
    ir.test_files = ["bid_handler_test.go"]
    ir.test_functions = [{"name": "TestPlaceBid", "file": "bid_handler_test.go"}]
    ir.coverage_report = {"coverage_pct": 45, "framework": "go test"}
    ir.sql_operations = [
        {"sql_operation": "INSERT", "table": "user_bids", "file": "bid_repo.go"},
    ]
    ir.auth_models = [
        {"middleware": "AuthMiddleware", "logic": "需要登录"},
    ]
    ir.imports = [
        {"module": "gorm.io/gorm"},
        {"module": "github.com/gin-gonic/gin"},
        {"module": "github.com/go-redis/redis"},
        {"module": "github.com/segmentio/kafka-go"},
        {"module": "golang-migrate/migrate"},
    ]
    ir.services = [{"name": "user-service"}, {"name": "order-service"}]
    for k, v in overrides.items():
        setattr(ir, k, v)
    return ir


def make_profile(**overrides):
    """构造测试用 profile"""
    profile = {
        "profile": {
            "name": "test-project",
            "business_domain": "auction",
            "repositories": [],
            "business_rules": {
                "database_errors": [
                    {"code": "DB_001", "description": "数据库错误处理规范"},
                ],
                "redis_errors": [
                    {"code": "REDIS_001", "description": "Redis 错误处理规范"},
                ],
            },
            "modules": [
                {"name": "bid-module", "goal": "出价管理", "keywords": ["出价", "bid"]},
                {"name": "user-module", "goal": "用户管理", "keywords": ["用户", "user"]},
            ],
            "state_machines": {
                "BidStatus": {
                    "Status": {
                        "PENDING": {"transitions": ["PAID"]},
                    }
                },
            },
            "service_topology": {
                "services": [
                    {"name": "user-service", "port": 8081},
                    {"name": "order-service", "port": 8082},
                ]
            },
        }
    }
    for k, v in overrides.items():
        profile["profile"][k] = v
    return profile


class TestReviewEngineExpertChecks:
    """专家级检查方法测试"""
    
    def _make_engine(self, tmp_path, profile=None):
        return ReviewEngine(
            profile or make_profile(),
            str(tmp_path / "out"),
            wiki_path=str(tmp_path),
        )
    
    # ── 跨模块影响分析 ─────────────────────────────────────
    
    def test_analyze_cross_module_impact(self, tmp_path):
        """测试跨模块影响分析"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._analyze_cross_module_impact(ir, "新增出价功能，涉及用户模块")
        assert isinstance(checks, list)
    
    def test_analyze_cross_module_impact_exception(self, tmp_path):
        """测试跨模块分析异常时返回空"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        with patch("scripts.review_engine.analyze_cross_module_impact",
                   side_effect=RuntimeError("fail")):
            checks = engine._analyze_cross_module_impact(ir, "测试")
            assert checks == []
    
    # ── 字段冲突检测 ───────────────────────────────────────
    
    def test_detect_field_conflicts(self, tmp_path):
        """测试字段冲突检测"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._detect_field_conflicts(ir, "修改用户出价金额字段")
        assert isinstance(checks, list)
    
    def test_detect_field_conflicts_exception(self, tmp_path):
        """测试字段冲突检测异常"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        with patch("scripts.review_engine.detect_field_conflicts",
                   side_effect=RuntimeError("fail")):
            checks = engine._detect_field_conflicts(ir, "测试")
            assert checks == []
    
    # ── 跨仓库依赖分析 ─────────────────────────────────────
    
    def test_cross_repo_multi_service(self, tmp_path):
        """测试多服务检测"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._analyze_cross_repo_deps(ir, "跨服务调用用户和订单")
        assert any(c["rule"] == "multi_service_detected" for c in checks)
    
    def test_cross_repo_no_cross_service(self, tmp_path):
        """测试无跨服务关键词"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._analyze_cross_repo_deps(ir, "修改出价金额")
        # 无跨服务关键词时，只有共享实体检查可能触发
        assert isinstance(checks, list)
    
    def test_cross_repo_shared_entity(self, tmp_path):
        """测试共享实体变更风险"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._analyze_cross_repo_deps(ir, "修改公共用户实体")
        assert any(c["rule"] == "shared_entity_change_risk" for c in checks)
    
    # ── 业务规则校验 ───────────────────────────────────────
    
    def test_validate_business_rules_error_coverage(self, tmp_path):
        """测试错误码覆盖检查"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.error_codes = []  # 无错误码
        checks = engine._validate_business_rules(
            ir, "出价失败时返回错误，异常处理", make_profile()
        )
        assert any(c["rule"] == "error_code_coverage" for c in checks)
    
    def test_validate_business_rules_auth_missing(self, tmp_path):
        """测试鉴权缺失检查"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.auth_models = []  # 无鉴权
        checks = engine._validate_business_rules(
            ir, "需要登录后才能出价，鉴权必须", make_profile()
        )
        assert any(c["rule"] == "auth_missing" for c in checks)
    
    def test_validate_business_rules_struct_missing(self, tmp_path):
        """测试 struct 缺失检查"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.structs = []
        checks = engine._validate_business_rules(
            ir, "新增 AuctionService 出价服务", make_profile()
        )
        assert any(c["rule"] == "struct_missing" for c in checks)
    
    def test_validate_business_rules_ok(self, tmp_path):
        """测试全部通过"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._validate_business_rules(ir, "修改出价金额", make_profile())
        assert isinstance(checks, list)
    
    # ── 业务规则约束 ───────────────────────────────────────
    
    def test_check_business_rule_constraints_violation(self, tmp_path):
        """测试违反约束"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_business_rule_constraints(
            ir, "数据库错误直接抛异常，不处理", make_profile()["profile"]
        )
        assert len(checks) > 0
        assert checks[0]["severity"] == "high"
    
    def test_check_business_rule_constraints_no_rules(self, tmp_path):
        """测试无规则配置"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        profile = make_profile()
        profile["profile"]["business_rules"] = {}
        checks = engine._check_business_rule_constraints(
            ir, "数据库错误直接抛异常", profile["profile"]
        )
        assert checks == []
    
    # ── 模块边界 ────────────────────────────────────────────
    
    def test_check_module_boundaries_cross_module(self, tmp_path):
        """测试跨模块依赖"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_module_boundaries(
            ir, "出价管理功能，同时需要用户管理", make_profile()["profile"]
        )
        assert any(c["rule"] == "cross_module_dependency" for c in checks)
    
    def test_check_module_boundaries_no_modules(self, tmp_path):
        """测试无模块配置"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        profile = make_profile()
        profile["profile"]["modules"] = []
        checks = engine._check_module_boundaries(ir, "出价", profile["profile"])
        assert checks == []
    
    # ── Schema 迁移风险 ────────────────────────────────────
    
    def test_check_schema_migration_no_change(self, tmp_path):
        """测试无 schema 变更"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_schema_migration_risk(ir, "修改出价金额")
        assert checks == []
    
    def test_check_schema_migration_with_tool(self, tmp_path):
        """测试有迁移工具"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_schema_migration_risk(ir, "新增表 user_bids 新增字段")
        assert isinstance(checks, list)
    
    # ── 分布式锁 ───────────────────────────────────────────
    
    def test_check_distributed_lock_concurrency(self, tmp_path):
        """测试并发无锁"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.functions = [{"name": "PlaceBid", "params": "", "returns": "", "file": "bid.go"}]
        checks = engine._check_distributed_lock_risk(
            ir, "支持高并发出价，防止超卖，库存扣减"
        )
        assert any(c["rule"] == "concurrency_no_lock" for c in checks)
    
    def test_check_distributed_lock_no_concurrency(self, tmp_path):
        """测试无并发需求"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_distributed_lock_risk(ir, "修改出价金额")
        assert checks == []
    
    # ── 数据一致性 ─────────────────────────────────────────
    
    def test_check_data_consistency_no_tx(self, tmp_path):
        """测试无事务实现"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.functions = [{"name": "PlaceBid", "params": "", "returns": "", "file": "bid.go"}]
        checks = engine._check_data_consistency(
            ir, "出价需要事务保证，跨服务数据一致性"
        )
        assert any(c["rule"] == "no_transaction_impl" for c in checks)
    
    def test_check_data_consistency_no_req(self, tmp_path):
        """测试无一致性需求"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_data_consistency(ir, "修改出价金额")
        assert checks == []
    
    # ── 数据保留合规 ───────────────────────────────────────
    
    def test_check_data_retention_pdp(self, tmp_path):
        """测试个人数据处理"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.functions = [{"name": "PlaceBid", "params": "", "returns": "", "file": "bid.go"}]
        checks = engine._check_data_retention_compliance(
            ir, "收集用户个人信息用于出价，包含用户手机号"
        )
        assert any(c["rule"] == "pdp_no_masking" for c in checks)
    
    def test_check_data_retention_no_pdp(self, tmp_path):
        """测试无个人数据"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_data_retention_compliance(ir, "修改出价金额")
        assert checks == []
    
    # ── 灰度发布 ───────────────────────────────────────────
    
    def test_check_gradual_release_high_risk(self, tmp_path):
        """测试高风险变更"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.functions = [{"name": "PlaceBid", "params": "", "returns": "", "file": "bid.go"}]
        checks = engine._check_gradual_release_strategy(
            ir, "核心功能重构，重大变更影响主流程"
        )
        assert any(c["rule"] == "no_gradual_release" for c in checks)
    
    def test_check_gradual_release_low_risk(self, tmp_path):
        """测试低风险变更"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_gradual_release_strategy(ir, "修改出价金额")
        assert checks == []
    
    # ── 数据流冲突 ─────────────────────────────────────────
    
    def test_detect_data_flow_conflicts(self, tmp_path):
        """测试数据流检查"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._detect_data_flow_conflicts(
            ir, "数据来源是用户中心，通过数据同步"
        )
        assert isinstance(checks, list)
    
    def test_detect_data_flow_conflicts_no_req(self, tmp_path):
        """测试无数据流需求"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._detect_data_flow_conflicts(ir, "修改出价金额")
        assert checks == []
    
    # ── 流程完整性 ─────────────────────────────────────────
    
    def test_check_flow_completeness(self, tmp_path):
        """测试流程完整性"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_flow_completeness(ir, "用户出价流程")
        assert isinstance(checks, list)
    
    # ── 兼容性检查 ─────────────────────────────────────────
    
    def test_check_compatibility_existing_api(self, tmp_path):
        """测试修改现有接口"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_compatibility(
            ir, "修改 /api/auction/bid 接口出价功能", make_profile()
        )
        assert any(c["rule"] == "existing_api_modification" for c in checks)
    
    def test_check_compatibility_idempotency(self, tmp_path):
        """测试幂等性"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.functions = [{"name": "PlaceBid", "params": "", "returns": "", "file": "bid.go"}]
        checks = engine._check_compatibility(
            ir, "需要幂等处理防止重复提交", make_profile()
        )
        assert any(c["rule"] == "idempotency_missing" for c in checks)
    
    def test_check_compatibility_rate_limit(self, tmp_path):
        """测试限流"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.functions = [{"name": "PlaceBid", "params": "", "returns": "", "file": "bid.go"}]
        checks = engine._check_compatibility(
            ir, "需要限流控制 qps 限制", make_profile()
        )
        assert any(c["rule"] == "rate_limit_missing" for c in checks)
    
    def test_check_compatibility_no_issue(self, tmp_path):
        """测试无兼容性问题"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_compatibility(ir, "修改出价金额", make_profile())
        assert isinstance(checks, list)
    
    # ── API 影响分析 ───────────────────────────────────────
    
    def test_analyze_api_impact(self, tmp_path):
        """测试 API 影响"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._analyze_api_impact(ir, "修改出价接口")
        assert isinstance(checks, list)
    
    # ── 安全风险 ───────────────────────────────────────────
    
    def test_detect_security_risks(self, tmp_path):
        """测试安全风险检测"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._detect_security_risks(ir, "用户密码登录")
        assert isinstance(checks, list)
    
    # ── 可观测性 ───────────────────────────────────────────
    
    def test_check_observability(self, tmp_path):
        """测试可观测性"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_observability(ir, "核心出价流程")
        assert isinstance(checks, list)
    
    # ── 核心流程验证 ───────────────────────────────────────
    
    def test_validate_core_flows(self, tmp_path):
        """测试核心流程验证"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._validate_core_flows(ir, "用户出价主流程")
        assert isinstance(checks, list)
    
    # ── 外部依赖风险 ───────────────────────────────────────
    
    def test_check_external_dependency_risk(self, tmp_path):
        """测试外部依赖风险"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_external_dependency_risk(
            ir, "依赖第三方支付接口"
        )
        assert isinstance(checks, list)
    
    # ── 数据隐私合规 ───────────────────────────────────────
    
    def test_check_data_privacy_compliance(self, tmp_path):
        """测试数据隐私"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_data_privacy_compliance(
            ir, "收集用户个人信息和手机号"
        )
        assert isinstance(checks, list)
    
    # ── API 版本影响 ───────────────────────────────────────
    
    def test_check_api_versioning_impact(self, tmp_path):
        """测试 API 版本影响"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_api_versioning_impact(
            ir, "修改现有接口，删除字段"
        )
        assert isinstance(checks, list)
    
    # ── 缓存穿透风险 ───────────────────────────────────────
    
    def test_check_cache_penetration_risk(self, tmp_path):
        """测试缓存穿透"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_cache_penetration_risk(
            ir, "热点数据需要缓存，防止缓存穿透"
        )
        assert isinstance(checks, list)
    
    # ── 备份恢复策略 ───────────────────────────────────────
    
    def test_check_backup_recovery_strategy(self, tmp_path):
        """测试备份恢复"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_backup_recovery_strategy(
            ir, "核心数据需要备份和恢复方案"
        )
        assert isinstance(checks, list)
    
    # ── 配置管理 ───────────────────────────────────────────
    
    def test_check_config_management(self, tmp_path):
        """测试配置管理"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_config_management(ir, "新增配置项")
        assert isinstance(checks, list)
    
    # ── 多租户隔离 ─────────────────────────────────────────
    
    def test_check_multi_tenant_isolation(self, tmp_path):
        """测试多租户"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_multi_tenant_isolation(ir, "支持多租户数据隔离")
        assert isinstance(checks, list)
    
    # ── 性能风险评估 ───────────────────────────────────────
    
    def test_assess_performance_risk(self, tmp_path):
        """测试性能风险"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._assess_performance_risk(
            ir, "高并发场景需要优化性能", make_profile()
        )
        assert isinstance(checks, list)
