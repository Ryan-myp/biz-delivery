#!/usr/bin/env python3
"""
Code Snippet Injector — 把关键代码片段注入 prompt
替代旧方案：只提取结构名让 LLM 猜实现
新方案：直接送代码给 LLM
"""

import re
from pathlib import Path
from typing import Dict, List, Optional


class CodeSnippetInjector:
    """从已扫描的 IR 中提取关键代码片段，注入到 prompt
    
    核心改进：
    - 不再只提取 struct 名称，而是提取完整的接口/类型定义
    - 支持 Go/Python/Java 三种语言
    - 自动识别关键文件（接口定义、核心逻辑）
    - 控制片段长度，避免 prompt 过长
    """
    
    # 关键模式匹配（用于识别重要代码）
    KEY_PATTERNS = {
        'go': [
            r'type\s+(\w+)\s+interface\s*\{',           # 接口定义
            r'type\s+(\w+)\s+struct\s*\{',              # 结构体定义
            r'func\s+\(\s*\*?(\w+)\s+\w+\s*\)\s+(\w+)', # 方法定义
        ],
        'python': [
            r'class\s+(\w+)',                            # 类定义
            r'def\s+(\w+)\s*\(',                        # 函数定义
        ],
    }
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
    
    def extract_key_snippets(self, ir, max_snippets: int = 10, max_chars_per_snippet: int = 800) -> List[Dict]:
        """从 repo 中提取关键代码片段
        
        Returns:
            List of {"name": str, "file": str, "code": str, "type": str}
        """
        snippets = []
        
        # 1. 提取接口定义
        interface_snippets = self._extract_interfaces(ir, max_snippets // 2)
        snippets.extend(interface_snippets)
        
        # 2. 提取核心结构体（带字段和方法的）
        struct_snippets = self._extract_structures(ir, max_snippets // 2)
        snippets.extend(struct_snippets)
        
        # 3. 提取关键方法实现
        method_snippets = self._extract_methods(ir, max_snippets - len(snippets))
        snippets.extend(method_snippets)
        
        return snippets
    
    def _extract_interfaces(self, ir, max_count: int) -> List[Dict]:
        """提取 Go 接口定义"""
        snippets = []
        
        for struct in ir.structs:
            if not struct.file:
                continue
            
            filepath = self.repo_path / struct.file if not struct.file.startswith('/') else Path(struct.file)
            if not filepath.exists():
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8', errors='ignore')
                
                # 找接口定义（type XXX interface { ... }）
                for match in re.finditer(r'type\s+(\w+)\s+interface\s*\{(.*?)^\}', content, re.MULTILINE | re.DOTALL):
                    name = match.group(1)
                    body = match.group(2).strip()
                    
                    # 过滤掉太大的接口
                    if len(body) > 600:
                        continue
                    
                    code = f"type {name} interface {{\n{body}\n}}"
                    
                    snippets.append({
                        "name": name,
                        "file": struct.file,
                        "code": code[:800],
                        "type": "interface"
                    })
                    
                    if len(snippets) >= max_count:
                        return snippets
                        
            except Exception:
                continue
        
        return snippets
    
    def _extract_structures(self, ir, max_count: int) -> List[Dict]:
        """提取 Go 结构体定义（带字段和方法签名）"""
        snippets = []
        
        for struct in ir.structs:
            if not struct.file or not struct.fields:
                continue
            
            filepath = self.repo_path / struct.file if not struct.file.startswith('/') else Path(struct.file)
            if not filepath.exists():
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8', errors='ignore')
                
                # 找 struct 定义
                pattern = rf'type\s+{re.escape(struct.name)}\s+struct\s*\{{(.*?)^\}}'
                match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
                
                if match:
                    body = match.group(1).strip()
                    code = f"type {struct.name} struct {{\n{body}\n}}"
                    
                    # 只显示有字段的 struct
                    if struct.fields:
                        snippets.append({
                            "name": struct.name,
                            "file": struct.file,
                            "code": code[:800],
                            "type": "struct"
                        })
                    
                    if len(snippets) >= max_count:
                        return snippets
                        
            except Exception:
                continue
        
        return snippets
    
    def _extract_methods(self, ir, max_count: int) -> List[Dict]:
        """提取关键方法实现"""
        snippets = []
        
        for func in ir.functions[:20]:  # 只看前20个函数
            if not func.file:
                continue
            
            filepath = self.repo_path / func.file if not func.file.startswith('/') else Path(func.file)
            if not filepath.exists():
                continue
            
            try:
                content = filepath.read_text(encoding='utf-8', errors='ignore')
                
                # 找方法定义
                pattern = rf'func\s+\(.*?\)\s+{re.escape(func.name)}\s*\('
                match = re.search(pattern, content)
                
                if match:
                    start = match.start()
                    # 往前找 func 关键字
                    line_start = content.rfind('\n', 0, start) + 1
                    
                    # 找匹配的 }
                    brace_count = 0
                    end_pos = len(content)
                    for i in range(start, len(content)):
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if brace_count <= 0:
                                end_pos = i + 1
                                break
                    
                    code = content[line_start:end_pos].strip()
                    
                    # 过滤太短或太长的代码
                    if 100 < len(code) < 1500:
                        snippets.append({
                            "name": func.name,
                            "file": func.file,
                            "code": code,
                            "type": "method"
                        })
                    
                    if len(snippets) >= max_count:
                        return snippets
                        
            except Exception:
                continue
        
        return snippets
    
    def inject_into_prompt(self, prompt: str, snippets: List[Dict]) -> str:
        """把代码片段注入到 prompt 中"""
        
        if not snippets:
            return prompt
        
        # 添加新的章节
        inject_section = "\n\n## 关键代码片段\n\n"
        inject_section += "以下是从代码中提取的关键接口定义、结构体和方法实现：\n\n"
        
        for s in snippets:
            inject_section += f"### `{s['name']}` ({s['type']})\n"
            inject_section += f"**文件**: `{s['file']}`\n\n"
            inject_section += f"```go\n{s['code']}\n```\n\n"
        
        # 插入到 prompt 末尾之前
        if "请基于以上信息" in prompt:
            parts = prompt.split("请基于以上信息")
            prompt = parts[0] + inject_section + "\n\n请基于以上信息和代码" + parts[1]
        else:
            prompt += inject_section
        
        return prompt


def generate_enhanced_prompt(ir, repos, dep_graph, repo_paths):
    """生成增强版 prompt（包含关键代码片段）
    
    Args:
        ir: IRDocument 对象
        repos: 仓库列表
        dep_graph: 依赖图
        repo_paths: 仓库路径列表
    
    Returns:
        str: 增强后的 prompt
    """
    from run_pipeline import LLMKnowledgeGenerator  # 复用现有的 prompt 生成
    
    generator = LLMKnowledgeGenerator()
    prompt = generator.build_prompt(ir, dep_graph, repos)
    
    # 对每个仓库提取代码片段
    all_snippets = []
    for repo_path in repo_paths:
        if repo_path and Path(repo_path).exists():
            injector = CodeSnippetInjector(repo_path)
            snippets = injector.extract_key_snippets(ir, max_snippets=8)
            all_snippets.extend(snippets)
    
    # 注入到 prompt
    if all_snippets:
        prompt = injector.inject_into_prompt(prompt, all_snippets)
    
    return prompt
