"""
Documentation Skill v2.0 - 资深文档生成专家
自动生成 README, API文档, 架构文档, CHANGELOG, CONTRIBUTING 等

核心能力:
  1. README 自动生成 (带徽章, TOC, 功能特性)
  2. API 文档自动发现 (从代码扫描接口)
  3. 架构文档生成 (Mermaid 图表)
  4. 领域适配模板 (根据项目类型调整)
  5. 多语言支持 (Go/Java/Python/TypeScript)
"""
import re
import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from skills.base import SkillBase, SkillResult


@dataclass
class DocSection:
    """文档章节"""
    title: str
    content: str
    order: int


@dataclass 
class APIMethod:
    """API 方法"""
    method: str
    path: str
    description: str
    params: List[str]
    response: str


class DocumentationSkillV2(SkillBase):
    """文档生成 Skill v2.0"""

    # 领域模板
    DOMAIN_TEMPLATES = {
        'advertising': {
            'keywords': ['RTB', 'DSP', 'SSP', '竞价', '出价', '曝光', '点击'],
            'features': ['实时竞价引擎', '预算追踪', '降级策略', '反作弊'],
            'tech_stack': ['Go', 'Redis', 'Kafka', 'ClickHouse', 'Prometheus'],
        },
        'agent': {
            'keywords': ['Agent', 'LLM', 'RAG', 'ReAct', 'Tool', '记忆'],
            'features': ['多Agent协作', '记忆系统', 'Tool调用', '安全Guardrails'],
            'tech_stack': ['Python', 'FastAPI', 'Redis', '向量数据库', 'LangChain'],
        },
        'ecommerce': {
            'keywords': ['订单', '商品', '库存', '支付', '购物车', '优惠券'],
            'features': ['订单状态机', '库存预扣', '支付Saga', '幂等控制'],
            'tech_stack': ['Go', 'MySQL', 'Redis', 'Kafka', 'Sentinel'],
        },
        'finance': {
            'keywords': ['交易', '账户', '风控', '合规', '清算', '对账'],
            'features': ['强一致性交易', '风控双引擎', '审计日志', '合规检查'],
            'tech_stack': ['Java', 'MySQL', 'Redis', 'Kafka', 'Flink'],
        },
        'cloud_native': {
            'keywords': ['Kubernetes', 'K8s', '容器', 'Docker', 'Istio', 'Helm'],
            'features': ['微服务部署', '服务网格', 'GitOps', '可观测性'],
            'tech_stack': ['Go', 'Kubernetes', 'Istio', 'Prometheus', 'Grafana'],
        },
        'devops': {
            'keywords': ['CI/CD', 'Jenkins', 'ArgoCD', 'GitOps', 'Terraform'],
            'features': ['自动化流水线', '基础设施即代码', '蓝绿部署', '混沌工程'],
            'tech_stack': ['Go', 'Jenkins', 'ArgoCD', 'Terraform', 'Prometheus'],
        },
        'security': {
            'keywords': ['加密', 'JWT', 'OAuth', '零信任', 'RBAC', '审计'],
            'features': ['零信任架构', '密钥管理', '访问控制', '安全审计'],
            'tech_stack': ['Go', 'Vault', 'OIDC', 'OPA', 'Prometheus'],
        },
        'ml_ops': {
            'keywords': ['模型', '训练', '推理', 'MLflow', '特征', 'A/B测试'],
            'features': ['模型服务', '特征存储', '漂移监控', '实验平台'],
            'tech_stack': ['Python', 'Triton', 'MLflow', 'Kafka', 'Redis'],
        },
        'fullstack': {
            'keywords': ['系统', '项目', '应用', '服务'],
            'features': ['高性能架构', '可扩展设计', '企业级安全', '可观测性'],
            'tech_stack': ['Go/Python/Java', 'MySQL/PostgreSQL', 'Redis', 'Kafka', 'Kubernetes'],
        },
    }

    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile)
        self.output_dir = profile.get('output_dir', './docs') if profile else './docs'

    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行文档生成"""
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)

        code_path = input_data.get("code_path", ".")
        doc_types = input_data.get("doc_types", ["readme", "api", "architecture"])
        domain = input_data.get("domain", "fullstack")
        prd_content = input_data.get("prd_content", "")

        try:
            # 分析项目
            analysis = self._analyze_project(code_path, domain)
            
            # 生成文档
            docs = {}
            if "readme" in doc_types:
                docs["README.md"] = self._generate_readme(analysis, domain, prd_content)
            if "api" in doc_types:
                docs["API.md"] = self._generate_api_docs(analysis, domain)
            if "architecture" in doc_types:
                docs["ARCHITECTURE.md"] = self._generate_architecture_doc(analysis, domain)
            if "changelog" in doc_types:
                docs["CHANGELOG.md"] = self._generate_changelog(analysis)
            if "contributing" in doc_types:
                docs["CONTRIBUTING.md"] = self._generate_contributing(analysis, domain)
            if "security" in doc_types:
                docs["SECURITY.md"] = self._generate_security_doc(domain)

            # 保存文档
            saved_files = self._save_docs(docs, self.output_dir)

            return SkillResult(
                success=True,
                output={
                    "doc_types": doc_types,
                    "files_generated": saved_files,
                    "total_size": sum(len(v) for v in docs.values()),
                    "analysis": analysis,
                },
                metadata={
                    "skill": "documentation_v2",
                    "generated_at": datetime.now().isoformat(),
                    "domain": domain,
                }
            )

        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"Documentation generation failed: {str(e)}"]
            )

    def _analyze_project(self, path: str, domain: str) -> Dict:
        """分析项目结构"""
        path_obj = Path(path).resolve()
        
        if not path_obj.exists():
            return self._get_default_analysis(domain)

        # 统计文件
        file_stats = self._scan_files(path_obj)
        
        # 检测语言和框架
        lang_info = self._detect_language(file_stats)
        
        # 检测 API 端点
        api_endpoints = self._discover_apis(path_obj, file_stats)
        
        # 检测配置
        config_info = self._detect_config(path_obj)
        
        # 检测依赖
        dependencies = self._detect_dependencies(path_obj, lang_info['language'])
        
        # 获取领域信息
        domain_info = self.DOMAIN_TEMPLATES.get(domain, self.DOMAIN_TEMPLATES['fullstack'])

        return {
            'path': str(path_obj),
            'language': lang_info['language'],
            'frameworks': lang_info['frameworks'],
            'file_stats': file_stats,
            'api_endpoints': api_endpoints[:20],  # 最多20个
            'config': config_info,
            'dependencies': dependencies[:15],
            'domain': domain,
            'domain_info': domain_info,
            'generated_at': datetime.now().isoformat(),
        }

    def _scan_files(self, path: Path) -> Dict:
        """扫描文件"""
        stats = {
            'total': 0,
            'by_ext': {},
            'by_dir': {},
            'max_depth': 0,
        }
        
        for root, dirs, files in os.walk(path):
            depth = root.replace(str(path), '').count(os.sep)
            stats['max_depth'] = max(stats['max_depth'], depth)
            
            for f in files:
                stats['total'] += 1
                ext = Path(f).suffix.lower() or '(no ext)'
                stats['by_ext'][ext] = stats['by_ext'].get(ext, 0) + 1
                
                dir_name = os.path.basename(root)
                stats['by_dir'][dir_name] = stats['by_dir'].get(dir_name, 0) + 1
        
        return stats

    def _detect_language(self, file_stats: Dict) -> Dict:
        """检测语言和框架"""
        lang_map = {
            '.go': ('Go', ['gin', 'fiber', 'echo', 'gorm', 'zerolog']),
            '.py': ('Python', ['fastapi', 'django', 'flask', 'celery', 'sqlalchemy']),
            '.java': ('Java', ['spring', 'mybatis', 'netflix', 'grpc']),
            '.ts': ('TypeScript', ['next', 'nuxt', 'express', 'nestjs']),
            '.js': ('JavaScript', ['react', 'vue', 'express', 'node']),
            '.rs': ('Rust', ['actix', 'tokio', 'axum', 'serde']),
        }
        
        # 找主要语言
        primary_ext = max(file_stats.get('by_ext', {}).items(), key=lambda x: x[1])[0]
        language, frameworks = lang_map.get(primary_ext, (primary_ext.lstrip('.').upper(), []))
        
        return {'language': language, 'frameworks': frameworks[:3]}

    def _discover_apis(self, path: Path, file_stats: Dict) -> List[Dict]:
        """发现 API 端点"""
        endpoints = []
        
        # 扫描路由定义
        api_patterns = {
            '.go': [r'@(Get|Post|Put|Delete)\("([^"]+)"', r'r\.Get\("([^"]+)"'],
            '.py': [r'@(app\.)?(route|get|post|put|delete)\(["\']([^"\']+)', r"@app\.(get|post|put|delete)\(['\"]([^'\"]+)"],
            '.java': [r'@(GetMapping|PostMapping|PutMapping|DeleteMapping)\("([^"]+)"'],
        }
        
        for ext, patterns in api_patterns.items():
            for py_file in path.rglob(f'*{ext}'):
                try:
                    content = py_file.read_text(errors='ignore')
                    for pattern in patterns:
                        for match in re.finditer(pattern, content):
                            path_str = match.group(1) if match.lastindex >= 1 else match.group(0)
                            endpoints.append({
                                'method': 'GET',
                                'path': path_str,
                                'file': str(py_file),
                            })
                except:
                    pass
        
        return endpoints[:20]

    def _detect_config(self, path: Path) -> Dict:
        """检测配置文件"""
        configs = {}
        config_files = {
            'go.mod': 'go_module',
            'package.json': 'npm_package',
            'pom.xml': 'maven_project',
            'requirements.txt': 'python_deps',
            'Dockerfile': 'docker',
            'docker-compose.yml': 'docker_compose',
            'Makefile': 'makefile',
            '.github/workflows/*.yml': 'github_actions',
        }
        
        for pattern, config_type in config_files.items():
            if '*' in pattern:
                continue
            for f in path.glob(pattern):
                configs[config_type] = str(f)
        
        # 搜索工作流
        for wf in path.rglob('.github/workflows/*.yml'):
            configs['github_actions'] = str(wf)
            break
        
        return configs

    def _detect_dependencies(self, path: Path, language: str) -> List[str]:
        """检测依赖"""
        deps = []
        
        dep_files = {
            'Go': [('go.mod', r'module\s+(\S+)\s+\n\s+(\S+)'), ('go.sum', None)],
            'Python': [('requirements.txt', r'^([^#=\s].+)'), ('setup.py', None)],
            'Java': [('pom.xml', r'<dependency>.*?<artifactId>([^<]+)</artifactId>'), 
                     ('build.gradle', r'implementation\s+[\'"]([^\'"]+)')],
            'TypeScript': [('package.json', None)],
        }
        
        for lang_deps in dep_files.get(language, []):
            filename, pattern = lang_deps
            for f in path.glob(filename):
                try:
                    content = f.read_text()
                    if pattern:
                        for match in re.finditer(pattern, content, re.DOTALL):
                            if match.lastindex:
                                deps.append(match.group(1))
                    elif filename == 'package.json':
                        pkg = json.loads(content)
                        deps.extend(list(pkg.get('dependencies', {}).keys())[:10])
                        deps.extend(list(pkg.get('devDependencies', {}).keys())[:5])
                except:
                    pass
        
        return list(set(deps))[:15]

    def _get_default_analysis(self, domain: str) -> Dict:
        """获取默认分析"""
        domain_info = self.DOMAIN_TEMPLATES.get(domain, self.DOMAIN_TEMPLATES['fullstack'])
        return {
            'path': 'unknown',
            'language': 'Multi-language',
            'frameworks': [],
            'file_stats': {'total': 0, 'by_ext': {}, 'by_dir': {}},
            'api_endpoints': [],
            'config': {},
            'dependencies': [],
            'domain': domain,
            'domain_info': domain_info,
            'generated_at': datetime.now().isoformat(),
        }

    # ========== 文档生成方法 ==========

    def _generate_readme(self, analysis: Dict, domain: str, prd_content: str) -> str:
        """生成 README"""
        lines = []
        
        # 标题和徽章
        project_name = analysis['path'].split('/')[-1] if analysis['path'] != 'unknown' else 'Project'
        lines.append(f"# {project_name}")
        lines.append("")
        lines.append(f"[![Go Version](https://img.shields.io/badge/go-{analysis['language']}-blue.svg)]()")
        lines.append(f"[![Domain](https://img.shields.io/badge/domain-{domain}-green.svg)]()")
        lines.append(f"[![License](https://img.shields.io/badge/license-MIT-purple.svg)]()")
        lines.append("")
        
        # 简介
        lines.append("## Overview")
        lines.append("")
        if prd_content:
            # 从 PRD 提取简介
            intro_match = re.search(r'##\s*[项项项目背景|背景]\s*\n+(.*?)(?=\n##|$)', prd_content, re.DOTALL)
            if intro_match:
                lines.append(intro_match.group(1).strip()[:200] + "...")
            else:
                lines.append(f"A {domain} project built with {analysis['language']}.")
        else:
            domain_info = analysis.get('domain_info', {})
            features = domain_info.get('features', [])
            lines.append(f"A {domain} project with key features:")
            for f in features[:4]:
                lines.append(f"- {f}")
        lines.append("")
        
        # TOC
        lines.append("## Table of Contents")
        lines.append("")
        lines.append("1. [Overview](#overview)")
        lines.append("2. [Features](#features)")
        lines.append("3. [Tech Stack](#tech-stack)")
        lines.append("4. [Project Structure](#project-structure)")
        lines.append("5. [Getting Started](#getting-started)")
        lines.append("6. [API Reference](#api-reference)")
        lines.append("7. [Architecture](#architecture)")
        lines.append("8. [Contributing](#contributing)")
        lines.append("")
        
        # 功能特性
        lines.append("## Features")
        lines.append("")
        domain_info = analysis.get('domain_info', {})
        features = domain_info.get('features', [
            'High Performance',
            'Scalable Architecture', 
            'Enterprise Security',
            'Observability',
        ])
        for f in features[:6]:
            lines.append(f"- ✅ {f}")
        lines.append("")
        
        # 技术栈
        lines.append("## Tech Stack")
        lines.append("")
        tech_list = domain_info.get('tech_stack', [analysis['language']])
        tech_list.extend(analysis.get('dependencies', [])[:3])
        lines.append("| Component | Technology |")
        lines.append("|-----------|------------|")
        for tech in tech_list[:8]:
            lines.append(f"| {tech.split('/')[-1]} | {tech} |")
        lines.append("")
        
        # 项目结构
        lines.append("## Project Structure")
        lines.append("")
        lines.append("```")
        if analysis['file_stats']['total'] > 0:
            for dir_name, count in sorted(analysis['file_stats']['by_dir'].items(), key=lambda x: -x[1])[:10]:
                lines.append(f"├── {dir_name}/ ({count} files)")
        else:
            lines.append("├── cmd/")
            lines.append("│   └── main.go")
            lines.append("├── internal/")
            lines.append("│   ├── handler/")
            lines.append("│   ├── service/")
            lines.append("│   └── repo/")
            lines.append("├── pkg/")
            lines.append("├── docs/")
            lines.append("└── test/")
        lines.append("```")
        lines.append("")
        
        # 快速开始
        lines.append("## Getting Started")
        lines.append("")
        lines.append("### Prerequisites")
        lines.append("")
        if analysis['language'] == 'Go':
            lines.append("- Go 1.21+")
            lines.append("- Make")
            lines.append("- Docker (optional)")
        elif analysis['language'] == 'Python':
            lines.append("- Python 3.10+")
            lines.append("- pip / poetry")
            lines.append("- Docker (optional)")
        lines.append("")
        
        lines.append("### Installation")
        lines.append("")
        lines.append("```bash")
        if analysis['language'] == 'Go':
            lines.append("go mod download")
            lines.append("go build -o bin/server ./cmd/main.go")
        elif analysis['language'] == 'Python':
            lines.append("pip install -r requirements.txt")
            lines.append("python -m uvicorn app.main:app --reload")
        else:
            lines.append("# TODO: Add build commands")
        lines.append("```")
        lines.append("")
        
        lines.append("### Run Tests")
        lines.append("")
        lines.append("```bash")
        if analysis['language'] == 'Go':
            lines.append("go test ./... -v -cover")
        elif analysis['language'] == 'Python':
            lines.append("pytest -v")
        lines.append("```")
        lines.append("")
        
        # API 参考
        lines.append("## API Reference")
        lines.append("")
        endpoints = analysis.get('api_endpoints', [])
        if endpoints:
            lines.append("| Method | Path | Description |")
            lines.append("|--------|------|-------------|")
            for ep in endpoints[:10]:
                lines.append(f"| {ep.get('method', 'GET')} | `{ep.get('path', '/')}` | - |")
        else:
            lines.append("_See [API.md](./API.md) for detailed API reference._")
        lines.append("")
        
        # 架构
        lines.append("## Architecture")
        lines.append("")
        lines.append("_See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed architecture documentation._")
        lines.append("")
        
        # 贡献
        lines.append("## Contributing")
        lines.append("")
        lines.append("Please read [CONTRIBUTING.md](./CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.")
        lines.append("")
        
        # 许可证
        lines.append("## License")
        lines.append("")
        lines.append("This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.")
        lines.append("")
        
        return "\n".join(lines)

    def _generate_api_docs(self, analysis: Dict, domain: str) -> str:
        """生成 API 文档"""
        lines = [
            "# API Documentation",
            "",
            f"**Domain**: {domain}",
            f"**Generated**: {analysis.get('generated_at', 'N/A')}",
            "",
            "---",
            "",
        ]
        
        endpoints = analysis.get('api_endpoints', [])
        
        if not endpoints:
            # 生成模板
            domain_info = analysis.get('domain_info', {})
            templates = {
                'advertising': [
                    ("POST", "/api/v1/bid", "实时竞价请求", ["impression_id", "bid_price", "targeting"]),
                    ("GET", "/api/v1/budget/{account_id}", "查询预算", ["account_id"]),
                    ("POST", "/api/v1/fallback", "降级出价", ["impression_id", "fallback_price"]),
                ],
                'agent': [
                    ("POST", "/api/v1/chat", "发送消息", ["message", "context_id"]),
                    ("GET", "/api/v1/memory/{id}", "查询记忆", ["id"]),
                    ("POST", "/api/v1/tool/{name}", "调用工具", ["params"]),
                ],
                'ecommerce': [
                    ("POST", "/api/v1/orders", "创建订单", ["product_id", "quantity", "user_id"]),
                    ("GET", "/api/v1/orders/{id}", "查询订单", ["id"]),
                    ("POST", "/api/v1/payments", "发起支付", ["order_id", "amount", "method"]),
                ],
                'finance': [
                    ("POST", "/api/v1/transactions", "发起交易", ["account_id", "amount", "type"]),
                    ("GET", "/api/v1/accounts/{id}", "查询账户", ["id"]),
                    ("POST", "/api/v1/risk/check", "风控检查", ["transaction_id", "amount"]),
                ],
            }
            endpoints = templates.get(domain, [
                ("GET", "/api/v1/health", "健康检查", []),
                ("POST", "/api/v1/process", "处理请求", ["input"]),
            ])
        
        lines.append("## Endpoints")
        lines.append("")
        lines.append("| Method | Path | Description |")
        lines.append("|--------|------|-------------|")
        
        for ep in endpoints[:15]:
            if isinstance(ep, dict):
                method = ep.get('method', 'GET')
                path = ep.get('path', '/')
                desc = ep.get('description', '')
            else:
                method = ep[0]
                path = ep[1]
                desc = ep[2] if len(ep) > 2 else ''
            lines.append(f"| {method} | `{path}` | {desc} |")
        
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # 详细接口
        lines.append("## Detailed API Reference")
        lines.append("")
        
        for i, ep in enumerate(endpoints[:5]):
            method = ep.get('method', 'GET') if isinstance(ep, dict) else ep[0]
            path = ep.get('path', '/') if isinstance(ep, dict) else ep[1]
            desc = ep.get('description', '') if isinstance(ep, dict) else ep[2]
            params = ep.get('params', []) if isinstance(ep, dict) else (ep[3] if len(ep) > 3 else [])
            
            lines.append(f"### {method} {path}")
            lines.append("")
            lines.append(f"**Description**: {desc}")
            lines.append("")
            
            if params:
                lines.append("**Parameters**:")
                lines.append("")
                lines.append("| Parameter | Type | Required | Description |")
                lines.append("|-----------|------|----------|-------------|")
                for p in params:
                    lines.append(f"| {p} | string | Yes | {p} parameter |")
                lines.append("")
            
            lines.append("**Response**:")
            lines.append("")
            lines.append("```json")
            lines.append("{")
            lines.append('  "code": 0,')
            lines.append('  "message": "success",')
            lines.append('  "data": {}')
            lines.append("}")
            lines.append("```")
            lines.append("")
        
        return "\n".join(lines)

    def _generate_architecture_doc(self, analysis: Dict, domain: str) -> str:
        """生成架构文档"""
        lines = [
            "# Architecture Documentation",
            "",
            f"**Domain**: {domain}",
            f"**Language**: {analysis.get('language', 'N/A')}",
            f"**Generated**: {analysis.get('generated_at', 'N/A')}",
            "",
            "---",
            "",
            "## Architecture Diagram",
            "",
            "```mermaid",
            "graph TB",
        ]
        
        # 根据领域生成架构图
        arch_patterns = {
            'advertising': [
                "Client[Client/Browser]",
                "LB[Load Balancer]",
                "BidEngine[Bid Engine]",
                "ProfileCache[(Profile Cache)]",
                "BudgetService[Budget Service]",
                "Kafka[Kafka]",
                "Analytics[Analytics]",
                "Client --> LB",
                "LB --> BidEngine",
                "BidEngine --> ProfileCache",
                "BidEngine --> BudgetService",
                "BidEngine --> Kafka",
                "Kafka --> Analytics",
            ],
            'agent': [
                "User[User]",
                "API[API Gateway]",
                "Agent[Agent Core]",
                "Memory[(Memory Store)]",
                "Tools[Tools]",
                "LLM[LLM Service]",
                "User --> API",
                "API --> Agent",
                "Agent --> Memory",
                "Agent --> Tools",
                "Agent --> LLM",
            ],
            'ecommerce': [
                "User[User]",
                "Web[Web Server]",
                "OrderSvc[Order Service]",
                "StockSvc[Stock Service]",
                "PaySvc[Payment Service]",
                "DB[(Database)]",
                "Cache[(Redis)]",
                "User --> Web",
                "Web --> OrderSvc",
                "OrderSvc --> StockSvc",
                "OrderSvc --> PaySvc",
                "OrderSvc --> DB",
                "OrderSvc --> Cache",
            ],
        }
        
        pattern = arch_patterns.get(domain, arch_patterns['ecommerce'])
        for item in pattern:
            lines.append(f"    {item}")
        
        lines.extend([
            "```",
            "",
            "---",
            "",
            "## Tech Stack",
            "",
            "| Layer | Technology | Purpose |",
            "|-------|------------|---------|",
        ])
        
        domain_info = analysis.get('domain_info', {})
        tech_stack = domain_info.get('tech_stack', [])
        
        layers = [
            ("前端", "React/Vue/Go Templates"),
            ("API层", "Go/Java/Python REST API"),
            ("服务层", "微服务架构"),
            ("数据层", ", '.join(tech_stack[:4]) if tech_stack else 'MySQL/Redis/Kafka'"),
            ("基础设施", "Kubernetes/Docker"),
        ]
        
        for layer, tech in layers:
            lines.append(f"| {layer} | {tech} | Core infrastructure |")
        
        lines.extend([
            "",
            "---",
            "",
            "## Design Patterns",
            "",
        ])
        
        patterns = {
            'advertising': ['CQRS', 'Event Sourcing', 'Circuit Breaker', 'Retry Pattern'],
            'agent': ['ReAct', 'Planner-Executor', 'Tool Use', 'Memory Management'],
            'ecommerce': ['Saga Pattern', 'CQRS', 'Repository Pattern', 'Factory Pattern'],
            'finance': ['2PC/TCC', 'Outbox Pattern', 'CQRS', 'Event Sourcing'],
            'cloud_native': ['Sidecar', 'Service Mesh', 'Operator Pattern', 'GitOps'],
            'devops': ['Infrastructure as Code', 'GitOps', 'Canary Deployment'],
            'security': ['Zero Trust', 'RBAC', 'OAuth2', 'mTLS'],
            'ml_ops': ['Feature Store', 'Model Registry', 'CI/CD for ML', 'A/B Testing'],
        }
        
        for p in patterns.get(domain, ['Clean Architecture', 'Repository Pattern', 'Dependency Injection']):
            lines.append(f"- **{p}**: Core design pattern for this domain")
        
        lines.extend([
            "",
            "---",
            "",
            "## Module Structure",
            "",
            "```",
        ])
        
        # 生成模块结构
        module_structure = {
            'advertising': ['cmd/', 'internal/bid/', 'internal/profile/', 'internal/budget/', 'pkg/'],
            'agent': ['cmd/', 'internal/agent/', 'internal/memory/', 'internal/tools/', 'pkg/'],
            'ecommerce': ['cmd/', 'internal/order/', 'internal/stock/', 'internal/payment/', 'pkg/'],
            'finance': ['cmd/', 'internal/transaction/', 'internal/risk/', 'internal/compliance/', 'pkg/'],
        }
        
        modules = module_structure.get(domain, ['cmd/', 'internal/', 'pkg/', 'docs/'])
        for m in modules:
            lines.append(f"├── {m}")
        lines.append("```")
        
        lines.extend([
            "",
            "---",
            "",
            "## Deployment Architecture",
            "",
            "```mermaid",
            "graph LR",
            "    CDN[CDN] --> LB[Load Balancer]",
            "    LB --> Pod1[Pod 1]",
            "    LB --> Pod2[Pod 2]",
            "    LB --> Pod3[Pod 3]",
            "    Pod1 --> DB[(Database)]",
            "    Pod1 --> Cache[(Redis)]",
            "    Pod1 --> MQ[(Message Queue)]",
            "```",
            "",
            "**Key Deployment Considerations:**",
            "",
            "- Multiple replicas for high availability",
            "- Auto-scaling based on QPS",
            "- Multi-AZ deployment for disaster recovery",
            "- Resource limits and requests configured",
            "",
        ])
        
        return "\n".join(lines)

    def _generate_changelog(self, analysis: Dict) -> str:
        """生成 CHANGELOG"""
        lines = [
            "# Changelog",
            "",
            "All notable changes to this project will be documented in this file.",
            "",
            "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),",
            "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).",
            "",
            "---",
            "",
            "## [Unreleased]",
            "",
            "### Added",
            "- Initial project structure",
            f"- Domain: {analysis.get('domain', 'fullstack')}",
            f"- Language: {analysis.get('language', 'Go')}",
            "",
            "### Changed",
            "- Nothing yet",
            "",
            "### Deprecated",
            "- Nothing yet",
            "",
            "### Removed",
            "- Nothing yet",
            "",
            "### Fixed",
            "- Nothing yet",
            "",
            "### Security",
            "- Nothing yet",
            "",
        ]
        
        return "\n".join(lines)

    def _generate_contributing(self, analysis: Dict, domain: str) -> str:
        """生成 CONTRIBUTING"""
        lines = [
            "# Contributing",
            "",
            "Thanks for your interest in contributing! This document provides guidelines for contributing to this project.",
            "",
            "---",
            "",
            "## Development Setup",
            "",
            f"1. Clone the repository",
            "2. Install dependencies",
            f"3. Run tests: `{self._get_test_command(analysis['language'])}`",
            "4. Create a branch for your changes",
            "",
            "## Code Style",
            "",
            "- Follow the existing code style",
            "- Write meaningful commit messages",
            "- Add tests for new features",
            "- Update documentation as needed",
            "",
            "## Pull Request Process",
            "",
            "1. Create a feature branch",
            "2. Make your changes",
            "3. Run tests and ensure they pass",
            "4. Submit a pull request",
            "",
            "## Report Bugs",
            "",
            "Please use the [issue tracker](../../issues) to report bugs.",
            "",
            "## Request Features",
            "",
            "Please use the [issue tracker](../../issues) to request features.",
            "",
        ]
        
        return "\n".join(lines)

    def _generate_security_doc(self, domain: str) -> str:
        """生成安全文档"""
        lines = [
            "# Security",
            "",
            f"**Domain**: {domain}",
            "",
            "---",
            "",
            "## Security Measures",
            "",
        ]
        
        security_measures = {
            'advertising': [
                "预算追踪防超投机制",
                "竞价数据加密传输",
                "敏感操作审计日志",
            ],
            'agent': [
                "输入过滤防注入",
                "Token 成本监控",
                "Tool 调用权限控制",
            ],
            'ecommerce': [
                "支付数据加密",
                "用户信息脱敏",
                "操作审计日志",
            ],
            'finance': [
                "资金安全加密",
                "交易不可篡改",
                "合规审计日志",
                "权限最小化原则",
            ],
            'security': [
                "零信任架构",
                "密钥管理 (Vault)",
                "TLS 全链路加密",
                "RBAC 权限控制",
            ],
        }
        
        measures = security_measures.get(domain, [
            "数据传输加密 (TLS)",
            "敏感数据存储加密",
            "操作审计日志",
            "定期安全扫描",
        ])
        
        for m in measures:
            lines.append(f"- ✅ {m}")
        
        lines.extend([
            "",
            "---",
            "",
            "## Reporting Security Issues",
            "",
            "Please report security vulnerabilities to the project maintainers.",
            "",
        ])
        
        return "\n".join(lines)

    def _get_test_command(self, language: str) -> str:
        """获取测试命令"""
        commands = {
            'Go': 'go test ./... -v -cover',
            'Python': 'pytest -v',
            'Java': 'mvn test',
            'TypeScript': 'npm test',
            'JavaScript': 'npm test',
            'Rust': 'cargo test',
        }
        return commands.get(language, 'make test')

    def _save_docs(self, docs: Dict[str, str], output_dir: str) -> List[str]:
        """保存文档"""
        saved = []
        path_obj = Path(output_dir)
        path_obj.mkdir(parents=True, exist_ok=True)
        
        for filename, content in docs.items():
            filepath = path_obj / filename
            filepath.write_text(content, encoding='utf-8')
            saved.append(str(filepath))
        
        return saved


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 doc_skill_v2.py <code_path> [--domain DOMAIN] [--types TYPES]")
        sys.exit(1)
    
    code_path = sys.argv[1]
    domain = "fullstack"
    doc_types = ["readme", "api", "architecture"]
    
    for arg in sys.argv[2:]:
        if arg.startswith("--domain="):
            domain = arg.split("=")[1]
        elif arg.startswith("--types="):
            doc_types = arg.split("=")[1].split(",")
    
    skill = DocumentationSkillV2({"output_dir": "./docs"})
    result = skill.run({
        "code_path": code_path,
        "domain": domain,
        "doc_types": doc_types,
    })
    
    if result.success:
        print(f"Generated {len(result.output['files_generated'])} docs:")
        for f in result.output['files_generated']:
            print(f"  - {f}")
    else:
        print(f"Error: {result.errors}")
