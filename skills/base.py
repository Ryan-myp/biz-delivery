"""
Skill 基类定义
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path


@dataclass
class SkillResult:
    """Skill 执行结果"""
    success: bool
    output: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "errors": self.errors,
            "metadata": self.metadata,
        }


class SkillBase(ABC):
    """所有 Skill 的基类"""
    
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        self.profile = profile or {}
        self.skill_name = self.__class__.__name__
    
    @abstractmethod
    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行 Skill"""
        pass
    
    def validate_input(self, input_data: Dict[str, Any]) -> List[str]:
        """验证输入数据"""
        errors = []
        
        # 检查必要的输入
        required_fields = getattr(self, "REQUIRED_INPUT", [])
        for field in required_fields:
            if field not in input_data:
                errors.append(f"Missing required field: {field}")
        
        return errors
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self.profile.get(key, default)
