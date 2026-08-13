"""
Base Engine 深度测试套件
覆盖：_normalize_profile、_get_scan_cache_dir、_try_load_cached_ir、_scan_codebase、
      _parallel_scan、_sequential_scan、_dict_to_ir、_build_*_section、_load_business_cards、_format_weighted_evidence
目标：scripts/base_engine.py 覆盖率 ≥85%
"""
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scripts.base_engine import EngineBase
from scripts.learn_repo import IRDocument


def make_profile(tmp_path, with_repo=True, nested=False):
    """构造 profile"""
    repo_path = tmp_path / "repo"
    if with_repo:
        repo_path.mkdir(exist_ok=True)
        (repo_path / "main.go").write_text("package main\n", encoding="utf-8")
    profile = {
        "name": "test-project",
        "business_domain": "test-domain",
        "repositories": [
            {"path": str(repo_path), "language": "go", "name": "test-repo"},
        ],
    }
    if nested:
        return {"profile": profile}
    return profile


def make_ir():
    """构造 IRDocument"""
    from scripts.learn_repo import RouteDef
    
    ir = IRDocument(repo_name="test", repo_path="/tmp/test", language="go")
    ir.routes = [
        RouteDef(path="/api/login", method="POST", handler="LoginHandler", module="handler", file="auth.go"),
        RouteDef(path="/api/user/{id}", method="GET", handler="GetUser", module="handler", file="user.go"),
    ]
    ir.business_logic = [
        {"handler": "LoginHandler", "description": "登录", "calls": ["AuthService"]},
    ]
    ir.entity_tables = [
        {"entity": "User", "table": "users", "file": "model/user.go"},
    ]
    ir.error_codes = [
        {"name": "ERR_LOGIN", "code": "AUTH_001", "category": "auth", "message": "登录失败"},
    ]
    ir.auth_models = [{"middleware": "AuthMiddleware", "logic": "需要登录"}]
    ir.sql_operations = [
        {"func": "Login", "table": "users", "operation": "SELECT"},
    ]
    ir.test_files = ["auth_test.go"]
    ir.test_functions = [{"name": "TestLogin", "file": "auth_test.go"}]
    ir.coverage_report = {"coverage_pct": 45, "framework": "go test"}
    ir.core_flows = [
        {"flow_name": "登录流程", "entry_point": "LoginHandler", "call_chain": ["LoginHandler"]},
    ]
    ir.packages = {
        "handler": {"files": ["auth.go"], "functions": ["LoginHandler"]},
    }
    ir.call_graph = [
        {"caller": "LoginHandler", "callee": "AuthService"},
    ]
    ir.services = [{"name": "user-service"}]
    return ir


class TestBaseEngine:
    """Base Engine 测试"""
    
    def _make_engine(self, tmp_path, profile=None):
        return EngineBase(
            profile or make_profile(tmp_path),
            str(tmp_path / "out"),
            wiki_path=str(tmp_path),
        )
    
    def test_normalize_profile_flat(self, tmp_path):
        """测试扁平 profile"""
        engine = self._make_engine(tmp_path)
        norm = EngineBase._normalize_profile({"name": "flat"})
        assert norm["name"] == "flat"
    
    def test_normalize_profile_nested(self, tmp_path):
        """测试嵌套 profile"""
        engine = self._make_engine(tmp_path)
        norm = EngineBase._normalize_profile(
            {"profile": {"name": "nested"}}
        )
        assert norm["name"] == "nested"
    
    def test_normalize_profile_empty(self, tmp_path):
        """测试空 profile"""
        engine = self._make_engine(tmp_path)
        norm = EngineBase._normalize_profile({})
        assert norm == {}
    
    def test_get_scan_cache_dir(self, tmp_path):
        """测试缓存目录推断"""
        engine = self._make_engine(tmp_path)
        cache_dir = engine._get_scan_cache_dir()
        assert cache_dir is not None
        assert ".biz_delivery_cache" in cache_dir
    
    def test_get_scan_cache_dir_no_repos(self, tmp_path):
        """测试无仓库"""
        engine = self._make_engine(tmp_path, profile={
            "name": "test", "business_domain": "d", "repositories": []
        })
        assert engine._get_scan_cache_dir() is None
    
    def test_try_load_cached_ir(self, tmp_path):
        """测试加载缓存 IR"""
        cache_dir = tmp_path / ".biz_delivery_cache"
        cache_dir.mkdir()
        (cache_dir / "ir_cache.json").write_text(
            json.dumps({"repo_name": "cached", "language": "go"}),
            encoding="utf-8",
        )
        
        engine = self._make_engine(tmp_path)
        cached = engine._try_load_cached_ir(str(cache_dir))
        assert cached["repo_name"] == "cached"
    
    def test_try_load_cached_ir_missing(self, tmp_path):
        """测试缓存文件不存在"""
        engine = self._make_engine(tmp_path)
        assert engine._try_load_cached_ir(str(tmp_path / "missing")) is None
    
    def test_try_load_cached_ir_stale(self, tmp_path):
        """测试过期缓存"""
        cache_dir = tmp_path / ".biz_delivery_cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "ir_cache.json"
        cache_file.write_text(json.dumps({"repo_name": "old"}), encoding="utf-8")
        # 设置 25 小时前的修改时间
        old_time = time.time() - 25 * 3600
        import os
        os.utime(cache_file, (old_time, old_time))
        
        engine = self._make_engine(tmp_path)
        assert engine._try_load_cached_ir(str(cache_dir)) is None
    
    def test_scan_codebase_no_repos(self, tmp_path):
        """测试无仓库扫描"""
        engine = self._make_engine(tmp_path, profile={
            "name": "test", "business_domain": "d", "repositories": []
        })
        ir = engine._scan_codebase()
        assert ir.repo_name == "none"
        assert ir.language == "unknown"
    
    def test_scan_codebase_with_cache(self, tmp_path):
        """测试使用缓存扫描"""
        cache_dir = tmp_path / ".biz_delivery_cache"
        cache_dir.mkdir()
        (cache_dir / "ir_cache.json").write_text(
            json.dumps({"repo_name": "cached-ir", "language": "go", "structs": []}),
            encoding="utf-8",
        )
        
        engine = self._make_engine(tmp_path)
        # 直接 patch _dict_to_ir 验证缓存路径被使用
        with patch.object(EngineBase, "_dict_to_ir") as mock_dict_to_ir:
            mock_dict_to_ir.return_value = make_ir()
            ir = engine._scan_codebase()
        
        mock_dict_to_ir.assert_called_once()
        assert ir.repo_name == "test"
    
    def test_sequential_scan(self, tmp_path):
        """测试顺序扫描"""
        engine = self._make_engine(tmp_path)
        with patch("scripts.base_engine.GoScanner") as MockScanner:
            mock_scanner = MagicMock()
            mock_scanner.scan_directory.return_value = make_ir()
            MockScanner.return_value = mock_scanner
            
            ir = engine._sequential_scan()
        
        assert ir.repo_name == "multi"
        assert len(ir.routes) == 2
    
    def test_sequential_scan_unsupported_language(self, tmp_path):
        """测试不支持的语言"""
        repo_path = tmp_path / "repo-java"
        repo_path.mkdir()
        profile = {
            "name": "test",
            "business_domain": "d",
            "repositories": [{"path": str(repo_path), "language": "java"}],
        }
        engine = self._make_engine(tmp_path, profile=profile)
        
        ir = engine._sequential_scan()
        assert len(ir.structs) == 0
    
    def test_dict_to_ir(self, tmp_path):
        """测试 dict 转 IR"""
        data = {
            "repo_name": "cached",
            "repo_path": "/tmp",
            "language": "go",
            "structs": [{"name": "User"}],
            "routes": [{"method": "GET", "path": "/api", "handler": "H"}],
        }
        ir = EngineBase._dict_to_ir(data)
        assert ir.repo_name == "cached"
        assert len(ir.structs) == 1
        assert len(ir.routes) == 1
    
    def test_dict_to_ir_empty(self, tmp_path):
        """测试空 dict"""
        ir = EngineBase._dict_to_ir({})
        assert ir.repo_name == "cached"
    
    def test_build_ir_summary(self, tmp_path):
        """测试 IR 摘要"""
        engine = self._make_engine(tmp_path)
        summary = engine._build_ir_summary(make_ir())
        assert isinstance(summary, list)
        assert len(summary) > 0
    
    def test_build_routes_section(self, tmp_path):
        """测试路由章节"""
        engine = self._make_engine(tmp_path)
        section = engine._build_routes_section(make_ir())
        assert "关键路由" in section
        assert "/api/login" in section
    
    def test_build_business_logic_section(self, tmp_path):
        """测试业务逻辑章节"""
        engine = self._make_engine(tmp_path)
        section = engine._build_business_logic_section(make_ir())
        assert "登录" in section
    
    def test_build_entity_table_section(self, tmp_path):
        """测试实体表章节"""
        engine = self._make_engine(tmp_path)
        section = engine._build_entity_table_section(make_ir())
        assert "users" in section
    
    def test_build_error_code_section(self, tmp_path):
        """测试错误码章节"""
        engine = self._make_engine(tmp_path)
        section = engine._build_error_code_section(make_ir())
        assert "AUTH_001" in section
    
    def test_build_auth_model_section(self, tmp_path):
        """测试鉴权模型章节"""
        engine = self._make_engine(tmp_path)
        section = engine._build_auth_model_section(make_ir())
        assert "AuthMiddleware" in section
    
    def test_build_sql_section(self, tmp_path):
        """测试 SQL 章节"""
        engine = self._make_engine(tmp_path)
        section = engine._build_sql_section(make_ir())
        assert "users" in section
    
    def test_build_test_coverage_section(self, tmp_path):
        """测试测试覆盖章节"""
        engine = self._make_engine(tmp_path)
        section = engine._build_test_coverage_section(make_ir())
        assert "测试覆盖情况" in section
    
    def test_build_core_flows_section(self, tmp_path):
        """测试核心流程章节"""
        engine = self._make_engine(tmp_path)
        section = engine._build_core_flows_section(make_ir())
        assert "登录流程" in section
    
    def test_build_packages_section(self, tmp_path):
        """测试包结构章节"""
        engine = self._make_engine(tmp_path)
        section = engine._build_packages_section(make_ir())
        assert "handler" in section
    
    def test_build_call_graph_section(self, tmp_path):
        """测试调用图章节"""
        engine = self._make_engine(tmp_path)
        section = engine._build_call_graph_section(make_ir())
        assert "LoginHandler" in section
    
    def test_load_business_cards(self, tmp_path):
        """测试加载业务卡片"""
        cards = {"scenario_cards": [{"scenario": "登录"}]}
        cards_file = tmp_path / "business_cards.json"
        cards_file.write_text(json.dumps(cards), encoding="utf-8")
        
        engine = self._make_engine(tmp_path)
        loaded = engine._load_business_cards(str(tmp_path))
        assert loaded["scenario_cards"][0]["scenario"] == "登录"
    
    def test_load_business_cards_missing(self, tmp_path):
        """测试业务卡片不存在"""
        engine = self._make_engine(tmp_path)
        assert engine._load_business_cards(str(tmp_path)) is None
    
    def test_format_weighted_evidence(self, tmp_path):
        """测试加权证据格式化"""
        engine = self._make_engine(tmp_path)
        evidence = [
            {"title": "file1.go", "score": 0.9, "source_type": "code", "content": "func A"},
            {"title": "file2.go", "score": 0.5, "source_type": "wiki", "content": "doc"},
        ]
        formatted = engine._format_weighted_evidence(evidence, top_n=5)
        assert isinstance(formatted, list)
        assert len(formatted) <= 5
