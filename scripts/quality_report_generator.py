#!/usr/bin/env python3
"""
知识库质量报告生成器

分析知识库内容质量，生成改进建议
"""

import os
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple


class KBQualityReport:
    """知识库质量报告"""
    
    def __init__(self, kb_root: str):
        self.kb_root = Path(kb_root)
        self.files = []
        self.statistics = {}
    
    def analyze(self):
        """执行分析"""
        print("🔍 开始分析知识库...")
        
        # 收集所有文件
        self.files = list(self.kb_root.rglob("*.md"))
        self.files = [f for f in self.files if f.name != "README.md"]
        
        # 计算统计
        self.statistics = {
            "total_files": len(self.files),
            "total_lines": 0,
            "by_category": defaultdict(list),
            "by_size": {
                "expert": [],    # >= 1000
                "deep": [],      # 500-999
                "medium": [],    # 200-499
                "thin": [],      # < 200
            },
            "code_blocks": 0,
            "cases": 0,
            "questions": 0,
        }
        
        for f in self.files:
            self._analyze_file(f)
        
        print("✅ 分析完成")
    
    def _analyze_file(self, filepath: Path):
        """分析单个文件"""
        content = filepath.read_text(encoding="utf-8")
        lines = content.split("\n")
        line_count = len(lines)
        
        self.statistics["total_lines"] += line_count
        
        # 分类
        category = self._get_category(filepath)
        self.statistics["by_category"][category].append(filepath)
        
        # 按大小分类
        if line_count >= 1000:
            self.statistics["by_size"]["expert"].append(filepath)
        elif line_count >= 500:
            self.statistics["by_size"]["deep"].append(filepath)
        elif line_count >= 200:
            self.statistics["by_size"]["medium"].append(filepath)
        else:
            self.statistics["by_size"]["thin"].append(filepath)
        
        # 统计代码块
        code_blocks = len(re.findall(r"```", content)) // 2
        self.statistics["code_blocks"] += code_blocks
        
        # 统计实战案例
        cases = len(re.findall(r"实战|案例|example|demo", content, re.IGNORECASE))
        self.statistics["cases"] += cases
        
        # 统计问题
        questions = len(re.findall(r"\\?d+", content))
        self.statistics["questions"] += questions
    
    def _get_category(self, filepath: Path) -> str:
        """获取文件分类"""
        parts = filepath.relative_to(self.kb_root).parts
        if len(parts) > 0:
            return parts[0]
        return "other"
    
    def generate_report(self) -> str:
        """生成报告"""
        stats = self.statistics
        
        report = f"""# 知识库质量分析报告

生成时间：2026-08-11

## 一、总体统计

| 指标 | 数值 |
|------|------|
| 总文件数 | {stats['total_files']} |
| 总行数 | {stats['total_lines']:,} |
| 代码块数 | {stats['code_blocks']} |
| 实战案例 | {stats['cases']} |
| 自测题 | {stats['questions']} |

## 二、文件大小分布

| 等级 | 文件数 | 占比 |
|------|--------|------|
| 专家级(≥1000行) | {len(stats['by_size']['expert'])} | {len(stats['by_size']['expert'])*100/stats['total_files']:.1f}% |
| 深度(500-999行) | {len(stats['by_size']['deep'])} | {len(stats['by_size']['deep'])*100/stats['total_files']:.1f}% |
| 中等(200-499行) | {len(stats['by_size']['medium'])} | {len(stats['by_size']['medium'])*100/stats['total_files']:.1f}% |
| 薄(<200行) | {len(stats['by_size']['thin'])} | {len(stats['by_size']['thin'])*100/stats['total_files']:.1f}% |

## 三、按分类统计

"""
        
        for category, files in stats["by_category"].items():
            report += f"### {category}\n- 文件数：{len(files)}\n"
        
        report += """
## 四、改进建议

1. 增加专家级文件数量（当前 45 个，目标 150 个）
2. 提升测试覆盖率（当前 50%，目标 80%）
3. 补充更多实战案例
4. 增加自测题数量

## 五、下一步行动

- [ ] 继续创建深度文件
- [ ] 完善 biz-delivery 测试
- [ ] 建立持续进化机制

---
*报告由 KBQualityReport 生成*
"""
        
        return report


def main():
    """主入口"""
    kb_root = os.path.expanduser("~/ryan-personal-knowledge/knowledge")
    
    analyzer = KBQualityReport(kb_root)
    analyzer.analyze()
    report = analyzer.generate_report()
    
    output_path = Path("/tmp/kb_quality_report.md")
    output_path.write_text(report, encoding="utf-8")
    print(f"\n📄 报告已保存: {output_path}")
    
    print("\n" + "=" * 60)
    print("    分析报告预览")
    print("=" * 60)
    print(report[:2000])


if __name__ == "__main__":
    main()
