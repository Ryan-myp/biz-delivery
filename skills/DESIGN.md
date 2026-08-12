# Skill 设计原则

> **Skill 是确定性、规则驱动的组件，不依赖 LLM**

---

## 一、设计原则

### 1.1 核心原则

```
Skill = 确定性逻辑 + 模板填充 + 规则检查
       ↑
    不依赖 LLM
```

### 1.2 与 LLM 的关系

| 层级 | 职责 | 是否依赖 LLM |
|------|------|-------------|
| **Skill 层** | 规则检查、模板填充、确定性逻辑 | ❌ 否 |
| **Agent 层** | 编排 Skill、必要时调用 LLM 增强 | ✅ 可选 |

### 1.3 为什么 Skill 不应依赖 LLM

1. **确定性**：相同输入产生相同输出，便于测试和调试
2. **可预测性**：行为可控，不会出现幻觉
3. **成本**：无需每次调用都消耗 API
4. **速度**：纯代码执行，无网络延迟
5. **离线可用**：无网络也能工作

---

## 二、Skill 实现模式

### 2.1 规则检查模式（Rule-Based）

适用于：PRD Review、质量门禁

```python
class PRDReviewSkill(SkillBase):
    """规则检查示例"""
    
    RULES = {
        "missing_title": {
            "pattern": r"^#\s+(.+)",
            "severity": "P0",
            "message": "PRD 应包含标题",
        },
        # ...
    }
    
    def run(self, input_data):
        # 纯规则检查，不依赖 LLM
        issues = self._check_rules(input_data["prd_content"])
        return SkillResult(success=len(p0_issues) == 0, output={...})
```

### 2.2 模板填充模式（Template-Based）

适用于：TD 生成、测试用例生成

```python
class TDSkill(SkillBase):
    """模板填充示例"""
    
    TEMPLATE = """
# 技术方案：{title}

## 架构设计
- 风格：{style}
- 模块：{modules}
"""
    
    def run(self, input_data):
        # 提取信息 → 填充模板
        info = self._extract_info(input_data["prd_content"])
        td_content = self.TEMPLATE.format(**info)
        return SkillResult(success=True, output={"td_content": td_content})
```

### 2.3 规则分解模式（Rule Decomposition）

适用于：Task Planning

```python
class TaskPlanningSkill(SkillBase):
    """规则分解示例"""
    
    TASK_TYPES = {
        "auth": {"priority": "P0", "type": "infrastructure"},
        "database": {"priority": "P0", "type": "infrastructure"},
        "api": {"priority": "P1", "type": "feature"},
        # ...
    }
    
    def run(self, input_data):
        # 基于规则生成任务
        tasks = self._generate_tasks(input_data["td_content"])
        return SkillResult(success=True, output={"tasks": tasks})
```

---

## 三、LLM 增强点

虽然 Skill 本身不依赖 LLM，但可以在以下场景选择性地调用 LLM：

### 3.1 Skill 输出后增强

```python
# Skill 生成基础输出
skill_result = prd_review_skill.run(prd_content)

# 可选：调用 LLM 增强
if need_llm_enhancement:
    enhanced = call_llm(skill_result.output, "请优化这个审查报告")
    skill_result.output = enhanced
```

### 3.2 Agent 编排层调用

```python
class AgentOrchestrator:
    """Agent 编排器"""
    
    def run(self, prd_path):
        # 1. 运行 Skill（确定性）
        review = PRDReviewSkill().run(prd)
        
        # 2. 必要时调用 LLM
        if review.has_issues():
            llm_advice = self.call_llm(f"针对这些问题，给出建议：{review.issues}")
        
        # 3. 继续运行后续 Skill
        td = TDSkill().run(prd, review)
        # ...
```

---

## 四、对比：旧架构 vs 新架构

### 4.1 旧架构（依赖 LLM）

```
PRD → [ReviewEngine] → Prompt → LLM → 报告
              ↑
         必须调用 LLM
```

**问题**：
- 无法离线使用
- 成本高
- 结果不确定

### 4.2 新架构（Skill 确定性）

```
PRD → [PRDReviewSkill] → 审查报告（确定性）
           ↑
        纯规则检查
```

**优势**：
- ✅ 离线可用
- ✅ 零成本
- ✅ 结果确定
- ✅ 易于测试

---

## 五、扩展指南

### 5.1 如何编写新 Skill

```python
# skills/my_skill.py
from .base import SkillBase, SkillResult

class MySkill(SkillBase):
    """我的 Skill 描述"""
    
    REQUIRED_INPUT = ["input_field"]
    
    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        # 1. 验证输入
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)
        
        # 2. 执行确定性逻辑
        result = self._process(input_data["input_field"])
        
        # 3. 返回结果
        return SkillResult(
            success=True,
            output={"result": result},
            metadata={"approach": "rule_based"}
        )
    
    def _process(self, data: str) -> str:
        """具体的处理逻辑"""
        # 纯 Python 代码，不调用 LLM
        return data.upper()
```

### 5.2 何时需要 LLM

| 场景 | 是否需要 LLM | 建议 |
|------|-------------|------|
| 规则检查 | ❌ | 纯 Skill |
| 模板填充 | ❌ | 纯 Skill |
| 代码理解 | ⚠️ | Skill + 可选 LLM |
| 创意生成 | ✅ | LLM 优先 |
| 复杂推理 | ✅ | LLM 优先 |

---

## 六、总结

**Skill 的核心价值**：
1. 确定性：相同输入 → 相同输出
2. 低成本：无需 API 调用
3. 可测试：单元测试覆盖
4. 可组合：Skill 链式调用

**LLM 的定位**：
- LLM 是可选的增强层
- 用于 Skill 无法处理的复杂场景
- 不在 Skill 层强制依赖

---

*设计原则确立于 2026-08-12*
