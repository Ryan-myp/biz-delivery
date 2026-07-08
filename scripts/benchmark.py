#!/usr/bin/env python3
"""biz-delivery 性能基准测试"""

import subprocess
import time
import json
from pathlib import Path

def run_learn(profile_path: str, output_dir: str) -> tuple:
    """运行 learn 并记录时间"""
    start = time.time()
    result = subprocess.run(
        ['python3', 'scripts/learn_repo.py',
         '--profile', profile_path,
         '--output-dir', output_dir],
        cwd='/Users/yanping.ma/biz-delivery',
        capture_output=True, text=True, timeout=120
    )
    elapsed = time.time() - start
    
    return elapsed, result.returncode == 0

def run_query(query: str, sources: str, cache_dir: str) -> tuple:
    """运行查询并记录时间"""
    start = time.time()
    result = subprocess.run(
        ['python3', 'scripts/query_evidence.py',
         '--query', query,
         '--sources', sources,
         '--cache-dir', cache_dir],
        cwd='/Users/yanping.ma/biz-delivery',
        capture_output=True, text=True, timeout=30
    )
    elapsed = time.time() - start
    
    # 解析结果
    lines = result.stdout.split('\n')
    total_results = 0
    for line in lines:
        if '结果:' in line:
            try:
                total_results = int(line.split(':')[1].strip())
            except:
                pass
    
    return elapsed, total_results

def main():
    print("=" * 70)
    print("biz-delivery 性能基准测试")
    print("=" * 70)
    
    # 测试项目
    projects = [
        {'name': 'sponge', 'profile': 'profiles/sponge.json', 'cache_dir': 'knowledge/sponge'},
        {'name': 'conc', 'profile': 'profiles/conc.json', 'cache_dir': 'knowledge/conc'},
        {'name': 'eino', 'profile': 'profiles/eino.json', 'cache_dir': 'knowledge/eino'},
    ]
    
    # 测试查询
    queries = [
        '素材',
        '竞价',
        '缓存',
        '广告组',
        '创意审核',
    ]
    
    results = []
    
    for project in projects:
        print(f"\n【{project['name']}】")
        print("-" * 40)
        
        # 测试 learn
        elapsed, success = run_learn(project['profile'], f'/tmp/benchmark-{project["name"]}')
        if success:
            print(f"  learn 耗时: {elapsed:.2f}s")
            results.append({'project': project['name'], 'type': 'learn', 'time': elapsed})
        else:
            print(f"  learn 失败")
        
        # 测试查询
        for query in queries:
            elapsed, total = run_query(query, 'code', project['cache_dir'])
            print(f"  搜'{query}': {elapsed:.2f}s, {total} 个结果")
            results.append({'project': project['name'], 'query': query, 'time': elapsed, 'results': total})
    
    # 输出汇总
    print("\n" + "=" * 70)
    print("汇总")
    print("=" * 70)
    for r in results:
        if 'query' in r:
            print(f"  {r['project']} 搜'{r['query']}': {r['time']:.2f}s, {r['results']} 个结果")
        else:
            print(f"  {r['project']} learn: {r['time']:.2f}s")

if __name__ == '__main__':
    main()
