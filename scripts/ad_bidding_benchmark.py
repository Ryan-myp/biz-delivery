#!/usr/bin/env python3
"""
广告竞价系统性能测试

模拟高并发竞价场景，测试系统性能
"""

import asyncio
import aiohttp
import time
import statistics
from dataclasses import dataclass
from typing import List, Dict
import random


@dataclass
class BenchmarkResult:
    """压测结果"""
    p50: float
    p90: float
    p95: float
    p99: float
    avg: float
    max: float
    min: float
    qps: float
    total_requests: int
    error_count: int


class BidBenchmark:
    """竞价系统压测"""
    
    def __init__(self, url: str, concurrency: int = 100):
        self.url = url
        self.concurrency = concurrency
        self.latencies: List[float] = []
        self.errors: int = 0
        self.total: int = 0
    
    async def send_request(self, session: aiohttp.ClientSession, 
                           request_id: int) -> float:
        """发送竞价请求"""
        start = time.time()
        
        payload = {
            "impression_id": f"imp_{request_id}",
            "ad_slot_id": "home_banner",
            "user_id": f"user_{random.randint(1, 10000)}",
            "bid_price": round(random.uniform(0.1, 10.0), 2),
            "timestamp": int(time.time() * 1000)
        }
        
        try:
            async with session.post(
                self.url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=1.0)
            ) as resp:
                await resp.json()
                elapsed = time.time() - start
                self.latencies.append(elapsed * 1000)  # 转换为毫秒
                self.total += 1
                return elapsed
        except Exception as e:
            self.errors += 1
            self.total += 1
            return 0
    
    async def run(self, duration: float = 30.0) -> BenchmarkResult:
        """运行压测"""
        print(f"🚀 开始竞价系统压测")
        print(f"   URL: {self.url}")
        print(f"   并发数: {self.concurrency}")
        print(f"   持续时间: {duration}秒")
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            start_time = time.time()
            
            for i in range(self.concurrency):
                task = asyncio.create_task(
                    self._sustained_request(session, i, duration)
                )
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            elapsed = time.time() - start_time
        
        return self._calculate_metrics(elapsed)
    
    async def _sustained_request(self, session: aiohttp.ClientSession,
                                 request_id: int, duration: float):
        """持续发送请求"""
        while time.time() - session._connector._time < duration:
            await self.send_request(session, request_id)
            await asyncio.sleep(0.01)
    
    def _calculate_metrics(self, elapsed: float) -> BenchmarkResult:
        """计算性能指标"""
        if not self.latencies:
            return BenchmarkResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        
        sorted_latencies = sorted(self.latencies)
        n = len(sorted_latencies)
        
        return BenchmarkResult(
            p50=sorted_latencies[int(n * 0.5)],
            p90=sorted_latencies[int(n * 0.9)],
            p95=sorted_latencies[int(n * 0.95)],
            p99=sorted_latencies[int(n * 0.99)],
            avg=statistics.mean(sorted_latencies),
            max=sorted_latencies[-1],
            min=sorted_latencies[0],
            qps=self.total / elapsed,
            total_requests=self.total,
            error_count=self.errors
        )
    
    def print_report(self, result: BenchmarkResult):
        """打印报告"""
        print("\n" + "=" * 60)
        print("    竞价系统压测报告")
        print("=" * 60)
        print(f"\n📊 延迟统计 (ms):")
        print(f"  P50:  {result.p50:.2f}")
        print(f"  P90:  {result.p90:.2f}")
        print(f"  P95:  {result.p95:.2f}")
        print(f"  P99:  {result.p99:.2f}")
        print(f"  Avg:  {result.avg:.2f}")
        print(f"  Max:  {result.max:.2f}")
        print(f"  Min:  {result.min:.2f}")
        
        print(f"\n📈 吞吐量:")
        print(f"  QPS:  {result.qps:.2f}")
        print(f"  总请求: {result.total_requests}")
        
        print(f"\n❌ 错误:")
        print(f"  错误数: {result.error_count}")
        print(f"  错误率: {result.error_count*100/result.total_requests:.2f}%" if result.total_requests > 0 else "  错误率: 0%")
        print("=" * 60)


async def main():
    """主入口"""
    # 测试配置
    url = "http://localhost:8080/api/bid"
    concurrency = 100
    duration = 30.0
    
    benchmark = BidBenchmark(url, concurrency)
    result = await benchmark.run(duration)
    benchmark.print_report(result)


if __name__ == "__main__":
    asyncio.run(main())
