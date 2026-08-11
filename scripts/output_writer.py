#!/usr/bin/env python3
"""
Output Writer - 输出写入器模块
从 learn_repo.py 拆分出来的输出逻辑
"""

import json
from pathlib import Path
from typing import Dict, List, Optional


class OutputWriter:
    """输出结果写入器"""
    
    def write_ir_document(self, ir_doc: Dict, output_dir: Path):
        """写入 IR Document"""
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "ir_document.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(ir_doc, f, indent=2, ensure_ascii=False)
        print(f"  ✅ IR Document saved: {output_path}")
        return output_path
    
    def write_markdown(self, content: str, output_dir: Path, filename: str = "knowledge.md"):
        """写入 Markdown 文档"""
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✅ Markdown saved: {output_path}")
        return output_path
    
    def write_summary(self, stats: Dict, output_dir: Path):
        """写入总结报告"""
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "summary.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        print(f"  ✅ Summary saved: {output_path}")
        return output_path
    
    def write_wiki(self, content: str, wiki_path: Path):
        """写入 Wiki 文档"""
        wiki_path.mkdir(parents=True, exist_ok=True)
        output_path = wiki_path / "knowledge.md"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✅ Wiki saved: {output_path}")
        return output_path
