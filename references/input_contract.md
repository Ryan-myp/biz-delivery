# Input Contract

## PRD 输入格式

### 支持的输入类型
1. **文本内容** — 直接传入 PRD Markdown 文本
2. **文件路径** — 本地 `.md` 或 `.txt` 文件路径
3. **URL** — Confluence/Wiki 页面 URL（需实现 fetch_prd hook）

### PRD 内容要求
- 必须包含：功能描述、用户故事、验收标准
- 建议包含：上下文背景、非功能需求、风险评估

### 示例输入

```markdown
# 功能：广告组批量暂停

## 背景
当前广告组暂停操作仅支持单个操作，需要支持批量暂停。

## 用户故事
作为广告主，我希望能够批量暂停多个广告组，以提高操作效率。

## 验收标准
1. 支持选择多个广告组进行批量暂停
2. 批量操作应具有幂等性
3. 操作结果应实时反馈
```

## Profile 输入格式

参考 `references/profile_schema.json`

## Hook 输入/输出契约

### fetch_prd(prd_input, workspace_root) → str
- 输入：PRD URL 或路径
- 输出：PRD 文本内容

### map_terms(terms) → Dict[str, List[str]]
- 输入：业务术语字典
- 输出：代码关键词映射

### validate(review_result, profile) → dict
- 输入：审查结果 + Profile
- 输出：校验结果

### post_review(review_result, profile) → dict
- 输入：审查结果 + Profile
- 输出：处理后结果

### test_dimensions(profile) → List[TestDimension]
- 输入：Profile
- 输出：测试维度列表
