#!/usr/bin/env python3
"""Evaluation harness for biz-delivery engines.

Provides automated testing of PRD review accuracy, TD quality, and test case coverage.

Usage:
    python3 evaluate.py --mode review --profile profiles/my-service.json --output-dir eval/results
    python3 evaluate.py --mode td --profile profiles/my-service.json --output-dir eval/results
    python3 evaluate.py --mode test --profile profiles/my-service.json --output-dir eval/results
    python3 evaluate.py --mode full --profile profiles/my-service.json --output-dir eval/results
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Sample PRDs for evaluation ──────────────────────────────

SAMPLE_PRDS = {
    "new_feature": """
# 新增广告组批量导入功能

## 需求描述
支持通过 CSV/Excel 文件批量导入广告组数据，包括：
- 广告组名称、预算、出价策略
- 定向设置（地域、年龄、性别）
- 状态默认为草稿

## 业务流程
1. 用户选择文件上传
2. 系统解析文件格式并校验数据
3. 对每条记录进行业务规则校验
4. 批量创建广告组，返回成功/失败统计
5. 生成导入报告供下载

## 性能要求
- 支持单次导入最多 10000 条记录
- QPS 要求：100 QPS
- 需要 Redis 缓存导入进度

## 权限要求
- 仅广告主角色可操作
- 需要审核通过后才能上线

## 错误处理
- 文件格式错误：返回具体行号和错误原因
- 业务规则校验失败：跳过该条记录，继续处理其他记录
- 系统异常：记录日志，通知管理员
""",

    "enhancement": """
# 素材审核流程优化

## 需求描述
优化现有素材审核流程，增加以下功能：
- 支持多级审核（初审 → 复审 → 终审）
- 审核意见模板化
- 审核超时自动提醒

## 兼容性要求
- 不影响现有单级审核流程
- 旧素材继续使用原审核流程
- 新素材可选择审核级别

## 接口变更
- POST /api/v1/creative/review 增加 level 参数
- GET /api/v1/creative/{id}/audit-log 新增审核日志查询

## 数据变更
- creative_audit_log 表新增 audit_level 字段
""",

    "high_risk_change": """
# 核心竞价引擎重构

## 需求描述
对现有竞价引擎进行全面重构，提升性能和可扩展性：
- 引入异步事件驱动架构
- 支持多策略竞价（实时竞价、预留竞价、优先竞价）
- 引入消息队列解耦各组件

## 性能目标
- 当前 P99 延迟 50ms，目标降至 10ms
- 支持 10000 QPS
- 引入 Redis 缓存热点数据

## 风险说明
这是核心功能重大变更，需要：
- Feature Flag 控制灰度发布
- 完整的回滚方案
- 双写策略保证数据一致性
""",
}


# ── Evaluation Metrics ──────────────────────────────────────

class ReviewEvaluator:
    """Evaluate PRD review engine output quality."""
    
    def __init__(self, profile: dict, output_dir: str):
        self.profile = profile
        self.output_dir = Path(output_dir)
        self.results: List[Dict] = []
    
    def evaluate(self, prd_key: Optional[str] = None) -> Dict[str, Any]:
        """Run evaluation on sample PRDs."""
        keys = [prd_key] if prd_key else list(SAMPLE_PRDS.keys())
        
        overall = {
            "total_tests": len(keys),
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "details": [],
        }
        
        for key in keys:
            prd_text = SAMPLE_PRDS[key]
            result = self._evaluate_single(key, prd_text)
            overall["details"].append(result)
            
            if result["status"] == "pass":
                overall["passed"] += 1
            elif result["status"] == "warn":
                overall["warnings"] += 1
            else:
                overall["failed"] += 1
        
        return overall
    
    def _evaluate_single(self, prd_key: str, prd_text: str) -> Dict:
        """Evaluate a single PRD through the review pipeline."""
        start_time = time.time()
        
        # Step 1: Run review engine
        from review_engine import ReviewEngine
        
        review_output = self.output_dir / f"review_{prd_key}"
        review_output.mkdir(parents=True, exist_ok=True)
        
        try:
            engine = ReviewEngine(self.profile, str(review_output))
            review_result = engine.review(prd_text)
            
            # Check that prompt was generated
            prompt_file = Path(review_result.get("prompt_file", ""))
            if not prompt_file.exists():
                return {
                    "prd": prd_key,
                    "status": "fail",
                    "error": "Review prompt file not generated",
                    "duration": time.time() - start_time,
                }
            
            prompt_content = prompt_file.read_text(encoding="utf-8")
            
            # Step 2: Evaluate prompt quality
            checks = self._check_prompt_quality(prompt_content, prd_text)
            
            status = "pass"
            for check in checks:
                if check["severity"] == "critical":
                    status = "fail"
                    break
                elif check["severity"] == "warning" and status != "fail":
                    status = "warn"
            
            return {
                "prd": prd_key,
                "status": status,
                "checks": checks,
                "prompt_length": len(prompt_content),
                "duration": time.time() - start_time,
            }
            
        except Exception as e:
            return {
                "prd": prd_key,
                "status": "fail",
                "error": str(e),
                "duration": time.time() - start_time,
            }
    
    def _check_prompt_quality(self, prompt: str, prd_text: str) -> List[Dict]:
        """Check that the review prompt contains essential sections."""
        checks = []
        
        # Check for codebase summary
        if "代码库摘要" in prompt:
            checks.append({"name": "has_codebase_summary", "severity": "info"})
        else:
            checks.append({"name": "missing_codebase_summary", "severity": "critical"})
        
        # Check for routes section
        if "关键路由" in prompt or "Routes" in prompt:
            checks.append({"name": "has_routes_section", "severity": "info"})
        else:
            checks.append({"name": "missing_routes_section", "severity": "warning"})
        
        # Check for business logic section
        if "业务逻辑" in prompt or "Business Logic" in prompt:
            checks.append({"name": "has_business_logic", "severity": "info"})
        else:
            checks.append({"name": "missing_business_logic", "severity": "warning"})
        
        # Check for evidence section
        if "证据" in prompt or "evidence" in prompt.lower():
            checks.append({"name": "has_evidence", "severity": "info"})
        else:
            checks.append({"name": "missing_evidence", "severity": "warning"})
        
        # Check for prechecks section
        if "预检" in prompt or "precheck" in prompt.lower():
            checks.append({"name": "has_prechecks", "severity": "info"})
        else:
            checks.append({"name": "missing_prechecks", "severity": "warning"})
        
        # Check for review rules
        if "审查规则" in prompt or "review rules" in prompt.lower():
            checks.append({"name": "has_review_rules", "severity": "info"})
        else:
            checks.append({"name": "missing_review_rules", "severity": "critical"})
        
        # Check for output format
        if "输出格式" in prompt or "output format" in prompt.lower():
            checks.append({"name": "has_output_format", "severity": "info"})
        else:
            checks.append({"name": "missing_output_format", "severity": "warning"})
        
        return checks


class TDEvaluator:
    """Evaluate Technical Design generation quality."""
    
    def __init__(self, profile: dict, output_dir: str):
        self.profile = profile
        self.output_dir = Path(output_dir)
    
    def evaluate(self, prd_key: Optional[str] = None) -> Dict[str, Any]:
        """Run evaluation on sample PRDs."""
        keys = [prd_key] if prd_key else list(SAMPLE_PRDS.keys())[:2]
        
        overall = {"total": len(keys), "passed": 0, "failed": 0, "details": []}
        
        for key in keys:
            prd_text = SAMPLE_PRDS[key]
            result = self._evaluate_single(key, prd_text)
            overall["details"].append(result)
            if result.get("status") == "pass":
                overall["passed"] += 1
            else:
                overall["failed"] += 1
        
        return overall
    
    def _evaluate_single(self, prd_key: str, prd_text: str) -> Dict:
        """Evaluate a single PRD through the TD pipeline."""
        start_time = time.time()
        
        from td_engine import TDEngine
        
        td_output = self.output_dir / f"td_{prd_key}"
        td_output.mkdir(parents=True, exist_ok=True)
        
        try:
            engine = TDEngine(self.profile, str(td_output))
            td_result = engine.generate_td(prd_text)
            
            prompt_file = Path(td_result.get("prompt_file", ""))
            if not prompt_file.exists():
                return {"prd": prd_key, "status": "fail", "error": "TD prompt not generated"}
            
            content = prompt_file.read_text(encoding="utf-8")
            
            # Check TD prompt quality
            checks = []
            required_sections = ["架构设计", "接口设计", "数据库设计", "流程图", "风险评估"]
            for section in required_sections:
                if section in content:
                    checks.append(f"has_{section}")
                else:
                    checks.append(f"missing_{section}")
            
            has_mermaid = "mermaid" in content.lower()
            if has_mermaid:
                checks.append("has_mermaid_diagrams")
            else:
                checks.append("missing_mermaid_diagrams")
            
            status = "pass" if all("missing" not in c for c in checks) else "warn"
            
            return {
                "prd": prd_key,
                "status": status,
                "checks": checks,
                "prompt_length": len(content),
                "duration": time.time() - start_time,
            }
            
        except Exception as e:
            return {
                "prd": prd_key,
                "status": "fail",
                "error": str(e),
            }


class TestEvaluator:
    """Evaluate test case generation quality."""
    
    def __init__(self, profile: dict, output_dir: str):
        self.profile = profile
        self.output_dir = Path(output_dir)
    
    def evaluate(self, prd_key: Optional[str] = None) -> Dict[str, Any]:
        """Run evaluation on sample PRDs."""
        keys = [prd_key] if prd_key else list(SAMPLE_PRDS.keys())[:2]
        
        overall = {"total": len(keys), "passed": 0, "failed": 0, "details": []}
        
        for key in keys:
            prd_text = SAMPLE_PRDS[key]
            result = self._evaluate_single(key, prd_text)
            overall["details"].append(result)
            if result.get("status") == "pass":
                overall["passed"] += 1
            else:
                overall["failed"] += 1
        
        return overall
    
    def _evaluate_single(self, prd_key: str, prd_text: str) -> Dict:
        """Evaluate a single PRD through the test pipeline."""
        start_time = time.time()
        
        from test_engine import TestEngine
        
        test_output = self.output_dir / f"test_{prd_key}"
        test_output.mkdir(parents=True, exist_ok=True)
        
        try:
            engine = TestEngine(self.profile, str(test_output))
            test_result = engine.generate_tests(prd_text)
            
            prompt_file = Path(test_result.get("prompt_file", ""))
            if not prompt_file.exists():
                return {"prd": prd_key, "status": "fail", "error": "Test prompt not generated"}
            
            content = prompt_file.read_text(encoding="utf-8")
            
            # Check test prompt quality
            checks = []
            required_sections = ["正向流程", "异常分支", "边界条件", "安全测试"]
            for section in required_sections:
                if section in content:
                    checks.append(f"has_{section}")
                else:
                    checks.append(f"missing_{section}")
            
            has_error_codes = "错误码" in content or "error_code" in content.lower()
            if has_error_codes:
                checks.append("has_error_codes")
            else:
                checks.append("missing_error_codes")
            
            has_structs = "Struct" in content or "struct" in content.lower()
            if has_structs:
                checks.append("has_struct_info")
            else:
                checks.append("missing_struct_info")
            
            status = "pass" if all("missing" not in c for c in checks) else "warn"
            
            return {
                "prd": prd_key,
                "status": status,
                "checks": checks,
                "prompt_length": len(content),
                "duration": time.time() - start_time,
            }
            
        except Exception as e:
            return {
                "prd": prd_key,
                "status": "fail",
                "error": str(e),
            }


def run_evaluation(mode: str, profile_path: str, output_dir: str, prd_key: Optional[str] = None) -> Dict:
    """Run full evaluation pipeline."""
    # Load profile
    with open(profile_path) as f:
        profile = json.load(f)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    if mode in ("review", "full"):
        print("\n📋 Evaluating PRD Review Engine...")
        evaluator = ReviewEvaluator(profile, str(output_path / "review"))
        results["review"] = evaluator.evaluate(prd_key)
        print(f"   Status: {results['review']['passed']}/{results['review']['total']} passed")
    
    if mode in ("td", "full"):
        print("\n🏗️  Evaluating TD Engine...")
        evaluator = TDEvaluator(profile, str(output_path / "td"))
        results["td"] = evaluator.evaluate(prd_key)
        print(f"   Status: {results['td']['passed']}/{results['td']['total']} passed")
    
    if mode in ("test", "full"):
        print("\n🧪 Evaluating Test Engine...")
        evaluator = TestEvaluator(profile, str(output_path / "test"))
        results["test"] = evaluator.evaluate(prd_key)
        print(f"   Status: {results['test']['passed']}/{results['test']['total']} passed")
    
    # Save results
    results_file = output_path / "evaluation_results.json"
    results_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✅ Results saved to: {results_file}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Biz-Delivery Evaluation Harness")
    parser.add_argument("--mode", choices=["review", "td", "test", "full"], default="full")
    parser.add_argument("--profile", required=True, help="Profile JSON path")
    parser.add_argument("--output-dir", required=True, help="Output directory for results")
    parser.add_argument("--prd", help="Specific PRD key to test (new_feature/enhancement/high_risk_change)")
    
    args = parser.parse_args()
    
    results = run_evaluation(args.mode, args.profile, args.output_dir, args.prd)
    
    # Print summary
    total_tests = sum(r.get("total", 0) for r in results.values())
    total_passed = sum(r.get("passed", 0) for r in results.values())
    
    print(f"\n{'='*60}")
    print(f"EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {total_passed}")
    print(f"Failed/Warn: {total_tests - total_passed}")
    
    for mode, result in results.items():
        passed = result.get("passed", 0)
        total = result.get("total", 0)
        pct = (passed / total * 100) if total > 0 else 0
        print(f"  {mode}: {passed}/{total} ({pct:.0f}%)")
    
    # Exit with error if any critical failures
    has_critical = False
    for mode, result in results.items():
        for detail in result.get("details", []):
            if detail.get("status") == "fail":
                has_critical = True
                print(f"\n❌ CRITICAL: {mode}/{detail.get('prd')} failed: {detail.get('error', 'unknown')}")
    
    sys.exit(1 if has_critical else 0)


if __name__ == "__main__":
    main()
