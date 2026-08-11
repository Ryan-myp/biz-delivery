#!/usr/bin/env python3
"""
知识库质量评估与升级建议

分析知识库内容，生成升级建议
"""

import os
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple


class KBAnalyzer:
    """知识库分析器"""
    
    def __init__(self, kb_root: Path):
        self.kb_root = kb_root
        self.files = []
        self.issues = []
    
    def analyze(self):
        """分析知识库"""
        for md in self.kb_root.rglob("*.md"):
            if md.name == "README.md":
                continue
            self._analyze_file(md)
    
    def _analyze_file(self, path: Path):
        """分析单个文件"""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return
        
        lines = len(content.split("\n"))
        chars = len(content.encode("utf-8"))
        
        # 检查质量指标
        has_code = "```" in content
        has_diagram = any(kw in content for kw in ["架构图", "时序图", "流程图"])
        has_case = any(kw in content for kw in ["案例", "实战", "排障"])
        has_fail = any(kw in content for kw in ["失败", "踩坑", "教训"])
        
        # 计算质量分
        score = 0
        if lines >= 1000:
            score += 40
        elif lines >= 500:
            score += 25
        elif lines >= 200:
            score += 10
        
        if has_code:
            score += 20
        if has_diagram:
            score += 15
        if has_case:
            score += 15
        if has_fail:
            score += 10
        
        # 检查问题
        issues = []
        if lines < 500:
            issues.append(f"文件较短({lines}行)，建议扩展到500行以上")
        if not has_code:
            issues.append("缺少代码示例")
        if not has_case:
            issues.append("缺少实战案例")
        if not has_fail:
            issues.append("缺少失败经验总结")
        
        self.files.append({
            "path": str(path),
            "lines": lines,
            "chars": chars,
            "score": score,
            "issues": issues
        })
        
        self.issues.extend([
            {"file": str(path), "issue": issue}
            for issue in issues
        ])
    
    def get_upgrade_candidates(self, min_score: int = 50) -> List[Dict]:
        """获取待升级文件"""
        return [f for f in self.files if f["score"] < min_score]
    
    def generate_report(self) -> str:
        """生成报告"""
        lines = [
            "# 知识库质量评估报告",
            "",
            f"> 生成时间：2026-08-11",
            f"> 路径：{self.kb_root}",
            ""
        ]
        
        # 统计
        total = len(self.files)
        expert = sum(1 for f in self.files if f["lines"] >= 1000)
        deep = sum(1 for f in self.files if 500 <= f["lines"] < 1000)
        mid = sum(1 for f in self.files if 200 <= f["lines"] < 500)
        thin = sum(1 for f in self.files if f["lines"] < 200)
        
        lines.extend([
            "## 一、整体统计",
            "",
            f"| 指标 | 数量 | 占比 |",
            f"|------|------|------|",
            f"| 总文件 | {total} | 100% |",
            f"| 🟢 专家级(≥1000行) | {expert} | {expert*100//max(total,1)}% |",
            f"| 🟢 深度(500-999行) | {deep} | {deep*100//max(total,1)}% |",
            f"| 🟡 中等(200-499行) | {mid} | {mid*100//max(total,1)}% |",
            f"| 🟠 薄(<200行) | {thin} | {thin*100//max(total,1)}% |",
            ""
        ])
        
        # 待升级文件
        candidates = self.get_upgrade_candidates()
        if candidates:
            lines.extend([
                "## 二、待升级文件",
                ""
            ])
            
            # 按板块分组
            by_domain = defaultdict(list)
            for f in candidates:
                domain = f["path"].split("/")[-2] if len(f["path"].split("/")) > 2 else "other"
                by_domain[domain].append(f)
            
            for domain, files in sorted(by_domain.items(), key=lambda x: -len(x[1]))[:5]:
                lines.extend([
                    f"### {domain}",
                    ""
                ])
                for f in sorted(files, key=lambda x: x["lines"])[:5]:
                    lines.append(f"- `{Path(f['path']).name}`: {f['lines']} 行, 缺{'少代码/案例' if '缺少' in str(f['issues']) else ''}")
                lines.append("")
        
        return "\n".join(lines)


def main():
    kb_root = Path.home() / "ryan-personal-knowledge" / "knowledge"
    analyzer = KBAnalyzer(kb_root)
    analyzer.analyze()
    report = analyzer.generate_report()
    
    output_path = Path.home() / ".hermes" / "scripts" / "reports" / "kb-quality-report-20260811.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    
    print(f"✅ 报告已生成: {output_path}")
    print(f"\n统计: 总文件 {len(analyzer.files)}, 待升级 {len(analyzer.get_upgrade_candidates())}")


if __name__ == "__main__":
    main()
