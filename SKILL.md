---
name: biz-delivery
description: "端到端智能业务交付框架：PRD审查→技术方案→Agent开发→测试生成→自动化执行。一套完整的从需求到交付的自动化流程。"
version: 3.0.0
author: ryan
platforms: [linux, macos]
metadata:
  hermes:
    tags: [delivery, prd-review, td, agent, test-case, automation, quality-gate, generic]
---

# biz-delivery v3.0 — 智能业务交付框架

## 概述

一套完整的端到端业务交付框架，从 PRD 到自动化执行的完整链路。

**核心原则：流程通用，业务通过 Profile + Hooks 配置扩展。**

## 完整交付链路

```
PRD → Review → TD → Agent Tasks → Implementation → Test → Automation → Quality Gate
 │       │       │         │             │            │          │            │
 ▼       ▼       ▼         ▼             ▼            ▼          ▼            ▼
文本    报告     设计       任务列表       代码        用例       执行结果     质量评分
                                    (AI Agent)   (自动生成)   (自动验证)
```

## 快速开始

### 1. 初始化业务 Profile

```bash
python3 scripts/init_profile.py \
  --business-domain "my-service" \
  --repository "/path/to/repo" \
  --output profiles/my-service.json
```

### 2. 实现 Hooks（按业务需求）

编辑 `hooks/` 下的文件：
- `fetch_prd.py` — 定义如何获取 PRD（Confluence/Wiki/本地文件）
- `map_terms.py` — 业务术语映射到代码关键词
- `validate.py` — 业务专属校验规则
- `post_review.py` — 评审后处理
- `test_dimensions.py` — 业务专属测试维度

### 3. 运行完整流水线

```bash
# 一键运行所有阶段
python3 scripts/delivery_pipeline.py \
  --profile "profiles/my-service.json" \
  --prd "prd.md" \
  --output-dir "delivery/my-feature" \
  --stages learn,review,td,tasks,agent,test,automation,quality
```

### 4. 运行部分阶段

```bash
# 仅运行 PRD 审查
python3 scripts/delivery_pipeline.py \
  --profile "profiles/my-service.json" \
  --prd "prd.md" \
  --output-dir "delivery/my-feature" \
  --stages review

# 仅运行自动化执行
python3 scripts/automation.py \
  --work-dir "delivery/my-feature" \
  --language go
```

## 目录结构

```
biz-delivery/
├── SKILL.md                    # 本文件
├── scripts/
│   ├── delivery_pipeline.py    # [v3.0] 端到端流水线
│   ├── automation.py           # [v3.0] 自动化执行引擎
│   ├── review_engine.py        # PRD 审查引擎
│   ├── td_engine.py            # 技术方案生成引擎
│   ├── test_engine.py          # 测试用例生成引擎
│   ├── learn_repo.py           # 知识提取引擎
│   ├── query/                  # 查询模块（v2.0 拆分）
│   │   ├── intent.py           # 意图识别
│   │   ├── fuzzy_match.py      # 模糊匹配
│   │   ├── synonym_expansion.py # 同义词扩展
│   │   ├── multi_path_query.py # 多路查询
│   │   ├── rrf_fusion.py       # RRF 融合
│   │   └── wiki_query.py       # Wiki 查询
│   ├── review/                 # [v2.0] 审查能力增强
│   │   ├── cross_module_analysis.py # 跨模块影响分析
│   │   ├── field_conflict.py      # 字段级冲突检测
│   │   ├── incremental_ir.py      # 增量 IR 更新
│   │   └── multi_repo_deps.py     # 多仓库依赖追踪
│   └── agent/                  # [v3.0] Agent 支持
│       └── prompt_generator.py  # Agent 提示词生成
├── profiles/                   # 业务 Profile 配置
├── hooks/                      # 业务专属 Hook 实现
├── templates/                  # Jinja2 模板
├── knowledge/                  # 知识库（learn 模式输出）
├── delivery/                   # 交付产物（auto 模式输出）
├── tests/                      # 测试套件
└── references/                 # 参考文档
```

## 三层架构

```
┌────────────────────────────────────────────────────────────┐
│                    biz-delivery v3.0                       │
└────────────────────────────────────────────────────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ Layer 1       │   │ Layer 2       │   │ Layer 3       │
│ 知识提取层     │   │ 引擎层         │   │ Agent 执行层   │
│               │   │               │   │               │
│ • learn_repo  │   │ • review      │   │ • Setup Agent │
│ • wiki_engine │   │ • td_engine   │   │ • Implement   │
│ • query/      │   │ • test_engine │   │ • Test Agent  │
│               │   │               │   │ • Review Agent│
│               │   │ • delivery    │   │               │
│               │   │   _pipeline   │   │ • automation  │
└───────────────┘   └───────────────┘   └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ Layer 4       │   │ Layer 5       │   │ Layer 6       │
│ 业务配置层     │   │ 质量门禁层     │   │ 输出层         │
│               │   │               │   │               │
│ • profiles/   │   │ • quality_gate│   │ • delivery/   │
│ • hooks/      │   │ • validator   │   │ • reports/    │
└───────────────┘   └───────────────┘   └───────────────┘
```

## 业务 Profile 格式

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
      "exclude_patterns": ["test_*", "fixtures"]
    }
  ],
  "modules": [
    {"name": "AdGroup / 广告组", "keywords": ["adgroup", "广告组"]},
    {"name": "Creative / 素材", "keywords": ["creative", "素材", "review"]}
  ],
  "domain_terms": {
    "审核": "review",
    "发布": "publish"
  },
  "state_machines": {
    "Creative": {
      "states": ["DRAFT", "PENDING_APPROVAL", "APPROVED", "REJECTED", "LIVE"],
      "transitions": [
        {"from": "DRAFT", "to": "PENDING_APPROVAL", "action": "Submit"}
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

## 扩展点设计

### 实现 Hook 的步骤

1. **fetch_prd.py** (必需) — 定义如何获取 PRD
   ```python
   def fetch_prd(url, workspace_root):
       """从 Confluence/Wiki/本地文件获取 PRD"""
       ...
   ```

2. **map_terms.py** (可选) — 业务术语映射
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

## 版本演进

| 版本 | 能力 | 说明 |
|------|------|------|
| v1.0 | PRD Review + TD + Test | 基础三阶段 |
| v2.0 | 查询模块拆分 + 审查能力增强 | 跨模块分析、字段冲突检测 |
| v3.0 | 端到端完整交付 | Agent 任务生成 + 执行 + 自动化 + 质量门禁 |

## 详细文档

- [DOCS_V3.md](DOCS_V3.md) — v3.0 完整文档
- [references/extension_guide.md](references/extension_guide.md) — 扩展指南
- [references/profile_schema.json](references/profile_schema.json) — Profile Schema
- [CAPABILITY_ASSESSMENT.md](CAPABILITY_ASSESSMENT.md) — 能力评估
