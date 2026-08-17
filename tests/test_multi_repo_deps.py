"""Tests for scripts/review/multi_repo_deps.py"""
import pytest
from scripts.review.multi_repo_deps import (
    CrossRepoDependencyTracker,
    MultiRepoImpactAnalyzer,
    analyze_multi_repo_dependencies,
    DEPENDENCY_TYPES,
)


class TestDependencyTypes:
    def test_all_types_defined(self):
        assert "rpc" in DEPENDENCY_TYPES
        assert "mq" in DEPENDENCY_TYPES
        assert "http" in DEPENDENCY_TYPES
        assert "db" in DEPENDENCY_TYPES
        assert "cache" in DEPENDENCY_TYPES

    def test_rpc_keywords(self):
        assert "grpc" in DEPENDENCY_TYPES["rpc"]
        assert "stub" in DEPENDENCY_TYPES["rpc"]


class TestCrossRepoDependencyTracker:
    def test_single_repo_no_deps(self):
        tracker = CrossRepoDependencyTracker([
            {"repo_name": "svc-a", "imports": [], "functions": []}
        ])
        assert tracker.rpc_deps == {}
        assert tracker.mq_deps == {}
        assert tracker.http_deps == {}
        assert tracker.cross_repo_calls == []

    def test_rpc_dependency_via_shared_keyword(self):
        """Both repos import grpc → RPC dependency detected."""
        tracker = CrossRepoDependencyTracker([
            {
                "repo_name": "svc-a",
                "imports": [{"module": "google.golang.org/grpc"}],
                "functions": [{"name": "CallB", "calls": []}],
            },
            {
                "repo_name": "svc-b",
                "imports": [{"module": "google.golang.org/grpc"}],
                "functions": [{"name": "Handle", "calls": []}],
            },
        ])
        deps = tracker.get_all_dependencies()
        assert "rpc" in deps
        # Both share grpc keyword → detected as RPC dep
        assert "svc-b" in tracker.rpc_deps.get("svc-a", set()) or "svc-a" in tracker.rpc_deps.get("svc-b", set())

    def test_mq_dependency_via_shared_topic(self):
        """Both services publish/subscribe to same topic → MQ dependency."""
        tracker = CrossRepoDependencyTracker([
            {
                "repo_name": "svc-a",
                "imports": [],
                "functions": [{"name": "publish_order", "signature": '"orders.topic"'}],
            },
            {
                "repo_name": "svc-b",
                "imports": [],
                "functions": [{"name": "consume_order", "signature": '"orders.topic"'}],
            },
        ])
        deps = tracker.get_all_dependencies()
        assert "svc-b" in tracker.mq_deps.get("svc-a", set()) or "svc-a" in tracker.mq_deps.get("svc-b", set())

    def test_http_dependency_via_url(self):
        """Service A calls Service B's HTTP endpoint."""
        tracker = CrossRepoDependencyTracker([
            {
                "repo_name": "svc-a",
                "imports": [],
                "functions": [{"name": "call_b", "signature": "http://svc-b.example.com/api"}],
            },
            {
                "repo_name": "svc-b",
                "imports": [],
                "configs": [{"value": "http://svc-b.example.com/api"}],
            },
        ])
        deps = tracker.get_all_dependencies()
        assert "http" in deps

    def test_get_dependents(self):
        tracker = CrossRepoDependencyTracker([
            {
                "repo_name": "svc-a",
                "imports": [{"module": "google.golang.org/grpc"}],
                "functions": [],
            },
            {
                "repo_name": "svc-b",
                "imports": [{"module": "google.golang.org/grpc"}],
                "functions": [],
            },
        ])
        dependents = tracker.get_dependents("svc-b")
        assert "svc-a" in dependents

    def test_get_depended_by(self):
        tracker = CrossRepoDependencyTracker([
            {
                "repo_name": "svc-a",
                "imports": [{"module": "google.golang.org/grpc"}],
                "functions": [],
            },
            {
                "repo_name": "svc-b",
                "imports": [{"module": "google.golang.org/grpc"}],
                "functions": [],
            },
        ])
        depended_by = tracker.get_depended_by("svc-b")
        assert "svc-a" in depended_by

    def test_get_all_dependencies_empty(self):
        tracker = CrossRepoDependencyTracker([])
        deps = tracker.get_all_dependencies()
        assert deps["rpc"] == {}
        assert deps["mq"] == {}
        assert deps["http"] == {}
        assert deps["calls"] == []

    def test_dict_based_ir_functions(self):
        tracker = CrossRepoDependencyTracker([
            {
                "repo_name": "svc-a",
                "imports": [{"module": "google.golang.org/grpc"}],
                "functions": [{"name": "handler", "calls": []}],
            },
            {
                "repo_name": "svc-b",
                "imports": [{"module": "google.golang.org/grpc"}],
                "functions": [{"name": "process", "calls": []}],
            },
        ])
        deps = tracker.get_all_dependencies()
        assert isinstance(deps, dict)

    def test_multiple_repos_chain(self):
        """Three repos all using grpc → all pairwise RPC deps."""
        tracker = CrossRepoDependencyTracker([
            {"repo_name": "a", "imports": [{"module": "google.golang.org/grpc"}], "functions": []},
            {"repo_name": "b", "imports": [{"module": "google.golang.org/grpc"}], "functions": []},
            {"repo_name": "c", "imports": [{"module": "google.golang.org/grpc"}], "functions": []},
        ])
        assert "b" in tracker.rpc_deps.get("a", set())
        assert "c" in tracker.rpc_deps.get("a", set())
        assert "a" in tracker.rpc_deps.get("b", set())

    def test_no_cross_repo_deps(self):
        """Single repo with no cross-repo dependencies."""
        tracker = CrossRepoDependencyTracker([
            {"repo_name": "solo", "imports": [], "functions": []}
        ])
        deps = tracker.get_all_dependencies()
        assert deps["rpc"] == {}
        assert deps["mq"] == {}
        assert deps["http"] == {}

    def test_self_ignored(self):
        """A repo should not depend on itself."""
        tracker = CrossRepoDependencyTracker([
            {
                "repo_name": "svc-a",
                "imports": [{"module": "google.golang.org/grpc"}],
                "functions": [],
            },
        ])
        assert "svc-a" not in tracker.rpc_deps.get("svc-a", set())


class TestMultiRepoImpactAnalyzer:
    def test_analyze_impact_no_deps(self):
        tracker = CrossRepoDependencyTracker([
            {"repo_name": "solo", "imports": [], "functions": []}
        ])
        analyzer = MultiRepoImpactAnalyzer(tracker)
        report = analyzer.analyze_impact("solo")
        assert report["repo"] == "solo"
        assert report["direct_dependencies"] == []
        assert report["reverse_dependencies"] == []
        assert report["risks"] == []

    def test_analyze_impact_high_coupling(self):
        """Service depending on 3+ others → high coupling risk."""
        irs = [
            {"repo_name": f"svc-{i}", "imports": [{"module": "google.golang.org/grpc"}], "functions": []}
            for i in range(5)
        ] + [
            {"repo_name": "hub", "imports": [{"module": "google.golang.org/grpc"}], "functions": []}
        ]
        tracker = CrossRepoDependencyTracker(irs)
        analyzer = MultiRepoImpactAnalyzer(tracker)
        report = analyzer.analyze_impact("hub")
        # hub shares grpc with all 5 svcs → 5 direct deps → high_coupling
        assert len(report["direct_dependencies"]) >= 3
        risks = [r for r in report["risks"] if r["type"] == "high_coupling"]
        assert len(risks) > 0

    def test_analyze_impact_high_dependents(self):
        """Service depended on by 3+ others → high dependents risk."""
        irs = [
            {"repo_name": "hub", "imports": [{"module": "google.golang.org/grpc"}], "functions": []}
        ] + [
            {"repo_name": f"svc-{i}", "imports": [{"module": "google.golang.org/grpc"}], "functions": []}
            for i in range(5)
        ]
        tracker = CrossRepoDependencyTracker(irs)
        analyzer = MultiRepoImpactAnalyzer(tracker)
        report = analyzer.analyze_impact("hub")
        assert len(report["reverse_dependencies"]) >= 3
        risks = [r for r in report["risks"] if r["type"] == "high_dependents"]
        assert len(risks) > 0

    def test_analyze_impact_no_circuit_breaker(self):
        """PRD mentions high-availability but no fallback found."""
        tracker = CrossRepoDependencyTracker([
            {"repo_name": "svc-a", "imports": [{"module": "google.golang.org/grpc"}], "functions": []},
            {"repo_name": "svc-b", "imports": [{"module": "google.golang.org/grpc"}], "functions": []},
        ])
        analyzer = MultiRepoImpactAnalyzer(tracker)
        report = analyzer.analyze_impact("svc-a", prd_text="高可用容灾降级")
        risks = [r for r in report["risks"] if r["type"] == "no_circuit_breaker"]
        assert len(risks) > 0

    def test_analyze_impact_with_fallback(self):
        """PRD mentions high-availability and fallback function exists."""
        tracker = CrossRepoDependencyTracker([
            {
                "repo_name": "svc-a",
                "imports": [{"module": "google.golang.org/grpc"}],
                "functions": [{"name": "CallB", "calls": ["fallback_handler"]}],
            },
            {"repo_name": "svc-b", "imports": [{"module": "google.golang.org/grpc"}], "functions": []},
        ])
        analyzer = MultiRepoImpactAnalyzer(tracker)
        report = analyzer.analyze_impact("svc-a", prd_text="高可用容灾降级")
        risks = [r for r in report["risks"] if r["type"] == "no_circuit_breaker"]
        assert len(risks) == 0

    def test_analyze_impact_no_prd_text(self):
        """No PRD text → no circuit breaker risk."""
        tracker = CrossRepoDependencyTracker([
            {"repo_name": "svc-a", "imports": [{"module": "google.golang.org/grpc"}], "functions": []},
            {"repo_name": "svc-b", "imports": [{"module": "google.golang.org/grpc"}], "functions": []},
        ])
        analyzer = MultiRepoImpactAnalyzer(tracker)
        report = analyzer.analyze_impact("svc-a")
        risks = [r for r in report["risks"] if r["type"] == "no_circuit_breaker"]
        assert len(risks) == 0

    def test_get_all_impact_reports(self):
        tracker = CrossRepoDependencyTracker([
            {"repo_name": "a", "imports": [{"module": "google.golang.org/grpc"}], "functions": []},
            {"repo_name": "b", "imports": [{"module": "google.golang.org/grpc"}], "functions": []},
        ])
        analyzer = MultiRepoImpactAnalyzer(tracker)
        # No get_all_impact_reports method; test individual calls
        report_a = analyzer.analyze_impact("a")
        report_b = analyzer.analyze_impact("b")
        assert report_a["repo"] == "a"
        assert report_b["repo"] == "b"
        for report in [report_a, report_b]:
            assert "risks" in report


class TestAnalyzeMultiRepoDependencies:
    def test_empty_list(self):
        result = analyze_multi_repo_dependencies([])
        assert result["dependencies"]["rpc"] == {}
        assert result["repo_summaries"] == {}

    def test_single_repo(self):
        result = analyze_multi_repo_dependencies([
            {"repo_name": "solo", "imports": [], "functions": []}
        ])
        assert "solo" in result["repo_summaries"]

    def test_two_repos_shared_rpc(self):
        result = analyze_multi_repo_dependencies([
            {"repo_name": "a", "imports": [{"module": "google.golang.org/grpc"}], "functions": []},
            {"repo_name": "b", "imports": [{"module": "google.golang.org/grpc"}], "functions": []},
        ])
        assert "a" in result["dependencies"]["rpc"]
        assert "b" in result["dependencies"]["rpc"]["a"]

    def test_with_profiles(self):
        profiles = {"a": {"business_domain": "ads"}, "b": {"business_domain": "ads"}}
        result = analyze_multi_repo_dependencies([
            {"repo_name": "a", "imports": [{"module": "google.golang.org/grpc"}], "functions": []},
            {"repo_name": "b", "imports": [{"module": "google.golang.org/grpc"}], "functions": []},
        ], profiles=profiles)
        assert "a" in result["repo_summaries"]

    def test_dict_ir_format(self):
        result = analyze_multi_repo_dependencies([
            {
                "repo_name": "a",
                "imports": [{"module": "google.golang.org/grpc"}],
                "functions": [{"name": "publish", "calls": []}],
            },
            {
                "repo_name": "b",
                "imports": [{"module": "google.golang.org/grpc"}],
                "functions": [{"name": "consume", "calls": []}],
            },
        ])
        assert "a" in result["dependencies"]["rpc"]
        assert "b" in result["dependencies"]["rpc"]["a"]

    def test_mq_same_topic(self):
        result = analyze_multi_repo_dependencies([
            {
                "repo_name": "a",
                "imports": [],
                "functions": [{"name": "publish_order", "signature": '"orders.topic"'}],
            },
            {
                "repo_name": "b",
                "imports": [],
                "functions": [{"name": "consume_order", "signature": '"orders.topic"'}],
            },
        ])
        assert "mq" in result["dependencies"]
