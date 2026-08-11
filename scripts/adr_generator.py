#!/usr/bin/env python3
"""
架构决策记录 (ADR) 生成工具

基于设计决策生成标准化的架构决策记录
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict


class ADR:
    """架构决策记录"""
    
    def __init__(self, title: str, decision: str, status: str = "proposed"):
        self.title = title
        self.decision = decision
        self.status = status
        self.date = datetime.now().strftime("%Y-%m-%d")
        self.context = []
        self.consequences = []
        self.references = []
    
    def add_context(self, context: str):
        """添加上下文"""
        self.context.append(context)
    
    def add_consequence(self, consequence: str, positive: bool = True):
        """添加影响"""
        self.consequences.append({
            "text": consequence,
            "positive": positive
        })
    
    def add_reference(self, ref: str):
        """添加参考"""
        self.references.append(ref)
    
    def to_markdown(self) -> str:
        """生成 Markdown"""
        lines = [
            f"# {self.title}",
            "",
            f"**状态**: {self.status}",
            f"**日期**: {self.date}",
            "",
            "## 上下文",
            ""
        ]
        
        for ctx in self.context:
            lines.extend([f"- {ctx}", ""])
        
        lines.extend([
            "## 决策",
            "",
            f"{self.decision}",
            "",
            "## 影响",
            ""
        ])
        
        for c in self.consequences:
            prefix = "✅" if c["positive"] else "⚠️"
            lines.append(f"- {prefix} {c['text']}")
        
        if self.references:
            lines.extend([
                "",
                "## 参考",
                ""
            ])
            for ref in self.references:
                lines.append(f"- {ref}")
        
        lines.append("")
        return "\n".join(lines)


def create_dr_api_decision() -> ADR:
    """创建 REST vs GraphQL 决策记录"""
    adr = ADR(
        title="API 风格选择：REST vs GraphQL",
        decision="采用 RESTful API 作为主要接口风格，GraphQL 作为补充。"
    )
    
    adr.add_context("需要为业务系统提供数据访问接口")
    adr.add_context("团队熟悉 REST 风格，学习成本低")
    adr.add_context("GraphQL 适合复杂查询场景，但增加运维复杂度")
    
    adr.add_consequence("REST 接口简单，易于理解和调试", positive=True)
    adr.add_consequence("GraphQL 查询灵活，减少接口变更", positive=True)
    adr.add_consequence("REST 缓存友好，性能可控", positive=True)
    adr.add_consequence("GraphQL 学习曲线陡峭", positive=False)
    adr.add_consequence("REST 版本管理简单", positive=True)
    
    adr.add_reference("REST API Design Guide")
    adr.add_reference("GraphQL Best Practices")
    
    return adr


def create_cache_strategy_decision() -> ADR:
    """创建缓存策略决策记录"""
    adr = ADR(
        title="缓存策略设计",
        decision="采用多级缓存架构：L1 本地缓存 + L2 Redis 缓存 + 数据库"
    )
    
    adr.add_context("高并发场景需要降低数据库压力")
    adr.add_context("数据一致性要求适中，允许短暂不一致")
    adr.add_context("热点数据需要快速响应")
    
    adr.add_consequence("L1 缓存减少网络开销，响应最快", positive=True)
    adr.add_consequence("L2 缓存实现分布式共享", positive=True)
    adr.add_consequence("多级缓存增加系统复杂度", positive=False)
    adr.add_consequence("缓存一致性问题需要专门处理", positive=False)
    
    adr.add_reference("Redis 官方文档")
    adr.add_reference("多级缓存设计模式")
    
    return adr


def create_mq_decision() -> ADR:
    """创建消息队列决策记录"""
    adr = ADR(
        title="消息队列选型",
        decision="采用 Kafka 作为主要消息队列，RabbitMQ 作为补充"
    )
    
    adr.add_context("需要高吞吐量消息处理")
    adr.add_context("需要消息持久化和重放能力")
    adr.add_context("部分场景需要复杂路由")
    
    adr.add_consequence("Kafka 吞吐量大，适合日志收集", positive=True)
    adr.add_consequence("RabbitMQ 路由灵活，适合复杂场景", positive=True)
    adr.add_consequence("Kafka 运维复杂度较高", positive=False)
    adr.add_consequence("消息重复消费需要业务侧处理", positive=False)
    
    adr.add_reference("Kafka 官方文档")
    adr.add_reference("RabbitMQ 最佳实践")
    
    return adr


def main():
    """生成 ADR 文件"""
    output_dir = Path.home() / "ryan-personal-knowledge" / "knowledge" / "architecture"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    decisions = [
        create_dr_api_decision(),
        create_cache_strategy_decision(),
        create_mq_decision(),
    ]
    
    for adr in decisions:
        filename = adr.title.replace(" ", "-").lower() + ".md"
        filepath = output_dir / filename
        filepath.write_text(adr.to_markdown(), encoding="utf-8")
        print(f"✅ 生成: {filepath}")


if __name__ == "__main__":
    main()
