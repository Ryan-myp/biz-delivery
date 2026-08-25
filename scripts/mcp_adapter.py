#!/usr/bin/env python3
"""
MCP Adapter — Model Context Protocol 适配器

职责：
  - MCP 服务器协议实现
  - 工具注册和发现
  - 动态工具加载
  - JSON-RPC 2.0 通信

设计原则：
  - 纯 Python 实现，无外部依赖
  - 支持 stdio 和 SSE 传输
  - 插件式工具注册
"""

import json
import asyncio
import inspect
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
import uuid


# ──────────────────────────────────────────────
# MCP Types
# ──────────────────────────────────────────────

@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "metadata": self.metadata,
        }


@dataclass
class MCPResource:
    """MCP 资源定义"""
    uri: str
    name: str
    description: str
    mime_type: str = "text/plain"
    get_handler: Optional[Callable] = None
    
    def to_dict(self) -> Dict:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


@dataclass
class MCPPrompt:
    """MCP 提示词定义"""
    name: str
    description: str
    arguments: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments,
        }


# ──────────────────────────────────────────────
# JSON-RPC 2.0
# ──────────────────────────────────────────────

class JSONRPC:
    """JSON-RPC 2.0 消息处理"""
    
    @staticmethod
    def create_request(method: str, params: Dict = None, request_id: str = None) -> Dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id or str(uuid.uuid4()),
            "method": method,
            "params": params or {},
        }
    
    @staticmethod
    def create_response(result: Any, request_id: str) -> Dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }
    
    @staticmethod
    def create_error(error_code: int, message: str, request_id: str = None, data: Any = None) -> Dict:
        error = {
            "code": error_code,
            "message": message,
        }
        if data is not None:
            error["data"] = data
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error,
        }
    
    @staticmethod
    def is_request(msg: Dict) -> bool:
        return isinstance(msg, dict) and "method" in msg and "jsonrpc" in msg
    
    @staticmethod
    def is_notification(msg: Dict) -> bool:
        return JSONRPC.is_request(msg) and "id" not in msg


# ──────────────────────────────────────────────
# MCP Server
# ──────────────────────────────────────────────

class MCPServer:
    """MCP 服务器"""
    
    VERSION = "2024-11-05"
    
    def __init__(self, name: str = "biz-delivery-mcp", version: str = "4.0.0"):
        self.name = name
        self.version = version
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self.prompts: Dict[str, MCPPrompt] = {}
        self._initialized = False
        self._message_id = 0
    
    def register_tool(self, tool: MCPTool):
        """注册工具"""
        self.tools[tool.name] = tool
    
    def register_resource(self, resource: MCPResource):
        """注册资源"""
        self.resources[resource.uri] = resource
    
    def register_prompt(self, prompt: MCPPrompt):
        """注册提示词"""
        self.prompts[prompt.name] = prompt
    
    def tool(self, name: str, description: str, input_schema: Dict, **kwargs):
        """装饰器：注册工具"""
        def decorator(func: Callable) -> Callable:
            self.register_tool(MCPTool(
                name=name,
                description=description,
                input_schema=input_schema,
                handler=func,
                metadata=kwargs,
            ))
            return func
        return decorator
    
    def resource(self, uri: str, name: str, description: str, **kwargs):
        """装饰器：注册资源"""
        def decorator(func: Callable) -> Callable:
            self.register_resource(MCPResource(
                uri=uri,
                name=name,
                description=description,
                get_handler=func,
                **kwargs,
            ))
            return func
        return decorator
    
    def prompt(self, name: str, description: str, arguments: List[Dict] = None, **kwargs):
        """装饰器：注册提示词"""
        def decorator(func: Callable) -> Callable:
            self.register_prompt(MCPPrompt(
                name=name,
                description=description,
                arguments=arguments or [],
            ))
            return func
        return decorator
    
    async def handle_message(self, message: Dict) -> Optional[Dict]:
        """处理 JSON-RPC 消息"""
        if not JSONRPC.is_request(message):
            return None
        
        method = message.get("method", "")
        params = message.get("params", {})
        request_id = message.get("id")
        
        # 初始化握手
        if method == "initialize":
            return self._handle_initialize(params, request_id)
        
        if not self._initialized and method != "initialize":
            return JSONRPC.create_error(
                -32600, "Not initialized", request_id
            )
        
        # 方法分发
        handlers = {
            "tools/list": lambda p: self._handle_tools_list(p),
            "tools/call": lambda p: self._handle_tool_call(p, request_id),
            "resources/list": lambda p: self._handle_resources_list(p),
            "resources/read": lambda p: self._handle_resource_read(p),
            "prompts/list": lambda p: self._handle_prompts_list(p),
            "prompts/get": lambda p: self._handle_prompt_get(p),
        }
        
        handler = handlers.get(method)
        if handler:
            return await handler(params)
        
        return JSONRPC.create_error(-32601, f"Method not found: {method}", request_id)
    
    def _handle_initialize(self, params: Dict, request_id: str) -> Dict:
        """处理初始化请求"""
        self._initialized = True
        return JSONRPC.create_response({
            "protocolVersion": self.VERSION,
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {},
            },
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            },
        }, request_id)
    
    async def _handle_tools_list(self, params: Dict) -> Dict:
        """列出所有工具"""
        return JSONRPC.create_response({
            "tools": [t.to_dict() for t in self.tools.values()]
        }, params.get("request_id"))
    
    async def _handle_tool_call(self, params: Dict, request_id: str) -> Dict:
        """调用工具"""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        tool = self.tools.get(tool_name)
        if not tool:
            return JSONRPC.create_error(-32602, f"Tool not found: {tool_name}", request_id)
        
        try:
            # 执行工具
            if inspect.iscoroutinefunction(tool.handler):
                result = await tool.handler(**arguments)
            else:
                result = tool.handler(**arguments)
            
            return JSONRPC.create_response({"content": result}, request_id)
        except Exception as e:
            return JSONRPC.create_error(-32000, str(e), request_id)
    
    async def _handle_resources_list(self, params: Dict) -> Dict:
        """列出所有资源"""
        return JSONRPC.create_response({
            "resources": [r.to_dict() for r in self.resources.values()]
        }, params.get("request_id"))
    
    async def _handle_resource_read(self, params: Dict) -> Dict:
        """读取资源"""
        uri = params.get("uri", "")
        resource = self.resources.get(uri)
        
        if not resource:
            return JSONRPC.create_error(-32002, f"Resource not found: {uri}")
        
        if resource.get_handler:
            content = resource.get_handler()
            return JSONRPC.create_response({
                "uri": uri,
                "name": resource.name,
                "mimeType": resource.mime_type,
                "text": content,
            }, params.get("request_id"))
        
        return JSONRPC.create_error(-32002, "No content handler", params.get("request_id"))
    
    async def _handle_prompts_list(self, params: Dict) -> Dict:
        """列出所有提示词"""
        return JSONRPC.create_response({
            "prompts": [p.to_dict() for p in self.prompts.values()]
        }, params.get("request_id"))
    
    async def _handle_prompt_get(self, params: Dict) -> Dict:
        """获取提示词"""
        prompt_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        prompt = self.prompts.get(prompt_name)
        if not prompt:
            return JSONRPC.create_error(-32003, f"Prompt not found: {prompt_name}")
        
        # 简单模板替换
        template = f"【{prompt_name}】\n{prompt.description}"
        for arg in prompt.arguments:
            placeholder = f"[{arg.get('name', '')}]"
            value = arguments.get(arg.get("name", ""), "")
            template = template.replace(placeholder, value)
        
        return JSONRPC.create_response({
            "description": prompt.description,
            "messages": [{
                "role": "user",
                "content": template
            }]
        }, params.get("request_id"))
    
    def get_tools(self) -> List[Dict]:
        """获取所有工具定义"""
        return [t.to_dict() for t in self.tools.values()]
    
    def get_resources(self) -> List[Dict]:
        """获取所有资源定义"""
        return [r.to_dict() for r in self.resources.values()]


# ──────────────────────────────────────────────
# 内置工具注册
# ──────────────────────────────────────────────

def register_builtin_tools(server: MCPServer):
    """注册内置工具"""
    
    @server.tool(
        "list_projects",
        "列出所有项目",
        {"type": "object", "properties": {}}
    )
    async def list_projects():
        import os
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from scripts.orchestrator import get_store
        store = get_store()
        projects = store.list_projects()
        return [{"id": p.id, "name": p.name, "task_count": len(p.tasks)} for p in projects]
    
    @server.tool(
        "list_tasks",
        "列出项目下的任务",
        {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "项目 ID"}
            },
            "required": ["project_id"]
        }
    )
    async def list_tasks(project_id: str):
        from scripts.orchestrator import get_store
        store = get_store()
        project = store.get_project(project_id)
        if not project:
            return {"error": f"Project not found: {project_id}"}
        return [
            {"id": t.id, "name": t.name, "progress": t.progress}
            for t in project.tasks.values()
        ]
    
    @server.tool(
        "get_task_context",
        "获取任务上下文状态",
        {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "task_id": {"type": "string"}
            },
            "required": ["project_id", "task_id"]
        }
    )
    async def get_task_context(project_id: str, task_id: str):
        from scripts.orchestrator import get_store
        store = get_store()
        project = store.get_project(project_id)
        if not project:
            return {"error": "Project not found"}
        task = project.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        
        # 确保初始化
        if not task.memory_system:
            task.memory_system = MemorySystem()
        if not task.context_window:
            task.context_window = ContextWindow(max_tokens=8000, model=task.model_name)
        
        return {
            "message_count": len(task.messages),
            "context_stats": task.to_dict().get("context_stats", {}),
            "memory_stats": task.memory_system.stats(),
            "stages": {k: v.status.value for k, v in task.stages.items()},
        }
    
    @server.tool(
        "search_memory",
        "搜索记忆",
        {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "task_id": {"type": "string"},
                "query": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "default": 10}
            },
            "required": ["project_id", "task_id"]
        }
    )
    async def search_memory(project_id: str, task_id: str, query: str = "", limit: int = 10):
        from scripts.orchestrator import get_store
        store = get_store()
        project = store.get_project(project_id)
        if not project:
            return {"error": "Project not found"}
        task = project.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if not task.memory_system:
            return {"memories": [], "total": 0}
        
        memories = task.memory_system.search(query, limit=limit)
        return {
            "memories": [m.to_dict() for m in memories],
            "total": len(memories),
        }
    
    @server.tool(
        "add_memory",
        "添加记忆",
        {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "task_id": {"type": "string"},
                "type": {"type": "string", "enum": ["preference", "fact", "decision", "context"]},
                "content": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["project_id", "task_id", "content"]
        }
    )
    async def add_memory(project_id: str, task_id: str, content: str, 
                        type: str = "fact", tags: List[str] = None):
        from scripts.orchestrator import get_store
        store = get_store()
        project = store.get_project(project_id)
        if not project:
            return {"error": "Project not found"}
        task = project.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if not task.memory_system:
            task.memory_system = MemorySystem()
        
        mem = task.memory_system.add(type, content, tags or [], task_id)
        return {"id": mem.id, "type": mem.type, "content": mem.content}
    
    @server.tool(
        "run_stage",
        "运行指定阶段",
        {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "task_id": {"type": "string"},
                "stage": {"type": "string", "enum": ["learn", "review", "td", "agent", "test", "automation"]}
            },
            "required": ["project_id", "task_id", "stage"]
        }
    )
    async def run_stage(project_id: str, task_id: str, stage: str):
        from scripts.orchestrator import get_store, get_orchestrator
        store = get_store()
        orchestrator = get_orchestrator()
        
        project = store.get_project(project_id)
        if not project:
            return {"error": "Project not found"}
        task = project.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        
        result = orchestrator.run_stage(task, stage)
        return result
    
    # 注册资源
    @server.resource(
        "config://settings",
        "系统配置",
        "当前系统配置信息"
    )
    async def get_settings():
        from scripts.orchestrator import get_store
        store = get_store()
        return json.dumps(store.stats(), indent=2, ensure_ascii=False)
    
    # 注册提示词
    @server.prompt(
        "prd_review",
        "PRD 审查提示词",
        [
            {"name": "prd_text", "description": "PRD 文本"},
            {"name": "focus_areas", "description": "关注领域（逗号分隔）"},
        ]
    )
    def prd_review_prompt(prd_text: str, focus_areas: str = "") -> str:
        return f"""审查以下 PRD，重点关注：{focus_areas}

PRD 内容：
{prd_text}

请从以下角度审查：
1. 完整性：是否有遗漏的需求点？
2. 一致性：各部分是否矛盾？
3. 可测试性：需求是否可验证？
4. 风险点：有哪些潜在风险？

输出格式：
【审查报告】
- 完整度评分：X/10
- 一致性评分：X/10
- 可测试性评分：X/10
- 发现的问题：
  1. ...
- 建议："""


# ──────────────────────────────────────────────
# MCP Client
# ──────────────────────────────────────────────

class MCPClient:
    """MCP 客户端（用于调用外部 MCP 服务器）"""
    
    def __init__(self, transport: str = "stdio", **kwargs):
        self.transport = transport
        self.config = kwargs
        self._tools: List[Dict] = []
        self._initialized = False
    
    async def connect(self) -> bool:
        """连接到 MCP 服务器"""
        # 实际实现需要 subprocess 或 HTTP 连接
        # 这里简化为模拟
        self._initialized = True
        return True
    
    async def list_tools(self) -> List[Dict]:
        """列出可用工具"""
        if not self._initialized:
            await self.connect()
        return self._tools
    
    async def call_tool(self, name: str, arguments: Dict) -> Any:
        """调用工具"""
        if not self._initialized:
            await self.connect()
        # 实际实现需要发送 JSON-RPC 请求
        raise NotImplementedError("MCP client transport not implemented")
    
    def set_tools(self, tools: List[Dict]):
        """设置工具列表（用于模拟）"""
        self._tools = tools


# ──────────────────────────────────────────────
# 用法示例
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, '..')
    
    # 创建服务器
    server = MCPServer("biz-delivery-mcp", "4.0.0")
    
    # 注册内置工具
    register_builtin_tools(server)
    
    # 测试工具列表
    tools = server.get_tools()
    print(f"注册工具数: {len(tools)}")
    for t in tools[:5]:
        print(f"  - {t['name']}: {t['description'][:50]}...")
    
    # 模拟 JSON-RPC 请求
    async def test():
        # Initialize
        init_msg = JSONRPC.create_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }, "req-1")
        
        result = await server.handle_message(init_msg)
        print(f"\n初始化响应: {result['result']['serverInfo']['name']}")
        
        # List tools
        list_msg = JSONRPC.create_request("tools/list", {}, "req-2")
        result = await server.handle_message(list_msg)
        print(f"\n工具数量: {len(result['result']['tools'])}")
        
        # Call tool
        call_msg = JSONRPC.create_request("tools/call", {
            "name": "list_projects",
            "arguments": {}
        }, "req-3")
        result = await server.handle_message(call_msg)
        print(f"\nlist_projects 结果: {json.dumps(result, ensure_ascii=False)[:100]}...")
    
    asyncio.run(test())
