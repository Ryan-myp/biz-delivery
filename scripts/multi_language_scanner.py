#!/usr/bin/env python3
"""
Multi-language Code Scanner - 支持 Go/Python/Java/TypeScript

功能：
1. 基于 AST 的结构提取（类似 Graphify）
2. 跨语言统一输出格式
3. 自动识别语言类型
"""

import json
import re
import subprocess
import ast
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict, Counter

try:
    import tree_sitter_go as tsgo
    import tree_sitter_python as tspy
    import tree_sitter_java as tsjava
    import tree_sitter_typescript as tsts
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False


class ScanResult:
    """扫描结果统一格式"""
    def __init__(self, repo_name: str, repo_path: str, language: str):
        self.repo_name = repo_name
        self.repo_path = repo_path
        self.language = language
        self.structs: List[Dict] = []
        self.functions: List[Dict] = []
        self.interfaces: List[Dict] = []
        self.enums: List[Dict] = []
        self.edges: List[Dict] = []
        self.metadata: Dict = {}
    
    def to_dict(self) -> Dict:
        return {
            "repo_name": self.repo_name,
            "repo_path": self.repo_path,
            "language": self.language,
            "stats": {
                "structs": len(self.structs),
                "functions": len(self.functions),
                "interfaces": len(self.interfaces),
                "enums": len(self.enums),
                "edges": len(self.edges),
                "total": len(self.structs) + len(self.functions) + len(self.interfaces) + len(self.enums),
            },
            "structs": self.structs[:100],  # 限制返回数量
            "functions": self.functions[:100],
        }


class GoScanner:
    """Go 代码扫描器（基于 tree-sitter-go）"""
    
    _PREDEFINED = frozenset({
        "bool", "byte", "complex64", "complex128", "error", "float32", "float64",
        "int", "int8", "int16", "int32", "int64", "rune", "string",
        "uint", "uint8", "uint16", "uint32", "uint64", "uintptr", "any",
    })
    
    @classmethod
    def scan(cls, repo_path: Path) -> ScanResult:
        if not HAS_TREE_SITTER:
            return cls._fallback_scan(repo_path)
        
        result = ScanResult(repo_path.name, str(repo_path), "go")
        parser = Parser(Language(tsgo.language()))
        
        for go_file in repo_path.rglob("*.go"):
            try:
                content = go_file.read_text(encoding='utf-8', errors='ignore')
                tree = parser.parse(content.encode('utf-8'))
                cls._extract_nodes(tree, go_file, result)
            except Exception as e:
                print(f"  ⚠️  {go_file.name}: {e}")
        
        # 计算依赖边
        result.edges = cls._compute_edges(result)
        return result
    
    @classmethod
    def _extract_nodes(cls, tree, file_path: Path, result: ScanResult):
        for node in tree.root_node.children:
            if node.type == 'type_declaration':
                cls._extract_type(node, file_path, result)
            elif node.type == 'function_declaration':
                cls._extract_function(node, file_path, result)
            elif node.type == 'method_declaration':
                cls._extract_method(node, file_path, result)
    
    @classmethod
    def _extract_type(cls, node, file_path: Path, result: ScanResult):
        for child in node.children:
            if child.type != 'type_spec':
                continue
            name_node = child.child_by_field_name('name')
            if not name_node:
                continue
            type_name = name_node.text.decode('utf-8')
            if type_name in cls._PREDEFINED:
                continue
            
            line = child.start_point[0] + 1
            type_body = None
            for c in child.children:
                if c.type in ('struct_type', 'interface_type'):
                    type_body = c
                    break
            
            if type_body:
                struct_def = {
                    "name": type_name,
                    "file": str(file_path.relative_to(file_path.parent.parent)),
                    "line": line,
                    "type": "STRUCT" if type_body.type == 'struct_type' else 'INTERFACE',
                    "fields": cls._extract_fields(type_body),
                }
                result.structs.append(struct_def)
            else:
                # 基础类型别名
                func_def = {
                    "name": type_name,
                    "file": str(file_path.relative_to(file_path.parent.parent)),
                    "line": line,
                    "return_type": "ALIAS",
                }
                result.functions.append(func_def)
    
    @classmethod
    def _extract_function(cls, node, file_path: Path, result: ScanResult):
        name_node = node.child_by_field_name('name')
        if not name_node:
            return
        func_name = name_node.text.decode('utf-8')
        if func_name in cls._PREDEFINED:
            return
        
        params = cls._extract_params(node.child_by_field_name('parameters'))
        returns = cls._extract_returns(node)
        
        result.functions.append({
            "name": func_name,
            "file": str(file_path.relative_to(file_path.parent.parent)),
            "line": node.start_point[0] + 1,
            "params": params,
            "returns": returns,
            "type": "FUNCTION",
        })
    
    @classmethod
    def _extract_method(cls, node, file_path: Path, result: ScanResult):
        receiver = node.child_by_field_name('receiver')
        receiver_type = None
        if receiver:
            for param in receiver.children:
                if param.type == 'parameter_declaration':
                    type_node = param.child_by_field_name('type')
                    if type_node:
                        receiver_type = type_node.text.decode('utf-8').lstrip('*').strip()
                    break
        
        name_node = node.child_by_field_name('name')
        if not name_node:
            return
        method_name = name_node.text.decode('utf-8')
        
        params = cls._extract_params(node.child_by_field_name('parameters'))
        returns = cls._extract_returns(node)
        
        func_def = {
            "name": f"{receiver_type}.{method_name}" if receiver_type else method_name,
            "file": str(file_path.relative_to(file_path.parent.parent)),
            "line": node.start_point[0] + 1,
            "params": params,
            "returns": returns,
            "type": "METHOD",
        }
        if receiver_type:
            func_def["receiver"] = receiver_type
        result.functions.append(func_def)
    
    @classmethod
    def _extract_fields(cls, struct_node) -> List[Dict]:
        fields = []
        for child in struct_node.children:
            if child.type == 'field_declaration':
                for field in child.children:
                    if field.type == 'field_declaration_list':
                        for name_node in field.children:
                            if name_node.type == 'field_identifier':
                                fields.append({
                                    "name": name_node.text.decode('utf-8'),
                                })
        return fields
    
    @classmethod
    def _extract_params(cls, params_node) -> List[str]:
        if not params_node:
            return []
        params = []
        for param in params_node.children:
            if param.type == 'parameter_declaration':
                name_node = param.child_by_field_name('name')
                if name_node:
                    params.append(name_node.text.decode('utf-8'))
        return params
    
    @classmethod
    def _extract_returns(cls, func_node) -> List[str]:
        returns = []
        result_clause = func_node.child_by_field_name('result')
        if result_clause:
            for param in result_clause.children:
                if param.type == 'parameter_declaration':
                    type_node = param.child_by_field_name('type')
                    if type_node:
                        returns.append(type_node.text.decode('utf-8'))
        return returns
    
    @classmethod
    def _compute_edges(cls, result: ScanResult) -> List[Dict]:
        """计算依赖边"""
        edges = []
        struct_names = {s['name'] for s in result.structs}
        
        for func in result.functions:
            for param in func.get('params', []):
                if param in struct_names:
                    edges.append({
                        "source": func['name'],
                        "target": param,
                        "relation": "USES",
                    })
            for ret in func.get('returns', []):
                if ret in struct_names:
                    edges.append({
                        "source": func['name'],
                        "target": ret,
                        "relation": "RETURNS",
                    })
        
        return edges
    
    @classmethod
    def _fallback_scan(cls, repo_path: Path) -> ScanResult:
        """正则 fallback（tree-sitter 不可用时）"""
        result = ScanResult(repo_path.name, str(repo_path), "go")
        pattern = re.compile(r'type\s+(\w+)\s+(?:struct|interface)\s*\{')
        
        for go_file in repo_path.rglob("*.go"):
            try:
                content = go_file.read_text(encoding='utf-8', errors='ignore')
                for m in pattern.finditer(content):
                    result.structs.append({
                        "name": m.group(1),
                        "file": str(go_file.relative_to(repo_path.parent)),
                        "line": content[:m.start()].count('\n') + 1,
                        "type": "STRUCT",
                        "fields": [],
                    })
            except Exception:
                pass
        return result


class PythonScanner:
    """Python 代码扫描器（基于 ast 模块）"""
    
    @classmethod
    def scan(cls, repo_path: Path) -> ScanResult:
        result = ScanResult(repo_path.name, str(repo_path), "python")
        
        for py_file in repo_path.rglob("*.py"):
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                tree = ast.parse(content)
                cls._extract_nodes(tree, py_file, result)
            except Exception as e:
                print(f"  ⚠️  {py_file.name}: {e}")
        
        result.edges = cls._compute_edges(result)
        return result
    
    @classmethod
    def _extract_nodes(cls, tree, file_path: Path, result: ScanResult):
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                result.structs.append({
                    "name": node.name,
                    "file": str(file_path.relative_to(file_path.parent.parent)),
                    "line": node.lineno,
                    "type": "CLASS",
                    "fields": cls._extract_class_fields(node),
                })
            elif isinstance(node, ast.FunctionDef):
                result.functions.append({
                    "name": node.name,
                    "file": str(file_path.relative_to(file_path.parent.parent)),
                    "line": node.lineno,
                    "params": [a.arg for a in node.args.args if a.arg != 'self'],
                    "returns": [],
                    "type": "FUNCTION",
                })
    
    @classmethod
    def _extract_class_fields(cls, class_node: ast.ClassDef) -> List[str]:
        """提取类的字段"""
        fields = []
        for stmt in class_node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                fields.append(stmt.target.id)
        return fields
    
    @classmethod
    def _compute_edges(cls, result: ScanResult) -> List[Dict]:
        edges = []
        class_names = {s['name'] for s in result.structs}
        for func in result.functions:
            for param in func.get('params', []):
                if param in class_names:
                    edges.append({"source": func['name'], "target": param, "relation": "USES"})
        return edges


class JavaScanner:
    """Java 代码扫描器（基于 tree-sitter-java）"""
    
    @classmethod
    def scan(cls, repo_path: Path) -> ScanResult:
        if not HAS_TREE_SITTER:
            return cls._fallback_scan(repo_path)
        
        result = ScanResult(repo_path.name, str(repo_path), "java")
        parser = Parser(Language(tsjava.language()))
        
        for java_file in repo_path.rglob("*.java"):
            try:
                content = java_file.read_text(encoding='utf-8', errors='ignore')
                tree = parser.parse(content.encode('utf-8'))
                cls._extract_nodes(tree, java_file, result)
            except Exception as e:
                print(f"  ⚠️  {java_file.name}: {e}")
        
        result.edges = cls._compute_edges(result)
        return result
    
    @classmethod
    def _extract_nodes(cls, tree, file_path: Path, result: ScanResult):
        for node in tree.root_node.children:
            if node.type == 'class_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    result.structs.append({
                        "name": name_node.text.decode('utf-8'),
                        "file": str(file_path.relative_to(file_path.parent.parent)),
                        "line": node.start_point[0] + 1,
                        "type": "CLASS",
                    })
            elif node.type == 'method_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    result.functions.append({
                        "name": name_node.text.decode('utf-8'),
                        "file": str(file_path.relative_to(file_path.parent.parent)),
                        "line": node.start_point[0] + 1,
                        "type": "METHOD",
                    })
    
    @classmethod
    def _fallback_scan(cls, repo_path: Path) -> ScanResult:
        result = ScanResult(repo_path.name, str(repo_path), "java")
        pattern = re.compile(r'(?:public|private|protected)?\s*(?:class|interface)\s+(\w+)')
        for java_file in repo_path.rglob("*.java"):
            try:
                content = java_file.read_text(encoding='utf-8', errors='ignore')
                for m in pattern.finditer(content):
                    result.structs.append({
                        "name": m.group(1),
                        "file": str(java_file.relative_to(repo_path.parent)),
                        "line": content[:m.start()].count('\n') + 1,
                        "type": "CLASS",
                    })
            except Exception:
                pass
        return result
    
    @classmethod
    def _compute_edges(cls, result: ScanResult) -> List[Dict]:
        return []


class TypeScriptScanner:
    """TypeScript 代码扫描器（基于正则 fallback）"""
    
    @classmethod
    def scan(cls, repo_path: Path) -> ScanResult:
        result = cls._fallback_scan(repo_path)
        return result
    
    @classmethod
    def _fallback_scan(cls, repo_path: Path) -> ScanResult:
        result = ScanResult(repo_path.name, str(repo_path), "typescript")
        
        # 匹配 class 定义
        class_pattern = re.compile(r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)')
        # 匹配 interface 定义
        interface_pattern = re.compile(r'(?:export\s+)?interface\s+(\w+)')
        # 匹配 function 定义
        func_pattern = re.compile(r'(?:export\s+)?function\s+(\w+)')
        
        for ts_file in repo_path.rglob("*.ts"):
            try:
                content = ts_file.read_text(encoding='utf-8', errors='ignore')
                rel_path = str(ts_file.relative_to(repo_path.parent))
                
                for m in class_pattern.finditer(content):
                    result.structs.append({
                        "name": m.group(1),
                        "file": rel_path,
                        "line": content[:m.start()].count('\n') + 1,
                        "type": "CLASS",
                    })
                
                for m in interface_pattern.finditer(content):
                    result.structs.append({
                        "name": m.group(1),
                        "file": rel_path,
                        "line": content[:m.start()].count('\n') + 1,
                        "type": "INTERFACE",
                    })
                
                for m in func_pattern.finditer(content):
                    result.functions.append({
                        "name": m.group(1),
                        "file": rel_path,
                        "line": content[:m.start()].count('\n') + 1,
                        "type": "FUNCTION",
                    })
                    
            except Exception:
                pass
        
        return result
    
    @classmethod
    def _extract_nodes(cls, tree, file_path: Path, result: ScanResult):
        for node in tree.root_node.children:
            if node.type == 'class_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    result.structs.append({
                        "name": name_node.text.decode('utf-8'),
                        "file": str(file_path.relative_to(file_path.parent.parent)),
                        "line": node.start_point[0] + 1,
                        "type": "CLASS",
                    })
            elif node.type in ('function_declaration', 'method_definition'):
                name_node = node.child_by_field_name('name')
                if name_node:
                    result.functions.append({
                        "name": name_node.text.decode('utf-8'),
                        "file": str(file_path.relative_to(file_path.parent.parent)),
                        "line": node.start_point[0] + 1,
                        "type": "FUNCTION",
                    })
    
    @classmethod
    def _fallback_scan(cls, repo_path: Path) -> ScanResult:
        result = ScanResult(repo_path.name, str(repo_path), "typescript")
        pattern = re.compile(r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)')
        for ts_file in repo_path.rglob("*.ts"):
            try:
                content = ts_file.read_text(encoding='utf-8', errors='ignore')
                for m in pattern.finditer(content):
                    result.structs.append({
                        "name": m.group(1),
                        "file": str(ts_file.relative_to(repo_path.parent)),
                        "line": content[:m.start()].count('\n') + 1,
                        "type": "CLASS",
                    })
            except Exception:
                pass
        return result
    
    @classmethod
    def _compute_edges(cls, result: ScanResult) -> List[Dict]:
        return []


# 语言映射
LANGUAGE_SCANNERS = {
    "go": GoScanner,
    "python": PythonScanner,
    "java": JavaScanner,
    "typescript": TypeScriptScanner,
    "tsx": TypeScriptScanner,
}


def detect_language(repo_path: Path) -> Optional[str]:
    """自动检测语言"""
    extensions = {
        '.go': 'go',
        '.py': 'python',
        '.java': 'java',
        '.ts': 'typescript',
        '.tsx': 'typescript',
    }
    
    lang_counts = Counter()
    for f in repo_path.rglob("*"):
        if f.suffix in extensions:
            lang_counts[extensions[f.suffix]] += 1
    
    if lang_counts:
        return lang_counts.most_common(1)[0][0]
    return None


def scan_repo(repo_path: Path, language: Optional[str] = None) -> Optional[ScanResult]:
    """扫描仓库，自动检测或指定语言"""
    if language is None:
        language = detect_language(repo_path)
    
    if language not in LANGUAGE_SCANNERS:
        print(f"❌ 不支持的语言: {language}")
        return None
    
    scanner = LANGUAGE_SCANNERS[language]
    return scanner.scan(repo_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python multi_language_scanner.py <repo_path> [--lang go|python|java|typescript]")
        sys.exit(1)
    
    repo_path = Path(sys.argv[1])
    lang = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].startswith('--lang') else None
    
    result = scan_repo(repo_path, lang)
    if result:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
