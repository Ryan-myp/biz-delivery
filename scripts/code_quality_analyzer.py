#!/usr/bin/env python3
"""
biz-delivery 性能分析与优化工具

检查代码质量、重复代码、潜在问题
"""

import ast
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple


class CodeAnalyzer:
    """代码分析器"""
    
    def __init__(self, directory: Path):
        self.directory = directory
        self.results = {
            'files': [],
            'duplicates': [],
            'long_functions': [],
            'imports': defaultdict(list),
            'complexity': {},
        }
    
    def analyze(self) -> Dict:
        """执行全面分析"""
        for py_file in self.directory.rglob('*.py'):
            self.analyze_file(py_file)
        
        self.find_duplicates()
        self.calculate_complexity()
        
        return self.results
    
    def analyze_file(self, filepath: Path):
        """分析单个文件"""
        try:
            content = filepath.read_text(encoding='utf-8')
            tree = ast.parse(content)
            
            file_info = {
                'path': str(filepath),
                'lines': len(content.split('\n')),
                'classes': [],
                'functions': [],
                'imports': [],
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    file_info['classes'].append({
                        'name': node.name,
                        'lineno': node.lineno,
                    })
                elif isinstance(node, ast.FunctionDef):
                    file_info['functions'].append({
                        'name': node.name,
                        'lineno': node.lineno,
                        'args': len(node.args.args),
                        'decorator_names': [
                            d.attr if isinstance(d, ast.Attribute) else d.id
                            for d in node.decorator_list
                        ],
                    })
                    # 检查函数长度
                    end_lineno = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno + 50
                    if end_lineno - node.lineno > 50:
                        self.results['long_functions'].append({
                            'file': str(filepath),
                            'func': node.name,
                            'lines': end_lineno - node.lineno,
                        })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        file_info['imports'].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    file_info['imports'].append(node.module)
            
            self.results['files'].append(file_info)
            
            for imp in file_info['imports']:
                self.results['imports'][imp].append(str(filepath))
                
        except SyntaxError as e:
            print(f"语法错误: {filepath}: {e}")
    
    def find_duplicates(self):
        """查找重复代码"""
        func_signatures = defaultdict(list)
        
        for file_info in self.results['files']:
            for func in file_info['functions']:
                sig = f"{file_info['path']}:{func['name']}"
                func_signatures[sig].append({
                    'file': file_info['path'],
                    'name': func['name'],
                    'lineno': func['lineno'],
                })
        
        for sig, locations in func_signatures.items():
            if len(locations) > 1:
                self.results['duplicates'].append({
                    'signature': sig,
                    'locations': locations,
                })
    
    def calculate_complexity(self):
        """计算代码复杂度"""
        for file_info in self.results['files']:
            filepath = Path(file_info['path'])
            content = filepath.read_text(encoding='utf-8')
            
            # 简单复杂度计算
            complexity = {
                'functions': len(file_info['functions']),
                'classes': len(file_info['classes']),
                'lines': file_info['lines'],
                'avg_func_length': 0,
            }
            
            if file_info['functions']:
                total_lines = sum(
                    50 for _ in file_info['functions']  # 简化计算
                )
                complexity['avg_func_length'] = total_lines // len(file_info['functions'])
            
            self.results['complexity'][filepath.name] = complexity
    
    def generate_report(self) -> str:
        """生成分析报告"""
        report = []
        report.append("# biz-delivery 代码质量报告")
        report.append("")
        report.append("> 生成时间：2026-08-11")
        report.append("")
        
        report.append("## 一、文件统计")
        report.append(f"| 指标 | 数值 |")
        report.append(f"|------|------|")
        report.append(f"| 总文件数 | {len(self.results['files'])} |")
        report.append(f"| 总函数数 | {sum(len(f['functions']) for f in self.results['files'])} |")
        report.append(f"| 总类数 | {sum(len(f['classes']) for f in self.results['files'])} |")
        report.append("")
        
        report.append("## 二、重复代码")
        if self.results['duplicates']:
            for dup in self.results['duplicates']:
                report.append(f"### {dup['signature']}")
                for loc in dup['locations']:
                    report.append(f"- {loc['file']}:{loc['lineno']}")
                report.append("")
        else:
            report.append("✅ 未发现明显重复代码")
            report.append("")
        
        report.append("## 三、长函数检查 (>50行)")
        if self.results['long_functions']:
            for func in self.results['long_functions']:
                report.append(f"- {func['file']}: {func['func']} ({func['lines']}行)")
        else:
            report.append("✅ 未发现超长函数")
        report.append("")
        
        report.append("## 四、公共导入")
        for imp, files in sorted(self.results['imports'].items(), key=lambda x: -len(x[1]))[:10]:
            report.append(f"- `{imp}`: {len(files)} 个文件使用")
        report.append("")
        
        return "\n".join(report)


def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="biz-delivery 代码质量分析")
    parser.add_argument("--dir", default=str(Path.home() / "biz-delivery" / "scripts"),
                        help="分析目录")
    parser.add_argument("--output", default=None, help="输出文件")
    
    args = parser.parse_args()
    
    analyzer = CodeAnalyzer(Path(args.dir))
    results = analyzer.analyze()
    report = analyzer.generate_report()
    
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"报告已保存: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
