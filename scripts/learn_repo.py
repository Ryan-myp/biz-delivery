#!/usr/bin/env python3
"""learn 模式 — 从代码仓库学习并生成知识库

Usage:
    python3 learn_repo.py --profile profiles/my-service.json --output-dir knowledge/
    
流程:
    1. 解析 Profile，获取 repositories 列表
    2. 对每个仓库调用对应语言的 scanner（Go/Python/Java）
    3. 构建多仓库依赖图
    4. 组装 IR + 依赖图 → LLM prompt
    5. 调用 LLM 生成知识库
    6. 写入 wiki_engine + markdown
"""

import argparse
import json
import hashlib
from dataclasses import asdict
from collections import defaultdict
import os
import importlib.util
import ast
import urllib.request
import urllib.parse
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
# Forward reference for IRDocument
IRDocument = None




class CodeKnowledgeExtractor:
    """通用代码知识提取器 — 支持 Go/Python/Java"""
    
    def __init__(self, repo_path: str, language: str = "go"):
        self.repo_path = Path(repo_path)
        self.language = language
        self.packages = {}
    
    def extract(self) -> Dict[str, Any]:
        """提取代码知识"""
        if self.language == "go":
            return self._extract_go()
        elif self.language == "python":
            return self._extract_python()
        elif self.language == "java":
            return self._extract_java()
        else:
            return {"error": f"Unsupported language: {self.language}"}
    
    def _extract_go(self, max_files: int = 2000) -> Dict[str, Any]:
        """提取 Go 代码知识"""
        packages = {}

        for go_file in list(self.repo_path.rglob("**/*.go"))[:max_files]:
            if "test" in go_file.name.lower() or "mock" in go_file.name.lower():
                continue
            
            try:
                text = go_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            
            # 找 package 声明（跳过注释）
            lines = text.split("\n")
            pkg_name = None
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("//") and not stripped.startswith("/*") and not stripped.startswith("*"):
                    pkg_match = re.match(r"package\s+(\w+)", stripped)
                    if pkg_match:
                        pkg_name = pkg_match.group(1)
                    break
            
            if not pkg_name:
                continue
            
            if pkg_name not in packages:
                packages[pkg_name] = {"files": [], "imports": set(), "interfaces": {}, "structs": {}, "functions": []}
            
            rel_path = str(go_file.relative_to(self.repo_path.parent))
            packages[pkg_name]["files"].append(rel_path)
            
            # 提取 import
            imports = re.findall(r'"([^"]+)"', text)
            packages[pkg_name]["imports"].update(imports)
            
            # 提取 interface 定义
            interfaces = re.findall(r"type\s+(\w+)\s+interface\s*{(.*?)^\}", text, re.MULTILINE | re.DOTALL)
            for name, body in interfaces:
                methods = re.findall(r"\s+(\w+)\s*\(|\s+(\w+)\s+\w+\s+\(", body)
                method_list = [m[0] or m[1] for m in methods if m[0] or m[1]]
                packages[pkg_name]["interfaces"][name] = {"file": rel_path, "methods": method_list[:10]}
            
            # 提取 struct 定义
            structs = re.findall(r"type\s+(\w+)\s+struct\s*{(.*?)^\}", text, re.MULTILINE | re.DOTALL)
            for name, body in structs:
                fields = re.findall(r"\s+(\w+)\s+\w+", body)
                packages[pkg_name]["structs"][name] = {"file": rel_path, "fields": fields[:10]}
            
            # 提取导出函数
            funcs = re.findall(r"func\s+(\w+)\s*\(", text)
            for name in funcs:
                if name[0].isupper():
                    packages[pkg_name]["functions"].append(name)
        
        return self._build_summary(packages)
    
    def _extract_python(self) -> Dict[str, Any]:
        """提取 Python 代码知识"""
        packages = {}
        
        for py_file in self.repo_path.rglob("**/*.py"):
            if "__pycache__" in str(py_file) or "test" in py_file.name.lower():
                continue
            
            try:
                text = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            
            rel_path = str(py_file.relative_to(self.repo_path.parent))
            parts = rel_path.split("/")
            pkg_name = parts[0] if len(parts) > 1 else "root"
            
            if pkg_name not in packages:
                packages[pkg_name] = {"files": [], "imports": set(), "classes": {}, "functions": []}
            
            packages[pkg_name]["files"].append(rel_path)
            
            # 提取 import
            imports = re.findall(r"from\s+(\S+)\s+import|\s+import\s+(\S+)", text)
            for m in imports:
                for imp in m:
                    if imp:
                        packages[pkg_name]["imports"].add(imp)
            
            # 提取 class 定义
            classes = re.findall(r"class\s+(\w+)(?:\(([^)]+)\))?:\s*\n((?:\s+.*)*)", text, re.DOTALL)
            for name, bases, body in classes:
                methods = re.findall(r"def\s+(\w+)\s*\(", body)
                packages[pkg_name]["classes"][name] = {"file": rel_path, "bases": bases.split(",") if bases else [], "methods": methods[:10]}
            
            # 提取 top-level 函数
            funcs = re.findall(r"^def\s+(\w+)\s*\(", text, re.MULTILINE)
            for name in funcs:
                if not name.startswith("_"):
                    packages[pkg_name]["functions"].append(name)
        
        return self._build_summary(packages)
    
    def _extract_java(self) -> Dict[str, Any]:
        """提取 Java 代码知识"""
        packages = {}
        
        for java_file in self.repo_path.rglob("**/*.java"):
            try:
                text = java_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            
            # 找 package 声明
            pkg_match = re.search(r"package\s+([\w.]+);", text)
            if not pkg_match:
                continue
            pkg_name = pkg_match.group(1)
            
            if pkg_name not in packages:
                packages[pkg_name] = {"files": [], "imports": set(), "classes": {}, "interfaces": {}}
            
            rel_path = str(java_file.relative_to(self.repo_path.parent))
            packages[pkg_name]["files"].append(rel_path)
            
            # 提取 import
            imports = re.findall(r"import\s+([\w.]+);", text)
            packages[pkg_name]["imports"].update(imports)
            
            # 提取 class/interface 定义
            types = re.findall(r"(?:public|private|protected)?\s*(?:class|interface|enum)\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?\s*\{", text)
            for type_name, extends, implements in types:
                is_interface = "interface" in text[text.find(type_name)-50:text.find(type_name)].lower() if type_name in text else False
                
                if is_interface:
                    packages[pkg_name]["interfaces"][type_name] = {"file": rel_path, "extends": extends.split(",") if extends else [], "methods": []}
                else:
                    packages[pkg_name]["classes"][type_name] = {"file": rel_path, "extends": extends.split(",") if extends else [], "implements": implements.split(",") if implements else [], "fields": [], "methods": []}
        
        return self._build_summary(packages)
    
    def _build_summary(self, packages: Dict) -> Dict[str, Any]:
        """构建知识摘要"""
        serializable_packages = {}
        for pkg, data in packages.items():
            serializable_packages[pkg] = {
                "files": data.get("files", [])[:20],
                "imports": sorted(list(data.get("imports", set())))[:20],
                "interfaces": data.get("interfaces", {}),
                "structs": data.get("structs", {}),
                "classes": data.get("classes", {}),
                "functions": sorted(list(set(data.get("functions", []))))[:50],
            }
        
        # 提取核心流程逻辑
        flow = self._extract_flow()
        
        return {
            "language": self.language, 
            "packages": serializable_packages, 
            "package_count": len(serializable_packages),
            "flow": flow,
        }
    
    
    def _extract_cross_repo_deps(self, ir: IRDocument) -> List[Dict]:
        """提取跨仓库依赖 — 从 HTTP 调用和 RPC 调用推断"""
        deps = []
        
        # 扫描所有 Go 文件
        for go_file in self.repo_path.rglob("**/*.go"):
            if "test" in go_file.name.lower():
                continue
            try:
                content = go_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            
            # 找 HTTP 调用
            http_calls = re.findall(r'(http\.(Get|Post|Put|Delete)\s*\(\s*"[^"]+"\s*,\s*[^)]+\)', content)
            if http_calls:
                deps.append({
                    'type': 'http',
                    'file': str(go_file.relative_to(self.repo_path.parent)),
                    'calls': [c[0] for c in http_calls[:5]],
                })
            
            # 找 RPC 调用
            rpc_calls = re.findall(r'(grpc\.(Client|Server)\s*\w+\s*\()', content)
            if rpc_calls:
                deps.append({
                    'type': 'rpc',
                    'file': str(go_file.relative_to(self.repo_path.parent)),
                    'calls': [c[0] for c in rpc_calls[:5]],
                })
        
        return deps

    def _extract_flow(self) -> Dict[str, Any]:
        """提取核心流程逻辑"""
        flow = {
            "startup": [],
            "cli_commands": {},
            "templates": [],
        }
        
        # 1. 提取启动流程
        for go_file in self.repo_path.rglob("**/main.go"):
            try:
                content = go_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            
            # 找关键调用
            calls = re.findall(r'(\w+)\.\w+\(', content)
            rel_path = str(go_file.relative_to(self.repo_path.parent))
            flow["startup"].append({
                "file": rel_path,
                "calls": list(set(calls))[:10],
            })
        
        # 2. 提取 CLI 命令
        for go_file in self.repo_path.rglob("**/*.go"):
            if "test" in go_file.name.lower():
                continue
            try:
                content = go_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            
            # 找 cobra.Command 定义
            cmd_matches = re.findall(r'func\s+(\w+Command)\s*\(\)\s*\*cobra\.Command', content)
            if cmd_matches:
                pkg = go_file.parent.name
                if pkg not in flow["cli_commands"]:
                    flow["cli_commands"][pkg] = []
                flow["cli_commands"][pkg].extend(cmd_matches)
        
        # 3. 提取模板文件
        for go_file in self.repo_path.rglob("**/*.go"):
            if "test" in go_file.name.lower():
                continue
            try:
                content = go_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            
            if "embed.FS" in content or "//go:embed" in content:
                rel_path = str(go_file.relative_to(self.repo_path.parent))
                flow["templates"].append(rel_path)
        
        return flow



def _generate_enhanced_summary(ir: dict, kb_dir: str) -> str:
    """生成增强版知识摘要"""
    packages = ir.get('packages', {})
    flow = ir.get('flow', {})
    cli_cmds = flow.get('cli_commands', {})
    total_cmds = sum(len(cmds) for cmds in cli_cmds.values())
    
    lines = [
        f"# {ir.get('repo_name', 'Project')} 知识摘要",
        "",
        "## 概览",
        f"- 语言: {ir.get('language', 'unknown')}",
        f"- 包数: {len(packages)}",
        f"- 接口总数: {sum(len(p.get('interfaces', {})) for p in packages.values())}",
        f"- 结构体总数: {len(ir.get('structs', []))}",
        f"- 导出函数总数: {len(ir.get('functions', []))}",
        f"- CLI 命令: {total_cmds} 个 ({len(cli_cmds)} 个包)",
        "",
        "## 核心包",
        ""
    ]
    
    sorted_pkgs = sorted(packages.items(), key=lambda x: len(x[1].get('files', [])), reverse=True)[:10]
    for pkg, data in sorted_pkgs:
        lines.append(f"### `{pkg}`")
        lines.append(f"- Files: {len(data.get('files', []))}")
        
        interfaces = data.get('interfaces', {})
        if interfaces:
            lines.append(f"- **Interfaces**: {', '.join(interfaces.keys())[:100]}")
        
        funcs = data.get('functions', [])
        if funcs:
            lines.append(f"- **Key Functions**: {', '.join(funcs[:5])}")
        
        lines.append("")
    
    if cli_cmds:
        lines.append("## CLI 命令体系")
        lines.append("")
        for pkg, cmds in sorted(cli_cmds.items(), key=lambda x: len(x[1]), reverse=True):
            unique_cmds = list(set(cmds))[:8]
            lines.append(f"### `{pkg}`")
            lines.append(f"- Commands: {', '.join(unique_cmds)}")
            lines.append("")
    
    startup = flow.get('startup', [])
    if startup:
        lines.append("## 核心流程")
        lines.append("")
        lines.append("### 启动流程")
        lines.append("```")
        for s in startup[:1]:
            lines.append(s.get('file', ''))
            lines.append(f"  ↓")
            calls = s.get('calls', [])
            lines.append(f"  {', '.join(calls[:5])}")
        lines.append("```")
        lines.append("")
    
    summary = '\n'.join(lines)
    
    summary_file = Path(kb_dir) / "summary.md"
    summary_file.write_text(summary, encoding='utf-8')
    
    return summary



# ============================================================================
# IR (Intermediate Representation) — 多语言统一中间表示
# ============================================================================

@dataclass
class StructDef:
    """结构体定义（Go struct / Python class / Java class）"""
    name: str
    file: str
    lines: tuple = (0, 0)
    fields: List[Dict] = field(default_factory=list)
    methods: List[Dict] = field(default_factory=list)
    table_name: Optional[str] = None  # Go GORM TableName


@dataclass
class FuncDef:
    """函数/方法定义"""
    name: str
    file: str
    lines: tuple = (0, 0)
    params: List[Dict] = field(default_factory=list)
    returns: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    is_route: bool = False  # 是否是 API 路由
    route_path: Optional[str] = None
    http_method: Optional[str] = None


@dataclass
class RouteDef:
    """路由定义"""
    path: str
    method: str  # GET/POST/PUT/DELETE
    handler: str  # 处理函数名
    module: str  # 所属模块
    file: str
    middleware: List[str] = field(default_factory=list)


@dataclass
class ImportDef:
    """导入依赖"""
    module: str
    names: List[str] = field(default_factory=list)
    is_local: bool = False  # 是否是本项目内部依赖
    target_repo: Optional[str] = None  # 指向哪个仓库


@dataclass
class TableDef:
    """数据库表定义"""
    name: str
    entity_class: str
    fields: List[Dict] = field(default_factory=list)
    primary_key: Optional[str] = None
    relations: List[Dict] = field(default_factory=list)  # foreign key / has_many


@dataclass
class ServiceDef:
    """服务层定义"""
    name: str
    file: str
    methods: List[Dict] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)  # 依赖的 DAO/外部服务


@dataclass
class CallEdge:
    """调用图边"""
    caller: str  # 调用者函数名
    caller_pkg: str  # 调用者所在包
    callee: str  # 被调用者函数名
    callee_pkg: str  # 被调用者所在包
    pos: str  # 源代码位置
    is_static: bool = True  # 是否是静态调用


@dataclass
class DataFlowNode:
    """数据流节点"""
    var_name: str
    kind: str  # "definition" | "use" | "assignment"
    lineno: int
    file: str
    value_expr: Optional[str] = None  # 赋值表达式


@dataclass
class IRDocument:
    """完整 IR 文档 — 一个仓库的标准化表示（增强版：含 CG+DFG）"""
    repo_name: str
    repo_path: str
    language: str
    structs: List[StructDef] = field(default_factory=list)
    functions: List[FuncDef] = field(default_factory=list)
    routes: List[RouteDef] = field(default_factory=list)
    imports: List[ImportDef] = field(default_factory=list)
    tables: List[TableDef] = field(default_factory=list)
    services: List[ServiceDef] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)
    readme: Optional[str] = None
    
    # CPG 增强字段
    call_graph: List[CallEdge] = field(default_factory=list)  # 调用图
    data_flow: List[DataFlowNode] = field(default_factory=list)  # 数据流
    entry_points: List[Dict] = field(default_factory=list)  # 入口点
    packages: Dict[str, Any] = field(default_factory=dict)  # 包结构（通用）
    
    # 测试覆盖
    test_files: List[str] = field(default_factory=list)  # 测试文件列表
    test_functions: List[Dict] = field(default_factory=list)  # {name, file, line, covers, framework}
    coverage_report: Dict = field(default_factory=dict)  # {total_funcs, tested_funcs, uncovered_funcs}
    
    # API 文档
    api_spec: List[Dict] = field(default_factory=list)  # OpenAPI-like spec
    
    # SQL/GORM 操作
    sql_operations: List[Dict] = field(default_factory=list)  # {func, file, line, operation, table, condition}
    
    # 错误码定义
    error_codes: List[Dict] = field(default_factory=list)  # {name, code, message, category}
    
    # 权限/鉴权
    auth_models: List[Dict] = field(default_factory=list)  # {middleware, file, logic, protected_routes}
    
    # Entity/TableName 映射
    entity_tables: List[Dict] = field(default_factory=list)  # {entity, table, file}
    
    # Condition 查询条件
    conditions: List[Dict] = field(default_factory=list)  # {name, file, fields}
    
    # 配置解析
    configs: List[Dict] = field(default_factory=list)  # {file, type, key, value}
    
    # 性能热点
    perf_hotspots: List[Dict] = field(default_factory=list)
    
    # 业务逻辑（从入口点追踪调用链）
    business_logic: List[Dict] = field(default_factory=list)  # {route, handler, call_chain, description}
    
    # 核心业务流程（自动推断）
    core_flows: List[Dict] = field(default_factory=list)  # {flow_name, entry_point, call_chain, data_flow, max_depth}

    # Agent Workflow 深度解析（从 workflow YAML + Go 源码联合提取）
    agent_workflows: Dict = field(default_factory=dict)  # {agent_dir: {workflows, executors, summary}}

    # Go 源码业务流程追踪（纯代码分析，不从 YAML 读）
    go_business_flows: Dict = field(default_factory=dict)  # {agent_dir: {summary, entry_points, traces}}

    # SPX Processor 业务逻辑（dap → ad_delivery_platform 跨仓库调用）
    spex_business_flows: Dict = field(default_factory=dict)  # {repo_path: {traces, summary}}

    # 架构模式（状态机、Redis锁、Kafka、重试、幂等等）
    architectural_patterns: Dict = field(default_factory=dict)  # {state_machines, redis_locks, kafka_patterns, retry_logic, idempotency, task_group_patterns}

    # 向后兼容
    compat_issues: List[Dict] = field(default_factory=list)


# ============================================================================
# Go Scanner — 基于 ripgrep 的 Go 代码扫描器
# ============================================================================

class GoScanner:
    """Go 代码扫描器 — 使用 ripgrep 批量扫描，替代逐文件 Python re
    
    核心改进：
    - 用 rg --json 一次性搜所有文件，比 Python re 逐文件快 5-10x
    - 扫描结果按文件分组，再解析 struct/func/route/import
    - 降级策略：rg 不可用时自动 fallback 到 Python re
    """
    
    # Python re fallback patterns
    STRUCT_RE = re.compile(r'type\s+(\w+)\s+struct\s*\{(.*?)\n\}', re.DOTALL)
    TABLE_NAME_RE = re.compile(r'func.*?\*\w+\)\s+TableName\(\)\s+string\s*\{[^}]*return\s+"([^"]+)"')
    METHOD_SIG_RE = re.compile(r'func\s+\(\s*\*?(\w+)\)\s+(\w+)\s*\(([^)]*)\)\s*(\w+)?\s*\{')
    TOP_FUNC_RE = re.compile(r'^func\s+(\w+)\s*\(([^)]*)\)\s*(.*?)\{', re.MULTILINE)
    ROUTE_RE = re.compile(
        r'(?:r|group|engine|creativeGroup|groupPermission)\.'
        r'(GET|POST|PUT|DELETE|PATCH|ANY|Group)\s*\(\s*"([^"]+)"(?:\s*,\s*(.+?))?\s*\)'
    )
    GORM_TAG_RE = re.compile(r'gorm:"([^"]*)"')
    JSON_TAG_RE = re.compile(r'json:"([^"]*)"')
    QUERY_TAG_RE = re.compile(r'query:"([^"]*)"')
    GORMWHERE_TAG_RE = re.compile(r'gormwhere:"([^"]*)"')
    FIELD_TYPE_RE = re.compile(r'^\s*(\w+)\s+(?:\*?)?([\w\[\]{}|<>, ]+)(?=\s+`)')
    FIELD_TYPE_NO_TAG_RE = re.compile(r'^\s*(\w+)\s+(?:\*?)?([\w\[\]{}|<>, ]+)\s*$')
    IMPORT_BLOCK_RE = re.compile(r'import\s*\(\s*(.*?)\s*\)', re.DOTALL)
    SINGLE_IMPORT_RE = re.compile(r'^\s*"([^"]+)"\s*$')
    
    def __init__(self, use_ripgrep: bool = True):
        self.use_ripgrep = use_ripgrep
        self._rg_available = None
    
    def _is_rgrep_available(self) -> bool:
        if self._rg_available is None:
            try:
                r = subprocess.run(["rg", "--version"], capture_output=True, text=True, timeout=5)
                self._rg_available = r.returncode == 0 and "ripgrep" in r.stdout
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._rg_available = False
        return self._rg_available
    
    def _scan_with_rgrep(self, dir_path: Path, max_files: int) -> IRDocument:
        """用 ripgrep 批量扫描 — 核心加速路径（并行执行所有 rgrep）"""
        ir = IRDocument(
            repo_name=dir_path.name,
            repo_path=str(dir_path),
            language="go",
        )

        exclude_args = ["--glob", "!vendor/**", "--glob", "!**/.git/**", "--glob", "!**/_test.go"]

        # Define all scan tasks: (rg_args, parser_fn) pairs
        scan_tasks = [
            (["rg", "--json", "--type", "go", "-n",
              r"type\s+(\w+)\s+struct\s*\{"] + exclude_args + [str(dir_path)],
             lambda out: self._parse_rg_structs(out, ir, dir_path, max_files)),
            (["rg", "--json", "--type", "go", "-n",
              r'func\s+\(\s*\*\w+\)\s+TableName\(\)\s+string'] + exclude_args + [str(dir_path)],
             lambda out: self._parse_rg_table_names(out, ir)),
            (["rg", "--json", "--type", "go", "-n",
              r'func\s+\(\s*\*?\w+\)\s+\w+\s*\('] + exclude_args + [str(dir_path)],
             lambda out: self._parse_rg_methods(out, ir, dir_path, max_files)),
            (["rg", "--json", "--type", "go", "-n",
              r'^func\s+\w+\s*\('] + exclude_args + [str(dir_path)],
             lambda out: self._parse_rg_top_funcs(out, ir, dir_path, max_files)),
            (["rg", "--json", "--type", "go", "-n",
              r'(?:r|group|engine)\.(GET|POST|PUT|DELETE|PATCH)\s*\(\s*"([^"]+)"'] + exclude_args + [str(dir_path)],
             lambda out: self._parse_rg_routes(out, ir, dir_path, max_files)),
            (["rg", "--json", "--type", "go", "-n",
              r'"([^"]+)"'] + exclude_args + [str(dir_path)],
             lambda out: self._parse_rg_imports(out, ir, dir_path, max_files)),
            (["rg", "--json", "--type", "go", "-A", "30", "-n",
              r'type\s+\w+\s+struct\s*\{'] + exclude_args + [str(dir_path)],
             lambda out: self._parse_rg_struct_fields(out, ir, dir_path, max_files)),
        ]

        # Run all rgrep calls in parallel ( ThreadPoolExecutor, max 8 workers )
        import concurrent.futures
        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(scan_tasks))) as executor:
            futures = {executor.submit(self._run_rg, args): (fn, i) for i, (args, fn) in enumerate(scan_tasks)}
            for future in concurrent.futures.as_completed(futures):
                fn, idx = futures[future]
                try:
                    fn(future.result())
                except Exception as e:
                    print(f"  ⚠️  rgrep scan #{idx+1} failed: {e}")
        elapsed = time.time() - start
        print(f"  ✅ Parallel rgrep scans done in {elapsed:.1f}s")

        # Sequential post-processing (not IO-bound, keep sequential)
        self._extract_business_logic(ir, dir_path, max_entries=100)
        self._build_call_graph_from_signatures(ir)
        ir.core_flows = self._infer_core_business_flow_v2(ir)

        # 深度流程提取：从 workflow YAML + Go 源码联合推断详细业务逻辑
        try:
            agent_dirs = self._find_agent_dirs(dir_path)
            if agent_dirs:
                # 1. Workflow YAML 结构（步骤级流程）
                from deep_flow_extractor import extract_deep_flows
                print(f"  🔬 Extracting deep flows from {len(agent_dirs)} agent dir(s)...")
                deep_result = extract_deep_flows(agent_dirs, [str(dir_path)])
                ir.agent_workflows = deep_result
                for agent_dir, data in deep_result.items():
                    wf_count = len(data.get('workflows', {}))
                    exec_count = len(data.get('executors', {}))
                    print(f"    {Path(agent_dir).name}: {wf_count} workflows (YAML), {exec_count} executors traced")

                # 2. Go 源码真实调用链（不从 YAML 读，纯代码分析）
                from go_flow_analyzer import analyze_go_agent
                go_result = analyze_go_agent(agent_dirs[0], [str(dir_path)])
                ir.go_business_flows[agent_dirs[0]] = go_result
                entries = go_result.get('entry_points', [])
                run_funcs = [f for f in entries if f.startswith('runUA')]
                print(f"    {Path(agent_dirs[0]).name}: {len(entries)} entries, "
                      f"{len(run_funcs)} run* functions traced from Go source")

            # 3. SPX Processor 跨仓库调用分析（dap → ad_delivery_platform 真实业务逻辑）
            spex_dir = dir_path / "app" / "admin" / "spexprocessor"
            if spex_dir.exists():
                from go_flow_analyzer import analyze_spex_processors
                print(f"  🔬 Analyzing SPX processors: {spex_dir}...")
                spex_result = analyze_spex_processors(str(dir_path))
                ir.spex_business_flows[str(dir_path)] = spex_result
                traces = spex_result.get('traces', {})
                for func_name in list(traces.keys())[:5]:
                    calls = traces[func_name].get('calls', [])
                    cross_repo = [c for c in calls if c.get('cross_repo') or c.get('external_call')]
                    print(f"    {func_name}: {len(calls)} calls, {len(cross_repo)} → ad_delivery_platform")

            # 4. 架构模式检测（状态机、Redis锁、Kafka、重试、幂等等）
            from go_flow_analyzer import analyze_patterns, generate_pattern_summary
            print(f"  🔬 Detecting architectural patterns across repos...")
            pattern_results = analyze_patterns([str(dir_path)])
            ir.architectural_patterns = pattern_results
            print(f"    Found: {len(pattern_results.get('state_machines', []))} state machines, "
                  f"{len(pattern_results.get('redis_locks', []))} Redis patterns, "
                  f"{len(pattern_results.get('kafka_patterns', []))} Kafka consumers, "
                  f"{len(pattern_results.get('retry_logic', []))} retry patterns")
        except Exception as e:
            print(f"  ⚠️  Deep flow extraction skipped: {e}")

        self._extract_error_codes(ir, dir_path, max_files)
        self._extract_entity_tables(ir, dir_path, max_files)
        self._extract_conditions(ir, dir_path, max_files)
        self._extract_configs(ir, dir_path, max_files)

        return ir

    @staticmethod
    def _run_rg(args: list) -> str:
        """Run a single rgrep command and return stdout. Shared across all scan tasks."""
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=120)
            if r.returncode in (0, 1):
                return r.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return ""
    
    def _parse_rg_json_lines(self, output: str) -> Dict[str, List[Dict]]:
        """解析 rg --json 输出，按文件分组
        同时接受 match 和 context 两种类型（-A 上下文行）

        注意：rg --json 输出的 lines.text 字段中，
        换行符和制表符会被序列化为字面量的 \\n 和 \\t（两个字符）。
        Python 的 json.loads 默认不允许 JSON 字符串中有未转义的控制字符，
        所以需要先将这些字面量转义序列替换为真正的控制字符。
        """
        by_file = {}
        for line in output.strip().split('\n'):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                # rg 输出的是合法的 JSON，但某些 text 字段里可能包含
                # 字面量的反斜杠+n（即 JSON 字符串中的 \\n，表示两个字符）
                # 这种情况下需要把 \\n 替换为真正的换行符（\n）再解析
                try:
                    # 使用负向后瞻，只替换不在反斜杠后的 \n 和 \t
                    # 这样可以保留其他合法的 JSON 转义序列
                    fixed = re.sub(r'(?<!\\)\\n', '\n', line)
                    fixed = re.sub(r'(?<!\\)\\t', '\t', fixed)
                    data = json.loads(fixed)
                except json.JSONDecodeError:
                    continue

            # 接受 match 和 context 两种类型
            data_type = data.get("type")
            if data_type not in ("match", "context"):
                continue
            raw = data.get("data", {})
            file_path = raw.get("path", {}).get("text", "")
            line_num = raw.get("line_number", 0)
            line_text = raw.get("lines", {}).get("text", "")
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append({"line": line_num, "text": line_text, "type": data_type})
        return by_file
    
    def _parse_rg_structs(self, output: str, ir: IRDocument, dir_path: Path, max_files: int):
        """从 rg 输出解析 struct 定义"""
        by_file = self._parse_rg_json_lines(output)
        count = 0
        for file_path, lines in by_file.items():
            if count >= max_files:
                break
            rel_path = Path(file_path).relative_to(dir_path.parent)
            count += 1
            
            # 收集该文件的所有 struct 信息
            struct_defs = {}  # name -> {"fields": [], "table_name": None}
            for line_info in lines:
                text = line_info["text"]
                
                # 匹配 type XXX struct
                m = re.search(r'type\s+(\w+)\s+struct', text)
                if m:
                    struct_name = m.group(1)
                    if struct_name not in struct_defs:
                        struct_defs[struct_name] = {"fields": [], "table_name": None}
            
            # 添加到 IR
            for name, info in struct_defs.items():
                ir.structs.append(StructDef(
                    name=name,
                    file=str(rel_path),
                    fields=info["fields"][:30],
                ))
    
    def _parse_rg_struct_fields(self, output: str, ir: IRDocument, dir_path: Path, max_files: int):
        """从 rg -A 30 的输出中提取 struct 字段

        rg -A 30 输出每行都有 type: match 或 context，
        其中 match 行是 type XXX struct {，
        context 行是 struct body 里的字段定义。
        按行号排序后，用栈追踪当前 struct 名。
        """
        by_file = self._parse_rg_json_lines(output)
        count = 0
        for file_path, lines in by_file.items():
            if count >= max_files:
                break
            rel_path = Path(file_path).relative_to(dir_path.parent)
            count += 1

            # 按行号排序
            lines_sorted = sorted(lines, key=lambda x: x["line"])

            # 遍历，用栈追踪当前 struct
            struct_stack = []  # [(struct_name, fields_list)]
            for line_info in lines_sorted:
                text = line_info["text"]
                # 去掉行首的 tab
                text_stripped = text.lstrip('\t')

                # 匹配 type XXX struct {
                m = re.search(r'type\s+(\w+)\s+struct\s*\{', text_stripped)
                if m:
                    struct_stack.append((m.group(1), []))
                    continue

                # 匹配结束括号（可能是单独的 } 或者 } 后面有空格）
                if text_stripped.strip() == '}' and struct_stack:
                    struct_stack.pop()
                    continue

                # 匹配字段行: FieldName Type `tag`
                if struct_stack:
                    # 跳过空行和注释
                    if not text_stripped or text_stripped.startswith('//'):
                        continue
                    # 匹配字段定义: 字段名 + 类型
                    # 支持带 tag: FieldName Type `tag`
                    field_m = re.match(r'(\w+)\s+(\S+?)(?:\s+`(.+?)`)?\s*$', text_stripped)
                    if field_m:
                        field_name = field_m.group(1)
                        # 跳过关键字
                        if field_name in ('type', 'func', 'var', 'const', 'return', 'if', 'for', 'switch', 'struct'):
                            continue
                        field_type = field_m.group(2).rstrip(',')
                        field = {"name": field_name, "type": field_type}
                        # 如果有 tag，保存
                        if field_m.group(3):
                            field["tag"] = field_m.group(3)
                        struct_stack[-1][1].append(field)

            # 将提取的字段写入 IR
            for struct_name, fields in struct_stack:
                # 先尝试找到匹配的 struct
                found = False
                for s in ir.structs:
                    if s.name == struct_name and s.file == str(rel_path):
                        s.fields = fields[:30]
                        found = True
                        break
                # 如果没有找到匹配的 struct，创建新的
                if not found:
                    ir.structs.append(StructDef(
                        name=struct_name,
                        file=str(rel_path),
                        fields=fields[:30],
                    ))

    def _parse_rg_table_names(self, output: str, ir: IRDocument):
        """从 rg 输出提取 TableName — 读取上下文行找 return "xxx" """
        by_file = self._parse_rg_json_lines(output)
        for file_path, lines in by_file.items():
            for i, line_info in enumerate(lines):
                text = line_info["text"]
                # 找 TableName 方法
                m = re.search(r'func\s+\(\s*\*(\w+)\)\s+TableName', text)
                if m:
                    struct_name = m.group(1)
                    # 查下一行是否有 return "table_name"
                    if i + 1 < len(lines):
                        next_text = lines[i + 1]["text"]
                        tn_match = re.search(r'return\s+"([^"]+)"', next_text)
                        if tn_match:
                            # 更新对应 struct
                            for s in ir.structs:
                                if s.name == struct_name:
                                    s.table_name = tn_match.group(1)
                                    break
    
    def _parse_rg_methods(self, output: str, ir: IRDocument, dir_path: Path, max_files: int):
        """从 rg 输出解析 method 签名"""
        by_file = self._parse_rg_json_lines(output)
        count = 0
        for file_path, lines in by_file.items():
            if count >= max_files:
                break
            rel_path = Path(file_path).relative_to(dir_path.parent)
            count += 1
            for line_info in lines:
                text = line_info["text"]
                m = self.METHOD_SIG_RE.search(text)
                if m:
                    receiver = m.group(1)
                    method_name = m.group(2)
                    params_str = m.group(3).strip()
                    return_type = m.group(4)
                    
                    # 跳过 TableName 等简单方法
                    if method_name in ('TableName', 'GetInternalSequenceName'):
                        continue
                    
                    ir.functions.append(FuncDef(
                        name=method_name,
                        file=str(rel_path),
                        params=self._parse_params(params_str),
                        returns=return_type,
                        is_route="Handler" in method_name,
                    ))
    
    def _parse_rg_top_funcs(self, output: str, ir: IRDocument, dir_path: Path, max_files: int):
        """从 rg 输出解析顶层函数"""
        by_file = self._parse_rg_json_lines(output)
        count = 0
        for file_path, lines in by_file.items():
            if count >= max_files:
                break
            rel_path = Path(file_path).relative_to(dir_path.parent)
            count += 1
            for line_info in lines:
                text = line_info["text"]
                m = self.TOP_FUNC_RE.search(text)
                if m:
                    func_name = m.group(1)
                    if func_name.startswith('Test'):
                        continue
                    ir.functions.append(FuncDef(
                        name=func_name,
                        file=str(rel_path),
                        params=self._parse_params(m.group(2)),
                        returns=m.group(3).strip() or None,
                    ))
    
    def _parse_rg_routes(self, output: str, ir: IRDocument, dir_path: Path, max_files: int):
        """从 rg 输出解析路由"""
        by_file = self._parse_rg_json_lines(output)
        count = 0
        for file_path, lines in by_file.items():
            if count >= max_files:
                break
            rel_path = Path(file_path).relative_to(dir_path.parent)
            count += 1
            for line_info in lines:
                text = line_info["text"]
                m = self.ROUTE_RE.search(text)
                if m:
                    method = m.group(1)
                    path = m.group(2)
                    handler = m.group(3).strip() if m.group(3) else ""
                    handler_name = ""
                    if handler:
                        parts = re.split(r'[,.]', handler)
                        handler_name = parts[-1].strip()
                    
                    ir.routes.append(RouteDef(
                        path=path,
                        method=method,
                        handler=handler_name,
                        module="",
                        file=str(rel_path),
                    ))
    
    def _parse_rg_imports(self, output: str, ir: IRDocument, dir_path: Path, max_files: int):
        """从 rg 输出解析 import — 匹配 import 路径，过滤 tag/注释"""
        by_file = self._parse_rg_json_lines(output)
        count = 0
        for file_path, lines in by_file.items():
            if count >= max_files:
                break
            rel_path = Path(file_path).relative_to(dir_path.parent)
            count += 1
            for line_info in lines:
                text = line_info["text"].strip()
                # 跳过注释
                if text.startswith('//'):
                    continue
                # 匹配 import "path"
                m = re.match(r'import\s+"([^"]+)"', text)
                if m:
                    ir.imports.append(ImportDef(
                        module=m.group(1),
                        is_local="git." in m.group(1) and "github.com" not in m.group(1),
                    ))
                    continue
                # 匹配 import 块内的路径： "path" 或 alias "path"
                # strip 后： "path" 或 alias "path"
                m = re.match(r'(?:(\w+)\s+)?"([^"]+)"', text)
                if m:
                    imp_path = m.group(2)
                    # import 路径特征：包含 / 且不是 tag（gorm/json/query 开头的值）
                    if '/' in imp_path:
                        ir.imports.append(ImportDef(
                            module=imp_path,
                            is_local="git." in imp_path and "github.com" not in imp_path,
                        ))
    
    def _parse_params(self, params_str: str) -> List[Dict[str, str]]:
        """解析函数参数列表"""
        params = []
        if not params_str or params_str.strip() == '':
            return params
        parts = []
        depth = 0
        current = []
        for ch in params_str:
            if ch in '<[{':
                depth += 1
                current.append(ch)
            elif ch in '>]}':
                depth -= 1
                current.append(ch)
            elif ch == ',' and depth == 0:
                parts.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            parts.append(''.join(current).strip())
        for part in parts:
            part = part.strip()
            if not part:
                continue
            tokens = part.split()
            if len(tokens) >= 2:
                params.append({"name": tokens[0], "type": ' '.join(tokens[1:])})
            elif len(tokens) == 1:
                params.append({"name": "", "type": tokens[0]})
        return params
    
    def scan_directory(self, dir_path: Path, max_files: int = 2000,
                       incremental: bool = False, changed_files: List[Path] = None) -> IRDocument:
        """扫描整个目录 — 使用 ripgrep 批量扫描（加速版）

        支持增量扫描：当 incremental=True 时，只扫描变更文件。
        changed_files 参数应包含自上次扫描以来变更的文件列表。
        """
        # 确保 dir_path 是 Path 对象
        if isinstance(dir_path, str):
            dir_path = Path(dir_path)

        # 使用 ripgrep 批量扫描（加速版）
        try:
            return self._scan_with_rgrep(dir_path, max_files)
        except Exception as e:
            print(f"  WARNING: ripgrep scan failed ({e}), fallback to Python re")
            return self._scan_with_python_re(dir_path, max_files, incremental, changed_files)
    
    def _scan_with_python_re(self, dir_path: Path, max_files: int,
                              incremental: bool = False, changed_files: List[Path] = None) -> IRDocument:
        """Fallback: 逐文件 Python re 扫描（原逻辑）"""
        ir = IRDocument(
            repo_name=dir_path.name,
            repo_path=str(dir_path),
            language="go",
        )
        count = 0
        go_files = sorted(dir_path.rglob("*.go"))
        for go_file in go_files:
            if count >= max_files:
                break
            if "vendor/" in str(go_file) or ".git/" in str(go_file):
                continue
            if incremental and changed_files is not None and go_file not in changed_files:
                continue
            try:
                content = go_file.read_text(encoding='utf-8', errors='replace')
            except Exception:
                continue
            count += 1
            rel_path = str(go_file.relative_to(dir_path.parent))
            
            # struct
            for sm in self.STRUCT_RE.finditer(content):
                struct_name = sm.group(1)
                body = sm.group(2)
                table_name = None
                tn = self.TABLE_NAME_RE.search(content)
                if tn:
                    table_name = tn.group(1)
                fields = []
                for line in body.strip().split('\n'):
                    line = line.strip()
                    if not line or line.startswith('//'):
                        continue
                    fm = self.FIELD_TYPE_RE.match(line)
                    if fm:
                        gorm = self.GORM_TAG_RE.findall(line)
                        json = self.JSON_TAG_RE.findall(line)
                        fields.append({"name": fm.group(1), "type": fm.group(2).strip(),
                                       "gorm_tag": gorm[0] if gorm else None, "json_tag": json[0] if json else None})
                ir.structs.append(StructDef(name=struct_name, file=rel_path, table_name=table_name, fields=fields[:30]))
            
            # func/method
            for fm in self.METHOD_SIG_RE.finditer(content):
                method_name = fm.group(2)
                if method_name in ('TableName', 'GetInternalSequenceName'):
                    continue
                ir.functions.append(FuncDef(name=method_name, file=rel_path,
                                            params=self._parse_params(fm.group(3).strip()),
                                            returns=fm.group(4), is_route="Handler" in method_name))
            
            for tm in self.TOP_FUNC_RE.finditer(content):
                func_name = tm.group(1)
                if func_name.startswith('Test'):
                    continue
                ir.functions.append(FuncDef(name=func_name, file=rel_path,
                                            params=self._parse_params(tm.group(2).strip()),
                                            returns=tm.group(3).strip() or None))
            
            # route
            for rm in self.ROUTE_RE.finditer(content):
                handler = ""
                if rm.group(3):
                    parts = re.split(r'[,.]', rm.group(3))
                    handler = parts[-1].strip()
                ir.routes.append(RouteDef(path=rm.group(2), method=rm.group(1), handler=handler,
                                          module="", file=rel_path))
            
            # import
            for im in self.SINGLE_IMPORT_RE.finditer(content):
                imp_path = im.group(1)
                ir.imports.append(ImportDef(module=imp_path, is_local="git." in imp_path and "github.com" not in imp_path))
        
        # 构建调用图（从 func 签名推断）
        self._extract_business_logic(ir, dir_path, max_entries=100)
        self._build_call_graph_from_signatures(ir)
        
        # 提取 API 文档（OpenAPI-like spec）
        self._extract_api_spec(ir, dir_path, max_files)
        
        # 提取权限/鉴权模型
        self._extract_auth_models(ir, dir_path, max_files)
        
        # 提取 SQL/GORM 操作
        self._extract_sql_operations(ir, dir_path, max_files)
        
        # 提取错误码定义
        self._extract_error_codes(ir, dir_path, max_files)
        
        # 提取 Entity/TableName 映射
        self._extract_entity_tables(ir, dir_path, max_files)
        
        # 提取 Condition 查询条件
        self._extract_conditions(ir, dir_path, max_files)
        
        # 提取配置
        self._extract_configs(ir, dir_path, max_files)
        
        
        # 检测性能热点
        self._detect_perf_hotspots(ir, dir_path, max_files)
        
        # 检测向后兼容问题
        self._detect_compat_issues(ir, dir_path, max_files)
        
        return ir
    
    def _extract_business_logic(self, ir: IRDocument, dir_path: Path, max_entries: int = 200):
        """从入口点（路由 handler）递归追踪调用链到 service/dao/外部 API
        
        借鉴 codebase-memory-mcp 的 pass_calls 方法：
        1. 从 handler 提取第一层调用
        2. 递归追踪到 service/dao 层
        3. 提取 SQL/外部 API 调用
        4. 生成完整调用树
        """
        # 快速检查：如果没有 *_module.go 文件，跳过
        module_files = list(dir_path.rglob("**/*_module.go"))
        if not module_files:
            module_files = list(dir_path.rglob("**/router.go")) + list(dir_path.rglob("**/handler.go"))
            if not module_files:
                print(f"  Skipping _extract_business_logic (no module/router/handler files)")
                return
        
        # 第一步：构建全局函数名 → 文件映射 + 方法体缓存
        # 只扫描已扫描的文件，不扫描整个项目
        all_go_files = list(dir_path.rglob("**/*.go"))[:100]  # 限制为少量文件
        func_to_files = {}
        func_bodies = {}  # (file, func_name) → body_text
        
        # DEBUG: 打印 func_to_file 的大小
        print(f"  Scanning {len(all_go_files)} Go files for function mapping...")
        
        for go_file in all_go_files[:max_entries * 20]:
            try:
                text = go_file.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            
            rel_path = str(go_file.relative_to(dir_path.parent))
            
            # 提取所有 func 定义
            # 修复：params 可能有嵌套括号，用更宽松的正则
            func_re = re.compile(r'func\s+(?:\((?:[^()]*|\([^()]*\))*\)\s+)?(\w+)\s*\(')
            for fm in func_re.finditer(text):
                func_name = fm.group(1)
                if func_name not in func_to_files:
                    func_to_files.setdefault(func_name, []).append(rel_path)
            
            # 提取方法体（用于递归追踪）
            method_re = re.compile(r'func\s+\(\s*(\w+)\s+\*?(\w+)\s*\)\s+(\w+)\s*\(')
            for mm in method_re.finditer(text):
                receiver_var = mm.group(1)
                receiver_type = mm.group(2)
                method_name = mm.group(3)
                start_pos = mm.end()
                
                # 找到方法体结束位置
                brace_count = 0
                method_body_start = None
                method_body_end = None
                
                for i, ch in enumerate(text[start_pos:]):
                    if ch == '{':
                        brace_count += 1
                        if method_body_start is None:
                            method_body_start = i + start_pos
                    elif ch == '}':
                        brace_count -= 1
                        if brace_count == 0 and method_body_start is not None:
                            method_body_end = i + start_pos + 1
                            break
                
                if method_body_start is not None and method_body_end is not None:
                    func_bodies[(rel_path, method_name)] = text[method_body_start:method_body_end]
            
            # 也提取包级别函数
            pkg_func_re = re.compile(r'^func\s+(\w+)\s*\(', re.MULTILINE)
            for pf in pkg_func_re.finditer(text):
                func_name = pf.group(1)
                start_pos = pf.end() - 1
                brace_count = 1
                method_body_start = start_pos + 1
                method_body_end = None
                
                for i, ch in enumerate(text[start_pos+1:]):
                    if ch == '{':
                        brace_count += 1
                    elif ch == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            method_body_end = start_pos + 1 + i
                            break
                
                if method_body_end is not None:
                    func_bodies[(rel_path, func_name)] = text[method_body_start:method_body_end]
        
        # 通用代码分析（不依赖 HTTP routes）
        print(f"  Performing universal code analysis...")
        
        # 提取包/模块结构
        packages = {}
        for go_file in all_go_files[:max_entries * 10]:
            try:
                text = go_file.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            
            rel_path = str(go_file.relative_to(dir_path.parent))
            
            # Go: package declaration (skip comments)
            lines = text.split('\n')
            pkg_line = ''
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('//') and not stripped.startswith('/*') and not stripped.startswith('*'):
                    pkg_line = stripped
                    break
            pkg_match = re.match(r'package\s+(\w+)', pkg_line)
            if pkg_match:
                pkg = pkg_match.group(1)
                if pkg not in packages:
                    packages[pkg] = {'files': [], 'imports': set(), 'exports': []}
                packages[pkg]['files'].append(rel_path)
                
                # 提取 import
                imports = re.findall(r'"([^"]+)"', text)
                packages[pkg]['imports'].update(imports)
                
                # 提取导出符号
                exports = re.findall(r'type\s+(\w+)|func\s+(\w+)', text)
                for exp in exports:
                    for name in exp:
                        if name and name[0].isupper():
                            packages[pkg]['exports'].append(name)
        
        print(f"  Extracted {len(packages)} packages")
        
        # 构建依赖关系
        dependencies = []
        for pkg, data in packages.items():
            for imp in data['imports']:
                dependencies.append({'from': pkg, 'to': imp, 'type': 'import'})
        
        # 保存到 IR
        ir.entry_points = list(packages.keys())[:20]  # 包作为入口点
        ir.call_graph = dependencies
        
        print(f"  Dependencies: {len(dependencies)}")
        
        # 第二步：扫描所有 *_module.go 文件，提取路由注册和 handler
        module_files = []
        for path in sorted(dir_path.rglob("**/*_module.go")):
            try:
                text = path.read_text(encoding='utf-8', errors='ignore')
                module_files.append((path, text))
            except Exception:
                continue
        
        # 第三步：从每个 module 文件提取路由和 handler，递归追踪调用链
        extracted = 0
        for module_path, module_text in module_files:
            if extracted >= max_entries:
                break
            
            rel_path = str(module_path.relative_to(dir_path.parent))
            
            # 提取路由注册
            route_pattern = re.compile(r'(?:group|groupPermission|r)\.(GET|POST|PUT|DELETE|PATCH)\s*\(\s*"([^"]+)"\s*,\s*(?:m\.)?(\w+)')
            route_matches = list(route_pattern.finditer(module_text))
            
            if not route_matches:
                continue
            
            # 提取模块结构体名
            struct_pattern = re.compile(r'type\s+(\w+Module)\s+struct')
            struct_match = struct_pattern.search(module_text)
            struct_name = struct_match.group(1) if struct_match else 'Module'
            
            for route_match in route_matches:
                if extracted >= max_entries:
                    break
                
                http_method = route_match.group(1)
                route_path = route_match.group(2)
                handler_name = route_match.group(3)
                
                # 提取 handler 方法体
                sig_pattern = re.compile(
                    rf'func\s+\(m\s+\*{re.escape(struct_name)}\)\s+{re.escape(handler_name)}\s*\('
                )
                sig_match = sig_pattern.search(module_text)
                
                if not sig_match:
                    continue
                
                start_pos = sig_match.end()
                brace_count = 0
                method_body_start = None
                method_body_end = None
                
                for i, ch in enumerate(module_text[start_pos:]):
                    if ch == '{':
                        brace_count += 1
                        if method_body_start is None:
                            method_body_start = i + start_pos
                    elif ch == '}':
                        brace_count -= 1
                        if brace_count == 0 and method_body_start:
                            method_body_end = i + start_pos
                            break
                
                if method_body_start is None or method_body_end is None:
                    continue
                
                handler_body = module_text[method_body_start:method_body_end]
                
                # 递归追踪调用链
                call_tree = self._trace_call_chain(
                    handler_body, func_to_files, func_bodies,
                    max_depth=3, visited=set(), depth=0
                )
                
                # 提取控制流
                handler_lines = handler_body.splitlines()[:100]
                control_points = []
                for line in handler_lines:
                    stripped = line.strip()
                    if any(stripped.startswith(kw) for kw in ['if ', 'else if', 'switch ', 'case ', 'for ', 'range ', 'return ']):
                        control_points.append(stripped[:150])
                
                
                # 提取数据流
                data_flow_keywords = ('bind', 'valid', 'request', 'req', 'dto', 'model', 
                                     'entity', 'dao', 'insert', 'save', 'update', 'delete', 
                                     'query', 'get', 'rpc', 'client', 'proxy', 'task', 
                                     'publish', 'callback')
                data_points = []
                for line in handler_lines:
                    lower = line.lower()
                    if any(kw in lower for kw in data_flow_keywords):
                        if ':=' in line or '=' in line or '.(' in line:
                            data_points.append(line.strip()[:150])
                
                # 增强：推断完整数据流路径（Request → Handler → Service → DAO → DB）
                data_flow = self._infer_data_flow(handler_body, call_tree)
                
                # 生成描述
                first_layer_calls = [c['name'] for c in call_tree[:10]]
                description = f"{handler_name} → [{', '.join(first_layer_calls[:5])}]"
                
                ir.business_logic.append({
                    "route": route_path,
                    "method": http_method,
                    "handler": handler_name,
                    "file": rel_path,
                    "call_tree": call_tree,  # 完整的递归调用树
                    "control_points": control_points[:8],
                    "data_points": data_points[:8],
                    "data_flow": data_flow,  # 增强：完整数据流路径
                    "description": description,
                })
                extracted += 1
        
        print(f"  Business logic extracted: {len(ir.business_logic)} entries from {extracted} routes")
    
    def _trace_call_chain(self, body: str, func_to_files: dict, func_bodies: dict,
                          max_depth: int = 3, visited: set = None, depth: int = 0) -> list:
        """递归追踪调用链
        
        Args:
            body: 函数体文本
            func_to_files: 函数名 → [文件] 映射
            func_bodies: (文件, 函数名) → 方法体映射
            max_depth: 最大递归深度
            visited: 已访问的函数名集合（避免循环）
            depth: 当前深度
        
        Returns:
            调用树: [{"name": "Foo", "file": "...", "calls": [...], "depth": 1}]
        """
        if visited is None:
            visited = set()
        
        
        excluded = {'if', 'for', 'switch', 'return', 'defer', 'go', 'select', 'make', 'new', 
                   'append', 'len', 'cap', 'close', 'copy', 'delete', 'panic', 'recover', 
                   'fmt', 'log', 'err', 'nil', 'string', 'int', 'bool', 'ctx', 'c', 'w', 'r',
                   'rsp', 'res', 'err', 'ok', 'done', 'cancel', 'Error', 'WithSuccess',
                   'WithError', 'NewContext', 'Reflect', 'User', 'Now', 'Unix', 'Int64', 'Int64s',
                   'AsInt64', 'LogE', 'LogI', 'ConstructResp', 'lockAdGroup', 'UnLockAdGroup',
                   'LockAdGroup'}
        
        # 提取当前层的调用
        calls = []
        for m in re.finditer(r'(?:m\.|ctx\.|util\.|dao\.|service\.|model\.|entity\.)(\w+)\s*\(', body):
            called = m.group(1)
            if called not in excluded and len(called) > 2 and called not in visited:
                calls.append(called)
        
        # 也提取不带前缀的调用
        for m in re.finditer(r'(?:(?:m|ctx|util|dao|service|model|entity)\.)?(\w+)\s*\(', body):
            called = m.group(1)
            if called not in excluded and len(called) > 2 and called not in calls:
                calls.append(called)
        
        result = []
        for call_name in sorted(set(calls))[:10]:  # 限制每层最多 10 个调用
            visited.add(call_name)
            
            # 找调用文件
            call_files = func_to_files.get(call_name, [])
            if not call_files:
                # 尝试在 func_bodies 里找
                for (f_name, fn), _body in func_bodies.items():
                    if fn == call_name:
                        call_files.append(f_name)
                        break
            
            call_entry = {
                "name": call_name,
                "file": call_files[0] if call_files else "",
                "calls": [],
                "depth": depth + 1,
            }
            
            # 递归追踪下一层
            if depth + 1 < max_depth and call_files:
                body_text = ""
                for cf in call_files:
                    bt = func_bodies.get((cf, call_name), "")
                    if bt:
                        body_text = bt
                        break
                if body_text:
                    sub_calls = self._trace_call_chain(
                        body_text, func_to_files, func_bodies,
                        max_depth=max_depth, visited=visited.copy(), depth=depth + 1
                    )
                    call_entry["calls"] = [c["name"] for c in sub_calls[:8]]
            
            result.append(call_entry)
        
        return result

    def _infer_core_business_flow(self, ir: IRDocument) -> List[Dict]:
        """从业务逻辑中自动推断核心业务流程
        
        增强策略：
        1. 从 business_logic 中提取调用链最深的 handler（通常是核心流程入口）
        2. 从 entry_points 提取非 HTTP 入口（CLI commands, cron jobs, background workers）
        3. 按调用深度排序，找到最长调用链
        4. 识别关键业务阶段（创建→审核→发布→上线）
        5. 提取数据流向（用户→API→Service→DAO→DB）
        6. 合并调用链相似的 flow（避免重复）
        """
        flows = []
        
        # 1. 从 HTTP routes 推断
        if ir.business_logic:
            for bl in ir.business_logic:
                call_tree = bl.get('call_tree', [])
                max_depth = self._calc_max_depth(call_tree)
                chain = self._flatten_call_chain(call_tree)
                flows.append({
                    "handler": bl.get('handler', ''),
                    "route": bl.get('route', ''),
                    "method": bl.get('method', ''),
                    "file": bl.get('file', ''),
                    "entry_type": "http",
                    "max_depth": max_depth,
                    "call_chain": chain[:15],
                    "data_points": bl.get('data_points', []),
                    "control_points": bl.get('control_points', []),
                    "data_flow": bl.get('data_flow', {}),
                })
        
        # 2. 从 entry_points 推断非 HTTP 入口
        if hasattr(ir, 'entry_points') and ir.entry_points:
            for ep in ir.entry_points[:20]:
                if isinstance(ep, str):
                    ep = {"name": ep}
                ep_name = ep.get('name', ep.get('package', ''))
                if not ep_name:
                    continue
                # 检查是否有对应的非 HTTP 入口（如 CLI command, main func, worker）
                files = ep.get('files', [])
                if not files and isinstance(ep.get('files', []), list):
                    files = ep['files']
                
                # 从 call_graph 推断入口点的下游调用
                downstream = []
                if hasattr(ir, 'call_graph') and ir.call_graph:
                    for edge in ir.call_graph:
                        if isinstance(edge, dict):
                            caller = edge.get('caller', edge.get('from', ''))
                            if caller == ep_name:
                                downstream.append(edge.get('callee', edge.get('to', '')))
                        elif hasattr(edge, 'caller'):
                            if edge.caller == ep_name:
                                downstream.append(edge.callee)
                
                if downstream:
                    flows.append({
                        "handler": ep_name,
                        "route": "",
                        "method": "",
                        "file": files[0] if files else "",
                        "entry_type": "entry_point",
                        "max_depth": 0,
                        "call_chain": downstream[:15],
                        "data_points": [],
                        "control_points": [],
                        "data_flow": {},
                    })
        
        # 3. 按深度排序，取 top 20
        flows.sort(key=lambda x: x['max_depth'], reverse=True)
        flows = flows[:20]
        
        # 4. 聚类合并（基于 route prefix + call chain similarity）
        grouped = self._cluster_business_flows(flows)
        
        # 5. 去重：合并调用链高度相似（Jaccard > 0.7）的 flow
        deduped = self._deduplicate_flows(grouped)
        
        return deduped

    def _infer_core_business_flow_v2(self, ir: IRDocument) -> List[Dict]:
        """增强版核心业务流程推断 — 多策略融合
        
        相比 _infer_core_business_flow 的改进：
        1. 从 IR 数据构建结构化输入（避免重复解析）
        2. 新增状态机流推断（从 status 字段 + 状态转换方法）
        3. 新增异步事件流推断（MQ publish/consume 配对）
        4. 新增 CRUD 流推断（从路由分组）
        5. 统一评分和排序（不再只按深度）
        6. 跨策略去重（同一业务入口可能被多种策略捕获）
        """
        # Import CoreFlowAnalyzer — use sys.path to avoid relative import issues
        analyzer_path = str(Path(__file__).parent / "core_flow_analyzer.py")
        spec = importlib.util.spec_from_file_location("core_flow_analyzer", analyzer_path)
        if spec and spec.loader:
            cfa_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cfa_module)
            CoreFlowAnalyzer = cfa_module.CoreFlowAnalyzer
        else:
            # Fallback: use the original method
            return self._infer_core_business_flow(ir)
        
        # Convert IRDocument to dict-friendly format for CoreFlowAnalyzer
        ir_dict = {
            'call_graph': [],
            'business_logic': [],
            'routes': [],
            'functions': [],
            'structs': [],
            'entity_tables': [],
            'core_flows': [],
            'services': [],
        }
        
        # Serialize call_graph
        for edge in getattr(ir, 'call_graph', []):
            if isinstance(edge, dict):
                ir_dict['call_graph'].append(edge)
            elif hasattr(edge, '__dict__'):
                ir_dict['call_graph'].append({
                    'caller': edge.caller,
                    'callee': edge.callee,
                    'caller_pkg': getattr(edge, 'caller_pkg', ''),
                    'callee_pkg': getattr(edge, 'callee_pkg', ''),
                })
        
        # Serialize business_logic
        for bl in getattr(ir, 'business_logic', []):
            if isinstance(bl, dict):
                ir_dict['business_logic'].append(bl)
        
        # Serialize routes
        for route in getattr(ir, 'routes', []):
            if isinstance(route, dict):
                ir_dict['routes'].append(route)
            elif hasattr(route, '__dict__'):
                ir_dict['routes'].append({
                    'path': route.path,
                    'method': route.method,
                    'handler': route.handler,
                    'file': route.file,
                })
        
        # Serialize functions
        for func in getattr(ir, 'functions', []):
            if isinstance(func, dict):
                ir_dict['functions'].append(func)
            elif hasattr(func, '__dict__'):
                ir_dict['functions'].append({
                    'name': func.name,
                    'file': func.file,
                    'params': getattr(func, 'params', []),
                    'returns': getattr(func, 'returns', None),
                })
        
        # Serialize structs
        for struct in getattr(ir, 'structs', []):
            if isinstance(struct, dict):
                ir_dict['structs'].append(struct)
            elif hasattr(struct, '__dict__'):
                ir_dict['structs'].append({
                    'name': struct.name,
                    'file': struct.file,
                    'fields': getattr(struct, 'fields', []),
                    'table_name': getattr(struct, 'table_name', None),
                })
        
        # Serialize entity_tables
        for et in getattr(ir, 'entity_tables', []):
            if isinstance(et, dict):
                ir_dict['entity_tables'].append(et)
        
        # Run enhanced analyzer — use analyze_all() for comprehensive flow data
        analyzer = CoreFlowAnalyzer(ir_dict)
        result = analyzer.analyze_all()
        
        # Add metadata from original IR
        for flow in result['flows']:
            flow['source'] = 'enhanced_analyzer'
        for path in result['critical_paths']:
            path['source'] = 'critical_path_analyzer'
        for df in result['data_flows']:
            df['source'] = 'data_flow_analyzer'
        
        # Add coverage metadata
        if 'flow_coverage' in result:
            for item in result['flow_coverage'].get('uncovered_entities', []):
                item['source'] = 'flow_coverage_analyzer'
        
        # Return combined data — flatten critical paths + data flows into core_flows
        # for backward compatibility with downstream engines
        # 增强：保留更多数据（critical_paths[:10] + data_flows[:20]），避免丢失关键流程
        all_flows = list(result['flows'])
        # Merge critical paths as high-priority flows (上限从5提升到10)
        for cp in result.get('critical_paths', [])[:10]:
            all_flows.append({
                'flow_name': cp.get('path_name', 'critical path'),
                'flow_type': 'critical_path',
                'entry_type': 'http',
                'entry_point': cp.get('entry_point', ''),
                'route': cp.get('route', ''),
                'call_chain': cp.get('call_chain', []),
                'stages': cp.get('stages', []),
                'is_golden_path': cp.get('is_golden_path', False),
                'domain': cp.get('cn_domain', ''),
                'confidence': cp.get('confidence', 0.5),
                'transition_count': cp.get('transition_count', 0),
                'entities': cp.get('entities', []),
                'matched_verbs': cp.get('matched_verbs', []),
                'score': cp.get('score', 0),
                'source': 'critical_path',
            })
        # Merge data flows — preserve full enriched fields (上限从10提升到20)
        for df in result.get('data_flows', [])[:20]:
            all_flows.append({
                'flow_name': df.get('flow_name', f"{df.get('route','')} 数据流"),
                'flow_type': 'data_flow',
                'entry_type': 'http',
                'entry_point': df.get('entry_point', ''),
                'route': df.get('route', ''),
                'http_method': df.get('http_method', ''),
                'call_chain': df.get('call_chain', df.get('dao_methods', [])),
                'stages': df.get('layers', []),
                'data_flow': ' → '.join(df.get('layers', [])),
                'entities': df.get('entities', []),
                'dao_methods': df.get('dao_methods', []),
                'cache_usage': df.get('cache_usage', []),
                'has_transaction': df.get('has_transaction', False),
                'depth': df.get('depth', 0),
                'score': df.get('score', 0),
                'source': 'data_flow',
            })
        
        # Sort by score descending so high-priority flows appear first
        all_flows.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        # ── Enhanced: integrate BusinessPathInference for lifecycle/workflow paths ──
        try:
            bpi_path = str(Path(__file__).parent / "business_path_inference.py")
            spec = importlib.util.spec_from_file_location("business_path_inference", bpi_path)
            if spec and spec.loader:
                bpi_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(bpi_module)
                bp_results = bpi_module.BusinessPathInference(ir_dict).infer_all()
                
                # Add lifecycle paths as high-priority flows
                for lp in bp_results.get('lifecycle_paths', [])[:5]:
                    all_flows.append({
                        'flow_name': f"{lp['entity']} 生命周期流程 ({', '.join(lp['present_actions'])})",
                        'flow_type': 'lifecycle',
                        'entry_point': lp['routes'][0]['handler'] if lp.get('routes') else '',
                        'route': lp['routes'][0]['path'] if lp.get('routes') else '',
                        'call_chain': lp['routes'][0]['handler'] if lp.get('routes') else '',
                        'stages': [r['action'] for r in lp.get('routes', [])],
                        'has_full_crud': lp.get('has_full_crud', False),
                        'missing_actions': lp.get('missing_actions', []),
                        'score': lp.get('score', 0) + 20,  # boost lifecycle paths
                        'source': 'business_path_inference',
                    })
                
                # Add approval workflows
                for wf in bp_results.get('approval_workflows', [])[:3]:
                    all_flows.append({
                        'flow_name': f"{wf['entity']} 审批工作流 ({', '.join(wf['steps'][:3])})",
                        'flow_type': 'approval_workflow',
                        'entry_point': wf['steps'][0].split(':')[1] if wf.get('steps') else '',
                        'call_chain': [s.split(': ')[-1] for s in wf.get('steps', [])],
                        'stages': wf.get('states', []),
                        'score': wf.get('score', 0) + 30,  # boost approval workflows
                        'source': 'business_path_inference',
                    })
                
                # ── Integrate importance ranking from BusinessPathInference ──
                # Merge top-5 importance ranking into all_flows as high-priority entries
                importance_ranking = bp_results.get('importance_ranking', [])
                for item in importance_ranking[:5]:
                    # Check if this flow_name already exists in all_flows (dedup)
                    existing_names = {f.get('flow_name', '') for f in all_flows}
                    if item['flow_name'] not in existing_names:
                        all_flows.append({
                            'flow_name': item['flow_name'],
                            'flow_type': item['flow_type'],
                            'entity': item.get('entity', ''),
                            'route_count': item.get('route_count', 0),
                            'has_full_crud': item.get('has_full_crud', False),
                            'importance_score': item['score'],
                            'traffic_score': item.get('traffic_score', 0),
                            'error_impact_score': item.get('error_impact_score', 0),
                            'business_value_score': item.get('business_value_score', 0),
                            'completeness_score': item.get('completeness_score', 0),
                            'importance_rank': item['rank'],
                            'score': item['score'] + 40,  # boost importance-ranked flows
                            'source': 'importance_ranking',
                        })
        
        except Exception:
            # business_path_inference is optional enhancement; don't break existing flow
            pass
        
        # Re-sort all_flows by the combined score (now includes importance ranking)
        all_flows.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return all_flows

    def build_core_flow_summary(self, ir: IRDocument, max_flows: int = 15) -> str:
        """Build a compact, actionable summary of core business flows for downstream engines.
        
        Unlike raw flow lists, this produces a structured text summary that:
        1. Groups flows by type (lifecycle/approval/data_flow/async/auth)
        2. Highlights critical paths with highest scores
        3. Identifies gaps (missing CRUD ops, incomplete workflows)
        4. Shows entity relationships and data ownership
        
        Returns a markdown-formatted string suitable for injection into prompts.
        """
        if not hasattr(ir, 'core_flows') or not ir.core_flows:
            return ""
        
        lines = []
        lines.append("## 核心业务流程摘要")
        lines.append("")
        
        # Group flows by type
        flow_groups = defaultdict(list)
        for flow in ir.core_flows[:max_flows]:
            if isinstance(flow, dict):
                ftype = flow.get('flow_type', 'unknown')
            else:
                ftype = getattr(flow, 'flow_type', 'unknown')
            flow_groups[ftype].append(flow)
        
        # Top entry points by score
        all_flows_sorted = sorted(
            [f for f in ir.core_flows if isinstance(f, dict)],
            key=lambda x: x.get('score', 0),
            reverse=True
        )[:max_flows]
        
        lines.append(f"**Top {len(all_flows_sorted)} 核心流程（按重要性排序）:**")
        lines.append("")
        
        for i, flow in enumerate(all_flows_sorted, 1):
            flow_name = flow.get('flow_name', 'Unknown')
            flow_type = flow.get('flow_type', '?')
            entry_point = flow.get('entry_point', '')
            route = flow.get('route', '')
            score = flow.get('score', 0)
            
            # Extract key info based on flow type
            extras = []
            if flow_type == 'lifecycle':
                missing = flow.get('missing_actions', [])
                if missing:
                    extras.append(f"缺失: {', '.join(missing)}")
                if flow.get('has_full_crud'):
                    extras.append("完整CRUD")
            elif flow_type == 'approval_workflow' or flow_type == 'multi_step_workflow':
                stages = flow.get('stages', [])
                if stages:
                    extras.append(f"阶段: {' → '.join(stages[:5])}")
            elif flow_type == 'data_flow':
                data_flow_str = flow.get('data_flow', '')
                if data_flow_str:
                    extras.append(f"数据流: {data_flow_str[:100]}")
            
            extra_str = f" ({', '.join(extras)})" if extras else ""
            route_str = f" @{route}" if route else ""
            
            lines.append(f"{i}. **{flow_name}** [type={flow_type}] score={score:.0f}{extra_str}{route_str}")
            if entry_point:
                lines.append(f"   - Entry: `{entry_point}`")
        
        lines.append("")
        
        # Entity relationships summary
        if hasattr(ir, 'entity_tables') and ir.entity_tables:
            entity_count = len(ir.entity_tables) if isinstance(ir.entity_tables, list) else 0
            if entity_count > 0:
                lines.append(f"**实体表 ({entity_count}个):**")
                for et in ir.entity_tables[:10]:
                    if isinstance(et, dict):
                        name = et.get('name', '?')
                        fields = et.get('fields', [])
                        n_fields = len(fields) if isinstance(fields, list) else 0
                        fks = et.get('foreign_keys', [])
                        fk_info = f" +{len(fks)}FK" if fks else ""
                        lines.append(f"- `{name}`: {n_fields} fields{fk_info}")
                    elif hasattr(et, 'name'):
                        lines.append(f"- `{et.name}`")
                lines.append("")
        
        # Service layer summary
        if hasattr(ir, 'services') and ir.services:
            svc_list = ir.services if isinstance(ir.services, list) else []
            if svc_list:
                lines.append(f"**服务模块 ({len(svc_list)}个):**")
                for svc in svc_list[:8]:
                    if isinstance(svc, dict):
                        lines.append(f"- {svc.get('name', svc.get('module', '?'))}")
                    elif hasattr(svc, 'name'):
                        lines.append(f"- {svc.name}")
                lines.append("")
        
        # Gap analysis
        lifecycle_flows = [f for f in all_flows_sorted 
                          if isinstance(f, dict) and f.get('flow_type') == 'lifecycle']
        for lf in lifecycle_flows[:5]:
            missing = lf.get('missing_actions', [])
            if missing:
                entity = lf.get('flow_name', '').split()[0] if lf.get('flow_name') else '?'
                lines.append(f"⚠️ **{entity} 生命周期不完整**: 缺少 {', '.join(missing)}")
        
        # Async/event flow detection
        async_flows = [f for f in all_flows_sorted 
                      if isinstance(f, dict) and f.get('flow_type') in ('async', 'event', 'mq')]
        if async_flows:
            lines.append("**异步事件流:**")
            for af in async_flows[:5]:
                name = af.get('flow_name', '?')
                stages = af.get('stages', [])
                stage_str = ' → '.join(stages[:4]) if stages else ''
                lines.append(f"- {name}: {stage_str}")
            lines.append("")
        
        # Auth flow analysis
        auth_flows = [f for f in all_flows_sorted 
                     if isinstance(f, dict) and f.get('flow_type') == 'auth']
        if auth_flows:
            lines.append("**认证授权流:**")
            for af in auth_flows[:5]:
                name = af.get('flow_name', '?')
                route = af.get('route', '')
                lines.append(f"- {name}" + (f" @{route}" if route else ""))
            lines.append("")
        
        # Data ownership mapping — which service/module owns which entity
        lines.append("**数据所有权映射:**")
        entity_service_map = self._map_entity_ownership(ir)
        for entity_name, owners in sorted(entity_service_map.items())[:10]:
            owner_str = ', '.join(owners[:3])
            lines.append(f"- `{entity_name}` → [{owner_str}]")
        if not entity_service_map:
            lines.append("- 未检测到明确的数据所有权映射")
        lines.append("")
        
        # CRUD gap analysis — detect entities with incomplete CRUD operations
        crud_gaps = self._analyze_crud_gaps(ir)
        if crud_gaps:
            lines.append("**CRUD 完整性分析:**")
            for gap in crud_gaps[:8]:
                entity = gap.get('entity', '?')
                present = gap.get('present', [])
                missing = gap.get('missing', [])
                if missing:
                    lines.append(f"- ⚠️ **{entity}**: 有 [{', '.join(present)}], 缺 {', '.join(missing)}")
                else:
                    lines.append(f"- ✅ **{entity}**: 完整 CRUD ({', '.join(present)})")
            lines.append("")
        
        # Layer completeness scoring per flow
        lines.append("**架构层完整性检查:**")
        layer_issues = []
        for flow in all_flows_sorted[:8]:
            if not isinstance(flow, dict):
                continue
            call_chain = flow.get('call_chain', [])
            if not call_chain or len(str(call_chain)) < 10:
                continue
            chain_str = str(call_chain)
            has_handler = any(kw in chain_str.lower() for kw in ['handler', 'handle', 'controller', 'api'])
            has_service = any(kw in chain_str.lower() for kw in ['service', 'biz', 'logic'])
            has_dao = any(kw in chain_str.lower() for kw in ['dao', 'repo', 'model', 'dal'])
            layers = sum([has_handler, has_service, has_dao])
            flow_name = flow.get('flow_name', '?')
            if layers <= 1:
                layer_issues.append(f"- ⚠️ **{flow_name}**: 仅 {layers} 层 ({'handler' if has_handler else ''}{'service' if has_service else ''}{'dao' if has_dao else ''})")
            elif layers == 2:
                missing_layer = []
                if not has_handler: missing_layer.append('Handler')
                if not has_service: missing_layer.append('Service')
                if not has_dao: missing_layer.append('DAO')
                layer_issues.append(f"- ℹ️ **{flow_name}**: 缺 {', '.join(missing_layer)}")
        if layer_issues:
            lines.extend(layer_issues[:5])
        else:
            lines.append("- 所有核心流程层完整性良好")
        lines.append("")
        
        # Cross-cutting concerns detection
        lines.append("**横切关注点检测:**")
        crossec = self._detect_cross_cutting_concerns(ir)
        if crossec:
            for concern in crossec[:6]:
                icon = "✅" if concern.get('present', True) else "⚠️"
                lines.append(f"- {icon} **{concern['name']}**: {concern['status']}")
        else:
            lines.append("- 未检测到横切关注点信息")
        lines.append("")
        
        if lines[-1] != "":
            lines.append("")
        
        return "\n".join(lines)

    def _detect_cross_cutting_concerns(self, ir: IRDocument) -> List[Dict]:
        """Detect cross-cutting concerns in the codebase.
        
        Checks for: auth middleware, rate limiting, retry/circuit-breaker,
        structured logging, metrics/prometheus, transaction management,
        idempotency handling, audit logging, error handling patterns.
        """
        concerns = []
        
        # Collect all source text for pattern matching
        all_text = ""
        for struct in getattr(ir, 'structs', []) or []:
            if isinstance(struct, dict):
                all_text += json.dumps(struct) + "\n"
        for func in getattr(ir, 'functions', []) or []:
            if isinstance(func, dict):
                all_text += json.dumps(func) + "\n"
        for route in getattr(ir, 'routes', []) or []:
            if isinstance(route, dict):
                all_text += json.dumps(route) + "\n"
        for svc in getattr(ir, 'services', []) or []:
            if isinstance(svc, dict):
                all_text += json.dumps(svc) + "\n"
        for cfg in getattr(ir, 'configs', []) or []:
            if isinstance(cfg, dict):
                all_text += json.dumps(cfg) + "\n"
        
        text_lower = all_text.lower()
        
        # 1. Auth/Middleware detection
        auth_patterns = ['auth', 'middleware', 'permission', 'rbac', 'abac', 'jwt', 'oauth', 'token', '鉴权']
        has_auth = any(p in text_lower for p in auth_patterns)
        concerns.append({
            'name': '认证/授权中间件',
            'present': has_auth,
            'status': '已实现' if has_auth else '未检测到，建议添加统一鉴权中间件',
        })
        
        # 2. Rate limiting
        rate_patterns = ['rate_limit', 'rate-limit', 'ratelimit', '限流', 'throttle', 'limiter']
        has_rate_limit = any(p in text_lower for p in rate_patterns)
        concerns.append({
            'name': '限流保护',
            'present': has_rate_limit,
            'status': '已实现' if has_rate_limit else '未检测到限流配置，建议对高频接口添加限流',
        })
        
        # 3. Retry/Circuit-breaker
        retry_patterns = ['retry', '重试', 'circuit_breaker', 'circuit-breaker', '熔断', 'fallback', '降级']
        has_retry = any(p in text_lower for p in retry_patterns)
        concerns.append({
            'name': '重试/熔断/降级',
            'present': has_retry,
            'status': '已实现' if has_retry else '未检测到重试/熔断机制，外部依赖调用建议添加',
        })
        
        # 4. Structured logging
        log_patterns = ['zap.', 'logrus', 'slog.', 'logger.', 'structured.log', 'traceId', 'trace_id', 'userId', 'user_id']
        has_logging = any(p in text_lower for p in log_patterns)
        concerns.append({
            'name': '结构化日志',
            'present': has_logging,
            'status': '已实现' if has_logging else '未检测到结构化日志，建议使用 zap/logrus + traceId',
        })
        
        # 5. Metrics/Prometheus
        metric_patterns = ['prometheus', 'prometheus_client', 'metrics.', 'histogram', 'counter', 'gauge', '监控指标']
        has_metrics = any(p in text_lower for p in metric_patterns)
        concerns.append({
            'name': 'Prometheus 监控指标',
            'present': has_metrics,
            'status': '已实现' if has_metrics else '未检测到监控指标，建议添加 QPS/延迟/错误率指标',
        })
        
        # 6. Transaction management
        tx_patterns = ['transaction', 'Transaction', 'tx.', 'BeginTx', 'Commit', 'Rollback', '事务']
        has_tx = any(p in text_lower for p in tx_patterns)
        concerns.append({
            'name': '事务管理',
            'present': has_tx,
            'status': '已实现' if has_tx else '未检测到事务处理，写操作建议包裹在事务中',
        })
        
        # 7. Idempotency
        idem_patterns = ['idempoten', '幂等', 'idempotency_key', 'request_id', 'unique_key', '去重']
        has_idem = any(p in text_lower for p in idem_patterns)
        concerns.append({
            'name': '幂等性保障',
            'present': has_idem,
            'status': '已实现' if has_idem else '未检测到幂等性处理，写操作建议添加幂等键',
        })
        
        # 8. Health check endpoints
        health_patterns = ['/health', '/ready', 'health_check', 'HealthCheck', 'liveness']
        has_health = any(p in text_lower for p in health_patterns)
        concerns.append({
            'name': '健康检查端点',
            'present': has_health,
            'status': '已实现' if has_health else '未检测到 /health 或 /ready 端点，K8s 部署必须提供',
        })
        
        return concerns
    
    def _map_entity_ownership(self, ir: IRDocument) -> Dict[str, List[str]]:
        """Map entities to their owning services/modules based on call_graph + package structure.
        
        Heuristics:
        - If a struct's table_name matches an entity, the DAO package that queries it owns it
        - If a service method creates/updates an entity, that service owns it
        - Route path prefix indicates which module handles the entity
        """
        ownership: Dict[str, List[str]] = defaultdict(list)
        
        # Strategy 1: From entity_tables foreign_keys → find related entities
        if hasattr(ir, 'entity_tables') and ir.entity_tables:
            et_list = ir.entity_tables if isinstance(ir.entity_tables, list) else []
            for et in et_list[:30]:
                name = et.get('name', '') if isinstance(et, dict) else getattr(et, 'name', '')
                if not name:
                    continue
                fks = et.get('foreign_keys', []) if isinstance(et, dict) else getattr(et, 'foreign_keys', [])
                if fks:
                    for fk in (fks if isinstance(fks, list) else []):
                        if isinstance(fk, dict) and 'ref_entity' in fk:
                            ref = fk['ref_entity']
                            if ref not in ownership[name]:
                                ownership[name].append(ref)
        
        # Strategy 2: From call_graph — find which services touch which entities
        # (already captured via Strategy 1 FK analysis + Strategy 3 route analysis)
        
        # Strategy 3: From routes — map route prefix to entity
        if hasattr(ir, 'routes') and ir.routes:
            routes = ir.routes if isinstance(ir.routes, list) else []
            for route in routes[:50]:
                if not isinstance(route, dict):
                    continue
                path = route.get('path', '')
                handler = route.get('handler', '')
                # Extract entity from route path like /api/v1/adgroups/{id}
                parts = path.strip('/').split('/')
                for part in parts:
                    if part.startswith('{'):
                        continue
                    # Check if this looks like an entity name
                    if len(part) > 2 and any(kw in part.lower() for kw in ['adgroup', 'creative', 'campaign', 'report', 'user', 'account', 'bid', 'budget']):
                        owner = handler.split('.')[0] if '.' in handler else handler
                        if owner not in ownership.get(part, []):
                            ownership.setdefault(part, []).append(owner)
        
        # Convert defaultdict to regular dict, ensure lists
        result = {}
        for k, v in ownership.items():
            result[k] = list(dict.fromkeys(v))[:3]  # deduplicate, keep top 3
        return result

    def _analyze_crud_gaps(self, ir: IRDocument) -> List[Dict]:
        """Analyze CRUD completeness for each entity detected in routes.
        
        Groups routes by resource/entity, checks which CRUD operations exist,
        and reports gaps. This is a lightweight version of lifecycle_paths
        that runs directly on IR without needing business_path_inference.
        
        Returns list of {entity, present, missing, route_count} dicts.
        """
        gaps = []
        
        # Group routes by entity
        entity_routes: Dict[str, List[dict]] = defaultdict(list)
        routes = getattr(ir, 'routes', []) or []
        if isinstance(routes, list):
            for route in routes:
                if not isinstance(route, dict):
                    continue
                path = route.get('path', '')
                method = route.get('method', 'GET')
                handler = route.get('handler', '')
                
                # Extract entity from path
                parts = path.strip('/').split('/')
                # Skip version segments
                entity = None
                for part in reversed(parts):
                    if part.startswith('{'):
                        continue
                    if part.isdigit() or part.startswith('v'):
                        continue
                    if len(part) > 1:
                        entity = part
                        break
                
                if not entity:
                    continue
                
                action_map = {
                    'POST': 'create', 'PUT': 'update', 'PATCH': 'update',
                    'DELETE': 'delete', 'GET': 'read',
                }
                action = action_map.get(method, 'unknown')
                entity_routes[entity].append({
                    'path': path,
                    'method': method,
                    'handler': handler,
                    'action': action,
                })
        
        # Analyze each entity
        for entity, routes_list in sorted(entity_routes.items()):
            actions = set(r['action'] for r in routes_list)
            action_labels = {
                'create': '创建', 'read': '查询', 'update': '更新', 'delete': '删除',
            }
            present = [action_labels.get(a, a) for a in sorted(actions) if a != 'unknown']
            missing = [action_labels.get(a, a) for a in ['create', 'read', 'update', 'delete'] if a not in actions]
            
            gaps.append({
                'entity': entity,
                'present': present,
                'missing': missing,
                'route_count': len(routes_list),
                'has_full_crud': set(['create', 'read', 'update', 'delete']).issubset(actions),
            })
        
        # Sort: incomplete first (gaps are more important), then by route count
        gaps.sort(key=lambda x: (0 if x['missing'] else 1, -x['route_count']))
        return gaps

    def _calc_max_depth(self, call_tree: list, current: int = 0) -> int:
        if not call_tree:
            return current
        max_d = current
        for entry in call_tree:
            d = self._calc_max_depth(entry.get('calls', []), current + 1)
            max_d = max(max_d, d)
        return max_d
    
    def _flatten_call_chain(self, call_tree: list, chain: list = None) -> list:
        if chain is None:
            chain = []
        for entry in call_tree:
            name = entry.get('name', '')
            if name and name not in chain:
                chain.append(name)
            self._flatten_call_chain(entry.get('calls', []), chain)
        return chain
    
    def _cluster_business_flows(self, flows: list) -> List[Dict]:
        """聚类业务流 — 基于 route prefix + entry_type
        
        增强：
        - 对 entry_point 类型的 flow 单独分组（CLI/command/worker）
        - 对 HTTP flow 按 route prefix 聚类
        - 合并同一 cluster 中的 handler 和 data_flow
        """
        clusters = defaultdict(list)
        for f in flows:
            entry_type = f.get('entry_type', 'http')
            route = f.get('route', '')
            handler = f.get('handler', '')
            
            if entry_type == 'entry_point':
                # entry_point 类型：用 handler name 作为 key
                key = f"__entry_point__/{handler}"
            elif route:
                parts = route.rstrip('/').split('/')
                prefix = '/'.join(parts[:3]) if len(parts) >= 3 else route
                key = f"http/{prefix}"
            else:
                # fallback: 用 handler 名
                key = f"http/__unknown__/{handler}"
            
            clusters[key].append(f)
        
        result = []
        for key, group in clusters.items():
            group.sort(key=lambda x: x['max_depth'], reverse=True)
            top = group[0]
            
            # 推断 flow name
            if key.startswith('__entry_point__'):
                flow_name = f"{top['handler']} 入口"
            else:
                route_prefix = key.split('/', 2)[-1] if '/' in key else key
                flow_name = self._infer_flow_name(route_prefix, top)
            
            # 合并 call_chain
            all_chains = []
            for g in group:
                all_chains.extend(g['call_chain'])
            all_chains = list(dict.fromkeys(all_chains))[:30]
            
            # 合并 data_flow（从 data_flow dict 中提取）
            data_flow_parts = []
            for g in group:
                df = g.get('data_flow', {})
                if isinstance(df, dict) and df.get('stages'):
                    data_flow_parts = df['stages']
                    break
            if not data_flow_parts:
                for dp in top.get('data_points', [])[:5]:
                    if any(kw in dp.lower() for kw in ['dao.', 'db.', 'insert', 'update', 'query']):
                        if 'DB' not in data_flow_parts:
                            data_flow_parts.append('DB')
                    elif any(kw in dp.lower() for kw in ['service.', 'create', 'build']):
                        if 'Service' not in data_flow_parts:
                            data_flow_parts.append('Service')
                    elif any(kw in dp.lower() for kw in ['req', 'bind', 'valid']):
                        if 'Request' not in data_flow_parts:
                            data_flow_parts.append('Request')
            if not data_flow_parts:
                data_flow_parts = ['Request', 'Handler', 'Service', 'DAO', 'DB']
            
            # 收集所有 entry_types
            entry_types = set()
            for g in group:
                entry_types.add(g.get('entry_type', 'http'))
            
            result.append({
                "flow_name": flow_name,
                "route_prefix": key.split('/', 2)[-1] if '/' in key else key,
                "handlers": list(dict.fromkeys(g['handler'] for g in group))[:10],
                "entry_point": top['handler'],
                "call_chain": all_chains,
                "data_flow": " → ".join(data_flow_parts),
                "max_depth": top['max_depth'],
                "stage_count": len(group),
                "entry_types": ", ".join(sorted(entry_types)),
            })
        return result
    
    def _infer_flow_name(self, route_prefix: str, flow: dict) -> str:
        handler = flow.get('handler', '').lower()
        route = flow.get('route', '').lower()
        verb_map = {
            'create': '创建', 'add': '新增', 'insert': '插入',
            'update': '更新', 'edit': '编辑', 'modify': '修改',
            'delete': '删除', 'remove': '移除',
            'get': '查询', 'list': '列表', 'search': '搜索', 'query': '检索',
            'approve': '审核', 'review': '复核', 'audit': '审计',
            'publish': '发布', 'release': '上线', 'submit': '提交',
            'pause': '暂停', 'resume': '恢复', 'activate': '激活',
            'share': '分享', 'export': '导出', 'import': '导入',
            'sync': '同步', 'refresh': '刷新',
        }
        for eng, cn in verb_map.items():
            if eng in handler or eng in route:
                return f"{cn}流程"
        return f"业务流 ({route_prefix})"
    
    def _deduplicate_flows(self, flows: List[Dict]) -> List[Dict]:
        """去重：合并调用链高度相似的 flow（Jaccard 相似度 > 0.7）
        
        避免同一个业务流被拆成多个相似条目。
        """
        if len(flows) <= 1:
            return flows
        
        result = []
        used = [False] * len(flows)
        
        for i, flow_i in enumerate(flows):
            if used[i]:
                continue
            
            # 以 flow_i 为基础，合并所有高度相似的
            merged = {
                "flow_name": flow_i["flow_name"],
                "route_prefix": flow_i["route_prefix"],
                "handlers": list(flow_i["handlers"]),
                "entry_point": flow_i["entry_point"],
                "call_chain": list(flow_i["call_chain"]),
                "data_flow": flow_i["data_flow"],
                "max_depth": flow_i["max_depth"],
                "stage_count": flow_i["stage_count"],
                "entry_types": {flow_i.get("entry_type", "http")},
            }
            
            chain_i = set(flow_i["call_chain"])
            used[i] = True
            
            for j in range(i + 1, len(flows)):
                if used[j]:
                    continue
                flow_j = flows[j]
                chain_j = set(flow_j["call_chain"])
                
                # Jaccard 相似度
                intersection = chain_i & chain_j
                union = chain_i | chain_j
                if not union:
                    continue
                jaccard = len(intersection) / len(union)
                
                if jaccard > 0.7:
                    # 合并
                    merged["handlers"].extend(flow_j["handlers"])
                    merged["handlers"] = list(dict.fromkeys(merged["handlers"]))[:20]
                    merged["call_chain"].extend(flow_j["call_chain"])
                    merged["call_chain"] = list(dict.fromkeys(merged["call_chain"]))[:30]
                    merged["entry_types"].add(flow_j.get("entry_type", "http"))
                    merged["max_depth"] = max(merged["max_depth"], flow_j["max_depth"])
                    merged["stage_count"] += flow_j["stage_count"]
                    used[j] = True
            
            merged["entry_types"] = ", ".join(sorted(merged["entry_types"]))
            merged["handlers"] = merged["handlers"][:10]
            result.append(merged)
        
        return result
    
    def _infer_data_flow(self, handler_body: str, call_tree: list) -> Dict:
        """从 handler 代码推断完整数据流路径
        
        策略：
        1. 识别请求来源（gin.Context / Request struct / URL params）
        2. 追踪变量传递（req → service → dao → db）
        3. 识别外部调用（RPC / HTTP / MQ）
        4. 识别数据落点（Insert / Update / Query / Delete）
        
        Returns:
            {
                "stages": ["Request", "Handler", "Service", "DAO", "DB"],
                "request_source": "gin.Context",
                "data_ops": ["insert", "update"],
                "external_calls": ["adp_rpc"],
                "full_path": "Request → Handler → AdGroupService → AdGroupDAO → Insert → MySQL",
            }
        """
        
        stages = []
        data_ops = []
        external_calls = []
        request_source = ""
        
        # 1. 识别请求来源
        if 'gin.Context' in handler_body or 'c.Bind' in handler_body:
            request_source = "gin.Context (HTTP Request)"
            stages.append("Request")
        elif 'request.Request' in handler_body or 'req *' in handler_body:
            request_source = "RPC Request"
            stages.append("Request")
        else:
            stages.append("Request")
            request_source = "HTTP Request"
        
        # 2. 识别 Handler 层
        stages.append("Handler")
        
        # 3. 识别 Service 层调用
        service_calls = re.findall(r'(?:m\.|\.)(\w+Service)\s*\(', handler_body)
        service_calls += re.findall(r'(\w+Service)\.(Create|Update|Delete|Get|List|Query|Build)', handler_body)
        if service_calls:
            stages.append("Service")
            for svc in set(service_calls):
                if isinstance(svc, tuple):
                    svc = svc[0]
                svc_methods = re.findall(rf'{svc}\.(Create|Update|Delete|Get|List|Query|Build|Validate)', handler_body)
                if svc_methods:
                    data_ops.extend(svc_methods)
        
        # 4. 识别 DAO 层调用
        dao_calls = re.findall(r'(?:dao\.|\.)(\w+DAO)\s*\(', handler_body)
        dao_methods = re.findall(r'DAO\.(Insert|Update|Delete|Get|List|Query|Count|Exists)', handler_body)
        if dao_calls or dao_methods:
            stages.append("DAO")
            for m in dao_methods:
                data_ops.append(m.lower())
        
        # 5. 识别直接 DB 操作
        db_ops = re.findall(r'\.(Insert|Update|Delete|Query|Get|List|Count|Exec|Scan)\s*\(', handler_body)
        for op in db_ops:
            if op not in data_ops:
                data_ops.append(op.lower())
        
        # 6. 识别外部 RPC/HTTP/MQ 调用
        rpc_calls = re.findall(r'(?:client|rpc|proxy|external)\.(\w+)', handler_body)
        mq_calls = re.findall(r'(?:mq|kafka|rabbit|pubsub|publish)\.\w+', handler_body)
        
        if rpc_calls:
            external_calls.extend([f"RPC:{c}" for c in set(rpc_calls)])
        if mq_calls:
            external_calls.extend([f"MQ:{c}" for c in set(mq_calls)])
        
        # 7. 构建完整路径
        if "DB" not in stages and ("DAO" in stages or data_ops):
            stages.append("DB")
        full_path = " → ".join(stages)
        if external_calls:
            full_path += f" [+{', '.join(external_calls[:3])}]"
        
        return {
            "stages": stages,
            "request_source": request_source,
            "data_ops": list(set(data_ops)),
            "external_calls": external_calls[:5],
            "full_path": full_path,
        }

    def _scan_test_files(self, ir: IRDocument, dir_path: Path, max_files: int):
        # 1. 找测试文件（用 find 命令，rg --files-with-matches 搜的是文件内容不是文件名）
        try:
            r = subprocess.run(
                ["find", str(dir_path), "-name", "*_test.go", "-not", "-path", "*/vendor/*"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                test_files = [f.strip() for f in r.stdout.strip().split('\n') if f.strip()]
                ir.test_files = test_files[:max_files]
        except Exception:
            pass
        
        # 2. 扫描测试函数 — 直接读测试文件（不依赖 rg，沙箱里 rg 不可用）
        framework = "unknown"
        
        # 先检测测试框架
        for tf in ir.test_files[:5]:
            full = dir_path / tf if isinstance(dir_path, Path) else Path(tf)
            if full.exists():
                try:
                    content = full.read_text()
                    if "goconvey" in content or "convey" in content:
                        framework = "goconvey"
                    elif "testify" in content:
                        framework = "testify"
                    elif "stretchr" in content:
                        framework = "stretchr"
                    break
                except Exception:
                    pass
        
        # 逐个测试文件扫描测试函数
        for tf in ir.test_files:
            if len(ir.test_functions) >= max_files * 5:
                break
            full = dir_path / tf if isinstance(dir_path, Path) else Path(tf)
            if not full.exists():
                continue
            try:
                content = full.read_text()
                # 相对路径：去掉 dir_path 前缀
                try:
                    rel = full.relative_to(dir_path.parent)
                except ValueError:
                    rel = full
                
                for i, line in enumerate(content.splitlines(), 1):
                    m = re.search(r'func\s+(Test\w+)\s*\(', line)
                    if m:
                        ir.test_functions.append({
                            "name": m.group(1),
                            "file": str(rel),
                            "line": i,
                            "framework": framework,
                            "covers": [],
                        })
            except Exception:
                pass
        
        # 3. 构建覆盖率报告
        all_func_names = set(f.name for f in ir.functions)
        tested_funcs = set()
        
        # 从测试文件中的 import 和 mock 推断被测函数
        for test_func in ir.test_functions:
            test_file = test_func["file"]
            full_path = dir_path / test_file if isinstance(dir_path, Path) else Path(test_file)
            if full_path.exists():
                try:
                    content = full_path.read_text()
                    # 找 TestXxx 中的被测方法调用
                    # 模式: obj.MethodName( 或 dao.MethodName( 或 req.MethodName(
                    calls = re.findall(r'(?:\w+\.)?(\w+)\s*\(', content)
                    for call in calls:
                        if call.startswith('Get') or call.startswith('Create') or call.startswith('Update') or call.startswith('Delete') or call.startswith('List') or call.startswith('Query') or call.startswith('Parse'):
                            tested_funcs.add(call)
                except Exception:
                    pass
        
        # 简单估算：测试文件中的 TestXxx 对应 Xxx 方法的测试
        for tf in ir.test_functions:
            # TestCreativeModel_GetCreativeShareName -> GetCreativeShareName
            test_name = tf["name"]
            if test_name.startswith("Test"):
                # 尝试提取被测方法名
                parts = test_name[4:].split("_")
                if len(parts) >= 2:
                    method_name = "_".join(parts[1:])
                    tested_funcs.add(method_name)
        
        total = len(all_func_names)
        tested = len(tested_funcs.intersection(all_func_names))
        
        ir.coverage_report = {
            "test_files": len(ir.test_files),
            "test_functions": len(ir.test_functions),
            "total_functions": total,
            "tested_functions": tested,
            "coverage_pct": round(tested / total * 100, 1) if total > 0 else 0,
            "framework": framework,
            "uncovered_highlights": list(all_func_names - tested_funcs)[:20],
        }


    def _extract_api_spec(self, ir: IRDocument, dir_path: Path, max_files: int):
        """从路由注册行提取 API 文档 — OpenAPI-like spec
        
        策略：
        1. 从 route.handler 提取方法名（去掉括号、receiver）
        2. 在路由文件中搜索该方法的实现
        3. 从方法签名提取 Request/Response struct
        4. 从方法体提取 return 语句中的 Response struct
        5. 从文件顶部提取 middleware 引用
        """
        # 先收集所有路由文件中的 handler 方法名 -> 文件映射
        route_by_file = {}
        for route in ir.routes:
            route_by_file.setdefault(route.file, []).append(route)
        
        for filepath, routes in route_by_file.items():
            # 去掉 filepath 中的 repo 名前缀（如 "creative-platform/app/..." -> "app/..."）
            parts = filepath.split('/')
            clean_filepath = filepath
            if parts and parts[0] == dir_path.name:
                clean_filepath = '/'.join(parts[1:])
            
            full_path = dir_path / clean_filepath
            if not full_path.exists():
                continue
            
            try:
                content = full_path.read_text()
                lines = content.splitlines()
            except Exception:
                continue
            
            for route in routes[:5]:
                try:
                    # 清理 handler 名：去掉括号、receiver
                    handler_raw = route.handler.strip()
                    # "RequestLog(" -> "RequestLog"
                    handler_name = re.sub(r'\s*\([^)]*\)\s*', '', handler_raw)
                    handler_name = re.sub(r'\s*\(.*', '', handler_name)
                    # 取最后一个点之后的名字
                    if '.' in handler_name:
                        handler_name = handler_name.split('.')[-1]
                    if not handler_name or handler_name in ('(', ''):
                        continue
                    
                    spec_item = {
                        "path": route.path,
                        "method": route.method,
                        "handler": handler_name,
                        "file": filepath,
                        "request_struct": None,
                        "response_struct": None,
                        "middleware": [],
                    }
                    
                    # 1. 找方法签名 — 搜 func (receiver) MethodName(params)
                    # 模式: func (m *Module) CreateAdGroup(c *gin.Context, req *CreateAdGroupRequest)
                    sig_pattern = rf'func\s+\([^)]+\)\s+{re.escape(handler_name)}\s*\((.*)\)'
                    sig_m = re.search(sig_pattern, content)
                    if sig_m:
                        params_str = sig_m.group(1)
                        # 从参数中提取 Request struct
                        req_match = re.search(r'req\s+\*?(\w+Request\w*)', params_str)
                        if req_match:
                            spec_item["request_struct"] = req_match.group(1)
                        # 也提取其他参数中的 Request
                        req_matches = re.findall(r'\*?(\w+Request\w*)', params_str)
                        if req_matches and not spec_item["request_struct"]:
                            spec_item["request_struct"] = req_matches[0]
                    
                    # 2. 找方法体内的 return 语句，提取 Response struct
                    # 从方法签名处往后找 return 语句
                    if sig_m:
                        method_body_start = sig_m.end()
                        # 找匹配的右花括号
                        brace_count = 1
                        pos = method_body_start
                        method_body = ""
                        while pos < len(content) and brace_count > 0:
                            ch = content[pos]
                            if ch == '{':
                                brace_count += 1
                            elif ch == '}':
                                brace_count -= 1
                            if brace_count > 0:
                                method_body += ch
                            pos += 1
                        
                        # 在方法体内找 return 语句
                        return_matches = re.findall(r'return\s+(\w+)\.\w+\(\s*(\*?\w+)\s*,', method_body)
                        if return_matches:
                            # 第一个非 error 的返回值通常是 response
                            for ret_var, ret_type in return_matches:
                                if ret_type and 'error' not in ret_type.lower() and ret_type != 'nil':
                                    spec_item["response_struct"] = ret_type.lstrip('*')
                                    break
                        
                        # 也搜简单的 return xxxResponse{
                        simple_resp = re.search(r'return\s+(\w+Response)', method_body)
                        if simple_resp and not spec_item["response_struct"]:
                            spec_item["response_struct"] = simple_resp.group(1)
                    
                    # 3. 提取 middleware — 从文件中的 middleware 使用
                    mw_matches = re.findall(r'middleware\.(\w+)', content)
                    if mw_matches:
                        spec_item["middleware"] = list(set(mw_matches))[:10]
                    
                    ir.api_spec.append(spec_item)
                    
                except Exception:
                    pass
    
    def _extract_sql_operations(self, ir: IRDocument, dir_path: Path, max_files: int):
        """从 DAO 层提取 SQL/GORM 操作
        
        扫描 dao/ 目录，提取：
        - db.Create() → INSERT
        - db.Update() → UPDATE
        - db.Delete() → DELETE
        - db.Find()/db.Where() → SELECT
        - db.CreateInBatches() → BATCH INSERT
        - Transaction → 大事务
        """
        dao_dir = dir_path / "dao"
        if not dao_dir.exists():
            return
        
        try:
            go_files = list(dao_dir.rglob("*.go"))
        except Exception:
            return
        
        # GORM 操作模式映射
        gorm_ops = {
            "db.Create": "INSERT",
            "db.Save": "INSERT_OR_UPDATE",
            "db.Update": "UPDATE",
            "db.Delete": "DELETE",
            "db.Find": "SELECT_ONE",
            "db.First": "SELECT_ONE",
            "db.Take": "SELECT_ONE",
            "db.Where": "FILTER",
            "db.Order": "ORDER_BY",
            "db.Select": "SELECT_COLUMNS",
            "db.Group": "GROUP_BY",
            "db.Having": "HAVING",
            "db.Limit": "LIMIT",
            "db.Offset": "OFFSET",
            "db.Count": "COUNT",
            "db.Pluck": "PLUCK",
            "db.Scan": "SCAN_RESULT",
            "db.Raw": "RAW_SQL",
            "db.Exec": "EXEC_SQL",
            "db.CreateInBatches": "BATCH_INSERT",
            "db.Transaction": "TRANSACTION",
        }
        
        for go_file in go_files:
            if len(ir.sql_operations) >= max_files * 20:
                break
            try:
                content = go_file.read_text()
                lines = content.splitlines()
                
                try:
                    rel = go_file.relative_to(dir_path.parent)
                except ValueError:
                    rel = go_file
                
                for i, line in enumerate(lines, 1):
                    line = line.strip()
                    # 跳过空行和注释
                    if not line or line.startswith("//") or line.startswith("/*"):
                        continue
                    
                    # 匹配 GORM 操作
                    for gorm_call, sql_op in gorm_ops.items():
                        if gorm_call in line and not line.strip().startswith("//"):
                            # 提取表名（从 func CreateXxx(ctx, entity *Entity) 或 entity.TableName()）
                            table_name = ""
                            
                            # 从函数签名获取 entity 类型
                            if i > 0:
                                # 往前找函数定义
                                for j in range(i-1, max(0, i-10), -1):
                                    func_m = re.search(r'func\s+\w+\([^)]*\*?(\w+Entity\w*)\)', lines[j])
                                    if func_m:
                                        # 从 struct 提取 table name
                                        entity_name = func_m.group(1)
                                        # 在 file 中找 TableName 方法
                                        table_pattern = r'func\s+\([^)]*\*' + re.escape(entity_name) + r'\)\s+TableName\s*\(\)\s+string\s*\{\s*return\s*"([^"]+)"'
                                        table_m = re.search(table_pattern, content)
                                        if table_m:
                                            table_name = table_m.group(1)
                                        break
                            
                            ir.sql_operations.append({
                                "file": str(rel),
                                "line": i,
                                "gorm_call": gorm_call,
                                "sql_operation": sql_op,
                                "table": table_name,
                                "context": line[:100],
                            })
                            break
            except Exception:
                pass
        
        # 识别大事务（Transaction 中有多步操作）
        for go_file in go_files:
            try:
                content = go_file.read_text()
                lines = content.splitlines()
                
                in_transaction = False
                tx_depth = 0
                tx_funcs = []
                
                for i, line in enumerate(lines, 1):
                    if "Transaction(" in line:
                        in_transaction = True
                        tx_depth = 0
                        # 往前找函数名
                        for j in range(i-1, max(0, i-5), -1):
                            func_m = re.search(r'func\s+(\w+)\s*\(', lines[j])
                            if func_m:
                                tx_funcs.append({
                                    "name": func_m.group(1),
                                    "file": str(rel) if 'rel' in dir() else str(go_file.relative_to(dir_path.parent)),
                                    "line": i,
                                })
                                break
                    
                    if in_transaction:
                        if '{' in line:
                            tx_depth += line.count('{')
                        if '}' in line:
                            tx_depth -= line.count('}')
                        
                        if tx_depth <= 0:
                            in_transaction = False
                            
            except Exception:
                pass
    
    def _extract_error_codes(self, ir: IRDocument, dir_path: Path, max_files: int):
        """从错误码定义文件提取错误码
        
        扫描 util/errors/ 目录，提取：
        - DB_QUERY_FAIL = 103
        - RDS_LOCK_FAIL = 218
        - 按类别分组（DB/Redis/HTTP/业务）
        """
        errors_dir = dir_path / "util" / "errors"
        if not errors_dir.exists():
            # 也搜其他可能的错误码文件
            errors_dir = None
        
        # 通用策略：搜所有错误码定义文件（errors.go, error.go, errcode.go 等）
        try:
            r = subprocess.run(
                ["find", str(dir_path), "-name", "errors*.go", "-o", "-name", "error*.go", "-o", "-name", "errcode*.go", "-not", "-path", "*/vendor/*"],
                capture_output=True, text=True, timeout=30
            )
        except Exception:
            return
        
        error_files = [f.strip() for f in r.stdout.strip().split('\n') if f.strip()]
        
        for error_file in error_files[:5]:
            full = dir_path / error_file if isinstance(dir_path, Path) else Path(error_file)
            if not full.exists():
                continue
            
            try:
                content = full.read_text()
                lines = content.splitlines()
                
                try:
                    rel = full.relative_to(dir_path.parent)
                except ValueError:
                    rel = full
                
                # 匹配错误码定义模式：
                # DB_QUERY_FAIL = newError(http.StatusOK, 103, "database query failed")
                # 或：DB_QUERY_FAIL       = newError(...)
                # 或：var DB_QUERY_FAIL = ...
                pattern = r'(\w+)\s*=\s*newError\([^,]+,\s*(\d+),\s*"([^"]+)"\)'
                matches = re.findall(pattern, content)
                
                for name, code, message in matches:
                    # 按 code 范围分类
                    code_int = int(code)
                    if code_int < 10:
                        category = "general"
                    elif code_int < 100:
                        category = "general"
                    elif code_int < 200:
                        category = "database"
                    elif code_int < 300:
                        category = "redis"
                    elif code_int < 400:
                        category = "http"
                    elif code_int < 500:
                        category = "login"
                    elif code_int < 600:
                        category = "partner"
                    elif code_int < 700:
                        category = "creative"
                    elif code_int < 800:
                        category = "imagestop"
                    elif code_int < 900:
                        category = "adshare"
                    else:
                        category = "other"
                    
                    ir.error_codes.append({
                        "name": name,
                        "code": code_int,
                        "message": message,
                        "category": category,
                        "file": str(rel),
                    })
            except Exception:
                pass
    
    def _extract_auth_models(self, ir: IRDocument, dir_path: Path, max_files: int):
        """提取权限/鉴权模型
        
        扫描 middleware/ 目录，提取：
        - LoginCheck (token cookie → Redis → SSO)
        - PermissionCheck (权限校验逻辑)
        - 路由级权限配置
        
        结合 api_spec 中的 middleware 信息，构建受保护路由列表
        """
        # 1. 扫描 middleware 文件
        middleware_dir = dir_path / "app" / "adminapi" / "middleware"
        if not middleware_dir.exists():
            # 尝试其他可能的 middleware 路径
            try:
                r = subprocess.run(
                    ["find", str(dir_path), "-type", "d", "-name", "middleware"],
                    capture_output=True, text=True, timeout=30
                )
                middleware_dirs = [f.strip() for f in r.stdout.strip().split('\n') if f.strip()]
                # 排除 vendor
                middleware_dirs = [d for d in middleware_dirs if '/vendor/' not in d]
            except Exception:
                middleware_dirs = []
        else:
            middleware_dirs = [str(middleware_dir)]
        
        for mw_dir in middleware_dirs[:3]:
            try:
                mw_files = list(Path(mw_dir).rglob("*.go"))
            except Exception:
                continue
            
            for mw_file in mw_files:
                try:
                    content = mw_file.read_text()
                    
                    # 提取 middleware 函数定义
                    # func LoginCheck() gin.HandlerFunc
                    # func PermissionCheck() gin.HandlerFunc
                    mw_funcs = re.findall(r'func\s+(\w+)\s*\(\)\s+gin\.HandlerFunc\s*\{', content)
                    if not mw_funcs:
                        # 也搜 func (r *Router) xxx(c *gin.Context) 模式
                        mw_funcs = re.findall(r'func\s+(\w+)\s*\(c\s+\*gin\.Context\)', content)
                    
                    if mw_funcs:
                        try:
                            rel = mw_file.relative_to(dir_path.parent)
                        except ValueError:
                            rel = mw_file
                        
                        # 提取 middleware 逻辑关键词
                        logic_keywords = []
                        if "cookie" in content.lower():
                            logic_keywords.append("cookie-based")
                        if "redis" in content.lower():
                            logic_keywords.append("redis-cache")
                        if "token" in content.lower():
                            logic_keywords.append("token-validation")
                        if "sso" in content.lower():
                            logic_keywords.append("sso-integration")
                        if "permission" in content.lower() or "auth" in content.lower():
                            logic_keywords.append("permission-check")
                        if "rate" in content.lower():
                            logic_keywords.append("rate-limiting")
                        if "jwt" in content.lower():
                            logic_keywords.append("jwt")
                        
                        for mw_func in mw_funcs:
                            ir.auth_models.append({
                                "middleware": mw_func,
                                "file": str(rel),
                                "logic": "; ".join(logic_keywords) if logic_keywords else "unknown",
                                "description": "",
                            })
                except Exception:
                    pass
        
        # 2. 从 api_spec 构建受保护路由
        protected_routes = {}
        for api in ir.api_spec:
            mws = api.get("middleware", [])
            if mws and "LoginCheck" in mws:
                key = f"{api['method']} {api['path']}"
                protected_routes[key] = {
                    "middleware": mws,
                    "handler": api.get("handler", ""),
                }
        
        ir.auth_models.append({
            "middleware": "__protected_routes__",
            "file": "api_spec",
            "logic": f"{len(protected_routes)} routes protected by LoginCheck",
            "description": "",
            "protected_routes": protected_routes,
        })
    
    def _extract_entity_tables(self, ir: IRDocument, dir_path: Path, max_files: int):
        """从 entity 文件提取 TableName 映射
        
        扫描 dao/entity/ 目录，提取：
        - func (e *EntityName) TableName() string { return "table_name" }
        """
        entity_dir = dir_path / "dao" / "entity"
        if not entity_dir.exists():
            return
        
        try:
            go_files = list(entity_dir.rglob("*.go"))
        except Exception:
            return
        
        for go_file in go_files:
            if len(ir.entity_tables) >= max_files:
                break
            try:
                content = go_file.read_text()
                lines = content.splitlines()
                
                try:
                    rel = go_file.relative_to(dir_path.parent)
                except ValueError:
                    rel = go_file
                
                # 匹配 TableName 方法（跨行：func 和 return 在不同行）
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if 'TableName()' in stripped and 'func' in stripped:
                        # 提取 entity 名
                        entity_m = re.search(r'func\s+\([^)]*\*\s*(\w+Entity\w*)\)', stripped)
                        if entity_m:
                            entity_name = entity_m.group(1)
                            # 提取表名（可能在同一行或下一行）
                            table_m = re.search(r'return\s+"([^"]+)"', stripped)
                            if not table_m and i + 1 < len(lines):
                                table_m = re.search(r'return\s+"([^"]+)"', lines[i + 1])
                            if table_m:
                                table_name = table_m.group(1)
                                ir.entity_tables.append({
                                    "entity": entity_name,
                                    "table": table_name,
                                    "file": str(rel),
                                    "line": i + 1,
                                })
            except Exception:
                pass
    
    def _extract_conditions(self, ir: IRDocument, dir_path: Path, max_files: int):
        """从 condition 文件提取查询条件结构
        
        扫描 dao/condition/ 目录，提取：
        - type XxxCondition struct { ... }
        """
        cond_dir = dir_path / "dao" / "condition"
        if not cond_dir.exists():
            return
        
        try:
            go_files = list(cond_dir.rglob("*.go"))
        except Exception:
            return
        
        for go_file in go_files:
            if len(ir.conditions) >= max_files:
                break
            try:
                content = go_file.read_text()
                
                try:
                    rel = go_file.relative_to(dir_path.parent)
                except ValueError:
                    rel = go_file
                
                # 匹配 struct 定义
                for sm in re.finditer(r'type\s+(\w+Condition)\s+struct\s*\{(.*?)\n\}', content, re.DOTALL):
                    cond_name = sm.group(1)
                    body = sm.group(2)
                    
                    # 提取字段
                    fields = []
                    for fm in re.finditer(r'\s+(\w+)\s+\*?(\w+)', body):
                        fname = fm.group(1)
                        ftype = fm.group(2)
                        # 跳过 json/gorm tag
                        if fname in ('json', 'gorm', 'form'):
                            continue
                        fields.append({"name": fname, "type": ftype})
                    
                    if fields:
                        ir.conditions.append({
                            "name": cond_name,
                            "file": str(rel),
                            "fields": fields[:20],
                        })
            except Exception:
                pass
    
    def _extract_configs(self, ir: IRDocument, dir_path: Path, max_files: int):
        """提取配置文件内容
        
        扫描 etc/, deploy/ 目录，提取 YAML/JSON 配置
        """
        config_dirs = [
            dir_path / "etc",
            dir_path / "deploy",
        ]
        
        for config_dir in config_dirs:
            if not config_dir.exists():
                continue
            
            try:
                config_files = list(config_dir.glob("*.yml")) + list(config_dir.glob("*.yaml")) + list(config_dir.glob("*.json"))
            except Exception:
                continue
            
            for cf in config_files:
                if len(ir.configs) >= max_files * 10:
                    break
                try:
                    content = cf.read_text()
                    ext = cf.suffix.lower()
                    
                    try:
                        rel = cf.relative_to(dir_path.parent)
                    except ValueError:
                        rel = cf
                    
                    if ext in ('.yml', '.yaml'):
                        # 简单 YAML 键值提取
                        for line in content.splitlines():
                            line = line.strip()
                            if line and not line.startswith('#') and ':' in line:
                                key_val = line.split(':', 1)
                                if len(key_val) == 2:
                                    key = key_val[0].strip()
                                    val = key_val[1].strip()
                                    if val and not val.startswith('"') and not val.startswith("'"):
                                        ir.configs.append({
                                            "file": str(rel),
                                            "type": "yaml",
                                            "key": key,
                                            "value": val[:200],
                                        })
                    elif ext == '.json':
                        # 简单 JSON 键值提取
                        for line in content.splitlines():
                            line = line.strip()
                            if line and ':' in line and '"' in line:
                                kv_m = re.match(r'\s*"([^"]+)"\s*:\s*"([^"]+)"', line)
                                if kv_m:
                                    ir.configs.append({
                                        "file": str(rel),
                                        "type": "json",
                                        "key": kv_m.group(1),
                                        "value": kv_m.group(2)[:200],
                                    })
                except Exception:
                    pass
    
    def _detect_perf_hotspots(self, ir: IRDocument, dir_path: Path, max_files: int):
        """检测性能热点 — N+1 查询、大事务、缺少 Limit 的查询"""
        dao_dir = dir_path / "dao"
        if not dao_dir.exists():
            return
        
        try:
            go_files = list(dao_dir.rglob("*.go"))
        except Exception:
            return
        
        for go_file in go_files:
            if len(ir.perf_hotspots) >= max_files * 5:
                break
            try:
                content_f = go_file.read_text()
                lines = content_f.splitlines()
                
                try:
                    rel = go_file.relative_to(dir_path.parent)
                except ValueError:
                    rel = go_file
                
                # 1. N+1 查询：循环内的 db.Find/First/Count
                in_loop = False
                loop_indent = 0
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    
                    if stripped.startswith('for ') or stripped.startswith('for{'):
                        in_loop = True
                        loop_indent = len(line) - len(line.lstrip())
                    
                    if in_loop:
                        current_indent = len(line) - len(line.lstrip())
                        if current_indent <= loop_indent and stripped and not stripped.startswith('}'):
                            in_loop = False
                        
                        for db_call in ['db.Find', 'db.First', 'db.Count', 'db.Take']:
                            if db_call in stripped and not stripped.startswith('//'):
                                loop_var = ''
                                for_m = re.search(r'for\s+(\w+)\s*[:]?=', stripped)
                                if for_m:
                                    loop_var = for_m.group(1)
                                
                                ir.perf_hotspots.append({
                                    "type": "N+1_QUERY",
                                    "severity": "high",
                                    "file": str(rel),
                                    "line": i + 1,
                                    "detail": f"db.{db_call.replace('db.', '')} inside loop (var={loop_var})",
                                    "call": db_call,
                                    "loop_var": loop_var,
                                })
                                break
                
                # 2. 大事务：Transaction 中有大量 db 操作
                for i, line in enumerate(lines):
                    if 'Transaction(' in line and 'func' not in line:
                        for j in range(max(0, i-10), i):
                            func_m = re.search(r'func\s+(\w+)\s*\(', lines[j])
                            if func_m:
                                func_name = func_m.group(1)
                                db_ops = 0
                                tx_depth = 0
                                for k in range(j, min(len(lines), j + 200)):
                                    l = lines[k]
                                    if 'tx.' in l or 'db.' in l:
                                        if any(op in l for op in ['Create', 'Update', 'Delete', 'Find', 'First', 'Count']):
                                            db_ops += 1
                                    tx_depth += l.count('{') - l.count('}')
                                    if tx_depth <= 0:
                                        break
                                
                                if db_ops >= 3:
                                    ir.perf_hotspots.append({
                                        "type": "LARGE_TRANSACTION",
                                        "severity": "medium",
                                        "file": str(rel),
                                        "line": j + 1,
                                        "detail": f"Transaction with {db_ops} db operations",
                                        "func": func_name,
                                        "db_ops": db_ops,
                                    })
                                break
                
                # 3. 不带 Limit 的查询
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if ('db.Find(' in stripped or 'db.Where(' in stripped) and 'Limit' not in stripped:
                        has_limit = any('Limit(' in lines[k] for k in range(i, min(i + 10, len(lines))))
                        if not has_limit:
                            ir.perf_hotspots.append({
                                "type": "UNLIMITED_QUERY",
                                "severity": "medium",
                                "file": str(rel),
                                "line": i + 1,
                                "detail": f"Query without Limit: {stripped[:80]}",
                            })
                
                # 4. SQL 注入风险
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if ('db.Raw(' in stripped or 'db.Exec(' in stripped):
                        if '%s' in stripped or '%v' in stripped or '%' in stripped:
                            ir.perf_hotspots.append({
                                "type": "SQL_INJECTION_RISK",
                                "severity": "high",
                                "file": str(rel),
                                "line": i + 1,
                                "detail": f"Raw SQL with format specifier: {stripped[:80]}",
                            })
                
            except Exception:
                pass
    
    def _detect_compat_issues(self, ir: IRDocument, dir_path: Path, max_files: int):
        """检测向后兼容性问题"""
        try:
            go_files = list(dir_path.rglob("*.go"))
        except Exception:
            return
        
        go_files = [f for f in go_files if '/vendor/' not in str(f)][:max_files * 5]
        
        for go_file in go_files:
            if len(ir.compat_issues) >= max_files * 3:
                break
            try:
                content_f = go_file.read_text()
                lines = content_f.splitlines()
                
                try:
                    rel = go_file.relative_to(dir_path.parent)
                except ValueError:
                    rel = go_file
                
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    
                    if '// Deprecated' in stripped:
                        detail = stripped[:120]
                        sev = "warning"
                        if 'will be removed' in detail.lower() or 'use ' in detail.lower():
                            sev = "critical"
                        
                        ir.compat_issues.append({
                            "type": "DEPRECATED",
                            "severity": sev,
                            "file": str(rel),
                            "line": i + 1,
                            "detail": detail,
                        })
                        
                        for j in range(max(0, i-3), i):
                            func_m = re.search(r'func\s+(\w+)\s*\(', lines[j])
                            if func_m:
                                ir.compat_issues.append({
                                    "type": "DEPRECATED_FUNC",
                                    "severity": "warning",
                                    "file": str(rel),
                                    "line": j + 1,
                                    "detail": f"Deprecated function: {func_m.group(1)}",
                                    "func": func_m.group(1),
                                })
                                break
                
                # 硬编码值
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if re.search(r'=\s*\d{13,}', stripped):
                        ir.compat_issues.append({
                            "type": "HARDCODED_VALUE",
                            "severity": "low",
                            "file": str(rel),
                            "line": i + 1,
                            "detail": f"Potential hardcoded value: {stripped[:80]}",
                        })
                
            except Exception:
                pass
    
    def _build_call_graph_from_signatures(self, ir: IRDocument):
        """从 import + func 签名构建调用图"""

    @staticmethod
    def _find_agent_dirs(repo_path: Path) -> List[str]:
        """在 Go 仓库中查找 agent skill 目录（含 references/workflow.yaml）.

        识别模式：
        - app/agent/skills/{skill_name}/references/workflow.yaml
        - app/agent/{service_name}/  (含 agent_flow.go)
        """
        agent_dirs = []
        # 模式1: skills 子目录
        skills_ref = repo_path / "app" / "agent" / "skills"
        if skills_ref.exists():
            for skill_dir in skills_ref.iterdir():
                wf_file = skill_dir / "references" / "workflow.yaml"
                if wf_file.exists():
                    agent_dirs.append(str(skill_dir))
        # 模式2: 直接 agent 子服务
        agent_app = repo_path / "app" / "agent"
        if agent_app.exists():
            for subdir in agent_app.iterdir():
                if subdir.is_dir() and (subdir / "agent_flow.go").exists():
                    agent_dirs.append(str(subdir))
        return agent_dirs


# ============================================================================
# Python Scanner — 基于 AST 的 Python 代码扫描器（复用 knowledge_extractor）
# ============================================================================

class PythonScanner:
    """Python 代码扫描器 — 基于 AST
    
    改进：
    - 增强 class/method 提取，增加 decorator、return type、docstring
    - 提取类属性（类级别的变量赋值）
    - 支持 async def 函数
    - 改进 import 提取，区分 from-import 和 import
    - 增加 error recovery
    """
    
    def __init__(self, extractor=None):
        self.extractor = extractor
    
    def _analyze_data_flow(self, file_path: Path) -> List[DataFlowNode]:
        """从 AST 分析数据流 — 变量定义和使用"""
        nodes = []
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except Exception:
            return nodes
        
        for node in ast.walk(tree):
            # 变量赋值: x = expr
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        expr = ""
                        try:
                            expr = ast.unparse(node.value)
                        except Exception:
                            expr = "?"
                        nodes.append(DataFlowNode(
                            var_name=target.id,
                            kind="assignment",
                            lineno=node.lineno,
                            file=str(file_path),
                            value_expr=expr[:100],
                        ))
            
            # 变量使用: 读变量值
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                nodes.append(DataFlowNode(
                    var_name=node.id,
                    kind="use",
                    lineno=node.lineno,
                    file=str(file_path),
                ))
            
            # 变量定义: 在函数参数、类属性中
            elif isinstance(node, ast.arg):
                nodes.append(DataFlowNode(
                    var_name=node.arg,
                    kind="definition",
                    lineno=node.lineno,
                    file=str(file_path),
                ))
        
        return nodes
    
    def _get_decorator_names(self, node) -> List[str]:
        """提取函数的 decorator 名称"""
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(f"{dec.value.id}.{dec.attr}" if hasattr(dec.value, 'id') else dec.attr)
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    decorators.append(dec.func.attr)
        return decorators
    
    def _get_return_annotation(self, node) -> Optional[str]:
        """提取函数返回值类型注解"""
        if hasattr(node, 'returns') and node.returns:
            return_node = node.returns
            if isinstance(return_node, ast.Name):
                return return_node.id
            elif isinstance(return_node, ast.Attribute):
                return return_node.attr
            elif isinstance(return_node, ast.Subscript):
                # Optional[List[str]], Dict[str, int] 等
                try:
                    return ast.unparse(return_node)
                except Exception:
                    return "?"
        return None
    
    def _get_func_params(self, node) -> List[Dict[str, str]]:
        """提取函数参数（含类型注解）"""
        params = []
        args = node.args
        
        # 普通参数
        for i, arg in enumerate(args.args):
            param = {"name": arg.arg}
            if arg.annotation:
                try:
                    param["type"] = ast.unparse(arg.annotation)
                except Exception:
                    param["type"] = "?"
            else:
                param["type"] = "Any"
            # 检查是否有默认值
            if i < len(args.defaults):
                param["has_default"] = True
            params.append(param)
        
        # *args
        if args.vararg:
            params.append({
                "name": f"*{args.vararg.arg}",
                "type": ast.unparse(args.vararg.annotation) if args.vararg.annotation else "Any",
                "is_vararg": True,
            })
        
        # **kwargs
        if args.kwarg:
            params.append({
                "name": f"**{args.kwarg.arg}",
                "type": ast.unparse(args.kwarg.annotation) if args.kwarg.annotation else "Any",
                "is_kwarg": True,
            })
        
        return params
    
    def scan_file(self, file_path: Path) -> Dict[str, Any]:
        """扫描单个 Python 文件"""
        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception:
            return {"status": "degraded", "reason": "read_failed"}
        
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {"status": "degraded", "reason": "syntax_error"}
        
        result = {
            "file": str(file_path),
            "functions": [],
            "classes": [],
            "imports": [],
        }
        
        for node in ast.iter_child_nodes(tree):
            # 处理顶级函数和类
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                is_async = isinstance(node, ast.AsyncFunctionDef)
                result["functions"].append({
                    "name": node.name,
                    "async": is_async,
                    "params": self._get_func_params(node),
                    "return_type": self._get_return_annotation(node),
                    "decorators": self._get_decorator_names(node),
                    "docstring": ast.get_docstring(node),
                    "lineno": node.lineno,
                    "method_count": sum(1 for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))),
                })
            elif isinstance(node, ast.ClassDef):
                methods = []
                class_attrs = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append({
                            "name": item.name,
                            "async": isinstance(item, ast.AsyncFunctionDef),
                            "params": self._get_func_params(item),
                            "return_type": self._get_return_annotation(item),
                            "decorators": self._get_decorator_names(item),
                            "docstring": ast.get_docstring(item),
                        })
                    elif isinstance(item, ast.Assign):
                        # 类属性
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                class_attrs.append({
                                    "name": target.id,
                                    "type": "?",  # AST 无法直接推断值类型
                                })
                
                result["classes"].append({
                    "name": node.name,
                    "methods": methods,
                    "attrs": class_attrs[:20],
                    "decorators": self._get_decorator_names(node),
                    "bases": [ast.unparse(b) for b in node.bases if hasattr(b, 'id') or hasattr(b, 'attr')],
                    "docstring": ast.get_docstring(node),
                    "lineno": node.lineno,
                })
            
            # 处理 import
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    result["imports"].append({
                        "module": alias.name,
                        "asname": alias.asname,
                        "type": "import",
                    })
            elif isinstance(node, ast.ImportFrom):
                result["imports"].append({
                    "module": node.module or "",
                    "names": [alias.name for alias in node.names],
                    "asnames": [alias.asname for alias in node.names],
                    "level": node.level,  # 相对导入级别
                    "type": "from_import",
                })
        
        return result
    
    def scan_directory(self, dir_path: Path, max_files: int = 2000,
                       incremental: bool = False, changed_files: List[Path] = None) -> IRDocument:
        """扫描整个目录 — 支持增量扫描
        
        当 incremental=True 时，只扫描变更文件。
        changed_files 参数应包含自上次扫描以来变更的文件列表。
        """
        ir = IRDocument(
            repo_name=dir_path.name,
            repo_path=str(dir_path),
            language="python",
        )
        
        count = 0
        scanned_count = 0
        skipped_count = 0
        py_files = sorted(dir_path.rglob("*.py"))
        
        for py_file in py_files:
            if count >= max_files:
                break
            if "__pycache__" in str(py_file) or ".git" in str(py_file):
                continue
            
            # 增量扫描：跳过未变更文件
            if incremental and changed_files is not None:
                if py_file not in changed_files:
                    skipped_count += 1
                    continue
            
            try:
                result = self.scan_file(py_file)
                count += 1
                scanned_count += 1
                
                # 添加 functions
                for f in result.get("functions", []):
                    ir.functions.append(FuncDef(
                        name=f["name"],
                        file=str(py_file.relative_to(dir_path.parent)),
                        params=f.get("params", []),
                        returns=f.get("return_type"),
                        decorators=f.get("decorators", []),
                    ))
                
                # 添加 classes as structs
                for c in result.get("classes", []):
                    ir.structs.append(StructDef(
                        name=c["name"],
                        file=str(py_file.relative_to(dir_path.parent)),
                        methods=[{
                            "name": m["name"],
                            "params": m.get("params", []),
                            "return_type": m.get("return_type"),
                            "decorators": m.get("decorators", []),
                            "docstring": m.get("docstring"),
                        } for m in c.get("methods", [])],
                        fields=[{
                            "name": a["name"],
                            "type": a.get("type", "?"),
                        } for a in c.get("attrs", [])],
                    ))
                
                # 添加 imports
                for imp in result.get("imports", []):
                    ir.imports.append(ImportDef(
                        module=imp["module"],
                        names=imp.get("names", []),
                        is_local=imp.get("level", 0) > 0,  # 相对导入为 local
                    ))
            except Exception as e:
                print(f"  WARNING: Failed to scan {py_file.name}: {e}", file=sys.stderr)
        
        if incremental:
            print(f"  Python scan: scanned={scanned_count}, skipped={skipped_count}")
        
        # 数据流分析（样本文件，避免全量扫描太慢）
        sample_files = list(py_files)[:20]  # 最多分析 20 个文件
        for py_file in sample_files:
            try:
                df_nodes = self._analyze_data_flow(py_file)
                ir.data_flow.extend(df_nodes)
            except Exception:
                pass
        
        return ir


# ============================================================================
# Java Scanner — 基于 regexp 的 Java 代码扫描器（骨架）
# ============================================================================

class JavaScanner:
    """Java 代码扫描器 — 提取 class、method、annotation 等
    
    骨架实现：使用 regexp 进行初步扫描，生产环境建议改用 JavaParser 等 AST 工具
    
    功能：
    - 提取 class/interface/enum 定义
    - 提取 method 签名（含参数、返回类型、throws）
    - 提取 annotation（@RestController, @Service, @Autowired 等）
    - 提取 field 定义（含类型）
    - 提取 import 语句
    - 识别 Spring MVC 路由（@GetMapping, @PostMapping 等）
    """
    
    # Class/Interface/Enum 定义
    CLASS_RE = re.compile(
        r'(?:public\s+)?(?:abstract\s+)?(?:class|interface|enum)\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w\s,]+))?\s*\{'
    )
    # Method 签名
    METHOD_RE = re.compile(
        r'(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)(?:\s+throws\s+[\w\s,]+)?\s*\{'
    )
    # Field 定义
    FIELD_RE = re.compile(
        r'(?:private|protected|public)\s+(?:static\s+)?(?:final\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*[;=]'
    )
    # Annotation
    ANNOTATION_RE = re.compile(
        r'@(\w+)(?:\s*\([^)]*\))?'
    )
    # Spring MVC 路由注解
    SPRING_ROUTE_RE = re.compile(
        r'@(Get|Post|Put|Delete|Patch|Request)(Mapping|Endpoint)\s*\(\s*(?:value\s*=\s*)?"([^"]+)"'
    )
    # Import 语句
    IMPORT_RE = re.compile(
        r'^\s*import\s+([\w.]+)(?:\.\*)?\s*;'
    )
    
    def scan_file(self, file_path: Path) -> Dict[str, Any]:
        """扫描单个 Java 文件"""
        try:
            content = file_path.read_text(encoding='utf-8', errors='replace')
        except Exception:
            return {"status": "degraded", "reason": "read_failed"}
        
        result = {
            "file": str(file_path),
            "classes": [],
            "methods": [],
            "fields": [],
            "annotations": [],
            "routes": [],
            "imports": [],
        }
        
        lines = content.split('\n')
        current_class = None
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 跟踪当前 class 上下文
            class_match = self.CLASS_RE.search(stripped)
            if class_match:
                current_class = class_match.group(1)
                result["classes"].append({
                    "name": current_class,
                    "extends": class_match.group(2),
                    "implements": class_match.group(3),
                    "type": "class" if "class" in stripped else 
                            ("interface" if "interface" in stripped else "enum"),
                    "lineno": i + 1,
                })
            
            # 提取 method
            method_match = self.METHOD_RE.search(stripped)
            if method_match and current_class:
                params_str = method_match.group(3).strip()
                params = []
                if params_str:
                    for param in params_str.split(','):
                        param = param.strip()
                        parts = param.split()
                        if len(parts) >= 2:
                            params.append({
                                "type": parts[0],
                                "name": parts[-1],
                            })
                
                result["methods"].append({
                    "name": method_match.group(2),
                    "return_type": method_match.group(1),
                    "params": params,
                    "class": current_class,
                    "lineno": i + 1,
                })
            
            # 提取 annotation
            for ann_match in self.ANNOTATION_RE.finditer(stripped):
                ann_name = ann_match.group(1)
                if ann_name not in ('Override', 'SuppressWarnings'):
                    result["annotations"].append({
                        "name": ann_name,
                        "class": current_class,
                        "lineno": i + 1,
                    })
            
            # 提取 Spring MVC 路由
            route_match = self.SPRING_ROUTE_RE.search(stripped)
            if route_match:
                http_method = route_match.group(1).lower()
                path = route_match.group(3)
                result["routes"].append({
                    "method": http_method,
                    "path": path,
                    "class": current_class,
                    "lineno": i + 1,
                })
            
            # 提取 field
            field_match = self.FIELD_RE.search(stripped)
            if field_match and current_class:
                result["fields"].append({
                    "type": field_match.group(1),
                    "name": field_match.group(2),
                    "class": current_class,
                    "lineno": i + 1,
                })
            
            # 提取 import
            import_match = self.IMPORT_RE.match(stripped)
            if import_match:
                result["imports"].append({
                    "module": import_match.group(1),
                    "is_local": False,  # Java 通常没有 local import
                })
        
        return result
    
    def scan_directory(self, dir_path: Path, max_files: int = 2000,
                       incremental: bool = False, changed_files: List[Path] = None) -> IRDocument:
        """扫描整个目录 — 支持增量扫描
        
        当 incremental=True 时，只扫描变更文件。
        changed_files 参数应包含自上次扫描以来变更的文件列表。
        """
        ir = IRDocument(
            repo_name=dir_path.name,
            repo_path=str(dir_path),
            language="java",
        )
        
        count = 0
        scanned_count = 0
        skipped_count = 0
        java_files = sorted(dir_path.rglob("*.java"))
        
        for java_file in java_files:
            if count >= max_files:
                break
            if "target/" in str(java_file) or ".git" in str(java_file):
                continue
            
            if incremental and changed_files is not None:
                if java_file not in changed_files:
                    skipped_count += 1
                    continue
            
            try:
                result = self.scan_file(java_file)
                count += 1
                scanned_count += 1
                
                # 添加 classes as structs
                for c in result.get("classes", []):
                    ir.structs.append(StructDef(
                        name=c["name"],
                        file=str(java_file.relative_to(dir_path.parent)),
                        methods=[{
                            "name": m["name"],
                            "return_type": m.get("return_type"),
                        } for m in result.get("methods", []) if m.get("class") == c["name"]],
                    ))
                
                # 添加 methods as functions
                for m in result.get("methods", []):
                    ir.functions.append(FuncDef(
                        name=m["name"],
                        file=str(java_file.relative_to(dir_path.parent)),
                        params=m.get("params", []),
                        returns=m.get("return_type"),
                    ))
                
                # 添加 routes
                for r in result.get("routes", []):
                    ir.routes.append(RouteDef(
                        path=r["path"],
                        method=r["method"].upper(),
                        handler=r.get("class", ""),
                        module=r.get("class", ""),
                        file=str(java_file.relative_to(dir_path.parent)),
                    ))
                
                # 添加 imports
                for imp in result.get("imports", []):
                    ir.imports.append(ImportDef(
                        module=imp["module"],
                        is_local=imp.get("is_local", False),
                    ))
            except Exception as e:
                print(f"  WARNING: Failed to scan {java_file.name}: {e}", file=sys.stderr)
        
        if incremental:
            print(f"  Java scan: scanned={scanned_count}, skipped={skipped_count}")
        
        return ir


# ============================================================================
# Multi-Repo Analyzer — 多仓库关联分析
# ============================================================================

class MultiRepoAnalyzer:
    """多仓库依赖分析 — 构建仓库间的 import 关系图
    
    改进：
    - 正确扫描每个仓库的 import 并匹配跨仓库引用
    - 支持 import_prefix 和 repo name 两种匹配模式
    - 去重：同一对仓库之间只记录一条边
    - 收集跨仓库符号引用
    """
    
    def analyze(self, repos: List[Dict]) -> Dict[str, Any]:
        """
        分析多个仓库之间的依赖关系
        输入: Profile 中的 repositories 列表
        输出: 依赖图 + 跨仓库引用
        """
        dep_graph = {
            "nodes": [],
            "edges": [],
            "cross_refs": [],
        }
        
        # 构建 repo_name → repo_info 映射 + import_prefix 映射
        repo_map = {}
        for repo in repos:
            repo_map[repo["name"]] = repo
        
        # 构建 import prefix → repo_name 映射（用于跨仓库匹配）
        prefix_to_repo = {}
        for repo_name, repo_info in repo_map.items():
            # 优先使用 import_prefix
            prefix = repo_info.get("import_prefix", "")
            if prefix:
                prefix_to_repo[prefix] = repo_name
            # 也建立 repo name 作为 fallback
            prefix_to_repo[repo_name] = repo_name
        
        # 对每个仓库节点
        for repo_name, repo_info in repo_map.items():
            dep_graph["nodes"].append({
                "name": repo_name,
                "path": repo_info["path"],
                "language": repo_info.get("language", "unknown"),
            })
            
            repo_path = Path(repo_info["path"])
            if not repo_path.exists():
                continue
            
            # 扫描该仓库的 import
            language = repo_info.get("language", "go")
            scanner = self._get_scanner(language)
            ir = scanner.scan_directory(repo_path)
            
            # 收集该仓库的所有 import
            seen_targets = set()  # 去重
            for imp in ir.imports:
                if imp.is_local:
                    # 检查是否指向其他仓库
                    matched_repo = None
                    
                    # 尝试匹配 import_prefix
                    for prefix, target_name in prefix_to_repo.items():
                        if prefix and imp.module.startswith(prefix) and target_name != repo_name:
                            matched_repo = target_name
                            break
                    
                    # 尝试匹配 repo name
                    if not matched_repo:
                        for target_name, target_info in repo_map.items():
                            if target_name == repo_name:
                                continue
                            # 检查 import module 是否包含目标 repo name
                            if target_info.get("path"):
                                target_basename = Path(target_info["path"]).name
                                if target_basename in imp.module or target_name in imp.module:
                                    matched_repo = target_name
                                    break
                    
                    if matched_repo and matched_repo not in seen_targets:
                        seen_targets.add(matched_repo)
                        dep_graph["edges"].append({
                            "from": repo_name,
                            "to": matched_repo,
                            "symbols": [imp.module],
                        })
                        dep_graph["cross_refs"].append({
                            "from_repo": repo_name,
                            "to_repo": matched_repo,
                            "import": imp.module,
                            "language": language,
                        })
        
        return dep_graph
    
    def _get_scanner(self, language: str):
        if language == "python":
            return PythonScanner()
        elif language == "java":
            return JavaScanner()
        return GoScanner()


# ============================================================================
# LLM Knowledge Generator — LLM 学习总结
# ============================================================================

class LLMKnowledgeGenerator:
    """LLM 学习总结 — 将 IR + 依赖图转化为可读知识库"""
    
    def build_prompt(self, ir: IRDocument, dep_graph: Dict, repos: List[Dict], dir_path_str: str = None) -> str:
        """构建 LLM prompt"""
        prompt_parts = []
        
        prompt_parts.append("# 代码库学习任务")
        prompt_parts.append("")
        prompt_parts.append("你是一个资深软件架构师。请基于以下代码扫描结果，")
        prompt_parts.append("总结这个系统的架构、业务流程、数据模型和关键技术决策。")
        prompt_parts.append("")
        
        # 仓库信息
        prompt_parts.append("## 仓库信息")
        for repo in repos:
            prompt_parts.append(f"- **{repo['name']}**: {repo.get('language', 'unknown')} @ {repo['path']}")
        prompt_parts.append("")
        
        # 依赖图
        if dep_graph.get("edges"):
            prompt_parts.append("## 仓库依赖")
            for edge in dep_graph["edges"]:
                prompt_parts.append(f"- {edge['from']} → {edge['to']}")
            for ref in dep_graph.get("cross_refs", [])[:20]:
                prompt_parts.append(f"  - `{ref['import']}` ({ref['from_repo']} → {ref['to_repo']})")
            prompt_parts.append("")
        elif len(repos) > 1:
            prompt_parts.append("## 仓库依赖")
            prompt_parts.append("未发现跨仓库依赖边")
            prompt_parts.append("")
        
        # IR 摘要
        prompt_parts.append("## 代码结构摘要")
        prompt_parts.append(f"- Structs: {len(ir.structs)}")
        prompt_parts.append(f"- Functions: {len(ir.functions)}")
        prompt_parts.append(f"- Routes: {len(ir.routes)}")
        prompt_parts.append(f"- Imports: {len(ir.imports)}")
        prompt_parts.append("")
        
        # 关键 struct（带 TableName 的通常是数据库表）
        db_structs = [s for s in ir.structs if s.table_name]
        other_structs = [s for s in ir.structs if not s.table_name]
        
        if db_structs:
            prompt_parts.append("## 数据库表推断")
            for s in db_structs[:15]:
                prompt_parts.append(f"\n### `{s.table_name}` (Entity: {s.name})")
                prompt_parts.append(f"文件: {s.file}")
                for f in s.fields[:15]:
                    gorm = f.get('gorm_tag', '')
                    json = f.get('json_tag', '')
                    pk = 'PRIMARY_KEY' in gorm if gorm else False
                    pk_str = ' [PK]' if pk else ''
                    extra = f" gorm:{gorm}" if gorm else ""
                    extra += f" json:{json}" if json else ""
                    prompt_parts.append(f"- `{f['name']}`: {f['type']}{pk_str}{extra}")
            prompt_parts.append("")
        
        # 重要业务 struct（带字段详情）
        important_structs = []
        for s in other_structs:
            name_lower = s.name.lower()
            if any(kw in name_lower for kw in ['service', 'manager', 'handler', 'module', 'config', 'request', 'response']):
                important_structs.append(s)
        
        if important_structs:
            prompt_parts.append("## 关键业务 Struct")
            for s in important_structs[:20]:
                prompt_parts.append(f"\n### `{s.name}`")
                prompt_parts.append(f"文件: {s.file}")
                if s.fields:
                    for f in s.fields[:10]:
                        json = f.get('json_tag', '')
                        prompt_parts.append(f"- `{f['name']}`: {f['type']}" + (f" json:{json}" if json else ""))
            prompt_parts.append("")
        
        # 路由
        if ir.routes:
            prompt_parts.append("## API 路由")
            for r in ir.routes[:30]:
                prompt_parts.append(f"- `{r.method} {r.path}` ({r.file})")
            prompt_parts.append("")
        
        # Service 层
        services = [s for s in ir.structs if "service" in s.name.lower() or "manager" in s.name.lower()]
        if services:
            prompt_parts.append("## 服务层")
            for s in services[:15]:
                prompt_parts.append(f"- **{s.name}** ({len(s.methods)} methods)")
            prompt_parts.append("")
        
        # === 关键源码片段（从路由文件提取核心逻辑） ===
        if dir_path_str and ir.routes and ir.functions:
            prompt_parts.append("## 关键源码片段")
            prompt_parts.append("")
            prompt_parts.append("以下是从路由文件和入口点提取的核心实现代码，帮助理解业务逻辑：")
            prompt_parts.append("")
            
            # 收集需要提取源码的文件
            files_to_snippet = set()
            for route in ir.routes[:15]:
                files_to_snippet.add(route.file)
            for ep in ir.entry_points[:5]:
                files_to_snippet.add(ep['file'])
            
            # 提取源码片段
            for filepath in sorted(files_to_snippet)[:8]:
                # filepath 可能是 "creative-platform/app/..." 或 "app/..."，统一去掉首层 repo 名
                parts = filepath.split('/')
                if parts[0] == os.path.basename(dir_path_str):
                    filepath_clean = '/'.join(parts[1:])
                else:
                    filepath_clean = filepath
                full_path = Path(dir_path_str) / filepath_clean
                if full_path.exists():
                    try:
                        with open(full_path) as f:
                            file_content = f.read()
                            file_lines = file_content.splitlines(True)
                        
                        # 从路由注册行提取 handler 方法名: m.MethodName 或 r.MethodName
                        handler_methods = set()
                        for route in ir.routes:
                            if route.file == filepath:
                                # 从 route.handler 提取方法名（去掉可能的括号、receiver）
                                h = route.handler.strip()
                                # 去掉括号和多余字符: "CreateAdGroup" or "RequestLog("
                                h = re.sub(r'\s*\([^)]*\)\s*', '', h)  # 去掉 (receiver)
                                h = re.sub(r'\s*\([^)]*\)\s*', '', h)  # 去掉 (params)
                                h = re.sub(r'[^(]*\.(\w+).*', r'\1', h)  # 提取最后一个点后的名字
                                if h and h not in ('(', ''):
                                    handler_methods.add(h)
                        
                        # 提取这些方法的实现
                        for method_name in sorted(handler_methods)[:5]:
                            # 搜方法定义: func (r *Module) MethodName(
                            pattern = rf'func\s+\([^)]*\*\w+\)\s+{re.escape(method_name)}\s*\('
                            m = re.search(pattern, file_content)
                            if m:
                                # 找到函数起始位置，提取代码块
                                start_pos = m.start()
                                # 往前找 func 关键字所在的行
                                line_start = file_content.rfind('\n', 0, start_pos) + 1
                                # 往后找匹配的 }
                                brace_count = 0
                                ended = False
                                for ci in range(start_pos, len(file_content)):
                                    if file_content[ci] == '{':
                                        brace_count += 1
                                    elif file_content[ci] == '}':
                                        brace_count -= 1
                                        if brace_count <= 0:
                                            end_pos = ci + 1
                                            ended = True
                                            break
                                
                                if not ended:
                                    end_pos = min(start_pos + 3000, len(file_content))
                                
                                code = file_content[line_start:end_pos].rstrip()
                                if len(code) > 50:
                                    prompt_parts.append(f"### `{method_name}` ({filepath})")
                                    prompt_parts.append("```go")
                                    prompt_parts.append(code[:1500])  # 最多 1500 chars
                                    prompt_parts.append("```")
                                    prompt_parts.append("")
                        break
                    except Exception:
                        pass
            prompt_parts.append("")
        
        # 配置
        if ir.config_files:
            prompt_parts.append("## 配置文件")
            for cf in ir.config_files[:10]:
                prompt_parts.append(f"- {cf}")
            prompt_parts.append("")
        
        # === CPG 增强：调用图 + 数据流 + 入口点 ===
        if ir.call_graph:
            prompt_parts.append("## 调用关系 (Call Graph)")
            # 按 callee 分组
            callee_groups = {}
            for edge in ir.call_graph[:50]:
                callee_groups.setdefault(edge.get("callee", "?"), []).append(edge)
            for callee, edges in list(callee_groups.items())[:20]:
                callers = list(set(e.get("caller", "?") for e in edges if e.get("caller")))
                prompt_parts.append(f"- **{callee}** ← called by: {', '.join(callers[:5])}")
            prompt_parts.append("")
        
        if ir.entry_points:
            prompt_parts.append("## 入口点 (Entry Points)")
            for ep in ir.entry_points[:20]:
                if isinstance(ep, dict):
                    prompt_parts.append(f"- [{ep.get('type', '?')}] **{ep.get('name', '?')}** @ {ep.get('file', '?')}")
                else:
                    prompt_parts.append(f"- **{ep}**")
            prompt_parts.append("")
        
        if ir.data_flow:
            prompt_parts.append("## 数据流摘要 (Data Flow)")
            # 按变量名分组，只展示有 assignment 和 use 的变量
            var_kinds = {}
            for node in ir.data_flow[:100]:
                var_kinds.setdefault(node.var_name, set()).add(node.kind)
            for var_name, kinds in list(var_kinds.items())[:15]:
                if len(kinds) > 1:  # 既有定义又有使用的变量
                    prompt_parts.append(f"- `{var_name}`: {' → '.join(sorted(kinds))}")
            prompt_parts.append("")
        
        # === 测试覆盖报告 ===
        if ir.coverage_report:
            cr = ir.coverage_report
            prompt_parts.append("## 测试覆盖报告")
            prompt_parts.append(f"- 测试文件: {cr.get('test_files', 0)}")
            prompt_parts.append(f"- 测试函数: {cr.get('test_functions', 0)}")
            prompt_parts.append(f"- 测试框架: {cr.get('framework', 'unknown')}")
            prompt_parts.append(f"- 总函数数: {cr.get('total_functions', 0)}")
            prompt_parts.append(f"- 已测试函数: {cr.get('tested_functions', 0)}")
            pct = cr.get('coverage_pct', 0)
            prompt_parts.append(f"- 覆盖率: {pct}%")
            uncovered = cr.get('uncovered_highlights', [])
            if uncovered:
                prompt_parts.append("- **未测试函数（样本）**:")
                for fn in uncovered[:15]:
                    prompt_parts.append(f"  - `{fn}`")
            prompt_parts.append("")
        
        # === API 文档（OpenAPI-like） ===
        if ir.api_spec:
            prompt_parts.append("## API 文档 (OpenAPI-like Spec)")
            prompt_parts.append(f"共 {len(ir.api_spec)} 个端点")
            prompt_parts.append("")
            for api in ir.api_spec[:30]:
                req = api.get('request_struct', '') or '-'
                resp = api.get('response_struct', '') or '-'
                mw = ', '.join(api.get('middleware', [])) or 'none'
                prompt_parts.append(f"- `{api['method']} {api['path']}` → {api['handler']}")
                prompt_parts.append(f"  - Request: `{req}` | Response: `{resp}` | Middleware: {mw}")
            prompt_parts.append("")
        
        # SQL/GORM 操作
        if ir.sql_operations:
            prompt_parts.append("## SQL/GORM 操作 (Database Layer)")
            prompt_parts.append(f"共 {len(ir.sql_operations)} 个数据库操作")
            prompt_parts.append("")
            # 按操作类型分组统计
            op_counts = {}
            for op in ir.sql_operations:
                op_type = op.get('sql_operation', 'UNKNOWN')
                op_counts[op_type] = op_counts.get(op_type, 0) + 1
            prompt_parts.append("操作类型分布:")
            for op_type, count in sorted(op_counts.items(), key=lambda x: -x[1]):
                prompt_parts.append(f"- {op_type}: {count}")
            prompt_parts.append("")
            # 列出前 30 个操作
            for op in ir.sql_operations[:30]:
                prompt_parts.append(f"- `{op['gorm_call']}` → {op['sql_operation']} ({op['file']}:{op['line']})")
            prompt_parts.append("")
        
        # 错误码定义
        if ir.error_codes:
            prompt_parts.append("## 错误码定义 (Error Codes)")
            prompt_parts.append(f"共 {len(ir.error_codes)} 个错误码")
            prompt_parts.append("")
            # 按类别分组
            cat_errors = {}
            for ec in ir.error_codes:
                cat = ec.get('category', 'other')
                if cat not in cat_errors:
                    cat_errors[cat] = []
                cat_errors[cat].append(ec)
            for cat, errors in cat_errors.items():
                prompt_parts.append(f"### {cat} ({len(errors)} codes)")
                for ec in errors[:10]:
                    prompt_parts.append(f"- `{ec['name']}` = {ec['code']}: {ec['message']}")
                if len(errors) > 10:
                    prompt_parts.append(f"  ... 还有 {len(errors) - 10} 个")
                prompt_parts.append("")
        
        # 权限/鉴权模型
        if ir.auth_models:
            prompt_parts.append("## 权限/鉴权模型 (Authentication & Authorization)")
            prompt_parts.append(f"共 {len(ir.auth_models)} 个中间件/鉴权组件")
            prompt_parts.append("")
            for am in ir.auth_models:
                if am['middleware'] == '__protected_routes__':
                    protected_count = len(am.get('protected_routes', {}))
                    prompt_parts.append(f"- **受保护路由**: {protected_count} 个路由需要登录认证")
                else:
                    prompt_parts.append(f"- **{am['middleware']}** ({am['file']}): {am['logic']}")
            prompt_parts.append("")
        
        # Entity/TableName 映射
        if ir.entity_tables:
            prompt_parts.append("## Entity/TableName 映射 (Database Entities)")
            prompt_parts.append(f"共 {len(ir.entity_tables)} 个实体表")
            prompt_parts.append("")
            for et in ir.entity_tables[:30]:
                prompt_parts.append(f"- `{et['entity']}` → `{et['table']}` ({et['file']}:{et['line']})")
            prompt_parts.append("")
        
        # Condition 查询条件
        if ir.conditions:
            prompt_parts.append("## Condition 查询条件 (Query Conditions)")
            prompt_parts.append(f"共 {len(ir.conditions)} 个查询条件结构")
            prompt_parts.append("")
            for cond in ir.conditions[:15]:
                field_names = ', '.join(f['name'] for f in cond['fields'][:5])
                prompt_parts.append(f"- `{cond['name']}` ({cond['file']}): [{field_names}]")
                if len(cond['fields']) > 5:
                    prompt_parts.append(f"  ... 还有 {len(cond['fields']) - 5} 个字段")
            prompt_parts.append("")
        
        # 配置
        if ir.configs:
            prompt_parts.append("## 配置 (Configuration)")
            yaml_configs = [c for c in ir.configs if c.get('type') == 'yaml']
            json_configs = [c for c in ir.configs if c.get('type') == 'json']
            prompt_parts.append(f"YAML: {len(yaml_configs)} 项, JSON: {len(json_configs)} 项")
            prompt_parts.append("")
            # 按文件分组，每文件只展示前 5 个关键配置
            by_file = {}
            for c in ir.configs:
                by_file.setdefault(c['file'], []).append(c)
            for fname, items in list(by_file.items())[:3]:
                prompt_parts.append(f"### {fname}")
                for item in items[:5]:
                    prompt_parts.append(f"- `{item['key']}`: {item['value']}")
                prompt_parts.append("")
        
        # 性能热点
        if ir.perf_hotspots:
            prompt_parts.append("## 性能热点 (Performance Hotspots)")
            hot_counts = {}
            for h in ir.perf_hotspots:
                t = h.get('type', 'UNKNOWN')
                hot_counts[t] = hot_counts.get(t, 0) + 1
            prompt_parts.append(f"共 {len(ir.perf_hotspots)} 个性能问题:")
            for t, c in sorted(hot_counts.items(), key=lambda x: -x[1]):
                prompt_parts.append(f"- {t}: {c}")
            prompt_parts.append("")
            for h in ir.perf_hotspots[:20]:
                prompt_parts.append(f"- **[H:{h['severity']}]** `{h['type']}` ({h['file']}:{h['line']}): {h['detail']}")
            prompt_parts.append("")
        
        # 向后兼容
        if ir.compat_issues:
            prompt_parts.append("## 向后兼容 (Backward Compatibility)")
            comp_counts = {}
            for c in ir.compat_issues:
                t = c.get('type', 'UNKNOWN')
                comp_counts[t] = comp_counts.get(t, 0) + 1
            prompt_parts.append(f"共 {len(ir.compat_issues)} 个兼容问题:")
            for t, c in sorted(comp_counts.items(), key=lambda x: -x[1]):
                prompt_parts.append(f"- {t}: {c}")
            prompt_parts.append("")
            for c in ir.compat_issues[:20]:
                prompt_parts.append(f"- **[S:{c['severity']}]** `{c['type']}` ({c['file']}:{c['line']}): {c['detail']}")
            prompt_parts.append("")
        
        prompt_parts.append("---")
        prompt_parts.append("")
        prompt_parts.append("请基于以上信息，输出以下结构化知识：")
        prompt_parts.append("")
        prompt_parts.append("1. **架构总览** — 系统定位、技术栈、服务拆分、部署架构")
        prompt_parts.append("2. **核心业务流程** — 主要业务场景的流程描述（用文字，不需要 mermaid）")
        prompt_parts.append("3. **数据库表结构** — 表名、字段、ER 关系")
        prompt_parts.append("4. **服务层架构** — Service/DAO/Model 分层说明")
        prompt_parts.append("5. **外部系统集成** — 第三方 API、消息队列等")
        prompt_parts.append("6. **术语 Glossary** — 业务术语及其含义")
        
        return "\n".join(prompt_parts)
    
    def parse_llm_output(self, llm_response: str) -> Dict[str, Any]:
        """解析 LLM 输出的知识库 — 按标题分割"""
        knowledge = {
            "architecture": "",
            "business_flows": "",
            "database_schema": "",
            "service_architecture": "",
            "external_systems": "",
            "glossary": {},
        }
        
        section_map = {
            "架构总览": "architecture",
            "核心业务流程": "business_flows",
            "数据库表结构": "database_schema",
            "服务层架构": "service_architecture",
            "外部系统集成": "external_systems",
            "术语 Glossary": "glossary",
        }
        
        # 按 Markdown heading 级别分割：优先找 # (一级标题) 作为 section boundary
        # 因为 LLM 输出通常用 # 表示主标题，## 表示子标题
        sections = re.split(r'^# ', llm_response, flags=re.MULTILINE)
        
        for section in sections:
            for title, key in section_map.items():
                if section.startswith(title):
                    content = section[len(title):].strip()
                    if key == "glossary":
                        for line in content.split("\n"):
                            line = line.strip().lstrip("- ")
                            if ":" in line:
                                parts = line.split(":", 1)
                                knowledge[key][parts[0].strip()] = parts[1].strip()
                    else:
                        knowledge[key] = content
                    break
        
        return knowledge
    
    def auto_call_llm(self, prompt: str, knowledge_base_dir: str, 
                      dry_run: bool = False) -> Dict[str, Any]:
        """
        自动调用 LLM 生成知识库
        
        策略：
        1. 在 Hermes 环境中，通过 agent 自身调用 LLM（利用当前 session）
        2. 解析 LLM 输出，写入对应的知识文件
        3. 如果 dry_run=True，只打印 prompt 不调用
        
        注意：这个函数需要在 Hermes agent 上下文中运行，
        因为 Python 脚本本身没有 LLM API 访问权限。
        实际用法：脚本生成 prompt → 返回给 agent → agent 调用 LLM → 
        agent 把结果传回来写入文件。
        """
        if dry_run:
            return {
                "status": "dry_run",
                "prompt_length": len(prompt),
                "message": "Dry run — prompt generated, not sent to LLM",
            }
        
        # 在非 Hermes 环境下（如 CI），返回 prompt 让外部调用
        return {
            "status": "awaiting_llm",
            "prompt_length": len(prompt),
            "prompt_file": knowledge_base_dir + "/learn_prompt.md",
            "message": "LLM response expected. Write output to knowledge files.",
        }


# ============================================================================
# Knowledge Writer — 将 LLM 输出写入知识库文件
# ============================================================================

class KnowledgeWriter:
    """将解析后的知识库写入文件"""
    
    def write(self, knowledge: Dict, knowledge_base_dir: str) -> List[str]:
        """
        将知识库写入目录
        
        Returns: 写入的文件列表
        """
        kb_path = Path(knowledge_base_dir)
        kb_path.mkdir(parents=True, exist_ok=True)
        
        files_written = []
        
        # architecture.md
        if knowledge.get("architecture"):
            content = f"# 架构总览\n\n{knowledge['architecture']}\n"
            kb_path.joinpath("architecture.md").write_text(content, encoding="utf-8")
            files_written.append("architecture.md")
        
        # flows.md
        if knowledge.get("business_flows"):
            content = f"# 核心业务流程\n\n{knowledge['business_flows']}\n"
            kb_path.joinpath("flows.md").write_text(content, encoding="utf-8")
            files_written.append("flows.md")
        
        # schema.md
        if knowledge.get("database_schema"):
            content = f"# 数据库表结构\n\n{knowledge['database_schema']}\n"
            kb_path.joinpath("schema.md").write_text(content, encoding="utf-8")
            files_written.append("schema.md")
        
        # service.md
        if knowledge.get("service_architecture"):
            content = f"# 服务层架构\n\n{knowledge['service_architecture']}\n"
            kb_path.joinpath("services.md").write_text(content, encoding="utf-8")
            files_written.append("services.md")
        
        # external-systems.md
        if knowledge.get("external_systems"):
            content = f"# 外部系统集成\n\n{knowledge['external_systems']}\n"
            kb_path.joinpath("external-systems.md").write_text(content, encoding="utf-8")
            files_written.append("external-systems.md")
        
        # glossary.md
        if knowledge.get("glossary"):
            lines = ["# 术语 Glossary\n", ""]
            for key, val in sorted(knowledge["glossary"].items()):
                lines.append(f"- **{key}**: {val}")
            content = "\n".join(lines)
            kb_path.joinpath("glossary.md").write_text(content, encoding="utf-8")
            files_written.append("glossary.md")
        
        # 更新 index.md
        index = kb_path / "index.md"
        if index.exists() and index.stat().st_size > 0:
            # 追加写入状态
            content = index.read_text(encoding="utf-8")
            written_docs = "\n".join(f"| ✅ [{f}]({f}) | 已生成 |" for f in files_written)
            content = content.replace("待生成", "✅ 已生成")
            index.write_text(content, encoding="utf-8")
        
        return files_written


# ============================================================================
# Incremental Scanner — 增量扫描
# ============================================================================

class IncrementalScanner:
    """增量扫描 — 只扫描自上次以来变更的文件
    
    支持多语言：.go/.py/.java/.ts/.js 等常见源代码后缀。
    使用 SHA256 内容 hash 替代 mtime，避免时间戳抖动导致的误扫。
    """
    
    # 支持的源代码文件扩展名
    SOURCE_EXTENSIONS = {'.go', '.py', '.java', '.ts', '.js', '.rs', '.rb', '.php'}
    SKIP_DIRS = {'vendor/', '.git/', 'node_modules/', '__pycache__', '.tox', '.idea/', '.vscode/'}
    
    def __init__(self, knowledge_base_dir: str):
        self.kb_dir = Path(knowledge_base_dir)
        self.last_scan_file = self.kb_dir / ".last_scan_timestamp"
        self.hash_cache_file = self.kb_dir / ".file_hashes.json"
    
    def get_last_scan_time(self) -> Optional[float]:
        """获取上次扫描时间戳"""
        if self.last_scan_file.exists():
            return float(self.last_scan_file.read_text().strip())
        return None
    
    def set_last_scan_time(self):
        """更新上次扫描时间戳"""
        self.last_scan_file.write_text(str(time.time()), encoding="utf-8")
    
    @staticmethod
    def _compute_file_hash(file_path: Path) -> str:
        """Compute SHA256 hash of a file's content."""
        try:
            h = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            return h.hexdigest()[:16]
        except (IOError, OSError):
            return ''
    
    def load_hash_cache(self) -> Dict[str, str]:
        """Load previous file hashes from disk."""
        if self.hash_cache_file.exists():
            try:
                data = json.loads(self.hash_cache_file.read_text(encoding="utf-8"))
                return data.get("hashes", {})
            except Exception:
                pass
        return {}
    
    def save_hash_cache(self, hashes: Dict[str, str]):
        """Save current file hashes to disk."""
        self.hash_cache_file.write_text(
            json.dumps({"hashes": hashes, "timestamp": time.time()}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def _is_source_file(self, path: Path) -> bool:
        """Check if a file is a source code file we care about."""
        return path.suffix.lower() in self.SOURCE_EXTENSIONS
    
    def _should_skip(self, path: Path) -> bool:
        """Check if a file should be skipped."""
        path_str = str(path)
        return any(skip in path_str for skip in self.SKIP_DIRS)
    
    def find_changed_files(self, repo_path: Path) -> List[Path]:
        """找出自上次扫描以来变更的文件（支持多语言）
        
        策略：
        1. 首次扫描：返回所有源文件（全量扫描）
        2. 后续扫描：对比 SHA256 hash，只返回变更文件
        3. 如果 hash 计算失败，回退到 mtime 比较
        """
        last_time = self.get_last_scan_time()
        prev_hashes = self.load_hash_cache()
        
        modified = []
        current_hashes = {}
        
        # Collect all source files
        all_source_files = []
        for ext in self.SOURCE_EXTENSIONS:
            for f in repo_path.rglob(f"*{ext}"):
                if not self._should_skip(f):
                    all_source_files.append(f)
        
        for file_path in all_source_files:
            # Compute current hash
            current_hash = self._compute_file_hash(file_path)
            current_hashes[str(file_path)] = current_hash
            
            if not current_hash:
                # Hash computation failed, include for safety
                modified.append(file_path)
                continue
            
            prev_hash = prev_hashes.get(str(file_path))
            
            if prev_hash is None:
                # New file
                modified.append(file_path)
            elif prev_hash != current_hash:
                # Content changed
                modified.append(file_path)
            # else: unchanged, skip
        
        # Save current hashes for next comparison
        self.save_hash_cache(current_hashes)
        
        return modified

class WikiIngestor:
    """将 LLM 生成的知识库写入 wiki_engine"""
    
    def ingest(self, knowledge: Dict, wiki_path: Path, repo_name: str):
        """写入 wiki 页面"""
        wiki_path.mkdir(parents=True, exist_ok=True)
        
        # 生成 wiki 页面
        pages = {
            "index.md": f"# {repo_name} 知识库\n\n{knowledge.get('architecture', '')}",
            "architecture.md": f"# 架构总览\n\n{knowledge.get('architecture', '')}",
            "flows.md": f"# 核心流程\n\n{knowledge.get('business_flows', '')}",
            "schema.md": f"# 数据库表结构\n\n{knowledge.get('database_schema', '')}",
            "services.md": f"# 服务层\n\n{knowledge.get('service_architecture', '')}",
            "glossary.md": f"# 术语表\n\n" + "\n".join(f"- **{k}**: {v}" for k, v in knowledge.get("glossary", {}).items()),
        }
        
        for filename, content in pages.items():
            page_path = wiki_path / filename
            page_path.write_text(content, encoding="utf-8")
        
        return list(pages.keys())


# ============================================================================
# Main Entry Point — learn 模式
# ============================================================================

def _clean_handler(handler: str) -> str:
    """清理 handler 名称：去掉括号、receiver、不闭合的括号"""
    if not handler:
        return ""
    handler = re.sub(r'\s*\([^)]*$', '', handler)
    handler = re.sub(r'\s*\([^)]*\).*', '', handler)
    if '.' in handler:
        handler = handler.split('.')[-1]
    return handler.strip()


def learn_from_repos(profile_path: str, output_dir: str, wiki_path: Optional[str] = None,
                     knowledge_base_dir: Optional[str] = None, incremental: bool = False,
                     module_filter: Optional[str] = None, max_files: Optional[int] = None):
    """
    learn 模式主入口
    
    Args:
        profile_path: Profile JSON 文件路径
        output_dir: 临时输出目录（prompt 等）
        wiki_path: wiki_engine 路径（可选）
        knowledge_base_dir: 知识库持久化目录（可选，默认从 profile 推断）
        incremental: 是否增量扫描（只处理变更文件）
    """
    # 1. 加载 Profile
    with open(profile_path) as f:
        profile = json.load(f)
    
    # 从 profile 推断知识库目录
    if knowledge_base_dir is None:
        skill_dir = Path(__file__).parent.parent
        business_domain = profile.get("business_domain", "unknown")
        knowledge_base_dir = str(skill_dir / "knowledge" / business_domain)
    
    os.makedirs(knowledge_base_dir, exist_ok=True)
    
    repos = profile.get("repositories", [])
    if not repos:
        print("ERROR: No repositories configured in profile")
        sys.exit(1)
    
    learn_config = profile.get("learn_config", {})
    # max_files: explicit arg > profile config > dynamic estimate (no hard 500 limit)
    if max_files is not None:
        max_files = max_files
    else:
        profile_max = learn_config.get("max_files_per_lang", 0)
        if profile_max > 0:
            max_files = profile_max
        else:
            # Dynamic estimate based on actual repo size
            max_files = 2000  # fallback for backward compatibility
    
    # 2. 增量扫描准备
    incremental_scanner = None
    changed_files_by_repo = {}
    if incremental:
        incremental_scanner = IncrementalScanner(knowledge_base_dir)
        for repo in repos:
            repo_path = Path(repo["path"])
            if repo_path.exists():
                changed = incremental_scanner.find_changed_files(repo_path)
                changed_files_by_repo[repo["name"]] = changed
                if changed:
                    print(f"  📊 {repo['name']}: {len(changed)} changed files detected")
                else:
                    print(f"  📊 {repo['name']}: no changed files (full scan)")
    
    # 3. 扫描每个仓库
    all_ir = []
    for repo in repos:
        repo_path = Path(repo["path"])
        if not repo_path.exists():
            print(f"WARNING: Repository not found: {repo['path']}")
            continue
        
        language = repo.get("language", "go")
        print(f"Scanning {repo['name']} ({language}){' (incremental)' if incremental else ''}...")
        
        # 获取 scanner
        if language == "go":
            scanner = GoScanner()
        elif language == "python":
            scanner = PythonScanner()
        elif language == "java":
            scanner = JavaScanner()
        else:
            print(f"WARNING: Unsupported language: {language}, skipping")
            continue
        
        # 增量扫描：传入变更文件列表
        changed = changed_files_by_repo.get(repo["name"], [])
        ir = scanner.scan_directory(
            repo_path, 
            max_files=max_files,
            incremental=incremental,
            changed_files=changed if incremental else None,
        )
        ir.repo_name = repo["name"]
        ir.repo_path = repo["path"]
        all_ir.append(ir)
        
        print(f"  Found: {len(ir.structs)} structs, {len(ir.functions)} functions, {len(ir.routes)} routes, {len(ir.imports)} imports")
    
    if not all_ir:
        print("ERROR: No repositories scanned successfully")
        sys.exit(1)
    
    # 4. 更新扫描时间戳
    if incremental and incremental_scanner:
        incremental_scanner.set_last_scan_time()
    
    # 5. 多仓库关联分析
    analyzer = MultiRepoAnalyzer()
    dep_graph = analyzer.analyze(repos)
    print(f"Dependency graph: {len(dep_graph.get('edges', []))} edges")
    
    # 4. 构建 LLM prompt
    generator = LLMKnowledgeGenerator()
    combined_ir = all_ir[0]  # 取第一个作为主 IR
    prompt = generator.build_prompt(combined_ir, dep_graph, repos, repos[0]['path'] if repos else None)
    
    # 5. 输出 prompt（供 LLM 调用）
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    prompt_file = output_path / "learn_prompt.md"
    prompt_file.write_text(prompt, encoding="utf-8")
    
    # 存档到知识库目录
    kb_prompt_file = Path(knowledge_base_dir) / "learn_prompt.md"
    kb_prompt_file.write_text(prompt, encoding="utf-8")
    
    print(f"\nPrompt written to: {prompt_file}")
    print(f"Prompt archived to: {kb_prompt_file}")
    print(f"Knowledge base dir: {knowledge_base_dir}")
    print(f"\nRun LLM with this prompt, then save output to:")
    print(f"  {knowledge_base_dir}/architecture.md  (架构总览)")
    print(f"  {knowledge_base_dir}/flows.md         (核心流程)")
    print(f"  {knowledge_base_dir}/schema.md        (表结构)")
    print(f"  {knowledge_base_dir}/glossary.md      (术语表)")
    
    # 6. 写入知识库索引
    index_file = Path(knowledge_base_dir) / "index.md"
    if not index_file.exists() or index_file.stat().st_size == 0:
        index_content = f"# {profile.get('business_domain', 'Unknown')} 知识库\n\n"
        index_content += f"**扫描时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        index_content += f"**仓库**: {', '.join(r['name'] for r in repos)}\n\n"
        index_content += "## 文档\n\n"
        index_content += "| 文档 | 状态 |\n|------|------|\n"
        index_content += "| [architecture.md](architecture.md) | 架构总览 |\n"
        index_content += "| [flows.md](flows.md) | 核心业务流程 |\n"
        index_content += "| [schema.md](schema.md) | 数据库表结构 |\n"
        index_content += "| [services.md](services.md) | 服务层架构 |\n"
        index_content += "| [external-systems.md](external-systems.md) | 外部系统集成 |\n"
        index_content += "| [glossary.md](glossary.md) | 术语 Glossary |\n"
        index_content += "| [learn_prompt.md](learn_prompt.md) | 原始 LLM prompt |\n"
        index_file.write_text(index_content, encoding="utf-8")
        print(f"\nKnowledge index created: {index_file}")
    
    # 7. （可选）如果有 wiki_path，写入 wiki
    if wiki_path:
        # 这里需要 LLM 响应，暂时跳过
        print(f"\nNote: Wiki ingestion requires LLM response. Save prompt output first.")
    
    # 集成 code_graph_builder 图谱数据
    try:
        from code_graph_builder import CodeGraphBuilder
        print(f"  🔗 Building code graph from {all_ir[0].repo_path}...")
        builder = CodeGraphBuilder(all_ir[0].repo_name, all_ir[0].repo_path)
        graph = builder.build(lang=all_ir[0].language, max_files=max_files)
        
        # 提取图谱关键数据
        route_handler_map = []
        for edge in graph.edges:
            if edge.type == 'HANDLES':
                src = graph.find_by_id(edge.source_id)
                tgt = graph.find_by_id(edge.target_id)
                if src and tgt:
                    route_handler_map.append({
                        'route': f"{src.properties.get('http_method', '')} {src.properties.get('path', '')}",
                        'handler': tgt.name,
                        'file': tgt.file_path,
                    })
        
        call_pairs = defaultdict(int)
        for edge in graph.edges:
            if edge.type == 'CALLS':
                src = graph.find_by_id(edge.source_id)
                tgt = graph.find_by_id(edge.target_id)
                if src and tgt:
                    call_pairs[f"{src.name} → {tgt.name}"] += 1
        
        ir_cache_extra = {
            'route_handler_mappings': route_handler_map,
            'call_pairs_sample': dict(list(call_pairs.items())[:50]),
            'graph_stats': {
                'node_count': len(graph.nodes),
                'edge_count': len(graph.edges),
                'node_labels': dict(defaultdict(int, {n.label: 0 for n in graph.nodes}).__class__.__bases__[0] if False else {}),
            },
        }
        # 统计节点标签
        label_counts = defaultdict(int)
        for n in graph.nodes:
            label_counts[n.label] += 1
        ir_cache_extra['graph_stats']['node_labels'] = dict(label_counts)
        
        # 统计边类型
        edge_type_counts = defaultdict(int)
        for e in graph.edges:
            edge_type_counts[e.type] += 1
        ir_cache_extra['graph_stats']['edge_types'] = dict(edge_type_counts)
        
        print(f"  Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        print(f"  Route→Handler mappings: {len(route_handler_map)}")
    except ImportError:
        print(f"  ⚠️  code_graph_builder not available, skipping graph integration")
        ir_cache_extra = {}

    # Add flow completeness and dependency graph from CoreFlowAnalyzer
    try:
        analyzer_path = str(Path(__file__).parent / "core_flow_analyzer.py")
        spec = importlib.util.spec_from_file_location("core_flow_analyzer", analyzer_path)
        if spec and spec.loader:
            cfa_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cfa_module)
            CFA = cfa_module.CoreFlowAnalyzer
            
            ir_dict = {
                'call_graph': ir_cache.get('call_graph', []),
                'business_logic': ir_cache.get('business_logic', []),
                'routes': ir_cache.get('routes', []),
                'functions': ir_cache.get('functions', []),
                'structs': ir_cache.get('structs', []),
                'entity_tables': ir_cache.get('entity_tables', []),
                'core_flows': ir_cache.get('core_flows', []),
                'services': ir_cache.get('services', []),
            }
            
            analyzer = CFA(ir_dict)
            ir_cache_extra['flow_completeness'] = analyzer.infer_flow_completeness()
            ir_cache_extra['flow_dependency_graph'] = analyzer.build_flow_dependency_graph()
            print(f"  Flow completeness: {len(ir_cache_extra['flow_completeness'])} entities analyzed")
            fdg = ir_cache_extra['flow_dependency_graph']
            print(f"  Dependency graph: {fdg.get('node_count', 0)} nodes, {fdg.get('edge_count', 0)} edges")
    except Exception as e:
        print(f"  ⚠️  Flow completeness/dependency graph analysis failed: {e}")
        ir_cache_extra.setdefault('flow_completeness', [])
        ir_cache_extra.setdefault('flow_dependency_graph', {'nodes': [], 'edges': [], 'node_count': 0, 'edge_count': 0})

    # 启发式兜底函数
    def _generate_business_terminology_heuristic(bl_list):
        """当 LLM 不可用时，用启发式规则生成术语映射"""
        bt = {}
        handler_groups = {}
        for bl in bl_list:
            handler = bl.get('handler', '')
            if not handler:
                continue
            handler_groups[handler] = {
                'route': f"{bl.get('method', '')} {bl.get('route', '')}",
                'calls': bl.get('calls', [])[:5],
                'description': bl.get('description', ''),
            }
        
        # 基于 handler 名和调用链的启发式分组
        share_handlers = [h for h in handler_groups if 'Share' in h or 'share' in h.lower()]
        adgroup_handlers = [h for h in handler_groups if 'AdGroup' in h or 'adgroup' in h.lower()]
        requirement_handlers = [h for h in handler_groups if 'Requirement' in h or 'requirement' in h.lower()]
        
        if share_handlers:
            bt['素材分享'] = {
                'synonyms': ['share', 'partner share', 'adgroup share', '分享', 'share new', 'share add'] + [h.lower().replace('share', '') for h in share_handlers[:3]],
                'related_handlers': share_handlers,
                'related_routes': [handler_groups[h]['route'] for h in share_handlers],
                'description': '素材（广告组）分享给合作伙伴：支持新建分享、添加分享、重新发送、紧急暂停',
                'key_files': [],
            }
        if adgroup_handlers:
            bt['广告组创建'] = {
                'synonyms': ['adgroup', 'ad group', 'create adgroup', '新建广告组'] + [h.lower() for h in adgroup_handlers[:3]],
                'related_handlers': adgroup_handlers,
                'related_routes': [handler_groups[h]['route'] for h in adgroup_handlers],
                'description': '广告组管理，包括创建、编辑、删除、详情、列表',
                'key_files': [],
            }
        if requirement_handlers:
            bt['PN 处理'] = {
                'synonyms': ['requirement', 'creative requirement', 'PNS', '创意需求', 'partner requirement'] + [h.lower() for h in requirement_handlers[:3]],
                'related_handlers': requirement_handlers,
                'related_routes': [handler_groups[h]['route'] for h in requirement_handlers],
                'description': 'PNS(Partner Network Service) 创意需求管理，包括创建、删除、详情查询、列表查询',
                'key_files': [],
            }
        
        # 清理 synonyms
        for term in bt.values():
            term['synonyms'] = list(set(term['synonyms']))[:10]
        
        return bt

    # 用 LLM 从 business_logic 自动生成 business_terminology
    # 把 business_logic 喂给 LLM，让它按业务场景分组，生成中文术语映射
    business_terminology = {}
    if all_ir and all_ir[0].business_logic:
        bl_list = all_ir[0].business_logic[:30]
        
        # 构建 LLM prompt
        prompt = """你是一个代码分析专家。请根据以下 handler 的业务逻辑，按业务场景分组，生成中文业务术语映射表。

要求：
1. 把相关的 handler 归为一组，给每组起一个中文业务名（如"素材分享"、"广告组创建"）
2. 每组包含：中文业务名、相关 handler 列表、路由路径、业务描述、同义词（中英文）
3. 同义词要覆盖用户可能用的各种问法（中文业务词、英文 handler 名、路由关键词）
4. 输出格式为 JSON，key 是中文业务名，value 是术语对象

输入数据：
"""
        for bl in bl_list:
            prompt += f"- {bl.get('handler', '?')}: route={bl.get('method', '')} {bl.get('route', '')}, calls={bl.get('calls', [])[:5]}, desc={bl.get('description', '')}"
        
        prompt += """
请只输出 JSON，不要输出其他内容。格式如下：
{
  "中文业务名": {
    "synonyms": ["同义词1", "同义词2", ...],
    "related_handlers": ["Handler1", "Handler2", ...],
    "related_routes": ["POST /path1", "GET /path2", ...],
    "description": "业务描述",
    "key_files": ["file1.go", "file2.go"]
  }
}"""
        
        # 调用 LLM 生成（通过 Hermes agent context）
        try:
            # 尝试从环境变量获取 LLM API key
            llm_api_key = os.environ.get('HERMES_LLM_API_KEY', '')
            if llm_api_key:
                # 调用 LLM API
                
                payload = json.dumps({
                    "model": "agnes-2.0-flash",
                    "messages": [
                        {"role": "system", "content": "你是一个代码分析专家。请根据 handler 列表按业务场景分组，生成中文业务术语映射表。只输出 JSON，不要输出其他内容。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                }).encode('utf-8')
                
                req = urllib.request.Request(
                    'https://apihub.agnes-ai.com/v1/chat/completions',
                    data=payload,
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {llm_api_key}',
                    }
                )
                
                with urllib.request.urlopen(req, timeout=60) as resp:
                    llm_response = json.loads(resp.read().decode('utf-8'))
                    llm_text = llm_response['choices'][0]['message']['content']
                    
                    # 提取 JSON
                    json_match = re.search(r'\{.*\}', llm_text, re.DOTALL)
                    if json_match:
                        business_terminology = json.loads(json_match.group(0))
                        print(f"  LLM generated {len(business_terminology)} business terminology entries")
                    else:
                        print(f"  LLM response didn't contain valid JSON")
            else:
                # 没有 LLM API key，用启发式规则兜底
                print(f"  No LLM API key, using heuristic fallback")
                business_terminology = _generate_business_terminology_heuristic(bl_list)
        except Exception as e:
            print(f"  LLM generation failed ({e}), using heuristic fallback")
            business_terminology = _generate_business_terminology_heuristic(bl_list)
    

    
    # 保存 IR 缓存（供 query_evidence 复用）
    # 合并多仓库数据
    all_packages = {}
    all_flow = {}
    all_structs = []
    all_functions = []
    all_routes = []
    all_business_logic = []
    
    for ir in all_ir:
        # 包结构
        if hasattr(ir, 'packages') and ir.packages:
            for pkg_name, pkg_data in ir.packages.items():
                all_packages[pkg_name] = pkg_data
        
        # 流程
        if hasattr(ir, 'flow') and ir.flow:
            all_flow.update(ir.flow)
        
        # 其他数据（取前 100 个）
        all_structs.extend([asdict(s) for s in ir.structs[:50]])
        all_functions.extend([asdict(f) for f in ir.functions[:100]])
        all_routes.extend([{
            "path": r.path if hasattr(r, 'path') else r.get('path', ''),
            "method": r.method if hasattr(r, 'method') else r.get('method', ''),
            "handler": _clean_handler(r.handler) if hasattr(r, 'handler') else r.get('handler', ''),
            "module": r.module if hasattr(r, 'module') else r.get('module', ''),
        } for r in ir.routes[:50]])
        all_business_logic.extend(ir.business_logic[:10])
    
    ir_cache = {
        "repo_name": ", ".join(ir.repo_name for ir in all_ir),
        "repo_path": ", ".join(ir.repo_path for ir in all_ir),
        "language": all_ir[0].language if all_ir else "",
        "structs": all_structs[:100],
        "functions": all_functions[:100],
        "routes": all_routes[:100],
        "tables": [],
        "entity_tables": [],
        "sql_operations": [],
        "error_codes": [],
        "auth_models": [],
        "test_coverage": {
            "test_files": sum(len(ir.test_files) for ir in all_ir),
            "test_functions": sum(len(ir.test_functions) for ir in all_ir),
            "coverage_pct": sum(ir.coverage_report.get('coverage_pct', 0) for ir in all_ir) / len(all_ir) if all_ir else 0,
        },
        "business_logic": all_business_logic[:20],
        "business_terminology": business_terminology,
        "packages": all_packages,
        "flow": all_flow,
    }
    # 合并图谱数据到 IR 缓存
    ir_cache.update(ir_cache_extra)
    
    ir_cache_file = Path(knowledge_base_dir) / "ir_cache.json"
    ir_cache_file.write_text(json.dumps(ir_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  💾 IR cache saved to: {ir_cache_file}")
    
    # 生成 business_cards.json
    try:
        from llm_analyzer import LLMAnalyzer
        analyzer = LLMAnalyzer(ir_cache.get('repo_path', ''), str(ir_cache_file))
        cards = analyzer.generate_business_cards(str(Path(knowledge_base_dir) / 'business_cards.json'))
        llm_count = len(cards.get("llm_analyses", []))
        sc = len(cards.get("scenario_cards", []))
        la = len(cards.get("llm_analyses", []))
        er = len(cards.get("entity_relationships", []))
        ec = len(cards.get("error_categories", {}))
        print(f"  Business cards: {sc} scenarios, {la} LLM analyses, {er} entities, {ec} error categories")
    except Exception as e:
        print(f"  ⚠️  Failed to generate business cards: {e}")
    
    # 生成增强版知识摘要
    try:
        summary = _generate_enhanced_summary(ir_cache, knowledge_base_dir)
        print(f"  📝 Summary generated: {len(summary)} chars")
    except Exception as e:
        print(f"  WARNING: Summary generation failed ({e})")
    
    # 代码质量检查
    try:
        quality = _check_code_quality(ir_cache)
        print(f"  📊 Code quality: {quality}")
    except Exception as e:
        print(f"  WARNING: Quality check failed ({e})")
    
    # 生成文档包（architecture.md, flows.md, schema.md, glossary.md）
    try:
        from _generate_docs import generate_docs
        generate_docs(ir_cache, knowledge_base_dir)
        print(f"  📄 Docs generated")
    except Exception as e:
        print(f"  WARNING: Doc generation failed ({e})")
    
    return {
        "status": "ok",
        "repos_scanned": len(all_ir),
        "prompt_file": str(prompt_file),
        "kb_prompt_file": str(kb_prompt_file),
        "knowledge_base_dir": knowledge_base_dir,
        "output_dir": str(output_path),
        "ir_cache_file": str(ir_cache_file),
    }


def main():
    parser = argparse.ArgumentParser(description="Learn from code repositories")
    parser.add_argument("--profile", required=True, help="Profile JSON path")
    parser.add_argument("--output-dir", required=True, help="Knowledge output directory")
    parser.add_argument("--wiki-path", help="Wiki engine path for ingestion")
    parser.add_argument("--llm-response", help="LLM response text (file path or raw text via stdin)")
    parser.add_argument("--auto-llm", action="store_true", help="Auto-call LLM (requires Hermes agent context)")
    parser.add_argument("--incremental", action="store_true", help="Incremental scan (only changed files)")
    parser.add_argument("--dry-run", action="store_true", help="Just generate prompt, don't write anything")
    args = parser.parse_args()
    
    result = learn_from_repos(
        profile_path=args.profile,
        output_dir=args.output_dir,
        wiki_path=args.wiki_path,
        incremental=args.incremental,
    )
    
    if result["status"] != "ok":
        print(f"\n❌ Learn failed: {result.get('reason', 'unknown')}")
        sys.exit(1)
    
    kb_dir = result["knowledge_base_dir"]
    prompt_file = Path(kb_dir) / "learn_prompt.md"
    
    if args.dry_run:
        print(f"\n📝 Dry run complete. Prompt saved to: {prompt_file}")
        print(f"   Copy and send to LLM, then save response to knowledge files.")
        return
    
    # 如果有 LLM 响应，解析并写入
    if args.llm_response:
        print(f"\n📥 Processing LLM response from: {args.llm_response}")
        
        # 读取 LLM 响应
        if os.path.isfile(args.llm_response):
            llm_text = Path(args.llm_response).read_text(encoding="utf-8")
        else:
            llm_text = args.llm_response
        
        # 解析
        generator = LLMKnowledgeGenerator()
        knowledge = generator.parse_llm_output(llm_text)
        
        # 写入
        writer = KnowledgeWriter()
        files = writer.write(knowledge, kb_dir)
        
        print(f"✅ Knowledge files written: {', '.join(files)}")
        print(f"   Directory: {kb_dir}")
        return
    
    # 如果没有 LLM 响应，提示用户
    print(f"\n✅ Learn complete!")
    print(f"   Prompt: {prompt_file}")
    print(f"   IR Cache: {result.get('ir_cache_file', 'N/A')}")
    print(f"   Knowledge base: {kb_dir}")
    print(f"\n📋 Next step: Send prompt to LLM, then run again with --llm-response")
    print(f"   Example:")
    print(f"     # 1. 读取 prompt")
    print(f"     cat {prompt_file}")
    print(f"     # 2. 发给 LLM，保存响应到 /tmp/llm_response.txt")
    print(f"     # 3. 写入知识库")
    print(f"     python3 learn_repo.py --profile {args.profile} --llm-response /tmp/llm_response.txt")


if __name__ == "__main__":
    main()


# ============================================================================
# 知识库缓存机制
# ============================================================================

class KnowledgeCache:
    """知识库缓存 — 避免重复扫描"""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / 'kb_cache.json'
        self.cache = self._load_cache()
    
    def _load_cache(self) -> dict:
        """加载缓存"""
        if self.cache_file.exists():
            try:
                return json.load(open(self.cache_file))
            except Exception:
                return {}
        return {}
    
    def _save_cache(self):
        """保存缓存"""
        self.cache_file.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding='utf-8')
    
    def get(self, key: str, default=None):
        """获取缓存"""
        return self.cache.get(key, default)
    
    def set(self, key: str, value: dict, ttl: int = 3600):
        """设置缓存"""
        self.cache[key] = {
            'data': value,
            'timestamp': time.time(),
            'ttl': ttl,
        }
        self._save_cache()
    
    def is_expired(self, key: str) -> bool:
        """检查是否过期"""
        entry = self.cache.get(key)
        if not entry:
            return True
        return time.time() - entry.get('timestamp', 0) > entry.get('ttl', 3600)
    
    def invalidate(self, key: str):
        """失效缓存"""
        if key in self.cache:
            del self.cache[key]
            self._save_cache()


def generate_kb_cache(kb_base: str, cache_dir: str) -> dict:
    """生成知识库缓存 — 提取文件索引和关键词"""
    cache = KnowledgeCache(cache_dir)
    
    if cache.is_expired('kb_index'):
        kb_path = Path(kb_base)
        if not kb_path.exists():
            return {}
        
        index = {}
        md_files = list(kb_path.rglob('**/*.md'))
        for md_file in md_files[:100]:  # 限制数量
            try:
                content = md_file.read_text(encoding='utf-8', errors='ignore')
                # 提取关键词
                keywords = re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z]{2,}', content.lower())
                keywords = list(set(keywords))
                
                rel_path = str(md_file.relative_to(kb_path.parent))
                index[rel_path] = {
                    'keywords': keywords[:20],
                    'lines': len(content.split('\n')),
                }
            except Exception:
                continue
        
        cache.set('kb_index', index)
    
    return cache.get('kb_index', {})


def _check_code_quality(ir: dict) -> str:
    """从代码扫描结果推断代码质量"""
    issues = []
    
    # 1. 测试覆盖率
    test_cov = ir.get('test_coverage', {})
    if test_cov.get('coverage_pct', 0) < 30:
        issues.append("⚠️ 测试覆盖率低 (< 30%)")
    elif test_cov.get('coverage_pct', 0) < 60:
        issues.append("🟡 测试覆盖率中等 (30-60%)")
    else:
        issues.append("✅ 测试覆盖率高 (> 60%)")
    
    # 2. 错误码数量
    error_codes = ir.get('error_codes', [])
    if len(error_codes) < 10:
        issues.append("⚠️ 错误码定义少 (< 10)")
    else:
        issues.append(f"✅ 错误码定义充足 ({len(error_codes)} 个)")
    
    # 3. 文档注释
    structs = ir.get('structs', [])
    has_comments = sum(1 for s in structs if s.get('comments'))
    if has_comments < len(structs) * 0.5:
        issues.append("⚠️ 文档注释不足")
    else:
        issues.append("✅ 文档注释良好")
    
    return "; ".join(issues)
