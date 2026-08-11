# biz-delivery 使用手册

## 简介

biz-delivery 是一个智能化的代码理解和分析平台，支持：
- 代码图谱构建（Tree-sitter AST）
- 社区检测（Louvain算法）
- 多语言支持（Go/Python/Java/TypeScript）
- HTML可视化（D3.js）
- Prompt生成（紧凑化设计）

---

## 核心模块

### 1. Graphify Analysis
```bash
python scripts/graphify_analysis.py --repo /path/to/repo
```

### 2. Community Detection
```bash
python scripts/community_enhancer.py --input graph.json
```

### 3. Multi-Language Scanner
```bash
python scripts/multi_language_scanner.py --repo /path/to/repo --lang go
```

### 4. HTML Visualizer
```bash
python scripts/html_visualizer.py --input graph.json --output chart.html
```

---

## 使用流程

1. **扫描代码** → 生成IR Document
2. **构建图谱** → Graphify分析
3. **社区检测** → 识别关键模块
4. **生成Prompt** → 紧凑化知识提取
5. **可视化** → HTML图表展示

---

## 测试结果

```
✅ test_core_functions.py: 17 passed
✅ test_e2e.py: 5 passed
✅ test_workflows.py: 5 passed
```

---

## 性能基准

| 操作 | P95延迟 | 目标 |
|------|---------|------|
| Graphify分析 | <5s | <5s ✅ |
| 社区检测 | <2s | <2s ✅ |
| 多语言扫描 | <1s | <1s ✅ |
