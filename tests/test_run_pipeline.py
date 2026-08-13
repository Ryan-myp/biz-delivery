"""
Run Pipeline 深度测试套件
覆盖：load_profile、run_learn_mode、run_auto_mode、_safe_llm_call、_call_llm_for_*、run_prdtdd_mode
目标：scripts/run_pipeline.py 覆盖率 ≥75%
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scripts import run_pipeline


def make_profile(tmp_path, repo_exists=True):
    """构造测试 profile"""
    repo_path = tmp_path / "repo"
    if repo_exists:
        repo_path.mkdir(exist_ok=True)
        (repo_path.parent / "knowledge").mkdir(exist_ok=True)
        (repo_path.parent / "knowledge" / "test-domain").mkdir(exist_ok=True)
    return {
        "name": "test-project",
        "business_domain": "test-domain",
        "repositories": [{"path": str(repo_path)}],
    }


class TestLoadProfile:
    """Profile 加载测试"""
    
    def test_load_valid(self, tmp_path):
        """测试加载有效 profile"""
        profile_file = tmp_path / "profile.json"
        profile_file.write_text(json.dumps({"name": "test"}), encoding="utf-8")
        
        profile = run_pipeline.load_profile(str(profile_file))
        assert profile["name"] == "test"
    
    def test_load_missing(self, tmp_path):
        """测试文件不存在"""
        with pytest.raises(FileNotFoundError):
            run_pipeline.load_profile(str(tmp_path / "missing.json"))


class TestRunLearnMode:
    """learn 模式测试"""
    
    def test_run_learn(self, tmp_path):
        """测试 learn 模式"""
        with patch("scripts.run_pipeline.learn_from_repos",
                   return_value={"status": "completed", "repos_scanned": 1}) as mock_learn:
            result = run_pipeline.run_learn_mode(
                str(tmp_path / "p.json"), str(tmp_path / "out"), wiki_path=str(tmp_path)
            )
        
        mock_learn.assert_called_once()
        assert result["status"] == "completed"
    
    def test_run_learn_incremental(self, tmp_path):
        """测试增量学习"""
        with patch("scripts.run_pipeline.learn_from_repos") as mock_learn:
            run_pipeline.run_learn_mode(
                str(tmp_path / "p.json"), str(tmp_path / "out"), incremental=True
            )
        
        kwargs = mock_learn.call_args.kwargs
        assert kwargs["incremental"] is True


class TestSafeLLMCall:
    """安全 LLM 调用测试"""
    
    def test_success(self):
        """测试成功调用"""
        client = MagicMock()
        client.chat.return_value = {"content": "x" * 100, "usage": {"total_tokens": 10}}
        
        result = run_pipeline._safe_llm_call(client, "prompt", "system")
        assert result is not None
        assert result["content"] == "x" * 100
    
    def test_short_response_retries(self):
        """测试短响应重试"""
        client = MagicMock()
        client.chat.return_value = {"content": "short"}
        
        with patch("time.sleep"):
            result = run_pipeline._safe_llm_call(client, "prompt", "system", max_retries=1)
        
        assert result is None
        assert client.chat.call_count >= 2
    
    def test_exception_retries(self):
        """测试异常重试"""
        client = MagicMock()
        client.chat.side_effect = RuntimeError("API down")
        
        with patch("time.sleep"):
            result = run_pipeline._safe_llm_call(client, "prompt", "system", max_retries=1)
        
        assert result is None
        assert client.chat.call_count >= 2
    
    def test_success_after_failure(self):
        """测试失败后成功"""
        client = MagicMock()
        client.chat.side_effect = [
            RuntimeError("API down"),
            {"content": "x" * 100, "usage": {}},
        ]
        
        with patch("time.sleep"):
            result = run_pipeline._safe_llm_call(client, "prompt", "system", max_retries=2)
        
        assert result is not None


class TestCallLLMForReview:
    """审查 LLM 调用测试"""
    
    def test_no_prompt_file(self, tmp_path):
        """测试无 prompt 文件"""
        engine = MagicMock()
        engine.output_dir = tmp_path
        results = {}
        
        run_pipeline._call_llm_for_review(engine, MagicMock(), "prd", results, str(tmp_path))
        
        assert results["review"]["status"] == "skipped"
    
    def test_success(self, tmp_path):
        """测试成功"""
        (tmp_path / "review_prompt.md").write_text("prompt content", encoding="utf-8")
        
        engine = MagicMock()
        engine.output_dir = tmp_path
        engine._parse_review_report.return_value = {"p0_issues": ["issue1"]}
        
        client = MagicMock()
        client.chat.return_value = {"content": "x" * 200, "usage": {"total_tokens": 50}}
        
        results = {}
        run_pipeline._call_llm_for_review(engine, client, "prd", results, str(tmp_path))
        
        assert results["review"]["status"] == "completed"
        assert results["review"]["source"] == "llm_auto"
        engine.review_with_response.assert_called_once()
    
    def test_failure(self, tmp_path):
        """测试失败"""
        (tmp_path / "review_prompt.md").write_text("prompt", encoding="utf-8")
        
        engine = MagicMock()
        engine.output_dir = tmp_path
        client = MagicMock()
        client.chat.return_value = {"content": "short"}
        
        with patch("time.sleep"):
            results = {}
            run_pipeline._call_llm_for_review(engine, client, "prd", results, str(tmp_path))
        
        assert results["review"]["status"] == "error"


class TestCallLLMForTD:
    """TD LLM 调用测试"""
    
    def test_no_prompt_file(self, tmp_path):
        """测试无 prompt 文件"""
        engine = MagicMock()
        engine.output_dir = tmp_path
        results = {}
        
        run_pipeline._call_llm_for_td(engine, MagicMock(), "prd", results, str(tmp_path))
        
        assert results["td"]["status"] == "skipped"
    
    def test_success(self, tmp_path):
        """测试成功"""
        (tmp_path / "td_prompt.md").write_text("prompt", encoding="utf-8")
        
        engine = MagicMock()
        engine.output_dir = tmp_path
        client = MagicMock()
        client.chat.return_value = {"content": "x" * 200, "usage": {"total_tokens": 30}}
        
        results = {}
        run_pipeline._call_llm_for_td(engine, client, "prd", results, str(tmp_path))
        
        assert results["td"]["status"] == "completed"
        engine.generate_with_response.assert_called_once()
    
    def test_failure(self, tmp_path):
        """测试失败"""
        (tmp_path / "td_prompt.md").write_text("prompt", encoding="utf-8")
        
        engine = MagicMock()
        engine.output_dir = tmp_path
        client = MagicMock()
        client.chat.return_value = {"content": ""}
        
        with patch("time.sleep"):
            results = {}
            run_pipeline._call_llm_for_td(engine, client, "prd", results, str(tmp_path))
        
        assert results["td"]["status"] == "error"


class TestCallLLMForTests:
    """测试用例 LLM 调用测试"""
    
    def test_no_prompt_file(self, tmp_path):
        """测试无 prompt 文件"""
        engine = MagicMock()
        engine.output_dir = tmp_path
        results = {}
        
        run_pipeline._call_llm_for_tests(engine, MagicMock(), "prd", results, str(tmp_path))
        
        assert results["test"]["status"] == "skipped"
    
    def test_success(self, tmp_path):
        """测试成功"""
        (tmp_path / "test_prompt.md").write_text("prompt", encoding="utf-8")
        
        engine = MagicMock()
        engine.output_dir = tmp_path
        client = MagicMock()
        client.chat.return_value = {"content": "x" * 200, "usage": {}}
        
        results = {}
        run_pipeline._call_llm_for_tests(engine, client, "prd", results, str(tmp_path))
        
        assert results["test"]["status"] == "completed"
        engine.generate_with_response.assert_called_once()


class TestRunAutoMode:
    """auto 模式测试"""
    
    def test_no_api_key(self, tmp_path, monkeypatch):
        """测试无 API key 返回错误"""
        monkeypatch.delenv("AGNES_API_KEY", raising=False)
        profile = make_profile(tmp_path)
        out_dir = tmp_path / "out"
        
        with patch("scripts.run_pipeline.LLMClient", side_effect=ValueError("no key")):
            result = run_pipeline.run_auto_mode(profile, "PRD", str(out_dir))
        
        assert result["status"] == "error"
        assert "no key" in result["message"]
    
    def test_success(self, tmp_path):
        """测试成功流程"""
        profile = make_profile(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        
        # 预生成 LLM 报告，避免实际调用
        (out_dir / "review_report.md").write_text("x" * 200, encoding="utf-8")
        (out_dir / "technical_design.md").write_text("x" * 200, encoding="utf-8")
        (out_dir / "test_cases.md").write_text("x" * 200, encoding="utf-8")
        
        mock_client = MagicMock()
        mock_client.model = "test-model"
        
        with patch("scripts.run_pipeline.LLMClient", return_value=mock_client) as MockLLM:
            with patch("scripts.run_pipeline.ReviewEngine") as MockReview:
                mock_review = MagicMock()
                mock_review.review.return_value = {"status": "prompt_ready"}
                mock_review._parse_review_report.return_value = {"p0_issues": []}
                mock_review.output_dir = tmp_path
                MockReview.return_value = mock_review
                
                with patch("scripts.run_pipeline.TDEngine") as MockTD:
                    mock_td = MagicMock()
                    mock_td.generate_td.return_value = {"status": "prompt_ready"}
                    mock_td.output_dir = tmp_path
                    MockTD.return_value = mock_td
                    
                    with patch("scripts.run_pipeline.TestEngine") as MockTest:
                        mock_test = MagicMock()
                        mock_test.generate_tests.return_value = {"status": "prompt_ready"}
                        mock_test.output_dir = tmp_path
                        MockTest.return_value = mock_test
                        
                        result = run_pipeline.run_auto_mode(profile, "PRD", str(out_dir))
        
        assert result["status"] == "completed"
        assert result["stages_executed"] == ["review", "td", "test"]
        assert result["results"]["review"]["source"] == "existing_report"
        assert result["results"]["td"]["source"] == "existing"
        assert result["results"]["test"]["source"] == "existing"


class TestRunPrdtddMode:
    """prdtdd 模式测试"""
    
    def test_full_pipeline(self, tmp_path):
        """测试完整流水线"""
        profile = make_profile(tmp_path)
        out_dir = tmp_path / "out"
        
        with patch("scripts.run_pipeline.ReviewEngine") as MockReview, \
             patch("scripts.run_pipeline.TDEngine") as MockTD, \
             patch("scripts.run_pipeline.TestEngine") as MockTest:
            
            # Mock review
            mock_review = MagicMock()
            prompt_file = tmp_path / "review_prompt.md"
            prompt_file.write_text("review prompt", encoding="utf-8")
            mock_review.review.return_value = {
                "status": "prompt_ready",
                "prompt_file": str(prompt_file),
            }
            mock_review.output_dir = tmp_path
            MockReview.return_value = mock_review
            
            # Mock td
            mock_td = MagicMock()
            td_prompt = tmp_path / "td_prompt.md"
            td_prompt.write_text("td prompt", encoding="utf-8")
            mock_td.generate_td.return_value = {
                "status": "prompt_ready",
                "prompt_file": str(td_prompt),
            }
            mock_td.output_dir = tmp_path
            MockTD.return_value = mock_td
            
            # Mock test
            mock_test = MagicMock()
            test_prompt = tmp_path / "test_prompt.md"
            test_prompt.write_text("test prompt", encoding="utf-8")
            mock_test.generate_tests.return_value = {
                "status": "prompt_ready",
                "prompt_file": str(test_prompt),
            }
            mock_test.output_dir = tmp_path
            MockTest.return_value = mock_test
            
            result = run_pipeline.run_prdtdd_mode(
                profile, "PRD 内容", str(out_dir), stages=["review", "td", "test"]
            )
        
        assert result["status"] == "completed"
        assert result["stages_executed"] == ["review", "td", "test"]
        assert "review" in result["results"]
        assert "td" in result["results"]
        assert "test" in result["results"]
    
    def test_review_only(self, tmp_path):
        """测试仅 review"""
        profile = make_profile(tmp_path)
        out_dir = tmp_path / "out"
        
        with patch("scripts.run_pipeline.ReviewEngine") as MockReview:
            mock_review = MagicMock()
            prompt_file = tmp_path / "review_prompt.md"
            prompt_file.write_text("review", encoding="utf-8")
            mock_review.review.return_value = {
                "status": "prompt_ready",
                "prompt_file": str(prompt_file),
            }
            mock_review.output_dir = tmp_path
            MockReview.return_value = mock_review
            
            result = run_pipeline.run_prdtdd_mode(
                profile, "PRD", str(out_dir), stages=["review"]
            )
        
        assert result["stages_executed"] == ["review"]
        assert "td" not in result["results"]
    
    def test_with_existing_reports(self, tmp_path):
        """测试已有报告"""
        profile = make_profile(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "review_report.md").write_text("x" * 200, encoding="utf-8")
        
        with patch("scripts.run_pipeline.ReviewEngine") as MockReview:
            mock_review = MagicMock()
            mock_review.review.return_value = {"status": "prompt_ready"}
            mock_review.output_dir = tmp_path
            MockReview.return_value = mock_review
            
            with patch("scripts.run_pipeline.TDEngine") as MockTD:
                mock_td = MagicMock()
                mock_td.generate_td.return_value = {"status": "prompt_ready"}
                mock_td.output_dir = tmp_path
                MockTD.return_value = mock_td
                
                result = run_pipeline.run_prdtdd_mode(
                    profile, "PRD", str(out_dir), stages=["review", "td"]
                )
        
        assert result["status"] == "completed"
