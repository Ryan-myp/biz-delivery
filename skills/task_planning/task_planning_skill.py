"""
Task Planning Skill 实现
职责：将技术方案分解为可执行的 Agent 任务
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import SkillBase, SkillResult


class TaskPlanningSkill(SkillBase):
    """任务规划 Skill - 生成执行计划"""
    
    REQUIRED_INPUT = ["td_content"]
    
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile)
    
    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行任务规划"""
        # 验证输入
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)
        
        td_content = input_data["td_content"]
        profile = input_data.get("profile", self.profile)
        
        try:
            # 调用任务分解器
            from scripts.agent.prompt_generator import TaskDecomposer
            decomposer = TaskDecomposer(profile=profile)
            
            # 分解任务
            tasks = decomposer.decompose(
                requirement=td_content,
                td_content=td_content
            )
            
            # 格式化任务
            formatted_tasks = []
            for i, task in enumerate(tasks):
                formatted_tasks.append({
                    "id": task.get("id", f"T{i+1}"),
                    "title": task.get("title", task.get("name", f"Task {i+1}")),
                    "description": task.get("description", ""),
                    "priority": task.get("priority", "P1"),
                    "depends_on": task.get("depends_on", []),
                    "files_to_create": task.get("files_to_create", []),
                    "files_to_modify": task.get("files_to_modify", []),
                })
            
            # 排序（P0 优先）
            priority_order = {"P0": 0, "P1": 1, "P2": 2}
            formatted_tasks.sort(key=lambda t: priority_order.get(t["priority"], 9))
            
            return SkillResult(
                success=True,
                output={
                    "tasks": formatted_tasks,
                    "total_tasks": len(formatted_tasks),
                    "p0_count": sum(1 for t in formatted_tasks if t["priority"] == "P0"),
                    "p1_count": sum(1 for t in formatted_tasks if t["priority"] == "P1"),
                    "execution_order": [t["id"] for t in formatted_tasks],
                },
                metadata={
                    "skill": "task_planning",
                    "decomposer": "TaskDecomposer",
                }
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"Task planning failed: {str(e)}"]
            )
