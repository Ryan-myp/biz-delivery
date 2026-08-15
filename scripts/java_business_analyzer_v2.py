"""
Java Business Analyzer v2 - 增强版
支持更多 Java 框架: MyBatis, Spring Cloud, Quarkus 等
"""
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class JavaBusinessAnalyzerV2:
    """Java 项目业务语义分析器 v2"""

    # 扩展功能关键词映射
    FEATURE_KEYWORDS = {
        'web': ['controller', 'servlet', 'rest', 'http', 'request', 'response', 'endpoint'],
        'api': ['api', 'rest', 'graphql', 'endpoint', 'route', 'handler'],
        'data': ['repository', 'dao', 'entity', 'jpa', 'hibernate', 'mysql', 'postgres', 'mongodb'],
        'auth': ['auth', 'security', 'oauth', 'jwt', 'token', 'permission', 'rbac'],
        'mq': ['kafka', 'rabbitmq', 'activemq', 'jms', 'message', 'queue'],
        'cache': ['cache', 'redis', 'ehcache', 'caching'],
        'task': ['scheduled', 'job', 'cron', 'async', 'executor'],
        'file': ['file', 'upload', 'download', 'storage', 'io'],
        'search': ['search', 'elasticsearch', 'solr', 'index'],
        'notification': ['notification', 'email', 'sms', 'push', 'alert'],
        'payment': ['payment', 'billing', 'order', 'transaction', 'stripe', 'paypal'],
        'report': ['report', 'dashboard', 'analytics', 'statistics', 'metric'],
        'mybatis': ['mybatis', 'mapper', '@select', '@insert', '@update', '@delete', 'sqlsession'],
        'springcloud': ['feign', 'ribbon', 'eureka', 'config-server', 'gateway', 'hystrix', 'resilience4j'],
        'quarkus': ['quarkus', 'io.quarkus'],
        'micronaut': ['micronaut', 'io.micronaut'],
        'grpc': ['grpc', 'protobuf', '.proto'],
        'graphql': ['graphql', 'graphiql', 'apollographql'],
    }

    # 架构模式关键词
    ARCH_PATTERNS = {
        'microservice': ['feign', 'ribbon', 'eureka', 'config-server', 'gateway', 'spring-cloud'],
        'monolith': [],
        'event_driven': ['@kafka', '@rabbitlistener', '@jmslistener', 'eventbus', 'kafkaconsumer'],
        'ddd': ['aggregate', 'valueobject', 'domainevent', 'repository', 'boundedcontext'],
        'hexagonal': ['port', 'adapter', 'application.service', 'domain.service'],
        'clean_architecture': ['usecase', 'entity', 'repository', 'presentation'],
    }

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.java_files = list(self.project_path.rglob('*.java'))[:500]
        self.features = []
        self.modules = []
        self.project_name = self._detect_project_name()

    def _detect_project_name(self) -> str:
        """检测项目名称"""
        pom = self.project_path / 'pom.xml'
        if pom.exists():
            content = pom.read_text()
            name_match = re.search(r'<artifactId>(.+)</artifactId>', content)
            if name_match:
                return name_match.group(1)
        
        gradle = self.project_path / 'build.gradle'
        if gradle.exists():
            content = gradle.read_text()
            name_match = re.search(r"name\s+['\"](.+)['\"]", content)
            if name_match:
                return name_match.group(1)
        
        return self.project_path.name

    def analyze(self) -> Dict[str, Any]:
        """执行分析"""
        result = {
            'project_name': self.project_name,
            'language': 'java',
            'features': [],
            'modules': [],
            'architecture': {},
            'framework': 'unknown',
            'summary': '',
        }

        # 分析特征
        features = self._analyze_features()
        result['features'] = features

        # 分析模块
        modules = self._analyze_modules()
        result['modules'] = modules

        # 架构分析
        arch = self._analyze_architecture()
        result['architecture'] = arch
        result['framework'] = arch.get('framework', 'unknown')

        # 生成摘要
        result['summary'] = self._generate_summary(result)

        return result

    def _analyze_features(self) -> List[str]:
        """分析功能特征"""
        features = set()
        
        for java_file in self.java_files:
            if 'vendor/' in str(java_file) or 'target/' in str(java_file):
                continue
            
            try:
                content = java_file.read_text(errors='ignore').lower()
                
                for feature, keywords in self.FEATURE_KEYWORDS.items():
                    if any(kw in content for kw in keywords):
                        features.add(feature)
            except Exception:
                continue
        
        return sorted(list(features))

    def _analyze_modules(self) -> List[str]:
        """分析模块结构"""
        modules = []
        
        src_dirs = list(self.project_path.rglob('src/main/java'))
        for src_dir in src_dirs[:5]:
            for package_dir in src_dir.rglob('*'):
                if package_dir.is_dir() and package_dir.name not in ['java', 'META-INF']:
                    level = str(package_dir.relative_to(src_dir)).count('/')
                    if level <= 2:
                        modules.append(str(package_dir.relative_to(src_dir)))
        
        return sorted(modules)[:10]

    def _analyze_architecture(self) -> Dict:
        """分析架构特征"""
        arch = {
            'framework': 'unknown',
            'pattern': 'unknown',
            'components': [],
        }
        
        # 检测框架
        frameworks = {
            'spring_boot': ['spring-boot', 'springframework', 'spring-boot-starter', '@springBootApplication'],
            'spring_mvc': ['spring-mvc', 'DispatcherServlet'],
            'jakarta': ['jakarta.servlet', 'jakarta.ejb'],
            'quarkus': ['quarkus', 'io.quarkus'],
            'micronaut': ['micronaut', 'io.micronaut'],
            'play': ['play.api'],
            'mybatis': ['mybatis', 'SqlSessionFactory'],
        }
        
        for fw, keywords in frameworks.items():
            for kw in keywords:
                for java_file in self.java_files[:200]:
                    try:
                        if kw.lower() in java_file.read_text(errors='ignore').lower():
                            arch['framework'] = fw
                            break
                    except:
                        pass
                if arch['framework'] != 'unknown':
                    break
            if arch['framework'] != 'unknown':
                break
        
        # 检测架构模式
        for pattern, keywords in self.ARCH_PATTERNS.items():
            if keywords:
                for kw in keywords:
                    for java_file in self.java_files[:200]:
                        try:
                            if kw.lower() in java_file.read_text(errors='ignore').lower():
                                arch['pattern'] = pattern
                                break
                        except:
                            pass
                    if arch['pattern'] != 'unknown':
                        break
                if arch['pattern'] != 'unknown':
                    break
        
        # 检测组件
        components = []
        component_patterns = [
            (r'@Controller', 'Controller'),
            (r'@Service', 'Service'),
            (r'@Repository', 'Repository'),
            (r'@Component', 'Component'),
            (r'@Entity', 'Entity'),
            (r'@RestController', 'RestController'),
            (r'@Mapper', 'Mapper'),
            (r'@RequestMapping', 'RequestMapping'),
        ]
        
        for pattern, name in component_patterns:
            count = 0
            for java_file in self.java_files[:300]:
                try:
                    content = java_file.read_text(errors='ignore')
                    count += len(re.findall(pattern, content))
                except:
                    pass
            if count > 0:
                components.append({'name': name, 'count': count})
        
        arch['components'] = sorted(components, key=lambda x: x['count'], reverse=True)[:8]
        
        return arch

    def _generate_summary(self, result: Dict) -> str:
        """生成分析摘要"""
        lines = [
            f"# {result['project_name']} 业务分析 (v2)",
            "",
            f"**语言**: Java",
            f"**框架**: {result['framework']}",
            f"**架构模式**: {result['architecture']['pattern']}",
            "",
            "## 功能模块",
            "",
        ]
        
        features = result.get('features', [])
        if features:
            lines.append(f"检测到 {len(features)} 个功能类型:")
            lines.append("")
            for f in features:
                lines.append(f"- {f}")
        else:
            lines.append("- 未检测到明确功能特征")
        
        lines.extend([
            "",
            "## 架构组件",
            "",
        ])
        
        components = result['architecture'].get('components', [])
        if components:
            for c in components[:8]:
                lines.append(f"- {c['name']}: {c['count']} 个")
        else:
            lines.append("- 未检测到组件统计")
        
        lines.extend([
            "",
            "## 模块结构",
            "",
        ])
        
        modules = result.get('modules', [])
        if modules:
            for m in modules[:5]:
                lines.append(f"- {m}")
        else:
            lines.append("- 未检测到模块信息")
        
        return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 java_business_analyzer_v2.py <project_path>")
        sys.exit(1)
    
    analyzer = JavaBusinessAnalyzerV2(sys.argv[1])
    result = analyzer.analyze()
    print(result['summary'])
