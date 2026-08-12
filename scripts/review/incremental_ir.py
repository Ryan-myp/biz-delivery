#!/usr/bin/env python3
"""增量 IR 更新模块 — 仅扫描变更文件，避免全量重建

通过跟踪文件修改时间戳，只重新扫描发生变化的文件，
大幅提升后续查询的 IR 构建速度。

Usage:
    from scripts.review.incremental_ir import IncrementalIRUpdater
    
    updater = IncrementalIRUpdater(cache_path)
    updated_ir = updater.update(ir_data, repo_path, profile)
"""

from typing import Dict, List, Optional, Set
from pathlib import Path
import json
import hashlib
import time
from datetime import datetime


# ──────────────────────────────────────────────
# File Tracker — 文件变更追踪
# ──────────────────────────────────────────────

class FileTracker:
    """文件变更追踪器 — 记录文件哈希和修改时间"""
    
    def __init__(self):
        self.file_states: Dict[str, Dict] = {}  # path -> {mtime, size, hash}
    
    def load_from_cache(self, cache_path: str):
        """从缓存加载文件状态"""
        cache_file = Path(cache_path)
        if cache_file.exists():
            with open(cache_file) as f:
                data = json.load(f)
                self.file_states = data.get("file_states", {})
    
    def save_to_cache(self, cache_path: str):
        """保存文件状态到缓存"""
        cache_file = Path(cache_path)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w") as f:
            json.dump({"file_states": self.file_states, "updated_at": datetime.now().isoformat()}, f, indent=2)
    
    def get_file_hash(self, file_path: str) -> str:
        """计算文件哈希（用于检测内容变化）"""
        try:
            path = Path(file_path)
            if not path.exists():
                return ""
            
            # 只哈希前 4KB 和内容长度，快速检测变化
            with open(path, "rb") as f:
                content = f.read(4096)
                return hashlib.md5(content).hexdigest()
        except Exception:
            return ""
    
    def get_file_mtime(self, file_path: str) -> float:
        """获取文件修改时间"""
        try:
            return Path(file_path).stat().st_mtime
        except Exception:
            return 0.0
    
    def check_changes(self, file_paths: List[str]) -> Dict[str, str]:
        """检查文件变更情况
        
        Returns:
            {path: "added" | "modified" | "deleted" | "unchanged"}
        """
        changes = {}
        
        for path in file_paths:
            if path not in self.file_states:
                # 新文件
                changes[path] = "added"
            else:
                state = self.file_states[path]
                current_hash = self.get_file_hash(path)
                current_mtime = self.get_file_mtime(path)
                
                if current_hash != state.get("hash", ""):
                    changes[path] = "modified"
                elif current_mtime > state.get("mtime", 0):
                    changes[path] = "modified"
                else:
                    changes[path] = "unchanged"
        
        # 检测删除的文件
        for path in list(self.file_states.keys()):
            if path not in file_paths:
                changes[path] = "deleted"
        
        return changes
    
    def update_state(self, path: str, hash_value: str = None, mtime: float = None):
        """更新文件状态"""
        if hash_value is None:
            hash_value = self.get_file_hash(path)
        if mtime is None:
            mtime = self.get_file_mtime(path)
        
        self.file_states[path] = {
            "hash": hash_value,
            "mtime": mtime,
            "size": Path(path).stat().st_size if Path(path).exists() else 0,
        }


# ──────────────────────────────────────────────
# Incremental IR Updater — 增量 IR 更新器
# ──────────────────────────────────────────────

class IncrementalIRUpdater:
    """增量 IR 更新器 — 仅更新变更部分的 IR"""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.file_tracker = FileTracker()
        self.ir_cache_file = self.cache_dir / "ir_file_states.json"
        self._load_state()
    
    def _load_state(self):
        """加载当前状态"""
        self.file_tracker.load_from_cache(str(self.ir_cache_file))
    
    def _save_state(self):
        """保存当前状态"""
        self.file_tracker.save_to_cache(str(self.ir_cache_file))
    
    def update(
        self,
        existing_ir: dict,
        repo_path: str,
        scan_func,
        profile: dict = None
    ) -> dict:
        """增量更新 IR
        
        Args:
            existing_ir: 现有的 IR 数据
            repo_path: 仓库路径
            scan_func: 扫描函数，签名: scan_func(file_paths) -> IRDocument
            profile: 业务 Profile
            
        Returns:
            更新后的 IR 数据
        """
        repo = Path(repo_path)
        if not repo.exists():
            return existing_ir
        
        # 1. 收集所有源文件
        source_files = self._collect_source_files(repo, profile)
        
        # 2. 检测变更
        changes = self.file_tracker.check_changes(source_files)
        
        added_files = [p for p, s in changes.items() if s == "added"]
        modified_files = [p for p, s in changes.items() if s == "modified"]
        deleted_files = [p for p, s in changes.items() if s == "deleted"]
        
        print(f"📊 IR 增量更新: +{len(added_files)} ~{len(modified_files)} -{len(deleted_files)}")
        
        if not added_files and not modified_files and not deleted_files:
            print("  ✓ 无变更，跳过扫描")
            return existing_ir
        
        # 3. 只扫描变更文件
        changed_files = added_files + modified_files
        if changed_files:
            new_ir = scan_func(changed_files)
            
            # 4. 合并 IR
            updated_ir = self._merge_ir(existing_ir, new_ir, changes)
        else:
            updated_ir = existing_ir
        
        # 5. 更新文件状态
        for path in source_files:
            self.file_tracker.update_state(path)
        self._save_state()
        
        return updated_ir
    
    def _collect_source_files(self, repo: Path, profile: dict = None) -> List[str]:
        """收集源文件列表"""
        language = (profile or {}).get("language", "go")
        patterns = {
            "go": ["*.go"],
            "python": ["*.py"],
            "java": ["*.java"],
        }
        
        files = []
        for pattern in patterns.get(language, ["*.go"]):
            files.extend(str(p) for p in repo.rglob(pattern))
        
        return files
    
    def _merge_ir(
        self,
        old_ir: dict,
        new_ir: dict,
        changes: Dict[str, str]
    ) -> dict:
        """合并新旧 IR"""
        merged = old_ir.copy()
        
        # 合并 functions
        old_functions = {f["name"]: f for f in merged.get("functions", [])}
        new_functions = {f["name"]: f for f in new_ir.get("functions", [])}
        
        # 添加新函数，更新修改的函数
        for name, func in new_functions.items():
            if name not in old_functions:
                merged.setdefault("functions", []).append(func)
            elif changes.get(func.get("file", ""), "") in ["modified", "added"]:
                # 更新函数
                for i, old_func in enumerate(merged["functions"]):
                    if old_func.get("name") == name:
                        merged["functions"][i] = func
                        break
        
        # 合并 structs
        old_structs = {s["name"]: s for s in merged.get("structs", [])}
        new_structs = {s["name"]: s for s in new_ir.get("structs", [])}
        
        for name, struct in new_structs.items():
            if name not in old_structs:
                merged.setdefault("structs", []).append(struct)
            elif changes.get(struct.get("file", ""), "") in ["modified", "added"]:
                for i, old_struct in enumerate(merged["structs"]):
                    if old_struct.get("name") == name:
                        merged["structs"][i] = struct
                        break
        
        # 合并 routes
        old_routes = {(r.get("path"), r.get("method")): r for r in merged.get("routes", [])}
        new_routes = {(r.get("path"), r.get("method")): r for r in new_ir.get("routes", [])}
        
        for key, route in new_routes.items():
            if key not in old_routes:
                merged.setdefault("routes", []).append(route)
            elif changes.get(route.get("file", ""), "") in ["modified", "added"]:
                for i, old_route in enumerate(merged["routes"]):
                    if (old_route.get("path"), old_route.get("method")) == key:
                        merged["routes"][i] = route
                        break
        
        # 处理删除的文件
        for path, status in changes.items():
            if status == "deleted":
                merged = self._remove_from_ir(merged, path)
        
        return merged
    
    def _remove_from_ir(self, ir: dict, deleted_path: str) -> dict:
        """从 IR 中移除已删除文件的内容"""
        result = ir.copy()
        
        # 移除 functions
        result["functions"] = [
            f for f in result.get("functions", [])
            if f.get("file", "") != deleted_path
        ]
        
        # 移除 structs
        result["structs"] = [
            s for s in result.get("structs", [])
            if s.get("file", "") != deleted_path
        ]
        
        # 移除 routes
        result["routes"] = [
            r for r in result.get("routes", [])
            if r.get("file", "") != deleted_path
        ]
        
        return result
    
    def force_full_rebuild(self, repo_path: str, scan_func, profile: dict = None) -> dict:
        """强制全量重建 IR"""
        self.file_tracker = FileTracker()
        return scan_func(self._collect_source_files(Path(repo_path), profile))


# ──────────────────────────────────────────────
# IR Cache Manager — IR 缓存管理
# ──────────────────────────────────────────────

class IRCacheManager:
    """IR 缓存管理器 — 管理多仓库的 IR 缓存"""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cache_path(self, repo_name: str) -> str:
        """获取仓库的缓存路径"""
        return str(self.cache_dir / f"{repo_name}_ir.json")
    
    def get_file_states_path(self, repo_name: str) -> str:
        """获取文件状态缓存路径"""
        return str(self.cache_dir / f"{repo_name}_file_states.json")
    
    def load_ir(self, repo_name: str) -> Optional[dict]:
        """加载 IR 缓存"""
        cache_path = self.get_cache_path(repo_name)
        if Path(cache_path).exists():
            with open(cache_path) as f:
                return json.load(f)
        return None
    
    def save_ir(self, repo_name: str, ir_data: dict):
        """保存 IR 缓存"""
        cache_path = self.get_cache_path(repo_name)
        with open(cache_path, "w") as f:
            json.dump(ir_data, f, ensure_ascii=False, indent=2)
    
    def invalidate(self, repo_name: str):
        """使缓存失效"""
        for pattern in [f"{repo_name}_ir.json", f"{repo_name}_file_states.json"]:
            cache_file = self.cache_dir / pattern
            if cache_file.exists():
                cache_file.unlink()


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def get_incremental_updater(cache_dir: str = ".cache") -> IncrementalIRUpdater:
    """获取增量 IR 更新器实例"""
    return IncrementalIRUpdater(cache_dir)


def get_cache_manager(repo_name: str, cache_dir: str = ".cache") -> IRCacheManager:
    """获取 IR 缓存管理器实例"""
    manager = IRCacheManager(cache_dir)
    return manager


if __name__ == "__main__":
    # 测试示例
    print("=== 增量 IR 更新测试 ===")
    
    updater = IncrementalIRUpdater(".test_cache")
    print(f"缓存目录: {updater.cache_dir}")
    print("✓ 增量更新器初始化完成")
