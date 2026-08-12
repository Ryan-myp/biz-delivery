"""
Tests for TDEngine — technical design generation logic.
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.learn_repo import IRDocument
from scripts.td_engine_v2 import TDEngine


@pytest.fixture
def engine(sample_profile, tmp_out):
    return TDEngine(sample_profile, str(tmp_out))


@pytest.fixture
def full_engine(sample_profile, tmp_out, mock_ir_document):
    eng = TDEngine(sample_profile, str(tmp_out))
    with patch.object(eng, "_scan_codebase", return_value=mock_ir_document):
        yield eng


# ── generate_td() ─────────────────────────────────────────────────────────────


class TestGenerateTD:
    def test_no_llm_returns_prompt_ready(self, engine, sample_prd):
        result = engine.generate_td(sample_prd, use_llm=False)
        assert result["status"] == "prompt_ready"
        assert "prompt_file" in result
        assert result["prd_length"] == len(sample_prd)

    def test_prompt_file_created(self, engine, sample_prd):
        result = engine.generate_td(sample_prd, use_llm=False)
        p = Path(result["prompt_file"])
        assert p.exists()
        content = p.read_text(encoding="utf-8")
        assert len(content) > 0

    def test_with_llm_returns_completed(self, engine, sample_prd):
        original_key = os.environ.get("LLM_API_KEY", "")
        os.environ["LLM_API_KEY"] = "test-key"
        try:
            # Patch both the module-level variable and the method to ensure LLM path is taken
            with patch("scripts.td_engine_v2.LLM_API_KEY", "test-key"), \
                 patch.object(TDEngine, "_call_llm", return_value="mocked td design"):
                result = engine.generate_td(sample_prd, use_llm=True)
                assert result["status"] == "completed"
                assert "design" in result
                assert result["design"] == "mocked td design"
        finally:
            if original_key:
                os.environ["LLM_API_KEY"] = original_key
            else:
                os.environ.pop("LLM_API_KEY", None)

    def test_with_llm_fallback_when_no_key(self, engine, sample_prd):
        original_key = os.environ.pop("LLM_API_KEY", None)
        try:
            result = engine.generate_td(sample_prd, use_llm=True)
            assert result["status"] == "prompt_ready"
        finally:
            if original_key:
                os.environ["LLM_API_KEY"] = original_key

    def test_with_review_report(self, engine, sample_prd):
        result = engine.generate_td(sample_prd, review_report="review content", use_llm=False)
        assert result["status"] == "prompt_ready"
        prompt_file = Path(result["prompt_file"])
        content = prompt_file.read_text(encoding="utf-8")
        assert "review content" in content


# ── _call_llm() ──────────────────────────────────────────────────────────────


class TestCallLLM:
    def test_success(self, engine):
        original_key = os.environ.get("LLM_API_KEY", "")
        os.environ["LLM_API_KEY"] = "test-key"
        try:
            with patch("httpx.Client") as mock_client_cls:
                fake_resp = MagicMock()
                fake_resp.status_code = 200
                fake_resp.json.return_value = {
                    "choices": [{"message": {"content": "design output"}}]
                }
                fake_client = MagicMock()
                fake_client.post.return_value = fake_resp
                fake_client.__enter__ = MagicMock(return_value=fake_client)
                fake_client.__exit__ = MagicMock(return_value=False)
                mock_client_cls.return_value = fake_client
                result = engine._call_llm("some prompt")
                assert result == "design output"
        finally:
            if original_key:
                os.environ["LLM_API_KEY"] = original_key
            else:
                os.environ.pop("LLM_API_KEY", None)

    def test_failure_returns_none(self, engine):
        original_key = os.environ.get("LLM_API_KEY", "")
        os.environ["LLM_API_KEY"] = "test-key"
        try:
            with patch("httpx.Client") as mock_client_cls:
                mock_client_cls.side_effect = Exception("network error")
                result = engine._call_llm("prompt")
                assert result is None
        finally:
            if original_key:
                os.environ["LLM_API_KEY"] = original_key
            else:
                os.environ.pop("LLM_API_KEY", None)

    def test_http_error_returns_none(self, engine):
        original_key = os.environ.get("LLM_API_KEY", "")
        os.environ["LLM_API_KEY"] = "test-key"
        try:
            with patch("httpx.Client") as mock_client_cls:
                fake_resp = MagicMock()
                fake_resp.status_code = 500
                fake_resp.raise_for_status.side_effect = Exception("500")
                fake_client = MagicMock()
                fake_client.post.return_value = fake_resp
                fake_client.__enter__ = MagicMock(return_value=fake_client)
                fake_client.__exit__ = MagicMock(return_value=False)
                mock_client_cls.return_value = fake_client
                result = engine._call_llm("prompt")
                assert result is None
        finally:
            if original_key:
                os.environ["LLM_API_KEY"] = original_key
            else:
                os.environ.pop("LLM_API_KEY", None)


# ── _extract_sections() ──────────────────────────────────────────────────────


class TestExtractSections:
    def test_extracts_headings(self, engine):
        design = """
# 技术方案
## 1. 背景与目标
内容
## 2. 架构设计
内容
"""
        sections = engine._extract_sections(design)
        assert "1. 背景与目标" in sections
        assert "2. 架构设计" in sections

    def test_returns_defaults_when_no_headings(self, engine):
        sections = engine._extract_sections("just plain text")
        assert sections == ["架构设计", "接口设计", "数据库设计", "风险评估"]

    def test_empty_string(self, engine):
        sections = engine._extract_sections("")
        assert sections == ["架构设计", "接口设计", "数据库设计", "风险评估"]


# ── generate_with_response() ────────────────────────────────────────────────


class TestGenerateWithResponse:
    def test_saves_report(self, engine):
        result = engine.generate_with_response("td design content")
        assert result["status"] == "completed"
        assert "report_file" in result
        p = Path(result["report_file"])
        assert p.exists()
        assert p.read_text(encoding="utf-8") == "td design content"

    def test_sections_extracted(self, engine):
        content = "## 架构设计\n内容\n## 接口设计\n内容"
        result = engine.generate_with_response(content)
        assert "架构设计" in result["sections"]

    def test_empty_response(self, engine):
        result = engine.generate_with_response("")
        assert result["status"] == "completed"
        assert result["sections"] == ["架构设计", "接口设计", "数据库设计", "风险评估"]


# ── _build_td_prompt() ───────────────────────────────────────────────────────


class TestBuildTDPrompt:
    def test_contains_ir_summary(self, engine, mock_ir_document, sample_prd):
        prompt = engine._build_td_prompt(
            filtered={"evidence": [], "total": 0},
            ir=mock_ir_document,
            prd_text=sample_prd,
        )
        assert "test-domain" in prompt
        assert "Structs" in prompt

    def test_contains_routes(self, engine, mock_ir_document, sample_prd):
        prompt = engine._build_td_prompt(
            filtered={"evidence": [], "total": 0},
            ir=mock_ir_document,
            prd_text=sample_prd,
        )
        assert "/api/auction/bid" in prompt

    def test_contains_prd_content(self, engine, mock_ir_document, sample_prd):
        prompt = engine._build_td_prompt(
            filtered={"evidence": [], "total": 0},
            ir=mock_ir_document,
            prd_text=sample_prd,
        )
        assert "用户出价功能" in prompt

    def test_contains_review_report(self, engine, mock_ir_document, sample_prd):
        review = "## 审查报告\n发现问题"
        prompt = engine._build_td_prompt(
            filtered={"evidence": [], "total": 0},
            ir=mock_ir_document,
            prd_text=sample_prd,
            review_report=review,
        )
        assert "审查报告" in prompt
        assert "发现问题" in prompt

    def test_contains_output_format_template(self, engine, mock_ir_document, sample_prd):
        prompt = engine._build_td_prompt(
            filtered={"evidence": [], "total": 0},
            ir=mock_ir_document,
            prd_text=sample_prd,
        )
        assert "背景与目标" in prompt
        assert "架构设计" in prompt
        assert "接口设计" in prompt

    def test_handles_missing_mermaid_generator(self, engine, mock_ir_document, sample_prd):
        with patch.dict("sys.modules", {"mermaid_generator": None}):
            prompt = engine._build_td_prompt(
                filtered={"evidence": [], "total": 0},
                ir=mock_ir_document,
                prd_text=sample_prd,
            )
        assert "代码库分析结果" in prompt
