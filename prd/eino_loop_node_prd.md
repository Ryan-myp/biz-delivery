# PRD: Eino 框架新增 LoopNode 组件

## 一、需求背景

当前 Eino 框架支持 Chain、Branch、Parallel 等节点类型，但缺乏原地循环（Loop）节点。在某些 Agent 场景中，需要重复执行某个子图直到满足终止条件，例如：
- RAG 多轮检索：反复检索直到找到满意答案
- 工具调用重试：工具失败后自动重试 N 次
- 自我反思循环：生成→评估→修正，直到质量达标

## 二、功能需求

### 2.1 LoopNode 核心功能

1. **基本循环**
   - 支持配置最大迭代次数（max_iterations）
   - 支持配置循环名称（name），用于状态管理
   - 循环体可包含任意子图（SubGraph）

2. **迭代状态管理**
   - 每次迭代可访问上一轮的状态
   - 支持在状态中记录迭代次数
   - 迭代间可传递消息

3. **终止条件**
   - 条件函数式终止（ConditionFunc）
   - 计数器终止（max_iterations）
   - 用户中断支持（context.Context）

### 2.2 API 设计

```go
// LoopNode 结构
type LoopNode struct {
    name           string
    maxIterations  int
    body           Graph
    condition      func(ctx Context, state map[string]interface{}) bool
    options        []LoopOption
}

// LoopOption 配置选项
type LoopOption func(*LoopNode)

// 创建 LoopNode
func NewLoop(name string, body Graph, options ...LoopOption) *LoopNode

// 配置最大迭代次数
func WithMaxIterations(n int) LoopOption

// 配置终止条件
func WithCondition(cond func(ctx Context, state map[string]interface{}) bool) LoopOption

// 执行循环
func (l *LoopNode) Invoke(ctx context.Context, input map[string]interface{}) (map[string]interface{}, error)
func (l *LoopNode) Stream(ctx context.Context, input map[string]interface{}) (<-chan StreamEvent, error)
```

### 2.3 使用示例

```go
// 示例 1: 简单循环
loop := compose.NewLoop("search_loop", searchSubgraph,
    compose.WithMaxIterations(5),
    compose.WithCondition(func(ctx compose.Context, state map[string]interface{}) bool {
        return state["found"] == true
    }),
)

// 示例 2: 工具调用重试
retryLoop := compose.NewLoop("tool_retry", toolCallGraph,
    compose.WithMaxIterations(3),
    compose.WithCondition(func(ctx compose.Context, state map[string]interface{}) bool {
        return state["success"] == true
    }),
)
```

## 三、非功能需求

1. **性能**
   - 循环开销不超过串行执行的 10%
   - 支持并发循环（可选）

2. **错误处理**
   - 循环内部错误应向上抛出
   - 超时控制通过 context 实现
   - 无限循环保护（max_iterations 兜底）

3. **可观测性**
   - 每次迭代触发 Callback
   - 记录迭代次数到状态
   - 支持诊断信息输出

## 四、交付物

1. `compose/loop_node.go` — LoopNode 核心实现
2. `compose/loop_node_test.go` — 单元测试
3. `compose/loop_example_test.go` — 使用示例
4. `doc.go` — 文档更新

## 五、验收标准

1. 单元测试覆盖率 ≥ 80%
2. 所有现有测试通过
3. 示例代码可运行
4. 文档完整

## 六、风险与依赖

| 风险 | 应对 |
|------|------|
| 循环可能导致状态爆炸 | 限制状态大小，提供清理接口 |
| 与现有 Graph 系统集成复杂度 | 复用现有 Invoke/Stream 接口 |
| 测试用例覆盖不足 | 增加边界条件测试 |
