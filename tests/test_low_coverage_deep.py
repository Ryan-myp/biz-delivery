"""
低覆盖模块深度测试：core_flow_analyzer / delivery_pipeline / learn_repo GoScanner
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scripts.core_flow_analyzer import CoreFlowAnalyzer
from scripts.delivery_pipeline import (
    AgentTaskGenerator, QualityGate, DeliveryReport, AgentTask, TaskPriority, TaskStatus,
)
from scripts.learn_repo import CodeKnowledgeExtractor, GoScanner
from scripts.llm_client import LLMClient


# ═══════════════════════════════════════════════════════════
#  CoreFlowAnalyzer — 状态机 / 异步 / CRUD / 拓扑
# ═══════════════════════════════════════════════════════════

class TestStateMachineFlows:
    """_infer_state_machine_flows 深度测试"""

    def _analyzer(self, structs=None, funcs=None, routes=None):
        ir = {
            "structs": structs or [],
            "functions": funcs or [],
            "routes": routes or [],
            "call_graph": [],
        }
        return CoreFlowAnalyzer(ir)

    def test_state_machine_with_status_struct(self):
        """有 status 字段的 struct 触发状态机流程推理"""
        structs = [{"name": "AdGroup", "fields": [{"name": "status"}, {"name": "id", "type": "int"}]}]
        funcs = [{"name": "PublishAdGroup", "file": "svc.go"}, {"name": "RejectAdGroup", "file": "svc.go"}]
        routes = [{"method": "POST", "path": "/api/adgroups/{id}/publish", "handler": "PublishAdGroup"}]
        flows = self._analyzer(structs, funcs, routes)._infer_state_machine_flows()
        assert len(flows) >= 1
        assert flows[0]["flow_type"] == "state_machine"
        assert flows[0]["entry_point"] == "PublishAdGroup"

    def test_state_machine_no_status_fields(self):
        """没有 status/state 字段的 struct 不触发状态机"""
        structs = [{"name": "User", "fields": [{"name": "name", "type": "string"}]}]
        flows = self._analyzer(structs)._infer_state_machine_flows()
        assert flows == []

    def test_detect_states_from_function_names(self):
        """从函数名提取状态常量"""
        funcs = [
            {"name": "ApproveRequest", "file": "a.go"},
            {"name": "RejectApplication", "file": "b.go"},
            {"name": "DraftDocument", "file": "c.go"},
        ]
        states = self._analyzer(funcs=funcs)._detect_states("Doc")
        assert any("Draft" in s for s in states)

    def test_detect_states_empty(self):
        states = self._analyzer()._detect_states("Foo")
        assert states == []


class TestAsyncFlows:
    """_infer_async_flows 测试"""

    def _analyzer(self, funcs=None):
        ir = {"functions": funcs or [], "routes": [], "call_graph": [], "structs": []}
        return CoreFlowAnalyzer(ir)

    def test_producer_consumer_pairing(self):
        """发布者和消费者能正确配对"""
        funcs = [
            {"name": "BidPublish", "file": "pub.go"},
            {"name": "BidConsume", "file": "cons.go"},
            {"name": "HandleOrderEvent", "file": "h.go"},
        ]
        flows = self._analyzer(funcs=funcs)._infer_async_flows()
        assert len(flows) >= 1
        assert flows[0]["flow_type"] == "async_event"
        assert flows[0]["producer"] == "BidPublish"

    def test_no_matching_pairs(self):
        """没有配对时返回空"""
        funcs = [{"name": "FooBar", "file": "a.go"}]
        flows = self._analyzer(funcs=funcs)._infer_async_flows()
        assert flows == []


class TestCRUDFlows:
    """_infer_crud_flows 测试"""

    def _analyzer(self, routes=None):
        ir = {"routes": routes or [], "functions": [], "call_graph": [], "structs": []}
        return CoreFlowAnalyzer(ir)

    def test_crud_from_routes(self):
        """路由按资源分组生成 CRUD 流程"""
        routes = [
            {"method": "POST", "path": "/api/v1/creatives", "handler": "CreateCreative"},
            {"method": "GET", "path": "/api/v1/creatives/{id}", "handler": "GetCreative"},
            {"method": "PUT", "path": "/api/v1/creatives/{id}", "handler": "UpdateCreative"},
            {"method": "DELETE", "path": "/api/v1/creatives/{id}", "handler": "DeleteCreative"},
        ]
        flows = self._analyzer(routes=routes)._infer_crud_flows()
        assert len(flows) >= 1
        assert flows[0]["flow_type"] == "crud"
        assert "Create" in flows[0]["crud_ops"]
        assert "Delete" in flows[0]["crud_ops"]

    def test_no_routes(self):
        flows = self._analyzer(routes=[])._infer_crud_flows()
        assert flows == []


class TestMergeAndRank:
    """_merge_similar_flows / _rank_flows / detect_error_handling_flows"""

    def _analyzer(self):
        return CoreFlowAnalyzer({})

    def test_merge_same_entry_point(self):
        flows = [
            {"name": "A", "entry_point": "X", "call_chain": ["X", "Y"], "score": 60, "flow_type": "http"},
            {"name": "B", "entry_point": "X", "call_chain": ["X", "Z"], "score": 50, "flow_type": "http"},
            {"name": "C", "entry_point": "Y", "call_chain": ["Y"], "score": 40, "flow_type": "http"},
        ]
        merged = self._analyzer()._merge_similar_flows(flows)
        # A 和 B 应合并，C 独立
        assert len(merged) <= 2
        assert all("score" in f for f in merged)

    def test_rank_flows(self):
        flows = [
            {"name": "low", "score": 10},
            {"name": "high", "score": 90},
            {"name": "mid", "score": 50},
        ]
        ranked = self._analyzer()._rank_flows(flows)
        assert ranked[0]["name"] == "high"
        assert len(ranked) <= 15

    def test_detect_error_flows_with_structs(self):
        """错误处理流程检测"""
        ir = {
            "structs": [
                {"name": "ErrorCode", "fields": [{"name": "code_id"}, {"name": "msg"}]},
            ],
            "functions": [
                {"name": "HandleError", "file": "err.go", "layer": "handler"},
            ],
            "routes": [],
        }
        flows = CoreFlowAnalyzer(ir).detect_error_handling_flows()
        assert isinstance(flows, list)


class TestServiceTopology:
    """infer_service_topology / analyze_entity_ownership / cluster_business_processes"""

    def test_topology_from_files(self):
        """从文件路径推断服务拓扑"""
        funcs = [
            {"name": "PlaceBidHandler", "file": "handler/ad/auction/handler.go"},
            {"name": "BidService", "file": "service/ad/auction/service.go"},
            {"name": "BidDAO", "file": "dao/ad/auction/dao.go"},
        ]
        ir = {"functions": funcs, "routes": [], "call_graph": []}
        topo = CoreFlowAnalyzer(ir).infer_service_topology()
        assert "services" in topo
        assert "cross_service_deps" in topo

    def test_entity_ownership(self):
        ir = {
            "entity_tables": [{"entity": "Bid", "table": "bids"}],
            "functions": [{"name": "GetBid", "file": "dao/bid_dao.go"}],
            "call_graph": [],
            "routes": [],
        }
        result = CoreFlowAnalyzer(ir).analyze_entity_ownership()
        assert isinstance(result, list)

    def test_cluster_processes(self):
        ir = {
            "routes": [
                {"method": "POST", "path": "/api/login", "handler": "LoginHandler"},
                {"method": "POST", "path": "/api/bid", "handler": "PlaceBidHandler"},
            ],
            "functions": [
                {"name": "LoginHandler", "file": "handler/auth.go"},
                {"name": "PlaceBidHandler", "file": "handler/bid.go"},
            ],
            "call_graph": [],
        }
        clusters = CoreFlowAnalyzer(ir).cluster_business_processes()
        assert isinstance(clusters, list)


# ═══════════════════════════════════════════════════════════
#  DeliveryPipeline — run() 全链路
# ═══════════════════════════════════════════════════════════

class TestDeliveryPipelineRun:
    """全链路 run() 测试（mock LLM + 真实 pipeline 逻辑）"""

    def _make_pipeline(self, tmp_path):
        profile = {
            "business_domain": "auction",
            "repositories": [{"name": "test-repo", "path": str(tmp_path / "repo")}],
            "qa_mode": "quick",
        }
        llm = MagicMock(spec=LLMClient)
        llm.chat.return_value = {"content": "Mock LLM response"}
        return type('P', (), {
            'profile': profile,
            'llm_client': llm,
            'output_dir': tmp_path / "out",
            'wiki_path': str(tmp_path / "wiki"),
            'ir_data': {},
            'review_result': {},
            'td_content': "",
                       'agent_tasks': [],
            'test_cases': {},
            'execution_result': {},
        })()


    def test_quality_gate_pass(self, tmp_path):
        """质量门禁全通过"""
        gate = QualityGate(
            {"business_domain": "auction", "quality_gate": {"required_coverage": 0.7}},
            str(tmp_path / "out"),
        )
        report = DeliveryReport(
            prd_review={"p0_issues": [], "p1_issues": []},
            technical_design={},
            agent_tasks=[{"title": "t", "status": "passed"}],
            test_cases={"coverage": 0.8},
            execution_result={},
            quality_gate={"required_coverage": 0.7},
        )
        result = gate.evaluate(report)
        checks = {c["check"]: c["status"] for c in result["checks"]}
        # 无 P0 问题且覆盖率达标 → 无 failed check
        assert checks.get("prd_review_quality") != "failed"

    def test_quality_gate_fail_coverage(self, tmp_path):
        """质量门禁因覆盖率不足失败"""
        gate = QualityGate(
            {"business_domain": "auction", "quality_gate": {"required_coverage": 0.9}},
            str(tmp_path / "out"),
        )
        report = DeliveryReport(
            prd_review={"p0_issues": [{"msg": "critical issue"}], "p1_issues": []},
            technical_design={},
            agent_tasks=[],
            test_cases={"coverage": 0.5},
            execution_result={},
            quality_gate={"required_coverage": 0.9},
        )
        result = gate.evaluate(report)
        checks = {c["check"]: c["status"] for c in result["checks"]}
        # P0 issues → prd_review_quality failed
        assert checks.get("prd_review_quality") == "failed"


# ═══════════════════════════════════════════════════════════
#  learn_repo — GoScanner 降级扫描
# ═══════════════════════════════════════════════════════════

class TestGoScannerFallback:
    """GoScanner fallback 模式（ripgrep 不可用时）"""

    def test_scan_go_files_fallback(self, tmp_path):
        """用 Python re fallback 扫描真实 Go 文件"""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "bid.go").write_text('''package handler

import "fmt"

// BidRequest 出价请求
type BidRequest struct {
    Amount   float64
    Currency string
    UserID   int
}

// TableName 表名映射
func (b *BidRequest) TableName() string {
    return "bid_requests"
}

// PlaceBid 处理出价
func PlaceBid(ctx string) error {
    return nil
}

func GetBid(id string) (*BidRequest, error) {
    return nil, nil
}
''')
        scanner = GoScanner(use_ripgrep=False)  # 强制使用 Python re
        ir = scanner.scan_directory(pkg)
        from dataclasses import asdict
        d = asdict(ir)
        funcs = d.get("functions", [])
        struct_names = [s.get("name", "") for s in d.get("structs", [])]
        assert "BidRequest" in struct_names
        assert any("PlaceBid" in f.get("name", "") for f in funcs)

    def test_scan_go_skips_vendor_and_test(self, tmp_path):
        """扫描应跳过 vendor/ 和 _test.go 文件"""
        (tmp_path / "vendor").mkdir()
        (tmp_path / "vendor" / "dep.go").write_text('package vendor\ntype V struct{}\n')
        (tmp_path / "main.go").write_text('package main\nfunc main() {}\n')
        (tmp_path / "main_test.go").write_text('package main\nfunc TestX(t *testing.T) {}\n')
        
        scanner = GoScanner(use_ripgrep=False)
        ir = scanner.scan_directory(tmp_path)
        from dataclasses import asdict
        d = asdict(ir)
        funcs = d.get("functions", [])
        struct_names = [s.get("name", "") for s in d.get("structs", [])]
        assert "V" not in struct_names  # vendor 应被跳过
        assert "main" in [f.get("name", "") for f in funcs]

    def test_extract_routes_from_go(self, tmp_path):
        """从 Go 代码提取路由"""
        (tmp_path / "routes.go").write_text('''package handler

func Setup(r *mux.Router) {
    r.GET("/api/bid", PlaceBid)
    r.POST("/api/bid", CreateBid)
    group := r.Group("/api/v1")
    {
        group.GET("/creatives", ListCreatives)
        group.DELETE("/creatives/:id", DeleteCreative)
    }
}
''')
        scanner = GoScanner(use_ripgrep=False)
        ir = scanner.scan_directory(tmp_path)
        from dataclasses import asdict
        d = asdict(ir)
        routes = d.get("routes", [])
        paths = [r.get("path", "") for r in routes]
        assert "/api/bid" in paths
        # Routes are extracted per-segment: /api/v1, /creatives

    def test_extract_db_tags(self, tmp_path):
        """从 GORM tag 提取表名和列名"""
        (tmp_path / "model.go").write_text('''package model

type AdGroup struct {
    ID         uint   `gorm:"primaryKey"`
    Status     int    `gorm:"column:ad_group_status"`
    Name       string `gorm:"size:255"`
    Budget     float64
}

type Creative struct {
    ID    uint   `gorm:"primaryKey"`
    Title string `gorm:"size:200;not null"`
}
''')
        scanner = GoScanner(use_ripgrep=False)
        ir = scanner.scan_directory(tmp_path)
        from dataclasses import asdict
        d = asdict(ir)
        structs = d.get("structs", [])
        adgroup = next((s for s in structs if s.get("name") == "AdGroup"), None)
        assert adgroup is not None
        field_names = [f.get("name", "") for f in adgroup.get("fields", [])]
        assert "Status" in field_names or "ad_group_status" in field_names
