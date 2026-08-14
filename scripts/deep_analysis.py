#!/usr/bin/env python3
"""项目深度分析工具 — 对任何项目生成专家级业务理解.

Usage:
    python3 deep_analysis.py --path /path/to/project --output out/
    python3 deep_analysis.py --path /Users/yanping.ma/GolandProjects/dap --output out/dap/
    python3 deep_analysis.py --path /Users/yanping.ma/GolandProjects/ad_delivery_platform --output out/adp/

流程:
    1. 自动检测项目 (语言/框架/架构/规模)
    2. 代码库扫描 (IR + 调用图)
    3. 业务流程提取 (YAML + Go源码联合)
    4. 架构模式检测 (状态机/锁/重试/Kafka)
    5. 跨仓库调用分析 (如有多个仓库)
    6. 生成 Mermaid 流程图
    7. 输出知识库 + 业务摘要
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))


def run_full_analysis(project_path: str, output_dir: str, 
                      max_files: Optional[int] = None,
                      include_cross_repo: bool = False,
                      cross_repo_paths: Optional[List[str]] = None) -> Dict:
    """运行完整分析流程."""
    t0 = time.time()
    results = {"stages": {}, "total_time": 0, "errors": []}
    
    # ── Stage 1: 项目检测 ────────────────────────────────────────
    from project_auto_detector import detect_project, generate_profile
    print("🔍 Stage 1: 项目检测...")
    det = detect_project(project_path)
    if "error" in det:
        results["errors"].append(det["error"])
        return results
    
    profile = generate_profile(det)
    results["stages"]["detection"] = det
    print(f"   语言={det['language']} 框架={det['framework']} 架构={det['architecture']} "
          f"规模={det['scale']} 文件数={det['total_files']}")
    
    # ── Stage 2: 代码库扫描 ──────────────────────────────────────
    print("🔍 Stage 2: 代码库扫描...")
    from learn_repo import GoScanner, PythonScanner, JavaScanner
    lang = det["language"]
    repo_max = max_files or det["max_files"]
    
    scanner_map = {"go": GoScanner, "python": PythonScanner, "java": JavaScanner}
    scanner_cls = scanner_map.get(lang, GoScanner)
    scanner = scanner_cls()
    
    ir = scanner.scan_directory(Path(project_path), max_files=repo_max)
    results["stages"]["scan"] = {
        "language": lang,
        "structs": len(ir.structs),
        "functions": len(ir.functions),
        "routes": len(ir.routes),
        "entry_points": len(ir.entry_points),
    }
    print(f"   {len(ir.structs)} structs, {len(ir.functions)} functions, "
          f"{len(ir.routes)} routes, {len(ir.entry_points)} entry points")
    
    # ── Stage 3: 业务流程提取 ─────────────────────────────────────
    print("🔍 Stage 3: 业务流程提取...")
    if lang == "go":
        from go_flow_analyzer import analyze_go_agent, analyze_spex_processors
        from deep_flow_extractor import extract_deep_flows
        
        # 找 agent 目录
        agent_dirs = []
        for pattern in ["app/agent", "app/*/agent", "app/admin/agent"]:
            for d in Path(project_path).rglob(pattern.split("/")[-1]):
                if (d / "workflow").exists():
                    agent_dirs.append(str(d))
        
        if agent_dirs:
            # Go 源码分析
            try:
                go_result = analyze_go_agent(agent_dirs[0], [project_path])
                ir.go_business_flows[agent_dirs[0]] = go_result
                entries = go_result.get("entry_points", [])
                results["stages"]["go_flows"] = {"entries": len(entries)}
            except Exception as e:
                results["errors"].append(f"go_flows: {e}")
            
            # SPX 处理器分析
            spex_dir = Path(project_path) / "app" / "admin" / "spexprocessor"
            if spex_dir.exists():
                try:
                    spex_result = analyze_spex_processors(project_path)
                    ir.spex_business_flows[project_path] = spex_result
                    traces = spex_result.get("traces", {})
                    results["stages"]["spex_flows"] = {"traces": len(traces)}
                except Exception as e:
                    results["errors"].append(f"spex_flows: {e}")
            
            # YAML 工作流分析
            try:
                deep_result = extract_deep_flows(agent_dirs, [project_path])
                ir.agent_workflows = deep_result
                total_wf = sum(len(d.get("workflows", {})) for d in deep_result.values())
                results["stages"]["yaml_workflows"] = {"workflows": total_wf}
            except Exception as e:
                results["errors"].append(f"yaml_workflows: {e}")
    
    # ── Stage 4: 架构模式检测 ────────────────────────────────────
    print("🔍 Stage 4: 架构模式检测...")
    try:
        from go_flow_analyzer import analyze_patterns
        pattern_results = analyze_patterns([project_path])
        ir.architectural_patterns = pattern_results
        results["stages"]["patterns"] = {
            "state_machines": len(pattern_results.get("state_machines", [])),
            "redis_locks": len(pattern_results.get("redis_locks", [])),
            "kafka_consumers": len(pattern_results.get("kafka_patterns", [])),
            "retry_logic": len(pattern_results.get("retry_logic", [])),
            "idempotency": len(pattern_results.get("idempotency", [])),
            "task_groups": len(pattern_results.get("task_group_patterns", [])),
            "enums": len(pattern_results.get("enums", [])),
        }
        print(f"   状态机={results['stages']['patterns']['state_machines']}, "
              f"Redis锁={results['stages']['patterns']['redis_locks']}, "
              f"Kafka={results['stages']['patterns']['kafka_consumers']}, "
              f"枚举={results['stages']['patterns']['enums']}")
    except Exception as e:
        results["errors"].append(f"patterns: {e}")
    
    # ── Stage 5: 跨仓库分析 ──────────────────────────────────────
    if include_cross_repo and cross_repo_paths:
        print("🔍 Stage 5: 跨仓库调用分析...")
        try:
            from cross_repo_flow import analyze_cross_repo
            all_paths = [project_path] + cross_repo_paths
            cross_result = analyze_cross_repo(all_paths, max_files=3000)
            results["stages"]["cross_repo"] = {
                "calls": len(cross_result.get("calls", [])),
                "services": len(set(
                    c.get("caller", "").split("/")[-3] 
                    for c in cross_result.get("calls", [])
                )),
            }
            print(f"   跨仓库调用={results['stages']['cross_repo']['calls']}")
        except Exception as e:
            results["errors"].append(f"cross_repo: {e}")
    
    # ── Stage 6: 生成 Mermaid 图 ─────────────────────────────────
    print("🔍 Stage 6: 生成 Mermaid 流程图...")
    flow_data = {
        "spex_traces": getattr(ir, "spex_business_flows", {}) or {},
        "go_flows": getattr(ir, "go_business_flows", {}) or {},
        "patterns": getattr(ir, "architectural_patterns", {}) or {},
        "cross_repo": results.get("stages", {}).get("cross_repo", {}),
        "entry_points": getattr(ir, "entry_points", [])[:10],
    }
    
    try:
        from mermaid_generator import MermaidGenerator
        gen = MermaidGenerator({
            "packages": getattr(ir, "packages", {}) or {},
            "call_graph": getattr(ir, "call_graph", []) or [],
            "entity_tables": getattr(ir, "entity_tables", []) or [],
            "routes": getattr(ir, "routes", []) or [],
            "functions": getattr(ir, "functions", []) or [],
            "services": getattr(ir, "services", []) or [],
            "core_flows": getattr(ir, "core_flows", []) or [],
            "structs": getattr(ir, "structs", []) or [],
            "error_codes": getattr(ir, "error_codes", []) or [],
            "configs": getattr(ir, "configs", []) or [],
        }, flow_data=flow_data)
        
        diagrams = gen.generate_all_diagrams()
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        
        diagram_count = 0
        for name, content in diagrams.items():
            if content and "mermaid" in content.lower():
                (out_path / f"{name}.md").write_text(content, encoding="utf-8")
                diagram_count += 1
        
        results["stages"]["diagrams"] = {"count": diagram_count}
        print(f"   生成 {diagram_count} 张 Mermaid 图")
    except Exception as e:
        results["errors"].append(f"diagrams: {e}")
    
    # ── Stage 7: 生成业务摘要 ────────────────────────────────────
    print("🔍 Stage 7: 生成业务摘要...")
    summary = _generate_executive_summary(det, ir, results)
    (Path(output_dir) / "summary.md").write_text(summary, encoding="utf-8")
    
    # ── 保存完整结果 ─────────────────────────────────────────────
    results["total_time"] = time.time() - t0
    results["ir_summary"] = {
        "language": det["language"],
        "framework": det["framework"],
        "architecture": det["architecture"],
        "scale": det["scale"],
        "total_files": det["total_files"],
        "structs": len(ir.structs),
        "functions": len(ir.functions),
        "routes": len(ir.routes),
        "entry_points": len(ir.entry_points),
    }
    
    output_json = Path(output_dir) / "analysis_result.json"
    output_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"\n✅ 分析完成! 耗时 {results['total_time']:.1f}s")
    print(f"   输出目录: {output_dir}")
    print(f"   摘要文件: {output_json.parent / 'summary.md'}")
    
    return results


def _generate_executive_summary(det: Dict, ir, results: Dict) -> str:
    """生成专家级业务摘要."""
    lines = [
        "# 📊 项目业务深度分析报告",
        "",
        f"**项目**: {det.get('project_path', 'unknown')}",
        f"**语言**: {det.get('language', 'unknown')}",
        f"**框架**: {det.get('framework', 'unknown')}",
        f"**架构**: {det.get('architecture', 'unknown')}",
        f"**规模**: {det.get('scale', 'unknown')} ({det.get('total_files', 0)} 文件)",
        "",
        "---",
        "",
        "## 一、项目概览",
        "",
        f"这是一个 **{det.get('scale', 'unknown')}** 规模的 **{det.get('language', 'unknown')}** 项目，",
        f"采用 **{det.get('framework', 'unknown')}** 框架，架构风格为 **{det.get('architecture', 'unknown')}**。",
        "",
        "### 代码规模",
        "",
        f"| 指标 | 数量 |",
        f"|------|------|",
        f"| Struct | {len(ir.structs)} |",
        f"| Function | {len(ir.functions)} |",
        f"| Route | {len(ir.routes)} |",
        f"| Entry Points | {len(getattr(ir, 'entry_points', []))} |",
        "",
    ]
    
    # 业务逻辑
    if hasattr(ir, 'business_logic') and ir.business_logic:
        lines.append("## 二、核心业务流程")
        lines.append("")
        for bl in ir.business_logic[:5]:
            route = bl.get('route', '?')
            handler = bl.get('handler', '?')
            desc = bl.get('description', '')[:100]
            lines.append(f"- `{route}` → `{handler}`: {desc}")
        lines.append("")
    
    # 架构模式
    patterns = getattr(ir, 'architectural_patterns', {})
    if patterns:
        lines.append("## 三、架构模式")
        lines.append("")
        sm = patterns.get('state_machines', [])
        if sm:
            lines.append("### 状态机")
            for item in sm[:5]:
                lines.append(f"- `{item['func']}` @ {item['file']}:{item['line']} — {item['pattern']}")
            lines.append("")
        
        redis = patterns.get('redis_locks', [])
        if redis:
            lines.append("### Redis 分布式锁")
            for item in redis[:5]:
                lines.append(f"- `{item['func']}` — {item['desc']}")
            lines.append("")
        
        retry = patterns.get('retry_logic', [])
        if retry:
            lines.append("### 重试机制")
            for item in retry[:5]:
                lines.append(f"- `{item['func']}` — {item['desc']}")
            lines.append("")
        
        kafka = patterns.get('kafka_patterns', [])
        if kafka:
            lines.append("### Kafka 消息队列")
            for item in kafka[:5]:
                lines.append(f"- `{item['func']}` — {item['desc']}")
            lines.append("")
    
    # 跨仓库
    stages = results.get("stages", {})
    cross = stages.get("cross_repo", {})
    if cross.get("calls"):
        lines.append("## 四、跨仓库依赖")
        lines.append("")
        lines.append(f"- 跨仓库调用: {cross['calls']}")
        lines.append(f"- 涉及服务: {cross.get('services', 0)}")
        lines.append("")
    
    lines.append("---")
    lines.append(f"*Generated in {results.get('total_time', 0):.1f}s by biz-delivery deep analysis*")
    
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="项目深度分析工具")
    parser.add_argument("--path", required=True, help="项目根目录")
    parser.add_argument("--output", required=True, help="输出目录")
    parser.add_argument("--max-files", type=int, default=None, help="最大扫描文件数")
    parser.add_argument("--cross-repo", action="store_true", help="启用跨仓库分析")
    parser.add_argument("--cross-paths", nargs="*", help="额外仓库路径")
    args = parser.parse_args()
    
    run_full_analysis(
        project_path=args.path,
        output_dir=args.output,
        max_files=args.max_files,
        include_cross_repo=args.cross_repo,
        cross_repo_paths=args.cross_paths,
    )
