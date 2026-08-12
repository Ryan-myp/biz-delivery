# biz-delivery — 通用业务交付框架

一套通用的业务交付引擎，从 PRD 到测试用例的全链路自动化。

**核心原则：流程通用，业务通过 Profile + Hooks 配置扩展。**

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

### 3. 运行流水线

```bash
# 完整链路：PRD → 评审 → TD → 开发计划 → 测试用例 → 自动化计划
python3 scripts/run_pipeline.py \
  --profile "profiles/my-service.json" \
  --text "<PRD内容>" \
  --output-dir delivery/my-feature \
  --mode auto
```

## 运行模式

| 模式 | 说明 | 输出 |
|------|------|------|
| `learn` | 代码扫描 → 构建知识库 | knowledge/\* |
| `prdtdd` | 生成 Prompt 文件，需手动调用 LLM | delivery/\*_prompt.md |
| `auto` | PRD → LLM 审查 → TD → 测试（全自动） | delivery/\*.md |
| `eval` | 评估审查准确性 | evaluation/\* |

## 目录结构

```
biz-delivery/
├── scripts/              # 核心引擎脚本
│   ├── run_pipeline.py   # 端到端流水线
│   ├── review_engine.py  # PRD 评审引擎
│   ├── td_engine.py      # 技术方案生成引擎
│   ├── test_engine.py    # 测试用例生成引擎
│   ├── query_evidence.py # 证据查询引擎
│   ├── learn_repo.py     # 代码学习引擎
│   └── base_engine.py    # 引擎基类
├── profiles/             # 业务 Profile 配置
│   ├── default.json      # 默认配置
│   └── index.json        # 注册表
├── hooks/                # 业务 Hook 实现
│   ├── fetch_prd.py
│   ├── map_terms.py
│   ├── validate.py
│   ├── post_review.py
│   └── test_dimensions.py
├── templates/            # Jinja2 模板
│   ├── review_report.md.j2
│   ├── td.md.j2
│   └── test_cases.md.j2
├── knowledge/            # 编译式知识库
│   ├── creative-platform/
│   ├── ad-platform/
│   └── sponge/
├── wiki_engine/          # Wiki 知识引擎
├── tests/                # 测试套件
└── references/           # 参考文档
```

## 三层架构

```
┌─ Layer 1: 知识提取引擎 ───────────────────┐
│  AST Parser / CFG / DFG / Flow Builder     │
└────────────────────────────────────────────┘
                     │
                     ▼
┌─ Layer 2: 核心引擎 ────────────────────────┐
│  review_engine / td_engine / test_engine    │
└────────────────────────────────────────────┘
                     ▲
                     │
┌─ Layer 3: 业务配置 ────────────────────────┐
│  profiles/ + hooks/                         │
└────────────────────────────────────────────┘
```

## v2.0 新增能力

> 详见 [OPTIMIZATION_V2_SUMMARY.md](OPTIMIZATION_V2_SUMMARY.md)

### 能力评估

| 维度 | 升级前 | 升级后 |
|------|--------|--------|
| 代码理解能力 | ★★★☆☆ | ★★★★☆ |
| PRD 审查能力 | ★★★★☆ | ★★★★★ |
| 遗漏识别能力 | ★★☆☆☆ | ★★★★☆ |
| 冲突检测能力 | ★★★☆☆ | ★★★★★ |
| **总分** | **13/20** | **18/20** |

### 新增模块

```
scripts/review/
├── cross_module_analysis.py  # 跨模块影响分析（调用链推断）
├── field_conflict.py         # 字段级冲突检测（破坏性变更、Schema风险）
├── incremental_ir.py         # 增量 IR 更新（文件级变更检测）
└── multi_repo_deps.py        # 多仓库依赖追踪（RPC/MQ/HTTP）
```

### 使用示例

```python
# 跨模块影响分析
from scripts.review import analyze_cross_module_impact
result = analyze_cross_module_impact(prd_text, ir_data, profile)

# 字段级冲突检测
from scripts.review import detect_field_conflicts
result = detect_field_conflicts(prd_text, ir_data)
```

## 业务接入指南

1. **创建 Profile**: 复制 `profiles/default.json` 并修改
2. **实现 Hooks**: 根据业务需求实现 `hooks/` 下的函数
3. **配置 Wiki**: 运行 `learn` 模式构建知识库
4. **开始交付**: 使用 `auto` 或 `prdtdd` 模式

详细指南请参考 [references/extension_guide.md](references/extension_guide.md)

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

## 常见问题

### Q: 如何添加新的业务域？
A: 创建新的 Profile 文件在 `profiles/` 目录，并实现对应的 Hooks。

### Q: 如何跳过某个阶段？
A: 使用 `--stages` 参数指定要执行的阶段，如 `--stages review,test`。

### Q: LLM 调用失败怎么办？
A: 检查 `AGNES_API_KEY` 环境变量，或使用 `prdtdd` 模式手动调用 LLM。

### Q: 如何提高查询准确性？
A: 完善知识库（运行 `learn` 模式），优化术语映射（编辑 `hooks/map_terms.py`）。

## 开发指南

### 添加新的引擎

1. 继承 `EngineBase` 类
2. 实现 `generate()` 方法
3. 在 `run_pipeline.py` 中添加新模式

### 扩展 Profile Schema

参考 `references/profile_schema.json`，修改后更新验证逻辑。

## 许可证

内部工具，仅供 Sapiens AI 团队使用。

---

## v3.0 新增能力

> 详见 [DOCS_V3.md](DOCS_V3.md) 和 [V3_COMPLETION_REPORT.md](V3_COMPLETION_REPORT.md)

### 完整交付链路

```
PRD → Review → TD → Agent Tasks → Implementation → Test → Automation → Quality Gate
```

### 新增模块

| 模块 | 说明 | 行数 |
|------|------|------|
| `delivery_pipeline.py` | 端到端流水线 | 1163 |
| `automation.py` | 自动化执行引擎 | 509 |
| `agent/prompt_generator.py` | Agent 提示词生成 | 433 |
| `review/cross_module_analysis.py` | 跨模块影响分析 | 462 |
| `review/field_conflict.py` | 字段级冲突检测 | 380 |
| `review/incremental_ir.py` | 增量 IR 更新 | 353 |
| `review/multi_repo_deps.py` | 多仓库依赖追踪 | 343 |

### 快速开始

```bash
# 一键运行完整流水线
python3 scripts/delivery_pipeline.py \
  --profile profiles/my-service.json \
  --prd prd.md \
  --output-dir delivery/my-feature
```
