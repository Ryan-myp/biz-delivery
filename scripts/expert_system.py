"""
Expert System - 资深专家系统
三层架构：领域知识 + 案例学习 + 专家决策

设计理念:
  - 不只是规则匹配，而是理解业务上下文
  - 从历史案例中学习，持续优化
  - 多维度评估，生成可执行方案
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ExpertCase:
    """专家案例"""
    case_id: str
    domain: str           # 领域: ad/agent/ecommerce/finance
    prd_summary: str      # PRD摘要
    issues_found: List[Dict]  # 发现的问题
    solutions: List[Dict]   # 解决方案
    outcome: str          # 结果: success/failure/unknown
    lessons: List[str]    # 经验教训
    timestamp: datetime


@dataclass
class DomainKnowledge:
    """领域知识"""
    domain: str
    name: str
    best_practices: List[str]
    anti_patterns: List[str]
    risk_patterns: List[str]
    reference_docs: List[str]


class DomainKnowledgeEngine:
    """领域知识引擎 - 从 Ryan 知识库提取专家知识"""

    def __init__(self, kb_path: str = None):
        self.kb_path = Path(kb_path) if kb_path else Path('/Users/yanping.ma/ryan-personal-knowledge')
        self.knowledge = {}
        self._load_knowledge()

    def _load_knowledge(self):
        """加载领域知识"""
        # 广告领域知识
        self.knowledge['advertising'] = DomainKnowledge(
            domain='advertising',
            name='广告技术专家',
            best_practices=[
                '竞价延迟 P99 < 100ms，画像查询 < 5ms',
                '预算追踪使用预扣机制 + 异步同步',
                '降级策略: 画像 → 规则 → 默认出价',
                '反作弊: 设备指纹 + 行为分析 + 实时风控',
                '归因模型: Shapley值 or 马尔可夫链',
            ],
            anti_patterns=[
                '直接拼接 SQL 查询用户 ID',
                '同步阻塞式画像查询',
                '预算追踪使用单一计数器',
                '缺少降级策略的单点依赖',
            ],
            risk_patterns=[
                '高并发下的预算超投',
                '画像服务超时导致整体延迟',
                '模型推理失败无 fallback',
            ],
            reference_docs=[
                'knowledge/advertising/dsp-high-concurrency-design-deep.md',
                'knowledge/advertising/ad-bidding-engine-deep.md',
                'knowledge/advertising/ad-budget-overrun-warning-case-deep.md',
            ]
        )

        # Agent 领域知识
        self.knowledge['agent'] = DomainKnowledge(
            domain='agent',
            name='Agent 架构专家',
            best_practices=[
                'ReAct 模式适合通用任务，Planner 适合复杂多步',
                '记忆系统: 短期(对话) + 长期(向量DB)',
                'Tool 设计遵循幂等性 + 错误处理 + 超时控制',
                '安全 Guardrails: 输入过滤 + 输出审核 + 权限控制',
            ],
            anti_patterns=[
                'Agent 循环无终止条件',
                'Tool 调用无超时控制',
                '记忆检索无缓存',
                'Token 使用无成本控制',
            ],
            risk_patterns=[
                'Prompt Injection 攻击',
                'Tool 调用失败导致状态不一致',
                '长对话 Token 超预算',
            ],
            reference_docs=[
                'knowledge/agent-ai/agent-architecture-deep.md',
                'knowledge/agent-ai/react-deep-dive.md',
                'knowledge/agent-ai/ad-ai-evaluation-security-deep.md',
            ]
        )

        # 电商领域知识
        self.knowledge['ecommerce'] = DomainKnowledge(
            domain='ecommerce',
            name='电商交易专家',
            best_practices=[
                '库存扣减使用预扣 + 异步确认',
                '订单状态机只允许合法转换',
                '支付使用最终一致性 (Saga)',
                '优惠券叠加需要防重入控制',
            ],
            anti_patterns=[
                '库存扣减无并发控制',
                '订单状态随意跳转',
                '支付回调无幂等处理',
            ],
            risk_patterns=[
                '高并发下单导致超卖',
                '支付状态不一致',
                '优惠券被恶意刷取',
            ],
            reference_docs=[
                'knowledge/architecture/ddd-strategic-master.md',
                'knowledge/architecture/compensating-transaction.md',
            ]
        )

        # 金融领域知识
        self.knowledge['finance'] = DomainKnowledge(
            domain='finance',
            name='金融交易专家',
            best_practices=[
                '交易使用强一致性 (本地事务)',
                '金额使用 Decimal 或整数(分)',
                '操作日志不可篡改',
                '风控规则 + 模型双引擎',
            ],
            anti_patterns=[
                '交易使用浮点数计算',
                '缺少操作审计日志',
                '风控规则硬编码',
            ],
            risk_patterns=[
                '资金安全漏洞',
                '合规风险',
                '数据泄露',
            ],
            reference_docs=[
                'knowledge/architecture/cqrs-master.md',
                'knowledge/architecture/event-driven-microservice-source.md',
            ]
        )

        # 全栈领域知识
        self.knowledge['fullstack'] = DomainKnowledge(
            domain='fullstack',
            name='全栈架构专家',
            best_practices=[
                '微服务按业务能力划分',
                '缓存策略: 本地 → Redis → DB',
                '数据库读写分离 + 分库分表',
                '容灾: 多可用区 + 异地多活',
            ],
            anti_patterns=[
                '服务间紧耦合调用',
                '缓存穿透/击穿/雪崩无防护',
                '单点数据库瓶颈',
            ],
            risk_patterns=[
                '数据库连接池耗尽',
                '缓存雪崩导致数据库宕机',
                '服务级联故障',
            ],
            reference_docs=[
                'knowledge/architecture/microservice-patterns.md',
                'knowledge/fullstack/backend-performance-optimization-deep.md',
            ]
        )

        # 云原生领域知识
        self.knowledge['cloud_native'] = DomainKnowledge(
            domain='cloud_native',
            name='云原生架构专家',
            best_practices=[
                '容器化部署: Docker + Kubernetes',
                '服务网格: Istio/Linkerd 流量管理',
                '不可变基础设施: GitOps + ArgoCD',
                '可观测性: Prometheus + Grafana + Jaeger',
            ],
            anti_patterns=[
                '直接操作生产环境',
                '无资源配置限制',
                '硬编码配置',
            ],
            risk_patterns=[
                '节点故障导致服务不可用',
                '网络策略配置错误',
                '存储类不支持持久化',
            ],
            reference_docs=[
                'knowledge/kubernetes/kubernetes-best-practices.md',
                'knowledge/cloud-native/cloud-native-patterns.md',
            ]
        )

        # DevOps 领域知识
        self.knowledge['devops'] = DomainKnowledge(
            domain='devops',
            name='DevOps 专家',
            best_practices=[
                'CI/CD: 流水线自动化 + 蓝绿部署',
                '基础设施即代码: Terraform + Ansible',
                '监控告警: 多层监控 + 智能告警',
                '混沌工程: 定期故障演练',
            ],
            anti_patterns=[
                '手动部署生产环境',
                '无回滚机制',
                '监控缺失',
            ],
            risk_patterns=[
                '部署失败导致服务中断',
                '配置漂移',
                '告警疲劳',
            ],
            reference_docs=[
                'knowledge/devops/ci-cd-pipeline-guide.md',
                'knowledge/infra/infrastructure-as-code.md',
            ]
        )

        # 数据工程领域知识
        self.knowledge['data_engineering'] = DomainKnowledge(
            domain='data_engineering',
            name='数据工程专家',
            best_practices=[
                '批流一体: Spark + Flink',
                '数据湖: Delta Lake / Iceberg',
                '实时计算: Kafka + ClickHouse',
                '数据质量: 数据血缘 + 质量监控',
            ],
            anti_patterns=[
                'ETL 同步阻塞',
                '数据孤岛',
                '缺少数据质量监控',
            ],
            risk_patterns=[
                '数据延迟导致决策失误',
                '数据质量差',
                '存储成本失控',
            ],
            reference_docs=[
                'knowledge/bigdata/big-data-architecture.md',
                'knowledge/clickhouse/clickhouse-optimization.md',
            ]
        )

        # 安全工程领域知识
        self.knowledge['security'] = DomainKnowledge(
            domain='security',
            name='安全工程专家',
            best_practices=[
                '零信任架构: 持续验证 + 最小权限',
                '加密存储: AES-256 + 密钥轮换',
                '安全审计: 操作日志 + 异常检测',
                '漏洞管理: 定期扫描 + 修复跟踪',
            ],
            anti_patterns=[
                '硬编码密钥',
                '明文存储敏感数据',
                '缺少访问控制',
            ],
            risk_patterns=[
                '数据泄露',
                '权限提升攻击',
                '供应链攻击',
            ],
            reference_docs=[
                'knowledge/security/security-best-practices.md',
                'knowledge/jwt/jwt-security-guide.md',
            ]
        )

        # ML 工程领域知识
        self.knowledge['ml_ops'] = DomainKnowledge(
            domain='ml_ops',
            name='ML 工程专家',
            best_practices=[
                '模型训练: 分布式训练 + 超参优化',
                '模型服务: ONNX + Triton Inference Server',
                '模型监控: 数据漂移 + 性能衰减',
                'MLOps: MLflow + Kubeflow',
            ],
            anti_patterns=[
                '模型版本混乱',
                '无 A/B 测试框架',
                '缺少模型监控',
            ],
            risk_patterns=[
                '模型退化',
                '推理延迟超标',
                '训练数据泄露',
            ],
            reference_docs=[
                'knowledge/ml/ml-production-guide.md',
                'knowledge/agent-ai/llm-inference-optimization.md',
            ]
        )

        # 游戏平台领域知识
        self.knowledge['gaming'] = DomainKnowledge(
            domain='gaming',
            name='游戏平台专家',
            best_practices=[
                '实时对战: WebSocket + 状态同步',
                '匹配系统: ELO/MMR 算法',
                '反作弊: 客户端校验 + 服务端验证',
                '全球加速: CDN + 边缘计算',
            ],
            anti_patterns=[
                '纯客户端逻辑',
                '无心跳检测',
                '缺少防作弊机制',
            ],
            risk_patterns=[
                '延迟导致游戏体验差',
                '外挂破坏平衡',
                '服务器过载',
            ],
            reference_docs=[
                'knowledge/gaming/game-server-architecture.md',
                'knowledge/network/network-optimization.md',
            ]
        )

        # IoT 领域知识
        self.knowledge['iot'] = DomainKnowledge(
            domain='iot',
            name='IoT 专家',
            best_practices=[
                '设备管理: 统一设备注册 + 认证',
                '边缘计算: 本地决策 + 云端同步',
                '协议适配: MQTT + CoAP + HTTP',
                '数据上报: 批量上传 + 断点续传',
            ],
            anti_patterns=[
                '直连云端',
                '无离线处理',
                '协议混用无适配层',
            ],
            risk_patterns=[
                '设备掉线',
                '数据丢失',
                '协议不兼容',
            ],
            reference_docs=[
                'knowledge/iot/iot-platform-design.md',
                'knowledge/messaging/mqtt-protocol-guide.md',
            ]
        )

        # SaaS 领域知识
        self.knowledge['saas'] = DomainKnowledge(
            domain='saas',
            name='SaaS 架构专家',
            best_practices=[
                '多租户: 数据库隔离 + 行级权限',
                '订阅计费: Stripe/Braintree 集成',
                '租户隔离: 虚拟主机 / 独立数据库',
                'SLA 保障: 多区域部署 + 自动故障转移',
            ],
            anti_patterns=[
                '租户数据混存无隔离',
                '硬编码租户配置',
                '缺少用量计量',
            ],
            risk_patterns=[
                '租户数据泄露',
                '计费错误',
                '单租户影响其他租户',
            ],
            reference_docs=[
                'knowledge/saas/multi-tenant-architecture.md',
                'knowledge/architecture/tenancy-patterns.md',
            ]
        )

        # 社交网络领域知识
        self.knowledge['social'] = DomainKnowledge(
            domain='social',
            name='社交网络专家',
            best_practices=[
                'Feed 流: 推拉结合 (Fan-out on write/read)',
                '即时消息: WebSocket + 消息持久化',
                '关系存储: Neo4j / 图数据库',
                '内容分发: CDN + 边缘缓存',
            ],
            anti_patterns=[
                '全量拉取 Feed',
                '无消息去重',
                '关系查询无索引',
            ],
            risk_patterns=[
                'Feed 延迟高',
                '消息重复/丢失',
                '热门内容撑爆数据库',
            ],
            reference_docs=[
                'knowledge/social/feed-system-design.md',
                'knowledge/database/graph-database-guide.md',
            ]
        )

        # 物流供应链领域知识
        self.knowledge['logistics'] = DomainKnowledge(
            domain='logistics',
            name='物流供应链专家',
            best_practices=[
                '路径优化: 遗传算法 + 实时路况',
                '仓储管理: WMS + 自动拣货',
                '轨迹追踪: GPS + 地理围栏',
                '供需预测: 时间序列 + 机器学习',
            ],
            anti_patterns=[
                '人工排线',
                '无实时轨迹更新',
                '库存数据滞后',
            ],
            risk_patterns=[
                '配送延误',
                '货物丢失',
                '库存不准',
            ],
            reference_docs=[
                'knowledge/logistics/supply-chain-optimization.md',
                'knowledge/algorithm/path-finding-algorithms.md',
            ]
        )

    def get_domain_knowledge(self, domain: str) -> Optional[DomainKnowledge]:
        """获取领域知识"""
        return self.knowledge.get(domain)

    def search_related_cases(self, domain: str, query: str) -> List[Dict]:
        """搜索相关案例"""
        # 这里可以扩展为从知识库搜索
        return []


class CaseLearningEngine:
    """案例学习引擎 - 从历史案例中学习"""

    def __init__(self, cases_path: str = None):
        self.cases_path = Path(cases_path) if cases_path else Path('/Users/yanping.ma/biz-delivery/knowledge/cases')
        self.cases_path.mkdir(parents=True, exist_ok=True)
        self.cases: List[ExpertCase] = []
        self._load_cases()

    def _load_cases(self):
        """加载历史案例"""
        case_files = list(self.cases_path.glob('*.json'))
        for case_file in case_files:
            try:
                with open(case_file) as f:
                    data = json.load(f)
                    case = ExpertCase(
                        case_id=data.get('case_id', ''),
                        domain=data.get('domain', ''),
                        prd_summary=data.get('prd_summary', ''),
                        issues_found=data.get('issues_found', []),
                        solutions=data.get('solutions', []),
                        outcome=data.get('outcome', 'unknown'),
                        lessons=data.get('lessons', []),
                        timestamp=datetime.fromisoformat(data.get('timestamp', '')),
                    )
                    self.cases.append(case)
            except Exception:
                continue

    def save_case(self, case: ExpertCase):
        """保存案例"""
        case_file = self.cases_path / f"{case.case_id}.json"
        data = {
            'case_id': case.case_id,
            'domain': case.domain,
            'prd_summary': case.prd_summary,
            'issues_found': case.issues_found,
            'solutions': case.solutions,
            'outcome': case.outcome,
            'lessons': case.lessons,
            'timestamp': case.timestamp.isoformat(),
        }
        with open(case_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_similar_cases(self, domain: str, issue_type: str, limit: int = 5) -> List[ExpertCase]:
        """获取相似案例"""
        similar = []
        for case in self.cases:
            if case.domain == domain:
                # 简单匹配：检查 issue type
                for issue in case.issues_found:
                    if issue_type in issue.get('name', '') or issue_type in issue.get('message', ''):
                        similar.append(case)
                        break
        return similar[:limit]

    def get_success_patterns(self, domain: str) -> List[str]:
        """获取成功模式"""
        patterns = []
        for case in self.cases:
            if case.domain == domain and case.outcome == 'success':
                patterns.extend(case.lessons)
        return list(set(patterns))[:10]

    def get_failure_patterns(self, domain: str) -> List[str]:
        """获取失败模式"""
        patterns = []
        for case in self.cases:
            if case.domain == domain and case.outcome == 'failure':
                patterns.extend(case.lessons)
        return list(set(patterns))[:10]


class ExpertDecisionEngine:
    """专家决策引擎 - 生成专家级判断"""

    def __init__(self, knowledge_engine: DomainKnowledgeEngine, case_engine: CaseLearningEngine):
        self.kb = knowledge_engine
        self.cases = case_engine

    def analyze_prd(self, prd_content: str, domain: str) -> Dict:
        """PRD 专家分析"""
        domain_kb = self.kb.get_domain_knowledge(domain)
        if not domain_kb:
            return {'analysis': '未知领域', 'recommendations': []}

        analysis = {
            'domain': domain,
            'business_value': self._analyze_business_value(prd_content, domain),
            'technical_feasibility': self._analyze_technical_feasibility(prd_content, domain),
            'risk_assessment': self._assess_risks(prd_content, domain),
            'optimization_suggestions': self._generate_suggestions(prd_content, domain),
        }

        return analysis

    def _analyze_business_value(self, prd: str, domain: str) -> Dict:
        """分析业务价值"""
        # 检查是否有量化指标
        has_metrics = bool(re.search(r'[≤<>]=?\s*\d+\s*(%|ms|s|QPS|万|亿)', prd))

        # 检查目标用户
        has_user = bool(re.search(r'(用户|客户|商家|广告主|开发者)', prd))

        # 检查商业价值
        has_value = bool(re.search(r'(收入|成本|效率|转化率|ROI)', prd))

        return {
            'has_quantified_metrics': has_metrics,
            'has_target_user': has_user,
            'has_business_value': has_value,
            'score': sum([has_metrics, has_user, has_value]) * 33,
            'recommendation': self._get_value_recommendation(has_metrics, has_user, has_value),
        }

    def _get_value_recommendation(self, has_metrics: bool, has_user: bool, has_value: bool) -> str:
        """获取价值建议"""
        if has_metrics and has_user and has_value:
            return "✅ 业务价值清晰，指标可量化"
        elif has_metrics and has_user:
            return "⚠️ 建议补充商业价值说明"
        elif has_metrics:
            return "⚠️ 建议明确目标用户和商业价值"
        else:
            return "❌ 需补充业务背景、目标用户和价值量化"

    def _analyze_technical_feasibility(self, prd: str, domain: str) -> Dict:
        """分析技术可行性"""
        domain_kb = self.kb.get_domain_knowledge(domain)

        # 检查是否提到关键技术点
        checked_items = []
        if domain == 'advertising':
            checked_items = [
                ('竞价延迟', r'(?i)(延迟|latency|P99|<\s*\d+\s*ms)'),
                ('预算追踪', r'(?i)(预算|budget|预扣)'),
                ('降级策略', r'(?i)(降级|fallback|容灾)'),
            ]
        elif domain == 'agent':
            checked_items = [
                ('Agent模式', r'(?i)(ReAct|Planner|Multi-Agent)'),
                ('记忆系统', r'(?i)(记忆|memory|上下文)'),
                ('Tool设计', r'(?i)(Tool|工具|Function.*Calling)'),
            ]
        elif domain == 'ecommerce':
            checked_items = [
                ('并发控制', r'(?i)(并发|锁|分布式)'),
                ('一致性', r'(?i)(一致| Saga |TCC|事务)'),
                ('幂等', r'(?i)(幂等|idempotent)'),
            ]
        elif domain == 'finance':
            checked_items = [
                ('一致性', r'(?i)(一致|事务|ACID)'),
                ('安全', r'(?i)(安全|加密|脱敏)'),
                ('审计', r'(?i)(审计|日志|trace)'),
            ]

        results = []
        for name, pattern in checked_items:
            found = bool(re.search(pattern, prd))
            results.append({
                'item': name,
                'covered': found,
                'reference': domain_kb.best_practices[0] if domain_kb.best_practices else ''
            })

        covered_count = sum(1 for r in results if r['covered'])
        return {
            'items_checked': results,
            'coverage_rate': covered_count / len(results) if results else 0,
            'feasibility': '高' if covered_count == len(results) else '中' if covered_count > len(results) * 0.5 else '低',
        }

    def _assess_risks(self, prd: str, domain: str) -> List[Dict]:
        """风险评估"""
        domain_kb = self.kb.get_domain_knowledge(domain)
        risks = []

        if domain_kb:
            # 添加领域风险
            for risk in domain_kb.risk_patterns[:3]:
                risks.append({
                    'type': 'domain',
                    'risk': risk,
                    'level': '高' if '超投' in risk or '泄漏' in risk else '中',
                    'mitigation': self._get_mitigation(risk, domain),
                })

            # 检查 PRD 是否提到了风险应对
            if not re.search(r'(?i)(风险|预案|降级|容灾|backup)', prd):
                risks.append({
                    'type': 'missing',
                    'risk': 'PRD 未提及风险预案',
                    'level': '高',
                    'mitigation': '添加风险评估和应急预案章节',
                })

        return risks

    def _get_mitigation(self, risk: str, domain: str) -> str:
        """获取风险缓解措施"""
        mitigations = {
            'advertising': {
                '超投': '使用预扣机制 + 本地缓存 + 异步对账',
                '延迟': '优化查询路径，画像本地缓存，模型推理并行',
                '降级': '设计多级降级：画像→规则→默认出价',
            },
            'agent': {
                'Injection': '输入过滤 + 输出审核 + 权限控制',
                '超时': 'Tool 调用设置超时 + 重试策略',
                'Token': '上下文压缩 + 模型分级 + 成本监控',
            },
            'ecommerce': {
                '超卖': '库存预扣 + 分布式锁 + 异步确认',
                '不一致': 'Saga 模式 + 对账机制',
            },
            'finance': {
                '安全': '加密存储 + 传输 TLS + 审计日志',
                '合规': '数据脱敏 + 权限控制 + 操作审计',
            }
        }

        domain_mits = mitigations.get(domain, {})
        for key, mit in domain_mits.items():
            if key in risk:
                return mit

        return "根据领域最佳实践设计缓解方案"

    def _generate_suggestions(self, prd: str, domain: str) -> List[Dict]:
        """生成优化建议"""
        suggestions = []
        domain_kb = self.kb.get_domain_knowledge(domain)

        # 基于反模式检查
        if domain_kb:
            for anti_pattern in domain_kb.anti_patterns[:3]:
                if self._check_anti_pattern(prd, anti_pattern):
                    suggestions.append({
                        'type': 'anti_pattern',
                        'issue': anti_pattern,
                        'suggestion': f"避免 {anti_pattern}，参考最佳实践",
                        'reference': domain_kb.reference_docs[0] if domain_kb.reference_docs else '',
                    })

        # 基于成功案例
        success_patterns = self.cases.get_success_patterns(domain)
        for pattern in success_patterns[:2]:
            suggestions.append({
                'type': 'best_practice',
                'issue': '可参考的成功经验',
                'suggestion': pattern,
                'reference': '',
            })

        return suggestions

    def _check_anti_pattern(self, prd: str, anti_pattern: str) -> bool:
        """检查是否违反反模式"""
        # 简单检查：如果 PRD 中没有提到相关关键词，可能违反
        keywords = anti_pattern.split()[:2]
        return not any(kw.lower() in prd.lower() for kw in keywords)

    def generate_review_report(self, analysis: Dict, domain: str) -> str:
        """生成审查报告"""
        lines = [
            f"# 🎯 {domain.upper()} 领域专家 PRD 审查报告",
            "",
            f"**审查时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
        ]

        # 业务价值分析
        value = analysis.get('business_value', {})
        lines.extend([
            "## 一、业务价值评估",
            "",
            f"- **目标用户**: {'✅ 已定义' if value.get('has_target_user') else '❌ 缺失'}",
            f"- **量化指标**: {'✅ 已定义' if value.get('has_quantified_metrics') else '❌ 缺失'}",
            f"- **商业价值**: {'✅ 已说明' if value.get('has_business_value') else '❌ 缺失'}",
            f"- **综合评分**: {value.get('score', 0)}/100",
            "",
            f"**建议**: {value.get('recommendation', '')}",
            "",
        ])

        # 技术可行性
        tech = analysis.get('technical_feasibility', {})
        lines.extend([
            "## 二、技术可行性评估",
            "",
            f"- **关键项覆盖率**: {tech.get('coverage_rate', 0):.0%}",
            f"- **可行性评级**: {tech.get('feasibility', '未知')}",
            "",
        ])

        for item in tech.get('items_checked', []):
            status = "✅" if item['covered'] else "❌"
            lines.append(f"- {status} {item['item']}")

        lines.extend([
            "",
            "## 三、风险评估",
            "",
        ])

        for risk in analysis.get('risk_assessment', [])[:5]:
            level_icon = "🔴" if risk['level'] == '高' else "🟡"
            lines.append(f"- {level_icon} **{risk['risk']}** ({risk['level']})")
            lines.append(f"  - 💡 缓解: {risk['mitigation']}")

        lines.extend([
            "",
            "## 四、优化建议",
            "",
        ])

        for sug in analysis.get('optimization_suggestions', [])[:5]:
            icon = "⚠️" if sug['type'] == 'anti_pattern' else "💡"
            lines.append(f"- {icon} {sug['suggestion']}")
            if sug.get('reference'):
                lines.append(f"  - 📚 参考: [{sug['reference']}]()")

        lines.extend([
            "",
            "---",
            "",
            f"*报告由资深专家系统生成 | 领域: {domain}*",
        ])

        return "\n".join(lines)


class SeniorExpertSystem:
    """资深专家系统入口"""

    def __init__(self, kb_path: str = None):
        self.kb_engine = DomainKnowledgeEngine(kb_path)
        self.case_engine = CaseLearningEngine()
        self.decision_engine = ExpertDecisionEngine(self.kb_engine, self.case_engine)

    def review(self, prd_content: str, domain: str = None) -> Dict:
        """执行专家审查"""
        # 如果没有指定领域，自动检测
        if not domain:
            domain = self._detect_domain(prd_content)

        # 执行分析
        analysis = self.decision_engine.analyze_prd(prd_content, domain)

        # 生成报告
        report = self.decision_engine.generate_review_report(analysis, domain)

        return {
            'success': True,
            'domain': domain,
            'analysis': analysis,
            'report': report,
            'timestamp': datetime.now().isoformat(),
        }

    def _detect_domain(self, prd: str) -> str:
        """检测领域"""
        scores = {
            'advertising': 0,
            'agent': 0,
            'ecommerce': 0,
            'finance': 0,
            'fullstack': 0,
            'cloud_native': 0,
            'devops': 0,
            'data_engineering': 0,
            'security': 0,
            'ml_ops': 0,
            'gaming': 0,
            'iot': 0,
            'saas': 0,
            'social': 0,
            'logistics': 0,
        }

        # 广告关键词
        for kw in ['竞价', 'RTB', 'DSP', 'SSP', '广告', '出价', '曝光', '点击', '归因', 'ROI']:
            if kw in prd:
                scores['advertising'] += 1

        # Agent 关键词
        for kw in ['Agent', 'LLM', 'RAG', 'ReAct', '记忆', 'Tool']:
            if kw in prd:
                scores['agent'] += 1

        # 电商关键词
        for kw in ['订单', '商品', '库存', '支付', '购物车', '优惠券']:
            if kw in prd:
                scores['ecommerce'] += 1

        # 金融关键词
        for kw in ['交易', '账户', '风控', '合规', '清算']:
            if kw in prd:
                scores['finance'] += 1

        # 云原生关键词
        for kw in ['Kubernetes', 'K8s', '容器', 'Docker', 'Istio', '服务网格', 'Helm']:
            if kw in prd:
                scores['cloud_native'] += 1

        # DevOps 关键词
        for kw in ['CI/CD', 'Jenkins', 'ArgoCD', 'GitOps', 'Terraform', '流水线', '部署']:
            if kw in prd:
                scores['devops'] += 1

        # 数据工程关键词
        for kw in ['Spark', 'Flink', 'Kafka', 'ClickHouse', '数据湖', 'ETL', '实时计算']:
            if kw in prd:
                scores['data_engineering'] += 1

        # 安全关键词
        for kw in ['加密', 'JWT', 'OAuth', '零信任', '安全', '权限', '审计', '漏洞']:
            if kw in prd:
                scores['security'] += 1

        # ML 关键词
        for kw in ['模型', '训练', '推理', 'MLflow', '特征', 'A/B测试', '漂移']:
            if kw in prd:
                scores['ml_ops'] += 1

        # 游戏关键词
        for kw in ['游戏', '对战', '匹配', 'ELO', '反作弊', '帧同步', '状态同步']:
            if kw in prd:
                scores['gaming'] += 1

        # IoT 关键词
        for kw in ['IoT', '设备', 'MQTT', '边缘计算', '传感器', '固件', 'OTA']:
            if kw in prd:
                scores['iot'] += 1

        # SaaS 关键词
        for kw in ['多租户', 'SaaS', '订阅', '计费', '隔离', 'SLA']:
            if kw in prd:
                scores['saas'] += 1

        # 社交关键词
        for kw in ['Feed', '信息流', '关注', '社交', '关系', '即时消息', 'WebSocket']:
            if kw in prd:
                scores['social'] += 1

        # 物流关键词
        for kw in ['物流', '配送', '仓储', '路径优化', '轨迹', 'WMS', 'GPS']:
            if kw in prd:
                scores['logistics'] += 1

        # 默认全栈
        max_score = max(scores.values())
        if max_score == 0:
            return 'fullstack'

        return max(scores, key=scores.get)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 expert_system.py <prd_file>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        prd_content = f.read()

    expert = SeniorExpertSystem()
    result = expert.review(prd_content)

    print(result['report'])
    print()
    print(f"领域: {result['domain']}")
    print(f"分析时间: {result['timestamp']}")
