#!/usr/bin/env python3
"""质量门禁 — 验证分析输出是否达到专家级标准.

检查项:
1. 必填字段存在性
2. 内容完整性
3. 模式检测覆盖率
4. 图表生成数量
5. 数据一致性
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple


# ── 专家级标准定义 ─────────────────────────────────────────────

EXPERT_LEVEL_STANDARDS = {
    "min_stages": 7,          # 至少完成 7 个阶段
    "max_errors": 0,          # 不允许有错误
    "min_diagrams": 5,        # 至少生成 5 张图
    "min_patterns": 3,        # 至少检测到 3 类模式
    "min_structs": 5,         # 至少识别 5 个结构体
    "summary_min_length": 500,  # 摘要至少 500 字符
}


def verify_analysis(output_dir: str) -> Dict:
    """验证分析结果是否符合专家级标准."""
    results = {
        "passed": True,
        "score": 0,
        "max_score": 100,
        "checks": [],
        "warnings": [],
        "errors": [],
    }

    output_path = Path(output_dir)
    result_json = output_path / "analysis_result.json"
    summary_md = output_path / "summary.md"

    # ── 检查 1: 必须有 analysis_result.json ────────────────────
    if not result_json.exists():
        results["errors"].append("缺少 analysis_result.json")
        results["passed"] = False
        return results
    results["checks"].append({"name": "结果文件存在", "status": "pass"})

    # ── 检查 2: 必须有 summary.md ──────────────────────────────
    if not summary_md.exists():
        results["errors"].append("缺少 summary.md")
        results["passed"] = False
        return results
    results["checks"].append({"name": "摘要文件存在", "status": "pass"})

    # ── 加载分析结果 ───────────────────────────────────────────
    try:
        with open(result_json) as f:
            data = json.load(f)
    except Exception as e:
        results["errors"].append(f"解析 analysis_result.json 失败: {e}")
        results["passed"] = False
        return results

    # ── 检查 3: 阶段完成情况 ───────────────────────────────────
    stages = data.get("stages", {})
    stage_count = len([k for k, v in stages.items() if not v.get("_error")])
    expected_stages = EXPERT_LEVEL_STANDARDS["min_stages"]

    if stage_count >= expected_stages:
        results["checks"].append({
            "name": f"阶段完成 ({stage_count}/{expected_stages})",
            "status": "pass",
            "score": 20,
        })
        results["score"] += 20
    else:
        results["checks"].append({
            "name": f"阶段完成 ({stage_count}/{expected_stages})",
            "status": "fail",
            "score": 0,
        })
        results["warnings"].append(f"仅完成 {stage_count} 个阶段，期望 {expected_stages}")

    # ── 检查 4: 错误数 ─────────────────────────────────────────
    errors = data.get("errors", [])
    if len(errors) == 0:
        results["checks"].append({
            "name": "无错误",
            "status": "pass",
            "score": 20,
        })
        results["score"] += 20
    else:
        results["checks"].append({
            "name": f"错误数 ({len(errors)})",
            "status": "fail",
            "score": 0,
        })
        results["errors"].extend(errors[:3])  # 最多显示3个

    # ── 检查 5: 图表生成 ───────────────────────────────────────
    diagrams = stages.get("diagrams", {})
    diagram_count = len(diagrams.get("diagrams", {})) if diagrams else 0
    min_diagrams = EXPERT_LEVEL_STANDARDS["min_diagrams"]

    if diagram_count >= min_diagrams:
        results["checks"].append({
            "name": f"图表生成 ({diagram_count} 张)",
            "status": "pass",
            "score": 20,
        })
        results["score"] += 20
    else:
        results["checks"].append({
            "name": f"图表生成 ({diagram_count} 张)",
            "status": "fail",
            "score": 0,
        })
        results["warnings"].append(f"仅生成 {diagram_count} 张图，期望 {min_diagrams}")

    # ── 检查 6: 模式检测 ───────────────────────────────────────
    patterns = stages.get("patterns", {})
    pattern_types = sum(1 for k, v in patterns.items() if isinstance(v, list) and len(v) > 0)
    min_patterns = EXPERT_LEVEL_STANDARDS["min_patterns"]

    if pattern_types >= min_patterns:
        results["checks"].append({
            "name": f"模式检测 ({pattern_types} 类)",
            "status": "pass",
            "score": 20,
        })
        results["score"] += 20
    else:
        results["checks"].append({
            "name": f"模式检测 ({pattern_types} 类)",
            "status": "fail",
            "score": 0,
        })
        results["warnings"].append(f"仅检测到 {pattern_types} 类模式，期望 {min_patterns}")

    # ── 检查 7: IR 数据完整性 ──────────────────────────────────
    ir_summary = data.get("ir_summary", {})
    struct_count = ir_summary.get("structs", 0)
    func_count = ir_summary.get("functions", 0)

    if struct_count >= EXPERT_LEVEL_STANDARDS["min_structs"]:
        results["checks"].append({
            "name": f"结构体识别 ({struct_count})",
            "status": "pass",
            "score": 10,
        })
        results["score"] += 10
    else:
        results["checks"].append({
            "name": f"结构体识别 ({struct_count})",
            "status": "warn",
            "score": 5,
        })
        results["warnings"].append(f"仅识别 {struct_count} 个结构体")

    # ── 检查 8: 摘要长度 ───────────────────────────────────────
    if summary_md.exists():
        summary_text = summary_md.read_text(encoding="utf-8")
        min_length = EXPERT_LEVEL_STANDARDS["summary_min_length"]
        if len(summary_text) >= min_length:
            results["checks"].append({
                "name": f"摘要长度 ({len(summary_text)} 字符)",
                "status": "pass",
                "score": 10,
            })
            results["score"] += 10
        else:
            results["checks"].append({
                "name": f"摘要长度 ({len(summary_text)} 字符)",
                "status": "fail",
                "score": 0,
            })
            results["warnings"].append(f"摘要仅 {len(summary_text)} 字符，期望 {min_length}")

    # ── 计算最终评级 ───────────────────────────────────────────
    score = results["score"]
    if score >= 90:
        grade = "A+ 顶级专家水平"
    elif score >= 80:
        grade = "A 优秀"
    elif score >= 70:
        grade = "B+ 良好"
    elif score >= 60:
        grade = "B 及格"
    else:
        grade = "C 需改进"

    results["grade"] = grade
    results["passed"] = results["passed"] and len(results["errors"]) == 0

    return results


def print_report(results: Dict):
    """打印质量报告."""
    print("\n" + "=" * 60)
    print("📊 质量门禁报告")
    print("=" * 60)
    print(f"评级: {results.get('grade', 'N/A')}")
    print(f"得分: {results.get('score', 0)}/{results.get('max_score', 100)}")
    print(f"状态: {'✅ 通过' if results.get('passed') else '❌ 未通过'}")
    print()

    print("检查项:")
    for check in results.get("checks", []):
        icon = "✅" if check["status"] == "pass" else "⚠️" if check["status"] == "warn" else "❌"
        print(f"  {icon} {check['name']}")
    print()

    if results.get("warnings"):
        print("警告:")
        for w in results["warnings"]:
            print(f"  ⚠️  {w}")
        print()

    if results.get("errors"):
        print("错误:")
        for e in results["errors"]:
            print(f"  ❌ {e}")
        print()

    print("=" * 60)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 quality_gate.py <output_dir>")
        sys.exit(1)

    results = verify_analysis(sys.argv[1])
    print_report(results)

    sys.exit(0 if results["passed"] else 1)
