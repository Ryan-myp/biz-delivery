#!/usr/bin/env python3
"""Incremental scanner with SHA256 content hash + mtime fallback.

Tracks file content hashes to avoid re-scanning unchanged files.
Uses SHA256 for reliable content change detection, with mtime as fallback.
Supports delta tracking and cache hit rate statistics.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class FileCache:
    """File-level cache for incremental scanning.
    
    Stores file content hashes (SHA256) and their scan results.
    On next scan, only files with changed hashes are re-scanned.
    Supports delta tracking and cache hit rate statistics.
    """
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / "file_cache.json"
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.scan_delta: Dict[str, str] = {}  # file_path -> status (scanned/skipped/new)
        self.stats: Dict[str, int] = {
            'total_files': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'new_files': 0,
        }
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
    
    @staticmethod
    def compute_sha256(file_path: str) -> str:
        """Compute SHA256 content hash for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            SHA256 hex digest, or empty string on failure
        """
        try:
            p = Path(file_path)
            if not p.exists():
                return ''
            hasher = hashlib.sha256()
            with open(p, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (IOError, OSError):
            return ''
    
    @staticmethod
    def _get_mtime(file_path: str) -> float:
        """Get file modification time as fallback."""
        try:
            return Path(file_path).stat().st_mtime
        except (IOError, OSError):
            return 0.0
    
    def needs_scan(self, file_path: str, current_hash: str) -> bool:
        """Check if file needs rescanning based on content hash.
        
        Falls back to mtime comparison if hash is empty.
        
        Args:
            file_path: Path to the file
            current_hash: Current SHA256 hash of the file
            
        Returns:
            True if file needs rescanning
        """
        cached_hash = self.get_hash(file_path)
        if cached_hash is None:
            return True  # New file
        
        if current_hash:
            return cached_hash != current_hash
        
        # Fallback to mtime comparison
        cached_mtime = self.cache.get(file_path, {}).get('mtime', 0)
        current_mtime = self._get_mtime(file_path)
        return cached_mtime != current_mtime
    
    def mark_scanned(self, file_path: str, file_hash: str, scan_time: float = 0.0):
        """Mark a file as scanned with its hash."""
        self.cache[file_path] = {
            'hash': file_hash,
            'mtime': self._get_mtime(file_path),
            'scanned_at': scan_time or time.time(),
        }
        # Record in delta
        if file_path not in self.scan_delta:
            self.scan_delta[file_path] = 'scanned'
    
    def mark_skipped(self, file_path: str):
        """Mark a file as skipped (cache hit)."""
        if file_path not in self.scan_delta:
            self.scan_delta[file_path] = 'skipped'
    
    def mark_new(self, file_path: str):
        """Mark a file as new (not previously in cache)."""
        if file_path not in self.scan_delta:
            self.scan_delta[file_path] = 'new'
    
    def record_scan_result(self, file_path: str, status: str):
        """Record the result of scanning a file."""
        self.stats['total_files'] += 1
        if status == 'hit':
            self.stats['cache_hits'] += 1
            self.mark_skipped(file_path)
        elif status == 'miss':
            self.stats['cache_misses'] += 1
        elif status == 'new':
            self.stats['new_files'] += 1
            self.mark_new(file_path)
    
    def get_changed_files(self, all_files: List[str]) -> List[str]:
        """Get list of files that need rescanning.
        
        Uses SHA256 content hash for reliable change detection.
        Falls back to mtime comparison if hash computation fails.
        
        Args:
            all_files: List of all file paths to check
            
        Returns:
            List of file paths that have changed or are new
        """
        changed = []
        for file_path in all_files:
            try:
                current_hash = self.compute_sha256(file_path)
                if self.needs_scan(file_path, current_hash):
                    changed.append(file_path)
            except Exception:
                # If anything goes wrong, include the file for safety
                changed.append(file_path)
        return changed
    
    def _get_delta_summary(self) -> Dict[str, int]:
        """Get summary of scan delta by status."""
        summary = {'scanned': 0, 'skipped': 0, 'new': 0}
        for status in self.scan_delta.values():
            if status in summary:
                summary[status] += 1
        return summary
    
    def get_scan_stats(self) -> Dict[str, Any]:
        """Get comprehensive scan statistics including cache hit rate."""
        total = self.stats['total_files']
        hits = self.stats['cache_hits']
        hit_rate = round((hits / total * 100) if total > 0 else 0.0, 2)
        
        return {
            'total_files': total,
            'cache_hits': hits,
            'cache_misses': self.stats['cache_misses'],
            'new_files': self.stats['new_files'],
            'hit_rate': hit_rate,
            'delta_summary': self._get_delta_summary(),
        }
    
    def reset_stats(self):
        """Reset scan statistics for a new scan run."""
        self.stats = {
            'total_files': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'new_files': 0,
        }
        self.scan_delta = {}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics (legacy method, kept for compatibility)."""
        return {
            'total_files': len(self.cache),
            'cache_file': str(self.cache_file),
            'last_updated': max(
                (entry.get('scanned_at', 0) for entry in self.cache.values()),
                default=0,
            ),
        }


class IncrementalScanner:
    """Wrapper that adds incremental scanning to the main scanner.
    
    Features:
    - SHA256 content hash for reliable change detection
    - mtime fallback when hash computation fails
    - Delta tracking (records which files were scanned/skipped/new)
    - Cache hit rate statistics
    """
    
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
    
    def find_changed_files(self, repo_path: Path) -> List[Path]:
        """Find files that have changed since last scan.
        
        Uses SHA256 content hash for reliable detection.
        Falls back to mtime comparison.
        
        Returns:
            List of changed file paths
        """
        all_files = []
        for ext in ['*.go', '*.py', '*.java']:
            all_files.extend(repo_path.rglob(ext))
        
        # Filter out vendor/.git directories
        filtered_files = [
            f for f in all_files
            if 'vendor/' not in str(f) and '.git/' not in str(f)
        ]
        
        file_strs = [str(f) for f in filtered_files]
        changed_strs = self.cache.get_changed_files(file_strs)
        
        return [Path(f) for f in changed_strs]
    
    def scan_incremental(self, repo_path: str, go_files: List[Path], 
                         scanner_func) -> Dict[str, Any]:
        """Scan only changed files with full delta tracking.
        
        Args:
            repo_path: Repository path
            go_files: List of files to potentially scan
            scanner_func: Function to call for scanning changed files
            
        Returns:
            {
                'changed_count': N,
                'skipped_count': M,
                'total_count': N+M,
                'hit_rate': X.XX,
                'delta': {...},
            }
        """
        # Reset stats for this scan
        self.cache.reset_stats()
        
        stats = {
            'changed_count': 0,
            'skipped_count': 0,
            'total_count': len(go_files),
        }
        
        # Get files that need scanning
        file_strs = [str(f) for f in go_files]
        changed_strs = self.cache.get_changed_files(file_strs)
        changed_files = [Path(f) for f in changed_strs]
        
        # Scan changed files
        for go_file in changed_files:
            file_str = str(go_file)
            current_hash = self.cache.compute_sha256(file_str)
            
            if current_hash and self.cache.needs_scan(file_str, current_hash):
                # File has changed, scan it
                try:
                    scanner_func(go_file)
                    self.cache.mark_scanned(file_str, current_hash)
                    self.cache.record_scan_result(file_str, 'miss')
                    stats['changed_count'] += 1
                except Exception as e:
                    print(f"  WARNING: Failed to scan {file_str}: {e}", file=__import__('sys').stderr)
            else:
                # File hasn't changed, use cache
                self.cache.record_scan_result(file_str, 'hit')
                stats['skipped_count'] += 1
        
        # Handle new files (not in cache at all)
        for go_file in go_files:
            file_str = str(go_file)
            if file_str not in self.cache.cache:
                try:
                    scanner_func(go_file)
                    current_hash = self.cache.compute_sha256(file_str)
                    if current_hash:
                        self.cache.mark_scanned(file_str, current_hash)
                    self.cache.record_scan_result(file_str, 'new')
                    stats['changed_count'] += 1
                except Exception as e:
                    print(f"  WARNING: Failed to scan new file {file_str}: {e}", file=__import__('sys').stderr)
        
        # Save cache
        self.cache._save()
        
        # Add stats
        scan_stats = self.cache.get_scan_stats()
        stats['hit_rate'] = scan_stats['hit_rate']
        stats['delta'] = scan_stats['delta_summary']
        
        return stats
    
    def set_last_scan_time(self):
        """Update last scan timestamp."""
        self.cache.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache.cache_file.write_text(str(time.time()), encoding='utf-8')
    
    def get_last_scan_time(self) -> Optional[float]:
        """Get last scan timestamp."""
        if self.cache.cache_file.exists():
            try:
                return float(self.cache.cache_file.read_text().strip())
            except (ValueError, IOError):
                return None
        return None
