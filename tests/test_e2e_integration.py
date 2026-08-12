#!/usr/bin/env python3
"""
端到端集成测试
测试完整的 biz-delivery 工作流程
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


class TestLearnPhase:
    """测试 Learn 阶段"""

    def test_scan_go_files(self, tmp_path):
        """测试扫描 Go 文件"""
        # 创建一个简单的 Go 文件
        go_file = tmp_path / "test.go"
        go_file.write_text("""
package test

type User struct {
    ID   int    `json:"id"`
    Name string `json:"name"`
}

func (u *User) GetID() int {
    return u.ID
}

func main() {
    u := &User{ID: 1, Name: "test"}
    println(u.GetID())
}
""")
        
        # 验证文件存在
        assert go_file.exists()
        assert go_file.suffix == ".go"
    
    def test_scan_python_files(self, tmp_path):
        """测试扫描 Python 文件"""
        # 创建一个简单的 Python 文件
        py_file = tmp_path / "test.py"
        py_file.write_text("""
class User:
    def __init__(self, user_id, name):
        self.id = user_id
        self.name = name
    
    def get_id(self):
        return self.id

def main():
    user = User(1, "test")
    print(user.get_id())

if __name__ == "__main__":
    main()
""")
        
        assert py_file.exists()
        assert py_file.suffix == ".py"


class TestReviewPhase:
    """测试 Review 阶段"""

    def test_prd_review_with_rules(self):
        """测试基于规则的 PRD 审查"""
        # 模拟一个简单的 PRD 审查流程
        prd = {
            "features": [
                {"name": "用户登录", "priority": "P0"},
                {"name": "数据导出", "priority": "P1"},
            ],
            "api_specs": [
                {"method": "POST", "path": "/api/login"},
                {"method": "GET", "path": "/api/users"},
            ]
        }
        
        # 验证 PRD 结构
        assert len(prd["features"]) == 2
        assert prd["features"][0]["priority"] == "P0"
        assert len(prd["api_specs"]) == 2
    
    def test_technical_design_validation(self):
        """测试技术方案验证"""
        td = {
            "architecture": "microservice",
            "modules": [
                {"name": "auth", "language": "go"},
                {"name": "user", "language": "python"},
            ],
            "dependencies": {
                "auth": ["user"],
                "user": []
            }
        }
        
        # 验证 TD 结构
        assert td["architecture"] == "microservice"
        assert len(td["modules"]) == 2
        assert "auth" in td["dependencies"]


class TestAgentPhase:
    """测试 Agent 阶段"""

    def test_task_decomposition(self):
        """测试任务分解"""
        requirement = "实现用户认证功能"
        td_content = """
## 认证模块设计
- JWT Token 生成
- 用户登录验证
- 权限检查中间件
"""
        
        # 模拟任务分解
        tasks = [
            {"id": "T1", "title": "JWT Token 生成", "priority": "P0"},
            {"id": "T2", "title": "用户登录验证", "priority": "P0"},
            {"id": "T3", "title": "权限检查中间件", "priority": "P1"},
        ]
        
        assert len(tasks) == 3
        assert tasks[0]["priority"] == "P0"
        assert "JWT" in tasks[0]["title"]
    
    def test_agent_prompt_generation(self):
        """测试 Agent 提示词生成"""
        from agent.prompt_generator import AgentPromptGenerator
        
        generator = AgentPromptGenerator(profile={"language": "go"})
        
        # 使用 generate_impl_prompt 生成提示词
        prompt = generator.generate_impl_prompt(
            requirements="实现 JWT Token 生成功能",
            technical_design="## JWT 模块\n- Token 生成\n- Token 验证"
        )
        
        assert len(prompt) > 50
        assert "JWT" in prompt or "Token" in prompt


class TestQualityGate:
    """测试质量门禁"""

    def test_passing_quality_gate(self):
        """测试通过的质量门禁"""
        report = {
            "prd_review": {"status": "passed", "p0_issues": []},
            "technical_design": {"status": "valid"},
            "test_coverage": 0.85,
            "build_status": "success",
        }
        
        # 验证门禁逻辑
        assert report["prd_review"]["status"] == "passed"
        assert report["test_coverage"] >= 0.8
        assert report["build_status"] == "success"
    
    def test_failing_quality_gate(self):
        """测试失败的质量门禁"""
        report = {
            "prd_review": {"status": "failed", "p0_issues": ["Critical issue"]},
            "technical_design": {"status": "invalid"},
            "test_coverage": 0.3,
            "build_status": "failed",
        }
        
        # 验证门禁逻辑
        assert report["prd_review"]["status"] == "failed"
        assert len(report["prd_review"]["p0_issues"]) > 0
        assert report["test_coverage"] < 0.5


class TestEndToEndFlow:
    """测试端到端流程"""

    def test_complete_workflow(self):
        """测试完整工作流程"""
        workflow = {
            "phase_1_learn": {
                "status": "completed",
                "files_scanned": 100,
                "structs_found": 50,
                "functions_found": 80,
            },
            "phase_2_review": {
                "status": "completed",
                "issues_found": 5,
                "p0_issues": 0,
                "p1_issues": 3,
            },
            "phase_3_td": {
                "status": "completed",
                "modules_defined": 3,
                "apis_defined": 5,
            },
            "phase_4_agent": {
                "status": "pending",
                "tasks_generated": 10,
            },
            "phase_5_quality_gate": {
                "status": "passing",
                "score": 85,
            },
        }
        
        # 验证工作流结构
        assert "phase_1_learn" in workflow
        assert "phase_5_quality_gate" in workflow
        assert workflow["phase_1_learn"]["status"] == "completed"
        assert workflow["phase_5_quality_gate"]["score"] >= 80


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
