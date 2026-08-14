#!/usr/bin/env python3
"""Package Registry — lightweight index for large project support.

Instead of scanning all files for every PRD iteration, we:
1. Build a registry once (lightweight: package names, file counts, import map)
2. On each PRD iteration, identify relevant packages via keyword matching
3. Only scan/load the relevant packages + their dependencies
4. This reduces scan time from O(total_files * 8) to O(relevant_files)

Registry format (package_registry.json):
{
  "packages": {
    "github.com/user/project/share": {
      "files": ["share/handler.go", ...],
      "imports": {"fmt", "time", ...},
      "structs": {"ShareReq": {"file": "...", "fields": [...]}},
      "methods": {"GetShare": {"file": "...", "sig": "..."}},
      "routes": [{"method": "GET", "path": "/api/share", "handler": "GetShare"}],
      "funcs": {"ListShares": {"file": "...", "sig": "..."}},
    }
  },
  "package_tree": ["github.com/user/project/share", ...],
  "build_time": 1234567890
}
"""

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class PackageInfo:
    """Lightweight info about one Go package."""
    name: str
    files: List[str] = field(default_factory=list)
    file_count: int = 0
    imports: Set[str] = field(default_factory=set)
    structs: Dict[str, Dict] = field(default_factory=dict)
    methods: Dict[str, Dict] = field(default_factory=dict)
    routes: List[Dict] = field(default_factory=list)
    funcs: Dict[str, Dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "file_count": self.file_count,
            "files": self.files[:20],  # keep top 20 for index
            "imports": list(self.imports)[:30],
            "structs": {k: {"file": v["file"], "fields": v["fields"][:5]}
                        for k, v in list(self.structs.items())[:30]},
            "methods": {k: {"file": v["file"], "sig": v["sig"][:100]}
                        for k, v in list(self.methods.items())[:30]},
            "routes": self.routes[:20],
            "funcs": {k: {"file": v["file"], "sig": v["sig"][:100]}
                      for k, v in list(self.funcs.items())[:30]},
        }


class PackageRegistry:
    """Builds and manages a lightweight package registry for fast targeted scanning."""

    REGISTRY_FILENAME = "package_registry.json"
    CACHE_AGE_HOURS = 24

    def __init__(self, repo_path: str, language: str = "go"):
        self.repo_path = Path(repo_path)
        self.language = language
        self.registry_path = self.repo_path.parent / ".biz_delivery_cache" / self.REGISTRY_FILENAME
        self.packages: Dict[str, PackageInfo] = {}
        self._loaded = False

    def _is_fresh(self) -> bool:
        """Check if registry cache is still valid."""
        if not self.registry_path.exists():
            return False
        age_hours = (time.time() - self.registry_path.stat().st_mtime) / 3600
        return age_hours < self.CACHE_AGE_HOURS

    def load(self) -> bool:
        """Load registry from cache. Returns True if loaded successfully."""
        if self._loaded:
            return True
        if not self._is_fresh():
            return False
        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
            self.packages = {
                name: PackageInfo(
                    name=name,
                    files=d.get("files", []),
                    file_count=d.get("file_count", 0),
                    imports=set(d.get("imports", [])),
                    structs={k: {"file": v["file"], "fields": v["fields"]}
                             for k, v in d.get("structs", {}).items()},
                    methods={k: {"file": v["file"], "sig": v["sig"]}
                             for k, v in d.get("methods", {}).items()},
                    routes=d.get("routes", []),
                    funcs={k: {"file": v["file"], "sig": v["sig"]}
                           for k, v in d.get("funcs", {}).items()},
                )
                for name, d in data.get("packages", {}).items()
            }
            self._loaded = True
            print(f"  📦 Loaded package registry: {len(self.packages)} packages "
                  f"(from {self.registry_path})")
            return True
        except Exception as e:
            print(f"  ⚠️  Failed to load registry: {e}")
            return False

    def build(self, max_packages: int = 500) -> bool:
        """Build package registry from scratch.

        Strategy:
        1. Run go list to get all packages
        2. For each package, run a SINGLE rgrep to extract ALL symbols
        3. Build PackageInfo for each package
        4. Save to cache
        """
        print(f"  🔧 Building package registry for {self.repo_path}...")
        start = time.time()

        # Step 1: Get all packages
        packages = self._get_packages()
        if not packages:
            # Fallback: parse go.mod and directory structure
            packages = self._get_packages_fallback()

        print(f"  📦 Found {len(packages)} packages")

        # Step 2: Build registry for each package
        for pkg_path in packages[:max_packages]:
            pkg_name = self._pkg_path_to_name(pkg_path)
            if not pkg_name:
                continue

            info = PackageInfo(name=pkg_name, files=[], file_count=0)

            # Find package files
            pkg_dir = self.repo_path / pkg_path
            if pkg_dir.exists():
                for f in pkg_dir.rglob("*.go"):
                    if "vendor/" in str(f) or ".git/" in str(f):
                        continue
                    if "_test.go" in f.name or "mock" in f.name.lower():
                        continue
                    rel = str(f.relative_to(self.repo_path.parent))
                    info.files.append(rel)
                    info.file_count += 1

                # Single rgrep call per package for ALL symbol types
                # This is the key optimization: 1 call instead of 8
                self._extract_symbols_for_package(info, pkg_dir)

                # Extract imports
                for fpath in info.files[:50]:  # limit import extraction
                    full = self.repo_path.parent / fpath
                    if full.exists():
                        try:
                            text = full.read_text(errors="ignore")
                            for m in re.findall(r'"([^"]+)"', text):
                                info.imports.add(m)
                        except Exception:
                            pass

            self.packages[pkg_name] = info

        elapsed = time.time() - start
        print(f"  ✅ Registry built: {len(self.packages)} packages in {elapsed:.1f}s")

        # Save to cache
        self._save()
        return True

    def _get_packages(self) -> List[str]:
        """Use go list to get all packages."""
        try:
            r = subprocess.run(
                ["go", "list", "./..."],
                capture_output=True, text=True, timeout=60,
                cwd=str(self.repo_path),
            )
            if r.returncode == 0:
                return [p.strip() for p in r.stdout.strip().split('\n') if p.strip()]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return []

    def _get_packages_fallback(self) -> List[str]:
        """Fallback: infer packages from directory structure."""
        packages = []
        for d in self.repo_path.rglob("*.go"):
            if "vendor/" in str(d) or ".git/" in str(d):
                continue
            pkg = str(d.parent.relative_to(self.repo_path))
            if pkg not in packages:
                packages.append(pkg)
        return packages

    @staticmethod
    def _pkg_path_to_name(pkg_path: str) -> Optional[str]:
        """Convert package path to full import path."""
        try:
            r = subprocess.run(
                ["go", "list", "-f", "{{.ImportPath}}", pkg_path],
                capture_output=True, text=True, timeout=10,
                cwd=str(pkg_path.parent.parent),
            )
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            pass
        # Use directory-based name as fallback
        parts = pkg_path.split('/')
        return "/".join(["github.com/example", "project"] + parts) if len(parts) > 1 else parts[0] if parts else None

    def _extract_symbols_for_package(self, info: PackageInfo, pkg_dir: Path):
        """Extract ALL symbols from a package in a SINGLE rgrep call.

        Instead of 8 separate rgrep calls, we do one pass that extracts
        structs, methods, functions, and routes together.
        """
        import re as _re
        try:
            # Single pass: read all package files and extract symbols
            for fpath in info.files[:200]:  # limit per package
                full = self.repo_path.parent / fpath
                if not full.exists():
                    continue
                try:
                    text = full.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                # Structs
                for m in _re.finditer(r'type\s+(\w+)\s+struct\s*\{(.*?)^\}', text, _re.MULTILINE | _re.DOTALL):
                    name, body = m.group(1), m.group(2)
                    fields = _re.findall(r'\s+(\w+)\s+\w+', body)
                    info.structs[name] = {"file": fpath, "fields": fields[:10]}

                # Methods
                for m in _re.finditer(r'func\s+\(\s*\*?(\w+)\)\s+(\w+)\s*\(([^)]*)\)\s*(\w*)\s*\(([^)]*)\)', text):
                    receiver, method_name, params, ret_type, ret_params = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
                    sig = f"func (*{receiver}) {method_name}({params.strip()})"
                    if ret_type or ret_params:
                        sig += f" {ret_type}({ret_params.strip()})"
                    info.methods[method_name] = {"file": fpath, "sig": sig[:150]}

                # Top-level functions
                for m in _re.finditer(r'^func\s+(\w+)\s*\(([^)]*)\)', text, _re.MULTILINE):
                    fname, params = m.group(1), m.group(2).strip()
                    info.funcs[fname] = {"file": fpath, "sig": f"func {fname}({params})"[:150]}

                # Routes
                for m in _re.finditer(
                    r'(?:r|group|engine)\.(GET|POST|PUT|DELETE|PATCH)\s*\(\s*"([^"]+)"', text
                ):
                    method, path = m.group(1), m.group(2)
                    info.routes.append({"method": method, "path": path, "file": fpath})

        except Exception:
            pass

    def _save(self):
        """Save registry to cache file."""
        cache_dir = self.registry_path.parent
        cache_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "packages": {name: info.to_dict() for name, info in self.packages.items()},
            "build_time": time.time(),
            "package_count": len(self.packages),
        }
        try:
            self.registry_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception:
            pass

    def find_relevant_packages(self, keywords: List[str], max_packages: int = 20) -> List[str]:
        """Find packages relevant to the given keywords.

        Scoring:
        1. Package name matches keyword
        2. Package imports match keyword
        3. Package has structs/methods matching keyword
        4. Package has routes matching keyword
        """
        scored = []
        for pkg_name, pkg_info in self.packages.items():
            score = 0
            name_lower = pkg_name.lower()

            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower in name_lower:
                    score += 10
                # Check imports
                for imp in pkg_info.imports:
                    if kw_lower in imp.lower():
                        score += 5
                # Check struct/method names
                for sname in pkg_info.structs:
                    if kw_lower in sname.lower():
                        score += 8
                for mname in pkg_info.methods:
                    if kw_lower in mname.lower():
                        score += 8
                for fname in pkg_info.funcs:
                    if kw_lower in fname.lower():
                        score += 5
                # Check routes
                for route in pkg_info.routes:
                    if kw_lower in route.get("path", "").lower():
                        score += 10

            if score > 0:
                scored.append((score, pkg_name, pkg_info))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        return [pkg_name for _, pkg_name, _ in scored[:max_packages]]

    def get_package_files(self, pkg_name: str) -> List[str]:
        """Get all source files for a package."""
        pkg = self.packages.get(pkg_name)
        return pkg.files if pkg else []

    def get_transitive_deps(self, pkg_name: str, depth: int = 2) -> Set[str]:
        """Get packages that the given package depends on (up to depth levels)."""
        visited = set()
        queue = [(pkg_name, 0)]

        while queue:
            current_pkg, d = queue.pop(0)
            if d >= depth or current_pkg in visited:
                continue
            visited.add(current_pkg)

            pkg_info = self.packages.get(current_pkg)
            if not pkg_info:
                continue

            for imp in pkg_info.imports:
                # Try to find matching package in registry
                for known_pkg in self.packages:
                    if imp in known_pkg or known_pkg in imp:
                        queue.append((known_pkg, d + 1))
                        break

        return visited - {pkg_name}

    def get_freshness(self) -> float:
        """Get registry age in hours."""
        if not self.registry_path.exists():
            return float('inf')
        return (time.time() - self.registry_path.stat().st_mtime) / 3600


# Re-import re at module level
import re
