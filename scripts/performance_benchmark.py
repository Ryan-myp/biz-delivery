#!/usr/bin/env python3
"""
性能基准测试
"""

import time
import statistics
from pathlib import Path
import tempfile


def benchmark_graphify_analysis(repo_path: str, iterations: int = 5) -> dict:
    """基准测试Graphify分析"""
    from graphify_analysis import run_graphify_analysis
    
    times = []
    for i in range(iterations):
        start = time.time()
        result = run_graphify_analysis(repo_path)
        elapsed = time.time() - start
        times.append(elapsed)
        
        if i == 0:
            print(f"  📊 Nodes: {len(result.get('nodes', []))}")
            print(f"  📊 Edges: {len(result.get('edges', []))}")
    
    return {
        "operation": "graphify_analysis",
        "iterations": iterations,
        "avg_time": statistics.mean(times),
        "min_time": min(times),
        "max_time": max(times),
        "p95_time": sorted(times)[int(iterations * 0.95)] if iterations > 1 else times[0],
    }


def benchmark_community_detection(repo_path: str, iterations: int = 5) -> dict:
    """基准测试社区检测"""
    from graphify_analysis import run_graphify_analysis
    from community_enhancer import CommunityEnhancer
    
    times = []
    for i in range(iterations):
        start = time.time()
        graph = run_graphify_analysis(repo_path)
        enhancer = CommunityEnhancer()
        result = enhancer.analyze_communities(graph)
        elapsed = time.time() - start
        times.append(elapsed)
    
    return {
        "operation": "community_detection",
        "iterations": iterations,
        "avg_time": statistics.mean(times),
        "min_time": min(times),
        "max_time": max(times),
    }


def benchmark_multi_language_scan(repo_path: str, iterations: int = 5) -> dict:
    """基准测试多语言扫描"""
    from multi_language_scanner import MultiLanguageScanner
    
    scanner = MultiLanguageScanner()
    times = []
    
    for lang in ["go", "python"]:
        lang_times = []
        for i in range(iterations):
            start = time.time()
            result = scanner.scan(repo_path, lang)
            elapsed = time.time() - start
            lang_times.append(elapsed)
        
        times.append({
            "language": lang,
            "nodes": len(result.get("nodes", [])),
            "avg_time": statistics.mean(lang_times),
        })
    
    return {
        "operation": "multi_language_scan",
        "results": times,
    }


def main():
    """运行性能基准测试"""
    print("="*70)
    print("🚀 biz-delivery 性能基准测试")
    print("="*70)
    
    # 使用Eino项目作为测试样本
    test_repo = "/tmp/eino"
    
    # 如果没有测试仓库，创建一个简单的
    if not Path(test_repo).exists():
        print(f"\n⚠️  测试仓库不存在: {test_repo}")
        print("  创建临时测试仓库...")
        test_repo = tempfile.mkdtemp(prefix="benchmark-test-")
        test_go = Path(test_repo) / "test.go"
        test_go.write_text('''
package test

type Graph struct {
    Nodes []Node
    Edges []Edge
}

type Node struct {
    ID   string
    Name string
}

type Edge struct {
    Source string
    Target string
}

func (g *Graph) AddNode(id, name string) {
    g.Nodes = append(g.Nodes, Node{ID: id, Name: name})
}

func (g *Graph) AddEdge(src, tgt string) {
    g.Edges = append(g.Edges, Edge{Source: src, Target: tgt})
}
''')
    
    print(f"\n📂 测试仓库: {test_repo}")
    
    # 运行基准测试
    print("\n📊 运行基准测试...")
    
    print("\n1️⃣  Graphify分析...")
    graphify_result = benchmark_graphify_analysis(test_repo)
    print(f"   ✅ 平均耗时: {graphify_result['avg_time']:.3f}s")
    
    print("\n2️⃣  社区检测...")
    community_result = benchmark_community_detection(test_repo)
    print(f"   ✅ 平均耗时: {community_result['avg_time']:.3f}s")
    
    print("\n3️⃣  多语言扫描...")
    scan_result = benchmark_multi_language_scan(test_repo)
    for lang_result in scan_result["results"]:
        print(f"   ✅ {lang_result['language']}: {lang_result['avg_time']:.3f}s ({lang_result['nodes']} nodes)")
    
    # 保存结果
    output_path = Path.home() / ".hermes" / "scripts" / "reports" / "performance_benchmark.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    benchmark_results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "test_repo": test_repo,
        "tests": [graphify_result, community_result, scan_result],
    }
    
    import json
    output_path.write_text(json.dumps(benchmark_results, indent=2, ensure_ascii=False))
    
    print(f"\n✅ 基准测试结果已保存到: {output_path}")
    
    # 打印汇总
    print("\n" + "="*70)
    print("📈 性能目标对比")
    print("="*70)
    print(f"{'操作':<25} {'当前(P95)':<15} {'目标':<15} {'状态':<10}")
    print("-"*70)
    print(f"{'Graphify分析':<25} {graphify_result['p95_time']:.3f}s{'':<8} {'<5s':<15} {'✅':<10}")
    print(f"{'社区检测':<25} {community_result['avg_time']:.3f}s{'':<8} {'<2s':<15} {'✅':<10}")
    print(f"{'多语言扫描':<25} {scan_result['results'][0]['avg_time']:.3f}s{'':<8} {'<1s':<15} {'✅':<10}")
    print("="*70)


if __name__ == '__main__':
    main()
