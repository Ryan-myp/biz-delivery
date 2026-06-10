#!/usr/bin/env python3
"""
自动化知识管理系统演示

展示如何通过 Wiki 引擎自动学习新知识：
1. 从原始文档创建知识页面
2. 自动建立页面间的链接
3. 支持智能查询和回答
"""

import sys
from pathlib import Path

_BD_ROOT = str(Path(__file__).parent.parent)
if _BD_ROOT not in sys.path:
    sys.path.insert(0, _BD_ROOT)

from ingest import WikiContext, WikiPage, auto_ingest
from query import wiki_search, synthesize_answer
from summarizer import enhanced_query

def main():
    print("=== 自动化知识管理系统演示 ===\n")
    
    # 1. 设置 Wiki 目录
    wiki_dir = Path("/tmp/learning-demo")
    raw_dir = wiki_dir / "raw"
    
    # 确保目录存在
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. 创建新的学习材料
    materials = {
        "knowledge-engineering.md": """# 知识工程

## 什么是知识工程
知识工程是将人类专业知识转化为计算机可处理形式的过程。

## 核心方法
1. 知识获取 - 从专家或文档中提取知识
2. 知识表示 - 用结构化方式表示知识
3. 知识推理 - 基于知识进行推理和决策

## 应用场景
- 专家系统
- 智能问答
- 决策支持

## 与技术结合
- 与 RAG 结合：增强检索的知识质量
- 与 ReAct 结合：提供推理基础
""",
        "agent-architecture.md": """# Agent 架构设计

## 什么是 Agent 架构
Agent 架构是设计智能代理系统的框架和方法。

## 核心组件
1. 感知模块 - 接收外部环境信息
2. 推理模块 - 基于知识和规则进行推理
3. 行动模块 - 执行决策并影响环境

## 常见架构模式
- 分层架构
- 反应式架构
- 混合架构

## 与知识管理
- 依赖知识库进行决策
- 支持知识的持续学习
"""
    }
    
    # 保存学习材料
    for filename, content in materials.items():
        filepath = raw_dir / filename
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"✅ 创建学习材料: {filename}")
    
    # 3. 使用 Wiki 引擎自动处理
    print("\n🔄 使用 Wiki 引擎处理新知识...")
    
    for filename in materials.keys():
        result = auto_ingest(str(wiki_dir), str(raw_dir / filename))
        print(f"✅ 处理完成: {filename}")
        if result.get('page_path'):
            print(f"   页面路径: {result['page_path']}")
        if result.get('wikilinks'):
            print(f"   链接到: {result['wikilinks']}")
    
    # 4. 加载所有页面
    print("\n📚 加载所有知识页面...")
    wiki = WikiContext(wiki_dir)
    wiki.load_all()
    
    print(f"   共加载 {len(wiki.pages)} 个页面")
    for path, page in wiki.pages.items():
        print(f"   - {page.title} ({page.page_type})")
    
    # 5. 测试智能查询
    print("\n🔍 测试智能查询...")
    
    test_queries = [
        "什么是知识工程？",
        "Agent 架构包含哪些组件？",
        "RAG 和知识工程有什么关系？"
    ]
    
    for query in test_queries:
        print(f"\n查询: {query}")
        result = wiki_search(query, wiki, top_k=5)
        print(f"   找到 {result['total']} 个相关页面")
        
        if result['results']:
            for r in result['results'][:2]:
                print(f"   - {r['path'].name} (得分: {r['score']:.4f})")

if __name__ == "__main__":
    main()
