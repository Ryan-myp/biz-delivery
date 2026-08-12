# 术语表

## 核心术语

### `compose`
- **userInputVariant**: 
- **AnyGraph**: getGenericHelper, compile, inputType
- **Serializer**: Marshal, Unmarshal
- **streamReader**: copy, getType, getChunkType
- **GraphCompileCallback**: OnFinish

### `adk`
- **MessageType**: 
- **OnSubAgents**: OnSetSubAgents, OnSetAsSubAgent, OnDisallowTransferToParent
- **eventSenderToolWrapperMarker**: isEventSenderToolWrapper, user, NewEventSenderToolWrapper

### `schema`
- **contentBlockVariant**: 
- **userInputVariant**: 
- **assistantGenVariant**: 
- **functionToolCallVariant**: 
- **serverToolCallVariant**: 

### `callbacks`
- **Handler**: OnStart, OnEnd, OnError
- **TimingChecker**: Needed

### `internal`
- **Backend**: Write

### `prompt`
- **ChatTemplate**: Format
- **AgenticChatTemplate**: Format

### `filesystem`
- **MultiModalReader**: MultiModalRead
- **Backend**: LsInfo, Read, GrepRaw
- **Shell**: Execute
- **StreamingShell**: ExecuteStreaming

### `plantask`
- **Backend**: LsInfo, Read, Write

### `host`
- **MultiAgentCallback**: OnHandOff
