#!/usr/bin/env python3
"""代码片段注入器 - 提取关键代码片段"""
import re
from pathlib import Path
from typing import Dict, List


class CodeSnippetInjector:
    """从已扫描的 IR 中提取关键代码片段，注入到 prompt"""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def _resolve_file_path(self, file_path: str) -> Path:
        """解析文件路径，处理重复的前缀
        
        例如: "eino/adk/agent_tool.go" -> "/tmp/eino/adk/agent_tool.go"
        """
        if not file_path:
            return Path()
        
        # 如果已经是绝对路径，直接返回
        if file_path.startswith('/'):
            return Path(file_path)
        
        # 尝试直接拼接
        filepath = self.repo_path / file_path
        if filepath.exists():
            return filepath
        
        # 如果路径包含仓库名前缀，去掉一层
        parts = Path(file_path).parts
        if len(parts) > 1:
            # 尝试去掉第一个部分
            filepath2 = self.repo_path / Path(*parts[1:])
            if filepath2.exists():
                return filepath2
        
        return filepath

    def extract_key_snippets(self, ir, max_snippets: int = 10) -> List[Dict]:
        """从 repo 中提取关键代码片段
        
        Args:
            ir: IRDocument 对象
            max_snippets: 最多提取多少个片段
        """
        snippets = []
        
        # 1. 提取带字段的 struct（优先提取字段多的）
        structs_with_fields = sorted(
            [s for s in ir.structs if s.fields],
            key=lambda x: len(x.fields),
            reverse=True
        )
        
        for s in structs_with_fields[:6]:
            code = self._extract_struct_code(s)
            if code:
                snippets.append({
                    'name': s.name,
                    'type': 'struct',
                    'file': s.file or '',
                    'fields': s.fields,
                    'methods': s.methods,
                    'code': code,
                })
        
        # 2. 提取带方法的接口
        structs_with_methods = [
            s for s in ir.structs 
            if s.methods and len(s.methods) >= 2
            and not any(sn['name'] == s.name for sn in snippets)
        ]
        
        for s in structs_with_methods[:4]:
            code = self._extract_methods_code(s)
            if code:
                snippets.append({
                    'name': s.name,
                    'type': 'interface',
                    'file': s.file or '',
                    'fields': s.fields,
                    'methods': s.methods,
                    'code': code,
                })
        
        return snippets[:max_snippets]

    def _extract_struct_code(self, struct) -> str:
        """提取 struct 定义代码"""
        if not struct.file:
            return ""
        
        filepath = self._resolve_file_path(struct.file)
        if not filepath.exists():
            return ""
        
        try:
            content = filepath.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return ""
        
        # 找 type XXX struct { ... }
        pattern = rf'type\s+{re.escape(struct.name)}\s+struct\s*\{{'
        match = re.search(pattern, content)
        if not match:
            return ""
        
        start = match.start()
        # 找匹配的结束括号
        brace_count = 0
        end = start
        for i, c in enumerate(content[start:], start):
            if c == '{':
                brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break
        
        return content[start:end].strip()

    def _extract_methods_code(self, struct) -> str:
        """提取方法定义代码"""
        if not struct.file:
            return ""
        
        filepath = self._resolve_file_path(struct.file)
        if not filepath.exists():
            return ""
        
        try:
            content = filepath.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return ""
        
        # 找 func (s *StructName) MethodName(
        pattern = rf'func\s+\(\s*\*?\s*{re.escape(struct.name)}\s+\w+\s*\)\s+(\w+)\s*\('
        matches = list(re.finditer(pattern, content))
        
        if not matches:
            return ""
        
        # 提取前3个方法
        snippets = []
        for m in matches[:3]:
            start = m.start()
            # 找方法体结束（下一个 func 或文件结束）
            next_func = re.search(r'\nfunc\s+', content[start + 1:])
            end = start + 1 + next_func.start() if next_func else start + 300
            snippet = content[start:end].strip()
            if snippet:
                snippets.append(snippet)
        
        return '\n\n'.join(snippets)

    def generate_prompt_section(self, snippets: List[Dict]) -> str:
        """生成 prompt 中的代码片段部分"""
        if not snippets:
            return ""
        
        lines = ["## 关键代码片段\n"]
        
        for i, s in enumerate(snippets, 1):
            lines.append(f"### {i}. {s['name']} ({s['type']})")
            lines.append(f"- File: `{s['file']}`")
            lines.append("")
            
            if s.get('fields'):
                lines.append("**Fields:**")
                for f in s['fields'][:8]:
                    tag = f" `{f.get('gorm_tag', '')}`" if f.get('gorm_tag') else ""
                    json_tag = f" `{f.get('json_tag', '')}`" if f.get('json_tag') else ""
                    lines.append(f"- `{f['name']}`: {f['type']}{tag}{json_tag}")
                lines.append("")
            
            if s.get('methods'):
                lines.append("**Methods:**")
                for m in s['methods'][:5]:
                    lines.append(f"- `{m['name']}`")
                lines.append("")
            
            if s.get('code'):
                lines.append("**Code:**")
                lines.append("```go")
                lines.append(s['code'])
                lines.append("```")
                lines.append("")
        
        return '\n'.join(lines)
