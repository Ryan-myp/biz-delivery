"""
PRD 审查 Skill - 基于规则的纯确定性审查

检测 PRD 中的缺失章节、模糊需求、潜在冲突等常见问题。
"""

import re
from typing import Dict, Any, List
from ..base import SkillBase, SkillResult


class PRDReviewSkill(SkillBase):
    """PRD 审查 Skill - 基于规则的纯确定性审查"""
    
    RULES = {
        "missing_title": {
            "name": "缺少标题",
            "pattern": r"^#\s+(.+)",
            "flags": re.MULTILINE,
            "severity": "P0",
            "message": "PRD 应包含一级标题（标题）",
        },
        "missing_requirements": {
            "name": "缺少需求描述",
            "pattern": r"##\s*(需求|功能|业务目标)",
            "severity": "P0",
            "message": "PRD 应包含需求描述章节",
        },
        "missing_goals": {
            "name": "缺少业务目标",
            "pattern": r"##\s*(业务目标|目标|goal|目的|背景)",
            "severity": "P0",
            "message": "PRD 应说明业务目标和背景",
        },
        "missing_timeline": {
            "name": "缺少时间规划",
            "pattern": r"##\s*(时间|排期|里程碑|schedule)",
            "severity": "P1",
            "message": "PRD 应包含时间规划章节",
        },
        "missing_dependencies": {
            "name": "缺少依赖说明",
            "pattern": r"##\s*(依赖|前置|依赖项|dependency)",
            "severity": "P1",
            "message": "PRD 应说明依赖关系",
        },
        "missing_rollback": {
            "name": "缺少回滚方案",
            "pattern": r"##\s*(回滚|rollback|降级|fallback)",
            "severity": "P1",
            "message": "PRD 应包含回滚方案",
        },
        "missing_monitoring": {
            "name": "缺少监控方案",
            "pattern": r"##\s*(监控|monitoring|告警|alert)",
            "severity": "P2",
            "message": "PRD 应包含监控方案",
        },
        "missing_risk": {
            "name": "缺少风险评估",
            "pattern": r"##\s*(风险|risk|预案|contingency)",
            "severity": "P1",
            "message": "PRD 应包含风险评估",
        },
        "missing_metrics": {
            "name": "缺少成功指标",
            "pattern": r"##\s*(指标|metric|成功标准|success)",
            "severity": "P1",
            "message": "PRD 应定义成功指标",
        },
        "missing_api_design": {
            "name": "缺少接口设计",
            "pattern": r"##\s*(接口|API|endpoint|契约)",
            "severity": "P2",
            "message": "PRD 应包含接口设计说明",
        },
        "missing_data_model": {
            "name": "缺少数据模型",
            "pattern": r"##\s*(数据|model|schema|实体)",
            "severity": "P2",
            "message": "PRD 应包含数据模型说明",
        },
        "missing_security": {
            "name": "缺少安全考虑",
            "pattern": r"##\s*(安全|security|权限|auth)",
            "severity": "P1",
            "message": "PRD 应包含安全考虑",
        },
        "missing_performance": {
            "name": "缺少性能要求",
            "pattern": r"##\s*(性能|performance|QPS|延迟)",
            "severity": "P1",
            "message": "PRD 应包含性能要求",
        },
        "vague_requirement": {
            "name": "模糊需求",
            "pattern": r"(尽快|大概|可能|或许|类似|差不多)",
            "severity": "P1",
            "message": "发现模糊表述，建议明确具体数值或标准",
        },
        "missing_acceptance_criteria": {
            "name": "缺少验收标准",
            "pattern": r"##\s*(验收|acceptance|测试标准|验证)",
            "severity": "P1",
            "message": "PRD 应包含验收标准",
        },
    }
    
    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行 PRD 审查"""
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)
        
        prd_content = input_data["prd_content"]
        issues = self._check_rules(prd_content)
        
        p0_issues = [i for i in issues if i["severity"] == "P0"]
        p1_issues = [i for i in issues if i["severity"] == "P1"]
        p2_issues = [i for i in issues if i["severity"] == "P2"]
        
        summary = self._generate_summary(issues, p0_issues, p1_issues, p2_issues)
        
        return SkillResult(
            success=len(p0_issues) == 0,
            output={
                "issues": issues,
                "summary": summary,
                "total_issues": len(issues),
                "p0_issues": len(p0_issues),
                "p0_count": len(p0_issues),
                "p1_issues": len(p1_issues),
                "p1_count": len(p1_issues),
                "p2_issues": len(p2_issues),
                "p2_count": len(p2_issues),
            },
            metadata={"skill": "prd_review", "rules_checked": len(self.RULES)}
        )
    
    def _check_rules(self, prd_content: str) -> List[Dict]:
        """检查所有规则"""
        issues = []
        
        for rule_name, rule in self.RULES.items():
            pattern = rule["pattern"]
            flags = rule.get("flags", 0)
            matches = re.search(pattern, prd_content, flags | re.IGNORECASE)
            
            # 对于必须存在的章节，如果未找到则报错
            if not matches and rule["severity"] in ["P0", "P1"]:
                issues.append({
                    "rule": rule_name,
                    "name": rule["name"],
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "type": "missing",
                })
            # 对于模糊需求检查
            elif matches and rule["name"] == "模糊需求":
                issues.append({
                    "rule": rule_name,
                    "name": rule["name"],
                    "severity": rule["severity"],
                    "message": f"发现模糊表述: '{matches.group()}'",
                    "type": "vague",
                    "match": matches.group(),
                })
        
        return issues
    
    def _generate_summary(self, issues, p0_issues, p1_issues, p2_issues) -> str:
        """生成审查摘要"""
        lines = [
            f"## PRD 审查报告",
            f"",
            f"- **总问题数**: {len(issues)}",
            f"- **P0 严重**: {len(p0_issues)}",
            f"- **P1 重要**: {len(p1_issues)}",
            f"- **P2 建议**: {len(p2_issues)}",
            f"",
        ]
        
        if p0_issues:
            lines.append("### 🔴 P0 问题（必须修复）")
            for issue in p0_issues:
                lines.append(f"- {issue['name']}: {issue['message']}")
            lines.append("")
        
        if p1_issues:
            lines.append("### 🟡 P1 问题（建议修复）")
            for issue in p1_issues:
                lines.append(f"- {issue['name']}: {issue['message']}")
            lines.append("")
        
        if p2_issues:
            lines.append("### 🟢 P2 建议（可选优化）")
            for issue in p2_issues:
                lines.append(f"- {issue['name']}: {issue['message']}")
            lines.append("")
        
        if not issues:
            lines.append("✅ PRD 结构完整，未发现明显问题")
        
        return "\n".join(lines)
