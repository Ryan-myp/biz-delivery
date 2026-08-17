"""Additional tests for project_auto_detector to improve coverage."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.project_auto_detector import (
    detect_language, detect_framework, detect_architecture,
    estimate_scale, find_entry_points, detect_project,
    generate_profile, _get_relevant_modules,
)


class TestDetectLanguageEdgeCases:
    """Test detect_language edge cases not covered by existing tests."""

    def test_unknown_language(self, tmp_path):
        """Empty directory → unknown."""
        lang = detect_language(tmp_path)
        assert lang == "unknown"

    def test_indicator_match_score_increased(self, tmp_path):
        """When indicator text is found in file, score += 5 path."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.go").write_text('package main\nfunc main() {}\n')
        lang = detect_language(repo)
        assert lang == "go"

    def test_python_language(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "app.py").write_text('from flask import Flask\napp = Flask(__name__)\n')
        lang = detect_language(repo)
        assert lang == "python"

    def test_java_language(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "App.java").write_text('public class App { public static void main(String[] a) {} }\n')
        lang = detect_language(repo)
        assert lang == "java"


class TestDetectFrameworkEdgeCases:
    """Test detect_framework edge cases."""

    def test_unknown_language(self, tmp_path):
        fw = detect_framework(tmp_path, "rust")
        assert fw == "unknown"

    def test_python_fastapi(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text('from fastapi import FastAPI\napp = FastAPI()\n')
        fw = detect_framework(repo, "python")
        assert fw == "fastapi"

    def test_python_flask(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "app.py").write_text('from flask import Flask\napp = Flask(__name__)\n')
        fw = detect_framework(repo, "python")
        assert fw == "flask"

    def test_go_gin(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.go").write_text('import "github.com/gin-gonic/gin"\nfunc main() {}\n')
        fw = detect_framework(repo, "go")
        assert fw == "gin"

    def test_go_no_framework(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.go").write_text('package main\nfunc main() {}\n')
        fw = detect_framework(repo, "go")
        assert fw == "none"


class TestDetectArchitectureEdgeCases:
    """Test detect_architecture for non-standard languages."""

    def test_non_go_python_returns_monolith(self, tmp_path):
        """For unsupported languages, returns monolith."""
        arch = detect_architecture(tmp_path, "rust")
        assert arch == "monolith"

    def test_python_monolith(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "app.py").write_text('from flask import Flask\n')
        arch = detect_architecture(repo, "python")
        assert arch == "monolith"

    def test_python_microservice(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        for i in range(3):
            (repo / f"app{i}.py").write_text('from flask import Flask\n')
        # Need blueprint files for microservice
        (repo / "blueprint_a.py").write_text('')
        (repo / "blueprint_b.py").write_text('')
        arch = detect_architecture(repo, "python")
        assert arch == "microservice"


class TestEstimateScaleEdgeCases:
    """Test estimate_scale for all scale thresholds."""

    def test_small_project(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        for i in range(5):
            (repo / f"file{i}.py").write_text('x = 1\n')
        info = estimate_scale(repo, "python")
        assert info["scale"] == "small"
        assert info["max_files"] <= 500

    def test_medium_project(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        # Create ~600 files to hit medium scale
        for i in range(600):
            (repo / f"file{i}.py").write_text('x = 1\n')
        info = estimate_scale(repo, "python")
        assert info["scale"] == "medium"
        assert info["max_files"] <= 2000

    def test_large_project(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        for i in range(3500):
            (repo / f"file{i}.go").write_text('package main\n')
        info = estimate_scale(repo, "go")
        assert info["scale"] == "large"
        assert info["max_files"] <= 5000

    def test_unknown_language_defaults_to_go(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "x.ts").write_text('// ts\n')
        info = estimate_scale(repo, "typescript")
        assert isinstance(info, dict)
        assert "scale" in info


class TestGetRelevantModules:
    """Test _get_relevant_modules with different project characteristics."""

    def test_default_modules(self):
        det = {"language": "go", "architecture": "monolith", "framework": "gin"}
        modules = _get_relevant_modules(det)
        assert "base_engine" in modules
        assert "go_flow_analyzer" in modules
        assert "cross_repo_flow" not in modules

    def test_microservice_adds_modules(self):
        det = {"language": "go", "architecture": "microservice", "framework": "gin"}
        modules = _get_relevant_modules(det)
        assert "cross_repo_flow" in modules
        assert "mermaid_generator" in modules

    def test_spex_framework_adds_module(self):
        det = {"language": "go", "architecture": "monolith", "framework": "spex"}
        modules = _get_relevant_modules(det)
        assert "go_flow_analyzer" in modules
        assert modules.count("go_flow_analyzer") == 2  # default + spex


class TestGenerateProfile:
    """Test generate_profile with various detection results."""

    def test_basic_profile(self):
        det = {
            "project_path": "/tmp/test",
            "language": "go",
            "framework": "gin",
            "architecture": "monolith",
            "scale": "small",
            "total_files": 100,
            "max_files": 500,
            "analysis_depth": "balanced",
            "entry_points": ["main.go"],
        }
        profile = generate_profile(det)
        assert profile["business_domain"] == "go"
        assert len(profile["repositories"]) == 1
        assert profile["repositories"][0]["path"] == "/tmp/test"
        assert "analysis_modules" in profile

    def test_profile_with_microservice(self):
        det = {
            "project_path": "/tmp/ms",
            "language": "go",
            "framework": "spex",
            "architecture": "microservice",
            "scale": "large",
            "total_files": 5000,
            "max_files": 5000,
            "analysis_depth": "full",
            "entry_points": [],
        }
        profile = generate_profile(det)
        assert profile["business_domain"] == "go"
        assert "cross_repo_flow" in profile["analysis_modules"]


class TestFindEntryPoints:
    """Test find_entry_points edge cases."""

    def test_no_entry_points(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "lib.go").write_text('package lib\n')
        entries = find_entry_points(repo, "go")
        assert entries == []

    def test_main_go_detected(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.go").write_text('package main\n')
        entries = find_entry_points(repo, "go")
        assert any("main.go" in e for e in entries)


class TestMainBlockJSON:
    """Test the CLI main block JSON output path."""

    def test_main_json_mode(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.go").write_text('package main\nfunc main() {}\n')
        result = subprocess.run(
            [sys.executable, "-m", "scripts.project_auto_detector",
             "--path", str(repo), "--json"],
            capture_output=True, text=True,
            cwd="/Users/yanping.ma/biz-delivery"
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "language" in data
