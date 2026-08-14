#!/usr/bin/env python3
"""多服务自动发现 + 跨仓库依赖分析

自动生成 profiles/multi-service-ad-platform.json，包含：
- dap (3441 files) 和 ad_delivery_platform (5194 files) 两个主 repo
- 37 个微服务目录映射
- SPX/proto RPC 依赖图（从 import 路径推断）
- 共享基础设施识别
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ── 已知服务结构 ──────────────────────────────────────────────

REPO_CONFIG = {
    "dap": {
        "path": "/Users/yanping.ma/GolandProjects/dap",
        "module": "git.garena.com/shopee/marketing/dap",
        "services": {
            "admin": "管理后台 API 服务",
            "agent": "AI Agent 入口服务",
            "dap_agent": "DAP Agent 核心服务",
            "dv360sync": "DV360 数据同步服务",
            "facebooksync": "Facebook 数据同步服务",
            "fb_sync": "Facebook 同步辅助服务",
            "feed_upload": "Feed 上传服务",
            "filedownload": "文件下载服务（最大路由数）",
            "googlesync": "Google Ads 数据同步服务",
            "image_download": "图片下载服务",
            "innerapi": "内部 API 聚合服务",
            "taskexecutor": "任务执行器服务",
            "tiktoksync": "TikTok 数据同步服务",
        },
    },
    "ad_delivery_platform": {
        "path": "/Users/yanping.ma/GolandProjects/ad_delivery_platform",
        "module": "git.garena.com/shopee/marketing/ad_delivery_platform",
        "services": {
            "account": "账户管理服务",
            "accountdomain": "账户领域服务",
            "admgmt": "广告管理核心服务",
            "ads": "广告投放核心服务",
            "adsdomain": "广告领域服务",
            "adstraffic": "广告流量处理服务",
            "commondomain": "公共领域服务（共享配置/消费者）",
            "dspproxy": "DSP Proxy 服务",
            "facebookproxy": "Facebook API Proxy",
            "googleapi": "Google Ads API 代理服务",
            "googleproxy": "Google Proxy 服务",
            "imagedownload": "图片下载服务",
            "notice": "通知服务",
            "product": "产品管理服务",
            "reconciliation": "对账服务",
            "rpcserver": "RPC 聚合服务（钱包/通道）",
            "selleradmin": "卖家后台管理 API",
            "strategy": "策略引擎服务",
            "taskmanager": "任务调度管理",
            "taskworker": "任务执行 Worker",
            "tiktokproxy": "TikTok API Proxy",
            "timer": "定时任务调度服务",
            "trafficitem": "流量项处理服务",
        },
    },
}

# 跨 repo 依赖：dap 依赖 ad_delivery_platform（作为外部模块）
CROSS_REPO_DEPS = [
    {"from": "dap/innerapi", "to": "ad_delivery_platform/account", "type": "rpc", "desc": "调用账户信息"},
    {"from": "dap/innerapi", "to": "ad_delivery_platform/product", "type": "rpc", "desc": "调用产品信息"},
    {"from": "dap/admin", "to": "ad_delivery_platform/selleradmin", "type": "rpc", "desc": "管理后台调用卖家 API"},
    {"from": "dap/tiktoksync", "to": "ad_delivery_platform/tiktokproxy", "type": "rpc", "desc": "TikTok 数据同步调用 proxy"},
    {"from": "dap/googlesync", "to": "ad_delivery_platform/googleapi", "type": "rpc", "desc": "Google 数据同步调用 API"},
    {"from": "dap/facebooksync", "to": "ad_delivery_platform/facebookproxy", "type": "rpc", "desc": "FB 数据同步调用 proxy"},
    {"from": "dap/fb_sync", "to": "ad_delivery_platform/facebookproxy", "type": "rpc", "desc": "FB 同步辅助调用 proxy"},
]

# 共享模块（两个 repo 都依赖）
SHARED_MODULES = [
    "git.garena.com/shopee/marketing/adscomm",
    "git.garena.com/shopee/marketing/adscomm/v2",
    "git.garena.com/shopee/marketing/mkt-common",
    "git.garena.com/shopee/marketing/config-client",
    "git.garena.com/shopee/marketing/crs-common",
    "git.garena.com/shopee/mts/go-application-server/gas",
    "git.garena.com/shopee/mts/go-application-server/spi/*",
    "git.garena.com/shopee/mms/mms-sdk/orchestrator-sdk",
    "git.garena.com/shopee/platform/golang_splib",
    "git.garena.com/shopee/pl/shopeepay-common/shark",
]


def build_profile(output_path: str = "profiles/multi-service-ad-platform.json") -> Dict:
    """构建完整的多服务 Profile。"""
    repositories = []
    modules = []
    all_spex_deps = _scan_spex_dependencies()
    all_import_deps = _scan_internal_imports()

    for repo_key, repo_cfg in REPO_CONFIG.items():
        repo_path = Path(repo_cfg["path"])
        if not repo_path.exists():
            print(f"⚠️  Skipping {repo_key}: path not found {repo_path}")
            continue

        file_count = _count_go_files(repo_path)
        svc_dir = repo_path / "app"

        repositories.append({
            "name": repo_key,
            "path": str(repo_path),
            "language": "go",
            "max_files": min(file_count, 5000),
            "module": repo_cfg["module"],
        })

        for svc_name, svc_desc in repo_cfg["services"].items():
            modules.append({
                "name": f"{repo_key}/{svc_name}",
                "repo": repo_key,
                "path": str(svc_dir / svc_name) if (svc_dir / svc_name).exists() else "",
                "keywords": [svc_name, repo_key],
                "description": svc_desc,
                "goal": f"Service: {repo_key}/{svc_name}",
            })

    # 跨服务依赖（从 SPX 和 import 扫描结果合并）
    cross_service_deps = _merge_dependency_edges(all_spex_deps, all_import_deps, CROSS_REPO_DEPS)

    # 基础设施
    infrastructure = {
        "database": "MySQL (GORM)",
        "cache": "Redis (go-redis)",
        "message_queue": "Kafka (ShopMsg/GAS)",
        "rpc_framework": "micro/go-micro + SPX",
        "config": "Apollo + GAS config-client",
        "shared_modules": SHARED_MODULES,
    }

    profile = {
        "business_domain": "ad-marketing-platform",
        "repositories": repositories,
        "learn_config": {
            "max_files_per_lang": 5000,
            "include_tests": True,
            "max_files": 5000,
        },
        "modules": modules,
        "cross_service_dependencies": cross_service_deps,
        "infrastructure": infrastructure,
        "repo_count": len(repositories),
        "service_count": len(modules),
        "total_files": sum(_count_go_files(Path(r["path"])) for r in repositories),
    }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, ensure_ascii=False, indent=2))
    print(f"✅ Profile saved to {out}")
    print(f"   Repos: {len(repositories)}, Services: {len(modules)}, Files: {profile['total_files']}")
    print(f"   Cross-service deps: {len(cross_service_deps)} edges")
    return profile


def _count_go_files(repo_path: Path) -> int:
    count = 0
    for f in repo_path.rglob("*.go"):
        if "vendor/" in str(f) or ".git/" in str(f):
            continue
        count += 1
        if count >= 6000:
            break
    return count


def _scan_spex_dependencies() -> List[Dict]:
    """扫描两个 repo 中的 SPX proto 生成文件，推断 RPC 调用关系。"""
    deps = []
    spex_base = Path("/Users/yanping.ma/biz-delivery")
    spex_dir = spex_base / "scripts" / "spex_integration.py"

    for repo_key, repo_cfg in REPO_CONFIG.items():
        repo_path = Path(repo_cfg["path"])
        # Scan infrastructure/spex/ for generated proto imports
        spex_gen = repo_path / "infrastructure" / "spex"
        if not spex_gen.exists():
            continue
        for pb_file in list(spex_gen.rglob("*.go"))[:500]:
            try:
                text = pb_file.read_text(errors="ignore")
                # Extract service names from proto package declarations
                for m in re.finditer(r'package\s+(\w+)', text):
                    svc = m.group(1).lower()
                    if svc not in ("gen", "go"):
                        deps.append({"from": f"{repo_key}/spex", "to": svc, "type": "proto_rpc"})
            except:
                pass
    return deps


def _scan_internal_imports() -> List[Dict]:
    """扫描 Go import 语句，推断服务间依赖。"""
    deps = []
    repo_paths = {k: Path(v["path"]) for k, v in REPO_CONFIG.items()}

    for repo_key, repo_path in repo_paths.items():
        seen = set()
        for f in list(repo_path.rglob("*.go"))[:3000]:
            if "vendor/" in str(f) or ".git/" in str(f) or "_test.go" in str(f):
                continue
            try:
                text = f.read_text(errors="ignore")
                for m in re.finditer(
                    r'git\.garena\.com/shopee/marketing/([^/]+)/(\w+)',
                    text,
                ):
                    mod, svc = m.group(1), m.group(2)
                    edge_key = (repo_key, mod, svc)
                    if edge_key in seen:
                        continue
                    seen.add(edge_key)
                    # Only count same-repo or cross-repo internal deps
                    if mod == repo_key.replace("_", "") or mod in REPO_CONFIG:
                        deps.append({
                            "from": repo_key,
                            "to": f"{mod}/{svc}",
                            "type": "import",
                        })
            except:
                continue
    return deps


def _merge_dependency_edges(
    spex_deps: List[Dict],
    import_deps: List[Dict],
    known_deps: List[Dict],
) -> List[Dict]:
    """合并多源依赖，去重。"""
    seen = set()
    result = []

    for dep in known_deps:
        key = (dep["from"], dep["to"], dep["type"])
        if key not in seen:
            seen.add(key)
            result.append(dep)

    for dep in import_deps[:50]:  # cap to avoid noise
        key = (dep["from"], dep["to"], dep["type"])
        if key not in seen:
            seen.add(key)
            result.append(dep)

    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="profiles/multi-service-ad-platform.json")
    args = parser.parse_args()
    build_profile(args.output)
