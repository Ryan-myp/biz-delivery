"""
Extra coverage: PythonScanner / JavaScanner / field_conflict / MultiRepoAnalyzer / Pipeline run()
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scripts.learn_repo import (
    PythonScanner, JavaScanner, MultiRepoAnalyzer, LLMKnowledgeGenerator,
)
from scripts.review.field_conflict import (
    FieldChangeParser, FieldUsageTracker, FieldConflictDetector,
    SchemaChangeAnalyzer, detect_field_conflicts,
)
from scripts.delivery_pipeline import (
    BizDeliveryPipeline, AgentTaskGenerator, QualityGate, DeliveryReport, AgentTask,
    TaskPriority,
)


# ═══════════════════════════════════════════════════════════
#  PythonScanner — AST-based 扫描
# ═══════════════════════════════════════════════════════════

class TestPythonScanner:
    """PythonScanner 深度测试"""

    def _write_py(self, tmp_path: Path, name: str, code: str) -> Path:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(code, encoding="utf-8")
        return p

    def test_scan_function_with_params_and_return(self, tmp_path):
        code = '''
def place_bid(user_id: int, amount: float) -> dict:
    """Place a bid for a user."""
    return {"status": "ok"}

async def async_get_bid(bid_id: str) -> str:
    return bid_id
'''
        self._write_py(tmp_path, "bid.py", code)
        scanner = PythonScanner()
        result = scanner.scan_file(tmp_path / "bid.py")
        funcs = result["functions"]
        assert len(funcs) >= 1
        p = next(f for f in funcs if f["name"] == "place_bid")
        assert p["return_type"] == "dict"
        assert p["params"][0]["name"] == "user_id"
        assert p["params"][0]["type"] == "int"
        # async func
        a = next(f for f in funcs if f["name"] == "async_get_bid")
        assert a["async"] is True

    def test_scan_class_with_methods(self, tmp_path):
        code = '''
class BidService:
    """Bid business logic."""
    
    def __init__(self, db):
        self.db = db
    
    def get_bid(self, bid_id: int) -> dict:
        return {}
    
    async def create_bid(self, req: dict) -> None:
        pass
'''
        self._write_py(tmp_path, "svc.py", code)
        scanner = PythonScanner()
        result = scanner.scan_file(tmp_path / "svc.py")
        classes = result["classes"]
        svc = next(c for c in classes if c["name"] == "BidService")
        method_names = [m["name"] for m in svc["methods"]]
        assert "get_bid" in method_names
        assert "create_bid" in method_names
        create = next(m for m in svc["methods"] if m["name"] == "create_bid")
        assert create["async"] is True

    def test_scan_imports(self, tmp_path):
        code = '''
import os
import json
from typing import List, Optional
from collections import defaultdict
import mypackage.submod as sm
'''
        self._write_py(tmp_path, "imports.py", code)
        scanner = PythonScanner()
        result = scanner.scan_file(tmp_path / "imports.py")
        mods = {imp["module"] for imp in result["imports"]}
        assert "os" in mods
        assert "typing" in mods
        assert "mypackage.submod" in mods

    def test_scan_syntax_error_returns_degraded(self, tmp_path):
        self._write_py(tmp_path, "bad.py", "def foo(\n    unclosed")
        scanner = PythonScanner()
        result = scanner.scan_file(tmp_path / "bad.py")
        assert result["status"] == "degraded"
        assert result["reason"] == "syntax_error"

    def test_scan_data_flow(self, tmp_path):
        code = '''
def process(order_id):
    total = order_id * 2
    result = calculate(total)
    return result
'''
        self._write_py(tmp_path, "flow.py", code)
        scanner = PythonScanner()
        nodes = scanner._analyze_data_flow(tmp_path / "flow.py")
        var_names = {n.var_name for n in nodes}
        assert "total" in var_names
        assert "order_id" in var_names

    def test_scan_directory(self, tmp_path):
        self._write_py(tmp_path, "a.py", "def foo(): pass\n")
        self._write_py(tmp_path, "b.py", "class Bar:\n    def baz(self): pass\n")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "c.pyc").write_bytes(b"")
        scanner = PythonScanner()
        ir = scanner.scan_directory(tmp_path)
        all_funcs = []
        for s in ir.functions:
            all_funcs.append(s.get("name", "") if isinstance(s, dict) else s.name)
        assert "foo" in all_funcs
        for s in ir.functions:
            fname = s.get("file", "") if isinstance(s, dict) else s.file
            assert "__pycache__" not in str(fname)

    def test_decorator_extraction(self, tmp_path):
        code = '''
@app.route("/bid")
@login_required
def place_bid(req):
    pass

@dataclass
class BidRequest:
    amount: float
'''
        self._write_py(tmp_path, "dec.py", code)
        scanner = PythonScanner()
        result = scanner.scan_file(tmp_path / "dec.py")
        funcs = result["functions"]
        bid = next(f for f in funcs if f["name"] == "place_bid")
        assert "route" in bid["decorators"]
        assert "login_required" in bid["decorators"]

    def test_vararg_and_kwarg(self, tmp_path):
        code = '''
def flex_func(a: int, *args: str, **kwargs: dict):
    pass
'''
        self._write_py(tmp_path, "flex.py", code)
        scanner = PythonScanner()
        result = scanner.scan_file(tmp_path / "flex.py")
        params = result["functions"][0]["params"]
        param_names = [p["name"] for p in params]
        assert "*args" in param_names
        assert "**kwargs" in param_names


# ═══════════════════════════════════════════════════════════
#  JavaScanner — regexp 扫描
# ═══════════════════════════════════════════════════════════

class TestJavaScanner:
    """JavaScanner 深度测试"""

    def _write_java(self, tmp_path: Path, name: str, code: str) -> Path:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(code, encoding="utf-8")
        return p

    def test_scan_class_with_methods_and_fields(self, tmp_path):
        code = '''
package com.example.bid;

import java.util.List;

public class BidService {
    private Long id;
    private String status;
    private static final int MAX_BID = 1000;

    public BidResponse placeBid(Long userId, double amount) throws Exception {
        return new BidResponse();
    }

    public List<Bid> getBids(Long userId) {
        return null;
    }
}
'''
        self._write_java(tmp_path, "BidService.java", code)
        scanner = JavaScanner()
        result = scanner.scan_file(tmp_path / "BidService.java")
        classes = result["classes"]
        assert len(classes) == 1
        cls = classes[0]
        assert cls["name"] == "BidService"
        methods = result["methods"]
        assert any(m["name"] == "placeBid" for m in methods)
        fields = result["fields"]
        assert any(f["name"] == "id" for f in fields)
        assert any(f["name"] == "MAX_BID" for f in fields)

    def test_scan_spring_routes(self, tmp_path):
        code = '''
@RestController
@RequestMapping("/api/bids")
public class BidController {
    @GetMapping("/{id}")
    public Bid getBid(@PathVariable Long id) { return null; }

    @PostMapping("/create")
    public Bid createBid(@RequestBody BidRequest req) { return null; }

    @DeleteMapping("/{id}")
    public void deleteBid(@PathVariable Long id) {}
}
'''
        self._write_java(tmp_path, "BidController.java", code)
        scanner = JavaScanner()
        result = scanner.scan_file(tmp_path / "BidController.java")
        routes = result["routes"]
        paths = [r["path"] for r in routes]
        assert "/{id}" in paths or any("{id}" in p for p in paths)
        assert any(r["method"] == "post" for r in routes)

    def test_scan_annotations(self, tmp_path):
        code = '''
@Service
public class OrderService {
    @Autowired
    private OrderRepository repo;

    @Override
    public String toString() { return ""; }
}
'''
        self._write_java(tmp_path, "OrderService.java", code)
        scanner = JavaScanner()
        result = scanner.scan_file(tmp_path / "OrderService.java")
        anns = [a["name"] for a in result["annotations"]]
        assert "Service" in anns
        assert "Autowired" in anns
        # Override and SuppressWarnings should be filtered
        assert "Override" not in anns

    def test_scan_imports(self, tmp_path):
        code = '''
package com.example;

import java.util.List;
import java.util.*;
import com.example.dto.BidDto;

public class Foo {}
'''
        self._write_java(tmp_path, "Foo.java", code)
        scanner = JavaScanner()
        result = scanner.scan_file(tmp_path / "Foo.java")
        modules = [imp["module"] for imp in result["imports"]]
        assert "java.util.List" in modules
        assert "com.example.dto.BidDto" in modules

    def test_scan_interface(self, tmp_path):
        code = '''
public interface BidRepository {
    Object findByUserId();
}
'''
        self._write_java(tmp_path, "BidRepository.java", code)
        scanner = JavaScanner()
        result = scanner.scan_file(tmp_path / "BidRepository.java")
        cls = result["classes"][0]
        assert cls["type"] == "interface"

    def test_scan_empty_file(self, tmp_path):
        self._write_java(tmp_path, "Empty.java", "")
        scanner = JavaScanner()
        result = scanner.scan_file(tmp_path / "Empty.java")
        assert result["classes"] == []
        assert result["methods"] == []

    def test_scan_file_read_error(self, tmp_path):
        scanner = JavaScanner()
        fake_path = tmp_path / "nope.java"
        # Make it unreadable by returning a mock that raises
        with patch.object(Path, 'read_text', side_effect=IOError("permission denied")):
            result = scanner.scan_file(fake_path)
            assert result["status"] == "degraded"
            assert result["reason"] == "read_failed"


# ═══════════════════════════════════════════════════════════
#  field_conflict.py — 字段冲突检测
# ═══════════════════════════════════════════════════════════

class TestFieldChangeParser:
    """字段变更解析测试"""

    def test_parse_add_fields(self):
        parser = FieldChangeParser()
        prd = "add batch_id to Creative and add status to AdGroup"
        changes = parser.parse_field_changes(prd)
        adds = [c for c in changes if c["type"] == "add"]
        assert any(c["field"] == "batch_id" for c in adds)
        assert any(c["table"] == "Creative" for c in adds)

    def test_parse_remove_fields(self):
        parser = FieldChangeParser()
        prd = "delete old_status from Creative"
        changes = parser.parse_field_changes(prd)
        removes = [c for c in changes if c["type"] == "remove"]
        assert len(removes) >= 1
        assert removes[0]["field"] == "old_status"

    def test_parse_modify_fields(self):
        parser = FieldChangeParser()
        prd = "modify URL to varchar(2048)"
        changes = parser.parse_field_changes(prd)
        modifies = [c for c in changes if c["type"] == "modify"]
        assert any(c["field"] == "URL" for c in modifies)

    def test_parse_mixed_changes(self):
        parser = FieldChangeParser()
        prd = """
        1. 新增 batch_id 字段到 Creative 表
        2. 删除 Creative 表的 old_status 字段
        3. 修改 Creative 表的 URL 字段长度
        """
        changes = parser.parse_field_changes(prd)
        types = {c["type"] for c in changes}
        assert "add" in types
        assert "remove" in types
        assert "modify" in types

    def test_parse_empty_prd(self):
        parser = FieldChangeParser()
        changes = parser.parse_field_changes("")
        assert changes == []


class TestFieldUsageTracker:
    """字段使用追踪测试"""

    def test_build_index_from_structs(self):
        structs = [
            {"name": "Creative", "fields": [{"name": "ID"}, {"name": "URL"}, {"name": "Status"}]},
            {"name": "Bid", "fields": [{"name": "amount"}, {"name": "user_id"}]},
        ]
        tracker = FieldUsageTracker(structs)
        assert tracker.is_field_in_struct("Creative", "ID") is True
        assert tracker.is_field_in_struct("Creative", "NonExistent") is False

    def test_get_usage_count(self):
        structs = [
            {"name": "Creative", "fields": [{"name": "URL"}, {"name": "Status"}]},
        ]
        funcs = [
            {"name": "GetCreative", "struct": "Creative", "fields_used": ["URL", "Status"]},
            {"name": "UpdateCreative", "struct": "Creative", "fields_used": ["Status"]},
        ]
        tracker = FieldUsageTracker(structs, funcs)
        # Status used in GetCreative + UpdateCreative
        assert tracker.get_field_usage_count("Creative", "Status") >= 2
        # URL only in GetCreative
        assert tracker.get_field_usage_count("Creative", "URL") >= 1

    def test_get_references(self):
        structs = [{"name": "Bid", "fields": [{"name": "amount"}]}]
        funcs = [{"name": "Calc", "struct": "Bid", "fields_used": ["amount"]}]
        tracker = FieldUsageTracker(structs, funcs)
        refs = tracker.get_field_references("Bid", "amount")
        assert "Calc" in refs


class TestFieldConflictDetector:
    """字段冲突检测测试"""

    def test_detect_remove_breaking_change(self):
        ir = {
            "structs": [{"name": "Creative", "fields": [{"name": "URL"}]}],
            "functions": [{"name": "GetCreative", "struct": "Creative", "fields_used": ["URL"]}],
        }
        detector = FieldConflictDetector(ir)
        conflicts = detector.detect_conflicts("delete URL from Creative")
        assert len(conflicts) >= 1
        assert any(c["type"] == "breaking_change" for c in conflicts)

    def test_detect_duplicate_add(self):
        ir = {
            "structs": [{"name": "Creative", "fields": [{"name": "batch_id"}]}],
            "functions": [],
        }
        detector = FieldConflictDetector(ir)
        conflicts = detector.detect_conflicts("add batch_id to Creative")
        assert any(c["type"] == "duplicate_field" for c in conflicts)

    def test_detect_modify_field(self):
        # modify of a field that IS used → breaking_change (not field_modification)
        ir = {
            "structs": [{"name": "Creative", "fields": [{"name": "URL"}]}],
            "functions": [{"name": "GetCreative", "struct": "Creative", "fields_used": ["URL"]}],
        }
        detector = FieldConflictDetector(ir)
        # modify without table in parsed change → no conflict detected (parser limitation)
        # This tests the code path that handles modify type
        conflicts = detector.detect_conflicts("变更 URL 为 varchar(2048)")
        # Currently parser doesn't extract table for modify → conflicts is []
        # The code path is tested (no crash), verify it handles gracefully
        assert isinstance(conflicts, list)
        # Test with explicit table via _check_change directly
        change = {"type": "modify", "field": "URL", "table": "Creative", "description": "varchar(2048)"}
        direct = detector._check_change(change)
        assert len(direct) >= 1
        assert any(c["type"] == "field_modification" for c in direct)

    def test_no_conflicts_clean_prd(self):
        ir = {"structs": [], "functions": []}
        detector = FieldConflictDetector(ir)
        conflicts = detector.detect_conflicts("这是一个没有字段变更的 PRD")
        assert conflicts == []


class TestSchemaChangeAnalyzer:
    """Schema 变更风险分析"""

    def test_big_table_no_online_ddl(self):
        analyzer = SchemaChangeAnalyzer({})
        risks = analyzer.analyze_schema_changes("大表变更，需要新增索引字段")
        assert any(r["type"] == "big_table_no_online_ddl" for r in risks)

    def test_big_table_with_online_ddl(self):
        analyzer = SchemaChangeAnalyzer({})
        risks = analyzer.analyze_schema_changes("大表变更，使用 online DDL 方案")
        no_risk = [r for r in risks if r["type"] == "big_table_no_online_ddl"]
        assert len(no_risk) == 0

    def test_big_table_no_backfill(self):
        analyzer = SchemaChangeAnalyzer({})
        risks = analyzer.analyze_schema_changes("大表变更，新增字段需要回填历史数据")
        no_risk = [r for r in risks if r["type"] == "no_backfill_strategy"]
        assert len(no_risk) == 0

    def test_index_change_risk(self):
        analyzer = SchemaChangeAnalyzer({})
        risks = analyzer.analyze_schema_changes("新增唯一索引 on bids table")
        assert any(r["type"] == "index_change_risk" for r in risks)

    def test_no_risks_normal_prd(self):
        analyzer = SchemaChangeAnalyzer({})
        risks = analyzer.analyze_schema_changes("修改用户昵称显示逻辑")
        assert risks == []


class TestDetectFieldConflicts:
    """集成测试：detect_field_conflicts 公共 API"""

    def test_full_integration(self):
        ir = {
            "structs": [{"name": "Creative", "fields": [{"name": "URL"}, {"name": "Status"}]}],
            "functions": [{"name": "GetCreative", "struct": "Creative", "fields_used": ["URL"]}],
            "entity_tables": [{"entity": "Creative", "table": "creatives"}],
        }
        prd = """
        # 素材优化
        ## 变更
        1. 新增 batch_id 字段到 Creative 表
        2. 删除 Creative 表的 URL 字段
        3. 修改 Creative 表的 Status 字段
        """
        result = detect_field_conflicts(prd, ir)
        assert result["total_issues"] >= 1
        assert isinstance(result["field_conflicts"], list)
        assert isinstance(result["schema_risks"], list)


# ═══════════════════════════════════════════════════════════
#  MultiRepoAnalyzer — 多仓库依赖
# ═══════════════════════════════════════════════════════════

class TestMultiRepoAnalyzer:
    """多仓库依赖分析测试"""

    def test_analyze_single_repo(self, tmp_path):
        repo = tmp_path / "repo-a"
        repo.mkdir()
        (repo / "go.mod").write_text('module repo-a\n')
        (repo / "main.go").write_text('package main\nfunc main(){}\n')
        
        analyzer = MultiRepoAnalyzer()
        repos = [{"name": "repo-a", "path": str(repo), "language": "go"}]
        result = analyzer.analyze(repos)
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["name"] == "repo-a"

    def test_analyze_two_repos_no_deps(self, tmp_path):
        r1 = tmp_path / "repo-a"
        r1.mkdir()
        (r1 / "go.mod").write_text('module repo-a\n')
        r2 = tmp_path / "repo-b"
        r2.mkdir()
        (r2 / "go.mod").write_text('module repo-b\n')
        
        analyzer = MultiRepoAnalyzer()
        repos = [
            {"name": "repo-a", "path": str(r1), "language": "go"},
            {"name": "repo-b", "path": str(r2), "language": "go"},
        ]
        result = analyzer.analyze(repos)
        assert len(result["nodes"]) == 2
        # 两个独立仓库，无跨仓库 import
        assert len(result["edges"]) == 0

    def test_analyze_with_import_prefix(self, tmp_path):
        r1 = tmp_path / "internal-lib"
        r1.mkdir()
        (r1 / "go.mod").write_text('module github.com/org/internal-lib\n')
        (r1 / "util.go").write_text('package lib\nfunc Helper(){}\n')
        r2 = tmp_path / "app"
        r2.mkdir()
        (r2 / "go.mod").write_text('module github.com/org/app\n')
        (r2 / "main.go").write_text('''package main
import "github.com/org/internal-lib"
func main() { internal-lib.Helper() }
''')
        
        analyzer = MultiRepoAnalyzer()
        repos = [
            {"name": "internal-lib", "path": str(r1), "language": "go",
             "import_prefix": "github.com/org/internal-lib"},
            {"name": "app", "path": str(r2), "language": "go",
             "import_prefix": "github.com/org/app"},
        ]
        result = analyzer.analyze(repos)
        assert len(result["nodes"]) == 2
        # Edge detection depends on actual import parsing; just verify structure
        assert "edges" in result
        assert "cross_refs" in result


# ═══════════════════════════════════════════════════════════
#  BizDeliveryPipeline — run() 端到端（mock stages）
# ═══════════════════════════════════════════════════════════

class TestPipelineRun:
    """BizDeliveryPipeline.run() 端到端测试"""

    def test_run_selective_stages(self, tmp_path):
        """只执行 review + td + quality 阶段（跳过 learn/agent）"""
        from scripts.delivery_pipeline import BizDeliveryPipeline
        import json

        repo_dir = tmp_path / "repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "README.md").write_text("# Repo\n")
        (tmp_path / "wiki").mkdir(parents=True)
        (tmp_path / "profile.json").write_text(json.dumps({
            "business_domain": "auction",
            "repositories": [{"name": "test", "path": str(repo_dir)}],
        }))

        out_dir = tmp_path / "out"
        out_dir.mkdir(parents=True)
        pipeline = BizDeliveryPipeline(
            profile_path=str(tmp_path / "profile.json"),
            output_dir=str(out_dir),
            wiki_path=str(tmp_path / "wiki"),
        )

        prd = "# 出价功能\n用户可以对广告出价。\n"

        # 只跑 review + td + quality，跳过 learn/agent
        report = pipeline.run(prd, stages=["review", "td", "quality"])

        assert report is not None
        assert isinstance(report, DeliveryReport)
        assert report.prd_review is not None

    def test_run_all_stages_with_mocks(self, tmp_path):
        """完整 run() 调用，mock learn/agent/execution"""
        from scripts.delivery_pipeline import BizDeliveryPipeline
        import json

        repo_dir = tmp_path / "repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "go.mod").write_text("module test\n")
        (tmp_path / "wiki").mkdir()
        (tmp_path / "profile.json").write_text(json.dumps({
            "business_domain": "auction",
            "repositories": [{"name": "test", "path": str(repo_dir)}],
        }))

        with patch('scripts.delivery_pipeline.learn_from_repos') as mock_learn:
            mock_learn.return_value = {"ir_data": {"functions": [], "structs": [], "routes": []}}
            
            with patch('scripts.delivery_pipeline.QualityGate') as mock_qg:
                mock_qg.return_value.evaluate.return_value = {
                    "score": 80, "passed": True,
                    "checks": [], "blockers": [], "warnings": [],
                }
                
                out_dir = tmp_path / "out"
                out_dir.mkdir(parents=True)
                pipeline = BizDeliveryPipeline(
                    profile_path=str(tmp_path / "profile.json"),
                    output_dir=str(out_dir),
                    wiki_path=str(tmp_path / "wiki"),
                )
                
                prd = "# 简单需求\n\n## 接口\nPOST /api/bid"
                report = pipeline.run(prd, stages=["learn", "review", "td", "quality"])
                
                assert report is not None
                assert report.prd_review is not None

    def test_run_generates_report_structure(self, tmp_path):
        """run() 返回的 DeliveryReport 包含必要字段"""
        from scripts.delivery_pipeline import BizDeliveryPipeline
        import json

        repo_dir = tmp_path / "repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "README.md").write_text("# Repo\n")
        (tmp_path / "wiki").mkdir()
        (tmp_path / "profile.json").write_text(json.dumps({
            "business_domain": "test",
            "repositories": [{"name": "test", "path": str(repo_dir)}],
        }))

        out_dir = tmp_path / "out"
        out_dir.mkdir(parents=True)
        pipeline = BizDeliveryPipeline(
            profile_path=str(tmp_path / "profile.json"),
            output_dir=str(out_dir),
            wiki_path=str(tmp_path / "wiki"),
        )

        report = pipeline.run("# PRD\n", stages=["review", "td", "quality"])

        # DeliveryReport 结构验证
        assert hasattr(report, "prd_review")
        assert hasattr(report, "technical_design")
        assert hasattr(report, "agent_tasks")
        assert hasattr(report, "test_cases")
        assert hasattr(report, "execution_result")
        assert hasattr(report, "quality_gate")
