# 代码库学习任务

你是一个资深软件架构师。请基于以下代码扫描结果，
总结这个系统的架构、业务流程、数据模型和关键技术决策。

## 仓库信息
- **sponge**: go @ /Users/yanping.ma/GolandProjects/sponge

## 代码结构摘要
- Structs: 79
- Functions: 121
- Routes: 0
- Imports: 0

## 关键业务 Struct

### `serviceMethods`
文件: sponge/cmd/sponge/commands/merge/module/merge.go

### `handlerGenerator`
文件: sponge/cmd/sponge/commands/generate/handler.go

### `configType`
文件: sponge/cmd/sponge/commands/generate/config.go

### `serviceGenerator`
文件: sponge/cmd/sponge/commands/generate/service.go

### `serviceAndHandlerGenerator`
文件: sponge/cmd/sponge/commands/generate/service-handler.go

### `copyConfigGenerator`
文件: sponge/cmd/sponge/commands/generate/configmap.go

### `handlerPbGenerator`
文件: sponge/cmd/sponge/commands/generate/handler-pb.go

### `PbService`
文件: sponge/cmd/protoc-gen-json-field/parser/parser.go

### `ServiceMethod`
文件: sponge/cmd/protoc-gen-json-field/parser/parser.go

### `Service`
文件: sponge/cmd/protoc-gen-json-field/generate/gen.go

### `ServiceMethod`
文件: sponge/cmd/protoc-gen-go-gin/internal/parse/parse.go

### `PbService`
文件: sponge/cmd/protoc-gen-go-gin/internal/parse/parse.go

### `HTTPPbService`
文件: sponge/cmd/protoc-gen-go-gin/internal/parse/parse.go

### `handlerLogicFields`
文件: sponge/cmd/protoc-gen-go-gin/internal/generate/handler/gen.go

### `serviceLogicFields`
文件: sponge/cmd/protoc-gen-go-gin/internal/generate/service/gen.go

## 服务层
- **serviceMethods** (0 methods)
- **serviceGenerator** (0 methods)
- **serviceAndHandlerGenerator** (0 methods)
- **PbService** (0 methods)
- **ServiceMethod** (0 methods)
- **Service** (0 methods)
- **ServiceMethod** (0 methods)
- **PbService** (0 methods)
- **HTTPPbService** (0 methods)
- **serviceLogicFields** (0 methods)

---

请基于以上信息，输出以下结构化知识：

1. **架构总览** — 系统定位、技术栈、服务拆分、部署架构
2. **核心业务流程** — 主要业务场景的流程描述（用文字，不需要 mermaid）
3. **数据库表结构** — 表名、字段、ER 关系
4. **服务层架构** — Service/DAO/Model 分层说明
5. **外部系统集成** — 第三方 API、消息队列等
6. **术语 Glossary** — 业务术语及其含义