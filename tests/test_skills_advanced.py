"""
高级 Skill 测试套件
覆盖：SkillOrchestrator 完整流水线、AgentExecutionSkill、AutomatedTestingSkill、SkillBase
目标：skills/ 覆盖率 ≥90%
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.base import SkillBase, SkillResult


# ============================================================
# SkillBase 深度测试
# ============================================================

class TestSkillBaseDeep:
    """Skill 基类深度测试"""
    
    class _ConcreteSkill(SkillBase):
        """测试用具体 Skill"""
        def run(self, input_data):
            return SkillResult(success=True)
    
    def _make_skill(self, profile=None):
        return self._ConcreteSkill(profile=profile)
    
    def test_skill_result_defaults(self):
        """测试 SkillResult 默认值"""
        result = SkillResult(success=True)
        assert result.output == {}
        assert result.errors == []
        assert result.metadata == {}
    
    def test_skill_result_to_dict(self):
        """测试 to_dict 序列化"""
        result = SkillResult(
            success=True,
            output={"a": 1},
            errors=["e1"],
            metadata={"m": 2}
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["output"] == {"a": 1}
        assert d["errors"] == ["e1"]
        assert d["metadata"] == {"m": 2}
    
    def test_get_config_with_default(self):
        """测试 get_config 返回默认值"""
        skill = self._make_skill({"language": "go"})
        assert skill.get_config("language") == "go"
        assert skill.get_config("missing", "fallback") == "fallback"
        assert skill.get_config("missing") is None
    
    def test_get_config_empty_profile(self):
        """测试空 profile"""
        skill = self._make_skill({})
        assert skill.get_config("language") is None
        assert skill.get_config("language", "python") == "python"
    
    def test_get_config_none_profile(self):
        """测试 profile 为 None"""
        skill = self._make_skill(None)
        assert skill.profile == {}
        assert skill.get_config("anything", 42) == 42
    
    def test_validate_input_empty_required(self):
        """测试无必填字段时验证通过"""
        skill = self._make_skill()
        errors = skill.validate_input({"a": 1})
        assert errors == []
    
    def test_validate_input_with_required(self):
        """测试有必填字段时"""
        class TestSkill(SkillBase):
            REQUIRED_INPUT = ["name", "content"]
            def run(self, input_data):
                return SkillResult(success=True)
        
        skill = TestSkill(profile={})
        
        # 缺少字段
        errors = skill.validate_input({"name": "x"})
        assert "Missing required field: content" in errors
        
        # 全部提供
        errors = skill.validate_input({"name": "x", "content": "y"})
        assert errors == []
    
    def test_skill_name_default(self):
        """测试 skill_name 默认值"""
        class MySkill(SkillBase):
            def run(self, input_data):
                return SkillResult(success=True)
        skill = MySkill(profile={})
        assert skill.skill_name == "MySkill"
    
    def test_run_abstract(self):
        """测试抽象方法不可直接调用"""
        with pytest.raises(TypeError):
            SkillBase(profile={})


# ============================================================
# AgentExecutionSkill 深度测试
# ============================================================

class TestAgentExecutionSkill:
    """Agent 执行 Skill 测试"""
    
    def _make_tasks(self):
        return [
            {"id": "T1", "description": "实现登录接口"},
            {"id": "T2", "description": "实现注册接口"},
        ]
    
    def test_run_missing_input(self):
        """测试缺少必填输入"""
        from skills.agent_execution import AgentExecutionSkill
        skill = AgentExecutionSkill(profile={})
        result = skill.run({})
        assert result.success is False
        assert len(result.errors) > 0
    
    def test_run_missing_tasks(self):
        """测试缺少 tasks"""
        from skills.agent_execution import AgentExecutionSkill
        skill = AgentExecutionSkill(profile={})
        result = skill.run({"code_context": "context"})
        assert result.success is False
        assert any("tasks" in e for e in result.errors)
    
    def test_run_success(self):
        """测试成功执行"""
        from skills.agent_execution import AgentExecutionSkill
        
        with patch("scripts.agent.prompt_generator.AgentPromptGenerator") as MockGen:
            mock_gen = MagicMock()
            mock_gen.generate_task_prompt.return_value = "生成的任务提示词"
            MockGen.return_value = mock_gen
            
            skill = AgentExecutionSkill(profile={"language": "python"})
            tasks = self._make_tasks()
            
            result = skill.run({
                "tasks": tasks,
                "code_context": "用户登录系统",
                "profile": {"language": "python"},
            })
            
            assert result.success is True
            assert result.output["total_tasks"] == 2
            assert result.output["completed_tasks"] == 0
            assert len(result.output["results"]) == 2
            assert result.output["results"][0]["task_id"] == "T1"
            assert result.output["results"][0]["status"] == "pending_llm"
            assert result.output["results"][0]["code_generated"] is False
            assert "提示词" in result.output["results"][0]["prompt"]
    
    def test_run_single_task(self):
        """测试单个任务"""
        from skills.agent_execution import AgentExecutionSkill
        
        with patch("scripts.agent.prompt_generator.AgentPromptGenerator"):
            skill = AgentExecutionSkill(profile={})
            result = skill.run({
                "tasks": [{"id": "T1", "description": "任务1"}],
                "code_context": "",
            })
            assert result.success is True
            assert result.output["total_tasks"] == 1
    
    def test_run_exception_handling(self):
        """测试异常处理"""
        from skills.agent_execution import AgentExecutionSkill
        
        with patch("scripts.agent.prompt_generator.AgentPromptGenerator",
                   side_effect=RuntimeError("LLM 不可用")):
            skill = AgentExecutionSkill(profile={})
            result = skill.run({
                "tasks": [{"id": "T1"}],
                "code_context": "",
            })
            assert result.success is False
            assert any("failed" in e.lower() for e in result.errors)
    
    def test_run_empty_tasks(self):
        """测试空任务列表"""
        from skills.agent_execution import AgentExecutionSkill
        skill = AgentExecutionSkill(profile={})
        result = skill.run({
            "tasks": [],
            "code_context": "",
        })
        assert result.success is True
        assert result.output["total_tasks"] == 0


# ============================================================
# AutomatedTestingSkill 深度测试
# ============================================================

class TestAutomatedTestingSkill:
    """自动化测试 Skill 测试"""
    
    def test_run_missing_input(self):
        """测试缺少必填输入"""
        from skills.automated_testing import AutomatedTestingSkill
        skill = AutomatedTestingSkill(profile={})
        result = skill.run({})
        assert result.success is False
        assert len(result.errors) > 0
    
    def test_run_missing_code_dir(self):
        """测试缺少 code_dir"""
        from skills.automated_testing import AutomatedTestingSkill
        skill = AutomatedTestingSkill(profile={})
        result = skill.run({"test_cases": []})
        assert result.success is False
        assert any("code_dir" in e for e in result.errors)
    
    def test_run_success_passing(self):
        """测试成功通过"""
        from skills.automated_testing import AutomatedTestingSkill
        
        mock_result = {
            "build": {"success": True},
            "unit_tests": {"passed": 10, "total": 10},
            "integration_tests": {"passed": 5, "total": 5},
            "coverage": {"percent": 85},
            "validation": {"passed": True},
        }
        
        with patch("scripts.automation.AutomationPipeline") as MockPipeline:
            mock_pipeline = MagicMock()
            mock_pipeline.execute.return_value = mock_result
            MockPipeline.return_value = mock_pipeline
            
            skill = AutomatedTestingSkill(profile={"language": "go"})
            result = skill.run({
                "code_dir": "/tmp/test-code",
                "test_cases": [{"name": "TC1"}],
                "profile": {"language": "go"},
            })
            
            assert result.success is True
            assert result.output["build"]["success"] is True
            assert result.output["coverage"]["percent"] == 85
            assert result.output["validation"]["passed"] is True
    
    def test_run_success_failing(self):
        """测试失败结果"""
        from skills.automated_testing import AutomatedTestingSkill
        
        mock_result = {
            "build": {"success": False, "error": "编译失败"},
            "unit_tests": {"passed": 0, "total": 3},
            "integration_tests": {"passed": 0, "total": 0},
            "coverage": {"percent": 0},
            "validation": {"passed": False},
        }
        
        with patch("scripts.automation.AutomationPipeline") as MockPipeline:
            mock_pipeline = MagicMock()
            mock_pipeline.execute.return_value = mock_result
            MockPipeline.return_value = mock_pipeline
            
            skill = AutomatedTestingSkill(profile={})
            result = skill.run({
                "code_dir": "/tmp/bad-code",
                "test_cases": [],
            })
            
            assert result.success is False
            assert result.output["build"]["success"] is False
    
    def test_run_default_language(self):
        """测试默认语言 go"""
        from skills.automated_testing import AutomatedTestingSkill
        
        with patch("scripts.automation.AutomationPipeline") as MockPipeline:
            mock_pipeline = MagicMock()
            mock_pipeline.execute.return_value = {"validation": {"passed": True}}
            MockPipeline.return_value = mock_pipeline
            
            skill = AutomatedTestingSkill(profile={})
            result = skill.run({
                "code_dir": "/tmp/test",
                "test_cases": [],
            })
            
            # 验证默认语言是 go
            call_kwargs = MockPipeline.call_args.kwargs
            assert call_kwargs.get("language") == "go"
    
    def test_run_exception_handling(self):
        """测试异常处理"""
        from skills.automated_testing import AutomatedTestingSkill
        
        with patch("scripts.automation.AutomationPipeline",
                   side_effect=RuntimeError("测试环境不可用")):
            skill = AutomatedTestingSkill(profile={})
            result = skill.run({
                "code_dir": "/tmp/test",
                "test_cases": [],
            })
            assert result.success is False
            assert any("failed" in e.lower() for e in result.errors)


# ============================================================
# SkillOrchestrator 深度测试
# ============================================================

class TestSkillOrchestratorDeep:
    """编排器深度测试"""
    
    def _make_orchestrator(self):
        """创建完整的编排器"""
        from skills import (
            SkillOrchestrator, PRDReviewSkill, TDSkill,
            TaskPlanningSkill, TestCaseSkill,
        )
        from skills.agent_execution import AgentExecutionSkill
        from skills.automated_testing import AutomatedTestingSkill
        
        orchestrator = SkillOrchestrator(profile={"language": "python"})
        orchestrator.register("prd_review", PRDReviewSkill())
        orchestrator.register("td", TDSkill())
        orchestrator.register("task_planning", TaskPlanningSkill())
        orchestrator.register("agent_execution", AgentExecutionSkill())
        orchestrator.register("test_case", TestCaseSkill())
        orchestrator.register("automated_testing", AutomatedTestingSkill())
        return orchestrator
    
    def _write_prd(self, tmp_path, content=None):
        """写入 PRD 文件"""
        default_prd = """# 用户登录功能

## 需求描述
用户可以使用邮箱和密码登录系统

## 业务目标
提升用户体验，降低流失率

## 时间规划
- Phase 1: 2周
- Phase 2: 1周

## 依赖说明
- 依赖用户中心服务
- 依赖短信服务

## 风险评估
- 中等风险：数据迁移

## 成功指标
- 登录成功率 > 99%
- 响应时间 < 500ms

## 监控方案
- 接入监控系统

## 安全考虑
- OAuth2 认证
- 密码加密存储

## 接口设计
- POST /api/login

## 数据模型
- User { id, email, password }

## 性能要求
- QPS > 1000
"""
        prd_file = tmp_path / "prd.md"
        prd_file.write_text(content or default_prd, encoding="utf-8")
        return str(prd_file)
    
    def test_run_pipeline_full(self, tmp_path):
        """测试完整流水线"""
        orchestrator = self._make_orchestrator()
        prd_path = self._write_prd(tmp_path)
        
        result = orchestrator.run_pipeline(prd_path, mode="full")
        
        assert result["success"] is True
        assert "review" in result["stages"]
        assert "td" in result["stages"]
        assert "planning" in result["stages"]
        assert "test_case" in result["stages"]
        assert "agent" in result["stages"]
        assert "automated_testing" in result["stages"]
        assert len(result["stages"]) == 6  # full 包含全部阶段
    
    def test_run_pipeline_review_mode(self, tmp_path):
        """测试仅 review 模式"""
        orchestrator = self._make_orchestrator()
        prd_path = self._write_prd(tmp_path)
        
        result = orchestrator.run_pipeline(prd_path, mode="review")
        
        assert result["mode"] == "review"
        assert "review" in result["stages"]
        assert "td" not in result["stages"]
        assert result["stages"]["review"]["success"] is True
    
    def test_run_pipeline_td_mode(self, tmp_path):
        """测试仅 td 模式"""
        orchestrator = self._make_orchestrator()
        prd_path = self._write_prd(tmp_path)
        
        result = orchestrator.run_pipeline(prd_path, mode="td")
        
        assert "review" not in result["stages"]
        assert "td" in result["stages"]
        assert result["stages"]["td"]["success"] is True
    
    def test_run_pipeline_plan_mode(self, tmp_path):
        """测试 plan 模式"""
        orchestrator = self._make_orchestrator()
        prd_path = self._write_prd(tmp_path)
        
        result = orchestrator.run_pipeline(prd_path, mode="plan")
        
        assert "planning" in result["stages"]
        assert result["stages"]["planning"]["success"] is True
    
    def test_run_pipeline_test_mode(self, tmp_path):
        """测试 test 模式"""
        orchestrator = self._make_orchestrator()
        prd_path = self._write_prd(tmp_path)
        
        result = orchestrator.run_pipeline(prd_path, mode="test")
        
        assert "test_case" in result["stages"]
        assert result["stages"]["test_case"]["success"] is True
    
    def test_run_pipeline_review_failure_blocks(self, tmp_path):
        """测试 review 失败阻断流水线"""
        orchestrator = self._make_orchestrator()
        prd_path = self._write_prd(tmp_path, content="# 没有目标的 PRD\n\n## 需求\n随便写点\n")
        
        result = orchestrator.run_pipeline(prd_path, mode="full")
        
        assert result["blocked"] is True
        assert result["block_reason"] == "PRD review failed"
        assert "review" in result["stages"]
        assert "td" not in result["stages"]
    
    def test_run_pipeline_missing_file(self, tmp_path):
        """测试 PRD 文件不存在"""
        orchestrator = self._make_orchestrator()
        
        with pytest.raises(FileNotFoundError):
            orchestrator.run_pipeline(str(tmp_path / "nonexist.md"), mode="full")
    
    def test_run_skill_not_found(self):
        """测试未注册的 Skill"""
        orchestrator = self._make_orchestrator()
        result = orchestrator._run_skill("unknown_skill", {})
        assert result["success"] is False
        assert "not found" in result["error"]
    
    def test_run_skill_records_history(self, tmp_path):
        """测试历史记录"""
        orchestrator = self._make_orchestrator()
        prd_path = self._write_prd(tmp_path)
        
        orchestrator.run_pipeline(prd_path, mode="review")
        
        assert len(orchestrator.history) >= 1
        assert orchestrator.history[0]["skill"] == "prd_review"
        assert orchestrator.history[0]["success"] is True
        assert "timestamp" in orchestrator.history[0]
    
    def test_register_duplicate_overwrites(self):
        """测试重复注册覆盖"""
        from skills import SkillOrchestrator
        orchestrator = SkillOrchestrator(profile={})
        
        class FakeSkill(SkillBase):
            def run(self, input_data):
                return SkillResult(success=True)
        
        orchestrator.register("fake", FakeSkill())
        orchestrator.register("fake", FakeSkill())
        
        assert len(orchestrator.skills) == 1
    
    def test_history_empty_initially(self):
        """测试初始历史为空"""
        from skills import SkillOrchestrator
        orchestrator = SkillOrchestrator(profile={})
        assert orchestrator.history == []
        assert orchestrator.skills == {}
    
    def test_run_pipeline_agent_mode(self, tmp_path):
        """测试 agent 模式"""
        from skills import SkillOrchestrator, PRDReviewSkill, TDSkill, TaskPlanningSkill
        from skills.agent_execution import AgentExecutionSkill
        
        orchestrator = SkillOrchestrator(profile={})
        orchestrator.register("prd_review", PRDReviewSkill())
        orchestrator.register("td", TDSkill())
        orchestrator.register("task_planning", TaskPlanningSkill())
        orchestrator.register("agent_execution", AgentExecutionSkill())
        
        prd_path = self._write_prd(tmp_path)
        
        with patch("scripts.agent.prompt_generator.AgentPromptGenerator"):
            result = orchestrator.run_pipeline(prd_path, mode="agent")
            assert "agent" in result["stages"]
    
    def test_run_pipeline_auto_test_mode(self, tmp_path):
        """测试 auto_test 模式"""
        from skills import SkillOrchestrator, PRDReviewSkill, TDSkill, TaskPlanningSkill, TestCaseSkill
        from skills.automated_testing import AutomatedTestingSkill
        
        orchestrator = SkillOrchestrator(profile={})
        orchestrator.register("prd_review", PRDReviewSkill())
        orchestrator.register("td", TDSkill())
        orchestrator.register("task_planning", TaskPlanningSkill())
        orchestrator.register("test_case", TestCaseSkill())
        orchestrator.register("automated_testing", AutomatedTestingSkill())
        
        prd_path = self._write_prd(tmp_path)
        
        with patch("scripts.automation.AutomationPipeline") as MockPipeline:
            mock_pipeline = MagicMock()
            mock_pipeline.execute.return_value = {"validation": {"passed": True}}
            MockPipeline.return_value = mock_pipeline
            
            result = orchestrator.run_pipeline(prd_path, mode="auto_test")
            assert "automated_testing" in result["stages"]
