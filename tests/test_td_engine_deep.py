"""
TD Engine 深度测试套件
覆盖：TDEngine.generate_td、generate_with_response、_build_td_prompt
目标：scripts/td_engine.py 覆盖率 ≥85%
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.td_engine import TDEngine
from scripts.base_engine import EngineBase


def make_profile():
    return {
        "name": "test-project",
        "business_domain": "test-domain",
        "repositories": [],
    }


class TestTDEngine:
    """TD 引擎测试"""
    
    def _make_engine(self, tmp_path, tmp_out):
        return TDEngine(make_profile(), str(tmp_out), wiki_path=str(tmp_path))
    
    def _make_ir(self):
        """构造 IRDocument"""
        from scripts.learn_repo import IRDocument
        ir = IRDocument(
            repo_name="test-repo",
            repo_path="/tmp/test-repo",
            language="go",
            packages={
                "handler": {"files": ["handler/user.go"], "imports": ["service"]},
                "service": {"files": ["service/user.go"], "imports": ["dao"]},
                "dao": {"files": ["dao/user.go"], "imports": []},
            },
        )
        ir.routes = [
            {"method": "POST", "path": "/api/login", "handler": "UserHandler"},
            {"method": "GET", "path": "/api/user/{id}", "handler": "UserHandler"},
        ]
        ir.business_logic = [
            {"handler": "UserHandler", "description": "用户登录", "calls": ["AuthService.Login"], "file": "handler/user.go"},
        ]
        ir.entity_tables = [
            {"entity": "User", "table": "users", "file": "model/user.go"},
        ]
        ir.error_codes = [
            {"name": "BAD_PASSWORD", "code": "AUTH_001", "category": "auth", "message": "密码错误"},
        ]
        ir.auth_models = [{"model": "JWT", "expire": "24h"}]
        ir.sql_operations = [{"table": "users", "op": "SELECT"}]
        ir.core_flows = [
            {"name": "登录流程", "steps": ["handler", "service", "dao"]},
        ]
        ir.services = [
            {"name": "user-service"},
            {"name": "order-service"},
        ]
        ir.call_graph = [
            {"caller": "handler/user", "callee": "service/user"},
            {"caller": "service/user", "callee": "dao/user"},
        ]
        ir.functions = [{"name": "Login", "file": "handler/user.go"}]
        ir.structs = [{"name": "User", "file": "model/user.go"}]
        ir.configs = [{"key": "jwt_secret", "value": "***"}]
        return ir
    
    def test_generate_with_response(self, tmp_path, tmp_out):
        """测试 LLM 响应保存"""
        engine = self._make_engine(tmp_path, tmp_out)
        llm_output = "# 技术方案\n\n## 1. 背景与目标\n..."
        
        result = engine.generate_with_response(llm_output)
        
        assert result["status"] == "completed"
        assert Path(result["report_file"]).exists()
        assert "架构设计" in result["sections"]
        content = Path(result["report_file"]).read_text(encoding="utf-8")
        assert content == llm_output
    
    def test_generate_td_prompt(self, tmp_path, tmp_out):
        """测试 TD prompt 生成"""
        engine = self._make_engine(tmp_path, tmp_out)
        
        prd = "# 用户登录功能\n\n## 需求描述\n用户邮箱密码登录"
        
        with patch.object(engine, "_scan_codebase", return_value=self._make_ir()):
            with patch.object(engine, "_query_evidence_for_prd",
                              return_value={"total": 0, "evidence": []}):
                result = engine.generate_td(prd)
        
        assert result["status"] == "prompt_ready"
        assert result["prd_length"] == len(prd)
        prompt_file = Path(result["prompt_file"])
        assert prompt_file.exists()
        prompt_text = prompt_file.read_text(encoding="utf-8")
        assert "技术方案生成任务" in prompt_text
        assert "PRD 内容" in prompt_text
    
    def test_generate_td_with_review_report(self, tmp_path, tmp_out):
        """测试带审查报告的 TD 生成"""
        engine = self._make_engine(tmp_path, tmp_out)
        
        prd = "# 登录功能\n\n## 需求\n邮箱密码登录"
        review = "# 审查报告\n\n## P0 问题\n缺少安全方案"
        
        with patch.object(engine, "_scan_codebase", return_value=self._make_ir()):
            with patch.object(engine, "_query_evidence_for_prd",
                              return_value={"total": 0, "evidence": []}):
                result = engine.generate_td(prd, review_report=review)
        
        prompt_text = Path(result["prompt_file"]).read_text(encoding="utf-8")
        assert "PRD 审查报告" in prompt_text
        assert "缺少安全方案" in prompt_text
    
    def test_build_td_prompt_sections(self, tmp_path, tmp_out):
        """测试 prompt 包含所有章节"""
        engine = self._make_engine(tmp_path, tmp_out)
        ir = self._make_ir()
        
        prompt = engine._build_td_prompt(
            {"total": 0, "evidence": []}, ir,
            "# 登录功能\n\n## 需求\n测试", None
        )
        
        assert "技术方案生成任务" in prompt
        assert "代码库摘要" in prompt
        assert "关键路由" in prompt
        assert "业务逻辑" in prompt
        assert "Entity-Table" in prompt or "实体" in prompt
        assert "错误码" in prompt
        assert "鉴权模型" in prompt
        assert "SQL 操作" in prompt
        assert "核心业务流程" in prompt
        assert "PRD 内容" in prompt
        assert "技术方案生成规则" in prompt
        assert "输出格式" in prompt
    
    def test_build_td_prompt_multi_service(self, tmp_path, tmp_out):
        """测试多服务提示"""
        engine = self._make_engine(tmp_path, tmp_out)
        ir = self._make_ir()
        
        prompt = engine._build_td_prompt(
            {"total": 0, "evidence": []}, ir, "# 测试", None
        )
        
        assert "跨仓库服务拓扑" in prompt
        assert "user-service" in prompt
        assert "order-service" in prompt
        assert "跨服务事务一致性方案" in prompt
    
    def test_build_td_prompt_with_evidence(self, tmp_path, tmp_out):
        """测试带证据的 prompt"""
        engine = self._make_engine(tmp_path, tmp_out)
        ir = self._make_ir()
        
        filtered = {
            "total": 1,
            "evidence": [
                {"title": "handler/user.go", "score": 0.85, "content": "func Login() {}"},
            ]
        }
        
        prompt = engine._build_td_prompt(filtered, ir, "# 测试", None)
        
        assert "代码库证据" in prompt
        assert "handler/user.go" in prompt
        assert "0.850" in prompt
    
    def test_build_td_prompt_with_business_cards(self, tmp_path, tmp_out):
        """测试业务卡片注入"""
        engine = self._make_engine(tmp_path, tmp_out)
        ir = self._make_ir()
        
        # 创建业务卡片文件
        cards = {
            "scenario_cards": [
                {"scenario": "UserHandler", "description": "登录", "call_chain": ["AuthService"]},
            ],
            "entity_relationships": [
                {"entity": "User", "table": "users"},
            ],
            "error_categories": {
                "auth": [{"name": "BAD_PASSWORD"}],
            },
        }
        cards_file = tmp_out / "business_cards.json"
        cards_file.write_text(json.dumps(cards), encoding="utf-8")
        
        prompt = engine._build_td_prompt(
            {"total": 0, "evidence": []}, ir, "# 测试", None, cache_dir=str(tmp_out)
        )
        
        assert "业务知识卡片" in prompt
        assert "UserHandler" in prompt
    
    def test_build_td_prompt_with_review(self, tmp_path, tmp_out):
        """测试审查报告注入"""
        engine = self._make_engine(tmp_path, tmp_out)
        ir = self._make_ir()
        
        prompt = engine._build_td_prompt(
            {"total": 0, "evidence": []}, ir, "# 测试", "# 审查报告\nP0 问题"
        )
        
        assert "PRD 审查报告" in prompt
        assert "P0 问题" in prompt
    
    def test_build_td_prompt_single_service(self, tmp_path, tmp_out):
        """测试单服务不显示拓扑"""
        engine = self._make_engine(tmp_path, tmp_out)
        ir = self._make_ir()
        ir.services = [{"name": "user-service"}]
        
        prompt = engine._build_td_prompt(
            {"total": 0, "evidence": []}, ir, "# 测试", None
        )
        
        assert "跨仓库服务拓扑" not in prompt
    
    def test_build_td_prompt_no_call_graph(self, tmp_path, tmp_out):
        """测试无调用图"""
        engine = self._make_engine(tmp_path, tmp_out)
        ir = self._make_ir()
        ir.call_graph = []
        
        prompt = engine._build_td_prompt(
            {"total": 0, "evidence": []}, ir, "# 测试", None
        )
        
        assert "技术方案生成任务" in prompt  # 不崩溃
    
    def test_generate_td_save_error(self, tmp_path, tmp_out):
        """测试保存失败"""
        engine = self._make_engine(tmp_path, tmp_out)
        
        with patch.object(engine, "_scan_codebase", return_value=self._make_ir()):
            with patch.object(engine, "_query_evidence_for_prd",
                              return_value={"total": 0, "evidence": []}):
                with patch.object(Path, "write_text", side_effect=PermissionError("denied")):
                    with pytest.raises(PermissionError):
                        engine.generate_td("# 测试")
