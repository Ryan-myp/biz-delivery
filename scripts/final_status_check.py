#!/usr/bin/env python3
"""
最终验收 - 检查当前状态并生成报告
"""

from pathlib import Path
import json
from datetime import datetime


def check_status():
    """检查当前状态"""
    kb_path = Path.home() / "ryan-personal-knowledge" / "knowledge"
    files = list(kb_path.rglob("*.md"))
    
    expert_count = 0
    deep_count = 0
    total_lines = 0
    
    for f in files:
        content = f.read_text(errors="ignore")
        lines = len(content.split("\n"))
        total_lines += lines
        
        if lines >= 1000:
            expert_count += 1
        elif lines >= 500:
            deep_count += 1
    
    # biz-delivery统计
    biz_path = Path.home() / "biz-delivery"
    biz_files = list(biz_path.rglob("*.py"))
    biz_lines = sum(len(f.read_text(errors="ignore").split("\n")) for f in biz_files)
    
    return {
        "knowledge_base": {
            "total_files": len(files),
            "expert_level": expert_count,
            "deep_level": deep_count,
            "total_lines": total_lines,
            "expert_target": 100,
            "deep_target": 300,
        },
        "biz_delivery": {
            "total_files": len(biz_files),
            "total_lines": biz_lines,
        },
        "timestamp": datetime.now().isoformat(),
    }


def main():
    status = check_status()
    
    kb = status["knowledge_base"]
    biz = status["biz_delivery"]
    
    print("="*70)
    print("📊 全面优化迭代完成 - 最终状态报告")
    print("="*70)
    print()
    print("知识库:")
    print(f"  - 总文件数: {kb['total_files']}")
    print(f"  - 专家级(≥1000行): {kb['expert_level']}/{kb['expert_target']} ({kb['expert_level']/kb['expert_target']*100:.1f}%)")
    print(f"  - 深度(500-999行): {kb['deep_level']}/{kb['deep_target']} ({kb['deep_level']/kb['deep_target']*100:.1f}%)")
    print(f"  - 总代码行数: {kb['total_lines']:,}")
    print()
    print("biz-delivery:")
    print(f"  - Python文件: {biz['total_files']}")
    print(f"  - 总代码行数: {biz['total_lines']:,}")
    print()
    
    # 保存报告
    report_path = Path.home() / ".hermes" / "scripts" / "reports" / "final-status-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(status, indent=2, ensure_ascii=False))
    
    print(f"📁 详细报告: {report_path}")
    print("="*70)


if __name__ == "__main__":
    main()
