# Extension Guide

## 为新业务添加 Profile 和 Hook

### 1. 创建 Profile

复制并修改 `profiles/default.json`：

```bash
cp profiles/default.json profiles/my-service.json
```

编辑关键字段：
- `business_domain`: 业务标识
- `repositories`: 代码仓库路径
- `modules`: 业务模块定义
- `state_machines`: 状态机定义（如有）
- `business_rules`: 业务规则（错误码、约束等）

### 2. 实现 Hooks

#### 2.1 fetch_prd.py

定义如何获取 PRD：

```python
def fetch_prd(prd_input: str, workspace_root: str) -> str:
    """获取 PRD 内容"""
    # 从 Confluence、Wiki 或本地文件获取
    ...
```

#### 2.2 map_terms.py

定义业务术语映射：

```python
def map_terms(terms: Dict[str, str]) -> Dict[str, List[str]]:
    """业务术语 → 代码关键词"""
    # 例如：素材审核 → ["creative_review", "review_creative"]
    ...
```

#### 2.3 validate.py

定义审查结果的校验规则：

```python
def validate(review_result: dict, profile: dict) -> dict:
    """校验审查结果的业务完整性"""
    # 检查 P0 问题、状态机覆盖等
    ...
```

#### 2.4 post_review.py

定义审查后的处理逻辑：

```python
def post_review(review_result: dict, profile: dict) -> dict:
    """后处理审查结果"""
    # 提取关键词、生成摘要、评估风险
    ...
```

#### 2.5 test_dimensions.py

定义业务专属测试维度：

```python
def get_test_dimensions(profile: dict) -> List[TestDimension]:
    """获取测试维度"""
    # 例如：素材格式、渠道兼容、状态转换
    ...
```

### 3. 注册 Profile

```bash
python3 scripts/profile_registry.py --register profiles/my-service.json
```

### 4. 运行流水线

```bash
python3 scripts/run_pipeline.py \
  --profile profiles/my-service.json \
  --mode auto \
  --text "<PRD内容>" \
  --output-dir delivery/my-feature
```

## 自定义 LLM Prompt

修改各引擎中的 prompt 构建函数：

- `review_engine.py` → `_build_review_prompt()`
- `td_engine.py` → `_build_td_prompt()`
- `test_engine.py` → `_build_test_prompt()`

或使用 `llm_client.py` 中的辅助函数：

- `build_review_prompt()`
- `build_td_prompt()`
- `build_test_prompt()`

## 自定义知识库查询

修改 `query_evidence.py` 中的查询策略：

1. 添加自定义查询模式
2. 修改权重计算
3. 添加新的证据源

## 扩展 Point 说明

```
biz-delivery/
├── scripts/          ← 核心引擎（一般不需修改）
├── profiles/         ← 业务配置（按需修改）
├── hooks/            ← 业务差异（按需实现）
├── templates/        ← 输出模板（按需修改）
└── knowledge/        ← 知识库（自动生成）
```

**核心原则**：业务差异通过 Profile + Hooks 配置，不修改核心引擎。
