"""Tests for package_registry — registry building, loading, and querying."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scripts.package_registry import PackageRegistry, PackageInfo


# ===========================================================================
# PackageInfo
# ===========================================================================

class TestPackageInfo:
    def test_basic(self):
        info = PackageInfo(name="github.com/user/pkg")
        assert info.name == "github.com/user/pkg"
        assert info.files == []
        assert info.file_count == 0
        assert info.imports == set()
        assert info.structs == {}
        assert info.methods == {}
        assert info.routes == []
        assert info.funcs == {}

    def test_to_dict(self):
        info = PackageInfo(
            name="github.com/user/pkg",
            files=["a.go", "b.go"],
            file_count=2,
            imports={"fmt", "time"},
            structs={"User": {"file": "a.go", "fields": ["ID", "Name"]}},
            methods={"GetUser": {"file": "a.go", "sig": "func (*User) GetUser()"}},
            routes=[{"method": "GET", "path": "/api/users"}],
            funcs={"ListUsers": {"file": "a.go", "sig": "func ListUsers()"}},
        )
        d = info.to_dict()
        assert d["name"] == "github.com/user/pkg"
        assert d["file_count"] == 2
        assert d["files"] == ["a.go", "b.go"]
        assert sorted(d["imports"]) == ["fmt", "time"]
        assert d["structs"]["User"]["fields"] == ["ID", "Name"]
        assert d["methods"]["GetUser"]["sig"] == "func (*User) GetUser()"
        assert d["routes"] == [{"method": "GET", "path": "/api/users"}]
        assert d["funcs"]["ListUsers"]["sig"] == "func ListUsers()"

    def test_to_dict_truncates(self):
        info = PackageInfo(name="pkg")
        # Fill with more than limits
        info.files = [f"f{i}.go" for i in range(30)]
        info.imports = set(f"imp{i}" for i in range(40))
        info.structs = {f"S{i}": {"file": "f.go", "fields": ["a", "b"]} for i in range(40)}
        info.methods = {f"M{i}": {"file": "f.go", "sig": "sig"} for i in range(40)}
        info.funcs = {f"F{i}": {"file": "f.go", "sig": "sig"} for i in range(40)}
        d = info.to_dict()
        assert len(d["files"]) <= 20
        assert len(d["imports"]) <= 30
        assert len(d["structs"]) <= 30
        assert len(d["methods"]) <= 30
        assert len(d["funcs"]) <= 30


# ===========================================================================
# PackageRegistry — initialization
# ===========================================================================

class TestRegistryInit:
    def test_init_defaults(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        reg = PackageRegistry(str(repo), "go")
        assert reg.repo_path == repo
        assert reg.language == "go"
        assert reg.packages == {}
        assert reg._loaded is False
        expected_cache = repo.parent / ".biz_delivery_cache" / "package_registry.json"
        assert reg.registry_path == expected_cache

    def test_init_python(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        reg = PackageRegistry(str(repo), "python")
        assert reg.language == "python"


# ===========================================================================
# PackageRegistry — load / save
# ===========================================================================

class TestRegistryLoadSave:
    def test_load_not_fresh(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        reg = PackageRegistry(str(repo), "go")
        # No cache file → not fresh
        assert reg.load() is False

    def test_load_success(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        cache_dir = repo.parent / ".biz_delivery_cache"
        cache_dir.mkdir()
        data = {
            "packages": {
                "github.com/user/pkg": {
                    "name": "github.com/user/pkg",
                    "file_count": 2,
                    "files": ["main.go"],
                    "imports": ["fmt"],
                    "structs": {"User": {"file": "main.go", "fields": ["ID"]}},
                    "methods": {"GetUser": {"file": "main.go", "sig": "func (*User) GetUser()"}},
                    "routes": [],
                    "funcs": {},
                }
            },
            "build_time": 1234567890,
            "package_count": 1,
        }
        cache_file = cache_dir / "package_registry.json"
        cache_file.write_text(json.dumps(data))

        reg = PackageRegistry(str(repo), "go")
        # Mock _is_fresh to return True
        with patch.object(reg, '_is_fresh', return_value=True):
            result = reg.load()
        assert result is True
        assert reg._loaded is True
        assert len(reg.packages) == 1
        pkg = reg.packages["github.com/user/pkg"]
        assert isinstance(pkg, PackageInfo)
        assert pkg.structs["User"]["fields"] == ["ID"]
        assert "fmt" in pkg.imports

    def test_load_corrupt_file(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        cache_dir = repo.parent / ".biz_delivery_cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "package_registry.json"
        cache_file.write_text("not valid json {{{")

        reg = PackageRegistry(str(repo), "go")
        with patch.object(reg, '_is_fresh', return_value=True):
            assert reg.load() is False

    def test_load_already_loaded(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        reg = PackageRegistry(str(repo), "go")
        reg._loaded = True
        assert reg.load() is True

    def test_save_and_load_roundtrip (self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        reg = PackageRegistry(str(repo), "go")
        reg.packages["github.com/user/pkg"] = PackageInfo(
            name="github.com/user/pkg",
            files=["main.go"],
            imports={"fmt"},
            structs={"User": {"file": "main.go", "fields": ["ID"]}},
        )
        reg._save()

        # Reload
        reg2 = PackageRegistry(str(repo), "go")
        with patch.object(reg2, '_is_fresh', return_value=True):
            assert reg2.load() is True
        assert "github.com/user/pkg" in reg2.packages
        assert "User" in reg2.packages["github.com/user/pkg"].structs


# ===========================================================================
# PackageRegistry — build helpers
# ===========================================================================

class TestRegistryBuild:
    def test_get_packages_fallback(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        # Create some Go files
        sub = repo / "pkg1"
        sub.mkdir()
        (sub / "a.go").write_text("package pkg1\n")
        (sub / "b_test.go").write_text("package pkg1\n")
        (repo / "main.go").write_text("package main\n")

        reg = PackageRegistry(str(repo), "go")
        pkgs = reg._get_packages_fallback()
        assert "pkg1" in pkgs
        assert "." in pkgs or "" in pkgs  # root package

    def test_pkg_path_to_name(self):
        name = PackageRegistry._pkg_path_to_name("some/deep/path")
        assert name is not None

    def test_find_relevant_packages_empty(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        reg = PackageRegistry(str(repo), "go")
        result = reg.find_relevant_packages(["user", "order"])
        assert result == []

    def test_find_relevant_packages_scored(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        reg = PackageRegistry(str(repo), "go")
        reg.packages["github.com/user/service"] = PackageInfo(
            name="github.com/user/service",
            structs={"UserService": {"file": "s.go", "fields": []}},
            methods={"CreateUser": {"file": "s.go", "sig": "func ()"}},
        )
        result = reg.find_relevant_packages(["user"])
        assert "github.com/user/service" in result

    def test_get_package_files(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        reg = PackageRegistry(str(repo), "go")
        reg.packages["github.com/user/pkg"] = PackageInfo(
            name="github.com/user/pkg", files=["a.go", "b.go"]
        )
        assert reg.get_package_files("github.com/user/pkg") == ["a.go", "b.go"]
        assert reg.get_package_files("unknown") == []

    def test_get_transitive_deps(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        reg = PackageRegistry(str(repo), "go")
        reg.packages["github.com/user/a"] = PackageInfo(
            name="github.com/user/a", imports={"github.com/user/b"}
        )
        reg.packages["github.com/user/b"] = PackageInfo(
            name="github.com/user/b", imports=set()
        )
        deps = reg.get_transitive_deps("github.com/user/a", depth=2)
        assert "github.com/user/b" in deps

    def test_get_transitive_deps_empty(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        reg = PackageRegistry(str(repo), "go")
        deps = reg.get_transitive_deps("nonexistent")
        assert deps == set()

    def test_get_freshness_no_cache(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        reg = PackageRegistry(str(repo), "go")
        assert reg.get_freshness() == float('inf')

    def test_get_freshness_with_cache(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        cache_dir = repo.parent / ".biz_delivery_cache"
        cache_dir.mkdir()
        (cache_dir / "package_registry.json").write_text("{}")

        reg = PackageRegistry(str(repo), "go")
        freshness = reg.get_freshness()
        assert isinstance(freshness, float)
        assert freshness < 1.0  # just created, should be fresh
