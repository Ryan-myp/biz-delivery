# biz-delivery 项目定位

> **核心定位：研发流程 Skill 标准化系统**

---

## 一、项目定位

biz-delivery 是一个**研发流程 Skill 标准化系统**。

通过**确定性、规则驱动**的 Skill，将 PRD 审查、技术方案生成、任务规划、测试用例生成等环节标准化。

---

## 二、Skill 架构

### 2.1 核心理念

```
Skill = 确定性逻辑 + 模板填充 + 规则检查
       ↑
    不依赖 LLM
```

### 2.2 六大核心 Skill

| 序号 | Skill | 实现方式 | 依赖 LLM |
|------|-------|---------|---------|
| 1 | **PRD Review Skill** | 规则检查 | ❌ |
| 2 | **TD Skill** | 模板填充 | ❌ |
| 3 | **Task Planning Skill** | 规则分解 | ❌ |
| 4 | **Agent Execution Skill** | 任务调度 | ⚠️ 可选 |
| 5 | **Test Case Skill** | 模板生成 | ❌ |
| 6 | **Automated Testing Skill** | 脚本执行 | ❌ |

### 2.3 Skill 特点

✅ **确定性**：相同输入产生相同输出  
✅ **可测试**：100% 单元测试覆盖  
✅ **低成本**：无需 API 调用  
✅ **可组合**：支持链式调用  

---

## 三、使用方式

### 3.1 单独运行 Skill

```bash
# 只运行 PRD Review
python3 -c "
from skills.prd_review import PRDReviewSkill
skill = PRDReviewSkill(profile={'language': 'go'})
result = skill.run({'prd_content': open('prd.md').read()})
print(result.output)
"

# 只生成技术方案
python3 -c "
from skills.technical_design import TDSkill
skill = TDSkill(profile={'language': 'go'})
result = skill.run({'prd_content': open('prd.md').read()})
print(result.output['td_content'])
"
```

### 3.2 Skill 链式调用

```bash
# 完整流水线
python3 scripts/run_pipeline.py --mode full --prd prd/your_prd.md

# 分阶段运行
python3 scripts/run_pipeline.py --mode review --prd prd/your_prd.md
python3 scripts/run_pipeline.py --mode td --prd prd/your_prd.md
python3 scripts/run_pipeline.py --mode plan --td delivery/your_td/td.md
python3 scripts/run_pipeline.py --mode test --prd prd/your_prd.md
```

---

## 四、扩展开发

### 4.1 自定义 Skill

```python
# skills/my_skill.py
from skills.base import SkillBase, SkillResult

class MySkill(SkillBase):
    """我的 Skill"""
    
    REQUIRED_INPUT = ["input_data"]
    
    def run(self, input_data):
        # 确定性逻辑
        result = self._process(input_data["input_data"])
        return SkillResult(success=True, output={"result": result})
    
    def _process(self, data):
        # 纯 Python 代码
        return data.upper()
```

### 4.2 Hook 扩展

```python
# hooks/my_hook.py
def my_hook(context):
    """在特定阶段执行自定义逻辑"""
    pass
```

---

## 五、价值主张

### 5.1 对比传统方案

| 维度 | 传统方案 | biz-delivery |
|------|---------|-------------|
| **确定性** | ❌ LLM 幻觉 | ✅ 纯规则 |
| **成本** | ❌ 每次 API 调用 | ✅ 零成本 |
| **可测试** | ❌ 难以测试 | ✅ 100% 覆盖 |
| **离线** | ❌ 需要网络 | ✅ 完全离线 |

### 5.2 适用场景

✅ **推荐使用**：
- PRD 快速审查
- 技术方案模板化
- 测试用例批量生成
- 任务计划自动生成

⚠️ **不适用**：
- 创意写作
- 复杂推理
- 开放性讨论

---

## 六、技术栈

- **语言**：Python 3.9+
- **测试**：pytest
- **模板**：Jinja2
- **编排**：SkillOrchestrator

---

*最后更新：2026-08-12*
