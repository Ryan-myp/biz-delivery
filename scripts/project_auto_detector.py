#!/usr/bin/env python3
"""项目自动检测器 — 识别项目类型、语言、框架、架构风格.

Usage:
    python3 project_auto_detector.py --path /path/to/project
    
输出:
    {
        "language": "go",
        "framework": "spex",
        "architecture": "monolith|microservice|serverless",
        "scale": "small|medium|large",
        "max_files": 2000,
        "entry_points": ["main.go", ...],
        "config_files": ["config.yaml", ...],
        "test_pattern": "**/*_test.go",
        "analysis_depth": "full"
    }
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional


# ── 语言检测 ────────────────────────────────────────────────

_LANG_DETECTORS = {
    "go": {
        "files": ["*.go"],
        "indicators": ["package main", "func ", "import ", "type ", "struct "],
        "entry_patterns": ["main.go", "cmd/**/*.go"],
    },
    "python": {
        "files": ["*.py"],
        "indicators": ["import ", "def ", "class ", "@app.route", "from flask", "from django"],
        "entry_patterns": ["app.py", "main.py", "wsgi.py", "manage.py", "run.py"],
    },
    "java": {
        "files": ["*.java"],
        "indicators": ["public class ", "public static void main", "@RestController", "@Service"],
        "entry_patterns": ["**/Application.java", "**/*Application.java"],
    },
    "typescript": {
        "files": ["*.ts", "*.tsx"],
        "indicators": ["import ", "export ", "const ", "function ", "class "],
        "entry_patterns": ["src/main.ts", "src/index.ts", "src/app.ts"],
    },
}


def detect_language(project_path: Path) -> str:
    """根据文件扩展名和标志性代码检测语言."""
    scores = {}
    for lang, config in _LANG_DETECTORS.items():
        score = 0
        # 文件数量
        for pattern in config["files"]:
            count = len(list(project_path.rglob(pattern)))
            score += count * 10
        # 标志性代码
        if score > 0:
            sample_files = list(project_path.rglob(config["files"][0]))[:50]
            for f in sample_files:
                try:
                    text = f.read_text(errors='ignore')[:5000]
                    for indicator in config["indicators"][:3]:
                        if indicator in text:
                            score += 5
                            break
                except Exception:
                    pass
        if score > 0:
            scores[lang] = score
    return max(scores, key=scores.get) if scores else "unknown"


# ── 框架检测 ────────────────────────────────────────────────

_FRAMEWORK_DETECTORS = {
    "go": {
        "spex": ("spexprocessor", "SPX"),
        "gin": ("gin", "github.com/gin-gonic"),
        "fiber": ("fiber", "gofiber"),
        "echo": ("echo", "labstack/echo"),
        "mux": ("mux", "gorilla/mux"),
        "standard": None,
    },
    "python": {
        "fastapi": ("fastapi", "from fastapi"),
        "flask": ("flask", "from flask"),
        "django": ("django", "import django"),
        "celery": ("celery", "from celery"),
        "none": None,
    },
    "java": {
        "springboot": ("SpringApplication", "SpringBootApplication"),
        "micronaut": ("@Micronaut", "io.micronaut"),
        "quarkus": ("Quarkus", "io.quarkus"),
        "none": None,
    },
}


def detect_framework(project_path: Path, language: str) -> str:
    """检测项目使用的框架."""
    if language not in _FRAMEWORK_DETECTORS:
        return "unknown"
    
    framework_map = _FRAMEWORK_DETECTORS[language]
    candidates = [(k, v) for k, v in framework_map.items() if v is not None]
    
    for fw_name, (file_hint, import_hint) in candidates:
        # 检查文件
        if file_hint:
            go_files = list(project_path.rglob("*.go"))[:100]
            if any(file_hint in str(f) for f in go_files):
                return fw_name
        # 检查 import
        if import_hint:
            lang_ext = ".ts" if language == "typescript" else ".go" if language == "go" else ".py"
            sample_files = list(project_path.rglob(f"*{lang_ext}"))[:100]
            for f in sample_files:
                try:
                    text = f.read_text(errors='ignore')[:2000]
                    if import_hint in text:
                        return fw_name
                except Exception:
                    pass
    return "none"


# ── 架构风格检测 ────────────────────────────────────────────

def detect_architecture(project_path: Path, language: str) -> str:
    """检测架构风格: monolith | microservice | serverless."""
    # Go 项目: 检查是否有多个 cmd/ 或 main 函数入口
    if language == "go":
        cmd_dirs = list(project_path.rglob("cmd"))
        main_funcs = list(project_path.rglob("*_server.go")) + list(project_path.rglob("main.go"))
        spex_dirs = list(project_path.rglob("spexprocessor"))
        
        if len(cmd_dirs) >= 3 or len(spex_dirs) >= 2:
            return "microservice"
        elif len(main_funcs) >= 2:
            return "microservice"
        return "monolith"
    
    # Python 项目: 检查是否有多个 app/ 或 blueprint
    if language == "python":
        app_dirs = list(project_path.rglob("app"))
        blueprints = list(project_path.rglob("*blueprint*.py"))
        if len(app_dirs) >= 3 or len(blueprints) >= 2:
            return "microservice"
        return "monolith"
    
    return "monolith"


# ── 规模评估 ────────────────────────────────────────────────

def estimate_scale(project_path: Path, language: str) -> Dict:
    """评估项目规模，返回 max_files 和建议."""
    ext_map = {"go": "*.go", "python": "*.py", "java": "*.java", "typescript": "*.ts"}
    ext = ext_map.get(language, "*.go")
    
    total = sum(1 for _ in project_path.rglob(ext) 
                if "vendor/" not in str(_) and ".git/" not in str(_))
    
    if total < 500:
        scale = "small"
        max_files = min(total, 500)
    elif total < 3000:
        scale = "medium"
        max_files = min(total, 2000)
    else:
        scale = "large"
        max_files = min(total, 5000)
    
    return {"total_files": total, "scale": scale, "max_files": max_files}


# ── 入口点检测 ─────────────────────────────────────────────

def find_entry_points(project_path: Path, language: str) -> List[str]:
    """找到项目的主要入口文件."""
    entries = []
    for pattern in ["main.go", "main.py", "app.py", "index.ts", 
                    "**/*Application.java", "**/*Application.kt",
                    "**/server.go", "**/cmd/**/*.go"]:
        for f in project_path.rglob(pattern):
            if "vendor/" not in str(f) and ".git/" not in str(f):
                entries.append(str(f.relative_to(project_path)))
    return entries[:10]


# ── 主检测函数 ──────────────────────────────────────────────

def detect_project(project_path: str) -> Dict:
    """检测项目完整信息."""
    path = Path(project_path)
    if not path.exists():
        return {"error": f"Path not found: {project_path}"}
    
    language = detect_language(path)
    framework = detect_framework(path, language)
    architecture = detect_architecture(path, language)
    scale_info = estimate_scale(path, language)
    entries = find_entry_points(path, language)
    
    # 确定分析深度
    depth_map = {"small": "light", "medium": "balanced", "large": "full"}
    analysis_depth = depth_map.get(scale_info["scale"], "balanced")
    
    result = {
        "project_path": project_path,
        "language": language,
        "framework": framework,
        "architecture": architecture,
        "scale": scale_info["scale"],
        "total_files": scale_info["total_files"],
        "max_files": scale_info["max_files"],
        "analysis_depth": analysis_depth,
        "entry_points": entries,
    }
    
    return result


def generate_profile(detection: Dict) -> Dict:
    """根据检测结果生成 biz-delivery profile."""
    return {
        "business_domain": detection.get("language", "unknown"),
        "repositories": [{
            "name": Path(detection["project_path"]).name,
            "path": detection["project_path"],
            "language": detection["language"],
            "max_files": detection["max_files"],
        }],
        "learn_config": {
            "max_files_per_lang": detection["max_files"],
            "depth": detection["analysis_depth"],
        },
        "analysis_modules": _get_relevant_modules(detection),
    }


def _get_relevant_modules(det: Dict) -> List[str]:
    """根据项目特征返回需要运行的分析模块."""
    modules = ["base_engine", "go_flow_analyzer"]
    if det["architecture"] == "microservice":
        modules.append("cross_repo_flow")
        modules.append("mermaid_generator")
    if det["framework"] in ("spex",):
        modules.append("go_flow_analyzer")
    return modules


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    
    result = detect_project(args.path)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"语言: {result.get('language', 'unknown')}")
        print(f"框架: {result.get('framework', 'unknown')}")
        print(f"架构: {result.get('architecture', 'unknown')}")
        print(f"规模: {result.get('scale', 'unknown')} ({result.get('total_files', 0)} 文件)")
        print(f"最大文件数: {result.get('max_files', 2000)}")
        print(f"分析深度: {result.get('analysis_depth', 'balanced')}")
        print(f"入口: {', '.join(result.get('entry_points', [])[:3])}")
