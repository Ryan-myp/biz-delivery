#!/usr/bin/env python3
"""
生产环境故障排查手册

收录真实生产环境问题排查案例和解决方案
"""

import sys
from pathlib import Path


class TroubleshootingGuide:
    """故障排查指南"""
    
    def __init__(self):
        self.cases = []
    
    def add_case(self, name, symptom, cause, solution):
        """添加排查案例"""
        self.cases.append({
            'name': name,
            'symptom': symptom,
            'cause': cause,
            'solution': solution
        })
    
    def print_guide(self):
        """打印排查指南"""
        print("=" * 60)
        print("    生产环境故障排查手册")
        print("=" * 60)
        
        for i, case in enumerate(self.cases, 1):
            print(f"\n【案例 {i}】{case['name']}")
            print(f"症状：{case['symptom']}")
            print(f"根因：{case['cause']}")
            print(f"方案：{case['solution']}")
            print("-" * 60)


def main():
    guide = TroubleshootingGuide()
    
    # 添加真实案例
    guide.add_case(
        "Go 服务 CPU 100%",
        "服务响应变慢，P99 延迟飙升",
        "goroutine 泄漏导致调度器压力大",
        "1. pprof 分析 goroutine\n2. 定位泄漏点\n3. 修复并发逻辑"
    )
    
    guide.add_case(
        "MySQL 连接数爆满",
        "应用报错 Too many connections",
        "连接池配置不当，未释放连接",
        "1. 检查连接池配置\n2. 修复连接泄漏\n3. 设置合理 max_connections"
    )
    
    guide.add_case(
        "Redis 内存溢出",
        "Redis 拒绝写入，OOM 错误",
        "最大内存未设置，淘汰策略不当",
        "1. 设置 maxmemory\n2. 配置淘汰策略\n3. 监控内存使用"
    )
    
    guide.add_case(
        "Kafka 消息堆积",
        "消费延迟越来越大",
        "消费者处理速度慢，分区数不足",
        "1. 增加消费者实例\n2. 优化消费逻辑\n3. 调整 partition 数"
    )
    
    guide.print_guide()


if __name__ == "__main__":
    main()
