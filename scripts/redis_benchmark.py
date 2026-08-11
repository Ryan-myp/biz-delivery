#!/usr/bin/env python3
"""
Redis 客户端性能测试

测试不同场景下的 Redis 性能表现
"""

import asyncio
import time
import redis
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class BenchmarkResult:
    """压测结果"""
    ops: int
    avg_latency: float
    p50: float
    p95: float
    p99: float
    max_latency: float
    success_rate: float


class RedisBenchmark:
    """Redis 性能测试"""
    
    def __init__(self, host: str = "localhost", port: int = 6379):
        self.host = host
        self.port = port
        self.client = redis.Redis(host=host, port=port, decode_responses=True)
        self.latencies: List[float] = []
    
    def setup(self, key_prefix: str = "bench"):
        """准备测试数据"""
        self.key_prefix = key_prefix
        # 清空测试数据
        keys = self.client.keys(f"{key_prefix}:*")
        if keys:
            self.client.delete(*keys)
    
    def benchmark_single(self, key: str, value: str, iterations: int = 1000) -> BenchmarkResult:
        """单键操作测试"""
        latencies = []
        success = 0
        
        for i in range(iterations):
            start = time.time()
            try:
                self.client.set(key, value)
                self.client.get(key)
                latencies.append((time.time() - start) * 1000)  # 毫秒
                success += 1
            except Exception as e:
                print(f"Error: {e}")
        
        latencies.sort()
        n = len(latencies)
        
        return BenchmarkResult(
            ops=success,
            avg_latency=sum(latencies) / n if n > 0 else 0,
            p50=latencies[int(n * 0.5)] if n > 0 else 0,
            p95=latencies[int(n * 0.95)] if n > 0 else 0,
            p99=latencies[int(n * 0.99)] if n > 0 else 0,
            max_latency=max(latencies) if latencies else 0,
            success_rate=success / iterations if iterations > 0 else 0,
        )
    
    def benchmark_pipeline(self, key_prefix: str, count: int = 1000) -> BenchmarkResult:
        """Pipeline 批量操作测试"""
        pipe = self.client.pipeline()
        
        # 准备数据
        for i in range(count):
            key = f"{key_prefix}:{i}"
            pipe.set(key, f"value_{i}")
        
        start = time.time()
        try:
            pipe.execute()
            elapsed = (time.time() - start) * 1000
            return BenchmarkResult(
                ops=count,
                avg_latency=elapsed / count,
                p50=elapsed / count,
                p95=elapsed / count,
                p99=elapsed / count,
                max_latency=elapsed,
                success_rate=1.0,
            )
        except Exception as e:
            return BenchmarkResult(
                ops=0,
                avg_latency=0,
                p50=0,
                p95=0,
                p99=0,
                max_latency=0,
                success_rate=0,
            )
    
    def benchmark_hash(self, key: str, field_count: int = 100) -> BenchmarkResult:
        """Hash 操作测试"""
        latencies = []
        
        # 写入
        start = time.time()
        for i in range(field_count):
            self.client.hset(key, f"field_{i}", f"value_{i}")
        write_time = (time.time() - start) * 1000
        
        # 读取
        start = time.time()
        for i in range(100):
            self.client.hget(key, f"field_{i % field_count}")
        read_time = (time.time() - start) * 1000
        
        return BenchmarkResult(
            ops=field_count * 2,
            avg_latency=(write_time + read_time) / (field_count * 2),
            p50=read_time / 100,
            p95=read_time / 100,
            p99=read_time / 100,
            max_latency=max(write_time, read_time),
            success_rate=1.0,
        )
    
    def benchmark_list(self, key: str, count: int = 1000) -> BenchmarkResult:
        """List 操作测试"""
        latencies = []
        
        # LPUSH
        start = time.time()
        for i in range(count):
            self.client.lpush(key, f"value_{i}")
            latencies.append((time.time() - start) / count * 1000)
        
        # LRANGE
        start = time.time()
        for _ in range(100):
            self.client.lrange(key, 0, 99)
            latencies.append((time.time() - start) / 100 * 1000)
        
        latencies.sort()
        n = len(latencies)
        
        return BenchmarkResult(
            ops=count + 100,
            avg_latency=sum(latencies) / n,
            p50=latencies[int(n * 0.5)],
            p95=latencies[int(n * 0.95)],
            p99=latencies[int(n * 0.99)],
            max_latency=max(latencies),
            success_rate=1.0,
        )
    
    def benchmark_zset(self, key: str, count: int = 1000) -> BenchmarkResult:
        """Sorted Set 操作测试"""
        latencies = []
        
        # ZADD
        start = time.time()
        for i in range(count):
            self.client.zadd(key, {f"member_{i}": i})
            latencies.append((time.time() - start) / count * 1000)
        
        # ZRANGE
        start = time.time()
        for _ in range(100):
            self.client.zrange(key, 0, 99)
            latencies.append((time.time() - start) / 100 * 1000)
        
        latencies.sort()
        n = len(latencies)
        
        return BenchmarkResult(
            ops=count + 100,
            avg_latency=sum(latencies) / n,
            p50=latencies[int(n * 0.5)],
            p95=latencies[int(n * 0.95)],
            p99=latencies[int(n * 0.99)],
            max_latency=max(latencies),
            success_rate=1.0,
        )
    
    def run_all(self) -> Dict[str, BenchmarkResult]:
        """运行所有测试"""
        print("🚀 开始 Redis 性能测试...")
        self.setup()
        
        results = {}
        
        # 单键操作
        print("  - 单键操作测试...")
        results["single"] = self.benchmark_single("bench:_single", "test_value")
        
        # Pipeline
        print("  - Pipeline 批量操作测试...")
        results["pipeline"] = self.benchmark_pipeline("bench:pipe")
        
        # Hash
        print("  - Hash 操作测试...")
        results["hash"] = self.benchmark_hash("bench:hash")
        
        # List
        print("  - List 操作测试...")
        results["list"] = self.benchmark_list("bench:list")
        
        # ZSet
        print("  - Sorted Set 操作测试...")
        results["zset"] = self.benchmark_zset("bench:zset")
        
        print("✅ 测试完成")
        return results
    
    def print_report(self, results: Dict[str, BenchmarkResult]):
        """打印报告"""
        print("\n" + "=" * 60)
        print("    Redis 性能测试报告")
        print("=" * 60)
        
        for name, result in results.items():
            print(f"\n【{name}】")
            print(f"  操作数: {result.ops}")
            print(f"  平均延迟: {result.avg_latency:.3f}ms")
            print(f"  P50: {result.p50:.3f}ms")
            print(f"  P95: {result.p95:.3f}ms")
            print(f"  P99: {result.p99:.3f}ms")
            print(f"  最大延迟: {result.max_latency:.3f}ms")
            print(f"  成功率: {result.success_rate*100:.1f}%")
        
        print("\n" + "=" * 60)
    
    def cleanup(self):
        """清理测试数据"""
        keys = self.client.keys("bench:*")
        if keys:
            self.client.delete(*keys)


async def main():
    """主入口"""
    benchmark = RedisBenchmark()
    results = benchmark.run_all()
    benchmark.print_report(results)
    benchmark.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
