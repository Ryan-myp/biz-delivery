"""
Quality Gate CLI - 质量门禁命令行工具
支持 CI/CD 集成、HTML 报告生成、质量趋势追踪

核心功能:
  1. CLI 质量检查
  2. HTML 报告生成
  3. JSON 指标导出
  4. 质量门禁配置
  5. 趋势追踪
"""
import json
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import html


class QualityGateCLI:
    """质量门禁 CLI"""

    # 质量阈值配置
    THRESHOLDS = {
        'A_PLUS': 90,
        'A': 80,
        'B_PLUS': 70,
        'B': 60,
        'C': 0,
    }

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.history_file = Path(self.config.get('history_file', './.quality_history.json'))
        self.history = self._load_history()

    def _load_history(self) -> List[Dict]:
        """加载历史质量数据"""
        if self.history_file.exists():
            try:
                return json.loads(self.history_file.read_text())
            except:
                return []
        return []

    def _save_history(self):
        """保存历史质量数据"""
        self.history_file.write_text(json.dumps(self.history, indent=2, ensure_ascii=False))

    def check(self, output_dir: str, strict: bool = False) -> Dict:
        """执行质量检查"""
        checks = {
            'result_file': {'name': '分析结果文件', 'weight': 10},
            'summary_file': {'name': '摘要文件', 'weight': 10},
            'td_file': {'name': '技术方案', 'weight': 15},
            'test_cases': {'name': '测试用例', 'weight': 10},
            'code_review': {'name': '代码审查', 'weight': 15},
            'no_critical_issues': {'name': '无严重问题', 'weight': 20},
            'domain_coverage': {'name': '领域覆盖', 'weight': 10},
            'knowledge_base': {'name': '知识库引用', 'weight': 10},
        }

        result = {
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'score': 0,
            'max_score': sum(c['weight'] for c in checks.values()),
            'passed': False,
        }

        output_path = Path(output_dir)

        # 执行检查
        for check_name, check_info in checks.items():
            passed, detail = self._perform_check(check_name, output_path)
            result['checks'][check_name] = {
                'passed': passed,
                'detail': detail,
                'weight': check_info['weight'],
            }
            if passed:
                result['score'] += check_info['weight']

        # 计算评级
        percentage = int(result['score'] / result['max_score'] * 100)
        result['percentage'] = percentage
        result['rating'] = self._get_rating(percentage)
        result['passed'] = percentage >= (70 if strict else 60)

        # 保存到历史
        self.history.append({
            'timestamp': result['timestamp'],
            'score': result['score'],
            'max_score': result['max_score'],
            'percentage': percentage,
            'rating': result['rating'],
            'passed': result['passed'],
        })
        self._save_history()

        return result

    def _perform_check(self, check_name: str, output_path: Path) -> tuple:
        """执行单个检查"""
        try:
            if check_name == 'result_file':
                exists = (output_path / 'analysis_result.json').exists()
                return exists, '结果文件' if exists else '缺少结果文件'

            elif check_name == 'summary_file':
                exists = (output_path / 'summary.md').exists()
                return exists, '摘要文件' if exists else '缺少摘要文件'

            elif check_name == 'td_file':
                exists = (output_path / 'tech_design.md').exists()
                return exists, '技术方案' if exists else '缺少技术方案'

            elif check_name == 'test_cases':
                exists = (output_path / 'test_cases').exists() or \
                         any(f.startswith('test_') for f in output_path.glob('*test*'))
                return exists, '测试用例目录' if exists else '缺少测试用例'

            elif check_name == 'code_review':
                exists = (output_path / 'code_review_result.json').exists()
                return exists, '代码审查结果' if exists else '缺少代码审查'

            elif check_name == 'no_critical_issues':
                # 检查是否有 P0 问题
                result_file = output_path / 'analysis_result.json'
                if result_file.exists():
                    data = json.loads(result_file.read_text())
                    issues = data.get('issues', [])
                    p0_count = sum(1 for i in issues if i.get('severity') == 'P0')
                    return p0_count == 0, f'{p0_count} 个 P0 问题'
                return True, '无结果文件，跳过检查'

            elif check_name == 'domain_coverage':
                # 检查领域覆盖率
                result_file = output_path / 'analysis_result.json'
                if result_file.exists():
                    data = json.loads(result_file.read_text())
                    feasibility = data.get('analysis', {}).get('technical_feasibility', {})
                    coverage = feasibility.get('coverage_rate', 0)
                    return coverage >= 0.7, f'覆盖率 {coverage:.0%}'
                return True, '无结果文件，跳过检查'

            elif check_name == 'knowledge_base':
                # 检查知识库引用
                result_file = output_path / 'analysis_result.json'
                if result_file.exists():
                    data = json.loads(result_file.read_text())
                    suggestions = data.get('analysis', {}).get('optimization_suggestions', [])
                    has_kb = any(s.get('reference') for s in suggestions)
                    return has_kb, '有知识库引用' if has_kb else '缺少知识库引用'
                return True, '无结果文件，跳过检查'

            return True, '未知检查项'

        except Exception as e:
            return False, f'检查异常: {str(e)}'

    def _get_rating(self, percentage: int) -> str:
        """获取评级"""
        if percentage >= 90:
            return 'A+'
        elif percentage >= 80:
            return 'A'
        elif percentage >= 70:
            return 'B+'
        elif percentage >= 60:
            return 'B'
        else:
            return 'C'

    def generate_html_report(self, result: Dict, output_path: str) -> str:
        """生成 HTML 报告"""
        checks_html = ''
        for check_name, check_data in result['checks'].items():
            icon = '✅' if check_data['passed'] else '❌'
            checks_html += f'''
            <tr>
                <td>{icon}</td>
                <td>{check_data['detail']}</td>
                <td>{check_data['weight']}</td>
                <td>{'通过' if check_data['passed'] else '失败'}</td>
            </tr>'''

        rating_color = {
            'A+': '#28a745', 'A': '#20c997', 'B+": '#17a2b8',
            'B': '#ffc107', 'C': '#dc3545'
        }.get(result['rating'], '#6c757d')

        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>质量门禁报告</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid {rating_color}; padding-bottom: 10px; }}
        .score {{ font-size: 48px; font-weight: bold; color: {rating_color}; text-align: center; margin: 20px 0; }}
        .rating {{ font-size: 24px; text-align: center; color: {rating_color}; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; }}
        .passed {{ color: #28a745; }}
        .failed {{ color: #dc3545; }}
        .footer {{ margin-top: 30px; color: #666; font-size: 12px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 质量门禁报告</h1>
        <div class="score">{result['score']}/{result['max_score']}</div>
        <div class="rating">评级: {result['rating']} ({result['percentage']}%)</div>
        <div style="text-align: center; margin: 10px 0;">
            {'<span class="passed">✅ 通过</span>' if result['passed'] else '<span class="failed">❌ 不通过</span>'}
        </div>
        <h2>检查项详情</h2>
        <table>
            <tr><th>状态</th><th>检查项</th><th>权重</th><th>结果</th></tr>
            {checks_html}
        </table>
        <div class="footer">
            生成时间: {result['timestamp']} | biz-delivery Quality Gate v2.0
        </div>
    </div>
</body>
</html>'''

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html_content, encoding='utf-8')
        return str(output_file)

    def generate_json_report(self, result: Dict, output_path: str) -> str:
        """生成 JSON 报告"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        return str(output_file)

    def get_trend(self, days: int = 7) -> Dict:
        """获取质量趋势"""
        cutoff = datetime.now().timestamp() - days * 86400
        recent = [h for h in self.history if datetime.fromisoformat(h['timestamp']).timestamp() > cutoff]
        
        if not recent:
            return {'trend': 'no_data', 'checks': []}
        
        scores = [h['percentage'] for h in recent]
        trend = 'stable'
        if len(scores) >= 2:
            if scores[-1] > scores[0]:
                trend = 'improving'
            elif scores[-1] < scores[0]:
                trend = 'declining'
        
        return {
            'trend': trend,
            'period_days': days,
            'checks_count': len(recent),
            'avg_score': sum(scores) / len(scores),
            'min_score': min(scores),
            'max_score': max(scores),
            'latest': recent[-1] if recent else None,
        }


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(description='biz-delivery Quality Gate')
    parser.add_argument('command', choices=['check', 'report', 'trend'], help='命令')
    parser.add_argument('--output-dir', '-o', default='./output', help='输出目录')
    parser.add_argument('--format', '-f', choices=['html', 'json', 'text'], default='text', help='输出格式')
    parser.add_argument('--strict', action='store_true', help='严格模式')
    parser.add_argument('--days', type=int, default=7, help='趋势查询天数')
    
    args = parser.parse_args()
    
    gate = QualityGateCLI()
    
    if args.command == 'check':
        result = gate.check(args.output_dir, args.strict)
        
        if args.format == 'html':
            report_path = gate.generate_html_report(result, f'{args.output_dir}/quality_report.html')
            print(f'HTML 报告已生成: {report_path}')
        elif args.format == 'json':
            report_path = gate.generate_json_report(result, f'{args.output_dir}/quality_report.json')
            print(f'JSON 报告已生成: {report_path}')
        else:
            print(f'\n质量门禁结果:')
            print(f'  得分: {result["score"]}/{result["max_score"]} ({result["percentage"]}%)')
            print(f'  评级: {result["rating"]}')
            print(f'  状态: {"✅ 通过" if result["passed"] else "❌ 不通过"}')
            print(f'\n检查项:')
            for name, data in result['checks'].items():
                icon = '✅' if data['passed'] else '❌'
                print(f'  {icon} {data["detail"]} ({data["weight"]}分)')
    
    elif args.command == 'report':
        result = gate.check(args.output_dir, args.strict)
        if args.format == 'html':
            report_path = gate.generate_html_report(result, f'{args.output_dir}/quality_report.html')
            print(f'报告已生成: {report_path}')
        elif args.format == 'json':
            report_path = gate.generate_json_report(result, f'{args.output_dir}/quality_report.json')
            print(f'报告已生成: {report_path}')
    
    elif args.command == 'trend':
        trend = gate.get_trend(args.days)
        print(f'\n质量趋势 (最近 {args.days} 天):')
        print(f'  趋势: {trend["trend"]}')
        print(f'  检查次数: {trend["checks_count"]}')
        print(f'  平均分数: {trend["avg_score"]:.1f}')
        print(f'  最低分数: {trend["min_score"]}')
        print(f'  最高分数: {trend["max_score"]}')
        if trend.get('latest'):
            print(f'  最新: {trend["latest"]["rating"]} ({trend["latest"]["percentage"]}%)\n')


if __name__ == '__main__':
    main()
