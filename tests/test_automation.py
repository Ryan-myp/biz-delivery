#!/usr/bin/env python3
"""
自动化执行引擎测试
测试 CodeExecutor, BuildChecker, TestRunner, ResultValidator
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from automation import (
    AutomationPipeline,
    CodeExecutor,
    BuildChecker,
    TestRunner,
    ResultValidator,
    ExecutionStatus,
)


class TestCodeExecutor:
    """测试代码执行器"""

    def test_init(self):
        """测试初始化"""
        executor = CodeExecutor(work_dir="/tmp/test")
        assert executor.work_dir == Path("/tmp/test")
        assert executor.timeout == 300
    
    def test_run_with_mock(self):
        """测试执行（Mock模式）"""
        executor = CodeExecutor(work_dir="/tmp/test")
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="output", stderr="")
            
            result = executor.run("go test ./...")
            assert result.status == ExecutionStatus.SUCCESS
            assert result.return_code == 0
            assert "output" in result.stdout


class TestBuildChecker:
    """测试编译检查器"""

    def test_init(self):
        """测试初始化"""
        executor = CodeExecutor(work_dir="/tmp/test")
        checker = BuildChecker(executor=executor, language="go")
        assert checker.language == "go"
    
    def test_check_success(self):
        """测试编译成功"""
        executor = CodeExecutor(work_dir="/tmp/test")
        checker = BuildChecker(executor=executor, language="go")
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            
            result = checker.check()
            assert result.status == ExecutionStatus.SUCCESS
    
    def test_check_failure(self):
        """测试编译失败"""
        executor = CodeExecutor(work_dir="/tmp/test")
        checker = BuildChecker(executor=executor, language="go")
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")
            
            result = checker.check()
            assert result.status == ExecutionStatus.FAILED


class TestTestRunner:
    """测试测试运行器"""

    def test_init(self):
        """测试初始化"""
        executor = CodeExecutor(work_dir="/tmp/test")
        runner = TestRunner(executor=executor, language="go")
        assert runner.language == "go"
    
    def test_run_unit_tests_success(self):
        """测试单元测试成功"""
        executor = CodeExecutor(work_dir="/tmp/test")
        runner = TestRunner(executor=executor, language="go")
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="ok", stderr="")
            
            result = runner.run_unit_tests()
            assert result.status == ExecutionStatus.SUCCESS


class TestResultValidator:
    """测试结果验证器"""

    def test_init(self):
        """测试初始化"""
        validator = ResultValidator(expected={"status": "passed"})
        assert validator.expected["status"] == "passed"
    
    def test_validate_success(self):
        """测试验证通过"""
        validator = ResultValidator(expected={"status": "passed"})
        
        result = validator.validate({
            "status": "passed",
            "coverage": {"overall": 0.85}
        })
        
        assert result["passed"] == True
    
    def test_validate_failure(self):
        """测试验证失败"""
        validator = ResultValidator(expected={"status": "passed"})
        
        result = validator.validate({
            "status": "failed",
            "coverage": {"overall": 0.3}
        })
        
        assert result["passed"] == False


class TestAutomationPipeline:
    """测试自动化流水线"""

    def test_init(self, tmp_path):
        """测试初始化"""
        pipeline = AutomationPipeline(
            work_dir=str(tmp_path),
            language="go",
        )
        assert pipeline.language == "go"
        assert isinstance(pipeline.executor, CodeExecutor)
        assert isinstance(pipeline.build_checker, BuildChecker)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
