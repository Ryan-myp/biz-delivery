"""
测试用例生成 Skill - 模板生成

基于 PRD 内容，自动生成正向、异常和边界测试用例。
"""

import re
from typing import Dict, Any, List
from ..base import SkillBase, SkillResult


class TestCaseSkill(SkillBase):
    """测试用例生成 Skill - 模板生成"""
    
    TEMPLATE = """# 测试用例：{title}

## 正向用例
{% for case in positive_cases %}
### {case.id} {case.title}
- **前置条件**: {case.precondition}
- **操作步骤**: {case.steps}
- **预期结果**: {case.expected}
{% endfor %}

## 异常用例
{% for case in negative_cases %}
### {case.id} {case.title}
- **异常场景**: {case.scenario}
- **操作步骤**: {case.steps}
- **预期结果**: {case.expected}
{% endfor %}

## 边界用例
{% for case in boundary_cases %}
### {case.id} {case.title}
- **边界条件**: {case.condition}
- **操作步骤**: {case.steps}
- **预期结果**: {case.expected}
{% endfor %}
"""
    
    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """生成测试用例"""
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)
        
        prd_content = input_data["prd_content"]
        
        # 提取关键信息
        title = self._extract_title(prd_content)
        requirements = self._extract_requirements(prd_content)
        
        # 生成测试用例
        positive_cases = self._generate_positive_cases(requirements)
        negative_cases = self._generate_negative_cases(requirements)
        boundary_cases = self._generate_boundary_cases(requirements)
        
        # 填充模板
        test_content = self._fill_template(
            self.TEMPLATE,
            title=title,
            positive_cases=positive_cases,
            negative_cases=negative_cases,
            boundary_cases=boundary_cases
        )
        
        return SkillResult(
            success=True,
            output={
                "test_cases": positive_cases + negative_cases + boundary_cases,
                "positive_count": len(positive_cases),
                "negative_count": len(negative_cases),
                "boundary_count": len(boundary_cases),
                "total_count": len(positive_cases) + len(negative_cases) + len(boundary_cases),
                "test_content": test_content,
            },
            metadata={"skill": "test_case", "template": "markdown"}
        )
    
    def _extract_title(self, prd_content: str) -> str:
        """提取标题"""
        match = re.search(r"^#\s+(.+)", prd_content, re.MULTILINE)
        return match.group(1).strip() if match else "未命名功能"
    
    def _extract_requirements(self, prd_content: str) -> List[str]:
        """提取需求列表"""
        requirements = []
        
        # 查找需求描述章节
        req_match = re.search(r"##\s*需求描述\s*\n((?:-\s+.+\n?)*)", prd_content)
        if req_match:
            lines = req_match.group(1).strip().split('\n')
            requirements.extend([line.strip()[2:] for line in lines if line.strip().startswith('-')])
        
        # 如果没有找到，使用整个 PRD 作为需求
        if not requirements:
            requirements.append(prd_content[:200])
        
        return requirements
    
    def _generate_positive_cases(self, requirements: List[str]) -> List[Dict]:
        """生成正向用例"""
        cases = []
        for i, req in enumerate(requirements[:3], 1):  # 最多3个正向用例
            cases.append({
                "id": f"POS-{i:03d}",
                "type": "positive",
                "title": f"正常场景{i}",
                "precondition": "系统正常运行",
                "steps": f"执行{req[:30]}...",
                "expected": "功能正常执行，无异常"
            })
        return cases
    
    def _generate_negative_cases(self, requirements: List[str]) -> List[Dict]:
        """生成异常用例"""
        cases = []
        for i, req in enumerate(requirements[:2], 1):  # 最多2个异常用例
            cases.append({
                "id": f"NEG-{i:03d}",
                "type": "negative",
                "title": f"异常场景{i}",
                "scenario": f"输入无效数据时",
                "steps": f"输入错误参数，执行{req[:20]}...",
                "expected": "系统返回错误提示，不崩溃"
            })
        return cases
    
    def _generate_boundary_cases(self, requirements: List[str]) -> List[Dict]:
        """生成边界用例"""
        cases = []
        for i, req in enumerate(requirements[:2], 1):  # 最多2个边界用例
            cases.append({
                "id": f"BDY-{i:03d}",
                "type": "boundary",
                "title": f"边界场景{i}",
                "condition": f"边界值测试",
                "steps": f"输入边界值，执行{req[:20]}...",
                "expected": "系统正确处理边界情况"
            })
        return cases
    
    def _fill_template(self, template: str, **kwargs) -> str:
        """填充模板"""
        try:
            from jinja2 import Template
            t = Template(template)
            return t.render(**kwargs)
        except Exception:
            # 降级处理：简单字符串替换
            result = template
            for key, value in kwargs.items():
                result = result.replace("{" + key + "}", str(value))
            return result
