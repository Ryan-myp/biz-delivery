#!/usr/bin/env python3
"""自动发现 GolandProjects 下的所有 Go 服务，生成 multi-service profile。

用途：一键扫描所有服务的依赖关系，生成完整的服务拓扑。

Usage:
    python3 scripts/auto_discover_services.py --output profiles/multi-service.json
    python3 scripts/auto_discover_services.py --path /Users/yanping.ma/GolandProjects --output profiles/all-services.json
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def discover_go_services(base_path: str, max_services: int = 100) -> List[Dict[str, Any]]:
    """扫描 base_path 下所有 Go 服务（含 go.mod 的目录）。"""
    services = []
    base = Path(base_path)

    for go_mod in base.rglob("go.mod"):
        if len(services) >= max_services:
            break
        # Skip vendor and node_modules
        if "vendor/" in str(go_mod) or "node_modules/" in str(go_mod):
            continue

        repo_path = go_mod.parent
        try:
            # Count Go files (capped at 5000 for speed)
            count = 0
            for f in repo_path.rglob("*.go"):
                if "vendor/" in str(f) or ".git/" in str(f):
                    continue
                count += 1
                if count >= 5000:
                    break

            # Get module name from go.mod
            mod_name = ""
            try:
                mod_content = go_mod.read_text(encoding="utf-8", errors="ignore")
                for line in mod_content.split("\n"):
                    line = line.strip()
                    if line.startswith("module "):
                        mod_name = line[7:].strip()
                        break
            except Exception:
                pass

            services.append({
                "name": repo_path.name,
                "path": str(repo_path),
                "language": "go",
                "max_files": min(count, 5000),
                "module_name": mod_name,
                "file_count": count,
            })
        except Exception:
            continue

    # Sort by file count descending
    services.sort(key=lambda s: s["file_count"], reverse=True)
    return services


def build_cross_repo_imports(services: List[Dict]) -> List[Dict]:
    """检测服务间的 import 依赖关系。

    策略：
    1. 收集所有服务的 module name
    2. 对每个服务，扫描其 import 语句中的其他服务 module name
    3. 构建依赖边
    """
    # Build module name → service name map
    mod_to_service = {}
    for svc in services:
        mod = svc.get("module_name", "")
        if mod:
            mod_to_service[mod] = svc["name"]
        mod_to_service[svc["name"]] = svc["name"]

    deps = []
    for svc in services:
        repo_path = Path(svc["path"])
        svc_deps = set()

        # Scan imports in all .go files (limited)
        for go_file in list(repo_path.rglob("*.go"))[:2000]:
            if "vendor/" in str(go_file) or ".git/" in str(go_file):
                continue
            try:
                text = go_file.read_text(encoding="utf-8", errors="ignore")
                for m in __import__('re').findall(r'"([^"]+)"', text):
                    # Check if this import matches any known service module
                    for known_mod, known_svc in mod_to_service.items():
                        if known_mod and known_mod in m and known_svc != svc["name"]:
                            svc_deps.add(known_svc)
            except Exception:
                continue

        for dep in svc_deps:
            deps.append({
                "from": svc["name"],
                "to": dep,
                "type": "import",
            })

    return deps


def infer_shared_infra(services: List[Dict]) -> Dict[str, Any]:
    """推断共享基础设施（MySQL, Redis, Kafka 等）。"""
    infra = {
        "databases": {},
        "cache": {},
        "message_queues": {},
        "external_apis": [],
    }

    for svc in services:
        repo_path = Path(svc["path"])
        for go_file in list(repo_path.rglob("*.go"))[:500]:
            if "vendor/" in str(go_file) or ".git/" in str(go_file):
                continue
            try:
                text = go_file.read_text(encoding="utf-8", errors="ignore")
                # MySQL
                if re_search(text, r'gorm\.(Open|DB|Table)\s*\('):
                    db_name = extract_db_name(text)
                    if db_name:
                        infra["databases"][db_name] = infra["databases"].get(db_name, []) + [svc["name"]]
                # Redis
                if re_search(text, r'redis\.\w+|redigo\.\w+|go-redis'):
                    infra["cache"][svc["name"]] = "redis"
                # Kafka
                if re_search(text, r'kafka|sarama|confluent'):
                    infra["message_queues"][svc["name"]] = "kafka"
            except Exception:
                continue

    # Convert lists to counts
    for k in infra:
        if isinstance(infra[k], dict):
            infra[k] = {k2: len(v2) if isinstance(v2, list) else v2 for k2, v2 in infra[k].items()}

    return infra


def re_search(text: str, pattern: str) -> bool:
    import re
    return bool(re.search(pattern, text, re.IGNORECASE))


def extract_db_name(text: str) -> Optional[str]:
    import re
    m = re.search(r'gorm\.Open\s*\(\s*"([^"]+)"', text)
    if m:
        return m.group(1).split("/")[-1].split("?")[0]
    return None


def generate_profile(base_path: str = "/Users/yanping.ma/GolandProjects",
                     output_path: str = "profiles/multi-service.json",
                     max_services: int = 50) -> Dict:
    """生成完整的多服务 Profile。"""
    print(f"🔍 Discovering Go services in {base_path}...")
    services = discover_go_services(base_path, max_services=max_services)
    print(f"  Found {len(services)} services (total {sum(s['file_count'] for s in services)} files)")

    # Build cross-repo dependencies
    print("  🔗 Building cross-repo dependency graph...")
    deps = build_cross_repo_imports(services)
    print(f"  Found {len(deps)} import dependencies")

    # Infer shared infrastructure
    print("  🏗️  Inferring shared infrastructure...")
    infra = infer_shared_infra(services)

    # Build module descriptions
    modules = []
    for svc in services:
        modules.append({
            "name": f"{svc['name']} / {svc['name']}",
            "keywords": [svc["name"], svc.get("module_name", "")],
            "goal": f"Service: {svc['name']} ({svc['file_count']} Go files)",
        })

    profile = {
        "business_domain": "multi-service-platform",
        "repositories": [
            {
                "name": s["name"],
                "path": s["path"],
                "language": "go",
                "max_files": s["max_files"],
            }
            for s in services
        ],
        "learn_config": {
            "max_files_per_lang": 5000,
            "include_tests": True,
        },
        "modules": modules,
        "cross_repo_deps": deps,
        "infrastructure": infra,
        "service_count": len(services),
        "total_files": sum(s["file_count"] for s in services),
    }

    # Save
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, ensure_ascii=False, indent=2))
    print(f"  ✅ Profile saved to {out}")

    return profile


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="/Users/yanping.ma/GolandProjects")
    parser.add_argument("--output", default="profiles/multi-service.json")
    parser.add_argument("--max-services", type=int, default=50)
    args = parser.parse_args()

    generate_profile(args.path, args.output, args.max_services)
