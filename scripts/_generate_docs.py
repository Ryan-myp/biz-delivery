"""文档自动生成"""
import json
from pathlib import Path

def generate_docs(ir: dict, kb_dir: str):
    """生成文档包"""
    kb_path = Path(kb_dir)
    packages = ir.get('packages', {})
    flow = ir.get('flow', {})
    
    # architecture.md
    arch_lines = [
        "# 项目架构总览",
        "",
        "## 概览",
        f"- 仓库: {ir.get('repo_name', 'unknown')}",
        f"- 语言: {ir.get('language', 'unknown')}",
        f"- 包数: {len(packages)}",
        "",
        "## 包结构",
        ""
    ]
    
    sorted_pkgs = sorted(packages.items(), key=lambda x: len(x[1].get('files', [])), reverse=True)
    for pkg, data in sorted_pkgs:
        arch_lines.append(f"### `{pkg}`")
        arch_lines.append(f"- Files: {len(data.get('files', []))}")
        interfaces = data.get('interfaces', {})
        if interfaces:
            arch_lines.append(f"- **Interfaces**: {', '.join(interfaces.keys())[:100]}")
        funcs = data.get('functions', [])
        if funcs:
            arch_lines.append(f"- **Key Functions**: {', '.join(funcs[:5])}")
        arch_lines.append("")
    
    (kb_path / 'architecture.md').write_text('\n'.join(arch_lines), encoding='utf-8')
    
    # flows.md
    flow_lines = ["# 核心流程", "", "## 启动流程", ""]
    for s in flow.get('startup', []):
        flow_lines.append(f"### `{s.get('file', '')}`")
        flow_lines.append(f"```")
        flow_lines.append(s.get('file', ''))
        flow_lines.append(f"  ↓")
        calls = s.get('calls', [])
        flow_lines.append(f"  {', '.join(calls[:5])}")
        flow_lines.append(f"```")
        flow_lines.append("")
    
    (kb_path / 'flows.md').write_text('\n'.join(flow_lines), encoding='utf-8')
    
    # schema.md
    schema_lines = ["# 数据结构", "", "## 核心结构体", ""]
    for s in ir.get('structs', [])[:20]:
        schema_lines.append(f"### `{s.get('name', '')}`")
        schema_lines.append(f"- File: `{s.get('file', '')}`")
        fields = s.get('fields', [])
        if fields:
            schema_lines.append(f"- Fields: {', '.join(fields[:5])}")
        schema_lines.append("")
    
    (kb_path / 'schema.md').write_text('\n'.join(schema_lines), encoding='utf-8')
    
    # glossary.md
    glossary_lines = ["# 术语表", "", "## 核心术语", ""]
    for pkg, data in sorted_pkgs[:10]:
        interfaces = data.get('interfaces', {})
        if interfaces:
            glossary_lines.append(f"### `{pkg}`")
            for iface, info in list(interfaces.items())[:5]:
                methods = info.get('methods', [])
                glossary_lines.append(f"- **{iface}**: {', '.join(methods[:3])}")
            glossary_lines.append("")
    
    (kb_path / 'glossary.md').write_text('\n'.join(glossary_lines), encoding='utf-8')
