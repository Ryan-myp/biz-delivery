# biz-delivery 研发流程 Skill 架构

> 定位：从 PRD 到测试用例的**研发流程 Skill 标准化系统**

---

## 一、Skill 体系总览

```
PRD → [Review Skill] → TD Skill → [Task Planning Skill] → Agent → [Test Case Skill] → [Automated Testing Skill]
```

| 阶段 | Skill 名称 | 输入 | 输出 | 状态 |
|------|-----------|------|------|------|
| 1 | **PRD Review Skill** | PRD 文档 | 问题清单 | ✅ 已实现 |
| 2 | **TD Skill** | PRD + Review 结果 | 技术方案 | ✅ 已实现 |
| 3 | **Task Planning Skill** | TD | 执行计划 | ✅ 已实现 |
| 4 | **Agent Execution Skill** | 执行计划 | 代码 | ⚠️ 待完善 |
| 5 | **Test Case Skill** | PRD + TD | 测试用例 | ✅ 已实现 |
| 6 | **Automated Testing Skill** | 代码 + Test Case | 测试结果 | ⚠️ 待完善 |

---

## 二、各 Skill 详细设计

### 2.1 PRD Review Skill（PRD 审查）

**职责**：自主发现 PRD 中的问题

**输入**：
- PRD 文档（Markdown）
- 业务 Profile（领域规则）

**输出**：
- 问题清单（P0/P1/P2）
- 风险评级
- 改进建议

**实现**：
```python
# scripts/review_engine.py
class ReviewEngine(EngineBase):
    """PRD 审查引擎"""
    
    CHECKS = {
        "completeness": "需求完整性检查",
        "consistency": "需求一致性检查",
        "feasibility": "技术可行性检查",
        "testability": "可测试性检查",
        # ... 共 17 类检查项
    }
```

**Hook 支持**：
- `hooks/fetch_prd.py` - PRD 获取
- `hooks/validate.py` - 审查校验
- `hooks/post_review.py` - 后处理（风险评级、摘要生成）

---

### 2.2 TD Skill（技术方案生成）

**职责**：根据 PRD 生成技术方案

**输入**：
- PRD 文档
- Review 结果（问题清单）
- 历史方案库（避免重复）

**输出**：
- 架构设计（Mermaid 图）
- 模块划分
- API 接口定义
- 数据模型
- 非功能需求（性能、安全）

**实现**：
```python
# scripts/td_engine.py
class TDEngine(EngineBase):
    """技术方案生成引擎"""
    
    def generate(self, prd_content, review_issues):
        """生成技术方案"""
        pass
```

**模板**：
- `templates/td.md.j2` - 技术方案模板

---

### 2.3 Task Planning Skill（任务规划）

**职责**：将技术方案分解为可执行的 Agent 任务

**输入**：
- 技术方案
- 代码库上下文

**输出**：
- 任务列表（优先级、依赖关系）
- 每个任务的描述
- 文件变更计划

**实现**：
```python
# scripts/agent/task_planner.py
class TaskPlanner:
    """任务规划器"""
    
    def plan(self, td_content, code_context):
        """生成执行计划"""
        pass
```

**Agent 提示词**：
- `scripts/agent/prompt_generator.py`
  - `generate_setup_prompt()` - 环境准备
  - `generate_impl_prompt()` - 代码实现
  - `generate_test_prompt()` - 测试编写

---

### 2.4 Agent Execution Skill（Agent 执行）

**职责**：执行任务计划，生成代码

**输入**：
- 任务列表
- 代码库上下文

**输出**：
- 生成的代码文件
- 编译/测试结果

**实现**：
```python
# scripts/agent/code_writer.py (待完善)
class CodeWriter:
    """代码生成器"""
    
    def write(self, task, context):
        """根据任务生成代码"""
        pass
```

**当前状态**：
- ✅ Prompt 生成完整
- ⚠️ 代码生成仅输出描述，未实现实际写入

---

### 2.5 Test Case Skill（测试用例生成）

**职责**：根据 PRD 和技术方案生成测试用例

**输入**：
- PRD 文档
- 技术方案
- 业务 Profile（测试维度配置）

**输出**：
- 测试用例列表（按优先级分类）
- 测试维度分析
- 覆盖率评估

**实现**：
```python
# scripts/test_engine.py
class TestEngine(EngineBase):
    """测试用例生成引擎"""
    
    def generate(self, prd_content, td_content):
        """生成测试用例"""
        pass
```

**Hook 支持**：
- `hooks/test_dimensions.py` - 按业务域定制测试维度

---

### 2.6 Automated Testing Skill（自动化测试）

**职责**：根据测试用例执行自动化测试

**输入**：
- 生成的代码
- 测试用例

**输出**：
- 测试结果
- 覆盖率报告
- 失败分析

**实现**：
```python
# scripts/automation.py
class AutomationPipeline:
    """自动化测试流水线"""
    
    def run(self, code_dir, test_cases):
        """执行自动化测试"""
        pass
```

**当前状态**：
- ✅ 编译检查、单元测试、集成测试框架完整
- ⚠️ 需要真实代码才能验证

---

## 三、Skill 调用链

```python
# 完整的 Skill 调用链
from skills import PRDReviewSkill, TDSkill, TaskPlanningSkill, AgentExecutionSkill, TestCaseSkill, AutomatedTestingSkill

# 1. PRD Review
review_result = PRDReviewSkill.run(prd_path)

# 2. Technical Design
td_result = TDSkill.run(prd_path, review_result)

# 3. Task Planning
tasks = TaskPlanningSkill.run(td_result)

# 4. Agent Execution（需要 LLM API Key）
code_result = AgentExecutionSkill.run(tasks)

# 5. Test Case Generation
test_cases = TestCaseSkill.run(prd_path, td_result)

# 6. Automated Testing
test_result = AutomatedTestingSkill.run(code_result, test_cases)
```

---

## 四、Profile 配置

每个 Skill 可以通过 Profile 配置自定义行为：

```json
{
  "language": "go",
  "review": {
    "checks": ["completeness", "consistency", "feasibility"],
    "strictness": "high"
  },
  "td": {
    "style": "microservice",
    "include_mermaid": true
  },
  "test": {
    "dimensions": ["unit", "integration", "e2e"],
    "coverage_threshold": 0.8
  }
}
```

---

## 五、扩展点

### 5.1 新增 Skill

```python
# skills/my_skill.py
class MySkill(SkillBase):
    """自定义 Skill"""
    
    def run(self, input_data):
        # 实现 Skill 逻辑
        pass
```

### 5.2 Hook 扩展

```python
# hooks/my_hook.py
def my_hook(context):
    """自定义 Hook"""
    pass
```

---

## 六、运行模式

### 6.1 全链路模式
```bash
python3 scripts/run_pipeline.py --mode full --prd prd/eino_loop_node_prd.md
```

### 6.2 单 Skill 模式
```bash
# 只运行 PRD Review
python3 scripts/run_pipeline.py --mode review --prd prd/eino_loop_node_prd.md

# 只生成技术方案
python3 scripts/run_pipeline.py --mode td --prd prd/eino_loop_node_prd.md

# 只生成测试用例
python3 scripts/run_pipeline.py --mode test --prd prd/eino_loop_node_prd.md
```

---

*架构设计完成，各 Skill 实现中...*
