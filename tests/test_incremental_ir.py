"""Tests for scripts/review/incremental_ir.py"""
import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.review.incremental_ir import FileTracker, IncrementalIRUpdater, IRCacheManager


# ===========================================================================
# FileTracker
# ===========================================================================

class TestFileTracker:
    def test_init(self):
        ft = FileTracker()
        assert ft.file_states == {}

    def test_get_file_hash_new_file(self, tmp_path):
        ft = FileTracker()
        f = tmp_path / "test.go"
        f.write_text("package main")
        h = ft.get_file_hash(str(f))
        assert h and len(h) == 32  # md5 hex

    def test_get_file_hash_missing(self):
        ft = FileTracker()
        assert ft.get_file_hash("/nonexistent/path.go") == ""

    def test_get_file_mtime(self, tmp_path):
        ft = FileTracker()
        f = tmp_path / "test.go"
        f.write_text("package main")
        mtime = ft.get_file_mtime(str(f))
        assert mtime > 0

    def test_get_file_mtime_missing(self):
        ft = FileTracker()
        assert ft.get_file_mtime("/nonexistent/path.go") == 0.0

    def test_save_load_cache(self, tmp_path):
        ft = FileTracker()
        cache = tmp_path / "states.json"
        ft.file_states = {
            "a.go": {"hash": "abc", "mtime": 1000.0, "size": 100},
            "b.go": {"hash": "def", "mtime": 2000.0, "size": 200},
        }
        ft.save_to_cache(str(cache))
        ft2 = FileTracker()
        ft2.load_from_cache(str(cache))
        assert "a.go" in ft2.file_states
        assert ft2.file_states["a.go"]["hash"] == "abc"

    def test_load_cache_missing_file(self):
        ft = FileTracker()
        ft.load_from_cache("/tmp/nonexistent_cache_12345.json")
        assert ft.file_states == {}

    def test_update_state(self, tmp_path):
        ft = FileTracker()
        f = tmp_path / "test.go"
        f.write_text("package main")
        ft.update_state(str(f))
        assert str(f) in ft.file_states
        assert ft.file_states[str(f)]["hash"]
        assert ft.file_states[str(f)]["mtime"] > 0

    def test_update_state_with_forced_values(self, tmp_path):
        ft = FileTracker()
        f = tmp_path / "test.go"
        f.write_text("package main")
        ft.update_state(str(f), hash_value="forced_hash", mtime=9999.0)
        assert ft.file_states[str(f)]["hash"] == "forced_hash"
        assert ft.file_states[str(f)]["mtime"] == 9999.0

    def test_check_changes_added(self, tmp_path):
        ft = FileTracker()
        f1 = tmp_path / "a.go"
        f1.write_text("package main")
        changes = ft.check_changes([str(f1)])
        assert changes[str(f1)] == "added"

    def test_check_changes_unchanged(self, tmp_path):
        ft = FileTracker()
        f1 = tmp_path / "a.go"
        f1.write_text("package main")
        ft.update_state(str(f1))
        changes = ft.check_changes([str(f1)])
        assert changes[str(f1)] == "unchanged"

    def test_check_changes_modified(self, tmp_path):
        ft = FileTracker()
        f1 = tmp_path / "a.go"
        f1.write_text("package main")
        ft.update_state(str(f1))
        time.sleep(0.01)
        f1.write_text("package main // modified")
        changes = ft.check_changes([str(f1)])
        assert changes[str(f1)] == "modified"

    def test_check_changes_deleted(self, tmp_path):
        ft = FileTracker()
        f1 = tmp_path / "a.go"
        f1.write_text("package main")
        ft.update_state(str(f1))
        f1.unlink()
        changes = ft.check_changes([])
        assert changes[str(f1)] == "deleted"

    def test_check_changes_mixed(self, tmp_path):
        ft = FileTracker()
        f1 = tmp_path / "a.go"
        f2 = tmp_path / "b.go"
        f1.write_text("package main")
        f2.write_text("package main")
        ft.update_state(str(f1))
        ft.update_state(str(f2))
        f2.unlink()
        changes = ft.check_changes([str(f1)])
        assert changes[str(f1)] == "unchanged"
        assert changes[str(f2)] == "deleted"


# ===========================================================================
# IncrementalIRUpdater
# ===========================================================================

class TestIncrementalIRUpdater:
    def test_init(self):
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        assert isinstance(updater.file_tracker, FileTracker)

    def test_collect_source_files_go(self, tmp_path):
        (tmp_path / "a.go").write_text("package main\n")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.go").write_text("package sub\n")
        (tmp_path / "readme.md").write_text("readme")
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        files = updater._collect_source_files(tmp_path, {"language": "go"})
        assert len(files) >= 2

    def test_collect_source_files_python(self, tmp_path):
        (tmp_path / "a.py").write_text("def foo(): pass\n")
        (tmp_path / "a.go").write_text("package main\n")
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        files = updater._collect_source_files(tmp_path, {"language": "python"})
        py_files = [f for f in files if f.endswith(".py")]
        assert len(py_files) >= 1

    def test_collect_source_files_default(self, tmp_path):
        (tmp_path / "a.go").write_text("package main\n")
        (tmp_path / "b.py").write_text("x=1\n")
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        # Default language is "go", so only .go files are collected
        files = updater._collect_source_files(tmp_path, None)
        assert len(files) >= 1

    def test_merge_ir_add_new_function(self):
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        old_ir = {"functions": [], "structs": [], "routes": []}
        new_ir = {
            "functions": [{"name": "Foo", "file": "a.go"}],
            "structs": [], "routes": [],
        }
        changes = {"a.go": "added"}
        merged = updater._merge_ir(old_ir, new_ir, changes)
        assert len(merged["functions"]) == 1
        assert merged["functions"][0]["name"] == "Foo"

    def test_merge_ir_update_existing_function(self):
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        old_ir = {
            "functions": [{"name": "Foo", "file": "a.go", "impl": "old"}],
            "structs": [], "routes": [],
        }
        new_ir = {
            "functions": [{"name": "Foo", "file": "a.go", "impl": "new"}],
            "structs": [], "routes": [],
        }
        changes = {"a.go": "modified"}
        merged = updater._merge_ir(old_ir, new_ir, changes)
        assert merged["functions"][0]["impl"] == "new"

    def test_merge_ir_skip_unchanged(self):
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        old_ir = {
            "functions": [{"name": "Foo", "file": "a.go"}],
            "structs": [], "routes": [],
        }
        new_ir = {
            "functions": [{"name": "Foo", "file": "a.go", "impl": "different"}],
            "structs": [], "routes": [],
        }
        changes = {"a.go": "unchanged"}
        merged = updater._merge_ir(old_ir, new_ir, changes)
        # Should keep old version since file is unchanged
        assert merged["functions"][0].get("impl") != "different"

    def test_merge_ir_add_new_struct(self):
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        old_ir = {"functions": [], "structs": [], "routes": []}
        new_ir = {
            "functions": [],
            "structs": [{"name": "User", "file": "user.go"}],
            "routes": [],
        }
        changes = {"user.go": "added"}
        merged = updater._merge_ir(old_ir, new_ir, changes)
        assert len(merged["structs"]) == 1
        assert merged["structs"][0]["name"] == "User"

    def test_merge_ir_add_new_route(self):
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        old_ir = {"functions": [], "structs": [], "routes": []}
        new_ir = {
            "functions": [], "structs": [],
            "routes": [{"path": "/users", "method": "GET", "file": "routes.go"}],
        }
        changes = {"routes.go": "added"}
        merged = updater._merge_ir(old_ir, new_ir, changes)
        assert len(merged["routes"]) == 1
        assert merged["routes"][0]["path"] == "/users"

    def test_merge_ir_remove_deleted_file(self):
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        old_ir = {
            "functions": [
                {"name": "A", "file": "keep.go"},
                {"name": "B", "file": "removed.go"},
            ],
            "structs": [{"name": "X", "file": "removed.go"}],
            "routes": [{"path": "/del", "file": "removed.go"}],
        }
        new_ir = {"functions": [], "structs": [], "routes": []}
        changes = {"removed.go": "deleted"}
        merged = updater._merge_ir(old_ir, new_ir, changes)
        assert all(f["file"] != "removed.go" for f in merged["functions"])
        assert all(s.get("file") != "removed.go" for s in merged["structs"])
        assert all(r.get("file") != "removed.go" for r in merged["routes"])

    def test_merge_ir_empty_old(self):
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        new_ir = {
            "functions": [{"name": "NewFunc"}],
            "structs": [], "routes": [],
        }
        merged = updater._merge_ir({}, new_ir, {})
        assert merged["functions"][0]["name"] == "NewFunc"

    def test_remove_from_ir(self):
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        ir = {
            "functions": [{"name": "A", "file": "x.go"}, {"name": "B", "file": "y.go"}],
            "structs": [{"name": "S", "file": "x.go"}],
            "routes": [{"path": "/r", "file": "x.go"}],
        }
        result = updater._remove_from_ir(ir, "x.go")
        assert len(result["functions"]) == 1
        assert result["functions"][0]["name"] == "B"
        assert result["structs"] == []
        assert result["routes"] == []

    def test_force_full_rebuild(self, tmp_path):
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        (tmp_path / "a.go").write_text("package main\n")
        def scan_func(files):
            return {"functions": [{"name": "Main", "file": str(tmp_path / "a.go")}]}
        result = updater.force_full_rebuild(str(tmp_path), scan_func)
        assert "functions" in result
        assert len(result["functions"]) == 1

    def test_run_update_all_unchanged(self, tmp_path):
        """All files unchanged — update returns existing IR unchanged."""
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        f = tmp_path / "a.go"
        f.write_text("package main\n")
        # Pre-populate tracker state so check_changes sees them as known
        updater.file_tracker.update_state(str(f))
        old_ir = {"functions": [{"name": "Main"}], "structs": [], "routes": []}
        def scan_func(files):
            return {"functions": [], "structs": [], "routes": []}
        result = updater.update(old_ir, str(tmp_path), scan_func, profile={"language": "go"})
        # Since files are unchanged, should return existing_ir unchanged
        assert result is old_ir or (hasattr(result, 'functions') and result['functions'][0]['name'] == 'Main')

    def test_run_update_with_changes(self, tmp_path):
        """Some files changed — should re-scan and merge."""
        updater = IncrementalIRUpdater(cache_dir=".test_cache_unit")
        f = tmp_path / "a.go"
        f.write_text("package main\n")
        updater.file_tracker.update_state(str(f))
        # Modify the file
        time.sleep(0.01)
        f.write_text("package main // modified\n")
        old_ir = {"functions": [], "structs": [], "routes": []}
        def scan_func(files):
            return {"functions": [{"name": "ModifiedFunc", "file": str(f)}], "structs": [], "routes": []}
        result = updater.update(old_ir, str(tmp_path), scan_func, profile={"language": "go"})
        assert "functions" in result


# ===========================================================================
# IRCacheManager
# ===========================================================================

class TestIRCacheManager:
    def test_init_creates_dir(self, tmp_path):
        mgr = IRCacheManager(cache_dir=str(tmp_path / "cache"))
        assert (tmp_path / "cache").exists()

    def test_get_cache_path(self, tmp_path):
        mgr = IRCacheManager(cache_dir=str(tmp_path / "cache"))
        p = mgr.get_cache_path("my-repo")
        assert "my-repo_ir.json" in p

    def test_get_file_states_path(self, tmp_path):
        mgr = IRCacheManager(cache_dir=str(tmp_path / "cache"))
        p = mgr.get_file_states_path("my-repo")
        assert "my-repo_file_states.json" in p

    def test_save_and_load_ir(self, tmp_path):
        mgr = IRCacheManager(cache_dir=str(tmp_path / "cache"))
        ir_data = {"repo_name": "test", "functions": [{"name": "Foo"}]}
        mgr.save_ir("test-repo", ir_data)
        loaded = mgr.load_ir("test-repo")
        assert loaded is not None
        assert loaded["functions"][0]["name"] == "Foo"

    def test_load_ir_missing(self, tmp_path):
        mgr = IRCacheManager(cache_dir=str(tmp_path / "cache"))
        assert mgr.load_ir("nonexistent") is None

    def test_invalidate(self, tmp_path):
        mgr = IRCacheManager(cache_dir=str(tmp_path / "cache"))
        mgr.save_ir("my-repo", {"functions": []})
        mgr.invalidate("my-repo")
        assert mgr.load_ir("my-repo") is None
        # Both cache files removed
        assert not (tmp_path / "cache" / "my-repo_ir.json").exists()
        assert not (tmp_path / "cache" / "my-repo_file_states.json").exists()

    def test_invalidate_nonexistent(self, tmp_path):
        mgr = IRCacheManager(cache_dir=str(tmp_path / "cache"))
        # Should not raise
        mgr.invalidate("nonexistent")


# ===========================================================================
# Public API functions
# ===========================================================================

class TestPublicAPI:
    def test_get_incremental_updater(self):
        from scripts.review.incremental_ir import get_incremental_updater
        updater = get_incremental_updater(cache_dir=".test_cache_api")
        assert isinstance(updater, IncrementalIRUpdater)

    def test_get_cache_manager(self):
        from scripts.review.incremental_ir import get_cache_manager
        mgr = get_cache_manager("my-repo", cache_dir=".test_cache_api")
        assert isinstance(mgr, IRCacheManager)
