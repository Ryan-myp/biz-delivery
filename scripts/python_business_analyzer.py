#!/usr/bin/env python3
"""Python 项目业务语义分析器 — 从代码中提取项目定位、功能、架构、核心流程.

分析维度:
1. 项目定位 — 从 README、docstring、模块名推断
2. 主要功能 — 从 API 路由、类名、函数名提取
3. 架构组件 — 从目录结构、导入关系推断
4. 核心流程 — 从关键函数调用链追踪
"""

import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict


class PythonBusinessAnalyzer:
    """Python 项目业务语义分析器."""
    
    # 功能关键词映射
    FEATURE_KEYWORDS = {
        'video': ['video', 'avatar', 'sadtalker', 'digital_human', 'ai_video'],
        'voice': ['voice', 'clone', 'tts', 'audio', 'speech'],
        'chat': ['chat', 'conversation', 'assistant', 'llm', 'prompt'],
        'content': ['content', 'write', 'copywriting', 'article', 'blog', 'post'],
        'image': ['image', 'photo', 'picture', 'generate', 'edit'],
        'code': ['code', 'program', 'develop', 'debug', 'review', 'optimize'],
        'data': ['data', 'analyze', 'analytics', 'dashboard', 'report', 'forecast'],
        'social': ['social', 'share', 'post', 'publish', 'cross_post'],
        'ecommerce': ['order', 'billing', 'coupon', 'checkout', 'payment'],
        'admin': ['admin', 'portal', 'user', 'permission', 'auth'],
    }
    
    def __init__(self, project_path: str):
        self.path = Path(project_path)
        self.result = {
            'project_name': '',
            'description': '',
            'features': [],
            'modules': [],
            'architecture': {},
            'core_flows': [],
            'api_routes': [],
            'key_classes': [],
            'tech_stack': [],
        }
    
    def analyze(self) -> Dict:
        """执行完整分析."""
        self._extract_project_info()
        self._extract_features()
        self._extract_modules()
        self._extract_architecture()
        self._extract_api_routes()
        self._extract_key_classes()
        self._extract_tech_stack()
        self._infer_core_flows()
        return self.result
    
    def _extract_project_info(self):
        """从 README 和 main.py 提取项目信息."""
        # 1. 优先从 main.py docstring 提取
        main_py = self.path / 'main.py'
        if main_py.exists():
            text = main_py.read_text(errors='ignore')
            # 查找顶层 docstring
            doc_match = re.search(r'^"""(.+?)"""', text, re.DOTALL | re.MULTILINE)
            if doc_match:
                doc = doc_match.group(1).strip()
                lines = doc.split('\n')
                # 第一行非空且长度合适作为简介
                for line in lines:
                    line = line.strip()
                    if line and len(line) > 10 and len(line) < 200:
                        self.result['description'] = line
                        # 尝试提取项目名称
                        name_match = re.search(r'([A-Za-z][\w\s]*平台|Smart\s+\w+|[\w]+\s+Platform)', line, re.I)
                        if name_match:
                            self.result['project_name'] = name_match.group(1).strip()
                        break
        
        # 2. 查找 README
        if not self.result['project_name']:
            for readme in ['README.md', 'README', 'readme.md']:
                p = self.path.parent / readme  # 在项目根目录查找
                if p.exists():
                    text = p.read_text(errors='ignore')[:5000]
                    lines = text.split('\n')
                    for line in lines[:10]:
                        if line.startswith('# '):
                            self.result['project_name'] = line[2:].strip()
                            break
                    if self.result['project_name']:
                        break
        
        # 3. 从目录名推断
        if not self.result['project_name']:
            self.result['project_name'] = self.path.name.replace('_', '-').title()
        
        # 4. 从 pyproject.toml / setup.py 提取
        for config in ['pyproject.toml', 'setup.py', 'setup.cfg']:
            p = self.path.parent / config
            if p.exists():
                text = p.read_text(errors='ignore')[:2000]
                name_match = re.search(r'name\s*=\s*["\'](.+?)["\']', text)
                if name_match:
                    self.result['project_name'] = name_match.group(1)
                desc_match = re.search(r'description\s*=\s*["\'](.+?)["\']', text)
                if desc_match:
                    self.result['description'] = desc_match.group(1)[:200]
                break
    
    def _extract_features(self):
        """从文件结构和关键词提取功能列表."""
        features = set()
        
        # 分析 Python 文件名
        for py_file in self.path.rglob('*.py'):
            if '__pycache__' in str(py_file) or 'artifacts' in str(py_file):
                continue
            name = py_file.stem.lower()
            
            # 检查功能关键词
            for feature, keywords in self.FEATURE_KEYWORDS.items():
                for kw in keywords:
                    if kw in name:
                        features.add(feature)
                        break
        
        # 从 import 分析依赖功能
        for py_file in list(self.path.rglob('*.py'))[:100]:
            text = py_file.read_text(errors='ignore')[:3000]
            for feature, keywords in self.FEATURE_KEYWORDS.items():
                for kw in keywords:
                    if kw in text.lower() and feature not in features:
                        features.add(feature)
                        break
        
        self.result['features'] = sorted(list(features))
    
    def _extract_modules(self):
        """从目录结构提取模块."""
        modules = []
        
        # 直接子目录作为模块
        for d in self.path.iterdir():
            if d.is_dir() and d.name not in ['__pycache__', 'artifacts', '.pytest_cache', '.ruff_cache']:
                modules.append({
                    'name': d.name,
                    'type': 'directory',
                    'file_count': len(list(d.rglob('*.py'))),
                })
        
        # 顶层 Python 文件作为模块
        for f in self.path.glob('*.py'):
            if f.name not in ['main.py', 'conftest.py']:
                modules.append({
                    'name': f.stem,
                    'type': 'file',
                    'file_count': 1,
                })
        
        self.result['modules'] = sorted(modules, key=lambda x: -x['file_count'])[:20]
    
    def _extract_architecture(self):
        """分析架构组件."""
        arch = {
            'framework': 'unknown',
            'pattern': 'unknown',
            'components': [],
        }

        # 检测框架 - 扫描更多文件
        framework_found = False
        for py_file in list(self.path.rglob('*.py'))[:100]:
            if '__pycache__' in str(py_file):
                continue
            text = py_file.read_text(errors='ignore')
            text_lower = text.lower()
            if not framework_found:
                if 'fastapi' in text_lower:
                    arch['framework'] = 'fastapi'
                    framework_found = True
                elif 'flask' in text_lower:
                    arch['framework'] = 'flask'
                    framework_found = True
                elif 'django' in text_lower:
                    arch['framework'] = 'django'
                    framework_found = True

        # 检测架构模式
        has_celery = any('celery' in f.read_text(errors='ignore').lower()
                        for f in list(self.path.rglob('*.py'))[:50])
        has_redis = any('redis' in f.read_text(errors='ignore').lower()
                       for f in list(self.path.rglob('*.py'))[:50])
        has_sqlalchemy = any('sqlalchemy' in f.read_text(errors='ignore').lower()
                            for f in list(self.path.rglob('*.py'))[:50])
        has_asyncio = any('asyncio' in f.read_text(errors='ignore')
                         for f in list(self.path.rglob('*.py'))[:50])

        if has_celery:
            arch['pattern'] = 'celery_async'
            arch['components'].append({'name': 'Celery Worker', 'type': 'async_task'})
        if has_redis:
            arch['components'].append({'name': 'Redis', 'type': 'cache_queue'})
        if has_sqlalchemy:
            arch['components'].append({'name': 'SQLAlchemy', 'type': 'orm'})
        if has_asyncio:
            arch['components'].append({'name': 'AsyncIO', 'type': 'async_runtime'})

        # 检测数据库
        db_files = list(self.path.rglob('*database*.py')) + list(self.path.rglob('*db*.py'))
        if db_files or any('sqlite' in f.read_text(errors='ignore').lower()
                          for f in list(self.path.rglob('*.py'))[:30]):
            arch['components'].append({'name': 'Database', 'type': 'storage'})

        self.result['architecture'] = arch
    
    def _extract_api_routes(self):
        """提取所有 API 路由."""
        routes = []
        seen = set()
        
        for py_file in list(self.path.rglob('*.py'))[:100]:
            if '__pycache__' in str(py_file):
                continue
            text = py_file.read_text(errors='ignore')
            
            # 匹配 @router.get, @app.post 等
            for match in re.finditer(r'@(?:router|app)\.(get|post|put|delete|patch)\s*\(\s*"([^"]+)"', text):
                method = match.group(1).upper()
                path = match.group(2)
                key = f"{method}:{path}"
                if key not in seen:
                    seen.add(key)
                    routes.append({
                        'method': method,
                        'path': path,
                        'file': str(py_file.relative_to(self.path)),
                    })
        
        self.result['api_routes'] = sorted(routes, key=lambda x: x['path'])[:50]
    
    def _extract_key_classes(self):
        """提取关键类定义."""
        classes = []
        
        for py_file in list(self.path.rglob('*.py'))[:100]:
            if '__pycache__' in str(py_file):
                continue
            text = py_file.read_text(errors='ignore')
            
            for match in re.finditer(r'class\s+(\w+)', text):
                class_name = match.group(1)
                # 过滤常见的非业务类
                if class_name in ['BaseModel', 'Config', 'Settings', 'HTTPException']:
                    continue
                if class_name.startswith('_') or class_name.startswith('Test'):
                    continue
                
                # 找类文档字符串
                class_start = match.end()
                doc_match = re.search(r'""".*?"""', text[class_start:class_start+500], re.DOTALL)
                doc = doc_match.group(0).strip('"""').strip()[:100] if doc_match else ''
                
                classes.append({
                    'name': class_name,
                    'file': str(py_file.relative_to(self.path)),
                    'doc': doc,
                })
        
        self.result['key_classes'] = classes[:30]
    
    def _extract_tech_stack(self):
        """从 import 推断技术栈."""
        imports = defaultdict(int)
        
        for py_file in list(self.path.rglob('*.py'))[:50]:
            text = py_file.read_text(errors='ignore')
            for match in re.finditer(r'from\s+(\S+)\s+import|import\s+(\S+)', text):
                mod = match.group(1) or match.group(2)
                if mod and not mod.startswith('.'):
                    imports[mod.split('.')[0]] += 1
        
        tech_stack = []
        for mod, count in sorted(imports.items(), key=lambda x: -x[1])[:15]:
            if count >= 2:
                tech_stack.append({'module': mod, 'usage_count': count})
        
        self.result['tech_stack'] = tech_stack
    
    def _infer_core_flows(self):
        """推断核心业务流程."""
        flows = []
        
        # 从 API 路由推断流程
        post_routes = [r for r in self.result['api_routes'] if r['method'] == 'POST']
        
        # 分组相关路由
        flow_groups = defaultdict(list)
        for route in post_routes:
            path_parts = route['path'].split('/')
            if len(path_parts) >= 2:
                group = '/' + '/'.join(path_parts[:3])
                flow_groups[group].append(route)
        
        for group_path, routes in list(flow_groups.items())[:5]:
            flows.append({
                'name': f'{group_path} 流程',
                'description': f'包含 {len(routes)} 个 POST 接口',
                'routes': [r['path'] for r in routes[:3]],
            })
        
        # 从类方法推断
        for cls in self.result['key_classes'][:5]:
            if any(kw in cls['name'].lower() for kw in ['engine', 'service', 'manager', 'processor']):
                flows.append({
                    'name': f'{cls["name"]} 核心逻辑',
                    'description': cls.get('doc', '')[:100],
                    'file': cls['file'],
                })
        
        self.result['core_flows'] = flows[:10]


def analyze_python_project(project_path: str) -> Dict:
    """分析 Python 项目的业务语义."""
    analyzer = PythonBusinessAnalyzer(project_path)
    return analyzer.analyze()


def generate_business_summary(analysis: Dict) -> str:
    """生成业务摘要报告."""
    lines = [
        f"# 📊 {analysis.get('project_name', '项目')} 业务深度分析",
        "",
        f"**项目路径**: `{analysis.get('project_path', 'unknown')}`",
        f"**分析时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
    ]
    
    # 项目简介
    lines.append("## 一、项目定位")
    lines.append("")
    name = analysis.get('project_name', '未知项目')
    desc = analysis.get('description', '暂无描述')
    lines.append(f"### {name}")
    lines.append("")
    if desc:
        lines.append(f"**简介**: {desc}")
        lines.append("")
    
    # 主要功能
    features = analysis.get('features', [])
    if features:
        lines.append("## 二、主要功能")
        lines.append("")
        feature_desc = {
            'video': '🎬 AI 视频生成',
            'voice': '🔊 语音合成与克隆',
            'chat': '💬 AI 对话助手',
            'content': '✍️ 内容创作',
            'image': '🖼️ 图像处理',
            'code': '💻 代码辅助',
            'data': '📊 数据分析',
            'social': '📱 社交分享',
            'ecommerce': '🛒 电商交易',
            'admin': '👤 用户管理',
        }
        for feat in features:
            icon = feature_desc.get(feat, '📦')
            lines.append(f"- {icon} **{feat.capitalize()}**")
        lines.append("")
    
    # 架构组件
    arch = analysis.get('architecture', {})
    if arch.get('components'):
        lines.append("## 三、架构组件")
        lines.append("")
        lines.append(f"- **框架**: {arch.get('framework', 'unknown')}")
        lines.append(f"- **模式**: {arch.get('pattern', 'unknown')}")
        for comp in arch.get('components', []):
            lines.append(f"- **{comp['name']}** ({comp['type']})")
        lines.append("")
    
    # 核心模块
    modules = analysis.get('modules', [])
    if modules:
        lines.append("## 四、核心模块")
        lines.append("")
        for mod in modules[:10]:
            icon = "📁" if mod.get('type') == 'directory' else "📄"
            lines.append(f"- {icon} **{mod['name']}** ({mod.get('file_count', 0)} 文件)")
        lines.append("")
    
    # API 接口概览
    routes = analysis.get('api_routes', [])
    if routes:
        lines.append("## 五、API 接口概览")
        lines.append("")
        lines.append(f"共检测到 {len(routes)} 个 API 端点")
        lines.append("")
        lines.append("| 方法 | 路径 | 说明 |")
        lines.append("|------|------|------|")
        for r in routes[:15]:
            lines.append(f"| {r['method']} | `{r['path']}` | - |")
        lines.append("")
    
    # 核心流程
    flows = analysis.get('core_flows', [])
    if flows:
        lines.append("## 六、核心业务流程")
        lines.append("")
        for i, flow in enumerate(flows[:5], 1):
            lines.append(f"### {i}. {flow.get('name', '未命名流程')}")
            lines.append("")
            lines.append(flow.get('description', ''))
            lines.append("")
    
    # 技术栈
    stack = analysis.get('tech_stack', [])
    if stack:
        lines.append("## 七、技术栈")
        lines.append("")
        tech_names = [t['module'] for t in stack[:10]]
        lines.append(", ".join(tech_names))
        lines.append("")
    
    lines.append("---")
    lines.append("*Generated by biz-delivery Python Business Analyzer*")
    
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 python_business_analyzer.py <project_path>")
        sys.exit(1)
    
    analysis = analyze_python_project(sys.argv[1])
    summary = generate_business_summary(analysis)
    print(summary)
