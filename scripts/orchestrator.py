#!/usr/bin/env python3
"""
biz-delivery Orchestrator — 流程编排层（多任务支持）

设计原则：
  - Core Skills 完全独立，不依赖本模块
  - 本模块只是一个协调器，可以随时抽离
  - 通过 LLMClient 切换底层模型
  - 支持多项目、多任务、多对话（类似 Codex）

使用方式：
  # 命令行
  python3 scripts/orchestrator.py --profile profiles/default.json --prd prd.md

  # Web API
  python3 scripts/web_api.py --port 8000
"""

import json
import time
import threading
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

from scripts.llm_client import LLMClient
from scripts.git_manager import GitManager, RepoConfig
from scripts.context_manager import MemorySystem, ContextWindow, TokenEstimator


# ──────────────────────────────────────────────
# Stage & Status
# ──────────────────────────────────────────────

class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

STAGE_ORDER = ["learn", "review", "td", "tasks", "agent", "test", "automation"]


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class ChatMessage:
    role: str       # "user" | "assistant" | "system"
    content: str
    timestamp: str
    stage: str = ""


@dataclass
class StageRecord:
    status: StageStatus = StageStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output_dir: str = ""
    artifacts: Dict[str, str] = field(default_factory=dict)
    error: str = ""
    summary: str = ""


@dataclass
class TaskSession:
    """单个任务/对话 — 一个项目可以有多个 TaskSession"""
    id: str
    name: str
    created_at: str
    updated_at: str
    
    # Context
    prd_text: str = ""
    profile_path: str = ""
    output_dir: str = ""
    wiki_path: Optional[str] = None
    
    # 多仓库支持
    repositories: List[Dict] = field(default_factory=list)  # [{name, url, branch, path}]
    git_managers: Dict[str, GitManager] = field(default_factory=dict)  # name -> GitManager
    target_branch: str = ""  # 为当前任务创建的功能分支
    
    # LLM
    llm_client: Optional[LLMClient] = None
    model_name: str = "agnes-2.0-flash"
    
    # Stage tracking (optional — task can be free-chat without pipeline)
    current_stage_idx: int = 0
    stages: Dict[str, StageRecord] = field(default_factory=dict)
    use_pipeline: bool = False  # Whether this task uses guided pipeline
    
    # Conversation
    messages: List[ChatMessage] = field(default_factory=list)
    
    # 上下文管理
    context_window: Optional[ContextWindow] = None
    memory_system: Optional[MemorySystem] = None
    context_truncated: bool = False  # 是否已触发压缩
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.stages:
            for s in STAGE_ORDER:
                self.stages[s] = StageRecord()
    
    def get_repo_manager(self, repo_name: str) -> Optional[GitManager]:
        """获取指定仓库的 GitManager"""
        return self.git_managers.get(repo_name)
    
    def ensure_repos(self):
        """确保所有仓库已就绪"""
        for repo_cfg in self.repositories:
            name = repo_cfg.get("name", "")
            if name in self.git_managers:
                continue
            repo = RepoConfig(
                name=name,
                url=repo_cfg.get("path") or repo_cfg.get("url", ""),
                branch=repo_cfg.get("branch", "main"),
                local_path=repo_cfg.get("path"),
                language=repo_cfg.get("language", "go"),
            )
            gm = GitManager(repo, username="biz-delivery", email="biz@delivery.ai")
            if gm.ensure_repo():
                self.git_managers[name] = gm
    
    def create_feature_branch(self, repo_name: str, feature_name: str) -> str:
        """为指定仓库创建功能分支"""
        gm = self.git_managers.get(repo_name)
        if not gm:
            return ""
        branch = f"biz-delivery/{feature_name}"
        gm.create_branch(branch)
        return branch
    
    def commit_to_repo(self, repo_name: str, rel_path: str, content: str, commit_msg: str) -> str:
        """提交文件到指定仓库"""
        gm = self.git_managers.get(repo_name)
        if not gm:
            return ""
        gm.add_file(rel_path, content)
        return gm.commit(commit_msg)
    
    def add_message(self, role: str, content: str, stage: str = ""):
        self.messages.append(ChatMessage(
            role=role, content=content,
            timestamp=datetime.now().isoformat(), stage=stage,
        ))
        self.updated_at = datetime.now().isoformat()
    
    @property
    def current_stage(self) -> str:
        if not self.use_pipeline or self.current_stage_idx >= len(STAGE_ORDER):
            return ""
        return STAGE_ORDER[self.current_stage_idx]
    
    @property
    def progress(self) -> dict:
        if not self.use_pipeline:
            return {"total": 0, "completed": 0, "percent": 0, "current_stage": ""}
        total = len(STAGE_ORDER)
        completed = sum(1 for s in self.stages.values() if s.status == StageStatus.COMPLETED)
        return {
            "total": total,
            "completed": completed,
            "percent": int(completed / total * 100),
            "current_stage": self.current_stage,
        }
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "prd_text": self.prd_text[:200] + "..." if len(self.prd_text) > 200 else self.prd_text,
            "profile_path": self.profile_path,
            "output_dir": self.output_dir,
            "wiki_path": self.wiki_path,
            "model_name": self.model_name,
            "use_pipeline": self.use_pipeline,
            "current_stage": self.current_stage,
            "progress": self.progress,
            "messages": [asdict(m) for m in self.messages[-20:]],  # last 20
            "context_stats": {
                "total_tokens": TokenEstimator.count_messages([asdict(m) for m in self.messages]) if self.messages else 0,
                "truncated": self.context_truncated,
                "memory_count": len(self.memory_system.memories) if self.memory_system else 0,
            },
            "stages": {k: {"status": v.status.value if hasattr(v.status, "value") else v.status, **{"started_at": v.started_at, "completed_at": v.completed_at, "output_dir": v.output_dir, "artifacts": v.artifacts, "error": v.error, "summary": v.summary}} for k, v in self.stages.items()},
            "metadata": self.metadata,
        }
    
    def get_context_messages(self) -> List[Dict]:
        """获取适配后的上下文消息（自动压缩）"""
        if not self.messages:
            return []
        
        msg_dicts = [asdict(m) for m in self.messages]
        
        # 初始化 context window
        if not self.context_window:
            self.context_window = ContextWindow(max_tokens=8000, model=self.model_name)
        
        # 检查是否需要压缩
        if self.context_window.should_compress(msg_dicts) and not self.context_truncated:
            self.context_truncated = True
            # 生成记忆
            if self.memory_system:
                summary = self.context_window.summarizer.summarize(msg_dicts)
                self.memory_system.add(
                    "context", 
                    f"会话摘要: {summary[:200]}",
                    tags=["auto_summary", self.id],
                    task_id=self.id
                )
        
        return self.context_window.fit_messages(msg_dicts)
    
    def get_memory_context(self) -> str:
        """获取相关记忆上下文"""
        if not self.memory_system:
            return ""
        # 基于 PRD 搜索相关记忆
        query = self.prd_text[:100] if self.prd_text else ""
        memories = self.memory_system.search(query, limit=3)
        if not memories:
            memories = self.memory_system.get_by_task(self.id)[:3]
        
        if not memories:
            return ""
        
        return "\n".join(f"- [{m.type}] {m.content}" for m in memories)


# ──────────────────────────────────────────────
# Project
# ──────────────────────────────────────────────

@dataclass
class Project:
    id: str
    name: str
    created_at: str
    updated_at: str
    output_root: str  # Base dir for all tasks
    tasks: Dict[str, TaskSession] = field(default_factory=dict)
    
    def add_task(self, name: str, prd_text: str = "", profile_path: str = "",
                 use_pipeline: bool = True, model_name: str = "agnes-2.0-flash") -> TaskSession:
        task_id = str(uuid.uuid4())[:8]
        task = TaskSession(
            id=task_id,
            name=name,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            prd_text=prd_text,
            profile_path=profile_path,
            output_dir=str(Path(self.output_root) / task_id),
            use_pipeline=use_pipeline,
            model_name=model_name,
        )
        # Init LLM client
        try:
            task.llm_client = LLMClient(model=model_name)
        except ValueError:
            task.llm_client = None
        self.tasks[task_id] = task
        self.updated_at = datetime.now().isoformat()
        return task
    
    def get_task(self, task_id: str) -> Optional[TaskSession]:
        return self.tasks.get(task_id)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "output_root": self.output_root,
            "task_count": len(self.tasks),
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
        }


# ──────────────────────────────────────────────
# Project Store（内存 + JSON 持久化）
# ──────────────────────────────────────────────

class ProjectStore:
    def __init__(self, store_path: str = "/tmp/biz-delivery/projects.json"):
        self.store_path = Path(store_path)
        self.projects: Dict[str, Project] = {}
        self._load()
    
    def _load(self):
        if self.store_path.exists():
            try:
                data = json.loads(self.store_path.read_text())
                for pid, pdata in data.get("projects", {}).items():
                    project = Project(
                        id=pdata["id"],
                        name=pdata["name"],
                        created_at=pdata["created_at"],
                        updated_at=pdata["updated_at"],
                        output_root=pdata["output_root"],
                    )
                    for tid, tdata in pdata.get("tasks", {}).items():
                        task = TaskSession(
                            id=tdata["id"],
                            name=tdata["name"],
                            created_at=tdata["created_at"],
                            updated_at=tdata["updated_at"],
                            prd_text=tdata.get("prd_text", ""),
                            profile_path=tdata.get("profile_path", ""),
                            output_dir=tdata.get("output_dir", ""),
                            wiki_path=tdata.get("wiki_path"),
                            use_pipeline=tdata.get("use_pipeline", False),
                            model_name=tdata.get("model_name", "agnes-2.0-flash"),
                            current_stage_idx=tdata.get("current_stage_idx", 0),
                            metadata=tdata.get("metadata", {}),
                        )
                        for sname, srec in tdata.get("stages", {}).items():
                            # Convert string status back to StageStatus enum
                            raw_status = srec.get("status", "pending")
                            if isinstance(raw_status, str):
                                try:
                                    srec["status"] = StageStatus(raw_status)
                                except ValueError:
                                    srec["status"] = StageStatus.PENDING
                            task.stages[sname] = StageRecord(**srec)
                        for msg in tdata.get("messages", []):
                            task.messages.append(ChatMessage(**msg))
                        project.tasks[tid] = task
                    self.projects[pid] = project
            except Exception as e:
                print(f"⚠️ Failed to load store: {e}")
    
    def _save(self):
        data = {
            "projects": {
                pid: p.to_dict() for pid, p in self.projects.items()
            }
        }
        # Save without LLM clients and large message content
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    
    def create_project(self, name: str, output_root: str = "/tmp/biz-delivery") -> Project:
        pid = str(uuid.uuid4())[:8]
        project = Project(
            id=pid,
            name=name,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            output_root=output_root,
        )
        Path(output_root).mkdir(parents=True, exist_ok=True)
        self.projects[pid] = project
        self._save()
        return project
    
    def list_projects(self) -> List[Project]:
        return list(self.projects.values())
    
    def get_project(self, project_id: str) -> Optional[Project]:
        return self.projects.get(project_id)
    
    def delete_project(self, project_id: str) -> bool:
        if project_id in self.projects:
            del self.projects[project_id]
            self._save()
            return True
        return False


# ──────────────────────────────────────────────
# Pipeline Orchestrator
# ──────────────────────────────────────────────

class PipelineOrchestrator:
    """流程编排器 — 可选的，用于 guided pipeline 模式"""
    
    on_stage_start = None
    on_stage_complete = None
    on_stage_error = None
    
    def __init__(self, profile_path: str, llm_model: str = "agnes-2.0-flash"):
        self.profile_path = profile_path
        self.model_name = llm_model
        try:
            self.llm_client = LLMClient(model=llm_model)
        except ValueError:
            self.llm_client = None
    
    def run_stage(self, task: TaskSession, stage: str) -> dict:
        """执行单个阶段"""
        if stage not in STAGE_ORDER:
            return {"status": "failed", "error": f"Unknown stage: {stage}"}
        
        rec = task.stages[stage]
        if rec.status == StageStatus.COMPLETED:
            return {"status": "completed", "message": f"Stage {stage} already done"}
        
        rec.status = StageStatus.RUNNING
        rec.started_at = datetime.now().isoformat()
        
        if self.on_stage_start:
            self.on_stage_start(task, stage)
        
        try:
            handler = getattr(self, f"_exec_{stage}", None)
            if handler:
                result = handler(task)
            else:
                result = {"status": "skipped", "message": f"No handler for {stage}"}
            
            rec.status = StageStatus.COMPLETED
            rec.completed_at = datetime.now().isoformat()
            rec.summary = result.get("summary", "")
            rec.artifacts.update(result.get("artifacts", {}))
            
            if self.on_stage_complete:
                self.on_stage_complete(task, stage, rec)
            
            return {"status": "completed", **result}
            
        except Exception as e:
            rec.status = StageStatus.FAILED
            rec.error = str(e)
            rec.completed_at = datetime.now().isoformat()
            
            if self.on_stage_error:
                self.on_stage_error(task, stage, e)
            
            return {"status": "failed", "error": str(e)}
    
    def chat(self, task: TaskSession, message: str, stage: Optional[str] = None) -> dict:
        """对话接口 — 集成记忆和上下文管理"""
        target_stage = stage or task.current_stage
        
        # 初始化记忆系统
        if not task.memory_system:
            task.memory_system = MemorySystem()
        
        task.add_message("user", message, target_stage)
        
        # 构建系统提示（包含记忆上下文）
        system_prompt = self._build_system_prompt(task, target_stage)
        memory_context = task.get_memory_context()
        if memory_context:
            system_prompt += f"\n\n【相关记忆】\n{memory_context}"
        
        # 获取适配后的上下文
        context_messages = task.get_context_messages()
        
        try:
            if task.llm_client:
                # 使用完整的上下文消息列表
                response = task.llm_client.chat_with_messages(
                    context_messages + [{"role": "user", "content": message}]
                )
                reply = response.get("content", "")
                # 记录 token 使用
                task.metadata["last_tokens"] = response.get("usage", {}).get("total_tokens", 0)
            else:
                reply = f"[Demo mode] 收到消息: {message}"
        except Exception as e:
            reply = f"LLM 调用失败: {e}"
        
        task.add_message("assistant", reply, target_stage)
        return {
            "stage": target_stage, 
            "reply": reply, 
            "model": task.model_name,
            "tokens_used": task.metadata.get("last_tokens", 0),
            "context_truncated": task.context_truncated,
        }
    
    def _build_system_prompt(self, task: TaskSession, stage: str) -> str:
        desc = {
            "learn": "知识提取阶段",
            "review": "PRD 审查阶段 — 基于代码 IR 审查 PRD",
            "td": "技术方案生成阶段",
            "tasks": "Agent 任务分解阶段",
            "agent": "Agent 代码执行阶段",
            "test": "测试用例生成阶段",
            "automation": "自动化执行阶段",
            "": "自由对话",
        }.get(stage, stage)
        return f"""你是 biz-delivery 智能交付助手，当前模式: {desc}

PRD（如有）:
{task.prd_text[:500] if task.prd_text else '(无 PRD，自由对话模式)'}

输出要求：简洁、实用、针对当前阶段提供具体建议。"""
    
    def _build_user_prompt(self, task: TaskSession, stage: str, message: str) -> str:
        history = task.messages[-6:]
        history_text = "\n".join(
            f"{'用户' if m.role == 'user' else '助手'}: {m.content}"
            for m in history
        )
        return f"""[对话历史]
{history_text if history_text else '(无历史)'}

[当前消息]
{message}"""
    
    # ── Stage Executors ──
    
    def _exec_learn(self, task: TaskSession) -> dict:
        """Stage 1: 知识提取 — 从实际仓库构建 IR"""
        from scripts.learn_repo import learn_from_repos
        
        # 确保仓库已就绪
        task.ensure_repos()
        
        knowledge_dir = Path(task.output_dir) / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            result = learn_from_repos(
                profile_path=task.profile_path or "profiles/default.json",
                output_dir=str(knowledge_dir),
                wiki_path=task.wiki_path,
            )
            
            # 保存 IR 摘要
            summary = {
                "repo_name": getattr(result, 'repo_name', 'unknown'),
                "language": getattr(result, 'language', 'unknown'),
                "structs": len(getattr(result, 'structs', [])),
                "functions": len(getattr(result, 'functions', [])),
                "routes": len(getattr(result, 'routes', [])),
            }
            summary_file = knowledge_dir / "ir_summary.json"
            summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
            
            # 保存 IR 到目标仓库
            for name, gm in task.git_managers.items():
                ir_dir = gm.repo.work_dir / ".biz-delivery"
                ir_dir.mkdir(exist_ok=True)
                (ir_dir / "ir_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
            
            return {
                "summary": f"知识提取完成: {summary['functions']} 函数, {summary['structs']} 结构体",
                "artifacts": {"ir_summary": str(summary_file)},
            }
        except Exception as e:
            return {"summary": f"学习失败: {e}", "artifacts": {}}
    
    def _exec_review(self, task: TaskSession) -> dict:
        from scripts.review_engine import ReviewEngine
        review_dir = Path(task.output_dir) / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        try:
            profile_path = task.profile_path or "profiles/default.json"
            profile = json.load(open(profile_path))
            engine = ReviewEngine(profile, str(review_dir), wiki_path=task.wiki_path)
            result = engine.review(task.prd_text)
            return {"summary": "审查完成", "artifacts": {"prompt": result.get("prompt_file", "")}}
        except Exception as e:
            return {"summary": f"审查失败: {e}", "artifacts": {}}
    
    def _exec_td(self, task: TaskSession) -> dict:
        """Stage 3: 技术方案 + 代码生成 — 写入目标仓库"""
        from scripts.td_engine import TDEngine
        
        td_dir = Path(task.output_dir) / "td"
        td_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            profile = json.load(open(task.profile_path or "profiles/default.json"))
            engine = TDEngine(profile, str(td_dir), wiki_path=task.wiki_path)
            result = engine.generate_td(task.prd_text, "")
            
            # 写入技术方案到仓库
            td_file = td_dir / "technical_design.md"
            if td_file.exists():
                for name, gm in task.git_managers.items():
                    tech_dir = gm.repo.work_dir / ".biz-delivery" / "tech-design"
                    tech_dir.mkdir(parents=True, exist_ok=True)
                    (tech_dir / f"{task.id}.md").write_text(td_file.read_text())
            
            return {
                "summary": "技术方案已生成并写入仓库",
                "artifacts": {"report": result.get("report_file", "")},
            }
        except Exception as e:
            return {"summary": f"TD 失败: {e}", "artifacts": {}}
    
    def _exec_agent(self, task: TaskSession) -> dict:
        """Stage 5: Agent 执行 — 生成实际代码并写入仓库"""
        from scripts.delivery_pipeline import AgentExecutor, AgentTask
        
        tasks_dir = Path(task.output_dir) / "tasks"
        tasks_file = tasks_dir / "agent_tasks.json"
        if not tasks_file.exists():
            return {"summary": "跳过: 未找到任务文件，请先执行 Tasks 阶段", "artifacts": {}}
        
        try:
            tasks_data = json.loads(tasks_file.read_text())
            tasks = [AgentTask(**t) for t in tasks_data]
            
            executor = AgentExecutor(
                profile=json.load(open(task.profile_path or "profiles/default.json")),
                output_dir=task.output_dir,
            )
            
            # 为每个仓库创建功能分支
            for name, gm in task.git_managers.items():
                branch = f"biz-delivery/{task.name[:20]}"
                gm.create_branch(branch)
                task.create_feature_branch(name, task.name[:20])
            
            result = executor.execute(tasks, task.llm_client)
            
            # 提交变更
            for name, gm in task.git_managers.items():
                gm.commit(f"feat: {task.name} - {result.get('completed', 0)} tasks done")
            
            return {
                "summary": f"Agent 执行完成: {result.get('completed', 0)}/{result.get('total', 0)} 任务",
                "artifacts": {"execution_log": result.get("log_file", "")},
            }
        except Exception as e:
            return {"summary": f"Agent 失败: {e}", "artifacts": {}}
    
    def _exec_test(self, task: TaskSession) -> dict:
        from scripts.test_engine import TestEngine
        test_dir = Path(task.output_dir) / "test"
        test_dir.mkdir(parents=True, exist_ok=True)
        try:
            profile = json.load(open(task.profile_path or "profiles/default.json"))
            engine = TestEngine(profile, str(test_dir), wiki_path=task.wiki_path)
            td_content = (Path(task.output_dir) / "td" / "technical_design.md").read_text() if (Path(task.output_dir) / "td" / "technical_design.md").exists() else ""
            result = engine.generate_tests(task.prd_text, td_content)
            return {"summary": "测试用例已生成", "artifacts": {"report": result.get("report_file", "")}}
        except Exception as e:
            return {"summary": f"Test 失败: {e}", "artifacts": {}}
    
    def _exec_automation(self, task: TaskSession) -> dict:
        from scripts.automation import run_automation
        try:
            profile = json.load(open(task.profile_path or "profiles/default.json"))
            lang = profile.get("language", "go")
            result = run_automation(profile_path=task.profile_path or "profiles/default.json",
                                    output_dir=task.output_dir, language=lang)
            return {"summary": f"自动化: {result.get('status', '?')}", "artifacts": {}}
        except Exception as e:
            return {"summary": f"Automation 失败: {e}", "artifacts": {}}


# ──────────────────────────────────────────────
# Global Store（供 web_api 使用）
# ──────────────────────────────────────────────

_store = ProjectStore()
_orchestrator = None

def get_store() -> ProjectStore:
    return _store

def get_orchestrator() -> PipelineOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = PipelineOrchestrator(profile_path="profiles/default.json")
    return _orchestrator
