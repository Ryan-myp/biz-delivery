"""
Expert PRD Reviewer - 专家级 PRD 审查 (规则引擎 + 知识库增强)
不使用 LLM，完全基于规则和知识库
"""
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


class ExpertPRDReviewer:
    """专家级 PRD 审查 - 规则引擎 + 知识库增强"""
    
    def __init__(self, knowledge_base=None):
        from skills.prd_review.review_skill_v2 import PRDReviewSkill
        self.rule_engine = PRDReviewSkill()
        self.kb = knowledge_base
        
        # 专家规则 (超出基础规则的深度检查)
        self.expert_rules = {
            'business_metrics': {
                'name': '业务指标量化',
                'pattern': r'(?i)(提升|降低|减少|增加|达到|>=|<=|>\s*\d+|%|倍|万|亿)',
                'severity': 'P1',
                'message': '建议补充量化业务指标 (如：转化率提升 X%)',
            },
            'rollback_plan': {
                'name': '回滚方案详细性',
                'pattern': r'(?i)(回滚|rollback|降级|fallback|应急|预案)',
                'severity': 'P1',
                'message': '回滚方案需包含具体操作步骤和验证点',
            },
            'data_migration': {
                'name': '数据迁移风险',
                'pattern': r'(?i)(迁移|migrate|数据同步|兼容|backward)',
                'severity': 'P1',
                'message': '数据迁移需考虑兼容性、回滚和验证方案',
            },
            'performance_baseline': {
                'name': '性能基准',
                'pattern': r'(?i)(性能|performance|QPS|延迟|latency|吞吐|throughput|P99|P95)',
                'severity': 'P1',
                'message': '需明确性能基准和监控指标',
            },
            'security_review': {
                'name': '安全审查',
                'pattern': r'(?i)(安全|security|权限|auth|加密|privacy|隐私|渗透|攻击)',
                'severity': 'P1',
                'message': '需包含安全审查和渗透测试计划',
            },
            'monitoring': {
                'name': '监控告警',
                'pattern': r'(?i)(监控|monitoring|告警|alert|观测|observability|trace)',
                'severity': 'P2',
                'message': '需定义监控维度和告警阈值',
            },
            'testing_strategy': {
                'name': '测试策略',
                'pattern': r'(?i)(测试|test|QA|验收|acceptance|用例|scenario)',
                'severity': 'P2',
                'message': '需明确测试策略和验收标准',
            },
            'stakeholder': {
                'name': '利益相关方',
                'pattern': r'(?i)(依赖|depend|collaborat|协同|对接|接口方)',
                'severity': 'P1',
                'message': '需明确依赖方和协同方',
            },
            'timeline_risk': {
                'name': '排期风险评估',
                'pattern': r'(?i)(排期|timeline|里程碑|milestone|deadline|上线|release)',
                'severity': 'P2',
                'message': '排期需考虑风险和缓冲时间',
            },
        }
    
    def review(self, prd_content: str) -> Dict[str, Any]:
        """执行专家级审查"""
        
        # Step 1: 规则引擎基础审查
        rule_result = self.rule_engine.run({'prd_content': prd_content})
        
        # Step 2: 知识库增强分析
        kb_analysis = self._knowledge_base_analysis(prd_content)
        
        # Step 3: 专家规则检查
        expert_issues = self._expert_rules_check(prd_content)
        
        # Step 4: 综合报告
        report = self._generate_report(rule_result, kb_analysis, expert_issues)
        
        return report
    
    def _knowledge_base_analysis(self, prd: str) -> Dict:
        """知识库增强分析"""
        if not self.kb:
            return {'recommendations': [], 'patterns': [], 'cases': []}
        
        analysis = {
            'recommendations': [],
            'patterns': [],
            'cases': [],
        }
        
        # 查询 PRD 最佳实践
        prd_results = self.kb.search("PRD 编写最佳实践", limit=3)
        if prd_results:
            analysis['recommendations'].append({
                'source': 'PRD最佳实践',
                'content': prd_results[0].get('preview', '')[:200],
            })
        
        # 查询技术架构模式
        arch_results = self.kb.search("技术方案设计", category="architecture", limit=3)
        if arch_results:
            analysis['patterns'].append({
                'source': '架构模式库',
                'pattern': arch_results[0].get('name', ''),
            })
        
        # 查询风险评估案例
        risk_results = self.kb.search("项目风险评估", limit=3)
        if risk_results:
            analysis['cases'].append({
                'source': '风险案例库',
                'case': risk_results[0].get('name', ''),
            })
        
        return analysis
    
    def _expert_rules_check(self, prd: str) -> List[Dict]:
        """专家规则检查"""
        issues = []
        
        for rule_name, rule in self.expert_rules.items():
            matches = list(re.finditer(rule['pattern'], prd))
            if not matches:
                # 规则未匹配，生成建议
                issues.append({
                    'rule': rule_name,
                    'severity': rule['severity'],
                    'name': rule['name'],
                    'message': rule['message'],
                    'suggestion': self._get_suggestion(rule_name),
                })
        
        return issues
    
    def _get_suggestion(self, rule_name: str) -> str:
        """获取具体建议"""
        suggestions = {
            'business_metrics': '补充量化指标：如转化率提升10%、响应时间<100ms、吞吐量>1000 QPS',
            'rollback_plan': '回滚方案应包含：回滚触发条件、具体操作步骤、数据恢复方案、验证清单',
            'data_migration': '数据迁移需考虑：兼容性、灰度策略、回滚机制、数据校验',
            'performance_baseline': '需明确：基准测试环境、核心指标、SLA承诺、压测方案',
            'security_review': '安全审查应覆盖：认证授权、数据安全、渗透测试、合规要求',
            'monitoring': '监控维度：业务指标、系统指标、日志追踪、告警分级',
            'testing_strategy': '测试策略：单元测试、集成测试、E2E测试、性能测试、安全测试',
            'stakeholder': '利益相关方：产品、研发、测试、运维、业务方、合规',
            'timeline_risk': '排期风险：缓冲时间、依赖风险、技术难点、人员变动',
        }
        return suggestions.get(rule_name, '请参考相关文档完善')
    
    def _generate_report(self, rule_result: Dict, kb_analysis: Dict, expert_issues: List) -> Dict:
        """生成专家报告"""
        # 统计问题
        all_issues = rule_result.get('output', {}).get('issues', []) + expert_issues
        p0 = [i for i in all_issues if i.get('severity') == 'P0']
        p1 = [i for i in all_issues if i.get('severity') == 'P1']
        p2 = [i for i in all_issues if i.get('severity') == 'P2']
        
        # 生成报告
        report_lines = [
            "# PRD 专家审查报告",
            "",
            "## 一、审查概览",
            "",
            f"- 🔴 P0 问题: {len(p0)} 个 (必须修复)",
            f"- 🟡 P1 问题: {len(p1)} 个 (建议修复)",
            f"- 🔵 P2 问题: {len(p2)} 个 (可选优化)",
            "",
        ]
        
        # 详细问题
        if all_issues:
            report_lines.append("## 二、详细问题")
            report_lines.append("")
            
            if p0:
                report_lines.append("### 🔴 P0 严重问题")
                for issue in p0:
                    report_lines.append(f"- **{issue.get('name')}**: {issue.get('message')}")
                report_lines.append("")
            
            if p1:
                report_lines.append("### 🟡 P1 重要问题")
                for issue in p1[:5]:
                    report_lines.append(f"- **{issue.get('name')}**: {issue.get('message')}")
                    if 'suggestion' in issue:
                        report_lines.append(f"  - 💡 建议: {issue['suggestion']}")
                report_lines.append("")
            
            if p2:
                report_lines.append("### 🔵 P2 优化建议")
                for issue in p2[:5]:
                    report_lines.append(f"- **{issue.get('name')}**: {issue.get('message')}")
                report_lines.append("")
        
        # 知识库建议
        if kb_analysis.get('recommendations'):
            report_lines.append("## 三、知识库最佳实践")
            report_lines.append("")
            for rec in kb_analysis['recommendations'][:3]:
                report_lines.append(f"### {rec['source']}")
                report_lines.append(f"{rec['content'][:300]}...")
                report_lines.append("")
        
        # 架构模式参考
        if kb_analysis.get('patterns'):
            report_lines.append("## 四、参考架构模式")
            report_lines.append("")
            for pattern in kb_analysis['patterns'][:3]:
                report_lines.append(f"- **{pattern['pattern']}** ({pattern['source']})")
            report_lines.append("")
        
        # 风险案例
        if kb_analysis.get('cases'):
            report_lines.append("## 五、风险案例参考")
            report_lines.append("")
            for case in kb_analysis['cases'][:3]:
                report_lines.append(f"- **{case['case']}** ({case['source']})")
            report_lines.append("")
        
        # 总结
        report_lines.append("## 六、总结与建议")
        report_lines.append("")
        
        if len(p0) > 0:
            report_lines.append("⚠️ **建议**: PRD 存在严重问题，需重新评审后再进入开发阶段。")
        elif len(p1) > 0:
            report_lines.append("✅ **建议**: PRD 基本合格，建议补充 P1 问题后再启动开发。")
        else:
            report_lines.append("✅ **建议**: PRD 质量良好，可以进入下一阶段。")
        
        report_lines.append("")
        report_lines.append(f"**审查时间**: {self._get_timestamp()}")
        report_lines.append(f"**规则引擎**: {len(rule_result.get('output', {}).get('issues', []))} 条规则")
        report_lines.append(f"**知识库**: {len(kb_analysis.get('recommendations', []))} 条建议")
        
        return {
            'success': len(p0) == 0,
            'p0_count': len(p0),
            'p1_count': len(p1),
            'p2_count': len(p2),
            'issues': all_issues,
            'kb_analysis': kb_analysis,
            'report': '\n'.join(report_lines),
        }
    
    def _get_timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='专家级 PRD 审查 (规则+知识库)')
    parser.add_argument('prd_file', help='PRD 文件路径')
    parser.add_argument('--output', '-o', help='输出文件')
    parser.add_argument('--kb-path', default='/Users/yanping.ma/ryan-personal-knowledge', 
                        help='知识库路径')
    args = parser.parse_args()
    
    # 加载知识库
    import sys
    sys.path.insert(0, '/Users/yanping.ma/biz-delivery')
    from scripts.ryan_knowledge_bridge import RyanKnowledgeBridge
    kb = RyanKnowledgeBridge(args.kb_path)
    
    # 读取 PRD
    with open(args.prd_file) as f:
        prd_content = f.read()
    
    # 执行审查
    reviewer = ExpertPRDReviewer(kb)
    report = reviewer.review(prd_content)
    
    # 输出报告
    print(report['report'])
    
    # 保存报告
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report['report'])
        print(f"\n报告已保存到: {args.output}")


if __name__ == '__main__':
    main()
