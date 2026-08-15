"""
Expert Knowledge Integration - 专家知识集成模块
将 Ryan Personal Knowledge Base 的知识引入 biz-delivery
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class ExpertKnowledgeIntegrator:
    """专家知识集成器"""

    def __init__(self, kb_path: str = None):
        self.kb_path = Path(kb_path) if kb_path else Path('/Users/yanping.ma/ryan-personal-knowledge')
        self.bridge = None
        self._init_bridge()

    def _init_bridge(self):
        """初始化桥接器"""
        from .ryan_knowledge_bridge import RyanKnowledgeBridge
        self.bridge = RyanKnowledgeBridge(str(self.kb_path))

    def get_architecture_patterns(self) -> Dict:
        """获取架构模式知识"""
        patterns = {
            'microservice': [],
            'event_sourcing': [],
            'cqrs': [],
            'ddd': [],
            'saga': [],
            'circuit_breaker': [],
        }
        
        # 搜索相关文档
        for query in ['微服务架构', 'Event Sourcing', 'CQRS', 'DDD', 'Saga模式', '熔断器']:
            results = self.bridge.search(query, 'architecture')
            patterns[query[:4]] = results[:3]
        
        return patterns

    def get_best_practices(self, domain: str) -> List[Dict]:
        """获取最佳实践"""
        domain_map = {
            'go': 'go',
            'mysql': 'mysql',
            'redis': 'redis',
            'kafka': 'kafka',
            'distributed': 'distributed',
            'cloud_native': 'cloud-native',
        }
        
        category = domain_map.get(domain, domain)
        results = self.bridge.search(f"{domain}最佳实践", category)
        return results[:5]

    def get_expert_skill(self, skill_name: str) -> Optional[Dict]:
        """获取专家技能"""
        return self.bridge.get_skill_info(skill_name)

    def get_all_skills(self) -> List[str]:
        """获取所有专家技能"""
        return list(self.bridge.skills_index.keys())

    def generate_expert_report(self, project_type: str, language: str) -> str:
        """生成专家级分析报告"""
        lines = [
            f"# {project_type} 项目专家分析报告",
            "",
            f"**生成时间**: {self._get_timestamp()}",
            f"**语言**: {language}",
            "",
            "## 一、架构模式建议",
            "",
        ]
        
        # 根据项目类型推荐架构
        if language == 'go':
            patterns = self.get_architecture_patterns()
            lines.append("### 推荐架构模式")
            lines.append("")
            lines.append("| 模式 | 适用场景 | 参考文档 |")
            lines.append("|------|----------|----------|")
            lines.append("| 微服务 | 大型分布式系统 | [微服务架构深度] |")
            lines.append("| DDD | 复杂业务领域 | [DDD落地指南] |")
            lines.append("| CQRS | 读写分离场景 | [CQRS模式实现] |")
            lines.append("| Saga | 分布式事务 | [Saga模式实战] |")
        
        lines.extend([
            "",
            "## 二、技术栈建议",
            "",
        ])
        
        # 技术栈建议
        tech_stack = self._get_tech_stack_suggestions(language, project_type)
        for tool, reason in tech_stack.items():
            lines.append(f"- **{tool}**: {reason}")
        
        lines.extend([
            "",
            "## 三、最佳实践",
            "",
        ])
        
        # 最佳实践
        practices = self.get_best_practices(language)
        for p in practices[:3]:
            lines.append(f"### {p.get('name', 'Unknown')}")
            lines.append(f"- 路径: {p.get('path', 'N/A')}")
            lines.append(f"- 相关性: {p.get('relevance', 0)}")
            lines.append("")
        
        lines.extend([
            "",
            "## 四、专家技能",
            "",
            "可参考以下专家技能提升分析质量:",
            "",
        ])
        
        for skill in self.get_all_skills()[:5]:
            lines.append(f"- {skill}")
        
        return "\n".join(lines)

    def _get_tech_stack_suggestions(self, language: str, project_type: str) -> Dict:
        """获取技术栈建议"""
        suggestions = {
            'go': {
                'gin': 'HTTP框架，性能优秀',
                'fiber': '高性能HTTP框架',
                'echo': '极简高性能框架',
                'gorm': 'ORM库，支持多数据库',
                'kratos': '云原生微服务框架',
                'etcd': '分布式配置和协调',
                'go-kratos': '微服务治理',
            },
            'python': {
                'fastapi': '异步高性能框架',
                'sqlalchemy': 'ORM， SQLAlchemy2.0',
                'celery': '分布式任务队列',
                'redis': '缓存和消息队列',
                'kafka-python': 'Kafka客户端',
            },
            'java': {
                'spring-boot': '主流Java框架',
                'mybatis': 'ORM框架',
                'netty': 'NIO框架',
                'dubbo': 'RPC框架',
                'spring-cloud': '微服务生态',
            },
        }
        
        return suggestions.get(language, {})

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


if __name__ == "__main__":
    integrator = ExpertKnowledgeIntegrator()
    
    print("=" * 80)
    print("📚 专家知识集成验证")
    print("=" * 80)
    print()
    
    # 测试1: 架构模式
    print("【1. 架构模式】")
    patterns = integrator.get_architecture_patterns()
    for pattern, results in patterns.items():
        if results:
            print(f"  {pattern}: {len(results)} 篇文档")
    print()
    
    # 测试2: 专家技能
    print("【2. 专家技能】")
    skills = integrator.get_all_skills()
    print(f"  可用技能数: {len(skills)}")
    for skill in skills[:5]:
        print(f"    - {skill}")
    print()
    
    # 测试3: 生成报告
    print("【3. 专家报告生成】")
    report = integrator.generate_expert_report('backend', 'go')
    print(report[:500])
    print("...")
    
    print()
    print("=" * 80)
