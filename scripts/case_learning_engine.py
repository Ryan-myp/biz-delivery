"""
Case Learning Engine v2.0 - 资深案例学习系统
从历史审查案例中学习，持续优化专家判断

核心功能:
  1. 案例存储与检索
  2. 模式识别与学习
  3. 规则权重优化
  4. 成功案例推荐
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class ExpertCase:
    """专家案例"""
    case_id: str
    domain: str
    sub_domain: str  # 子领域如 advertising+ml_ops
    prd_summary: str
    issues_found: List[Dict]
    solutions: List[Dict]
    outcome: str  # success/failure/unknown
    lessons: List[str]
    quality_score: int  # 1-100
    timestamp: str


class CaseLearningEngine:
    """案例学习引擎"""

    def __init__(self, cases_path: str = None):
        self.cases_path = Path(cases_path) if cases_path else Path('/Users/yanping.ma/biz-delivery/knowledge/cases')
        self.cases_path.mkdir(parents=True, exist_ok=True)
        self.cases: List[ExpertCase] = []
        self.patterns: Dict[str, Dict] = {}  # 学习到的模式
        self.rule_weights: Dict[str, float] = {}  # 规则权重
        self._load_cases()
        self._load_patterns()

    def _load_cases(self):
        """加载历史案例"""
        case_files = list(self.cases_path.glob('*.json'))
        for case_file in sorted(case_files, key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                with open(case_file) as f:
                    data = json.load(f)
                    case = ExpertCase(
                        case_id=data.get('case_id', ''),
                        domain=data.get('domain', ''),
                        sub_domain=data.get('sub_domain', ''),
                        prd_summary=data.get('prd_summary', ''),
                        issues_found=data.get('issues_found', []),
                        solutions=data.get('solutions', []),
                        outcome=data.get('outcome', 'unknown'),
                        lessons=data.get('lessons', []),
                        quality_score=data.get('quality_score', 50),
                        timestamp=data.get('timestamp', ''),
                    )
                    self.cases.append(case)
            except Exception:
                continue

    def _load_patterns(self):
        """加载学习到的模式"""
        patterns_file = self.cases_path / 'patterns.json'
        if patterns_file.exists():
            try:
                with open(patterns_file) as f:
                    self.patterns = json.load(f)
            except Exception:
                self.patterns = {}

    def save_case(self, case: ExpertCase):
        """保存案例"""
        case_file = self.cases_path / f"{case.case_id}.json"
        data = asdict(case)
        with open(case_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.cases.append(case)

    def get_similar_cases(self, domain: str, issue_type: str, limit: int = 5) -> List[ExpertCase]:
        """获取相似案例"""
        similar = []
        for case in self.cases:
            score = 0
            # 领域匹配
            if case.domain == domain or case.sub_domain.startswith(domain):
                score += 10
            # 问题类型匹配
            for issue in case.issues_found:
                if issue_type.lower() in issue.get('name', '').lower() or \
                   issue_type.lower() in issue.get('message', '').lower():
                    score += 5
                    break
            # 结果匹配
            if case.outcome == 'success':
                score += 3
            if score > 0:
                similar.append((score, case))
        similar.sort(key=lambda x: -x[0])
        return [c for _, c in similar[:limit]]

    def get_success_patterns(self, domain: str) -> List[str]:
        """获取成功案例模式"""
        patterns = []
        for case in self.cases:
            if case.domain == domain and case.outcome == 'success':
                patterns.extend(case.lessons)
        return list(set(patterns))[:10]

    def get_failure_patterns(self, domain: str) -> List[str]:
        """获取失败案例模式"""
        patterns = []
        for case in self.cases:
            if case.domain == domain and case.outcome == 'failure':
                patterns.extend(case.lessons)
        return list(set(patterns))[:10]

    def learn_from_case(self, case: ExpertCase):
        """从案例中学习"""
        # 更新规则权重
        for issue in case.issues_found:
            rule_name = issue.get('rule', issue.get('name', 'unknown'))
            if rule_name not in self.rule_weights:
                self.rule_weights[rule_name] = 1.0
            # 根据结果调整权重
            if case.outcome == 'success':
                self.rule_weights[rule_name] = min(self.rule_weights.get(rule_name, 1.0) + 0.1, 2.0)
            elif case.outcome == 'failure':
                self.rule_weights[rule_name] = max(self.rule_weights.get(rule_name, 1.0) - 0.05, 0.5)

        # 保存模式
        self._save_patterns()

    def _save_patterns(self):
        """保存模式"""
        patterns_file = self.cases_path / 'patterns.json'
        with open(patterns_file, 'w') as f:
            json.dump({
                'patterns': self.patterns,
                'rule_weights': self.rule_weights,
                'updated_at': datetime.now().isoformat(),
            }, f, indent=2, ensure_ascii=False)

    def generate_recommendations(self, domain: str, prd_content: str) -> List[Dict]:
        """生成建议"""
        recommendations = []

        # 基于成功案例
        success_patterns = self.get_success_patterns(domain)
        for pattern in success_patterns[:3]:
            recommendations.append({
                'type': 'best_practice',
                'source': '成功案例',
                'recommendation': pattern,
                'confidence': 0.8,
            })

        # 基于失败案例
        failure_patterns = self.get_failure_patterns(domain)
        for pattern in failure_patterns[:2]:
            recommendations.append({
                'type': 'anti_pattern',
                'source': '失败教训',
                'recommendation': f"避免: {pattern}",
                'confidence': 0.7,
            })

        # 基于规则权重
        for rule_name, weight in sorted(self.rule_weights.items(), key=lambda x: -x[1])[:3]:
            if weight > 1.5:  # 高权重规则
                recommendations.append({
                    'type': 'high_priority_rule',
                    'source': '规则学习',
                    'recommendation': f"重点关注: {rule_name}",
                    'confidence': weight / 2.0,
                })

        return recommendations

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self.cases)
        success = sum(1 for c in self.cases if c.outcome == 'success')
        failure = sum(1 for c in self.cases if c.outcome == 'failure')
        unknown = sum(1 for c in self.cases if c.outcome == 'unknown')

        by_domain = {}
        for case in self.cases:
            d = case.domain
            by_domain[d] = by_domain.get(d, 0) + 1

        return {
            'total_cases': total,
            'success_rate': f"{success/total*100:.1f}%" if total > 0 else "0%",
            'by_domain': by_domain,
            'by_outcome': {'success': success, 'failure': failure, 'unknown': unknown},
            'rules_tracked': len(self.rule_weights),
        }


# 预置示例案例
SAMPLE_CASES = [
    {
        "case_id": "ad-bidding-001",
        "domain": "advertising",
        "sub_domain": "advertising+ml_ops",
        "prd_summary": "DSP竞价引擎优化，P99延迟从150ms降到80ms",
        "issues_found": [
            {"name": "画像查询同步阻塞", "severity": "P0", "message": "画像查询阻塞主线程"},
            {"name": "预算追踪竞态", "severity": "P0", "message": "并发预算扣减存在竞态"},
        ],
        "solutions": [
            {"solution": "画像本地缓存+异步预取", "effective": True},
            {"solution": "预扣机制+本地计数器", "effective": True},
        ],
        "outcome": "success",
        "lessons": [
            "画像查询必须异步化，P99延迟是关键指标",
            "预算追踪使用预扣机制防止超投",
            "本地缓存TTL设置1-5秒平衡一致性和性能",
        ],
        "quality_score": 95,
        "timestamp": "2024-01-15T10:00:00"
    },
    {
        "case_id": "agent-mem-001",
        "domain": "agent",
        "sub_domain": "agent",
        "prd_summary": "Agent记忆系统设计，支持长期记忆检索",
        "issues_found": [
            {"name": "记忆检索无缓存", "severity": "P1", "message": "每次检索都调用向量DB"},
            {"name": "Token无成本控制", "severity": "P1", "message": "长对话Token无限增长"},
        ],
        "solutions": [
            {"solution": "Redis缓存热点记忆", "effective": True},
            {"solution": "上下文压缩+模型分级", "effective": True},
        ],
        "outcome": "success",
        "lessons": [
            "记忆检索必须加缓存，否则延迟不可接受",
            "Token成本必须设置上限，防止长对话失控",
            "短期记忆用内存，长期记忆用向量DB",
        ],
        "quality_score": 90,
        "timestamp": "2024-02-01T14:00:00"
    },
    {
        "case_id": "ecom-order-001",
        "domain": "ecommerce",
        "sub_domain": "ecommerce",
        "prd_summary": "电商订单系统，双11高并发场景",
        "issues_found": [
            {"name": "库存扣减无锁", "severity": "P0", "message": "并发下单导致超卖"},
            {"name": "支付回调无幂等", "severity": "P0", "message": "重复回调导致重复发货"},
        ],
        "solutions": [
            {"solution": "分布式锁+预扣库存", "effective": True},
            {"solution": "业务唯一键幂等控制", "effective": True},
        ],
        "outcome": "success",
        "lessons": [
            "高并发场景库存必须预扣+分布式锁",
            "支付回调必须幂等，使用业务唯一键",
            "双11场景必须做压测，P99<200ms",
        ],
        "quality_score": 88,
        "timestamp": "2024-03-10T09:00:00"
    },
    {
        "case_id": "fin-risk-001",
        "domain": "finance",
        "sub_domain": "finance+security",
        "prd_summary": "金融交易平台，实时风控系统",
        "issues_found": [
            {"name": "风控规则硬编码", "severity": "P1", "message": "规则变更需要重新发布"},
            {"name": "交易金额浮点计算", "severity": "P0", "message": "浮点数精度丢失导致资金差异"},
        ],
        "solutions": [
            {"solution": "规则引擎动态加载", "effective": True},
            {"solution": "Decimal精确计算", "effective": True},
        ],
        "outcome": "success",
        "lessons": [
            "风控规则必须动态配置，支持热更新",
            "金融金额必须使用Decimal，禁止浮点",
            "操作日志必须不可篡改，支持审计",
        ],
        "quality_score": 92,
        "timestamp": "2024-04-05T16:00:00"
    },
    {
        "case_id": "cloud-k8s-001",
        "domain": "cloud_native",
        "sub_domain": "cloud_native+devops",
        "prd_summary": "K8s集群迁移，GitOps部署流程",
        "issues_found": [
            {"name": "容器无资源限制", "severity": "P1", "message": "单Pod占用全部节点资源"},
            {"name": "缺少健康检查", "severity": "P1", "message": "异常Pod持续接收流量"},
        ],
        "solutions": [
            {"solution": "设置requests/limits", "effective": True},
            {"solution": "添加liveness/readiness probe", "effective": True},
        ],
        "outcome": "success",
        "lessons": [
            "所有容器必须设置资源限制",
            "健康检查是服务可靠性的基础",
            "使用LimitRange强制默认限制",
        ],
        "quality_score": 85,
        "timestamp": "2024-05-20T11:00:00"
    },
    {
        "case_id": "sec-zero-001",
        "domain": "security",
        "sub_domain": "security",
        "prd_summary": "零信任安全架构设计",
        "issues_found": [
            {"name": "API无访问控制", "severity": "P0", "message": "敏感接口未做权限校验"},
            {"name": "密钥硬编码", "severity": "P0", "message": "生产密钥写在代码中"},
        ],
        "solutions": [
            {"solution": "RBAC权限控制", "effective": True},
            {"solution": "Vault密钥管理", "effective": True},
        ],
        "outcome": "success",
        "lessons": [
            "所有API必须做权限校验",
            "密钥必须使用Vault等密钥管理服务",
            "定期扫描代码仓库泄露的密钥",
        ],
        "quality_score": 90,
        "timestamp": "2024-06-15T08:00:00"
    },
]


def init_sample_cases(cases_path: str = None):
    """初始化示例案例"""
    engine = CaseLearningEngine(cases_path)
    
    # 只添加不存在的案例
    existing_ids = {c.case_id for c in engine.cases}
    
    for sample in SAMPLE_CASES:
        if sample['case_id'] not in existing_ids:
            case = ExpertCase(**sample)
            engine.save_case(case)
            engine.learn_from_case(case)
    
    return engine


if __name__ == '__main__':
    import sys
    engine = init_sample_cases()
    stats = engine.get_stats()
    print(f"总案例数: {stats['total_cases']}")
    print(f"成功率: {stats['success_rate']}")
    print(f"领域分布: {stats['by_domain']}")
    print(f"规则权重: {stats['rules_tracked']} 条")
