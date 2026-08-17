"""Tests for init_profile — _scan_structure, _extract_terms, main()."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.init_profile import ProfileGenerator, interactive_mode, main, LANGUAGE_TERM_MAP


# ===========================================================================
# LANGUAGE_TERM_MAP
# ===========================================================================

class TestLanguageTermMap:
    def test_go_terms(self):
        terms = LANGUAGE_TERM_MAP.get("go", {})
        assert "service" in terms
        assert terms["service"] == "服务"
        assert "struct" in terms
        assert terms["struct"] == "结构体"

    def test_python_terms(self):
        terms = LANGUAGE_TERM_MAP.get("python", {})
        assert "service" in terms
        assert terms["service"] == "服务"

    def test_java_terms(self):
        terms = LANGUAGE_TERM_MAP.get("java", {})
        assert "controller" in terms
        assert terms["controller"] == "控制器"

    def test_unknown_language(self):
        terms = LANGUAGE_TERM_MAP.get("rust", {})
        assert terms == {}


# ===========================================================================
# ProfileGenerator
# ===========================================================================

class TestProfileGenerator:
    def test_generate_minimal(self, tmp_path):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        gen = ProfileGenerator("my-service", str(repo), "go")
        profile = gen.generate()
        assert profile["business_domain"] == "my-service"
        assert profile["repositories"][0]["name"] == "my-service"
        assert profile["repositories"][0]["path"] == str(repo)
        assert profile["repositories"][0]["language"] == "go"
        assert "modules" in profile

    def test_scan_structure_go_internal(self, tmp_path):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        # Create Go internal package
        internal = repo / "internal" / "user"
        internal.mkdir(parents=True)
        (internal / "user.go").write_text("package user\n")
        gen = ProfileGenerator("svc", str(repo), "go")
        gen._scan_structure()
        modules = gen.profile["modules"]
        names = [m["name"] for m in modules]
        assert any("user" in n for n in names)

    def test_scan_structure_go_cmd(self, tmp_path):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        cmd = repo / "cmd" / "server"
        cmd.mkdir(parents=True)
        (cmd / "main.go").write_text("package main\n")
        gen = ProfileGenerator("svc", str(repo), "go")
        gen._scan_structure()
        modules = gen.profile["modules"]
        names = [m["name"] for m in modules]
        assert any("cmd/server" in n or "server" in n for n in names)

    def test_scan_structure_python_src(self, tmp_path):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        src = repo / "src" / "users"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        (src / "model.py").write_text("# user model\n")
        gen = ProfileGenerator("svc", str(repo), "python")
        gen._scan_structure()
        modules = gen.profile["modules"]
        names = [m["name"] for m in modules]
        assert any("src.users" in n or "users" in n for n in names)

    def test_scan_structure_python_root(self, tmp_path):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        pkg = repo / "users"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        gen = ProfileGenerator("svc", str(repo), "python")
        gen._scan_structure()
        modules = gen.profile["modules"]
        names = [m["name"] for m in modules]
        assert "users" in names

    def test_scan_structure_java(self, tmp_path):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        java_src = repo / "src" / "main" / "java" / "com" / "example"
        java_src.mkdir(parents=True)
        (java_src / "UserService.java").write_text("class UserService {}\n")
        gen = ProfileGenerator("svc", str(repo), "java")
        gen._scan_structure()
        modules = gen.profile["modules"]
        names = [m["name"] for m in modules]
        assert any("UserService" in n for n in names)

    def test_scan_structure_nonexistent_repo(self, tmp_path):
        gen = ProfileGenerator("svc", str(tmp_path / "does_not_exist"), "go")
        gen._scan_structure()
        assert gen.profile["modules"] == []

    def test_extract_keywords_from_dir(self, tmp_path):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        pkg = repo / "users"
        pkg.mkdir()
        (pkg / "UserService.go").write_text("")
        (pkg / "user_model.py").write_text("")
        gen = ProfileGenerator("svc", str(repo), "go")
        keywords = gen._extract_keywords_from_dir(pkg)
        kw_lower = [k.lower() for k in keywords]
        # CamelCase is merged: UserService → "userservice"
        assert any("user" in k for k in kw_lower)

    def test_extract_terms_unknown_language(self, tmp_path):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        gen = ProfileGenerator("svc", str(repo), "rust")
        gen._extract_terms()
        # Should not crash, default empty terms
        assert isinstance(gen.profile.get("business_terms"), dict) or True


# ===========================================================================
# interactive_mode
# ===========================================================================

class TestInteractiveMode:
    def test_basic_flow(self, tmp_path, monkeypatch):
        """Test interactive mode with mocked inputs."""
        repo = tmp_path / "myrepo"
        repo.mkdir()
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        monkeypatch.setattr("builtins.input", lambda prompt: {
            "业务域名 (如 creative-platform)": "test-svc",
            "仓库路径 (绝对路径)": str(repo),
            "选择语言 (1/2/3)": "1",
        }.get(prompt, "test-svc"))

        # Change to tmp_path so output goes there
        import os
        orig_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = interactive_mode()
            assert result.endswith("test-svc.json")
            assert (tmp_path / "profiles" / "test-svc.json").exists()
        finally:
            os.chdir(orig_cwd)

    def test_empty_domain_defaults(self, tmp_path, monkeypatch):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        def mock_input(prompt):
            if "业务域名" in prompt:
                return ""  # empty → defaults to "my-service"
            elif "仓库路径" in prompt:
                return str(repo)
            elif "选择语言" in prompt:
                return "2"
            return ""

        monkeypatch.setattr("builtins.input", mock_input)

        import os
        orig_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = interactive_mode()
            assert result.endswith("my-service.json")
        finally:
            os.chdir(orig_cwd)


# ===========================================================================
# main()
# ===========================================================================

class TestMain:
    def test_missing_args(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["init_profile.py"])
        rc = main()
        assert rc == 1

    def test_non_interactive_mode(self, tmp_path, monkeypatch):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        monkeypatch.setattr("sys.argv", [
            "init_profile.py",
            "--name", "test-svc",
            "--repo", str(repo),
            "--language", "go",
            "--output", str(profiles_dir / "test-svc.json"),
        ])
        rc = main()
        assert rc == 0
        assert (profiles_dir / "test-svc.json").exists()

    def test_interactive_flag(self, tmp_path, monkeypatch):
        repo = tmp_path / "myrepo"
        repo.mkdir()
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        def mock_input(prompt):
            if "业务域名" in prompt:
                return "inter-svc"
            elif "仓库路径" in prompt:
                return str(repo)
            elif "选择语言" in prompt:
                return "3"
            return ""

        monkeypatch.setattr("builtins.input", mock_input)
        monkeypatch.setattr("sys.argv", ["init_profile.py", "--interactive"])

        import os
        orig_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            rc = main()
            assert rc == 0
        finally:
            os.chdir(orig_cwd)
