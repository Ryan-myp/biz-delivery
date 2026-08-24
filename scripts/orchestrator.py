#!/usr/bin/env python3
"""
biz-delivery Orchestrator — 流程编排层

职责：
  1. 串联 6 大核心 Skill，管理阶段状态和对话上下文
  2. 提供 LLM 切换入口（LLMClient 统一接口）
  3. 记录各阶段产物路径，供 Web 平台可视化

设计原则：
  - Core Skills 完全独立，不依赖本模块
  - 本模块只是一个协调器，可以随时抽离
  - 通过 LLMClient 切换底层模型

使用方式：
  # 完整流程
  orch = PipelineOrchestrator(profile_path="profiles/default.json")
  result = orch.run(prd_text="...")

  # 对话式逐步执行
  orch = PipelineOrchestrator(profile_path="profiles/default.json")
  orch.start_session(prd_text="...", output_dir="/tmp/delivery")
  orch.next_stage()          # → learn
  orch.chat("帮我改进一下")   # → 当前阶段的 LLM 对话
  orch.next_stage()          # → review
  ...
"""

import json
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

from scripts.llm_client import LLMClient


# ──────────────────────────────────────────────
# Stage & Status
# ──────────────────────────────────────────────

class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

STAGE_ORDER = ["learn", "review", "td", "tasks", "agent", "test", "automation"]


@dataclass
class StageRecord:
    """单个阶段的执行记录"""
    status: StageStatus = StageStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output_dir: str = ""
    artifacts: Dict[str, str] = field(default_factory=dict)  # artifact_name -> file_path
    error: str = ""
    summary: str = ""


@dataclass
class ChatMessage:
    role: str       # "user" | "assistant"
    content: str
    timestamp: str
    stage: str = ""


@dataclass
class SessionContext:
    """会话上下文 — 贯穿整个交付流程"""
    project_id: str
    prd_text: str
    profile_path: str
    output_dir: str
    wiki_path: Optional[str]
    created_at: str
    
    # Stage tracking
    current_stage_idx: int = 0
    stages: Dict[str, StageRecord] = field(default_factory=dict)
    
    # Conversation per stage
    conversations: Dict[str, List[ChatMessage]] = field(default_factory=dict)
    
    # LLM context
    llm_client: Optional[LLMClient] = None
    model_name: str = ""
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.stages:
            for stage in STAGE_ORDER:
                self.stages[stage] = StageRecord()
    
    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "prd_text": self.prd_text[:200] + "..." if len(self.prd_text) > 200 else self.prd_text,
            "profile_path": self.profile_path,
            "output_dir": self.output_dir,
            "wiki_path": self.wiki_path,
            "created_at": self.created_at,
            "current_stage_idx": self.current_stage_idx,
            "model_name": self.model_name,
            "stages": {k: asdict(v) for k, v in self.stages.items()},
            "conversations": {
                k: [asdict(m) for m in v] for k, v in self.conversations.items()
            },
            "metadata": self.metadata,
        }
    
    def add_message(self, stage: str, role: str, content: str):
        if stage not in self.conversations:
            self.conversations[stage] = []
        self.conversations[stage].append(ChatMessage(
            role=role, content=content,
            timestamp=datetime.now().isoformat(), stage=stage,
        ))
    
    @property
    def current_stage(self) -> str:
        return STAGE_ORDER[self.current_stage_idx] if self.current_stage_idx < len(STAGE_ORDER) else ""
    
    @property
    def progress(self) -> dict:
        total = len(STAGE_ORDER)
        completed = sum(1 for s in self.stages.values() if s.status == StageStatus.COMPLETED)
        return {"total": total, "completed": completed, "percent": int(completed/total*100)}


# ──────────────────────────────────────────────
# Pipeline Orchestrator
# ──────────────────────────────────────────────

class PipelineOrchestrator:
    """流程编排器 — 串联 6 大核心 Skill"""
    
    # Hook: 各阶段执行前后的回调
    # 子类可以 override 这些方法来注入自定义逻辑
    on_stage_start = None    # Callable[[SessionContext, str], None]
    on_stage_complete = None # Callable[[SessionContext, str, StageRecord], None]
    on_stage_error = None    # Callable[[SessionContext, str, Exception], None]
    
    def __init__(
        self,
        profile_path: str,
        output_dir: str,
        wiki_path: Optional[str] = None,
        llm_model: str = "agnes-2.0-flash",
        llm_api_key: Optional[str] = None,
        llm_api_url: Optional[str] = None,
    ):
        self.profile_path = profile_path
        self.output_dir = Path(output_dir)
        self.wiki_path = wiki_path
        
        # LLM Client — 统一切换入口
        self.llm_client = LLMClient(
            api_key=llm_api_key,
            api_url=llm_api_url,
            model=llm_model,
        )
        self.model_name = llm_model
        
        # 会话上下文
        self.context: Optional[SessionContext] = None
        
        # 后台任务
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start_session(self, prd_text: str, project_name: str = "") -> SessionContext:
        """创建新会话"""
        project_id = datetime.now().strftime("%Y%m%d") + "_" + project_name[:8].replace(" ", "_")
        self.context = SessionContext(
            project_id=project_id,
            prd_text=prd_text,
            profile_path=self.profile_path,
            output_dir=str(self.output_dir),
            wiki_path=self.wiki_path,
            created_at=datetime.now().isoformat(),
            llm_client=self.llm_client,
            model_name=self.model_name,
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.context
    
    def run(self, prd_text: str, project_name: str = "", stages: Optional[List[str]] = None) -> dict:
        """运行完整流程（同步）"""
        ctx = self.start_session(prd_text, project_name)
        stages = stages or STAGE_ORDER
        
        for stage in stages:
            if ctx.current_stage_idx < len(STAGE_ORDER) and STAGE_ORDER[ctx.current_stage_idx] != stage:
                # Skip to the requested stage
                idx = STAGE_ORDER.index(stage)
                ctx.current_stage_idx = idx
            
            result = self.run_stage(ctx, stage)
            if result["status"] == "failed":
                break
            ctx.current_stage_idx = min(ctx.current_stage_idx + 1, len(STAGE_ORDER))
        
        return {
            "project_id": ctx.project_id,
            "progress": ctx.progress,
            "stages": {k: asdict(v) for k, v in ctx.stages.items()},
        }
    
    def run_async(self, prd_text: str, project_name: str = "", stages: Optional[List[str]] = None):
        """异步运行完整流程"""
        self._running = True
        self._thread = threading.Thread(
            target=self._run_background,
            args=(prd_text, project_name, stages),
            daemon=True,
        )
        self._thread.start()
        return {"project_id": self.context.project_id if self.context else None, "status": "started"}
    
    def _run_background(self, prd_text: str, project_name: str, stages: Optional[List[str]]):
        try:
            self.run(prd_text, project_name, stages)
        finally:
            self._running = False
    
    def run_stage(self, ctx: SessionContext, stage: str) -> dict:
        """执行单个阶段"""
        if stage not in STAGE_ORDER:
            return {"status": "failed", "error": f"Unknown stage: {stage}"}
        
        rec = ctx.stages[stage]
        if rec.status == StageStatus.COMPLETED:
            return {"status": "completed", "message": f"Stage {stage} already done"}
        
        rec.status = StageStatus.RUNNING
        rec.started_at = datetime.now().isoformat()
        
        # Call hook
        if self.on_stage_start:
            self.on_stage_start(ctx, stage)
        
        try:
            handler = getattr(self, f"_exec_{stage}", None)
            if handler:
                result = handler(ctx)
            else:
                result = {"status": "skipped", "message": f"No handler for {stage}"}
            
            rec.status = StageStatus.COMPLETED
            rec.completed_at = datetime.now().isoformat()
            rec.summary = result.get("summary", "")
            rec.artifacts.update(result.get("artifacts", {}))
            
            if self.on_stage_complete:
                self.on_stage_complete(ctx, stage, rec)
            
            return {"status": "completed", **result}
            
        except Exception as e:
            rec.status = StageStatus.FAILED
            rec.error = str(e)
            rec.completed_at = datetime.now().isoformat()
            
            if self.on_stage_error:
                self.on_stage_error(ctx, stage, e)
            
            return {"status": "failed", "error": str(e)}
    
    # ──────────────────────────────────────────
    # Stage Executors
    # ──────────────────────────────────────────
    
    def _exec_learn(self, ctx: SessionContext) -> dict:
        """Stage 1: 知识提取"""
        from scripts.learn_repo import learn_from_repos
        
        knowledge_dir = Path(ctx.output_dir) / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        
        result = learn_from_repos(
            profile_path=ctx.profile_path,
            output_dir=str(knowledge_dir),
            wiki_path=ctx.wiki_path,
        )
        
        # Save summary
        summary = {
            "repo_name": getattr(result, 'repo_name', 'unknown'),
            "language": getattr(result, 'language', 'unknown'),
            "structs": len(getattr(result, 'structs', [])),
            "functions": len(getattr(result, 'functions', [])),
            "routes": len(getattr(result, 'routes', [])),
        }
        summary_file = knowledge_dir / "summary.json"
        summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        
        return {
            "summary": f"知识提取完成: {summary['functions']} 函数, {summary['structs']} 结构体, {summary['routes']} 路由",
            "artifacts": {"summary": str(summary_file)},
        }
    
    def _exec_review(self, ctx: SessionContext) -> dict:
        """Stage 2: PRD 审查"""
        from scripts.review_engine import ReviewEngine
        
        review_dir = Path(ctx.output_dir) / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        
        profile = json.load(open(ctx.profile_path))
        engine = ReviewEngine(profile, str(review_dir), wiki_path=ctx.wiki_path)
        
        result = engine.review(ctx.prd_text)
        
        prompt_file = result.get("prompt_file", "")
        return {
            "summary": f"审查 Prompt 已生成: {prompt_file}",
            "artifacts": {"prompt": prompt_file},
        }
    
    def _exec_td(self, ctx: SessionContext) -> dict:
        """Stage 3: 技术方案"""
        from scripts.td_engine import TDEngine
        
        td_dir = Path(ctx.output_dir) / "td"
        td_dir.mkdir(parents=True, exist_ok=True)
        
        profile = json.load(open(ctx.profile_path))
        engine = TDEngine(profile, str(td_dir), wiki_path=ctx.wiki_path)
        
        # Load review if available
        review_content = ""
        review_file = Path(ctx.output_dir) / "review" / "review_report.md"
        if review_file.exists():
            review_content = review_file.read_text()
        
        result = engine.generate_td(ctx.prd_text, review_content)
        
        return {
            "summary": f"技术方案已生成",
            "artifacts": {"report": result.get("report_file", "")},
        }
    
    def _exec_tasks(self, ctx: SessionContext) -> dict:
        """Stage 4: Agent 任务生成"""
        from scripts.delivery_pipeline import AgentTaskGenerator
        
        tasks_dir = Path(ctx.output_dir) / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        
        profile = json.load(open(ctx.profile_path))
        generator = AgentTaskGenerator(profile, ir_data={})
        
        # Load TD
        td_content = ""
        td_file = Path(ctx.output_dir) / "td" / "technical_design.md"
        if td_file.exists():
            td_content = td_file.read_text()
        
        tasks = generator.generate_tasks(td_content, "")
        
        tasks_file = tasks_dir / "agent_tasks.json"
        tasks_file.write_text(json.dumps([t.to_dict() for t in tasks], ensure_ascii=False, indent=2))
        
        return {
            "summary": f"生成 {len(tasks)} 个 Agent 任务",
            "artifacts": {"tasks": str(tasks_file)},
        }
    
    def _exec_agent(self, ctx: SessionContext) -> dict:
        """Stage 5: Agent 执行（需要 LLM）"""
        from scripts.delivery_pipeline import AgentExecutor
        
        tasks_dir = Path(ctx.output_dir) / "tasks"
        tasks_file = tasks_dir / "agent_tasks.json"
        if not tasks_file.exists():
            return {"summary": "跳过: 未找到任务文件，请先执行 Tasks 阶段", "artifacts": {}}
        
        tasks_data = json.loads(tasks_file.read_text())
        from scripts.delivery_pipeline import AgentTask
        tasks = [AgentTask(**t) for t in tasks_data]
        
        executor = AgentExecutor(
            profile=json.load(open(ctx.profile_path)),
            output_dir=ctx.output_dir,
        )
        
        result = executor.execute(tasks, self.llm_client)
        
        return {
            "summary": f"Agent 执行: {result.get('completed', 0)}/{result.get('total', 0)} 任务完成",
            "artifacts": {"execution_log": result.get("log_file", "")},
        }
    
    def _exec_test(self, ctx: SessionContext) -> dict:
        """Stage 6: 测试用例生成"""
        from scripts.test_engine import TestEngine
        
        test_dir = Path(ctx.output_dir) / "test"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        profile = json.load(open(ctx.profile_path))
        engine = TestEngine(profile, str(test_dir), wiki_path=ctx.wiki_path)
        
        # Load TD
        td_content = ""
        td_file = Path(ctx.output_dir) / "td" / "technical_design.md"
        if td_file.exists():
            td_content = td_file.read_text()
        
        result = engine.generate_tests(ctx.prd_text, td_content)
        
        return {
            "summary": f"测试用例已生成",
            "artifacts": {"report": result.get("report_file", "")},
        }
    
    def _exec_automation(self, ctx: SessionContext) -> dict:
        """Stage 7: 自动化执行"""
        from scripts.automation import run_automation
        
        profile = json.load(open(ctx.profile_path))
        lang = profile.get("language", "go")
        
        result = run_automation(
            profile_path=ctx.profile_path,
            output_dir=ctx.output_dir,
            language=lang,
        )
        
        return {
            "summary": f"自动化执行: {result.get('status', 'unknown')}",
            "artifacts": {"report": result.get("report_file", "")},
        }
    
    # ──────────────────────────────────────────
    # Chat Interface
    # ──────────────────────────────────────────
    
    def chat(self, message: str, stage: Optional[str] = None) -> dict:
        """对话接口 — 在当前阶段进行 LLM 对话"""
        if not self.context:
            return {"error": "No active session. Call start_session() first."}
        
        ctx = self.context
        target_stage = stage or ctx.current_stage
        
        # Add user message
        ctx.add_message(target_stage, "user", message)
        
        # Build context-aware prompt
        system_prompt = self._build_system_prompt(ctx, target_stage)
        user_prompt = self._build_user_prompt(ctx, target_stage, message)
        
        # Call LLM
        try:
            response = ctx.llm_client.chat(user_prompt, system=system_prompt)
            reply = response.get("content", "")
        except Exception as e:
            reply = f"LLM 调用失败: {e}"
        
        # Add assistant message
        ctx.add_message(target_stage, "assistant", reply)
        
        return {
            "stage": target_stage,
            "reply": reply,
            "model": ctx.model_name,
        }
    
    def _build_system_prompt(self, ctx: SessionContext, stage: str) -> str:
        stage_names = {
            "learn": "知识提取阶段",
            "review": "PRD 审查阶段 — 基于代码 IR 审查 PRD",
            "td": "技术方案生成阶段",
            "tasks": "Agent 任务分解阶段",
            "agent": "Agent 代码执行阶段",
            "test": "测试用例生成阶段",
            "automation": "自动化执行阶段",
        }
        desc = stage_names.get(stage, stage)
        return f"""你是 biz-delivery 智能交付助手，正在执行: {desc}

当前 PRD:
{ctx.prd_text[:500]}{'...' if len(ctx.prd_text) > 500 else ''}

输出要求：简洁、实用、针对当前阶段提供具体建议。"""
    
    def _build_user_prompt(self, ctx: SessionContext, stage: str, message: str) -> str:
        # Append recent conversation history
        history = ctx.conversations.get(stage, [])[-6:]  # last 6 messages
        history_text = "\n".join(
            f"{'用户' if m.role == 'user' else '助手'}: {m.content}"
            for m in history
        )
        
        return f"""[对话历史]
{history_text if history_text else '(无历史)'}

[当前消息]
{message}"""
    
    def switch_model(self, model: str, api_key: Optional[str] = None, api_url: Optional[str] = None):
        """切换底层 LLM"""
        self.llm_client = LLMClient(
            api_key=api_key or self.llm_client.api_key,
            api_url=api_url or self.llm_client.api_url,
            model=model,
        )
        self.model_name = model
        if self.context:
            self.context.model_name = model
    
    def get_progress(self) -> dict:
        """获取进度"""
        if not self.context:
            return {"error": "No active session"}
        return {
            "project_id": self.context.project_id,
            **self.context.progress,
            "current_stage": self.context.current_stage,
            "stages": {k: asdict(v) for k, v in self.context.stages.items()},
        }


# ──────────────────────────────────────────────
# CLI Entry
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="biz-delivery 流程编排器")
    parser.add_argument("--profile", required=True, help="Profile JSON 路径")
    parser.add_argument("--prd", required=True, help="PRD 内容或文件路径")
    parser.add_argument("--output-dir", default="/tmp/biz-delivery/output")
    parser.add_argument("--wiki-path", default=None)
    parser.add_argument("--model", default="agnes-2.0-flash", help="LLM 模型")
    parser.add_argument("--stages", default=None, help="指定阶段，逗号分隔")
    args = parser.parse_args()
    
    # Load PRD
    prd_text = args.prd
    if Path(args.prd).exists():
        prd_text = Path(args.prd).read_text()
    
    # Run
    orch = PipelineOrchestrator(
        profile_path=args.profile,
        output_dir=args.output_dir,
        wiki_path=args.wiki_path,
        llm_model=args.model,
    )
    
    stages = args.stages.split(",") if args.stages else None
    result = orch.run(prd_text, stages=stages)
    
    print(f"\n{'='*50}")
    print(f"项目: {result['project_id']}")
    print(f"进度: {result['progress']['completed']}/{result['progress']['total']} 阶段")
    for name, rec in result['stages'].items():
        icon = "✅" if rec['status'] == 'completed' else ("❌" if rec['status'] == 'failed' else "⏳")
        print(f"  {icon} {name}: {rec.get('summary', rec['status'])}")
