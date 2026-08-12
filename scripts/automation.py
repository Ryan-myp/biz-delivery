#!/usr/bin/env python3
"""
自动化执行引擎 — 执行代码、运行测试、验证结果

支持：
1. 代码编译检查
2. 单元测试执行
3. 集成测试执行
4. 覆盖率分析
5. 结果验证
"""

import subprocess
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class ExecutionStatus(Enum):
    """执行状态"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class ExecutionResult:
    """执行结果"""
    command: str
    status: ExecutionStatus
    stdout: str
    stderr: str
    return_code: int
    duration: float
    coverage: Optional[Dict] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# Code Executor — 代码执行器
# ============================================================================

class CodeExecutor:
    """代码执行器 — 执行编译、测试等命令"""
    
    def __init__(self, work_dir: str, timeout: int = 300):
        self.work_dir = Path(work_dir)
        self.timeout = timeout
        self.results: List[ExecutionResult] = []
    
    def run(self, command: str, cwd: Optional[str] = None, env: Optional[dict] = None) -> ExecutionResult:
        """执行命令
        
        Args:
            command: 要执行的命令
            cwd: 工作目录
            env: 环境变量
            
        Returns:
            执行结果
        """
        import time
        start_time = time.time()
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd or str(self.work_dir),
                env={**os.environ, **(env or {})},
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            
            execution_result = ExecutionResult(
                command=command,
                status=ExecutionStatus.SUCCESS if result.returncode == 0 else ExecutionStatus.FAILED,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                duration=time.time() - start_time,
            )
            
            self.results.append(execution_result)
            return execution_result
            
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                command=command,
                status=ExecutionStatus.ERROR,
                stdout="",
                stderr=f"Timeout after {self.timeout}s",
                return_code=-1,
                duration=self.timeout,
            )
        except Exception as e:
            return ExecutionResult(
                command=command,
                status=ExecutionStatus.ERROR,
                stdout="",
                stderr=str(e),
                return_code=-1,
                duration=time.time() - start_time,
            )
    
    def get_last_result(self) -> Optional[ExecutionResult]:
        """获取最后一次执行结果"""
        return self.results[-1] if self.results else None
    
    def get_all_results(self) -> List[Dict]:
        """获取所有执行结果"""
        return [r.to_dict() for r in self.results]


# ============================================================================
# Build Checker — 编译检查器
# ============================================================================

class BuildChecker:
    """编译检查器 — 验证代码能否正确编译"""
    
    def __init__(self, executor: CodeExecutor, language: str = "go"):
        self.executor = executor
        self.language = language
    
    def check(self, target: str = ".") -> ExecutionResult:
        """检查代码能否编译
        
        Args:
            target: 编译目标（包路径或文件路径）
            
        Returns:
            编译检查结果
        """
        if self.language == "go":
            command = f"go build ./... 2>&1"
        elif self.language == "python":
            # Python 不需要编译，检查语法
            command = f"python3 -m py_compile $(find {target} -name '*.py' | head -20) 2>&1"
        elif self.language == "java":
            command = "mvn compile -q 2>&1 || gradle compileJava 2>&1"
        else:
            command = f"echo 'Unknown language: {self.language}' && exit 1"
        
        return self.executor.run(command)
    
    def is_compilable(self) -> bool:
        """检查代码是否可编译"""
        result = self.check()
        return result.status == ExecutionStatus.SUCCESS


# ============================================================================
# Test Runner — 测试运行器
# ============================================================================

class TestRunner:
    """测试运行器 — 执行单元测试和集成测试"""
    
    def __init__(self, executor: CodeExecutor, language: str = "go"):
        self.executor = executor
        self.language = language
        self.test_results: Dict[str, List[Dict]] = {}
    
    def run_unit_tests(self, pattern: str = None, coverage: bool = True) -> ExecutionResult:
        """运行单元测试
        
        Args:
            pattern: 测试文件匹配模式
            coverage: 是否生成覆盖率报告
            
        Returns:
            测试结果
        """
        if self.language == "go":
            test_pattern = pattern or "./..."
            coverage_flag = "-coverprofile=coverage.out -coverpkg=./..." if coverage else ""
            command = f"go test {coverage_flag} {test_pattern} -v 2>&1"
        elif self.language == "python":
            test_pattern = pattern or "tests/"
            command = f"pytest {test_pattern} -v --tb=short 2>&1"
            if coverage:
                command += " --cov=. --cov-report=xml"
        elif self.language == "java":
            command = "mvn test -q 2>&1 || gradle test 2>&1"
        else:
            command = f"echo 'Unknown language: {self.language}' && exit 1"
        
        result = self.executor.run(command)
        self.test_results["unit"] = self._parse_test_output(result.stdout, result.stderr)
        return result
    
    def run_integration_tests(self) -> ExecutionResult:
        """运行集成测试"""
        if self.language == "go":
            command = "go test ./... -tags=integration -v 2>&1"
        elif self.language == "python":
            command = "pytest tests/integration -v 2>&1"
        else:
            command = "echo 'Integration tests not implemented for this language'"
        
        result = self.executor.run(command)
        self.test_results["integration"] = self._parse_test_output(result.stdout, result.stderr)
        return result
    
    def run_e2e_tests(self) -> ExecutionResult:
        """运行端到端测试"""
        if self.language == "go":
            command = "go test ./e2e -v 2>&1"
        elif self.language == "python":
            command = "pytest tests/e2e -v 2>&1"
        else:
            command = "echo 'E2E tests not implemented for this language'"
        
        result = self.executor.run(command)
        self.test_results["e2e"] = self._parse_test_output(result.stdout, result.stderr)
        return result
    
    def _parse_test_output(self, stdout: str, stderr: str) -> List[Dict]:
        """解析测试输出"""
        tests = []
        
        # Go test 输出解析
        go_pattern = r'===\s+RUN\s+([^\\n]+)\n---\s+(PASS|FAIL):\s+([^\\n]+)'
        for match in re.finditer(go_pattern, stdout):
            tests.append({
                "name": match.group(1).strip(),
                "status": "passed" if match.group(2) == "PASS" else "failed",
                "full_name": match.group(3).strip(),
            })
        
        # pytest 输出解析
        pytest_pattern = r'([^\\s]+)::([^\\s]+)\s+(PASSED|FAILED|ERROR)'
        for match in re.finditer(pytest_pattern, stdout):
            tests.append({
                "name": f"{match.group(1)}::{match.group(2)}",
                "status": "passed" if match.group(3) == "PASSED" else "failed",
                "full_name": f"{match.group(1)}::{match.group(2)}",
            })
        
        return tests
    
    def get_coverage(self) -> Optional[Dict]:
        """获取测试覆盖率"""
        if self.language == "go":
            coverage_file = self.executor.work_dir / "coverage.out"
            if coverage_file.exists():
                return self._parse_go_coverage(str(coverage_file))
        elif self.language == "python":
            coverage_file = self.executor.work_dir / "coverage.xml"
            if coverage_file.exists():
                return self._parse_python_coverage(str(coverage_file))
        return None
    
    def _parse_go_coverage(self, coverage_file: str) -> Dict:
        """解析 Go 覆盖率报告"""
        try:
            result = subprocess.run(
                f"go tool cover -func={coverage_file}",
                shell=True,
                capture_output=True,
                text=True,
            )
            # 解析最后一行的总体覆盖率
            lines = result.stdout.strip().split('\n')
            for line in reversed(lines):
                if line.startswith('total:'):
                    match = re.search(r'(\d+\.?\d*)%', line)
                    if match:
                        return {"type": "go", "overall": float(match.group(1))}
        except Exception:
            pass
        return {"type": "go", "overall": 0}
    
    def _parse_python_coverage(self, coverage_file: str) -> Dict:
        """解析 Python 覆盖率报告"""
        try:
            with open(coverage_file) as f:
                content = f.read()
                # 提取 line-rate
                match = re.search(r'line-rate="([\d.]+)"', content)
                if match:
                    return {"type": "python", "overall": float(match.group(1))}
        except Exception:
            pass
        return {"type": "python", "overall": 0}
    
    def get_summary(self) -> Dict:
        """获取测试摘要"""
        total = sum(len(v) for v in self.test_results.values())
        passed = sum(
            sum(1 for t in tests if t["status"] == "passed")
            for tests in self.test_results.values()
        )
        
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0,
            "by_type": {k: len(v) for k, v in self.test_results.items()},
            "coverage": self.get_coverage(),
        }


# ============================================================================
# Validator — 结果验证器
# ============================================================================

class ResultValidator:
    """结果验证器 — 验证交付物是否符合要求"""
    
    def __init__(self, expected: dict = None):
        self.expected = expected or {}
        self.checks = []
    
    def validate(self, actual: dict) -> Dict:
        """验证实际结果是否符合预期
        
        Args:
            actual: 实际结果
            
        Returns:
            验证结果
        """
        checks = []
        
        # 1. 检查必需文件是否存在
        required_files = self.expected.get("required_files", [])
        for file_path in required_files:
            exists = Path(file_path).exists()
            checks.append({
                "check": f"文件存在: {file_path}",
                "status": "passed" if exists else "failed",
                "expected": "存在",
                "actual": "存在" if exists else "不存在",
            })
        
        # 2. 检查测试覆盖率
        coverage = actual.get("coverage", {})
        required_coverage = self.expected.get("required_coverage", 0.7)
        if coverage:
            overall = coverage.get("overall", 0)
            checks.append({
                "check": "测试覆盖率",
                "status": "passed" if overall >= required_coverage else "warning",
                "expected": f">= {required_coverage*100:.0f}%",
                "actual": f"{overall*100:.1f}%",
            })
        
        # 3. 检查编译状态
        compilable = actual.get("compilable", False)
        checks.append({
            "check": "编译状态",
            "status": "passed" if compilable else "failed",
            "expected": "编译成功",
            "actual": "编译成功" if compilable else "编译失败",
        })
        
        # 4. 检查测试通过率
        test_summary = actual.get("test_summary", {})
        pass_rate = test_summary.get("pass_rate", 0)
        required_pass_rate = self.expected.get("required_pass_rate", 0.9)
        checks.append({
            "check": "测试通过率",
            "status": "passed" if pass_rate >= required_pass_rate else "warning",
            "expected": f">= {required_pass_rate*100:.0f}%",
            "actual": f"{pass_rate*100:.1f}%",
        })
        
        # 计算总体评分
        passed = sum(1 for c in checks if c["status"] == "passed")
        total = len(checks)
        score = passed / total if total > 0 else 0
        
        return {
            "checks": checks,
            "score": score,
            "passed": passed,
            "total": total,
            "overall_status": "passed" if score >= 0.8 else ("warning" if score >= 0.6 else "failed"),
        }


# ============================================================================
# Automation Pipeline — 自动化流水线
# ============================================================================

class AutomationPipeline:
    """自动化执行流水线"""
    
    def __init__(
        self,
        work_dir: str,
        language: str = "go",
        expected: dict = None
    ):
        self.work_dir = work_dir
        self.language = language
        self.executor = CodeExecutor(work_dir, timeout=600)
        self.build_checker = BuildChecker(self.executor, language)
        self.test_runner = TestRunner(self.executor, language)
        self.validator = ResultValidator(expected)
    
    def execute(self) -> Dict:
        """执行完整的自动化流程
        
        Returns:
            执行结果
        """
        print("\n" + "=" * 60)
        print("  自动化执行流水线")
        print("=" * 60)
        
        # Step 1: 编译检查
        print("\n🔨 Step 1: 编译检查")
        build_result = self.build_checker.check()
        print(f"  状态: {'✅ 通过' if build_result.status == ExecutionStatus.SUCCESS else '❌ 失败'}")
        if build_result.stderr:
            print(f"  错误: {build_result.stderr[:200]}")
        
        # Step 2: 运行单元测试
        print("\n🧪 Step 2: 运行单元测试")
        unit_result = self.test_runner.run_unit_tests()
        summary = self.test_runner.get_summary()
        print(f"  总数: {summary['total']}, 通过: {summary['passed']}, 失败: {summary['failed']}")
        print(f"  通过率: {summary['pass_rate']*100:.1f}%")
        if summary.get('coverage'):
            print(f"  覆盖率: {summary['coverage'].get('overall', 0)*100:.1f}%")
        
        # Step 3: 运行集成测试（可选）
        print("\n🔌 Step 3: 运行集成测试")
        try:
            integration_result = self.test_runner.run_integration_tests()
            print(f"  状态: {'✅ 通过' if integration_result.status == ExecutionStatus.SUCCESS else '⚠️ 跳过/失败'}")
        except Exception as e:
            print(f"  ⚠️  集成测试跳过: {e}")
        
        # Step 4: 结果验证
        print("\n✅ Step 4: 结果验证")
        actual_result = {
            "compilable": build_result.status == ExecutionStatus.SUCCESS,
            "test_summary": summary,
            "coverage": summary.get("coverage"),
        }
        validation = self.validator.validate(actual_result)
        
        print(f"  评分: {validation['score']*100:.0f}/100")
        print(f"  状态: {validation['overall_status'].upper()}")
        
        for check in validation['checks']:
            icon = "✅" if check['status'] == 'passed' else "❌"
            print(f"    {icon} {check['check']}: {check['actual']}")
        
        return {
            "build": build_result.to_dict(),
            "unit_tests": summary,
            "validation": validation,
            "all_results": self.executor.get_all_results(),
        }


# ============================================================================
# Public API
# ============================================================================

def run_automation(
    work_dir: str,
    language: str = "go",
    expected: dict = None
) -> Dict:
    """运行自动化执行流水线
    
    Args:
        work_dir: 工作目录
        language: 编程语言
        expected: 预期结果配置
        
    Returns:
        执行结果
    """
    pipeline = AutomationPipeline(work_dir, language, expected)
    return pipeline.execute()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="自动化执行引擎")
    parser.add_argument("--work-dir", required=True, help="工作目录")
    parser.add_argument("--language", default="go", help="编程语言")
    parser.add_argument("--expected", help="预期结果 JSON 文件")
    
    args = parser.parse_args()
    
    expected = None
    if args.expected and Path(args.expected).exists():
        with open(args.expected) as f:
            expected = json.load(f)
    
    result = run_automation(args.work_dir, args.language, expected)
    print("\n" + json.dumps(result, indent=2, ensure_ascii=False))
