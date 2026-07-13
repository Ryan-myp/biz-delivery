#!/usr/bin/env python3
"""Incremental scanner with file-level caching.

Tracks file modification times to avoid re-scanning unchanged files.
Uses a simple JSON cache with mtime-based invalidation.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class FileCache:
    """File-level cache for incremental scanning.
    
    Stores file content hashes and their scan results.
    On next scan, only files with changed hashes are re-scanned.
    """
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / "file_cache.json"
        self.cache: Dict[str, Dict[str, Any]] = {}
        self._load()
    
    def _load(self):
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    self.cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.cache = {}
    
    def _save(self):
        """Save cache to disk."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
    
    def get_hash(self, file_path: str) -> Optional[str]:
        """Get cached hash for a file."""
        return self.cache.get(file_path, {}).get('hash')
    
    def needs_scan(self, file_path: str, current_hash: str) -> bool:
        """Check if file needs rescanning."""
        cached_hash = self.get_hash(file_path)
        if cached_hash is None:
            return True  # New file
        return cached_hash != current_hash
    
    def mark_scanned(self, file_path: str, file_hash: str, scan_time: float = 0.0):
        """Mark a file as scanned with its hash."""
        self.cache[file_path] = {
            'hash': file_hash,
            'scanned_at': scan_time or time.time(),
        }
    
    def get_changed_files(self, all_files: List[str]) -> List[str]:
        """Get list of files that need rescanning."""
        return [f for f in all_files if self.needs_scan(f, self._compute_hash(f))]
    
    @staticmethod
    def _compute_hash(file_path: str) -> str:
        """Compute content hash for a file."""
        try:
            p = Path(file_path)
            if not p.exists():
                return ''
            content = p.read_bytes()
            return hashlib.md5(content).hexdigest()[:12]
        except (IOError, OSError):
            return ''
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'total_files': len(self.cache),
            'cache_file': str(self.cache_file),
            'last_updated': max(
                (entry.get('scanned_at', 0) for entry in self.cache.values()),
                default=0,
            ),
        }


class IncrementalScanner:
    """Wrapper that adds incremental scanning to the main scanner."""
    
    def __init__(self, cache_dir: str, max_cache_age_hours: int = 24):
        self.cache = FileCache(cache_dir)
        self.max_cache_age = max_cache_age_hours
    
    def should_use_cache(self, repo_path: str) -> bool:
        """Check if cached IR data is still valid."""
        cache_file = Path(repo_path) / ".biz_delivery_cache" / "ir_cache.json"
        if not cache_file.exists():
            return False
        
        # Check cache age
        mtime = cache_file.stat().st_mtime
        age_hours = (time.time() - mtime) / 3600
        return age_hours < self.max_cache_age
    
    def scan_incremental(self, repo_path: str, go_files: List[Path], 
                         scanner_func) -> Dict[str, Any]:
        """Scan only changed files.
        
        Returns:
            {'changed_count': N, 'skipped_count': M, 'total_count': N+M}
        """
        stats = {'changed_count': 0, 'skipped_count': 0, 'total_count': len(go_files)}
        
        for go_file in go_files:
            file_str = str(go_file)
            current_hash = self.cache._compute_hash(file_str)
            
            if self.cache.needs_scan(file_str, current_hash):
                stats['changed_count'] += 1
                # Will be re-scanned by scanner_func
            else:
                stats['skipped_count'] += 1
        
        return stats
