#!/usr/bin/env python3
"""查询缓存模块 - 提升查询性能"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional


class QueryCache:
    """轻量级文件缓存，支持 TTL"""
    
    def __init__(self, cache_dir: Path, ttl_seconds: int = 3600):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, query: str, scopes: list[str]) -> str:
        key_str = f"{query}:{','.join(sorted(scopes))}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"
    
    def get(self, query: str, scopes: list[str]) -> Optional[dict]:
        """获取缓存结果"""
        key = self._get_cache_key(query, scopes)
        path = self._get_cache_path(key)
        
        if not path.exists():
            return None
        
        mtime = path.stat().st_mtime
        if time.time() - mtime > self.ttl_seconds:
            path.unlink()  # 过期清理
            return None
        
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    
    def set(self, query: str, scopes: list[str], data: dict):
        """设置缓存结果"""
        key = self._get_cache_key(query, scopes)
        path = self._get_cache_path(key)
        data["cached_at"] = time.time()
        # 保存 query 和 scopes 以便按关键词清理
        data["_query"] = query
        data["_scopes"] = scopes
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    def clear(self, query: str = None):
        """清除缓存（可选指定 query 关键词）"""
        if not query:
            for f in self.cache_dir.glob("*.json"):
                f.unlink()
            return
        
        for f in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if query in str(data):
                    f.unlink()
            except Exception:
                pass
