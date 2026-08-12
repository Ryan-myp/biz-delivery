"""
Technical Design Skill 实现
职责：根据 PRD 生成技术方案
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import SkillBase, SkillResult


class TDSkill(SkillBase):
    """技术方案生成 Skill"""
    
    REQUIRED_INPUT = ["prd_content"]
    
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile)
    
    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行技术方案生成"""
        # 验证输入
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)
        
        prd_content = input_data["prd_content"]
        profile = input_data.get("profile", self.profile)
        
        try:
            # 调用 TD 引擎
            from scripts.td_engine import TDEngine
            engine = TDEngine(profile=profile)
            
            # 生成技术方案
            result = engine.run(prd_content=prd_content)
            
            # 提取 TD 内容
            td_content = ""
            if hasattr(result, 'td_content'):
                td_content = result.td_content
            elif isinstance(result, dict):
                td_content = result.get('td_content', '')
            
            return SkillResult(
                success=True,
                output={
                    "td_content": td_content,
                    "sections": self._extract_sections(td_content),
                },
                metadata={
                    "skill": "technical_design",
                    "template": "td.md.j2",
                }
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"TD generation failed: {str(e)}"]
            )
    
    def _extract_sections(self, td_content: str) -> List[str]:
        """提取章节"""
        sections = []
        for line in td_content.split('\n'):
            if line.startswith('## '):
                sections.append(line.strip())
        return sections
