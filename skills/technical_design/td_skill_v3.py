"""
Technical Design Skill v3.0 - 资深专家版
领域自适应技术方案生成 + 架构权衡分析

核心升级:
  1. 领域架构模式 (广告/Agent/电商/金融)
  2. 性能成本权衡分析
  3. 风险预案设计
  4. 知识库最佳实践引用
"""
import re
from typing import Any, Dict, List, Optional
from ..base import SkillBase, SkillResult


class TDSkillV3(SkillBase):
    """技术方案生成 Skill - 资深专家版"""

    # 领域架构模式库
    DOMAIN_ARCH_PATTERNS = {
        'advertising': {
            'name': '广告竞价系统架构',
            'pattern': 'event-driven-microservice',
            'components': [
                'API Gateway (Kong/Nginx)',
                'Bid Handler (Go)',
                'User Profile Service (Redis/HBase)',
                'Pricing Engine (规则 + 模型)',
                'Budget Tracker (Redis + 本地缓存)',
                'Settlement Service (Kafka)',
            ],
            'key_decisions': [
                '延迟预算: P99 < 100ms',
                '降级策略: 画像→规则→默认出价',
                '预算追踪: 本地预扣 + 异步同步',
            ],
            'reference_docs': [
                'knowledge/advertising/dsp-high-concurrency-design-deep.md',
                'knowledge/advertising/ad-bidding-engine-deep.md',
            ]
        },
        'agent': {
            'name': 'Agent 编排系统架构',
            'pattern': 'react-multi-agent',
            'components': [
                'Agent Orchestrator (Manager Agent)',
                'Tool Registry (MCP/Function Calling)',
                'Memory System (短期 + 长期)',
                'LLM Router (模型选择)',
                'Guardrails (安全过滤)',
                'Observability (Tracing + Logging)',
            ],
            'key_decisions': [
                'Agent 模式: ReAct vs Planner vs Multi-Agent',
                '记忆策略: 向量DB + 时间衰减',
                '工具编排: 串行/并行/条件分支',
            ],
            'reference_docs': [
                'knowledge/agent-ai/agent-architecture-deep.md',
                'knowledge/agent-ai/react-deep-dive.md',
            ]
        },
        'ecommerce': {
            'name': '电商交易架构',
            'pattern': 'ddd-event-sourcing',
            'components': [
                'Order Service (DDD 聚合根)',
                'Inventory Service (分布式锁)',
                'Payment Service (最终一致性)',
                'Promotion Service (规则引擎)',
                'Message Queue (Kafka)',
                'CDC (Canal/Debezium)',
            ],
            'key_decisions': [
                '数据一致性: Saga 模式',
                '库存扣减: 预扣 + 异步确认',
                '幂等设计: 业务唯一键',
            ],
            'reference_docs': [
                'knowledge/architecture/ddd-strategic-master.md',
                'knowledge/architecture/compensating-transaction.md',
            ]
        },
        'finance': {
            'name': '金融交易系统架构',
            'pattern': 'cqrs-event-sourcing',
            'components': [
                'Trading Service (强一致性)',
                'Risk Control Service (实时风控)',
                'Account Service (分布式事务)',
                'Clearing Service (T+1 清算)',
                'Audit Service (不可篡改日志)',
                'Compliance Service (合规检查)',
            ],
            'key_decisions': [
                '数据一致性: 强一致 (本地事务)',
                '风控策略: 规则 + 模型双引擎',
                '审计要求: 操作日志不可篡改',
            ],
            'reference_docs': [
                'knowledge/architecture/cqrs-master.md',
                'knowledge/architecture/event-driven-microservice-source.md',
            ]
        },
        'fullstack': {
            'name': '通用微服务架构',
            'pattern': 'modular-monolith',
            'components': [
                'API Gateway',
                'Core Service',
                'Database (读写分离)',
                'Cache (Redis)',
                'Message Queue',
                'Monitoring',
            ],
            'key_decisions': [
                '架构风格: 模块化单体 → 微服务演进',
                '数据库: 单库 → 分库分表',
                '缓存: 本地 → Redis → 多级',
            ],
            'reference_docs': [
                'knowledge/architecture/microservice-patterns.md',
                'knowledge/architecture/hexagonal-architecture.md',
            ]
        }
    }

    # 性能权衡矩阵
    PERFORMANCE_TRADEOFFS = {
        'consistency': {
            'strong': {'latency': '高', 'throughput': '低', 'cost': '高'},
            'eventual': {'latency': '中', 'throughput': '高', 'cost': '中'},
            'flexible': {'latency': '低', 'throughput': '高', 'cost': '低'},
        },
        'availability': {
            'high': {'complexity': '高', 'cost': '高', 'data_loss_risk': '低'},
            'medium': {'complexity': '中', 'cost': '中', 'data_loss_risk': '中'},
            'basic': {'complexity': '低', 'cost': '低', 'data_loss_risk': '高'},
        },
        'partition_tolerance': {
            'yes': {'latency_increase': '有', 'data_consistency': '最终一致'},
            'no': {'latency_increase': '无', 'data_consistency': '强一致'},
        }
    }

    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行技术方案生成"""
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)

        prd_content = input_data["prd_content"]
        profile = input_data.get("profile", self.profile)

        try:
            # 提取 PRD 信息
            prd_info = self._extract_prd_info(prd_content)

            # 识别领域
            domain = self._detect_domain(prd_content)

            # 获取领域架构模式
            arch_pattern = self.DOMAIN_ARCH_PATTERNS.get(domain, self.DOMAIN_ARCH_PATTERNS['fullstack'])

            # 生成技术方案
            td_content = self._generate_expert_td(prd_info, profile, arch_pattern, domain)

            # 生成权衡分析
            tradeoff_analysis = self._generate_tradeoff_analysis(prd_info, domain)

            # 生成风险预案
            risk_plan = self._generate_risk_plan(prd_info, domain)

            return SkillResult(
                success=True,
                output={
                    "td_content": td_content,
                    "sections": self._extract_sections(td_content),
                    "language": profile.get("language", "go"),
                    "domain": domain,
                    "arch_pattern": arch_pattern['name'],
                    "tradeoff_analysis": tradeoff_analysis,
                    "risk_plan": risk_plan,
                    "extracted_info": prd_info,
                },
                metadata={
                    "skill": "technical_design_v3",
                    "domain": domain,
                    "arch_pattern": arch_pattern['pattern'],
                }
            )

        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"TD generation failed: {str(e)}"]
            )

    def _detect_domain(self, prd: str) -> str:
        """识别 PRD 所属领域"""
        domain_scores = {
            'advertising': 0,
            'agent': 0,
            'ecommerce': 0,
            'finance': 0,
            'fullstack': 0,
        }

        # 广告领域关键词
        ad_keywords = ['竞价', 'RTB', 'DSP', 'SSP', '广告', '出价', '曝光', '点击',
                       '归因', 'ROI', 'eCPM', 'pCTR', '反作弊', '创意', '素材']
        for kw in ad_keywords:
            if kw in prd:
                domain_scores['advertising'] += 1

        # Agent 领域关键词
        agent_keywords = ['Agent', 'LLM', 'RAG', 'ReAct', '工具调用', '记忆系统',
                         'Multi-Agent', 'Planner', 'Function Calling', 'MCP']
        for kw in agent_keywords:
            if kw in prd:
                domain_scores['agent'] += 1

        # 电商领域关键词
        ecommerce_keywords = ['订单', '商品', '库存', '支付', '购物车', '促销', '优惠券']
        for kw in ecommerce_keywords:
            if kw in prd:
                domain_scores['ecommerce'] += 1

        # 金融领域关键词
        finance_keywords = ['交易', '账户', '风控', '合规', '清算', '对账']
        for kw in finance_keywords:
            if kw in prd:
                domain_scores['finance'] += 1

        # 根据得分确定领域
        max_score = max(domain_scores.values())
        if max_score == 0:
            return 'fullstack'

        detected_domain = max(domain_scores, key=domain_scores.get)
        return detected_domain

    def _extract_prd_info(self, prd_content: str) -> Dict[str, Any]:
        """从 PRD 提取关键信息"""
        info = {
            "title": "",
            "requirements": [],
            "apis": [],
            "data_models": [],
            "constraints": [],
            "features": [],
            "tech_stack": [],
            "performance_req": {},
        }

        # 提取标题
        title_match = re.search(r"^#\s+(.+)", prd_content, re.MULTILINE)
        if title_match:
            info["title"] = title_match.group(1).strip()

        # 提取功能需求
        for match in re.finditer(r'(?:^|\n)#{3,5}\s*[\d]+\.[\d]+\s*(.+?)(?:\（|\()', prd_content):
            text = match.group(1).strip()
            if len(text) > 3:
                info["features"].append(text)

        # 提取 F1/F2 特性
        for match in re.finditer(r'(?:^|\n)#{4,6}\s*F[\d.]+\s*:\s*(.+)', prd_content):
            info["features"].append(match.group(1).strip())

        # 提取 API
        for match in re.finditer(r'\b(GET|POST|PUT|DELETE|PATCH)\s+(/\S+)', prd_content):
            info["apis"].append({
                "method": match.group(1),
                "path": match.group(2)
            })

        # 提取性能指标
        for match in re.finditer(r'([≤<>]=?)\s*(\d+)\s*(ms|s|min|QPS|万)', prd_content):
            info["performance_req"][match.group(3)] = {
                "operator": match.group(1),
                "value": match.group(2)
            }

        # 提取技术栈
        tech_keywords = ['go', 'gin', 'fiber', 'echo', 'fastapi', 'flask',
                        'redis', 'kafka', 'mysql', 'postgres', 'mongodb',
                        'docker', 'kubernetes', 'grpc', 'protobuf', 'etcd']
        for kw in tech_keywords:
            if kw in prd_content.lower():
                info["tech_stack"].append(kw)

        # 提取约束
        for match in re.finditer(r'(?:^|\n)[\-*]\s*(.*(?:必须|禁止|不能|应|需).*)', prd_content):
            text = match.group(1).strip()
            if len(text) > 5 and len(text) < 200:
                info["constraints"].append(text)

        return info

    def _generate_expert_td(self, info: Dict, profile: Dict, arch_pattern: Dict, domain: str) -> str:
        """生成专家级技术方案"""
        lines = [
            f"# 技术方案：{info.get('title', '未命名项目')}",
            "",
            f"**领域**: {arch_pattern['name']}",
            f"**架构模式**: {arch_pattern['pattern']}",
            f"**生成时间**: {self._get_timestamp()}",
            "",
            "---",
            "",
        ]

        # 1. 架构设计
        lines.extend([
            "## 一、架构设计",
            "",
            f"### 1.1 架构模式",
            f"- **模式**: {arch_pattern['name']}",
            f"- **适用场景**: {self._get_scenario_description(domain)}",
            "",
            f"### 1.2 核心组件",
            "",
            "| 组件 | 职责 | 技术选型 |",
            "|------|------|----------|",
        ])

        for i, comp in enumerate(arch_pattern['components'][:6], 1):
            lines.append(f"| {i}. {comp.split('(')[0].strip()} | 核心业务逻辑 | {comp.split('(')[1].rstrip(')') if '(' in comp else 'Go'} |")

        lines.extend([
            "",
            f"### 1.3 关键架构决策",
            "",
        ])

        for decision in arch_pattern.get('key_decisions', [])[:3]:
            lines.append(f"- {decision}")

        lines.extend([
            "",
            "### 1.4 模块划分",
            "",
        ])

        # 根据功能需求生成模块划分
        features = info.get('features', [])[:5]
        for i, feature in enumerate(features, 1):
            lines.append(f"{i}. **{feature[:30]}...**")

        lines.extend([
            "",
            "## 二、接口设计",
            "",
            "### 2.1 API 列表",
            "",
            "| 方法 | 路径 | 说明 |",
            "|------|------|------|",
        ])

        for api in info.get('apis', [])[:5]:
            lines.append(f"| {api['method']} | {api['path']} | 核心接口 |")

        lines.extend([
            "",
            "## 三、数据模型",
            "",
            "### 3.1 核心实体",
            "",
        ])

        # 根据领域生成数据模型
        if domain == 'advertising':
            lines.extend([
                "- **AdGroup**: 广告组 (ID, 预算, 状态, 时间窗口)",
                "- **Creative**: 创意素材 (ID, 类型, 状态, 审核结果)",
                "- **BidRequest**: 竞价请求 (ID, 用户ID, 上下文, 出价)",
                "- **Budget**: 预算追踪 (ID, 日预算, 已消耗, 频次控制)",
            ])
        elif domain == 'agent':
            lines.extend([
                "- **Agent**: Agent 实例 (ID, 模式, 工具集, 记忆)",
                "- **ToolCall**: 工具调用 (ID, AgentID, 工具名, 输入输出)",
                "- **Message**: 对话消息 (ID, 角色, 内容, 时间戳)",
                "- **Memory**: 记忆记录 (ID, 类型, 内容, 过期时间)",
            ])
        elif domain == 'ecommerce':
            lines.extend([
                "- **Order**: 订单 (ID, 用户ID, 商品, 金额, 状态)",
                "- **Inventory**: 库存 (ID, 商品ID, 数量, 预扣)",
                "- **Payment**: 支付记录 (ID, 订单ID, 方式, 状态)",
                "- **Promotion**: 优惠规则 (ID, 类型, 条件, 折扣)",
            ])
        else:
            lines.extend([
                "- **Entity**: 核心业务实体",
                "- **DTO**: 数据传输对象",
                "- **Query**: 查询对象",
            ])

        lines.extend([
            "",
            "## 四、技术选型",
            "",
            "### 4.1 技术栈",
            "",
        ])

        for tech in info.get('tech_stack', [])[:8]:
            lines.append(f"- {tech}")

        lines.extend([
            "",
            "### 4.2 中间件",
            "",
            "| 组件 | 选型 | 用途 |",
            "|------|------|------|",
            "| 缓存 | Redis | 热点数据/分布式锁 |",
            "| 消息队列 | Kafka | 异步解耦/削峰 |",
            "| 配置中心 | etcd/Nacos | 动态配置 |",
            "| 服务发现 | Consul/Nacos | 服务注册发现 |",
            "",
            "## 五、性能设计",
            "",
        ])

        # 性能指标
        perf_req = info.get('performance_req', {})
        if perf_req:
            lines.append("### 5.1 性能指标")
            lines.append("")
            for unit, req in perf_req.items():
                lines.append(f"- P{unit}: {req['operator']}{req['value']}")
        else:
            lines.append("### 5.1 性能目标")
            lines.append("")
            lines.append("- QPS: > 1000")
            lines.append("- 延迟 P99: < 100ms")
            lines.append("- 可用性: > 99.9%")

        lines.extend([
            "",
            "### 5.2 优化策略",
            "",
        ])

        # 根据领域给出优化策略
        if domain == 'advertising':
            lines.extend([
                "- **画像查询优化**: Redis 本地缓存 + 异步预取",
                "- **出价决策优化**: 规则引擎 + 模型并行推理",
                "- **预算追踪优化**: 分段预算 + 本地计数器",
            ])
        elif domain == 'agent':
            lines.extend([
                "- **Token 优化**: 上下文压缩 + 模型分级",
                "- **Tool 调用优化**: 结果缓存 + 批量请求",
                "- **记忆检索优化**: 向量索引 + 混合检索",
            ])
        else:
            lines.extend([
                "- **数据库优化**: 索引设计 + 分库分表",
                "- **缓存优化**: 多级缓存 + 预热策略",
                "- **并发优化**: 连接池 + 异步处理",
            ])

        lines.extend([
            "",
            "## 六、可靠性设计",
            "",
            "### 6.1 容灾方案",
            "",
            "- **多可用区部署**: 跨 AZ 部署，故障自动切换",
            "- **数据备份**: 每日全量 + 实时增量",
            "- **降级策略**: 核心功能优先，非核心功能降级",
            "",
            "### 6.2 监控告警",
            "",
            "| 监控维度 | 指标 | 告警阈值 |",
            "|----------|------|----------|",
            "| 业务 | QPS/成功率 | < 99% |",
            "| 性能 | P99 延迟 | > 200ms |",
            "| 资源 | CPU/内存 | > 80% |",
            "| 错误 | 异常率 | > 1% |",
            "",
            "## 七、成本评估",
            "",
            "| 成本项 | 估算 | 说明 |",
            "|--------|------|------|",
            "| 服务器 | X 台 | 按 QPS 估算 |",
            "| 带宽 | X GB/月 | 按流量估算 |",
            "| 存储 | X TB | 按数据量估算 |",
            "| 中间件 | Redis/Kafka | 按规格估算 |",
            "",
            "## 八、实施计划",
            "",
            "### Phase 1: 基础架构 (2周)",
            "- 服务骨架搭建",
            "- 核心接口实现",
            "- 基础测试",
            "",
            "### Phase 2: 核心功能 (3周)",
            "- 业务逻辑实现",
            "- 性能优化",
            "- 集成测试",
            "",
            "### Phase 3: 上线准备 (1周)",
            "- 容灾演练",
            "- 监控接入",
            "- 上线发布",
            "",
            "---",
            "",
            f"*方案由资深专家系统生成 | 领域: {arch_pattern['name']}*",
        ])

        return "\n".join(lines)

    def _generate_tradeoff_analysis(self, info: Dict, domain: str) -> Dict:
        """生成权衡分析"""
        return {
            "consistency_vs_latency": {
                "description": "一致性与延迟权衡",
                "recommendation": "根据业务容忍度选择",
                "options": [
                    {"name": "强一致", "latency": "高", "use_case": "金融交易"},
                    {"name": "最终一致", "latency": "中", "use_case": "电商订单"},
                    {"name": "灵活一致", "latency": "低", "use_case": "广告竞价"},
                ]
            },
            "availability_vs_partition": {
                "description": "可用性与分区容忍权衡",
                "recommendation": "AP 优先还是 CP 优先",
                "options": [
                    {"name": "AP 优先", "consistency": "最终一致", "use_case": "高可用场景"},
                    {"name": "CP 优先", "availability": "可能降级", "use_case": "数据强一致场景"},
                ]
            },
            "cost_vs_performance": {
                "description": "成本与性能权衡",
                "recommendation": "按需扩容，弹性伸缩",
                "options": [
                    {"name": "高性能高成本", "infra": "多可用区 + 全量缓存", "cost": "高"},
                    {"name": "平衡型", "infra": "单可用区 + 核心缓存", "cost": "中"},
                    {"name": "成本优先", "infra": "基础部署 + 按需扩容", "cost": "低"},
                ]
            }
        }

    def _generate_risk_plan(self, info: Dict, domain: str) -> Dict:
        """生成风险预案"""
        risks = [
            {
                "name": "性能风险",
                "level": "高",
                "description": "高并发场景下系统性能下降",
                "mitigation": "限流熔断 + 降级策略 + 缓存预热",
                "owner": "后端团队"
            },
            {
                "name": "数据一致性风险",
                "level": "中",
                "description": "分布式场景下数据不一致",
                "mitigation": "Saga 模式 + 对账机制 + 补偿事务",
                "owner": "架构团队"
            },
            {
                "name": "安全问题",
                "level": "高",
                "description": "安全漏洞导致数据泄露",
                "mitigation": "安全扫描 + 渗透测试 + 加密存储",
                "owner": "安全团队"
            },
        ]

        # 根据领域添加特定风险
        if domain == 'advertising':
            risks.append({
                "name": "预算超投风险",
                "level": "高",
                "description": "并发场景下预算超投",
                "mitigation": "预扣机制 + 本地缓存 + 异步对账",
                "owner": "后端团队"
            })
        elif domain == 'agent':
            risks.append({
                "name": "Token 超支风险",
                "level": "中",
                "description": "长对话导致 Token 超预算",
                "mitigation": "上下文压缩 + Token 限制 + 成本监控",
                "owner": "算法团队"
            })

        return {"risks": risks}

    def _get_scenario_description(self, domain: str) -> str:
        """获取场景描述"""
        descriptions = {
            'advertising': '高并发实时竞价，要求低延迟高吞吐',
            'agent': '多Agent协作，需要灵活编排和记忆管理',
            'ecommerce': '交易核心系统，需要强一致性和高可用',
            'finance': '金融交易系统，需要强一致和严格合规',
            'fullstack': '通用业务系统，需要可扩展和易维护',
        }
        return descriptions.get(domain, '通用业务场景')

    def _extract_sections(self, content: str) -> List[str]:
        """提取章节"""
        return re.findall(r"^##\s+(.+)", content, re.MULTILINE)

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 td_skill_v3.py <prd_file>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        content = f.read()
    skill = TDSkillV3({"language": "go"})
    result = skill.run({"prd_content": content})
    print(result.output["td_content"])
