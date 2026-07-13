#!/usr/bin/env python3
"""端到端流水线 — 支持 learn 和 prdtdd 双模式

Usage:
    # learn 模式：代码 → 知识库
    python3 run_pipeline.py \
      --profile profiles/my-service.json \
      --mode learn \
      --output-dir knowledge/my-service

    # prdtdd 模式：PRD → 评审 → TD → 测试
    python3 run_pipeline.py \
      --profile profiles/my-service.json \
      --mode prdtdd \
      --text "<PRD内容或URL>" \
      --output-dir delivery/my-feature

    # 串联模式：先 learn 再 prdtdd
    python3 run_pipeline.py \
      --profile profiles/my-service.json \
      --mode learn,prdtdd \
      --text "<PRD内容或URL>" \
      --output-dir delivery/my-feature
"""

import argparse
import json
import os
import sys
from pathlib import Path


def load_profile(profile_path: str) -> dict:
    """加载 Profile 配置"""
    with open(profile_path) as f:
        return json.load(f)


def run_learn_mode(profile_path: str, output_dir: str, wiki_path: str = None) -> dict:
    """执行 learn 模式"""
    from learn_repo import learn_from_repos

    result = learn_from_repos(
        profile_path=profile_path,
        output_dir=output_dir,
        wiki_path=wiki_path,
    )
    return result



def run_prdtdd_mode(profile: dict, prd_text: str, output_dir: str, stages: list = None, wiki_path: str = None) -> dict:
    """执行 prdtdd 模式 — 支持阶段间数据传递
    
    串联逻辑：
    - review → td: TD 接收审查报告（review_report 参数）
    - td → test: Test 接收 TD 内容（td_text 参数）
    - 每个阶段复用同一个 kb_dir，避免重复扫描
    - 自动检测 LLM 响应文件（review_report.md / technical_design.md / test_cases.md）
      如果存在，自动读取并传递给下一阶段
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from review_engine import ReviewEngine
    from td_engine import TDEngine
    from test_engine import TestEngine
    
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
        review_engine = ReviewEngine(profile, output_dir, wiki_path)
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
        td_engine = TDEngine(profile, output_dir, wiki_path)
        
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
        test_engine = TestEngine(profile, output_dir, wiki_path)
        
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
                       help="Mode: learn, prdtdd, or learn,prdtdd (comma-separated)")
    parser.add_argument("--text", help="PRD content or URL (for prdtdd mode)")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--wiki-path", help="Wiki engine path")
    parser.add_argument("--stages", help="Stages for prdtdd: review,td,plan,test,automation")
    args = parser.parse_args()
    
    # 加载 Profile
    profile = load_profile(args.profile)
    profile_path = args.profile
    
    # 解析模式
    modes = [m.strip() for m in args.mode.split(",")]
    stages = [s.strip() for s in args.stages.split(",")] if args.stages else None
    
    # 按顺序执行各模式
    results = {}
    for mode in modes:
        print(f"\n{'='*60}")
        print(f"Running mode: {mode}")
        print(f"{'='*60}")
        
        if mode == "learn":
            output = os.path.join(args.output_dir, "knowledge")
            result = run_learn_mode(profile_path, output, args.wiki_path)
            results["learn"] = result
            
        elif mode == "prdtdd":
            output = os.path.join(args.output_dir, "delivery")
            if not args.text:
                print("ERROR: --text is required for prdtdd mode")
                sys.exit(1)
            result = run_prdtdd_mode(profile, args.text, output, stages)
            results["prdtdd"] = result
            
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
