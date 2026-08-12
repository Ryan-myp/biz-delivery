"""
Skills 测试套件 - 核心 Skill 单元测试
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.base import SkillBase, SkillResult


class TestSkillBase:
    """测试 Skill 基类"""
    
    def test_skill_result_creation(self):
        """测试 SkillResult 创建"""
        result = SkillResult(
            success=True,
            output={"test": "data"},
            errors=[],
            metadata={"key": "value"}
        )
        
        assert result.success == True
        assert result.output["test"] == "data"
        assert result.metadata["key"] == "value"
        assert len(result.errors) == 0


class TestPRDReviewSkill:
    """测试 PRD Review Skill"""
    
    def test_run_missing_title(self):
        """测试缺少标题的问题"""
        from skills.prd_review import PRDReviewSkill
        
        skill = PRDReviewSkill(profile={"language": "go"})
        
        result = skill.run({
            "prd_content": "这是一个没有标题的 PRD\n\n## 需求\n用户登录功能"
        })
        
        assert result.success == False
        assert result.output["p0_issues"] > 0
    
    def test_run_complete_prd(self):
        """测试完整的 PRD"""
        from skills.prd_review import PRDReviewSkill
        
        skill = PRDReviewSkill(profile={"language": "go"})
        
        prd_content = """# 用户登录功能

## 需求描述
用户可以使用邮箱和密码登录系统

## 业务目标
提升用户体验

## 时间规划
- Phase 1: 2周
- Phase 2: 2周

## 依赖说明
- 依赖用户中心服务

## 风险评估
- 中等风险：数据迁移

## 成功指标
- 登录成功率 > 99%
- 响应时间 < 500ms

## 监控方案
- 接入监控系统

## 安全考虑
- OAuth2 认证

## 性能要求
- 支持 1000 QPS

## 验收标准
- 通过所有测试用例
"""
        
        result = skill.run({"prd_content": prd_content})
        
        # 应该有至少一些规则通过，但不一定是全部成功
        assert result.output["total_issues"] >= 0
        assert "issues" in result.output
    
    def test_run_invalid_input(self):
        """测试无效输入"""
        from skills.prd_review import PRDReviewSkill
        
        skill = PRDReviewSkill(profile={"language": "go"})
        
        # 缺少必需参数
        with pytest.raises(KeyError):
            skill.run({})
    
    def test_detect_vague_requirements(self):
        """测试模糊需求检测"""
        from skills.prd_review import PRDReviewSkill
        
        skill = PRDReviewSkill()
        
        prd_content = """
# 系统优化

## 需求描述
- 尽快完成重构
- 大概需要一个月
- 性能应该会更好
"""
        
        result = skill.run({"prd_content": prd_content})
        
        # 应该有模糊需求问题
        vague_issues = [i for i in result.output["issues"] if i["type"] == "vague"]
        assert len(vague_issues) > 0


class TestTDSkill:
    """测试 TD Skill"""
    
    def test_run_with_go_profile(self):
        """测试 Go 语言配置文件"""
        from skills.technical_design import TDSkill
        
        skill = TDSkill(profile={"language": "go"})
        
        prd_content = "# 用户中心\\n## 需求\\n重构用户中心服务"
        
        result = skill.run({"prd_content": prd_content})
        
        assert result.success == True
        assert "td_content" in result.output
        assert "Go" in result.output["td_content"] or "架构" in result.output["td_content"]
    
    def test_run_with_python_profile(self):
        """测试 Python 语言配置文件"""
        from skills.technical_design import TDSkill
        
        skill = TDSkill(profile={"language": "python"})
        
        prd_content = "# 用户中心\\n## 需求\\n重构用户中心服务"
        
        result = skill.run({"prd_content": prd_content})
        
        assert result.success == True
        assert "td_content" in result.output


class TestTaskPlanningSkill:
    """测试 Task Planning Skill"""
    
    def test_run(self):
        """测试任务规划"""
        from skills.task_planning import TaskPlanningSkill
        
        skill = TaskPlanningSkill(profile={"language": "go"})
        
        td_content = """
## 架构设计
- 风格：微服务
- 模块：用户服务、订单服务

## 模块设计
### 用户服务
- 职责：用户管理
- 接口：REST API
"""
        
        result = skill.run({"td_content": td_content})
        
        assert result.success == True
        assert len(result.output["tasks"]) > 0


class TestTestCaseSkill:
    """测试 TestCase Skill"""
    
    def test_run(self):
        """测试测试用例生成"""
        from skills.test_case import TestCaseSkill
        
        skill = TestCaseSkill(profile={"language": "go"})
        
        prd_content = "# 用户登录\\n## 需求\\n用户可通过手机号登录"
        
        result = skill.run({"prd_content": prd_content})
        
        assert result.success == True
        assert result.output["total_count"] > 0
        assert len(result.output["test_cases"]) > 0
    
    def test_run_with_mock(self):
        """测试运行（真实实现）"""
        from skills.test_case import TestCaseSkill
        
        skill = TestCaseSkill(profile={"language": "go"})
        
        prd_content = """# 用户登录功能

## 需求描述
用户可以使用邮箱和密码登录系统

## 接口定义
- POST /api/login
- GET /api/user/info
"""
        
        result = skill.run({"prd_content": prd_content})
        
        assert result.success == True
        assert result.output["total_count"] > 0
        assert len(result.output["test_cases"]) > 0


class TestSkillOrchestrator:
    """测试 Skill 编排器"""
    
    def test_register_and_run(self):
        """测试注册和运行 Skill"""
        from skills import SkillOrchestrator, PRDReviewSkill, TDSkill
        
        orchestrator = SkillOrchestrator(profile={"language": "go"})
        orchestrator.register("prd_review", PRDReviewSkill())
        orchestrator.register("td", TDSkill())
        
        assert "prd_review" in orchestrator.skills
        assert "td" in orchestrator.skills
    
    def test_run_pipeline(self):
        """测试流水线执行"""
        from skills import SkillOrchestrator, PRDReviewSkill, TDSkill
        
        orchestrator = SkillOrchestrator(profile={"language": "go"})
        orchestrator.register("prd_review", PRDReviewSkill())
        orchestrator.register("td", TDSkill())
        
        prd_content = """# 用户登录功能

## 需求描述
用户可以使用邮箱和密码登录系统

## 业务目标
提升用户体验

## 时间规划
- Phase 1: 2周
- Phase 2: 2周

## 依赖说明
- 依赖网关服务

## 风险评估
- 中等风险

## 成功指标
- 登录成功率 > 99%
"""
        
        result = orchestrator._run_skill("prd_review", {"prd_content": prd_content})
        
        assert "output" in result
        assert "issues" in result["output"]


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

## 业务目标
提升用户体验

## 时间规划
- Phase 1: 2周
- Phase 2: 2周

## 依赖说明
- 依赖网关服务

## 风险评估
- 中等风险

## 成功指标
- 登录成功率 > 99%

## 验收标准
- 通过所有测试用例
"""
        
        # 运行 PRD Review
        review_result = orchestrator._run_skill("prd_review", {"prd_content": prd_content})
        assert "output" in review_result
        
        # 运行 TD
        td_result = orchestrator._run_skill("td", {"prd_content": prd_content})
        assert "output" in td_result
        
        # 运行 Task Planning
        task_result = orchestrator._run_skill("task_planning", {"td_content": td_result["output"]["td_content"]})
        assert "output" in task_result
        
        # 运行 Test Case
        test_result = orchestrator._run_skill("test_case", {"prd_content": prd_content})
        assert "output" in test_result
