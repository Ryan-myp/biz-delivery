#!/usr/bin/env python3
"""
GitManager — Git 仓库操作封装

职责：
  - 克隆/打开本地仓库
  - 创建分支、提交代码
  - 推送变更（可选）
  - 列出文件和目录结构

设计原则：
  - 不依赖 gitpython，直接用 subprocess（更可靠）
  - 支持 SSH/HTTPS URL
  - 支持已有本地路径
"""

import subprocess
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import json


@dataclass
class RepoConfig:
    """仓库配置"""
    name: str
    url: str  # git URL 或本地路径
    branch: str = "main"
    local_path: Optional[str] = None  # 如果已有本地副本
    language: str = "go"
    
    @property
    def is_local(self) -> bool:
        return self.local_path is not None or str(self.url).startswith("/") or str(self.url).startswith(".")
    
    @property
    def work_dir(self) -> Path:
        if self.local_path:
            return Path(self.local_path)
        # 默认克隆到 /tmp/biz-delivery/repos/{name}
        return Path(f"/tmp/biz-delivery/repos/{self.name}")


class GitManager:
    """Git 仓库操作管理器"""
    
    def __init__(self, repo: RepoConfig, username: str = "", email: str = ""):
        self.repo = repo
        self.username = username
        self.email = email
        self._cloned = False
    
    def ensure_repo(self) -> bool:
        """确保仓库已就绪（克隆或打开）"""
        work_dir = self.repo.work_dir
        
        if self.repo.is_local and work_dir.exists():
            # 本地已有仓库，直接打开
            return True
        
        if work_dir.exists():
            # 本地有目录但不是 git repo，先检查
            if (work_dir / ".git").exists():
                return True
            # 删除并重新克隆
            shutil.rmtree(work_dir)
        
        if self.repo.is_local:
            # 本地路径，复制
            src = Path(self.repo.url)
            if src.exists():
                shutil.copytree(src, work_dir, dirs_exist_ok=True)
                self._init_git(work_dir)
                return True
        
        # 远程仓库，克隆
        if self.repo.url.startswith("http") or self.repo.url.startswith("git@"):
            self._clone(work_dir)
            return True
        
        return False
    
    def _init_git(self, path: Path):
        """初始化 git repo"""
        self._run(["git", "init"], cwd=path)
        if self.username:
            self._run(["git", "config", "user.name", self.username], cwd=path)
        if self.email:
            self._run(["git", "config", "user.email", self.email], cwd=path)
    
    def _clone(self, target: Path):
        """克隆远程仓库"""
        self._run(["git", "clone", self.repo.url, str(target)])
        # Checkout 到目标分支
        self._run(["git", "checkout", "-b", self.repo.branch], cwd=target)
        self._cloned = True
    
    def _run(self, cmd: List[str], cwd: Optional[Path] = None) -> str:
        """运行 git 命令"""
        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                raise RuntimeError(f"git {' '.join(cmd)} failed: {result.stderr}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"git command timed out: {' '.join(cmd)}")
    
    def create_branch(self, branch_name: str) -> str:
        """创建新分支"""
        work_dir = self.repo.work_dir
        self._run(["git", "checkout", "-b", branch_name], cwd=work_dir)
        return branch_name
    
    def get_branch(self) -> str:
        """获取当前分支"""
        return self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"], 
                       cwd=self.repo.work_dir)
    
    def add_file(self, rel_path: str, content: str):
        """添加/更新文件"""
        work_dir = self.repo.work_dir
        full_path = work_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
    
    def commit(self, message: str) -> str:
        """提交变更"""
        work_dir = self.repo.work_dir
        self._run(["git", "add", "."], cwd=work_dir)
        self._run(["git", "commit", "-m", message], cwd=work_dir)
        return self._run(["git", "rev-parse", "--short", "HEAD"], cwd=work_dir)
    
    def push(self, branch: Optional[str] = None, upstream: bool = True):
        """推送变更"""
        work_dir = self.repo.work_dir
        branch = branch or self.get_branch()
        cmd = ["git", "push"]
        if upstream:
            cmd.extend(["-u", "origin", branch])
        else:
            cmd.extend([branch])
        self._run(cmd, cwd=work_dir)
    
    def list_files(self, pattern: str = "**/*", exclude_git: bool = True) -> List[str]:
        """列出文件"""
        work_dir = self.repo.work_dir
        if exclude_git:
            # 排除 .git 目录
            result = self._run(["find", ".", "-type", "f", "-not", "-path", "./.git/*"], 
                             cwd=work_dir)
            return [f[2:] for f in result.split("\n") if f]  # Remove leading ./
        return []
    
    def get_file_content(self, rel_path: str) -> str:
        """获取文件内容"""
        work_dir = self.repo.work_dir
        full_path = work_dir / rel_path
        if full_path.exists():
            return full_path.read_text(encoding="utf-8")
        return ""
    
    def status(self) -> Dict[str, Any]:
        """获取仓库状态"""
        work_dir = self.repo.work_dir
        try:
            status = self._run(["git", "status", "--porcelain"], cwd=work_dir)
            branches = self._run(["git", "branch", "-l"], cwd=work_dir)
            return {
                "dirty": bool(status),
                "current_branch": self.get_branch(),
                "branches": [b.strip().lstrip("* ") for b in branches.split("\n") if b.strip()],
                "changes": status.split("\n") if status else [],
            }
        except Exception as e:
            return {"error": str(e)}


# ──────────────────────────────────────────────
# 用法示例
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # 测试本地仓库
    repo = RepoConfig(
        name="test-repo",
        url="/Users/yanping.ma/GolandProjects/creative-platform",
        branch="test-branch",
        language="go"
    )
    gm = GitManager(repo, username="test", email="test@test.com")
    gm.ensure_repo()
    print(f"✅ Repo: {gm.repo.work_dir}")
    print(f"Branch: {gm.get_branch()}")
    print(f"Files: {len(gm.list_files())} files")
    
    # 测试写文件
    gm.add_file("test/hello.txt", "Hello from biz-delivery!")
    commit_hash = gm.commit("Test commit")
    print(f"Committed: {commit_hash}")
