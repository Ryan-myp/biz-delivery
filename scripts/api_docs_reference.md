#!/usr/bin/env python3
"""
biz-delivery API 文档
"""

# ============================================================================
# biz-delivery API 参考文档
# ============================================================================

## 1. 核心模块

### 1.1 GraphifyAnalysis - 代码图谱分析

```python
from graphify_analysis import GraphifyAnalysis

# 初始化
analysis = GraphifyAnalysis(repo_path="/path/to/repo")

# 运行分析
result = analysis.analyze()

# 获取结果
nodes = result["nodes"]      # 代码节点
edges = result["edges"]      # 依赖边
communities = result["communities"]  # 社区划分
god_nodes = result["god_nodes"]      # 核心节点
```

### 1.2 CommunityEnhancer - 社区增强

```python
from community_enhancer import CommunityEnhancer

enhancer = CommunityEnhancer()

# 分析社区
result = enhancer.analyze(nodes, edges)

# 获取命名后的社区
named_communities = result["named_communities"]
importance_ranking = result["importance_ranking"]
```

### 1.3 MultiLanguageScanner - 多语言扫描器

```python
from multi_language_scanner import MultiLanguageScanner

scanner = MultiLanguageScanner()

# 扫描Go代码
result = scanner.scan("/path/to/go/repo", language="go")

# 扫描Python代码
result = scanner.scan("/path/to/python/repo", language="python")

# 扫描结果
nodes = result["nodes"]      # 结构体/类
edges = result["edges"]      # 依赖关系
stats = result["stats"]      # 统计信息
```

### 1.4 HTMLVisualizer - HTML可视化

```python
from html_visualizer import HTMLVisualizer

visualizer = HTMLVisualizer()

# 生成HTML报告
html_content = visualizer.generate(nodes, edges, communities)

# 保存文件
visualizer.save(html_content, "report.html")
```

## 2. CLI 命令

### 2.1 基本用法

```bash
# 分析代码仓库
python scripts/graphify_analysis.py --repo /path/to/repo

# 分析社区结构
python scripts/community_enhancer.py --input graph.json

# 生成可视化报告
python scripts/html_visualizer.py --input graph.json --output report.html

# 扫描多语言代码
python scripts/multi_language_scanner.py --path /path/to/repo --lang go
```

### 2.2 高级选项

```bash
# 指定输出目录
python scripts/graphify_analysis.py --repo /path/to/repo --output-dir ./reports

# 调整社区检测参数
python scripts/community_enhancer.py --resolution 0.5 --min-size 5

# 生成紧凑Prompt
python scripts/graphify_prompt_builder.py --nodes graph.json --output prompt.md
```

## 3. 数据格式

### 3.1 GraphJSON

```json
{
  "nodes": [
    {
      "id": "node_1",
      "name": "Graph",
      "type": "struct",
      "file": "graph.go",
      "degree": 15,
      "in_degree": 8,
      "out_degree": 7
    }
  ],
  "edges": [
    {
      "source": "node_1",
      "target": "node_2",
      "type": "DEPENDS_ON"
    }
  ],
  "communities": [
    {
      "id": 0,
      "name": "graph-core",
      "nodes": ["node_1", "node_2"],
      "importance": 15.5
    }
  ]
}
```

### 3.2 ScanResult

```json
{
  "repo_name": "example-repo",
  "language": "go",
  "nodes": [...],
  "edges": [...],
  "stats": {
    "total_nodes": 100,
    "total_edges": 150,
    "structs": 30,
    "functions": 70
  }
}
```

## 4. 性能基准

| 操作 | 耗时 | 内存 |
|------|------|------|
| 100节点图分析 | <1s | <50MB |
| 1000节点图分析 | <5s | <200MB |
| 社区检测(1000节点) | <2s | <100MB |
| HTML生成(1000节点) | <1s | <50MB |

## 5. 错误处理

```python
try:
    result = analysis.analyze()
except FileNotFoundError as e:
    print(f"仓库不存在: {e}")
except subprocess.CalledProcessError as e:
    print(f"Tree-sitter执行失败: {e}")
except Exception as e:
    print(f"未知错误: {e}")
```
