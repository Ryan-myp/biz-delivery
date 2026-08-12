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
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        return result.stdout + result.stderr
    except Exception as e:
        return f"Error: {e}"

def check_test_coverage() -> Dict[str, Any]:
    """检查测试覆盖率"""
    print("📊 检查测试覆盖率...")
    output = run_cmd("cd /Users/yanping.ma/biz-delivery && python3 -m pytest tests/ -q --tb=no 2>&1")
    
    coverage = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "warnings": 0
    }
    
    # 解析输出
    lines = output.split('\n')
    for line in lines:
        if 'passed' in line and 'failed' in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == 'passed':
                    try:
                        coverage["passed"] = int(parts[i-1]) if i > 0 else 0
                    except:
                        pass
                elif part == 'failed':
                    try:
                        coverage["failed"] = int(parts[i-1]) if i > 0 else 0
                    except:
                        pass
                elif part == 'error':
                    try:
                        coverage["errors"] = int(parts[i-1]) if i > 0 else 0
                    except:
                        pass
        if 'warning' in line.lower() and 'passed' not in line:
            try:
                coverage["warnings"] = int(line.strip().split()[0])
            except:
                pass
    
    # 尝试获取覆盖率
    cov_output = run_cmd("cd /Users/yanping.ma/biz-delivery && python3 -m pytest tests/ --cov=scripts --cov-report=term-missing -q 2>&1")
    for line in cov_output.split('\n'):
        if 'TOTAL' in line or '%' in line:
            try:
                parts = line.split()
                for part in parts:
                    if '%' in part:
                        coverage["total"] = int(part.replace('%', ''))
            except:
                pass
    
    return coverage

def find_issues() -> List[Dict[str, str]]:
    """查找项目中的问题"""
    issues = []
    
    # 查找 TODO/FIXME
    print("🔍 查找 TODO/FIXME...")
    output = run_cmd("grep -r \"TODO\\|FIXME\\|HACK\" /Users/yanping.ma/biz-delivery/scripts/ 2>/dev/null | head -20")
    if output.strip():
        issues.append({
            "type": "todo",
            "description": "发现 TODO/FIXME 标记",
            "detail": output.strip()[:500],
            "severity": "medium"
        })
    
    # 查找未使用的导入（简单检查）
    print("🔍 检查代码质量...")
    output = run_cmd("flake8 /Users/yanping.ma/biz-delivery/scripts/ --max-line-length=100 2>/dev/null | head -20")
    if output.strip():
        issues.append({
            "type": "code_quality",
            "description": "发现代码质量问题",
            "detail": output.strip()[:500],
            "severity": "low"
        })
    
    # 检查测试文件
    test_files = list(BASE_DIR.glob("tests/**/*.py"))
    script_files = list((BASE_DIR / "scripts").glob("*.py")) + list((BASE_DIR / "scripts" / "**").glob("*.py"))
    
    if len(test_files) < len(script_files) * 0.3:
        issues.append({
            "type": "test_coverage",
            "description": f"测试覆盖不足 (测试文件: {len(test_files)}, 脚本文件: {len(script_files)})",
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
        "config_files": 0
    }
    
    # 排除 node_modules, .git 等
    exclude_dirs = {'node_modules', '.git', '.venv', '__pycache__', 'scripts/archive'}
    
    for path in BASE_DIR.rglob("*"):
        # 跳过排除的目录
        if any(exclude in path.parts for exclude in exclude_dirs):
            continue
        
        if path.is_file():
            structure["total_files"] += 1
            if path.suffix == '.py':
                structure["python_files"] += 1
                if 'test' in path.parts or 'tests' in path.parts:
                    structure["test_files"] += 1
            elif path.suffix in ['.md', '.txt', '.json', '.yml', '.yaml']:
                structure["docs_files"] += 1
            elif path.name in ['requirements.txt', 'setup.py', 'pyproject.toml', '.gitignore']:
                structure["config_files"] += 1
    
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
    print(f"📊 测试结果:")
    print(f"   - 覆盖率: {coverage['total']}%")
    print(f"   - 通过: {coverage['passed']}")
    print(f"   - 失败: {coverage['failed']}")
    print(f"   - 错误: {coverage['errors']}")
    print()
    
    # 查找问题
    issues = find_issues()
    if issues:
        print("⚠️  发现问题:")
        for issue in issues:
            severity = issue.get('severity', 'medium').upper()
            print(f"   - [{severity}] {issue['type']}: {issue['description']}")
        print()
    
    # 输出总结
    print("=" * 60)
    print("✅ 分析完成")
    print("=" * 60)
    
    # 输出 JSON 结果供后续处理
    result = {
        "structure": structure,
        "coverage": coverage,
        "issues": issues
    }
    
    return result

if __name__ == "__main__":
    main()
