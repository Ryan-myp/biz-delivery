"""
Code Review Skill - 代码审查 Skill
"""
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..base import SkillBase, SkillResult


class CodeReviewSkill(SkillBase):
    """代码审查 Skill - 检测常见问题和安全漏洞"""

    # 安全检查规则
    SECURITY_RULES = {
        "sql_injection": {
            "name": "SQL 注入风险",
            "pattern": r'(?i)(executeQuery|createStatement|prepareStatement).*["\'].*\+',
            "severity": "P0",
            "message": "发现潜在 SQL 注入，应使用参数化查询",
        },
        "hardcoded_secret": {
            "name": "硬编码密钥",
            "pattern": r'(?i)(password|secret|api_key|token)\s*=\s*["\'][^"\']{5,}["\']',
            "severity": "P0",
            "message": "发现硬编码密钥，应使用环境变量或密钥管理服务",
        },
        "path_traversal": {
            "name": "路径遍历风险",
            "pattern": r'(?i)new\s+File\(.+\+\s*\w+',
            "severity": "P1",
            "message": "发现路径拼接，可能存在路径遍历攻击",
        },
        "xss": {
            "name": "XSS 风险",
            "pattern": r'(?i)(innerHTML|document\.write|eval\()',
            "severity": "P1",
            "message": "发现 XSS 风险，应使用安全的输出编码",
        },
        "insecure_random": {
            "name": "不安全随机数",
            "pattern": r'(?i)Math\.random\(\)|new\s+Random\(\)',
            "severity": "P2",
            "message": "发现不安全随机数生成，安全场景应使用 SecureRandom",
        },
    }

    # 代码质量规则
    QUALITY_RULES = {
        "magic_number": {
            "name": "魔法数字",
            "pattern": r'\b\d{4,}\b',
            "severity": "P2",
            "message": "发现魔法数字，应提取为常量",
        },
        "long_method": {
            "name": "方法过长",
            "pattern": r'(?:public|private|protected)\s+\w+[^{]*\{[^}]{500,}',
            "severity": "P1",
            "message": "方法过长（>500字符），建议拆分",
        },
        "too_many_params": {
            "name": "参数过多",
            "pattern": r'\([^)]{100,}\)',
            "severity": "P2",
            "message": "方法参数过多，建议封装为对象",
        },
        "null_check_missing": {
            "name": "缺少空值检查",
            "pattern": r'\w+\.\w+\(.*\)\.\w+\(',
            "severity": "P1",
            "message": "链式调用缺少空值检查",
        },
    }

    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile)

    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行代码审查"""
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)

        code_path = input_data.get("code_path", "")
        file_pattern = input_data.get("file_pattern", "*.go")
        max_files = input_data.get("max_files", 50)

        try:
            # 收集文件
            files = self._collect_files(code_path, file_pattern, max_files)
            
            if not files:
                return SkillResult(
                    success=False,
                    errors=[f"未找到匹配 {file_pattern} 的文件"]
                )

            # 执行检查
            security_issues = []
            quality_issues = []
            
            for filepath in files:
                try:
                    content = filepath.read_text(errors='ignore')
                    
                    # 安全审查
                    for rule_name, rule in self.SECURITY_RULES.items():
                        matches = list(re.finditer(rule["pattern"], content))
                        for match in matches[:3]:  # 每个规则最多3个
                            line_no = content[:match.start()].count('\n') + 1
                            security_issues.append({
                                "file": str(filepath.relative_to(code_path) if code_path in str(filepath) else filepath.name),
                                "line": line_no,
                                "rule": rule_name,
                                "severity": rule["severity"],
                                "message": rule["message"],
                                "code": content.split('\n')[line_no-1][:80] if line_no <= len(content.split('\n')) else ""
                            })
                    
                    # 质量审查
                    for rule_name, rule in self.QUALITY_RULES.items():
                        matches = list(re.finditer(rule["pattern"], content))
                        for match in matches[:2]:
                            line_no = content[:match.start()].count('\n') + 1
                            quality_issues.append({
                                "file": str(filepath.relative_to(code_path) if code_path in str(filepath) else filepath.name),
                                "line": line_no,
                                "rule": rule_name,
                                "severity": rule["severity"],
                                "message": rule["message"],
                            })
                
                except Exception as e:
                    continue

            # 汇总结果
            issues = security_issues + quality_issues
            p0_count = sum(1 for i in issues if i["severity"] == "P0")
            p1_count = sum(1 for i in issues if i["severity"] == "P1")
            p2_count = sum(1 for i in issues if i["severity"] == "P2")

            return SkillResult(
                success=True,
                output={
                    "total_files": len(files),
                    "total_issues": len(issues),
                    "p0_count": p0_count,
                    "p1_count": p1_count,
                    "p2_count": p2_count,
                    "security_issues": security_issues,
                    "quality_issues": quality_issues,
                    "issues": issues,
                    "summary": self._generate_summary(issues),
                },
                metadata={
                    "skill": "code_review",
                    "rules_checked": len(self.SECURITY_RULES) + len(self.QUALITY_RULES),
                }
            )

        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"Code review failed: {str(e)}"]
            )

    def _collect_files(self, path: str, pattern: str, max_files: int) -> List[Path]:
        """收集待审查文件"""
        path_obj = Path(path)
        if not path_obj.exists():
            return []
        return list(path_obj.rglob(pattern))[:max_files]

    def _generate_summary(self, issues: List[Dict]) -> str:
        """生成审查摘要"""
        p0 = [i for i in issues if i["severity"] == "P0"]
        p1 = [i for i in issues if i["severity"] == "P1"]
        p2 = [i for i in issues if i["severity"] == "P2"]
        
        lines = [
            "# 代码审查报告",
            "",
            f"## 统计",
            f"- 总问题数: {len(issues)}",
            f"- 🔴 P0 (严重): {len(p0)}",
            f"- 🟡 P1 (重要): {len(p1)}",
            f"- 🔵 P2 (建议): {len(p2)}",
            "",
        ]
        
        if p0:
            lines.append("## 🔴 P0 安全问题")
            for i in p0[:5]:
                lines.append(f"- [{i['file']}:{i['line']}] {i['message']}")
            lines.append("")
        
        if p1:
            lines.append("## 🟡 P1 重要问题")
            for i in p1[:5]:
                lines.append(f"- [{i['file']}:{i['line']}] {i['message']}")
            lines.append("")
        
        if not issues:
            lines.append("✅ 未发现明显问题")
        
        return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 code_review_skill.py <code_path>")
        sys.exit(1)
    
    skill = CodeReviewSkill({"language": "go"})
    result = skill.run({"code_path": sys.argv[1]})
    print(result.output["summary"])
