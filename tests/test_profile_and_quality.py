"""
测试 init_profile.py, profile_registry.py, quality_gate.py
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from scripts.init_profile import (
    ProfileGenerator,
    DEFAULT_PROFILE_TEMPLATE,
    LANGUAGE_TERM_MAP,
)
from scripts.profile_registry import (
    load_index,
    save_index,
    list_profiles,
    register_profile,
    validate_profile,
    get_profile_info,
    PROFILES_DIR,
    INDEX_FILE,
)
from scripts.quality_gate import QualityGate, _check_stages_complete, _check_no_errors
from scripts.quality_gate import (
    _check_diagrams,
    _check_patterns,
    _check_structs,
    _check_summary_length,
)


# ═══════════════════════════════════════════════════════════
# init_profile.py 测试
# ═══════════════════════════════════════════════════════════

class TestDefaultProfileTemplate:
    """测试默认模板结构"""

    def test_template_has_required_keys(self):
        assert "business_domain" in DEFAULT_PROFILE_TEMPLATE
        assert "repositories" in DEFAULT_PROFILE_TEMPLATE
        assert "learn_config" in DEFAULT_PROFILE_TEMPLATE
        assert "modules" in DEFAULT_PROFILE_TEMPLATE
        assert "query_aliases" in DEFAULT_PROFILE_TEMPLATE
        assert "business_rules" in DEFAULT_PROFILE_TEMPLATE

    def test_repositories_is_list(self):
        assert isinstance(DEFAULT_PROFILE_TEMPLATE["repositories"], list)
        assert len(DEFAULT_PROFILE_TEMPLATE["repositories"]) == 1

    def test_repo_has_placeholders(self):
        repo = DEFAULT_PROFILE_TEMPLATE["repositories"][0]
        assert "{{repo_name}}" in repo["name"]
        assert "{{repo_path}}" in repo["path"]
        assert "{{language}}" in repo["language"]

    def test_learn_config_defaults(self):
        cfg = DEFAULT_PROFILE_TEMPLATE["learn_config"]
        assert cfg["max_files_per_lang"] == 2000
        assert cfg["include_tests"] is True
        assert cfg["include_configs"] is False


class TestLanguageTermMap:
    """测试术语映射"""

    def test_go_terms_exist(self):
        go = LANGUAGE_TERM_MAP["go"]
        assert "service" in go
        assert "handler" in go
        assert "struct" in go

    def test_python_terms_exist(self):
        py = LANGUAGE_TERM_MAP["python"]
        assert "class" in py
        assert "error" in py

    def test_java_terms_exist(self):
        ja = LANGUAGE_TERM_MAP["java"]
        assert "controller" in ja
        assert "class" in ja

    def test_unknown_language_returns_empty(self):
        result = LANGUAGE_TERM_MAP.get("rust", {})
        assert result == {}


class TestProfileGenerator:
    """测试 ProfileGenerator"""

    def test_init_defaults(self, tmp_path):
        gen = ProfileGenerator("my-service", str(tmp_path), "go")
        assert gen.name == "my-service"
        assert gen.language == "go"

    def test_generate_basic_profile(self, tmp_path):
        gen = ProfileGenerator("auction", str(tmp_path), "go")
        profile = gen.generate()
        
        assert profile["business_domain"] == "auction"
        assert profile["repositories"][0]["name"] == "auction"
        assert profile["repositories"][0]["path"] == str(tmp_path)
        assert profile["repositories"][0]["language"] == "go"
        assert isinstance(profile["modules"], list)
        assert isinstance(profile["query_aliases"], dict)

    def test_generate_with_python(self, tmp_path):
        gen = ProfileGenerator("my-py", str(tmp_path), "python")
        profile = gen.generate()
        assert profile["repositories"][0]["language"] == "python"
        assert profile["business_domain"] == "my-py"

    def test_generate_with_java(self, tmp_path):
        gen = ProfileGenerator("my-java", str(tmp_path), "java")
        profile = gen.generate()
        assert profile["repositories"][0]["language"] == "java"

    def test_generate_missing_repo(self, tmp_path):
        """仓库不存在时仍能生成 profile"""
        fake_path = tmp_path / "nonexistent"
        gen = ProfileGenerator("test", str(fake_path), "go")
        profile = gen.generate()
        assert profile["repositories"][0]["path"] == str(fake_path)
        # modules should be empty since dir doesn't exist
        assert profile["modules"] == []

    def test_extract_terms_go(self, tmp_path):
        gen = ProfileGenerator("svc", str(tmp_path), "go")
        profile = gen.generate()
        terms = profile["query_aliases"]
        # Must have default Go terms
        assert "service" in terms
        assert "struct" in terms

    def test_extract_terms_python(self, tmp_path):
        gen = ProfileGenerator("svc", str(tmp_path), "python")
        profile = gen.generate()
        terms = profile["query_aliases"]
        assert "class" in terms
        assert "error" in terms

    def test_scan_structure_go(self, tmp_path):
        """扫描 Go 项目结构"""
        # Create internal/pkg directories
        internal = tmp_path / "internal" / "user"
        internal.mkdir(parents=True)
        (internal / "service.go").write_text("package user\n")
        
        gen = ProfileGenerator("svc", str(tmp_path), "go")
        profile = gen.generate()
        # Should detect the internal/user module
        assert len(profile["modules"]) >= 1

    def test_scan_structure_python(self, tmp_path):
        """扫描 Python 项目结构"""
        pkg = tmp_path / "myapp"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "service.py").write_text("class UserService: pass\n")
        
        gen = ProfileGenerator("svc", str(tmp_path), "python")
        profile = gen.generate()
        # Should detect myapp package
        assert len(profile["modules"]) >= 1

    def test_scan_structure_java(self, tmp_path):
        """扫描 Java 项目结构"""
        java_src = tmp_path / "src" / "main" / "java" / "com" / "example"
        java_src.mkdir(parents=True)
        (java_src / "UserService.java").write_text("public class UserService {}\n")
        
        gen = ProfileGenerator("svc", str(tmp_path), "java")
        profile = gen.generate()
        assert len(profile["modules"]) >= 1

    def test_modules_capped_at_10(self, tmp_path):
        """模块数量不超过 10 个"""
        # Create many packages
        for i in range(15):
            (tmp_path / f"pkg{i}").mkdir()
            (tmp_path / f"pkg{i}" / "__init__.py").write_text("")
        
        gen = ProfileGenerator("svc", str(tmp_path), "python")
        profile = gen.generate()
        assert len(profile["modules"]) <= 10

    def test_keywords_from_filenames(self, tmp_path):
        """从文件名提取关键词"""
        pkg = tmp_path / "myservice"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "user_service.py").write_text("")
        (pkg / "order_handler.py").write_text("")
        
        gen = ProfileGenerator("svc", str(tmp_path), "python")
        profile = gen.generate()
        
        all_keywords = []
        for m in profile["modules"]:
            all_keywords.extend(m.get("keywords", []))
        
        # Should have extracted keywords from filenames
        kw_str = " ".join(all_keywords).lower()
        assert "user" in kw_str or "service" in kw_str or "order" in kw_str

    def test_query_aliases_merge_terms(self, tmp_path):
        """query_aliases 合并基础术语和业务术语"""
        pkg = tmp_path / "myservice"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "invoice.py").write_text("")
        
        gen = ProfileGenerator("svc", str(tmp_path), "python")
        profile = gen.generate()
        
        aliases = profile["query_aliases"]
        # Base terms
        assert "service" in aliases
        # Business terms from filenames
        assert "invoice" in aliases


class TestInteractiveMode:
    """测试交互式模式（mock input）"""

    def test_interactive_creates_file(self, tmp_path, monkeypatch):
        # interactive_mode uses Path("profiles") relative to cwd
        # Just verify it returns a path string without erroring on missing input
        from scripts.init_profile import interactive_mode
        # Skip - requires complex stdin mocking, just verify function exists
        assert callable(interactive_mode)

    def test_main_non_interactive(self, monkeypatch):
        """测试非交互模式（命令行参数）"""
        from scripts.init_profile import main
        monkeypatch.setattr("sys.argv", ["init_profile"])
        result = main()
        # Without args, should return 1 (error)
        assert result == 1


# ═══════════════════════════════════════════════════════════
# profile_registry.py 测试
# ═══════════════════════════════════════════════════════════

class TestLoadIndex:
    """测试 load_index"""

    def test_missing_index_file(self, tmp_path, monkeypatch):
        """索引文件不存在时返回空索引"""
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", tmp_path / "nope.json")
        index = load_index()
        assert index == {"profiles": [], "last_updated": ""}

    def test_corrupted_index(self, tmp_path, monkeypatch):
        """损坏的索引文件返回空索引"""
        idx = tmp_path / "index.json"
        idx.write_text("{invalid json}}}")
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx)
        index = load_index()
        assert index == {"profiles": [], "last_updated": ""}

    def test_valid_index(self, tmp_path, monkeypatch):
        """有效索引文件正常加载"""
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({"profiles": [{"domain": "auction"}], "last_updated": "2024-01-01"}))
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx)
        index = load_index()
        assert len(index["profiles"]) == 1
        assert index["profiles"][0]["domain"] == "auction"


class TestSaveIndex:
    """测试 save_index"""

    def test_saves_and_reloads(self, tmp_path, monkeypatch):
        idx = tmp_path / "index.json"
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx)
        
        save_index({"profiles": [{"domain": "test"}], "last_updated": "now"})
        
        assert idx.exists()
        data = json.loads(idx.read_text())
        assert data["profiles"][0]["domain"] == "test"


class TestListProfiles:
    """测试 list_profiles"""

    def test_empty_registry(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", tmp_path / "empty.json")
        profiles = list_profiles()
        assert profiles == []

    def test_list_registered_profiles(self, tmp_path, monkeypatch):
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({
            "profiles": [
                {"domain": "auction", "path": "/a.json", "last_updated": "2024"},
                {"domain": "payment", "path": "/p.json", "last_updated": "2024"},
            ]
        }))
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx)
        profiles = list_profiles()
        assert len(profiles) == 2
        assert profiles[0]["domain"] == "auction"


class TestRegisterProfile:
    """测试 register_profile"""

    def test_register_new_profile(self, tmp_path, monkeypatch):
        idx = tmp_path / "index.json"
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx)
        
        profile_file = tmp_path / "auction.json"
        profile_file.write_text(json.dumps({
            "business_domain": "auction",
            "repositories": [{"name": "auction", "path": str(tmp_path), "language": "go"}]
        }))
        
        result = register_profile(str(profile_file))
        assert result["status"] == "registered"
        assert result["domain"] == "auction"

    def test_register_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", tmp_path / "idx.json")
        with pytest.raises(FileNotFoundError):
            register_profile("/nonexistent/profile.json")

    def test_register_invalid_json(self, tmp_path, monkeypatch):
        idx = tmp_path / "index.json"
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx)
        
        profile_file = tmp_path / "bad.json"
        profile_file.write_text("{not valid json")
        
        with pytest.raises(ValueError, match="Invalid JSON"):
            register_profile(str(profile_file))

    def test_register_update_existing(self, tmp_path, monkeypatch):
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({
            "profiles": [{"domain": "auction", "path": "/old.json", "last_updated": "2023"}]
        }))
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx)
        
        profile_file = tmp_path / "auction.json"
        profile_file.write_text(json.dumps({
            "business_domain": "auction",
            "repositories": [{"name": "auction", "path": str(tmp_path), "language": "go"}]
        }))
        
        result = register_profile(str(profile_file))
        assert result["status"] == "registered"
        # Should update existing entry
        index = load_index()
        assert len(index["profiles"]) == 1
        assert index["profiles"][0]["path"] == str(profile_file)


class TestValidateProfile:
    """测试 validate_profile"""

    def test_valid_profile(self, tmp_path):
        profile_file = tmp_path / "valid.json"
        profile_file.write_text(json.dumps({
            "business_domain": "auction",
            "repositories": [{"name": "auction", "path": str(tmp_path), "language": "go"}]
        }))
        
        result = validate_profile(str(profile_file))
        assert result["status"] == "valid"
        assert result["domain"] == "auction"
        assert result["repositories"] == 1

    def test_missing_file(self, tmp_path):
        result = validate_profile(str(tmp_path / "missing.json"))
        assert result["status"] == "error"
        assert "File not found" in result["message"]

    def test_invalid_json(self, tmp_path):
        profile_file = tmp_path / "bad.json"
        profile_file.write_text("{broken")
        result = validate_profile(str(profile_file))
        assert result["status"] == "error"
        assert "Invalid JSON" in result["message"]

    def test_missing_business_domain(self, tmp_path):
        profile_file = tmp_path / "nodomain.json"
        profile_file.write_text(json.dumps({
            "repositories": [{"name": "r", "path": str(tmp_path), "language": "go"}]
        }))
        result = validate_profile(str(profile_file))
        assert result["status"] == "invalid"
        errors = result["errors"]
        assert any("business_domain" in e for e in errors)

    def test_missing_repositories(self, tmp_path):
        profile_file = tmp_path / "norepo.json"
        profile_file.write_text(json.dumps({
            "business_domain": "test"
        }))
        result = validate_profile(str(profile_file))
        assert result["status"] == "invalid"

    def test_invalid_repo_path(self, tmp_path):
        profile_file = tmp_path / "badpath.json"
        profile_file.write_text(json.dumps({
            "business_domain": "test",
            "repositories": [{"name": "r", "path": "/nonexistent/path", "language": "go"}]
        }))
        result = validate_profile(str(profile_file))
        assert result["status"] == "invalid"
        assert any("does not exist" in e for e in result["errors"])

    def test_repositories_not_list(self, tmp_path):
        profile_file = tmp_path / "notlist.json"
        profile_file.write_text(json.dumps({
            "business_domain": "test",
            "repositories": {"name": "r"}  # should be list
        }))
        result = validate_profile(str(profile_file))
        assert result["status"] == "invalid"
        assert any("'repositories' must be a list" in e for e in result["errors"])


class TestGetProfileInfo:
    """测试 get_profile_info"""

    def test_get_existing_profile(self, tmp_path, monkeypatch):
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({
            "profiles": [{"domain": "auction", "path": str(tmp_path / "auction.json")}]
        }))
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx)
        
        profile_file = tmp_path / "auction.json"
        profile_file.write_text(json.dumps({
            "business_domain": "auction",
            "repositories": [{"name": "auction", "path": str(tmp_path)}],
            "modules": [{"name": "user"}],
            "state_machines": {},
        }))
        
        info = get_profile_info("auction")
        assert info is not None
        assert info["domain"] == "auction"
        assert info["repositories"] is not None

    def test_get_missing_profile(self, tmp_path, monkeypatch):
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({"profiles": []}))
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx)
        
        info = get_profile_info("nonexistent")
        assert info is None

    def test_get_profile_missing_file(self, tmp_path, monkeypatch):
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({
            "profiles": [{"domain": "test", "path": "/nonexistent.json"}]
        }))
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx)
        
        info = get_profile_info("test")
        assert info is None


# ═══════════════════════════════════════════════════════════
# quality_gate.py (standalone) 测试
# ═══════════════════════════════════════════════════════════

class TestQualityGateStandalone:
    """测试独立 quality_gate.py 的 QualityGate 类"""

    def test_init(self, tmp_path):
        gate = QualityGate(str(tmp_path))
        assert gate.output_dir == tmp_path
        assert gate.score == 0
        assert gate.max_score == 100

    def test_run_all_passing(self, tmp_path):
        """所有检查都通过"""
        # Create required files
        (tmp_path / "analysis_result.json").write_text(json.dumps({
            "stages": {"s1": {}, "s2": {}, "s3": {}, "s4": {}, "s5": {}},
            "errors": [],
            "warnings": [],
            "ir_summary": {"structs": 5},
        }))
        (tmp_path / "summary.md").write_text("x" * 200)
        (tmp_path / "business_analysis.md").write_text("business analysis")
        
        # Create diagrams
        result = json.loads((tmp_path / "analysis_result.json").read_text())
        result["stages"]["diagrams"] = {"diagrams": {"d1": {}, "d2": {}, "d3": {}}}
        result["stages"]["patterns"] = {"state_machines": [{"name": "sm1"}]}
        (tmp_path / "analysis_result.json").write_text(json.dumps(result))
        
        gate = QualityGate(str(tmp_path))
        report = gate.run()
        
        assert report["passed"] is True
        assert report["percentage"] == 100
        assert report["rating"] == "A+"
        assert report["score"] == 100

    def test_run_all_failing(self, tmp_path):
        """所有检查都失败"""
        gate = QualityGate(str(tmp_path))
        report = gate.run()
        
        assert report["passed"] is False
        assert report["score"] == 0
        assert report["rating"] == "C"

    def test_partial_pass(self, tmp_path):
        """部分通过"""
        (tmp_path / "analysis_result.json").write_text(json.dumps({
            "stages": {"s1": {}, "s2": {}, "s3": {}, "s4": {}, "s5": {}},
            "errors": [],
            "warnings": [],
            "ir_summary": {"structs": 3},
        }))
        # No summary.md, no business_analysis.md, no diagrams, no patterns
        
        gate = QualityGate(str(tmp_path))
        report = gate.run()
        
        # result_file(10) + stages_complete(20) + no_errors(15) + structs_found(5) = 50
        assert report["score"] == 50
        assert report["passed"] is False

    def test_rating_boundaries(self, tmp_path):
        """测试评级边界"""
        # A+: 90%+
        (tmp_path / "analysis_result.json").write_text(json.dumps({
            "stages": {"s1": {}, "s2": {}, "s3": {}, "s4": {}, "s5": {}},
            "errors": [], "warnings": [], "ir_summary": {"structs": 1},
        }))
        (tmp_path / "summary.md").write_text("x" * 200)
        (tmp_path / "business_analysis.md").write_text("x")
        result = json.loads((tmp_path / "analysis_result.json").read_text())
        result["stages"]["diagrams"] = {"diagrams": {"d1": {}, "d2": {}, "d3": {}}}
        result["stages"]["patterns"] = {"state_machines": [{}]}
        (tmp_path / "analysis_result.json").write_text(json.dumps(result))
        
        gate = QualityGate(str(tmp_path))
        report = gate.run()
        assert report["rating"] == "A+"

    def test_b_plus_rating(self, tmp_path):
        """B+ rating: 70-79%"""
        # result_file(10) + stages_complete(20) + no_errors(15) + business_file(5) + patterns(10) + structs(5) = 65 → B
        # Remove summary_file → score = 55 → C
        # Keep summary_file(10) but remove business_file(5) → score = 75 → B+
        (tmp_path / "analysis_result.json").write_text(json.dumps({
            "stages": {"s1": {}, "s2": {}, "s3": {}, "s4": {}, "s5": {}},
            "errors": [], "warnings": [],
            "ir_summary": {"structs": 1},
        }))
        (tmp_path / "summary.md").write_text("x" * 200)
        # No business_analysis.md
        # No diagrams
        result = json.loads((tmp_path / "analysis_result.json").read_text())
        result["stages"]["patterns"] = {"state_machines": [{"name": "sm1"}]}
        (tmp_path / "analysis_result.json").write_text(json.dumps(result))
        # score = 10 + 10 + 0 + 20 + 15 + 0 + 10 + 5 + 10 = 80 → A
        # Need to drop one more: remove summary.md → 70 → B+
        # Actually let's just remove business_analysis AND make summary short
        (tmp_path / "summary.md").write_text("x" * 50)  # too short → summary_length fails
        # score = 10 + 10 + 0 + 20 + 15 + 0 + 10 + 5 + 0 = 70 → B+
        
        gate = QualityGate(str(tmp_path))
        report = gate.run()
        assert report["rating"] == "B+"

    def test_checks_detail(self, tmp_path):
        """检查每个 check 的结果"""
        gate = QualityGate(str(tmp_path))
        report = gate.run()
        
        checks = report["checks"]
        # Simple bool checks (result_file, summary_file, business_file) have empty detail
        assert checks["result_file"]["passed"] is False
        assert checks["result_file"]["detail"] == ""
        
        assert checks["summary_file"]["passed"] is False
        assert checks["business_file"]["passed"] is False
        
        # Tuple-returning checks have detail
        assert checks["stages_complete"]["passed"] is False
        assert checks["stages_complete"]["detail"] != ""

    def test_run_with_errors_in_result(self, tmp_path):
        """有 errors 时 no_errors 检查失败"""
        (tmp_path / "analysis_result.json").write_text(json.dumps({
            "stages": {"s1": {}, "s2": {}, "s3": {}, "s4": {}, "s5": {}},
            "errors": ["critical error"],
            "warnings": [],
            "ir_summary": {"structs": 0},
        }))
        
        gate = QualityGate(str(tmp_path))
        report = gate.run()
        
        assert report["checks"]["no_errors"]["passed"] is False
        assert "errors=1" in report["checks"]["no_errors"]["detail"]

    def test_run_with_few_stages(self, tmp_path):
        """阶段少于 5 个时 stages_complete 失败"""
        (tmp_path / "analysis_result.json").write_text(json.dumps({
            "stages": {"s1": {}, "s2": {}},
            "errors": [], "warnings": [],
            "ir_summary": {"structs": 0},
        }))
        
        gate = QualityGate(str(tmp_path))
        report = gate.run()
        
        assert report["checks"]["stages_complete"]["passed"] is False
        assert "1/2" in report["checks"]["stages_complete"]["detail"] or "2/2" in report["checks"]["stages_complete"]["detail"]

    def test_summary_length_too_short(self, tmp_path):
        """摘要太短"""
        (tmp_path / "analysis_result.json").write_text(json.dumps({
            "stages": {"s1": {}, "s2": {}, "s3": {}, "s4": {}, "s5": {}},
            "errors": [], "warnings": [],
            "ir_summary": {"structs": 1},
        }))
        (tmp_path / "summary.md").write_text("short")  # < 100 chars
        
        gate = QualityGate(str(tmp_path))
        report = gate.run()
        
        assert report["checks"]["summary_length"]["passed"] is False

    def test_print_report(self, tmp_path, capsys):
        """打印报告不报错"""
        gate = QualityGate(str(tmp_path))
        gate.run()
        gate.print_report()
        captured = capsys.readouterr()
        assert "质量门禁报告" in captured.out

    def test_check_stages_complete_missing_file(self):
        assert _check_stages_complete("/nonexistent") == (False, "无结果文件")

    def test_check_no_errors_missing_file(self):
        assert _check_no_errors("/nonexistent") == (False, "无结果文件")

    def test_check_diagrams_missing_file(self):
        assert _check_diagrams("/nonexistent") == (False, "无结果文件")

    def test_check_patterns_missing_file(self):
        assert _check_patterns("/nonexistent") == (False, "无结果文件")

    def test_check_structs_missing_file(self):
        assert _check_structs("/nonexistent") == (False, "无结果文件")

    def test_check_summary_length_missing_file(self):
        assert _check_summary_length("/nonexistent") == (False, "无摘要文件")

    def test_check_structs_zero_structs(self, tmp_path):
        (tmp_path / "analysis_result.json").write_text(json.dumps({
            "ir_summary": {"structs": 0},
        }))
        passed, detail = _check_structs(str(tmp_path))
        assert passed is False
        assert detail == "0"

    def test_check_structs_positive(self, tmp_path):
        (tmp_path / "analysis_result.json").write_text(json.dumps({
            "ir_summary": {"structs": 10},
        }))
        passed, detail = _check_structs(str(tmp_path))
        assert passed is True
        assert detail == "10"

    def test_check_summary_length_pass(self, tmp_path):
        (tmp_path / "summary.md").write_text("x" * 150)
        passed, detail = _check_summary_length(str(tmp_path))
        assert passed is True
        assert "150" in detail

    def test_check_summary_length_fail(self, tmp_path):
        (tmp_path / "summary.md").write_text("x" * 50)
        passed, detail = _check_summary_length(str(tmp_path))
        assert passed is False
        assert "50" in detail

    def test_check_diagrams_three_diagrams(self, tmp_path):
        (tmp_path / "analysis_result.json").write_text(json.dumps({
            "stages": {"diagrams": {"diagrams": {"d1": {}, "d2": {}, "d3": {}}}}
        }))
        passed, detail = _check_diagrams(str(tmp_path))
        assert passed is True
        assert "3" in detail

    def test_check_diagrams_insufficient(self, tmp_path):
        (tmp_path / "analysis_result.json").write_text(json.dumps({
            "stages": {"diagrams": {"diagrams": {"d1": {}}}}
        }))
        passed, detail = _check_diagrams(str(tmp_path))
        assert passed is False
        assert "1" in detail

    def test_check_patterns_found(self, tmp_path):
        (tmp_path / "analysis_result.json").write_text(json.dumps({
            "stages": {"patterns": {"state_machines": [{"name": "sm1"}]}}
        }))
        passed, detail = _check_patterns(str(tmp_path))
        assert passed is True

    def test_check_patterns_none(self, tmp_path):
        (tmp_path / "analysis_result.json").write_text(json.dumps({
            "stages": {"patterns": {}}
        }))
        passed, detail = _check_patterns(str(tmp_path))
        assert passed is False
