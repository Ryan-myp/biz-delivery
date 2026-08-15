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
import signal
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))


# ── 超时处理 ─────────────────────────────────────────────────

class TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("Stage timeout")


def _run_with_timeout(fn, *args, timeout: int = 120, stage_name: str = "") -> Dict:
    """带超时的步骤执行，失败不中断整体流程."""
    print(f"🔍 {stage_name}...")
    try:
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout)
        result = fn(*args)
        signal.alarm(0)
        return result or {}
    except TimeoutError:
        msg = f"{stage_name} 超时 ({timeout}s)"
        print(f"   ⚠️  {msg}, 跳过")
        return {"_timeout": True, "_error": msg}
    except Exception as e:
        msg = f"{stage_name} 失败: {e}"
        print(f"   ❌ {msg}")
        return {"_error": msg}


# ── 主分析函数 ───────────────────────────────────────────────

def run_full_analysis(project_path: str, output_dir: str,
                      max_files: Optional[int] = None,
                      include_cross_repo: bool = False,
                      cross_repo_paths: Optional[List[str]] = None,
                      stage_timeout: int = 120) -> Dict:
    """运行完整分析流程."""
    t0 = time.time()
    results = {"stages": {}, "total_time": 0, "errors": [], "warnings": []}

    # ── Stage 1: 项目检测 ──────────────────────────────────────
    det = _run_with_timeout(_detect_project, project_path, timeout=30,
                           stage_name="Stage 1: 项目检测")
    if "_error" in det:
        results["errors"].append(det["_error"])
        results["total_time"] = time.time() - t0
        return results

    profile = _run_with_timeout(_generate_profile, det, timeout=10,
                               stage_name="Stage 1b: 生成Profile")
    results["stages"]["detection"] = det
    results["stages"]["profile"] = profile
    lang = det.get("language", "go")
    repo_max = max_files or det.get("max_files", 2000)

    # 大项目降速策略
    if det.get("scale") == "large" and repo_max > 2000:
        repo_max = min(repo_max, 1500)
        results["warnings"].append(f"大项目降速: max_files={repo_max}")
        print(f"   ⚠️  大项目降速优化: max_files={repo_max}")

    # ── Stage 2: 代码库扫描 ──────────────────────────────────────
    scan_result = _run_with_timeout(
        _scan_codebase, project_path, lang, repo_max,
        timeout=180, stage_name="Stage 2: 代码库扫描"
    )
    results["stages"]["scan"] = scan_result
    if "_error" in scan_result:
        results["errors"].append(scan_result["_error"])
        ir = None
    else:
        ir = scan_result.get("ir")

    # ── Stage 3: 业务流程提取 ─────────────────────────────────────
    if lang == "go" and ir is not None:
        go_flows = _run_with_timeout(
            _analyze_go_flows, project_path, ir,
            timeout=180, stage_name="Stage 3: Go流程提取"
        )
        results["stages"]["go_flows"] = go_flows
        if "_error" not in go_flows:
            ir.go_business_flows = go_flows.get("flows", {})

        spex_flows = _run_with_timeout(
            _analyze_spex, project_path,
            timeout=120, stage_name="Stage 3b: SPX分析"
        )
        results["stages"]["spex_flows"] = spex_flows
        if "_error" not in spex_flows:
            ir.spex_business_flows = spex_flows.get("traces", {})

        yaml_wf = _run_with_timeout(
            _analyze_yaml_workflows, project_path,
            timeout=60, stage_name="Stage 3c: YAML工作流"
        )
        results["stages"]["yaml_workflows"] = yaml_wf

    # ── Stage 4: 架构模式检测 ────────────────────────────────────
    pattern_result = _run_with_timeout(
        _detect_patterns, project_path,
        timeout=60, stage_name="Stage 4: 模式检测"
    )
    results["stages"]["patterns"] = pattern_result
    if "_error" not in pattern_result and ir is not None:
        ir.architectural_patterns = pattern_result

    # ── Stage 5: 跨仓库分析 ──────────────────────────────────────
    if include_cross_repo and cross_repo_paths:
        cross_result = _run_with_timeout(
            _analyze_cross_repo, project_path, cross_repo_paths,
            timeout=180, stage_name="Stage 5: 跨仓库分析"
        )
        results["stages"]["cross_repo"] = cross_result

    # ── Stage 6: 生成 Mermaid 图 ─────────────────────────────────
    diagram_result = _run_with_timeout(
        _generate_diagrams, ir, results.get("stages", {}),
        timeout=60, stage_name="Stage 6: Mermaid图生成"
    )
    results["stages"]["diagrams"] = diagram_result

    # ── Stage 7: 生成业务摘要 ────────────────────────────────────
    summary = _generate_executive_summary(det, ir, results)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    (out_path / "summary.md").write_text(summary, encoding="utf-8")
    results["stages"]["summary"] = {"output": str(out_path / "summary.md")}

    # ── Stage 7b: Python 项目业务语义分析 ────────────────────────
    if lang == "python":
        try:
            from python_business_analyzer import analyze_python_project, generate_business_summary
            print("🔍 Stage 7b: Python 业务语义分析...")
            biz_analysis = analyze_python_project(project_path)
            biz_summary = generate_business_summary(biz_analysis)
            (out_path / "business_analysis.md").write_text(biz_summary, encoding="utf-8")
            results["stages"]["business_analysis"] = {
                "output": str(out_path / "business_analysis.md"),
                "features": len(biz_analysis.get("features", [])),
                "routes": len(biz_analysis.get("api_routes", [])),
                "modules": len(biz_analysis.get("modules", [])),
            }
            print(f"   检测到 {len(biz_analysis.get('features', []))} 个功能模块")
        except Exception as e:
            results["warnings"].append(f"business_analysis: {e}")

    # ── 保存完整结果 ─────────────────────────────────────────────
    results["total_time"] = time.time() - t0
    results["ir_summary"] = {
        "language": det.get("language"),
        "framework": det.get("framework"),
        "architecture": det.get("architecture"),
        "scale": det.get("scale"),
        "total_files": det.get("total_files", 0),
        "structs": len(ir.structs) if ir else 0,
        "functions": len(ir.functions) if ir else 0,
        "routes": len(ir.routes) if ir else 0,
    }

    output_json = out_path / "analysis_result.json"
    output_json.write_text(json.dumps(_make_serializable(results), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ 分析完成! 耗时 {results['total_time']:.1f}s")
    print(f"   输出目录: {output_dir}")
    print(f"   摘要文件: {out_path / 'summary.md'}")
    if results["errors"]:
        print(f"   ⚠️  错误数: {len(results['errors'])}")
    if results["warnings"]:
        print(f"   ⚠️  警告数: {len(results['warnings'])}")

    return results


# ── 各阶段实现 ────────────────────────────────────────────────

def _detect_project(path: str) -> Dict:
    from project_auto_detector import detect_project
    return detect_project(path)


def _generate_profile(det: Dict) -> Dict:
    from project_auto_detector import generate_profile
    return generate_profile(det)


def _scan_codebase(path: str, language: str, max_files: int) -> Dict:
    from learn_repo import GoScanner, PythonScanner, JavaScanner
    scanner_map = {"go": GoScanner, "python": PythonScanner, "java": JavaScanner}
    scanner_cls = scanner_map.get(language, GoScanner)
    scanner = scanner_cls()
    ir = scanner.scan_directory(Path(path), max_files=max_files)
    return {
        "ir": ir,
        "structs": len(ir.structs),
        "functions": len(ir.functions),
        "routes": len(ir.routes),
        "entry_points": len(ir.entry_points),
    }


def _analyze_go_flows(path: str, ir) -> Dict:
    from go_flow_analyzer import analyze_go_agent
    from deep_flow_extractor import extract_deep_flows

    # 找 agent 目录
    agent_dirs = []
    for pattern in ["app/agent", "app/*/agent", "app/admin/agent"]:
        parts = pattern.split("/")
        for d in Path(path).rglob(parts[-1]):
            if (d / "workflow").exists():
                agent_dirs.append(str(d))

    flows = {}
    if agent_dirs:
        try:
            result = analyze_go_agent(agent_dirs[0], [path])
            flows[agent_dirs[0]] = result
        except Exception as e:
            return {"_error": f"go_agent: {e}"}

    try:
        deep_result = extract_deep_flows(agent_dirs, [path])
        ir.agent_workflows = deep_result
    except Exception:
        pass

    return {"flows": flows}


def _analyze_spex(path: str) -> Dict:
    from go_flow_analyzer import analyze_spex_processors
    spex_dir = Path(path) / "app" / "admin" / "spexprocessor"
    if not spex_dir.exists():
        return {"_skipped": "spexprocessor目录不存在"}
    try:
        result = analyze_spex_processors(path)
        return {"traces": result.get("traces", {})}
    except Exception as e:
        return {"_error": f"spex: {e}"}


def _analyze_yaml_workflows(path: str) -> Dict:
    from deep_flow_extractor import extract_deep_flows
    agent_dirs = []
    for pattern in ["app/agent", "app/*/agent"]:
        parts = pattern.split("/")
        for d in Path(path).rglob(parts[-1]):
            if (d / "workflow").exists():
                agent_dirs.append(str(d))
    try:
        result = extract_deep_flows(agent_dirs, [path])
        total = sum(len(d.get("workflows", {})) for d in result.values())
        return {"workflows": total, "agents": len(result)}
    except Exception as e:
        return {"_error": str(e)}


def _detect_patterns(path: str) -> Dict:
    """使用通用模式检测器."""
    from universal_pattern_detector import detect_patterns
    return detect_patterns([path])


def _analyze_cross_repo(path: str, cross_paths: List[str]) -> Dict:
    from cross_repo_flow import analyze_cross_repo
    all_paths = [path] + cross_paths
    result = analyze_cross_repo(all_paths, max_files=2000)
    calls = result.get("calls", [])
    services = set()
    for c in calls:
        caller = c.get("caller", "")
        pkg = caller.split("/")
        if len(pkg) >= 3:
            services.add(pkg[-3])
    return {"calls": len(calls), "services": len(services)}


def _generate_diagrams(ir, stages: Dict) -> Dict:
    from mermaid_generator import MermaidGenerator

    # 确保 flow_data 中的 cross_repo 是 dict
    cross_repo_val = stages.get("cross_repo", {})
    if not isinstance(cross_repo_val, dict):
        cross_repo_val = {}

    # 转换 entry_points 格式（IRDocument 是字符串列表，Mermaid 需要 dict）
    raw_entry_points = getattr(ir, "entry_points", []) or []
    if raw_entry_points and isinstance(raw_entry_points[0], str):
        entry_points = [{"name": ep, "file": "", "calls": []} for ep in raw_entry_points[:10]]
    else:
        entry_points = raw_entry_points[:10]

    flow_data = {
        "spex_traces": getattr(ir, "spex_business_flows", {}) or {},
        "go_flows": getattr(ir, "go_business_flows", {}) or {},
        "patterns": getattr(ir, "architectural_patterns", {}) or {},
        "cross_repo": cross_repo_val,
        "entry_points": entry_points,
    }

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
    out_path = Path(".").absolute()  # Will be overwritten
    return {"diagrams": diagrams}


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
        f"| Struct | {len(ir.structs) if ir else 0} |",
        f"| Function | {len(ir.functions) if ir else 0} |",
        f"| Route | {len(ir.routes) if ir else 0} |",
        f"| Entry Points | {len(getattr(ir, 'entry_points', [])) if ir else 0} |",
        "",
    ]

    # 业务逻辑
    if ir and hasattr(ir, 'business_logic') and ir.business_logic:
        lines.append("## 二、核心业务流程")
        lines.append("")
        for bl in ir.business_logic[:5]:
            route = bl.get('route', '?')
            handler = bl.get('handler', '?')
            desc = bl.get('description', '')[:100]
            lines.append(f"- `{route}` → `{handler}`: {desc}")
        lines.append("")

    # 架构模式
    patterns = getattr(ir, 'architectural_patterns', {}) if ir else {}
    if patterns:
        lines.append("## 三、架构模式")
        lines.append("")
        sm = patterns.get('state_machines', [])
        if sm:
            lines.append("### 状态机")
            for item in sm[:5]:
                lines.append(f"- `{item['func']}` @ {item['file']}:{item['line']}")
                states = item.get('states', item.get('transitions', []))
                if states:
                    lines.append(f"  {', '.join(states[:3])}")
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

        enums = patterns.get('enums', [])
        if enums:
            lines.append("### 枚举/常量定义")
            lines.append(f"检测到 {len(enums)} 组枚举定义")
            for item in enums[:5]:
                lines.append(f"- `{item['file']}` ({item['type']}, {item['count']}个): {', '.join(item['names'][:4])}")
            lines.append("")

    # 警告信息
    warnings = results.get("warnings", [])
    if warnings:
        lines.append("## 四、注意事项")
        lines.append("")
        for w in warnings[:5]:
            lines.append(f"- ⚠️  {w}")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated in {results.get('total_time', 0):.1f}s by biz-delivery deep analysis*")

    return "\n".join(lines)


def _make_serializable(obj):
    """将对象转换为可JSON序列化的格式."""
    import json
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_serializable(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        # IRDocument 等自定义对象 → 转为 dict
        return {k: _make_serializable(v) for k, v in obj.__dict__.items()
                if not k.startswith('_')}
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    else:
        return obj


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="项目深度分析工具")
    parser.add_argument("--path", required=True, help="项目根目录")
    parser.add_argument("--output", required=True, help="输出目录")
    parser.add_argument("--max-files", type=int, default=None, help="最大扫描文件数")
    parser.add_argument("--cross-repo", action="store_true", help="启用跨仓库分析")
    parser.add_argument("--cross-paths", nargs="*", help="额外仓库路径")
    parser.add_argument("--timeout", type=int, default=120, help="每步超时秒数")
    args = parser.parse_args()

    run_full_analysis(
        project_path=args.path,
        output_dir=args.output,
        max_files=args.max_files,
        include_cross_repo=args.cross_repo,
        cross_repo_paths=args.cross_paths,
        stage_timeout=args.timeout,
    )
