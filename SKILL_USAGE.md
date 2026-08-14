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
- `*.md` — 11 张 Mermaid 流程图（可直接在 mermaid.live 预览）
- `analysis_result.json` — 完整分析数据

### 2. 项目自动检测

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

### 3. 模式检测（独立运行）

```bash
# 检测架构模式
python3 scripts/go_flow_analyzer.py \
  --repo-paths /path/to/repo1 /path/to/repo2 \
  --patterns
```

**检测 7 类模式**：
| 模式 | 说明 | 对 agent 的价值 |
|------|------|----------------|
| 状态机 | 状态常量 + 转换逻辑 | 知道合法状态值和跳转规则 |
| Redis锁 | Del/DeleteKey/RedisMutex | 知道并发安全边界 |
| 重试 | retry/backoff/sleep | 知道失败后系统行为 |
| Kafka | Producer/Consumer | 知道异步解耦点 |
| 幂等 | CheckConfirm/分布式锁 | 知道重入安全性 |
| 任务组 | CreateTaskGroup/回调 | 知道批量操作生命周期 |
| 枚举 | const block 分类 | 知道字段合法取值范围 |

### 4. 使用 biz 标准流程

```bash
# 初始化项目
python3 scripts/init_profile.py --domain auction --output profiles/

# 运行完整流水线
python3 scripts/run_pipeline.py \
  --profile profiles/my-service.json \
  --prd prd.md \
  --output out/
```

## 核心能力矩阵

| 能力 | 脚本 | 输入 | 输出 |
|------|------|------|------|
| 项目检测 | `project_auto_detector.py` | 项目路径 | language/framework/architecture/scale |
| 代码扫描 | `learn_repo.py` | 项目路径 | IRDocument (structs/functions/routes) |
| 流程提取 | `go_flow_analyzer.py` | 仓库路径 | 调用链 + 入口点 + 特征 |
| 模式检测 | `go_flow_analyzer.py --patterns` | 仓库路径 | 7类架构模式 |
| 跨仓库分析 | `cross_repo_flow.py` | 多仓库路径 | 跨服务 RPC 调用链 |
| 流程图 | `mermaid_generator.py` | IR + flow 数据 | 11 张 Mermaid 图 |
| 深度分析 | `deep_analysis.py` | 项目路径 | summary.md + 所有图 + JSON |

## 支持的编程语言

- ✅ Go（完整支持：扫描、流程、模式、跨仓库）
- ✅ Python（扫描 + 基础流程）
- ✅ Java（扫描 + 基础流程）
- 🔄 TypeScript（扫描中）

## 典型场景

### 场景 1：接手一个新 Go 微服务
```bash
python3 scripts/deep_analysis.py --path ./my-service --output out/
cat out/summary.md    # 了解业务
cat out/state_machine.md  # 了解状态机
cat out/architecture.md   # 了解架构
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

### 场景 3：快速模式识别
```bash
python3 scripts/go_flow_analyzer.py \
  --repo-paths ./service-a ./service-b \
  --patterns
```
