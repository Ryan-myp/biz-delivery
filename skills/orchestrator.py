"""
Skill 编排器
职责：协调多个 Skill 的执行，形成完整的研发流程
"""

from typing import Any, Dict, List, Optional
from .base import SkillBase, SkillResult


class SkillOrchestrator:
    """Skill 编排器"""
    
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        self.profile = profile or {}
        self.skills: Dict[str, SkillBase] = {}
        self.history: List[Dict[str, Any]] = []
    
    def register(self, name: str, skill: SkillBase):
        """注册 Skill"""
        self.skills[name] = skill
    
    def run_pipeline(self, prd_path: str, mode: str = "full") -> Dict[str, Any]:
        """运行完整流水线"""
        # 读取 PRD
        with open(prd_path, 'r', encoding='utf-8') as f:
            prd_content = f.read()
        
        result = {
            "prd_path": prd_path,
            "mode": mode,
            "stages": {},
        }
        
        # 1. PRD Review
        if mode in ["full", "review"]:
            review_result = self._run_skill("prd_review", {
                "prd_content": prd_content,
                "profile": self.profile,
            })
            result["stages"]["review"] = review_result
            if not review_result["success"]:
                result["blocked"] = True
                result["block_reason"] = "PRD review failed"
                return result
        
        # 2. Technical Design
        if mode in ["full", "td"]:
            td_result = self._run_skill("td", {
                "prd_content": prd_content,
                "profile": self.profile,
            })
            result["stages"]["td"] = td_result
        
        # 3. Task Planning
        if mode in ["full", "plan"]:
            td_content = td_result.get("output", {}).get("td_content", "")
            plan_result = self._run_skill("task_planning", {
                "td_content": td_content,
                "profile": self.profile,
            })
            result["stages"]["planning"] = plan_result
        
        # 4. Agent Execution
        if mode in ["full", "agent"]:
            tasks = plan_result.get("output", {}).get("tasks", [])
            agent_result = self._run_skill("agent_execution", {
                "tasks": tasks,
                "code_context": prd_content,
                "profile": self.profile,
            })
            result["stages"]["agent"] = agent_result
        
        # 5. Test Case Generation
        if mode in ["full", "test"]:
            test_result = self._run_skill("test_case", {
                "prd_content": prd_content,
                "profile": self.profile,
            })
            result["stages"]["test_case"] = test_result
        
        # 6. Automated Testing
        if mode in ["full", "auto_test"]:
            code_dir = agent_result.get("output", {}).get("code_dir", ".")
            test_cases = test_result.get("output", {}).get("test_cases", [])
            auto_test_result = self._run_skill("automated_testing", {
                "code_dir": code_dir,
                "test_cases": test_cases,
                "profile": self.profile,
            })
            result["stages"]["automated_testing"] = auto_test_result
        
        result["success"] = all(
            s.get("success", False) for s in result["stages"].values()
        )
        
        return result
    
    def _run_skill(self, name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """运行单个 Skill"""
        skill = self.skills.get(name)
        if not skill:
            return {"success": False, "error": f"Skill {name} not found"}
        
        result = skill.run(input_data)
        
        # 记录历史
        self.history.append({
            "skill": name,
            "success": result.success,
            "timestamp": str(__import__('datetime').datetime.now()),
        })
        
        return result.to_dict()
