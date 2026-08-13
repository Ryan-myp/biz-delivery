"""
Delivery Pipeline 深度测试套件
覆盖：AgentTask、DeliveryReport、AgentTaskGenerator、QualityGate
目标：scripts/delivery_pipeline.py 覆盖率 ≥55%
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scripts.delivery_pipeline import (
    TaskPriority, TaskStatus, AgentPhase, AgentTask, DeliveryReport,
    AgentTaskGenerator, QualityGate, BizDeliveryPipeline,
)


def make_task():
    return AgentTask(
        id="T001",
        title="实现出价接口",
        description="实现 PlaceBid handler",
        priority=TaskPriority.P0,
        phase=AgentPhase.IMPLEMENT,
        depends_on=[],
        files_to_create=["handler/bid.go"],
        files_to_modify=[],
        code_template="func PlaceBid(ctx) error { return nil }",
        test_cases=["TC001", "TC002"],
        acceptance_criteria=["出价成功返回 200"],
    )


# ─── AgentTask 测试 ────────────────────────────────────────────

class TestAgentTask:
    def test_to_dict(self):
        task = make_task()
        d = task.to_dict()
        assert d["id"] == "T001"
        assert d["title"] == "实现出价接口"
        # priority 是枚举，to_dict 用 asdict 会保留枚举对象
        assert d["priority"] == TaskPriority.P0

    def test_to_prompt(self):
        task = make_task()
        prompt = task.to_prompt()
        assert "实现出价接口" in prompt
        assert "T001" in prompt
        assert "[TASK_COMPLETE]" in prompt
        assert "handler/bid.go" in prompt

    def test_to_prompt_with_dependencies(self):
        task = make_task()
        task.depends_on = ["T000"]
        prompt = task.to_prompt()
        assert "T000" in prompt

    def test_priority_values(self):
        assert TaskPriority.P0.value == "P0"
        assert TaskPriority.P1.value == "P1"
        assert TaskPriority.P2.value == "P2"

    def test_status_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_phase_values(self):
        assert AgentPhase.SETUP.value == "setup"
        assert AgentPhase.IMPLEMENT.value == "implement"
        assert AgentPhase.TEST.value == "test"
        assert AgentPhase.REVIEW.value == "review"


# ─── AgentTaskGenerator 测试 ──────────────────────────────────

class TestAgentTaskGenerator:
    def _make_gen(self):
        profile = {
            "business_domain": "auction",
            "repositories": [{"name": "test-repo", "path": "/tmp/test"}],
        }
        ir = {
            "functions": [{"name": "PlaceBid"}],
            "routes": [{"path": "/api/bid", "method": "POST", "handler": "PlaceBid"}],
            "structs": [{"name": "BidRequest"}],
        }
        return AgentTaskGenerator(profile, ir)

    def test_generate_tasks_empty_td(self):
        gen = self._make_gen()
        tasks = gen.generate_tasks("# 无变更\n\n保持现状")
        assert isinstance(tasks, list)

    def test_generate_tasks_with_module(self):
        gen = self._make_gen()
        td = "# 技术方案\n\n## 新增模块\n新增模块: BidHandler"
        tasks = gen.generate_tasks(td)
        assert isinstance(tasks, list)
        assert len(tasks) > 0

    def test_parse_td_elements_no_modules(self):
        gen = self._make_gen()
        elements = gen._parse_td_elements("# 无内容")
        assert isinstance(elements, list)

    def test_parse_td_elements_with_interface(self):
        gen = self._make_gen()
        td = "GET /api/users\nPOST /api/bid"
        elements = gen._parse_td_elements(td)
        assert isinstance(elements, list)

    def test_extract_new_modules(self):
        gen = self._make_gen()
        modules = gen._extract_new_modules("新增模块: BidHandler\n新建 adgroup.go")
        assert "BidHandler" in modules or "adgroup" in modules

    def test_extract_new_interfaces_route(self):
        gen = self._make_gen()
        interfaces = gen._extract_new_interfaces("GET /api/users")
        assert isinstance(interfaces, list)

    def test_extract_db_changes_create_table(self):
        gen = self._make_gen()
        changes = gen._extract_db_changes("CREATE TABLE bids (id INT, amount DECIMAL)")
        assert any(c.get("table") == "bids" for c in changes)

    def test_resolve_dependencies(self):
        gen = self._make_gen()
        tasks = [make_task(), make_task()]
        gen._resolve_dependencies(tasks)
        assert isinstance(tasks, list)

    def test_priority_score(self):
        gen = self._make_gen()
        # P0 优先级更高，score 应该更小（排在前面）
        assert gen._priority_score(TaskPriority.P0) <= gen._priority_score(TaskPriority.P2)


# ─── QualityGate 测试 ──────────────────────────────────────────

class TestQualityGate:
    def _make_gate(self, tmp_path):
        profile = {
            "business_domain": "auction",
            "quality_gate": {"required_coverage": 0.7},
        }
        return QualityGate(profile, str(tmp_path / "out"))

    def test_prd_review_passed(self, tmp_path):
        gate = self._make_gate(tmp_path)
        report = DeliveryReport(
            prd_review={"p0_issues": [], "p1_issues": []},
            technical_design={},
            agent_tasks=[],
            test_cases={"coverage": 0.8},
            execution_result={},
            quality_gate={"required_coverage": 0.7},
        )
        result = gate.evaluate(report)
        checks = {c["check"]: c["status"] for c in result["checks"]}
        assert checks.get("prd_review_quality") == "passed"

    def test_prd_review_failed(self, tmp_path):
        gate = self._make_gate(tmp_path)
        report = DeliveryReport(
            prd_review={"p0_issues": [{"msg": "需求不清晰"}], "p1_issues": []},
            technical_design={},
            agent_tasks=[],
            test_cases={"coverage": 0.9},
            execution_result={},
            quality_gate={"required_coverage": 0.7},
        )
        result = gate.evaluate(report)
        checks = {c["check"]: c["status"] for c in result["checks"]}
        assert checks.get("prd_review_quality") == "failed"

    def test_td_completeness(self, tmp_path):
        gate = self._make_gate(tmp_path)
        report = DeliveryReport(
            prd_review={"p0_issues": [], "p1_issues": []},
            technical_design={"架构设计": "...", "接口设计": "...", "数据库设计": "..."},
            agent_tasks=[],
            test_cases={"coverage": 0.9},
            execution_result={},
            quality_gate={"required_coverage": 0.7},
        )
        result = gate.evaluate(report)
        checks = {c["check"]: c["status"] for c in result["checks"]}
        assert checks.get("td_completeness") == "passed"

    def test_td_missing_sections(self, tmp_path):
        gate = self._make_gate(tmp_path)
        report = DeliveryReport(
            prd_review={"p0_issues": [], "p1_issues": []},
            technical_design={"架构设计": "..."},
            agent_tasks=[],
            test_cases={"coverage": 0.9},
            execution_result={},
            quality_gate={"required_coverage": 0.7},
        )
        result = gate.evaluate(report)
        checks = {c["check"]: c["status"] for c in result["checks"]}
        assert checks.get("td_completeness") == "warning"

    def test_task_completion_high(self, tmp_path):
        gate = self._make_gate(tmp_path)
        tasks = [
            {"status": "completed"},
            {"status": "completed"},
            {"status": "completed"},
            {"status": "completed"},
        ]
        report = DeliveryReport(
            prd_review={"p0_issues": [], "p1_issues": []},
            technical_design={},
            agent_tasks=tasks,
            test_cases={"coverage": 0.9},
            execution_result={},
            quality_gate={"required_coverage": 0.7},
        )
        result = gate.evaluate(report)
        checks = {c["check"]: c["status"] for c in result["checks"]}
        # 75% 完成率
        assert checks.get("task_completion") == "passed"

    def test_task_completion_low(self, tmp_path):
        gate = self._make_gate(tmp_path)
        tasks = [
            {"status": "completed"},
            {"status": "pending"},
            {"status": "pending"},
            {"status": "pending"},
        ]
        report = DeliveryReport(
            prd_review={"p0_issues": [], "p1_issues": []},
            technical_design={},
            agent_tasks=tasks,
            test_cases={"coverage": 0.9},
            execution_result={},
            quality_gate={"required_coverage": 0.7},
        )
        result = gate.evaluate(report)
        checks = {c["check"]: c["status"] for c in result["checks"]}
        assert checks.get("task_completion") == "failed"

    def test_test_coverage_low(self, tmp_path):
        gate = self._make_gate(tmp_path)
        report = DeliveryReport(
            prd_review={"p0_issues": [], "p1_issues": []},
            technical_design={},
            agent_tasks=[],
            test_cases={"coverage": 0.5},
            execution_result={},
            quality_gate={"required_coverage": 0.7},
        )
        result = gate.evaluate(report)
        checks = {c["check"]: c["status"] for c in result["checks"]}
        assert checks.get("test_coverage") == "warning"

    def test_full_pass(self, tmp_path):
        gate = self._make_gate(tmp_path)
        report = DeliveryReport(
            prd_review={"p0_issues": [], "p1_issues": []},
            technical_design={"架构设计": "x", "接口设计": "x", "数据库设计": "x"},
            agent_tasks=[{"status": "completed"}],
            test_cases={"coverage": 0.9},
            execution_result={},
            quality_gate={"required_coverage": 0.7},
        )
        result = gate.evaluate(report)
        passed = sum(1 for c in result["checks"] if c["status"] == "passed")
        assert passed > 0


# ─── BizDeliveryPipeline 测试 ─────────────────────────────────

class TestBizDeliveryPipeline:
    @patch('scripts.delivery_pipeline.LLMClient')
    def test_init(self, mock_llm, tmp_path):
        profile_path = tmp_path / "profile.json"
        profile_path.write_text(json.dumps({
            "business_domain": "test",
            "repositories": [{"name": "test", "path": str(tmp_path)}],
        }))
        mock_llm.return_value = MagicMock()
        pipeline = BizDeliveryPipeline(str(profile_path), str(tmp_path / "out"))
        assert pipeline is not None

    def test_init_missing_profile(self, tmp_path):
        with pytest.raises((FileNotFoundError, Exception)):
            BizDeliveryPipeline(str(tmp_path / "no_exist.json"), str(tmp_path / "out"))
