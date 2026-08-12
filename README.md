# biz-delivery

> **研发流程 Skill 标准化系统** — 从 PRD 到测试用例的自动化流程

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://github.com/Ryan-myp/biz-delivery/actions/workflows/ci.yml/badge.svg)](https://github.com/Ryan-myp/biz-delivery/actions)

---

## 📋 项目定位

biz-delivery 是一个**研发流程 Skill 标准化系统**，通过可复用的 Skill 组件，将 PRD 审查、技术方案生成、任务规划、测试用例生成等环节标准化、自动化。

### 核心能力

| Skill | 功能 | 状态 |
|-------|------|------|
| **PRD Review** | 自主发现 PRD 问题 | ✅ |
| **Technical Design** | 根据 PRD 写技术方案 | ✅ |
| **Task Planning** | 生成执行计划让 Agent 写代码 | ✅ |
| **Agent Execution** | 执行任务计划，生成代码 | ⚠️ 需 LLM |
| **Test Case** | 生成测试用例 | ✅ |
| **Automated Testing** | 自动化测试验证 | ⚠️ 需真实代码 |

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
├── skills/                    # Skill 实现
│   ├── base.py               # Skill 基类
│   ├── prd_review/           # PRD 审查 Skill
│   ├── technical_design/     # 技术方案 Skill
│   ├── task_planning/        # 任务规划 Skill
│   ├── agent_execution/      # Agent 执行 Skill
│   ├── test_case/            # 测试用例 Skill
│   ├── automated_testing/    # 自动化测试 Skill
│   └── orchestrator.py       # Skill 编排器
├── scripts/                   # 核心引擎
│   ├── review_engine.py      # 审查引擎
│   ├── td_engine.py          # 技术方案引擎
│   ├── test_engine.py        # 测试用例引擎
│   ├── automation.py         # 自动化测试引擎
│   └── agent/                # Agent 模块
├── hooks/                     # Hook 扩展点
├── templates/                 # Jinja2 模板
├── profiles/                  # 业务 Profile
├── prd/                       # PRD 文档
├── delivery/                  # 交付产物
└── tests/                     # 测试用例
```

---

## 📖 详细文档

- [项目定位](POSITIONING.md) - 核心理念和使用场景
- [Skill 架构](SKILL_ARCHITECTURE.md) - 各 Skill 详细设计
- [快速开始](QUICKSTART.md) - 上手指南
- [API 参考](references/api_reference.md) - 接口文档
- [扩展指南](references/extension_guide.md) - 如何自定义 Skill

---

## 🧪 测试

```bash
# 运行所有测试
python3 -m pytest tests/ -v

# 运行特定测试
python3 -m pytest tests/test_skills.py -v
```

**测试结果**: 284 passed

---

## 📝 示例

查看 `prd/eino_loop_node_prd.md` 了解 PRD 格式示例。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 License

MIT License
