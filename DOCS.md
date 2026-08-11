# biz-delivery 文档体系

## 📚 文档分类

### 1. API文档
- `API_REFERENCE.md` - API接口参考
- `SCRIPTS_GUIDE.md` - 脚本使用说明

### 2. 架构文档
- `ARCHITECTURE.md` - 系统架构设计
- `DESIGN_PATTERNS.md` - 设计模式

### 3. 用户手册
- `USER_GUIDE.md` - 快速开始指南
- `FAQ.md` - 常见问题解答

### 4. 开发指南
- `DEVELOPER_GUIDE.md` - 开发者指南
- `CONTRIBUTING.md` - 贡献指南

---

## 📖 API文档

### 核心引擎

#### GraphifyEngine
```python
from unified_api import GraphifyEngine

engine = GraphifyEngine()
result = engine.execute(ir_document)
```

**输入**: IRDocument
**输出**: IRDocument (增强版)

#### CommunityEngine
```python
from unified_api import CommunityEngine

engine = CommunityEngine()
result = engine.execute(ir_document)
```

#### PromptEngine
```python
from unified_api import PromptEngine

engine = PromptEngine()
result = engine.execute(ir_document)
```

---

## 🚀 快速开始

### 安装依赖
```bash
pip install tree-sitter tree-sitter-go pytest
```

### 运行测试
```bash
python -m pytest scripts/ -v
```

### 分析代码仓库
```bash
python scripts/learn_repo_v2.py --repo /path/to/repo --lang go --output ./output
```

---

## 📊 核心能力

| 能力 | 描述 | 状态 |
|------|------|------|
| 代码图谱分析 | Tree-sitter AST解析 | ✅ |
| 社区检测 | Louvain算法 | ✅ |
| 多语言扫描 | Go/Python/Java/TS | ✅ |
| HTML可视化 | D3.js图表 | ✅ |
| Prompt生成 | 紧凑化设计 | ✅ |
