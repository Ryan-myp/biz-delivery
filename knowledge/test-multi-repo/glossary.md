# 术语表

## 核心术语

### `compose`
- **AnyGraph**: getGenericHelper, compile, inputType
- **Serializer**: Marshal, Unmarshal
- **streamReader**: copy, getType, getChunkType
- **GraphCompileCallback**: OnFinish
- **channel**: reportValues, reportDependencies, reportSkip

### `adk`
- **Agent**: Name, Description, SetAutomaticClose
- **OnSubAgents**: OnSetSubAgents, OnSetAsSubAgent, OnDisallowTransferToParent
- **ResumableAgent**: Resume

### `callbacks`
- **Handler**: OnStart, OnEnd, OnError
- **TimingChecker**: Needed

### `schema`
- **iStreamReader**: recvAny, copyAny, Close
- **MessagesTemplate**: Format

### `filesystem`
- **Backend**: LsInfo, Read, GrepRaw
- **ShellBackend**: Execute
- **StreamingShellBackend**: ExecuteStreaming

### `document`
- **Loader**: Load
- **Transformer**: Transform

### `prompt`
- **ChatTemplate**: Format

### `tool`
- **BaseTool**: Info
- **InvokableTool**: InvokableRun
- **StreamableTool**: StreamableRun
- **EnhancedInvokableTool**: InvokableRun
- **EnhancedStreamableTool**: StreamableRun
