"""
PRD Review Skill 实现
职责：自主发现 PRD 中的问题
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import SkillBase, SkillResult


class PRDReviewSkill(SkillBase):
    """PRD 审查 Skill - 自主发现 PRD 问题"""
    
    REQUIRED_INPUT = ["prd_content"]
    
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile)
    
    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行 PRD 审查"""
        # 验证输入
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)
        
        prd_content = input_data["prd_content"]
        profile = input_data.get("profile", self.profile)
        
        try:
            # 调用审查引擎
            from scripts.review_engine import ReviewEngine
            engine = ReviewEngine(profile=profile)
            
            # 执行审查
            result = engine.run(prd_content=prd_content)
            
            # 提取问题
            issues = []
            if hasattr(result, 'issues'):
                issues = result.issues
            elif isinstance(result, dict):
                issues = result.get('issues', [])
            
            # 分类问题
            p0_issues = [i for i in issues if i.get('priority') == 'P0']
            p1_issues = [i for i in issues if i.get('priority') == 'P1']
            p2_issues = [i for i in issues if i.get('priority') == 'P2']
            
            return SkillResult(
                success=len(p0_issues) == 0,  # 有 P0 问题则失败
                output={
                    "issues": issues,
                    "p0_count": len(p0_issues),
                    "p1_count": len(p1_issues),
                    "p2_count": len(p2_issues),
                    "total_issues": len(issues),
                    "risk_level": self._calculate_risk(p0_issues, p1_issues),
                },
                metadata={
                    "skill": "prd_review",
                    "total_checks": 17,
                }
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"PRD Review failed: {str(e)}"]
            )
    
    def _calculate_risk(self, p0_issues: List, p1_issues: List) -> str:
        """计算风险等级"""
        if len(p0_issues) > 0:
            return "high"
        elif len(p1_issues) > 3:
            return "medium"
        else:
            return "low"
