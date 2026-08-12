# biz-delivery 项目定位

> **核心定位：研发流程 Skill 标准化系统**

---

## 一、项目定位

biz-delivery 是一个**从 PRD 到测试用例的研发流程 Skill 标准化系统**。

### 1.1 核心理念

通过标准化的 **Skill**，将研发流程中的关键环节抽象为可复用、可组合的组件：

```
PRD → [Review Skill] → [TD Skill] → [Task Planning Skill] → Agent → [Test Case Skill] → [Automated Testing Skill]
```

### 1.2 六大核心 Skill

| 序号 | Skill 名称 | 职责 | 输入 | 输出 |
|------|-----------|------|------|------|
| 1 | **PRD Review Skill** | 自主发现 PRD 问题 | PRD 文档 | 问题清单（P0/P1/P2） |
| 2 | **TD Skill** | 根据 PRD 写技术方案 | PRD + Review 结果 | 技术方案 |
| 3 | **Task Planning Skill** | 生成执行计划 | 技术方案 | 任务列表 |
| 4 | **Agent Execution Skill** | 执行任务计划 | 任务列表 | 代码 |
| 5 | **Test Case Skill** | 生成测试用例 | PRD + TD | 测试用例 |
| 6 | **Automated Testing Skill** | 自动化测试 | 代码 + 用例 | 测试结果 |

---

## 二、核心价值

### 2.1 流程标准化

- ✅ 每个环节都有明确的输入/输出
- ✅ 支持单独运行或链式调用
- ✅ 可通过 Profile 配置自定义行为

### 2.2 能力复用

- ✅ Skill 可独立使用
- ✅ 支持 Hook 扩展
- ✅ 支持自定义 Profile

### 2.3 质量保障

- ✅ PRD 审查自动发现 P0 问题
- ✅ 技术方案模板化
- ✅ 测试用例自动生成
- ✅ 自动化测试验证

---

## 三、使用场景

### 3.1 典型工作流

```bash
# 1. 审查 PRD
python3 scripts/run_pipeline.py --mode review --prd prd/your_prd.md

# 2. 生成技术方案
python3 scripts/run_pipeline.py --mode td --prd prd/your_prd.md

# 3. 生成任务计划
python3 scripts/run_pipeline.py --mode plan --td delivery/your_td/td.md

# 4. 生成测试用例
python3 scripts/run_pipeline.py --mode test --prd prd/your_prd.md

# 5. 完整流程
python3 scripts/run_pipeline.py --mode full --prd prd/your_prd.md
```

### 3.2 适用场景

✅ **推荐使用**：
- 新需求 PRD 审查
- 技术方案模板化
- 测试用例批量生成
- 代码知识库构建

⚠️ **限制说明**：
- Agent 代码生成需要 LLM API Key
- 自动化测试需要真实代码
- 当前仅支持 Go/Python

---

## 四、技术架构

```
biz-delivery/
├── skills/                    # Skill 实现
│   ├── base.py               # Skill 基类
│   ├── prd_review/           # PRD 审查 Skill
│   ├── technical_design/     # 技术方案 Skill
│   ├── task_planning/        # 任务规划 Skill
│   ├── agent_execution/      # Agent 执行 Skill
│   ├── test_case/            # 测试用例 Skill
│   ├── automated_testing/    # 自动化测试 Skill
│   └── orchestrator.py       # Skill 编排器
├── scripts/                   # 核心引擎
│   ├── review_engine.py      # 审查引擎
│   ├── td_engine.py          # 技术方案引擎
│   ├── test_engine.py        # 测试用例引擎
│   ├── automation.py         # 自动化测试引擎
│   └── agent/                # Agent 模块
├── hooks/                     # Hook 扩展点
│   ├── fetch_prd.py
│   ├── validate.py
│   ├── post_review.py
│   └── test_dimensions.py
├── templates/                 # Jinja2 模板
│   ├── review_report.md.j2
│   ├── td.md.j2
│   └── test_cases.md.j2
└── profiles/                  # 业务 Profile
    └── index.json
```

---

## 五、扩展开发

### 5.1 自定义 Skill

```python
# skills/my_skill.py
from skills.base import SkillBase, SkillResult

class MySkill(SkillBase):
    """我的自定义 Skill"""
    
    REQUIRED_INPUT = ["input_data"]
    
    def run(self, input_data):
        # 实现 Skill 逻辑
        return SkillResult(
            success=True,
            output={"result": "value"}
        )
```

### 5.2 Hook 扩展

```python
# hooks/my_hook.py
def my_hook(context):
    """自定义 Hook"""
    # 在特定阶段执行自定义逻辑
    pass
```

---

## 六、与竞品的差异

| 维度 | biz-delivery | 传统工具 |
|------|-------------|---------|
| **定位** | 研发流程 Skill 标准化 | 单一环节工具 |
| **扩展性** | 高（Skill + Hook） | 低 |
| **可组合性** | 支持链式调用 | 不支持 |
| **配置化** | Profile + Hook | 硬编码 |

---

## 七、总结

**biz-delivery 是什么**：
> 一个将研发流程抽象为可复用 Skill 的标准化系统

**biz-delivery 不是什么**：
- ❌ 不是端到端交付框架
- ❌ 不是纯代码生成工具
- ❌ 不是完整的 DevOps 平台

**核心价值**：
> 通过 Skill 标准化，让 PRD 审查、技术方案、任务规划、测试用例生成等环节更加高效、可控、可追溯。

---

*最后更新：2026-08-12*
