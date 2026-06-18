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
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


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
        """用 ripgrep 批量扫描 — 核心加速路径"""
        ir = IRDocument(
            repo_name=dir_path.name,
            repo_path=str(dir_path),
            language="go",
        )
        
        exclude_args = ["--glob", "!vendor/**", "--glob", "!**/.git/**", "--glob", "!**/_test.go"]
        
        # 1. 扫描 struct 定义
        try:
            r = subprocess.run(
                ["rg", "--json", "--type", "go", "-n",
                 r"type\s+(\w+)\s+struct\s*\{"] + exclude_args + [str(dir_path)],
                capture_output=True, text=True, timeout=120
            )
            if r.returncode in (0, 1):  # 0=found, 1=no match
                self._parse_rg_structs(r.stdout, ir, dir_path, max_files)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 2. 扫描 TableName
        try:
            r = subprocess.run(
                ["rg", "--json", "--type", "go", "-n",
                 r'func\s+\(\s*\*\w+\)\s+TableName\(\)\s+string'] + exclude_args + [str(dir_path)],
                capture_output=True, text=True, timeout=120
            )
            if r.returncode in (0, 1):
                self._parse_rg_table_names(r.stdout, ir)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 3. 扫描 method signatures
        try:
            r = subprocess.run(
                ["rg", "--json", "--type", "go", "-n",
                 r'func\s+\(\s*\*?\w+\)\s+\w+\s*\('] + exclude_args + [str(dir_path)],
                capture_output=True, text=True, timeout=120
            )
            if r.returncode in (0, 1):
                self._parse_rg_methods(r.stdout, ir, dir_path, max_files)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 4. 扫描 top-level func
        try:
            r = subprocess.run(
                ["rg", "--json", "--type", "go", "-n",
                 r'^func\s+\w+\s*\('] + exclude_args + [str(dir_path)],
                capture_output=True, text=True, timeout=120
            )
            if r.returncode in (0, 1):
                self._parse_rg_top_funcs(r.stdout, ir, dir_path, max_files)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 5. 扫描 routes
        try:
            r = subprocess.run(
                ["rg", "--json", "--type", "go", "-n",
                 r'(?:r|group|engine)\.(GET|POST|PUT|DELETE|PATCH)\s*\(\s*"([^"]+)"'] + exclude_args + [str(dir_path)],
                capture_output=True, text=True, timeout=120
            )
            if r.returncode in (0, 1):
                self._parse_rg_routes(r.stdout, ir, dir_path, max_files)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 6. 扫描 imports
        try:
            r = subprocess.run(
                ["rg", "--json", "--type", "go", "-n",
                 r'"([^"]+)"'] + exclude_args + [str(dir_path)],
                capture_output=True, text=True, timeout=120
            )
            if r.returncode in (0, 1):
                self._parse_rg_imports(r.stdout, ir, dir_path, max_files)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 7. 扫描 struct 字段（用 rg -A 获取 struct body 上下文）
        try:
            r = subprocess.run(
                ["rg", "--json", "--type", "go", "-A", "30", "-n",
                 r'type\s+\w+\s+struct\s*\{'] + exclude_args + [str(dir_path)],
                capture_output=True, text=True, timeout=180
            )
            if r.returncode in (0, 1):
                self._parse_rg_struct_fields(r.stdout, ir, dir_path, max_files)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 构建调用图和入口点（测试扫描和 API 文档提取在 scan_directory 中统一调用）
        self._build_call_graph_from_signatures(ir)
        
        # 提取 SQL/GORM 操作
        self._extract_sql_operations(ir, dir_path, max_files)
        
        # 提取错误码定义
        self._extract_error_codes(ir, dir_path, max_files)
        
        return ir
    
    def _parse_rg_json_lines(self, output: str) -> Dict[str, List[Dict]]:
        """解析 rg --json 输出，按文件分组
        同时接受 match 和 context 类型（-A 上下文行）
        """
        by_file = {}
        for line in output.strip().split('\n'):
            if not line.strip():
                continue
            # rg --json 输出的 lines.text 可能包含换行符，导致 json.loads 失败
            cleaned = line.replace('\\n', ' ').replace('\\t', ' ')
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                continue
            # 接受 match 和 context 两种类型
            data_type = data.get("type")
            if data_type not in ("match", "context"):
                continue
            raw = data.get("data", {})
            file_path = raw.get("path", {}).get("text", "")
            line_num = raw.get("line_number", 0)
            line_text = raw.get("lines", {}).get("text", "").strip()
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
                
                # 匹配 type XXX struct
                m = re.search(r'type\s+(\w+)\s+struct', text)
                if m:
                    struct_stack.append((m.group(1), []))
                    continue
                
                # 匹配字段行: FieldName Type `tag`
                if struct_stack:
                    field_m = re.search(r'^\s+(\w+)\s+(\S+?)(?:\s+`(.+)`)?\s*$', text)
                    if field_m and field_m.group(1) not in ('type', 'func', 'var', 'const'):
                        tag = field_m.group(3) or ""
                        field = {"name": field_m.group(1), "type": field_m.group(2)}
                        gorm = re.search(r'gorm:"([^"]*)"', tag)
                        json = re.search(r'json:"([^"]*)"', tag)
                        if gorm:
                            field["gorm_tag"] = gorm.group(1)
                        if json:
                            field["json_tag"] = json.group(1)
                        struct_stack[-1][1].append(field)
            
            # 将提取的字段写入 IR
            for struct_name, fields in struct_stack:
                for s in ir.structs:
                    if s.name == struct_name and s.file == str(rel_path):
                        s.fields = fields[:30]
                        break

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
    
    def scan_directory(self, dir_path: Path, max_files: int = 500,
                       incremental: bool = False, changed_files: List[Path] = None) -> IRDocument:
        """扫描整个目录"""
        # 优先用 ripgrep，不可用时 fallback 到 Python re
        if self.use_ripgrep and self._is_rgrep_available():
            try:
                ir = self._scan_with_rgrep(dir_path, max_files)
            except Exception as e:
                print(f"  WARNING: ripgrep scan failed ({e}), falling back to Python re", file=sys.stderr)
                ir = self._scan_with_python_re(dir_path, max_files, incremental, changed_files)
        else:
            ir = self._scan_with_python_re(dir_path, max_files, incremental, changed_files)
        
        # 统一调用测试扫描和 API 文档提取（不依赖 rg 可用性）
        self._scan_test_files(ir, dir_path, max_files)
        self._extract_api_spec(ir, dir_path, max_files)
        
        return ir
    
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
        self._build_call_graph_from_signatures(ir)
        
        # 提取 API 文档（OpenAPI-like spec）
        self._extract_api_spec(ir, dir_path, max_files)
        
        # 提取权限/鉴权模型
        self._extract_auth_models(ir, dir_path, max_files)
        
        # 提取 SQL/GORM 操作
        self._extract_sql_operations(ir, dir_path, max_files)
        
        # 提取错误码定义
        self._extract_error_codes(ir, dir_path, max_files)
        
        return ir
    
    def _build_call_graph_from_signatures(self, ir: IRDocument):
        """从函数签名和 import 构建调用图（简化版）
        
        策略：
        1. 从 func 签名中识别 Handler 方法
        2. 从 import 中识别跨包调用
        3. 从 func 名中识别常见调用模式（如 service.xxx, dao.xxx）
        """
        # 构建函数名 → 文件映射
        func_to_file = {}
        for f in ir.functions:
            key = f.name
            if key not in func_to_file:
                func_to_file[key] = []
            func_to_file[key].append(f.file)
        
        # 从 import 推断跨包调用
        for imp in ir.imports:
            if imp.is_local:
                # 本地包导入 → 可能调用该包中的函数
                pkg_name = imp.module.split('/')[-1]  # 取最后一层包名
                for func_name in func_to_file:
                    # 如果函数名以包名开头，说明是包级调用
                    if func_name.startswith(pkg_name + '.') or func_name.startswith(pkg_name + '_'):
                        ir.call_graph.append(CallEdge(
                            caller="unknown",
                            caller_pkg="",
                            callee=func_name,
                            callee_pkg=imp.module,
                            pos="",
                        ))
        
        # 从函数名模式推断调用关系
        call_patterns = [
            (r'service\.', 'service'),
            (r'dao\.', 'dao'),
            (r'model\.', 'model'),
            (r'util\.', 'util'),
            (r'handler\.', 'handler'),
        ]
        for pattern, category in call_patterns:
            for f in ir.functions:
                if re.search(pattern, f.name):
                    # 这类函数通常是 service/dao 层调用
                    pass  # 已在函数名中体现
        
        # 识别入口点（Handler 方法和 main 函数）
        for f in ir.functions:
            if f.is_route or f.name in ('main', 'Run', 'Start', 'Serve'):
                ir.entry_points.append({
                    "name": f.name,
                    "file": f.file,
                    "type": "handler" if f.is_route else "entry",
                })


    def _scan_test_files(self, ir: IRDocument, dir_path: Path, max_files: int):
        """扫描测试文件 — 提取测试函数、被测函数、覆盖率报告"""
        # 1. 找测试文件（用 find 命令，rg --files-with-matches 搜的是文件内容不是文件名）
        try:
            r = subprocess.run(
                ["find", str(dir_path), "-name", "*_test.go", "-not", "-path", "*/vendor/*"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                test_files = [f.strip() for f in r.stdout.strip().split('\n') if f.strip()]
                ir.test_files = test_files[:max_files]
        except:
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
                except:
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
            except:
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
                except:
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
            except:
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
        except:
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
            except:
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
                            
            except:
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
        except:
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
            except:
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
            except:
                middleware_dirs = []
        else:
            middleware_dirs = [str(middleware_dir)]
        
        for mw_dir in middleware_dirs[:3]:
            try:
                mw_files = list(Path(mw_dir).rglob("*.go"))
            except:
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
                except:
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
    
    def _build_call_graph_from_signatures(self, ir: IRDocument):
        """从 import + func 签名构建调用图"""


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
                        except:
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
                except:
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
                except:
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
        
        import ast
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
    
    def scan_directory(self, dir_path: Path, max_files: int = 500,
                       incremental: bool = False, changed_files: List[Path] = None) -> IRDocument:
        """扫描整个目录"""
        ir = IRDocument(
            repo_name=dir_path.name,
            repo_path=str(dir_path),
            language="python",
        )
        
        count = 0
        py_files = sorted(dir_path.rglob("*.py"))
        
        for py_file in py_files:
            if count >= max_files:
                break
            if "__pycache__" in str(py_file) or ".git" in str(py_file):
                continue
            
            # 增量扫描
            if incremental and changed_files is not None:
                if py_file not in changed_files:
                    continue
            
            try:
                result = self.scan_file(py_file)
                count += 1
                
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
    
    def scan_directory(self, dir_path: Path, max_files: int = 500,
                       incremental: bool = False, changed_files: List[Path] = None) -> IRDocument:
        """扫描整个目录"""
        ir = IRDocument(
            repo_name=dir_path.name,
            repo_path=str(dir_path),
            language="java",
        )
        
        count = 0
        java_files = sorted(dir_path.rglob("*.java"))
        
        for java_file in java_files:
            if count >= max_files:
                break
            if "target/" in str(java_file) or ".git" in str(java_file):
                continue
            
            if incremental and changed_files is not None:
                if java_file not in changed_files:
                    continue
            
            try:
                result = self.scan_file(java_file)
                count += 1
                
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
                callee_groups.setdefault(edge.callee, []).append(edge)
            for callee, edges in list(callee_groups.items())[:20]:
                callers = list(set(e.caller for e in edges if e.caller))
                prompt_parts.append(f"- **{callee}** ← called by: {', '.join(callers[:5])}")
            prompt_parts.append("")
        
        if ir.entry_points:
            prompt_parts.append("## 入口点 (Entry Points)")
            for ep in ir.entry_points[:20]:
                prompt_parts.append(f"- [{ep['type']}] **{ep['name']}** @ {ep['file']}")
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
    """增量扫描 — 只扫描自上次以来变更的文件"""
    
    def __init__(self, knowledge_base_dir: str):
        self.kb_dir = Path(knowledge_base_dir)
        self.last_scan_file = self.kb_dir / ".last_scan_timestamp"
    
    def get_last_scan_time(self) -> Optional[float]:
        """获取上次扫描时间戳"""
        if self.last_scan_file.exists():
            return float(self.last_scan_file.read_text().strip())
        return None
    
    def set_last_scan_time(self):
        """更新上次扫描时间戳"""
        self.last_scan_file.write_text(str(time.time()), encoding="utf-8")
    
    def find_changed_files(self, repo_path: Path) -> List[Path]:
        """找出自上次扫描以来变更的文件"""
        last_time = self.get_last_scan_time()
        if last_time is None:
            return []  # 首次扫描，返回空表示全量扫
        
        modified = []
        for go_file in repo_path.rglob("*.go"):
            if "vendor/" in str(go_file) or ".git/" in str(go_file):
                continue
            mtime = go_file.stat().st_mtime
            if mtime > last_time:
                modified.append(go_file)
        
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

def learn_from_repos(profile_path: str, output_dir: str, wiki_path: Optional[str] = None, 
                     knowledge_base_dir: Optional[str] = None, incremental: bool = False):
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
    max_files = learn_config.get("max_files_per_lang", 500)
    
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
    
    return {
        "status": "ok",
        "repos_scanned": len(all_ir),
        "prompt_file": str(prompt_file),
        "kb_prompt_file": str(kb_prompt_file),
        "knowledge_base_dir": knowledge_base_dir,
        "output_dir": str(output_path),
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
