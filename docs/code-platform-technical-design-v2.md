# Code Platform 技术方案 v2.0

> **核心理念**: 不只是Web化，而是构建一个**研发质量闭环系统**
> 
> **版本**: 2.0  
> **日期**: 2026-08-15  
> **作者**: biz-delivery Senior Expert Team

---

## 一、问题本质：为什么需要 Platform？

### 1.1 当前系统的三个断层

```
┌─────────────────────────────────────────────────────────────────┐
│                    当前命令行系统的问题                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   PRD → [Skill1] → [Skill2] → [Skill3] → [Skill4]              │
│                ↓           ↓           ↓           ↓            │
│              断点1        断点2        断点3        断点4        │
│                ↓           ↓           ↓           ↓            │
│              结果散落    结果散落    结果散落    结果散落        │
│                ↓                                                     │
│              无法串联 ❌    无法反馈 ❌    无法度量 ❌               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**核心问题**：
1. **流程断层**: 每个Skill独立运行，结果无法自动串联
2. **知识断层**: 历史审查结果没有积累，每次从头开始
3. **评估断层**: 不知道审查准确率，无法优化规则
4. **协作断层**: 单用户模式，团队经验无法共享

### 1.2 资深专家的判断

> "Web界面只是表象，真正的价值是构建**研发质量闭环**"

**闭环设计**：
```
PRD输入 → 智能审查 → 发现问题 → 修复验证 → 效果评估 → 规则优化
    ↑                                                        ↓
    └──────────────── 反馈学习 ←←←←←←←←←←←←←←←←←←←←←←←←←←←┘
```

---

## 二、架构设计：三层闭环系统

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Layer 4: 体验层 (Experience)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Web Dashboard│  │  CLI Tool   │  │  IDE Plugin  │              │
│  │  (React)     │  │  (Python)   │  │  (VSCode)    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
├─────────────────────────────────────────────────────────────────────┤
│                     Layer 3: 服务层 (Services)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ PipelineSvc  │  │ QualitySvc   │  │ KnowledgeSvc │              │
│  │ (流程编排)    │  │ (质量度量)    │  │ (知识管理)    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
├─────────────────────────────────────────────────────────────────────┤
│                     Layer 2: 引擎层 (Engines)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ ReviewEngine │  │ TDEngine     │  │ TestEngine   │              │
│  │ (审查引擎)    │  │ (设计引擎)    │  │ (测试引擎)    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ReviewEngine  │  │ CodeEngine   │  │ LearnEngine  │              │
│  │v2(专家规则)   │  │ (代码分析)    │  │ (知识学习)    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
├─────────────────────────────────────────────────────────────────────┤
│                     Layer 1: 数据层 (Data)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  PipelineDB  │  │ KnowledgeDB  │  │  FeedbackDB  │              │
│  │ (流程数据)    │  │ (知识数据)    │  │ (反馈数据)    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│  ┌──────────────┐                                                  │
│  │ Ryan KB      │  (1787篇专家文档)                                │
│  │ (只读)       │                                                  │
│  └──────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心创新：质量闭环

```
┌─────────────────────────────────────────────────────────────────────┐
│                         质量闭环设计                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│   │  PRD输入  │───▶│ 智能审查  │───▶│ 问题发现  │───▶│ 修复验证  │     │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘     │
│        ↑                                                  ↓         │
│        │                                          ┌──────────┐     │
│        │                                          │ 效果评估  │     │
│        │                                          └──────────┘     │
│        │                                                  ↓         │
│        │                                          ┌──────────┐     │
│        │                                          │ 规则优化  │     │
│        │                                          └──────────┘     │
│        │                                                  ↓         │
│        └──────────────────────────────────────────────────┘         │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  关键指标:                                                           │
│  - 审查覆盖率: 发现的问题 / 实际存在的问题                            │
│  - 误报率: 误报问题 / 总发现问题                                     │
│  - 修复率: 已修复问题 / 发现问题总数                                  │
│  - 规则优化: 每月新增/优化规则数                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 三、核心模块设计

### 3.1 Pipeline Orchestrator（流程编排器）

**设计目标**: 解决流程断层问题

```python
class PipelineOrchestrator:
    """
    Pipeline编排器 - 串联所有Skill，实现端到端自动化
    
    核心能力:
    1. 串行/并行执行多个Skill
    2. 支持条件分支 (如果P0=0则继续，否则阻塞)
    3. 失败重试和降级策略
    4. 进度实时推送
    """
    
    def __init__(self, pipeline_config: dict):
        self.config = pipeline_config
        self.stages = self._parse_stages()
        self.feedback_loop = FeedbackLoop()
    
    async def execute(self, context: PipelineContext) -> PipelineResult:
        """执行Pipeline"""
        result = PipelineResult(pipeline_id=context.pipeline_id)
        
        for stage in self.stages:
            # 1. 执行Stage
            stage_result = await self._execute_stage(stage, context)
            
            # 2. 检查质量门禁
            if not self._check_quality_gate(stage_result):
                result.blocked = True
                result.block_reason = f"{stage.name} 未通过质量门禁"
                break
            
            # 3. 更新上下文
            context = context.merge(stage_result)
            
            # 4. 记录反馈
            self.feedback_loop.record(stage.name, stage_result)
            
            result.add_stage(stage.name, stage_result)
        
        return result
    
    def _check_quality_gate(self, result: StageResult) -> bool:
        """质量门禁检查"""
        # P0问题必须为0才能继续
        if result.p0_count > 0:
            return False
        # 或者自定义质量规则
        return self.config.get("quality_gate", {}).get("allow_p0", False)
```

**Pipeline配置示例**:
```json
{
  "name": "full-review",
  "stages": [
    {
      "name": "prd_review",
      "skill": "prd_review_v2",
      "config": {"expert_rules": true},
      "quality_gate": {"max_p0": 0, "max_p1": 5}
    },
    {
      "name": "technical_design",
      "skill": "td_v2",
      "depends_on": ["prd_review"],
      "condition": "prd_review.p0_count == 0"
    },
    {
      "name": "test_generation",
      "skill": "test_case_v2",
      "depends_on": ["technical_design"]
    },
    {
      "name": "code_review",
      "skill": "code_review",
      "parallel": true,
      "depends_on": ["test_generation"]
    }
  ],
  "feedback": {
    "enabled": true,
    "learning_rate": 0.1
  }
}
```

### 3.2 Feedback Loop（反馈学习系统）

**设计目标**: 解决评估断层问题

```python
class FeedbackLoop:
    """
    反馈学习系统 - 从历史数据中学习，持续优化规则
    
    核心能力:
    1. 收集人工反馈 (正确/错误/忽略)
    2. 计算规则准确率
    3. 自动调整规则阈值
    4. 推荐规则优化建议
    """
    
    def __init__(self, db: FeedbackDB):
        self.db = db
        self.rule_stats = RuleStatistics()
    
    def record_feedback(self, feedback: FeedbackRecord):
        """记录用户反馈"""
        self.db.insert(feedback)
        self.rule_stats.update(feedback.rule_name, feedback.is_correct)
    
    def get_rule_performance(self, rule_name: str) -> dict:
        """获取规则性能指标"""
        return {
            "precision": self.rule_stats.precision(rule_name),
            "recall": self.rule_stats.recall(rule_name),
            "f1": self.rule_stats.f1_score(rule_name),
            "trend": self.rule_stats.trend(rule_name, days=30)
        }
    
    def optimize_rules(self) -> List[RuleSuggestion]:
        """生成规则优化建议"""
        suggestions = []
        
        # 低准确率规则建议
        for rule in self.rule_stats.get_low_precision_rules(threshold=0.5):
            suggestions.append(RuleSuggestion(
                rule_name=rule.name,
                action="adjust_threshold",
                reason=f"准确率仅 {rule.precision:.1%}",
                confidence=0.8
            ))
        
        # 高误报规则建议
        for rule in self.rule_stats.get_high_false_positive_rules():
            suggestions.append(RuleSuggestion(
                rule_name=rule.name,
                action="refine_condition",
                reason=f"误报率 {rule.false_positive_rate:.1%}",
                confidence=0.7
            ))
        
        return suggestions
```

**反馈数据结构**:
```python
@dataclass
class FeedbackRecord:
    pipeline_id: str
    stage_name: str
    rule_name: str
    issue_id: str
    is_correct: bool      # 是否正确
    feedback_type: str    # correct/incorrect/ignore
    comment: str          # 用户备注
    timestamp: datetime
```

### 3.3 Quality Dashboard（质量仪表盘）

**设计目标**: 让质量可见、可度量、可优化

```
┌─────────────────────────────────────────────────────────────────────┐
│                        质量仪表盘                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │  审查覆盖率      │  │  问题修复率      │  │  规则准确率      │     │
│  │                 │  │                 │  │                 │     │
│  │     85%         │  │     92%         │  │     78%         │     │
│  │   ↑ 5% vs上月   │  │   ↑ 3% vs上月   │  │   ↓ 2% vs上月   │     │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘     │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    问题趋势图 (近30天)                        │   │
│  │                                                              │   │
│  │  P0 ████░░░░░░░░░░░░░░░░  12  ← 下降趋势 ✅                 │   │
│  │  P1 ████████░░░░░░░░░░  45  ← 稳定                          │   │
│  │  P2 ████████████░░░░░░  78  ← 上升趋势 ⚠️                   │   │
│  │                                                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐                          │
│  │  项目质量排名    │  │  规则优化建议    │                          │
│  │                 │  │                 │                          │
│  │  1. ad-platform │  │  • 调整规则X阈值 │                          │
│  │  2. eino        │  │  • 新增规则Y     │                          │
│  │  3. creative    │  │  • 优化规则Z描述 │                          │
│  └─────────────────┘  └─────────────────┘                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**关键指标定义**:
| 指标 | 定义 | 目标值 |
|------|------|--------|
| 审查覆盖率 | 被审查的PRD / 总PRD数 | > 90% |
| 问题发现率 | 发现问题数 / PRD总数 | > 5个/PRD |
| P0解决率 | 已解决P0 / 总P0 | > 95% |
| 规则准确率 | 正确判断 / 总判断 | > 80% |
| 修复效率 | 平均修复时间 | < 2天 |

### 3.4 Knowledge Graph（知识图谱）

**设计目标**: 解决知识断层问题

```
┌─────────────────────────────────────────────────────────────────────┐
│                       知识图谱架构                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────┐                                                │
│   │   PRD节点    │                                                │
│   │  (需求文档)  │                                                │
│   └──────┬───────┘                                                │
│          │ contains                                               │
│          ▼                                                         │
│   ┌──────────────┐    identifies    ┌──────────────┐              │
│   │  功能需求节点 │─────────────────▶│  问题节点     │              │
│   │  (功能描述)   │                 │ (P0/P1/P2)   │              │
│   └──────────────┘                 └──────┬───────┘              │
│                                           │ resolved_by            │
│                                           ▼                        │
│                                    ┌──────────────┐              │
│                                    │  解决方案节点 │              │
│                                    │ (修复建议)    │              │
│                                    └──────┬───────┘              │
│                                           │ references            │
│                                           ▼                        │
│   ┌──────────────┐                 ┌──────────────┐              │
│   │  代码节点     │◀────────────────│  知识库节点   │              │
│   │ (实现文件)    │                 │ (最佳实践)    │              │
│   └──────────────┘                 └──────────────┘              │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  知识来源:                                                          │
│  - Ryan KB: 1787篇专家文档                                         │
│  - 历史审查: 每次PRD审查的结果                                      │
│  - 反馈数据: 用户对规则的反馈                                        │
└─────────────────────────────────────────────────────────────────────┘
```

**图谱查询示例**:
```python
# 查询类似PRD的历史问题
query = """
MATCH (prd:PRD {id: $prd_id})
MATCH (prd)-[:contains]->(req:Requirement)
MATCH (req)-[:identifies]->(issue:Issue)
MATCH (issue)-[:resolved_by]->(solution:Solution)
MATCH (solution)-[:references]->(kb:Knowledge)
RETURN issue, solution, kb
"""

# 返回: 类似问题 + 解决方案 + 参考文档
```

---

## 四、技术选型与实现

### 4.1 后端技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| **API框架** | FastAPI | 异步支持好，自动生成API文档 |
| **ORM** | SQLAlchemy 2.0 | 成熟稳定，支持异步 |
| **任务队列** | Celery + Redis | 可靠的任务调度，支持重试 |
| **实时通信** | WebSocket (FastAPI) | 进度推送，无需额外组件 |
| **认证** | JWT + OAuth2 | 标准方案，易于集成 |
| **搜索** | Elasticsearch | 知识检索，支持全文搜索 |

### 4.2 前端技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| **框架** | React 18 + TypeScript | 类型安全，生态成熟 |
| **UI库** | Ant Design Pro | 企业级组件，开箱即用 |
| **状态管理** | Zustand | 轻量级，适合中大型应用 |
| **图表** | ECharts | 功能强大，国内首选 |
| **编辑器** | Monaco Editor | VSCode同款，PRD编辑体验好 |
| **实时通信** | WebSocket + SWR | 自动重连，缓存管理 |

### 4.3 数据库设计

```sql
-- 项目表
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    language TEXT NOT NULL,
    framework TEXT,
    repo_path TEXT,
    profile JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pipeline表
CREATE TABLE pipelines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    prd_content TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    result JSONB,
    quality_score DECIMAL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Stage表
CREATE TABLE stages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id UUID REFERENCES pipelines(id),
    name TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    result JSONB,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- 反馈表
CREATE TABLE feedbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id UUID REFERENCES pipelines(id),
    stage_name TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    issue_id TEXT,
    is_correct BOOLEAN,
    feedback_type TEXT,
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 知识图谱节点表
CREATE TABLE knowledge_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL,  -- prd/requirement/issue/solution/knowledge
    content JSONB,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 知识图谱边表
CREATE TABLE knowledge_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES knowledge_nodes(id),
    target_id UUID REFERENCES knowledge_nodes(id),
    relation TEXT NOT NULL,
    confidence DECIMAL DEFAULT 1.0
);
```

---

## 五、核心API设计

### 5.1 Pipeline API

```typescript
// 创建Pipeline
POST /api/v1/pipelines
{
  "project_id": "uuid",
  "prd_content": "PRD文本",
  "stages": ["prd_review", "td", "test", "code_review"]
}

// 执行Pipeline
POST /api/v1/pipelines/{id}/execute

// 获取Pipeline进度
GET /api/v1/pipelines/{id}
// WebSocket: ws://host/ws/pipeline/{id}

// 获取阶段结果
GET /api/v1/pipelines/{id}/stages/{stage_name}

// 取消执行
POST /api/v1/pipelines/{id}/cancel
```

### 5.2 Feedback API

```typescript
// 提交反馈
POST /api/v1/pipelines/{id}/feedback
{
  "stage_name": "prd_review",
  "rule_name": "missing_title",
  "issue_id": "issue_123",
  "is_correct": true,
  "comment": "正确识别了缺少标题的问题"
}

// 获取规则性能
GET /api/v1/rules/{rule_name}/performance

// 获取优化建议
GET /api/v1/rules/optimize
```

### 5.3 Knowledge API

```typescript
// 搜索知识
GET /api/v1/knowledge/search?q=竞价系统&category=architecture

// 获取知识详情
GET /api/v1/knowledge/{doc_id}

// 查询相关知识图谱
GET /api/v1/knowledge/graph?node_id={node_id}
```

---

## 六、实施路线图

### Phase 1: 核心闭环 (4周)

| 周 | 任务 | 交付物 |
|----|------|--------|
| W1 | Pipeline Orchestrator 实现 | 可串联执行的Pipeline引擎 |
| W2 | Feedback Loop 实现 | 反馈收集和规则统计 |
| W3 | 基础Web界面 | 项目/Pipeline CRUD |
| W4 | 集成测试和优化 | 端到端可用 |

**Phase 1 目标**: 实现"PRD输入 → 自动审查 → 结果输出"的完整闭环

### Phase 2: 智能化 (4周)

| 周 | 任务 | 交付物 |
|----|------|--------|
| W5 | 质量仪表盘 | 可视化质量指标 |
| W6 | 知识图谱 | 问题-解决方案关联 |
| W7 | 规则自动优化 | 基于反馈调整阈值 |
| W8 | 团队功能 | 多用户/权限 |

**Phase 2 目标**: 实现"审查 → 反馈 → 优化"的智能闭环

### Phase 3: 生态化 (4周)

| 周 | 任务 | 交付物 |
|----|------|--------|
| W9 | IDE插件 | VSCode插件 |
| W10 | CLI增强 | 命令行交互优化 |
| W11 | API开放 | 第三方集成 |
| W12 | 文档和培训 | 使用手册 |

**Phase 3 目标**: 构建"平台 + 工具 + 生态"的完整体系

---

## 七、风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|----------|
| 反馈收集率低 | 无法优化规则 | 设计轻量的反馈入口 (一键按钮) |
| 知识图谱复杂度高 | 维护困难 | 分阶段构建，先核心后扩展 |
| 实时进度推送延迟 | 用户体验差 | WebSocket + 轮询降级 |
| 并发执行冲突 | 数据不一致 | 分布式锁 + 乐观锁 |

---

## 八、成功指标

| 指标 | Phase 1 | Phase 2 | Phase 3 |
|------|---------|---------|---------|
| Pipeline执行成功率 | > 90% | > 95% | > 98% |
| 规则准确率 | 基准 | > 80% | > 85% |
| 用户满意度 | > 3/5 | > 4/5 | > 4.5/5 |
| 反馈收集率 | > 30% | > 50% | > 70% |
| 审查覆盖率 | > 50% | > 80% | > 95% |

---

## 附录

### A. 技术栈版本

```
Python: 3.11+
FastAPI: 0.100+
SQLAlchemy: 2.0+
React: 18+
TypeScript: 5+
Ant Design: 5+
Celery: 5+
Redis: 7+
PostgreSQL: 15+
Elasticsearch: 8+
```

### B. 参考资源

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Ant Design Pro 文档](https://pro.ant.design/)
- [Celery 官方文档](https://docs.celeryproject.org/)
- [Ryan Personal KB](/Users/yanping.ma/ryan-personal-knowledge/)
