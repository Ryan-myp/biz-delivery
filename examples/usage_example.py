"""
biz-delivery 使用示例
演示如何使用核心功能
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.expert_system import SeniorExpertSystem
from scripts.case_learning_engine import CaseLearningEngine
from scripts.quality_gate_cli import QualityGateCLI
from scripts.ryan_kb_loader import get_kb


def example_prd_review():
    """PRD审查示例"""
    print("=" * 60)
    print("示例1: PRD审查")
    print("=" * 60)

    expert = SeniorExpertSystem()

    # 示例PRD
    prd = """# 广告竞价引擎优化

## 背景
当前DSP系统QPS 5万，P99延迟150ms，需要优化到P99<100ms。

## 功能需求
1. 竞价引擎优化 - RTB实时竞价
2. 预算追踪 - 预扣机制防超投
3. 降级策略 - 画像→规则→默认出价
4. 反作弊 - 设备指纹+ML模型

## 非功能需求
- P99延迟 < 100ms
- 预算超投率 < 0.1%
- 可用性 99.99%
"""

    result = expert.review(prd, "advertising")
    analysis = result.get('analysis', {})

    print(f"\n【领域识别】{result['domain']}")

    print(f"\n【知识库引用】{len(analysis.get('knowledge_references', []))}篇")
    for ref in analysis.get('knowledge_references', [])[:3]:
        print(f"  - {ref.get('title', 'N/A')}")

    print(f"\n【技术可行性】")
    tech = analysis.get('technical_feasibility', {})
    print(f"  覆盖率: {tech.get('coverage_rate', 0):.0%}")
    print(f"  可行性: {tech.get('feasibility', 'N/A')}")

    print(f"\n【风险评估】{len(analysis.get('risk_assessment', []))}个风险")
    for risk in analysis.get('risk_assessment', [])[:3]:
        print(f"  ⚠️ {risk.get('level', '')}: {risk.get('risk', '')}")

    print(f"\n【优化建议】{len(analysis.get('optimization_suggestions', []))}条")
    for sug in analysis.get('optimization_suggestions', [])[:3]:
        print(f"  - [{sug.get('type', '')}] {sug.get('suggestion', '')[:50]}...")


def example_case_learning():
    """案例学习示例"""
    print("\n" + "=" * 60)
    print("示例2: 案例学习")
    print("=" * 60)

    cases = CaseLearningEngine()

    print(f"\n【案例统计】")
    stats = cases.get_stats()
    print(f"  总案例数: {stats['total_cases']}")
    print(f"  成功率: {stats['success_rate']}")
    print(f"  领域分布: {len(stats['by_domain'])}个")

    print(f"\n【案例列表】")
    for case in cases.cases[:5]:
        print(f"  📋 {case.case_id} - {case.domain}")
        print(f"     摘要: {case.prd_summary[:40]}...")
        print(f"     结果: {case.outcome} (质量分: {case.quality_score})")
        if case.lessons:
            print(f"     经验: {case.lessons[0][:30]}...")


def example_quality_gate():
    """质量门禁示例"""
    print("\n" + "=" * 60)
    print("示例3: 质量门禁")
    print("=" * 60)

    gate = QualityGateCLI()
    result = gate.check('.')

    print(f"\n【质量评分】{result['score']}/{result['max_score']} ({result['percentage']}%)")
    print(f"【评级】{result['rating']}")
    print(f"【通过】{'✅' if result['passed'] else '❌'}")

    print(f"\n【检查项详情】")
    for name, data in result.get('checks', {}).items():
        icon = "✅" if data['passed'] else "❌"
        print(f"  {icon} {name}: {data['detail']}")


def example_kb_search():
    """知识库搜索示例"""
    print("\n" + "=" * 60)
    print("示例4: 知识库搜索")
    print("=" * 60)

    kb = get_kb()
    stats = kb.get_stats()

    print(f"\n【知识库统计】")
    print(f"  总文档数: {stats['total_docs']}")
    print(f"  索引词数: {stats['index_size']}")
    print(f"  领域分布:")
    for domain, count in sorted(stats['by_domain'].items(), key=lambda x: -x[1])[:5]:
        print(f"    - {domain}: {count}篇")

    print(f"\n【搜索示例】")
    queries = ['竞价', 'Agent', 'Redis', '事务']
    for q in queries:
        results = kb.search(q, limit=2)
        print(f"  '{q}': {len(results)}篇")
        for r in results[:1]:
            print(f"    - {r['title'][:40]}")


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🎯 biz-delivery 使用示例")
    print("=" * 60)

    example_prd_review()
    example_case_learning()
    example_quality_gate()
    example_kb_search()

    print("\n" + "=" * 60)
    print("✅ 所有示例执行完成")
    print("=" * 60)
