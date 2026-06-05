#!/usr/bin/env python3
"""知识提取引擎 - 把代码/文档变成结构化知识"""

import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ASTExtractor:
    """Python AST 提取器 - 提取函数、类、方法的结构信息"""
    
    def extract_file(self, file_path: Path) -> dict:
        """提取单个文件的所有定义"""
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            return {"status": "degraded", "reason": "parse_failed"}
        
        return {
            "file": str(file_path),
            "functions": self._extract_functions(tree),
            "classes": self._extract_classes(tree),
            "imports": self._extract_imports(tree),
            "comments": self._extract_comments(source, tree),
        }
    
    def _extract_functions(self, tree) -> List[dict]:
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append({
                    "type": "function",
                    "name": node.name,
                    "args": self._get_args(node),
                    "returns": self._get_type(node.returns),
                    "decorators": [self._get_name(d) for d in node.decorator_list],
                    "lines": (node.lineno, node.end_lineno),
                    "docstring": ast.get_docstring(node),
                    "async": isinstance(node, ast.AsyncFunctionDef),
                    "children": [],  # 需要 build_callgraph 时填充
                })
        return functions
    
    def _extract_classes(self, tree) -> List[dict]:
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                classes.append({
                    "type": "class",
                    "name": node.name,
                    "bases": [self._get_name(b) for b in node.bases],
                    "methods": [{
                        "name": m.name,
                        "args": self._get_args(m),
                        "returns": self._get_type(m.returns),
                        "decorators": [self._get_name(d) for d in m.decorator_list],
                        "docstring": ast.get_docstring(m),
                    } for m in methods],
                    "lines": (node.lineno, node.end_lineno),
                })
        return classes
    
    def _extract_imports(self, tree) -> List[dict]:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend({
                    "module": alias.name,
                    "asname": alias.asname,
                } for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append({
                    "module": node.module,
                    "names": [alias.name for alias in node.names],
                    "level": node.level,
                })
        return imports
    
    def _extract_comments(self, source: str, tree) -> List[str]:
        """提取文件级注释"""
        # 简单实现：获取文件 docstring
        docstring = ast.get_docstring(tree)
        return [docstring] if docstring else []
    
    def _get_args(self, node) -> List[dict]:
        args = []
        for arg in node.args.args:
            args.append({
                "name": arg.arg,
                "annotation": self._get_type(arg.annotation),
            })
        if node.args.vararg:
            args.append({"name": f"*{node.args.vararg.arg}", "is_vararg": True})
        if node.args.kwarg:
            args.append({"name": f"**{node.args.kwarg.arg}", "is_kwarg": True})
        return args
    
    def _get_type(self, annotation) -> Optional[str]:
        if annotation is None:
            return None
        if isinstance(annotation, ast.Name):
            return annotation.id
        if isinstance(annotation, ast.Attribute):
            return f"{self._get_type(annotation.value)}.{annotation.attr}"
        return str(ast.dump(annotation)[:50])
    
    def _get_name(self, node) -> Optional[str]:
        if node is None:
            return None
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        if isinstance(node, ast.Constant):
            return str(node.value)
        return None


class FlowBuilder:
    """业务流构建器 - 从入口点发现业务流"""
    
    def discover_entry_points(self, repo_root: Path, language: str = "python") -> List[dict]:
        """发现入口点（API路由、Controller等）"""
        entry_points = []
        
        if language == "python":
            # 搜索 FastAPI/Flask 路由装饰器
            patterns = [
                r"@app\.(get|post|put|delete|patch)\s*\(['\"]([^'\"]+)",
                r"@router\.(get|post|put|delete|patch)\s*\(['\"]([^'\"]+)",
                r"@route\.(get|post|put|delete|patch)\s*\(['\"]([^'\"]+)",
                r"@(api|bp)\.(register_|add_)(route|resource)",
                r"app\.add_url_rule\s*\(\s*['\"]([^'\"]+)",
            ]
            entry_points = self._search_patterns(repo_root, patterns, language)
        
        return entry_points
    
    def _search_patterns(self, repo_root: Path, patterns: List[str], language: str) -> List[dict]:
        """在代码库中搜索入口点模式"""
        results = []
        
        for py_file in repo_root.rglob(f"*.{language}"):
            try:
                source = py_file.read_text(encoding="utf-8")
                for pattern in patterns:
                    for match in re.finditer(pattern, source):
                        results.append({
                            "type": "entry_point",
                            "file": str(py_file.relative_to(repo_root)),
                            "route": match.group(match.lastindex),
                            "pattern": pattern,
                        })
            except Exception:
                continue
        
        return results
    
    def build_call_graph(self, entry_point: dict, repo_root: Path) -> dict:
        """从入口点构建调用拓扑"""
        extractor = ASTExtractor()
        file_path = repo_root / entry_point["file"]
        
        if not file_path.exists():
            return {"status": "degraded", "reason": "file_not_found"}
        
        ast_data = extractor.extract_file(file_path)
        
        # 简化的调用图：从函数中提取调用链
        call_graph = {
            "entry_point": entry_point,
            "functions": ast_data.get("functions", []),
            "call_depth": self._infer_call_depth(ast_data["functions"]),
        }
        
        return call_graph
    
    def _infer_call_depth(self, functions: List[dict]) -> int:
        """推断调用深度（简化实现）"""
        return 3  # 默认3层


class DFGAnalyzer:
    """数据流分析器 - 追踪变量传播"""
    
    def analyze(self, file_path: Path) -> dict:
        """分析文件中的数据流"""
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            return {"status": "degraded", "reason": "parse_failed"}
        
        # 提取变量定义和使用
        definitions = {}
        uses = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        definitions[target.id] = node.lineno
            
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                uses.setdefault(node.id, []).append(node.lineno)
        
        return {
            "definitions": definitions,
            "uses": uses,
            "variables": list(set(definitions.keys()) | set(uses.keys())),
        }


class SemanticExtractor:
    """语义层提取器 - 从代码/文档中提取业务语义"""
    
    def extract(self, file_path: Path, content: str) -> dict:
        """提取语义层知识"""
        return {
            "function_descriptions": self._extract_function_descriptions(content),
            "business_concepts": self._extract_business_concepts(content),
            "design_patterns": self._detect_design_patterns(content),
            "docstring_summary": self._extract_docstrings(content),
        }
    
    def _extract_function_descriptions(self, content: str) -> List[dict]:
        """从函数 docstring 提取功能描述"""
        descriptions = []
        func_pattern = re.compile(r'def\s+(\w+)\s*\([^)]*\)\s*:\s*"""?([\s\S]*?)(?=\n\s{0,3}\w|\Z)')
        
        for match in func_pattern.finditer(content):
            func_name = match.group(1)
            doc = match.group(2).strip()
            if doc and len(doc) > 10:
                descriptions.append({
                    "function": func_name,
                    "description": doc[:200],  # 截断
                    "type": "docstring",
                })
        
        return descriptions
    
    def _extract_business_concepts(self, content: str) -> List[dict]:
        """提取业务概念（简化实现 - 可扩展为术语映射表）"""
        # 从注释和变量名中提取
        concepts = []
        
        # 常见业务模式
        business_indicators = {
            "campaign": ["campaign", "广告系列", "广告组"],
            "ad_group": ["ad_group", "adgroup", "广告组"],
            "user": ["user", "account", "用户", "账号", "账户"],
            "budget": ["budget", "预算", "amount"],
            "bidding": ["bidding", "bid", "出价", "策略"],
        }
        
        for concept, keywords in business_indicators.items():
            if any(k in content.lower() for k in keywords):
                concepts.append({
                    "concept": concept,
                    "confidence": 0.7,
                    "keywords": keywords,
                })
        
        return concepts
    
    def _detect_design_patterns(self, content: str) -> List[dict]:
        """检测常见设计模式（简化实现）"""
        patterns = []
        
        if "class " in content and "def " in content:
            patterns.append({"pattern": "OOP Class Structure", "confidence": 0.5})
        
        if any(x in content for x in ["@staticmethod", "@classmethod", "@property"]):
            patterns.append({"pattern": "Decorator Pattern", "confidence": 0.6})
        
        if "self." in content:
            patterns.append({"pattern": "Instance Methods", "confidence": 0.7})
        
        return patterns
    
    def _extract_docstrings(self, content: str) -> List[str]:
        """提取所有 docstring"""
        return [
            m.group(1).strip()
            for m in re.finditer(r'"""([\s\S]*?)"""', content)
        ]


def extract_code_knowledge(repo_root: Path, file_patterns: List[str] = None) -> dict:
    """从仓库中提取结构化知识"""
    repo_path = Path(repo_root)
    if not repo_path.exists():
        return {"status": "error", "reason": "repo_not_found"}
    
    extractor = ASTExtractor()
    semantic_extractor = SemanticExtractor()
    
    files = list(repo_path.rglob("*.py")) if file_patterns is None else []
    if file_patterns:
        files = [f for f in files if any(pat in str(f) for pat in file_patterns)]
    
    nodes = []
    edges = []
    
    for file_path in files[:100]:  # 限制数量避免超时
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # AST 提取
            ast_data = extractor.extract_file(file_path)
            for func in ast_data.get("functions", []):
                nodes.append({
                    "id": f"{file_path.name}:{func['name']}",
                    "type": "function",
                    "name": func["name"],
                    "file": str(file_path.relative_to(repo_path)),
                    "line": func["lines"][0],
                    "content": json.dumps(func, ensure_ascii=False),
                    "metadata": {
                        "decorators": func.get("decorators", []),
                        "async": func.get("async", False),
                    },
                })
            
            for cls in ast_data.get("classes", []):
                nodes.append({
                    "id": f"{file_path.name}:{cls['name']}",
                    "type": "class",
                    "name": cls["name"],
                    "file": str(file_path.relative_to(repo_path)),
                    "line": cls["lines"][0],
                    "content": json.dumps(cls, ensure_ascii=False),
                    "metadata": {
                        "bases": cls.get("bases", []),
                        "methods_count": len(cls.get("methods", [])),
                    },
                })
            
            # 语义层提取
            semantic = semantic_extractor.extract(file_path, content)
            if semantic.get("function_descriptions"):
                for desc in semantic["function_descriptions"]:
                    nodes.append({
                        "id": f"{file_path.name}:{desc['function']}_desc",
                        "type": "description",
                        "name": desc["function"],
                        "file": str(file_path.relative_to(repo_path)),
                        "content": desc["description"],
                        "metadata": {"source": "docstring"},
                    })
            
        except Exception:
            continue
    
    return {
        "status": "ok",
        "mode": "knowledge_extraction",
        "nodes": nodes,
        "edges": edges,
        "total_files": len(files),
        "total_nodes": len(nodes),
    }
