"""
biz-delivery tests conftest — shared fixtures for all engine tests.
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make scripts available on the path so tests can import engines directly
BIZ_DIR = Path(__file__).parent.parent / "scripts"


@pytest.fixture(autouse=True)
def _patch_llm_calls(monkeypatch):
    """Suppress real LLM calls across the entire test suite."""
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "choices": [{"message": {"content": "mocked llm output"}}]
    }
    fake_client = MagicMock()
    fake_client.post.return_value = fake_resp
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr("httpx.Client", fake_client)
    # Clear LLM_API_KEY to prevent real LLM calls, but allow tests to override
    monkeypatch.delenv("LLM_API_KEY", raising=False)

@pytest.fixture(autouse=True)
def _set_agnes_api_key(monkeypatch):
    """Set a fake AGNES_API_KEY so BizDeliveryPipeline can be instantiated."""
    monkeypatch.setenv("AGNES_API_KEY", "fake-test-key")


@pytest.fixture
def tmp_out(tmp_path: Path) -> Path:
    """A clean temporary output directory for each test."""
    d = tmp_path / "output"
    d.mkdir()
    return d


@pytest.fixture
def sample_profile() -> dict:
    """Minimal profile that passes EngineBase validation."""
    return {
        "name": "sample-project",
        "business_domain": "test-domain",
        "repositories": [],
    }


@pytest.fixture
def nested_profile() -> dict:
    """Profile with a nested 'profile' key (as the real code expects)."""
    return {
        "profile": {
            "name": "nested-project",
            "business_domain": "nested-domain",
            "repositories": [],
        }
    }


@pytest.fixture
def sample_prd() -> str:
    return """
# 用户出价功能

## 需求描述
实现一个允许用户对产品进行出价的功能。

## 接口
- POST /api/auction/bid
- GET /api/auction/status

## 业务规则
- 出价金额必须为正数
- 同一用户不能重复出价
"""


@pytest.fixture
def sample_llm_response() -> str:
    return """
# 审查报告

## 合理性检查
- [P0] 缺少幂等性校验
- [P1] 并发控制不足

## 场景遗漏
- [P1] 未考虑网络超时

## 风险评估
整体风险: 中
"""


@pytest.fixture
def sample_test_llm_response() -> str:
    return """
# 测试用例

## 正向流程
| TC001 | 正常出价 | 用户已登录 | 点击出价按钮 | 出价成功 | P0 |
| TC002 | 查询状态 | 无 | 请求状态接口 | 返回当前状态 | P1 |

## 异常分支
| TC003 | 重复出价 | 已出价用户 | 再次出价 | 返回错误 | P0 |

## 边界条件
| TC004 | 空参数 | 无 | 不传参数 | 校验失败 | P1 |
"""


@pytest.fixture
def mock_ir_document():
    """Create a minimal IRDocument for testing."""
    from scripts.learn_repo import IRDocument
    ir = IRDocument(repo_name="test", repo_path="/tmp/test", language="go")
    ir.structs = [
        {"name": "UserBid", "fields": ["user_id", "amount", "product_id"]},
        {"name": "BidRequest", "fields": ["user_id", "amount"]},
    ]
    ir.functions = [
        {"name": "PlaceBid", "params": "ctx, req", "returns": "*Response", "file": "bid.go"},
        {"name": "GetBidStatus", "params": "ctx", "returns": "*StatusResponse", "file": "bid.go"},
    ]
    ir.routes = [
        {"method": "POST", "path": "/api/auction/bid", "handler": "PlaceBid"},
        {"method": "GET", "path": "/api/auction/status", "handler": "GetBidStatus"},
    ]
    ir.error_codes = [
        {"name": "ERR_BID_DUPLICATE", "code": 4001, "message": "重复出价"},
        {"name": "ERR_BID_AMOUNT", "code": 4002, "message": "出价金额无效"},
    ]
    ir.entity_tables = [
        {"entity": "UserBid", "table": "user_bids"},
    ]
    ir.business_logic = [
        {
            "route": "/api/auction/bid",
            "method": "POST",
            "handler": "PlaceBid",
            "description": "用户提交出价",
            "calls": ["ValidateBid", "SaveBid", "NotifyAuction"],
        }
    ]
    ir.core_flows = [
        {
            "flow_name": "出价流程",
            "entry_point": "PlaceBid",
            "call_chain": ["PlaceBid", "ValidateBid", "SaveBid"],
            "data_flow": "request -> validate -> persist -> notify",
            "max_depth": 3,
        }
    ]
    ir.packages = {
        "handlers/bid": {
            "files": ["bid_handler.go"],
            "functions": ["PlaceBid", "GetBidStatus"],
            "structs": {"BidRequest": {}, "BidResponse": {}},
        }
    }
    ir.call_graph = [
        {"caller": "PlaceBid", "callee": "ValidateBid"},
        {"caller": "PlaceBid", "callee": "SaveBid"},
    ]
    ir.test_files = ["bid_handler_test.go"]
    ir.test_functions = [{"name": "TestPlaceBid", "file": "bid_handler_test.go"}]
    ir.coverage_report = {"coverage_pct": 45, "framework": "go test"}
    ir.sql_operations = [
        {"sql_operation": "INSERT", "table": "user_bids", "file": "bid_repo.go"},
    ]
    ir.auth_models = [
        {"middleware": "AuthMiddleware", "logic": "需要登录"},
    ]
    ir.imports = [
        {"module": "gorm.io/gorm"},
        {"module": "github.com/gin-gonic/gin"},
    ]
    return ir


@pytest.fixture
def sample_business_cards(tmp_path: Path) -> Path:
    """Write a business_cards.json to tmp_path for _load_business_cards tests."""
    data = {
        "scenario_cards": [
            {"scenario": "正常出价", "description": "用户成功出价", "call_chain": ["PlaceBid", "ValidateBid"]},
            {"scenario": "重复出价", "description": "用户重复提交", "call_chain": ["PlaceBid"]},
        ],
        "entity_relationships": [
            {"entity": "UserBid", "table": "user_bids"},
        ],
        "error_categories": {
            "业务错误": ["ERR_BID_DUPLICATE", "ERR_BID_AMOUNT"],
            "系统错误": ["ERR_INTERNAL"],
        },
    }
    bc_file = tmp_path / "business_cards.json"
    bc_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return bc_file
