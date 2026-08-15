# PRD: Eino 智能代码审查 Agent 系统

## 一、需求背景与目标

### 1.1 业务背景

随着软件工程复杂度提升，代码审查已成为保障代码质量的关键环节。传统 Code Review 存在以下痛点：
- **人工审查效率低**：资深工程师时间宝贵，难以覆盖所有 PR
- **标准不统一**：不同 reviewer 关注点不同，审查质量参差不齐
- **重复性工作多**：格式、命名、基础安全等问题重复出现

本 PRD 旨在设计并实现一个基于 **Eino 框架** 的智能代码审查 Agent 系统，通过 LLM 自动化完成代码审查，提升效率与一致性。

### 1.2 业务目标与背景

| 目标 | 指标 | 期限 |
|------|------|------|
| 自动化率 | 80% 常规问题自动识别 | v1.0 (M1) |
| 准确率 | 误报率 < 15%，漏报率 < 10% | v1.0 (M1) |
| 性能 | 单次审查 < 30s（1000行以内） | v1.0 (M1) |
| 覆盖率 | 支持 Go/Python/Java 三种语言 | v1.1 (M2) |

### 1.3 用户画像

- **开发者**：提交代码后自动获得审查反馈
- **Tech Lead**：配置审查规则，查看团队代码质量趋势
- **QA**：追溯历史审查记录，定位高频问题类型

---

## 二、需求描述

### 2.1 核心功能

#### F1: 代码解析与提取
- 支持解析 Go/Python/Java 源码
- 提取函数签名、类型定义、导入依赖
- 构建代码 AST（抽象语法树）用于深度分析

#### F2: 智能审查
- **基础检查**：命名规范、代码格式、注释完整性
- **安全扫描**：SQL 注入、XSS、硬编码密钥
- **性能审查**：N+1 查询、内存泄漏、不当并发
- **架构审查**：依赖倒置、循环依赖、单点故障

#### F3: 智能体编排
- **主 Agent**：协调整体审查流程
- **子 Agent**：
  - SecurityAgent：专注安全漏洞检测
  - PerformanceAgent：专注性能问题
  - CodeStyleAgent：专注代码风格
  - ArchAgent：专注架构问题
- 支持子 Agent 协作与结果合并

#### F4: 报告生成
- Markdown 格式审查报告
- 问题分级（Critical/Warning/Info）
- 修复建议与代码示例
- 可配置报告模板

#### F5: 流式输出
- SSE 推送实时审查进度
- 增量显示已发现问题
- 支持中断与恢复

### 2.2 API 设计

```go
// 审查服务接口
type ReviewService interface {
    // 异步审查，返回任务ID
    ReviewAsync(ctx context.Context, req *ReviewRequest) (string, error)
    
    // 同步审查，流式返回结果
    ReviewStream(ctx context.Context, req *ReviewRequest) (<-chan *ReviewEvent, error)
    
    // 查询审查结果
    GetResult(ctx context.Context, taskID string) (*ReviewResult, error)
}

// 请求结构
type ReviewRequest struct {
    RepoURL       string           // 仓库地址
    Branch        string           // 分支名
    PRNumber      int              // PR 编号
    Languages     []string         // 目标语言
    Config        ReviewConfig     // 审查配置
}

// 审查结果
type ReviewResult struct {
    TaskID      string           // 任务ID
    Status      string           // pending/completed/failed
    Issues      []Issue          // 发现的问题
    Summary     ReviewSummary    // 总结
    CreatedAt   time.Time        // 创建时间
    CompletedAt *time.Time       // 完成时间
}

// 单个问题
type Issue struct {
    ID        string   // 问题ID
    Severity  string   // critical/warning/info
    Category  string   // security/performance/style/architecture
    File      string   // 文件名
    Line      int      // 行号
    Message   string   // 问题描述
    Suggestion string  // 修复建议
    Code      string   // 问题代码片段
}
```

---

## 三、技术方案

### 3.1 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 框架 | CloudWeGo Eino | Go LLM 应用开发框架 |
| LLM | GPT-4o / Claude 3.5 Sonnet | 代码理解能力最强 |
| 向量数据库 | Milvus | 代码片段相似度检索 |
| 缓存 | Redis | 审查结果缓存、任务队列 |
| 消息队列 | Kafka | 异步任务分发 |
| 前端 | Vue 3 + TypeScript | 审查报告可视化 |

### 3.2 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend (Vue 3)                    │
│                    审查报告展示 + 配置管理                  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                     API Gateway (Gin)                    │
│                   HTTP/WebSocket 接入层                   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   Review Service                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Main Agent│  │ Security │  │Performance│              │
│  │ (Eino)   │←→│  Agent   │←→│  Agent   │              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
│       │             │             │                      │
│  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐              │
│  │CodeStyle │  │  Arch    │  │ LLM API  │              │
│  │  Agent   │  │  Agent   │  │(OpenAI/  │              │
│  └────┬─────┘  └────┬─────┘  │ Claude)  │              │
│       │             │         └────┬─────┘              │
│  ┌────▼─────────────▼─────────▼─────┐                  │
│  │         Code Parser              │                  │
│  │  (astx/gopls/tree-sitter)        │                  │
│  └──────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │   Redis    │  │   Kafka    │  │  Milvus    │
   │   缓存      │  │   任务队列  │  │  向量检索   │
   └────────────┘  └────────────┘  └────────────┘
```

### 3.3 Eino 编排设计

#### 3.3.1 Graph 定义

```go
// 主审查流程图
graph := compose.NewGraph[*ReviewRequest, *ReviewResult]()

// 节点定义
graph.AddLambdaNode("parse", parseCodeNode)
graph.AddChatModelNode("security_check", securityModel)
graph.AddChatModelNode("performance_check", performanceModel)
graph.AddChatModelNode("style_check", styleModel)
graph.AddChatModelNode("architecture_check", archModel)
graph.AddLambdaNode("merge_results", mergeResultsNode)
graph.AddLambdaNode("generate_report", generateReportNode)

// 边定义（并行执行检查）
graph.AddEdge(compose.START, "parse")
graph.AddEdge("parse", "security_check")
graph.AddEdge("parse", "performance_check")
graph.AddEdge("parse", "style_check")
graph.AddEdge("parse", "architecture_check")

// 并行汇聚
graph.AddEdge("security_check", "merge_results")
graph.AddEdge("performance_check", "merge_results")
graph.AddEdge("style_check", "merge_results")
graph.AddEdge("architecture_check", "merge_results")
graph.AddEdge("merge_results", "generate_report")
graph.AddEdge("generate_report", compose.END)
```

#### 3.3.2 Agent 实现

```go
// 安全审查 Agent
securityAgent, _ := adk.NewChatModelAgent(ctx, &adk.ChatModelAgentConfig{
    Model: securityModel,
    Instructions: `你是一个代码安全专家。请检查代码中的：
1. SQL 注入风险
2. XSS 攻击向量
3. 硬编码密钥或密码
4. 不安全的加密算法
5. 路径遍历漏洞`,
})

// 主 Agent 编排
mainAgent, _ := adk.NewDeepAgent(ctx, &deep.Config{
    ChatModel: mainModel,
    SubAgents: []adk.Agent{
        securityAgent,
        performanceAgent,
        styleAgent,
        archAgent,
    },
    ToolsConfig: adk.ToolsConfig{
        ToolsNodeConfig: compose.ToolsNodeConfig{
            Tools: []tool.BaseTool{codeParseTool, reviewTool},
        },
    },
})
```

### 3.4 数据模型

```sql
-- 审查任务表
CREATE TABLE review_tasks (
    id VARCHAR(36) PRIMARY KEY,
    repo_url VARCHAR(500) NOT NULL,
    branch VARCHAR(200),
    pr_number INT,
    status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
    config JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 审查问题表
CREATE TABLE review_issues (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(36) NOT NULL,
    severity ENUM('critical', 'warning', 'info'),
    category ENUM('security', 'performance', 'style', 'architecture'),
    file_path VARCHAR(500),
    line_number INT,
    message TEXT,
    suggestion TEXT,
    code_snippet TEXT,
    is_resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES review_tasks(id)
);

-- 审查结果摘要表
CREATE TABLE review_summaries (
    task_id VARCHAR(36) PRIMARY KEY,
    total_issues INT,
    critical_count INT,
    warning_count INT,
    info_count INT,
    summary_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 四、实施计划

### 4.1 实施计划与时间排期

| 阶段 | 任务 | 工期 | 交付物 |
|------|------|------|--------|
| M1 | 基础框架搭建 | 2周 | 项目骨架、Graph 定义、基础 Agent |
| M2 | 核心审查能力 | 3周 | 4类审查 Agent、流式输出、报告生成 |
| M3 | 集成测试 | 2周 | 端到端测试、准确率调优 |
| M4 | 生产部署 | 1周 | Docker 镜像、监控告警 |

### 4.2 技术依赖与前置条件

- [x] Eino 框架 v0.8+
- [ ] OpenAI API Key / Claude API Key
- [ ] Redis 7.0+
- [ ] Kafka 3.5+

### 4.3 回滚方案

如遇重大故障，执行以下回滚步骤：
1. 停止 Eino Agent 服务，回退至上一版本镜像
2. 恢复 Redis 缓存数据
3. 清理 Kafka 积压消息
4. 发布公告通知用户

---

## 五、风险评估

| 风险 | 等级 | 应对措施 |
|------|------|----------|
| LLM 调用成本超预期 | 高 | 设置 token 上限，启用缓存复用 |
| 审查准确率不足 | 中 | 持续优化 Prompt，引入人工反馈学习 |
| 大文件处理超时 | 中 | 分块处理，设置超时熔断 |
| 多语言 AST 解析不稳定 | 低 | 优先支持 Go，Java/Python 后续迭代 |
| API Key 泄露风险 | 高 | 使用 KMS 加密存储，禁用日志打印 |

### 5.1 性能要求

- **单次审查延迟**：< 30s（P95，1000行以内代码）
- **并发能力**：支持 100 个并发审查任务
- **吞吐量**：≥ 10 任务/分钟

### 5.2 安全考虑

- API Key 通过环境变量注入，禁止硬编码
- 审查结果仅对授权用户可见
- 支持 HTTPS 传输加密

---

## 六、验收标准与成功指标

| 指标 | 目标值 | 测量方式 |
|------|--------|----------|
| 审查自动化率 | ≥ 80% | 自动发现 / 总问题数 |
| 误报率 | < 15% | 人工复核误报比例 |
| 漏报率 | < 10% | 人工对比漏报比例 |
| 平均审查时间 | < 30s | 端到端耗时 P95 |
| 用户满意度 | ≥ 4.0/5.0 | 内部调查 |

---

## 七、附录

### 7.1 术语表

| 术语 | 说明 |
|------|------|
| Eino | CloudWeGo 的 Go LLM 应用开发框架 |
| ADK | Agent Development Kit，Eino 的智能体开发套件 |
| ReAct | Reasoning + Acting，智能体常用推理模式 |
| RAG | Retrieval Augmented Generation，检索增强生成 |
| AST | Abstract Syntax Tree，抽象语法树 |

### 7.2 参考资料

- [Eino 官方文档](https://www.cloudwego.io/zh/docs/eino/)
- [CloudWeGo 社区](https://www.cloudwego.io/)
- [代码审查最佳实践](https://landing.google.com/sre/book/chapters/code-review.html)
