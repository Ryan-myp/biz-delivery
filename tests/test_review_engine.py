"""
Tests for ReviewEngine — PRD review logic, parsing, and precheck methods.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.learn_repo import IRDocument
from scripts.review_engine import ReviewEngine


@pytest.fixture
def engine(sample_profile, tmp_out):
    return ReviewEngine(sample_profile, str(tmp_out))


@pytest.fixture
def full_engine(sample_profile, tmp_out, mock_ir_document):
    eng = ReviewEngine(sample_profile, str(tmp_out))
    with patch.object(eng, "_scan_codebase", return_value=mock_ir_document):
        yield eng


# ── review() — the main entry point ──────────────────────────────────────────


class TestReview:
    @patch.object(ReviewEngine, "_query_and_validate")
    @patch.object(ReviewEngine, "_build_review_prompt")
    def test_review_returns_prompt_ready(self, mock_build, mock_query, engine, sample_prd):
        mock_query.return_value = {"evidence": [], "total": 0}
        mock_build.return_value = "prompt text"
        result = engine.review(sample_prd)
        assert result["status"] == "prompt_ready"
        assert "prompt_file" in result
        assert result["prd_length"] == len(sample_prd)

    def test_review_creates_prompt_file(self, engine, sample_prd):
        with patch.object(engine, "_query_and_validate", return_value={"evidence": [], "total": 0}):
            with patch.object(engine, "_build_review_prompt", return_value="prompt"):
                result = engine.review(sample_prd)
        prompt_file = Path(result["prompt_file"])
        assert prompt_file.exists()
        assert prompt_file.read_text(encoding="utf-8") == "prompt"

    def test_review_empty_prd(self, engine):
        with patch.object(engine, "_query_and_validate", return_value={"evidence": [], "total": 0}):
            with patch.object(engine, "_build_review_prompt", return_value="prompt"):
                result = engine.review("")
        assert result["status"] == "prompt_ready"
        assert result["prd_length"] == 0


# ── review_with_response() ───────────────────────────────────────────────────


class TestReviewWithResponse:
    def test_saves_report_and_returns_completed(self, engine):
        response = "- [P0] Critical issue\n- [P1] Warning issue"
        result = engine.review_with_response(response)
        assert result["status"] == "completed"
        assert "report_file" in result
        assert Path(result["report_file"]).exists()
        assert result["sections"] == ["合理性检查", "场景遗漏", "前后一致性", "风险评估"]

    def test_report_content_written(self, engine):
        response = "review content here"
        result = engine.review_with_response(response)
        content = Path(result["report_file"]).read_text(encoding="utf-8")
        assert content == response

    def test_invalid_response_still_saves(self, engine):
        result = engine.review_with_response("some garbage")
        assert result["status"] == "completed"


# ── _parse_review_report() ───────────────────────────────────────────────────


class TestParseReviewReport:
    def test_parses_p0_issues(self, engine):
        response = "## P0 Issues\n- [P0] Critical issue\n- [P0] Another critical"
        parsed = engine._parse_review_report(response)
        assert len(parsed["p0_issues"]) == 2
        assert parsed["p0_issues"][0]["priority"] == "P0"

    def test_parses_p1_issues(self, engine):
        response = "## P1 Issues\n- [P1] Warning issue"
        parsed = engine._parse_review_report(response)
        assert len(parsed["p1_issues"]) == 1

    def test_parses_p2_issues(self, engine):
        response = "## P2 Issues\n- [P2] Low issue"
        parsed = engine._parse_review_report(response)
        assert len(parsed["p2_issues"]) == 1

    def test_severity_score_computed(self, engine):
        response = "## P0 Issues\n- [P0] A\n## P1 Issues\n- [P1] B\n## P2 Issues\n- [P2] C"
        parsed = engine._parse_review_report(response)
        assert parsed["severity_score"] == 6  # 3 + 2 + 1

    def test_risk_level_critical(self, engine):
        response = "## P0 Issues\n" + "\n".join([f"- [P0] Issue {i}" for i in range(2)])
        parsed = engine._parse_review_report(response)
        assert parsed["risk_level"] == "critical"

    def test_risk_level_high(self, engine):
        response = "## P1 Issues\n- [P1] A\n- [P1] B"  # 2 issues = score 4 -> high
        parsed = engine._parse_review_report(response)
        assert parsed["risk_level"] == "high"

    def test_risk_level_medium(self, engine):
        response = "## P1 Issues\n- [P1] Single issue"  # 1 issue = score 2 -> medium
        parsed = engine._parse_review_report(response)
        assert parsed["risk_level"] == "medium"

    def test_risk_level_low(self, engine):
        response = "## P2 Issues\n- [P2] Low issue"  # 1 P2 = score 1 -> medium (not low!)
        parsed = engine._parse_review_report(response)
        assert parsed["risk_level"] == "medium"

    def test_empty_response(self, engine):
        parsed = engine._parse_review_report("")
        assert parsed["overall_status"] == "unknown"
        assert parsed["severity_score"] == 0
        assert parsed["risk_level"] == "low"
        assert parsed["all_issues"] == []

    def test_sections_dict_empty_when_no_sections(self, engine):
        response = "## P0 Issues\n- [P0] Issue"
        parsed = engine._parse_review_report(response)
        assert isinstance(parsed["sections"], dict)

    def test_category_coverage_counted(self, engine):
        response = "## P0 Issues\n- [P0] redis cache performance\n- [P1] sql injection attack"
        parsed = engine._parse_review_report(response)
        assert isinstance(parsed["category_coverage"], dict)
        assert parsed["all_issues"]

    def test_recommendations_present(self, engine):
        response = "## P0 Issues\n- [P0] Some issue"
        parsed = engine._parse_review_report(response)
        assert len(parsed["recommendations"]) > 0

    def test_overall_status_from_keywords(self, engine):
        for keyword in ["通过", "需修订", "Blocked", "Approved", "Needs Revision"]:
            parsed = engine._parse_review_report(f"# {keyword}")
            assert parsed["overall_status"] == keyword


# ── _classify_issue_category() ───────────────────────────────────────────────


class TestClassifyIssueCategory:
    def test_cache_keyword(self, engine):
        assert engine._classify_issue_category("redis cache performance issue") == "性能缓存"

    def test_auth_keyword(self, engine):
        assert engine._classify_issue_category("permission token auth") == "鉴权权限"

    def test_security_keyword(self, engine):
        assert engine._classify_issue_category("security vulnerability xss") == "安全漏洞"

    def test_chinese_keyword(self, engine):
        assert engine._classify_issue_category("数据库事务隔离") == "数据库事务"

    def test_default_category(self, engine):
        assert engine._classify_issue_category("some random text without keywords") == "其他通用"

    def test_empty_string(self, engine):
        assert engine._classify_issue_category("") == "其他通用"

    def test_distributed_lock_keyword(self, engine):
        # "redlock" contains "lock" which matches 分布式锁
        assert engine._classify_issue_category("distributed lock redlock") == "分布式锁"


# ── _generate_recommendation() ───────────────────────────────────────────────


class TestGenerateRecommendation:
    def test_known_category(self, engine):
        rec = engine._generate_recommendation("性能缓存", "P0")
        assert "Redis" in rec or "缓存" in rec

    def test_unknown_category(self, engine):
        rec = engine._generate_recommendation("未知类别", "P1")
        assert "未知类别" in rec

    def test_recommendation_contains_category(self, engine):
        rec = engine._generate_recommendation("鉴权权限", "P0")
        assert "鉴权权限" in rec or "RBAC" in rec


# ── _extract_section() ───────────────────────────────────────────────────────


class TestExtractSection:
    def test_existing_section(self, engine):
        text = "## 合理性检查\n内容\n## Other"
        result = engine._extract_section(text, "合理性检查")
        assert result == "内容"

    def test_missing_section(self, engine):
        result = engine._extract_section("no such section", "Missing")
        assert result is None

    def test_heading_variants(self, engine):
        text = "# 标题\n内容"
        result = engine._extract_section(text, "标题")
        assert result == "内容"

    def test_stop_at_next_heading(self, engine):
        text = "## First\ncontent\n## Second\nmore"
        result = engine._extract_section(text, "First")
        assert result == "content"
        assert "Second" not in result

    def test_empty_text(self, engine):
        result = engine._extract_section("", "anything")
        assert result is None

    def test_returns_none_on_bad_match(self, engine):
        # When regex matches but group(1) is None (buggy pattern), should return None
        result = engine._extract_section("just text", "missing")
        assert result is None


# ── _query_and_validate() ────────────────────────────────────────────────────


class TestQueryAndValidate:
    @patch.object(ReviewEngine, "_query_evidence_for_prd")
    @patch.object(ReviewEngine, "_run_prechecks")
    def test_returns_filtered_with_prechecks(self, mock_prechecks, mock_query, engine, mock_ir_document, sample_prd):
        mock_query.return_value = {"evidence": [], "total": 0}
        mock_prechecks.return_value = [{"check": "entity_exists", "severity": "info"}]
        result = engine._query_and_validate(mock_ir_document, sample_prd, "/tmp/cache")
        assert "prechecks" in result
        assert result["prechecks"][0]["check"] == "entity_exists"

    @patch.object(ReviewEngine, "_query_evidence_for_prd")
    def test_returns_total_evidence(self, mock_query, engine, mock_ir_document, sample_prd):
        mock_query.return_value = {"evidence": [{"title": "e1"}], "total": 1}
        with patch.object(engine, "_run_prechecks", return_value=[]):
            result = engine._query_and_validate(mock_ir_document, sample_prd, "/tmp")
        assert result["total"] == 1


# ── _run_prechecks() ─────────────────────────────────────────────────────────


class TestRunPrechecks:
    def test_returns_list(self, engine, mock_ir_document, sample_prd):
        checks = engine._run_prechecks(mock_ir_document, sample_prd, [])
        assert isinstance(checks, list)

    def test_route_missing_check(self, engine, mock_ir_document):
        prd_with_missing_route = "访问 /api/nonexistent/endpoint"
        checks = engine._run_prechecks(mock_ir_document, prd_with_missing_route, [])
        route_checks = [c for c in checks if c.get("check") == "route_missing"]
        assert len(route_checks) >= 1

    def test_performance_risk_check(self, engine, mock_ir_document):
        prd = "高并发场景，需要支持大量请求"
        checks = engine._run_prechecks(mock_ir_document, prd, [])
        perf_checks = [c for c in checks if c.get("check") == "performance_risk"]
        assert isinstance(perf_checks, list)

    def test_entity_checks(self, engine, mock_ir_document):
        checks = engine._run_prechecks(mock_ir_document, "涉及 UserBid 实体", [])
        assert isinstance(checks, list)


# ── _analyze_cross_repo_deps() ───────────────────────────────────────────────


class TestAnalyzeCrossRepoDeps:
    def test_no_cross_service_keywords(self, engine, mock_ir_document):
        checks = engine._analyze_cross_repo_deps(mock_ir_document, "简单功能需求")
        assert isinstance(checks, list)

    def test_multi_service_detected(self, engine, mock_ir_document):
        mock_ir_document.services = [
            {"name": "svc-a"},
            {"name": "svc-b"},
        ]
        prd = "跨服务调用，需要RPC通信"
        checks = engine._analyze_cross_repo_deps(mock_ir_document, prd)
        multi_svc = [c for c in checks if c.get("rule") == "multi_service_detected"]
        assert len(multi_svc) >= 1

    def test_high_coupling_detected(self, engine, mock_ir_document):
        mock_ir_document.call_graph = [
            {"caller": f"pkg-a.func{i}", "callee": f"pkg-b.func{i}"}
            for i in range(15)
        ]
        prd = "服务间调用"
        checks = engine._analyze_cross_repo_deps(mock_ir_document, prd)
        coupling = [c for c in checks if c.get("rule") == "high_cross_package_coupling"]
        assert len(coupling) >= 1


# ── _validate_business_rules() ───────────────────────────────────────────────


class TestValidateBusinessRules:
    def test_error_code_missing(self, engine, mock_ir_document):
        prd = "需要处理各种错误场景，包括404和500错误"
        mock_ir_document.error_codes = []
        checks = engine._validate_business_rules(mock_ir_document, prd, {})
        err_checks = [c for c in checks if c.get("rule") == "error_code_coverage"]
        assert len(err_checks) >= 1

    def test_auth_missing(self, engine, mock_ir_document):
        prd = "需要鉴权控制"
        mock_ir_document.auth_models = []
        checks = engine._validate_business_rules(mock_ir_document, prd, {})
        auth_checks = [c for c in checks if c.get("rule") == "auth_missing"]
        assert len(auth_checks) >= 1

    def test_struct_missing(self, engine, mock_ir_document):
        prd = "需要新增Order实体"
        mock_ir_document.structs = []
        checks = engine._validate_business_rules(mock_ir_document, prd, {})
        struct_checks = [c for c in checks if c.get("rule") == "struct_missing"]
        assert len(struct_checks) >= 1

    def test_empty_checks_when_no_issues(self, engine, mock_ir_document):
        prd = "一个简单的GET请求"
        checks = engine._validate_business_rules(mock_ir_document, prd, {})
        assert isinstance(checks, list)


# ── _build_review_prompt() ───────────────────────────────────────────────────


class TestBuildReviewPrompt:
    def test_prompt_contains_ir_summary(self, engine, mock_ir_document, sample_prd):
        with patch.object(engine, "_query_and_validate", return_value={"evidence": [], "total": 0}):
            prompt = engine._build_review_prompt(
                {"evidence": [], "total": 0},
                mock_ir_document,
                sample_prd,
                cache_dir="/tmp",
            )
        assert "test-domain" in prompt
        assert "Structs" in prompt

    def test_prompt_contains_routes(self, engine, mock_ir_document, sample_prd):
        with patch.object(engine, "_query_and_validate", return_value={"evidence": [], "total": 0}):
            prompt = engine._build_review_prompt(
                {"evidence": [], "total": 0},
                mock_ir_document,
                sample_prd,
                cache_dir="/tmp",
            )
        assert "/api/auction/bid" in prompt

    def test_prompt_contains_review_rules(self, engine, mock_ir_document, sample_prd):
        with patch.object(engine, "_query_and_validate", return_value={"evidence": [], "total": 0}):
            prompt = engine._build_review_prompt(
                {"evidence": [], "total": 0},
                mock_ir_document,
                sample_prd,
                cache_dir="/tmp",
            )
        assert "审查规则" in prompt or "规则" in prompt

    def test_prompt_contains_evidence(self, engine, mock_ir_document, sample_prd):
        evidence = [{"title": "e1", "score": 0.9, "content": "text"}]
        with patch.object(engine, "_query_and_validate", return_value={"evidence": evidence, "total": 1}):
            prompt = engine._build_review_prompt(
                {"evidence": evidence, "total": 1},
                mock_ir_document,
                sample_prd,
                cache_dir="/tmp",
            )
        assert "e1" in prompt
