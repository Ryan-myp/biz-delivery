"""
Tests for TestEngine — test case generation and report parsing.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.learn_repo import IRDocument
from scripts.test_engine import TestEngine


@pytest.fixture
def engine(sample_profile, tmp_out):
    return TestEngine(sample_profile, str(tmp_out))


@pytest.fixture
def full_engine(sample_profile, tmp_out, mock_ir_document):
    eng = TestEngine(sample_profile, str(tmp_out))
    with patch.object(eng, "_scan_codebase", return_value=mock_ir_document):
        yield eng


# ── generate_tests() ─────────────────────────────────────────────────────────


class TestGenerateTests:
    def test_returns_prompt_ready(self, engine, sample_prd):
        result = engine.generate_tests(sample_prd)
        assert result["status"] == "prompt_ready"
        assert "prompt_file" in result
        assert result["prd_length"] == len(sample_prd)

    def test_prompt_file_created(self, engine, sample_prd):
        result = engine.generate_tests(sample_prd)
        p = Path(result["prompt_file"])
        assert p.exists()
        assert len(p.read_text(encoding="utf-8")) > 0

    def test_prompt_contains_prd(self, engine, sample_prd):
        result = engine.generate_tests(sample_prd)
        content = Path(result["prompt_file"]).read_text(encoding="utf-8")
        assert "用户出价功能" in content

    def test_empty_prd(self, engine):
        result = engine.generate_tests("")
        assert result["status"] == "prompt_ready"
        assert result["prd_length"] == 0


# ── generate_with_response() ────────────────────────────────────────────────


class TestGenerateWithResponse:
    def test_saves_report(self, engine):
        result = engine.generate_with_response("test cases content")
        assert result["status"] == "completed"
        assert "report_file" in result
        p = Path(result["report_file"])
        assert p.exists()
        assert p.read_text(encoding="utf-8") == "test cases content"

    def test_sections_expected(self, engine):
        result = engine.generate_with_response("content")
        assert result["sections"] == ["正向流程", "异常分支", "边界条件", "性能测试", "安全测试"]

    def test_empty_response(self, engine):
        result = engine.generate_with_response("")
        assert result["status"] == "completed"


# ── _parse_test_report() ─────────────────────────────────────────────────────


class TestParseTestReport:
    def test_parses_table_cases(self, engine):
        response = """
| TC001 | 正常出价 | 用户已登录 | 点击出价 | 出价成功 | P0 |
| TC002 | 查询状态 | 无 | 请求状态 | 返回状态 | P1 |
| TC003 | 重复出价 | 已出价 | 再次出价 | 返回错误 | P0 |
"""
        parsed = engine._parse_test_report(response)
        assert parsed["has_structured_data"] is True
        assert parsed["total_cases"] == 3

    def test_categorized_by_priority(self, engine):
        response = """
| TC001 | 场景A | 预条件 | 步骤 | 预期 | P0 |
| TC002 | 场景B | 预条件 | 步骤 | 预期 | P1 |
| TC003 | 场景C | 预条件 | 步骤 | 预期 | P2 |
"""
        parsed = engine._parse_test_report(response)
        assert len(parsed["by_priority"]["P0"]) == 1
        assert len(parsed["by_priority"]["P1"]) == 1
        assert len(parsed["by_priority"]["P2"]) == 1

    def test_categorized_by_category(self, engine):
        response = """
| TC001 | 创建操作测试 | 预条件 | 步骤 | 预期 | P1 |
| TC002 | 查询操作测试 | 预条件 | 步骤 | 预期 | P1 |
"""
        parsed = engine._parse_test_report(response)
        assert isinstance(parsed["by_category"], dict)
        assert "创建操作" in parsed["by_category"]
        assert "查询操作" in parsed["by_category"]

    def test_coverage_analysis_present(self, engine):
        response = "| TC001 | 场景 | 预 | 步 | 期 | P0 |"
        parsed = engine._parse_test_report(response)
        ca = parsed["coverage_analysis"]
        assert ca["structured"] is True
        assert ca["total_cases"] == 1

    def test_recommendations_for_missing_scenarios(self, engine):
        response = "| TC001 | 正常流程 | 预 | 步 | 期 | P0 |"
        parsed = engine._parse_test_report(response)
        assert isinstance(parsed["recommendations"], list)

    def test_uncovered_scenarios_detected(self, engine):
        response = "| TC001 | 正常流程 | 预 | 步 | 期 | P0 |"
        parsed = engine._parse_test_report(response)
        ca = parsed["coverage_analysis"]
        assert "uncovered_scenarios" in ca

    def test_non_table_response(self, engine):
        response = "一些测试说明\nTC001 描述\nTC002 描述"
        parsed = engine._parse_test_report(response)
        assert parsed["has_structured_data"] is False
        assert parsed["total_cases"] == 2
        assert any("未检测到结构化测试用例表格" in r for r in parsed["recommendations"])

    def test_empty_response(self, engine):
        parsed = engine._parse_test_report("")
        assert parsed["total_cases"] == 0
        assert parsed["has_structured_data"] is False

    def test_invalid_priority_defaults_to_p2(self, engine):
        response = "| TC001 | 场景 | 预 | 步 | 期 | P9 |"
        parsed = engine._parse_test_report(response)
        assert len(parsed["by_priority"]["P2"]) == 1

    def test_section_extraction(self, engine):
        response = """
## 正向流程
内容1

## 异常分支
内容2
"""
        parsed = engine._parse_test_report(response)
        assert "正向流程" in parsed["sections"]
        assert "异常分支" in parsed["sections"]


# ── _detect_uncovered_scenarios() ────────────────────────────────────────────


class TestDetectUncoveredScenarios:
    def test_detects_missing_auth_scenario(self, engine):
        cases_by_cat = {
            "正向流程": [{"scenario": "正常出价"}],
        }
        uncovered = engine._detect_uncovered_scenarios(cases_by_cat, "")
        assert "鉴权检查" in uncovered

    def test_all_scenarios_covered(self, engine):
        cases_by_cat = {
            "正向流程": [{"scenario": "正常出价"}],
            "安全测试": [{"scenario": "鉴权检查 token 无效"}],
            "异常与边界": [{"scenario": "空值处理 null"}],
        }
        uncovered = engine._detect_uncovered_scenarios(cases_by_cat, "")
        assert len(uncovered) < 6

    def test_empty_cases(self, engine):
        uncovered = engine._detect_uncovered_scenarios({}, "")
        assert len(uncovered) >= 4

    def test_partial_coverage(self, engine):
        cases_by_cat = {
            "正向流程": [{"scenario": "正常流程"}],
            "安全测试": [{"scenario": "权限不足"}],
        }
        uncovered = engine._detect_uncovered_scenarios(cases_by_cat, "")
        assert len(uncovered) > 0


# ── generate_test_code_from_ir() ─────────────────────────────────────────────


class TestGenerateTestCodeFromIR:
    @patch("scripts.test_engine.TestCodeGenerator")
    def test_generates_test_files(self, mock_gen_cls, engine, mock_ir_document):
        mock_gen = MagicMock()
        mock_gen.generate_batch_tests.return_value = {
            "bid_handler_test.go": "package handlers\n\nfunc TestPlaceBid(t *testing.T) {}",
        }
        mock_gen_cls.return_value = mock_gen

        with patch.object(engine, "_scan_codebase", return_value=mock_ir_document):
            result = engine.generate_test_code_from_ir(
                handlers=["PlaceBid"],
                test_types=["success"],
                language="go",
            )
        assert result["status"] == "completed"
        assert "bid_handler_test.go" in result["files"]
        assert result["summary"]["handlers"] == ["PlaceBid"]

    def test_no_handlers_generates_all(self, engine, mock_ir_document):
        with patch.object(engine, "_scan_codebase", return_value=mock_ir_document):
            with patch("scripts.test_engine.TestCodeGenerator") as mock_gen_cls:
                mock_gen = MagicMock()
                mock_gen.generate_batch_tests.return_value = {}
                mock_gen_cls.return_value = mock_gen
                engine.generate_test_code_from_ir()
                call_args = mock_gen.generate_batch_tests.call_args
                assert len(call_args[0][0]) > 0

    def test_with_custom_test_types(self, engine, mock_ir_document):
        with patch.object(engine, "_scan_codebase", return_value=mock_ir_document):
            with patch("scripts.test_engine.TestCodeGenerator") as mock_gen_cls:
                mock_gen = MagicMock()
                mock_gen.generate_batch_tests.return_value = {}
                mock_gen_cls.return_value = mock_gen
                engine.generate_test_code_from_ir(
                    handlers=["PlaceBid"],
                    test_types=["boundary"],
                    language="python",
                )
                call_args = mock_gen.generate_batch_tests.call_args
                assert call_args[0][1] == ["boundary"]
