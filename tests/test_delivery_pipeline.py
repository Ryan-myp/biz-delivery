#!/usr/bin/env python3
"""
端到端流水线核心功能测试
测试 BizDeliveryPipeline 的完整流程
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from delivery_pipeline import (
    DeliveryReport,
    AgentTask,
    TaskPriority,
    AgentPhase,
    QualityGate,
)


class TestDeliveryReport:
    """测试交付报告模型"""

    def test_create_report(self):
        """测试创建交付报告"""
        report = DeliveryReport(
            prd_review={"status": "passed", "p0_issues": [], "p1_issues": []},
            technical_design={"type": "microservice", "new_files": [], "modified_files": []},
            agent_tasks=[],
            test_cases={"total_cases": 0, "p0_count": 0, "coverage": 0.9},
            execution_result={"status": "unknown", "pass_rate": 0.95},
            quality_gate={"passed": False, "blockers": []},
        )
        
        assert report.prd_review["status"] == "passed"
        assert isinstance(report.agent_tasks, list)
    
    def test_report_summary(self):
        """测试报告摘要生成"""
        report = DeliveryReport(
            prd_review={"status": "passed", "p0_issues": [], "p1_issues": ["issue1"]},
            technical_design={"type": "monolith", "new_files": ["auth.go"], "modified_files": []},
            agent_tasks=[
                {"id": "T1", "title": "Auth", "priority": "P0"},
                {"id": "T2", "title": "API", "priority": "P1"},
            ],
            test_cases={"total_cases": 10, "p0_count": 2, "coverage": 0.85},
            execution_result={"status": "passed", "pass_rate": 0.95},
            quality_gate={"passed": True, "blockers": []},
        )
        
        summary = report.summary()
        assert "biz-delivery v3.0" in summary
        assert "PRD 审查" in summary
        assert "技术方案" in summary
        assert "Agent 开发任务" in summary
        assert "质量门禁" in summary


class TestAgentTask:
    """测试Agent任务模型"""

    def test_task_creation(self):
        """测试任务创建"""
        task = AgentTask(
            id="TASK-001",
            title="Implement authentication",
            description="Add JWT authentication module",
            priority=TaskPriority.P0,
            phase=AgentPhase.SETUP,
            depends_on=[],
            files_to_create=["auth.go"],
            files_to_modify=[],
            code_template="package auth",
            test_cases=["TestLogin", "TestTokenValidation"],
            acceptance_criteria=["User can login", "Token is valid"],
        )
        
        assert task.id == "TASK-001"
        assert task.priority == TaskPriority.P0
        assert task.phase == AgentPhase.SETUP
        assert "auth.go" in task.files_to_create
    
    def test_task_to_dict(self):
        """测试任务序列化"""
        task = AgentTask(
            id="TASK-001",
            title="Test Task",
            description="desc",
            priority=TaskPriority.P1,
            phase=AgentPhase.IMPLEMENT,
            depends_on=[],
            files_to_create=[],
            files_to_modify=[],
            code_template="",
            test_cases=[],
            acceptance_criteria=[],
        )
        
        data = task.to_dict()
        assert data["id"] == "TASK-001"
        assert data["priority"] == TaskPriority.P1
    
    def test_task_to_prompt(self):
        """测试任务提示词生成"""
        task = AgentTask(
            id="TASK-001",
            title="Implement auth",
            description="Add JWT module",
            priority=TaskPriority.P0,
            phase=AgentPhase.SETUP,
            depends_on=[],
            files_to_create=["auth.go"],
            files_to_modify=[],
            code_template="package auth",
            test_cases=["TestLogin"],
            acceptance_criteria=["Login works"],
        )
        
        prompt = task.to_prompt()
        
        assert "TASK-001" in prompt
        assert "Implement auth" in prompt
        assert "JWT" in prompt
        assert "auth.go" in prompt
        assert "TestLogin" in prompt
        assert "TASK_COMPLETE" in prompt
    
    def test_task_priority_sorting(self):
        """测试任务优先级排序"""
        tasks = [
            AgentTask(id="T3", title="t3", description="t3", priority=TaskPriority.P2, phase=AgentPhase.SETUP, depends_on=[], files_to_create=[], files_to_modify=[], code_template="", test_cases=[], acceptance_criteria=[]),
            AgentTask(id="T1", title="t1", description="t1", priority=TaskPriority.P0, phase=AgentPhase.SETUP, depends_on=[], files_to_create=[], files_to_modify=[], code_template="", test_cases=[], acceptance_criteria=[]),
            AgentTask(id="T2", title="t2", description="t2", priority=TaskPriority.P1, phase=AgentPhase.SETUP, depends_on=[], files_to_create=[], files_to_modify=[], code_template="", test_cases=[], acceptance_criteria=[]),
        ]
        
        sorted_tasks = sorted(tasks, key=lambda t: t.priority.value)
        assert sorted_tasks[0].priority == TaskPriority.P0
        assert sorted_tasks[1].priority == TaskPriority.P1
        assert sorted_tasks[2].priority == TaskPriority.P2


class TestQualityGate:
    """测试质量门禁"""

    def test_quality_gate_init(self):
        """测试质量门禁初始化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            gate = QualityGate(profile={}, output_dir=tmpdir)
            assert gate.output_dir == Path(tmpdir)
    
    def test_evaluate_passing_report(self):
        """测试通过的报告评分"""
        with tempfile.TemporaryDirectory() as tmpdir:
            gate = QualityGate(profile={}, output_dir=tmpdir)
            
            report = DeliveryReport(
                prd_review={"status": "passed", "p0_issues": [], "p1_issues": []},
                technical_design={"type": "microservice"},
                agent_tasks=[],
                test_cases={"total_cases": 10, "coverage": 0.9},
                execution_result={"status": "passed", "pass_rate": 0.95},
                quality_gate={"passed": True},
            )
            
            result = gate.evaluate(report)
            assert "score" in result
            assert "checks" in result
    
    def test_evaluate_failing_report(self):
        """测试失败报告的评分"""
        with tempfile.TemporaryDirectory() as tmpdir:
            gate = QualityGate(profile={}, output_dir=tmpdir)
            
            report = DeliveryReport(
                prd_review={"status": "failed", "p0_issues": ["Critical issue"], "p1_issues": []},
                technical_design={},
                agent_tasks=[],
                test_cases={"coverage": 0.3},
                execution_result={},
                quality_gate={},
            )
            
            result = gate.evaluate(report)
            assert result["score"] < 100
    
    def test_evaluate_low_coverage(self):
        """测试低覆盖率评分"""
        with tempfile.TemporaryDirectory() as tmpdir:
            gate = QualityGate(profile={}, output_dir=tmpdir)
            
            report = DeliveryReport(
                prd_review={"p0_issues": [], "p1_issues": []},
                technical_design={},
                agent_tasks=[],
                test_cases={"coverage": 0.3},
                execution_result={},
                quality_gate={},
            )
            
            result = gate.evaluate(report)
            checks = result.get("checks", [])
            coverage_check = next((c for c in checks if c["check"] == "test_coverage"), None)
            if coverage_check:
                assert coverage_check["status"] == "warning"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
