#!/usr/bin/env python3
"""Expert PRD Reviewer - 专家级 PRD 审查 (规则引擎 + LLM 增强)"""

import sys
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional


class ExpertPRDReviewer:
    """专家级 PRD 审查 - 规则引擎 + LLM 增强"""
    
    def __init__(self, llm_client=None):
        from skills.prd_review.review_skill_v2 import PRDReviewSkill
        self.rule_engine = PRDReviewSkill()
        self.llm = llm_client
    
    def review(self, prd_content: str, context: Dict = None) -> Dict:
        """执行专家级审查"""
        # Step 1: 规则引擎基础审查
        rule_result = self.rule_engine.run({'prd_content': prd_content})
        
        # Step 2: LLM 深度分析
        llm_analysis = self._llm_deep_analysis(prd_content, context)
        
        # Step 3: 综合报告
        report = self._generate_report(rule_result, llm_analysis)
        
        return report
    
    def _llm_deep_analysis(self, prd: str, context: Dict) -> str:
        """LLM 深度分析"""
        if not self.llm:
            return "[LLM未配置，跳过语义分析]\n\n请配置 AGNES_API_KEY 环境变量以获得专家级分析。"
        
        system_prompt = """你是一位资深产品专家和技术架构师，擅长从业务和技术双重视角分析 PRD。
你的分析应该体现：
1. 业务价值的深度理解
2. 技术可行性的专业判断
3. 风险预警的前瞻性
4. 方案优化的建设性"""
        
        user_prompt = f"""请从专家视角分析以下 PRD，重点关注：

1. **业务价值评估**
   - 目标用户是谁？解决什么痛点？
   - 商业价值如何量化？
   - 与现有系统的协同关系？

2. **技术可行性分析**
   - 当前架构是否支持？
   - 需要哪些技术储备？
   - 主要技术风险点？

3. **风险评估**
   - 上线风险
   - 数据迁移风险
   - 回滚预案充分性

4. **优化建议**
   - 架构优化建议
   - 性能优化空间
   - 成本控制建议

PRD内容：
{prd}

请以资深专家视角给出专业分析报告。"""
        
        try:
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ]
            result = self.llm.chat(messages, temperature=0.3, max_tokens=2000)
            return result.choices[0]['message']['content'] if result.choices else ''
        except Exception as e:
            return f"[LLM分析失败: {str(e)}]"
    
    def _generate_report(self, rule_result: Dict, llm_analysis: str) -> Dict:
        """生成综合报告"""
        issues = rule_result.get('output', {}).get('issues', [])
        
        return {
            'success': rule_result.success,
            'rule_issues': issues,
            'p0_count': rule_result.get('output', {}).get('p0_count', 0),
            'p1_count': rule_result.get('output', {}).get('p1_count', 0),
            'p2_count': rule_result.get('output', {}).get('p2_count', 0),
            'llm_analysis': llm_analysis,
            'expert_summary': self._summarize(issues, llm_analysis),
        }
    
    def _summarize(self, issues: List, llm_analysis: str) -> str:
        """生成专家摘要"""
        p0 = [i for i in issues if i.get('severity') == 'P0']
        p1 = [i for i in issues if i.get('severity') == 'P1']
        p2 = [i for i in issues if i.get('severity') == 'P2']
        
        lines = [
            "# PRD 专家审查报告",
            "",
            "## 一、基础检查",
            "",
            f"- 🔴 P0 问题: {len(p0)} 个",
            f"- 🟡 P1 问题: {len(p1)} 个",
            f"- 🔵 P2 问题: {len(p2)} 个",
            "",
        ]
        
        if p0:
            lines.append("## 二、P0 严重问题")
            lines.append("")
            for issue in p0:
                lines.append(f"- {issue.get('name')}: {issue.get('message')}")
            lines.append("")
        
        if p1:
            lines.append("## 三、P1 重要问题")
            lines.append("")
            for issue in p1[:5]:
                lines.append(f"- {issue.get('name')}: {issue.get('message')}")
            lines.append("")
        
        lines.append("## 四、LLM 深度分析")
        lines.append("")
        lines.append(llm_analysis if llm_analysis else "[LLM未配置]")
        
        return "\n".join(lines)


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='专家级 PRD 审查')
    parser.add_argument('prd_file', help='PRD 文件路径')
    parser.add_argument('--output', '-o', help='输出文件')
    args = parser.parse_args()
    
    # 加载 LLM 客户端
    api_key = None
    config_path = Path.home() / ".hermes" / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
        api_key = config.get('providers', {}).get('custom', {}).get('api_key', '')
    
    # 使用环境变量或默认key
    if not api_key:
        api_key = os.getenv('AGNES_API_KEY', 'sk-cDvao7SpHGLSGMXeIhydC0cyVPOO7Lgpdd2PkYtCv0LNcvgF')
    
    from scripts.llm_client import LLMClient
    llm_client = LLMClient(api_key=api_key)
    
    # 读取 PRD
    with open(args.prd_file) as f:
        prd_content = f.read()
    
    # 执行审查
    reviewer = ExpertPRDReviewer(llm_client)
    report = reviewer.review(prd_content)
    
    # 输出报告
    output = report['expert_summary']
    print(output)
    
    # 保存到文件
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"\n报告已保存到: {args.output}")


if __name__ == '__main__':
    main()
