#!/usr/bin/env python3
"""Shared base classes for biz-delivery engines.

Eliminates code duplication between review_engine, td_engine, and test_engine.
Each engine inherits from EngineBase and only implements its own prompt building logic.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from learn_repo import GoScanner, IRDocument


# ──────────────────────────────────────────────
# Route handler cleanup regex (shared)
# ──────────────────────────────────────────────
_HANDLER_CLEAN_RE = re.compile(r'\s*\([^)]*$')
_HANDLER_CLEAN_RE2 = re.compile(r'\s*\([^)]*\).*')


class EngineBase:
    """Base class for all biz-delivery engines.

    Provides shared:
    - Codebase scanning (_scan_codebase)
    - Evidence querying (_query_evidence_for_prd)
    - Profile normalization
    - KB directory inference
    """

    def __init__(self, profile: dict, output_dir: str, wiki_path: Optional[str] = None):
        self.profile = profile
        self.output_dir = Path(output_dir)
        self.wiki_path = wiki_path
        
        # Validate and normalize profile
        profile_data = self._normalize_profile(profile)
        
        # Required fields validation
        missing = []
        if not profile_data.get("business_domain"):
            missing.append("business_domain")
        if not profile_data.get("repositories"):
            missing.append("repositories")
        
        # Warn on missing required fields
        if missing:
            print(f"⚠️  Profile missing required fields: {', '.join(missing)}")
            print(f"   business_domain will default to 'unknown'")
            print(f"   repositories will be empty — engines may skip scanning")
        
        self.business_domain = profile_data.get("business_domain", "unknown")
        self.repos = profile_data.get("repositories", [])
        
        # Validate repository paths
        for repo in self.repos:
            repo_path = repo.get("path", "")
            if repo_path and not Path(repo_path).exists():
                print(f"⚠️  Repository path does not exist: {repo_path}")

        # Infer kb_dir from profile or project structure
        self.kb_dir = None
        repo_paths = [r.get("path", "") for r in self.repos if r.get("path")]
        if repo_paths:
            rp = Path(repo_paths[0])
            kb_candidate = rp.parent / "knowledge" / self.business_domain
            if kb_candidate.exists():
                self.kb_dir = str(kb_candidate)

    # ── Profile helpers ─────────────────────────

    @staticmethod
    def _normalize_profile(profile: dict) -> dict:
        """Handle both flat and nested profile structures."""
        if isinstance(profile, dict):
            inner = profile.get('profile', {})
            if inner:
                return inner
        return profile

    # ── Incremental / Parallel Scan Support ─────

    def _get_scan_cache_dir(self) -> Optional[str]:
        """Infer a cache directory for incremental scanning."""
        for repo in self.repos:
            rp = Path(repo.get("path", ""))
            if rp.exists():
                return str(rp.parent / ".biz_delivery_cache")
        return None

    def _try_load_cached_ir(self, cache_dir: str) -> Optional[dict]:
        """Try loading IR from cache (ir_cache.json). Returns None if stale."""
        cache_file = Path(cache_dir) / "ir_cache.json"
        if not cache_file.exists():
            return None
        try:
            import time as _time
            age_hours = (_time.time() - cache_file.stat().st_mtime) / 3600
            if age_hours > 24:
                return None
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    # ── Codebase scanning ───────────────────────

    def _scan_codebase(self) -> IRDocument:
        """Scan configured repositories and return merged IRDocument.

        Supports:
        - Multi-repo merging
        - Incremental scan (loads cached IR if fresh)
        - Parallel scan via parallel_scanner when kb_dir is available
        """
        if not self.repos:
            print("⚠️  No repositories configured, skipping scan")
            return IRDocument(repo_name="none", repo_path="", language="unknown")

        # Try incremental scan first
        cache_dir = self._get_scan_cache_dir()
        if cache_dir:
            cached = self._try_load_cached_ir(cache_dir)
            if cached:
                print(f"✅ Using cached IR from {cache_dir}/ir_cache.json")
                # Reconstruct IRDocument from dict
                return self._dict_to_ir(cached)

        # Fallback: full scan (possibly parallel)
        kb_dir = self.kb_dir or cache_dir
        if kb_dir:
            try:
                from .parallel_scanner import ParallelScanner
                result = self._parallel_scan(kb_dir)
                if result is not None:
                    return result
            except Exception:
                pass  # Fall back to sequential

        # Sequential scan (original path)
        return self._sequential_scan()

    def _parallel_scan(self, kb_dir: str) -> Optional[IRDocument]:
        """Try parallel scan via ParallelScanner."""
        from .parallel_scanner import ParallelScanner
        scanners = {}
        for repo in self.repos:
            lang = repo.get("language", "go")
            if lang == "go" and "GoScanner" not in scanners:
                scanners["go"] = GoScanner()
        if not scanners:
            return None

        ps = ParallelScanner(kb_dir, max_workers=min(4, len(self.repos)))
        scan_results = ps.scan_repos(self.repos, scanners, max_files=500)
        valid = [r for r in scan_results if "ir" in r]
        if not valid:
            return None

        # Merge results
        merged = IRDocument(repo_name="multi-parallel", repo_path="", language="go")
        for sr in valid:
            ir = sr["ir"]
            for attr in ['structs', 'functions', 'routes', 'entity_tables',
                         'sql_operations', 'error_codes', 'auth_models',
                         'business_logic', 'test_files', 'test_functions',
                         'imports', 'configs', 'services']:
                if hasattr(ir, attr):
                    getattr(merged, attr).extend(getattr(ir, attr))
            for attr in ['packages', 'call_graph', 'core_flows', 'perf_hotspots']:
                if hasattr(ir, attr) and getattr(ir, attr):
                    if not hasattr(merged, attr):
                        setattr(merged, attr, [])
                    getattr(merged, attr).extend(getattr(ir, attr))

        langs = set()
        for r in valid:
            ir_item = r.get("ir")
            if ir_item and hasattr(ir_item, "language"):
                langs.add(ir_item.language)
        merged.language = ",".join(sorted(langs)) if len(langs) > 1 else (list(langs)[0] if langs else "go")
        return merged

    def _sequential_scan(self) -> IRDocument:
        """Original sequential scan path."""
        merged = IRDocument(repo_name="multi", repo_path="", language="go")
        scanners_used = set()

        for repo in self.repos:
            repo_path = Path(repo["path"])
            language = repo.get("language", "go")
            repo_name = repo.get("name", repo_path.name)

            if language == "go":
                scanner = GoScanner()
            else:
                print(f"⚠️  Unsupported language {language} for repo {repo_name}, skipping")
                continue

            scanners_used.add(language)
            ir = scanner.scan_directory(repo_path)
            ir.repo_name = repo_name
            ir.repo_path = str(repo_path)

            for route in ir.routes:
                if hasattr(route, 'handler'):
                    route.handler = _HANDLER_CLEAN_RE.sub('', route.handler)
                    route.handler = _HANDLER_CLEAN_RE2.sub('', route.handler)
                    if '.' in route.handler:
                        route.handler = route.handler.split('.')[-1]
                    route.handler = route.handler.strip()

            merged.structs.extend(ir.structs)
            merged.functions.extend(ir.functions)
            merged.routes.extend(ir.routes)
            merged.entity_tables.extend(ir.entity_tables)
            merged.sql_operations.extend(ir.sql_operations)
            merged.error_codes.extend(ir.error_codes)
            merged.auth_models.extend(ir.auth_models)
            merged.business_logic.extend(ir.business_logic)
            merged.test_files.extend(ir.test_files)
            merged.test_functions.extend(ir.test_functions)
            merged.imports.extend(ir.imports)
            merged.configs.extend(ir.configs)

            if hasattr(ir, 'packages') and ir.packages:
                merged.packages.update(ir.packages) if hasattr(merged, 'packages') else None
            if hasattr(ir, 'call_graph') and ir.call_graph:
                merged.call_graph.extend(ir.call_graph) if hasattr(merged, 'call_graph') else None
            if hasattr(ir, 'core_flows') and ir.core_flows:
                merged.core_flows.extend(ir.core_flows) if hasattr(merged, 'core_flows') else None
            if hasattr(ir, 'services') and ir.services:
                merged.services.extend(ir.services) if hasattr(merged, 'services') else None
            if hasattr(ir, 'perf_hotspots') and ir.perf_hotspots:
                merged.perf_hotspots.extend(ir.perf_hotspots) if hasattr(merged, 'perf_hotspots') else None

            if language != "unknown":
                merged.language = language

            print(f"  Scanned repo '{repo_name}': {len(ir.structs)} structs, "
                  f"{len(ir.functions)} functions, {len(ir.routes)} routes")

        if len(scanners_used) == 1:
            merged.language = list(scanners_used)[0]
        elif len(scanners_used) > 1:
            merged.language = ", ".join(sorted(scanners_used))

        return merged

    @staticmethod
    def _dict_to_ir(data: dict) -> IRDocument:
        """Reconstruct IRDocument from cached dict."""
        ir = IRDocument(
            repo_name=data.get("repo_name", "cached"),
            repo_path=data.get("repo_path", ""),
            language=data.get("language", "go"),
        )
        for attr in ['structs', 'functions', 'routes', 'entity_tables',
                     'sql_operations', 'error_codes', 'auth_models',
                     'business_logic', 'test_files', 'test_functions',
                     'imports', 'configs', 'services']:
            val = data.get(attr, [])
            if val:
                setattr(ir, attr, val)
        for attr in ['packages', 'call_graph', 'core_flows', 'perf_hotspots']:
            val = data.get(attr)
            if val:
                setattr(ir, attr, val)
        return ir

    # ── Evidence querying ───────────────────────

    def _query_evidence_for_prd(self, prd_text: str, cache_dir: str = "") -> dict:
        """Query evidence from codebase using PRD keywords.

        Uses shared _common.query_evidence_for_prd implementation.
        Lazy import to avoid circular dependency with _common (which uses relative imports).
        """
        # Lazy import to avoid circular dependency
        from _common import query_evidence_for_prd as qefp
        
        profile_data = self._normalize_profile(self.profile)
        return qefp(
            prd_text=prd_text,
            profile=profile_data,
            wiki_path=self.wiki_path or "",
            cache_dir=cache_dir,
            top_k_per_query=5,
            max_total=30,
        )

    # ── Prompt building helpers ─────────────────

    def _build_ir_summary(self, ir: IRDocument) -> List[str]:
        """Build a standard IR summary section for prompts."""
        parts = []
        parts.append(f"- **业务域**: {self.business_domain}")
        parts.append(f"- **仓库**: {', '.join(r.get('name', r.get('path', '')) for r in self.repos)}")
        parts.append(f"- **语言**: {ir.language}")
        parts.append(f"- **Structs**: {len(ir.structs)}")
        parts.append(f"- **Functions**: {len(ir.functions)}")
        parts.append(f"- **Routes**: {len(ir.routes)}")
        parts.append(f"- **Entity Tables**: {len(ir.entity_tables)}")
        parts.append(f"- **SQL Operations**: {len(ir.sql_operations)}")
        parts.append(f"- **Error Codes**: {len(ir.error_codes)}")
        parts.append(f"- **Auth Models**: {len(ir.auth_models)}")
        coverage = getattr(ir, 'coverage_report', {}).get('coverage_pct', 0) if hasattr(ir, 'coverage_report') else 0
        parts.append(f"- **Test Coverage**: {coverage}%")
        return parts

    def _build_routes_section(self, ir: IRDocument, label: str = "关键路由", limit: int = 30) -> str:
        """Format routes for prompt injection."""
        if not ir.routes:
            return ""
        lines = [f"## {label}（前{limit}条）"]
        for route in ir.routes[:limit]:
            method = getattr(route, 'method', 'GET').upper()
            path = getattr(route, 'path', '?')
            handler = getattr(route, 'handler', '?')
            lines.append(f"- `{method}` {path} → `{handler}`")
        lines.append("")
        return "\n".join(lines)

    def _build_business_logic_section(self, ir: IRDocument, label: str = "业务逻辑", limit: int = 10) -> str:
        """Format business logic call chains for prompt injection."""
        if not ir.business_logic:
            return ""
        lines = [f"## {label}（入口点调用链）"]
        for bl in ir.business_logic[:limit]:
            route = bl.get('route', '?')
            method = bl.get('method', 'GET')
            handler = bl.get('handler', '?')
            desc = bl.get('description', '')
            lines.append(f"- `{method}` {route} → `{handler}`")
            lines.append(f"  逻辑: {desc}")
            calls = bl.get('calls', [])
            if calls:
                lines.append(f"  调用: {', '.join(calls[:8])}")
            second = bl.get('second_layer', [])
            if second:
                for sl in second[:5]:
                    name = sl.get('name', '?') if isinstance(sl, dict) else getattr(sl, 'name', '?')
                    file = sl.get('file', '?') if isinstance(sl, dict) else getattr(sl, 'file', '?')
                    lines.append(f"    - {name}() @ {file}")
            lines.append("")
        return "\n".join(lines)

    def _build_entity_table_section(self, ir: IRDocument, limit: int = 15) -> str:
        """Format entity-table mappings for prompt injection."""
        if not ir.entity_tables:
            return ""
        lines = ["## Entity-Table 映射（前{}张）".format(limit)]
        for et in ir.entity_tables[:limit]:
            entity = et.get('entity', '?') if isinstance(et, dict) else '?'
            table = et.get('table', '?') if isinstance(et, dict) else '?'
            lines.append(f"- `{entity}` → `{table}`")
        lines.append("")
        return "\n".join(lines)

    def _build_error_code_section(self, ir: IRDocument, limit: int = 15) -> str:
        """Format error codes for prompt injection."""
        if not ir.error_codes:
            return ""
        lines = ["## 错误码（前{}个）".format(limit)]
        for ec in ir.error_codes[:limit]:
            name = ec.get('name', '?') if isinstance(ec, dict) else '?'
            code = ec.get('code', '?') if isinstance(ec, dict) else '?'
            msg = ec.get('message', '') if isinstance(ec, dict) else ''
            lines.append(f"- `{name}`: {code} — {msg}")
        lines.append("")
        return "\n".join(lines)

    def _build_auth_model_section(self, ir: IRDocument) -> str:
        """Format auth models for prompt injection."""
        if not ir.auth_models:
            return ""
        lines = ["## 鉴权模型"]
        for am in ir.auth_models:
            mw = am.get('middleware', '?') if isinstance(am, dict) else '?'
            logic = am.get('logic', '') if isinstance(am, dict) else ''
            lines.append(f"- **{mw}**: {logic}")
        lines.append("")
        return "\n".join(lines)

    def _build_sql_section(self, ir: IRDocument, limit: int = 10) -> str:
        """Format SQL operations for prompt injection."""
        if not ir.sql_operations:
            return ""
        lines = ["## SQL 操作示例（前{}个）".format(limit)]
        for sq in ir.sql_operations[:limit]:
            op = sq.get('sql_operation', '?') if isinstance(sq, dict) else '?'
            table = sq.get('table', '?') if isinstance(sq, dict) else '?'
            file = sq.get('file', '?') if isinstance(sq, dict) else '?'
            lines.append(f"- `{op}` on `{table}` in `{file}`")
        lines.append("")
        return "\n".join(lines)

    def _build_test_coverage_section(self, ir: IRDocument) -> str:
        """Format test coverage info for prompt injection."""
        if not getattr(ir, 'test_functions', None) and not ir.test_files:
            return ""
        lines = ["## 测试覆盖情况"]
        lines.append(f"- **测试文件**: {len(ir.test_files)}")
        lines.append(f"- **测试函数**: {len(ir.test_functions)}")
        cr = getattr(ir, 'coverage_report', {})
        lines.append(f"- **框架**: {cr.get('framework', 'unknown') if isinstance(cr, dict) else 'unknown'}")
        if isinstance(cr, dict) and cr.get('uncovered_highlights'):
            uncovered = cr['uncovered_highlights'][:10]
            lines.append(f"- **未覆盖函数**: {', '.join(uncovered)}")
        lines.append("")
        return "\n".join(lines)

    def _build_core_flows_section(self, ir: IRDocument, limit: int = 8) -> str:
        """Format core business flows for prompt injection."""
        if not hasattr(ir, 'core_flows') or not ir.core_flows:
            return ""
        lines = ["## 核心业务流程（从代码自动推断）"]
        for cf in ir.core_flows[:limit]:
            flow_name = cf.get('flow_name', '?')
            entry_point = cf.get('entry_point', '?')
            route_prefix = cf.get('route_prefix', '?')
            call_chain = cf.get('call_chain', [])
            data_flow = cf.get('data_flow', '?')
            max_depth = cf.get('max_depth', 0)
            lines.append(f"- **{flow_name}**: {entry_point}")
            lines.append(f"  路由: {route_prefix}")
            lines.append(f"  调用链: {', '.join(call_chain[:6])}")
            lines.append(f"  数据流: {data_flow}")
            lines.append(f"  深度: {max_depth}")
        lines.append("")
        return "\n".join(lines)

    def _build_packages_section(self, ir: IRDocument, limit: int = 15) -> str:
        """Format package structure for architecture diagram generation."""
        if not hasattr(ir, 'packages') or not ir.packages:
            return ""
        lines = ["## 包结构（用于架构图生成）"]
        for pkg_name, pkg_data in list(ir.packages.items())[:limit]:
            files = pkg_data.get('files', []) if isinstance(pkg_data, dict) else []
            funcs = pkg_data.get('functions', []) if isinstance(pkg_data, dict) else []
            structs = pkg_data.get('structs', {}) if isinstance(pkg_data, dict) else {}
            lines.append(f"### `{pkg_name}`")
            lines.append(f"- Files: {len(files)}")
            if funcs:
                lines.append(f"- Functions: {', '.join(funcs[:5])}")
            if structs:
                keys = structs.keys() if isinstance(structs, dict) else list(structs)[:5]
                lines.append(f"- Structs: {', '.join(keys)}")
        lines.append("")
        return "\n".join(lines)

    def _build_call_graph_section(self, ir: IRDocument, limit: int = 20) -> str:
        """Format call graph edges for service relationship diagrams."""
        if not hasattr(ir, 'call_graph') or not ir.call_graph:
            return ""
        lines = ["## 调用关系（用于服务关系图）"]
        for edge in ir.call_graph[:limit]:
            if isinstance(edge, dict):
                caller = edge.get('caller', '?')
                callee = edge.get('callee', '?')
            else:
                caller = getattr(edge, 'caller', '?')
                callee = getattr(edge, 'callee', '?')
            lines.append(f"- `{caller}` → `{callee}`")
        lines.append("")
        return "\n".join(lines)

    def _load_business_cards(self, cache_dir: str) -> Optional[dict]:
        """Load business_cards.json from kb_dir or cache_dir."""
        candidates = []
        if self.kb_dir:
            candidates.append(Path(self.kb_dir) / "business_cards.json")
        if cache_dir:
            candidates.append(Path(cache_dir) / "business_cards.json")
        for bc_file in candidates:
            if bc_file.exists():
                try:
                    with open(bc_file) as f:
                        return json.load(f)
                except Exception:
                    pass
        return None
