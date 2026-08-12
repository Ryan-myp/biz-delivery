# conc, eino 知识摘要

## 概览
- 语言: go
- 包数: 41
- 接口总数: 39
- 结构体总数: 58
- 导出函数总数: 100
- CLI 命令: 0 个 (0 个包)

## 核心包

### `compose`
- Files: 20
- **Interfaces**: AnyGraph, Serializer, streamReader, GraphCompileCallback, channel
- **Key Functions**: AppendAddressSegment, BatchResumeWithData, CompositeInterrupt, ExtractInterruptInfo, FromField

### `adk`
- Files: 14
- **Interfaces**: Agent, OnSubAgents, ResumableAgent
- **Key Functions**: AddSessionValue, AddSessionValues, AgentWithDeterministicTransferTo, AgentWithOptions, AppendAddressSegment

### `callbacks`
- Files: 8
- **Interfaces**: Handler, TimingChecker
- **Key Functions**: AppendGlobalHandlers, AppendHandlers, EnsureRunInfo, InitCallbackHandlers, InitCallbacks

### `schema`
- Files: 8
- **Interfaces**: iStreamReader, MessagesTemplate
- **Key Functions**: AssistantMessage, ConcatMessageArray, ConcatMessageStream, ConcatMessages, ConcatToolResults

### `utils`
- Files: 7
- **Key Functions**: ConcurrentRetrieveWithCallback, WithMarshalOutput, WithSchemaModifier, WithUnmarshalArguments, WrapInvokableToolWithErrorHandler

### `pool`
- Files: 6
- **Key Functions**: New

### `filesystem`
- Files: 6
- **Interfaces**: Backend, ShellBackend, StreamingShellBackend
- **Key Functions**: NewInMemoryBackend, NewMiddleware

### `document`
- Files: 5
- **Interfaces**: Loader, Transformer
- **Key Functions**: ConvLoaderCallbackInput, ConvLoaderCallbackOutput, ConvTransformerCallbackInput, ConvTransformerCallbackOutput, GetLoaderCommonOptions

### `prompt`
- Files: 5
- **Interfaces**: ChatTemplate
- **Key Functions**: ConvCallbackInput, ConvCallbackOutput, FromMessages

### `tool`
- Files: 5
- **Interfaces**: BaseTool, InvokableTool, StreamableTool, EnhancedInvokableTool, EnhancedStreamableTool
- **Key Functions**: CompositeInterrupt, ConvCallbackInput, ConvCallbackOutput, Interrupt, StatefulInterrupt
