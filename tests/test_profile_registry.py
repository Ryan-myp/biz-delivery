"""Tests for profile_registry — load/save index, register, validate, info."""
import json
import tempfile
from pathlib import Path

import pytest

from scripts.profile_registry import (
    load_index, save_index, list_profiles,
    register_profile, validate_profile, get_profile_info,
    _get_mtime, _now,
)


# ===========================================================================
# load_index / save_index
# ===========================================================================

class TestIndexIO:
    def test_load_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "scripts.profile_registry.INDEX_FILE",
            tmp_path / "index.json"
        )
        idx = load_index()
        assert idx == {"profiles": [], "last_updated": ""}

    def test_load_corrupt(self, tmp_path, monkeypatch):
        idx_file = tmp_path / "index.json"
        idx_file.write_text("not json {{{")
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx_file)
        idx = load_index()
        assert idx == {"profiles": [], "last_updated": ""}

    def test_save_and_load(self, tmp_path, monkeypatch):
        idx_file = tmp_path / "index.json"
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx_file)
        save_index({"profiles": [{"domain": "test"}], "last_updated": "now"})
        idx = load_index()
        assert idx["profiles"][0]["domain"] == "test"

    def test_list_profiles_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "scripts.profile_registry.INDEX_FILE",
            tmp_path / "index.json"
        )
        assert list_profiles() == []

    def test_list_profiles_with_entries(self, tmp_path, monkeypatch):
        idx_file = tmp_path / "index.json"
        idx_file.write_text(json.dumps({"profiles": [
            {"domain": "svc-a", "path": "/a.json"},
            {"domain": "svc-b", "path": "/b.json"},
        ]}))
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx_file)
        profiles = list_profiles()
        assert len(profiles) == 2
        assert profiles[0]["domain"] == "svc-a"


# ===========================================================================
# register_profile
# ===========================================================================

class TestRegisterProfile:
    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            register_profile(str(tmp_path / "missing.json"))

    def test_invalid_json(self, tmp_path):
        pf = tmp_path / "bad.json"
        pf.write_text("not json")
        with pytest.raises(ValueError):
            register_profile(str(pf))

    def test_missing_required_fields(self, tmp_path):
        pf = tmp_path / "no-domain.json"
        pf.write_text(json.dumps({"repositories": []}))
        with pytest.raises(ValueError):
            register_profile(str(pf))

    def test_valid_register(self, tmp_path, monkeypatch):
        idx_file = tmp_path / "index.json"
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx_file)
        pf = tmp_path / "svc.json"
        pf.write_text(json.dumps({
            "business_domain": "my-svc",
            "repositories": [{"name": "my-svc", "path": str(tmp_path)}],
        }))
        result = register_profile(str(pf))
        assert result["status"] == "registered"
        assert result["domain"] == "my-svc"
        # Verify in index
        idx = load_index()
        assert len(idx["profiles"]) == 1
        assert idx["profiles"][0]["domain"] == "my-svc"

    def test_register_update_existing(self, tmp_path, monkeypatch):
        idx_file = tmp_path / "index.json"
        idx_file.write_text(json.dumps({
            "profiles": [{"domain": "svc", "path": "/old.json"}],
        }))
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx_file)
        pf = tmp_path / "svc-new.json"
        pf.write_text(json.dumps({
            "business_domain": "svc",
            "repositories": [{"name": "svc", "path": str(tmp_path)}],
        }))
        result = register_profile(str(pf))
        assert result["status"] == "registered"
        idx = load_index()
        # Should update, not duplicate
        assert len(idx["profiles"]) == 1
        assert idx["profiles"][0]["path"] == str(pf)


# ===========================================================================
# validate_profile
# ===========================================================================

class TestValidateProfile:
    def test_file_not_found(self, tmp_path):
        result = validate_profile(str(tmp_path / "missing.json"))
        assert result["status"] == "error"

    def test_invalid_json(self, tmp_path):
        pf = tmp_path / "bad.json"
        pf.write_text("{bad")
        result = validate_profile(str(pf))
        assert result["status"] == "error"

    def test_missing_domain(self, tmp_path):
        pf = tmp_path / "no-domain.json"
        pf.write_text(json.dumps({"repositories": []}))
        result = validate_profile(str(pf))
        assert result["status"] == "invalid"
        assert any("business_domain" in e for e in result["errors"])

    def test_missing_repositories(self, tmp_path):
        pf = tmp_path / "no-repos.json"
        pf.write_text(json.dumps({"business_domain": "test"}))
        result = validate_profile(str(pf))
        assert result["status"] == "invalid"

    def test_repositories_not_list(self, tmp_path):
        pf = tmp_path / "bad-repos.json"
        pf.write_text(json.dumps({
            "business_domain": "test",
            "repositories": "not-a-list",
        }))
        result = validate_profile(str(pf))
        assert result["status"] == "invalid"

    def test_repo_missing_name(self, tmp_path):
        pf = tmp_path / "no-name.json"
        pf.write_text(json.dumps({
            "business_domain": "test",
            "repositories": [{"path": "/tmp"}],
        }))
        result = validate_profile(str(pf))
        assert result["status"] == "invalid"
        assert any("name" in e for e in result["errors"])

    def test_repo_missing_path(self, tmp_path):
        pf = tmp_path / "no-path.json"
        pf.write_text(json.dumps({
            "business_domain": "test",
            "repositories": [{"name": "r"}],
        }))
        result = validate_profile(str(pf))
        assert result["status"] == "invalid"
        assert any("path" in e for e in result["errors"])

    def test_repo_path_not_exists(self, tmp_path):
        pf = tmp_path / "bad-path.json"
        pf.write_text(json.dumps({
            "business_domain": "test",
            "repositories": [{"name": "r", "path": "/nonexistent/path"}],
        }))
        result = validate_profile(str(pf))
        assert result["status"] == "invalid"
        assert any("does not exist" in e for e in result["errors"])

    def test_valid(self, tmp_path):
        pf = tmp_path / "valid.json"
        pf.write_text(json.dumps({
            "business_domain": "test-svc",
            "repositories": [{"name": "r", "path": str(tmp_path)}],
            "modules": [{"name": "m"}],
        }))
        result = validate_profile(str(pf))
        assert result["status"] == "valid"
        assert result["domain"] == "test-svc"
        assert result["repositories"] == 1


# ===========================================================================
# get_profile_info
# ===========================================================================

class TestGetProfileInfo:
    def test_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "scripts.profile_registry.INDEX_FILE",
            tmp_path / "index.json"
        )
        result = get_profile_info("unknown")
        assert result is None

    def test_found(self, tmp_path, monkeypatch):
        idx_file = tmp_path / "index.json"
        idx_file.write_text(json.dumps({
            "profiles": [{"domain": "svc", "path": str(tmp_path / "svc.json")}]
        }))
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx_file)
        (tmp_path / "svc.json").write_text(json.dumps({
            "business_domain": "svc",
            "repositories": [],
            "modules": [{"name": "m"}],
            "state_machines": {},
        }))
        result = get_profile_info("svc")
        assert result is not None
        assert result["domain"] == "svc"
        assert result["modules"] == [{"name": "m"}]

    def test_path_not_exists(self, tmp_path, monkeypatch):
        idx_file = tmp_path / "index.json"
        idx_file.write_text(json.dumps({
            "profiles": [{"domain": "svc", "path": "/nonexistent.json"}]
        }))
        monkeypatch.setattr("scripts.profile_registry.INDEX_FILE", idx_file)
        result = get_profile_info("svc")
        assert result is None


# ===========================================================================
# Time helpers
# ===========================================================================

class TestTimeHelpers:
    def test_get_mtime(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        mtime = _get_mtime(f)
        assert isinstance(mtime, str)
        assert "-" in mtime  # YYYY-MM-DD format

    def test_now(self):
        now = _now()
        assert isinstance(now, str)
        assert "-" in now
