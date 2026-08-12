# sponge 知识摘要

## 概览
- 语言: go
- 包数: 91
- 接口总数: 33
- 结构体总数: 50
- 导出函数总数: 100
- CLI 命令: 42 个 (5 个包)

## 核心包

### `generate`
- Files: 20
- **Key Functions**: CacheCommand, ConfigCommand, ConfigmapCommand, DaoCommand, DeleteCodeMark

### `initial`
- Files: 20
- **Key Functions**: Close, CreateServices, InitApp

### `parser`
- Files: 13
- **Key Functions**: ConvertToSQLByMgoFields, ConvertToSQLByPgFields, GetMongodbTableInfo, GetMysqlTableInfo, GetPostgresqlTableInfo

### `commands`
- Files: 12
- **Key Functions**: AssistantCommand, GenGraphCommand, GenMicroCommand, GenWebCommand, GetSpongeDir

### `main`
- Files: 11

### `patch`
- Files: 11
- **Key Functions**: AdaptMonoRepoCommand, CheckAndModifyDuplicateErrorCodeNO, CopyGOModCommand, CopyProtoCommand, CopyThirdPartyProtoCommand

### `interceptor`
- Files: 11
- **Key Functions**: ClientCtxRequestID, ClientCtxRequestIDField, ClientOptionTracing, ClientTokenOption, CtxRequestIDField

### `server`
- Files: 8
- **Key Functions**: AdaptToWindowsZip, CompressPathToZip, GenerateCode, GetRecord, GetTemplateInfo

### `service`
- Files: 7
- **Key Functions**: GenerateFiles, NewUserExampleClient, NewUserExampleServer, RegisterAllService

### `utils`
- Files: 7
- **Key Functions**: AdaptiveMongodbDsn, AdaptiveMysqlDsn, AdaptivePostgresqlDsn, AdaptiveSqlite, AutoOpenBrowser

## CLI 命令体系

### `generate`
- Commands: RPCPbCommand, ConfigmapCommand, HandleSwaggerJSONCommand, GRPCAndHTTPPbCommand, GRPCAndHTTPCommand, HandlerPbCommand, RPCGwPbCommand, HTTPPbCommand

### `commands`
- Commands: GenWebCommand, AssistantCommand, GenGraphCommand, GenMicroCommand, MergeCommand, UpgradeCommand, InitCommand, PluginsCommand

### `patch`
- Commands: CopyProtoCommand, ModifyDuplicateErrorCodeNumCommand, ModifyDuplicateErrorCodeOffsetCommand, DeleteJSONOmitemptyCommand, GenTypesPbCommand, CopyGOModCommand, GenerateDBInitCommand, AdaptMonoRepoCommand

### `template`
- Commands: SQLCommand, FieldCommand, ProtobufCommand

### `assistant`
- Commands: ChatCommand, GenerateCommand

## 核心流程

### 启动流程
```
sponge/cmd/sponge/main.go
  ↓
  rootCMD, fmt, commands, os, generate
```
