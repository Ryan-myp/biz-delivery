"""
Agent Prompt Generator 深度测试套件
覆盖：AgentPromptGenerator 全部方法、TaskDecomposer 全部方法、generate_agent_prompt、decompose_task
目标：scripts/agent/prompt_generator.py 覆盖率 ≥85%
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scripts.agent.prompt_generator import (
    AgentPromptGenerator, TaskDecomposer,
    generate_agent_prompt, decompose_task,
)


SAMPLE_TD = """
# 技术方案

## 模块: AdGroup
### 功能描述
广告组管理模块

### 接口设计
- POST /api/v1/adgroups

## 模块: Creative
### 功能描述
素材管理模块

### 接口设计
- POST /api/v1/creatives
"""


class TestAgentPromptGenerator:
    """Agent 提示词生成器测试"""
    
    def _make_generator(self, language="go"):
        return AgentPromptGenerator({"language": language})
    
    def test_init_go(self):
        """测试 Go 初始化"""
        gen = self._make_generator("go")
        assert gen.language == "go"
        assert gen.package_manager == "go mod"
    
    def test_init_python(self):
        """测试 Python 初始化"""
        gen = self._make_generator("python")
        assert gen.language == "python"
        assert gen.package_manager == "pip / poetry"
    
    def test_init_java(self):
        """测试 Java 初始化"""
        gen = self._make_generator("java")
        assert gen.language == "java"
        assert gen.package_manager == "maven / gradle"
    
    def test_init_unknown_language(self):
        """测试未知语言"""
        gen = self._make_generator("rust")
        assert gen.package_manager == "unknown"
    
    def test_init_default_go(self):
        """测试默认语言"""
        gen = AgentPromptGenerator({})
        assert gen.language == "go"
    
    def test_generate_setup_prompt(self):
        """测试 setup prompt"""
        gen = self._make_generator()
        prompt = gen.generate_setup_prompt("/tmp/repo")
        assert "环境准备任务" in prompt
        assert "go" in prompt
        assert "/tmp/repo" in prompt
    
    def test_generate_impl_prompt(self):
        """测试 implement prompt"""
        gen = self._make_generator()
        prompt = gen.generate_impl_prompt(
            requirements="实现用户登录",
            technical_design="使用 JWT 认证",
        )
        assert "代码实现任务" in prompt
        assert "实现用户登录" in prompt
        assert "使用 JWT 认证" in prompt
    
    def test_generate_impl_prompt_with_context(self):
        """测试带上下文的 implement prompt"""
        gen = self._make_generator()
        prompt = gen.generate_impl_prompt(
            requirements="实现登录",
            technical_design="JWT",
            code_context="现有代码",
        )
        assert "代码实现任务" in prompt
    
    def test_generate_test_prompt(self):
        """测试 test prompt"""
        gen = self._make_generator()
        prompt = gen.generate_test_prompt(
            feature_description="用户登录",
            test_cases=["正常登录", "密码错误"],
        )
        assert "测试编写任务" in prompt
        assert "正常登录" in prompt
        assert "test_用户登录.go" in prompt
    
    def test_generate_test_prompt_python(self):
        """测试 Python test prompt"""
        gen = self._make_generator("python")
        prompt = gen.generate_test_prompt(
            feature_description="login",
            test_cases=["valid"],
        )
        assert "login" in prompt
        assert ".py" in prompt
    
    def test_generate_test_prompt_with_file(self):
        """测试指定测试文件"""
        gen = self._make_generator()
        prompt = gen.generate_test_prompt(
            feature_description="登录",
            test_cases=["test"],
            test_file="auth_test.go",
        )
        assert "auth_test.go" in prompt
    
    def test_generate_test_prompt_empty_cases(self):
        """测试空测试用例"""
        gen = self._make_generator()
        prompt = gen.generate_test_prompt(
            feature_description="登录",
            test_cases=[],
        )
        assert "测试编写任务" in prompt
    
    def test_generate_review_prompt(self):
        """测试 review prompt"""
        gen = self._make_generator()
        prompt = gen.generate_review_prompt("修改了登录逻辑")
        assert "代码审查任务" in prompt
        assert "修改了登录逻辑" in prompt
    
    def test_generate_task_prompt_setup(self):
        """测试任务 prompt setup"""
        gen = self._make_generator()
        prompt = gen.generate_task_prompt({
            "type": "setup",
            "repo_path": "/tmp/repo",
        })
        assert "环境准备任务" in prompt
    
    def test_generate_task_prompt_implement(self):
        """测试任务 prompt implement"""
        gen = self._make_generator()
        prompt = gen.generate_task_prompt({
            "type": "implement",
            "requirements": "实现登录",
            "technical_design": "JWT",
        })
        assert "代码实现任务" in prompt
    
    def test_generate_task_prompt_test(self):
        """测试任务 prompt test"""
        gen = self._make_generator()
        prompt = gen.generate_task_prompt({
            "type": "test",
            "feature": "登录",
            "test_cases": ["正常"],
        })
        assert "测试编写任务" in prompt
    
    def test_generate_task_prompt_review(self):
        """测试任务 prompt review"""
        gen = self._make_generator()
        prompt = gen.generate_task_prompt({
            "type": "review",
            "changes": "修改",
        })
        assert "代码审查任务" in prompt
    
    def test_generate_task_prompt_unknown(self):
        """测试未知任务类型"""
        gen = self._make_generator()
        prompt = gen.generate_task_prompt({"type": "unknown", "data": 1})
        assert "任务" in prompt


class TestTaskDecomposer:
    """任务分解器测试"""
    
    def _make_decomposer(self):
        return TaskDecomposer({"language": "go"})
    
    def test_decompose_with_modules(self):
        """测试模块分解"""
        decomposer = self._make_decomposer()
        tasks = decomposer.decompose("广告组管理", SAMPLE_TD)
        
        # AdGroup 和 Creative 两个模块 → 2 implement + 2 test + 1 review
        assert len(tasks) == 5
        implement_tasks = [t for t in tasks if t["type"] == "implement"]
        test_tasks = [t for t in tasks if t["type"] == "test"]
        review_tasks = [t for t in tasks if t["type"] == "review"]
        assert len(implement_tasks) == 2
        assert len(test_tasks) == 2
        assert len(review_tasks) == 1
        assert set(review_tasks[0]["depends_on"]) == {"test_AdGroup", "test_Creative"}
    
    def test_decompose_empty_td(self):
        """测试空 TD"""
        decomposer = self._make_decomposer()
        tasks = decomposer.decompose("需求", "")
        assert tasks == []
    
    def test_extract_modules(self):
        """测试模块提取"""
        decomposer = self._make_decomposer()
        modules = decomposer._extract_modules(SAMPLE_TD)
        assert "AdGroup" in modules
        assert "Creative" in modules
    
    def test_extract_modules_alt_pattern(self):
        """测试其他模块模式"""
        decomposer = self._make_decomposer()
        td = "### 订单模块\n\n### 用户模块\n"
        modules = decomposer._extract_modules(td)
        assert "订单" in modules
        assert "用户" in modules
    
    def test_extract_module_design(self):
        """测试模块设计提取"""
        decomposer = self._make_decomposer()
        design = decomposer._extract_module_design(SAMPLE_TD, "AdGroup")
        assert "广告组管理模块" in design
    
    def test_extract_module_design_missing(self):
        """测试模块不存在"""
        decomposer = self._make_decomposer()
        design = decomposer._extract_module_design(SAMPLE_TD, "Missing")
        assert "Missing" in design
    
    def test_generate_test_cases(self):
        """测试用例生成"""
        decomposer = self._make_decomposer()
        cases = decomposer._generate_test_cases("需求", "AdGroup")
        assert len(cases) == 3
        assert "正常流程测试" in cases[0]
        assert "异常处理测试" in cases[1]
        assert "边界条件测试" in cases[2]


class TestPublicAPI:
    """公共 API 测试"""
    
    def test_generate_agent_prompt_setup(self):
        """测试 setup"""
        prompt = generate_agent_prompt("setup", {"language": "go"}, repo_path="/tmp")
        assert "环境准备任务" in prompt
    
    def test_generate_agent_prompt_implement(self):
        """测试 implement"""
        prompt = generate_agent_prompt(
            "implement", {"language": "go"},
            requirements="实现登录", technical_design="JWT",
        )
        assert "代码实现任务" in prompt
    
    def test_generate_agent_prompt_test(self):
        """测试 test"""
        prompt = generate_agent_prompt(
            "test", {"language": "go"},
            feature="登录", test_cases=["正常"],
        )
        assert "测试编写任务" in prompt
    
    def test_generate_agent_prompt_review(self):
        """测试 review"""
        prompt = generate_agent_prompt(
            "review", {"language": "go"}, changes="修改"
        )
        assert "代码审查任务" in prompt
    
    def test_generate_agent_prompt_unknown(self):
        """测试未知类型"""
        prompt = generate_agent_prompt("unknown", {"language": "go"}, data=1)
        assert "未知任务类型" in prompt
    
    def test_decompose_task(self):
        """测试任务分解"""
        tasks = decompose_task("需求", SAMPLE_TD, {"language": "go"})
        assert len(tasks) >= 1
