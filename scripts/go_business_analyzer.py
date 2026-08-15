#!/usr/bin/env python3
"""Go 项目业务语义分析器 — 从代码中提取项目定位、功能、架构、核心流程.

分析维度:
1. 项目定位 — 从 README、main.go、package 注释推断
2. 主要功能 — 从路由、handler 名、proto 文件提取
3. 架构组件 — 从目录结构、import 关系推断
4. 核心流程 — 从入口函数调用链追踪
"""

import re
from pathlib import Path
from typing import Dict, List
from collections import defaultdict


class GoBusinessAnalyzer:
    """Go 项目业务语义分析器."""
    
    # 功能关键词映射 - 使用更精确的关键词避免误判
    FEATURE_KEYWORDS = {
        'ads': ['advertising', 'campaign', 'adgroup', 'creative', 'bid', 'rtb', 'dsp', 'ssp'],
        'video': ['video', 'avatar', 'sadtalker', 'digital_human', 'media', 'streaming'],
        'voice': ['voice', 'audio', 'tts', 'speech', 'sound', 'clone'],
        'data': ['data', 'analytics', 'report', 'dashboard', 'metric', 'statistics'],
        'user': ['user', 'account', 'auth', 'permission', 'profile', 'rbac'],
        'order': ['order', 'billing', 'payment', 'invoice', 'transaction', 'checkout'],
        'search': ['search', 'query', 'index', 'discover', 'elasticsearch'],
        'mq': ['kafka', 'rabbitmq', 'message', 'queue', 'event', 'pubsub'],
        'task': ['task', 'job', 'worker', 'scheduler', 'cron', 'workflow'],
        'ai': ['ai', 'llm', 'gpt', 'claude', 'prompt', 'embedding', 'rag'],
        'framework': ['eino', 'gin', 'fiber', 'echo', 'spex', 'kitex'],
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
            'entry_points': [],
            'tech_stack': [],
        }
    
    def analyze(self) -> Dict:
        """执行完整分析."""
        self._extract_project_info()
        self._extract_features()
        self._extract_modules()
        self._extract_architecture()
        self._extract_entry_points()
        self._infer_core_flows()
        return self.result
    
    def _extract_project_info(self):
        """从 README 和 main.go 提取项目信息."""
        # 查找 README
        for readme in ['README.md', 'README', 'readme.md']:
            p = self.path / readme
            if not p.exists():
                p = self.path.parent / readme
            if p.exists():
                text = p.read_text(errors='ignore')[:5000]
                lines = text.split('\n')
                for line in lines[:10]:
                    if line.startswith('# '):
                        self.result['project_name'] = line[2:].strip()
                        break
                for line in lines:
                    if line.startswith('##') or line.startswith('###'):
                        break
                    if line and not line.startswith('#') and len(line) > 20:
                        self.result['description'] = line.strip()[:200]
                        break
                if self.result['project_name'] or self.result['description']:
                    break
        
        # 从 go.mod 提取
        go_mod = self.path / 'go.mod'
        if go_mod.exists():
            text = go_mod.read_text(errors='ignore')
            mod_match = re.search(r'module\s+(\S+)', text)
            if mod_match:
                module_path = mod_match.group(1)
                if not self.result['project_name']:
                    self.result['project_name'] = module_path.split('/')[-1]
        
        # 从 main.go 注释提取
        main_go = self.path / 'main.go'
        if not main_go.exists():
            main_go = next(self.path.rglob('cmd/*/main.go'), None)
        if main_go and main_go.exists():
            text = main_go.read_text(errors='ignore')[:2000]
            # 查找包级注释
            comment_match = re.search(r'//\s*(.+)', text)
            if comment_match:
                desc = comment_match.group(1).strip()
                if desc and len(desc) > 10:
                    self.result['description'] = desc[:200]
        
        # 从目录名推断
        if not self.result['project_name']:
            self.result['project_name'] = self.path.name.replace('_', '-').lower()
    
    def _extract_features(self):
        """从代码提取功能列表."""
        features = set()
        
        # 分析 Go 文件名
        for go_file in list(self.path.rglob('*.go'))[:200]:
            if '__pycache__' in str(go_file) or 'vendor/' in str(go_file):
                continue
            name = go_file.stem.lower()
            
            for feature, keywords in self.FEATURE_KEYWORDS.items():
                for kw in keywords:
                    if kw in name:
                        features.add(feature)
                        break
        
        # 从代码内容分析
        for go_file in list(self.path.rglob('*.go'))[:100]:
            if 'vendor/' in str(go_file) or '_test.go' in str(go_file):
                continue
            text = go_file.read_text(errors='ignore')[:3000]
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
            if d.is_dir() and d.name not in ['vendor', '.git', 'node_modules']:
                go_count = len(list(d.rglob('*.go')))
                if go_count > 0:
                    modules.append({
                        'name': d.name,
                        'type': 'directory',
                        'file_count': go_count,
                    })
        
        self.result['modules'] = sorted(modules, key=lambda x: -x['file_count'])[:15]
    
    def _extract_architecture(self):
        """分析架构组件."""
        arch = {
            'framework': 'unknown',
            'pattern': 'unknown',
            'components': [],
        }
        
        # 检测框架
        framework_found = False
        for go_file in list(self.path.rglob('*.go'))[:100]:
            if 'vendor/' in str(go_file):
                continue
            text = go_file.read_text(errors='ignore')
            text_lower = text.lower()
            if not framework_found:
                if 'spex' in text_lower or 'spexprocessor' in text:
                    arch['framework'] = 'spex'
                    framework_found = True
                elif 'gin' in text_lower and 'github.com/gin-gonic' in text:
                    arch['framework'] = 'gin'
                    framework_found = True
                elif 'fiber' in text_lower:
                    arch['framework'] = 'fiber'
                    framework_found = True
                elif 'echo' in text_lower and 'labstack/echo' in text:
                    arch['framework'] = 'echo'
                    framework_found = True
        
        # 检测架构模式
        has_kafka = any('kafka' in f.read_text(errors='ignore').lower()
                       for f in list(self.path.rglob('*.go'))[:50])
        has_redis = any('redis' in f.read_text(errors='ignore').lower()
                       for f in list(self.path.rglob('*.go'))[:50])
        has_gorm = any('gorm' in f.read_text(errors='ignore').lower()
                      for f in list(self.path.rglob('*.go'))[:50])
        has_grpc = any('grpc' in f.read_text(errors='ignore').lower()
                      for f in list(self.path.rglob('*.go'))[:30])
        
        if has_kafka:
            arch['pattern'] = 'event_driven'
            arch['components'].append({'name': 'Kafka', 'type': 'message_queue'})
        if has_redis:
            arch['components'].append({'name': 'Redis', 'type': 'cache'})
        if has_gorm:
            arch['components'].append({'name': 'GORM', 'type': 'orm'})
        if has_grpc:
            arch['components'].append({'name': 'gRPC', 'type': 'rpc'})
            arch['pattern'] = 'microservice'
        
        self.result['architecture'] = arch
    
    def _extract_entry_points(self):
        """提取入口点."""
        entries = []
        
        # 找 main.go
        for main_go in list(self.path.rglob('main.go'))[:20]:
            if 'vendor/' in str(main_go) or '.git/' in str(main_go):
                continue
            rel = str(main_go.relative_to(self.path))
            entries.append({
                'name': 'main',
                'file': rel,
                'type': 'entry_point',
            })
        
        # 找 cmd 目录
        for cmd_dir in list(self.path.rglob('cmd'))[:10]:
            rel = str(cmd_dir.relative_to(self.path))
            entries.append({
                'name': rel.split('/')[-1],
                'file': rel + '/main.go',
                'type': 'command',
            })
        
        self.result['entry_points'] = entries[:10]
    
    def _infer_core_flows(self):
        """推断核心业务流程."""
        flows = []
        
        # 从 handler 函数推断
        handler_funcs = []
        for go_file in list(self.path.rglob('*.go'))[:100]:
            if 'vendor/' in str(go_file):
                continue
            text = go_file.read_text(errors='ignore')
            # 找 HTTP handler
            for match in re.finditer(r'func\s+(\w+)\s*\(', text):
                func_name = match.group(1)
                if func_name[0].isupper() and len(func_name) > 3:
                    handler_funcs.append({
                        'name': func_name,
                        'file': str(go_file.relative_to(self.path)),
                    })
        
        # 分组相关 handler
        flow_groups = defaultdict(list)
        for hf in handler_funcs[:30]:
            # 按前缀分组
            prefix = hf['name'][:3].lower()
            flow_groups[prefix].append(hf)
        
        for prefix, funcs in list(flow_groups.items())[:5]:
            flows.append({
                'name': f'{prefix.upper()} 相关业务',
                'description': f'包含 {len(funcs)} 个业务函数',
                'functions': [f['name'] for f in funcs[:3]],
            })
        
        # 从目录结构推断流程
        for module in self.result['modules'][:3]:
            if module['file_count'] > 5:
                flows.append({
                    'name': f'{module["name"]} 模块流程',
                    'description': f'核心模块，{module["file_count"]} 个 Go 文件',
                })
        
        self.result['core_flows'] = flows[:8]


def analyze_go_project(project_path: str) -> Dict:
    """分析 Go 项目的业务语义."""
    analyzer = GoBusinessAnalyzer(project_path)
    return analyzer.analyze()


def generate_go_business_summary(analysis: Dict) -> str:
    """生成 Go 项目业务摘要报告."""
    lines = [
        f"# 📊 {analysis.get('project_name', '项目')} 业务深度分析",
        "",
        f"**项目路径**: `{analysis.get('project_path', 'unknown')}`",
        "",
        "---",
        "",
    ]
    
    # 项目简介
    lines.append("## 一、项目定位")
    lines.append("")
    name = analysis.get('project_name', '未知项目')
    desc = analysis.get('description', '')
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
            'ads': '📢 广告投放',
            'video': '🎬 视频处理',
            'voice': '🔊 语音处理',
            'data': '📊 数据分析',
            'user': '👤 用户管理',
            'order': '💰 订单交易',
            'search': '🔍 搜索查询',
            'mq': '📨 消息队列',
            'task': '⚙️ 任务调度',
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
    
    # 入口点
    entries = analysis.get('entry_points', [])
    if entries:
        lines.append("## 五、入口点")
        lines.append("")
        for entry in entries[:5]:
            lines.append(f"- `{entry['file']}` ({entry['type']})")
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
            if 'functions' in flow:
                lines.append(f"关键函数: {', '.join(flow['functions'][:3])}")
            lines.append("")
    
    lines.append("---")
    lines.append("*Generated by biz-delivery Go Business Analyzer*")
    
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 go_business_analyzer.py <project_path>")
        sys.exit(1)
    
    analysis = analyze_go_project(sys.argv[1])
    summary = generate_go_business_summary(analysis)
    print(summary)
