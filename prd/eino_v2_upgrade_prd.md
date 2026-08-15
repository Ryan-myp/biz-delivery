# PRD: Eino 框架 v2.0 升级迭代

## 一、需求背景

### 1.1 现状分析

Eino 当前版本（v0.8）存在以下问题：
- **42 个 deprecated API** 未清理，影响开发者体验
- **3 处 TODO** 未实现（checkpoint/batch resume/indirect edges）
- **adk 与 compose 耦合度高**，组件难以独立复用
- **流式处理测试覆盖不足**，stream_concat 仅 88 行
- **无官方 benchmark 数据**，性能无基准可参考

### 1.2 升级目标

| 目标 | 指标 | 优先级 |
|------|------|--------|
| 清理 deprecated API | 0 个遗留 | P0 |
| 实现 TODO 功能 | 3 项全部完成 | P0 |
| 解耦 adk/compose | 独立包引用通过 | P1 |
| 提升流式测试覆盖 | ≥ 90% | P1 |
| 添加 benchmark | 覆盖核心路径 | P2 |

---

## 二、功能需求

### 2.1 废弃 API 清理（P0）

**背景**: 当前存在 42 个 deprecated 声明，跨 6 个文件，影响新开发者学习曲线。

**需求**:
- F1.1: 移除所有 Deprecated 标记（保留迁移路径文档）
- F1.2: 更新所有内部调用点使用新 API
- F1.3: 提供 `eino-migrate` CLI 工具辅助迁移
- F1.4: 更新所有示例代码

**验收标准**:
- `go vet ./...` 无 deprecated 警告
- 所有测试用例通过
- 示例代码可运行

### 2.2 TODO 功能实现（P0）

#### F2.1: Checkpoint Batch Resume（compose/resume.go）

```go
// 当前状态: 单个 checkpoint resume 已支持
// 需求: 支持批量 resume，用于并发场景

func (w *Workflow) BatchResume(ctx context.Context, checkpoints []Checkpoint) error
```

**实现要点**:
- 支持并行恢复多个 workflow 实例
- 共享检查点状态隔离
- 错误回滚机制

#### F2.2: Indirect Edge Validation（compose/workflow.go）

```go
// 当前状态: 无验证
// 需求: 编译时检测间接边（A→B, B→C, 无 A→C 的短路路径）

func (g *Graph) ValidateIndirectEdges() error
```

**实现要点**:
- 构建依赖图检测回路
- 报告冗余边（transitive reduction）
- 编译阶段拦截

#### F2.3: Goroutine Error Tracing（compose/state_test.go）

```go
// 当前状态: stream 处理 goroutine 错误无法追踪
// 需求: 在 stream 协程中捕获并上报错误

func (s *Stream) WithErrorTracing() *Stream
```

**实现要点**:
- 使用 sync.ErrGroup 包装
- 错误信息包含 goroutine ID
- 自动附加上下文栈

### 2.3 架构解耦（P1）

**背景**: adk 直接 import compose，导致两者必须同步发布。

**需求**:
- F3.1: 提取 `compose/core` 子包（基础类型定义）
- F3.2: adk 改为引用 `compose/core`
- F3.3: compose 保持向后兼容

**验收标准**:
- `go build ./adk/...` 不依赖 `github.com/cloudwego/eino/compose`
- 现有测试全部通过

### 2.4 流式处理增强（P1）

**背景**: stream_concat.go 仅 88 行，测试覆盖不足。

**需求**:
- F4.1: 实现 `ConcatOption` 支持自定义拼接策略
- F4.2: 增加 `StreamCopy` 支持多订阅者
- F4.3: 测试覆盖提升至 ≥ 90%

### 2.5 Benchmark 体系（P2）

**需求**:
- F5.1: 添加 `compose/benchmark_test.go`
- F5.2: 覆盖 Graph Compile / Invoke / Stream 核心路径
- F5.3: CI 中集成 benchmark 回归检测

---

## 三、技术方案

### 3.1 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 语言 | Go 1.21+ | 保持与主版本一致 |
| 测试 | testify + benchstat | 单元测试 + 性能基准 |
| CI | GitHub Actions | 自动化回归 |
| 文档 | go doc + website | API 文档 |

### 3.2 模块划分

```
eino/
├── compose/
│   ├── core/          ← 新增：解耦后的核心类型
│   │   ├── graph.go
│   │   ├── runnable.go
│   │   └── types.go
│   ├── graph.go       ← 改为引用 core
│   ├── workflow.go
│   ├── resume.go      ← 新增 BatchResume
│   ├── validate.go    ← 新增 IndirectEdge 验证
│   └── stream.go      ← 增强流式处理
├── adk/
│   └── ...            ← 改为引用 compose/core
├── components/        ← 保持不变
└── schema/            ← 保持不变
```

### 3.3 关键设计

#### 3.3.1 BatchResume 接口

```go
type CheckpointBatch struct {
    Instances []CheckpointInstance
}

type CheckpointInstance struct {
    ID        string
    State     map[string]any
    Position  NodePosition
}

func (w *Workflow) BatchResume(ctx context.Context, batch CheckpointBatch) error {
    // 使用 errgroup 并行恢复
    g, ctx := errgroup.WithContext(ctx)
    for i := range batch.Instances {
        g.Go(func(idx int) error {
            return w.resumeSingle(ctx, batch.Instances[idx])
        })
    }
    return g.Wait()
}
```

#### 3.3.2 IndirectEdge 验证算法

```go
func validateIndirectEdges(g *Graph) error {
    // Floyd-Warshall 传递闭包
    reach := make(map[string]map[string]bool)
    // ... 构建可达性矩阵
    
    for from := range g.Nodes {
        for via := range g.Nodes {
            if from == via { continue }
            for to := range g.Nodes {
                if to == from || to == via { continue }
                // 如果 from→via 和 via→to 存在，但 from→to 不存在
                // 且 via 不是必经节点，则报告为间接边
                if reach[from][via] && reach[via][to] && !reach[from][to] {
                    // 合法情况，跳过
                } else if reach[from][via] && reach[via][to] && reach[from][to] {
                    // 存在间接边
                    return fmt.Errorf("indirect edge: %s -> %s -> %s", from, via, to)
                }
            }
        }
    }
    return nil
}
```

### 3.4 数据迁移方案

#### 3.4.1 Deprecated API 迁移映射

| 旧 API | 新 API | 迁移复杂度 |
|--------|--------|-----------|
| `RegisterSerializableType` | `schema.RegisterName[T]` | 低 |
| `InterruptAndRerun` | `InterruptContexts` | 中 |
| `Middlewares` (ChatModel) | `Handlers` (interface) | 高 |
| `Message.MultiContent` | `MessageInputPart.Extra` | 中 |

#### 3.4.2 CLI 工具设计

```bash
# 一键迁移
eino-migrate --from v0.8 --to v2.0 --path ./my-project

# 预览变更
eino-migrate --dry-run --path ./my-project

# 生成迁移报告
eino-migrate --report --path ./my-project
```

---

## 四、实施计划

### 4.1 里程碑

| 阶段 | 周期 | 交付物 | 负责人 |
|------|------|--------|--------|
| M1: API 清理 | 1周 | 移除 deprecated + 迁移工具 | Core Team |
| M2: TODO 实现 | 2周 | BatchResume + Validate + Tracing | Feature Team |
| M3: 架构解耦 | 1周 | compose/core 包 + 依赖调整 | Arch Team |
| M4: 流式增强 | 1周 | StreamCopy + 测试覆盖 | Test Team |
| M5: Benchmark | 0.5周 | 性能基准 + CI 集成 | Perf Team |
| M6: 发布 | 0.5周 | v2.0 release + 文档更新 | Release Team |

**总计**: 6 周

### 4.2 技术依赖

- [x] Go 1.21+ toolchain
- [x] GitHub Actions (CI)
- [ ] 需评审: `compose/core` 包边界定义
- [ ] 需评审: BatchResume 并发模型

---

## 五、风险评估

| 风险 | 等级 | 应对措施 |
|------|------|----------|
| deprecated API 影响存量用户 | 高 | 提供 6 个月过渡期 + 迁移工具 |
| BatchResume 并发竞态 | 中 | 充分测试 + 引入 race detector |
| 解耦后编译时间增加 | 低 | monorepo 内部包不影响外部 |
| benchmark 结果不稳定 | 低 | CI 中跑 3 次取平均 |

### 5.1 回滚方案

1. 新版本发布为 `eino/v2` 独立模块路径
2. 原有 v0.8 保持不变
3. 提供 `go get github.com/cloudwego/eino@v0.8` 回退

---

## 六、验收标准

| 指标 | 目标 | 测量方式 |
|------|------|----------|
| Deprecated API | 0 个 | `go vet ./...` |
| TODO 完成度 | 3/3 | issue 关闭 |
| 测试覆盖率 | ≥ 85% | `go test -cover` |
| 流式测试覆盖 | ≥ 90% | `go test -cover ./compose/...` |
| Benchmark 回归 | 无下降 | GitHub Actions |
| 迁移工具可用性 | 可用 | 人工验证 |

---

## 七、附录

### 7.1 术语表

| 术语 | 说明 |
|------|------|
| Checkpoint | 执行状态快照，用于中断恢复 |
| Indirect Edge | 可通过中间节点到达的冗余边 |
| Stream Concat | 多路流合并为单路输出 |
| Batch Resume | 同时恢复多个 workflow 实例 |

### 7.2 参考资料

- [Eino 官方文档](https://www.cloudwego.io/zh/docs/eino/)
- [Go errgroup 最佳实践](https://pkg.go.dev/golang.org/x/sync/errgroup)
- [Graph 传递闭包算法](https://en.wikipedia.org/wiki/Transitive_reduction)
