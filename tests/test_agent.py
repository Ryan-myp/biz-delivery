#!/usr/bin/env python3
"""
Agent 任务生成测试
测试 AgentPromptGenerator 和 TaskDecomposer
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from agent.prompt_generator import AgentPromptGenerator, TaskDecomposer


class TestAgentPromptGenerator:
    """测试Agent提示词生成器"""

    def test_init(self):
        """测试初始化"""
        generator = AgentPromptGenerator(profile={"language": "go"})
        assert generator.profile["language"] == "go"
    
    def test_generate_setup_prompt(self):
        """测试生成环境准备提示词"""
        generator = AgentPromptGenerator(profile={"language": "go"})
        
        prompt = generator.generate_setup_prompt("/tmp/test")
        
        assert len(prompt) > 50
        assert "/tmp/test" in prompt
    
    def test_generate_impl_prompt(self):
        """测试生成实现提示词"""
        generator = AgentPromptGenerator(profile={"language": "go"})
        
        prompt = generator.generate_impl_prompt(
            requirements="Implement auth module",
            technical_design="## Auth Module\n- Login handler\n- Token service"
        )
        
        assert len(prompt) > 100
        assert "Auth" in prompt or "auth" in prompt
    
    def test_generate_test_prompt(self):
        """测试生成测试提示词"""
        generator = AgentPromptGenerator(profile={"language": "go"})
        
        prompt = generator.generate_test_prompt(
            feature_description="Login feature",
            test_cases=["TestLogin", "TestLogout"],
            test_file="auth_test.go"
        )
        
        assert len(prompt) > 50
        assert "Login" in prompt or "login" in prompt
    
    def test_generate_review_prompt(self):
        """测试生成审查提示词"""
        generator = AgentPromptGenerator(profile={"language": "go"})
        
        prompt = generator.generate_review_prompt("修改了 auth.go")
        
        assert len(prompt) > 50
        assert "auth.go" in prompt
    
    def test_generate_task_prompt_setup(self):
        """测试生成环境准备任务提示词"""
        generator = AgentPromptGenerator(profile={"language": "go"})
        
        task = {"type": "setup", "repo_path": "/tmp/test"}
        prompt = generator.generate_task_prompt(task)
        
        assert "环境准备" in prompt or "DevOps" in prompt
    
    def test_generate_task_prompt_implement(self):
        """测试生成实现任务提示词"""
        generator = AgentPromptGenerator(profile={"language": "go"})
        
        task = {
            "type": "implement",
            "requirements": "实现登录功能",
            "technical_design": "## 登录模块",
            "code_context": ""
        }
        prompt = generator.generate_task_prompt(task)
        
        assert "登录" in prompt or "login" in prompt.lower()


class TestTaskDecomposer:
    """测试任务分解器"""

    def test_init(self):
        """测试初始化"""
        decomposer = TaskDecomposer(profile={"language": "go"})
        assert decomposer.profile["language"] == "go"
    
    def test_decompose(self):
        """测试任务分解"""
        decomposer = TaskDecomposer(profile={"language": "go"})
        
        requirement = "Implement user authentication"
        td_content = """
## Architecture
- Auth module
- Token service

## Modules
1. auth_handler
2. token_service
"""
        
        tasks = decomposer.decompose(requirement, td_content)
        
        assert isinstance(tasks, list)
        if len(tasks) > 0:
            task = tasks[0]
            assert "id" in task or "task_id" in task
            assert "title" in task or "name" in task


class TestPromptContent:
    """测试提示词内容"""

    def test_impl_prompt_has_structure(self):
        """测试实现提示词结构"""
        generator = AgentPromptGenerator(profile={"language": "go"})
        
        prompt = generator.generate_impl_prompt(
            requirements="Add login feature",
            technical_design="## Login Module"
        )
        
        # 检查提示词包含基本结构
        assert "功能需求" in prompt or "requirement" in prompt.lower()
        assert "技术方案" in prompt or "td" in prompt.lower()
    
    def test_test_prompt_has_requirements(self):
        """测试测试提示词包含需求"""
        generator = AgentPromptGenerator(profile={"language": "go"})
        
        prompt = generator.generate_test_prompt(
            feature_description="User login",
            test_cases=["TestLoginSuccess", "TestLoginFailure"],
            test_file="login_test.go"
        )
        
        assert "User login" in prompt or "login" in prompt.lower()
        assert "TestLoginSuccess" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
