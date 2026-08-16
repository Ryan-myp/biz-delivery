"""
AI Decision Engine v1.0 - AI辅助决策引擎
基于知识库和案例学习的智能决策支持

核心能力:
  1. 智能模式匹配 - 从历史案例中匹配相似场景
  2. 风险预测 - 基于历史数据预测项目风险
  3. 方案推荐 - 生成最优技术方案建议
  4. 决策解释 - 提供可解释的决策依据
  5. 持续学习 - 从新案例中优化决策模型
"""
import re
import json
import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import Counter


@dataclass
class DecisionPattern:
    """决策模式"""
    pattern_id: str
    name: str
    description: str
    indicators: List[str]
    weight: float  # 0-1 重要性权重
    success_rate: float  # 历史成功率
    sources: List[str]  # 来源案例ID


@dataclass
class RiskPrediction:
    """风险预测"""
    risk_type: str
    probability: float  # 0-1 发生概率
    impact: str  # 高/中/低
    mitigation: str
    confidence: float  # 预测置信度


@dataclass
class Recommendation:
    """推荐方案"""
    category: str
    title: str
    description: str
    priority: str  # P0/P1/P2
    confidence: float
    evidence: List[str]  # 支持证据


class AIDecisionEngine:
    """AI决策引擎"""

    # 预置决策模式
    DECISION_PATTERNS = {
        'performance_optimization': DecisionPattern(
            pattern_id='perf_opt',
            name='性能优化场景',
            description='系统面临性能瓶颈，需要优化响应时间或吞吐量',
            indicators=['P99', '延迟', 'QPS', '吞吐量', '性能', '优化'],
            weight=0.9,
            success_rate=0.85,
            sources=[],
        ),
        'high_concurrency': DecisionPattern(
            pattern_id='high_conc',
            name='高并发场景',
            description='系统需要处理大量并发请求，关注锁和竞态问题',
            indicators=['并发', '锁', '竞态', '分布式锁', 'Redis'],
            weight=0.85,
            success_rate=0.80,
            sources=[],
        ),
        'consistency_critical': DecisionPattern(
            pattern_id='consistency',
            name='强一致性场景',
            description='系统对数据一致性要求极高，如金融交易',
            indicators=['一致', '事务', 'ACID', '金融', '交易', '资金'],
            weight=0.95,
            success_rate=0.90,
            sources=[],
        ),
        'realtime_system': DecisionPattern(
            pattern_id='realtime',
            name='实时计算场景',
            description='系统需要实时处理数据流，关注延迟和背压',
            indicators=['实时', '流', 'Kafka', 'Flink', '延迟'],
            weight=0.80,
            success_rate=0.75,
            sources=[],
        ),
        'security_sensitive': DecisionPattern(
            pattern_id='security',
            name='安全敏感场景',
            description='系统处理敏感数据，需要强化安全措施',
            indicators=['加密', '安全', '鉴权', '权限', '零信任'],
            weight=0.90,
            success_rate=0.88,
            sources=[],
        ),
        'scalability_required': DecisionPattern(
            pattern_id='scalability',
            name='高可扩展场景',
            description='系统需要支持水平扩展，关注无状态设计',
            indicators=['扩展', '弹性', 'Kubernetes', '水平', '微服务'],
            weight=0.75,
            success_rate=0.82,
            sources=[],
        ),
        'ml_integration': DecisionPattern(
            pattern_id='ml_int',
            name='ML集成场景',
            description='系统需要集成机器学习模型，关注推理延迟',
            indicators=['模型', 'ML', '推理', '特征', '训练'],
            weight=0.70,
            success_rate=0.78,
            sources=[],
        ),
    }

    def __init__(self, cases_engine=None, kb_engine=None):
        self.cases = cases_engine
        self.kb = kb_engine
        self.decision_log: List[Dict] = []
        self.model_weights = self._load_model_weights()

    def _load_model_weights(self) -> Dict:
        """加载模型权重"""
        weights_file = Path('./.cache/model_weights.json')
        if weights_file.exists():
            try:
                return json.loads(weights_file.read_text())
            except:
                pass
        return {
            'performance': 1.0,
            'consistency': 1.0,
            'security': 1.0,
            'scalability': 1.0,
        }

    def _save_model_weights(self):
        """保存模型权重"""
        weights_file = Path('./.cache/model_weights.json')
        weights_file.parent.mkdir(parents=True, exist_ok=True)
        weights_file.write_text(json.dumps(self.model_weights, indent=2))

    def analyze(self, prd_content: str, domain: str) -> Dict:
        """执行AI决策分析"""
        # 1. 模式匹配
        patterns = self._match_patterns(prd_content)

        # 2. 风险预测
        risks = self._predict_risks(prd_content, domain, patterns)

        # 3. 方案推荐
        recommendations = self._generate_recommendations(prd_content, domain, patterns, risks)

        # 4. 决策摘要
        summary = self._generate_summary(patterns, risks, recommendations)

        return {
            'domain': domain,
            'patterns_detected': [p.name for p in patterns],
            'risk_predictions': [asdict(r) for r in risks],
            'recommendations': [asdict(r) for r in recommendations],
            'summary': summary,
            'timestamp': datetime.now().isoformat(),
        }

    def _match_patterns(self, prd: str) -> List[DecisionPattern]:
        """匹配决策模式"""
        matched = []
        prd_lower = prd.lower()

        for pattern in self.DECISION_PATTERNS.values():
            score = 0
            for indicator in pattern.indicators:
                if indicator.lower() in prd_lower:
                    score += 1

            # 加权评分
            weighted_score = score * pattern.weight

            if weighted_score > 0:
                # 计算置信度
                confidence = min(1.0, weighted_score / (len(pattern.indicators) * pattern.weight) + 0.3)
                pattern_copy = DecisionPattern(
                    **{k: v for k, v in asdict(pattern).items() if k != 'sources'},
                )
                pattern_copy.sources = []  # 清空来源
                matched.append((confidence, pattern_copy))

        # 按置信度排序
        matched.sort(key=lambda x: -x[0])
        return [p for _, p in matched[:5]]  # 最多返回5个

    def _predict_risks(self, prd: str, domain: str, patterns: List[DecisionPattern]) -> List[RiskPrediction]:
        """预测风险"""
        risks = []

        # 基于模式的风险分析
        pattern_risk_map = {
            'perf_opt': RiskPrediction(
                risk_type='性能不达标',
                probability=0.3 if any('P99' in prd or '延迟' in prd for _ in [1]) else 0.5,
                impact='高',
                mitigation='引入缓存层+异步化+连接池优化',
                confidence=0.8,
            ),
            'high_conc': RiskPrediction(
                risk_type='并发竞态',
                probability=0.4,
                impact='高',
                mitigation='分布式锁+乐观锁+幂等设计',
                confidence=0.85,
            ),
            'consistency': RiskPrediction(
                risk_type='数据不一致',
                probability=0.2,
                impact='严重',
                mitigation='Saga/TCC分布式事务+对账机制',
                confidence=0.9,
            ),
            'security': RiskPrediction(
                risk_type='安全漏洞',
                probability=0.3,
                impact='严重',
                mitigation='零信任架构+密钥管理+审计日志',
                confidence=0.88,
            ),
            'realtime': RiskPrediction(
                risk_type='消息堆积',
                probability=0.35,
                impact='中',
                mitigation='背压机制+分区消费+扩容策略',
                confidence=0.75,
            ),
            'scalability': RiskPrediction(
                risk_type='扩展瓶颈',
                probability=0.25,
                impact='中',
                mitigation='无状态设计+分库分表+CDN',
                confidence=0.82,
            ),
        }

        pattern_names = {p.name for p in patterns}
        for name, risk in pattern_risk_map.items():
            if name.lower() in ' '.join(pattern_names).lower() or \
               any(ind in prd for ind in risk.risk_type):
                risks.append(risk)

        # 添加通用风险
        if 'P99' in prd or '延迟' in prd:
            risks.append(RiskPrediction(
                risk_type='SLA违约风险',
                probability=0.4,
                impact='高',
                mitigation='设置熔断降级+容量规划+监控告警',
                confidence=0.7,
            ))

        if '加密' in prd or '安全' in prd:
            risks.append(RiskPrediction(
                risk_type='密钥泄露风险',
                probability=0.15,
                impact='严重',
                mitigation='使用Vault+定期轮换+访问审计',
                confidence=0.9,
            ))

        return risks[:5]  # 最多5个风险

    def _generate_recommendations(self, prd: str, domain: str,
                                   patterns: List[DecisionPattern],
                                   risks: List[RiskPrediction]) -> List[Recommendation]:
        """生成推荐方案"""
        recommendations = []

        # 基于匹配模式的推荐
        for pattern in patterns:
            rec = self._get_pattern_recommendation(pattern, prd)
            if rec:
                recommendations.append(rec)

        # 基于风险的推荐
        for risk in risks:
            rec = Recommendation(
                category='risk_mitigation',
                title=f'缓解{risk.risk_type}',
                description=risk.mitigation,
                priority='P0' if risk.impact == '严重' else 'P1',
                confidence=risk.confidence,
                evidence=[f'风险预测: {risk.risk_type} (概率{risk.probability:.0%})'],
            )
            recommendations.append(rec)

        # 基于案例的推荐
        if self.cases:
            case_recs = self._get_case_recommendations(domain, prd)
            recommendations.extend(case_recs)

        # 排序: P0 > P1 > P2, 然后按置信度
        priority_order = {'P0': 0, 'P1': 1, 'P2': 2}
        recommendations.sort(key=lambda r: (priority_order.get(r.priority, 3), -r.confidence))

        return recommendations[:10]

    def _get_pattern_recommendation(self, pattern: DecisionPattern, prd: str) -> Optional[Recommendation]:
        """获取模式推荐"""
        rec_map = {
            'perf_opt': Recommendation(
                category='performance',
                title='性能优化方案',
                description='采用缓存+异步+连接池的组合优化策略',
                priority='P1',
                confidence=pattern.success_rate,
                evidence=[f'历史成功率: {pattern.success_rate:.0%}', f'模式匹配度: {pattern.weight:.0%}'],
            ),
            'high_conc': Recommendation(
                category='concurrency',
                title='高并发解决方案',
                description='使用Redis分布式锁+乐观锁+幂等设计',
                priority='P0',
                confidence=pattern.success_rate,
                evidence=['分布式锁防竞态', '乐观锁提升吞吐', '幂等保证一致性'],
            ),
            'consistency': Recommendation(
                category='consistency',
                title='强一致性方案',
                description='采用Saga模式+本地消息表+对账机制',
                priority='P0',
                confidence=pattern.success_rate,
                evidence=['金融级一致性要求', '补偿机制兜底'],
            ),
            'security': Recommendation(
                category='security',
                title='安全加固方案',
                description='实施零信任架构+密钥管理+操作审计',
                priority='P0',
                confidence=pattern.success_rate,
                evidence=['安全是基础', '合规要求'],
            ),
            'realtime': Recommendation(
                category='realtime',
                title='实时计算方案',
                description='Flink流处理+Kafka分区+背压控制',
                priority='P1',
                confidence=pattern.success_rate,
                evidence=['流式计算最佳实践'],
            ),
            'scalability': Recommendation(
                category='scalability',
                title='高可扩展方案',
                description='无状态服务+K8s HPA+分库分表',
                priority='P1',
                confidence=pattern.success_rate,
                evidence=['水平扩展标准方案'],
            ),
        }

        return rec_map.get(pattern.pattern_id)

    def _get_case_recommendations(self, domain: str, prd: str) -> List[Recommendation]:
        """基于案例的推荐"""
        if not self.cases:
            return []

        similar_cases = self.cases.get_similar_cases(domain, prd, limit=3)
        recommendations = []

        for case in similar_cases:
            for lesson in case.lessons[:2]:
                recommendations.append(Recommendation(
                    category='case_learning',
                    title=f'案例经验: {case.case_id}',
                    description=lesson,
                    priority='P2',
                    confidence=case.quality_score / 100,
                    evidence=[f'案例ID: {case.case_id}', f'结果: {case.outcome}'],
                ))

        return recommendations

    def _generate_summary(self, patterns: List[DecisionPattern],
                          risks: List[RiskPrediction],
                          recommendations: List[Recommendation]) -> Dict:
        """生成决策摘要"""
        # 计算综合风险评分
        risk_score = sum(r.probability * (3 if r.impact == '严重' else 2 if r.impact == '高' else 1)
                        for r in risks) / max(len(risks), 1)

        # 计算方案覆盖度
        categories = set(r.category for r in recommendations)
        coverage = len(categories) / 6 * 100  # 6个主要类别

        # 生成决策建议
        if risk_score > 2.0:
            overall_risk = '高'
        elif risk_score > 1.0:
            overall_risk = '中'
        else:
            overall_risk = '低'

        return {
            'matched_patterns': len(patterns),
            'total_risks': len(risks),
            'total_recommendations': len(recommendations),
            'risk_level': overall_risk,
            'risk_score': round(risk_score, 2),
            'coverage_rate': f'{coverage:.0f}%',
            'decision_quality': '优秀' if coverage > 80 else '良好' if coverage > 50 else '一般',
        }

    def learn_from_decision(self, prd: str, outcome: str, quality_score: int):
        """从决策结果中学习"""
        # 更新模式成功率
        patterns = self._match_patterns(prd)
        for pattern in patterns:
            if pattern.success_rate < quality_score / 100:
                # 调整权重
                self.model_weights[pattern.pattern_id] = min(
                    self.model_weights.get(pattern.pattern_id, 1.0) + 0.05, 2.0
                )

        self._save_model_weights()

        # 记录决策日志
        self.decision_log.append({
            'timestamp': datetime.now().isoformat(),
            'outcome': outcome,
            'quality_score': quality_score,
            'patterns': [p.name for p in patterns],
        })

    def get_decision_history(self, limit: int = 10) -> List[Dict]:
        """获取决策历史"""
        return self.decision_log[-limit:]


# 单例
_decision_engine = None

def get_decision_engine(cases_engine=None, kb_engine=None):
    """获取决策引擎单例"""
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = AIDecisionEngine(cases_engine, kb_engine)
    return _decision_engine


if __name__ == '__main__':
    import sys
    from scripts.case_learning_engine import CaseLearningEngine

    engine = AIDecisionEngine(cases_engine=CaseLearningEngine())

    prd = """# 广告竞价引擎优化
    QPS 5万 P99<100ms
    预扣预算防超投
    设备指纹反作弊
    """

    result = engine.analyze(prd, 'advertising')
    print(json.dumps(result, ensure_ascii=False, indent=2))
