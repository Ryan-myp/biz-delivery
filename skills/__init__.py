"""
biz-delivery 研发流程 Skill 系统

Skill 体系：
1. PRD Review Skill - 自主发现 PRD 问题
2. TD Skill - 根据 PRD 写技术方案
3. Task Planning Skill - 生成执行计划让 Agent 写代码
4. Agent Execution Skill - 执行任务计划，生成代码
5. Test Case Skill - 生成测试用例
6. Automated Testing Skill - 自动化测试
"""

from .base import SkillBase, SkillResult
from .prd_review import PRDReviewSkill
from .technical_design import TDSkill
from .task_planning import TaskPlanningSkill
from .agent_execution import AgentExecutionSkill
from .test_case import TestCaseSkill
from .automated_testing import AutomatedTestingSkill
from .orchestrator import SkillOrchestrator

__all__ = [
    "SkillBase",
    "SkillResult",
    "PRDReviewSkill",
    "TDSkill",
    "TaskPlanningSkill",
    "AgentExecutionSkill",
    "TestCaseSkill",
    "AutomatedTestingSkill",
    "SkillOrchestrator",
]
