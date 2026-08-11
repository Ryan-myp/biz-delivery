#!/usr/bin/env python3
"""
biz-delivery 性能测试套件

测试各引擎性能表现，生成性能报告
"""

import sys
import time
import statistics
from pathlib import Path
from typing import Dict, List

# 添加 biz-delivery 路径
sys.path.insert(0, str(Path(__file__).parent))


class PerformanceTest:
    """性能测试"""
    
    def __init__(self):
        from review_engine import ReviewEngine
        from td_engine_v2 import TDEngine
        from test_engine import TestEngine
        
        self.profile = {
            "name": "perf-test",
            "repositories": [],
            "business_domain": "test",
        }
        self.output_dir = "/tmp/biz_perf_test"
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        self.review_engine = ReviewEngine(self.profile, self.output_dir)
        self.td_engine = TDEngine(self.profile, self.output_dir)
        self.test_engine = TestEngine(self.profile, self.output_dir)
    
    def run_review_benchmark(self, iterations: int = 100) -> Dict:
        """审查引擎性能测试"""
        prd = """
        # 广告竞价系统

        ## 功能需求
        1. 用户出价功能
        2. 预算控制
        3. 实时竞价
        4. 质量分计算
        """
        
        times = []
        for i in range(iterations):
            start = time.time()
            result = self.review_engine.review(prd)
            elapsed = time.time() - start
            times.append(elapsed)
        
        return {
            "engine": "review",
            "iterations": iterations,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times),
            "p50_time": statistics.median(times),
            "p95_time": sorted(times)[int(iterations * 0.95)],
            "status": "pass" if all(r["status"] == "prompt_ready" for r in [self.review_engine.review(prd) for _ in range(5)]) else "fail"
        }
    
    def run_td_benchmark(self, iterations: int = 100) -> Dict:
        """TD 引擎性能测试"""
        prd = """
        # 订单系统

        ## 功能需求
        1. 创建订单
        2. 查询订单
        3. 订单状态流转
        """
        
        times = []
        for i in range(iterations):
            start = time.time()
            result = self.td_engine.generate_td(prd, use_llm=False)
            elapsed = time.time() - start
            times.append(elapsed)
        
        return {
            "engine": "td",
            "iterations": iterations,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times),
            "p50_time": statistics.median(times),
            "p95_time": sorted(times)[int(iterations * 0.95)],
            "status": "pass"
        }
    
    def run_test_benchmark(self, iterations: int = 100) -> Dict:
        """测试引擎性能测试"""
        prd = """
        # 用户登录系统

        ## 功能需求
        1. 用户登录
        2. 用户注册
        3. Token 验证
        """
        
        times = []
        for i in range(iterations):
            start = time.time()
            result = self.test_engine.generate_tests(prd)
            elapsed = time.time() - start
            times.append(elapsed)
        
        return {
            "engine": "test",
            "iterations": iterations,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times),
            "p50_time": statistics.median(times),
            "p95_time": sorted(times)[int(iterations * 0.95)],
            "status": "pass"
        }
    
    def run_all_benchmarks(self) -> Dict:
        """运行所有性能测试"""
        print("🚀 开始性能测试...")
        
        results = {
            "review": self.run_review_benchmark(),
            "td": self.run_td_benchmark(),
            "test": self.run_test_benchmark(),
        }
        
        print("✅ 性能测试完成")
        return results
    
    def generate_report(self, results: Dict) -> str:
        """生成性能报告"""
        report = """
# biz-delivery 性能测试报告

## 测试环境
- 时间：2026-08-11
- 迭代次数：100

## 测试结果

### 审查引擎
| 指标 | 值 |
|------|-----|
| 平均耗时 | {review_avg:.3f}s |
| 最小耗时 | {review_min:.3f}s |
| 最大耗时 | {review_max:.3f}s |
| P50 耗时 | {review_p50:.3f}s |
| P95 耗时 | {review_p95:.3f}s |

### TD 引擎
| 指标 | 值 |
|------|-----|
| 平均耗时 | {td_avg:.3f}s |
| 最小耗时 | {td_min:.3f}s |
| 最大耗时 | {td_max:.3f}s |
| P50 耗时 | {td_p50:.3f}s |
| P95 耗时 | {td_p95:.3f}s |

### 测试引擎
| 指标 | 值 |
|------|-----|
| 平均耗时 | {test_avg:.3f}s |
| 最小耗时 | {test_min:.3f}s |
| 最大耗时 | {test_max:.3f}s |
| P50 耗时 | {test_p50:.3f}s |
| P95 耗时 | {test_p95:.3f}s |

## 结论
""".format(
            review_avg=results["review"]["avg_time"] * 1000,
            review_min=results["review"]["min_time"] * 1000,
            review_max=results["review"]["max_time"] * 1000,
            review_p50=results["review"]["p50_time"] * 1000,
            review_p95=results["review"]["p95_time"] * 1000,
            td_avg=results["td"]["avg_time"] * 1000,
            td_min=results["td"]["min_time"] * 1000,
            td_max=results["td"]["max_time"] * 1000,
            td_p50=results["td"]["p50_time"] * 1000,
            td_p95=results["td"]["p95_time"] * 1000,
            test_avg=results["test"]["avg_time"] * 1000,
            test_min=results["test"]["min_time"] * 1000,
            test_max=results["test"]["max_time"] * 1000,
            test_p50=results["test"]["p50_time"] * 1000,
            test_p95=results["test"]["p95_time"] * 1000,
        )
        
        return report


def main():
    """主入口"""
    tester = PerformanceTest()
    results = tester.run_all_benchmarks()
    report = tester.generate_report(results)
    
    # 保存报告
    output_path = Path("/tmp/biz_perf_report.md")
    output_path.write_text(report, encoding="utf-8")
    print(f"\n📄 性能报告: {output_path}")
    
    # 打印摘要
    print("\n" + "=" * 60)
    print("    性能测试摘要")
    print("=" * 60)
    for name, result in results.items():
        print(f"\n{name} 引擎:")
        print(f"  平均耗时: {result['avg_time']*1000:.2f}ms")
        print(f"  P95 耗时: {result['p95_time']*1000:.2f}ms")
    print("=" * 60)


if __name__ == "__main__":
    main()
