#!/usr/bin/env python3
"""
Skills 系统测试
测试所有 Skill 的基本功能（纯确定性实现）
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
    """测试 PRD Review Skill（纯规则实现）"""

    def test_run_missing_title(self):
        """测试缺少标题的问题"""
        from skills.prd_review import PRDReviewSkill
        
        skill = PRDReviewSkill(profile={"language": "go"})
        
        result = skill.run({
            "prd_content": "这是一个没有标题的 PRD\n\n## 需求\n用户登录功能"
        })
        
        assert result.success == False  # P0 问题导致失败
        assert result.output["p0_count"] > 0
    
    def test_run_complete_prd(self):
        """测试完整的 PRD"""
        from skills.prd_review import PRDReviewSkill
        
        skill = PRDReviewSkill(profile={"language": "go"})
        
        prd_content = """# 用户登录功能

## 需求描述
用户可以使用邮箱和密码登录系统

## 接口定义
- POST /api/login
- GET /api/user/info

## 数据模型
- User
- Token

## 边界条件
- 密码长度限制
- 邮箱格式验证
"""
        
        result = skill.run({"prd_content": prd_content})
        
        assert result.success == True
        assert result.metadata["approach"] == "rule_based"
    
    def test_run_with_vague_requirements(self):
        """测试模糊需求检测"""
        from skills.prd_review import PRDReviewSkill
        
        skill = PRDReviewSkill(profile={"language": "go"})
        
        result = skill.run({
            "prd_content": "# 优化系统\n\n我们需要优化用户体验，提升系统性能"
        })
        
        # 应该检测到模糊需求
        issues = result.output.get("issues", [])
        vague_issues = [i for i in issues if "模糊" in i.get("name", "")]
        assert len(vague_issues) > 0


class TestTDSkill:
    """测试 TD Skill（模板填充）"""

    def test_run_with_mock(self):
        """测试运行（真实实现）"""
        from skills.technical_design import TDSkill
        
        skill = TDSkill(profile={"language": "go"})
        
        prd_content = """# 用户登录功能

## 需求描述
用户可以使用邮箱和密码登录系统

## 接口定义
- POST /api/login
- GET /api/user/info
"""
        
        result = skill.run({"prd_content": prd_content})
        
        assert result.success == True
        assert "技术方案" in result.output["td_content"]
        assert "用户登录功能" in result.output["td_content"]


class TestTaskPlanningSkill:
    """测试任务规划 Skill（基于规则）"""

    def test_run_with_mock(self):
        """测试运行（真实实现）"""
        from skills.task_planning import TaskPlanningSkill
        
        skill = TaskPlanningSkill(profile={"language": "go"})
        
        td_content = """# 技术方案：用户登录

## 模块划分
- AuthModule
- UserModule

## 接口设计
| GET | /api/users | 获取用户列表 |
| POST | /api/login | 用户登录 |
"""
        
        result = skill.run({"td_content": td_content})
        
        assert result.success == True
        assert result.output["total_tasks"] > 0
        # P0 任务应该排在前面
        tasks = result.output["tasks"]
        if len(tasks) > 1:
            assert tasks[0]["priority"] <= tasks[1]["priority"]


class TestTestCaseSkill:
    """测试测试用例生成 Skill（基于模板）"""

    def test_run_with_mock(self):
        """测试运行（真实实现）"""
        from skills.test_case import TestCaseSkill
        
        skill = TestCaseSkill(profile={"language": "go"})
        
        prd_content = """# 用户登录功能

## 需求描述
用户可以使用邮箱和密码登录系统

## 接口定义
- POST /api/login
"""
        
        result = skill.run({"prd_content": prd_content})
        
        assert result.success == True
        assert result.output["total_cases"] > 0
        # 应该有正向、异常、边界用例
        case_types = [c["type"] for c in result.output["test_cases"]]
        assert "positive" in case_types
        assert "negative" in case_types
        assert "boundary" in case_types


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


class TestSkillIntegration:
    """测试 Skill 集成"""

    def test_full_pipeline(self):
        """测试完整流水线（Skill 链式调用）"""
        from skills import SkillOrchestrator, PRDReviewSkill, TDSkill, TaskPlanningSkill, TestCaseSkill
        
        orchestrator = SkillOrchestrator(profile={"language": "go"})
        orchestrator.register("prd_review", PRDReviewSkill())
        orchestrator.register("td", TDSkill())
        orchestrator.register("task_planning", TaskPlanningSkill())
        orchestrator.register("test_case", TestCaseSkill())
        
        prd_content = """# 用户登录功能

## 需求描述
用户可以使用邮箱和密码登录系统

## 接口定义
- POST /api/login
- GET /api/user/info

## 数据模型
- User
"""
        
        # 运行 PRD Review
        review_result = orchestrator._run_skill("prd_review", {"prd_content": prd_content})
        assert review_result["success"] == True or review_result["output"]["p0_count"] == 0
        
        # 运行 TD
        td_result = orchestrator._run_skill("td", {"prd_content": prd_content})
        assert td_result["success"] == True
        
        # 运行 Task Planning
        td_content = td_result.get("output", {}).get("td_content", "")
        plan_result = orchestrator._run_skill("task_planning", {"td_content": td_content})
        assert plan_result["success"] == True
        
        # 运行 Test Case
        test_result = orchestrator._run_skill("test_case", {"prd_content": prd_content})
        assert test_result["success"] == True
        
        # 验证所有 Skill 都是确定性实现
        assert review_result.get("metadata", {}).get("approach") == "rule_based"
        assert td_result.get("metadata", {}).get("approach") == "template_based"
        assert plan_result.get("metadata", {}).get("approach") == "rule_based"
        assert test_result.get("metadata", {}).get("approach") == "template_based"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
