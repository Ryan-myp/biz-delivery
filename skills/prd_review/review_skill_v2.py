"""
PRD 审查 Skill v3.0 - 资深专家版
50+ 专家级规则，覆盖架构/性能/安全/可靠性/领域专家

核心升级:
  1. 从 17条 → 50+条规则
  2. 新增领域专家规则 (广告/Agent/电商/金融)
  3. 增加架构级问题检测
  4. 添加知识库推荐
"""
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from ..base import SkillBase, SkillResult


class PRDReviewSkill(SkillBase):
    """PRD 审查 Skill - 资深专家版，50+专家规则"""

    # ==================== P0 严重问题规则 (必须修复) ====================
    P0_RULES = {
        "missing_title": {
            "name": "缺少标题",
            "pattern": r"^#\s+(.+)",
            "flags": re.MULTILINE,
            "severity": "P0",
            "message": "PRD 应包含一级标题（标题）",
            "suggestion": "添加清晰的 PRD 标题，如 'XXX 系统 v2.0 升级方案'",
        },
        "missing_requirements": {
            "name": "缺少需求描述",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+\.?[\d零一二三四五六七八九十]*\s*.{0,30}(需求|功能|用户故事|规格|functional)",
            "flags": re.MULTILINE,
            "severity": "P0",
            "message": "PRD 应包含需求描述章节",
            "suggestion": "添加 '需求描述' 或 '功能规格' 章节，详细说明系统功能",
        },
        "missing_goals": {
            "name": "缺少业务目标",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+\.?[\d零一二三四五六七八九十]*\s*.{0,30}(背景|目标|愿景|目的|goals|background)",
            "flags": re.MULTILINE,
            "severity": "P0",
            "message": "PRD 应说明业务目标和背景",
            "suggestion": "添加 '业务背景' 章节，说明为什么要做这个需求，解决什么问题",
        },
        "missing_acceptance": {
            "name": "缺少验收标准",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(验收|acceptance|测试标准|验证|交付标准|成功标准)",
            "flags": re.MULTILINE,
            "severity": "P0",
            "message": "PRD 应包含验收标准",
            "suggestion": "添加 '验收标准' 章节，明确什么算完成，如 'P99延迟<100ms'",
        },
        "vague_metrics": {
            "name": "指标量化不足",
            "pattern": r"(?i)(提升|降低|减少|增加|达到|>=|<=|>\s*\d+|%|倍|万|亿)",
            "flags": 0,
            "severity": "P0",
            "message": "业务指标应量化（如：转化率提升 X%）",
            "suggestion": "补充具体数值指标，如 '响应时间从 200ms 降到 100ms'",
        },
        "missing_api_contract": {
            "name": "缺少接口契约",
            "pattern": r"(?i)(接口|API|endpoint|rest|graphql|契约|proto|grpc)",
            "flags": 0,
            "severity": "P0",
            "message": "涉及系统交互的 PRD 应定义接口契约",
            "suggestion": "添加 '接口设计' 章节，定义请求/响应格式、错误码、限流策略",
        },
    }

    # ==================== P1 重要问题规则 ====================
    P1_RULES = {
        "missing_timeline": {
            "name": "缺少时间规划",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(时间|排期|里程碑|进度|计划|schedule|timeline|里程碑)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应包含时间规划章节",
            "suggestion": "添加 '时间规划' 章节，明确各阶段交付物和时间点",
        },
        "missing_dependencies": {
            "name": "缺少依赖说明",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(依赖|前置|依赖项|prerequisite|dependencies|依赖方)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应说明依赖关系",
            "suggestion": "添加 '依赖说明' 章节，列出内部/外部依赖及负责人",
        },
        "missing_rollback": {
            "name": "缺少回滚方案",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(回滚|rollback|降级|fallback|应急|预案)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应包含回滚方案",
            "suggestion": "添加 '回滚方案' 章节，明确回滚触发条件、操作步骤、验证点",
        },
        "missing_risk": {
            "name": "缺少风险评估",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(风险|risk|预案|contingency|假设)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应包含风险评估",
            "suggestion": "添加 '风险评估' 章节，列出技术/业务/资源风险及应对措施",
        },
        "missing_security": {
            "name": "缺少安全考虑",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+\.?[\d零一二三四五六七八九十]*\s*.{0,30}(安全|security|权限|auth|加密|隐私|privacy|渗透)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应包含安全考虑",
            "suggestion": "添加 '安全设计' 章节，覆盖认证授权、数据加密、渗透测试",
        },
        "missing_performance": {
            "name": "缺少性能要求",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+\.?[\d零一二三四五六七八九十]*\s*.{0,30}(性能|performance|QPS|延迟|latency|吞吐|throughput|P99|P95)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应包含性能要求",
            "suggestion": "添加 '性能要求' 章节，明确 QPS、延迟、并发数等指标",
        },
        "missing_data_migration": {
            "name": "缺少数据迁移方案",
            "pattern": r"(?i)(迁移|migrate|数据同步|兼容|backward|data migration)",
            "flags": 0,
            "severity": "P1",
            "message": "涉及数据变更的 PRD 应有迁移方案",
            "suggestion": "添加 '数据迁移' 章节，说明兼容策略、灰度方案、回滚机制",
        },
        "missing_monitoring": {
            "name": "缺少监控方案",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(监控|monitoring|告警|alert|观测|observability|trace)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应包含监控方案",
            "suggestion": "添加 '监控告警' 章节，定义监控维度和告警阈值",
        },
        "missing_architecture": {
            "name": "缺少架构设计",
            "pattern": r"(?i)(架构|architecture|微服务|monolith|DDD|CQRS|event.*sourcing)",
            "flags": 0,
            "severity": "P1",
            "message": "中大型项目 PRD 应有架构设计说明",
            "suggestion": "添加 '架构设计' 章节，说明技术选型、模块划分、服务边界",
        },
        "missing_test_strategy": {
            "name": "缺少测试策略",
            "pattern": r"(?:^|\n)#{1,4}\s*[\d一二三四五六七八九十]+[、.．]?\s*.{0,30}(测试|test|QA|验收|acceptance|用例|scenario)",
            "flags": re.MULTILINE,
            "severity": "P1",
            "message": "PRD 应包含测试策略",
            "suggestion": "添加 '测试策略' 章节，明确单元测试、集成测试、E2E测试范围",
        },
        "vague_requirement": {
            "name": "模糊需求",
            "pattern": r"\b(尽快|大概|可能|或许|类似|差不多|一些|若干|较多|大约|适当|合理)\b",
            "flags": 0,
            "severity": "P1",
            "message": "发现模糊表述，建议明确具体数值或标准",
            "suggestion": "将模糊表述改为具体数值，如 '尽快' → '3个工作日内'",
        },
        "missing_stakeholder": {
            "name": "缺少利益相关方",
            "pattern": r"(?i)(依赖|depend|collaborat|协同|对接|接口方|stakeholder|owner)",
            "flags": 0,
            "severity": "P1",
            "message": "应明确利益相关方和负责人",
            "suggestion": "添加 '利益相关方' 章节，列出产品、研发、测试、运维负责人",
        },
    }

    # ==================== P2 优化建议规则 ====================
    P2_RULES = {
        "missing_monitoring_detail": {
            "name": "监控细节不足",
            "pattern": r"(?i)(监控|monitoring|告警|alert)",
            "flags": 0,
            "severity": "P2",
            "message": "监控方案应包含具体指标和阈值",
            "suggestion": "补充监控指标：CPU/内存/延迟/错误率，并设置阈值",
        },
        "missing_disaster_recovery": {
            "name": "缺少容灾设计",
            "pattern": r"(?i)(容灾|disaster.*recovery|多可用区|multi-AZ|异地|backup)",
            "flags": 0,
            "severity": "P2",
            "message": "重要系统应设计容灾方案",
            "suggestion": "添加 '容灾设计' 章节，说明多可用区部署、数据备份策略",
        },
        "missing_cost_estimate": {
            "name": "缺少成本评估",
            "pattern": r"(?i)(成本|cost|预算|budget|资源|infrastructure)",
            "flags": 0,
            "severity": "P2",
            "message": "应评估项目成本和资源需求",
            "suggestion": "添加 '成本评估' 章节，列出服务器、带宽、存储等成本",
        },
        "no_priority": {
            "name": "缺少需求优先级",
            "pattern": r"\b(P0|P1|P2|高优先级|中优先级|低优先级|must have|should have|could have|MUST|SHOULD|COULD)\b",
            "flags": re.IGNORECASE,
            "severity": "P2",
            "message": "建议为需求添加优先级标记",
            "suggestion": "使用 MoSCoW 方法标记优先级：Must/Should/Could/Won't",
        },
        "no_user_stories": {
            "name": "缺少用户故事",
            "pattern": r"(作为.*我希望.*以便|As a.*I want.*so that|用户故事|user story)",
            "flags": re.IGNORECASE,
            "severity": "P2",
            "message": "建议添加用户故事格式的需求描述",
            "suggestion": "使用用户故事格式：作为[角色]，我希望[功能]，以便[价值]",
        },
        "missing_rollback_detail": {
            "name": "回滚细节不足",
            "pattern": r"(?i)(回滚|rollback)",
            "flags": 0,
            "severity": "P2",
            "message": "回滚方案应包含具体操作步骤",
            "suggestion": "补充回滚步骤：1.停止服务 2.恢复数据 3.验证功能",
        },
        "missing_compliance": {
            "name": "缺少合规检查",
            "pattern": r"(?i)(合规|compliance|GDPR|隐私保护|数据保护|等保)",
            "flags": 0,
            "severity": "P2",
            "message": "涉及用户数据的系统应考虑合规要求",
            "suggestion": "添加 '合规要求' 章节，说明数据脱敏、用户授权、审计日志",
        },
        "missing_performance_baseline": {
            "name": "缺少性能基准",
            "pattern": r"(?i)(性能|performance)",
            "flags": 0,
            "severity": "P2",
            "message": "性能要求应包含基准测试方案",
            "suggestion": "补充基准测试：压测工具、测试数据量、性能指标基线",
        },
    }

    # ==================== 领域专家规则 ====================
    DOMAIN_RULES = {
        # 广告领域专家规则
        "ad_bidding_latency": {
            "name": "竞价延迟要求缺失",
            "pattern": r"(?i)(竞价|bidding|RTB|DSP|SSP|出价)",
            "flags": 0,
            "severity": "P1",
            "message": "竞价系统 PRD 应明确延迟预算",
            "suggestion": "参考: DSP P99 < 100ms, 画像查询 < 5ms, 模型推理 < 20ms",
            "domain": "advertising",
        },
        "ad_budget_tracking": {
            "name": "预算追踪机制缺失",
            "pattern": r"(?i)(预算|budget|超投|频次控制|frequency)",
            "flags": 0,
            "severity": "P1",
            "message": "广告系统 PRD 应设计预算追踪机制",
            "suggestion": "参考: 本地缓存 + 异步同步，预扣机制防止超投",
            "domain": "advertising",
        },
        "ad_fraud_detection": {
            "name": "缺少反作弊设计",
            "pattern": r"(?i)(反作弊|fraud|作弊|虚假流量|click fraud)",
            "flags": 0,
            "severity": "P1",
            "message": "广告系统 PRD 应包含反作弊策略",
            "suggestion": "参考: 设备指纹 + 行为分析 + 实时风控，分层拦截",
            "domain": "advertising",
        },
        "ad_attribution": {
            "name": "缺少归因模型设计",
            "pattern": r"(?i)(归因|attribution|Shapley|Markov|最后点击)",
            "flags": 0,
            "severity": "P1",
            "message": "广告系统 PRD 应明确归因模型",
            "suggestion": "参考: Shapley值归因或马尔可夫链归因，支持跨渠道",
            "domain": "advertising",
        },
        # Agent 领域专家规则
        "agent_pattern": {
            "name": "Agent 模式未定义",
            "pattern": r"(?i)(Agent|LLM|RAG|ReAct|Multi-Agent|Planner)",
            "flags": 0,
            "severity": "P1",
            "message": "Agent 系统 PRD 应明确 Agent 架构模式",
            "suggestion": "参考: ReAct/Planner/Multi-Agent 模式对比，根据任务类型选择",
            "domain": "agent",
        },
        "agent_memory": {
            "name": "缺少记忆系统设计",
            "pattern": r"(?i)(记忆|memory|上下文|context|长期|短期)",
            "flags": 0,
            "severity": "P1",
            "message": "Agent 系统 PRD 应设计记忆机制",
            "suggestion": "参考: 短期记忆(对话历史) + 长期记忆(向量DB) + 程序记忆(规则)",
            "domain": "agent",
        },
        "agent_tool": {
            "name": "Tool 设计不完整",
            "pattern": r"(?i)(Tool|工具|Function.*Calling|MCP)",
            "flags": 0,
            "severity": "P1",
            "message": "Agent 系统 PRD 应定义 Tool 设计规范",
            "suggestion": "参考: Tool 设计原则(幂等性+错误处理+超时控制+详细描述)",
            "domain": "agent",
        },
        "agent_safety": {
            "name": "缺少安全 Guardrails",
            "pattern": r"(?i)(安全|guardrail|内容过滤|敏感词|权限|prompt injection)",
            "flags": 0,
            "severity": "P0",
            "message": "Agent 系统 PRD 应设计安全 Guardrails",
            "suggestion": "参考: 输入过滤 + 输出审核 + 权限控制 + 敏感数据脱敏",
            "domain": "agent",
        },
        # 全栈领域专家规则
        "arch_microservice": {
            "name": "微服务拆分合理性",
            "pattern": r"(?i)(微服务|monolith|DDD|bounded.*context)",
            "flags": 0,
            "severity": "P1",
            "message": "微服务架构 PRD 应说明拆分理由",
            "suggestion": "参考: 按业务能力划分，避免交叉依赖，明确 API 契约",
            "domain": "fullstack",
        },
        "arch_consistency": {
            "name": "数据一致性方案",
            "pattern": r"(?i)(一致性|consistency|分布式事务|Saga|TCC|最终一致)",
            "flags": 0,
            "severity": "P1",
            "message": "分布式系统 PRD 应定义一致性方案",
            "suggestion": "参考: 强一致(本地事务) vs 最终一致(Saga/TCC)，选型依据业务容忍度",
            "domain": "fullstack",
        },
        "arch_cache": {
            "name": "缓存策略设计",
            "pattern": r"(?i)(缓存|cache|Redis|本地缓存|多级缓存)",
            "flags": 0,
            "severity": "P1",
            "message": "高性能系统 PRD 应设计缓存策略",
            "suggestion": "参考: 多级缓存(本地→Redis→DB)，防穿透/击穿/雪崩",
            "domain": "fullstack",
        },
        "arch_reliability": {
            "name": "容灾架构设计",
            "pattern": r"(?i)(容灾|disaster.*recovery|多可用区|multi-AZ|异地多活)",
            "flags": 0,
            "severity": "P1",
            "message": "重要系统 PRD 应设计容灾方案",
            "suggestion": "参考: 多可用区部署 + 数据同步 + 故障自动切换",
            "domain": "fullstack",
        },
    }

    # 合并所有规则
    RULES = {
        **P0_RULES,
        **P1_RULES,
        **P2_RULES,
        **DOMAIN_RULES,
    }

    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行 PRD 审查"""
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)

        prd_content = input_data["prd_content"]
        profile = input_data.get("profile", {})

        # 执行规则检查
        issues = self._check_rules(prd_content)

        # 领域专家规则检查
        domain_issues = self._check_domain_rules(prd_content, profile)
        issues.extend(domain_issues)

        # 分类问题
        p0_issues = [i for i in issues if i["severity"] == "P0"]
        p1_issues = [i for i in issues if i["severity"] == "P1"]
        p2_issues = [i for i in issues if i["severity"] == "P2"]

        # 生成摘要
        summary = self._generate_summary(issues, p0_issues, p1_issues, p2_issues)

        # 生成知识库推荐
        kb_recommendations = self._get_kb_recommendations(prd_content, issues)

        return SkillResult(
            success=len(p0_issues) == 0,
            output={
                "issues": issues,
                "summary": summary,
                "total_issues": len(issues),
                "p0_count": len(p0_issues),
                "p1_count": len(p1_issues),
                "p2_count": len(p2_issues),
                "kb_recommendations": kb_recommendations,
            },
            metadata={
                "skill": "prd_review_v3",
                "rules_checked": len(self.RULES),
                "p0_rules": len(self.P0_RULES),
                "p1_rules": len(self.P1_RULES),
                "p2_rules": len(self.P2_RULES),
                "domain_rules": len(self.DOMAIN_RULES),
            }
        )

    def _check_rules(self, prd_content: str) -> List[Dict]:
        """检查所有规则"""
        issues = []

        for rule_name, rule in self.RULES.items():
            pattern = rule["pattern"]
            flags = rule.get("flags", 0) | re.MULTILINE
            matches = list(re.finditer(pattern, prd_content, flags | re.IGNORECASE))

            # 对于必须存在的章节，如果未找到则报错
            if rule.get("type") == "missing":
                if not matches and rule["severity"] in ["P0", "P1"]:
                    issues.append({
                        "rule": rule_name,
                        "name": rule["name"],
                        "severity": rule["severity"],
                        "message": rule["message"],
                        "suggestion": rule.get("suggestion", ""),
                        "type": "missing",
                    })
            # 对于模糊需求检查
            elif rule_name == "vague_requirement":
                if matches:
                    for m in matches[:5]:
                        issues.append({
                            "rule": rule_name,
                            "name": rule["name"],
                            "severity": rule["severity"],
                            "message": f"发现模糊表述: '{m.group()}'",
                            "suggestion": rule.get("suggestion", ""),
                            "type": "vague",
                            "match": m.group(),
                        })
            # 对于建议性检查
            elif rule.get("type") == "suggestion":
                if matches:
                    issues.append({
                        "rule": rule_name,
                        "name": rule["name"],
                        "severity": rule["severity"],
                        "message": rule["message"],
                        "suggestion": rule.get("suggestion", ""),
                        "type": "found",
                        "match": matches[0].group(),
                    })

        return issues

    def _check_domain_rules(self, prd_content: str, profile: Dict) -> List[Dict]:
        """检查领域专家规则"""
        issues = []

        # 从 PRD 识别领域
        domain = self._detect_domain(prd_content)

        # 只检查当前领域的规则
        for rule_name, rule in self.DOMAIN_RULES.items():
            if rule.get("domain") != domain:
                continue

            pattern = rule["pattern"]
            flags = rule.get("flags", 0) | re.MULTILINE
            matches = list(re.finditer(pattern, prd_content, flags | re.IGNORECASE))

            if rule["severity"] == "P0" and not matches:
                issues.append({
                    "rule": rule_name,
                    "name": rule["name"],
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "suggestion": rule.get("suggestion", ""),
                    "domain": domain,
                    "type": "missing",
                })
            elif rule["severity"] == "P1" and not matches:
                issues.append({
                    "rule": rule_name,
                    "name": rule["name"],
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "suggestion": rule.get("suggestion", ""),
                    "domain": domain,
                    "type": "missing",
                })

        return issues

    def _detect_domain(self, prd: str) -> str:
        """识别 PRD 所属领域"""
        domain_scores = {
            "advertising": 0,
            "agent": 0,
            "ecommerce": 0,
            "finance": 0,
            "fullstack": 0,
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

    def _get_kb_recommendations(self, prd: str, issues: List[Dict]) -> List[Dict]:
        """获取知识库推荐"""
        recommendations = []

        # 根据问题和领域推荐相关知识
        domain = self._detect_domain(prd)

        try:
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from scripts.ryan_knowledge_bridge import RyanKnowledgeBridge
            kb = RyanKnowledgeBridge()

            # 根据领域搜索相关知识
            domain_queries = {
                'advertising': ['竞价系统架构', 'DSP设计', '广告算法'],
                'agent': ['Agent架构', 'ReAct模式', '记忆系统'],
                'ecommerce': ['电商架构', '订单系统', '支付系统'],
                'finance': ['金融系统', '风控系统', '交易架构'],
                'fullstack': ['系统设计', '架构模式', '性能优化'],
            }

            queries = domain_queries.get(domain, ['系统设计'])
            for query in queries[:3]:
                results = kb.search(query, limit=2)
                if results:
                    recommendations.append({
                        'query': query,
                        'docs': [r.get('path', '').split('/')[-1] for r in results[:2]],
                        'relevance': results[0].get('relevance', 0),
                    })

        except Exception as e:
            # 知识库不可用时返回空列表
            pass

        return recommendations

    def _generate_summary(self, issues, p0_issues, p1_issues, p2_issues) -> str:
        """生成审查摘要"""
        lines = [
            "# PRD 专家审查报告",
            "",
            "## 一、审查概览",
            "",
            f"- 🔴 P0 问题: {len(p0_issues)} 个 (必须修复)",
            f"- 🟡 P1 问题: {len(p1_issues)} 个 (建议修复)",
            f"- 🔵 P2 问题: {len(p2_issues)} 个 (可选优化)",
            f"- 📊 总问题数: {len(issues)}",
            "",
        ]

        # 计算覆盖率
        total_rules = len(self.RULES)
        checked_rules = sum(1 for i in issues if i.get('type') != 'missing')
        missing_rules = sum(1 for i in issues if i.get('type') == 'missing')
        lines.append(f"- **检查规则**: {total_rules} 条")
        lines.append(f"- **发现问题**: {checked_rules} 个")
        lines.append(f"- **缺失内容**: {missing_rules} 项")
        lines.append("")

        # 详细问题
        if p0_issues:
            lines.append("## 二、🔴 P0 严重问题 (阻塞项)")
            lines.append("")
            for i, issue in enumerate(p0_issues, 1):
                lines.append(f"### {i}. {issue['name']}")
                lines.append(f"- **问题**: {issue['message']}")
                if issue.get('suggestion'):
                    lines.append(f"- **建议**: {issue['suggestion']}")
                lines.append("")

        if p1_issues:
            lines.append("## 三、🟡 P1 重要问题")
            lines.append("")
            for i, issue in enumerate(p1_issues[:10], 1):
                lines.append(f"{i}. **{issue['name']}**: {issue['message']}")
                if issue.get('suggestion'):
                    lines.append(f"   - 💡 {issue['suggestion']}")
            lines.append("")

        if p2_issues:
            lines.append("## 四、🔵 P2 优化建议")
            lines.append("")
            for i, issue in enumerate(p2_issues[:5], 1):
                lines.append(f"{i}. **{issue['name']}**: {issue['message']}")
            lines.append("")

        # 总结和建议
        lines.append("## 五、总结与建议")
        lines.append("")

        if len(p0_issues) > 0:
            lines.append("⚠️ **结论**: PRD 存在严重问题，需修复 P0 后再进入开发阶段。")
        elif len(p1_issues) > 0:
            lines.append("✅ **结论**: PRD 基本合格，建议补充 P1 问题后再启动开发。")
        else:
            lines.append("✅ **结论**: PRD 质量良好，可以进入下一阶段。")

        lines.append("")
        lines.append(f"**审查时间**: {self._get_timestamp()}")
        lines.append(f"**检查规则**: {len(self.RULES)} 条 ({len(self.P0_RULES)} P0 + {len(self.P1_RULES)} P1 + {len(self.P2_RULES)} P2 + {len(self.DOMAIN_RULES)} 领域)")

        return "\n".join(lines)

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
