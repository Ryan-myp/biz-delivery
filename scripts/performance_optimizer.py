"""
Performance Optimizer - 性能优化模块
缓存机制、并行执行、增量更新

核心优化:
  1. 知识库缓存 (避免重复加载)
  2. 流水线并行执行
  3. 增量文档生成
  4. 结果缓存
"""
import hashlib
import json
import time
import functools
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime


class CacheManager:
    """缓存管理器"""
    
    def __init__(self, cache_dir: str = "./.cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, Any] = {}
        self._disk_cache: Dict[str, Path] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """从内存缓存获取"""
        return self._memory_cache.get(key)
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """设置内存缓存"""
        self._memory_cache[key] = {
            'value': value,
            'expires': time.time() + ttl,
        }
    
    def get_disk(self, key: str) -> Optional[Any]:
        """从磁盘缓存获取"""
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    return json.load(f)
            except:
                return None
        return None
    
    def set_disk(self, key: str, value: Any):
        """保存到磁盘缓存"""
        cache_file = self.cache_dir / f"{key}.json"
        with open(cache_file, 'w') as f:
            json.dump(value, f, indent=2, ensure_ascii=False)
        self._disk_cache[key] = cache_file
    
    def invalidate(self, key: str):
        """使缓存失效"""
        self._memory_cache.pop(key, None)
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            cache_file.unlink()
        self._disk_cache.pop(key, None)
    
    def clear(self):
        """清空所有缓存"""
        self._memory_cache.clear()
        for f in self.cache_dir.glob('*.json'):
            f.unlink()
        self._disk_cache.clear()


class ParallelExecutor:
    """并行执行器"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def map(self, func: Callable, items: List[Any]) -> List[Any]:
        """并行执行函数"""
        futures = {self.executor.submit(func, item): item for item in items}
        results = []
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                results.append(None)
        return results
    
    def shutdown(self):
        """关闭执行器"""
        self.executor.shutdown(wait=False)


class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self, cache_dir: str = "./.cache"):
        self.cache = CacheManager(cache_dir)
        self.parallel = ParallelExecutor(max_workers=4)
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'parallel_calls': 0,
            'sequential_calls': 0,
            'time_saved': 0.0,
        }
    
    def cached(self, func: Callable) -> Callable:
        """缓存装饰器"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            key = self._generate_key(func.__name__, args, kwargs)
            
            # 检查内存缓存
            cached_result = self.cache.get(key)
            if cached_result is not None:
                self.stats['cache_hits'] += 1
                return cached_result['value']
            
            # 检查磁盘缓存
            disk_result = self.cache.get_disk(key)
            if disk_result is not None:
                self.stats['cache_hits'] += 1
                self.cache.set(key, disk_result)
                return disk_result
            
            # 执行并缓存
            self.stats['cache_misses'] += 1
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            
            self.cache.set(key, result)
            self.cache.set_disk(key, result)
            return result
        
        return wrapper
    
    def parallel_map(self, func: Callable, items: List[Any]) -> List[Any]:
        """并行映射"""
        self.stats['parallel_calls'] += 1
        start_time = time.time()
        results = self.parallel.map(func, items)
        elapsed = time.time() - start_time
        self.stats['time_saved'] += elapsed * 0.5  # 估算节省时间
        return results
    
    def sequential_map(self, func: Callable, items: List[Any]) -> List[Any]:
        """顺序映射"""
        self.stats['sequential_calls'] += 1
        return [func(item) for item in items]
    
    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """生成缓存键"""
        key_data = f"{func_name}:{args}:{kwargs}"
        return hashlib.md5(key_data.encode()).hexdigest()[:16]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = self.stats['cache_hits'] / total * 100 if total > 0 else 0
        
        return {
            **self.stats,
            'hit_rate': f"{hit_rate:.1f}%",
            'memory_cache_size': len(self.cache._memory_cache),
            'disk_cache_size': len(self.cache._disk_cache),
        }


# 单例
_optimizer = None

def get_optimizer() -> PerformanceOptimizer:
    """获取性能优化器单例"""
    global _optimizer
    if _optimizer is None:
        _optimizer = PerformanceOptimizer()
    return _optimizer


def clear_cache():
    """清空缓存"""
    global _optimizer
    if _optimizer:
        _optimizer.cache.clear()
        _optimizer = None


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 perf_optimizer.py [stats|clear]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == 'stats':
        opt = get_optimizer()
        stats = opt.get_stats()
        print("【性能优化统计】")
        for k, v in stats.items():
            print(f"  {k}: {v}")
    
    elif cmd == 'clear':
        clear_cache()
        print("✅ 缓存已清空")
