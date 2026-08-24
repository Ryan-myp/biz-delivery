#!/usr/bin/env python3
"""
biz-delivery Web API — 纯可视化层

职责：
  - 提供 HTTP API 暴露 Orchestrator 的状态
  - Serve 前端页面（静态 HTML）
  - 不 import 任何核心 Skill（避免依赖耦合）

依赖：
  - scripts/orchestrator.py（唯一的编排入口）
  - FastAPI + Uvicorn

启动：
  python3 scripts/web_api.py --profile profiles/default.json --port 8000
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# 只导入 orchestrator，不导入核心 skills
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.orchestrator import PipelineOrchestrator, SessionContext


# ──────────────────────────────────────────────
# 全局状态
# ──────────────────────────────────────────────

orchestrator: Optional[PipelineOrchestrator] = None
project_name_counter = 0


def get_orchestrator() -> PipelineOrchestrator:
    global orchestrator
    return orchestrator


# ──────────────────────────────────────────────
# FastAPI 应用（延迟导入，避免启动时加载核心 skills）
# ──────────────────────────────────────────────

def create_app(orch: PipelineOrchestrator):
    """创建 FastAPI 应用（延迟导入 FastAPI）"""
    from fastapi import FastAPI, HTTPException
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    
    app = FastAPI(title="biz-delivery", version="3.0.0")
    
    # 挂载前端静态文件
    static_dir = Path(__file__).parent.parent / "templates" / "web"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # ── Models ──
    class StartSessionRequest(BaseModel):
        prd_text: str
        project_name: str = ""
    
    class ChatRequest(BaseModel):
        message: str
        stage: Optional[str] = None
    
    class SwitchModelRequest(BaseModel):
        model: str
        api_key: Optional[str] = None
        api_url: Optional[str] = None
    
    # ── Routes ──
    
    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "3.0.0", "stages": ["learn", "review", "td", "tasks", "agent", "test", "automation"]}
    
    @app.post("/api/session/start")
    async def start_session(req: StartSessionRequest):
        global project_name_counter
        project_name_counter += 1
        name = req.project_name or f"需求-{project_name_counter}"
        ctx = orch.start_session(req.prd_text, name)
        return {
            "project_id": ctx.project_id,
            "name": name,
            "current_stage": ctx.current_stage,
            "progress": ctx.progress,
            "model": orch.model_name,
        }
    
    @app.get("/api/session/progress")
    async def get_progress():
        if not orch.context:
            raise HTTPException(404, "No active session")
        return orch.get_progress()
    
    @app.post("/api/session/chat")
    async def chat(req: ChatRequest):
        if not orch.context:
            raise HTTPException(404, "No active session")
        return orch.chat(req.message, req.stage)
    
    @app.get("/api/session/chat/{stage}")
    async def get_chat_history(stage: str):
        if not orch.context:
            raise HTTPException(404, "No active session")
        msgs = orch.context.conversations.get(stage, [])
        return {"stage": stage, "messages": [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp}
            for m in msgs
        ]}
    
    @app.post("/api/session/run-stage/{stage}")
    async def run_stage(stage: str):
        if not orch.context:
            raise HTTPException(404, "No active session")
        if stage not in ["learn", "review", "td", "tasks", "agent", "test", "automation"]:
            raise HTTPException(400, f"Invalid stage: {stage}")
        result = orch.run_stage(orch.context, stage)
        return result
    
    @app.get("/api/session/stages")
    async def get_stages():
        if not orch.context:
            raise HTTPException(404, "No active session")
        return {
            "current": orch.context.current_stage,
            "progress": orch.context.progress,
            "stages": {
                name: {
                    "status": rec.status.value,
                    "summary": rec.summary,
                    "error": rec.error,
                }
                for name, rec in orch.context.stages.items()
            },
        }
    
    @app.post("/api/session/switch-model")
    async def switch_model(req: SwitchModelRequest):
        orch.switch_model(req.model, req.api_key, req.api_url)
        return {"model": orch.model_name, "message": f"Switched to {req.model}"}
    
    @app.get("/api/artifacts/{stage}")
    async def get_artifacts(stage: str):
        if not orch.context:
            raise HTTPException(404, "No active session")
        rec = orch.context.stages.get(stage)
        if not rec:
            raise HTTPException(404, f"Stage {stage} not found")
        artifacts = rec.artifacts
        results = {}
        for name, path in artifacts.items():
            if path and Path(path).exists():
                try:
                    results[name] = Path(path).read_text(encoding="utf-8")[:5000]
                except:
                    results[name] = f"[无法读取: {path}]"
            else:
                results[name] = f"[未生成: {path}]"
        return {"stage": stage, "artifacts": results}
    
    @app.get("/", response_class=HTMLResponse)
    async def index():
        static_dir = Path(__file__).parent.parent / "templates" / "web"
        index_file = static_dir / "index.html"
        if index_file.exists():
            return index_file.read_text(encoding="utf-8")
        return """
        <html><body>
        <h1>biz-delivery v3.0</h1>
        <p>Web 平台已就绪，请部署前端页面到 templates/web/</p>
        <h3>API 端点:</h3>
        <ul>
            <li>GET /api/health</li>
            <li>POST /api/session/start</li>
            <li>GET /api/session/progress</li>
            <li>POST /api/session/chat</li>
            <li>POST /api/session/run-stage/{stage}</li>
            <li>GET /api/session/stages</li>
            <li>POST /api/session/switch-model</li>
            <li>GET /api/artifacts/{stage}</li>
        </ul>
        </body></html>
        """
    
    return app


# ──────────────────────────────────────────────
# 启动入口
# ──────────────────────────────────────────────

def main():
    global orchestrator
    
    parser = argparse.ArgumentParser(description="biz-delivery Web API")
    parser.add_argument("--profile", default="profiles/default.json", help="Profile 路径")
    parser.add_argument("--port", type=int, default=8000, help="端口")
    parser.add_argument("--host", default="0.0.0.0", help="主机")
    parser.add_argument("--model", default="agnes-2.0-flash", help="默认 LLM 模型")
    parser.add_argument("--api-key", default=None, help="LLM API Key")
    args = parser.parse_args()
    
    # 创建 orchestrator
    orchestrator = PipelineOrchestrator(
        profile_path=args.profile,
        output_dir="/tmp/biz-delivery-web",
        llm_model=args.model,
        llm_api_key=args.api_key,
    )
    
    # 创建 FastAPI 应用
    app = create_app(orchestrator)
    
    # 启动
    print(f"🚀 biz-delivery Web API")
    print(f"   Profile: {args.profile}")
    print(f"   Model:   {args.model}")
    print(f"   Port:    {args.port}")
    print(f"   → http://localhost:{args.port}")
    
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
