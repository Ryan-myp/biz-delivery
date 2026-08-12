# biz-delivery 快速开始

## 1. 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 设置 API Key
export AGNES_API_KEY="your-api-key-here"
```

## 2. 初始化业务 Profile

```bash
# 使用默认模板创建新 Profile
python3 scripts/init_profile.py \
  --business-domain "my-service" \
  --repository "/path/to/your/repo" \
  --output profiles/my-service.json
```

编辑 `profiles/my-service.json` 填写业务详情。

## 3. 实现 Hooks（可选）

根据业务需求，在 `hooks/` 目录下实现：

| Hook | 用途 | 必需 |
|------|------|------|
| `fetch_prd.py` | 获取 PRD 内容 | ✅ |
| `map_terms.py` | 业务术语映射 | ⚠️ 推荐 |
| `validate.py` | 审查结果校验 | ⚠️ 推荐 |
| `post_review.py` | 评审后处理 | ❌ |
| `test_dimensions.py` | 测试维度定义 | ❌ |

## 4. 构建知识库

```bash
python3 scripts/run_pipeline.py \
  --profile profiles/my-service.json \
  --mode learn \
  --output-dir knowledge/my-service
```

## 5. 运行交付流水线

### 方式一：全自动模式（推荐）
```bash
python3 scripts/run_pipeline.py \
  --profile profiles/my-service.json \
  --mode auto \
  --text "$(cat prd.md)" \
  --output-dir delivery/my-feature
```

### 方式二：分阶段模式
```bash
# 只运行评审
python3 scripts/run_pipeline.py \
  --profile profiles/my-service.json \
  --mode prdtdd \
  --stages review \
  --text "$(cat prd.md)" \
  --output-dir delivery/my-feature

# 手动调用 LLM 后，再生成 TD
python3 scripts/run_pipeline.py \
  --profile profiles/my-service.json \
  --mode prdtdd \
  --stages td \
  --text "$(cat prd.md)" \
  --output-dir delivery/my-feature
```

## 6. 查看输出

```
delivery/my-feature/
├── review_prompt.md      # 审查 Prompt
├── review_report.md      # 审查报告
├── td_prompt.md          # TD Prompt
├── technical_design.md   # 技术方案
├── test_prompt.md        # 测试用例 Prompt
└── test_cases.md         # 测试用例
```

## 常用命令

```bash
# 列出已注册的 Profile
python3 scripts/profile_registry.py --list

# 验证 Profile
python3 scripts/profile_registry.py --validate --profile profiles/my-service.json

# 运行测试
python3 -m pytest tests/ -v

# 运行基准测试
python3 scripts/benchmark.py --profile profiles/default.json
```

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| LLM API 调用失败 | 检查 `AGNES_API_KEY` 环境变量 |
| 知识库为空 | 先运行 `learn` 模式 |
| 查询无结果 | 检查 Profile 中 repositories 路径是否正确 |
| 审查报告质量差 | 增加知识库规模，优化术语映射 |

## 下一步

- 阅读 [references/extension_guide.md](references/extension_guide.md) 了解如何扩展
- 阅读 [SKILL.md](SKILL.md) 了解完整架构
- 运行 `python3 scripts/benchmark.py` 了解性能基准
