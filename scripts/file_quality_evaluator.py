#!/usr/bin/env python3
"""
文件质量评审标准
用于评估知识库深度文件的质量
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


class FileQualityEvaluator:
    """文件质量评估器"""
    
    # 评分标准权重
    WEIGHTS = {
        "source_code_depth": 0.30,      # 源码深度
        "real_cases": 0.25,             # 真实案例
        "architecture_clarity": 0.20,   # 架构清晰度
        "code_quality": 0.15,           # 代码质量
        "practical_value": 0.10,        # 实用价值
    }
    
    # 合格分数线
    PASS_SCORE = 70
    EXPERT_SCORE = 90
    
    def __init__(self, kb_path: str = None):
        self.kb_path = Path(kb_path) if kb_path else Path.home() / "ryan-personal-knowledge" / "knowledge"
        self.evaluation_history = []
    
    def evaluate_file(self, file_path: str) -> Dict[str, Any]:
        """评估单个文件"""
        path = Path(file_path) if isinstance(file_path, str) else file_path
        content = path.read_text(encoding="utf-8", errors="ignore")
        
        # 计算各项得分
        scores = {
            "source_code_depth": self._evaluate_source_code_depth(content),
            "real_cases": self._evaluate_real_cases(content),
            "architecture_clarity": self._evaluate_architecture_clarity(content),
            "code_quality": self._evaluate_code_quality(content),
            "practical_value": self._evaluate_practical_value(content),
        }
        
        # 计算总分
        total_score = sum(scores[k] * self.WEIGHTS[k] for k in scores)
        
        # 生成评级
        if total_score >= self.EXPERT_SCORE:
            grade = "专家级"
        elif total_score >= self.PASS_SCORE:
            grade = "合格"
        else:
            grade = "不合格"
        
        # 生成改进建议
        suggestions = self._generate_suggestions(scores)
        
        result = {
            "file": str(path.relative_to(self.kb_path)),
            "lines": len(content.split("\n")),
            "scores": scores,
            "total_score": round(total_score, 2),
            "grade": grade,
            "suggestions": suggestions,
            "evaluated_at": datetime.now().isoformat(),
        }
        
        self.evaluation_history.append(result)
        return result
    
    def _evaluate_source_code_depth(self, content: str) -> float:
        """评估源码深度（0-100）"""
        score = 50  # 基础分
        
        # 检查是否包含真实源码
        real_code_indicators = [
            "func ",  # Go函数定义
            "class ",  # Python类定义
            "struct ",  # C/Go结构体
            "interface ",  # Go接口
            "type ",  # Go类型定义
        ]
        
        code_count = sum(1 for indicator in real_code_indicators if indicator in content)
        score += min(code_count * 5, 30)
        
        # 检查是否只有占位符
        placeholder_patterns = [
            "func ExampleFunc",
            "这是关于",
            "以下是系统",
            "{title}",
        ]
        
        placeholder_count = sum(1 for p in placeholder_patterns if p in content)
        score -= placeholder_count * 10
        
        # 检查源码行数占比
        code_lines = sum(1 for line in content.split("\n") if line.strip().startswith("func ") or 
                        line.strip().startswith("class ") or line.strip().startswith("type "))
        total_lines = len(content.split("\n"))
        code_ratio = code_lines / max(total_lines, 1)
        score += code_ratio * 20
        
        return min(max(score, 0), 100)
    
    def _evaluate_real_cases(self, content: str) -> float:
        """评估真实案例（0-100）"""
        score = 50
        
        # 检查案例关键词
        case_keywords = ["实战", "案例", "生产", "故障", "排障", "优化", "问题", "解决"]
        case_count = sum(1 for kw in case_keywords if kw in content)
        score += case_count * 3
        
        # 检查是否有具体数据
        data_indicators = ["P99", "延迟", "吞吐", "QPS", "ms", "us", "100%", "<"]
        data_count = sum(1 for ind in data_indicators if ind in content)
        score += min(data_count * 2, 20)
        
        return min(max(score, 0), 100)
    
    def _evaluate_architecture_clarity(self, content: str) -> float:
        """评估架构清晰度（0-100）"""
        score = 50
        
        # 检查是否有架构图
        if "```" in content and ("+" in content or "┌" in content or "├" in content):
            score += 15
        
        # 检查章节结构
        sections = content.split("## ")[1:] if "## " in content else []
        score += min(len(sections) * 2, 15)
        
        # 检查是否有目录
        if "目录" in content or "Contents" in content:
            score += 10
        
        return min(max(score, 0), 100)
    
    def _evaluate_code_quality(self, content: str) -> float:
        """评估代码质量（0-100）"""
        score = 50
        
        # 检查代码块
        code_blocks = content.count("```") // 2
        score += min(code_blocks * 3, 15)
        
        # 检查注释
        comment_lines = sum(1 for line in content.split("\n") if line.strip().startswith("//") or
                           line.strip().startswith("#") or line.strip().startswith("/*"))
        score += min(comment_lines * 0.5, 10)
        
        return min(max(score, 0), 100)
    
    def _evaluate_practical_value(self, content: str) -> float:
        """评估实用价值（0-100）"""
        score = 50
        
        # 检查是否有配置示例
        if "config" in content.lower() or "yaml" in content.lower():
            score += 10
        
        # 检查是否有命令行示例
        if "$" in content or "bash" in content.lower():
            score += 10
        
        # 检查是否有性能数据
        if "benchmark" in content.lower() or "perf" in content.lower():
            score += 10
        
        return min(max(score, 0), 100)
    
    def _generate_suggestions(self, scores: Dict[str, float]) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        if scores.get("source_code_depth", 0) < 70:
            suggestions.append("增加更多真实源码片段，替换占位符代码")
        
        if scores.get("real_cases", 0) < 70:
            suggestions.append("补充更多生产环境实战案例")
        
        if scores.get("architecture_clarity", 0) < 70:
            suggestions.append("增加架构图和流程图")
        
        if scores.get("code_quality", 0) < 70:
            suggestions.append("增加代码注释和说明")
        
        if scores.get("practical_value", 0) < 70:
            suggestions.append("增加配置示例和使用指南")
        
        return suggestions
    
    def batch_evaluate(self, pattern: str = "*.md", min_lines: int = 500) -> List[Dict[str, Any]]:
        """批量评估文件"""
        results = []
        
        for file_path in self.kb_path.rglob(pattern):
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = len(content.split("\n"))
            
            if lines >= min_lines:
                result = self.evaluate_file(file_path)
                results.append(result)
        
        return results
    
    def generate_report(self, output_path: str = None) -> Dict[str, Any]:
        """生成评估报告"""
        if not self.evaluation_history:
            return {"error": "No evaluations performed"}
        
        # 统计分布
        grades = {}
        avg_scores = {}
        for category in self.WEIGHTS.keys():
            scores = [e["scores"].get(category, 0) for e in self.evaluation_history]
            avg_scores[category] = sum(scores) / len(scores) if scores else 0
        
        total_scores = [e["total_score"] for e in self.evaluation_history]
        avg_total = sum(total_scores) / len(total_scores) if total_scores else 0
        
        for e in self.evaluation_history:
            grade = e["grade"]
            grades[grade] = grades.get(grade, 0) + 1
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "total_files_evaluated": len(self.evaluation_history),
            "average_score": round(avg_total, 2),
            "grade_distribution": grades,
            "category_averages": {k: round(v, 2) for k, v in avg_scores.items()},
            "evaluation_history": self.evaluation_history[-20:],  # 最近20条
        }
        
        if output_path:
            Path(output_path).write_text(json.dumps(report, indent=2, ensure_ascii=False))
        
        return report


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="评估知识库文件质量")
    parser.add_argument("--file", help="评估单个文件")
    parser.add_argument("--batch", action="store_true", help="批量评估")
    parser.add_argument("--output", help="输出报告路径")
    
    args = parser.parse_args()
    
    evaluator = FileQualityEvaluator()
    
    if args.file:
        result = evaluator.evaluate_file(args.file)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.batch:
        results = evaluator.batch_evaluate()
        report = evaluator.generate_report(args.output)
        print(f"评估了 {len(results)} 个文件")
        print(f"平均分: {report['average_score']}")
        print(f"分布: {report['grade_distribution']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
