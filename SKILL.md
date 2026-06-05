---
name: biz-delivery
description: "通用业务交付框架：PRD评审→证据查询→TD→开发计划→测试用例。业务差异通过 Profile + Hooks 配置，不修改核心引擎。"
version: 0.1.0
author: ryan
platforms: [linux, macos]
metadata:
  hermes:
    tags: [delivery, prd-review, td, test-case, profile, hooks, generic]
---

# 通用业务交付框架

## 概述

一套通用的业务交付引擎，从 PRD 到测试用例的全链路自动化。

**核心原则：流程通用，业务通过 profile 和 hooks 扩展。**

## 快速开始

```bash
# 1. 初始化业务 Profile
python3 scripts/init_profile.py \
  --business-domain "my-service" \
  --repository "/path/to/repo" \
  --output profiles/my-service.json

# 2. 按需实现 Hooks（最少实现 fetch_prd.py）
# 编辑 hooks/fetch_prd.py — 定义如何获取 PRD
# 编辑 hooks/validate.py — 定义业务校验规则

# 3. 开始使用
python3 scripts/run_pipeline.py \
  --profile "profiles/my-service.json" \
  --text "<PRD内容>" \
  --output-dir delivery/my-feature
```

## 三层架构

```
┌─ Layer 1: 知识提取引擎 ───────────────────┐
│  (把代码/文档变成结构化知识)               │
│                                            │
│  AST Parser    — 语法结构提取              │
│  CFG Builder   — 控制流图                 │
│  DFG Analyzer  — 数据流分析               │
│  Flow Builder  — 业务流发现               │
└────────────────────────────────────────────┘
                     │ 结构化知识
                     ▼
┌─ Layer 2: 核心引擎 (scripts/) ────────────┐
│  query_evidence.py   — 通用证据查询        │
│  review_engine.py    — PRD评审引擎         │
│  td_engine.py        — TD生成引擎          │
│  test_engine.py      — 测试用例引擎        │
│  profile_registry.py — 业务Profile管理     │
│  benchmark.py        — 回归测试            │
└────────────────────────────────────────────┘
                     ▲
                     │ Profile 配置
┌─ Layer 3: 业务 Profile (profiles/) ────────┐
│  定义业务域：仓库路径、术语、证据源、规则    │
└────────────────────────────────────────────┘
                     ▲
                     │ 实现差异
┌─ Layer 4: 业务 Hook (hooks/) ──────────────┐
│  fetch_prd.py      — 如何获取 PRD          │
│  map_terms.py      — 业务术语映射          │
│  validate.py       — 业务校验规则          │
│  post_review.py    — 评审后处理            │
│  test_dimensions.py— 业务专属测试维度       │
└────────────────────────────────────────────┘
```

## 目录结构

```
biz-delivery/
├── SKILL.md                    # 本文件
├── scripts/
│   ├── _common.py              # 通用工具函数
│   ├── query_evidence.py       # 通用证据查询
│   ├── review_engine.py        # PRD评审引擎
│   ├── td_engine.py            # TD生成引擎
│   ├── test_engine.py          # 测试用例引擎
│   ├── run_pipeline.py         # 端到端流水线
│   ├── init_profile.py         # 初始化业务Profile
│   ├── profile_registry.py     # 业务Profile注册表
│   ├── benchmark.py            # 回归测试
│   ├── knowledge_extractor.py  # ★ 知识提取引擎 (AST/CFG/DFG/Flow)
│   ├── smart_routing.py        # ★ 意图识别 + 智能路由
│   ├── query_cache.py          # ★ 查询缓存
│   └── rrf_fusion.py           # ★ RRF 融合查询
├── profiles/
│   ├── default.json            # 默认配置
│   └── index.json              # 业务注册表
├── hooks/
│   ├── fetch_prd.py            # Hook: 获取PRD
│   ├── map_terms.py            # Hook: 术语映射
│   ├── validate.py             # Hook: 校验规则
│   ├── post_review.py          # Hook: 评审后处理
│   └── test_dimensions.py      # Hook: 测试维度
├── references/
│   ├── profile_schema.json     # Profile Schema定义
│   ├── extension_guide.md      # 扩展指南
│   ├── input_contract.md       # 输入契约
│   └── output_contract.md      # 输出契约
└── templates/
    ├── review_report.md.j2     # 评审报告模板
    ├── td.md.j2               # TD模板
    └── test_cases.md.j2       # 测试用例模板
```

## 业务 Profile 格式

```json
{
  "business_domain": "my-service",
  "repositories": [
    {
      "name": "my-service",
      "path": "/path/to/repo",
      "language": "python",
      "entry_keywords": ["handler", "service", "controller"],
      "exclude_patterns": ["test_*", "fixtures"]
    }
  ],
  "evidence_sources": ["code", "schema", "api_docs"],
  "domain_terms": {
    "术语1": "解释1",
    "术语2": "解释2"
  },
  "review_rules": {
    "must_check": ["正向流程", "异常处理", "权限控制"],
    "quality_gate": "needs_revision"
  },
  "test_dimensions": ["正向", "边界", "异常", "兼容"],
  "scenario_cards": "path/to/scenarios.json"
}
```

## 扩展点设计

### 实现 Hook 的步骤

1. **fetch_prd.py** (必需) — 定义如何获取 PRD
   ```python
   def fetch_prd(url, workspace_root):
       """从 Confluence/Wiki/本地文件获取 PRD"""
       ...
   ```

2. **map_terms.py** (可选) — 业务术语映射到代码关键词
   ```python
   def map_terms(terms):
       """业务词 → 代码关键词"""
       return {"审批": "approve", "发布": "publish"}
   ```

3. **validate.py** (可选) — 业务专属校验规则
   ```python
   def validate(preview_result):
       """校验评审结果的业务完整性"""
       ...
   ```

## 端到端流水线

```bash
# 完整链路：PRD → 评审 → TD → 开发计划 → 测试用例 → 自动化计划
python3 scripts/run_pipeline.py \
  --profile "profiles/my-service.json" \
  --text "<PRD内容或URL>" \
  --output-dir "delivery/my-feature" \
  --stages review,td,plan,test,automation
```

## 维护

- 与 ad-ai-coding/business-delivery 对比：本 skill 更通用，ad-ai-coding 是广告专用版本
- 业务接入指南: references/abstraction-process.md
## 与 ad-ai-coding 的关系

biz-delivery 从 ad-ai-coding 的业务-delivery skill 抽象而来：

| 维度 | ad-ai-coding | biz-delivery |
|------|-------------|--------------|
| 广告场景卡 | 内置 | Profile 配置 |
| Provider映射 | 内置 | Hooks 实现 |
| Confluence PRD | 内置 | fetch_prd.py Hook |
| 流程引擎 | 硬编码 | 通用脚本 |
| 新业务接入 | 修改脚本 | 新增 Profile + Hooks |

## 输出状态

所有结构化产物统一使用：
```
ready | needs_revision | blocked | partial | degraded | missing
```

## 常见错误

- 修改核心引擎而不是新增 Profile
- 把某个业务的 profile 术语当成通用规则
- 查询命中一个文件名就断言完整流程已实现
- 跳过证据直接从 PRD 生成 TD
- PRD 有 blocker 仍输出可直接编码的 handoff

## 参考文档

- `references/abstraction-process.md` — 从 ad-ai-coding 抽象为通用 skill 的完整流程
- `references/extension_guide.md` — 如何为新业务添加 Profile 和 Hook
