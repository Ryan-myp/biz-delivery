# biz-delivery v3.0 — 智能业务交付框架

> 从 PRD 到自动化执行的完整端到端业务交付链路

---

## 一、架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                    biz-delivery v3.0                           │
│                     智能业务交付框架                            │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Layer 1      │   │  Layer 2      │   │  Layer 3      │
│  知识提取层    │──→│  引擎层        │──→│  Agent 执行层  │
│               │   │               │   │               │
│ • learn_repo  │   │ • review      │   │ • Setup Agent  │
│ • wiki_engine │   │ • td_engine   │   │ • Implement    │
│ • query/      │   │ • test_engine │   │ • Test Agent   │
│               │   │               │   │ • Review Agent │
│               │   │ • delivery    │   │               │
│               │   │   _pipeline   │   │ • automation   │
└───────────────┘   └───────────────┘   └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Layer 4      │   │  Layer 5      │   │  Layer 6      │
│  业务配置层    │   │  质量门禁层    │   │  输出层        │
│               │   │               │   │               │
│ • profiles/   │   │ • quality_gate│   │ • delivery/   │
│ • hooks/      │   │ • validator   │   │ • reports/    │
│               │   │               │   │ • artifacts/  │
└───────────────┘   └───────────────┘   └───────────────┘
```

---

## 二、完整交付链路

```
PRD → Review → TD → Agent Tasks → Implementation → Test → Quality Gate
  │       │       │        │             │           │          │
  ▼       ▼       ▼        ▼             ▼           ▼          ▼
 文本    报告     设计      任务列表      代码        用例       评分
                                   (Agent执行)   (自动生成)   (自动验证)
```

### 2.1 各阶段说明

| 阶段 | 输入 | 输出 | 说明 |
|------|------|------|------|
| **Learn** | 代码仓库 | IR 数据 | AST/CFG/DFG 分析，构建知识库 |
| **Review** | PRD + IR | 审查报告 | 识别遗漏、冲突、风险 |
| **TD** | PRD + Review | 技术方案 | 架构设计、接口定义、数据库设计 |
| **Tasks** | TD | Agent 任务列表 | 分解为可执行的开发任务 |
| **Agent** | Tasks + TD | 代码实现 | AI Agent 执行开发任务 |
| **Test** | PRD + TD | 测试用例 | 正向/异常/边界/安全测试 |
| **Automation** | 代码 | 执行结果 | 编译、测试、覆盖率验证 |
| **Quality** | 所有结果 | 质量报告 | 综合评分、阻塞项检测 |

---

## 三、核心组件

### 3.1 知识提取引擎

```python
# scripts/learn_repo.py
# 扫描代码，构建结构化 IR（Intermediate Representation）
from scripts.learn_repo import learn_from_repos

result = learn_from_repos(
    profile_path="profiles/my-service.json",
    output_dir="knowledge/my-service",
    wiki_path="wiki_engine/",
)
# 输出: IRDocument 包含 structs/functions/routes/call_graph/entity_tables 等
```

### 3.2 PRD 审查引擎

```python
# scripts/review_engine.py
# 基于 IR 审查 PRD 的合理性、完整性、风险
from scripts.review_engine import ReviewEngine

engine = ReviewEngine(profile, output_dir, wiki_path)
result = engine.review(prd_text)
# 输出: 审查报告（P0/P1/P2 问题列表）
```

**新增能力（v2.0）：**
- 跨模块影响分析（调用链推断）
- 字段级冲突检测（破坏性变更）
- 增量 IR 更新（文件级变更检测）
- 多仓库依赖追踪（RPC/MQ/HTTP）

### 3.3 技术方案生成引擎

```python
# scripts/td_engine.py
# 基于 PRD + 审查报告生成技术设计
from scripts.td_engine import TDEngine

engine = TDEngine(profile, output_dir, wiki_path)
result = engine.generate_td(prd_text, review_report)
# 输出: 技术方案（架构+接口+DB+流程图）
```

### 3.4 Agent 开发任务生成器

```python
# scripts/delivery_pipeline.py
# 将 TD 分解为 Agent 可执行的任务
from scripts.delivery_pipeline import AgentTaskGenerator

generator = AgentTaskGenerator(profile, ir_data)
tasks = generator.generate_tasks(td_content, review_report)
# 输出: List[AgentTask] 每个任务包含代码模板、验收标准
```

### 3.5 Agent 执行器

```python
# scripts/delivery_pipeline.py
# 执行 Agent 开发任务
from scripts.delivery_pipeline import AgentExecutor

executor = AgentExecutor(profile, output_dir)
result = executor.execute(tasks, llm_client)
# 输出: 执行结果（完成数、失败数、日志）
```

### 3.6 测试用例生成引擎

```python
# scripts/test_engine.py
# 基于 PRD + TD 生成测试用例
from scripts.test_engine import TestEngine

engine = TestEngine(profile, output_dir, wiki_path)
result = engine.generate_tests(prd_text, td_text)
# 输出: 测试用例（正向/异常/边界/安全）
```

### 3.7 自动化执行引擎

```python
# scripts/automation.py
# 执行编译、测试、覆盖率验证
from scripts.automation import run_automation

result = run_automation(
    work_dir="/path/to/repo",
    language="go",
    expected={"required_coverage": 0.7, "required_pass_rate": 0.9},
)
# 输出: 执行结果 + 质量评分
```

### 3.8 质量门禁

```python
# scripts/delivery_pipeline.py
# 评估整体交付质量
from scripts.delivery_pipeline import QualityGate

gate = QualityGate(profile, output_dir)
result = gate.evaluate(delivery_report)
# 输出: {score, passed, checks, blockers}
```

---

## 四、端到端使用

### 4.1 一键运行

```bash
python3 scripts/delivery_pipeline.py \
  --profile profiles/creative-platform.json \
  --prd prd.md \
  --output-dir delivery/my-feature \
  --stages learn,review,td,tasks,agent,test,automation,quality
```

### 4.2 分阶段运行

```bash
# 阶段 1: 知识提取
python3 scripts/delivery_pipeline.py \
  --profile profiles/my-service.json \
  --output-dir delivery/my-feature \
  --stages learn

# 阶段 2: PRD 审查
python3 scripts/delivery_pipeline.py \
  --profile profiles/my-service.json \
  --prd prd.md \
  --output-dir delivery/my-feature \
  --stages review

# 阶段 3: 技术方案生成
python3 scripts/delivery_pipeline.py \
  --profile profiles/my-service.json \
  --prd prd.md \
  --output-dir delivery/my-feature \
  --stages td

# 阶段 4: Agent 任务生成
python3 scripts/delivery_pipeline.py \
  --profile profiles/my-service.json \
  --prd prd.md \
  --output-dir delivery/my-feature \
  --stages tasks

# 阶段 5: Agent 执行
python3 scripts/delivery_pipeline.py \
  --profile profiles/my-service.json \
  --prd prd.md \
  --output-dir delivery/my-feature \
  --stages agent

# 阶段 6: 测试生成
python3 scripts/delivery_pipeline.py \
  --profile profiles/my-service.json \
  --prd prd.md \
  --output-dir delivery/my-feature \
  --stages test

# 阶段 7: 自动化执行
python3 scripts/automation.py \
  --work-dir delivery/my-feature \
  --language go

# 阶段 8: 质量门禁
python3 scripts/delivery_pipeline.py \
  --profile profiles/my-service.json \
  --prd prd.md \
  --output-dir delivery/my-feature \
  --stages quality
```

### 4.3 自动模式（全自动）

```bash
python3 scripts/run_pipeline.py \
  --profile profiles/my-service.json \
  --text "<PRD内容或文件路径>" \
  --output-dir delivery/my-feature \
  --mode auto
```

---

## 五、业务 Profile 配置

### 5.1 Profile 结构

```json
{
  "business_domain": "my-service",
  "language": "go",
  "repositories": [
    {
      "name": "my-service",
      "path": "/path/to/repo",
      "language": "go",
      "entry_keywords": ["handler", "service", "controller"],
      "exclude_patterns": ["test_*", "fixtures", "_test.go"]
    }
  ],
  "modules": [
    {"name": "AdGroup / 广告组", "keywords": ["adgroup", "广告组"]},
    {"name": "Creative / 素材", "keywords": ["creative", "素材", "review"]}
  ],
  "domain_terms": {
    "审核": "review",
    "发布": "publish",
    "下线": "offline"
  },
  "state_machines": {
    "Creative": {
      "states": ["DRAFT", "PENDING_APPROVAL", "APPROVED", "REJECTED", "LIVE"],
      "transitions": [
        {"from": "DRAFT", "to": "PENDING_APPROVAL", "action": "Submit"},
        {"from": "PENDING_APPROVAL", "to": "APPROVED", "action": "Approve"},
        {"from": "PENDING_APPROVAL", "to": "REJECTED", "action": "Reject"}
      ]
    }
  },
  "quality_gate": {
    "required_coverage": 0.7,
    "required_pass_rate": 0.9,
    "required_files": ["handler.go", "service.go", "dao.go"]
  }
}
```

### 5.2 Hooks 配置

```python
# hooks/fetch_prd.py — 获取 PRD
def fetch_prd(url, workspace_root):
    """从 Confluence/Wiki/本地文件获取 PRD"""
    ...

# hooks/map_terms.py — 术语映射
def map_terms(terms):
    """业务词 → 代码关键词"""
    return {"审核": "review", "发布": "publish"}

# hooks/validate.py — 业务校验
def validate(preview_result):
    """校验评审结果的业务完整性"""
    ...

# hooks/post_review.py — 评审后处理
def post_review(review_report):
    """提取关键词、生成摘要、风险评估"""
    ...

# hooks/test_dimensions.py — 业务测试维度
def get_test_dimensions():
    """返回业务专属测试维度"""
    return ["正向流程", "状态转换", "权限校验", "并发控制"]
```

---

## 六、Agent 任务格式

### 6.1 AgentTask 数据结构

```python
@dataclass
class AgentTask:
    id: str                              # 任务 ID (TASK-001)
    title: str                           # 任务标题
    description: str                     # 任务描述
    priority: TaskPriority               # 优先级 (P0/P1/P2)
    phase: AgentPhase                    # 阶段 (setup/implement/test/review)
    depends_on: List[str]                # 依赖的任务 ID
    files_to_create: List[str]           # 要创建的文件
    files_to_modify: List[str]           # 要修改的文件
    code_template: str                   # 代码模板（空壳）
    test_cases: List[str]                # 关联的测试用例
    acceptance_criteria: List[str]       # 验收标准
```

### 6.2 任务示例

```json
{
  "id": "TASK-001",
  "title": "[MODULE] AdGroup",
  "description": "实现 AdGroup 模块的业务逻辑",
  "priority": "P0",
  "phase": "implement",
  "depends_on": [],
  "files_to_create": [
    "internal/adgroup/adgroup.go",
    "internal/adgroup/handler.go",
    "internal/adgroup/service.go"
  ],
  "code_template": "package adgroup\n\n// AdGroupService 处理广告组业务\ntype AdGroupService struct {}",
  "test_cases": ["正常创建广告组", "参数校验失败", "权限不足"],
  "acceptance_criteria": [
    "✅ AdGroup 模块代码编译通过",
    "✅ 单元测试通过",
    "✅ 代码覆盖率 ≥ 70%"
  ]
}
```

---

## 七、质量门禁标准

### 7.1 检查项

| 检查项 | 标准 | 严重度 |
|--------|------|--------|
| PRD 审查 P0 问题 | 无 P0 问题 | Critical |
| TD 完整性 | 包含架构/接口/DB 设计 | High |
| Agent 任务完成率 | ≥ 80% | Critical |
| 测试覆盖率 | ≥ 70% | High |
| 测试通过率 | ≥ 90% | Critical |
| 编译成功 | 无编译错误 | Critical |

### 7.2 评分计算

```
总分 = Σ(通过的检查项) / 总检查项 × 100

质量门禁通过条件:
  - 总分 ≥ 80
  - 无 Critical 级别的检查失败
```

---

## 八、扩展指南

### 8.1 添加新的编程语言支持

在 `scripts/automation.py` 中添加新的语言实现：

```python
class BuildChecker:
    def check(self, target="."):
        if self.language == "go":
            command = "go build ./..."
        elif self.language == "python":
            command = "python3 -m py_compile ..."
        elif self.language == "java":
            command = "mvn compile"
        # 添加新语言...
```

### 8.2 添加新的业务域

1. 复制 `profiles/default.json` 并修改
2. 实现 `hooks/` 下的业务专属逻辑
3. 运行 `python3 scripts/init_profile.py --business-domain my-service`

### 8.3 自定义质量门禁

修改 Profile 中的 `quality_gate` 配置：

```json
{
  "quality_gate": {
    "required_coverage": 0.8,
    "required_pass_rate": 0.95,
    "required_files": ["handler.go", "service.go"]
  }
}
```

---

## 九、与 v2.0 的关系

| 特性 | v2.0 | v3.0 |
|------|------|------|
| PRD 审查 | ✅ | ✅ 增强 |
| 技术方案生成 | ✅ | ✅ 增强 |
| 测试用例生成 | ✅ | ✅ 增强 |
| Agent 任务生成 | ❌ | ✅ 新增 |
| Agent 执行 | ❌ | ✅ 新增 |
| 自动化执行 | ❌ | ✅ 新增 |
| 质量门禁 | 基础 | ✅ 增强 |

---

## 十、总结

biz-delivery v3.0 是一套**完整的智能业务交付框架**，覆盖：

1. **PRD Review** — 基于 IR 的智能审查
2. **Technical Design** — 自动生成技术方案
3. **Agent Tasks** — 分解为可执行任务
4. **Coding** — AI Agent 辅助开发
5. **Testing** — 自动生成测试用例
6. **Automation** — 编译、测试、覆盖率验证
7. **Quality Gate** — 综合质量评估

**核心价值：**
- 端到端自动化，减少人工干预
- 基于代码库 IR，避免凭空设计
- 业务差异通过 Profile + Hooks 配置
- 质量门禁确保交付物合格
