"""
综合测试套件 - 测试所有 Skill 的边界条件和异常场景
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.prd_review.review_skill import PRDReviewSkill
from skills.technical_design.td_skill import TDSkill
from skills.task_planning.task_planning_skill import TaskPlanningSkill
from skills.test_case.test_case_skill import TestCaseSkill


class TestPRDReviewSkillEdgeCases:
    """PRD Review Skill 边界条件测试"""
    
    def test_empty_prd(self):
        """空 PRD 应返回所有规则未通过"""
        skill = PRDReviewSkill()
        result = skill.run({"prd_content": ""})
        
        assert result.success == False
        assert result.output["total_issues"] > 0
    
    def test_valid_full_prd(self):
        """完整的 PRD 应通过大部分规则"""
        prd = """# 用户中心重构

## 需求描述
- 重构用户中心服务
- 提升并发能力

## 业务目标
提高系统性能

## 时间规划
- Phase 1: 2周
- Phase 2: 2周

## 依赖说明
- 依赖网关服务

## 风险评估
- 高风险：数据迁移

## 成功指标
- QPS > 1000
- P99 < 100ms

## 监控方案
- 接入监控平台

## 安全考虑
- OAuth2 认证

## 性能要求
- 响应时间 < 200ms
"""
        skill = PRDReviewSkill()
        result = skill.run({"prd_content": prd})
        
        # 主要关注点：没有 P0 问题
        assert result.output["p0_issues"] == 0
    
    def test_vague_requirements(self):
        """模糊需求应被检测"""
        prd = """
# 系统优化

## 需求描述
- 尽快完成重构
- 大概需要一个月
- 性能应该会更好
"""
        skill = PRDReviewSkill()
        result = skill.run({"prd_content": prd})
        
        assert result.success == False
        vague_issues = [i for i in result.output["issues"] if i["type"] == "vague"]
        assert len(vague_issues) > 0
    
    def test_special_characters(self):
        """包含特殊字符的 PRD 应正确处理"""
        prd = "# 测试\\n## 需求\\n- 支持 emoji: 🎉\\n- 特殊符号: $%&"
        skill = PRDReviewSkill()
        result = skill.run({"prd_content": prd})
        
        assert result.success == False  # 缺少需求描述章节


class TestTDSkillEdgeCases:
    """TD Skill 边界条件测试"""
    
    def test_prd_with_special_chars(self):
        """包含特殊字符的 PRD 应正确处理"""
        prd = "# 测试\\n## 需求\\n- 支持 emoji: 🎉\\n- 特殊符号: $%&"
        skill = TDSkill()
        result = skill.run({"prd_content": prd})
        
        assert result.success == True
        assert "td_content" in result.output
    
    def test_multiline_description(self):
        """多行描述应正确提取"""
        prd = """
# 系统重构

## 需求描述
这是一个复杂的需求：
1. 第一步
2. 第二步
3. 第三步
"""
        skill = TDSkill()
        result = skill.run({"prd_content": prd})
        
        assert result.success == True
    
    def test_empty_prd(self):
        """空 PRD 应返回默认技术方案"""
        skill = TDSkill()
        result = skill.run({"prd_content": ""})
        
        assert result.success == True
        assert "td_content" in result.output
    
    def test_large_prd(self):
        """大型 PRD 应正常处理"""
        prd = "# 大型系统\\n" + "\\n".join([f"## 需求{i}\\n- 需求描述{i}" for i in range(10)])
        skill = TDSkill()
        result = skill.run({"prd_content": prd})
        
        assert result.success == True
        assert len(result.output["td_content"]) > 100


class TestTaskPlanningSkill:
    """Task Planning Skill 测试"""
    
    def test_task_priority_ordering(self):
        """任务应按优先级排序"""
        td = """
## 后端任务
- 用户认证模块（涉及鉴权）
- 数据导出功能
- API 接口开发
"""
        skill = TaskPlanningSkill()
        result = skill.run({"td_content": td})
        
        tasks = result.output["tasks"]
        assert len(tasks) > 0
        # P0 任务应该在前
        p0_tasks = [t for t in tasks if t["priority"] == "P0"]
        assert len(p0_tasks) > 0
    
    def test_empty_td(self):
        """空 TD 应返回默认任务"""
        skill = TaskPlanningSkill()
        result = skill.run({"td_content": ""})
        
        assert result.success == True
        assert len(result.output["tasks"]) > 0
    
    def test_complex_dependencies(self):
        """复杂依赖关系应正确解析"""
        td = """
## 任务列表
- [P0] 数据库迁移（依赖：数据备份）
- [P1] API 开发（依赖：数据库迁移）
- [P0] 认证服务（无依赖）
"""
        skill = TaskPlanningSkill()
        result = skill.run({"td_content": td})
        
        tasks = result.output["tasks"]
        assert len(tasks) >= 3


class TestTestCaseSkill:
    """Test Case Skill 测试"""
    
    def test_positive_cases_only(self):
        """正向用例生成"""
        prd = "# 用户登录\\n## 需求\\n用户可通过手机号登录"
        skill = TestCaseSkill()
        result = skill.run({"prd_content": prd})
        
        cases = result.output["test_cases"]
        positive = [c for c in cases if c["type"] == "positive"]
        assert len(positive) > 0
    
    def test_negative_cases(self):
        """异常用例生成"""
        prd = "# 用户注册\\n## 需求\\n用户填写表单注册"
        skill = TestCaseSkill()
        result = skill.run({"prd_content": prd})
        
        cases = result.output["test_cases"]
        negative = [c for c in cases if c["type"] == "negative"]
        assert len(negative) > 0
    
    def test_boundary_cases(self):
        """边界用例生成"""
        prd = "# 输入验证\\n## 需求\\n用户名长度 4-20 字符"
        skill = TestCaseSkill()
        result = skill.run({"prd_content": prd})
        
        cases = result.output["test_cases"]
        boundary = [c for c in cases if c["type"] == "boundary"]
        assert len(boundary) > 0
    
    def test_empty_prd(self):
        """空 PRD 应返回基础测试用例"""
        skill = TestCaseSkill()
        result = skill.run({"prd_content": ""})
        
        assert result.success == True
        assert len(result.output["test_cases"]) > 0


class TestSkillIntegration:
    """Skill 集成测试"""
    
    def test_full_pipeline(self):
        """完整流水线测试"""
        prd = """# 订单系统重构

## 需求描述
重构订单系统，支持高并发

## 业务目标
提升系统性能

## 时间规划
- Phase 1: 2周

## 依赖说明
- 依赖网关

## 风险评估
- 中等风险

## 成功指标
- QPS > 1000
"""
        review_skill = PRDReviewSkill()
        review_result = review_skill.run({"prd_content": prd})
        
        td_skill = TDSkill()
        td_result = td_skill.run({"prd_content": prd})
        
        task_skill = TaskPlanningSkill()
        task_result = task_skill.run({"td_content": td_result.output["td_content"]})
        
        test_skill = TestCaseSkill()
        test_result = test_skill.run({"prd_content": prd})
        
        # 验证所有 Skill 都成功执行
        assert review_result.success or review_result.output["p0_issues"] == 0
        assert td_result.success
        assert task_result.success
        assert test_result.success
