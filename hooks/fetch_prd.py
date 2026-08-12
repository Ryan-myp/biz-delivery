#!/usr/bin/env python3
"""Hook: 获取 PRD

定义如何从不同来源获取 PRD 内容。
根据业务需求实现此函数。

Usage:
    from hooks.fetch_prd import fetch_prd
    
    prd_text = fetch_prd(prd_url, workspace_root)
"""

from pathlib import Path
from typing import Optional


def fetch_prd(prd_input: str, workspace_root: str) -> str:
    """从 URL 或本地路径获取 PRD 内容
    
    Args:
        prd_input: PRD URL 或本地文件路径
        workspace_root: 工作区根目录
        
    Returns:
        PRD 文本内容
        
    Examples:
        # 从 Confluence 获取
        prd = fetch_prd("https://wiki.example.com/prd/123", "/path/to/work")
        
        # 从本地文件获取
        prd = fetch_prd("/path/to/prd.md", "/path/to/work")
    """
    prd_path = Path(prd_input)
    
    # 如果是本地文件
    if prd_path.exists() and prd_path.is_file():
        return prd_path.read_text(encoding="utf-8")
    
    # 如果是 URL，实现相应的抓取逻辑
    # 例如从 Confluence、Wiki、Google Docs 等获取
    if prd_input.startswith("http"):
        # TODO: 实现 HTTP 抓取逻辑
        raise NotImplementedError(f"Fetching PRD from URL is not implemented: {prd_input}")
    
    # 尝试在 workspace_root 下查找
    candidate = Path(workspace_root) / prd_input
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    
    raise ValueError(f"PRD not found: {prd_input}")


# 业务特定实现示例
def fetch_prd_from_confluence(prd_url: str, token: str) -> str:
    """从 Confluence 获取 PRD（示例实现）"""
    # 需要安装 requests 库
    # import requests
    # response = requests.get(prd_url, auth=("email", token))
    # return response.text
    raise NotImplementedError("Confluence fetch not implemented")


def fetch_prd_from_local(prd_path: str) -> str:
    """从本地 Markdown 文件获取 PRD"""
    path = Path(prd_path)
    if not path.exists():
        raise FileNotFoundError(f"PRD file not found: {prd_path}")
    return path.read_text(encoding="utf-8")
