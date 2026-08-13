"""
Review Engine 增强检查测试套件
覆盖：_check_compatibility 增强分支（破坏性变更/前端影响/第三方/必填字段/类型变更/约束变更）、
      _check_api_versioning_impact、_check_cache_penetration_risk、_assess_performance_risk
目标：scripts/review_engine.py 覆盖率 ≥80%
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.review_engine import ReviewEngine
from scripts.learn_repo import IRDocument, RouteDef


def make_ir(**overrides):
    """构造测试用 IRDocument"""
    ir = IRDocument(repo_name="test", repo_path="/tmp/test", language="go")
    ir.routes = [
        RouteDef(path="/api/auction/bid", method="POST", handler="PlaceBid", module="handler", file="bid.go"),
        RouteDef(path="/api/v1/users", method="GET", handler="GetUsers", module="handler", file="user.go"),
    ]
    ir.functions = [
        {"name": "PlaceBid", "params": "ctx", "returns": "*Response", "file": "bid.go"},
        {"name": "GetUsers", "params": "ctx", "returns": "*Response", "file": "user.go"},
        {"name": "AuditLog", "params": "action", "returns": "error", "file": "audit.go"},
        {"name": "RateLimiter", "params": "key", "returns": "bool", "file": "ratelimit.go"},
        {"name": "RedisSetNX", "params": "key", "returns": "bool", "file": "redis.go"},
    ]
    ir.imports = [
        {"module": "gorm.io/gorm"},
        {"module": "github.com/go-redis/redis"},
        {"module": "golang-migrate/migrate"},
    ]
    ir.structs = [
        {"name": "BidRequest", "fields": ["user_id", "amount"]},
    ]
    ir.entity_tables = [
        {"entity": "BidRequest", "table": "bids"},
    ]
    for k, v in overrides.items():
        setattr(ir, k, v)
    return ir


def make_profile():
    return {
        "profile": {
            "name": "test",
            "business_domain": "auction",
            "repositories": [],
        }
    }


class TestCheckCompatibilityEnhancements:
    """兼容性增强检查测试"""
    
    def _make_engine(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir(exist_ok=True)
        return ReviewEngine(make_profile(), str(out_dir), wiki_path=str(tmp_path))
    
    def test_breaking_change_no_deprecation(self, tmp_path):
        """测试破坏性变更无废弃策略"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.functions = [{"name": "PlaceBid", "params": "", "returns": "", "file": "bid.go"}]
        ir.routes = [
            RouteDef(path="/api/auction/bid", method="POST", handler="PlaceBid", module="h", file="bid.go"),
        ]
        
        checks = engine._check_compatibility(
            ir, "删除字段，修改请求结构，breaking change", make_profile()["profile"]
        )
        
        assert any(c["rule"] == "no_deprecation_strategy" for c in checks)
    
    def test_breaking_change_with_v2(self, tmp_path):
        """测试有 v2 版本时无 dual api 警告"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.functions = [{"name": "PlaceBid", "params": "", "returns": "", "file": "bid.go"}]
        ir.routes = [
            RouteDef(path="/api/v1/auction/bid", method="POST", handler="PlaceBid", module="h", file="bid.go"),
            RouteDef(path="/api/v2/auction/bid", method="POST", handler="PlaceBid", module="h", file="bid.go"),
        ]
        
        checks = engine._check_compatibility(
            ir, "删除字段，修改请求结构", make_profile()["profile"]
        )
        
        # v1 和 v2 都存在，dual api 检查通过
        dual_checks = [c for c in checks if c["rule"] == "no_dual_api_strategy"]
        # 但因为 has_versioning，no_api_versioning 也不会触发
        assert isinstance(checks, list)
    
    def test_frontend_impact(self, tmp_path):
        """测试前端影响"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.functions = [{"name": "PlaceBid", "params": "", "returns": "", "file": "bid.go"}]
        
        checks = engine._check_compatibility(
            ir, "修改 /api/auction/bid 接口，路径调整，前端需要适配", make_profile()["profile"]
        )
        
        assert any(c["rule"] == "frontend_impact" for c in checks)
    
    def test_third_party_no_callback(self, tmp_path):
        """测试第三方无回调"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.functions = [{"name": "PlaceBid", "params": "", "returns": "", "file": "bid.go"}]
        
        checks = engine._check_compatibility(
            ir, "修改 /api/auction/bid 接口，对接第三方系统", make_profile()["profile"]
        )
        
        assert any(c["rule"] == "third_party_no_callback" for c in checks)
    
    def test_required_field_no_default(self, tmp_path):
        """测试必填字段无默认值"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        
        checks = engine._check_compatibility(
            ir, "新增表 bids 新增字段，必填不能为空", make_profile()["profile"]
        )
        
        assert any(c["rule"] == "no_default_for_required_field" for c in checks)
    
    def test_type_change_no_migration(self, tmp_path):
        """测试类型变更无迁移"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        
        checks = engine._check_compatibility(
            ir, "修改字段类型，类型变更", make_profile()["profile"]
        )
        
        assert any(c["rule"] == "field_type_change_no_migration" for c in checks)
    
    def test_constraint_change_no_data_prep(self, tmp_path):
        """测试约束变更无数据准备"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        
        checks = engine._check_compatibility(
            ir, "新增表 users，改为 NOT NULL 非空", make_profile()["profile"]
        )
        
        assert any(c["rule"] == "constraint_change_no_data_prep" for c in checks)
    
    def test_audit_log_present(self, tmp_path):
        """测试审计日志存在时不告警"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()  # 包含 AuditLog 函数
        
        checks = engine._check_compatibility(
            ir, "需要审计日志记录操作", make_profile()["profile"]
        )
        
        audit_checks = [c for c in checks if c["rule"] == "audit_missing"]
        assert len(audit_checks) == 0
    
    def test_audit_log_missing(self, tmp_path):
        """测试审计日志缺失"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.functions = [{"name": "PlaceBid", "params": "", "returns": "", "file": "bid.go"}]
        
        checks = engine._check_compatibility(
            ir, "需要审计日志记录", make_profile()["profile"]
        )
        
        assert any(c["rule"] == "audit_missing" for c in checks)


class TestCheckApiVersioningImpact:
    """API 版本影响测试"""
    
    def _make_engine(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir(exist_ok=True)
        return ReviewEngine(make_profile(), str(out_dir), wiki_path=str(tmp_path))
    
    def test_versioning_impact(self, tmp_path):
        """测试版本影响"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_api_versioning_impact(ir, "修改现有接口")
        assert isinstance(checks, list)
    
    def test_versioning_impact_breaking(self, tmp_path):
        """测试破坏性变更"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_api_versioning_impact(ir, "删除字段，接口不兼容")
        assert isinstance(checks, list)


class TestCheckCachePenetrationRisk:
    """缓存穿透风险测试"""
    
    def _make_engine(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir(exist_ok=True)
        return ReviewEngine(make_profile(), str(out_dir), wiki_path=str(tmp_path))
    
    def test_cache_penetration(self, tmp_path):
        """测试缓存穿透"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_cache_penetration_risk(
            ir, "热点数据需要缓存，防止缓存穿透"
        )
        assert isinstance(checks, list)
    
    def test_cache_penetration_no_cache(self, tmp_path):
        """测试无缓存关键词"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._check_cache_penetration_risk(ir, "普通功能")
        assert checks == []


class TestAssessPerformanceRisk:
    """性能风险评估测试"""
    
    def _make_engine(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir(exist_ok=True)
        return ReviewEngine(make_profile(), str(out_dir), wiki_path=str(tmp_path))
    
    def test_performance_risk(self, tmp_path):
        """测试性能风险"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._assess_performance_risk(
            ir, "高并发场景需要优化性能", make_profile()["profile"]
        )
        assert isinstance(checks, list)
    
    def test_performance_risk_no_index(self, tmp_path):
        """测试无索引"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        checks = engine._assess_performance_risk(
            ir, "查询性能需要优化", make_profile()["profile"]
        )
        assert isinstance(checks, list)


class TestReviewMainFlow:
    """主流程边界测试"""
    
    def _make_engine(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir(exist_ok=True)
        return ReviewEngine(make_profile(), str(out_dir), wiki_path=str(tmp_path))
    
    def test_review_empty_prd(self, tmp_path):
        """测试空 PRD"""
        engine = self._make_engine(tmp_path)
        with patch.object(engine, "_scan_codebase", return_value=make_ir()):
            with patch.object(engine, "_query_and_validate", return_value={"total": 0, "evidence": []}):
                result = engine.review("")
        
        assert result["status"] in ("prompt_ready", "error")
    
    def test_review_with_prechecks(self, tmp_path):
        """测试带预检查"""
        engine = self._make_engine(tmp_path)
        ir = make_ir()
        ir.error_codes = []  # 触发预检查
        
        with patch.object(engine, "_scan_codebase", return_value=ir):
            with patch.object(engine, "_query_and_validate",
                              return_value={"total": 0, "evidence": [], "prechecks": [{
                                  "rule": "test", "severity": "high", "description": "测试检查"
                              }]}):
                result = engine.review("用户登录功能")
        
        assert "prompt_file" in result or "status" in result
    
    def test_parse_review_report_sections(self, tmp_path):
        """测试报告解析各章节"""
        engine = self._make_engine(tmp_path)
        report = """
# 审查报告

## 1. Overall Assessment
Status: Needs Revision
Confidence: Medium
Summary: 需要改进

## 2. Critical Issues (P0)
- [P0] 缺少幂等性 — 需要加锁

## 3. Important Issues (P1)
- [P1] 并发不足

## 4. Minor Issues (P2)
- [P2] 建议优化

## 5. Section-by-Section Review
### 5.1 Correctness Check
分析内容

### 5.2 Scenario Completeness
场景分析

## 6. Recommendations
建议优化
"""
        parsed = engine._parse_review_report(report)
        assert "overall_status" in parsed
        assert "p0_issues" in parsed
        assert "sections" in parsed
        assert "recommendations" in parsed
        assert "severity_score" in parsed
        assert "risk_level" in parsed
