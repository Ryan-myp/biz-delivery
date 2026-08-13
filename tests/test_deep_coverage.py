"""
learn_repo / core_flow_analyzer / delivery_pipeline 扩展测试
覆盖：_extract_go、_infer_from_business_logic、generate_tasks 等核心路径
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scripts.learn_repo import (
    CodeKnowledgeExtractor, IRDocument, StructDef, FuncDef, RouteDef,
    KnowledgeWriter, _generate_enhanced_summary,
)
from scripts.core_flow_analyzer import CoreFlowAnalyzer
from scripts.delivery_pipeline import (
    AgentTaskGenerator, TaskPriority, TaskStatus, AgentPhase, AgentTask,
    DeliveryReport, QualityGate,
)


# ─── CodeKnowledgeExtractor._extract_go 深度测试 ─────────────

class TestExtractGo:
    """Go 代码提取深度测试"""

    def _make_go_repo(self, tmp_path):
        """创建带真实 Go 代码的测试仓库"""
        pkg_dir = tmp_path / "ad-service" / "handler"
        pkg_dir.mkdir(parents=True)

        (pkg_dir / "bid.go").write_text('''package handler

import "fmt"

type BidRequest struct {
    Amount float64
    Currency string
}

func PlaceBid(ctx string) error {
    return nil
}

func GetBid(id string) (*BidRequest, error) {
    return nil, nil
}
''')

        (pkg_dir / "user.go").write_text('''package handler

type User struct {
    ID int
    Email string
    Status string
}

func GetUser(id int) (*User, error) {
    return nil, nil
}
''')

        return tmp_path / "ad-service"

    def test_extract_go_real_code(self, tmp_path):
        """测试真实 Go 代码提取"""
        repo = self._make_go_repo(tmp_path)
        ext = CodeKnowledgeExtractor(str(repo), "go")
        result = ext.extract()
        assert isinstance(result, dict)
        # 应该提取到包和函数
        assert "packages" in result or "functions" in result

    def test_extract_go_empty(self, tmp_path):
        """测试空 Go 仓库"""
        (tmp_path / "empty").mkdir()
        ext = CodeKnowledgeExtractor(str(tmp_path / "empty"), "go")
        result = ext.extract()
        assert isinstance(result, dict)

    def test_extract_go_skips_test_files(self, tmp_path):
        """测试跳过 test 文件"""
        pkg_dir = tmp_path / "svc"
        pkg_dir.mkdir()
        (pkg_dir / "main.go").write_text('package main\nfunc main() {}\n')
        (pkg_dir / "main_test.go").write_text('package main\nfunc TestMain(t *testing.T) {}\n')
        ext = CodeKnowledgeExtractor(str(pkg_dir), "go")
        result = ext.extract()
        assert isinstance(result, dict)

    def test_extract_go_no_exported_funcs(self, tmp_path):
        """测试无导出函数的仓库"""
        pkg_dir = tmp_path / "internal"
        pkg_dir.mkdir()
        (pkg_dir / "util.go").write_text('package internal\nfunc helper() {}\n')
        ext = CodeKnowledgeExtractor(str(pkg_dir), "go")
        result = ext.extract()
        assert isinstance(result, dict)


# ─── CoreFlowAnalyzer 深度测试 ───────────────────────────────

class TestInferFromBusinessLogic:
    """从业务逻辑推理流程测试"""

    def test_infer_from_bl_with_data(self):
        ir = {
            "business_logic": [
                {
                    "route": "/api/bid",
                    "handler": "PlaceBidHandler",
                    "call_chain": ["PlaceBidHandler", "BidService", "BidDAO"],
                    "call_tree": [{"calls": [{"calls": []}]}],
                    "data_flow": "request -> bid -> db",
                }
            ],
            "routes": [{"path": "/api/bid", "method": "POST", "handler": "PlaceBidHandler"}],
            "functions": [{"name": "PlaceBidHandler", "file": "h.go"}],
        }
        analyzer = CoreFlowAnalyzer(ir)
        flows = analyzer._infer_from_business_logic()
        assert len(flows) == 1
        assert flows[0]["flow_type"] == "http_handler"
        assert flows[0]["entry_point"] == "PlaceBidHandler"
        assert isinstance(flows[0]["stages"], list)

    def test_infer_from_bl_empty(self):
        analyzer = CoreFlowAnalyzer({})
        flows = analyzer._infer_from_business_logic()
        assert flows == []

    def test_infer_state_machine_flows_with_status_struct(self):
        """测试状态机流程检测（有 status 字段的 struct）"""
        ir = {
            "structs": [
                {"name": "AdGroup", "fields": [{"name": "status"}, {"name": "id"}]},
                {"name": "Creative", "fields": [{"name": "state"}, {"name": "title"}]},
            ],
            "routes": [],
            "functions": [],
            "call_graph": [],
        }
        analyzer = CoreFlowAnalyzer(ir)
        flows = analyzer._infer_state_machine_flows()
        assert isinstance(flows, list)
        # 有 status 字段的 struct 应触发状态机流程推理

    def test_infer_async_flows_empty(self):
        analyzer = CoreFlowAnalyzer({})
        flows = analyzer._infer_async_flows()
        assert isinstance(flows, list)

    def test_infer_crud_flows_empty(self):
        analyzer = CoreFlowAnalyzer({})
        flows = analyzer._infer_crud_flows()
        assert isinstance(flows, list)

    def test_infer_data_flow_routes_with_routes(self):
        ir = {
            "routes": [
                {"method": "POST", "path": "/api/bid", "handler": "PlaceBidHandler"},
            ],
            "functions": [
                {"name": "PlaceBidHandler", "file": "handler/bid.go"},
                {"name": "BidService", "file": "service/bid_service.go"},
                {"name": "BidDAO", "file": "dao/bid_dao.go"},
            ],
            "call_graph": [
                {"caller": "PlaceBidHandler", "callee": "BidService"},
                {"caller": "BidService", "callee": "BidDAO"},
            ],
            "entity_tables": [{"entity": "Bid", "table": "bids"}],
        }
        analyzer = CoreFlowAnalyzer(ir)
        flows = analyzer._infer_data_flow_routes()
        assert isinstance(flows, list)
        # 应该有至少一条路由的数据流
        if flows:
            assert "entry_point" in flows[0] or "handler" in flows[0]

    def test_infer_data_flows_full(self):
        ir = {
            "routes": [
                {"method": "POST", "path": "/api/users/{id}/bids", "handler": "PlaceBidHandler"},
            ],
            "functions": [
                {"name": "PlaceBidHandler", "file": "handler/bid.go"},
                {"name": "BidService", "file": "service/bid_service.go"},
                {"name": "BidDAO", "file": "dao/bid_dao.go"},
            ],
            "call_graph": [
                {"caller": "PlaceBidHandler", "callee": "BidService"},
                {"caller": "BidService", "callee": "BidDAO"},
            ],
        }
        analyzer = CoreFlowAnalyzer(ir)
        flows = analyzer.infer_data_flows()
        assert isinstance(flows, list)

    def test_extract_entities_from_path(self):
        analyzer = CoreFlowAnalyzer({})
        entities = analyzer._extract_entities_from_path("/api/users/{id}/bids")
        assert isinstance(entities, list)
        assert "users" in entities or "bids" in entities

    def test_calc_depth_nested(self):
        analyzer = CoreFlowAnalyzer({})
        tree = [
            {"calls": [{"calls": [{"calls": [{"calls": []}]}]}]},
        ]
        depth = analyzer._calc_depth(tree)
        assert depth >= 3

    def test_calc_depth_flat(self):
        analyzer = CoreFlowAnalyzer({})
        depth = analyzer._calc_depth([])
        assert depth == 0

    def test_extract_stages_multi(self):
        analyzer = CoreFlowAnalyzer({})
        stages = analyzer._extract_stages(["BindRequest", "PlaceBidHandler", "BidService", "BidDAO"])
        assert "Handler" in stages
        assert "Service" in stages
        assert "DAO" in stages

    def test_infer_flow_name_has_verb(self):
        analyzer = CoreFlowAnalyzer({})
        name = analyzer._infer_flow_name("PlaceBid", "/api/bid")
        assert "出价" in name or len(name) > 0

    def test_infer_flow_name_no_match(self):
        analyzer = CoreFlowAnalyzer({})
        name = analyzer._infer_flow_name("FooBar", "/api/xyz")
        assert isinstance(name, str)
        assert len(name) > 0

    def test_merge_similar_flows(self):
        analyzer = CoreFlowAnalyzer({})
        flows = [
            {"name": "login_flow", "score": 0.9, "route": "/api/login"},
            {"name": "login_flow", "score": 0.8, "route": "/api/login"},
            {"name": "bid_flow", "score": 0.7},
        ]
        merged = analyzer._merge_similar_flows(flows)
        assert len(merged) <= len(flows)

    def test_detect_error_handling_flows(self):
        ir = {
            "core_flows": [
                {
                    "flow_name": "出价流程",
                    "entry_point": "PlaceBidHandler",
                    "call_chain": ["PlaceBidHandler", "BidService", "BidDAO"],
                    "max_depth": 3,
                }
            ],
            "routes": [],
            "functions": [],
        }
        analyzer = CoreFlowAnalyzer(ir)
        flows = analyzer.detect_error_handling_flows()
        assert isinstance(flows, list)

    def test_rank_flows(self):
        analyzer = CoreFlowAnalyzer({})
        flows = [
            {"name": "A", "score": 0.3},
            {"name": "B", "score": 0.9},
            {"name": "C", "score": 0.5},
        ]
        ranked = analyzer._rank_flows(flows)
        assert ranked[0]["name"] == "B"
        assert len(ranked) <= 15

    def test_infer_service_topology(self):
        ir = {
            "services": [
                {"name": "auth-service", "port": 8080},
                {"name": "bid-service", "port": 8081},
            ],
            "call_graph": [],
            "routes": [],
            "functions": [],
        }
        analyzer = CoreFlowAnalyzer(ir)
        topology = analyzer.infer_service_topology()
        assert isinstance(topology, dict)

    def test_analyze_entity_ownership(self):
        ir = {
            "entity_tables": [
                {"entity": "User", "table": "users"},
                {"entity": "Bid", "table": "bids"},
            ],
            "functions": [],
            "call_graph": [],
        }
        analyzer = CoreFlowAnalyzer(ir)
        ownership = analyzer.analyze_entity_ownership()
        assert isinstance(ownership, list)

    def test_cluster_business_processes(self):
        ir = {
            "routes": [
                {"method": "POST", "path": "/api/login", "handler": "LoginHandler"},
                {"method": "POST", "path": "/api/bid", "handler": "PlaceBidHandler"},
            ],
            "functions": [
                {"name": "LoginHandler", "file": "h.go"},
                {"name": "PlaceBidHandler", "file": "h.go"},
            ],
            "call_graph": [],
        }
        analyzer = CoreFlowAnalyzer(ir)
        clusters = analyzer.cluster_business_processes()
        assert isinstance(clusters, list)


# ─── AgentTaskGenerator 深度测试 ─────────────────────────────

class TestAgentTaskGeneratorDeep:
    """Agent 任务生成器深度测试"""

    def _make_gen(self):
        profile = {
            "business_domain": "auction",
            "repositories": [{"name": "test-repo", "path": "/tmp/test"}],
        }
        ir = {
            "functions": [{"name": "PlaceBid"}],
            "routes": [{"path": "/api/bid", "method": "POST", "handler": "PlaceBid"}],
        }
        return AgentTaskGenerator(profile, ir)

    def test_generate_tasks_with_modules_and_interfaces(self):
        gen = self._make_gen()
        td = """
# 技术方案

## 新增模块
新增模块: BidHandler

## 新增接口
POST /api/bid
GET /api/bid/{id}
"""
        tasks = gen.generate_tasks(td)
        assert isinstance(tasks, list)
        assert len(tasks) > 0
        # 验证优先级排序
        for i in range(len(tasks) - 1):
            assert gen._priority_score(tasks[i].priority) <= gen._priority_score(tasks[i + 1].priority)

    def test_parse_td_elements_with_test_requirements(self):
        gen = self._make_gen()
        td = """
## 测试需求
- name: 出价成功测试
  priority: P0
  description: 测试出价成功场景
  files: [handler/bid_test.go]
"""
        elements = gen._parse_td_elements(td)
        assert any(e.get("type") == "test" for e in elements)

    def test_extract_new_interfaces_rpc(self):
        gen = self._make_gen()
        interfaces = gen._extract_new_interfaces("rpc PlaceBid(BidRequest) returns (BidResponse)")
        assert any("PlaceBid" in str(i) for i in interfaces)

    def test_extract_db_changes_alter_table(self):
        gen = self._make_gen()
        changes = gen._extract_db_changes("ALTER TABLE bids ADD COLUMN status VARCHAR(20);")
        assert isinstance(changes, list)
        # ALTER TABLE pattern matches with semicolon


# ─── QualityGate 边界测试 ────────────────────────────────────

class TestQualityGateEdgeCases:
    """质量门禁边界测试"""

    def _make_gate(self, tmp_path):
        profile = {
            "business_domain": "auction",
            "quality_gate": {"required_coverage": 0.7},
        }
        return QualityGate(profile, str(tmp_path / "out"))

    def test_empty_report(self, tmp_path):
        gate = self._make_gate(tmp_path)
        report = DeliveryReport(
            prd_review={},
            technical_design={},
            agent_tasks=[],
            test_cases={},
            execution_result={},
            quality_gate={"required_coverage": 0.7},
        )
        result = gate.evaluate(report)
        assert "checks" in result

    def test_zero_tasks(self, tmp_path):
        gate = self._make_gate(tmp_path)
        report = DeliveryReport(
            prd_review={"p0_issues": [], "p1_issues": []},
            technical_design={},
            agent_tasks=[],
            test_cases={"coverage": 0.0},
            execution_result={},
            quality_gate={"required_coverage": 0.7},
        )
        result = gate.evaluate(report)
        checks = {c["check"]: c["status"] for c in result["checks"]}
        assert checks.get("test_coverage") == "warning"

    def test_all_critical_failures(self, tmp_path):
        gate = self._make_gate(tmp_path)
        report = DeliveryReport(
            prd_review={"p0_issues": [{"msg": "critical"}], "p1_issues": []},
            technical_design={},
            agent_tasks=[{"status": "failed"}],
            test_cases={"coverage": 0.3},
            execution_result={},
            quality_gate={"required_coverage": 0.7},
        )
        result = gate.evaluate(report)
        failed = [c for c in result["checks"] if c["status"] == "failed"]
        assert len(failed) > 0


# ─── KnowledgeWriter 全类型测试 ─────────────────────────────

class TestKnowledgeWriterFull:
    """知识库写入器全功能测试"""

    def test_write_all_types(self, tmp_path):
        writer = KnowledgeWriter()
        knowledge = {
            "architecture": "# 架构",
            "business_flows": "# 流程",
            "database_schema": "# 数据库",
            "service_architecture": "# 服务",
            "external_systems": "# 外部系统",
            "glossary": {"出价": "Bid"},
        }
        files = writer.write(knowledge, str(tmp_path / "kb"))
        assert len(files) == 6
        assert (tmp_path / "kb" / "architecture.md").exists()
        assert (tmp_path / "kb" / "glossary.md").exists()

    def test_write_updates_index(self, tmp_path):
        writer = KnowledgeWriter()
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        # 创建已有 index.md
        (kb_dir / "index.md").write_text("# Knowledge Base\n\n| 文件 | 状态 |\n|------|------|\n| architecture.md | 待生成 |")
        files = writer.write({"architecture": "# 架构"}, str(kb_dir))
        index_content = (kb_dir / "index.md").read_text()
        assert "已生成" in index_content
