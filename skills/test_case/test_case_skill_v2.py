"""
测试用例生成 Skill v3.0 - 资深专家版

基于 PRD 内容，提取实际需求，生成场景化测试用例。
支持领域自适应、场景挖掘、边界覆盖。
"""
import re
from typing import Dict, Any, List
from ..base import SkillBase, SkillResult


class TestCaseSkillV2(SkillBase):
    """测试用例生成 Skill - 资深专家版"""

    # 领域特定测试场景模板
    DOMAIN_SCENARIOS = {
        'advertising': [
            {'name': '竞价延迟测试', 'type': 'performance', 'steps': '发送竞价请求，测量 P99 延迟是否 < 100ms'},
            {'name': '预算超投测试', 'type': 'negative', 'steps': '设置日预算 100 元，模拟并发请求验证不会超投'},
            {'name': '降级策略测试', 'type': 'negative', 'steps': '模拟画像服务超时，验证降级到规则出价'},
            {'name': '反作弊拦截测试', 'type': 'negative', 'steps': '构造虚假流量请求，验证被识别并拦截'},
        ],
        'agent': [
            {'name': 'Tool调用正确性测试', 'type': 'positive', 'steps': '调用工具获取数据，验证返回结果格式正确'},
            {'name': '记忆检索准确性测试', 'type': 'positive', 'steps': '发送相关历史对话，验证 Agent 能检索到相关信息'},
            {'name': '多Agent协作测试', 'type': 'positive', 'steps': '设计需要多个 Agent 协作的任务，验证分工正确'},
            {'name': 'Token成本控制测试', 'type': 'performance', 'steps': '监控长对话的 Token 消耗，验证在预算内'},
        ],
        'ecommerce': [
            {'name': '并发下单测试', 'type': 'performance', 'steps': '模拟 1000 用户同时下单，验证库存扣减正确'},
            {'name': '优惠券叠加测试', 'type': 'boundary', 'steps': '使用多个优惠券组合下单，验证折扣计算正确'},
            {'name': '支付超时测试', 'type': 'negative', 'steps': '模拟支付网关超时，验证订单状态回滚'},
            {'name': '库存不足测试', 'type': 'negative', 'steps': '下单时库存为 0，验证正确提示并拒绝下单'},
        ],
        'finance': [
            {'name': '交易一致性测试', 'type': 'positive', 'steps': '执行转账操作，验证源账户扣款和目标账户收款一致'},
            {'name': '风控拦截测试', 'type': 'negative', 'steps': '构造可疑交易，验证风控系统正确拦截'},
            {'name': '对账准确性测试', 'type': 'positive', 'steps': '生成对账文件，验证与交易系统数据一致'},
            {'name': '并发交易测试', 'type': 'performance', 'steps': '模拟高并发交易，验证系统稳定性'},
        ],
    }

    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """生成测试用例"""
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)

        prd_content = input_data["prd_content"]
        profile = input_data.get("profile", {})

        # 提取关键信息
        title = self._extract_title(prd_content)
        requirements = self._extract_requirements(prd_content)
        metrics = self._extract_metrics(prd_content)
        apis = self._extract_apis(prd_content)
        domain = self._detect_domain(prd_content)

        # 生成测试用例
        test_cases = self._generate_test_cases(title, requirements, metrics, apis, domain)

        # 分类统计
        positive = [c for c in test_cases if c['type'] == 'positive']
        negative = [c for c in test_cases if c['type'] == 'negative']
        boundary = [c for c in test_cases if c['type'] == 'boundary']
        performance = [c for c in test_cases if c['type'] == 'performance']
        security = [c for c in test_cases if c['type'] == 'security']

        # 生成 Markdown 内容
        test_content = self._generate_markdown(title, test_cases, domain)

        return SkillResult(
            success=True,
            output={
                "test_cases": test_cases,
                "positive_count": len(positive),
                "negative_count": len(negative),
                "boundary_count": len(boundary),
                "performance_count": len(performance),
                "security_count": len(security),
                "total_count": len(test_cases),
                "test_content": test_content,
                "metrics_found": metrics,
                "apis_found": apis,
                "domain": domain,
            },
            metadata={"skill": "test_case_v3", "domain": domain}
        )

    def _extract_title(self, prd_content: str) -> str:
        """提取标题"""
        match = re.search(r"^#\s+(.+)", prd_content, re.MULTILINE)
        return match.group(1).strip() if match else "未命名功能"

    def _extract_requirements(self, prd_content: str) -> List[Dict]:
        """提取需求列表 - 从多个格式提取"""
        requirements = []

        # 格式1: ### 2.1 xxx 或 #### F2.1: xxx
        for match in re.finditer(r'(?:^|\n)#{3,5}\s*[\d]+\.[\d]+\s*(.+?)(?:\（|\()', prd_content):
            req_text = match.group(1).strip()
            if len(req_text) > 3:
                requirements.append({
                    'text': req_text,
                    'source': 'heading',
                    'level': 3
                })

        # 格式2: #### F1: xxx 或 #### F2.1: xxx
        for match in re.finditer(r'(?:^|\n)#{4,6}\s*F[\d.]+\s*:\s*(.+)', prd_content):
            req_text = match.group(1).strip()
            requirements.append({
                'text': req_text,
                'source': 'feature',
                'level': 4
            })

        # 格式3: - xxx (功能列表)
        for match in re.finditer(r'(?:^|\n)\s*[-*]\s+(\S.+)', prd_content):
            text = match.group(1).strip()
            if len(text) > 5 and not text.startswith('```'):
                requirements.append({
                    'text': text,
                    'source': 'list',
                    'level': 3
                })

        # 去重
        seen = set()
        unique_reqs = []
        for r in requirements:
            key = r['text'][:30]
            if key not in seen:
                seen.add(key)
                unique_reqs.append(r)

        return unique_reqs[:15]  # 最多15条需求

    def _extract_metrics(self, prd_content: str) -> List[Dict]:
        """提取性能指标和成功标准"""
        metrics = []

        # 查找数字指标
        for match in re.finditer(r'([≤<>]=?)\s*(\d+)\s*(ms|s|min|小时|天|QPS|次|%)', prd_content):
            metrics.append({
                'operator': match.group(1),
                'value': match.group(2),
                'unit': match.group(3),
                'raw': match.group(0)
            })

        # 查找覆盖率要求
        for match in re.finditer(r'覆盖[率率]?\s*[≥=]?\s*(\d+)%', prd_content):
            metrics.append({
                'type': 'coverage',
                'value': match.group(1) + '%'
            })

        # 查找优先级标记
        priorities = re.findall(r'P(\d)', prd_content)
        if priorities:
            metrics.append({
                'type': 'priority',
                'count': len(priorities),
                'levels': list(set(priorities))
            })

        return metrics[:10]

    def _extract_apis(self, prd_content: str) -> List[Dict]:
        """提取 API 接口"""
        apis = []

        # 查找 HTTP 方法 + 路径
        for match in re.finditer(r'\b(GET|POST|PUT|DELETE|PATCH)\s+(/\S+)', prd_content):
            apis.append({
                'method': match.group(1),
                'path': match.group(2)
            })

        return apis[:10]

    def _generate_test_cases(self, title: str, requirements: List[Dict],
                              metrics: List[Dict], apis: List[Dict]) -> List[Dict]:
        """生成测试用例 - 基于实际需求生成有意义的内容"""
        cases = []
        case_id = 1

        # 1. 基于功能需求生成用例
        for i, req in enumerate(requirements[:8]):
            req_text = req['text'][:50]

            # 正向用例
            cases.append({
                "id": f"POS-{case_id:03d}",
                "type": "positive",
                "title": f"正常执行-{req_text}",
                "precondition": "系统正常运行，必要数据已准备",
                "steps": f"1. 准备测试数据\n2. 执行 {req_text}\n3. 验证输出结果符合预期",
                "expected": f"功能正常执行，返回预期结果",
                "requirement": req_text
            })
            case_id += 1

            # 异常用例
            cases.append({
                "id": f"NEG-{case_id:03d}",
                "type": "negative",
                "title": f"异常处理-{req_text}",
                "scenario": f"输入无效数据时",
                "steps": f"1. 准备无效测试数据\n2. 执行 {req_text}\n3. 验证错误处理",
                "expected": f"系统返回友好错误提示，不崩溃",
                "requirement": req_text
            })
            case_id += 1

        # 2. 基于指标生成性能用例
        for metric in metrics[:3]:
            if metric.get('unit') in ['ms', 's', 'min']:
                cases.append({
                    "id": f"PERF-{case_id:03d}",
                    "type": "performance",
                    "title": f"性能指标验证-{metric.get('raw', '')}",
                    "condition": f"性能指标: {metric.get('raw', '')}",
                    "steps": f"1. 准备负载数据\n2. 执行对应操作\n3. 测量响应时间",
                    "expected": f"响应时间满足 {metric.get('raw', '')} 要求",
                    "requirement": "性能指标"
                })
                case_id += 1

        # 3. 基于 API 生成接口用例
        for api in apis[:3]:
            cases.append({
                "id": f"API-{case_id:03d}",
                "type": "positive",
                "title": f"接口测试-{api['method']} {api['path']}",
                "precondition": "系统已部署，API 可访问",
                "steps": f"1. 发送 {api['method']} 请求到 {api['path']}\n2. 携带有效认证信息\n3. 验证响应状态码和数据结构",
                "expected": f"返回 200 OK，数据结构符合定义",
                "requirement": f"API: {api['method']} {api['path']}"
            })
            case_id += 1

        # 4. 边界用例
        cases.append({
            "id": f"BDY-{case_id:03d}",
            "type": "boundary",
            "title": "边界值测试",
            "condition": "极端边界条件",
            "steps": "1. 输入空数据\n2. 输入最大合法值\n3. 输入非法类型\n4. 并发请求测试",
            "expected": "系统正确处理所有边界情况",
            "requirement": "边界测试"
        })
        case_id += 1

        return cases

    def _generate_markdown(self, title: str, cases: List[Dict]) -> str:
        """生成 Markdown 测试用例文档"""
        lines = [f"# 测试用例：{title}", ""]

        # 分组
        by_type = {'positive': [], 'negative': [], 'boundary': [], 'performance': []}
        for c in cases:
            by_type[c['type']].append(c)

        # 正向用例
        if by_type['positive']:
            lines.append("## 正向用例")
            lines.append("")
            for c in by_type['positive']:
                lines.append(f"### {c['id']} {c['title']}")
                lines.append(f"- **前置条件**: {c['precondition']}")
                lines.append(f"- **操作步骤**: {c['steps']}")
                lines.append(f"- **预期结果**: {c['expected']}")
                lines.append("")

        # 异常用例
        if by_type['negative']:
            lines.append("## 异常用例")
            lines.append("")
            for c in by_type['negative']:
                lines.append(f"### {c['id']} {c['title']}")
                lines.append(f"- **异常场景**: {c['scenario']}")
                lines.append(f"- **操作步骤**: {c['steps']}")
                lines.append(f"- **预期结果**: {c['expected']}")
                lines.append("")

        # 边界用例
        if by_type['boundary']:
            lines.append("## 边界用例")
            lines.append("")
            for c in by_type['boundary']:
                lines.append(f"### {c['id']} {c['title']}")
                lines.append(f"- **边界条件**: {c['condition']}")
                lines.append(f"- **操作步骤**: {c['steps']}")
                lines.append(f"- **预期结果**: {c['expected']}")
                lines.append("")

        # 性能用例
        if by_type['performance']:
            lines.append("## 性能用例")
            lines.append("")
            for c in by_type['performance']:
                lines.append(f"### {c['id']} {c['title']}")
                lines.append(f"- **性能指标**: {c['condition']}")
                lines.append(f"- **操作步骤**: {c['steps']}")
                lines.append(f"- **预期结果**: {c['expected']}")
                lines.append("")

        return "\n".join(lines)
