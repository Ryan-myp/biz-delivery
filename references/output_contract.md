# Output Contract

## 流水线输出结构

```
delivery/<feature-name>/
├── review_prompt.md       # PRD 审查 Prompt
├── review_report.md       # PRD 审查报告
├── td_prompt.md           # 技术方案 Prompt
├── technical_design.md    # 技术方案
├── test_prompt.md         # 测试用例 Prompt
└── test_cases.md          # 测试用例
```

## 输出状态

| 状态 | 含义 | 后续操作 |
|------|------|----------|
| `ready` | 可直接进入开发 | 无需额外操作 |
| `needs_revision` | 需要修订后重新审查 | 修改 PRD 后重新运行 |
| `blocked` | 存在阻塞性问题 | 必须解决 P0 问题 |
| `partial` | 部分完成 | 补充缺失内容 |
| `degraded` | 质量下降 | 检查知识库更新 |
| `missing` | 内容缺失 | 补充输入或配置 |

## Review Report 结构

```markdown
## 1. Overall Assessment
Status: [Pass | Needs Revision | Blocked]
Confidence: [High | Medium | Low]
Summary: ...

## 2. Critical Issues (P0)
- [P0] ...

## 3. Important Issues (P1)
- [P1] ...

## 4. Minor Issues (P2)
- [P2] ...

## 5. Section-by-Section Review
### 5.1 Correctness Check
...

### 5.2 Scenario Completeness
...

## 6. Recommendations
...
```

## Technical Design 结构

```markdown
## 1. Design Decision
Type: [Enhancement | New Feature | Hybrid]
Rationale: ...

## 2. Architecture Design
### 2.1 Module Structure
...

### 2.2 Component Diagram
```mermaid
...
```

## 3. Data Model Changes
...

## 4. API Design
...

## 5. Implementation Plan
...

## 6. Risk & Mitigation
...
```

## Test Cases 结构

```markdown
| TC# | Category | Priority | Title | Preconditions | Steps | Expected Result | Error Code |
|-----|----------|----------|-------|---------------|-------|-----------------|------------|
| TC001 | Positive | P0 | ... | ... | ... | ... | ... |
```

Categories: positive, exception, boundary, security, performance, compatibility
Priorities: P0 (core), P1 (important), P2 (nice-to-have)
