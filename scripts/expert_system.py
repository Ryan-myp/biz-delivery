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
from scripts.performance_optimizer import get_optimizer
from scripts.ryan_kb_loader import get_kb
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
                'knowledge/infra/kubernetes-scheduler-source.md',
                'knowledge/mesh/service-mesh-istio-deep.md',
                'knowledge/devops/k8s-helm-deep.md',
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
                'knowledge/devops/k8s-production-deep.md',
                'knowledge/infra/docker-storage-driver.md',
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
                'knowledge/bigdata/data-warehouse-deep.md',
                'knowledge/big-data/realtime-data-pipeline-deep.md',
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
                'knowledge/security/security-architecture-deep.md',
                'knowledge/jwt/jwt-authentication-deep.md',
                'knowledge/https/https-security-deep-dive.md',
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
                'knowledge/ml/ml-system-architecture-deep.md',
                'knowledge/ml/model-serving-deep.md',
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
                'knowledge/network/websocket-realtime-deep.md',
                'knowledge/algorithm/graph-algorithms-deep.md',
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
                'knowledge/middleware/rabbitmq-nats-deep.md',
                'knowledge/middleware/message-queue-design.md',
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
                'knowledge/前沿/saas-agent-trend-deep.md',
                'knowledge/前沿/saas-agent-2026-deep.md',
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
                'knowledge/archive/versioned/neo4j-graph-db-deep-v2_1786438150.md',
                'knowledge/middleware/message-queue-advanced.md',
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
                'knowledge/security/zero-trust-mtls-supply-chain.md',
                'knowledge/algorithm/graph-algorithms-deep.md',
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
        # 提取主领域 (处理跨领域如 finance+security)
        primary_domain = domain.split('+')[0] if '+' in domain else domain
        domain_kb = self.kb.get_domain_knowledge(primary_domain)
        if not domain_kb:
            return {'analysis': '未知领域', 'recommendations': []}

        analysis = {
            'domain': domain,
            'business_value': self._analyze_business_value(prd_content, primary_domain),
            'technical_feasibility': self._analyze_technical_feasibility(prd_content, primary_domain),
            'risk_assessment': self._assess_risks(prd_content, primary_domain),
            'optimization_suggestions': self._generate_suggestions(prd_content, primary_domain),
            'knowledge_references': self._get_kb_references(prd_content, primary_domain),
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
        # 提取主领域 (处理跨领域如 finance+security)
        primary_domain = domain.split('+')[0] if '+' in domain else domain
        domain_kb = self.kb.get_domain_knowledge(primary_domain)

        # 检查是否提到关键技术点 - 所有15个领域
        checked_items = []
        if primary_domain == 'advertising':
            checked_items = [
                ('竞价延迟', r'(?i)(延迟|latency|P99|<\s*\d+\s*ms)'),
                ('预算追踪', r'(?i)(预算|budget|预扣)'),
                ('降级策略', r'(?i)(降级|fallback|容灾)'),
                ('反作弊', r'(?i)(作弊|fraud|反作弊)'),
            ]
        elif primary_domain == 'agent':
            checked_items = [
                ('Agent模式', r'(?i)(ReAct|Planner|Multi-Agent)'),
                ('记忆系统', r'(?i)(记忆|memory|上下文)'),
                ('Tool设计', r'(?i)(Tool|工具|Function.*Calling)'),
                ('安全Guardrails', r'(?i)(安全|guardrail|限制)'),
            ]
        elif primary_domain == 'ecommerce':
            checked_items = [
                ('并发控制', r'(?i)(并发|锁|分布式)'),
                ('一致性', r'(?i)(一致| Saga |TCC|事务)'),
                ('幂等', r'(?i)(幂等|idempotent)'),
                ('库存管理', r'(?i)(库存|pre扣|超卖)'),
            ]
        elif primary_domain == 'finance':
            checked_items = [
                ('一致性', r'(?i)(一致|事务|ACID)'),
                ('安全', r'(?i)(安全|加密|脱敏)'),
                ('审计', r'(?i)(审计|日志|trace)'),
                ('合规', r'(?i)(合规|regulatory|监管)'),
            ]
        elif primary_domain == 'cloud_native':
            checked_items = [
                ('资源限制', r'(?i)(limit|request|资源限制)'),
                ('健康检查', r'(?i)(liveness|readiness|probe)'),
                ('服务网格', r'(?i)(istio|mesh|熔断|重试)'),
                ('多可用区', r'(?i)(可用区|AZ|multi.*zone)'),
            ]
        elif primary_domain == 'devops':
            checked_items = [
                ('CI/CD', r'(?i)(CI/CD|Jenkins|GitLab|流水线)'),
                ('GitOps', r'(?i)(GitOps|ArgoCD|Flux)'),
                ('回滚策略', r'(?i)(回滚|rollback|蓝绿|灰度)'),
                ('监控告警', r'(?i)(Prometheus|Grafana|告警|alert)'),
            ]
        elif primary_domain == 'data_engineering':
            checked_items = [
                ('批流一体', r'(?i)(Spark|Flink|批流)'),
                ('数据质量', r'(?i)(质量|血缘|校验)'),
                ('实时计算', r'(?i)(实时|Kafka|流计算)'),
                ('成本优化', r'(?i)(成本|压缩|冷热分离)'),
            ]
        elif primary_domain == 'security':
            checked_items = [
                ('零信任', r'(?i)(零信任|zero.*trust|持续验证)'),
                ('加密存储', r'(?i)(加密|AES|密钥|Vault)'),
                ('访问控制', r'(?i)(RBAC|权限|最小权限)'),
                ('审计日志', r'(?i)(审计|log|不可篡改)'),
            ]
        elif primary_domain == 'ml_ops':
            checked_items = [
                ('模型服务', r'(?i)(模型服务|Triton|ONNX|推理服务)'),
                ('特征存储', r'(?i)(特征|feature.*store|特征库)'),
                ('漂移监控', r'(?i)(漂移|drift|监控|衰减)'),
                ('A/B测试', r'(?i)(A/B|abtest|实验平台)'),
            ]
        elif primary_domain == 'gaming':
            checked_items = [
                ('帧同步', r'(?i)(帧同步|state.*sync|确定性的)'),
                ('反作弊', r'(?i)(反作弊|anti.*cheat|外挂|检测)'),
                ('心跳检测', r'(?i)(心跳|heartbeat|keepalive)'),
                ('匹配算法', r'(?i)(ELO|MMR|匹配|ranking)'),
            ]
        elif primary_domain == 'iot':
            checked_items = [
                ('MQTT', r'(?i)(MQTT|CoAP|协议)'),
                ('边缘计算', r'(?i)(边缘|edge|本地计算)'),
                ('设备管理', r'(?i)(设备|OTA|固件|版本)'),
                ('断点续传', r'(?i)(断点|续传|缓存|离线)'),
            ]
        elif primary_domain == 'saas':
            checked_items = [
                ('多租户隔离', r'(?i)(租户|tenant|隔离|行级权限)'),
                ('订阅计费', r'(?i)(订阅|billing|Stripe|计费)'),
                ('SLA保障', r'(?i)(SLA|可用性|99\.\d+|故障转移)'),
                ('用量计量', r'(?i)(用量|metering|限流|配额)'),
            ]
        elif primary_domain == 'social':
            checked_items = [
                ('Feed流', r'(?i)(Feed|信息流|pull.*push|fanout)'),
                ('即时消息', r'(?i)(即时|websocket|消息|IM)'),
                ('关系存储', r'(?i)(关系|graph|neo4j|图数据库)'),
                ('CDN分发', r'(?i)(CDN|边缘|缓存|分发)'),
            ]
        elif primary_domain == 'logistics':
            checked_items = [
                ('路径优化', r'(?i)(路径|routing|遗传算法|调度)'),
                ('轨迹追踪', r'(?i)(轨迹|GPS|定位|实时追踪)'),
                ('仓储管理', r'(?i)(仓储|WMS|拣货|库存)'),
                ('需求预测', r'(?i)(预测|time.*series|机器学习|需求)'),
            ]
        else:  # fullstack or cross-domain
            checked_items = [
                ('架构设计', r'(?i)(架构|design|pattern)'),
                ('性能指标', r'(?i)(性能|performance|P99|QPS|延迟)'),
                ('容灾方案', r'(?i)(容灾|降级|备份|高可用)'),
                ('监控告警', r'(?i)(监控|monitor|告警|alert)'),
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
        """风险评估 - 增强版"""
        domain_kb = self.kb.get_domain_knowledge(domain)
        risks = []

        if domain_kb:
            # 添加领域风险
            for risk in domain_kb.risk_patterns[:3]:
                risks.append({
                    'type': 'domain',
                    'risk': risk,
                    'level': self._assess_risk_level(risk, domain),
                    'mitigation': self._get_mitigation(risk, domain),
                })

        # 基于PRD内容检测风险
        risk_detectors = self._get_risk_detectors(domain)
        for detector in risk_detectors:
            matched_risks = detector(prd)  # 直接调用函数
            for risk in matched_risks:
                # 避免重复
                if not any(r['risk'] == risk['risk'] for r in risks):
                    risks.append(risk)

        # 检查是否提到风险应对
        if not re.search(r'(?i)(风险|预案|降级|容灾|backup|fallback)', prd):
            risks.append({
                'type': 'missing',
                'risk': 'PRD未提及风险预案和降级策略',
                'level': '高',
                'mitigation': '添加风险评估章节，设计降级和容灾方案',
            })

        # 检查是否提到监控
        if not re.search(r'(?i)(监控|monitor|告警|alert|观测|observ)', prd):
            risks.append({
                'type': 'missing',
                'risk': 'PRD未提及监控告警方案',
                'level': '中',
                'mitigation': '添加监控告警设计，包括指标采集和异常告警',
            })

        return risks[:5]  # 最多返回5个风险

    def _assess_risk_level(self, risk: str, domain: str) -> str:
        """评估风险等级"""
        high_risk_keywords = ['超投', '泄漏', '资金', '安全', '一致']
        for kw in high_risk_keywords:
            if kw in risk:
                return '高'
        return '中'

    def _get_risk_detectors(self, domain: str) -> List:
        """获取风险检测器"""
        detectors = {
            'advertising': [
                lambda prd: [{'risk': '竞价延迟导致流量丢失', 'level': '高', 'mitigation': '优化查询路径，本地缓存画像'}] if '延迟' in prd or 'P99' in prd else [],
                lambda prd: [{'risk': '预算超投风险', 'level': '高', 'mitigation': '使用预扣机制+异步对账'}] if '预算' in prd and '预扣' not in prd else [],
            ],
            'agent': [
                lambda prd: [{'risk': 'Token成本失控', 'level': '中', 'mitigation': '设置Token预算+成本监控'}] if '成本' in prd or 'Token' in prd else [],
                lambda prd: [{'risk': 'Agent循环无终止', 'level': '高', 'mitigation': '设置最大迭代次数+Token限制'}] if '循环' in prd or '迭代' in prd else [],
            ],
            'ecommerce': [
                lambda prd: [{'risk': '超卖风险', 'level': '高', 'mitigation': 'Redis原子扣减+分布式锁'}] if '库存' in prd and '预扣' not in prd else [],
                lambda prd: [{'risk': '并发下单超时', 'level': '高', 'mitigation': '异步订单处理+消息队列'}] if '并发' in prd or 'QPS' in prd else [],
            ],
            'finance': [
                lambda prd: [{'risk': '资金安全风险', 'level': '高', 'mitigation': '加密存储+操作审计+双因素认证'}] if '资金' in prd or '支付' in prd else [],
                lambda prd: [{'risk': '数据一致性风险', 'level': '高', 'mitigation': 'Saga模式+对账机制'}] if '一致' in prd and 'Saga' not in prd else [],
            ],
        }
        return detectors.get(domain, [])

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
            },
            'cloud_native': {
                '节点故障': '多可用区部署 + Pod 副本 + 自动恢复',
                '网络异常': '服务网格熔断 + 重试 + 超时',
                '存储问题': 'PV/PVC 分离 + 备份策略',
            },
            'devops': {
                '部署失败': '蓝绿部署 + 自动回滚 + 灰度发布',
                '配置漂移': 'GitOps + 声明式配置 + 持续比对',
                '告警疲劳': '智能聚合 + 分级告警 + 静默策略',
            },
            'data_engineering': {
                '数据延迟': '流式处理 + 增量计算 + 缓存预热',
                '数据质量': '数据校验 + 血缘追踪 + 质量门禁',
                '存储成本': '冷热分离 + 压缩存储 + 生命周期管理',
            },
            'security': {
                '数据泄露': '加密存储 + 访问控制 + 审计日志',
                '权限提升': '最小权限 + 持续验证 + 微隔离',
                '供应链': '依赖扫描 + 签名验证 + SBOM',
            },
            'ml_ops': {
                '模型退化': '持续监控 + 自动重训练 + A/B 测试',
                '推理延迟': '模型优化 + 缓存 + 边缘推理',
                '数据泄露': '数据脱敏 + 访问控制 + 审计',
            },
            'gaming': {
                '延迟高': '服务端权威 + 客户端预测 + 插值',
                '外挂': '客户端校验 + 服务端验证 + 行为分析',
                '服务器过载': '弹性扩容 + 负载均衡 + 限流',
            },
            'iot': {
                '设备掉线': '本地缓存 + 断点续传 + 心跳检测',
                '数据丢失': '边缘缓冲 + 批量上报 + 确认机制',
                '协议不兼容': '统一适配层 + 协议转换 + 标准化',
            },
            'saas': {
                '数据泄露': '行级隔离 + 租户认证 + 审计日志',
                '计费错误': '独立计量 + 对账机制 + 人工复核',
                '单租户影响': '资源配额 + 隔离部署 + 降级策略',
            },
            'social': {
                'Feed 延迟': '混合扩散 + 分页加载 + 预计算',
                '消息重复': '消息 ID 去重 + 幂等处理',
                '数据库压力': '读写分离 + 分库分表 + 缓存',
            },
            'logistics': {
                '配送延误': '实时调度 + 动态路径 + 预警机制',
                '货物丢失': '全程追踪 + 电子封签 + 异常告警',
                '库存不准': '实时同步 + 盘点机制 + 差异分析',
            },
        }

        domain_mits = mitigations.get(domain, {})
        for key, mit in domain_mits.items():
            if key in risk:
                return mit

        return "根据领域最佳实践设计缓解方案"

    def _generate_suggestions(self, prd: str, domain: str) -> List[Dict]:
        """生成优化建议 - 增强版"""
        suggestions = []
        domain_kb = self.kb.get_domain_knowledge(domain)

        # 从真实知识库检索相关内容
        real_kb = get_kb()
        kb_results = real_kb.search(prd[:300], domain, limit=5)

        if kb_results:
            for doc in kb_results:
                suggestions.append({
                    'type': 'knowledge_base',
                    'issue': f"参考知识库: {doc['title']}",
                    'suggestion': doc['summary'][:200] + '...',
                    'reference': f"/ryan-personal-knowledge/{doc['path']}",
                })

        # 基于最佳实践生成建议
        if domain_kb and domain_kb.best_practices:
            for bp in domain_kb.best_practices[:3]:
                suggestions.append({
                    'type': 'best_practice',
                    'issue': '最佳实践',
                    'suggestion': f"遵循: {bp}",
                    'reference': '',
                })

        # 基于反模式检查
        if domain_kb:
            for anti_pattern in domain_kb.anti_patterns[:3]:
                if self._check_anti_pattern(prd, anti_pattern):
                    suggestions.append({
                        'type': 'anti_pattern',
                        'issue': f"避免反模式: {anti_pattern}",
                        'suggestion': f"避免 {anti_pattern}，参考最佳实践",
                        'reference': domain_kb.reference_docs[0] if domain_kb.reference_docs else '',
                    })

        # 基于成功案例
        success_patterns = self.cases.get_success_patterns(domain)
        for pattern in success_patterns[:2]:
            suggestions.append({
                'type': 'success_case',
                'issue': '可参考的成功经验',
                'suggestion': pattern,
                'reference': '',
            })

        # 基于性能指标生成建议
        perf_keywords = ['QPS', '延迟', 'P99', '吞吐量', '并发']
        for kw in perf_keywords:
            if kw in prd or kw.lower() in prd.lower():
                suggestions.append({
                    'type': 'performance',
                    'issue': f'性能指标: {kw}',
                    'suggestion': self._get_performance_suggestion(kw, domain),
                    'reference': '',
                })
                break

        # 基于安全关键词生成建议
        security_keywords = ['安全', '加密', '权限', '审计', '合规']
        for kw in security_keywords:
            if kw in prd:
                suggestions.append({
                    'type': 'security',
                    'issue': f'安全需求: {kw}',
                    'suggestion': self._get_security_suggestion(kw, domain),
                    'reference': '',
                })
                break

        return suggestions[:8]  # 限制建议数量，保证质量

    def _get_performance_suggestion(self, keyword: str, domain: str) -> str:
        """获取性能优化建议"""
        suggestions = {
            'advertising': '竞价引擎优化：本地缓存画像数据，模型推理并行化，异步上报统计',
            'agent': 'Agent优化：上下文压缩，Tool调用批处理，模型分级响应',
            'ecommerce': '高并发优化：Redis预扣库存，消息队列异步落库，限流降级',
            'finance': '交易性能优化：连接池管理，批量处理，缓存热点数据',
            'cloud_native': '云原生优化：HPA自动扩缩容，服务网格熔断重试，镜像优化',
            'gaming': '游戏性能优化：帧同步优化，状态压缩，边缘节点部署',
            'iot': 'IoT性能优化：边缘计算，数据压缩，批量上报',
            'saas': 'SaaS性能优化：多租户隔离，查询优化，缓存策略',
            'social': '社交性能优化：Feed流推拉结合，CDN分发，数据库分片',
            'logistics': '物流性能优化：路径算法优化，实时数据更新，缓存预热',
        }
        return suggestions.get(domain, '根据具体场景进行性能优化')

    def _get_security_suggestion(self, keyword: str, domain: str) -> str:
        """获取安全优化建议"""
        suggestions = {
            'advertising': '广告安全：设备指纹防作弊，API限流防刷，预算追踪审计',
            'agent': 'Agent安全：输入过滤防注入，输出审核，权限最小化',
            'ecommerce': '电商安全：支付加密，用户数据脱敏，防爬虫策略',
            'finance': '金融安全：资金加密存储，操作审计日志，双因素认证',
            'cloud_native': '云原生安全：mTLS服务网格，RBAC权限控制，密钥管理',
            'gaming': '游戏安全：客户端校验，服务端权威，反作弊检测',
            'iot': 'IoT安全：设备认证，数据传输加密，固件签名验证',
            'saas': 'SaaS安全：租户隔离，数据加密，访问审计',
            'social': '社交安全：内容审核，隐私保护，反垃圾策略',
            'logistics': '物流安全：货物追踪，电子封签，异常告警',
        }
        return suggestions.get(domain, '根据具体场景加强安全措施')

    def _get_kb_references(self, prd: str, domain: str) -> List[Dict]:
        """获取知识库引用 - 增强版"""
        real_kb = get_kb()

        # 提取PRD关键词
        keywords = []
        # 中文关键词
        cn_keywords = re.findall(r'[\u4e00-\u9fa5]{2,4}', prd)
        keywords.extend(cn_keywords[:15])
        # 英文关键词
        en_keywords = re.findall(r'\b[a-zA-Z]{3,}\b', prd)
        keywords.extend(en_keywords[:8])

        # 添加领域关键词
        domain_keywords = {
            'advertising': ['竞价', 'RTB', 'DSP', 'SSP', '曝光', '点击', '归因'],
            'agent': ['Agent', 'ReAct', '记忆', 'Tool', 'Prompt'],
            'ecommerce': ['订单', '库存', '支付', '秒杀', '购物车'],
            'finance': ['支付', '交易', '事务', '对账', '风控'],
            'cloud_native': ['Kubernetes', 'Docker', '服务网格', 'Helm'],
            'security': ['加密', 'JWT', 'OAuth', '零信任', '审计'],
            'data_engineering': ['Kafka', 'Flink', 'Spark', '数据湖'],
            'devops': ['CI/CD', 'Jenkins', 'GitOps', 'Terraform'],
            'ml_ops': ['模型', '训练', '推理', '特征', 'A/B测试'],
            'gaming': ['游戏', '对战', '匹配', '反作弊', '帧同步'],
            'iot': ['IoT', 'MQTT', '边缘', '设备', '传感器'],
            'saas': ['多租户', 'SaaS', '订阅', '计费', 'SLA'],
            'social': ['Feed', '社交', '关系', '即时消息', 'WebSocket'],
            'logistics': ['物流', '配送', '仓储', '路径优化', 'GPS'],
        }
        keywords.extend(domain_keywords.get(domain, [])[:5])

        # 去重
        keywords = list(dict.fromkeys(keywords))

        # 多关键词搜索，合并结果
        all_results = {}
        for kw in keywords:
            results = real_kb.search(kw, domain, limit=3)
            for r in results:
                path = r['path']
                if path not in all_results:
                    all_results[path] = r
                else:
                    all_results[path]['score'] += r['score']

        # 也搜索通用技术关键词
        tech_keywords = ['Redis', 'Kafka', 'MySQL', '分布式', '并发', '缓存', '事务', '一致性', '微服务']
        for kw in tech_keywords:
            results = real_kb.search(kw, limit=2)
            for r in results:
                path = r['path']
                if path not in all_results:
                    all_results[path] = r
                else:
                    all_results[path]['score'] += r['score'] * 0.5

        # 按分数排序
        sorted_results = sorted(all_results.values(), key=lambda x: -x['score'])[:8]

        references = []
        for doc in sorted_results:
            references.append({
                'title': doc['title'],
                'path': doc['path'],
                'relevance_score': doc['score'],
                'summary': doc['summary'][:150] + '...' if len(doc['summary']) > 150 else doc['summary'],
            })

        return references

    def _check_anti_pattern(self, prd: str, anti_pattern: str) -> bool:
        """检查是否违反反模式"""
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
        # 性能优化: 检查缓存
        cache_key = f"review_{abs(hash(prd_content))}_{domain or 'auto'}"
        cached = get_optimizer().cache.get(cache_key)
        if cached and isinstance(cached, dict) and 'success' in cached:
            return cached

        # 如果没有指定领域，自动检测
        if not domain:
            domain = self._detect_domain(prd_content)

        # 执行分析
        analysis = self.decision_engine.analyze_prd(prd_content, domain)

        # 生成报告
        report = self.decision_engine.generate_review_report(analysis, domain)

        result = {
            'success': True,
            'domain': domain,
            'analysis': analysis,
            'report': report,
            'timestamp': datetime.now().isoformat(),
        }
        
        # 保存到缓存 (只保存value，不包装)
        get_optimizer().cache._memory_cache[cache_key] = result
        
        return result

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

        # 广告关键词 (提高权重)
        for kw in ['竞价', 'RTB', 'DSP', 'SSP', '广告', '出价', '曝光', '点击', '归因', 'ROI', 'eCPM', 'CPC', 'CPM']:
            if kw in prd:
                scores['advertising'] += 2

        # Agent 关键词 (提高权重)
        for kw in ['Agent', 'LLM', 'RAG', 'ReAct', '记忆', 'Tool', 'Prompt', 'Function Calling', '多Agent']:
            if kw in prd:
                scores['agent'] += 2

        # 电商关键词 (提高权重)
        for kw in ['订单', '商品', '库存', '秒杀', '购物车', '优惠券', '电商', '零售', '发货', '退款', '超卖']:
            if kw in prd:
                scores['ecommerce'] += 2

        # 金融关键词 (提高权重)
        for kw in ['交易', '账户', '风控', '合规', '清算', '对账', '金融', '支付', '账务', '资金', 'ACID', 'Saga']:
            if kw in prd:
                scores['finance'] += 2

        # 云原生关键词
        for kw in ['Kubernetes', 'K8s', '容器', 'Docker', 'Istio', '服务网格', 'Helm']:
            if kw in prd:
                scores['cloud_native'] += 1

        # DevOps 关键词
        for kw in ['CI/CD', 'Jenkins', 'ArgoCD', 'GitOps', 'Terraform', '流水线', '部署', '蓝绿', '灰度']:
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
        for kw in ['模型', '训练', '推理', 'MLflow', '特征', 'A/B测试', '漂移', '机器学习', '深度学习', '神经网络']:
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

        primary_domain = max(scores, key=scores.get)

        # 检测跨领域项目
        cross_domains = self._detect_cross_domain(scores, primary_domain)

        # 如果有跨领域标签，返回主领域+跨领域
        if cross_domains:
            return f"{primary_domain}+{cross_domains[0]}"

        return primary_domain

    def _detect_cross_domain(self, scores: Dict[str, int], primary: str = None) -> List[str]:
        """检测跨领域关联"""
        cross_domains = []

        # AdTech = advertising + ml_ops
        if scores.get('advertising', 0) > 0 and scores.get('ml_ops', 0) > 0:
            if 'ml_ops' != primary:
                cross_domains.append('ml_ops')

        # AdTech = advertising + security (anti-fraud)
        if scores.get('advertising', 0) > 0 and scores.get('security', 0) > 0:
            if 'security' != primary:
                cross_domains.append('security')

        # FinTech = finance + security
        if scores.get('finance', 0) > 0 and scores.get('security', 0) > 0:
            if 'security' != primary:
                cross_domains.append('security')

        # FinTech = finance + data_engineering
        if scores.get('finance', 0) > 0 and scores.get('data_engineering', 0) > 0:
            if 'data_engineering' != primary:
                cross_domains.append('data_engineering')

        # Social + ml_ops (recommendation)
        if scores.get('social', 0) > 0 and scores.get('ml_ops', 0) > 0:
            if 'ml_ops' != primary:
                cross_domains.append('ml_ops')

        # Cloud + devops
        if scores.get('cloud_native', 0) > 0 and scores.get('devops', 0) > 0:
            if 'devops' != primary:
                cross_domains.append('devops')

        # IoT + cloud_native
        if scores.get('iot', 0) > 0 and scores.get('cloud_native', 0) > 0:
            if 'cloud_native' != primary:
                cross_domains.append('cloud_native')

        # Gaming + ml_ops (anti-cheat)
        if scores.get('gaming', 0) > 0 and scores.get('ml_ops', 0) > 0:
            if 'ml_ops' != primary:
                cross_domains.append('ml_ops')

        return list(set(cross_domains))[:2]  # 去重，最多返回2个

    def detect_patterns(self, prd: str, domain: str) -> List[Dict]:
        """检测项目模式"""
        patterns = []

        if re.search(r'(?i)(QPS|qps|吞吐量|throughput|延迟|latency|P99|P95)', prd):
            patterns.append({
                'type': 'performance',
                'name': '高性能需求',
                'indicators': ['QPS', '延迟', 'P99'],
                'suggestions': ['考虑缓存策略', '评估异步化处理', '设计限流降级方案'],
            })

        if re.search(r'(?i)(一致|atomic|事务|transaction|ACID|强一致)', prd):
            patterns.append({
                'type': 'consistency',
                'name': '强一致性需求',
                'indicators': ['事务', 'ACID', '强一致'],
                'suggestions': ['使用本地事务或分布式事务', '考虑最终一致性场景', '设计补偿机制'],
            })

        if re.search(r'(?i)(并发|concurrent|锁|lock|竞态|race)', prd):
            patterns.append({
                'type': 'concurrency',
                'name': '高并发场景',
                'indicators': ['并发', '锁', '竞态'],
                'suggestions': ['使用分布式锁', '考虑无锁数据结构', '设计幂等接口'],
            })

        if re.search(r'(?i)(实时|realtime|real-time|流|stream|Kafka)', prd):
            patterns.append({
                'type': 'realtime',
                'name': '实时计算需求',
                'indicators': ['实时', '流', 'Kafka'],
                'suggestions': ['评估 Flink/Spark Streaming', '设计背压机制', '考虑消息堆积处理'],
            })

        if re.search(r'(?i)(安全|security|加密|encrypt|鉴权|auth|权限|permission)', prd):
            patterns.append({
                'type': 'security',
                'name': '安全敏感场景',
                'indicators': ['加密', '鉴权', '权限'],
                'suggestions': ['使用 Vault 管理密钥', '实施零信任架构', '添加操作审计日志'],
            })

        if re.search(r'(?i)(扩展|scale|elastic|水平|横向)', prd):
            patterns.append({
                'type': 'scalability',
                'name': '高可扩展需求',
                'indicators': ['扩展', '弹性', '水平'],
                'suggestions': ['设计无状态服务', '使用 K8s 自动扩缩容', '考虑分库分表'],
            })

        return patterns

    def get_pattern_recommendations(self, patterns: List[Dict]) -> List[Dict]:
        """根据模式生成推荐"""
        recommendations = []
        for pattern in patterns:
            for suggestion in pattern.get('suggestions', []):
                recommendations.append({
                    'type': pattern['type'],
                    'pattern': pattern['name'],
                    'recommendation': suggestion,
                    'priority': '高' if pattern['type'] in ['security', 'consistency'] else '中',
                })
        return recommendations


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
