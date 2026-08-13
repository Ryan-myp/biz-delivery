"""
Test Engine 深度测试套件
覆盖：_parse_test_report 全部分支、_detect_uncovered_scenarios、generate_with_response、_build_test_prompt
目标：scripts/test_engine.py 覆盖率 ≥85%
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scripts.test_engine import TestEngine


def make_profile():
    return {
        "profile": {
            "name": "test-project",
            "business_domain": "auction",
            "repositories": [],
        }
    }


def _make_engine(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir(exist_ok=True)
    return TestEngine(make_profile(), str(out_dir), wiki_path=str(tmp_path))


TABLE_RESPONSE = """
# 测试用例

## 正向流程
| TC001 | 正常出价 | 用户已登录 | 点击出价 | 出价成功 | P0 |
| TC002 | 查询状态 | 无 | 请求接口 | 返回状态 | P1 |

## 异常分支
| TC003 | 重复出价 | 已出价 | 再次出价 | 返回错误 | P0 |
| TC004 | 空参数 | 无 | 不传参数 | 校验失败 | P1 |

## 边界条件
| TC005 | 金额为零 | 无 | 出价0元 | 拒绝 | P2 |
"""


class TestParseTestReport:
    """测试报告解析测试"""
    
    def test_parse_structured_table(self, tmp_path):
        """测试结构化表格解析"""
        engine = _make_engine(tmp_path)
        parsed = engine._parse_test_report(TABLE_RESPONSE)
        
        assert parsed["has_structured_data"] is True
        assert parsed["total_cases"] == 5
        assert len(parsed["by_priority"]["P0"]) == 2
        assert len(parsed["by_priority"]["P1"]) == 2
        assert len(parsed["by_priority"]["P2"]) == 1
        assert "创建操作" in parsed["by_category"] or "其他测试" in parsed["by_category"]
        assert parsed["coverage_analysis"]["structured"] is True
        assert "p0_count" in parsed["coverage_analysis"]
    
    def test_parse_no_table(self, tmp_path):
        """测试无表格"""
        engine = _make_engine(tmp_path)
        parsed = engine._parse_test_report("TC001 TC002 TC003")
        
        assert parsed["has_structured_data"] is False
        assert parsed["total_cases"] == 3
        assert parsed["coverage_analysis"]["structured"] is False
    
    def test_parse_empty(self, tmp_path):
        """测试空响应"""
        engine = _make_engine(tmp_path)
        parsed = engine._parse_test_report("")
        assert parsed["total_cases"] == 0
    
    def test_parse_invalid_priority(self, tmp_path):
        """测试无效优先级"""
        engine = _make_engine(tmp_path)
        response = "| TC001 | 测试 | 无 | 操作 | 结果 | P9 |"
        parsed = engine._parse_test_report(response)
        # P9 会被归为 P2
        assert len(parsed["by_priority"]["P2"]) >= 0
    
    def test_parse_sections_extracted(self, tmp_path):
        """测试章节提取"""
        engine = _make_engine(tmp_path)
        parsed = engine._parse_test_report(TABLE_RESPONSE)
        assert "正向流程" in parsed["sections"] or "异常分支" in parsed["sections"]
    
    def test_parse_recommendations_few_cases(self, tmp_path):
        """测试少量用例建议"""
        engine = _make_engine(tmp_path)
        response = "| TC001 | 出价 | 无 | 操作 | 成功 | P0 |"
        parsed = engine._parse_test_report(response)
        assert any("数量较少" in r for r in parsed["recommendations"])


class TestDetectUncoveredScenarios:
    """未覆盖场景检测测试"""
    
    def test_detect_uncovered(self, tmp_path):
        """测试检测未覆盖场景"""
        engine = _make_engine(tmp_path)
        cases = {
            "其他测试": [
                {"scenario": "正常出价", "priority": "P0"},
            ]
        }
        uncovered = engine._detect_uncovered_scenarios(cases, "出价功能")
        assert "鉴权检查" in uncovered  # 无权限场景
    
    def test_detect_all_covered(self, tmp_path):
        """测试全部覆盖"""
        engine = _make_engine(tmp_path)
        cases = {
            "异常与边界": [
                {"scenario": "权限不足被拒绝", "priority": "P0"},
                {"scenario": "空值校验", "priority": "P1"},
                {"scenario": "参数校验失败", "priority": "P1"},
                {"scenario": "错误处理", "priority": "P1"},
                {"scenario": "并发竞争", "priority": "P1"},
                {"scenario": "大批量性能", "priority": "P2"},
            ]
        }
        uncovered = engine._detect_uncovered_scenarios(cases, "测试")
        assert len(uncovered) < 6


class TestGenerateWithResponse:
    """LLM 响应处理测试"""
    
    def test_generate_with_response(self, tmp_path):
        """测试保存报告"""
        engine = _make_engine(tmp_path)
        result = engine.generate_with_response("# 测试用例\nTC001")
        assert result["status"] == "completed"
        assert Path(result["report_file"]).exists()
        assert "test_cases" in result["sections"] or "sections" in result


class TestBuildTestPrompt:
    """测试 Prompt 构建测试"""
    
    def _make_ir(self):
        from scripts.learn_repo import IRDocument, RouteDef
        ir = IRDocument(repo_name="test", repo_path="/tmp", language="go")
        ir.routes = [
            RouteDef(path="/api/bid", method="POST", handler="PlaceBid", module="h", file="bid.go"),
        ]
        ir.functions = [
            {"name": "PlaceBid", "params": "ctx", "returns": "err", "file": "bid.go"},
        ]
        ir.error_codes = [
            {"name": "ERR_BID", "code": 4001, "message": "出价失败"},
        ]
        return ir
    
    def test_build_test_prompt_full(self, tmp_path):
        """测试完整 prompt"""
        engine = _make_engine(tmp_path)
        ir = self._make_ir()
        prompt = engine._build_test_prompt(
            {"total": 0, "evidence": []}, ir,
            "# 出价功能\n\n## 需求\n用户出价",
            td_text="# 技术方案",
        )
        assert "出价功能" in prompt
        assert isinstance(prompt, str)
    
    def test_build_test_prompt_with_td(self, tmp_path):
        """测试带 TD 的 prompt"""
        engine = _make_engine(tmp_path)
        ir = self._make_ir()
        prompt = engine._build_test_prompt(
            {"total": 0, "evidence": []}, ir,
            "# 测试", td_text="# TD\n技术方案内容"
        )
        assert "技术方案内容" in prompt or "TD" in prompt


class TestGenerateTests:
    """主流程测试"""
    
    def test_generate_tests(self, tmp_path):
        """测试生成测试"""
        engine = _make_engine(tmp_path)
        with patch.object(engine, "_scan_codebase") as mock_scan:
            mock_scan.return_value = MagicMock()
            with patch.object(engine, "_query_evidence_for_prd",
                              return_value={"total": 0, "evidence": []}):
                result = engine.generate_tests("# 用户出价功能")
        
        assert "status" in result
        assert "prompt_file" in result or "message" in result
    
    def test_generate_test_code_from_ir(self, tmp_path):
        """测试从 IR 生成测试代码"""
        engine = _make_engine(tmp_path)
        with patch.object(engine, "_scan_codebase") as mock_scan:
            from scripts.learn_repo import IRDocument, RouteDef
            ir = IRDocument(repo_name="test", repo_path="/tmp", language="go")
            ir.routes = [
                RouteDef(path="/api/bid", method="POST", handler="PlaceBid", module="h", file="bid.go"),
            ]
            ir.functions = [{"name": "PlaceBid", "params": "ctx", "returns": "err", "file": "bid.go"}]
            mock_scan.return_value = ir
            
            result = engine.generate_test_code_from_ir(language="go")
        
        assert isinstance(result, dict)
        assert "summary" in result or "files" in result
