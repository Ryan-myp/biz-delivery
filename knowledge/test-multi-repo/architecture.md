# 项目架构总览

## 概览
- 仓库: conc, eino
- 语言: go
- 包数: 41
- 接口总数: 39
- 结构体总数: 58
- 导出函数总数: 100

## 包结构

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

### `host`
- Files: 5
- **Interfaces**: MultiAgentCallback
- **Key Functions**: ConvertCallbackHandlers, NewMultiAgent, WithAgentCallbacks

### `deep`
- Files: 4
- **Key Functions**: New

### `embedding`
- Files: 4
- **Interfaces**: Embedder
- **Key Functions**: ConvCallbackInput, ConvCallbackOutput, GetCommonOptions, WithModel

### `parser`
- Files: 4
- **Interfaces**: Parser
- **Key Functions**: GetCommonOptions, NewExtParser, WithConf, WithExtraMeta, WithURI

### `retriever`
- Files: 4
- **Interfaces**: Retriever
- **Key Functions**: ConvCallbackInput, ConvCallbackOutput, GetCommonOptions, WithDSLInfo, WithEmbedding

### `model`
- Files: 4
- **Interfaces**: BaseChatModel, ChatModel, ToolCallingChatModel
- **Key Functions**: ConvCallbackInput, ConvCallbackOutput, GetCommonOptions, WithMaxTokens, WithModel

### `indexer`
- Files: 4
- **Interfaces**: Indexer
- **Key Functions**: ConvCallbackInput, ConvCallbackOutput, GetCommonOptions, WithEmbedding, WithSubIndexes

### `react`
- Files: 4
- **Interfaces**: MessageFuture
- **Key Functions**: BuildAgentCallback, NewAgent, NewPersonaModifier, SetReturnDirectly, WithChatModelOptions

### `internal`
- Files: 3
- **Key Functions**: GetConcatFunc, GetMergeFunc

### `core`
- Files: 3
- **Interfaces**: CheckPointStore, InterruptContextsProvider
- **Key Functions**: AppendAddressSegment, BatchResumeWithData, FromInterruptContexts, GetCurrentAddress, GetNextResumptionPoints

### `skill`
- Files: 3
- **Interfaces**: Backend
- **Key Functions**: New, NewLocalBackend

### `reduction`
- Files: 3
- **Interfaces**: Backend
- **Key Functions**: NewClearToolResult, NewToolResultMiddleware

### `parent`
- Files: 3
- **Key Functions**: NewIndexer, NewRetriever

### `iter`
- Files: 2

### `panics`
- Files: 2
- **Key Functions**: NewRecovered, Try

### `multierror`
- Files: 2

### `generic`
- Files: 2
- **Key Functions**: ParseTypeName

### `planexecute`
- Files: 2
- **Interfaces**: Plan
- **Key Functions**: New, NewExecutor, NewPlanner, NewReplanner

### `agent`
- Files: 2
- **Key Functions**: ChatModelWithTools, GetComposeOptions, WithComposeOptions

### `conc`
- Files: 1
- **Key Functions**: NewWaitGroup

### `stream`
- Files: 1
- **Key Functions**: New

### `eino`
- Files: 1

### `safe`
- Files: 1
- **Key Functions**: NewPanicErr

### `serialization`
- Files: 1

### `mock`
- Files: 1

### `gmap`
- Files: 1

### `gslice`
- Files: 1

### `supervisor`
- Files: 1
- **Key Functions**: New

### `components`
- Files: 1
- **Interfaces**: Typer, Checker
- **Key Functions**: GetType, IsCallbacksEnabled

### `multiquery`
- Files: 1
- **Key Functions**: NewRetriever

### `router`
- Files: 1
- **Key Functions**: NewRetriever

---

## 核心依赖

- `compose` → 
		}

		destValue = field
	}
}

func instantiateIfNeeded(field reflect.Value) {
	if field.Kind() == reflect.Ptr {
		if field.IsNil() {
			field.Set(reflect.New(field.Type().Elem()))
		}
	} else if field.Kind() == reflect.Map {
		if field.IsNil() {
			field.Set(reflect.MakeMap(field.Type()))
		}
	}
}

func newInstanceByType(typ reflect.Type) reflect.Value {
	switch typ.Kind() {
	case reflect.Map:
		return reflect.MakeMap(typ)
	case reflect.Slice, reflect.Array:
		slice := reflect.New(typ).Elem()
		slice.Set(reflect.MakeSlice(typ, 0, 0))
		return slice
	case reflect.Ptr:
		typ = typ.Elem()
		origin := reflect.New(typ)
		nested := newInstanceByType(typ)
		origin.Elem().Set(nested)

		return origin
	default:
		return reflect.New(typ).Elem()
	}
}

func checkAndExtractFromField(fromField string, input reflect.Value) (reflect.Value, error) {
	f := input.FieldByName(fromField)
	if !f.IsValid() {
		return reflect.Value{}, fmt.Errorf(, 
	}

	info, ok := v.(*toolCallInfo)
	if !ok {
		return , 

// FromFieldPath creates a FieldMapping that maps a single predecessor field path to the entire successor input.
// This is an exclusive mapping - once set, no other field mappings can be added since the successor input
// has already been fully mapped.
//
// Example:
//
//	// Maps the 'name' field from nested 'user.profile' to the entire successor input
//	FromFieldPath(FieldPath{, 
//			return nil
//		})
//		return input, nil
//	}
func ProcessState[S any](ctx context.Context, handler func(context.Context, S) error) error {
	s, pMu, err := getState[S](ctx)
	if err != nil {
		return fmt.Errorf(, 
}

func getToolsNodeOptions(opts ...ToolsNodeOption) *toolsNodeOptions {
	o := &toolsNodeOptions{
		ToolOptions: make([]tool.Option, 0),
	}
	for _, opt := range opts {
		opt(o)
	}
	return o
}

type toolCallInfoKey struct{}
type toolCallInfo struct {
	toolCallID string
}

func setToolCallInfo(ctx context.Context, toolCallInfo *toolCallInfo) context.Context {
	return context.WithValue(ctx, toolCallInfoKey{}, toolCallInfo)
}

// GetToolCallID gets the current tool call id from the context.
func GetToolCallID(ctx context.Context) string {
	v := ctx.Value(toolCallInfoKey{})
	if v == nil {
		return 
- `adk` → 
	// These placeholders will be replaced with session values for , 
	TransferToAgentToolDesc = , 

func newBridgeStore() *bridgeStore {
	return &bridgeStore{}
}

func newResumeBridgeStore(data []byte) *bridgeStore {
	return &bridgeStore{
		Data:  data,
		Valid: true,
	}
}

type bridgeStore struct {
	Data  []byte
	Valid bool
}

func (m *bridgeStore) Get(_ context.Context, _ string) ([]byte, bool, error) {
	if m.Valid {
		return m.Data, true, nil
	}
	return nil, false, nil
}

func (m *bridgeStore) Set(_ context.Context, _ string, checkPoint []byte) error {
	m.Data = checkPoint
	m.Valid = true
	return nil
}

func getNextResumeAgent(ctx context.Context, info *ResumeInfo) (string, error) {
	nextAgents, err := core.GetNextResumptionPoints(ctx)
	if err != nil {
		return , 
)

var (
	toolInfoTransferToAgent = &schema.ToolInfo{
		Name: TransferToAgentToolName,
		Desc: TransferToAgentToolDesc,

		ParamsOneOf: schema.NewParamsOneOfByParams(map[string]*schema.ParameterInfo{
			,  +
			
- `callbacks` → AS IS, License, Model execution started: %s, Prompt execution completed: %s, context
- `schema` → 
			rt = pt.Elem()
		}
	}
	if rt.Name() != , 
		var err error
		if jinjaEnv.Statements.Exists(jinjaInclude) {
			err = jinjaEnv.Statements.Replace(jinjaInclude, func(parser *parser.Parser, args *parser.Parser) (nodes.Statement, error) {
				return nil, fmt.Errorf(, 
	case ChatMessagePartTypeAudioURL:
		if part.AudioURL != nil {
			return fmt.Sprintf(, 
	case ChatMessagePartTypeFileURL:
		if part.FileURL != nil {
			return fmt.Sprintf(, 
	case ChatMessagePartTypeVideoURL:
		if part.VideoURL != nil {
			return fmt.Sprintf(
- `utils` → 
	}

	parts := strings.Split(s, , 
	}

	return i.info.Name
}

// snakeToCamel converts a snake_case string to CamelCase.
func snakeToCamel(s string) string {
	if s == , 
	}

	return s.info.Name
}

// EnhancedStreamFunc is the function type for the enhanced streamable tool.
type EnhancedStreamFunc[T any] func(ctx context.Context, input T) (output *schema.StreamReader[*schema.ToolResult], err error)

// OptionableEnhancedStreamFunc is the function type for the enhanced streamable tool with tool option.
type OptionableEnhancedStreamFunc[T any] func(ctx context.Context, input T, opts ...tool.Option) (output *schema.StreamReader[*schema.ToolResult], err error)

// InferEnhancedStreamTool creates an EnhancedStreamableTool from a given function by inferring the ToolInfo from the function's request parameters.
// End-user can pass a SchemaCustomizerFn in opts to customize the go struct tag parsing process, overriding default behavior.
func InferEnhancedStreamTool[T any](toolName, toolDesc string, s EnhancedStreamFunc[T], opts ...Option) (tool.EnhancedStreamableTool, error) {
	ti, err := goStruct2ToolInfo[T](toolName, toolDesc, opts...)
	if err != nil {
		return nil, err
	}

	return NewEnhancedStreamTool(ti, s, opts...), nil
}

// InferOptionableEnhancedStreamTool creates an EnhancedStreamableTool from a given function by inferring the ToolInfo from the function's request parameters, with tool option.
func InferOptionableEnhancedStreamTool[T any](toolName, toolDesc string, s OptionableEnhancedStreamFunc[T], opts ...Option) (tool.EnhancedStreamableTool, error) {
	ti, err := goStruct2ToolInfo[T](toolName, toolDesc, opts...)
	if err != nil {
		return nil, err
	}

	return newOptionableEnhancedStreamTool(ti, s, opts...), nil
}

// NewEnhancedStreamTool Create an enhanced streaming tool, where the input is in JSON format and output is *schema.StreamReader[*schema.ToolResult].
func NewEnhancedStreamTool[T any](desc *schema.ToolInfo, s EnhancedStreamFunc[T], opts ...Option) tool.EnhancedStreamableTool {
	return newOptionableEnhancedStreamTool(desc,
		func(ctx context.Context, input T, _ ...tool.Option) (output *schema.StreamReader[*schema.ToolResult], err error) {
			return s(ctx, input)
		},
		opts...)
}

func newOptionableEnhancedStreamTool[T any](desc *schema.ToolInfo, s OptionableEnhancedStreamFunc[T], opts ...Option) tool.EnhancedStreamableTool {
	to := getToolOptions(opts...)

	return &enhancedStreamableTool[T]{
		info: desc,
		um:   to.um,
		Fn:   s,
	}
}

type enhancedStreamableTool[T any] struct {
	info *schema.ToolInfo

	um UnmarshalArguments

	Fn OptionableEnhancedStreamFunc[T]
}

func (s *enhancedStreamableTool[T]) Info(ctx context.Context) (*schema.ToolInfo, error) {
	return s.info, nil
}

func (s *enhancedStreamableTool[T]) StreamableRun(ctx context.Context, toolArgument *schema.ToolArgument, opts ...tool.Option) (
	outStream *schema.StreamReader[*schema.ToolResult], err error) {

	var inst T
	if s.um != nil {
		var val any
		val, err = s.um(ctx, toolArgument.Text)
		if err != nil {
			return nil, fmt.Errorf(, 

	paramsOneOf := schema.NewParamsOneOfByJSONSchema(js)

	return paramsOneOf, nil
}

// NewTool Create a tool, where the input and output are both in JSON format.
func NewTool[T, D any](desc *schema.ToolInfo, i InvokeFunc[T, D], opts ...Option) tool.InvokableTool {
	return newOptionableTool(desc, func(ctx context.Context, input T, _ ...tool.Option) (D, error) {
		return i(ctx, input)
	}, opts...)
}

func newOptionableTool[T, D any](desc *schema.ToolInfo, i OptionableInvokeFunc[T, D], opts ...Option) tool.InvokableTool {
	to := getToolOptions(opts...)

	return &invokableTool[T, D]{
		info: desc,
		um:   to.um,
		m:    to.m,
		Fn:   i,
	}
}

type invokableTool[T, D any] struct {
	info *schema.ToolInfo

	um UnmarshalArguments
	m  MarshalOutput

	Fn OptionableInvokeFunc[T, D]
}

func (i *invokableTool[T, D]) Info(ctx context.Context) (*schema.ToolInfo, error) {
	return i.info, nil
}

// InvokableRun invokes the tool with the given arguments.
func (i *invokableTool[T, D]) InvokableRun(ctx context.Context, arguments string, opts ...tool.Option) (output string, err error) {

	var inst T
	if i.um != nil {
		var val any
		val, err = i.um(ctx, arguments)
		if err != nil {
			return ,  {
		return 
