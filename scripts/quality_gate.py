#!/usr/bin/env python3
"""Quality Gate - 质量门禁系统

对分析结果进行多维度质量检查，给出评级。
"""
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class QualityGate:
    """质量门禁系统"""

    # 检查项定义
    CHECKS = {
        "result_file": {
            "name": "结果文件存在",
            "check": lambda d: os.path.exists(os.path.join(d, "analysis_result.json")),
            "weight": 10,
        },
        "summary_file": {
            "name": "摘要文件存在",
            "check": lambda d: os.path.exists(os.path.join(d, "summary.md")),
            "weight": 10,
        },
        "business_file": {
            "name": "业务分析文件存在",
            "check": lambda d: os.path.exists(os.path.join(d, "business_analysis.md")),
            "weight": 5,
        },
        "stages_complete": {
            "name": "阶段完成",
            "check": lambda d: _check_stages_complete(d),
            "weight": 20,
        },
        "no_errors": {
            "name": "无错误",
            "check": lambda d: _check_no_errors(d),
            "weight": 15,
        },
        "diagrams_generated": {
            "name": "图表生成",
            "check": lambda d: _check_diagrams(d),
            "weight": 15,
        },
        "patterns_detected": {
            "name": "模式检测",
            "check": lambda d: _check_patterns(d),
            "weight": 10,
        },
        "structs_found": {
            "name": "结构体识别",
            "check": lambda d: _check_structs(d),
            "weight": 5,
        },
        "summary_length": {
            "name": "摘要长度",
            "check": lambda d: _check_summary_length(d),
            "weight": 10,
        },
    }

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.results = {}
        self.score = 0
        self.max_score = sum(c["weight"] for c in self.CHECKS.values())

    def run(self) -> Dict:
        """执行质量门禁检查"""
        for check_name, check_def in self.CHECKS.items():
            result = check_def["check"](str(self.output_dir))
            if isinstance(result, tuple):
                passed, detail = result
            else:
                passed = bool(result)
                detail = ""
            self.results[check_name] = {
                "passed": passed,
                "detail": detail,
                "weight": check_def["weight"],
            }
            if passed:
                self.score += check_def["weight"]

        return self._generate_report()

    def _generate_report(self) -> Dict:
        """生成报告"""
        percentage = int(self.score / self.max_score * 100) if self.max_score > 0 else 0

        if percentage >= 90:
            rating = "A+"
            level = "顶级专家水平"
        elif percentage >= 80:
            rating = "A"
            level = "专业水平"
        elif percentage >= 70:
            rating = "B+"
            level = "良好水平"
        elif percentage >= 60:
            rating = "B"
            level = "一般水平"
        else:
            rating = "C"
            level = "需要改进"

        return {
            "rating": rating,
            "level": level,
            "score": self.score,
            "max_score": self.max_score,
            "percentage": percentage,
            "passed": percentage >= 60,
            "checks": self.results,
        }

    def print_report(self):
        """打印报告"""
        report = self._generate_report()

        print("=" * 60)
        print("📊 质量门禁报告")
        print("=" * 60)
        print(f"评级: {report['rating']} {report['level']}")
        print(f"得分: {report['score']}/{report['max_score']} ({report['percentage']}%)")
        print(f"状态: {'✅ 通过' if report['passed'] else '❌ 不通过'}")
        print()
        print("检查项:")
        for check_name, check_result in self.results.items():
            status = "✅" if check_result["passed"] else "❌"
            weight = check_result["weight"]
            detail = check_result.get("detail", "")
            print(f"  {status} {check_name} (权重{weight}) {detail}")
        print()
        print("=" * 60)


def _check_stages_complete(output_dir: str) -> Tuple[bool, str]:
    """检查阶段完成情况"""
    result_file = os.path.join(output_dir, "analysis_result.json")
    if not os.path.exists(result_file):
        return False, "无结果文件"

    with open(result_file) as f:
        data = json.load(f)

    stages = data.get("stages", {})
    completed = sum(1 for v in stages.values() if not v.get("_error"))
    total = len(stages)

    # 至少完成 5 个阶段
    passed = completed >= 5
    return passed, f"{completed}/{total}"


def _check_no_errors(output_dir: str) -> Tuple[bool, str]:
    """检查是否有错误"""
    result_file = os.path.join(output_dir, "analysis_result.json")
    if not os.path.exists(result_file):
        return False, "无结果文件"

    with open(result_file) as f:
        data = json.load(f)

    errors = data.get("errors", [])
    warnings = data.get("warnings", [])

    # 允许少量 warning，但不允许 error
    passed = len(errors) == 0
    detail = f"errors={len(errors)}, warnings={len(warnings)}"
    return passed, detail


def _check_diagrams(output_dir: str) -> Tuple[bool, str]:
    """检查图表生成情况"""
    result_file = os.path.join(output_dir, "analysis_result.json")
    if not os.path.exists(result_file):
        return False, "无结果文件"

    with open(result_file) as f:
        data = json.load(f)

    stages = data.get("stages", {})
    diagrams = stages.get("diagrams", {}).get("diagrams", {})

    passed = len(diagrams) >= 3
    return passed, f"{len(diagrams)} 张"


def _check_patterns(output_dir: str) -> Tuple[bool, str]:
    """检查模式检测情况"""
    result_file = os.path.join(output_dir, "analysis_result.json")
    if not os.path.exists(result_file):
        return False, "无结果文件"

    with open(result_file) as f:
        data = json.load(f)

    stages = data.get("stages", {})
    patterns = stages.get("patterns", {})

    # 检查各种模式类型
    pattern_types = [
        "state_machines", "redis_locks", "retry_logic",
        "kafka_patterns", "idempotency", "task_group_patterns", "enums"
    ]
    total_patterns = sum(len(patterns.get(pt, [])) for pt in pattern_types)

    passed = total_patterns >= 1
    return passed, f"{total_patterns} 类"


def _check_structs(output_dir: str) -> Tuple[bool, str]:
    """检查结构体识别情况"""
    result_file = os.path.join(output_dir, "analysis_result.json")
    if not os.path.exists(result_file):
        return False, "无结果文件"

    with open(result_file) as f:
        data = json.load(f)

    ir = data.get("ir_summary", {})
    struct_count = ir.get("structs", 0)

    passed = struct_count > 0
    return passed, f"{struct_count}"


def _check_summary_length(output_dir: str) -> Tuple[bool, str]:
    """检查摘要长度"""
    summary_file = os.path.join(output_dir, "summary.md")
    if not os.path.exists(summary_file):
        return False, "无摘要文件"

    with open(summary_file) as f:
        content = f.read()

    length = len(content)
    passed = length >= 100  # 降低标准到 100 字符
    return passed, f"{length} 字符"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 quality_gate.py <output_dir>")
        sys.exit(1)

    gate = QualityGate(sys.argv[1])
    report = gate.run()
    gate.print_report()
    sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
