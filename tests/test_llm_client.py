"""
LLM Client 深度测试套件
覆盖：LLMClient 全部方法、build_review_prompt、build_td_prompt、build_test_prompt、create_client
目标：scripts/llm_client.py 覆盖率 ≥80%
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.llm_client import (
    LLMClient, build_review_prompt, build_td_prompt,
    build_test_prompt, create_client,
)


class TestLLMClientInit:
    """LLMClient 初始化测试"""
    
    def test_init_with_key(self):
        """测试显式传 key"""
        client = LLMClient(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.model == "agnes-2.0-flash"
        assert client.retries == 3
    
    def test_init_custom_params(self):
        """测试自定义参数"""
        client = LLMClient(
            api_key="test-key",
            model="custom-model",
            max_tokens=4096,
            temperature=0.5,
            timeout=30,
            retries=5,
        )
        assert client.model == "custom-model"
        assert client.max_tokens == 4096
        assert client.temperature == 0.5
        assert client.timeout == 30
        assert client.retries == 5
    
    def test_init_no_key_raises(self, monkeypatch):
        """测试无 key 报错"""
        monkeypatch.delenv("AGNES_API_KEY", raising=False)
        with pytest.raises(ValueError, match="API key not found"):
            LLMClient()
    
    def test_load_api_key_from_env(self, monkeypatch):
        """测试从环境变量加载 key"""
        monkeypatch.setenv("AGNES_API_KEY", "env-key")
        client = LLMClient()
        assert client.api_key == "env-key"
    
    def test_load_api_key_from_json_config(self, tmp_path, monkeypatch):
        """测试从 JSON 配置加载"""
        monkeypatch.delenv("AGNES_API_KEY", raising=False)
        
        client = LLMClient.__new__(LLMClient)
        
        # mock open 返回带 api_key 的 JSON 配置
        fake_file = MagicMock()
        fake_file.__enter__.return_value = fake_file
        fake_file.read.return_value = json.dumps({"api_key": "json-key"})
        
        with patch("builtins.open", return_value=fake_file):
            key = client._load_api_key()
        assert key == "json-key"
    
    def test_load_api_key_json_broken(self, tmp_path, monkeypatch):
        """测试 JSON 配置损坏时优雅降级"""
        monkeypatch.delenv("AGNES_API_KEY", raising=False)
        
        client = LLMClient.__new__(LLMClient)
        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", side_effect=json.JSONDecodeError("bad", "doc", 0)):
            key = client._load_api_key()
        assert key == ""
    
    def test_load_api_key_empty(self, monkeypatch):
        """测试无 key"""
        monkeypatch.delenv("AGNES_API_KEY", raising=False)
        client = LLMClient.__new__(LLMClient)
        key = client._load_api_key()
        assert key == ""


class TestLLMClientMethods:
    """LLMClient 方法测试"""
    
    def _make_client(self):
        return LLMClient(api_key="test-key")
    
    def _make_mock_response(self, payload):
        """构造可用的 mock 响应（支持 context manager）"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(payload).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        return mock_response
    
    def test_build_request_basic(self):
        """测试基础请求构建"""
        client = self._make_client()
        body = client._build_request(
            [{"role": "user", "content": "hello"}],
        )
        assert body["model"] == "agnes-2.0-flash"
        assert body["messages"][0]["role"] == "user"
        assert body["max_tokens"] == 8192
    
    def test_build_request_response_format(self):
        """测试结构化输出"""
        client = self._make_client()
        body = client._build_request(
            [{"role": "user", "content": "hello"}],
            response_format={"type": "object", "properties": {"a": {"type": "string"}}},
        )
        assert body["response_format"]["type"] == "json_schema"
    
    def test_build_request_tools(self):
        """测试工具调用"""
        client = self._make_client()
        body = client._build_request(
            [{"role": "user", "content": "hello"}],
            tools=[{"type": "function", "name": "search"}],
        )
        assert body["tools"][0]["name"] == "search"
    
    def test_make_call_success(self):
        """测试 API 调用成功"""
        client = self._make_client()
        mock_response = self._make_mock_response({
            "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 10},
        })
        
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client._make_call({}, [])
        
        assert result["choices"][0]["message"]["content"] == "hello"
        assert client._call_count == 1
        assert client._total_tokens == 10
    
    def test_make_call_retry_success(self):
        """测试重试后成功"""
        client = self._make_client()
        
        from urllib.error import URLError
        mock_response = self._make_mock_response({
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 5},
        })
        
        with patch("urllib.request.urlopen", side_effect=[URLError("timeout"), mock_response]):
            result = client._make_call({}, [])
        
        assert result["choices"][0]["message"]["content"] == "ok"
    
    def test_make_call_fail(self):
        """测试 API 调用失败"""
        client = self._make_client()
        
        from urllib.error import URLError
        with patch("urllib.request.urlopen", side_effect=URLError("network error")):
            with pytest.raises(RuntimeError, match="LLM API call failed"):
                client._make_call({}, [])
    
    def test_chat_success(self):
        """测试聊天成功"""
        client = self._make_client()
        mock_response = self._make_mock_response({
            "choices": [{"message": {"content": "answer"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 15},
        })
        
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.chat("question", system="be helpful")
        
        assert result["content"] == "answer"
        assert result["finish_reason"] == "stop"
    
    def test_chat_no_choices(self):
        """测试无 choices"""
        client = self._make_client()
        mock_response = self._make_mock_response({
            "choices": [],
            "usage": {},
        })
        
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.chat("question")
        
        assert result["content"] == ""
    
    def test_chat_with_messages(self):
        """测试多消息聊天"""
        client = self._make_client()
        mock_response = self._make_mock_response({
            "choices": [{"message": {"content": "multi"}, "finish_reason": "stop"}],
            "usage": {},
        })
        
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.chat_with_messages([
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "user"},
            ])
        
        assert result["content"] == "multi"
    
    def test_chat_json_success(self):
        """测试 JSON 解析成功"""
        client = self._make_client()
        mock_response = self._make_mock_response({
            "choices": [{"message": {"content": '{"key": "value"}'}, "finish_reason": "stop"}],
            "usage": {},
        })
        
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.chat_json("parse this")
        
        assert result == {"key": "value"}
    
    def test_chat_json_markdown_fence(self):
        """测试 markdown 代码块 JSON"""
        client = self._make_client()
        
        content = '```json\n{"key": "value"}\n```'
        mock_response = self._make_mock_response({
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {},
        })
        
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.chat_json("parse this")
        
        assert result == {"key": "value"}
    
    def test_chat_json_failure(self):
        """测试 JSON 解析失败"""
        client = self._make_client()
        mock_response = self._make_mock_response({
            "choices": [{"message": {"content": "not json"}, "finish_reason": "stop"}],
            "usage": {},
        })
        
        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.chat_json("parse this")
        
        assert "_error" in result
        assert "_raw" in result
    
    def test_hash_prompt(self):
        """测试 prompt 哈希"""
        client = self._make_client()
        h1 = client.hash_prompt("same prompt")
        h2 = client.hash_prompt("same prompt")
        h3 = client.hash_prompt("different")
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 16
    
    def test_get_stats(self):
        """测试统计信息"""
        client = self._make_client()
        stats = client.get_stats()
        assert stats["total_calls"] == 0
        assert stats["total_tokens"] == 0


class TestPromptBuilders:
    """Prompt 构建器测试"""
    
    def test_build_review_prompt_full(self):
        """测试完整审查 prompt"""
        prompt = build_review_prompt(
            prd_text="# 用户出价",
            ir_summary="代码库: 出价服务",
            evidence=[
                {"title": "bid.go", "score": 0.9, "content": "func PlaceBid", "source": "code", "type": "function"},
            ],
            prechecks=[
                {"severity": "high", "description": "缺少幂等性", "suggestion": "添加锁"},
            ],
        )
        assert "CODEBASE CONTEXT" in prompt
        assert "PRE-CHECK RESULTS" in prompt
        assert "EVIDENCE FROM CODEBASE" in prompt
        assert "PRD CONTENT" in prompt
        assert "OUTPUT FORMAT" in prompt
        assert "缺少幂等性" in prompt
    
    def test_build_review_prompt_minimal(self):
        """测试最小输入"""
        prompt = build_review_prompt("测试", "", [], [])
        assert "PRD CONTENT" in prompt
        assert "OUTPUT FORMAT" in prompt
    
    def test_build_review_prompt_without_suggestion(self):
        """测试无建议的 precheck"""
        prompt = build_review_prompt(
            "测试", "", [],
            [{"severity": "info", "description": "提示"}],
        )
        assert "提示" in prompt
    
    def test_build_td_prompt_full(self):
        """测试完整 TD prompt"""
        prompt = build_td_prompt(
            prd_text="# 用户出价",
            review_report="# 审查\n发现 2 个问题",
            ir_summary="代码库摘要",
            diagrams="mermaid 图",
            evidence=[{"title": "bid.go", "content": "出价逻辑"}],
        )
        assert "CODEBASE CONTEXT" in prompt
        assert "PRD REVIEW FINDINGS" in prompt
        assert "RELEVANT CODE EVIDENCE" in prompt
        assert "OUTPUT FORMAT" in prompt
        assert "发现 2 个问题" in prompt
    
    def test_build_td_prompt_minimal(self):
        """测试最小 TD prompt"""
        prompt = build_td_prompt("测试", "", "", "", [])
        assert "OUTPUT FORMAT" in prompt
    
    def test_build_test_prompt_full(self):
        """测试完整测试 prompt"""
        prompt = build_test_prompt(
            prd_text="# 出价功能",
            td_text="# 技术方案",
            ir_summary="摘要",
            routes=[{"method": "POST", "path": "/api/bid", "handler": "PlaceBid"}],
            functions=[{"name": "PlaceBid", "package": "handler", "params": "ctx", "returns": "err"}],
            error_codes=[{"code": "ERR_X", "message": "错误"}],
        )
        assert "ACTUAL ROUTES" in prompt
        assert "KEY FUNCTIONS" in prompt
        assert "ERROR CODES" in prompt
        assert "TECHNICAL DESIGN" in prompt
        assert "OUTPUT FORMAT" in prompt
        assert "/api/bid" in prompt
    
    def test_build_test_prompt_minimal(self):
        """测试最小测试 prompt"""
        prompt = build_test_prompt("测试", "", "", [], [], [])
        assert "OUTPUT FORMAT" in prompt


class TestCreateClient:
    """create_client 工厂测试"""
    
    def test_create_with_kwargs(self):
        """测试 kwargs 创建"""
        client = create_client(api_key="key-1", model="model-1")
        assert client.api_key == "key-1"
        assert client.model == "model-1"
    
    def test_create_with_profile(self):
        """测试 profile 创建"""
        profile = {"profile": {"api_key": "key-2", "model": "model-2"}}
        client = create_client(profile=profile)
        assert client.api_key == "key-2"
        assert client.model == "model-2"
    
    def test_create_with_profile_llm(self):
        """测试 profile llm 配置"""
        profile = {"llm": {"api_key": "key-3", "model": "model-3"}}
        client = create_client(profile=profile)
        assert client.api_key == "key-3"
        assert client.model == "model-3"
    
    def test_create_with_profile_flat(self):
        """测试扁平 profile"""
        profile = {"api_key": "key-4", "model": "model-4"}
        client = create_client(profile=profile)
        assert client.api_key == "key-4"
        assert client.model == "model-4"
