"""
Frontend Project Analyzer - 前端项目分析器
支持 React, Vue, Angular, Svelte 等框架
"""
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class FrontendProjectAnalyzer:
    """前端项目分析器"""

    # 框架关键词映射
    FRAMEWORK_KEYWORDS = {
        'react': ['react', 'jsx', 'tsx', 'createelement', 'usestate', 'useneffect', 'hooks'],
        'vue': ['vue', 'v-bind', 'v-if', 'v-for', 'computed', 'watch', 'emit', 'setup'],
        'angular': ['angular', 'ngmodule', 'component', 'directive', 'pipe', 'service'],
        'svelte': ['svelte', '$: ', '$ ', 'onmount', 'beforeupdate'],
        'nextjs': ['nextjs', 'next/', 'getserverSideProps', 'getstaticprops'],
        'nuxt': ['nuxt', 'nuxt.config', 'asyncdata'],
        'solid': ['solidjs', 'createsignal', 'createtime', 'show'],
        'preact': ['preact', 'h()', 'preact/hooks'],
    }

    # UI 库关键词
    UI_LIBS = {
        'tailwind': ['tailwind', 'tailwindcss'],
        'material-ui': ['@mui', 'material-ui', 'maketheme'],
        'antdesign': ['antd', '@ant-design', 'procomponents'],
        'bootstrap': ['bootstrap', 'reactstrap'],
        'chakra': ['@chakra-ui', 'chakra'],
        'shadcn': ['shadcn', 'cmdk'],
    }

    # 状态管理
    STATE_MGMT = {
        'redux': ['redux', 'createredux', 'usedispatch', 'useselector'],
        'mobx': ['mobx', '@mobx', 'observer'],
        'zustand': ['zustand', 'createstore'],
        'jotai': ['jotai', 'useatom'],
        'pinia': ['pinia', 'definestore'],
        'vuex': ['vuex', 'createstore'],
    }

    # 构建工具
    BUILD_TOOLS = {
        'webpack': ['webpack', 'webpack.config'],
        'vite': ['vite', 'vite.config'],
        'rollup': ['rollup', 'rollup.config'],
        'esbuild': ['esbuild'],
        'parcel': ['parcel'],
    }

    # 测试工具
    TEST_TOOLS = {
        'jest': ['jest', 'jest.config'],
        'vitest': ['vitest', 'describe(', 'it('],
        'cypress': ['cypress', 'cy.', 'cypress.config'],
        'playwright': ['playwright', '@playwright'],
        'testing-library': ['@testing-library', 'render(', 'fireevent'],
    }

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.files = list(self.project_path.rglob('*'))[:1000]
        self.project_name = self._detect_project_name()

    def _detect_project_name(self) -> str:
        """检测项目名称"""
        pkg = self.project_path / 'package.json'
        if pkg.exists():
            try:
                import json
                data = json.loads(pkg.read_text())
                return data.get('name', self.project_path.name)
            except:
                pass
        return self.project_path.name

    def analyze(self) -> Dict[str, Any]:
        """执行分析"""
        result = {
            'project_name': self.project_name,
            'language': 'frontend',
            'framework': 'unknown',
            'ui_libs': [],
            'state_mgmt': [],
            'build_tools': [],
            'test_tools': [],
            'features': [],
            'file_stats': {},
            'summary': '',
        }

        # 检测框架
        framework = self._detect_framework()
        result['framework'] = framework

        # 检测 UI 库
        ui_libs = self._detect_ui_libs()
        result['ui_libs'] = ui_libs

        # 检测状态管理
        state_mgmt = self._detect_state_mgmt()
        result['state_mgmt'] = state_mgmt

        # 检测构建工具
        build_tools = self._detect_build_tools()
        result['build_tools'] = build_tools

        # 检测测试工具
        test_tools = self._detect_test_tools()
        result['test_tools'] = test_tools

        # 统计文件
        file_stats = self._count_files()
        result['file_stats'] = file_stats

        # 生成摘要
        result['summary'] = self._generate_summary(result)

        return result

    def _detect_framework(self) -> str:
        """检测前端框架"""
        for framework, keywords in self.FRAMEWORK_KEYWORDS.items():
            for f in self.files:
                if f.is_file() and f.suffix in ['.jsx', '.tsx', '.vue', '.svelte', '.js', '.ts']:
                    try:
                        content = f.read_text(errors='ignore').lower()
                        if any(kw in content for kw in keywords):
                            return framework
                    except:
                        pass
        return 'unknown'

    def _detect_ui_libs(self) -> List[str]:
        """检测 UI 库"""
        libs = []
        for lib, keywords in self.UI_LIBS.items():
            for f in self.files[:500]:
                if f.is_file():
                    try:
                        content = f.read_text(errors='ignore').lower()
                        if any(kw in content for kw in keywords):
                            libs.append(lib)
                            break
                    except:
                        pass
        return libs

    def _detect_state_mgmt(self) -> List[str]:
        """检测状态管理"""
        mgmt = []
        for tool, keywords in self.STATE_MGMT.items():
            for f in self.files[:500]:
                if f.is_file():
                    try:
                        content = f.read_text(errors='ignore').lower()
                        if any(kw in content for kw in keywords):
                            mgmt.append(tool)
                            break
                    except:
                        pass
        return mgmt

    def _detect_build_tools(self) -> List[str]:
        """检测构建工具"""
        tools = []
        for tool, keywords in self.BUILD_TOOLS.items():
            for f in self.files[:200]:
                if f.is_file() and 'config' in f.name.lower():
                    try:
                        content = f.read_text(errors='ignore').lower()
                        if any(kw in content for kw in keywords):
                            tools.append(tool)
                            break
                    except:
                        pass
        return tools

    def _detect_test_tools(self) -> List[str]:
        """检测测试工具"""
        tools = []
        for tool, keywords in self.TEST_TOOLS.items():
            for f in self.files[:500]:
                if f.is_file():
                    try:
                        content = f.read_text(errors='ignore').lower()
                        if any(kw in content for kw in keywords):
                            tools.append(tool)
                            break
                    except:
                        pass
        return tools

    def _count_files(self) -> Dict[str, int]:
        """统计文件类型"""
        counts = {}
        for f in self.files:
            if f.is_file():
                ext = f.suffix.lower() or '(no extension)'
                counts[ext] = counts.get(ext, 0) + 1
        return counts

    def _generate_summary(self, result: Dict) -> str:
        """生成分析摘要"""
        lines = [
            f"# {result['project_name']} 前端分析",
            "",
            f"**框架**: {result['framework']}",
            f"**文件总数**: {sum(result['file_stats'].values())}",
            "",
        ]

        if result['ui_libs']:
            lines.append("## UI 库")
            lines.append("")
            for lib in result['ui_libs']:
                lines.append(f"- {lib}")
            lines.append("")

        if result['state_mgmt']:
            lines.append("## 状态管理")
            lines.append("")
            for tool in result['state_mgmt']:
                lines.append(f"- {tool}")
            lines.append("")

        if result['build_tools']:
            lines.append("## 构建工具")
            lines.append("")
            for tool in result['build_tools']:
                lines.append(f"- {tool}")
            lines.append("")

        if result['test_tools']:
            lines.append("## 测试工具")
            lines.append("")
            for tool in result['test_tools']:
                lines.append(f"- {tool}")
            lines.append("")

        lines.append("## 文件统计")
        lines.append("")
        lines.append("| 扩展名 | 数量 |")
        lines.append("|--------|------|")
        for ext, count in sorted(result['file_stats'].items(), key=lambda x: x[1], reverse=True)[:10]:
            lines.append(f"| {ext} | {count} |")

        return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 frontend_analyzer.py <project_path>")
        sys.exit(1)
    
    analyzer = FrontendProjectAnalyzer(sys.argv[1])
    result = analyzer.analyze()
    print(result['summary'])
