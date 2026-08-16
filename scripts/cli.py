"""
biz-delivery CLI - 命令行工具
提供完整的交互式命令行界面

核心命令:
  1. biz-review <prd_file> - PRD审查
  2. biz-doc <domain> - 文档生成
  3. biz-quality <path> - 质量门禁
  4. biz-cases - 案例浏览
  5. biz-dashboard - 可视化
  6. biz-api - 启动API服务
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime


def cmd_review(args):
    """PRD审查命令"""
    from scripts.expert_system import SeniorExpertSystem
    from scripts.ai_decision_engine import AIDecisionEngine
    from scripts.case_learning_engine import CaseLearningEngine

    prd_path = Path(args.prd_file)
    if not prd_path.exists():
        print(f"❌ 文件不存在: {prd_path}")
        sys.exit(1)

    prd_content = prd_path.read_text()

    expert = SeniorExpertSystem()
    cases = CaseLearningEngine()
    decision = AIDecisionEngine(cases_engine=cases)

    # 检测领域
    domain = args.domain or expert._detect_domain(prd_content)
    print(f"📋 识别领域: {domain}")

    # 执行审查
    result = expert.review(prd_content, domain)
    patterns = expert.detect_patterns(prd_content, domain)

    # 显示结果
    print(f"\n🎯 审查结果:")
    print(f"   领域: {result['domain']}")

    analysis = result.get('analysis', {})

    # 业务价值
    value = analysis.get('business_value', {})
    print(f"\n📊 业务价值:")
    print(f"   评分: {value.get('score', 0)}/100")
    print(f"   目标用户: {'✅ 已定义' if value.get('has_target_user') else '❌ 缺失'}")
    print(f"   量化指标: {'✅ 已定义' if value.get('has_quantified_metrics') else '❌ 缺失'}")

    # 技术可行性
    tech = analysis.get('technical_feasibility', {})
    print(f"\n🔧 技术可行性:")
    print(f"   可行性: {tech.get('feasibility', 'N/A')}")
    if tech.get('items_checked'):
        for item in tech['items_checked']:
            icon = "✅" if item.get('covered') else "⚠️"
            print(f"   {icon} {item.get('item', '')}")

    # 风险
    risks = analysis.get('risk_assessment', [])
    if risks:
        print(f"\n⚠️ 风险:")
        for risk in risks[:5]:
            level = risk.get('level', '中')
            icon = "🔴" if level == '高' else "🟡"
            print(f"   {icon} {level}: {risk.get('risk', '')}")
            if risk.get('mitigation'):
                print(f"      💡 {risk['mitigation']}")

    # 模式检测
    if patterns:
        print(f"\n🔍 检测模式:")
        for p in patterns:
            print(f"   - {p['name']}: {', '.join(p['indicators'][:3])}")

    # AI决策
    ai_result = decision.analyze(prd_content, domain)
    print(f"\n🤖 AI决策:")
    print(f"   风险等级: {ai_result['summary']['risk_level']}")
    print(f"   推荐数: {ai_result['summary']['total_recommendations']}")
    print(f"   决策质量: {ai_result['summary']['decision_quality']}")

    # 导出
    if args.output:
        output = {
            'domain': domain,
            'review': result,
            'patterns': patterns,
            'ai_decision': ai_result,
            'timestamp': datetime.now().isoformat(),
        }
        Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
        print(f"\n💾 结果已保存到: {args.output}")


def cmd_doc(args):
    """文档生成命令"""
    from skills.documentation.doc_skill_v2 import DocumentationSkillV2

    doc_skill = DocumentationSkillV2({"output_dir": args.output_dir})

    print(f"📝 生成文档...")
    print(f"   领域: {args.domain}")
    print(f"   类型: {', '.join(args.doc_types)}")
    print(f"   输出: {args.output_dir}")

    result = doc_skill.run({
        "code_path": ".",
        "domain": args.domain,
        "doc_types": args.doc_types,
        "prd_content": args.prd_content or "",
    })

    if result.success:
        print(f"\n✅ 成功生成 {len(result.output.get('files_generated', []))} 个文档:")
        for f in result.output.get('files_generated', []):
            print(f"   - {Path(f).name}")
    else:
        print(f"\n❌ 生成失败: {result.errors}")


def cmd_quality(args):
    """质量门禁命令"""
    from scripts.quality_gate_cli import QualityGateCLI

    gate = QualityGateCLI()
    print(f"🏷️ 执行质量检查...")
    print(f"   路径: {args.path}")
    print(f"   严格模式: {args.strict}")

    result = gate.check(args.path, args.strict)

    print(f"\n📊 质量评分: {result['score']}/{result['max_score']}")
    print(f"   评级: {result['rating']}")
    print(f"   通过: {'✅' if result['passed'] else '❌'}")

    if args.html:
        report_path = gate.generate_html_report(result, f"{args.path}/quality_report.html")
        print(f"\n💾 HTML报告: {report_path}")


def cmd_cases(args):
    """案例浏览命令"""
    from scripts.case_learning_engine import CaseLearningEngine

    cases = CaseLearningEngine()
    print(f"📚 专家案例库")

    if args.domain:
        case_list = cases.list_cases(args.domain)
    else:
        case_list = cases.list_cases()

    print(f"   共 {len(case_list)} 个案例\n")

    for case in case_list:
        print(f"📋 {case.case_id} - {case.domain}")
        print(f"   摘要: {case.prd_summary[:60]}...")
        print(f"   结果: {case.outcome}")
        print(f"   质量: {case.quality_score}/100")
        if args.show_lessons and case.lessons:
            print(f"   经验:")
            for lesson in case.lessons[:3]:
                print(f"      - {lesson}")
        print()


def cmd_dashboard(args):
    """仪表盘命令"""
    from scripts.visualization_dashboard import VisualizationDashboard
    from scripts.quality_gate_cli import QualityGateCLI
    from datetime import datetime, timedelta

    gate = QualityGateCLI()
    history = gate.history[-100:] if hasattr(gate, 'history') else []

    dashboard = VisualizationDashboard(history)
    output = args.output or "./dashboard.html"

    print(f"📊 生成可视化仪表盘...")
    dashboard.generate_full_dashboard(output)
    print(f"✅ 仪表盘已生成: {output}")


def cmd_api(args):
    """启动API服务"""
    try:
        import uvicorn
        from api.server import app
        print(f"🚀 启动API服务...")
        print(f"   地址: http://{args.host}:{args.port}")
        print(f"   API文档: http://{args.host}:{args.port}/docs")
        uvicorn.run(app, host=args.host, port=args.port)
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print(f"   提示: pip install fastapi uvicorn")


def cmd_stats(args):
    """系统统计命令"""
    from scripts.expert_system import SeniorExpertSystem
    from scripts.case_learning_engine import CaseLearningEngine
    from scripts.performance_optimizer import get_optimizer

    expert = SeniorExpertSystem()
    cases = CaseLearningEngine()
    optimizer = get_optimizer()

    case_stats = cases.get_stats()
    opt_stats = optimizer.get_stats()

    print(f"📈 biz-delivery 系统统计")
    print(f"   领域覆盖: 15/15")
    print(f"   知识库文档: 34/34")
    print(f"   专家规则: 275+")
    print(f"   案例总数: {case_stats['total_cases']}")
    print(f"   成功率: {case_stats['success_rate']}")
    print(f"   缓存命中率: {opt_stats.get('hit_rate', '0%')}")
    print(f"   并行调用: {opt_stats.get('parallel_calls', 0)}")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        prog='biz',
        description='biz-delivery 端到端智能业务交付框架',
    )
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # review命令
    review_parser = subparsers.add_parser('review', help='PRD专家审查')
    review_parser.add_argument('prd_file', help='PRD文件路径')
    review_parser.add_argument('--domain', help='指定领域')
    review_parser.add_argument('--output', '-o', help='输出JSON文件')

    # doc命令
    doc_parser = subparsers.add_parser('doc', help='文档生成')
    doc_parser.add_argument('--domain', '-d', required=True, help='领域')
    doc_parser.add_argument('--doc-types', nargs='+', default=['readme'], help='文档类型')
    doc_parser.add_argument('--output-dir', default='/tmp/biz-docs', help='输出目录')
    doc_parser.add_argument('--prd', help='PRD内容文件')

    # quality命令
    quality_parser = subparsers.add_parser('quality', help='质量门禁检查')
    quality_parser.add_argument('path', help='项目路径')
    quality_parser.add_argument('--strict', action='store_true', help='严格模式')
    quality_parser.add_argument('--html', action='store_true', help='生成HTML报告')

    # cases命令
    cases_parser = subparsers.add_parser('cases', help='案例浏览')
    cases_parser.add_argument('--domain', help='按领域过滤')
    cases_parser.add_argument('--show-lessons', action='store_true', help='显示经验教训')

    # dashboard命令
    dashboard_parser = subparsers.add_parser('dashboard', help='生成仪表盘')
    dashboard_parser.add_argument('--output', '-o', help='输出文件路径')

    # api命令
    api_parser = subparsers.add_parser('api', help='启动API服务')
    api_parser.add_argument('--host', default='0.0.0.0')
    api_parser.add_argument('--port', type=int, default=8000)

    # stats命令
    stats_parser = subparsers.add_parser('stats', help='系统统计')

    args = parser.parse_args()

    if args.command == 'review':
        cmd_review(args)
    elif args.command == 'doc':
        cmd_doc(args)
    elif args.command == 'quality':
        cmd_quality(args)
    elif args.command == 'cases':
        cmd_cases(args)
    elif args.command == 'dashboard':
        cmd_dashboard(args)
    elif args.command == 'api':
        cmd_api(args)
    elif args.command == 'stats':
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
