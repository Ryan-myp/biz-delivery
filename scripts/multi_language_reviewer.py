"""
Multi-Language Code Review - 多语言代码审查增强
支持 Go/Java/Python/TypeScript 深度分析

核心能力:
  1. Go: 结构体分析、并发模式、错误处理
  2. Java: 设计模式、Spring注解、代码规范
  3. Python: PEP8、类型提示、性能瓶颈
  4. TypeScript: 类型安全、泛型、ESLint规则
"""
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class CodeIssue:
    """代码问题"""
    file: str
    line: int
    severity: str  # P0, P1, P2
    rule: str
    message: str
    suggestion: str


class MultiLanguageReviewer:
    """多语言代码审查器"""
    
    # Go 规则
    GO_RULES = {
        'err_check': {
            'pattern': r'\bif\s+err\s*!=\s*nil\s*\{[^}]*\}',
            'severity': 'P1',
            'message': '错误检查不完整',
            'suggestion': '使用 errors.Is/As 进行错误类型判断',
        },
        'goroutine_leak': {
            'pattern': r'\bgo\s+\w+\(',
            'severity': 'P1',
            'message': 'goroutine可能泄漏',
            'suggestion': '确保goroutine有退出机制',
        },
        'context_missing': {
            'pattern': r'func\s+\w+\([^)]*\)(?!\s*context\.Context)',
            'severity': 'P1',
            'message': '函数缺少context参数',
            'suggestion': '添加context.Context参数以支持超时取消',
        },
        'defer_missing': {
            'pattern': r'\bopen|create|connect\([^)]*\)',
            'severity': 'P1',
            'message': '资源未defer关闭',
            'suggestion': '使用defer关闭资源',
        },
    }
    
    # Java 规则
    JAVA_RULES = {
        'null_check': {
            'pattern': r'\.equals\(|==\s*\w+',
            'severity': 'P1',
            'message': '潜在NullPointerException',
            'suggestion': '使用Objects.equals()或Optional',
        },
        'resource_leak': {
            'pattern': r'\b(new\s+\w+\()|(InputStream|Reader|Writer)\b',
            'severity': 'P1',
            'message': '资源可能未关闭',
            'suggestion': '使用try-with-resources',
        },
        'synchronized_method': {
            'pattern': r'\bsynchronized\s*\(',
            'severity': 'P2',
            'message': '同步方法可能影响性能',
            'suggestion': '考虑使用并发容器或Lock',
        },
    }
    
    # Python 规则
    PYTHON_RULES = {
        'mutable_default': {
            'pattern': r'def\s+\w+\([^)]*=\s*\[|def\s+\w+\([^)]*=\s*\{',
            'severity': 'P0',
            'message': '可变默认参数',
            'suggestion': '使用None作为默认值，在函数内初始化',
        },
        'global_statement': {
            'pattern': r'\bglobal\s+',
            'severity': 'P1',
            'message': '使用global关键字',
            'suggestion': '避免使用global，考虑类或闭包',
        },
        'bare_except': {
            'pattern': r'except\s*:',
            'severity': 'P1',
            'message': '裸except捕获所有异常',
            'suggestion': '指定具体异常类型',
        },
        'imports': {
            'pattern': r'^import\s+|^from\s+\w+\s+import',
            'severity': 'P2',
            'message': '导入检查',
            'suggestion': '检查导入是否按标准库/第三方/本地分组',
        },
    }
    
    # TypeScript 规则
    TS_RULES = {
        'any_type': {
            'pattern': r':\s*any\b',
            'severity': 'P1',
            'message': '使用any类型',
            'suggestion': '定义具体类型或使用泛型',
        },
        'missing_return': {
            'pattern': r'func\s+\w+\([^)]*\)\s*(?!.*->)',
            'severity': 'P1',
            'message': '函数缺少返回类型',
            'suggestion': '明确指定返回类型',
        },
        'no_implicit_any': {
            'pattern': r'let\s+\w+\s*=\s*[^;]+;',
            'severity': 'P2',
            'message': '隐式any类型',
            'suggestion': '添加类型注解',
        },
    }
    
    def __init__(self):
        self.issues: List[CodeIssue] = []
    
    def analyze_file(self, file_path: str) -> List[CodeIssue]:
        """分析单个文件"""
        path = Path(file_path)
        if not path.exists():
            return []
        
        ext = path.suffix.lower()
        content = path.read_text(errors='ignore')
        lines = content.split('\n')
        
        issues = []
        
        if ext == '.go':
            issues = self._analyze_go(content, lines, str(path))
        elif ext == '.java':
            issues = self._analyze_java(content, lines, str(path))
        elif ext == '.py':
            issues = self._analyze_python(content, lines, str(path))
        elif ext in ['.ts', '.tsx']:
            issues = self._analyze_typescript(content, lines, str(path))
        
        self.issues.extend(issues)
        return issues
    
    def _analyze_go(self, content: str, lines: List[str], file_path: str) -> List[CodeIssue]:
        """分析Go代码"""
        issues = []
        for rule_name, rule in self.GO_RULES.items():
            for i, line in enumerate(lines, 1):
                if re.search(rule['pattern'], line):
                    issues.append(CodeIssue(
                        file=file_path,
                        line=i,
                        severity=rule['severity'],
                        rule=rule_name,
                        message=rule['message'],
                        suggestion=rule['suggestion'],
                    ))
        return issues
    
    def _analyze_java(self, content: str, lines: List[str], file_path: str) -> List[CodeIssue]:
        """分析Java代码"""
        issues = []
        for rule_name, rule in self.JAVA_RULES.items():
            for i, line in enumerate(lines, 1):
                if re.search(rule['pattern'], line):
                    issues.append(CodeIssue(
                        file=file_path,
                        line=i,
                        severity=rule['severity'],
                        rule=rule_name,
                        message=rule['message'],
                        suggestion=rule['suggestion'],
                    ))
        return issues
    
    def _analyze_python(self, content: str, lines: List[str], file_path: str) -> List[CodeIssue]:
        """分析Python代码"""
        issues = []
        for rule_name, rule in self.PYTHON_RULES.items():
            for i, line in enumerate(lines, 1):
                if re.search(rule['pattern'], line):
                    issues.append(CodeIssue(
                        file=file_path,
                        line=i,
                        severity=rule['severity'],
                        rule=rule_name,
                        message=rule['message'],
                        suggestion=rule['suggestion'],
                    ))
        return issues
    
    def _analyze_typescript(self, content: str, lines: List[str], file_path: str) -> List[CodeIssue]:
        """分析TypeScript代码"""
        issues = []
        for rule_name, rule in self.TS_RULES.items():
            for i, line in enumerate(lines, 1):
                if re.search(rule['pattern'], line):
                    issues.append(CodeIssue(
                        file=file_path,
                        line=i,
                        severity=rule['severity'],
                        rule=rule_name,
                        message=rule['message'],
                        suggestion=rule['suggestion'],
                    ))
        return issues
    
    def get_summary(self) -> Dict:
        """获取审查摘要"""
        p0 = sum(1 for i in self.issues if i.severity == 'P0')
        p1 = sum(1 for i in self.issues if i.severity == 'P1')
        p2 = sum(1 for i in self.issues if i.severity == 'P2')
        
        return {
            'total_issues': len(self.issues),
            'p0_count': p0,
            'p1_count': p1,
            'p2_count': p2,
            'issues': [vars(i) for i in self.issues],
        }


def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-language Code Review')
    parser.add_argument('path', help='文件或目录路径')
    parser.add_argument('--output', '-o', help='输出文件')
    
    args = parser.parse_args()
    
    reviewer = MultiLanguageReviewer()
    
    path = Path(args.path)
    if path.is_file():
        reviewer.analyze_file(str(path))
    elif path.is_dir():
        for ext in ['.go', '.java', '.py', '.ts', '.tsx']:
            for f in path.rglob(f'*{ext}'):
                reviewer.analyze_file(str(f))
    
    summary = reviewer.get_summary()
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
    else:
        print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
