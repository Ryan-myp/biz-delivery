#!/usr/bin/env python3
"""
biz-delivery 优化检查清单
用于 AI 分析项目状态，识别优化机会
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any

BASE_DIR = Path("/Users/yanping.ma/biz-delivery")

def run_cmd(cmd: str) -> str:
    """运行命令并返回输出"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout + result.stderr
    except Exception as e:
        return f"Error: {e}"

def check_test_coverage() -> Dict[str, Any]:
    """检查测试覆盖率"""
    print("📊 检查测试覆盖率...")
    output = run_cmd("python3 -m pytest tests/ --cov=scripts --cov-report=term-missing -q")
    
    coverage = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "warnings": 0,
        "missing_lines": []
    }
    
    # 解析输出
    for line in output.split('\n'):
        if 'passed' in line and 'failed' in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == 'passed':
                    coverage["passed"] = int(parts[i-1]) if i > 0 else 0
                elif part == 'failed':
                    coverage["failed"] = int(parts[i-1]) if i > 0 else 0
                elif part == 'warnings':
                    coverage["warnings"] = int(parts[i-1]) if i > 0 else 0
        if 'TOTAL' in line or 'coverage' in line.lower():
            if '%' in line:
                try:
                    coverage["total"] = int(line.split('%')[0].strip().split()[-1])
                except:
                    pass
    
    return coverage

def find_issues() -> List[Dict[str, str]]:
    """查找项目中的问题"""
    issues = []
    
    # 查找 TODO/FIXME
    print("🔍 查找 TODO/FIXME...")
    output = run_cmd("grep -r \"TODO\\|FIXME\\|HACK\" scripts/ tests/ 2>/dev/null | head -20")
    if output.strip():
        issues.append({
            "type": "todo",
            "description": "发现 TODO/FIXME 标记",
            "detail": output.strip()[:500]
        })
    
    # 查找未使用的导入
    print("🔍 查找未使用的导入...")
    output = run_cmd("grep -r \"^import\\|^from\" scripts/ | wc -l")
    if output.strip():
        issues.append({
            "type": "imports",
            "description": f"发现 {output.strip()} 个导入语句"
        })
    
    # 检查测试文件
    print("🔍 检查测试覆盖...")
    test_files = list(BASE_DIR.glob("tests/test_*.py"))
    script_files = list((BASE_DIR / "scripts").glob("*.py"))
    
    if len(test_files) < len(script_files) * 0.5:
        issues.append({
            "type": "test_coverage",
            "description": f"测试文件数量不足 ({len(test_files)} vs {len(script_files)} 个脚本)",
            "severity": "high"
        })
    
    return issues

def analyze_project_structure() -> Dict[str, Any]:
    """分析项目结构"""
    print("📁 分析项目结构...")
    
    structure = {
        "total_files": 0,
        "python_files": 0,
        "test_files": 0,
        "docs_files": 0,
        "modules": []
    }
    
    for path in BASE_DIR.rglob("*"):
        structure["total_files"] += 1
        if path.suffix == '.py':
            structure["python_files"] += 1
            if 'test' in path.parts:
                structure["test_files"] += 1
        elif path.suffix in ['.md', '.txt']:
            structure["docs_files"] += 1
    
    return structure

def main():
    """主函数"""
    print("=" * 60)
    print("🔍 biz-delivery 项目优化分析")
    print("=" * 60)
    print()
    
    # 分析项目结构
    structure = analyze_project_structure()
    print(f"📊 项目统计:")
    print(f"   - 总文件数: {structure['total_files']}")
    print(f"   - Python 文件: {structure['python_files']}")
    print(f"   - 测试文件: {structure['test_files']}")
    print(f"   - 文档文件: {structure['docs_files']}")
    print()
    
    # 检查测试覆盖率
    coverage = check_test_coverage()
    print(f"📊 测试覆盖率: {coverage['total']}%")
    print(f"   - 通过: {coverage['passed']}")
    print(f"   - 失败: {coverage['failed']}")
    print(f"   - 警告: {coverage['warnings']}")
    print()
    
    # 查找问题
    issues = find_issues()
    if issues:
        print("⚠️  发现问题:")
        for issue in issues:
            print(f"   - [{issue['type']}] {issue['description']}")
        print()
    
    # 输出总结
    print("=" * 60)
    print("✅ 分析完成")
    print("=" * 60)
    
    return {
        "structure": structure,
        "coverage": coverage,
        "issues": issues
    }

if __name__ == "__main__":
    main()
