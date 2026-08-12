#!/usr/bin/env python3
"""Profile Registry — 业务 Profile 注册与管理

Usage:
    python3 profile_registry.py --list
    python3 profile_registry.py --register profiles/my-service.json
    python3 profile_registry.py --validate profiles/my-service.json
    python3 profile_registry.py --info creative-platform
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


PROFILES_DIR = Path(__file__).parent.parent / "profiles"
INDEX_FILE = PROFILES_DIR / "index.json"


def load_index() -> dict:
    """加载注册表索引"""
    if not INDEX_FILE.exists():
        return {"profiles": [], "last_updated": ""}
    
    try:
        with open(INDEX_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"profiles": [], "last_updated": ""}


def save_index(index: dict) -> None:
    """保存注册表索引"""
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def list_profiles() -> List[dict]:
    """列出所有已注册的 Profile"""
    index = load_index()
    return index.get("profiles", [])


def register_profile(profile_path: str) -> dict:
    """注册新的 Profile"""
    profile_file = Path(profile_path)
    if not profile_file.exists():
        raise FileNotFoundError(f"Profile not found: {profile_path}")
    
    # 验证 Profile
    try:
        with open(profile_file) as f:
            profile = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in profile: {e}")
    
    # 必需字段检查
    required = ["business_domain", "repositories"]
    missing = [f for f in required if not profile.get(f)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    
    # 添加到索引
    index = load_index()
    
    # 检查是否已存在
    domain = profile["business_domain"]
    for i, p in enumerate(index.get("profiles", [])):
        if p.get("domain") == domain:
            index["profiles"][i] = {
                "path": str(profile_file),
                "domain": domain,
                "last_updated": _get_mtime(profile_file),
            }
            break
    else:
        index.setdefault("profiles", []).append({
            "path": str(profile_file),
            "domain": domain,
            "last_updated": _get_mtime(profile_file),
        })
    
    index["last_updated"] = _now()
    save_index(index)
    
    return {"status": "registered", "domain": domain, "path": str(profile_file)}


def validate_profile(profile_path: str) -> dict:
    """验证 Profile 合法性"""
    profile_file = Path(profile_path)
    if not profile_file.exists():
        return {"status": "error", "message": f"File not found: {profile_path}"}
    
    try:
        with open(profile_file) as f:
            profile = json.load(f)
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Invalid JSON: {e}"}
    
    # 必需字段
    errors = []
    if not profile.get("business_domain"):
        errors.append("Missing 'business_domain'")
    if not profile.get("repositories"):
        errors.append("Missing 'repositories'")
    elif not isinstance(profile.get("repositories"), list):
        errors.append("'repositories' must be a list")
    else:
        for i, repo in enumerate(profile["repositories"]):
            if not repo.get("name"):
                errors.append(f"repositories[{i}].name is required")
            if not repo.get("path"):
                errors.append(f"repositories[{i}].path is required")
            elif not Path(repo["path"]).exists():
                errors.append(f"repositories[{i}].path does not exist: {repo['path']}")
    
    if errors:
        return {"status": "invalid", "errors": errors}
    
    return {
        "status": "valid",
        "domain": profile.get("business_domain"),
        "repositories": len(profile.get("repositories", [])),
        "modules": len(profile.get("modules", [])),
    }


def get_profile_info(domain: str) -> Optional[dict]:
    """获取指定域的 Profile 信息"""
    index = load_index()
    for p in index.get("profiles", []):
        if p.get("domain") == domain:
            profile_path = p.get("path")
            if profile_path and Path(profile_path).exists():
                with open(profile_path) as f:
                    profile = json.load(f)
                return {
                    "domain": domain,
                    "path": profile_path,
                    **{k: profile.get(k) for k in ["repositories", "modules", "state_machines"]},
                }
    return None


def _get_mtime(path: Path) -> str:
    """获取文件修改时间"""
    import time
    mtime = path.stat().st_mtime
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))


def _now() -> str:
    """获取当前时间"""
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")


def main():
    parser = argparse.ArgumentParser(description="Profile Registry")
    parser.add_argument("--action", choices=["list", "register", "validate", "info"], default="list")
    parser.add_argument("--profile", help="Profile 文件路径")
    parser.add_argument("--domain", help="业务域名称")
    args = parser.parse_args()
    
    try:
        if args.action == "list":
            profiles = list_profiles()
            print(f"已注册 {len(profiles)} 个 Profile:\n")
            for p in profiles:
                print(f"  {p.get('domain', 'unknown'):30s} ← {p.get('path', '')}")
            print(f"\n最后更新: {profiles[-1].get('last_updated', 'N/A') if profiles else 'N/A'}")
            
        elif args.action == "register":
            if not args.profile:
                print("ERROR: --profile is required")
                sys.exit(1)
            result = register_profile(args.profile)
            print(f"✅ {result['status']}: {result['domain']}")
            
        elif args.action == "validate":
            if not args.profile:
                print("ERROR: --profile is required")
                sys.exit(1)
            result = validate_profile(args.profile)
            if result["status"] == "valid":
                print(f"✅ Profile valid: {result['domain']}")
                print(f"   Repositories: {result['repositories']}")
                print(f"   Modules: {result.get('modules', 0)}")
            else:
                print(f"❌ Profile invalid:")
                for err in result.get("errors", []):
                    print(f"   - {err}")
                sys.exit(1)
                
        elif args.action == "info":
            if not args.domain:
                print("ERROR: --domain is required")
                sys.exit(1)
            info = get_profile_info(args.domain)
            if info:
                print(json.dumps(info, indent=2, ensure_ascii=False))
            else:
                print(f"❌ Profile not found for domain: {args.domain}")
                sys.exit(1)
                
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
