# biz-delivery 文档体系

## 📚 文档分类

### 1. 核心文档
- `README.md` — 项目概述与快速开始
- `SKILL.md` — Skill 元数据与架构说明
- `USAGE.md` — 使用手册
- `DOCS.md` — 本文档索引

### 2. 参考文档
- `references/profile_schema.json` — Profile JSON Schema
- `references/input_contract.md` — 输入契约
- `references/output_contract.md` — 输出契约
- `references/extension_guide.md` — 扩展指南
- `references/learn_repo-notes.md` — 代码学习笔记
- `references/learn-quantitative-analysis.md` — 量化分析

### 3. 知识库
- `knowledge/*/` — 各业务域的编译式知识库
- `wiki_engine/` — Wiki 引擎实现

### 4. 测试
- `tests/` — pytest 测试套件
- `scripts/benchmark.py` — 性能基准测试

---

## 📖 API 参考

### 核心引擎

#### ReviewEngine
```python
from scripts.review_engine import ReviewEngine

engine = ReviewEngine(profile, output_dir, wiki_path)
result = engine.review(prd_text)
# result: {status, prompt_file, prd_length}
```

#### TDEngine
```python
from scripts.td_engine import TDEngine

engine = TDEngine(profile, output_dir, wiki_path)
result = engine.generate_td(prd_text, review_report)
# result: {status, prompt_file}
```

#### TestEngine
```python
from scripts.test_engine import TestEngine

engine = TestEngine(profile, output_dir, wiki_path)
result = engine.generate_tests(prd_text, td_text)
# result: {status, prompt_file}
```

### 流水线

#### run_pipeline.py
```bash
# Learn 模式
python3 scripts/run_pipeline.py --profile profiles/my-service.json --mode learn --output-dir knowledge/my-service

# PRD-TDD 模式
python3 scripts/run_pipeline.py --profile profiles/my-service.json --mode prdtdd --text "<PRD>" --output-dir delivery/my-feature

# Auto 模式（全自动）
python3 scripts/run_pipeline.py --profile profiles/my-service.json --mode auto --text "<PRD>" --output-dir delivery/my-feature
```

---

## 🔧 架构文档

### 知识提取引擎
- `scripts/knowledge_extractor.py` — AST/CFG/DFG 分析
- `scripts/code_graph_builder.py` — 代码图谱构建
- `scripts/core_flow_analyzer.py` — 核心流程分析

### 证据查询
- `scripts/query_evidence.py` — 多路融合查询
- `scripts/smart_routing.py` — 意图识别 + 路由
- `scripts/rrf_fusion.py` — RRF 融合算法

### Wiki 引擎
- `wiki_engine/ingest.py` — 知识摄入
- `wiki_engine/query.py` — 知识问答
- `wiki_engine/lint.py` — 知识审计

---

## 📊 业务 Profile

### 已配置的业务域
- `creative-platform` — 创意平台
- `ad-platform` — 广告投放平台
- `sponge` — 海绵平台
- `conc` — conciliation 服务
- `eino` — EINO 框架

### Profile 结构
```json
{
  "business_domain": "my-service",
  "repositories": [...],
  "modules": [...],
  "query_aliases": {...},
  "state_machines": {...},
  "business_rules": {...},
  "service_topology": {...}
}
```

详细 Schema 见 `references/profile_schema.json`
