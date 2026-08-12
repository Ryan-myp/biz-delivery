"""
Automated Testing Skill 实现
职责：根据测试用例执行自动化测试
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import SkillBase, SkillResult


class AutomatedTestingSkill(SkillBase):
    """自动化测试 Skill"""
    
    REQUIRED_INPUT = ["code_dir", "test_cases"]
    
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile)
    
    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行自动化测试"""
        # 验证输入
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)
        
        code_dir = input_data["code_dir"]
        test_cases = input_data.get("test_cases", [])
        profile = input_data.get("profile", self.profile)
        
        try:
            # 调用自动化引擎
            from scripts.automation import AutomationPipeline
            pipeline = AutomationPipeline(
                work_dir=code_dir,
                language=profile.get("language", "go"),
            )
            
            # 执行测试
            result = pipeline.execute()
            
            return SkillResult(
                success=result.get("validation", {}).get("passed", False),
                output={
                    "build": result.get("build", {}),
                    "unit_tests": result.get("unit_tests", {}),
                    "integration_tests": result.get("integration_tests", {}),
                    "coverage": result.get("coverage", {}),
                    "validation": result.get("validation", {}),
                },
                metadata={
                    "skill": "automated_testing",
                    "code_dir": code_dir,
                }
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"Automated testing failed: {str(e)}"]
            )
