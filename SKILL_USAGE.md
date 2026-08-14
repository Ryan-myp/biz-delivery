# biz-delivery Skill 使用指南

## 快速开始

### 1. 单项目深度分析（一键分析任何项目）

```bash
# 分析任意 Go/Python/Java 项目
python3 scripts/deep_analysis.py \
  --path /path/to/your/project \
  --output out/my-project/

# 分析多仓库项目（含跨仓库调用分析）
python3 scripts/deep_analysis.py \
  --path /path/to/dap \
  --cross-repo \
  --cross-paths /path/to/ad_delivery_platform \
  --output out/multi-repo/
```

**输出内容**：
- `summary.md` — 专家级业务摘要（架构、模式、关键流程）
- `enhanced_summary.md` — LLM 增强版摘要（可选）
- `analysis_result.json` — 完整分析数据
- `*.md` — 13 张 Mermaid 流程图

### 2. 质量门禁验证

```bash
# 验证分析结果是否达到专家级标准
python3 scripts/quality_gate.py out/my-project/

# 输出示例:
# ============================================================
# 📊 质量门禁报告
# ============================================================
# 评级: A+ 顶级专家水平
# 得分: 100/100
# 状态: ✅ 通过
```

### 3. LLM 增强摘要（可选）

```bash
# 使用模板化增强（无需 API Key）
python3 scripts/llm_enhanced_summary.py \
  --input out/my-project/ \
  --no-llm

# 使用 LLM 增强（需要 OPENAI_API_KEY）
export OPENAI_API_KEY=your-key
python3 scripts/llm_enhanced_summary.py \
  --input out/my-project/ \
  --model gpt-4
```

### 4. 项目自动检测

```bash
# 检测项目类型和特征
python3 scripts/project_auto_detector.py \
  --path /path/to/project \
  --json

# 输出示例:
# {
#   "language": "go",
#   "framework": "spex",
#   "architecture": "microservice",
#   "scale": "large",
#   "max_files": 5000,
#   "analysis_depth": "full"
# }
```

### 5. 通用模式检测（支持多语言）

```bash
# 检测任意语言的架构模式
python3 scripts/universal_pattern_detector.py \
  /path/to/go-project
  # 或
python3 scripts/universal_pattern_detector.py \
  /path/to/python-project
  # 或
python3 scripts/universal_pattern_detector.py \
  /path/to/java-project

# 检测 7 类模式:
# - 状态机 (State Machines)
# - Redis 分布式锁 (Redis Locks)
# - 重试机制 (Retry Logic)
# - Kafka/消息队列 (Kafka/MQ)
# - 幂等性 (Idempotency)
# - 任务组 (Task Groups)
# - 枚举/常量 (Enums)
```

## 核心能力矩阵

| 能力 | 脚本 | 输入 | 输出 |
|------|------|------|------|
| 项目检测 | `project_auto_detector.py` | 项目路径 | language/framework/architecture/scale |
| 代码扫描 | `learn_repo.py` | 项目路径 | IRDocument (structs/functions/routes) |
| 流程提取 | `go_flow_analyzer.py` | 仓库路径 | 调用链 + 入口点 + 特征 |
| **通用模式检测** | `universal_pattern_detector.py` | 仓库路径 | **7类架构模式（Go/Python/Java）** |
| 跨仓库分析 | `cross_repo_flow.py` | 多仓库路径 | 跨服务 RPC 调用链 |
| 流程图 | `mermaid_generator.py` | IR + flow 数据 | 13 张 Mermaid 图 |
| **质量门禁** | `quality_gate.py` | 输出目录 | 评级 A+/A/B/C |
| **LLM增强** | `llm_enhanced_summary.py` | 分析结果 | 专家级业务摘要 |
| 深度分析 | `deep_analysis.py` | 项目路径 | summary.md + 所有图 + JSON |

## 支持的编程语言

| 语言 | 扫描 | 流程提取 | 模式检测 | 图表生成 |
|------|------|----------|----------|----------|
| ✅ Go | 完整 | 完整 | 7类模式 | 13张图 |
| ✅ Python | 完整 | 基础 | 7类模式 | 9张图 |
| ✅ Java | 完整 | 基础 | 7类模式 | 9张图 |

## 典型场景

### 场景 1：接手一个新 Go 微服务
```bash
# 一键分析，30-40秒生成专家级报告
python3 scripts/deep_analysis.py --path ./my-service --output out/
cat out/summary.md    # 了解业务
cat out/state_machine.md  # 了解状态机
cat out/architecture.md   # 了解架构

# 验证质量
python3 scripts/quality_gate.py out/
```

### 场景 2：理解跨仓库调用
```bash
python3 scripts/deep_analysis.py \
  --path ./dap \
  --cross-repo \
  --cross-paths ./ad_delivery_platform \
  --output out/
cat out/cross_service_flow.md
```

### 场景 3：快速模式识别（任意语言）
```bash
# 支持 Go/Python/Java
python3 scripts/universal_pattern_detector.py ./service-a ./service-b
```

### 场景 4：LLM 增强分析
```bash
# 先生成基础分析
python3 scripts/deep_analysis.py --path ./project --output out/

# 再用 LLM 增强
python3 scripts/llm_enhanced_summary.py --input out/ --no-llm
# 或使用 GPT-4
python3 scripts/llm_enhanced_summary.py --input out/ --model gpt-4
```

## 性能基准

| 项目规模 | 文件数 | 分析耗时 | 图表数 | 评级 |
|----------|--------|----------|--------|------|
| 小型 | <500 | ~10s | 9-11 | A+ |
| 中型 | 500-2000 | ~35s | 11-13 | A+ |
| 大型 | >2000 | ~45s | 11-13 | A+ |

## 质量门禁标准

| 检查项 | 标准 | 权重 |
|--------|------|------|
| 阶段完成 | ≥7 个 | 20分 |
| 错误数 | 0 | 20分 |
| 图表生成 | ≥5 张 | 20分 |
| 模式检测 | ≥3 类 | 20分 |
| 结构体识别 | ≥5 个 | 10分 |
| 摘要长度 | ≥500 字符 | 10分 |

**评级标准**:
- A+ (90-100分): 顶级专家水平
- A (80-89分): 优秀
- B+ (70-79分): 良好
- B (60-69分): 及格
- C (<60分): 需改进

## 使用建议

### 最佳实践

```bash
# 1. 对新项目进行深度分析
python3 scripts/deep_analysis.py \
  --path /path/to/new-project \
  --output docs/knowledge-base/ \
  --max-files 200

# 2. 验证分析质量
python3 scripts/quality_gate.py docs/knowledge-base/

# 3. 如需增强，使用 LLM
python3 scripts/llm_enhanced_summary.py \
  --input docs/knowledge-base/ \
  --no-llm  # 或使用 --model gpt-4
```

### 注意事项

1. **大项目优化**: 系统会自动对大型项目降速（max_files 从 5000 降至 1500）
2. **超时保护**: 每个阶段都有超时限制（默认 60-120s），失败不影响整体流程
3. **增量分析**: 支持只扫描变更文件（incremental scan）
4. **多语言**: 系统自动检测项目语言并应用对应分析策略
