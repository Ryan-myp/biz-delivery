#!/usr/bin/env python3
"""
Code Parser - 代码解析器模块
从 learn_repo.py 拆分出来的核心数据结构定义
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ============================================================================
# 数据结构定义
# ============================================================================

@dataclass
class StructDef:
    """结构体定义"""
    name: str
    file: str
    table_name: Optional[str] = None
    fields: List[Dict] = field(default_factory=list)
    methods: List[Dict] = field(default_factory=list)


@dataclass
class FuncDef:
    """函数定义"""
    name: str
    file: str
    params: List[Dict] = field(default_factory=list)
    returns: Optional[str] = None
    is_route: bool = False
    call_chain: List[str] = field(default_factory=list)


@dataclass
class RouteDef:
    """路由定义"""
    path: str
    method: str
    handler: str
    module: str
    file: str
    params: List[Dict] = field(default_factory=list)


@dataclass
class ImportDef:
    """导入定义"""
    module: str
    is_local: bool = False


@dataclass
class IRDocument:
    """Intermediate Representation Document - 中间表示文档"""
    
    # 基本信息
    repo_name: str
    repo_path: str
    language: str
    
    # 代码元素
    structs: List[StructDef] = field(default_factory=list)
    functions: List[FuncDef] = field(default_factory=list)
    routes: List[RouteDef] = field(default_factory=list)
    imports: List[ImportDef] = field(default_factory=list)
    
    # 架构信息
    packages: Dict[str, Dict] = field(default_factory=dict)
    dependencies: List[Dict] = field(default_factory=list)
    call_graph: Dict[str, List[str]] = field(default_factory=dict)
    
    # 业务信息
    error_codes: List[Dict] = field(default_factory=list)
    auth_models: List[Dict] = field(default_factory=list)
    entity_tables: List[Dict] = field(default_factory=list)
    conditions: List[Dict] = field(default_factory=list)
    configs: List[Dict] = field(default_factory=list)
    perf_hotspots: List[Dict] = field(default_factory=list)
    business_logic: List[Dict] = field(default_factory=list)
    core_flows: List[Dict] = field(default_factory=list)
    compat_issues: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "repo_name": self.repo_name,
            "repo_path": self.repo_path,
            "language": self.language,
            "stats": {
                "structs": len(self.structs),
                "functions": len(self.functions),
                "routes": len(self.routes),
                "imports": len(self.imports),
                "total": len(self.structs) + len(self.functions) + len(self.routes),
            },
            "structs": [s.__dict__ for s in self.structs[:100]],
            "functions": [f.__dict__ for f in self.functions[:100]],
            "routes": [r.__dict__ for r in self.routes[:50]],
        }
    
    def add_route(self, route: RouteDef):
        """添加路由"""
        self.routes.append(route)
    
    def add_function(self, func: FuncDef):
        """添加函数"""
        self.functions.append(func)
    
    def add_struct(self, struct: StructDef):
        """添加结构体"""
        self.structs.append(struct)
