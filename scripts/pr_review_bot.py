"""
GitHub/GitLab PR Review Bot - 自动化PR审查机器人
集成到CI/CD流程，自动审查代码变更

核心功能:
  1. 自动触发PR审查
  2. 领域识别与专家分析
  3. 代码质量评分
  4. 自动生成审查评论
  5. 质量门禁拦截
"""
import json
import os
import sys
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import re

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.expert_system import SeniorExpertSystem
from skills.code_review.code_review_skill_v2 import CodeReviewSkillV2
from scripts.performance_optimizer import get_optimizer


class PRReviewBot:
    """PR审查机器人"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.expert = SeniorExpertSystem()
        self.code_review = CodeReviewSkillV2()
        self.optimizer = get_optimizer()
        
        # GitHub/GitLab token
        self.token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GITLAB_TOKEN')
        self.repo = os.environ.get('REPO', '')
        self.pr_number = os.environ.get('PR_NUMBER', '')

    def analyze_pr(self, pr_data: Dict) -> Dict:
        """分析PR数据"""
        # 提取PR信息
        pr_title = pr_data.get('title', '')
        pr_body = pr_data.get('body', '')
        files = pr_data.get('files', [])
        
        # 合并PR描述和文件内容作为审查输入
        pr_content = f"# {pr_title}\n\n{pr_body}\n\n## Changed Files\n"
        for f in files:
            pr_content += f"\n### {f.get('filename', '')}\n"
            if f.get('patch'):
                pr_content += f["patch"][:2000]  # 限制长度

        # 检测领域
        domain = self.expert._detect_domain(pr_content)
        
        # 执行专家审查
        review_result = self.expert.review(pr_content, domain)
        
        # 执行代码审查
        code_result = self.code_review.run({
            "code_path": ".",
            "domain": domain.split('+')[0],
            "file_pattern": "*.go,*.py,*.java",
        })
        
        return {
            'domain': domain,
            'prd_review': review_result,
            'code_review': code_result,
            'files_changed': len(files),
            'timestamp': datetime.now().isoformat(),
        }

    def generate_review_comment(self, analysis: Dict) -> str:
        """生成审查评论"""
        lines = [
            "## 🎯 biz-delivery 自动化审查报告",
            "",
            f"**审查时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**识别领域**: {analysis['domain']}",
            f"**变更文件**: {analysis['files_changed']} 个",
            "",
            "---",
            "",
        ]
        
        # PRD审查结果
        prd = analysis.get('prd_review', {})
        if prd.get('analysis'):
            value = prd['analysis'].get('business_value', {})
            lines.extend([
                "## 📊 业务价值评估",
                "",
                f"- **评分**: {value.get('score', 0)}/100",
                f"- **目标用户**: {'✅ 已定义' if value.get('has_target_user') else '❌ 缺失'}",
                f"- **量化指标**: {'✅ 已定义' if value.get('has_quantified_metrics') else '❌ 缺失'}",
                "",
            ])
            
            # 风险
            risks = prd['analysis'].get('risk_assessment', [])
            if risks:
                lines.append("## ⚠️ 风险提醒")
                lines.append("")
                for risk in risks[:3]:
                    level = risk.get('level', '中')
                    icon = "🔴" if level == '高' else "🟡"
                    lines.append(f"- {icon} **{level}**: {risk.get('risk', '')}")
                lines.append("")
        
        # 代码审查结果
        code = analysis.get('code_review', {})
        if code.get('output'):
            issues = code['output'].get('issues', [])
            if issues:
                lines.extend([
                    "## 🔍 代码审查发现",
                    "",
                    f"- **问题总数**: {len(issues)}",
                    "",
                ])
                for issue in issues[:5]:
                    severity = issue.get('severity', 'P1')
                    icon = "🔴" if severity == 'P0' else "🟡" if severity == 'P1' else "🟢"
                    lines.append(f"- {icon} [{severity}] {issue.get('name', 'Issue')}")
                lines.append("")
        
        # 建议
        suggestions = prd.get('analysis', {}).get('optimization_suggestions', [])
        if suggestions:
            lines.extend([
                "## 💡 优化建议",
                "",
            ])
            for sug in suggestions[:3]:
                lines.append(f"- {sug.get('suggestion', '')}")
            lines.append("")
        
        # 结论
        lines.extend([
            "---",
            "",
            "> 由 [biz-delivery](https://github.com/ryan-myp/biz-delivery) 自动生成",
        ])
        
        return "\n".join(lines)

    def post_review_comment(self, repo: str, pr_number: int, comment: str) -> bool:
        """发布审查评论到PR"""
        # 这里需要实际的GitHub/GitLab API调用
        # 暂时返回模拟结果
        print(f"📝 发布审查评论到 {repo}#{pr_number}")
        print(f"   评论长度: {len(comment)} 字符")
        return True

    def check_quality_gate(self, analysis: Dict) -> Dict:
        """检查质量门禁"""
        score = 100
        deductions = []
        
        # PRD审查扣分
        prd = analysis.get('prd_review', {})
        p0_issues = prd.get('analysis', {}).get('p0_count', 0)
        if p0_issues > 0:
            deduction = p0_issues * 10
            score -= deduction
            deductions.append(f"PRD P0问题: -{deduction}")
        
        # 代码审查扣分
        code = analysis.get('code_review', {})
        p0_count = code.get('output', {}).get('p0_count', 0)
        if p0_count > 0:
            deduction = p0_count * 15
            score -= deduction
            deductions.append(f"代码P0问题: -{deduction}")
        
        # 计算评级
        if score >= 90:
            rating = 'A+'
        elif score >= 80:
            rating = 'A'
        elif score >= 70:
            rating = 'B+'
        elif score >= 60:
            rating = 'B'
        else:
            rating = 'C'
        
        return {
            'score': max(0, score),
            'rating': rating,
            'deductions': deductions,
            'passed': score >= 60,
        }


def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='biz-delivery PR Review Bot')
    parser.add_argument('action', choices=['analyze', 'comment', 'check'], help='执行动作')
    parser.add_argument('--pr-data', type=str, help='PR数据JSON文件')
    parser.add_argument('--repo', type=str, help='仓库名称')
    parser.add_argument('--pr-number', type=int, help='PR编号')
    
    args = parser.parse_args()
    
    bot = PRReviewBot()
    
    if args.action == 'analyze':
        # 读取PR数据
        if args.pr_data:
            with open(args.pr_data) as f:
                pr_data = json.load(f)
        else:
            pr_data = {
                'title': 'Test PR',
                'body': 'Test description',
                'files': [],
            }
        
        result = bot.analyze_pr(pr_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'comment':
        # 生成并发表评论
        comment = bot.generate_review_comment({
            'domain': 'advertising',
            'prd_review': {'analysis': {'business_value': {'score': 80}}},
            'code_review': {'output': {'issues': []}},
            'files_changed': 5,
        })
        print(comment)
    
    elif args.action == 'check':
        # 质量门禁检查
        result = bot.check_quality_gate({
            'prd_review': {'analysis': {'p0_count': 0}},
            'code_review': {'output': {'p0_count': 0}},
        })
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
