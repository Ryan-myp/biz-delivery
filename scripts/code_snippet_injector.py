#!/usr/bin/env python3
"""代码片段注入器 - 提取关键代码片段"""
import re
from pathlib import Path
from typing import Dict, List, Optional

from learn_repo import StructDef, FuncDef


class CodeSnippetInjector:
    """提取关键代码片段，直接注入 prompt"""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def extract_key_snippets(self, ir, max_snippets: int = 10) -> List[Dict]:
        """提取关键代码片段

        Args:
            ir: IRDocument 对象
            max_snippets: 最多提取多少个片段
        """
        snippets = []

        # 1. 提取关键 struct 的完整定义
        key_structs = []
        for s in ir.structs:
            if s.fields and len(s.fields) >= 2:
                key_structs.append(s)

        # 按字段数量排序，取前5个
        key_structs.sort(key=lambda x: len(x.fields), reverse=True)

        for s in key_structs[:5]:
            code = self._extract_struct_code(str(s.file))
            if code:
                snippets.append({
                    'name': s.name,
                    'type': 'struct',
                    'file': s.file,
                    'fields': s.fields,
                    'code': code,
                })

        # 2. 提取关键接口的方法
        for s in ir.structs:
            if s.methods and len(s.methods) >= 2:
                code = self._extract_method_code(str(s.file), s.name)
                if code:
                    snippets.append({
                        'name': s.name,
                        'type': 'interface',
                        'file': s.file,
                        'methods': s.methods,
                        'code': code,
                    })
                    if len(snippets) >= max_snippets:
                        break

        return snippets[:max_snippets]

    def _extract_struct_code(self, file_path: str) -> str:
        """提取 struct 定义代码"""
        full_path = self.repo_path / file_path
        if not full_path.exists():
            return ""

        try:
            content = full_path.read_text(encoding='utf-8')
        except Exception:
            return ""

        # 找到 type XXX struct { ... }
        match = re.search(rf'type\s+{re.escape(self.repo_path.stem)}\b', content)
        if not match:
            # 尝试提取所有 struct
            structs = re.findall(r'type\s+(\w+)\s+struct\s*\{(.*?)\n\}', content, re.DOTALL)
            return "\n\n".join(f"type {name} struct {{\n{body}\n}}" for name, body in structs[:3])

        return content[:2000]

    def _extract_method_code(self, file_path: str, struct_name: str) -> str:
        """提取 struct 的方法代码"""
        full_path = self.repo_path / file_path
        if not full_path.exists():
            return ""

        try:
            content = full_path.read_text(encoding='utf-8')
        except Exception:
            return ""

        # 找到 (s *StructName) Method( 或类似的模式
        pattern = rf'func\s+\(\s*\*?\s*{re.escape(struct_name)}\s+\w+\s*\)\s+\w+\s*\('
        matches = list(re.finditer(pattern, content))

        if not matches:
            return ""

        # 提取前3个方法
        snippets = []
        for m in matches[:3]:
            start = m.start()
            # 找方法结束位置（下一个 func 或 }）
            end_pattern = rf'\nfunc\s+'
            end_match = re.search(end_pattern, content[start + 1:])
            end = start + 1 + end_match.start() if end_match else start + 500
            snippet = content[start:end].strip()
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
            if s['type'] == 'struct' and s.get('fields'):
                lines.append("**Fields:**")
                for f in s['fields'][:5]:
                    tag = f" `{f.get('tag', '')}`" if f.get('tag') else ""
                    lines.append(f"- `{f['name']}`: {f['type']}{tag}")
            lines.append("")
            lines.append("**Code:**")
            lines.append("```go")
            lines.append(s['code'])
            lines.append("```")
            lines.append("")

        return '\n'.join(lines)
