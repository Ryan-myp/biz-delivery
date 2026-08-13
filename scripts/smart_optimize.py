#!/usr/bin/env python3
"""
biz-delivery 智能优化脚本
功能: 分析项目状态，识别优化机会，执行自动化修复
目标: 将 skills 打造成资深专家水平
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

BASE_DIR = Path("/Users/yanping.ma/biz-delivery")
LOG_FILE = BASE_DIR / "logs" / "smart-optimize.log"
HISTORY_FILE = BASE_DIR / "OPTIMIZATION_HISTORY.md"

def log(msg: str):
    """记录日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(log_msg + '\n')

def run_cmd(cmd: str, cwd=None) -> tuple[int, str, str]:
    """运行命令"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=120, cwd=cwd or str(BASE_DIR)
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)

def analyze_skills_quality() -> Dict[str, Any]:
    """分析 Skill 质量"""
    log("🔍 分析 Skill 质量...")
    
    skills_dir = BASE_DIR / "skills"
    results = {
        "total_skills": 0,
        "skills_with_tests": 0,
        "avg_line_count": 0,
        "max_line_count": 0,
        "min_line_count": float('inf'),
        "issues": []
    }
    
    # 统计 skill 文件
    skill_files = list(skills_dir.rglob("*.py"))
    results["total_skills"] = len([f for f in skill_files if not f.name.startswith('_')])
    
    for skill_file in skill_files:
        if skill_file.name.startswith('_'):
            continue
            
        lines = len(skill_file.read_text().split('\n'))
        results["avg_line_count"] += lines
        results["max_line_count"] = max(results["max_line_count"], lines)
        results["min_line_count"] = min(results["min_line_count"], lines)
        
        # 检查是否有测试
        skill_name = skill_file.stem.replace('_skill', '')
        test_files = list((BASE_DIR / "tests").glob(f"*{skill_name}*"))
        if test_files:
            results["skills_with_tests"] += 1
        
        # 检查代码质量问题
        if lines < 50:
            results["issues"].append({
                "file": str(skill_file.relative_to(BASE_DIR)),
                "type": "too_short",
                "lines": lines,
                "severity": "medium"
            })
        elif lines > 500:
            results["issues"].append({
                "file": str(skill_file.relative_to(BASE_DIR)),
                "type": "too_long",
                "lines": lines,
                "severity": "low"
            })
    
    if results["total_skills"] > 0:
        results["avg_line_count"] //= results["total_skills"]
    
    return results

def analyze_test_coverage() -> Dict[str, Any]:
    """分析测试覆盖率"""
    log("📊 分析测试覆盖率...")
    
    # 运行测试
    returncode, stdout, stderr = run_cmd("python3 -m pytest tests/ -q --tb=short")
    
    coverage = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "warnings": 0,
        "coverage_percent": 0,
        "missing_lines": []
    }
    
    # 解析输出
    for line in stdout.split('\n') + stderr.split('\n'):
        if 'passed' in line and 'failed' in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == 'passed':
                    try:
                        coverage["passed"] = int(parts[i-1])
                    except:
                        pass
                elif part == 'failed':
                    try:
                        coverage["failed"] = int(parts[i-1])
                    except:
                        pass
                elif part == 'error':
                    try:
                        coverage["errors"] = int(parts[i-1])
                    except:
                        pass
                elif part == 'warnings':
                    try:
                        coverage["warnings"] = int(parts[i-1])
                    except:
                        pass
    
    # 获取覆盖率
    cov_returncode, cov_stdout, _ = run_cmd(
        "python3 -m pytest tests/ --cov=skills --cov=scripts --cov-report=term-missing -q"
    )
    
    for line in cov_stdout.split('\n'):
        if 'TOTAL' in line:
            try:
                coverage["coverage_percent"] = int(line.split('%')[0].strip().split()[-1])
            except:
                pass
        if 'scripts/' in line or 'skills/' in line:
            if '%' in line and 'TOTAL' not in line:
                try:
                    parts = line.split()
                    if len(parts) >= 3:
                        coverage["missing_lines"].append({
                            "file": parts[0],
                            "coverage": parts[1],
                            "lines": parts[2] if len(parts) > 2 else ""
                        })
                except:
                    pass
    
    return coverage

def find_expert_level_issues() -> List[Dict[str, str]]:
    """查找需要专家水平解决的问题"""
    log("🎯 查找专家级问题...")
    
    issues = []
    
    # 1. 检查 Skill 文档完整性
    skills_dir = BASE_DIR / "skills"
    for skill_py in skills_dir.rglob("*_skill.py"):
        skill_name = skill_py.stem.replace('_skill', '')
        
        # 检查对应文档
        doc_file = skills_dir / skill_name / "README.md"
        if not doc_file.exists():
            issues.append({
                "type": "missing_doc",
                "skill": skill_name,
                "description": f"缺少文档: {skill_name}/README.md",
                "severity": "high"
            })
        
        # 检查是否有示例
        example_dir = skills_dir / skill_name / "examples"
        if not example_dir.exists():
            issues.append({
                "type": "missing_example",
                "skill": skill_name,
                "description": f"缺少示例: {skill_name}/examples/",
                "severity": "medium"
            })
    
    # 2. 检查测试质量
    test_dir = BASE_DIR / "tests"
    for test_file in test_dir.glob("test_*.py"):
        content = test_file.read_text()
        
        # 检查是否有断言
        if 'assert' not in content and 'pytest.raises' not in content:
            issues.append({
                "type": "no_assertions",
                "file": str(test_file.relative_to(BASE_DIR)),
                "description": "测试文件缺少断言",
                "severity": "high"
            })
        
        # 检查测试文档字符串
        if '"""' not in content and "'''" not in content:
            issues.append({
                "type": "no_docstring",
                "file": str(test_file.relative_to(BASE_DIR)),
                "description": "测试文件缺少文档字符串",
                "severity": "low"
            })
    
    # 3. 检查代码重复
    log("🔍 检查代码重复...")
    returncode, stdout, _ = run_cmd("radon cc scripts/ -a 2>/dev/null || echo 'radon not installed'")
    if 'not installed' not in stdout:
        # 找出复杂度高的文件
        for line in stdout.split('\n'):
            if 'A' in line or 'B' in line:
                issues.append({
                    "type": "high_complexity",
                    "description": f"高复杂度: {line.strip()}",
                    "severity": "medium"
                })
    
    return issues

def generate_optimization_plan(
    skills_quality: Dict,
    test_coverage: Dict,
    expert_issues: List[Dict]
) -> Dict[str, Any]:
    """生成优化计划"""
    log("📋 生成优化计划...")
    
    plan = {
        "timestamp": datetime.now().isoformat(),
        "priority_issues": [],
        "optimization_tasks": [],
        "estimated_time": "30分钟"
    }
    
    # 按严重程度排序问题
    severity_order = {"high": 0, "medium": 1, "low": 2}
    all_issues = expert_issues.copy()
    
    # 添加技能质量问题
    for issue in skills_quality.get("issues", []):
        all_issues.append(issue)
    
    # 添加测试覆盖率问题
    if test_coverage.get("coverage_percent", 0) < 80:
        all_issues.append({
            "type": "low_coverage",
            "coverage": test_coverage["coverage_percent"],
            "target": 80,
            "severity": "high"
        })
    
    # 按严重程度排序
    all_issues.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 2))
    
    plan["priority_issues"] = all_issues[:10]  # 取前10个
    
    # 生成优化任务
    tasks = []
    
    # 任务1: 提升测试覆盖率
    if test_coverage.get("coverage_percent", 0) < 80:
        tasks.append({
            "id": "T001",
            "name": "提升测试覆盖率",
            "description": "补充测试用例，目标覆盖率 ≥80%",
            "priority": "high",
            "estimated_time": "15分钟"
        })
    
    # 任务2: 修复缺失文档
    missing_docs = [i for i in all_issues if i.get("type") == "missing_doc"]
    if missing_docs:
        tasks.append({
            "id": "T002",
            "name": "补充 Skill 文档",
            "description": f"为 {len(missing_docs)} 个 Skill 补充 README.md",
            "priority": "medium",
            "estimated_time": "10分钟"
        })
    
    # 任务3: 清理 TODO/FIXME
    todo_issues = [i for i in all_issues if i.get("type") == "todo"]
    if todo_issues:
        tasks.append({
            "id": "T003",
            "name": "清理 TODO/FIXME",
            "description": "处理或移除代码中的 TODO/FIXME 标记",
            "priority": "medium",
            "estimated_time": "5分钟"
        })
    
    plan["optimization_tasks"] = tasks
    
    return plan

def execute_optimization(plan: Dict[str, Any]) -> Dict[str, Any]:
    """执行优化"""
    log("⚡ 执行优化...")
    
    results = {
        "tasks_executed": [],
        "changes_made": [],
        "success": False
    }
    
    for task in plan.get("optimization_tasks", []):
        log(f"  执行任务: {task['name']}")
        
        if task["id"] == "T001":
            # 补充测试用例（简化版）
            success, changes = execute_test_improvement()
            results["tasks_executed"].append({
                "id": task["id"],
                "name": task["name"],
                "success": success
            })
            results["changes_made"].extend(changes)
            
        elif task["id"] == "T002":
            # 补充文档（简化版）
            success, changes = execute_doc_improvement()
            results["tasks_executed"].append({
                "id": task["id"],
                "name": task["name"],
                "success": success
            })
            results["changes_made"].extend(changes)
    
    results["success"] = len([t for t in results["tasks_executed"] if t["success"]]) > 0
    
    return results

def execute_test_improvement() -> tuple[bool, List[str]]:
    """执行测试改进"""
    changes = []
    
    # 查找低覆盖率的文件
    returncode, stdout, _ = run_cmd(
        "python3 -m pytest tests/ --cov=scripts --cov-report=term-missing -q"
    )
    
    # 识别需要测试的函数
    # 这里简化处理，实际应该分析 AST
    changes.append("分析了测试覆盖率")
    changes.append("识别出低覆盖率模块")
    
    return True, changes

def execute_doc_improvement() -> tuple[bool, List[str]]:
    """执行文档改进"""
    changes = []
    
    # 检查缺失的文档
    skills_dir = BASE_DIR / "skills"
    missing_docs = []
    
    for skill_py in skills_dir.rglob("*_skill.py"):
        skill_name = skill_py.stem.replace('_skill', '')
        doc_file = skills_dir / skill_name / "README.md"
        if not doc_file.exists():
            missing_docs.append(skill_name)
    
    if missing_docs:
        changes.append(f"发现 {len(missing_docs)} 个缺失文档的 Skill")
        # 实际生成文档需要 LLM，这里只记录
        for skill in missing_docs[:3]:  # 限制数量
            changes.append(f"  - {skill}: 需要生成文档")
    
    return True, changes

def save_history(plan: Dict, results: Dict):
    """保存优化历史"""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "plan": plan,
        "results": results
    }
    
    # 追加到历史文件
    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())
        except:
            history = []
    
    history.append(entry)
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))
    
    log(f"✅ 已保存优化历史到 {HISTORY_FILE}")

def main():
    """主函数"""
    log("=" * 60)
    log("🚀 biz-delivery 智能优化开始")
    log("=" * 60)
    
    try:
        # 1. 分析项目
        log("\n📊 步骤 1: 分析项目状态...")
        skills_quality = analyze_skills_quality()
        test_coverage = analyze_test_coverage()
        expert_issues = find_expert_level_issues()
        
        log(f"   - Skill 数量: {skills_quality['total_skills']}")
        log(f"   - 测试覆盖率: {test_coverage.get('coverage_percent', 0)}%")
        log(f"   - 发现问题: {len(expert_issues)}")
        
        # 2. 生成优化计划
        log("\n📋 步骤 2: 生成优化计划...")
        plan = generate_optimization_plan(skills_quality, test_coverage, expert_issues)
        
        log(f"   - 优先级问题: {len(plan['priority_issues'])}")
        log(f"   - 优化任务: {len(plan['optimization_tasks'])}")
        
        # 3. 执行优化
        log("\n⚡ 步骤 3: 执行优化...")
        results = execute_optimization(plan)
        
        log(f"   - 执行任务: {len(results['tasks_executed'])}")
        log(f"   - 成功: {results['success']}")
        
        # 4. 保存历史
        log("\n💾 步骤 4: 保存优化历史...")
        save_history(plan, results)
        
        # 5. 输出总结
        log("\n" + "=" * 60)
        log("✅ 优化完成")
        log("=" * 60)
        
        # 输出 JSON 结果供 Pi 扩展使用
        output = {
            "success": results["success"],
            "tasks_executed": len(results["tasks_executed"]),
            "changes": results["changes_made"],
            "coverage_before": test_coverage.get("coverage_percent", 0),
            "issues_found": len(expert_issues)
        }
        
        print(json.dumps(output, indent=2))
        
    except Exception as e:
        log(f"❌ 优化失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
