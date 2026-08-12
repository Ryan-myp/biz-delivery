# Eino 框架知识摘要

## 概览
- 语言: go
- 包数: 35
- 接口总数: 39
- 结构体总数: 342
- 导出函数总数: 215

## 核心包

### `compose`
- Files: 20
- **Interfaces**:
  - `AnyGraph`: getGenericHelper, compile, inputType
  - `Serializer`: Marshal, Unmarshal
  - `streamReader`: copy, getType, getChunkType
- **Key Functions**: AppendAddressSegment, BatchResumeWithData, CompositeInterrupt, ExtractInterruptInfo, FromField

### `adk`
- Files: 14
- **Interfaces**:
  - `Agent`: Name, Description, SetAutomaticClose
  - `OnSubAgents`: OnSetSubAgents, OnSetAsSubAgent, OnDisallowTransferToParent
  - `ResumableAgent`: Resume
- **Key Functions**: AddSessionValue, AddSessionValues, AgentWithDeterministicTransferTo, AgentWithOptions, AppendAddressSegment

### `callbacks`
- Files: 8
- **Interfaces**:
  - `Handler`: OnStart, OnEnd, OnError
  - `TimingChecker`: Needed
- **Key Functions**: AppendGlobalHandlers, AppendHandlers, EnsureRunInfo, InitCallbackHandlers, InitCallbacks

### `schema`
- Files: 8
- **Interfaces**:
  - `iStreamReader`: recvAny, copyAny, Close
  - `MessagesTemplate`: Format
- **Key Functions**: AssistantMessage, ConcatMessageArray, ConcatMessageStream, ConcatMessages, ConcatToolResults

### `utils`
- Files: 7
- **Key Functions**: ConcurrentRetrieveWithCallback, WithMarshalOutput, WithSchemaModifier, WithUnmarshalArguments, WrapInvokableToolWithErrorHandler

### `filesystem`
- Files: 6
- **Interfaces**:
  - `Backend`: LsInfo, Read, GrepRaw
  - `ShellBackend`: Execute
  - `StreamingShellBackend`: ExecuteStreaming
- **Key Functions**: NewInMemoryBackend, NewMiddleware

### `document`
- Files: 5
- **Interfaces**:
  - `Loader`: Load
  - `Transformer`: Transform
- **Key Functions**: ConvLoaderCallbackInput, ConvLoaderCallbackOutput, ConvTransformerCallbackInput, ConvTransformerCallbackOutput, GetLoaderCommonOptions

### `prompt`
- Files: 5
- **Interfaces**:
  - `ChatTemplate`: Format
- **Key Functions**: ConvCallbackInput, ConvCallbackOutput, FromMessages

### `tool`
- Files: 5
- **Interfaces**:
  - `BaseTool`: Info
  - `InvokableTool`: InvokableRun
  - `StreamableTool`: StreamableRun
- **Key Functions**: CompositeInterrupt, ConvCallbackInput, ConvCallbackOutput, Interrupt, StatefulInterrupt

### `host`
- Files: 5
- **Interfaces**:
  - `MultiAgentCallback`: OnHandOff
- **Key Functions**: ConvertCallbackHandlers, NewMultiAgent, WithAgentCallbacks

---

## 依赖关系

- `callbacks` → github.com/cloudwego/eino/callbacks, github.com/cloudwego/eino/components, github.com/cloudwego/eino/components/document, github.com/cloudwego/eino/components/embedding, github.com/cloudwego/eino/components/indexer
- `document` → github.com/cloudwego/eino/callbacks, github.com/cloudwego/eino/components/document/parser, github.com/cloudwego/eino/schema
- `prompt` → github.com/cloudwego/eino/callbacks, github.com/cloudwego/eino/components, github.com/cloudwego/eino/schema
- `tool` → github.com/cloudwego/eino/callbacks, github.com/cloudwego/eino/internal/core, github.com/cloudwego/eino/schema

## 核心设计模式

1. **Option 模式**: 每个组件都有 Options/Option 函数用于配置
2. **泛型接口**: Runnable[I, O] 统一 4 种数据流模式
3. **依赖注入**: 组件通过 Option 注入依赖
4. **回调机制**: Handler/Callback 用于监控和扩展
