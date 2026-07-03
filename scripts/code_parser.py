#!/usr/bin/env python3
"""
Unified Code Parser — 统一代码解析引擎

设计原则：
1. 语言无关的接口：extract_file, extract_routes, extract_calls, extract_data_flow
2. 每种语言一个实现（GoScanner, PythonASTExtractor, JavaScanner）
3. 上层按需调用，不重复实现

使用场景：
- learn_repo.py: 批量扫描，生成 IR 缓存
- query_evidence.py: 按需查询，搜索特定函数/路由/表
- review_engine/td_engine/test_engine: 注入代码证据

架构：
  CodeParser (抽象接口)
  ├── GoScanner (Go 语言，基于 ripgrep + 正则)
  ├── PythonASTExtractor (Python，基于 ast 模块)
  └── JavaScanner (Java，基于 tree-sitter)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any


# ============================================================================
# 统一数据模型（所有语言共用）
# ============================================================================

@dataclass
class CodeLocation:
    """代码位置"""
    file: str
    line: int
    end_line: int = 0


@dataclass
class CodeFunction:
    """函数/方法定义"""
    name: str
    file: str
    line: int
    params: List[Dict] = field(default_factory=list)
    returns: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    is_method: bool = False
    receiver: Optional[str] = None  # Go method receiver
    signature: str = ""  # 完整签名


@dataclass
class CodeStruct:
    """结构体/类定义"""
    name: str
    file: str
    line: int
    fields: List[Dict] = field(default_factory=list)
    methods: List[Dict] = field(default_factory=list)
    table_name: Optional[str] = None  # Go GORM TableName


@dataclass
class CodeRoute:
    """HTTP 路由"""
    path: str
    method: str  # GET/POST/PUT/DELETE
    handler: str  # 处理函数名
    file: str
    line: int
    middleware: List[str] = field(default_factory=list)


@dataclass
class CodeCall:
    """函数调用"""
    callee: str
    file: str
    line: int
    args: List[str] = field(default_factory=list)
    prefix: Optional[str] = None  # 如 dao., util., service.


@dataclass
class CodeTable:
    """数据库表"""
    entity: str
    table: str
    file: str
    fields: List[Dict] = field(default_factory=list)


@dataclass
class CodeImport:
    """导入语句"""
    module: str
    names: List[str] = field(default_factory=list)
    is_local: bool = False


@dataclass
class CodeError:
    """错误码"""
    name: str
    code: str
    message: str
    category: str = ""


@dataclass
class CodeAuth:
    """鉴权模型"""
    middleware: str
    file: str
    logic: str
    protected_routes: List[str] = field(default_factory=list)


@dataclass
class ParseResult:
    """统一解析结果"""
    language: str
    repo_path: str
    
    functions: List[CodeFunction] = field(default_factory=list)
    structs: List[CodeStruct] = field(default_factory=list)
    routes: List[CodeRoute] = field(default_factory=list)
    tables: List[CodeTable] = field(default_factory=list)
    imports: List[CodeImport] = field(default_factory=list)
    errors: List[CodeError] = field(default_factory=list)
    auth_models: List[CodeAuth] = field(default_factory=list)
    
    # 调用关系
    calls: List[CodeCall] = field(default_factory=list)
    call_graph: List[Dict] = field(default_factory=list)  # {caller, callee, file, line}
    
    # 数据流
    data_flow: List[Dict] = field(default_factory=list)  # {var, definition, uses}
    
    # 元数据
    total_files: int = 0
    total_lines: int = 0


# ============================================================================
# 抽象基类
# ============================================================================

class CodeParser(ABC):
    """代码解析器抽象基类"""
    
    @abstractmethod
    def parse_file(self, file_path: Path) -> Optional[ParseResult]:
        """解析单个文件"""
        pass
    
    @abstractmethod
    def parse_directory(self, dir_path: Path, max_files: int = 500) -> ParseResult:
        """解析整个目录"""
        pass
    
    @abstractmethod
    def extract_routes(self, dir_path: Path, max_files: int = 500) -> List[CodeRoute]:
        """提取 HTTP 路由"""
        pass
    
    @abstractmethod
    def extract_calls(self, dir_path: Path, max_files: int = 500) -> List[CodeCall]:
        """提取函数调用"""
        pass
    
    @abstractmethod
    def extract_tables(self, dir_path: Path, max_files: int = 500) -> List[CodeTable]:
        """提取数据库表"""
        pass
    
    @abstractmethod
    def extract_error_codes(self, dir_path: Path, max_files: int = 500) -> List[CodeError]:
        """提取错误码"""
        pass
    
    @abstractmethod
    def extract_auth_models(self, dir_path: Path, max_files: int = 500) -> List[CodeAuth]:
        """提取鉴权模型"""
        pass
    
    @abstractmethod
    def extract_call_graph(self, dir_path: Path, max_files: int = 500) -> List[Dict]:
        """提取调用图"""
        pass


# ============================================================================
# Go 解析器（基于 ripgrep + 正则）
# ============================================================================

class GoScanner(CodeParser):
    """Go 代码扫描器 — 基于 ripgrep + 正则"""
    
    def __init__(self, use_ripgrep: bool = True):
        self.use_ripgrep = use_ripgrep
        self._rg_available = self._check_rgrep()
    
    def _check_rgrep(self) -> bool:
        import subprocess
        try:
            subprocess.run(['rg', '--version'], capture_output=True, timeout=5)
            return True
        except:
            return False
    
    def parse_file(self, file_path: Path) -> Optional[ParseResult]:
        """解析单个 Go 文件"""
        # TODO: 实现单文件解析
        return None
    
    def parse_directory(self, dir_path: Path, max_files: int = 500) -> ParseResult:
        """解析整个 Go 项目"""
        # 委托给 GoScanner.scan_directory
        from learn_repo import GoScanner as LegacyGoScanner
        scanner = LegacyGoScanner()
        ir = scanner.scan_directory(dir_path, max_files=max_files)
        
        # 转换为统一格式
        result = ParseResult(
            language='go',
            repo_path=str(dir_path),
            total_files=len(ir.structs) + len(ir.functions),
            total_lines=0,
        )
        
        # 转换 structs
        for s in ir.structs[:100]:
            result.structs.append(CodeStruct(
                name=s.name,
                file=s.file,
                line=s.lines[0] if s.lines else 0,
                fields=s.fields[:10],
                table_name=s.table_name,
            ))
        
        # 转换 functions
        for f in ir.functions[:100]:
            result.functions.append(CodeFunction(
                name=f.name,
                file=f.file,
                line=f.lines[0] if f.lines else 0,
                params=f.params,
                returns=f.returns,
                is_method=f.is_route,
            ))
        
        # 转换 routes
        for r in ir.routes[:100]:
            result.routes.append(CodeRoute(
                path=r.path,
                method=r.method,
                handler=r.handler,
                file=getattr(r, 'file', ''),
                line=0,
            ))
        
        # 转换 tables
        for t in ir.entity_tables[:50]:
            result.tables.append(CodeTable(
                entity=t.get('entity', ''),
                table=t.get('table', ''),
                file=t.get('file', ''),
            ))
        
        # 转换 error_codes
        for e in ir.error_codes[:100]:
            result.errors.append(CodeError(
                name=e.get('name', ''),
                code=e.get('code', ''),
                message=e.get('message', ''),
                category=e.get('category', ''),
            ))
        
        # 转换 auth_models
        for a in ir.auth_models[:20]:
            result.auth_models.append(CodeAuth(
                middleware=a.get('middleware', ''),
                file=a.get('file', ''),
                logic=a.get('logic', ''),
                protected_routes=a.get('protected_routes', []),
            ))
        
        return result
    
    def extract_routes(self, dir_path: Path, max_files: int = 500) -> List[CodeRoute]:
        from learn_repo import GoScanner as LegacyGoScanner
        scanner = LegacyGoScanner()
        ir = scanner.scan_directory(dir_path, max_files=max_files)
        return [CodeRoute(
            path=r.path, method=r.method, handler=r.handler,
            file=getattr(r, 'file', ''), line=0
        ) for r in ir.routes[:max_files]]
    
    def extract_calls(self, dir_path: Path, max_files: int = 500) -> List[CodeCall]:
        """提取函数调用关系"""
        from learn_repo import GoScanner as LegacyGoScanner
        scanner = LegacyGoScanner()
        ir = scanner.scan_directory(dir_path, max_files=max_files)
        
        calls = []
        for bl in ir.business_logic[:max_files]:
            for call in bl.get('call_tree', []):
                calls.append(CodeCall(
                    callee=call['name'],
                    file=call.get('file', ''),
                    line=0,
                    prefix=self._guess_prefix(call['name']),
                ))
        return calls
    
    def _guess_prefix(self, func_name: str) -> Optional[str]:
        """根据函数名猜测前缀"""
        if 'dao' in func_name.lower():
            return 'dao.'
        if 'util' in func_name.lower():
            return 'util.'
        if 'service' in func_name.lower():
            return 'service.'
        return None
    
    def extract_tables(self, dir_path: Path, max_files: int = 500) -> List[CodeTable]:
        from learn_repo import GoScanner as LegacyGoScanner
        scanner = LegacyGoScanner()
        ir = scanner.scan_directory(dir_path, max_files=max_files)
        return [CodeTable(
            entity=t.get('entity', ''), table=t.get('table', ''),
            file=t.get('file', '')
        ) for t in ir.entity_tables[:max_files]]
    
    def extract_error_codes(self, dir_path: Path, max_files: int = 500) -> List[CodeError]:
        from learn_repo import GoScanner as LegacyGoScanner
        scanner = LegacyGoScanner()
        ir = scanner.scan_directory(dir_path, max_files=max_files)
        return [CodeError(
            name=e.get('name', ''), code=e.get('code', ''),
            message=e.get('message', ''), category=e.get('category', '')
        ) for e in ir.error_codes[:max_files]]
    
    def extract_auth_models(self, dir_path: Path, max_files: int = 500) -> List[CodeAuth]:
        from learn_repo import GoScanner as LegacyGoScanner
        scanner = LegacyGoScanner()
        ir = scanner.scan_directory(dir_path, max_files=max_files)
        return [CodeAuth(
            middleware=a.get('middleware', ''), file=a.get('file', ''),
            logic=a.get('logic', ''), protected_routes=a.get('protected_routes', [])
        ) for a in ir.auth_models[:max_files]]
    
    def extract_call_graph(self, dir_path: Path, max_files: int = 500) -> List[Dict]:
        """提取调用图"""
        from learn_repo import GoScanner as LegacyGoScanner
        scanner = LegacyGoScanner()
        ir = scanner.scan_directory(dir_path, max_files=max_files)
        
        edges = []
        for bl in ir.business_logic[:max_files]:
            caller = bl.get('handler', '')
            for call in bl.get('call_tree', []):
                callee = call['name']
                edges.append({
                    'caller': caller,
                    'callee': callee,
                    'caller_file': bl.get('file', ''),
                    'callee_file': call.get('file', ''),
                })
                # 递归子调用
                for sub in call.get('calls', []):
                    edges.append({
                        'caller': callee,
                        'callee': sub,
                        'caller_file': call.get('file', ''),
                        'callee_file': '',
                    })
        return edges


# ============================================================================
# Python 解析器（基于 ast 模块）
# ============================================================================

class PythonASTExtractor(CodeParser):
    """Python 代码解析器 — 基于 ast 模块"""
    
    def parse_directory(self, dir_path: Path, max_files: int = 500) -> ParseResult:
        import ast
        result = ParseResult(language='python', repo_path=str(dir_path))
        
        py_files = list(dir_path.rglob('*.py'))[:max_files]
        for file_path in py_files:
            try:
                source = file_path.read_text(encoding='utf-8')
                tree = ast.parse(source, filename=str(file_path))
            except:
                continue
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    params = []
                    for arg in node.args.args:
                        params.append({'name': arg.arg, 'type': ''})
                    
                    result.functions.append(CodeFunction(
                        name=node.name,
                        file=str(file_path.relative_to(dir_path)),
                        line=node.lineno,
                        params=params,
                        is_method=isinstance(node, ast.AsyncFunctionDef),
                    ))
        
        result.total_files = len(py_files)
        return result
    
    def extract_routes(self, dir_path: Path, max_files: int = 500) -> List[CodeRoute]:
        # TODO: 实现
        return []
    
    def extract_calls(self, dir_path: Path, max_files: int = 500) -> List[CodeCall]:
        """提取函数调用关系"""
        from learn_repo import GoScanner as LegacyGoScanner
        scanner = LegacyGoScanner()
        ir = scanner.scan_directory(dir_path, max_files=max_files)
        
        calls = []
        for bl in ir.business_logic[:max_files]:
            for call in bl.get('call_tree', []):
                calls.append(CodeCall(
                    callee=call['name'],
                    file=call.get('file', ''),
                    line=0,
                    prefix=self._guess_prefix(call['name']),
                ))
        return calls
    
    def _guess_prefix(self, func_name: str) -> Optional[str]:
        """根据函数名猜测前缀"""
        if 'dao' in func_name.lower():
            return 'dao.'
        if 'util' in func_name.lower():
            return 'util.'
        if 'service' in func_name.lower():
            return 'service.'
        return None
    
    def extract_tables(self, dir_path: Path, max_files: int = 500) -> List[CodeTable]:
        return []
    
    def extract_error_codes(self, dir_path: Path, max_files: int = 500) -> List[CodeError]:
        return []
    
    def extract_auth_models(self, dir_path: Path, max_files: int = 500) -> List[CodeAuth]:
        return []
    
    def extract_call_graph(self, dir_path: Path, max_files: int = 500) -> List[Dict]:
        return []


# ============================================================================
# 工厂函数
# ============================================================================

def get_parser(language: str) -> CodeParser:
    """获取指定语言的解析器"""
    if language == 'go':
        return GoScanner()
    elif language == 'python':
        return PythonASTExtractor()
    else:
        raise ValueError(f"Unsupported language: {language}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Unified Code Parser')
    parser.add_argument('--repo-path', required=True)
    parser.add_argument('--language', default='go', choices=['go', 'python'])
    args = parser.parse_args()
    
    p = get_parser(args.language)
    result = p.parse_directory(Path(args.repo_path))
    print(f"Language: {result.language}")
    print(f"Functions: {len(result.functions)}")
    print(f"Structs: {len(result.structs)}")
    print(f"Routes: {len(result.routes)}")
    print(f"Tables: {len(result.tables)}")
