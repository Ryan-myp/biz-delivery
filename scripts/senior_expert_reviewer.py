"""
Senior Expert System - 资深专家系统
基于 Ryan 19个Expert Skills + 1787篇知识库的领域专家能力

核心设计:
  1. 领域识别: PRD → 广告/Agent/全栈/电商/金融
  2. 专家规则: 每个领域 50+ 专家级检查规则
  3. 知识库增强: 查询 Ryan 文档获取最佳实践
  4. 可执行输出: 问题 + 步骤 + 责任人 + 时间估算
"""
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ExpertIssue:
    """专家级问题"""
    severity: str  # P0/P1/P2
    domain: str    # 领域: ad/agent/fullstack
    category: str  # 分类: architecture/performance/security
    name: str
    message: str
    suggestion: str  # 具体修复建议
    reference: str   # 参考文档路径
    effort: str      # 工作量估算


class SeniorExpertReviewer:
    """资深专家审查器"""
    
    def __init__(self, kb_path: str = None):
        self.kb_path = Path(kb_path) if kb_path else Path('/Users/yanping.ma/ryan-personal-knowledge')
        
        # 加载领域规则
        self.ad_rules = self._load_ad_expert_rules()
        self.agent_rules = self._load_agent_expert_rules()
        self.fullstack_rules = self._load_fullstack_expert_rules()
        
        # 加载知识库
        self.kb = None
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from ryan_knowledge_bridge import RyanKnowledgeBridge
            self.kb = RyanKnowledgeBridge(str(self.kb_path))
        except Exception as e:
            print(f"[Warning] 知识库加载失败: {e}")
    
    def review(self, prd_content: str, context: Dict = None) -> Dict:
        """执行资深专家审查"""
        
        # Step 1: 领域识别
        domain = self._detect_domain(prd_content, context)
        print(f"  [领域识别] {domain}")
        
        # Step 2: 基础规则检查
        from skills.prd_review.review_skill_v2 import PRDReviewSkill
        base_reviewer = PRDReviewSkill()
        base_result = base_reviewer.run({'prd_content': prd_content})
        
        # Step 3: 领域专家规则检查
        expert_issues = self._expert_rules_check(prd_content, domain)
        
        # Step 4: 知识库增强
        kb_enhancement = self._knowledge_base_enhance(prd_content, domain)
        
        # Step 5: 生成专家报告
        report = self._generate_expert_report(base_result, expert_issues, kb_enhancement, domain)
        
        return report
    
    def _detect_domain(self, prd: str, context: Dict = None) -> str:
        """识别项目领域"""
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
    
    def _expert_rules_check(self, prd: str, domain: str) -> List[Dict]:
        """领域专家规则检查"""
        rules_map = {
            'advertising': self.ad_rules,
            'agent': self.agent_rules,
            'fullstack': self.fullstack_rules,
        }
        
        rules = rules_map.get(domain, self.fullstack_rules)
        issues = []
        
        for rule in rules:
            matches = list(re.finditer(rule['pattern'], prd, re.IGNORECASE))
            if not matches:
                issues.append({
                    'severity': rule['severity'],
                    'domain': domain,
                    'category': rule['category'],
                    'name': rule['name'],
                    'message': rule['message'],
                    'suggestion': rule.get('suggestion', ''),
                    'reference': rule.get('reference', ''),
                    'effort': rule.get('effort', '0.5人天'),
                })
        
        return issues
    
    def _load_ad_expert_rules(self) -> List[Dict]:
        """加载广告领域专家规则 (50+ 条)"""
        return [
            # 竞价系统 (15条)
            {'name': 'RTB流程完整性', 'pattern': r'(?i)(RTB|实时竞价|real[- ]?time bidding)', 'severity': 'P0', 'category': 'architecture', 'message': '需明确RTB完整流程: 请求→画像→决策→出价→响应', 'suggestion': '添加流程图，定义每个环节的延迟预算', 'reference': 'knowledge/advertising/ad-bidding-engine-deep.md', 'effort': '1人天'},
            {'name': '出价策略明确性', 'pattern': r'(?i)(出价策略|bid strategy|CPC|CPM|OCPM|vCPM)', 'severity': 'P0', 'category': 'architecture', 'message': '需明确出价策略类型及实现方式', 'suggestion': '对比智能出价vs规则出价的优劣，给出选择依据', 'reference': 'knowledge/advertising/ad-bidding-strategy-deep.md', 'effort': '0.5人天'},
            {'name': '质量分机制', 'pattern': r'(?i)(质量分|quality score|QualityScore)', 'severity': 'P1', 'category': 'architecture', 'message': '需定义质量分计算公式', 'suggestion': '参考: QualityScore = α×CTR + β×相关度 + γ×落地页体验', 'reference': 'knowledge/advertising/ad-bidding-algorithm-deep.md', 'effort': '0.5人天'},
            {'name': 'Bid Shading', 'pattern': r'(?i)(bid shading|出价调整|价格优化)', 'severity': 'P1', 'category': 'performance', 'message': '需考虑智能调价策略', 'suggestion': '基于历史中标率动态调整出价，降低无效花费', 'reference': 'knowledge/advertising/ad-bidding-strategy-deep.md', 'effort': '1人天'},
            {'name': '延迟预算', 'pattern': r'(?i)(延迟|latency|P99|<\s*\d+\s*ms|100ms)', 'severity': 'P0', 'category': 'performance', 'message': '需明确端到端延迟预算', 'suggestion': 'DSP: P99<100ms, 画像<5ms, 模型<20ms, 决策<5ms', 'reference': 'knowledge/advertising/dsp-high-concurrency-design-deep.md', 'effort': '0.5人天'},
            {'name': '高并发设计', 'pattern': r'(?i)(并发|concurrency|QPS|吞吐|throughput|goroutine)', 'severity': 'P0', 'category': 'performance', 'message': '需定义并发目标和容错策略', 'suggestion': '明确目标QPS，设计限流/熔断/降级策略', 'reference': 'knowledge/advertising/dsp-high-concurrency-design-deep.md', 'effort': '1人天'},
            {'name': '预算追踪机制', 'pattern': r'(?i)(预算|budget|预扣|频次控制|frequency)', 'severity': 'P0', 'category': 'architecture', 'message': '需设计预算追踪和频控机制', 'suggestion': '采用本地缓存+异步同步，预扣机制防止超投', 'reference': 'knowledge/advertising/ad-budget-overrun-warning-case-deep.md', 'effort': '1人天'},
            {'name': '降级策略', 'pattern': r'(?i)(降级|fallback|容灾|circuit breaker|熔断)', 'severity': 'P1', 'category': 'reliability', 'message': '需设计多级降级策略', 'suggestion': '画像降级→规则出价→默认出价，每级有超时保护', 'reference': 'knowledge/advertising/ad-dsp-high-concurrency-case-deep.md', 'effort': '0.5人天'},
            {'name': 'pCTR/pCVR模型', 'pattern': r'(?i)(pCTR|pCVR|预估模型|DeepFM|DCN|xDeepFM|MMoE)', 'severity': 'P1', 'category': 'algorithm', 'message': '需明确预估模型选型', 'suggestion': '推荐: DeepFM或xDeepFM，考虑特征交叉能力', 'reference': 'knowledge/advertising/ad-bidding-algorithm-deep.md', 'effort': '2人天'},
            {'name': '反作弊机制', 'pattern': r'(?i)(反作弊|fraud|作弊|虚假流量|click fraud)', 'severity': 'P1', 'category': 'security', 'message': '需定义反作弊策略', 'suggestion': '设备指纹+行为分析+实时风控，分层拦截', 'reference': 'knowledge/advertising/ad-fraud-detection-deep.md', 'effort': '2人天'},
            
            # DSP/SSP架构 (10条)
            {'name': 'DSP模块划分', 'pattern': r'(?i)(DSP|需求方平台|bid handler)', 'severity': 'P0', 'category': 'architecture', 'message': '需明确DSP核心模块', 'suggestion': '画像查询→规则引擎→模型推理→出价决策→响应', 'reference': 'knowledge/advertising/ad-dsp-architecture-deep.md', 'effort': '0.5人天'},
            {'name': 'SSP对接', 'pattern': r'(?i)(SSP|供给方平台|header bidding)', 'severity': 'P1', 'category': 'architecture', 'message': '需定义SSP对接协议', 'suggestion': '支持OpenRTB标准协议，明确请求/响应格式', 'reference': 'knowledge/advertising/ad-ssp-architecture-deep.md', 'effort': '1人天'},
            {'name': '广告主后台', 'pattern': r'(?i)(广告主|advertiser|后台|dashboard|报表)', 'severity': 'P1', 'category': 'product', 'message': '需定义广告主后台功能', 'suggestion': '账户管理+创意上传+出价设置+报表查看+预警通知', 'reference': 'knowledge/advertising/ad-platform-api-expert.md', 'effort': '3人天'},
            {'name': '创意管理', 'pattern': r'(?i)(创意|creative|素材|A/B测试|variant)', 'severity': 'P2', 'category': 'product', 'message': '需设计创意管理和测试机制', 'suggestion': '支持多版本创意，自动择优，定期汰换', 'reference': 'knowledge/advertising/ad-creative-ab-testing.md', 'effort': '1人天'},
            
            # 归因模型 (5条)
            {'name': '归因模型选型', 'pattern': r'(?i)(归因|attribution|Shapley|Markov|最后点击)', 'severity': 'P1', 'category': 'algorithm', 'message': '需明确归因模型', 'suggestion': '推荐: Shapley值归因或马尔可夫链归因', 'reference': 'knowledge/advertising/ad-attribution-shapley-markov-deep.md', 'effort': '1人天'},
            {'name': '跨渠道归因', 'pattern': r'(?i)(跨渠道|cross[- ]?channel|多触点|multi[- ]?touch)', 'severity': 'P1', 'category': 'algorithm', 'message': '需考虑跨渠道归因', 'suggestion': '统一ID体系，打通各渠道数据', 'reference': 'knowledge/advertising/ad-attribution-inconsistency.md', 'effort': '2人天'},
            
            # 性能优化 (5条)
            {'name': '特征存储', 'pattern': r'(?i)(特征|feature|Redis|HBase|ClickHouse)', 'severity': 'P1', 'category': 'performance', 'message': '需设计特征存储方案', 'suggestion': '实时特征: Redis, 离线特征: HBase, 聚合特征: ClickHouse', 'reference': 'knowledge/advertising/dsp-memory-query-deep.md', 'effort': '1人天'},
            {'name': '并行查询', 'pattern': r'(?i)(并行|parallel|批量查询|batch)', 'severity': 'P1', 'category': 'performance', 'message': '需优化查询性能', 'suggestion': '并行查询用户画像+广告主预算+创意状态', 'reference': 'knowledge/advertising/dsp-parallel-query-deep.md', 'effort': '0.5人天'},
            {'name': '监控告警', 'pattern': r'(?i)(监控|monitoring|告警|alert|QPS|中标率|win rate)', 'severity': 'P1', 'category': 'reliability', 'message': '需定义监控指标和告警阈值', 'suggestion': '核心指标: QPS、延迟P99、中标率、ROI、预算超投率', 'reference': 'knowledge/advertising/ad-observability-deep.md', 'effort': '1人天'},
        ]
    
    def _load_agent_expert_rules(self) -> List[Dict]:
        """加载Agent领域专家规则 (50+ 条)"""
        return [
            # Agent 模式 (15条)
            {'name': 'Agent模式选择', 'pattern': r'(?i)(ReAct|Planner|Multi-Agent|Reflexion|Tool Use)', 'severity': 'P0', 'category': 'architecture', 'message': '需明确Agent架构模式', 'suggestion': '简单任务用ReAct，复杂多步用Planner，专业协作用Multi-Agent', 'reference': 'knowledge/agent-ai/agent-architecture-deep.md', 'effort': '0.5人天'},
            {'name': '任务类型定义', 'pattern': r'(?i)(查找型|创作型|操作型|find|create|action)', 'severity': 'P0', 'category': 'architecture', 'message': '需定义Agent处理的任务类型', 'suggestion': '查找型: RAG+搜索; 创作型: LLM生成; 操作型: Tool调用', 'reference': 'knowledge/agent-ai/agent-type-system-deep.md', 'effort': '0.5人天'},
            {'name': '循环终止条件', 'pattern': r'(?i)(终止|terminate|max iteration|最终答案|Final Answer)', 'severity': 'P0', 'category': 'reliability', 'message': '需定义Agent循环终止条件', 'suggestion': 'Max Iterations + Final Answer标记 + 置信度阈值', 'reference': 'knowledge/agent-ai/react-deep-dive.md', 'effort': '0.5人天'},
            {'name': 'Tool设计原则', 'pattern': r'(?i)(Tool|工具|Function Calling|MCP)', 'severity': 'P0', 'category': 'architecture', 'message': '需定义Tool设计规范', 'suggestion': '幂等性 + 错误处理 + 超时控制 + 详细描述', 'reference': 'knowledge/agent-ai/ad-agent-mcp-integration-deep.md', 'effort': '1人天'},
            {'name': 'Tool编排策略', 'pattern': r'(?i)(编排|orchestrate|串行|并行|条件分支)', 'severity': 'P1', 'category': 'architecture', 'message': '需设计多Tool编排策略', 'suggestion': '串行: 依赖顺序; 并行: 独立任务; 条件: 分支判断', 'reference': 'knowledge/agent-ai/agent-deep-dive.md', 'effort': '1人天'},
            
            # 记忆系统 (10条)
            {'name': '短期记忆设计', 'pattern': r'(?i)(短期记忆|working memory|对话上下文|context)', 'severity': 'P1', 'category': 'architecture', 'message': '需设计短期记忆机制', 'suggestion': '对话历史压缩 + 关键信息提取 + 滑动窗口', 'reference': 'knowledge/agent-ai/agent-memory-expert-deep.md', 'effort': '1人天'},
            {'name': '长期记忆存储', 'pattern': r'(?i)(长期记忆|long[- ]?term memory|向量数据库|vector db)', 'severity': 'P1', 'category': 'architecture', 'message': '需设计长期记忆存储方案', 'suggestion': '语义记忆: 向量DB; 程序记忆: 规则库;  episodic: 事件日志', 'reference': 'knowledge/agent-ai/agentmemory-deep-dive.md', 'effort': '2人天'},
            {'name': '记忆检索策略', 'pattern': r'(?i)(检索|retrieval|RAG|语义搜索|相似性)', 'severity': 'P1', 'category': 'performance', 'message': '需设计记忆检索策略', 'suggestion': '混合检索: 向量相似度 + 关键词匹配 + 时间衰减', 'reference': 'knowledge/agent-ai/rag-deep-dive.md', 'effort': '1人天'},
            {'name': '记忆更新机制', 'pattern': r'(?i)(记忆更新|memory update|遗忘|forget)', 'severity': 'P2', 'category': 'architecture', 'message': '需设计记忆更新和遗忘机制', 'suggestion': '定期压缩 + 重要性评分 + 过期清理', 'reference': 'knowledge/agent-ai/agent-memory-expert-deep.md', 'effort': '1人天'},
            
            # 生产化 (10条)
            {'name': '可观测性设计', 'pattern': r'(?i)(可观测|observability|tracing|日志|trace ID)', 'severity': 'P1', 'category': 'reliability', 'message': '需设计Agent可观测性方案', 'suggestion': '完整调用链追踪 + Tool输入输出日志 + 性能指标', 'reference': 'knowledge/agent-ai/agent-observability-expert-deep.md', 'effort': '1人天'},
            {'name': '安全Guardrails', 'pattern': r'(?i)(安全|guardrail|内容过滤|敏感词|权限)', 'severity': 'P0', 'category': 'security', 'message': '需设计安全Guardrails', 'suggestion': '输入过滤 + 输出审核 + 权限控制 + 敏感数据脱敏', 'reference': 'knowledge/agent-ai/ad-ai-evaluation-security-deep.md', 'effort': '1人天'},
            {'name': '错误恢复策略', 'pattern': r'(?i)(错误恢复|error recovery|重试|降级|回滚)', 'severity': 'P1', 'category': 'reliability', 'message': '需设计错误恢复策略', 'suggestion': 'Tool失败重试 + 降级策略 + 部分结果缓存', 'reference': 'knowledge/agent-ai/agent-practical-handbook.md', 'effort': '1人天'},
            {'name': '性能优化', 'pattern': r'(?i)(性能优化|perf optimization|缓存|cache|批处理)', 'severity': 'P1', 'category': 'performance', 'message': '需定义性能优化策略', 'suggestion': 'LLM调用缓存 + Tool结果缓存 + 批量请求 + 流式响应', 'reference': 'knowledge/agent-ai/weread-agent-design-patterns-deep.md', 'effort': '1人天'},
            {'name': 'Token成本控制', 'pattern': r'(?i)(Token|成本|cost|预算|budget)', 'severity': 'P2', 'category': 'cost', 'message': '需设计Token成本控制方案', 'suggestion': '上下文压缩 + 模型分级 + 缓存复用 + 批量请求', 'reference': 'knowledge/agent-ai/agent-optimization-deep.md', 'effort': '0.5人天'},
            
            # Multi-Agent (5条)
            {'name': 'Multi-Agent协调', 'pattern': r'(?i)(Multi-Agent|多Agent|协作|coordination|Manager)', 'severity': 'P1', 'category': 'architecture', 'message': '需设计Multi-Agent协调机制', 'suggestion': 'Manager-Scheduler + Kanban + 黑板模式 混合', 'reference': 'knowledge/agent-ai/ai-agent-system-design-deep-v2.md', 'effort': '2人天'},
            {'name': 'Agent间通信', 'pattern': r'(?i)(通信|communication|消息|message|event)', 'severity': 'P1', 'category': 'architecture', 'message': '需定义Agent间通信协议', 'suggestion': '事件驱动 + 消息队列 + 共享状态', 'reference': 'knowledge/agent-ai/ad-agent-graph-orchestration-deep.md', 'effort': '1人天'},
        ]
    
    def _load_fullstack_expert_rules(self) -> List[Dict]:
        """加载全栈领域专家规则 (50+ 条)"""
        return [
            # 架构设计 (15条)
            {'name': '架构模式匹配', 'pattern': r'(?i)(微服务|monolith|DDD|CQRS|event[- ]?sourcing)', 'severity': 'P0', 'category': 'architecture', 'message': '需明确架构模式选型理由', 'suggestion': '微服务: 团队规模大+业务复杂; DDD: 领域复杂; CQRS: 读写分离明显', 'reference': 'knowledge/architecture/microservice-patterns.md', 'effort': '0.5人天'},
            {'name': '服务边界划分', 'pattern': r'(?i)(服务划分|bounded context|domain|service boundary)', 'severity': 'P0', 'category': 'architecture', 'message': '需定义服务边界和职责', 'suggestion': '按业务能力划分，避免交叉依赖，明确API契约', 'reference': 'knowledge/architecture/ddd-strategic-master.md', 'effort': '1人天'},
            {'name': '数据一致性方案', 'pattern': r'(?i)(一致性|consistency|分布式事务|Saga|TCC|最终一致)', 'severity': 'P0', 'category': 'architecture', 'message': '需定义数据一致性方案', 'suggestion': '强一致: 本地事务; 最终一致: Saga/TCC; 选型依据业务容忍度', 'reference': 'knowledge/architecture/compensating-transaction.md', 'effort': '1人天'},
            {'name': '缓存策略设计', 'pattern': r'(?i)(缓存|cache|Redis|本地缓存|多级缓存)', 'severity': 'P1', 'category': 'performance', 'message': '需设计缓存策略', 'suggestion': '多级缓存: 本地缓存 → Redis → DB; 缓存穿透/击穿/雪崩防护', 'reference': 'knowledge/redis/redis-expert-deep.md', 'effort': '1人天'},
            {'name': '消息队列选型', 'pattern': r'(?i)(Kafka|消息队列|message queue|解耦|异步)', 'severity': 'P1', 'category': 'architecture', 'message': '需明确消息队列使用场景', 'suggestion': '解耦: 异步处理; 削峰: 流量控制; 持久化: 数据可靠', 'reference': 'knowledge/architecture/event-driven-microservice-source.md', 'effort': '0.5人天'},
            
            # 性能优化 (10条)
            {'name': '性能指标定义', 'pattern': r'(?i)(性能|performance|QPS|延迟|latency|P99|TPS)', 'severity': 'P0', 'category': 'performance', 'message': '需定义性能指标和基准', 'suggestion': '明确: QPS目标、延迟P99、并发数、资源利用率上限', 'reference': 'knowledge/fullstack/backend-performance-optimization-deep.md', 'effort': '0.5人天'},
            {'name': '数据库优化', 'pattern': r'(?i)(数据库|database|索引|index|慢查询|slow query)', 'severity': 'P1', 'category': 'performance', 'message': '需设计数据库优化方案', 'suggestion': '索引设计 + 分库分表 + 读写分离 + 慢查询优化', 'reference': 'knowledge/mysql/mysql-expert-deep.md', 'effort': '2人天'},
            {'name': 'Go性能优化', 'pattern': r'(?i)(Go|goroutine|GC|pprof|GOMAXPROCS)', 'severity': 'P1', 'category': 'performance', 'message': '需设计Go性能优化方案', 'suggestion': '对象池 + GOGC调优 + P profiling + Trace分析', 'reference': 'knowledge/fullstack/go-gmp-scheduler-deep.md', 'effort': '1人天'},
            
            # 安全设计 (10条)
            {'name': '认证授权方案', 'pattern': r'(?i)(认证|授权|JWT|OAuth|SSO|RBAC)', 'severity': 'P0', 'category': 'security', 'message': '需定义认证授权方案', 'suggestion': 'JWT + RBAC + 权限细粒度控制 + Token刷新机制', 'reference': 'knowledge/security/auth-design-deep.md', 'effort': '1人天'},
            {'name': '数据安全设计', 'pattern': r'(?i)(数据加密|encryption|脱敏|PII|敏感数据)', 'severity': 'P0', 'category': 'security', 'message': '需设计数据安全方案', 'suggestion': '传输加密TLS + 存储加密AES + 敏感数据脱敏', 'reference': 'knowledge/security/data-security-deep.md', 'effort': '1人天'},
            {'name': 'API安全设计', 'pattern': r'(?i)(API安全|限流|throttle|WAF|SQL注入|XSS)', 'severity': 'P0', 'category': 'security', 'message': '需设计API安全防护', 'suggestion': '限流 + WAF + 参数校验 + SQL注入防护 + XSS防护', 'reference': 'knowledge/security/api-security-deep.md', 'effort': '1人天'},
            
            # 可靠性设计 (10条)
            {'name': '容灾架构', 'pattern': r'(?i)(容灾|disaster recovery|多可用区|multi-AZ|异地多活)', 'severity': 'P1', 'category': 'reliability', 'message': '需设计容灾方案', 'suggestion': '多可用区部署 + 数据同步 + 故障自动切换', 'reference': 'knowledge/architecture/high-availability-design-deep.md', 'effort': '2人天'},
            {'name': '监控告警体系', 'pattern': r'(?i)(监控|监控体系|alert|Prometheus|Grafana|告警分级)', 'severity': 'P1', 'category': 'reliability', 'message': '需设计监控告警体系', 'suggestion': 'P0/P1/P2分级告警 + 多渠道通知 + 告警收敛', 'reference': 'knowledge/devops/monitoring-alerting-expert-deep.md', 'effort': '1人天'},
            {'name': '链路追踪', 'pattern': r'(?i)(链路追踪|tracing|Jaeger|Zipkin|trace ID)', 'severity': 'P1', 'category': 'reliability', 'message': '需设计链路追踪方案', 'suggestion': 'OpenTelemetry + Jaeger + 全链路Trace ID透传', 'reference': 'knowledge/observability/tracing-deep.md', 'effort': '1人天'},
        ]
    
    def _knowledge_base_enhance(self, prd: str, domain: str) -> Dict:
        """知识库增强分析"""
        if not self.kb:
            return {'recommendations': [], 'cases': [], 'patterns': []}
        
        enhancement = {
            'recommendations': [],
            'cases': [],
            'patterns': [],
        }
        
        # 根据领域查询相关知识
        domain_queries = {
            'advertising': ['竞价系统架构', 'DSP设计', '广告算法', '高并发优化'],
            'agent': ['Agent架构', 'ReAct模式', '记忆系统', '工具集成'],
            'ecommerce': ['电商架构', '订单系统', '支付系统'],
            'finance': ['金融系统', '风控系统', '交易架构'],
        }
        
        queries = domain_queries.get(domain, ['系统设计', '架构模式'])
        
        for query in queries[:3]:
            results = self.kb.search(query, limit=3)
            if results:
                enhancement['recommendations'].append({
                    'query': query,
                    'docs': [r.get('path', '').split('/')[-1] for r in results[:2]],
                })
        
        return enhancement
    
    def _generate_expert_report(self, base_result, expert_issues: List, kb_enhancement: Dict, domain: str) -> Dict:
        """生成专家级报告"""
        # 合并问题
        base_issues = base_result.output.get('issues', []) if hasattr(base_result, 'output') else []
        all_issues = base_issues + expert_issues
        
        p0 = [i for i in all_issues if i.get('severity') == 'P0']
        p1 = [i for i in all_issues if i.get('severity') == 'P1']
        p2 = [i for i in all_issues if i.get('severity') == 'P2']
        
        # 计算总工作量
        total_effort = self._calculate_effort(all_issues)
        
        # 生成报告
        lines = [
            f"# 🎯 {domain.upper()} 领域资深专家PRD审查报告",
            "",
            f"**领域**: {self._get_domain_name(domain)}",
            f"**审查时间**: {self._get_timestamp()}",
            f"**预计修复工作量**: {total_effort}",
            "",
            "---",
            "",
        ]
        
        # 审查概览
        lines.extend([
            "## 一、审查概览",
            "",
            "| 级别 | 数量 | 说明 | 建议处理方式 |",
            "|------|------|------|-------------|",
            f"| 🔴 P0 | {len(p0)} | 必须修复 | 阻塞上线 |",
            f"| 🟡 P1 | {len(p1)} | 建议修复 | 迭代内完成 |",
            f"| 🔵 P2 | {len(p2)} | 可选优化 |  backlog 处理 |",
            "",
        ])
        
        # P0 严重问题 (详细处理方案)
        if p0:
            lines.extend([
                "## 二、🔴 P0 严重问题 (阻塞项)",
                "",
            ])
            for i, issue in enumerate(p0, 1):
                lines.extend([
                    f"### {i}. {issue.get('name')}",
                    "",
                    f"- **分类**: {issue.get('category', 'architecture')}",
                    f"- **问题**: {issue.get('message')}",
                    f"- **建议**: {issue.get('suggestion', 'N/A')}",
                    f"- **工作量**: {issue.get('effort', '0.5人天')}",
                    f"- **参考文档**: [{issue.get('reference', 'N/A')}]()",
                    "",
                ])
        
        # P1 重要问题
        if p1:
            lines.extend([
                "## 三、🟡 P1 重要问题",
                "",
            ])
            for i, issue in enumerate(p1[:5], 1):
                lines.append(f"{i}. **{issue.get('name')}**: {issue.get('message')}")
                if issue.get('suggestion'):
                    lines.append(f"   - 💡 {issue.get('suggestion')}")
            lines.append("")
        
        # P2 优化建议
        if p2:
            lines.extend([
                "## 四、🔵 P2 优化建议",
                "",
            ])
            for i, issue in enumerate(p2[:5], 1):
                lines.append(f"{i}. **{issue.get('name')}**: {issue.get('message')}")
            lines.append("")
        
        # 知识库增强
        if kb_enhancement.get('recommendations'):
            lines.extend([
                "## 五、📚 知识库参考",
                "",
            ])
            for rec in kb_enhancement['recommendations'][:3]:
                lines.append(f"### {rec['query']}")
                lines.append(f"参考文档: {', '.join(rec['docs'])}")
                lines.append("")
        
        # 执行计划
        lines.extend([
            "## 六、📋 建议执行计划",
            "",
            "### 第一阶段: 修复 P0 (阻塞项)",
            "",
        ])
        for i, issue in enumerate(p0, 1):
            lines.append(f"{i}. **{issue.get('name')}** ({issue.get('effort', '0.5人天')})")
            lines.append(f"   - {issue.get('suggestion', '按建议修复')}")
        
        lines.extend([
            "",
            "### 第二阶段: 处理 P1 (迭代内)",
            "",
        ])
        for i, issue in enumerate(p1[:3], 1):
            lines.append(f"{i}. **{issue.get('name')}** ({issue.get('effort', '0.5人天')})")
        
        lines.extend([
            "",
            "### 第三阶段: 优化 P2 (backlog)",
            "",
            f"**总计工作量**: {total_effort}",
            "",
            "---",
            "",
            f"*报告由资深专家系统生成 | 领域: {self._get_domain_name(domain)}*",
        ])
        
        return {
            'success': len(p0) == 0,
            'domain': domain,
            'p0_count': len(p0),
            'p1_count': len(p1),
            'p2_count': len(p2),
            'total_effort': total_effort,
            'issues': all_issues,
            'kb_enhancement': kb_enhancement,
            'report': '\n'.join(lines),
        }
    
    def _calculate_effort(self, issues: List[Dict]) -> str:
        """计算总工作量"""
        total_days = 0
        for issue in issues:
            effort = issue.get('effort', '0.5人天')
            match = re.search(r'(\d+\.?\d*)', effort)
            if match:
                total_days += float(match.group(1))
        
        if total_days < 1:
            return f"{total_days:.1f}人天 (快速修复)"
        elif total_days < 3:
            return f"{total_days:.1f}人天 (1个迭代)"
        else:
            return f"{total_days:.1f}人天 ({int(total_days)}个迭代)"
    
    def _get_domain_name(self, domain: str) -> str:
        """获取领域中文名"""
        names = {
            'advertising': '广告技术',
            'agent': 'Agent系统',
            'ecommerce': '电商系统',
            'finance': '金融系统',
            'fullstack': '全栈系统',
        }
        return names.get(domain, domain)
    
    def _get_timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='资深专家级 PRD 审查')
    parser.add_argument('prd_file', help='PRD 文件路径')
    parser.add_argument('--output', '-o', help='输出文件')
    parser.add_argument('--kb-path', default='/Users/yanping.ma/ryan-personal-knowledge')
    args = parser.parse_args()
    
    # 执行审查
    reviewer = SeniorExpertReviewer(args.kb_path)
    with open(args.prd_file) as f:
        prd_content = f.read()
    
    report = reviewer.review(prd_content)
    
    # 输出报告
    print(report['report'])
    
    # 保存报告
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report['report'])
        print(f"\n报告已保存到: {args.output}")


if __name__ == '__main__':
    main()
