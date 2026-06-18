#!/usr/bin/env python3
"""learn 模式 — 从代码仓库学习并生成知识库

Usage:
    python3 learn_repo.py --profile profiles/my-service.json --output-dir knowledge/
    
流程:
    1. 解析 Profile，获取 repositories 列表
    2. 对每个仓库调用对应语言的 scanner（Go/Python/Java）
    3. 构建多仓库依赖图
    4. 组装 IR + 依赖图 → LLM prompt
    5. 调用 LLM 生成知识库
    6. 写入 wiki_engine + markdown
"""

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================================
# IR (Intermediate Representation) — 多语言统一中间表示
# ============================================================================

@dataclass
class StructDef:
    """结构体定义（Go struct / Python class / Java class）"""
    name: str
    file: str
    lines: tuple = (0, 0)
    fields: List[Dict] = field(default_factory=list)
    methods: List[Dict] = field(default_factory=list)
    table_name: Optional[str] = None  # Go GORM TableName


@dataclass
class FuncDef:
    """函数/方法定义"""
    name: str
    file: str
    lines: tuple = (0, 0)
    params: List[Dict] = field(default_factory=list)
    returns: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    is_route: bool = False  # 是否是 API 路由
    route_path: Optional[str] = None
    http_method: Optional[str] = None


@dataclass
class RouteDef:
    """路由定义"""
    path: str
    method: str  # GET/POST/PUT/DELETE
    handler: str  # 处理函数名
    module: str  # 所属模块
    file: str
    middleware: List[str] = field(default_factory=list)


@dataclass
class ImportDef:
    """导入依赖"""
    module: str
    names: List[str] = field(default_factory=list)
    is_local: bool = False  # 是否是本项目内部依赖
    target_repo: Optional[str] = None  # 指向哪个仓库


@dataclass
class TableDef:
    """数据库表定义"""
    name: str
    entity_class: str
    fields: List[Dict] = field(default_factory=list)
    primary_key: Optional[str] = None
    relations: List[Dict] = field(default_factory=list)  # foreign key / has_many


@dataclass
class ServiceDef:
    """服务层定义"""
    name: str
    file: str
    methods: List[Dict] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)  # 依赖的 DAO/外部服务


@dataclass
class IRDocument:
    """完整 IR 文档 — 一个仓库的标准化表示"""
    repo_name: str
    repo_path: str
    language: str
    structs: List[StructDef] = field(default_factory=list)
    functions: List[FuncDef] = field(default_factory=list)
    routes: List[RouteDef] = field(default_factory=list)
    imports: List[ImportDef] = field(default_factory=list)
    tables: List[TableDef] = field(default_factory=list)
    services: List[ServiceDef] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)
    readme: Optional[str] = None


# ============================================================================
# Go Scanner — 基于 regexp 的 Go 代码扫描器
# ============================================================================

class GoScanner:
    """Go 代码扫描器 — 提取 struct、func、route、TableName 等"""
    
    # Go struct 提取（支持 GORM tag）
    STRUCT_RE = re.compile(
        r'type\s+(\w+)\s+struct\s*\{(.*?)\n\}',
        re.DOTALL
    )
    # TableName 方法
    TABLE_NAME_RE = re.compile(
        r'func.*?\*\w+\)\s+TableName\(\)\s+string\s*\{[^}]*return\s+"([^"]+)"'
    )
    # func 定义（顶层函数和方法）
    FUNC_RE = re.compile(
        r'func\s+(\(?[\w\s\*,&<>]+\))?\s+(\w+)\s*\(([^)]*)\)\s*(.*?)\{'
    )
    # route 注册（r.GET / r.POST / group.GET 等）
    ROUTE_RE = re.compile(
        r'(?:r|group|engine)\.(GET|POST|PUT|DELETE|PATCH)\s*\(\s*"([^"]+)"'
    )
    # import 语句
    IMPORT_RE = re.compile(
        r'"([^"]+)"'
    )
    # gorm tag 提取
    GORM_TAG_RE = re.compile(
        r'gorm:"([^"]*)"'
    )
    # json tag 提取
    JSON_TAG_RE = re.compile(
        r'json:"([^"]*)"'
    )
    
    def scan_file(self, file_path: Path) -> Dict[str, Any]:
        """扫描单个 Go 文件"""
        try:
            content = file_path.read_text(encoding='utf-8', errors='replace')
        except Exception:
            return {"status": "degraded", "reason": "read_failed"}
        
        result = {
            "file": str(file_path),
            "structs": [],
            "funcs": [],
            "routes": [],
            "imports": [],
            "tables": [],
        }
        
        # 提取 struct
        for match in self.STRUCT_RE.finditer(content):
            struct_name = match.group(1)
            body = match.group(2)
            
            # 提取 TableName
            table_name = None
            if struct_name + "Entity" in content or struct_name + "Model" in content:
                tn_match = self.TABLE_NAME_RE.search(content)
                if tn_match:
                    table_name = tn_match.group(1)
            
            # 提取字段
            fields = []
            for line in body.strip().split('\n'):
                line = line.strip()
                if not line or line.startswith('//'):
                    continue
                # 匹配 `field Type \`tag\``
                field_match = re.match(r'(\w+)\s+(\S+)', line)
                if field_match:
                    field_name = field_match.group(1)
                    field_type = field_match.group(2)
                    
                    gorm_tags = self.GORM_TAG_RE.findall(line)
                    json_tags = self.JSON_TAG_RE.findall(line)
                    
                    fields.append({
                        "name": field_name,
                        "type": field_type,
                        "gorm_tag": gorm_tags[0] if gorm_tags else None,
                        "json_tag": json_tags[0] if json_tags else None,
                    })
            
            struct_def = {
                "name": struct_name,
                "fields": fields[:30],  # 限制字段数
                "table_name": table_name,
                "field_count": len(fields),
            }
            result["structs"].append(struct_def)
        
        # 提取 route
        for match in self.ROUTE_RE.finditer(content):
            result["routes"].append({
                "method": match.group(1),
                "path": match.group(2),
                "file": str(file_path.relative_to(file_path.parent.parent)),
            })
        
        # 提取 import
        for match in self.IMPORT_RE.finditer(content):
            imp_path = match.group(1)
            result["imports"].append({
                "module": imp_path,
                "is_local": "git." in imp_path and "github.com" not in imp_path,
            })
        
        return result
    
    def scan_directory(self, dir_path: Path, max_files: int = 500) -> IRDocument:
        """扫描整个目录"""
        ir = IRDocument(
            repo_name=dir_path.name,
            repo_path=str(dir_path),
            language="go",
        )
        
        count = 0
        for go_file in sorted(dir_path.rglob("*.go")):
            if count >= max_files:
                break
            if "vendor/" in str(go_file) or ".git/" in str(go_file):
                continue
            
            result = self.scan_file(go_file)
            count += 1
            
            for s in result.get("structs", []):
                ir.structs.append(StructDef(
                    name=s["name"],
                    file=str(go_file.relative_to(dir_path.parent)),
                    table_name=s.get("table_name"),
                    fields=s.get("fields", []),
                ))
            
            for r in result.get("routes", []):
                ir.routes.append(RouteDef(
                    path=r["path"],
                    method=r["method"],
                    handler="",
                    module="",
                    file=str(go_file.relative_to(dir_path.parent)),
                ))
            
            for imp in result.get("imports", []):
                ir.imports.append(ImportDef(
                    module=imp["module"],
                    is_local=imp.get("is_local", False),
                ))
        
        return ir


# ============================================================================
# Python Scanner — 基于 AST 的 Python 代码扫描器（复用 knowledge_extractor）
# ============================================================================

class PythonScanner:
    """Python 代码扫描器"""
    
    def __init__(self, extractor=None):
        self.extractor = extractor
    
    def scan_file(self, file_path: Path) -> Dict[str, Any]:
        """扫描单个 Python 文件"""
        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception:
            return {"status": "degraded", "reason": "read_failed"}
        
        import ast
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {"status": "degraded", "reason": "syntax_error"}
        
        result = {
            "file": str(file_path),
            "functions": [],
            "classes": [],
            "imports": [],
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                result["functions"].append({
                    "name": node.name,
                    "args": [a.arg for a in node.args.args],
                    "lineno": node.lineno,
                    "docstring": ast.get_docstring(node),
                })
            elif isinstance(node, ast.ClassDef):
                result["classes"].append({
                    "name": node.name,
                    "methods": [m.name for m in node.body if isinstance(m, ast.FunctionDef)],
                    "lineno": node.lineno,
                })
            elif isinstance(node, ast.ImportFrom):
                result["imports"].append({
                    "module": node.module,
                    "names": [alias.name for alias in node.names],
                })
        
        return result
    
    def scan_directory(self, dir_path: Path, max_files: int = 500) -> IRDocument:
        """扫描整个目录"""
        ir = IRDocument(
            repo_name=dir_path.name,
            repo_path=str(dir_path),
            language="python",
        )
        
        count = 0
        for py_file in sorted(dir_path.rglob("*.py")):
            if count >= max_files:
                break
            
            result = self.scan_file(py_file)
            count += 1
            
            for f in result.get("functions", []):
                ir.functions.append(FuncDef(
                    name=f["name"],
                    file=str(py_file.relative_to(dir_path.parent)),
                    params=f.get("args", []),
                ))
            
            for c in result.get("classes", []):
                ir.structs.append(StructDef(
                    name=c["name"],
                    file=str(py_file.relative_to(dir_path.parent)),
                    methods=[{"name": m} for m in c.get("methods", [])],
                ))
        
        return ir


# ============================================================================
# Multi-Repo Analyzer — 多仓库关联分析
# ============================================================================

class MultiRepoAnalyzer:
    """多仓库依赖分析 — 构建仓库间的 import 关系图"""
    
    def analyze(self, repos: List[Dict]) -> Dict[str, Any]:
        """
        分析多个仓库之间的依赖关系
        输入: Profile 中的 repositories 列表
        输出: 依赖图 + 跨仓库引用
        """
        dep_graph = {
            "nodes": [],  # 仓库节点
            "edges": [],  # 依赖边
            "cross_refs": [],  # 跨仓库符号引用
        }
        
        # 构建 import prefix → repo 的映射
        repo_map = {}
        for repo in repos:
            repo_map[repo["name"]] = repo
        
        # 对每个仓库，分析其 import 是否指向其他仓库
        for repo_name, repo_info in repo_map.items():
            dep_graph["nodes"].append({
                "name": repo_name,
                "path": repo_info["path"],
                "language": repo_info.get("language", "unknown"),
            })
            
            # 扫描该仓库的 import
            repo_path = Path(repo_info["path"])
            if not repo_path.exists():
                continue
            
            scanner = self._get_scanner(repo_info.get("language", "go"))
            ir = scanner.scan_directory(repo_path)
            
            for imp in ir.imports:
                # 检查是否指向其他仓库
                for other_name, other_info in repo_map.items():
                    if other_name == repo_name:
                        continue
                    if imp.module.startswith(other_info.get("import_prefix", "")):
                        dep_graph["edges"].append({
                            "from": repo_name,
                            "to": other_name,
                            "symbol": imp.names,
                        })
        
        return dep_graph
    
    def _get_scanner(self, language: str):
        if language == "python":
            return PythonScanner()
        return GoScanner()


# ============================================================================
# LLM Knowledge Generator — LLM 学习总结
# ============================================================================

class LLMKnowledgeGenerator:
    """LLM 学习总结 — 将 IR + 依赖图转化为可读知识库"""
    
    def build_prompt(self, ir: IRDocument, dep_graph: Dict, repos: List[Dict]) -> str:
        """构建 LLM prompt"""
        prompt_parts = []
        
        prompt_parts.append("# 代码库学习任务")
        prompt_parts.append("")
        prompt_parts.append("你是一个资深软件架构师。请基于以下代码扫描结果，")
        prompt_parts.append("总结这个系统的架构、业务流程、数据模型和关键技术决策。")
        prompt_parts.append("")
        
        # 仓库信息
        prompt_parts.append("## 仓库信息")
        for repo in repos:
            prompt_parts.append(f"- **{repo['name']}**: {repo.get('language', 'unknown')} @ {repo['path']}")
        prompt_parts.append("")
        
        # 依赖图
        if dep_graph.get("edges"):
            prompt_parts.append("## 仓库依赖")
            for edge in dep_graph["edges"]:
                prompt_parts.append(f"- {edge['from']} → {edge['to']}")
            prompt_parts.append("")
        
        # IR 摘要
        prompt_parts.append("## 代码结构摘要")
        prompt_parts.append(f"- Structs: {len(ir.structs)}")
        prompt_parts.append(f"- Functions: {len(ir.functions)}")
        prompt_parts.append(f"- Routes: {len(ir.routes)}")
        prompt_parts.append(f"- Imports: {len(ir.imports)}")
        prompt_parts.append("")
        
        # 关键 struct（带 TableName 的通常是数据库表）
        db_structs = [s for s in ir.structs if s.table_name]
        other_structs = [s for s in ir.structs if not s.table_name]
        
        if db_structs:
            prompt_parts.append("## 数据库表推断")
            for s in db_structs[:20]:
                prompt_parts.append(f"- **{s.name}** → `{s.table_name}` ({len(s.fields)} fields)")
                for f in s.fields[:8]:
                    gorm = f.get('gorm_tag', '')
                    pk = 'PRIMARY_KEY' in gorm if gorm else False
                    pk_str = ' [PK]' if pk else ''
                    prompt_parts.append(f"  - `{f['name']}`: {f.get('type', '?')}{pk_str}")
            prompt_parts.append("")
        
        # 重要业务 struct（按命名模式筛选）
        important_structs = []
        for s in other_structs:
            name_lower = s.name.lower()
            if any(kw in name_lower for kw in ['service', 'manager', 'handler', 'module', 'config', 'request', 'response']):
                important_structs.append(s)
        
        if important_structs:
            prompt_parts.append("## 关键业务 Struct")
            for s in important_structs[:30]:
                prompt_parts.append(f"- **{s.name}** ({len(s.fields)} fields, {len(s.methods)} methods)")
            prompt_parts.append("")
        
        # 路由
        if ir.routes:
            prompt_parts.append("## API 路由")
            for r in ir.routes[:30]:
                prompt_parts.append(f"- `{r.method} {r.path}` ({r.file})")
            prompt_parts.append("")
        
        # Service 层
        services = [s for s in ir.structs if "service" in s.name.lower() or "manager" in s.name.lower()]
        if services:
            prompt_parts.append("## 服务层")
            for s in services[:15]:
                prompt_parts.append(f"- **{s.name}** ({len(s.methods)} methods)")
            prompt_parts.append("")
        
        # 配置
        if ir.config_files:
            prompt_parts.append("## 配置文件")
            for cf in ir.config_files[:10]:
                prompt_parts.append(f"- {cf}")
            prompt_parts.append("")
        
        prompt_parts.append("---")
        prompt_parts.append("")
        prompt_parts.append("请基于以上信息，输出以下结构化知识：")
        prompt_parts.append("")
        prompt_parts.append("1. **架构总览** — 系统定位、技术栈、服务拆分、部署架构")
        prompt_parts.append("2. **核心业务流程** — 主要业务场景的流程描述（用文字，不需要 mermaid）")
        prompt_parts.append("3. **数据库表结构** — 表名、字段、ER 关系")
        prompt_parts.append("4. **服务层架构** — Service/DAO/Model 分层说明")
        prompt_parts.append("5. **外部系统集成** — 第三方 API、消息队列等")
        prompt_parts.append("6. **术语 Glossary** — 业务术语及其含义")
        
        return "\n".join(prompt_parts)
    
    def parse_llm_output(self, llm_response: str) -> Dict[str, Any]:
        """解析 LLM 输出的知识库 — 按标题分割"""
        knowledge = {
            "architecture": "",
            "business_flows": "",
            "database_schema": "",
            "service_architecture": "",
            "external_systems": "",
            "glossary": {},
        }
        
        section_map = {
            "架构总览": "architecture",
            "核心业务流程": "business_flows",
            "数据库表结构": "database_schema",
            "服务层架构": "service_architecture",
            "外部系统集成": "external_systems",
            "术语 Glossary": "glossary",
        }
        
        # 按 Markdown heading 级别分割：优先找 # (一级标题) 作为 section boundary
        # 因为 LLM 输出通常用 # 表示主标题，## 表示子标题
        sections = re.split(r'^# ', llm_response, flags=re.MULTILINE)
        
        for section in sections:
            for title, key in section_map.items():
                if section.startswith(title):
                    content = section[len(title):].strip()
                    if key == "glossary":
                        for line in content.split("\n"):
                            line = line.strip().lstrip("- ")
                            if ":" in line:
                                parts = line.split(":", 1)
                                knowledge[key][parts[0].strip()] = parts[1].strip()
                    else:
                        knowledge[key] = content
                    break
        
        return knowledge
    
    def auto_call_llm(self, prompt: str, knowledge_base_dir: str, 
                      dry_run: bool = False) -> Dict[str, Any]:
        """
        自动调用 LLM 生成知识库
        
        策略：
        1. 在 Hermes 环境中，通过 agent 自身调用 LLM（利用当前 session）
        2. 解析 LLM 输出，写入对应的知识文件
        3. 如果 dry_run=True，只打印 prompt 不调用
        
        注意：这个函数需要在 Hermes agent 上下文中运行，
        因为 Python 脚本本身没有 LLM API 访问权限。
        实际用法：脚本生成 prompt → 返回给 agent → agent 调用 LLM → 
        agent 把结果传回来写入文件。
        """
        if dry_run:
            return {
                "status": "dry_run",
                "prompt_length": len(prompt),
                "message": "Dry run — prompt generated, not sent to LLM",
            }
        
        # 在非 Hermes 环境下（如 CI），返回 prompt 让外部调用
        return {
            "status": "awaiting_llm",
            "prompt_length": len(prompt),
            "prompt_file": knowledge_base_dir + "/learn_prompt.md",
            "message": "LLM response expected. Write output to knowledge files.",
        }


# ============================================================================
# Knowledge Writer — 将 LLM 输出写入知识库文件
# ============================================================================

class KnowledgeWriter:
    """将解析后的知识库写入文件"""
    
    def write(self, knowledge: Dict, knowledge_base_dir: str) -> List[str]:
        """
        将知识库写入目录
        
        Returns: 写入的文件列表
        """
        kb_path = Path(knowledge_base_dir)
        kb_path.mkdir(parents=True, exist_ok=True)
        
        files_written = []
        
        # architecture.md
        if knowledge.get("architecture"):
            content = f"# 架构总览\n\n{knowledge['architecture']}\n"
            kb_path.joinpath("architecture.md").write_text(content, encoding="utf-8")
            files_written.append("architecture.md")
        
        # flows.md
        if knowledge.get("business_flows"):
            content = f"# 核心业务流程\n\n{knowledge['business_flows']}\n"
            kb_path.joinpath("flows.md").write_text(content, encoding="utf-8")
            files_written.append("flows.md")
        
        # schema.md
        if knowledge.get("database_schema"):
            content = f"# 数据库表结构\n\n{knowledge['database_schema']}\n"
            kb_path.joinpath("schema.md").write_text(content, encoding="utf-8")
            files_written.append("schema.md")
        
        # service.md
        if knowledge.get("service_architecture"):
            content = f"# 服务层架构\n\n{knowledge['service_architecture']}\n"
            kb_path.joinpath("services.md").write_text(content, encoding="utf-8")
            files_written.append("services.md")
        
        # external-systems.md
        if knowledge.get("external_systems"):
            content = f"# 外部系统集成\n\n{knowledge['external_systems']}\n"
            kb_path.joinpath("external-systems.md").write_text(content, encoding="utf-8")
            files_written.append("external-systems.md")
        
        # glossary.md
        if knowledge.get("glossary"):
            lines = ["# 术语 Glossary\n", ""]
            for key, val in sorted(knowledge["glossary"].items()):
                lines.append(f"- **{key}**: {val}")
            content = "\n".join(lines)
            kb_path.joinpath("glossary.md").write_text(content, encoding="utf-8")
            files_written.append("glossary.md")
        
        # 更新 index.md
        index = kb_path / "index.md"
        if index.exists() and index.stat().st_size > 0:
            # 追加写入状态
            content = index.read_text(encoding="utf-8")
            written_docs = "\n".join(f"| ✅ [{f}]({f}) | 已生成 |" for f in files_written)
            content = content.replace("待生成", "✅ 已生成")
            index.write_text(content, encoding="utf-8")
        
        return files_written


# ============================================================================
# Incremental Scanner — 增量扫描
# ============================================================================

class IncrementalScanner:
    """增量扫描 — 只扫描自上次以来变更的文件"""
    
    def __init__(self, knowledge_base_dir: str):
        self.kb_dir = Path(knowledge_base_dir)
        self.last_scan_file = self.kb_dir / ".last_scan_timestamp"
    
    def get_last_scan_time(self) -> Optional[float]:
        """获取上次扫描时间戳"""
        if self.last_scan_file.exists():
            return float(self.last_scan_file.read_text().strip())
        return None
    
    def set_last_scan_time(self):
        """更新上次扫描时间戳"""
        self.last_scan_file.write_text(str(time.time()), encoding="utf-8")
    
    def find_changed_files(self, repo_path: Path) -> List[Path]:
        """找出自上次扫描以来变更的文件"""
        last_time = self.get_last_scan_time()
        if last_time is None:
            return []  # 首次扫描，返回空表示全量扫
        
        modified = []
        for go_file in repo_path.rglob("*.go"):
            if "vendor/" in str(go_file) or ".git/" in str(go_file):
                continue
            mtime = go_file.stat().st_mtime
            if mtime > last_time:
                modified.append(go_file)
        
        return modified

class WikiIngestor:
    """将 LLM 生成的知识库写入 wiki_engine"""
    
    def ingest(self, knowledge: Dict, wiki_path: Path, repo_name: str):
        """写入 wiki 页面"""
        wiki_path.mkdir(parents=True, exist_ok=True)
        
        # 生成 wiki 页面
        pages = {
            "index.md": f"# {repo_name} 知识库\n\n{knowledge.get('architecture', '')}",
            "architecture.md": f"# 架构总览\n\n{knowledge.get('architecture', '')}",
            "flows.md": f"# 核心流程\n\n{knowledge.get('business_flows', '')}",
            "schema.md": f"# 数据库表结构\n\n{knowledge.get('database_schema', '')}",
            "services.md": f"# 服务层\n\n{knowledge.get('service_architecture', '')}",
            "glossary.md": f"# 术语表\n\n" + "\n".join(f"- **{k}**: {v}" for k, v in knowledge.get("glossary", {}).items()),
        }
        
        for filename, content in pages.items():
            page_path = wiki_path / filename
            page_path.write_text(content, encoding="utf-8")
        
        return list(pages.keys())


# ============================================================================
# Main Entry Point — learn 模式
# ============================================================================

def learn_from_repos(profile_path: str, output_dir: str, wiki_path: Optional[str] = None, knowledge_base_dir: Optional[str] = None):
    """
    learn 模式主入口
    
    Args:
        profile_path: Profile JSON 文件路径
        output_dir: 临时输出目录（prompt 等）
        wiki_path: wiki_engine 路径（可选）
        knowledge_base_dir: 知识库持久化目录（可选，默认从 profile 推断）
    """
    # 1. 加载 Profile
    with open(profile_path) as f:
        profile = json.load(f)
    
    # 从 profile 推断知识库目录
    if knowledge_base_dir is None:
        skill_dir = Path(__file__).parent.parent
        business_domain = profile.get("business_domain", "unknown")
        knowledge_base_dir = str(skill_dir / "knowledge" / business_domain)
    
    os.makedirs(knowledge_base_dir, exist_ok=True)
    
    repos = profile.get("repositories", [])
    if not repos:
        print("ERROR: No repositories configured in profile")
        sys.exit(1)
    
    learn_config = profile.get("learn_config", {})
    max_files = learn_config.get("max_files_per_lang", 500)
    
    # 2. 扫描每个仓库
    all_ir = []
    for repo in repos:
        repo_path = Path(repo["path"])
        if not repo_path.exists():
            print(f"WARNING: Repository not found: {repo['path']}")
            continue
        
        language = repo.get("language", "go")
        print(f"Scanning {repo['name']} ({language})...")
        
        if language == "go":
            scanner = GoScanner()
        elif language == "python":
            scanner = PythonScanner()
        else:
            print(f"WARNING: Unsupported language: {language}, skipping")
            continue
        
        ir = scanner.scan_directory(repo_path, max_files=max_files)
        ir.repo_name = repo["name"]
        ir.repo_path = repo["path"]
        all_ir.append(ir)
        
        print(f"  Found: {len(ir.structs)} structs, {len(ir.routes)} routes, {len(ir.imports)} imports")
    
    if not all_ir:
        print("ERROR: No repositories scanned successfully")
        sys.exit(1)
    
    # 3. 多仓库关联分析
    analyzer = MultiRepoAnalyzer()
    dep_graph = analyzer.analyze(repos)
    print(f"Dependency graph: {len(dep_graph.get('edges', []))} edges")
    
    # 4. 构建 LLM prompt
    generator = LLMKnowledgeGenerator()
    combined_ir = all_ir[0]  # 取第一个作为主 IR
    prompt = generator.build_prompt(combined_ir, dep_graph, repos)
    
    # 5. 输出 prompt（供 LLM 调用）
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    prompt_file = output_path / "learn_prompt.md"
    prompt_file.write_text(prompt, encoding="utf-8")
    
    # 存档到知识库目录
    kb_prompt_file = Path(knowledge_base_dir) / "learn_prompt.md"
    kb_prompt_file.write_text(prompt, encoding="utf-8")
    
    print(f"\nPrompt written to: {prompt_file}")
    print(f"Prompt archived to: {kb_prompt_file}")
    print(f"Knowledge base dir: {knowledge_base_dir}")
    print(f"\nRun LLM with this prompt, then save output to:")
    print(f"  {knowledge_base_dir}/architecture.md  (架构总览)")
    print(f"  {knowledge_base_dir}/flows.md         (核心流程)")
    print(f"  {knowledge_base_dir}/schema.md        (表结构)")
    print(f"  {knowledge_base_dir}/glossary.md      (术语表)")
    
    # 6. 写入知识库索引
    index_file = Path(knowledge_base_dir) / "index.md"
    if not index_file.exists() or index_file.stat().st_size == 0:
        index_content = f"# {profile.get('business_domain', 'Unknown')} 知识库\n\n"
        index_content += f"**扫描时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        index_content += f"**仓库**: {', '.join(r['name'] for r in repos)}\n\n"
        index_content += "## 文档\n\n"
        index_content += "| 文档 | 状态 |\n|------|------|\n"
        index_content += "| [architecture.md](architecture.md) | 架构总览 |\n"
        index_content += "| [flows.md](flows.md) | 核心业务流程 |\n"
        index_content += "| [schema.md](schema.md) | 数据库表结构 |\n"
        index_content += "| [services.md](services.md) | 服务层架构 |\n"
        index_content += "| [external-systems.md](external-systems.md) | 外部系统集成 |\n"
        index_content += "| [glossary.md](glossary.md) | 术语 Glossary |\n"
        index_content += "| [learn_prompt.md](learn_prompt.md) | 原始 LLM prompt |\n"
        index_file.write_text(index_content, encoding="utf-8")
        print(f"\nKnowledge index created: {index_file}")
    
    # 7. （可选）如果有 wiki_path，写入 wiki
    if wiki_path:
        # 这里需要 LLM 响应，暂时跳过
        print(f"\nNote: Wiki ingestion requires LLM response. Save prompt output first.")
    
    return {
        "status": "ok",
        "repos_scanned": len(all_ir),
        "prompt_file": str(prompt_file),
        "kb_prompt_file": str(kb_prompt_file),
        "knowledge_base_dir": knowledge_base_dir,
        "output_dir": str(output_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Learn from code repositories")
    parser.add_argument("--profile", required=True, help="Profile JSON path")
    parser.add_argument("--output-dir", required=True, help="Knowledge output directory")
    parser.add_argument("--wiki-path", help="Wiki engine path for ingestion")
    parser.add_argument("--llm-response", help="LLM response text (file path or raw text via stdin)")
    parser.add_argument("--auto-llm", action="store_true", help="Auto-call LLM (requires Hermes agent context)")
    parser.add_argument("--incremental", action="store_true", help="Incremental scan (only changed files)")
    parser.add_argument("--dry-run", action="store_true", help="Just generate prompt, don't write anything")
    args = parser.parse_args()
    
    result = learn_from_repos(
        profile_path=args.profile,
        output_dir=args.output_dir,
        wiki_path=args.wiki_path,
    )
    
    if result["status"] != "ok":
        print(f"\n❌ Learn failed: {result.get('reason', 'unknown')}")
        sys.exit(1)
    
    kb_dir = result["knowledge_base_dir"]
    prompt_file = Path(kb_dir) / "learn_prompt.md"
    
    if args.dry_run:
        print(f"\n📝 Dry run complete. Prompt saved to: {prompt_file}")
        print(f"   Copy and send to LLM, then save response to knowledge files.")
        return
    
    # 如果有 LLM 响应，解析并写入
    if args.llm_response:
        print(f"\n📥 Processing LLM response from: {args.llm_response}")
        
        # 读取 LLM 响应
        if os.path.isfile(args.llm_response):
            llm_text = Path(args.llm_response).read_text(encoding="utf-8")
        else:
            llm_text = args.llm_response
        
        # 解析
        generator = LLMKnowledgeGenerator()
        knowledge = generator.parse_llm_output(llm_text)
        
        # 写入
        writer = KnowledgeWriter()
        files = writer.write(knowledge, kb_dir)
        
        print(f"✅ Knowledge files written: {', '.join(files)}")
        print(f"   Directory: {kb_dir}")
        return
    
    # 如果没有 LLM 响应，提示用户
    print(f"\n✅ Learn complete!")
    print(f"   Prompt: {prompt_file}")
    print(f"   Knowledge base: {kb_dir}")
    print(f"\n📋 Next step: Send prompt to LLM, then run again with --llm-response")
    print(f"   Example:")
    print(f"     # 1. 读取 prompt")
    print(f"     cat {prompt_file}")
    print(f"     # 2. 发给 LLM，保存响应到 /tmp/llm_response.txt")
    print(f"     # 3. 写入知识库")
    print(f"     python3 learn_repo.py --profile {args.profile} --llm-response /tmp/llm_response.txt")


if __name__ == "__main__":
    main()
