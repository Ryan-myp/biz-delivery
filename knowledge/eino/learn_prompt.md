# 代码库学习任务

你是一个资深软件架构师。请基于以下代码扫描结果，
总结这个系统的架构、业务流程、数据模型和关键技术决策。

## 仓库信息
- **eino**: go @ /Users/yanping.ma/GolandProjects/eino

## 代码结构摘要
- Structs: 550
- Functions: 595
- Routes: 0
- Imports: 0

## 关键业务 Struct

### `request`
文件: eino/adk/agent_tool.go
- `Request`: string json:request

### `ToolsConfig`
文件: eino/adk/chatmodel.go

### `ChatModelAgentConfig`
文件: eino/adk/chatmodel.go

### `cbHandler`
文件: eino/adk/chatmodel.go

### `noToolsCbHandler`
文件: eino/adk/chatmodel.go

### `LsInfoRequest`
文件: eino/adk/filesystem/backend.go

### `ReadRequest`
文件: eino/adk/filesystem/backend.go

### `GrepRequest`
文件: eino/adk/filesystem/backend.go

### `GlobInfoRequest`
文件: eino/adk/filesystem/backend.go

### `WriteRequest`
文件: eino/adk/filesystem/backend.go

### `EditRequest`
文件: eino/adk/filesystem/backend.go

### `ExecuteRequest`
文件: eino/adk/filesystem/backend.go

### `ExecuteResponse`
文件: eino/adk/filesystem/backend.go

### `DeterministicTransferConfig`
文件: eino/adk/flow.go

### `Config`
文件: eino/adk/middlewares/filesystem/filesystem.go

### `toolResultOffloadingConfig`
文件: eino/adk/middlewares/filesystem/large_tool_result.go

### `ClearToolResultConfig`
文件: eino/adk/middlewares/reduction/clear_tool_result.go

### `toolResultOffloadingConfig`
文件: eino/adk/middlewares/reduction/large_tool_result.go

### `ToolResultConfig`
文件: eino/adk/middlewares/reduction/tool_result.go

### `LocalBackendConfig`
文件: eino/adk/middlewares/skill/local.go

## 服务层
- **edgeHandlerManager** (0 methods)
- **preNodeHandlerManager** (0 methods)
- **preBranchHandlerManager** (0 methods)
- **channelManager** (0 methods)
- **taskManager** (0 methods)
- **CtxManagerKey** (0 methods)

## 调用关系 (Call Graph)
- **?** ← called by: 

## 入口点 (Entry Points)
- **eino**
- **callbacks**
- **compose**
- **internal**
- **safe**
- **core**
- **serialization**
- **mock**
- **adk**
- **embedding**
- **document**
- **retriever**
- **model**
- **indexer**
- **gmap**
- **generic**
- **gslice**
- **schema**
- **skill**
- **filesystem**

## 权限/鉴权模型 (Authentication & Authorization)
共 1 个中间件/鉴权组件

- **受保护路由**: 0 个路由需要登录认证

## 向后兼容 (Backward Compatibility)
共 20 个兼容问题:
- DEPRECATED: 20

- **[S:critical]** `DEPRECATED` (eino/callbacks/interface.go:57): // Deprecated: Use AppendGlobalHandlers instead.
- **[S:warning]** `DEPRECATED` (eino/compose/graph_compile_options.go:76): // Deprecated: Eager execution is automatically enabled by default when a node's trigger mode is set to AllPredecessor.
- **[S:critical]** `DEPRECATED` (eino/compose/checkpoint.go:46): // Deprecated: RegisterSerializableType is deprecated. Use schema.RegisterName[T](name) instead.
- **[S:warning]** `DEPRECATED` (eino/compose/interrupt.go:44): // Deprecated: prefer Interrupt/StatefulInterrupt and CompositeInterrupt.
- **[S:warning]** `DEPRECATED` (eino/compose/interrupt.go:50): // Deprecated: prefer Interrupt(ctx, info) or StatefulInterrupt(ctx, info, state).
- **[S:critical]** `DEPRECATED` (eino/compose/workflow.go:413): // Deprecated: use *Workflow[I,O].End() to obtain a WorkflowNode instance for END, then work with it just like a normal 
- **[S:warning]** `DEPRECATED` (eino/schema/message.go:422): // Deprecated: This struct is deprecated as the MultiContent field is deprecated.
- **[S:warning]** `DEPRECATED` (eino/schema/message.go:459): // Deprecated: This struct is deprecated as the MultiContent field is deprecated.
- **[S:warning]** `DEPRECATED` (eino/schema/message.go:476): // Deprecated: This struct is deprecated as the MultiContent field is deprecated.
- **[S:warning]** `DEPRECATED` (eino/schema/message.go:493): // Deprecated: This struct is deprecated as the MultiContent field is deprecated.
- **[S:warning]** `DEPRECATED` (eino/schema/message.go:509): // Deprecated: This struct is deprecated as the MultiContent field is deprecated.
- **[S:critical]** `DEPRECATED` (eino/schema/message.go:626): // Deprecated: Use UserInputMultiContent for user multimodal inputs and AssistantGenMultiContent for model multimodal ou
- **[S:critical]** `DEPRECATED` (eino/adk/interrupt.go:36): // Deprecated: use InterruptContexts from the embedded InterruptInfo for user-facing details,
- **[S:critical]** `DEPRECATED` (eino/adk/chatmodel.go:122): // Deprecated: use ResumeWithData and ChatModelAgentResumeData instead.
- **[S:critical]** `DEPRECATED` (eino/adk/middlewares/reduction/clear_tool_result.go:59): // Deprecated: Use NewToolResultMiddleware instead, which combines clearing
- **[S:critical]** `DEPRECATED` (eino/components/model/interface.go:36): // Deprecated: Please use ToolCallingChatModel interface instead, which provides a safer way to bind tools
- **[S:critical]** `DEPRECATED` (eino/flow/agent/multiagent/host/types.go:152): // Deprecated: ChatModel is deprecated, please use ToolCallingModel instead.
- **[S:warning]** `DEPRECATED` (eino/flow/agent/react/option.go:44): // Deprecated: This changes tool list for ToolsNode ONLY.
- **[S:critical]** `DEPRECATED` (eino/flow/agent/react/react.go:141): // Deprecated: Use ToolCallingModel instead.
- **[S:warning]** `DEPRECATED` (eino/flow/agent/react/react.go:206): // Deprecated: Prefer directly including the persona message in the

---

请基于以上信息，输出以下结构化知识：

1. **架构总览** — 系统定位、技术栈、服务拆分、部署架构
2. **核心业务流程** — 主要业务场景的流程描述（用文字，不需要 mermaid）
3. **数据库表结构** — 表名、字段、ER 关系
4. **服务层架构** — Service/DAO/Model 分层说明
5. **外部系统集成** — 第三方 API、消息队列等
6. **术语 Glossary** — 业务术语及其含义