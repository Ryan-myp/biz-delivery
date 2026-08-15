"""
PRD 审查 Skill v2 - 增强版
支持中文编号(一、二、三)、多种章节格式、更宽松的关键字匹配
"""
import re
from typing import Dict, Any, List
from ..base import SkillBase, SkillResult


class PRDReviewSkill(SkillBase):
    """PRD 审查 Skill - 增强版，支持中文编号和多种格式"""

    # 使用更宽松的模式：匹配 ## 或 ### 后的内容中的任意位置
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
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+\.?[\d零一二三四五六七八九十]*\s*.{0,30}(需求|功能|用户故事|规格|functional)",
            "flags": re.MULTILINE,
            "severity": "P0",
            "message": "PRD 应包含需求描述章节",
        },
        "missing_goals": {
            "name": "缺少业务目标",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+\.?[\d零一二三四五六七八九十]*\s*.{0,30}(背景|目标|愿景|目的|goals|background)",
            "flags": re.MULTILINE,
            "severity": "P0",
            "message": "PRD 应说明业务目标和背景",
        },
        "missing_timeline": {
            "name": "缺少时间规划",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(时间|排期|里程碑|进度|计划|schedule|timeline)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应包含时间规划章节",
        },
        "missing_dependencies": {
            "name": "缺少依赖说明",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(依赖|前置|依赖项|prerequisite|dependencies)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应说明依赖关系",
        },
        "missing_rollback": {
            "name": "缺少回滚方案",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(回滚|rollback|降级|fallback|应急)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应包含回滚方案",
        },
        "missing_monitoring": {
            "name": "缺少监控方案",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(监控|monitoring|告警|alert|observability)",
            "flags": re.MULTILINE,
            "severity": "P2",
            "message": "PRD 应包含监控方案",
        },
        "missing_risk": {
            "name": "缺少风险评估",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(风险|risk|预案|contingency)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应包含风险评估",
        },
        "missing_metrics": {
            "name": "缺少成功指标",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(指标|metric|KPI|成功标准|success|验收标准|acceptance)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应定义成功指标",
        },
        "missing_api_design": {
            "name": "缺少接口设计",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(接口|API|endpoint|契约|rest|graphql)",
            "flags": re.MULTILINE,
            "severity": "P2",
            "message": "PRD 应包含接口设计说明",
        },
        "missing_data_model": {
            "name": "缺少数据模型",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(数据|model|schema|实体|ER|数据库|database)",
            "flags": re.MULTILINE,
            "severity": "P2",
            "message": "PRD 应包含数据模型说明",
        },
        "missing_security": {
            "name": "缺少安全考虑",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+\.?[\d零一二三四五六七八九十]*\s*.{0,30}(安全|security|权限|auth|加密|隐私|privacy)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应包含安全考虑",
        },
        "missing_performance": {
            "name": "缺少性能要求",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+\.?[\d零一二三四五六七八九十]*\s*.{0,30}(性能|performance|QPS|延迟|latency|吞吐|throughput)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应包含性能要求",
        },
        "vague_requirement": {
            "name": "模糊需求",
            "pattern": r"\b(尽快|大概|可能|或许|类似|差不多|一些|若干|较多|大约)\b",
            "severity": "P1",
            "message": "发现模糊表述，建议明确具体数值或标准",
        },
        "missing_acceptance_criteria": {
            "name": "缺少验收标准",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(验收|acceptance|测试标准|验证|交付标准)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应包含验收标准",
        },
        "no_user_stories": {
            "name": "缺少用户故事",
            "pattern": r"(作为.*我希望.*以便|As a.*I want.*so that|用户故事)",
            "flags": re.IGNORECASE,
            "severity": "P2",
            "message": "建议添加用户故事格式的需求描述",
        },
        "no_priority": {
            "name": "缺少需求优先级",
            "pattern": r"\b(P0|P1|P2|高优先级|中优先级|低优先级|must have|should have|could have)\b",
            "flags": re.IGNORECASE,
            "severity": "P2",
            "message": "建议为需求添加优先级标记",
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

        # success = 无 P0 问题
        return SkillResult(
            success=len(p0_issues) == 0,
            output={
                "issues": issues,
                "summary": summary,
                "total_issues": len(issues),
                "p0_count": len(p0_issues),
                "p1_count": len(p1_issues),
                "p2_count": len(p2_issues),
            },
            metadata={"skill": "prd_review_v2", "rules_checked": len(self.RULES)}
        )

    def _check_rules(self, prd_content: str) -> List[Dict]:
        """检查所有规则"""
        issues = []

        for rule_name, rule in self.RULES.items():
            pattern = rule["pattern"]
            flags = rule.get("flags", 0) | re.MULTILINE
            matches = list(re.finditer(pattern, prd_content, flags | re.IGNORECASE))

            # 对于必须存在的章节，如果未找到则报错
            if rule_name != "vague_requirement" and rule_name != "no_user_stories" and rule_name != "no_priority":
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
                # 只报告前5个模糊表述
                for m in matches[:5]:
                    issues.append({
                        "rule": rule_name,
                        "name": rule["name"],
                        "severity": rule["severity"],
                        "message": f"发现模糊表述: '{m.group()}'",
                        "type": "vague",
                        "match": m.group(),
                    })
            # 对于建议性检查
            elif matches and rule_name in ["no_user_stories", "no_priority"]:
                issues.append({
                    "rule": rule_name,
                    "name": rule["name"],
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "type": "found",
                    "match": matches[0].group(),
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
            lines.append("### 🔵 P2 建议（可选优化）")
            for issue in p2_issues:
                lines.append(f"- {issue['name']}: {issue['message']}")
            lines.append("")

        if not issues:
            lines.append("✅ 恭喜！PRD 结构完整，无重大问题。")

        return "\n".join(lines)
