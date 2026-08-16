"""
Code Review Skill v2.0 - 资深专家版
领域特定代码审查 + 性能诊断 + 架构分析

核心升级:
  1. 领域反模式检测 (广告/Agent/电商/金融)
  2. 性能问题诊断
  3. 架构缺陷识别
  4. 修复建议生成
"""
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..base import SkillBase, SkillResult


class CodeReviewSkillV2(SkillBase):
    """代码审查 Skill - 资深专家版"""

    # 安全检查规则 (扩展)
    SECURITY_RULES = {
        "sql_injection": {
            "name": "SQL 注入风险",
            "pattern": r'(?i)(executeQuery|createStatement|prepareStatement).*["\'].*\+',
            "severity": "P0",
            "message": "发现潜在 SQL 注入，应使用参数化查询",
            "fix": "使用 PreparedStatement 或 ORM 的参数化查询",
        },
        "hardcoded_secret": {
            "name": "硬编码密钥",
            "pattern": r'(?i)(password|secret|api_key|token)\s*=\s*["\'][^"\']{5,}["\']',
            "severity": "P0",
            "message": "发现硬编码密钥，应使用环境变量或密钥管理服务",
            "fix": "使用环境变量或 Vault/Secret Manager",
        },
        "path_traversal": {
            "name": "路径遍历风险",
            "pattern": r'(?i)new\s+File\(.+\+\s*\w+',
            "severity": "P1",
            "message": "发现路径拼接，可能存在路径遍历攻击",
            "fix": "使用 Path.normalize() 并校验路径前缀",
        },
        "xss": {
            "name": "XSS 风险",
            "pattern": r'(?i)(innerHTML|document\.write|eval\()',
            "severity": "P1",
            "message": "发现 XSS 风险，应使用安全的输出编码",
            "fix": "使用 DOMPurify 或转义输出",
        },
        "insecure_random": {
            "name": "不安全随机数",
            "pattern": r'(?i)Math\.random\(\)|new\s+Random\(\)',
            "severity": "P2",
            "message": "发现不安全随机数生成，安全场景应使用 SecureRandom",
            "fix": "使用 SecureRandom 或 crypto.randomBytes()",
        },
        "hardcoded_ip": {
            "name": "硬编码 IP",
            "pattern": r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',
            "severity": "P2",
            "message": "发现硬编码 IP 地址，应使用配置中心",
            "fix": "使用配置中心或环境变量管理 IP",
        },
    }

    # 性能检查规则
    PERFORMANCE_RULES = {
        "n_plus_one": {
            "name": "N+1 查询问题",
            "pattern": r'(?:for|foreach|range)\s+.*\{[^}]*\.find[^}]*\}',
            "severity": "P1",
            "message": "发现潜在的 N+1 查询，应使用批量查询或 JOIN",
            "fix": "使用 In 查询或预加载关联数据",
        },
        "missing_index": {
            "name": "缺少索引",
            "pattern": r'(?:WHERE|ORDER BY|GROUP BY).*\w+\s*(?:=|>|<|LIKE)',
            "severity": "P1",
            "message": "查询条件可能缺少索引，建议添加",
            "fix": "为高频查询条件添加索引",
        },
        "large_result_set": {
            "name": "大结果集",
            "pattern": r'SELECT\s+\*\s+FROM',
            "severity": "P1",
            "message": "使用 SELECT * 返回大结果集，应指定列名",
            "fix": "只查询需要的列，避免 SELECT *",
        },
        "synchronous_io": {
            "name": "同步 IO",
            "pattern": r'(?:func|def|async\s+func).*\{[^}]*\.(?:Read|Write|Query|Execute)[^}]*\}',
            "severity": "P2",
            "message": "发现同步 IO 操作，建议改为异步",
            "fix": "使用 async/await 或回调模式",
        },
        "memory_leak_pattern": {
            "name": "内存泄漏模式",
            "pattern": r'(?:map|slice|channel).*\{[^}]*\w+\s*=\s*self',
            "severity": "P1",
            "message": "发现可能的内存泄漏模式，检查对象引用",
            "fix": "及时释放不再使用的对象引用",
        },
    }

    # 架构检查规则
    ARCHITECTURE_RULES = {
        "tight_coupling": {
            "name": "紧耦合设计",
            "pattern": r'(?:import|package).*\.\.[A-Z]\w+',
            "severity": "P1",
            "message": "发现紧耦合设计，建议使用接口抽象",
            "fix": "定义接口，通过依赖注入解耦",
        },
        "god_class": {
            "name": "上帝类",
            "pattern": r'type\s+\w+\s+struct\s*\{[^}]{1000,}',
            "severity": "P1",
            "message": "发现上帝类（超过 50 个字段），建议拆分",
            "fix": "按职责拆分多个结构体",
        },
        "long_method": {
            "name": "方法过长",
            "pattern": r'(?:func|def|void).*\{[^}]{2000,}',
            "severity": "P2",
            "message": "方法过长（>200行），建议拆分",
            "fix": "按职责拆分多个方法",
        },
        "deep_nesting": {
            "name": "过深嵌套",
            "pattern": r'(?:if|for|switch).*\{[^}]*\{[^}]*\{[^}]*\{',
            "severity": "P2",
            "message": "嵌套过深（>3层），建议重构",
            "fix": "使用早返回、抽出方法减少嵌套",
        },
    }

    # 领域特定规则
    DOMAIN_RULES = {
        'advertising': [
            {
                "name": "竞价延迟超标",
                "pattern": r'(?:func|handle).*[Bb]id[^{]*\{[^}]{1000,}',
                "severity": "P0",
                "message": "竞价处理函数过长，可能影响延迟",
                "fix": "优化竞价路径，确保 P99 < 100ms",
                "domain": "advertising",
            },
            {
                "name": "预算追踪竞态",
                "pattern": r'(?:budget|预算).*(?:inc|add|subtract|update)',
                "severity": "P0",
                "message": "预算操作存在竞态风险",
                "fix": "使用分布式锁或预扣机制",
                "domain": "advertising",
            },
            {
                "name": "缺少降级逻辑",
                "pattern": r'(?:func|handle).*[Pp]rofile[^{]*\{[^}]*\}(?!.*fallback)',
                "severity": "P1",
                "message": "画像查询缺少降级逻辑",
                "fix": "添加降级策略：画像→规则→默认出价",
                "domain": "advertising",
            },
        ],
        'agent': [
            {
                "name": "Tool 调用无超时",
                "pattern": r'(?:func|call).*[Tt]ool[^{]*\{[^}]*\.(?:Call|Execute)[^}]*\}',
                "severity": "P1",
                "message": "Tool 调用缺少超时控制",
                "fix": "添加 context.WithTimeout，设置合理超时",
                "domain": "agent",
            },
            {
                "name": "记忆检索无缓存",
                "pattern": r'(?:func|search).*[Mm]emory[^{]*\{[^}]*\.(?:Search|Retrieve)[^}]*\}',
                "severity": "P2",
                "message": "记忆检索缺少缓存",
                "fix": "添加 Redis 缓存，设置合理 TTL",
                "domain": "agent",
            },
            {
                "name": "循环终止条件缺失",
                "pattern": r'for\s*\{[^}]*LLM[^}]*\}',
                "severity": "P0",
                "message": "Agent 循环缺少终止条件",
                "fix": "添加 Max Iterations 或 Final Answer 检测",
                "domain": "agent",
            },
        ],
        'ecommerce': [
            {
                "name": "库存扣减无锁",
                "pattern": r'(?:func|deduct).*[Ii]nventory[^{]*\{[^}]*\.(?:Update|Decrement)[^}]*\}',
                "severity": "P0",
                "message": "库存扣减缺少并发控制",
                "fix": "使用分布式锁或乐观锁",
                "domain": "ecommerce",
            },
            {
                "name": "订单状态机不完整",
                "pattern": r'(?:status|state).*(?:CREATE|PAY|SHIP|COMPLETE)',
                "severity": "P1",
                "message": "订单状态转换缺少合法性检查",
                "fix": "实现状态机，只允许合法转换",
                "domain": "ecommerce",
            },
        ],
        'finance': [
            {
                "name": "交易缺乏幂等",
                "pattern": r'(?:func|execute).*[Tt]ransaction[^{]*\{[^}]*\.(?:Insert|Update)[^}]*\}',
                "severity": "P0",
                "message": "交易操作缺少幂等性保证",
                "fix": "添加唯一业务键，实现幂等控制",
                "domain": "finance",
            },
            {
                "name": "金额使用浮点",
                "pattern": r'(?:amount|price|total).*:=\s*[\d.]+',
                "severity": "P0",
                "message": "金额计算使用浮点数，精度丢失风险",
                "fix": "使用 Decimal 或整数（分）存储",
                "domain": "finance",
            },
        ],
        'cloud_native': [
            {
                "name": "容器无资源限制",
                "pattern": r'(?:resources|limit|request).*nil|None',
                "severity": "P1",
                "message": "容器未设置资源限制，可能导致节点过载",
                "fix": "设置 requests/limits，启用 LimitRange",
                "domain": "cloud_native",
            },
            {
                "name": "缺少健康检查",
                "pattern": r'(?:liveness|readiness|health).*(?:null|none|skip)',
                "severity": "P1",
                "message": "服务缺少健康检查，影响调度可靠性",
                "fix": "添加 liveness/readiness probe",
                "domain": "cloud_native",
            },
            {
                "name": "硬编码配置",
                "pattern": r'(?:host|port|url).*=.*["\']\d+\.\d+\.\d+\.\d+',
                "severity": "P2",
                "message": "硬编码 IP 地址，应使用配置中心",
                "fix": "使用 ConfigMap 或环境变量",
                "domain": "cloud_native",
            },
        ],
        'devops': [
            {
                "name": "流水线无回滚",
                "pattern": r'(?:rollback|revert).*(?:null|none|skip|TODO)',
                "severity": "P0",
                "message": "部署流水线缺少回滚机制",
                "fix": "实现自动回滚，保留历史版本",
                "domain": "devops",
            },
            {
                "name": "缺少部署审批",
                "pattern": r'(?:approve|approval).*(?:auto|skip|bypass)',
                "severity": "P1",
                "message": "生产部署缺少人工审批",
                "fix": "添加审批环节，区分环境权限",
                "domain": "devops",
            },
        ],
        'data_engineering': [
            {
                "name": "ETL 同步阻塞",
                "pattern": r'(?:etl|pipeline).*(?:sync|blocking|wait)',
                "severity": "P1",
                "message": "ETL 使用同步阻塞，影响实时性",
                "fix": "改为异步流式处理，使用消息队列",
                "domain": "data_engineering",
            },
            {
                "name": "缺少数据质量检查",
                "pattern": r'(?:quality|validation).*(?:null|skip|TODO)',
                "severity": "P1",
                "message": "数据管道缺少质量检查",
                "fix": "添加数据校验规则，异常告警",
                "domain": "data_engineering",
            },
        ],
        'security': [
            {
                "name": "敏感数据明文存储",
                "pattern": r'(?:password|secret|token).*=.*["\'][^"\']{5,}["\']',
                "severity": "P0",
                "message": "敏感数据明文存储，存在泄露风险",
                "fix": "使用加密存储，密钥管理服务",
                "domain": "security",
            },
            {
                "name": "缺少访问控制",
                "pattern": r'(?:access|permission|auth).*(?:null|skip|TODO)',
                "severity": "P0",
                "message": "接口缺少访问控制",
                "fix": "添加 RBAC/ABAC 权限控制",
                "domain": "security",
            },
        ],
        'ml_ops': [
            {
                "name": "模型无版本管理",
                "pattern": r'(?:model|version).*(?:latest|v1).*(?:load|fetch)',
                "severity": "P1",
                "message": "模型加载缺少版本控制",
                "fix": "使用 MLflow 等工具管理模型版本",
                "domain": "ml_ops",
            },
            {
                "name": "推理无监控",
                "pattern": r'(?:predict|inference).*(?:async|no.*monitor)',
                "severity": "P1",
                "message": "模型推理缺少监控",
                "fix": "添加推理延迟、准确率监控",
                "domain": "ml_ops",
            },
        ],
        'gaming': [
            {
                "name": "游戏逻辑纯客户端",
                "pattern": r'(?:game|logic).*(?:client|frontend).*(?:only|single)',
                "severity": "P0",
                "message": "游戏逻辑仅客户端实现，易被破解",
                "fix": "关键逻辑服务端验证，客户端仅展示",
                "domain": "gaming",
            },
            {
                "name": "无心跳检测",
                "pattern": r'(?:heartbeat|ping).*(?:null|skip|TODO)',
                "severity": "P1",
                "message": "缺少心跳检测，无法感知掉线",
                "fix": "添加心跳机制，超时踢出",
                "domain": "gaming",
            },
        ],
        'iot': [
            {
                "name": "设备直连云端",
                "pattern": r'(?:device|sensor).*(?:cloud|server).*(?:direct|connect)',
                "severity": "P1",
                "message": "设备直连云端，缺少边缘层",
                "fix": "添加边缘计算层，本地预处理",
                "domain": "iot",
            },
            {
                "name": "无断网处理",
                "pattern": r'(?:offline|disconnect).*(?:null|skip|TODO)',
                "severity": "P1",
                "message": "缺少离线数据处理",
                "fix": "本地缓存 + 断点续传",
                "domain": "iot",
            },
        ],
        'saas': [
            {
                "name": "租户数据无隔离",
                "pattern": r'(?:tenant|customer).*(?:query|sql).*(?:without.*filter)',
                "severity": "P0",
                "message": "查询缺少租户过滤，存在数据泄露风险",
                "fix": "所有查询强制添加 tenant_id 过滤",
                "domain": "saas",
            },
            {
                "name": "缺少用量计量",
                "pattern": r'(?:usage|metering).*(?:null|skip|TODO)',
                "severity": "P1",
                "message": "缺少用量计量，无法按量计费",
                "fix": "添加用量统计，支持按量计费",
                "domain": "saas",
            },
        ],
        'social': [
            {
                "name": "Feed 全量拉取",
                "pattern": r'(?:feed|timeline).*(?:load|fetch).*(?:all|every)',
                "severity": "P1",
                "message": "Feed 全量拉取，性能差",
                "fix": "使用分页 + 懒加载，按需获取",
                "domain": "social",
            },
            {
                "name": "消息无去重",
                "pattern": r'(?:message|msg).*(?:duplicate|id).*(?:null|skip)',
                "severity": "P1",
                "message": "消息缺少去重机制",
                "fix": "添加消息 ID 去重，防止重复消费",
                "domain": "social",
            },
        ],
        'logistics': [
            {
                "name": "路径优化算法缺失",
                "pattern": r'(?:route|path).*(?:naive|simple).*(?:algorithm)',
                "severity": "P1",
                "message": "路径使用简单算法，效率低",
                "fix": "使用遗传算法或动态规划优化",
                "domain": "logistics",
            },
            {
                "name": "无实时轨迹更新",
                "pattern": r'(?:tracking|location).*(?:batch|periodic).*(?:update)',
                "severity": "P1",
                "message": "轨迹更新为批量模式，延迟高",
                "fix": "改为实时推送，WebSocket 更新",
                "domain": "logistics",
            },
        ],
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
        domain = input_data.get("domain", "fullstack")

        try:
            # 收集文件
            files = self._collect_files(code_path, file_pattern, max_files)

            if not files:
                return SkillResult(
                    success=False,
                    errors=[f"未找到匹配 {file_pattern} 的文件"]
                )

            # 执行检查
            all_issues = []

            # 安全审查
            security_issues = self._check_security(files)
            all_issues.extend(security_issues)

            # 性能审查
            performance_issues = self._check_performance(files)
            all_issues.extend(performance_issues)

            # 架构审查
            architecture_issues = self._check_architecture(files)
            all_issues.extend(architecture_issues)

            # 领域审查
            domain_issues = self._check_domain(files, domain)
            all_issues.extend(domain_issues)

            # 统计
            p0_count = sum(1 for i in all_issues if i["severity"] == "P0")
            p1_count = sum(1 for i in all_issues if i["severity"] == "P1")
            p2_count = sum(1 for i in all_issues if i["severity"] == "P2")

            return SkillResult(
                success=True,
                output={
                    "total_files": len(files),
                    "total_issues": len(all_issues),
                    "p0_count": p0_count,
                    "p1_count": p1_count,
                    "p2_count": p2_count,
                    "security_issues": security_issues,
                    "performance_issues": performance_issues,
                    "architecture_issues": architecture_issues,
                    "domain_issues": domain_issues,
                    "issues": all_issues,
                    "summary": self._generate_summary(all_issues, domain),
                    "domain": domain,
                },
                metadata={
                    "skill": "code_review_v2",
                    "rules_checked": (
                        len(self.SECURITY_RULES) +
                        len(self.PERFORMANCE_RULES) +
                        len(self.ARCHITECTURE_RULES) +
                        len(self.DOMAIN_RULES.get(domain, []))
                    ),
                }
            )

        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"Code review failed: {str(e)}"]
            )

    def _check_security(self, files: List[Path]) -> List[Dict]:
        """安全审查"""
        issues = []
        for filepath in files:
            try:
                content = filepath.read_text(errors='ignore')
                for rule_name, rule in self.SECURITY_RULES.items():
                    matches = list(re.finditer(rule["pattern"], content))
                    for match in matches[:3]:
                        line_no = content[:match.start()].count('\n') + 1
                        issues.append({
                            "file": filepath.name,
                            "line": line_no,
                            "rule": rule_name,
                            "severity": rule["severity"],
                            "category": "security",
                            "message": rule["message"],
                            "fix": rule.get("fix", ""),
                            "code": content.split('\n')[line_no-1][:80] if line_no <= len(content.split('\n')) else "",
                        })
            except Exception:
                continue
        return issues

    def _check_performance(self, files: List[Path]) -> List[Dict]:
        """性能审查"""
        issues = []
        for filepath in files:
            try:
                content = filepath.read_text(errors='ignore')
                for rule_name, rule in self.PERFORMANCE_RULES.items():
                    matches = list(re.finditer(rule["pattern"], content))
                    for match in matches[:2]:
                        line_no = content[:match.start()].count('\n') + 1
                        issues.append({
                            "file": filepath.name,
                            "line": line_no,
                            "rule": rule_name,
                            "severity": rule["severity"],
                            "category": "performance",
                            "message": rule["message"],
                            "fix": rule.get("fix", ""),
                        })
            except Exception:
                continue
        return issues

    def _check_architecture(self, files: List[Path]) -> List[Dict]:
        """架构审查"""
        issues = []
        for filepath in files:
            try:
                content = filepath.read_text(errors='ignore')
                for rule_name, rule in self.ARCHITECTURE_RULES.items():
                    matches = list(re.finditer(rule["pattern"], content))
                    for match in matches[:2]:
                        line_no = content[:match.start()].count('\n') + 1
                        issues.append({
                            "file": filepath.name,
                            "line": line_no,
                            "rule": rule_name,
                            "severity": rule["severity"],
                            "category": "architecture",
                            "message": rule["message"],
                            "fix": rule.get("fix", ""),
                        })
            except Exception:
                continue
        return issues

    def _check_domain(self, files: List[Path], domain: str) -> List[Dict]:
        """领域审查"""
        issues = []
        domain_rules = self.DOMAIN_RULES.get(domain, [])

        for filepath in files:
            try:
                content = filepath.read_text(errors='ignore')
                for rule in domain_rules:
                    matches = list(re.finditer(rule["pattern"], content))
                    for match in matches[:2]:
                        line_no = content[:match.start()].count('\n') + 1
                        issues.append({
                            "file": filepath.name,
                            "line": line_no,
                            "rule": rule["name"],
                            "severity": rule["severity"],
                            "category": "domain",
                            "domain": domain,
                            "message": rule["message"],
                            "fix": rule.get("fix", ""),
                        })
            except Exception:
                continue
        return issues

    def _collect_files(self, path: str, pattern: str, max_files: int) -> List[Path]:
        """收集待审查文件"""
        path_obj = Path(path)
        if not path_obj.exists():
            return []
        return list(path_obj.rglob(pattern))[:max_files]

    def _generate_summary(self, issues: List[Dict], domain: str) -> str:
        """生成审查摘要"""
        p0 = [i for i in issues if i["severity"] == "P0"]
        p1 = [i for i in issues if i["severity"] == "P1"]
        p2 = [i for i in issues if i["severity"] == "P2"]

        # 按类别分组
        by_category = {}
        for issue in issues:
            cat = issue.get('category', 'unknown')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(issue)

        lines = [
            f"# 代码审查报告 ({domain})",
            "",
            "## 统计",
            f"- 总问题数: {len(issues)}",
            f"- 🔴 P0 (严重): {len(p0)}",
            f"- 🟡 P1 (重要): {len(p1)}",
            f"- 🔵 P2 (建议): {len(p2)}",
            "",
        ]

        # 按类别展示
        for category, cat_issues in by_category.items():
            lines.append(f"## {category.upper()} 问题")
            lines.append("")
            for issue in cat_issues[:5]:
                lines.append(f"- [{issue['file']}:{issue['line']}] {issue['message']}")
                if issue.get('fix'):
                    lines.append(f"  - 💡 修复建议: {issue['fix']}")
            lines.append("")

        if not issues:
            lines.append("✅ 未发现明显问题")

        lines.append("")
        lines.append(f"**审查时间**: {self._get_timestamp()}")
        lines.append(f"**审查规则**: {len(self.SECURITY_RULES) + len(self.PERFORMANCE_RULES) + len(self.ARCHITECTURE_RULES) + len(self.DOMAIN_RULES.get(domain, []))} 条")

        return "\n".join(lines)

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 code_review_skill_v2.py <code_path> [domain]")
        sys.exit(1)

    code_path = sys.argv[1]
    domain = sys.argv[2] if len(sys.argv) > 2 else "fullstack"

    skill = CodeReviewSkillV2({"language": "go"})
    result = skill.run({"code_path": code_path, "domain": domain})
    print(result.output["summary"])
