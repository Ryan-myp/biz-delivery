#!/usr/bin/env python3
"""
知识库质量分析工具

分析知识库内容质量，生成改进建议
"""

import os
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple


class KBQualityAnalyzer:
    """知识库质量分析器"""
    
    def __init__(self, kb_root: str):
        self.kb_root = Path(kb_root)
        self.files = []
        self.stats = {}
    
    def analyze(self) -> Dict:
        """分析知识库质量"""
        self._collect_files()
        self._calculate_stats()
        return self._generate_report()
    
    def _collect_files(self):
        """收集所有 Markdown 文件"""
        self.files = []
        for md_file in self.kb_root.rglob("*.md"):
            if md_file.name == "README.md":
                continue
            self.files.append(md_file)
    
    def _calculate_stats(self):
        """计算统计指标"""
        total_files = len(self.files)
        expert_files = 0
        deep_files = 0
        mid_files = 0
        thin_files = 0
        
        code_blocks = 0
        total_lines = 0
        practice_cases = 0
        
        for f in self.files:
            content = f.read_text(encoding="utf-8", errors="ignore")
            lines = len(content.split("\n"))
            total_lines += lines
            
            # 分类
            if lines >= 1000:
                expert_files += 1
            elif lines >= 500:
                deep_files += 1
            elif lines >= 200:
                mid_files += 1
            else:
                thin_files += 1
            
            # 统计代码块
            code_blocks += len(re.findall(r"```", content)) // 2
            
            # 统计实战案例
            if "实战案例" in content or "案例" in content:
                practice_cases += 1
        
        self.stats = {
            "total_files": total_files,
            "expert_files": expert_files,
            "deep_files": deep_files,
            "mid_files": mid_files,
            "thin_files": thin_files,
            "total_lines": total_lines,
            "code_blocks": code_blocks,
            "practice_cases": practice_cases,
            "avg_lines": total_lines // total_files if total_files > 0 else 0,
            "code_coverage": code_blocks / total_files if total_files > 0 else 0,
            "practice_coverage": practice_cases / total_files if total_files > 0 else 0,
        }
    
    def _generate_report(self) -> Dict:
        """生成质量报告"""
        s = self.stats
        
        report = {
            "summary": {
                "总文件数": s["total_files"],
                "总行数": s["total_lines"],
                "平均行数": s["avg_lines"],
            },
            "quality": {
                "专家级文件(≥1000行)": s["expert_files"],
                "深度文件(500-999行)": s["deep_files"],
                "中等文件(200-499行)": s["mid_files"],
                "薄文件(<200行)": s["thin_files"],
            },
            "content": {
                "代码块数": s["code_blocks"],
                "实战案例数": s["practice_cases"],
                "代码覆盖率": f"{s['code_coverage']:.1%}",
                "案例覆盖率": f"{s['practice_coverage']:.1%}",
            },
            "recommendations": self._generate_recommendations(),
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """生成改进建议"""
        recommendations = []
        s = self.stats
        
        if s["expert_files"] < 150:
            recommendations.append(
                f"专家级文件不足：当前{s['expert_files']}个，目标150个，还需{s[150 - s['expert_files']]}个"
            )
        
        if s["deep_files"] + s["expert_files"] < 250:
            recommendations.append(
                f"深度文件不足：当前{s['deep_files'] + s['expert_files']}个，目标250个"
            )
        
        if s["practice_coverage"] < 0.6:
            recommendations.append(
                f"实战案例覆盖率低：当前{s['practice_coverage']:.1%}，目标60%+"
            )
        
        if s["code_coverage"] < 0.8:
            recommendations.append(
                f"代码覆盖率低：当前{s['code_coverage']:.1%}，目标80%+"
            )
        
        return recommendations
    
    def print_report(self):
        """打印报告"""
        report = self.analyze()
        
        print("\n" + "=" * 60)
        print("    知识库质量分析报告")
        print("=" * 60)
        
        print("\n【概览】")
        for k, v in report["summary"].items():
            print(f"  {k}: {v}")
        
        print("\n【质量分布】")
        for k, v in report["quality"].items():
            print(f"  {k}: {v}")
        
        print("\n【内容质量】")
        for k, v in report["content"].items():
            print(f"  {k}: {v}")
        
        if report["recommendations"]:
            print("\n【改进建议】")
            for rec in report["recommendations"]:
                print(f"  • {rec}")
        
        print("\n" + "=" * 60)


def main():
    """主入口"""
    kb_root = os.path.expanduser("~/ryan-personal-knowledge/knowledge")
    
    analyzer = KBQualityAnalyzer(kb_root)
    analyzer.print_report()


if __name__ == "__main__":
    main()
