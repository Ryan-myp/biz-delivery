"""
Industry Knowledge Base - 行业知识库
包含各行业的典型架构模式、最佳实践、常见问题
"""
import json
from typing import Dict, List, Any


class IndustryKnowledgeBase:
    """行业知识库"""

    # 电商行业知识
    ECOMMERCE = {
        'name': '电商行业',
        'patterns': {
            'order_flow': {
                'name': '订单流程',
                'stages': ['create', 'pay', 'ship', 'complete', 'refund'],
                'key_components': ['OrderService', 'PaymentGateway', 'InventoryManager'],
                'common_issues': ['库存超卖', '支付状态不一致', '订单超时取消'],
            },
            'recommendation': {
                'name': '推荐系统',
                'algorithms': ['collaborative_filtering', 'content_based', 'deep_learning'],
                'key_components': ['UserBehaviorTracker', 'FeatureExtractor', 'ModelService'],
                'common_issues': ['冷启动', '推荐多样性', '实时性'],
            },
            'promotion': {
                'name': '营销系统',
                'types': ['coupon', 'discount', 'bundle', 'flash_sale'],
                'key_components': ['PromotionEngine', 'CouponManager', 'PriceCalculator'],
                'common_issues': ['优惠叠加', '库存扣减时机', '并发控制'],
            },
        },
        'tech_stack': ['MySQL', 'Redis', 'Kafka', 'Elasticsearch', 'MongoDB'],
        'arch_patterns': ['微服务', 'DDD', 'CQRS'],
    }

    # 金融/支付行业知识
    FINANCE = {
        'name': '金融/支付行业',
        'patterns': {
            'payment_flow': {
                'name': '支付流程',
                'stages': ['init', 'authorize', 'capture', 'settle', 'reconcile'],
                'key_components': ['PaymentGateway', 'AccountService', 'RiskControl'],
                'common_issues': ['幂等性', '对账差异', '资金安全'],
            },
            'risk_control': {
                'name': '风控系统',
                'methods': ['rule_engine', 'ml_model', 'graph_analysis'],
                'key_components': ['RuleEngine', 'FraudDetector', 'LimitManager'],
                'common_issues': ['误判率', '实时性', '模型更新'],
            },
            'ledger': {
                'name': '账务系统',
                'principles': ['double_entry', 'atomic', 'auditable'],
                'key_components': ['LedgerService', 'AccountManager', 'TransactionRecorder'],
                'common_issues': ['金额精度', '对账一致性', '审计追踪'],
            },
        },
        'tech_stack': ['PostgreSQL', 'Redis', 'Kafka', 'Flink', 'HBase'],
        'arch_patterns': ['微服务', '事件溯源', 'Saga'],
    }

    # 社交/内容行业知识
    SOCIAL = {
        'name': '社交/内容行业',
        'patterns': {
            'feed_flow': {
                'name': 'Feed流',
                'models': ['push', 'pull', 'push_pull'],
                'key_components': ['FeedGenerator', 'ContentIndexer', 'RecommendationEngine'],
                'common_issues': ['延迟', '一致性', '计算量'],
            },
            'messaging': {
                'name': '即时消息',
                'features': ['online', 'offline', 'group', 'read_receipt'],
                'key_components': ['MessageService', 'PresenceManager', 'StorageEngine'],
                'common_issues': ['消息丢失', '乱序', '大群性能'],
            },
            'relation': {
                'name': '关系链',
                'models': [' follower', 'friend', 'follow'],
                'key_components': ['RelationService', 'GraphDatabase', 'CacheLayer'],
                'common_issues': ['并发写', '数据一致性', '查询性能'],
            },
        },
        'tech_stack': ['MySQL', 'Redis', 'Kafka', 'TencentIM', 'ES'],
        'arch_patterns': ['微服务', 'CQRS', 'Event Sourcing'],
    }

    # 物联网行业知识
    IOT = {
        'name': '物联网行业',
        'patterns': {
            'device_management': {
                'name': '设备管理',
                'lifecycle': ['register', 'activate', 'online', 'offline', 'decommission'],
                'key_components': ['DeviceService', 'ProvisioningService', 'OTAService'],
                'common_issues': ['设备在线状态', '并发连接', '协议适配'],
            },
            'telemetry': {
                'name': '遥测数据',
                'sources': ['sensor', 'actuator', 'gateway'],
                'key_components': ['TelemetryCollector', 'TimeSeriesDB', 'AlertEngine'],
                'common_issues': ['数据量大', '实时性', '存储成本'],
            },
            'command': {
                'name': '命令下发',
                'features': ['sync', 'async', 'batch'],
                'key_components': ['CommandService', 'DeviceProxy', 'ResultAggregator'],
                'common_issues': ['指令丢失', '执行超时', '状态同步'],
            },
        },
        'tech_stack': ['MQTT', 'InfluxDB', 'TimescaleDB', 'Kafka', 'Redis'],
        'arch_patterns': ['边缘计算', '流处理', '微服务'],
    }

    # 游戏行业知识
    GAMING = {
        'name': '游戏行业',
        'patterns': {
            'matchmaking': {
                'name': '匹配系统',
                'algorithms': ['elo', 'mmr', 'skill_based'],
                'key_components': ['MatchMaker', 'PlayerPool', 'QueueManager'],
                'common_issues': ['匹配时间', '平衡性', '服务器负载'],
            },
            'state_sync': {
                'name': '状态同步',
                'methods': ['lockstep', 'authoritative', 'prediction'],
                'key_components': ['GameState', 'SnapshotService', 'DiffService'],
                'common_issues': ['延迟', '一致性', '带宽'],
            },
            'leaderboard': {
                'name': '排行榜',
                'types': ['global', 'friend', 'clan', 'season'],
                'key_components': ['LeaderboardService', 'RankCalculator', 'RewardManager'],
                'common_issues': ['实时性', '缓存一致性', '刷榜'],
            },
        },
        'tech_stack': ['Redis', 'Kafka', 'gRPC', 'DynamoDB', ' Aerospike'],
        'arch_patterns': ['微服务', '事件驱动', 'CQRS'],
    }

    # 知识库
    KNOWLEDGE_BASE = {
        'ecommerce': ECOMMERCE,
        'finance': FINANCE,
        'social': SOCIAL,
        'iot': IOT,
        'gaming': GAMING,
    }

    def __init__(self):
        self.knowledge = self.KNOWLEDGE_BASE

    def get_industry_patterns(self, industry: str) -> Dict:
        """获取行业模式"""
        return self.knowledge.get(industry, {})

    def get_all_industries(self) -> List[str]:
        """获取所有行业"""
        return list(self.knowledge.keys())

    def generate_industry_report(self, industry: str, analysis_result: Dict) -> str:
        """生成行业分析报告"""
        patterns = self.get_industry_patterns(industry)
        if not patterns:
            return f"暂无 {industry} 行业知识库"

        lines = [
            f"# {patterns['name']} 行业分析报告",
            "",
            "## 典型架构模式",
            "",
        ]

        for pattern_name, pattern in patterns.get('patterns', {}).items():
            lines.append(f"### {pattern['name']}")
            lines.append(f"- 阶段: {', '.join(pattern.get('stages', []))}")
            lines.append(f"- 核心组件: {', '.join(pattern.get('key_components', []))}")
            lines.append(f"- 常见问题: {', '.join(pattern.get('common_issues', []))}")
            lines.append("")

        lines.append("## 技术栈建议")
        lines.append("")
        tech_stack = patterns.get('tech_stack', [])
        lines.append(", ".join(tech_stack))
        lines.append("")

        lines.append("## 架构模式建议")
        lines.append("")
        arch_patterns = patterns.get('arch_patterns', [])
        lines.append(", ".join(arch_patterns))

        return "\n".join(lines)


if __name__ == "__main__":
    kb = IndustryKnowledgeBase()
    
    print("可用行业:")
    for industry in kb.get_all_industries():
        print(f"  - {industry}")
    
    print("\n电商行业典型模式:")
    ecommerce = kb.get_industry_patterns('ecommerce')
    for pattern_name, pattern in ecommerce.get('patterns', {}).items():
        print(f"  {pattern['name']}: {', '.join(pattern.get('stages', []))}")
    
    print("\n示例报告:")
    print(kb.generate_industry_report('ecommerce', {}))
