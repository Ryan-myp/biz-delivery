#!/usr/bin/env python3
"""
Knowledge Extractor - 知识提取器模块
从 learn_repo.py 拆分出来的知识提取逻辑
"""

import re
from pathlib import Path
from typing import Dict, List, Optional

from code_parser import IRDocument, StructDef, FuncDef, RouteDef


class KnowledgeExtractor:
    """从 IRDocument 提取知识"""
    
    def extract_error_codes(self, ir: IRDocument) -> List[Dict]:
        """提取错误码定义"""
        error_codes = []
        for struct in ir.structs:
            if 'error' in struct.name.lower() or 'code' in struct.name.lower():
                error_codes.append({
                    'name': struct.name,
                    'file': struct.file,
                    'fields': struct.fields,
                })
        return error_codes
    
    def extract_auth_models(self, ir: IRDocument) -> List[Dict]:
        """提取鉴权模型"""
        auth_models = []
        for struct in ir.structs:
            if any(kw in struct.name.lower() for kw in ['auth', 'permission', 'role', 'user', 'token']):
                auth_models.append({
                    'name': struct.name,
                    'file': struct.file,
                    'fields': struct.fields,
                })
        return auth_models
    
    def extract_entity_tables(self, ir: IRDocument) -> List[Dict]:
        """提取Entity-Table映射"""
        entity_tables = []
        for struct in ir.structs:
            if struct.table_name:
                entity_tables.append({
                    'entity': struct.name,
                    'table': struct.table_name,
                    'file': struct.file,
                })
        return entity_tables
    
    def extract_config(self, ir: IRDocument) -> List[Dict]:
        """提取配置信息"""
        configs = []
        for func in ir.functions:
            if 'config' in func.name.lower() or 'init' in func.name.lower():
                configs.append({
                    'name': func.name,
                    'file': func.file,
                    'params': func.params,
                })
        return configs
    
    def extract_perf_hotspots(self, ir: IRDocument) -> List[Dict]:
        """提取性能热点"""
        hotspots = []
        for func in ir.functions:
            if any(kw in func.name.lower() for kw in ['cache', 'query', 'fetch', 'load', 'process']):
                hotspots.append({
                    'name': func.name,
                    'file': func.file,
                    'is_route': func.is_route,
                })
        return hotspots
    
    def extract_business_logic(self, ir: IRDocument, repo_path: Path, max_entries: int = 100) -> List[Dict]:
        """从入口点追踪调用链"""
        business_logic = []
        entry_points = []
        
        # 找入口点
        for route in ir.routes:
            entry_points.append({
                'path': route.path,
                'method': route.method,
                'handler': route.handler,
                'file': route.file,
            })
        
        for entry in entry_points[:max_entries]:
            call_chain = [entry['handler']]
            # TODO: 追踪调用链
            business_logic.append({
                'route': f"{entry['method']} {entry['path']}",
                'handler': entry['handler'],
                'call_chain': call_chain,
                'description': f"Route handler: {entry['handler']}",
            })
        
        return business_logic
    
    def build_call_graph(self, ir: IRDocument) -> Dict[str, List[str]]:
        """从 func 签名构建调用图"""
        call_graph = {}
        
        # 建立函数索引
        func_index = {}
        for func in ir.functions:
            func_index[func.name] = func.file
        
        # 从文件名推断依赖关系
        for struct in ir.structs:
            callers = []
            for func in ir.functions:
                if struct.name in func.file or struct.name.lower() in func.name.lower():
                    callers.append(func.name)
            if callers:
                call_graph[struct.name] = callers
        
        return call_graph
    
    def extract_all(self, ir: IRDocument, repo_path: Path) -> IRDocument:
        """提取所有知识"""
        ir.error_codes = self.extract_error_codes(ir)
        ir.auth_models = self.extract_auth_models(ir)
        ir.entity_tables = self.extract_entity_tables(ir)
        ir.configs = self.extract_config(ir)
        ir.perf_hotspots = self.extract_perf_hotspots(ir)
        ir.business_logic = self.extract_business_logic(ir, repo_path)
        ir.call_graph = self.build_call_graph(ir)
        
        return ir
