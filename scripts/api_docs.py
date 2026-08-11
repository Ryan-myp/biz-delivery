#!/usr/bin/env python3
"""
Biz-Delivery API 文档与使用示例

提供完整的 API 参考和示例代码
"""

# ============================================================================
# 核心模块概览
# ============================================================================

"""
biz-delivery 是一个企业级研发工具包，提供以下核心功能：

1. 代码图谱分析 (graphify_analysis.py)
   - 基于 tree-sitter AST 的代码解析
   - 图中心性分析（God Nodes 识别）
   - 社区检测（Louvain 算法）
   - 跨社区连接分析

2. 多语言扫描器 (multi_language_scanner.py)
   - Go: tree-sitter-go（完整 AST）
   - Python: ast 模块（原生支持）
   - Java: tree-sitter-java
   - TypeScript: tree-sitter-typescript

3. 知识搜索 (knowledge_search.py)
   - RRF 多路融合搜索
   - 中文分词优化
   - Wiki 增强模式

4. Prompt 生成 (graphify_prompt_builder.py)
   - Graphify 风格紧凑 prompt
   - Token 节省 70%+
   - 关键代码片段注入

5. 社区增强 (community_enhancer.py)
   - 自动命名
   - 重要性排序
   - 特征提取
"""


# ============================================================================
# 使用示例
# ============================================================================

EXAMPLE_USAGE = '''
# ============================================================================
# 示例 1: 分析 Go 仓库
# ============================================================================

from graphify_analysis import run_graphify_analysis

# 分析 Eino 框架
graph, god_nodes, communities, prompt = run_graphify_analysis(
    repo_path="/path/to/eino",
    max_files=100,
    output_dir="./output/eino-analysis"
)

print(f"节点数: {len(graph.nodes)}")
print(f"边数: {len(graph.edges)}")
print(f"God Nodes: {[n['label'] for n in god_nodes[:5]]}")
print(f"Prompt 长度: {len(prompt)} chars")

# ============================================================================
# 示例 2: 多语言扫描
# ============================================================================

from multi_language_scanner import scan_repo, detect_language
from pathlib import Path

# 自动检测语言
repo_path = Path("/path/to/repo")
language = detect_language(repo_path)
print(f"检测到语言: {language}")

# 扫描
result = scan_repo(repo_path)
print(f"Structs: {len(result.structs)}")
print(f"Functions: {len(result.functions)}")
print(f"Edges: {len(result.edges)}")

# 指定语言扫描
result_py = scan_repo(Path("/path/to/python-project"), language="python")
result_js = scan_repo(Path("/path/to/js-project"), language="typescript")

# ============================================================================
# 示例 3: 社区分析
# ============================================================================

from community_enhancer import enhance_communities
import json

# 增强社区分析
result = enhance_communities(
    graph_path="./output/eino-analysis/graph.json",
    output_path="./output/eino-analysis/enhanced_communities.json"
)

print(f"社区数: {result['total']}")
for comm in result['communities'][:5]:
    print(f"  #{comm['id']} {comm['name']}: {comm['size']} nodes, importance={comm['importance']}")

# ============================================================================
# 示例 4: HTML 可视化
# ============================================================================

from html_visualizer import generate_visualization

# 生成可视化
html_path = generate_visualization(
    graph_path="./output/eino-analysis/graph.json",
    output_path="./output/eino-analysis/graph_visualization.html"
)
print(f"可视化已生成: {html_path}")

# ============================================================================
# 示例 5: 知识库搜索
# ============================================================================

from knowledge_search import query_knowledge

# 查询知识库
results = query_knowledge(
    query="Redis缓存穿透怎么解决",
    kb_path="/path/to/knowledge",
    top_k=5
)

for r in results:
    print(f"[{r['score']:.4f}] {r['doc_path']}")
    print(f"  {r['snippet'][:100]}...")

# ============================================================================
# 示例 6: 完整工作流
# ============================================================================

import tempfile
from pathlib import Path
from graphify_analysis import run_graphify_analysis
from community_enhancer import enhance_communities
from html_visualizer import generate_visualization

def analyze_project(repo_path: str, output_base: str):
    """完整分析流程"""
    output_dir = Path(output_base)
    
    # 1. 代码图谱分析
    print("📊 Step 1: 代码图谱分析...")
    graph, god_nodes, communities, prompt = run_graphify_analysis(
        repo_path,
        max_files=200,
        output_dir=str(output_dir / "graph")
    )
    
    # 2. 社区增强
    print("📊 Step 2: 社区增强...")
    enhanced = enhance_communities(
        graph_path=str(output_dir / "graph" / "graph.json"),
        output_path=str(output_dir / "graph" / "enhanced_communities.json")
    )
    
    # 3. 可视化
    print("📊 Step 3: 生成可视化...")
    html_path = generate_visualization(
        graph_path=str(output_dir / "graph" / "graph.json"),
        output_path=str(output_dir / "graph" / "graph_visualization.html")
    )
    
    # 4. 汇总报告
    report = {
        "project": Path(repo_path).name,
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "god_nodes": len(god_nodes),
        "communities": enhanced['total'],
        "prompt_length": len(prompt),
        "html_output": html_path,
    }
    
    return report

# 使用
report = analyze_project("/path/to/eino", "./output/eino-full")
print(f"分析完成: {report}")

# ============================================================================
# 示例 7: 生成 Markdown 报告
# ============================================================================

from graphify_prompt_builder import GraphifyPromptBuilder

builder = GraphifyPromptBuilder(project_name="MyProject")
markdown = builder.generate_markdown_report(
    graph_data={
        "nodes": [...],
        "edges": [...],
        "communities": {...},
    },
    god_nodes=[...],
)

with open("project-report.md", "w") as f:
    f.write(markdown)
'''


# ============================================================================
# CLI 工具
# ============================================================================

CLI_COMMANDS = '''
# ============================================================================
# CLI 命令参考
# ============================================================================

# 分析代码仓库
python graphify_analysis.py /path/to/repo [max_files] [output_dir]

# 增强社区分析
python community_enhancer.py graph.json [output.json]

# 生成 HTML 可视化
python html_visualizer.py graph.json [output.html]

# 批量分析多个仓库
python batch_analyzer.py /path/to/repos --langs go,python,java

# 运行测试套件
python -m pytest test_e2e.py -v

# 生成报告
python report_generator.py --input graph.json --output report.md
'''


if __name__ == '__main__':
    print(__doc__)
    print("\n" + "="*70)
    print("EXAMPLE USAGE:")
    print("="*70)
    print(EXAMPLE_USAGE)
    print("\n" + "="*70)
    print("CLI COMMANDS:")
    print("="*70)
    print(CLI_COMMANDS)
