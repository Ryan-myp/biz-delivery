#!/usr/bin/env python3
"""
广告系统性能压测工具

模拟高并发请求，测试系统性能
"""

import asyncio
import aiohttp
import time
import statistics
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Metric:
    """性能指标"""
    p50: float
    p90: float
    p95: float
    p99: float
    avg: float
    max: float
    min: float
    qps: float
    error_rate: float


class LoadTester:
    """压测工具"""
    
    def __init__(self, url: str, concurrency: int = 100):
        self.url = url
        self.concurrency = concurrency
        self.results: List[float] = []
        self.errors: int = 0
        self.total: int = 0
    
    async def request(self, session: aiohttp.ClientSession, 
                      request_id: int) -> float:
        """发送请求"""
        start = time.time()
        try:
            async with session.get(self.url) as resp:
                await resp.text()
                elapsed = time.time() - start
                self.results.append(elapsed)
                self.total += 1
                return elapsed
        except Exception as e:
            self.errors += 1
            self.total += 1
            return 0
    
    async def run(self, duration: float = 60.0) -> Metric:
        """运行压测"""
        print(f"🚀 开始压测: {self.url}")
        print(f"   并发数: {self.concurrency}")
        print(f"   持续时间: {duration}秒")
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            start_time = time.time()
            
            # 创建并发任务
            for i in range(self.concurrency):
                task = asyncio.create_task(
                    self._sustained_request(session, i, duration)
                )
                tasks.append(task)
            
            # 等待所有任务完成
            await asyncio.gather(*tasks)
            
            elapsed = time.time() - start_time
        
        return self._calculate_metrics(elapsed)
    
    async def _sustained_request(self, session: aiohttp.ClientSession,
                                 request_id: int, duration: float):
        """持续发送请求"""
        while time.time() - session._connector._time < duration:
            await self.request(session, request_id)
            await asyncio.sleep(0.01)  # 小延迟
    
    def _calculate_metrics(self, elapsed: float) -> Metric:
        """计算指标"""
        if not self.results:
            return Metric(0, 0, 0, 0, 0, 0, 0, 0, 0)
        
        sorted_results = sorted(self.results)
        n = len(sorted_results)
        
        return Metric(
            p50=sorted_results[int(n * 0.5)],
            p90=sorted_results[int(n * 0.9)],
            p95=sorted_results[int(n * 0.95)],
            p99=sorted_results[int(n * 0.99)],
            avg=sum(sorted_results) / n,
            max=sorted_results[-1],
            min=sorted_results[0],
            qps=self.total / elapsed,
            error_rate=self.errors / max(self.total, 1)
        )
    
    def print_report(self, metric: Metric):
        """打印报告"""
        print("\n" + "=" * 60)
        print("    压测报告")
        print("=" * 60)
        print(f"\n📊 延迟统计:")
        print(f"  P50:  {metric.p50*1000:.2f}ms")
        print(f"  P90:  {metric.p90*1000:.2f}ms")
        print(f"  P95:  {metric.p95*1000:.2f}ms")
        print(f"  P99:  {metric.p99*1000:.2f}ms")
        print(f"  Avg:  {metric.avg*1000:.2f}ms")
        print(f"  Max:  {metric.max*1000:.2f}ms")
        print(f"  Min:  {metric.min*1000:.2f}ms")
        
        print(f"\n📈 吞吐量:")
        print(f"  QPS:  {metric.qps:.2f}")
        
        print(f"\n❌ 错误:")
        print(f"  错误率: {metric.error_rate*100:.2f}%")
        print("=" * 60)


async def main():
    """主入口"""
    # 测试目标
    url = "http://localhost:8080/health"
    concurrency = 100
    duration = 30.0
    
    tester = LoadTester(url, concurrency)
    metric = await tester.run(duration)
    tester.print_report(metric)


if __name__ == "__main__":
    asyncio.run(main())
