#!/usr/bin/env python3
"""
Go Scanner - Go代码扫描器模块
从 learn_repo.py 拆分出来的Go代码扫描逻辑
"""

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from code_parser import IRDocument, StructDef, FuncDef, RouteDef, ImportDef


class GoScanner:
    """Go代码扫描器 — 使用 ripgrep 批量扫描"""
    
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
    
    def _parse_params(self, params_str: str) -> List[Dict]:
        """解析函数参数"""
        params = []
        if not params_str.strip():
            return params
        for param in params_str.split(','):
            param = param.strip()
            if not param:
                continue
            tokens = param.split()
            if len(tokens) >= 2:
                params.append({"name": tokens[0], "type": ' '.join(tokens[1:])})
            elif len(tokens) == 1:
                params.append({"name": "", "type": tokens[0]})
        return params
    
    def scan_directory(self, dir_path: Path, max_files: int = 500,
                       incremental: bool = False, changed_files: List[Path] = None) -> IRDocument:
        """扫描整个目录"""
        try:
            return self._scan_with_rgrep(dir_path, max_files)
        except Exception as e:
            print(f"  WARNING: ripgrep scan failed ({e}), fallback to Python re")
            return self._scan_with_python_re(dir_path, max_files, incremental, changed_files)
    
    def _scan_with_rgrep(self, dir_path: Path, max_files: int) -> IRDocument:
        """用 ripgrep 批量扫描"""
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
                 r'type\s+(\w+)\s+struct\s*\{'] + exclude_args + [str(dir_path)],
                capture_output=True, text=True, timeout=120
            )
            if r.returncode in (0, 1):
                self._parse_rg_structs(r.stdout, ir, dir_path, max_files)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 2. 扫描 TableName
        try:
            r = subprocess.run(
                ["rg", "--json", "--type", "go", "-n",
                 r'func\s+\(\s*\*\w+\)\s+TableName\(\)\s+string'] + exclude_args + [str(dir_path)],
                capture_output=True, text=True, timeout=60
            )
            if r.returncode in (0, 1):
                self._parse_rg_table_names(r.stdout, ir)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return ir
    
    def _parse_rg_structs(self, output: str, ir: IRDocument, dir_path: Path, max_files: int):
        """解析 ripgrep 的 struct 扫描结果"""
        count = 0
        current_file = None
        current_struct = None
        
        for line in output.split('\n'):
            if not line.strip():
                continue
            try:
                data = __import__('json').loads(line)
            except:
                continue
            
            if data.get('type') == 'match':
                current_file = Path(data['data']['path']['text'])
                if count >= max_files:
                    break
                count += 1
            
            elif data.get('type') == 'submatch':
                parent = data.get('parent', {})
                if parent.get('type') == 'match':
                    # 提取 struct 名称
                    for m in data.get('matches', []):
                        for sub in m.get('submatches', []):
                            text = sub.get('text', '')
                            if text and text != 'struct':
                                current_struct = text
                                ir.structs.append(StructDef(
                                    name=text,
                                    file=str(current_file.relative_to(dir_path.parent)),
                                ))
                                break
    
    def _parse_rg_table_names(self, output: str, ir: IRDocument):
        """解析 ripgrep 的 TableName 扫描结果"""
        for line in output.split('\n'):
            if not line.strip():
                continue
            try:
                data = __import__('json').loads(line)
            except:
                continue
            if data.get('type') == 'match':
                # 提取表名
                pass
    
    def _scan_with_python_re(self, dir_path: Path, max_files: int,
                              incremental: bool = False, changed_files: List[Path] = None) -> IRDocument:
        """Fallback: 逐文件 Python re 扫描"""
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
        
        return ir
