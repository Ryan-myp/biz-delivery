#!/usr/bin/env python3
"""
biz-delivery Web API — 多项目、多对话可视化层

架构：
  - ProjectStore: 内存存储所有项目，JSON 持久化
  - TaskSession: 每个任务独立的对话 + 流程状态
  - PipelineOrchestrator: 可选的 guided pipeline 执行器
  
启动：
  python3 scripts/web_api.py --port 8000
  → http://localhost:8000
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.orchestrator import get_store, get_orchestrator, STAGE_ORDER
from scripts.context_manager import MemorySystem, ContextWindow, TokenEstimator
from scripts.mcp_adapter import MCPServer, register_builtin_tools, JSONRPC
from scripts.multi_model_router import MultiModelRouter, RoutingStrategy
from scripts.llm_wiki import RAGEngine


def create_app():
    from fastapi import FastAPI, HTTPException
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    
    app = FastAPI(title="biz-delivery", version="4.0.0")
    
    static_dir = Path(__file__).parent.parent / "templates" / "web"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    store = get_store()
    orch = get_orchestrator()
    
    # ── Models ──
    class CreateProjectRequest(BaseModel):
        name: str
        output_root: str = "/tmp/biz-delivery"
    
    class CreateTaskRequest(BaseModel):
        name: str
        prd_text: str = ""
        profile_path: str = ""
        use_pipeline: bool = True
        model_name: str = "agnes-2.0-flash"
        repositories: List[Dict] = []
        branch_prefix: str = "biz-delivery"
    
    class ChatRequest(BaseModel):
        message: str
        stage: Optional[str] = None
    
    class RunStageRequest(BaseModel):
        stage: str
    
    class SwitchModelRequest(BaseModel):
        model: str
    
    # ── Routes ──
    
    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "4.2.0", "projects": len(store.list_projects())}
    
    @app.get("/api/profiles")
    async def list_profiles():
        """列出可用 profiles"""
        import glob
        profile_dir = Path(__file__).parent.parent / "profiles"
        if not profile_dir.exists():
            return {"profiles": []}
        files = sorted([f.name for f in profile_dir.glob("*.json")])
        profiles = []
        for f in files:
            try:
                data = json.loads((profile_dir / f).read_text())
                repos = data.get("repositories", [])
                profiles.append({
                    "name": f.replace(".json", ""),
                    "path": str(profile_dir / f),
                    "domain": data.get("business_domain", ""),
                    "repo_count": len(repos),
                    "repos": repos,
                })
            except:
                pass
        return {"profiles": profiles}
    
    # ── Projects ──
    
    @app.get("/api/projects")
    async def list_projects():
        return [p.to_dict() for p in store.list_projects()]
    
    @app.post("/api/projects")
    async def create_project(req: CreateProjectRequest):
        project = store.create_project(req.name, req.output_root)
        return project.to_dict()
    
    @app.delete("/api/projects/{project_id}")
    async def delete_project(project_id: str):
        if not store.delete_project(project_id):
            raise HTTPException(404, "Project not found")
        return {"ok": True}
    
    # ── Tasks ──
    
    @app.get("/api/projects/{project_id}/tasks")
    async def list_tasks(project_id: str):
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        return [t.to_dict() for t in project.tasks.values()]
    
    @app.post("/api/projects/{project_id}/tasks")
    async def create_task(project_id: str, req: CreateTaskRequest):
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.add_task(
            name=req.name,
            prd_text=req.prd_text,
            profile_path=req.profile_path or "profiles/default.json",
            use_pipeline=req.use_pipeline,
            model_name=req.model_name,
        )
        if req.repositories:
            task.repositories = req.repositories
        if req.branch_prefix:
            task.branch_prefix = req.branch_prefix
        return task.to_dict()
    
    @app.delete("/api/projects/{project_id}/tasks/{task_id}")
    async def delete_task(project_id: str, task_id: str):
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        if task_id not in project.tasks:
            raise HTTPException(404, "Task not found")
        del project.tasks[task_id]
        store._save()
        return {"ok": True}
    
    # ── Task Detail ──
    
    @app.get("/api/projects/{project_id}/tasks/{task_id}")
    async def get_task(project_id: str, task_id: str):
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        return task.to_dict()
    
    @app.patch("/api/projects/{project_id}/tasks/{task_id}")
    async def update_task(project_id: str, task_id: str, data: dict):
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        for k, v in data.items():
            if hasattr(task, k):
                setattr(task, k, v)
        store._save()
        return task.to_dict()
    
    # ── Chat ──
    
    @app.get("/api/projects/{project_id}/tasks/{task_id}/chat")
    async def get_chat(project_id: str, task_id: str, limit: int = 20):
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        msgs = task.messages[-limit:]
        return {"messages": [{"role": m.role, "content": m.content, "timestamp": m.timestamp, "stage": m.stage} for m in msgs]}
    
    @app.post("/api/projects/{project_id}/tasks/{task_id}/chat")
    async def send_chat(project_id: str, task_id: str, req: ChatRequest):
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        
        result = orch.chat(task, req.message, req.stage)
        store._save()
        return result
    
    # ── Pipeline ──
    
    @app.get("/api/projects/{project_id}/tasks/{task_id}/stages")
    async def get_stages(project_id: str, task_id: str):
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        return {
            "use_pipeline": task.use_pipeline,
            "current_stage": task.current_stage,
            "progress": task.progress,
            "stages": {
                name: {
                    "status": rec.status.value if hasattr(rec.status, "value") else rec.status,
                    "summary": rec.summary,
                    "error": rec.error,
                    "artifacts": rec.artifacts,
                }
                for name, rec in task.stages.items()
            },
        }
    
    @app.post("/api/projects/{project_id}/tasks/{task_id}/run-stage")
    async def run_stage(project_id: str, task_id: str, req: RunStageRequest):
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        if not task.use_pipeline:
            return {"status": "skipped", "message": "Pipeline not enabled for this task"}
        
        result = orch.run_stage(task, req.stage)
        store._save()
        return result
    
    @app.post("/api/projects/{project_id}/tasks/{task_id}/next-stage")
    async def next_stage(project_id: str, task_id: str):
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        
        next_idx = task.current_stage_idx
        if next_idx < len(STAGE_ORDER):
            stage = STAGE_ORDER[next_idx]
            task.current_stage_idx = next_idx + 1
            result = orch.run_stage(task, stage)
            store._save()
            return {"stage": stage, **result}
        return {"status": "completed", "message": "All stages done"}
    
    @app.post("/api/projects/{project_id}/tasks/{task_id}/switch-model")
    async def switch_model(project_id: str, task_id: str, req: SwitchModelRequest):
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        task.model_name = req.model
        try:
            from scripts.llm_client import LLMClient
            task.llm_client = LLMClient(model=req.model)
        except ValueError:
            task.llm_client = None
        store._save()
        return {"model": req.model}
    
    @app.get("/api/projects/{project_id}/tasks/{task_id}/artifacts/{stage}")
    async def get_artifacts(project_id: str, task_id: str, stage: str):
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        rec = task.stages.get(stage)
        if not rec:
            raise HTTPException(404, f"Stage {stage} not found")
        results = {}
        for name, path in rec.artifacts.items():
            if path and Path(path).exists():
                try:
                    results[name] = Path(path).read_text(encoding="utf-8")[:5000]
                except:
                    results[name] = f"[无法读取]"
            else:
                results[name] = f"[未生成]"
        return {"stage": stage, "artifacts": results}
    
    # ── Index ──
    
    @app.get("/api/projects/{project_id}/tasks/{task_id}/repo-files/{repo_name}")
    async def get_repo_files(project_id: str, task_id: str, repo_name: str):
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        gm = task.get_repo_manager(repo_name)
        if not gm:
            raise HTTPException(404, f"Repo {repo_name} not found")
        return {
            "name": repo_name,
            "branch": gm.get_branch(),
            "files": gm.list_files(),
            "status": gm.status(),
        }
    
    @app.get("/repo-file/{repo_name:path}/{file_path:path}")
    async def get_repo_file(project_id: str, repo_name: str, file_path: str):
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        gm = task.get_repo_manager(repo_name)
        if not gm:
            raise HTTPException(404, f"Repo {repo_name} not found")
        content = gm.get_file_content(file_path)
        return {"path": file_path, "content": content}
    
    # ── Memory & Context APIs ──
    
    @app.get("/api/projects/{project_id}/tasks/{task_id}/context")
    async def get_context(project_id: str, task_id: str):
        """获取任务上下文状态"""
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        
        # 确保初始化
        if not task.memory_system:
            task.memory_system = MemorySystem()
        
        return {
            "task_id": task_id,
            "message_count": len(task.messages),
            "context_stats": task.to_dict().get("context_stats", {}),
            "memories": [m.to_dict() for m in task.memory_system.memories[-10:]],
            "memory_stats": task.memory_system.stats(),
        }
    
    @app.post("/api/projects/{project_id}/tasks/{task_id}/memory")
    async def add_memory(project_id: str, task_id: str, req: dict):
        """添加记忆"""
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        
        if not task.memory_system:
            task.memory_system = MemorySystem()
        
        mem = task.memory_system.add(
            mem_type=req.get("type", "fact"),
            content=req.get("content", ""),
            tags=req.get("tags", []),
            task_id=task_id,
        )
        return {"id": mem.id, "type": mem.type, "content": mem.content}
    
    @app.get("/api/projects/{project_id}/tasks/{task_id}/memory/search")
    async def search_memory(project_id: str, task_id: str, q: str = "", limit: int = 10):
        """搜索记忆"""
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        
        if not task.memory_system:
            return {"memories": [], "total": 0}
        
        memories = task.memory_system.search(q, limit=limit)
        return {"memories": [m.to_dict() for m in memories], "total": len(memories)}
    
    @app.delete("/api/projects/{project_id}/tasks/{task_id}/memory/{mem_id}")
    async def delete_memory(project_id: str, task_id: str, mem_id: str):
        """删除记忆"""
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        
        if not task.memory_system:
            raise HTTPException(404, "No memory system")
        
        # 找到并删除
        task.memory_system.memories = [m for m in task.memory_system.memories if m.id != mem_id]
        task.memory_system._save()
        return {"ok": True}
    
    @app.post("/api/projects/{project_id}/tasks/{task_id}/compress")
    async def compress_context(project_id: str, task_id: str):
        """手动压缩上下文"""
        project = store.get_project(project_id)
        if not project:
            raise HTTPException(404, "Project not found")
        task = project.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        
        if not task.context_window:
            task.context_window = ContextWindow(max_tokens=8000, model=task.model_name)
        
        # 强制压缩
        ctx_msgs = task.get_context_messages()
        return {
            "original_count": len(task.messages),
            "compressed_count": len(ctx_msgs),
            "truncated": task.context_truncated,
        }
    
    # ── MCP API ──
    # 创建独立的 MCP 服务器实例
    mcp_server = MCPServer("biz-delivery-mcp", "4.0.0")
    register_builtin_tools(mcp_server)
    
    # 创建独立的路由器实例
    model_router = MultiModelRouter()
    
    @app.get("/api/mcp/tools")
    async def get_mcp_tools():
        """获取 MCP 可用工具列表"""
        return {
            "server": mcp_server.name,
            "version": mcp_server.version,
            "tools": mcp_server.get_tools(),
            "resources": mcp_server.get_resources(),
        }
    
    @app.post("/api/mcp/call")
    async def call_mcp_tool(req: dict):
        """调用 MCP 工具"""
        import asyncio
        msg = JSONRPC.create_request(
            "tools/call",
            {"name": req["tool"], "arguments": req.get("args", {})},
            "web-request"
        )
        result = await mcp_server.handle_message(msg)
        return result.get("result", {})
    
    # ── Model Routing API ──
    
    @app.get("/api/models")
    async def list_models():
        """列出可用模型"""
        return {
            "models": [m.to_dict() for m in model_router.models.values()],
            "strategy": model_router.strategy.value,
        }
    
    @app.post("/api/models/route")
    async def route_model(req: dict):
        """智能路由到最佳模型"""
        task_type = req.get("task_type", "code")
        context_length = req.get("context_length", 4000)
        
        model_id = model_router.route(task_type, context_length)
        rec = model_router.get_recommendation(task_type, context_length)
        
        return rec
    
    @app.post("/api/models/set-strategy")
    async def set_strategy(req: dict):
        """设置路由策略"""
        strategy = RoutingStrategy(req.get("strategy", "balanced"))
        model_router.set_strategy(strategy)
        return {"strategy": strategy.value}
    
    @app.get("/api/models/stats")
    async def get_model_stats():
        """获取模型使用统计"""
        return model_router.get_all_stats()
    
    # ── LLM Wiki API ──
    
    @app.get("/api/wiki/stats")
    async def get_wiki_stats():
        """获取知识库统计"""
        wiki_path = "/tmp/biz-delivery/wiki"
        rag = RAGEngine(wiki_path)
        return rag.stats()
    
    @app.post("/api/wiki/build")
    async def build_wiki(req: dict):
        """构建知识库"""
        repo_path = req.get("repo_path", ".")
        language = req.get("language", "python")
        wiki_path = "/tmp/biz-delivery/wiki"
        
        rag = RAGEngine(wiki_path)
        result = rag.build_from_repo(repo_path, language)
        return result
    
    @app.post("/api/wiki/query")
    async def query_wiki(req: dict):
        """查询知识库"""
        question = req.get("question", "")
        top_k = req.get("top_k", 5)
        wiki_path = "/tmp/biz-delivery/wiki"
        
        rag = RAGEngine(wiki_path)
        result = rag.query(question, top_k=top_k)
        return result
    
    @app.get("/api/wiki/entries/{entry_id}")
    async def get_wiki_entry(entry_id: str):
        """获取知识条目详情"""
        wiki_path = "/tmp/biz-delivery/wiki"
        rag = RAGEngine(wiki_path)
        entry = rag.get_entity(entry_id)
        if not entry:
            raise HTTPException(404, "Entry not found")
        return entry
    
    @app.get("/")
    async def index():
        index_file = static_dir / "index.html" if static_dir.exists() else None
        if index_file and index_file.exists():
            return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
        return HTMLResponse(content="""
        <html><body>
        <h1>biz-delivery v3.0</h1>
        <p>多项目、多对话的智能交付平台</p>
        <h3>API:</h3>
        <ul>
            <li>GET /api/health</li>
            <li>GET /api/projects</li>
            <li>POST /api/projects</li>
            <li>DELETE /api/projects/{id}</li>
            <li>GET/POST /api/projects/{id}/tasks</li>
            <li>GET/POST /api/projects/{id}/tasks/{tid}/chat</li>
            <li>GET /api/projects/{id}/tasks/{tid}/stages</li>
            <li>POST /api/projects/{id}/tasks/{tid}/run-stage</li>
            <li>GET /api/projects/{id}/tasks/{tid}/artifacts/{stage}</li>
        </ul>
        </body></html>
        """)
    
    return app


def main():
    parser = argparse.ArgumentParser(description="biz-delivery Web API")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--store", default="/tmp/biz-delivery/projects.json", help="Store 路径")
    args = parser.parse_args()
    
    # 更新 store 路径
    from scripts.orchestrator import _store
    _store.store_path = Path(args.store)
    _store._load()
    
    app = create_app()
    
    print(f"🚀 biz-delivery Web API v3.0")
    print(f"   Port: {args.port}")
    print(f"   Store: {args.store}")
    print(f"   → http://localhost:{args.port}")
    
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
