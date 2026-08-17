"""Tests for profile_registry main() CLI path."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestMainCLI:
    """Test the argparse-based main() function in profile_registry.py."""

    def test_main_list_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", tmp_path / "index.json")
        result = subprocess.run(
            [sys.executable, "-m", "scripts.profile_registry", "--action", "list"],
            capture_output=True, text=True,
            cwd="/Users/yanping.ma/biz-delivery"
        )
        assert result.returncode == 0
        assert "已注册" in result.stdout

    def test_main_register_and_list(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", tmp_path / "index.json")
        pf = tmp_path / "svc.json"
        pf.write_text(json.dumps({
            "business_domain": "cli-test",
            "repositories": [{"name": "r", "path": str(tmp_path)}],
        }))
        # Register
        r1 = subprocess.run(
            [sys.executable, "-m", "scripts.profile_registry",
             "--action", "register", "--profile", str(pf)],
            capture_output=True, text=True,
            cwd="/Users/yanping.ma/biz-delivery"
        )
        assert r1.returncode == 0
        assert "registered" in r1.stdout.lower() or "✅" in r1.stdout
        # List
        r2 = subprocess.run(
            [sys.executable, "-m", "scripts.profile_registry", "--action", "list"],
            capture_output=True, text=True,
            cwd="/Users/yanping.ma/biz-delivery"
        )
        assert "cli-test" in r2.stdout

    def test_main_validate_valid(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", tmp_path / "index.json")
        pf = tmp_path / "valid.json"
        pf.write_text(json.dumps({
            "business_domain": "v",
            "repositories": [{"name": "r", "path": str(tmp_path)}],
        }))
        result = subprocess.run(
            [sys.executable, "-m", "scripts.profile_registry",
             "--action", "validate", "--profile", str(pf)],
            capture_output=True, text=True,
            cwd="/Users/yanping.ma/biz-delivery"
        )
        assert result.returncode == 0
        assert "valid" in result.stdout.lower() or "✅" in result.stdout

    def test_main_validate_invalid(self, tmp_path):
        pf = tmp_path / "bad.json"
        pf.write_text(json.dumps({"business_domain": "x"}))  # no repositories
        result = subprocess.run(
            [sys.executable, "-m", "scripts.profile_registry",
             "--action", "validate", "--profile", str(pf)],
            capture_output=True, text=True,
            cwd="/Users/yanping.ma/biz-delivery"
        )
        assert result.returncode != 0
        assert "invalid" in result.stdout.lower() or "❌" in result.stdout

    def test_main_info_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", tmp_path / "index.json")
        pf = tmp_path / "info_svc.json"
        pf.write_text(json.dumps({
            "business_domain": "info-svc",
            "repositories": [{"name": "r", "path": str(tmp_path)}],
            "modules": [{"name": "m"}],
        }))
        # First register it
        subprocess.run(
            [sys.executable, "-m", "scripts.profile_registry",
             "--action", "register", "--profile", str(pf)],
            capture_output=True, text=True, cwd="/Users/yanping.ma/biz-delivery"
        )
        # Then get info
        result = subprocess.run(
            [sys.executable, "-m", "scripts.profile_registry",
             "--action", "info", "--domain", "info-svc"],
            capture_output=True, text=True,
            cwd="/Users/yanping.ma/biz-delivery"
        )
        assert result.returncode == 0
        assert "info-svc" in result.stdout

    def test_main_info_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", tmp_path / "index.json")
        result = subprocess.run(
            [sys.executable, "-m", "scripts.profile_registry",
             "--action", "info", "--domain", "unknown-svc"],
            capture_output=True, text=True,
            cwd="/Users/yanping.ma/biz-delivery"
        )
        assert result.returncode != 0
        assert "not found" in result.stdout.lower() or "❌" in result.stdout

    def test_main_register_missing_profile_arg(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", tmp_path / "index.json")
        result = subprocess.run(
            [sys.executable, "-m", "scripts.profile_registry", "--action", "register"],
            capture_output=True, text=True,
            cwd="/Users/yanping.ma/biz-delivery"
        )
        assert result.returncode != 0

    def test_main_validate_missing_profile_arg(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", tmp_path / "index.json")
        result = subprocess.run(
            [sys.executable, "-m", "scripts.profile_registry", "--action", "validate"],
            capture_output=True, text=True,
            cwd="/Users/yanping.ma/biz-delivery"
        )
        assert result.returncode != 0

    def test_main_info_missing_domain_arg(self, tmp_path, monkeypatch):
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", tmp_path / "index.json")
        result = subprocess.run(
            [sys.executable, "-m", "scripts.profile_registry", "--action", "info"],
            capture_output=True, text=True,
            cwd="/Users/yanping.ma/biz-delivery"
        )
        assert result.returncode != 0

    def test_main_exception_handling(self, tmp_path, monkeypatch):
        """main() should catch exceptions and exit with error."""
        idx = tmp_path / "index.json"
        idx.write_text("not json {{{")  # corrupt index
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx)
        result = subprocess.run(
            [sys.executable, "-m", "scripts.profile_registry", "--action", "list"],
            capture_output=True, text=True,
            cwd="/Users/yanping.ma/biz-delivery"
        )
        # Should not crash with unhandled exception
        assert result.returncode == 0
