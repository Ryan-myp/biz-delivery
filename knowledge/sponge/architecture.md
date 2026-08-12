# 项目架构总览

## 概览
- 仓库: sponge
- 语言: go
- 包数: 91

## 包结构

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

### `gocrypto`
- Files: 7
- **Key Functions**: AesDecrypt, AesDecryptHex, AesEncrypt, AesEncryptHex, DesDecrypt

### `assistant`
- Files: 6
- **Interfaces**: UserExampleDao, Task
- **Key Functions**: ChatCommand, CleanUpAssistantCode, GenerateCommand, MergeAssistantCode, MyFuncName

### `cache`
- Files: 6
- **Interfaces**: UserExampleCache, CacheNameExampleCache, Cache
- **Key Functions**: BuildCacheKey, CloseGlobalMemory, Del, Get, GetGlobalMemoryCli

### `cpu`
- Files: 6
- **Interfaces**: CPU
- **Key Functions**: GetInfo, GetProcess, GetSystemCPU, ParseUintList, ReadStat

### `sse`
- Files: 6
- **Interfaces**: Data, Store
- **Key Functions**: NewAsyncTaskPool, NewClient, NewHub, NewSafeMap, SetNoConnectionErrText

### `rabbitmq`
- Files: 6
- **Key Functions**: NewConnection, NewConsumer, NewDelayedMessageExchange, NewDirectExchange, NewFanoutExchange

### `sasynq`
- Files: 6
- **Key Functions**: DefaultServerConfig, LoggingMiddleware, NewClient, NewScheduler, NewServer

### `handler`
- Files: 5
- **Interfaces**: UserExampleHandler
- **Key Functions**: GenerateFiles, NewUserExampleHandler, NewUserExamplePbHandler

### `database`
- Files: 5
- **Key Functions**: CloseDB, CloseRedis, GetCacheType, GetDB, GetRedisCli

### `tracer`
- Files: 5
- **Interfaces**: ResourceOption
- **Key Functions**: Close, GetProvider, Init, InitWithConfig, NewConsoleExporter

### `window`
- Files: 5
- **Interfaces**: Metric, Aggregation, RollingCounter
- **Key Functions**: Avg, Count, Max, Min, NewRollingCounter

### `logger`
- Files: 5
- **Key Functions**: Any, Bool, ByteString, Debug, Debugf

### `kafka`
- Files: 5
- **Key Functions**: AsyncProducerWithClientID, AsyncProducerWithConfig, AsyncProducerWithFlushBytes, AsyncProducerWithFlushFrequency, AsyncProducerWithFlushMessages

### `wcipher`
- Files: 5
- **Interfaces**: Cipher, CipherMode, Padding
- **Key Functions**: NewAES, NewAESWith, NewBlockCipher, NewCBCMode, NewCFBMode

### `middleware`
- Files: 5
- **Key Functions**: Auth, Cors, GetClaims, Logging, RateLimit

### `merge`
- Files: 4
- **Key Functions**: GRPCServiceCode, GinHandlerCode, GinServiceCode

### `template`
- Files: 4
- **Key Functions**: FieldCommand, ProtobufCommand, SQLCommand

### `routers`
- Files: 4
- **Key Functions**: NewRouter, NewRouter_pbExample

### `types`
- Files: 4

### `ecode`
- Files: 4
- **Key Functions**: Any

### `v1`
- Files: 4
- **Interfaces**: UserExampleClient, UserExampleServer, UnsafeUserExampleServer, UserExampleLogicer
- **Key Functions**: NewUserExampleClient, RegisterUserExampleRouter, RegisterUserExampleServer, WithUserExampleErrorToHTTPCode, WithUserExampleHTTPResponse

### `jwt`
- Files: 4
- **Key Functions**: GenerateCustomToken, GenerateToken, GenerateTwoTokens, GetClaimsUnverified, Init

### `encoding`
- Files: 4
- **Interfaces**: Codec, Encoding
- **Key Functions**: GetCodec, GzipDecode, GzipEncode, Marshal, RegisterCodec

### `query`
- Files: 4
- **Key Functions**: DefaultPage, NewPage, SetMaxSize, WithValidateFn, WithWhitelistNames

### `consul`
- Files: 4
- **Key Functions**: New, NewClient, NewRegistry, NewRegistryWithOptions, WithHealthCheck

### `module`
- Files: 3
- **Key Functions**: NewCodeAst, NewRouterCodeAst, ParseErrorCode, ParseGRPCMethodsTestAndBenchmarkCode, ParseHandlerAndServiceCode

### `parse`
- Files: 3
- **Key Functions**: GetImportPkg, GetMethods, GetServices, GetSourceImportPkg, ParseHTTPPbServices

### `metrics`
- Files: 3
- **Key Functions**: ClientHTTPService, ClientRegister, NewCustomListener, Register, ServerHTTPService

### `goast`
- Files: 3
- **Key Functions**: FilterFuncCode, FilterFuncCodeByFile, MergeGoCode, MergeGoFile, NewCodeAst

### `stat`
- Files: 3
- **Key Functions**: Init, WithAlarm, WithCPUThreshold, WithLog, WithMemoryThreshold

### `dlock`
- Files: 3
- **Interfaces**: Locker
- **Key Functions**: NewEtcd, NewRedisClusterLock, NewRedisLock

### `etcd`
- Files: 3
- **Key Functions**: New, NewRegistry, NewRegistryWithOptions, WithContext, WithMaxRetry

### `router`
- Files: 2
- **Key Functions**: GenerateFiles

### `rpcclient`
- Files: 2
- **Key Functions**: CloseServerNameExampleRPCConn, GetServerNameExampleRPCConn, NewServerNameExampleRPCConn

### `config`
- Files: 2
- **Key Functions**: Get, Init, NewCenter, Set, Show

### `dao`
- Files: 2
- **Interfaces**: UserExampleDao
- **Key Functions**: NewUserExampleDao

### `model`
- Files: 2

### `docs`
- Files: 2

### `ratelimit`
- Files: 2
- **Interfaces**: Limiter
- **Key Functions**: NewLimiter, WithBucket, WithCPUQuota, WithCPUThreshold, WithWindow

### `circuitbreaker`
- Files: 2
- **Interfaces**: CircuitBreaker
- **Key Functions**: NewBreaker, WithBucket, WithRequest, WithSuccess, WithWindow

### `benchmark`
- Files: 2
- **Interfaces**: Runner
- **Key Functions**: New

### `grpccli`
- Files: 2
- **Key Functions**: Dial, NewClient, WithDialOptions, WithDiscovery, WithDiscoveryInsecure

### `gtls`
- Files: 2
- **Key Functions**: GetClientTLSCredentials, GetClientTLSCredentialsByCA, GetServerTLSCredentials, GetServerTLSCredentialsByCA

### `gocron`
- Files: 2
- **Key Functions**: DeleteTask, EveryHour, EveryMinute, EverySecond, Everyday

### `gemini`
- Files: 2
- **Key Functions**: NewClient, WithEnableContext, WithInitialContextMessages, WithModel

### `chatgpt`
- Files: 2
- **Key Functions**: NewClient, WithEnableContext, WithInitialContextMessages, WithInitialRole, WithMaxTokens

### `goredis`
- Files: 2
- **Key Functions**: Close, CloseCluster, Init, InitCluster, InitSentinel

### `mgo`
- Files: 2
- **Key Functions**: Close, ConvertToObjectIDs, EmbedDeletedAt, EmbedUpdatedAt, ExcludeDeleted

### `nacoscli`
- Files: 2
- **Key Functions**: GetConfig, Init, NewNamingClient, WithAuth, WithClientConfig

### `consulcli`
- Files: 2
- **Key Functions**: Init, WithConfig, WithDatacenter, WithScheme, WithToken

### `sgorm`
- Files: 2
- **Key Functions**: CloseDB, GetTableName, SetDriver

### `postgresql`
- Files: 2
- **Key Functions**: Close, Init, WithConnMaxLifetime, WithEnableForeignKey, WithEnableTrace

### `sqlite`
- Files: 2
- **Key Functions**: Close, Init, WithConnMaxLifetime, WithEnableForeignKey, WithEnableTrace

### `mysql`
- Files: 2
- **Key Functions**: Close, Init, InitTidb, WithConnMaxLifetime, WithEnableForeignKey

### `etcdcli`
- Files: 2
- **Key Functions**: Init, WithAuth, WithAutoSyncInterval, WithConfig, WithDialTimeout

### `jy2struct`
- Files: 2
- **Key Functions**: Convert, FmtFieldName, ParseJSON, ParseYaml

### `prof`
- Files: 2
- **Key Functions**: EnableTrace, NewProfile, Register, SetDurationSecond, WaitSign

### `discovery`
- Files: 2
- **Key Functions**: DisableDebugLog, IsSecure, NewBuilder, WithInsecure, WithTimeout

### `registry`
- Files: 2
- **Interfaces**: Registry, Discovery, Watcher
- **Key Functions**: NewServiceInstance, WithMetadata, WithVersion

### `nacos`
- Files: 2
- **Key Functions**: New, NewRegistry, NewRegistryWithOptions, WithCluster, WithDefaultKind

### `configs`
- Files: 1
- **Key Functions**: Path

### `app`
- Files: 1
- **Interfaces**: IServer
- **Key Functions**: New

### `resolve`
- Files: 1
- **Key Functions**: Register

### `certfile`
- Files: 1
- **Key Functions**: Path

### `keepalive`
- Files: 1
- **Key Functions**: ClientKeepAlive, ServerKeepAlive

### `client`
- Files: 1
- **Key Functions**: Dial, NewClient, WithDialOption, WithLoadBalance, WithSecure

### `aicli`
- Files: 1
- **Interfaces**: Assistanter

### `deepseek`
- Files: 1
- **Key Functions**: NewClient

### `proto`
- Files: 1

### `json`
- Files: 1

### `group`
- Files: 1
- **Key Functions**: NewGroup

### `glog`
- Files: 1
- **Key Functions**: NewCustomGormLogger

### `dbclose`
- Files: 1
- **Key Functions**: Close

### `krand`
- Files: 1
- **Key Functions**: Bytes, Float64, Int, NewID, NewSeriesID

### `mem`
- Files: 1
- **Key Functions**: GetProcessMemory, GetSystemMemory

### `sql2code`
- Files: 1
- **Key Functions**: Generate, GenerateOne

### `httpcli`
- Files: 1
- **Key Functions**: Delete, Get, New, Patch, Post

### `gobash`
- Files: 1
- **Key Functions**: Exec, Run

### `copier`
- Files: 1
- **Key Functions**: Copy, CopyDefault, CopyWithOption

### `replacer`
- Files: 1
- **Interfaces**: Replacer
- **Key Functions**: New, NewFS

### `conf`
- Files: 1
- **Key Functions**: Parse, ParseConfigData, Show
