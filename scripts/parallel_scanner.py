#!/usr/bin/env python3
"""并行扫描 + 增量缓存模块

提供：
1. 多仓库并行扫描（ThreadPoolExecutor）
2. 基于文件 hash 的增量缓存（比 mtime 更可靠）
3. 跳过未变更的仓库（IR cache 新鲜时直接加载）

用法：
    from parallel_scanner import ParallelScanner
    scanner = ParallelScanner(kb_dir="/path/to/knowledge")
    results = scanner.scan_repos(repos, languages, max_workers=4)
"""

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional
import os


# ──────────────────────────────────────────────
# Hash-based incremental cache
# ──────────────────────────────────────────────

class HashCache:
    """基于文件 hash 的增量缓存
    
    相比 mtime 方案的优势：
    - 不受文件系统时间戳精度影响
    - 能检测到内容相同但时间戳变化的文件
    - 缓存 key 稳定（内容 hash）
    - 支持仓库级和文件级两级缓存
    """
    
    def __init__(self, kb_dir: str):
        self.kb_dir = Path(kb_dir)
        self.hash_file = self.kb_dir / ".scan_hashes.json"
        self.skip_file = self.kb_dir / ".skip_repos.json"
    
    def compute_repo_hash(self, repo_path: Path, lang: str, max_files: int = 500) -> str:
        """计算仓库内容的综合 hash
        
        策略：
        1. 收集所有源代码文件的 hash（限制数量避免慢扫描）
        2. 合并为 repo hash
        3. 加入语言标识避免 Go/Python 混淆
        4. 加入文件数量作为快速变化检测
        """
        file_hashes = []
        ext = self._lang_to_ext(lang)
        count = 0
        total_count = 0
        
        for f in sorted(repo_path.rglob(f"**/*{ext}")):
            total_count += 1
            if count >= max_files:
                break
            if any(skip in str(f) for skip in ['vendor/', '.git/', 'node_modules/', '__pycache__', '.tox']):
                continue
            try:
                h = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
                rel = str(f.relative_to(repo_path))
                file_hashes.append(f"{rel}:{h}")
                count += 1
            except (OSError, IOError):
                continue
        
        # 综合 hash：语言 + 文件数 + 文件hash列表
        content = f"lang={lang}|total={total_count}|scanned={count}|{';'.join(file_hashes[:200])}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def load_cached_hashes(self) -> Dict[str, Any]:
        """加载上次扫描的 hash 记录"""
        if self.hash_file.exists():
            try:
                return json.loads(self.hash_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"repos": {}, "timestamp": 0}
    
    def save_hashes(self, data: Dict[str, Any]):
        """保存 hash 记录"""
        data["timestamp"] = time.time()
        self.hash_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    def get_skipped_repos(self) -> set:
        """获取应该跳过的仓库（hash 未变化）"""
        if not self.skip_file.exists():
            return set()
        try:
            data = json.loads(self.skip_file.read_text(encoding="utf-8"))
            return set(data.get("repos", []))
        except Exception:
            return set()
    
    def save_skipped_repos(self, repo_names: List[str]):
        """保存跳过列表"""
        self.skip_file.write_text(
            json.dumps({"repos": repo_names, "timestamp": time.time()}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def is_cache_fresh(self, repo_name: str, expected_hash: str) -> bool:
        """检查仓库缓存是否新鲜"""
        cached = self.load_cached_hashes()
        repo_hash = cached.get("repos", {}).get(repo_name, "")
        return repo_hash == expected_hash and repo_hash != ""
    
    @staticmethod
    def _lang_to_ext(lang: str) -> str:
        mapping = {"go": ".go", "python": ".py", "java": ".java"}
        return mapping.get(lang, ".go")


# ──────────────────────────────────────────────
# Parallel scanner
# ──────────────────────────────────────────────

class ParallelScanner:
    """多仓库并行扫描器
    
    工作流程：
    1. 对每个仓库计算 hash
    2. 对比缓存，跳过未变更的仓库
    3. 对需要扫描的仓库，使用线程池并行扫描
    4. 保存新的 hash 记录
    """
    
    def __init__(self, kb_dir: str, max_workers: int = 4):
        self.kb_dir = Path(kb_dir)
        self.max_workers = max_workers
        self.hash_cache = HashCache(kb_dir)
    
    def scan_repos(
        self,
        repos: List[Dict[str, Any]],
        scanners: Dict[str, Any],
        max_files: int = 500,
    ) -> List[Dict[str, Any]]:
        """并行扫描多个仓库
        
        Args:
            repos: 仓库配置列表，每项包含 {name, path, language, ...}
            scanners: 语言 → scanner 实例映射，如 {"go": GoScanner(), "python": PythonScanner()}
            max_files: 每个仓库最大扫描文件数
            
        Returns:
            List of {repo_name, ir, skipped, duration}
        """
        results = []
        skipped_repos = self.hash_cache.get_skipped_repos()
        
        # 分离需要扫描和可以跳过的仓库
        to_scan = []
        for repo in repos:
            name = repo["name"]
            repo_path = Path(repo["path"])
            lang = repo.get("language", "go")
            
            if not repo_path.exists():
                results.append({
                    "repo_name": name,
                    "error": f"Repository not found: {repo_path}",
                    "skipped": False,
                })
                continue
            
            # 检查是否可以跳过
            if name in skipped_repos:
                results.append({
                    "repo_name": name,
                    "skipped": True,
                    "reason": "cached",
                })
                continue
            
            to_scan.append((repo, lang))
        
        if not to_scan:
            print("  All repos skipped (cache fresh)")
            return results
        
        # 并行扫描
        print(f"  Scanning {len(to_scan)} repos in parallel (max_workers={self.max_workers})...")
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for repo, lang in to_scan:
                future = executor.submit(
                    self._scan_single_repo, repo, lang, scanners, max_files
                )
                futures[future] = repo["name"]
            
            for future in as_completed(futures):
                repo_name = futures[future]
                try:
                    result = future.result(timeout=300)
                    result["repo_name"] = repo_name
                    result["duration"] = time.time() - start_time
                    results.append(result)
                except Exception as e:
                    results.append({
                        "repo_name": repo_name,
                        "error": str(e),
                        "skipped": False,
                        "duration": time.time() - start_time,
                    })
        
        # 保存 hash
        self._save_hashes(to_scan, results, max_files)
        
        skipped_count = sum(1 for r in results if r.get("skipped"))
        scanned_count = sum(1 for r in results if not r.get("skipped") and "error" not in r)
        error_count = sum(1 for r in results if "error" in r)
        print(f"  Done: {scanned_count} scanned, {skipped_count} skipped, {error_count} errors")
        
        return results
    
    def _scan_single_repo(
        self, repo: Dict, lang: str, scanners: Dict, max_files: int
    ) -> Dict:
        """扫描单个仓库"""
        repo_path = Path(repo["path"])
        scanner = scanners.get(lang)
        
        if scanner is None:
            return {"error": f"No scanner for language: {lang}"}
        
        try:
            ir = scanner.scan_directory(repo_path, max_files=max_files)
            ir.repo_name = repo["name"]
            ir.repo_path = str(repo_path)
            
            return {
                "ir": ir,
                "skipped": False,
                "structs": len(ir.structs) if hasattr(ir, 'structs') else 0,
                "functions": len(ir.functions) if hasattr(ir, 'functions') else 0,
                "routes": len(ir.routes) if hasattr(ir, 'routes') else 0,
            }
        except Exception as e:
            return {"error": f"Scan failed: {e}"}
    
    def _save_hashes(self, to_scan: List, results: List, max_files: int):
        """保存 hash 记录（用于下次增量对比）"""
        cached = self.hash_cache.load_cached_hashes()
        if "repos" not in cached:
            cached["repos"] = {}
        
        for (repo, lang), result in zip(to_scan, results):
            if "error" in result:
                continue
            try:
                repo_path = Path(repo["path"])
                h = self.hash_cache.compute_repo_hash(repo_path, lang, max_files)
                cached["repos"][repo["name"]] = h
            except Exception:
                pass
        
        self.hash_cache.save_hashes(cached)


# ──────────────────────────────────────────────
# Convenience: full pipeline with parallel scan
# ──────────────────────────────────────────────

def parallel_learn_from_repos(
    profile: Dict,
    output_dir: str,
    wiki_path: Optional[str] = None,
    kb_dir: Optional[str] = None,
    max_workers: int = 4,
    max_files: int = 500,
) -> Dict:
    """并行版本的 learn_from_repos
    
    替代原有的串行扫描，支持：
    - 多仓库并行扫描
    - 增量跳过（hash 对比）
    - 更快的多仓库场景
    """
    from learn_repo import GoScanner, PythonScanner, JavaScanner, MultiRepoAnalyzer, LLMKnowledgeGenerator
    
    repos = profile.get("repositories", [])
    if not repos:
        return {"error": "No repositories configured"}
    
    # 确定 kb_dir
    if kb_dir is None:
        skill_dir = Path(__file__).parent.parent
        domain = profile.get("business_domain", "unknown")
        kb_dir = str(skill_dir / "knowledge" / domain)
    
    os.makedirs(kb_dir, exist_ok=True)
    
    # 构建 scanner 映射
    scanners = {}
    for repo in repos:
        lang = repo.get("language", "go")
        if lang == "go" and "GoScanner" not in scanners:
            scanners["go"] = GoScanner()
        elif lang == "python" and "PythonScanner" not in scanners:
            scanners["python"] = PythonScanner()
        elif lang == "java" and "JavaScanner" not in scanners:
            scanners["java"] = JavaScanner()
    
    # 并行扫描
    scanner = ParallelScanner(kb_dir, max_workers=max_workers)
    scan_results = scanner.scan_repos(repos, scanners, max_files)
    
    # 过滤出有效的 IR
    valid_results = [r for r in scan_results if "ir" in r]
    if not valid_results:
        return {"error": "No repositories scanned successfully"}
    
    all_ir = [r["ir"] for r in valid_results]
    main_ir = all_ir[0]
    
    # 多仓库依赖分析
    analyzer = MultiRepoAnalyzer()
    dep_graph = analyzer.analyze(repos)
    print(f"Dependency graph: {len(dep_graph.get('edges', []))} edges")
    
    # 构建 prompt
    generator = LLMKnowledgeGenerator()
    prompt = generator.build_prompt(main_ir, dep_graph, repos, repos[0]['path'] if repos else None)
    
    # 输出
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    prompt_file = output_path / "learn_prompt.md"
    prompt_file.write_text(prompt, encoding="utf-8")
    
    return {
        "status": "completed",
        "repos_scanned": len(valid_results),
        "repos_skipped": sum(1 for r in scan_results if r.get("skipped")),
        "prompt_file": str(prompt_file),
        "dep_graph_edges": len(dep_graph.get("edges", [])),
        "structs": len(main_ir.structs) if hasattr(main_ir, 'structs') else 0,
        "functions": len(main_ir.functions) if hasattr(main_ir, 'functions') else 0,
    }
