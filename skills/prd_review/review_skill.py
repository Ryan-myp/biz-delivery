"""
PRD Review Skill 实现
职责：基于规则自主发现 PRD 中的问题

纯确定性实现，不依赖 LLM
"""

import re
from typing import Any, Dict, List, Optional
from ..base import SkillBase, SkillResult


class PRDReviewSkill(SkillBase):
    """PRD 审查 Skill - 基于规则的纯确定性审查"""
    
    REQUIRED_INPUT = ["prd_content"]
    
    # 定义审查规则
    RULES = {
        "missing_title": {
            "name": "缺少标题",
            "pattern": r"^#\s+(.+)",
            "severity": "P0",
            "message": "PRD 应包含一级标题（标题）",
        },
        "missing_requirements": {
            "name": "缺少需求描述",
            "pattern": r"##\s*(需求|功能|业务目标)",
            "severity": "P0",
            "message": "PRD 应包含需求描述章节",
        },
        "missing_api_specs": {
            "name": "缺少 API 规格",
            "pattern": r"##\s*(接口|API|接口定义)",
            "severity": "P1",
            "message": "PRD 应包含接口规格说明",
        },
        "missing_data_model": {
            "name": "缺少数据模型",
            "pattern": r"##\s*(数据|模型|Schema)",
            "severity": "P1",
            "message": "PRD 应包含数据模型定义",
        },
        "missing_edge_cases": {
            "name": "缺少边界条件",
            "pattern": r"##\s*(边界|异常|Edge)",
            "severity": "P1",
            "message": "PRD 应包含边界条件和异常处理",
        },
        "vague_requirement": {
            "name": "需求描述模糊",
            "pattern": r"优化|改善|提升|方便|更好",
            "severity": "P2",
            "message": "需求描述过于模糊，应具体可衡量",
        },
        "missing_performance": {
            "name": "缺少性能要求",
            "pattern": r"##\s*(性能|Performance|QoS)",
            "severity": "P2",
            "message": "PRD 应包含性能要求（QPS、延迟等）",
        },
        "missing_security": {
            "name": "缺少安全要求",
            "pattern": r"##\s*(安全|Security|Auth)",
            "severity": "P2",
            "message": "PRD 应包含安全要求说明",
        },
    }
    
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile)
    
    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行 PRD 审查"""
        # 验证输入
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)
        
        prd_content = input_data["prd_content"]
        
        # 执行规则检查
        issues = self._check_rules(prd_content)
        
        # 分类问题
        p0_issues = [i for i in issues if i["severity"] == "P0"]
        p1_issues = [i for i in issues if i["severity"] == "P1"]
        p2_issues = [i for i in issues if i["severity"] == "P2"]
        
        # 计算风险等级
        risk_level = self._calculate_risk(p0_issues, p1_issues)
        
        return SkillResult(
            success=len(p0_issues) == 0,  # 有 P0 问题则失败
            output={
                "issues": issues,
                "p0_count": len(p0_issues),
                "p1_count": len(p1_issues),
                "p2_count": len(p2_issues),
                "total_issues": len(issues),
                "risk_level": risk_level,
                "summary": self._generate_summary(issues),
            },
            metadata={
                "skill": "prd_review",
                "rules_checked": len(self.RULES),
                "approach": "rule_based",
            }
        )
    
    def _check_rules(self, prd_content: str) -> List[Dict]:
        """执行规则检查"""
        issues = []
        
        for rule_name, rule in self.RULES.items():
            if not re.search(rule["pattern"], prd_content, re.IGNORECASE):
                # 注意：如果没有匹配到，说明缺少该内容，应该添加问题
                # 但有些规则是检查"应该包含"的，所以没匹配到才是问题
                if rule_name in ["missing_title", "missing_requirements", 
                                 "missing_api_specs", "missing_data_model",
                                 "missing_edge_cases", "missing_performance",
                                 "missing_security"]:
                    issues.append({
                        "rule": rule_name,
                        "name": rule["name"],
                        "severity": rule["severity"],
                        "message": rule["message"],
                        "location": "document_structure",
                    })
        
        # 检查模糊需求
        vague_patterns = ["优化", "改善", "提升", "方便", "更好", "更高效", "更便捷"]
        for pattern in vague_patterns:
            if re.search(pattern, prd_content):
                issues.append({
                    "rule": "vague_requirement",
                    "name": f"模糊描述：{pattern}",
                    "severity": "P2",
                    "message": f"发现模糊描述\"{pattern}\"，应具体可衡量",
                    "location": "content",
                })
        
        return issues
    
    def _calculate_risk(self, p0_issues: List, p1_issues: List) -> str:
        """计算风险等级"""
        if len(p0_issues) > 0:
            return "high"
        elif len(p1_issues) > 3:
            return "medium"
        else:
            return "low"
    
    def _generate_summary(self, issues: List[Dict]) -> str:
        """生成审查摘要"""
        if not issues:
            return "✅ PRD 结构完整，未发现明显问题"
        
        p0_count = sum(1 for i in issues if i["severity"] == "P0")
        p1_count = sum(1 for i in issues if i["severity"] == "P1")
        p2_count = sum(1 for i in issues if i["severity"] == "P2")
        
        summary = f"⚠️ 发现 {len(issues)} 个问题"
        if p0_count > 0:
            summary += f"（P0: {p0_count}, P1: {p1_count}, P2: {p2_count}）"
            summary += "\n\n🔴 P0 问题（必须修复）："
            for i in issues:
                if i["severity"] == "P0":
                    summary += f"\n- {i['message']}"
        
        return summary
