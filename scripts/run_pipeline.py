#!/usr/bin/env python3
"""端到端流水线 — 支持 learn、prdtdd、auto 和 eval 四种模式

Usage:
    # learn 模式：代码 -> 知识库
    python3 run_pipeline.py --profile profiles/my-service.json --mode learn --output-dir knowledge/my-service

    # prdtdd 模式：PRD -> 评审 -> TD -> 测试（生成 prompt 文件，需手动调用 LLM）
    python3 run_pipeline.py --profile profiles/my-service.json --mode prdtdd --text "<PRD内容>" --output-dir delivery/my-feature

    # 串联模式：先 learn 再 prdtdd
    python3 run_pipeline.py --profile profiles/my-service.json --mode learn,prdtdd --text "<PRD内容>" --output-dir delivery/my-feature

    # auto 模式：PRD -> LLM 自动审查 -> TD -> 测试（全自动，无需手动调用 LLM）
    python3 run_pipeline.py --profile profiles/my-service.json --mode auto --text "<PRD内容>" --output-dir delivery/my-feature

    # eval 模式：评估审查准确性
    python3 run_pipeline.py --profile profiles/my-service.json --mode eval --output-dir evaluation/results
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Top-level imports for pipeline functions
from learn_repo import learn_from_repos
from llm_client import LLMClient
from review_engine import ReviewEngine
from td_engine import TDEngine
from test_engine import TestEngine


def load_profile(profile_path: str) -> dict:
    """加载 Profile 配置"""
    with open(profile_path) as f:
        return json.load(f)


def run_learn_mode(profile_path: str, output_dir: str, wiki_path: Optional[str] = None,
                   incremental: bool = False, module_filter: Optional[str] = None,
                   max_files: Optional[int] = None) -> dict:
    """执行 learn 模式

    Args:
        incremental: 如果为 True，使用 FileCache 只做增量扫描（跳过未变更文件）
        module_filter: 只扫描指定模块（如 "share"、"adgroup"）
        max_files: 每个仓库最大扫描文件数（覆盖 profile 配置）
    """

    result = learn_from_repos(
        profile_path=profile_path,
        output_dir=output_dir,
        wiki_path=wiki_path,
        incremental=incremental,
        module_filter=module_filter,
        max_files=max_files,
    )
    return result


def run_auto_mode(profile: dict, prd_text: str, output_dir: str, wiki_path: Optional[str] = None,
                  module_filter: str = None, max_files: int = None) -> dict:
    """执行 auto 模式 — PRD -> LLM 自动审查 -> TD -> 测试（全自动）
    
    与 prdtdd 模式不同，auto 模式会直接调用 LLM API 完成每个阶段，
    而不是只生成 prompt 文件。
    """
    os.makedirs(output_dir, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).parent))
    
    
    # 推断 kb_dir（所有引擎共享同一个知识库目录）
    kb_dir = None
    for repo in profile.get("repositories", []):
        rp = Path(repo.get("path", ""))
        if rp.exists():
            kb = Path(rp.parent) / "knowledge" / profile.get("business_domain", "unknown")
            if kb.exists():
                kb_dir = str(kb)
                break
    
    results = {}
    
    # Initialize LLM client
    try:
        llm_client = LLMClient()
        print(f"✅ LLM client initialized (model={llm_client.model})")
    except ValueError as e:
        print(f"❌ Failed to initialize LLM client: {e}")
        print("   Set AGNES_API_KEY environment variable or configure in profile")
        return {"status": "error", "message": str(e)}
    
    # Stage 1: PRD 审查（自动调用 LLM）
    print("\n📋 Stage 1: PRD Review (Auto)")
    review_engine = ReviewEngine(profile, output_dir, wiki_path,
                                 module_filter=module_filter, max_files=max_files)
    review_result = review_engine.review(prd_text)
    
    # 检查是否已有 LLM 生成的报告
    report_file = os.path.join(output_dir, "review_report.md")
    if os.path.exists(report_file):
        llm_report = Path(report_file).read_text(encoding="utf-8")
        if len(llm_report) > 100:
            parsed = review_engine._parse_review_report(llm_report)
            results["review"] = {
                "status": "completed",
                "report_file": report_file,
                "parsed": parsed,
                "source": "existing_report",
            }
            print(f"  ✅ Using existing review report ({len(llm_report)} chars)")
        else:
            review_engine.review_with_response(review_result.get("prompt_file", ""))
    else:
        # 调用 LLM 自动审查
        prompt_file = review_result.get("prompt_file")
        if not prompt_file or not Path(prompt_file).exists():
            print("  ⚠️  No prompt file generated, skipping LLM call")
            results["review"] = {"status": "skipped", "message": "No prompt available"}
        else:
            prompt_content = Path(prompt_file).read_text(encoding="utf-8")
            print(f"  🤖 Calling LLM for review ({len(prompt_content)} chars)...")
            
            system_prompt = """You are a senior software architect reviewing a Product Requirements Document (PRD) against the existing codebase.
Focus on: correctness, completeness, feasibility, risk, compatibility, performance, security.
Output your review in Markdown format with P0/P1/P2 priority levels."""
            
            try:
                llm_response = llm_client.chat(prompt_content, system=system_prompt)
                llm_content = llm_response.get("content", "")
                
                if llm_content:
                    review_engine.review_with_response(llm_content, prompt_file)
                    parsed = review_engine._parse_review_report(llm_content)
                    results["review"] = {
                        "status": "completed",
                        "report_file": report_file,
                        "parsed": parsed,
                        "source": "llm_auto",
                        "tokens_used": llm_response.get("usage", {}).get("total_tokens", 0),
                    }
                    print(f"  ✅ Review completed ({len(llm_content)} chars, {parsed.get('p0_issues', [])} P0 issues)")
                else:
                    results["review"] = {"status": "error", "message": "Empty LLM response"}
                    print("  ❌ Empty LLM response")
            except Exception as e:
                results["review"] = {"status": "error", "message": str(e)}
                print(f"  ❌ LLM call failed: {e}")
    
    # Stage 2: 技术方案生成（自动调用 LLM）
    print("\n📋 Stage 2: Technical Design (Auto)")
    td_engine = TDEngine(profile, output_dir, wiki_path,
                         module_filter=module_filter, max_files=max_files)
    td_result = td_engine.generate_td(prd_text=prd_text)
    
    # Check for existing TD
    td_report_file = os.path.join(output_dir, "technical_design.md")
    if os.path.exists(td_report_file):
        td_content = Path(td_report_file).read_text(encoding="utf-8")
        if len(td_content) > 100:
            results["td"] = {"status": "completed", "report_file": td_report_file, "source": "existing"}
            print(f"  ✅ Using existing technical design ({len(td_content)} chars)")
        else:
            _call_llm_for_td(td_engine, llm_client, prd_text, results, output_dir)
    else:
        _call_llm_for_td(td_engine, llm_client, prd_text, results, output_dir)
    
    # Stage 3: 测试用例生成（自动调用 LLM）
    print("\n📋 Stage 3: Test Cases (Auto)")
    test_engine = TestEngine(profile, output_dir, wiki_path,
                             module_filter=module_filter, max_files=max_files)
    test_result = test_engine.generate_tests(prd_text=prd_text)
    
    # Check for existing test cases
    test_report_file = os.path.join(output_dir, "test_cases.md")
    if os.path.exists(test_report_file):
        test_content = Path(test_report_file).read_text(encoding="utf-8")
        if len(test_content) > 100:
            results["test"] = {"status": "completed", "report_file": test_report_file, "source": "existing"}
            print(f"  ✅ Using existing test cases ({len(test_content)} chars)")
        else:
            _call_llm_for_tests(test_engine, llm_client, prd_text, results, output_dir)
    else:
        _call_llm_for_tests(test_engine, llm_client, prd_text, results, output_dir)
    
    return {
        "status": "completed",
        "results": results,
        "stages_executed": ["review", "td", "test"],
    }


def _safe_llm_call(llm_client, prompt_content: str, system_prompt: str, max_retries: int = 2) -> Optional[dict]:
    """安全调用 LLM API，带重试和错误处理。
    
    Args:
        llm_client: LLMClient 实例
        prompt_content: 提示词内容
        system_prompt: 系统提示词
        max_retries: 最大重试次数
        
    Returns:
        {content, usage} dict or None on failure
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = llm_client.chat(prompt_content, system=system_prompt)
            content = response.get("content", "")
            if content and len(content.strip()) > 50:
                return response
            last_error = f"Empty or too short response ({len(content)} chars)"
        except Exception as e:
            last_error = str(e)
        
        if attempt < max_retries:
            wait_time = (attempt + 1) * 2  # 2s, 4s exponential backoff
            print(f"  ⏳ Retry {attempt+1}/{max_retries} in {wait_time}s... (error: {last_error[:80]})")
            time.sleep(wait_time)
    
    return None


def _call_llm_for_review(review_engine, llm_client, prd_text, results, output_dir):
    """调用 LLM 审查 PRD（带重试）"""
    prompt_file = review_engine.output_dir / "review_prompt.md"
    if not prompt_file.exists():
        results["review"] = {"status": "skipped", "message": "No review prompt available"}
        return
    
    prompt_content = prompt_file.read_text(encoding="utf-8")
    print(f"  🤖 Calling LLM for review ({len(prompt_content)} chars)...")
    
    system_prompt = """You are a senior software architect reviewing a Product Requirements Document (PRD) against the existing codebase.
Focus on: correctness, completeness, feasibility, risk, compatibility, performance, security.
Output your review in Markdown format with P0/P1/P2 priority levels."""
    
    response = _safe_llm_call(llm_client, prompt_content, system_prompt)
    if response:
        llm_content = response.get("content", "")
        review_engine.review_with_response(llm_content, str(prompt_file))
        parsed = review_engine._parse_review_report(llm_content)
        results["review"] = {
            "status": "completed",
            "report_file": os.path.join(output_dir, "review_report.md"),
            "parsed": parsed,
            "source": "llm_auto",
            "tokens_used": response.get("usage", {}).get("total_tokens", 0),
        }
        p0_count = len(parsed.get('p0_issues', []))
        print(f"  ✅ Review completed ({len(llm_content)} chars, {p0_count} P0 issues)")
    else:
        results["review"] = {"status": "error", "message": f"LLM call failed after retries: {str(response) if response else 'unknown'}"}
        print(f"  ❌ Review generation failed after retries")


def _call_llm_for_td(td_engine, llm_client, prd_text, results, output_dir):
    """调用 LLM 生成技术方案（带重试）"""
    prompt_file = td_engine.output_dir / "td_prompt.md"
    if not prompt_file.exists():
        results["td"] = {"status": "skipped", "message": "No TD prompt available"}
        return
    
    prompt_content = prompt_file.read_text(encoding="utf-8")
    print(f"  🤖 Calling LLM for TD ({len(prompt_content)} chars)...")
    
    system_prompt = """You are a senior software architect. Generate a comprehensive Technical Design Document based on the PRD and codebase structure.
Include: architecture design, interface design, database design, data migration plan, mermaid diagrams."""
    
    response = _safe_llm_call(llm_client, prompt_content, system_prompt)
    if response:
        llm_content = response.get("content", "")
        td_engine.generate_with_response(llm_content)
        results["td"] = {
            "status": "completed",
            "report_file": str(td_engine.output_dir / "technical_design.md"),
            "source": "llm_auto",
            "tokens_used": response.get("usage", {}).get("total_tokens", 0),
        }
        print(f"  ✅ TD generated ({len(llm_content)} chars)")
    else:
        results["td"] = {"status": "error", "message": "LLM call failed after retries"}
        print(f"  ❌ TD generation failed after retries")


def _call_llm_for_tests(test_engine, llm_client, prd_text, results, output_dir):
    """调用 LLM 生成测试用例（带重试）"""
    prompt_file = test_engine.output_dir / "test_prompt.md"
    if not prompt_file.exists():
        results["test"] = {"status": "skipped", "message": "No test prompt available"}
        return
    
    prompt_content = prompt_file.read_text(encoding="utf-8")
    print(f"  🤖 Calling LLM for tests ({len(prompt_content)} chars)...")
    
    system_prompt = """You are a senior QA engineer. Generate comprehensive test cases based on the PRD and technical design.
Include: positive flows, exception handling, boundary conditions, state transitions, security tests."""
    
    response = _safe_llm_call(llm_client, prompt_content, system_prompt)
    if response:
        llm_content = response.get("content", "")
        test_engine.generate_with_response(llm_content)
        results["test"] = {
            "status": "completed",
            "report_file": str(test_engine.output_dir / "test_cases.md"),
            "source": "llm_auto",
            "tokens_used": response.get("usage", {}).get("total_tokens", 0),
        }
        print(f"  ✅ Test cases generated ({len(llm_content)} chars)")
    else:
        results["test"] = {"status": "error", "message": "LLM call failed after retries"}
        print(f"  ❌ Test generation failed after retries")


def run_prdtdd_mode(profile: dict, prd_text: str, output_dir: str, stages: list = None,
                    wiki_path: str = None, module_filter: str = None,
                    max_files: int = None) -> dict:
    """执行 prdtdd 模式 — 支持阶段间数据传递

    串联逻辑：
    - review → td: TD 接收审查报告（review_report 参数）
    - td → test: Test 接收 TD 内容（td_text 参数）
    - 每个阶段复用同一个 kb_dir，避免重复扫描
    - 自动检测 LLM 响应文件（review_report.md / technical_design.md / test_cases.md）
      如果存在，自动读取并传递给下一阶段
    """
    os.makedirs(output_dir, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).parent))

    # 推断 kb_dir（所有引擎共享同一个知识库目录）
    kb_dir = None
    for repo in profile.get("repositories", []):
        rp = Path(repo.get("path", ""))
        if rp.exists():
            kb = Path(rp.parent) / "knowledge" / profile.get("business_domain", "unknown")
            if kb.exists():
                kb_dir = str(kb)
                break

    stages = stages or ["review", "td", "test"]
    results = {}
    prev_context = None  # 前一个阶段的上下文（prompt 或 report）
    prev_stage = None    # 上一个执行的阶段名，用于自动检测 LLM 输出

    # Stage 1: PRD 审查
    if "review" in stages:
        print("\n📋 Stage 1: PRD Review")
        review_engine = ReviewEngine(profile, output_dir, wiki_path,
                                     module_filter=module_filter, max_files=max_files)
        review_result = review_engine.review(prd_text)
        results["review"] = review_result
        
        # 读取审查 prompt 文件，作为后续阶段的上下文
        prompt_file = review_result.get("prompt_file")
        if prompt_file and Path(prompt_file).exists():
            prev_context = Path(prompt_file).read_text(encoding="utf-8")
            print(f"  ✅ Review prompt saved ({len(prev_context)} chars)")
        
        # 自动检测：如果 LLM 已经生成了 review_report.md，优先使用
        report_file = os.path.join(output_dir, "review_report.md")
        if os.path.exists(report_file):
            llm_report = Path(report_file).read_text(encoding="utf-8")
            if len(llm_report) > 100:
                prev_context = llm_report
                print(f"  ✅ LLM review_report detected ({len(prev_context)} chars)")
        
        print(f"  Status: {review_result['status']}")
        if review_result.get("prompt_file"):
            print(f"  Prompt: {review_result['prompt_file']}")
        prev_stage = "review"
    
    # Stage 2: 技术方案生成（接收 review 报告）
    if "td" in stages:
        print("\n📋 Stage 2: Technical Design")
        td_engine = TDEngine(profile, output_dir, wiki_path,
                             module_filter=module_filter, max_files=max_files)
        
        # 如果有审查报告，注入给 TD
        td_kwargs = {"prd_text": prd_text}
        if prev_context:
            td_kwargs["review_report"] = prev_context
        
        td_result = td_engine.generate_td(**td_kwargs)
        results["td"] = td_result
        
        # 读取 TD prompt 文件，作为后续阶段的上下文
        prompt_file = td_result.get("prompt_file")
        if prompt_file and Path(prompt_file).exists():
            prev_context = Path(prompt_file).read_text(encoding="utf-8")
            print(f"  ✅ TD prompt saved ({len(prev_context)} chars)")
        
        # 自动检测：如果 LLM 已经生成了 technical_design.md，优先使用
        report_file = os.path.join(output_dir, "technical_design.md")
        if os.path.exists(report_file):
            llm_report = Path(report_file).read_text(encoding="utf-8")
            if len(llm_report) > 100:
                prev_context = llm_report
                print(f"  ✅ LLM technical_design detected ({len(prev_context)} chars)")
        
        print(f"  Status: {td_result['status']}")
        if td_result.get("prompt_file"):
            print(f"  Prompt: {td_result['prompt_file']}")
        prev_stage = "td"
    
    # Stage 3: 测试用例生成（接收 TD 内容）
    if "test" in stages:
        print("\n📋 Stage 3: Test Cases")
        test_engine = TestEngine(profile, output_dir, wiki_path,
                                 module_filter=module_filter, max_files=max_files)
        
        # 如果有 TD 内容，注入给 Test
        test_kwargs = {"prd_text": prd_text}
        if prev_context:
            test_kwargs["td_text"] = prev_context
        
        test_result = test_engine.generate_tests(**test_kwargs)
        results["test"] = test_result
        
        # 自动检测：如果 LLM 已经生成了 test_cases.md
        report_file = os.path.join(output_dir, "test_cases.md")
        if os.path.exists(report_file):
            llm_report = Path(report_file).read_text(encoding="utf-8")
            if len(llm_report) > 100:
                print(f"  ✅ LLM test_cases detected ({len(llm_report)} chars)")
        
        print(f"  Status: {test_result['status']}")
        if test_result.get("prompt_file"):
            print(f"  Prompt: {test_result['prompt_file']}")
    
    return {
        "status": "completed",
        "results": results,
        "stages_executed": stages,
    }


def main():
    parser = argparse.ArgumentParser(description="Biz Delivery Pipeline")
    parser.add_argument("--profile", required=True, help="Profile JSON path")
    parser.add_argument("--mode", default="learn", 
                       help="Mode: learn, prdtdd, auto, or eval")
    parser.add_argument("--text", help="PRD content or URL (for prdtdd/auto mode)")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--wiki-path", help="Wiki engine path")
    parser.add_argument("--stages", help="Stages for prdtdd: review,td,plan,test,automation")
    parser.add_argument("--incremental", action="store_true", help="Enable incremental scanning (skip unchanged files)")
    parser.add_argument("--module", help="Module scope filter (e.g. 'share', 'adgroup') — only scan relevant packages")
    parser.add_argument("--max-files", type=int, help="Max files per repo to scan (overrides profile default)")
    parser.add_argument("--prd-key", help="Specific PRD key for evaluation: new_feature/enhancement/high_risk_change")
    args = parser.parse_args()
    
    # 加载 Profile
    profile = load_profile(args.profile)
    profile_path = args.profile
    
    # 解析模式
    modes = [m.strip() for m in args.mode.split(",")]
    stages = [s.strip() for s in args.stages.split(",")] if args.stages else None
    
    # Evaluation mode
    if "eval" in modes:
        from evaluate import run_evaluation
        eval_prd = args.prd_key or None
        results = run_evaluation("full", args.profile, args.output_dir, eval_prd)
        print(f"\n{'='*60}")
        print("EVALUATION COMPLETE")
        print(f"{'='*60}")
        for mode, result in results.items():
            passed = result.get("passed", 0)
            total = result.get("total", 0)
            pct = (passed / total * 100) if total > 0 else 0
            status = "✅" if pct == 100 else ("⚠️" if pct >= 50 else "❌")
            print(f"  {status} {mode}: {passed}/{total} ({pct:.0f}%)")
        return
    
    # 按顺序执行各模式
    results = {}
    for mode in modes:
        print(f"\n{'='*60}")
        print(f"Running mode: {mode}")
        print(f"{'='*60}")
        
        if mode == "learn":
            output = os.path.join(args.output_dir, "knowledge")
            result = run_learn_mode(profile_path, output, args.wiki_path,
                                    incremental=args.incremental,
                                    module_filter=args.module,
                                    max_files=args.max_files)
            results["learn"] = result
            
        elif mode == "prdtdd":
            output = os.path.join(args.output_dir, "delivery")
            if not args.text:
                print("ERROR: --text is required for prdtdd mode")
                sys.exit(1)
            result = run_prdtdd_mode(profile, args.text, output, stages,
                                     wiki_path=args.wiki_path,
                                     module_filter=args.module,
                                     max_files=args.max_files)
            results["prdtdd"] = result
            
        elif mode == "auto":
            output = os.path.join(args.output_dir, "delivery")
            if not args.text:
                print("ERROR: --text is required for auto mode")
                sys.exit(1)
            result = run_auto_mode(profile, args.text, output, args.wiki_path,
                                   module_filter=args.module, max_files=args.max_files)
            results["auto"] = result
            
        else:
            print(f"WARNING: Unknown mode '{mode}', skipping")
    
    # 汇总结果
    print(f"\n{'='*60}")
    print("Pipeline Complete")
    print(f"{'='*60}")
    for mode, result in results.items():
        status = result.get("status", "unknown")
        print(f"  {mode}: {status}")
        if result.get("message"):
            print(f"    {result['message']}")
        if result.get("prompt_file"):
            print(f"    Prompt: {result['prompt_file']}")
        if result.get("output_dir"):
            print(f"    Output: {result['output_dir']}")


if __name__ == "__main__":
    main()
