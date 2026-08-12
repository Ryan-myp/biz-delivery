#!/usr/bin/env python3
"""
Skills 系统测试
测试所有 Skill 的基本功能
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


class TestSkillBase:
    """测试 Skill 基类"""

    def test_skill_result_to_dict(self):
        """测试 SkillResult 序列化"""
        from skills.base import SkillResult
        
        result = SkillResult(
            success=True,
            output={"key": "value"},
            errors=[],
            metadata={"skill": "test"}
        )
        
        data = result.to_dict()
        assert data["success"] == True
        assert data["output"]["key"] == "value"
        assert data["metadata"]["skill"] == "test"


class TestPRDReviewSkill:
    """测试 PRD Review Skill"""

    def test_run_with_mock(self):
        """测试运行（Mock 模式）"""
        from skills.prd_review import PRDReviewSkill
        
        skill = PRDReviewSkill(profile={"language": "go"})
        
        with patch('scripts.review_engine.ReviewEngine') as mock_engine:
            mock_result = Mock()
            mock_result.issues = [
                {"priority": "P1", "message": "Test issue"}
            ]
            mock_engine.return_value.run.return_value = mock_result
            
            result = skill.run({
                "prd_content": "## 用户登录功能\n\n用户可以使用邮箱登录"
            })
            
            assert result.success == True
            assert result.output["p1_count"] == 1
            assert result.output["total_issues"] == 1


class TestTDSkill:
    """测试 TD Skill"""

    def test_run_with_mock(self):
        """测试运行（Mock 模式）"""
        from skills.technical_design import TDSkill
        
        skill = TDSkill(profile={"language": "go"})
        
        with patch('scripts.td_engine.TDEngine') as mock_engine:
            mock_result = Mock()
            mock_result.td_content = "## 架构设计\n- 微服务\n- JWT 认证"
            mock_engine.return_value.run.return_value = mock_result
            
            result = skill.run({
                "prd_content": "## 用户登录功能"
            })
            
            assert result.success == True
            assert "架构设计" in result.output["td_content"]


class TestTaskPlanningSkill:
    """测试任务规划 Skill"""

    def test_run_with_mock(self):
        """测试运行（Mock 模式）"""
        from skills.task_planning import TaskPlanningSkill
        
        skill = TaskPlanningSkill(profile={"language": "go"})
        
        with patch('scripts.agent.prompt_generator.TaskDecomposer') as mock_decomposer:
            mock_decomposer.return_value.decompose.return_value = [
                {"id": "T1", "title": "Task 1", "priority": "P0"},
                {"id": "T2", "title": "Task 2", "priority": "P1"},
            ]
            
            result = skill.run({
                "td_content": "## 技术方案\n- Task 1\n- Task 2"
            })
            
            assert result.success == True
            assert result.output["total_tasks"] == 2
            assert result.output["p0_count"] == 1


class TestTestCaseSkill:
    """测试测试用例生成 Skill"""

    def test_run_with_mock(self):
        """测试运行（Mock 模式）"""
        from skills.test_case import TestCaseSkill
        
        skill = TestCaseSkill(profile={"language": "go"})
        
        with patch('scripts.test_engine.TestEngine') as mock_engine:
            mock_result = Mock()
            mock_result.test_cases = [
                {"priority": "P0", "case": "TestLogin"},
                {"priority": "P1", "case": "TestLogout"},
            ]
            mock_result.coverage_analysis = {"coverage": 0.8}
            mock_engine.return_value.run.return_value = mock_result
            
            result = skill.run({
                "prd_content": "## 用户登录功能"
            })
            
            assert result.success == True
            assert result.output["total_cases"] == 2
            assert result.output["p0_count"] == 1


class TestSkillOrchestrator:
    """测试 Skill 编排器"""

    def test_run_pipeline(self):
        """测试运行流水线"""
        from skills.orchestrator import SkillOrchestrator
        from skills.prd_review import PRDReviewSkill
        
        orchestrator = SkillOrchestrator(profile={"language": "go"})
        orchestrator.register("prd_review", PRDReviewSkill())
        
        # 测试注册
        assert "prd_review" in orchestrator.skills

    def test_run_skill_not_found(self):
        """测试未注册的 Skill"""
        from skills.orchestrator import SkillOrchestrator
        
        orchestrator = SkillOrchestrator()
        
        result = orchestrator._run_skill("nonexistent", {})
        
        assert result["success"] == False
        assert "not found" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
