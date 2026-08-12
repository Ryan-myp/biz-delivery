"""
Test Case Skill 实现
职责：根据 PRD 和技术方案生成测试用例
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import SkillBase, SkillResult


class TestCaseSkill(SkillBase):
    """测试用例生成 Skill"""
    
    REQUIRED_INPUT = ["prd_content"]
    
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile)
    
    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行测试用例生成"""
        # 验证输入
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)
        
        prd_content = input_data["prd_content"]
        profile = input_data.get("profile", self.profile)
        
        try:
            # 调用测试引擎
            from scripts.test_engine import TestEngine
            engine = TestEngine(profile=profile)
            
            # 生成测试用例
            result = engine.run(prd_content=prd_content)
            
            # 提取测试用例
            test_cases = []
            if hasattr(result, 'test_cases'):
                test_cases = result.test_cases
            elif isinstance(result, dict):
                test_cases = result.get('test_cases', [])
            
            # 分类
            p0_cases = [c for c in test_cases if c.get('priority') == 'P0']
            p1_cases = [c for c in test_cases if c.get('priority') == 'P1']
            p2_cases = [c for c in test_cases if c.get('priority') == 'P2']
            
            return SkillResult(
                success=True,
                output={
                    "test_cases": test_cases,
                    "total_cases": len(test_cases),
                    "p0_count": len(p0_cases),
                    "p1_count": len(p1_cases),
                    "p2_count": len(p2_cases),
                    "coverage_analysis": result.coverage_analysis if hasattr(result, 'coverage_analysis') else {},
                },
                metadata={
                    "skill": "test_case_generation",
                    "dimensions": self._get_dimensions(),
                }
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"Test case generation failed: {str(e)}"]
            )
    
    def _get_dimensions(self) -> List[str]:
        """获取测试维度"""
        return self.profile.get("test_dimensions", ["unit", "integration", "e2e"])
