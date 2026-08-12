"""
Task Planning Skill 实现
职责：将技术方案分解为可执行的 Agent 任务

纯确定性实现，基于规则分解
"""

import re
from typing import Any, Dict, List, Optional
from ..base import SkillBase, SkillResult


class TaskPlanningSkill(SkillBase):
    """任务规划 Skill - 基于规则的任务分解"""
    
    REQUIRED_INPUT = ["td_content"]
    
    # 任务类型映射
    TASK_TYPES = {
        "auth": {"type": "infrastructure", "priority": "P0", "keywords": ["auth", "login", "token", "jwt", "oauth"]},
        "database": {"type": "infrastructure", "priority": "P0", "keywords": ["database", "db", "schema", "migration", "model"]},
        "api": {"type": "feature", "priority": "P1", "keywords": ["api", "handler", "controller", "route", "endpoint"]},
        "service": {"type": "feature", "priority": "P1", "keywords": ["service", "business", "logic", "core"]},
        "middleware": {"type": "infrastructure", "priority": "P1", "keywords": ["middleware", "interceptor", "plugin"]},
        "test": {"type": "test", "priority": "P2", "keywords": ["test", "spec", "case"]},
        "config": {"type": "infrastructure", "priority": "P2", "keywords": ["config", "setting", "environment"]},
    }
    
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile)
    
    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行任务规划"""
        # 验证输入
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)
        
        td_content = input_data["td_content"]
        
        try:
            # 解析 TD 内容
            td_info = self._parse_td(td_content)
            
            # 生成任务
            tasks = self._generate_tasks(td_info)
            
            # 排序（P0 优先）
            priority_order = {"P0": 0, "P1": 1, "P2": 2}
            tasks.sort(key=lambda t: priority_order.get(t["priority"], 9))
            
            return SkillResult(
                success=True,
                output={
                    "tasks": tasks,
                    "total_tasks": len(tasks),
                    "p0_count": sum(1 for t in tasks if t["priority"] == "P0"),
                    "p1_count": sum(1 for t in tasks if t["priority"] == "P1"),
                    "p2_count": sum(1 for t in tasks if t["priority"] == "P2"),
                    "execution_order": [t["id"] for t in tasks],
                    "dependencies": self._build_dependencies(tasks),
                },
                metadata={
                    "skill": "task_planning",
                    "approach": "rule_based",
                    "task_types": list(set(t["type"] for t in tasks)),
                }
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"Task planning failed: {str(e)}"]
            )
    
    def _parse_td(self, td_content: str) -> Dict[str, Any]:
        """解析 TD 内容"""
        info = {
            "title": "",
            "modules": [],
            "apis": [],
            "data_models": [],
            "infrastructure": [],
        }
        
        # 提取标题
        title_match = re.search(r"^#\s+(.+)", td_content, re.MULTILINE)
        if title_match:
            info["title"] = title_match.group(1).strip()
        
        # 提取模块
        modules = re.findall(r"###\s*(\w+)", td_content)
        info["modules"] = modules
        
        # 提取 API
        apis = re.findall(r"\|\s*(GET|POST|PUT|DELETE)\s+\S+\s+\|", td_content)
        info["apis"] = apis
        
        # 提取数据模型
        models = re.findall(r"###\s*(\w+)\s*(?:Entity|Model|Struct)?", td_content)
        info["data_models"] = models
        
        return info
    
    def _generate_tasks(self, td_info: Dict) -> List[Dict]:
        """生成任务列表"""
        tasks = []
        task_id = 1
        
        # 基础设施任务
        for task_type, config in self.TASK_TYPES.items():
            if task_type in ["auth", "database", "middleware", "config"]:
                tasks.append({
                    "id": f"T{task_id:03d}",
                    "title": f"{config['type'].title()} - {task_type.title()}",
                    "description": f"实现 {task_type} 相关基础设施",
                    "type": config["type"],
                    "priority": config["priority"],
                    "depends_on": [],
                    "files_to_create": [f"{task_type}.go"],
                    "files_to_modify": [],
                })
                task_id += 1
        
        # API 任务
        for api in td_info.get("apis", [])[:5]:
            tasks.append({
                "id": f"T{task_id:03d}",
                "title": f"API - {api}",
                "description": f"实现 {api} 接口",
                "type": "feature",
                "priority": "P1",
                "depends_on": ["T001"],  # 依赖基础设施
                "files_to_create": [f"handlers/{api.lower()}.go"],
                "files_to_modify": [],
            })
            task_id += 1
        
        # 业务逻辑任务
        for module in td_info.get("modules", [])[:3]:
            tasks.append({
                "id": f"T{task_id:03d}",
                "title": f"Service - {module}",
                "description": f"实现 {module} 业务逻辑",
                "type": "feature",
                "priority": "P1",
                "depends_on": ["T001", "T002"],  # 依赖基础设施和 API
                "files_to_create": [f"services/{module.lower()}.go"],
                "files_to_modify": [],
            })
            task_id += 1
        
        # 测试任务
        for task in tasks:
            if task["type"] == "feature":
                tasks.append({
                    "id": f"T{task_id:03d}",
                    "title": f"Test - {task['title']}",
                    "description": f"为 {task['title']} 编写测试",
                    "type": "test",
                    "priority": "P2",
                    "depends_on": [task["id"]],
                    "files_to_create": [f"{task['title'].lower()}_test.go"],
                    "files_to_modify": [],
                })
                task_id += 1
        
        return tasks
    
    def _build_dependencies(self, tasks: List[Dict]) -> Dict[str, List[str]]:
        """构建依赖关系"""
        deps = {}
        for task in tasks:
            deps[task["id"]] = task.get("depends_on", [])
        return deps
