#!/usr/bin/env python3
"""Profile 初始化脚本 — 为新业务创建完整的 Profile 配置

Usage:
    python3 init_profile.py --name my-service --repo /path/to/repo --language go
    python3 init_profile.py --name creative-platform --interactive
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


# ──────────────────────────────────────────────
# Default Profile Template
# ──────────────────────────────────────────────

DEFAULT_PROFILE_TEMPLATE = {
    "business_domain": "{{domain}}",
    "repositories": [
        {
            "name": "{{repo_name}}",
            "path": "{{repo_path}}",
            "language": "{{language}}",
            "max_files": 2000
        }
    ],
    "learn_config": {
        "max_files_per_lang": 2000,
        "include_tests": True,
        "include_configs": False
    },
    "modules": [],
    "query_aliases": {},
    "state_machines": {},
    "business_rules": {
        "general_errors": [],
        "database_errors": [],
        "redis_errors": [],
        "http_errors": []
    },
    "service_topology": {
        "services": []
    }
}

# 常用业务术语映射（按语言）
LANGUAGE_TERM_MAP = {
    "go": {
        "service": "服务",
        "handler": "处理器",
        "middleware": "中间件",
        "repository": "仓储",
        "model": "模型",
        "entity": "实体",
        "interface": "接口",
        "struct": "结构体",
        "error": "错误",
        "config": "配置",
    },
    "python": {
        "service": "服务",
        "handler": "处理器",
        "middleware": "中间件",
        "repository": "仓储",
        "model": "模型",
        "entity": "实体",
        "interface": "接口",
        "class": "类",
        "error": "错误",
        "config": "配置",
    },
    "java": {
        "service": "服务",
        "controller": "控制器",
        "middleware": "拦截器",
        "repository": "仓储",
        "model": "模型",
        "entity": "实体",
        "interface": "接口",
        "class": "类",
        "error": "异常",
        "config": "配置",
    }
}


# ──────────────────────────────────────────────
# Profile Generator
# ──────────────────────────────────────────────

class ProfileGenerator:
    """Profile 生成器"""
    
    def __init__(self, name: str, repo_path: str, language: str):
        self.name = name
        self.repo_path = Path(repo_path)
        self.language = language.lower()
        self.profile = DEFAULT_PROFILE_TEMPLATE.copy()
        
    def generate(self) -> dict:
        """生成 Profile 配置"""
        # 填充基本信息
        self.profile["business_domain"] = self.name
        self.profile["repositories"][0]["name"] = self.name
        self.profile["repositories"][0]["path"] = str(self.repo_path)
        self.profile["repositories"][0]["language"] = self.language
        
        # 扫描目录结构，提取模块信息
        self._scan_structure()
        
        # 提取业务术语
        self._extract_terms()
        
        return self.profile
    
    def _scan_structure(self):
        """扫描仓库目录结构"""
        if not self.repo_path.exists():
            return
        
        # 扫描主要目录
        modules = []
        
        # Go 项目常见结构
        if self.language == "go":
            # 扫描内部包
            internal = self.repo_path / "internal"
            if internal.exists():
                for pkg in internal.iterdir():
                    if pkg.is_dir() and (pkg / "__init__.py" or list(pkg.glob("*.go"))):
                        modules.append({
                            "name": f"{self.name} / {pkg.name}",
                            "path": str(pkg.relative_to(self.repo_path)),
                            "keywords": self._extract_keywords_from_dir(pkg)
                        })
            
            # 扫描 cmd 目录
            cmd = self.repo_path / "cmd"
            if cmd.exists():
                for app in cmd.iterdir():
                    if app.is_dir():
                        modules.append({
                            "name": f"cmd/{app.name}",
                            "path": str(app.relative_to(self.repo_path)),
                            "keywords": [app.name]
                        })
        
        # Python 项目常见结构
        elif self.language == "python":
            # 扫描 src 目录
            src = self.repo_path / "src"
            if src.exists():
                for pkg in src.iterdir():
                    if pkg.is_dir() and (pkg / "__init__.py"):
                        modules.append({
                            "name": f"src.{pkg.name}",
                            "path": str(pkg.relative_to(self.repo_path)),
                            "keywords": self._extract_keywords_from_dir(pkg)
                        })
            else:
                # 扫描根目录下的包
                for pkg in self.repo_path.glob("*"):
                    if pkg.is_dir() and (pkg / "__init__.py"):
                        modules.append({
                            "name": pkg.name,
                            "path": str(pkg.relative_to(self.repo_path)),
                            "keywords": self._extract_keywords_from_dir(pkg)
                        })
        
        # Java 项目常见结构
        elif self.language == "java":
            # 扫描 src/main/java
            java_src = self.repo_path / "src" / "main" / "java"
            if java_src.exists():
                for pkg in list(java_src.rglob("*.java"))[:20]:
                    if pkg.parent not in [p for p in self.repo_path.rglob("test")]:
                        module_name = str(pkg.relative_to(java_src).with_suffix(''))
                        modules.append({
                            "name": module_name,
                            "path": str(pkg.relative_to(self.repo_path)),
                            "keywords": [pkg.stem]
                        })
        
        self.profile["modules"] = modules[:10]  # 最多 10 个模块
    
    def _extract_keywords_from_dir(self, directory: Path) -> List[str]:
        """从目录提取关键词"""
        keywords = set()
        
        # 扫描文件名
        for file in list(directory.rglob("*"))[:50]:
            if file.is_file():
                stem = file.stem
                keywords.add(stem.lower())
                
                # 提取驼峰命名
                import re
                matches = re.findall(r'[A-Z][a-z]+(?:[A-Z][a-z]+)*', stem)
                keywords.update(m.lower() for m in matches)
        
        return list(keywords)[:20]
    
    def _extract_terms(self):
        """提取业务术语映射"""
        terms = LANGUAGE_TERM_MAP.get(self.language, {})
        
        # 添加业务相关术语
        for module in self.profile.get("modules", []):
            for kw in module.get("keywords", [])[:5]:
                if kw not in terms:
                    terms[kw] = kw
        
        self.profile["query_aliases"] = terms


# ──────────────────────────────────────────────
# Interactive Mode
# ──────────────────────────────────────────────

def interactive_mode():
    """交互式创建 Profile"""
    print("=" * 50)
    print("biz-delivery Profile 创建助手")
    print("=" * 50)
    print()
    
    # 业务域名
    domain = input("业务域名 (如 creative-platform): ").strip()
    if not domain:
        domain = "my-service"
    
    # 仓库路径
    repo_path = input("仓库路径 (绝对路径): ").strip()
    if not repo_path:
        print("错误: 仓库路径不能为空")
        sys.exit(1)
    
    # 语言
    print("\n支持的语言:")
    print("  1. go")
    print("  2. python")
    print("  3. java")
    lang_input = input("选择语言 (1/2/3): ").strip()
    lang_map = {"1": "go", "2": "python", "3": "java"}
    language = lang_map.get(lang_input, "go")
    
    # 生成 Profile
    generator = ProfileGenerator(domain, repo_path, language)
    profile = generator.generate()
    
    # 保存文件
    output_path = Path("profiles") / f"{domain}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Profile 已保存到: {output_path}")
    print(f"\n预览:")
    print(json.dumps(profile, ensure_ascii=False, indent=2)[:500] + "...")
    
    return str(output_path)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="为 biz-delivery 创建 Profile 配置"
    )
    parser.add_argument(
        "--name", "-n",
        help="业务域名名称"
    )
    parser.add_argument(
        "--repo", "-r",
        help="仓库路径"
    )
    parser.add_argument(
        "--language", "-l",
        choices=["go", "python", "java"],
        help="编程语言"
    )
    parser.add_argument(
        "--output", "-o",
        help="输出文件路径"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="交互式模式"
    )
    
    args = parser.parse_args()
    
    # 交互式模式
    if args.interactive:
        output_path = interactive_mode()
        print(f"\nProfile 创建完成: {output_path}")
        return 0
    
    # 命令行模式
    if not args.name or not args.repo:
        parser.print_help()
        print("\n错误: --name 和 --repo 是必需参数（或使用 --interactive）")
        return 1
    
    # 生成 Profile
    generator = ProfileGenerator(args.name, args.repo, args.language or "go")
    profile = generator.generate()
    
    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path("profiles") / f"{args.name}.json"
    
    # 保存文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Profile 已保存: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
