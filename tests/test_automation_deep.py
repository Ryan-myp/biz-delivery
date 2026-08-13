"""
Automation 深度测试套件
覆盖：CodeExecutor、BuildChecker、TestRunner、ResultValidator、AutomationPipeline、run_automation
目标：scripts/automation.py 覆盖率 ≥85%
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scripts.automation import (
    CodeExecutor, BuildChecker, TestRunner, ResultValidator,
    AutomationPipeline, ExecutionStatus, run_automation,
)


class TestCodeExecutor:
    """代码执行器测试"""
    
    def test_run_success(self, tmp_path):
        """测试执行成功"""
        executor = CodeExecutor(str(tmp_path))
        result = executor.run("echo hello")
        assert result.status == ExecutionStatus.SUCCESS
        assert "hello" in result.stdout
        assert result.return_code == 0
    
    def test_run_failure(self, tmp_path):
        """测试执行失败"""
        executor = CodeExecutor(str(tmp_path))
        result = executor.run("exit 1")
        assert result.status == ExecutionStatus.FAILED
        assert result.return_code == 1
    
    def test_run_with_cwd(self, tmp_path):
        """测试自定义工作目录"""
        executor = CodeExecutor(str(tmp_path))
        result = executor.run("pwd", cwd=str(tmp_path))
        assert result.status == ExecutionStatus.SUCCESS
    
    def test_run_with_env(self, tmp_path):
        """测试自定义环境变量"""
        executor = CodeExecutor(str(tmp_path))
        result = executor.run("echo $MY_VAR", env={"MY_VAR": "custom"})
        assert "custom" in result.stdout
    
    def test_run_timeout(self, tmp_path):
        """测试超时"""
        executor = CodeExecutor(str(tmp_path), timeout=1)
        result = executor.run("sleep 5")
        assert result.status == ExecutionStatus.ERROR
        assert "Timeout" in result.stderr
    
    def test_run_exception(self, tmp_path):
        """测试异常处理"""
        executor = CodeExecutor(str(tmp_path))
        with patch("subprocess.run", side_effect=OSError("boom")):
            result = executor.run("anything")
        assert result.status == ExecutionStatus.ERROR
        assert "boom" in result.stderr
    
    def test_get_last_result(self, tmp_path):
        """测试获取最后结果"""
        executor = CodeExecutor(str(tmp_path))
        assert executor.get_last_result() is None
        executor.run("echo 1")
        executor.run("echo 2")
        result = executor.get_last_result()
        assert "2" in result.stdout
    
    def test_get_all_results(self, tmp_path):
        """测试获取所有结果"""
        executor = CodeExecutor(str(tmp_path))
        executor.run("echo 1")
        executor.run("echo 2")
        results = executor.get_all_results()
        assert len(results) == 2
        assert "1" in results[0]["stdout"]


class TestBuildChecker:
    """构建检查器测试"""
    
    def test_check_go(self, tmp_path):
        """测试 Go 构建"""
        executor = MagicMock()
        executor.run.return_value = MagicMock(
            status=ExecutionStatus.SUCCESS,
            return_code=0,
            stdout="",
            stderr="",
        )
        checker = BuildChecker(executor, language="go")
        result = checker.check()
        assert result.return_code == 0
    
    def test_check_python(self, tmp_path):
        """测试 Python 检查"""
        executor = MagicMock()
        executor.run.return_value = MagicMock(
            status=ExecutionStatus.SUCCESS,
            return_code=0,
            stdout="",
            stderr="",
        )
        checker = BuildChecker(executor, language="python")
        result = checker.check()
        assert result.return_code == 0
    
    def test_is_compilable_true(self, tmp_path):
        """测试可编译"""
        executor = MagicMock()
        executor.run.return_value = MagicMock(
            status=ExecutionStatus.SUCCESS,
            return_code=0,
            stdout="",
            stderr="",
        )
        checker = BuildChecker(executor)
        assert checker.is_compilable() is True
    
    def test_is_compilable_false(self, tmp_path):
        """测试不可编译"""
        executor = MagicMock()
        executor.run.return_value = MagicMock(
            status=ExecutionStatus.FAILED,
            return_code=1,
            stdout="",
            stderr="error",
        )
        checker = BuildChecker(executor)
        assert checker.is_compilable() is False


class TestTestRunner:
    """测试运行器测试"""
    
    def _make_runner(self, tmp_path, language="go"):
        executor = MagicMock()
        executor.run.return_value = MagicMock(
            status=ExecutionStatus.SUCCESS,
            return_code=0,
            stdout="ok  github.com/test 0.5s",
            stderr="",
        )
        return TestRunner(executor, language=language), executor
    
    def test_run_unit_tests(self, tmp_path):
        """测试单元测试"""
        runner, executor = self._make_runner(tmp_path)
        result = runner.run_unit_tests()
        assert result.return_code == 0
        executor.run.assert_called()
    
    def test_run_integration_tests(self, tmp_path):
        """测试集成测试"""
        runner, executor = self._make_runner(tmp_path)
        result = runner.run_integration_tests()
        assert result.return_code == 0
    
    def test_run_e2e_tests(self, tmp_path):
        """测试 E2E 测试"""
        runner, executor = self._make_runner(tmp_path)
        result = runner.run_e2e_tests()
        assert result.return_code == 0
    
    def test_parse_test_output_go(self, tmp_path):
        """测试 Go 输出解析"""
        runner, _ = self._make_runner(tmp_path)
        parsed = runner._parse_test_output(
            "=== RUN TestLogin\n--- PASS: TestLogin (0.01s)\nPASS\nok  0.5s",
            ""
        )
        assert isinstance(parsed, list)
    
    def test_get_coverage_none(self, tmp_path):
        """测试无覆盖率报告"""
        runner, executor = self._make_runner(tmp_path)
        executor.run.return_value = MagicMock(
            status=ExecutionStatus.SUCCESS,
            return_code=0,
            stdout="",
            stderr="",
        )
        coverage = runner.get_coverage()
        assert coverage is None or isinstance(coverage, dict)
    
    def test_parse_go_coverage(self, tmp_path):
        """测试 Go 覆盖率解析"""
        runner, _ = self._make_runner(tmp_path)
        cov_file = tmp_path / "coverage.out"
        cov_file.write_text(
            "mode: set\npkg/file.go:10.20,30.40 1 1\n", encoding="utf-8"
        )
        parsed = runner._parse_go_coverage(str(cov_file))
        assert isinstance(parsed, dict)
    
    def test_parse_python_coverage(self, tmp_path):
        """测试 Python 覆盖率解析"""
        runner, _ = self._make_runner(tmp_path, language="python")
        cov_file = tmp_path / "coverage.xml"
        cov_file.write_text(
            '<?xml version="1.0"?><coverage><packages><package name="test" line-rate="0.8"/></packages></coverage>',
            encoding="utf-8",
        )
        parsed = runner._parse_python_coverage(str(cov_file))
        assert isinstance(parsed, dict)
    
    def test_get_summary(self, tmp_path):
        """测试摘要"""
        runner, _ = self._make_runner(tmp_path)
        summary = runner.get_summary()
        assert isinstance(summary, dict)


class TestResultValidator:
    """结果验证器测试"""
    
    def test_validate_pass(self):
        """测试验证通过"""
        validator = ResultValidator({
            "required_coverage": 0.8,
            "required_pass_rate": 0.9,
        })
        result = validator.validate({
            "coverage": {"overall": 0.9},
            "compilable": True,
            "test_summary": {"pass_rate": 1.0},
        })
        assert result["overall_status"] == "passed"
        assert result["score"] >= 0.8
    
    def test_validate_fail_coverage(self):
        """测试覆盖率不达标"""
        validator = ResultValidator({
            "required_coverage": 0.8,
            "required_pass_rate": 0.9,
        })
        result = validator.validate({
            "coverage": {"overall": 0.5},
            "compilable": True,
            "test_summary": {"pass_rate": 1.0},
        })
        coverage_check = next(c for c in result["checks"] if c["check"] == "测试覆盖率")
        assert coverage_check["status"] == "warning"
    
    def test_validate_fail_passed(self):
        """测试通过率不足"""
        validator = ResultValidator({
            "required_coverage": 0.8,
            "required_pass_rate": 0.9,
        })
        result = validator.validate({
            "coverage": {"overall": 0.9},
            "compilable": True,
            "test_summary": {"pass_rate": 0.3},
        })
        pass_check = next(c for c in result["checks"] if c["check"] == "测试通过率")
        assert pass_check["status"] == "warning"
    
    def test_validate_default_rules(self):
        """测试默认规则"""
        validator = ResultValidator()
        result = validator.validate({
            "coverage": {"overall": 0.9},
            "compilable": True,
            "test_summary": {"pass_rate": 1.0},
        })
        assert result["overall_status"] == "passed"
    
    def test_validate_missing_fields(self):
        """测试缺失字段"""
        validator = ResultValidator()
        result = validator.validate({})
        assert result["total"] > 0
        # compilable 缺失时返回 failed
        build_check = next(c for c in result["checks"] if c["check"] == "编译状态")
        assert build_check["status"] == "failed"


class TestAutomationPipeline:
    """自动化流水线测试"""
    
    def _make_pipeline(self, tmp_path, **kwargs):
        return AutomationPipeline(work_dir=str(tmp_path), **kwargs)
    
    def test_execute_success(self, tmp_path):
        """测试执行成功"""
        pipeline = self._make_pipeline(tmp_path)
        
        with patch("scripts.automation.CodeExecutor") as MockExec:
            mock_exec = MagicMock()
            mock_exec.run.return_value = MagicMock(
                status=ExecutionStatus.SUCCESS,
                return_code=0,
                stdout="ok",
                stderr="",
            )
            MockExec.return_value = mock_exec
            
            result = pipeline.execute()
        
        assert "build" in result
        assert "validation" in result
    
    def test_execute_build_fail(self, tmp_path):
        """测试构建失败"""
        pipeline = self._make_pipeline(tmp_path)
        
        with patch("scripts.automation.CodeExecutor") as MockExec:
            mock_exec = MagicMock()
            mock_exec.run.return_value = MagicMock(
                status=ExecutionStatus.FAILED,
                return_code=1,
                stdout="",
                stderr="build error",
            )
            MockExec.return_value = mock_exec
            
            result = pipeline.execute()
        
        assert result["validation"]["passed"] is False or result["validation"]["passed"] == 0


class TestRunAutomation:
    """run_automation 函数测试"""
    
    def test_run(self, tmp_path):
        """测试运行"""
        profile = {
            "name": "test",
            "language": "python",
            "repositories": [],
        }
        with patch("scripts.automation.AutomationPipeline") as MockPipeline:
            mock_pipeline = MagicMock()
            mock_pipeline.execute.return_value = {"validation": {"passed": True}}
            MockPipeline.return_value = mock_pipeline
            
            result = run_automation(profile, str(tmp_path))
        
        assert result["validation"]["passed"] is True
