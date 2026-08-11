#!/usr/bin/env python3
"""
深度迭代优化总结报告
"""

import json
from pathlib import Path
from datetime import datetime


def generate_summary():
    kb_path = Path.home() / 'ryan-personal-knowledge' / 'knowledge'
    
    # 统计文件
    files = list(kb_path.rglob('*.md'))
    total_files = len(files)
    
    expert = []
    deep = []
    template_count = 0
    
    for f in files:
        content = f.read_text(encoding='utf-8', errors='ignore')
        lines = len(content.split('\n'))
        
        is_template = 'func ExampleFunc' in content or '这是关于' in content
        
        if lines >= 1000:
            expert.append((str(f.relative_to(kb_path)), lines, is_template))
            if is_template:
                template_count += 1
        elif lines >= 500:
            deep.append((str(f.relative_to(kb_path)), lines))
    
    # 统计实战案例
    combat_count = 0
    for f in files:
        content = f.read_text(encoding='utf-8', errors='ignore').lower()
        if any(kw in content for kw in ['实战', '案例', '排障', '故障', '优化', '生产']):
            combat_count += 1
    
    # 统计代码块
    code_block_count = 0
    for f in files:
        content = f.read_text(encoding='utf-8', errors='ignore')
        if '```' in content:
            code_block_count += 1
    
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_files': total_files,
        'expert_count': len(expert),
        'expert_target': 150,
        'expert_rate': f'{len(expert)/150*100:.1f}%',
        'deep_count': len(deep),
        'deep_target': 250,
        'deep_rate': f'{len(deep)/250*100:.1f}%',
        'template_count': template_count,
        'real_source_level': len(expert) - template_count,
        'combat_ratio': f'{combat_count/total_files*100:.1f}%',
        'code_block_coverage': f'{code_block_count/total_files*100:.1f}%',
        'total_lines': sum(e[1] for e in expert) + sum(d[1] for d in deep),
        'ads_files': 14,  # 本次新增的广告领域文件
    }
    
    # 保存报告
    output_path = Path.home() / '.hermes' / 'scripts' / 'reports' / 'kb-evolution-summary.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    
    print(f"📊 知识库深度迭代优化完成")
    print(f"  总文件数: {total_files}")
    print(f"  专家级: {len(expert)} / 150 ({summary['expert_rate']})")
    print(f"  深度: {len(deep)} / 250 ({summary['deep_rate']})")
    print(f"  真实源码级: {summary['real_source_level']} / {len(expert)}")
    print(f"  实战案例占比: {summary['combat_ratio']}")
    print(f"  代码块覆盖率: {summary['code_block_coverage']}")
    print(f"  广告领域新增: {summary['ads_files']} 个文件")
    print(f"\n报告已保存: {output_path}")
    
    return summary


if __name__ == '__main__':
    generate_summary()
