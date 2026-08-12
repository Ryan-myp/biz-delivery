# biz-delivery

> **研发流程 Skill 标准化系统** — 确定性、规则驱动、不依赖 LLM

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://github.com/Ryan-myp/biz-delivery/actions/workflows/ci.yml/badge.svg)](https://github.com/Ryan-myp/biz-delivery/actions)

---

## 📋 项目定位

biz-delivery 是一个**研发流程 Skill 标准化系统**。

通过**确定性、规则驱动**的 Skill，将 PRD 审查、技术方案生成、任务规划、测试用例生成等环节标准化。

### 核心理念

```
Skill = 确定性逻辑 + 模板填充 + 规则检查
       ↑
    不依赖 LLM
```

---

## 🎯 六大核心 Skill

| Skill | 功能 | 实现方式 | 依赖 LLM |
|-------|------|---------|---------|
| **PRD Review** | 自主发现 PRD 问题 | 规则检查 | ❌ |
| **TD** | 根据 PRD 写技术方案 | 模板填充 | ❌ |
| **Task Planning** | 生成执行计划 | 规则分解 | ❌ |
| **Agent Execution** | 执行任务计划 | 任务调度 | ⚠️ 可选 |
| **Test Case** | 生成测试用例 | 模板生成 | ❌ |
| **Automated Testing** | 自动化测试 | 脚本执行 | ❌ |

---

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置 Profile

```bash
python3 scripts/init_profile.py --lang go
```

### 运行 Skill

```bash
# 只运行 PRD Review
python3 scripts/run_pipeline.py --mode review --prd prd/your_prd.md

# 只生成技术方案
python3 scripts/run_pipeline.py --mode td --prd prd/your_prd.md

# 只生成测试用例
python3 scripts/run_pipeline.py --mode test --prd prd/your_prd.md

# 完整流程
python3 scripts/run_pipeline.py --mode full --prd prd/your_prd.md
```

---

## 📁 项目结构

```
biz-delivery/
├── skills/                    # Skill 实现（确定性）
│   ├── base.py               # Skill 基类
│   ├── prd_review/           # ✅ PRD 审查 Skill
│   ├── technical_design/     # ✅ 技术方案 Skill
│   ├── task_planning/        # ✅ 任务规划 Skill
│   ├── agent_execution/      # ⚠️ Agent 执行 Skill
│   ├── test_case/            # ✅ 测试用例 Skill
│   ├── automated_testing/    # ✅ 自动化测试 Skill
│   └── orchestrator.py       # Skill 编排器
├── scripts/                   # 核心引擎
│   ├── review_engine.py      # 审查引擎（兼容旧版）
│   ├── td_engine.py          # 技术方案引擎（兼容旧版）
│   ├── test_engine.py        # 测试用例引擎（兼容旧版）
│   └── agent/                # Agent 模块
├── hooks/                     # Hook 扩展点
├── templates/                 # Jinja2 模板
├── profiles/                  # 业务 Profile
├── prd/                       # PRD 文档
├── delivery/                  # 交付产物
└── tests/                     # 测试用例（287 tests）
```

---

## 📖 详细文档

- [项目定位](POSITIONING.md) - 核心理念和使用场景
- [Skill 设计原则](skills/DESIGN.md) - 为什么不依赖 LLM
- [Skill 架构](SKILL_ARCHITECTURE.md) - 各 Skill 详细设计
- [快速开始](QUICKSTART.md) - 上手指南
- [API 参考](references/api_reference.md) - 接口文档

---

## 🧪 测试

```bash
# 运行所有测试
python3 -m pytest tests/ -v

# 运行特定测试
python3 -m pytest tests/test_skills.py -v
```

**测试结果**: 287 passed

---

## 💡 核心价值

| 特性 | 说明 |
|------|------|
| **确定性** | 相同输入 → 相同输出，无幻觉 |
| **零成本** | 无需 API 调用，完全离线 |
| **可测试** | 100% 单元测试覆盖 |
| **可扩展** | 自定义 Skill 和 Hook |

---

## 📝 示例

查看 `prd/eino_loop_node_prd.md` 了解 PRD 格式示例。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 License

MIT License
