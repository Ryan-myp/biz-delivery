#!/usr/bin/env python3
"""
biz-delivery v3.0 — 智能业务交付框架

完整的端到端业务交付链路：
  PRD Review → Technical Design → Agent Tasks → Coding → Test Execution → Quality Gate

核心原则：流程通用，业务通过 Profile + Hooks 配置扩展
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

# 导入核心引擎
sys.path.insert(0, str(Path(__file__).parent))
from learn_repo import learn_from_repos, IRDocument
from llm_client import LLMClient
from review_engine import ReviewEngine
from td_engine import TDEngine
from test_engine import TestEngine


# ============================================================================
# 数据模型
# ============================================================================

class TaskPriority(Enum):
    """任务优先级"""
    P0 = "P0"  # 阻塞性任务
    P1 = "P1"  # 重要任务
    P2 = "P2"  # 一般任务


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class AgentPhase(Enum):
    """Agent 执行阶段"""
    SETUP = "setup"           # 环境准备
    IMPLEMENT = "implement"   # 代码实现
    TEST = "test"             # 测试验证
    REVIEW = "review"         # 代码审查


@dataclass
class AgentTask:
    """Agent 开发任务"""
    id: str
    title: str
    description: str
    priority: TaskPriority
    phase: AgentPhase
    depends_on: List[str]  # 依赖的任务 ID
    files_to_create: List[str]
    files_to_modify: List[str]
    code_template: str  # 代码模板（空壳）
    test_cases: List[str]  # 关联的测试用例
    acceptance_criteria: List[str]  # 验收标准
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_prompt(self) -> str:
        """生成 Agent 执行 Prompt"""
        prompt = f"""# 开发任务: {self.title}

## 任务描述
{self.description}

## 优先级
{self.priority.value}

## 所属阶段
{self.phase.value}

## 依赖任务
{', '.join(self.depends_on) if self.depends_on else '无'}

## 文件操作
- 新建文件: {', '.join(self.files_to_create)}
- 修改文件: {', '.join(self.files_to_modify)}

## 代码模板
```
{self.code_template}
```

## 测试用例
{chr(10).join(f'- {tc}' for tc in self.test_cases)}

## 验收标准
{chr(10).join(f'✅ {c}' for c in self.acceptance_criteria)}

## 执行要求
1. 严格按代码模板实现，不要添加额外逻辑
2. 确保所有测试用例通过
3. 完成后返回: [TASK_COMPLETE] {self.id}
"""
        return prompt


@dataclass
class DeliveryReport:
    """交付报告"""
    prd_review: Dict[str, Any]
    technical_design: Dict[str, Any]
    agent_tasks: List[Dict[str, Any]]
    test_cases: Dict[str, Any]
    execution_result: Dict[str, Any]
    quality_gate: Dict[str, Any]
    
    def summary(self) -> str:
        return f"""
# biz-delivery v3.0 交付报告

## 1. PRD 审查
- 状态: {self.prd_review.get('status', 'unknown')}
- P0 问题: {len(self.prd_review.get('p0_issues', []))}
- P1 问题: {len(self.prd_review.get('p1_issues', []))}

## 2. 技术方案
- 方案类型: {self.technical_design.get('type', 'unknown')}
- 新增文件: {self.technical_design.get('new_files', [])}
- 修改文件: {self.technical_design.get('modified_files', [])}

## 3. Agent 开发任务
- 总任务数: {len(self.agent_tasks)}
- P0 任务: {sum(1 for t in self.agent_tasks if t.get('priority') == 'P0')}
- P1 任务: {sum(1 for t in self.agent_tasks if t.get('priority') == 'P1')}

## 4. 测试用例
- 总用例数: {self.test_cases.get('total_cases', 0)}
- P0 用例: {self.test_cases.get('p0_count', 0)}
- 覆盖率: {self.test_cases.get('coverage', 'N/A')}

## 5. 执行结果
- 状态: {self.execution_result.get('status', 'unknown')}
- 通过率: {self.execution_result.get('pass_rate', 'N/A')}

## 6. 质量门禁
- 是否通过: {self.quality_gate.get('passed', False)}
- 阻塞项: {self.quality_gate.get('blockers', [])}
"""


# ============================================================================
# Agent Task Generator — Agent 开发任务生成器
# ============================================================================

class AgentTaskGenerator:
    """从 TD 生成 Agent 可执行的任务列表"""
    
    def __init__(self, profile: dict, ir_data: dict):
        self.profile = profile
        self.ir = ir_data
        self.task_counter = 0
    
    def generate_tasks(self, td_content: str, review_report: str = None) -> List[AgentTask]:
        """从 TD 内容生成 Agent 开发任务
        
        核心逻辑：
        1. 解析 TD 中的模块/接口/表设计
        2. 为每个设计元素生成具体开发任务
        3. 建立任务依赖关系
        4. 生成代码模板（空壳）
        """
        tasks = []
        
        # 1. 解析 TD 提取设计要素
        design_elements = self._parse_td_elements(td_content)
        
        # 2. 按优先级和依赖关系排序
        priorities = self._assign_priorities(design_elements)
        
        # 3. 生成任务
        for element in design_elements:
            task = self._create_task(element, priorities)
            if task:
                tasks.append(task)
        
        # 4. 建立依赖关系
        self._resolve_dependencies(tasks)
        
        # 5. 排序（按优先级和依赖）
        tasks.sort(key=lambda t: (self._priority_score(t.priority), len(t.depends_on)))
        
        return tasks
    
    def _parse_td_elements(self, td_content: str) -> List[Dict]:
        """解析 TD 内容，提取设计要素"""
        elements = []
        
        # 检测新模块
        new_modules = self._extract_new_modules(td_content)
        for mod in new_modules:
            elements.append({
                "type": "module",
                "name": mod,
                "priority": "P0",
                "phase": AgentPhase.IMPLEMENT,
                "description": f"实现 {mod} 模块",
                "files": self._guess_files(mod),
            })
        
        # 检测新接口
        new_interfaces = self._extract_new_interfaces(td_content)
        for iface in new_interfaces:
            elements.append({
                "type": "interface",
                "name": iface["name"],
                "priority": "P0",
                "phase": AgentPhase.IMPLEMENT,
                "description": f"实现 {iface['name']} 接口",
                "files": iface.get("files", []),
                "signature": iface.get("signature", ""),
            })
        
        # 检测数据库变更
        db_changes = self._extract_db_changes(td_content)
        for change in db_changes:
            elements.append({
                "type": "database",
                "name": change.get("table", "unknown"),
                "priority": "P0",
                "phase": AgentPhase.SETUP,
                "description": change.get("description", "数据库变更"),
                "files": ["migrations/" + change.get("file", "migration.sql")],
            })
        
        # 检测测试需求
        test_requirements = self._extract_test_requirements(td_content)
        for req in test_requirements:
            elements.append({
                "type": "test",
                "name": req.get("name", "unknown"),
                "priority": req.get("priority", "P1"),
                "phase": AgentPhase.TEST,
                "description": req.get("description", "测试需求"),
                "files": req.get("files", []),
            })
        
        return elements
    
    def _extract_new_modules(self, td_content: str) -> List[str]:
        """从 TD 提取新增模块"""
        modules = []
        # 检测 "新增模块: xxx" 或 "新建 xxx.go" 模式
        import re
        patterns = [
            r'新增模块[：:]\s*(\w+)',
            r'新建\s+([\w\-]+)\.(go|py|java)',
            r'新建模块\s+([\w\-]+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, td_content)
            modules.extend(matches)
        return list(set(modules))
    
    def _extract_new_interfaces(self, td_content: str) -> List[Dict]:
        """从 TD 提取新增接口"""
        interfaces = []
        import re
        # 检测 HTTP 路由
        route_pattern = r'(GET|POST|PUT|DELETE|PATCH)\s+[/\w\{\}-]+'
        routes = re.findall(route_pattern, td_content)
        for route in routes:
            if route not in ['handler', 'service', 'dao']:
                interfaces.append({
                    "name": route,
                    "files": [],
                    "signature": f"func Handle{route}(...)"
                })
        
        # 检测 RPC 方法
        rpc_pattern = r'rpc\s+(\w+)\s*\('
        rpcs = re.findall(rpc_pattern, td_content)
        for rpc in rpcs:
            interfaces.append({
                "name": rpc,
                "files": [],
                "signature": f"func {rpc}(...)"
            })
        
        return interfaces
    
    def _extract_db_changes(self, td_content: str) -> List[Dict]:
        """从 TD 提取数据库变更"""
        changes = []
        import re
        
        # CREATE TABLE
        create_pattern = r'CREATE\s+TABLE\s+(\w+)'
        creates = re.findall(create_pattern, td_content)
        for table in creates:
            changes.append({
                "table": table,
                "description": f"创建表 {table}",
                "file": f"create_{table}.sql"
            })
        
        # ALTER TABLE
        alter_pattern = r'ALTER\s+TABLE\s+\w+\s+(.+?)(?:;|\n)'
        alters = re.findall(alter_pattern, td_content)
        for alter in alters:
            changes.append({
                "table": "existing",
                "description": f"修改表结构: {alter.strip()[:50]}",
                "file": f"alter_table.sql"
            })
        
        return changes
    
    def _extract_test_requirements(self, td_content: str) -> List[Dict]:
        """从 TD 提取测试需求"""
        requirements = []
        import re
        
        # 检测测试相关描述
        test_patterns = [
            r'(测试|Test)\s+([^\n]{10,100})',
            r'需要测试\s+([^\n]{10,100})',
        ]
        for pattern in test_patterns:
            matches = re.findall(pattern, td_content)
            for match in matches:
                if isinstance(match, tuple):
                    desc = match[-1]
                else:
                    desc = match
                requirements.append({
                    "name": desc[:50],
                    "priority": "P1",
                    "description": desc,
                    "files": [f"test_{desc[:20].replace(' ', '_')}.go"]
                })
        
        return requirements[:10]  # 限制数量
    
    def _guess_files(self, module_name: str) -> List[str]:
        """根据模块名推测文件路径"""
        lang = self.profile.get("language", "go")
        if lang == "go":
            return [
                f"internal/{module_name.lower()}/{module_name.lower()}.go",
                f"internal/{module_name.lower()}/handler.go",
                f"internal/{module_name.lower()}/service.go",
                f"internal/{module_name.lower()}/dao.go",
            ]
        elif lang == "python":
            return [
                f"src/{module_name.lower()}/{module_name.lower()}.py",
                f"src/{module_name.lower()}/handler.py",
                f"src/{module_name.lower()}/service.py",
            ]
        return [f"{module_name.lower()}.py"]
    
    def _assign_priorities(self, elements: List[Dict]) -> Dict[str, str]:
        """为设计要素分配优先级"""
        priorities = {}
        for elem in elements:
            if elem["type"] in ["database", "module"]:
                priorities[elem["name"]] = "P0"
            elif elem["type"] == "interface":
                priorities[elem["name"]] = "P0"
            elif elem["type"] == "test":
                priorities[elem["name"]] = "P1"
            else:
                priorities[elem["name"]] = "P2"
        return priorities
    
    def _create_task(self, element: Dict, priorities: Dict) -> Optional[AgentTask]:
        """创建单个开发任务"""
        self.task_counter += 1
        task_id = f"TASK-{self.task_counter:03d}"
        
        # 生成代码模板
        code_template = self._generate_code_template(element)
        
        # 生成验收标准
        acceptance_criteria = self._generate_acceptance_criteria(element)
        
        return AgentTask(
            id=task_id,
            title=f"[{element['type'].upper()}] {element['name']}",
            description=element.get("description", ""),
            priority=TaskPriority(priorities.get(element["name"], "P2")),
            phase=element.get("phase", AgentPhase.IMPLEMENT),
            depends_on=[],
            files_to_create=element.get("files", []),
            files_to_modify=[],
            code_template=code_template,
            test_cases=[],
            acceptance_criteria=acceptance_criteria,
        )
    
    def _generate_code_template(self, element: Dict) -> str:
        """生成代码模板（空壳）"""
        lang = self.profile.get("language", "go")
        elem_type = element.get("type", "")
        name = element.get("name", "Unknown")
        
        if lang == "go":
            if elem_type == "module":
                return f"""package {name.lower()}

// {name}Service 处理 {name} 相关业务逻辑
type {name}Service struct {{
    // TODO: 注入依赖
}}

// New{name}Service 创建 {name}Service 实例
func New{name}Service() *{name}Service {{
    return &{name}Service{{}}
}}

// TODO: 实现业务方法
"""
            elif elem_type == "interface":
                return f"""// Handle{name} 处理 {name} 请求
func Handle{name}(ctx context.Context, req *Request) (*Response, error) {{
    // TODO: 实现业务逻辑
    return nil, nil
}}

// Request {name} 请求参数
type Request struct {{
    // TODO: 定义请求字段
}}

// Response {name} 响应结果
type Response struct {{
    // TODO: 定义响应字段
}}
"""
            elif elem_type == "database":
                return f"""-- Migration: {name}
-- TODO: 实现数据库迁移脚本
"""
        elif lang == "python":
            if elem_type == "module":
                return f"""# {name} 模块
class {name}Service:
    def __init__(self):
        # TODO: 初始化依赖
        pass
    
    # TODO: 实现业务方法
"""
        
        return "# TODO: Implement this module"
    
    def _generate_acceptance_criteria(self, element: Dict) -> List[str]:
        """生成验收标准"""
        criteria = []
        elem_type = element.get("type", "")
        name = element.get("name", "Unknown")
        
        if elem_type == "module":
            criteria.extend([
                f"✅ {name} 模块代码编译通过",
                f"✅ {name} 模块单元测试通过",
                f"✅ {name} 模块集成测试通过",
                f"✅ 代码覆盖率 ≥ 70%",
            ])
        elif elem_type == "interface":
            criteria.extend([
                f"✅ {name} 接口可正常调用",
                f"✅ 正常请求返回 200",
                f"✅ 异常请求返回正确错误码",
                f"✅ 鉴权检查通过",
            ])
        elif elem_type == "database":
            criteria.extend([
                f"✅ 数据库迁移脚本执行成功",
                f"✅ 表结构符合设计",
                f"✅ 索引创建正确",
                f"✅ 迁移后可回滚",
            ])
        
        return criteria
    
    def _resolve_dependencies(self, tasks: List[AgentTask]):
        """解析任务依赖关系"""
        # 数据库任务依赖: 无
        # 模块任务依赖: 数据库任务
        # 接口任务依赖: 模块任务
        
        db_tasks = [t for t in tasks if t.phase == AgentPhase.SETUP]
        impl_tasks = [t for t in tasks if t.phase == AgentPhase.IMPLEMENT]
        test_tasks = [t for t in tasks if t.phase == AgentPhase.TEST]
        
        # 模块依赖数据库
        for task in impl_tasks:
            for db_task in db_tasks:
                if db_task.name.lower() in task.name.lower() or \
                   any(f in task.name.lower() for f in db_task.files_to_create):
                    task.depends_on.append(db_task.id)
        
        # 测试依赖实现
        for task in test_tasks:
            for impl_task in impl_tasks:
                if impl_task.name.lower() in task.name.lower() or \
                   any(f in task.name for f in impl_task.files_to_create):
                    task.depends_on.append(impl_task.id)
    
    def _priority_score(self, priority: TaskPriority) -> int:
        """优先级分数（越低越优先）"""
        return {"P0": 0, "P1": 1, "P2": 2}.get(priority, 2)


# ============================================================================
# Agent Executor — Agent 执行器
# ============================================================================

class AgentExecutor:
    """Agent 开发任务执行器"""
    
    def __init__(self, profile: dict, output_dir: str):
        self.profile = profile
        self.output_dir = Path(output_dir)
        self.tasks: List[AgentTask] = []
        self.execution_log: List[Dict] = []
    
    def execute(self, tasks: List[AgentTask], llm_client: LLMClient) -> Dict:
        """执行 Agent 开发任务
        
        Args:
            tasks: 开发任务列表
            llm_client: LLM 客户端
            
        Returns:
            执行结果
        """
        self.tasks = tasks
        results = {
            "total_tasks": len(tasks),
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "log": [],
        }
        
        print(f"\n🤖 开始执行 {len(tasks)} 个 Agent 开发任务")
        print("=" * 60)
        
        # 按依赖关系排序执行
        executed = set()
        remaining = list(tasks)
        
        while remaining:
            # 找出可执行的任务（所有依赖已完成）
            ready_tasks = []
            blocked_tasks = []
            
            for task in remaining:
                if all(dep in executed for dep in task.depends_on):
                    ready_tasks.append(task)
                else:
                    blocked_tasks.append(task)
            
            if not ready_tasks:
                # 没有可执行任务，可能是循环依赖
                print(f"⚠️  发现循环依赖，跳过剩余 {len(blocked_tasks)} 个任务")
                for task in blocked_tasks:
                    results["skipped"] += 1
                    results["log"].append({
                        "task_id": task.id,
                        "status": "skipped",
                        "reason": "circular_dependency"
                    })
                break
            
            # 执行就绪任务
            for task in ready_tasks:
                print(f"\n📋 执行任务: {task.id} - {task.title}")
                print(f"   优先级: {task.priority.value} | 阶段: {task.phase.value}")
                
                result = self._execute_task(task, llm_client)
                results["log"].append(result)
                
                if result["status"] == "completed":
                    executed.add(task.id)
                    results["completed"] += 1
                    print(f"   ✅ 完成")
                elif result["status"] == "failed":
                    results["failed"] += 1
                    print(f"   ❌ 失败: {result.get('error', 'unknown')}")
                else:
                    results["skipped"] += 1
                    print(f"   ⏭️  跳过")
            
            # 移除已执行任务
            remaining = blocked_tasks
        
        print("\n" + "=" * 60)
        print(f"执行完成: {results['completed']}/{results['total_tasks']} 成功")
        
        return results
    
    def _execute_task(self, task: AgentTask, llm_client: LLMClient) -> Dict:
        """执行单个任务"""
        start_time = time.time()
        
        try:
            # 生成执行 Prompt
            prompt = task.to_prompt()
            
            # 调用 LLM 生成代码
            print(f"   🤖 调用 LLM 生成代码...")
            system_prompt = """You are a senior software developer. 
Implement the task exactly as specified. Follow the code template strictly.
Output only the code, no explanations."""
            
            response = llm_client.chat(prompt, system=system_prompt)
            code_content = response.get("content", "")
            
            if not code_content or len(code_content) < 50:
                return {
                    "task_id": task.id,
                    "status": "failed",
                    "error": "Empty or too short response",
                    "duration": time.time() - start_time,
                }
            
            # 保存生成的代码
            for file_path in task.files_to_create:
                full_path = self.output_dir / "agent_output" / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(code_content, encoding="utf-8")
                print(f"   💾 保存: {full_path}")
            
            # 保存任务执行日志
            log_file = self.output_dir / "agent_output" / f"{task.id}_log.md"
            log_file.write_text(f"""# 任务执行日志: {task.id}

## 基本信息
- 标题: {task.title}
- 优先级: {task.priority.value}
- 阶段: {task.phase.value}
- 创建时间: {time.strftime('%Y-%m-%d %H:%M:%S')}

## 任务描述
{task.description}

## 生成的代码
\`\`\`
{code_content[:2000]}
\`\`\`

## 验收标准
{chr(10).join(f'- {c}' for c in task.acceptance_criteria)}

## 执行耗时
{time.time() - start_time:.1f} 秒
""", encoding="utf-8")
            
            return {
                "task_id": task.id,
                "status": "completed",
                "duration": time.time() - start_time,
                "files_created": task.files_to_create,
                "code_length": len(code_content),
            }
            
        except Exception as e:
            return {
                "task_id": task.id,
                "status": "failed",
                "error": str(e),
                "duration": time.time() - start_time,
            }


# ============================================================================
# Quality Gate — 质量门禁
# ============================================================================

class QualityGate:
    """质量门禁 — 评估交付物质量"""
    
    def __init__(self, profile: dict, output_dir: str):
        self.profile = profile
        self.output_dir = Path(output_dir)
    
    def evaluate(self, delivery_report: DeliveryReport) -> Dict:
        """评估交付质量
        
        Returns:
            质量评估结果
        """
        checks = []
        
        # 1. PRD 审查质量
        review = delivery_report.prd_review
        p0_count = len(review.get("p0_issues", []))
        p1_count = len(review.get("p1_issues", []))
        
        if p0_count > 0:
            checks.append({
                "check": "prd_review_quality",
                "status": "failed",
                "message": f"PRD 审查发现 {p0_count} 个 P0 问题",
                "severity": "critical"
            })
        else:
            checks.append({
                "check": "prd_review_quality",
                "status": "passed",
                "message": "PRD 审查通过，无 P0 问题"
            })
        
        # 2. 技术方案完整性
        td = delivery_report.technical_design
        required_sections = ["架构设计", "接口设计", "数据库设计"]
        missing_sections = [s for s in required_sections if s not in str(td)]
        
        if missing_sections:
            checks.append({
                "check": "td_completeness",
                "status": "warning",
                "message": f"TD 缺少章节: {', '.join(missing_sections)}",
                "severity": "high"
            })
        else:
            checks.append({
                "check": "td_completeness",
                "status": "passed",
                "message": "TD 结构完整"
            })
        
        # 3. Agent 任务完成情况
        tasks = delivery_report.agent_tasks
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        total = len(tasks)
        
        if total > 0 and completed / total < 0.8:
            checks.append({
                "check": "task_completion",
                "status": "failed",
                "message": f"仅完成 {completed}/{total} 个任务 ({completed/total*100:.0f}%)",
                "severity": "critical"
            })
        else:
            checks.append({
                "check": "task_completion",
                "status": "passed",
                "message": f"Agent 任务完成率 {completed}/{total}"
            })
        
        # 4. 测试覆盖
        tests = delivery_report.test_cases
        coverage = tests.get("coverage", 0)
        
        if coverage < 0.7:
            checks.append({
                "check": "test_coverage",
                "status": "warning",
                "message": f"测试覆盖率 {coverage*100:.0f}%，低于 70%",
                "severity": "high"
            })
        else:
            checks.append({
                "check": "test_coverage",
                "status": "passed",
                "message": f"测试覆盖率 {coverage*100:.0f}%"
            })
        
        # 5. 执行结果
        execution = delivery_report.execution_result
        pass_rate = execution.get("pass_rate", 0)
        
        if pass_rate < 0.9:
            checks.append({
                "check": "execution_result",
                "status": "failed",
                "message": f"执行通过率 {pass_rate*100:.0f}%，低于 90%",
                "severity": "critical"
            })
        else:
            checks.append({
                "check": "execution_result",
                "status": "passed",
                "message": f"执行通过率 {pass_rate*100:.0f}%"
            })
        
        # 计算总体评分
        passed = sum(1 for c in checks if c.get("status") == "passed")
        total_checks = len(checks)
        score = passed / total_checks if total_checks > 0 else 0
        
        # 判断是否通过质量门禁
        critical_failures = [c for c in checks if c.get("severity") == "critical" and c.get("status") != "passed"]
        
        return {
            "score": score,
            "passed": len(critical_failures) == 0,
            "checks": checks,
            "blockers": [c["message"] for c in critical_failures],
            "warnings": [c["message"] for c in checks if c.get("severity") == "high" and c.get("status") != "passed"],
        }


# ============================================================================
# Main Pipeline — 主流水线
# ============================================================================

class BizDeliveryPipeline:
    """端到端业务交付流水线"""
    
    def __init__(self, profile_path: str, output_dir: str, wiki_path: Optional[str] = None):
        self.profile_path = profile_path
        self.output_dir = Path(output_dir)
        self.wiki_path = wiki_path
        
        # 加载配置
        with open(profile_path) as f:
            self.profile = json.load(f)
        
        # 初始化组件
        self.llm_client = LLMClient()
        self.task_generator = None
        self.agent_executor = None
        self.quality_gate = None
        
        # 执行状态
        self.ir_data = None
        self.review_result = None
        self.td_result = None
        self.tasks = []
        self.test_result = None
        self.execution_result = None
    
    def run(self, prd_text: str, stages: List[str] = None) -> DeliveryReport:
        """运行完整交付流水线
        
        Args:
            prd_text: PRD 内容
            stages: 要执行的阶段列表，None 表示全部
            
        Returns:
            交付报告
        """
        stages = stages or ["learn", "review", "td", "tasks", "agent", "test", "quality"]
        
        print("=" * 70)
        print("  biz-delivery v3.0 — 端到端业务交付流水线")
        print("=" * 70)
        
        # Stage 1: Learn（知识提取）
        if "learn" in stages:
            self._run_learn()
        
        # Stage 2: PRD Review
        if "review" in stages:
            self._run_review(prd_text)
        
        # Stage 3: Technical Design
        if "td" in stages:
            self._run_td(prd_text)
        
        # Stage 4: Agent Task Generation
        if "tasks" in stages:
            self._run_task_generation()
        
        # Stage 5: Agent Execution
        if "agent" in stages:
            self._run_agent_execution()
        
        # Stage 6: Test Generation
        if "test" in stages:
            self._run_test_generation(prd_text)
        
        # Stage 7: Quality Gate
        if "quality" in stages:
            self._run_quality_gate()
        
        # 生成交付报告
        report = self._generate_delivery_report()
        
        return report
    
    def _run_learn(self):
        """执行知识提取"""
        print("\n📚 Stage 1: 知识提取 (Learn)")
        print("-" * 50)
        
        result = learn_from_repos(
            profile_path=self.profile_path,
            output_dir=str(self.output_dir / "knowledge"),
            wiki_path=self.wiki_path,
        )
        
        self.ir_data = result.get("ir_data", {})
        print(f"  ✅ IR 构建完成: {len(self.ir_data.get('functions', []))} 个函数, "
              f"{len(self.ir_data.get('structs', []))} 个结构体")
    
    def _run_review(self, prd_text: str):
        """执行 PRD 审查"""
        print("\n📋 Stage 2: PRD 审查")
        print("-" * 50)
        
        engine = ReviewEngine(self.profile, str(self.output_dir), self.wiki_path)
        self.review_result = engine.review(prd_text)
        
        # 调用 LLM 自动审查
        prompt_file = self.output_dir / "review_prompt.md"
        if prompt_file.exists():
            prompt_content = prompt_file.read_text(encoding="utf-8")
            system_prompt = """You are a senior software architect reviewing a PRD.
Focus on: correctness, completeness, feasibility, risk.
Output your review in Markdown with P0/P1/P2 priority levels."""
            
            try:
                response = self.llm_client.chat(prompt_content, system=system_prompt)
                llm_content = response.get("content", "")
                if llm_content:
                    self.review_result = engine.review_with_response(llm_content, str(prompt_file))
                    print(f"  ✅ LLM 审查完成: {len(llm_content)} 字符")
            except Exception as e:
                print(f"  ⚠️  LLM 审查失败: {e}")
    
    def _run_td(self, prd_text: str):
        """执行技术方案生成"""
        print("\n📐 Stage 3: 技术方案生成")
        print("-" * 50)
        
        engine = TDEngine(self.profile, str(self.output_dir), self.wiki_path)
        review_report = None
        if self.review_result:
            report_file = self.output_dir / "review_report.md"
            if report_file.exists():
                review_report = report_file.read_text(encoding="utf-8")
        
        self.td_result = engine.generate_td(prd_text, review_report)
        
        # 调用 LLM 生成 TD
        prompt_file = self.output_dir / "td_prompt.md"
        if prompt_file.exists():
            prompt_content = prompt_file.read_text(encoding="utf-8")
            system_prompt = """You are a senior software architect. Generate a comprehensive Technical Design Document.
Include: architecture, interfaces, database design, data migration, diagrams."""
            
            try:
                response = self.llm_client.chat(prompt_content, system=system_prompt)
                llm_content = response.get("content", "")
                if llm_content:
                    self.td_result = engine.generate_with_response(llm_content)
                    print(f"  ✅ TD 生成完成: {len(llm_content)} 字符")
            except Exception as e:
                print(f"  ⚠️  LLM TD 生成失败: {e}")
    
    def _run_task_generation(self):
        """执行 Agent 任务生成"""
        print("\n📝 Stage 4: Agent 开发任务生成")
        print("-" * 50)
        
        if not self.td_result:
            print("  ⚠️  跳过：TD 未生成")
            return
        
        # 读取 TD 内容
        td_file = self.output_dir / "technical_design.md"
        if not td_file.exists():
            print("  ⚠️  跳过：TD 文件不存在")
            return
        
        td_content = td_file.read_text(encoding="utf-8")
        
        # 生成任务
        self.task_generator = AgentTaskGenerator(self.profile, self.ir_data)
        self.tasks = self.task_generator.generate_tasks(td_content, 
            self.review_result.get("parsed", {}) if self.review_result else None)
        
        print(f"  ✅ 生成 {len(self.tasks)} 个开发任务")
        
        # 保存任务列表
        tasks_file = self.output_dir / "agent_tasks.json"
        tasks_file.write_text(json.dumps([t.to_dict() for t in self.tasks], 
            ensure_ascii=False, indent=2), encoding="utf-8")
        
        # 按优先级分组显示
        p0_tasks = [t for t in self.tasks if t.priority == TaskPriority.P0]
        p1_tasks = [t for t in self.tasks if t.priority == TaskPriority.P1]
        print(f"     P0 (阻塞): {len(p0_tasks)} 个")
        print(f"     P1 (重要): {len(p1_tasks)} 个")
        print(f"     P2 (一般): {len(self.tasks) - len(p0_tasks) - len(p1_tasks)} 个")
    
    def _run_agent_execution(self):
        """执行 Agent 开发"""
        print("\n🤖 Stage 5: Agent 开发执行")
        print("-" * 50)
        
        if not self.tasks:
            print("  ⚠️  跳过：无开发任务")
            return
        
        self.agent_executor = AgentExecutor(self.profile, str(self.output_dir))
        self.execution_result = self.agent_executor.execute(self.tasks, self.llm_client)
        
        print(f"  ✅ 执行完成: {self.execution_result['completed']}/{self.execution_result['total_tasks']} 成功")
    
    def _run_test_generation(self, prd_text: str):
        """执行测试用例生成"""
        print("\n🧪 Stage 6: 测试用例生成")
        print("-" * 50)
        
        engine = TestEngine(self.profile, str(self.output_dir), self.wiki_path)
        td_text = None
        td_file = self.output_dir / "technical_design.md"
        if td_file.exists():
            td_text = td_file.read_text(encoding="utf-8")
        
        self.test_result = engine.generate_tests(prd_text, td_text)
        
        # 调用 LLM 生成测试用例
        prompt_file = self.output_dir / "test_prompt.md"
        if prompt_file.exists():
            prompt_content = prompt_file.read_text(encoding="utf-8")
            system_prompt = """You are a senior QA engineer. Generate comprehensive test cases.
Cover: positive flows, exception handling, boundary conditions, security tests."""
            
            try:
                response = self.llm_client.chat(prompt_content, system=system_prompt)
                llm_content = response.get("content", "")
                if llm_content:
                    self.test_result = engine.generate_with_response(llm_content)
                    print(f"  ✅ 测试用例生成完成: {len(llm_content)} 字符")
            except Exception as e:
                print(f"  ⚠️  LLM 测试生成失败: {e}")
    
    def _run_quality_gate(self):
        """执行质量门禁评估"""
        print("\n🚪 Stage 7: 质量门禁评估")
        print("-" * 50)
        
        self.quality_gate = QualityGate(self.profile, str(self.output_dir))
        
        # 构建交付报告
        report = self._generate_delivery_report()
        
        # 执行质量评估
        quality_result = self.quality_gate.evaluate(report)
        
        print(f"  质量评分: {quality_result['score']*100:.0f}/100")
        print(f"  是否通过: {'✅ 通过' if quality_result['passed'] else '❌ 未通过'}")
        
        if quality_result['blockers']:
            print(f"  阻塞项:")
            for b in quality_result['blockers']:
                print(f"    - {b}")
        
        if quality_result['warnings']:
            print(f"  警告项:")
            for w in quality_result['warnings']:
                print(f"    - {w}")
        
        # 保存质量报告
        quality_file = self.output_dir / "quality_gate.md"
        quality_file.write_text(self._format_quality_report(quality_result), encoding="utf-8")
        
        return quality_result
    
    def _generate_delivery_report(self) -> DeliveryReport:
        """生成交付报告"""
        return DeliveryReport(
            prd_review=self.review_result or {},
            technical_design=self.td_result or {},
            agent_tasks=[t.to_dict() for t in self.tasks] if self.tasks else [],
            test_cases=self.test_result or {},
            execution_result=self.execution_result or {},
            quality_gate={},  # 在 _run_quality_gate 中填充
        )
    
    def _format_quality_report(self, quality: Dict) -> str:
        """格式化质量报告"""
        lines = [
            "# 质量门禁报告",
            "",
            f"**评分**: {quality['score']*100:.0f}/100",
            f"**结论**: {'✅ 通过' if quality['passed'] else '❌ 未通过'}",
            "",
            "## 检查项",
            "",
        ]
        
        for check in quality['checks']:
            status = "✅" if check['status'] == 'passed' else "❌"
            lines.append(f"- {status} **{check['check']}**: {check.get('message', '')}")
        
        if quality['blockers']:
            lines.append("")
            lines.append("## 阻塞项")
            for b in quality['blockers']:
                lines.append(f"- 🔴 {b}")
        
        if quality['warnings']:
            lines.append("")
            lines.append("## 警告项")
            for w in quality['warnings']:
                lines.append(f"- 🟡 {w}")
        
        return "\n".join(lines)


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="biz-delivery v3.0 — 端到端业务交付流水线")
    parser.add_argument("--profile", required=True, help="Profile JSON 路径")
    parser.add_argument("--prd", help="PRD 内容（文件路径或文本）")
    parser.add_argument("--prd-url", help="PRD URL")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    parser.add_argument("--wiki-path", help="Wiki 引擎路径")
    parser.add_argument("--stages", help="要执行的阶段: learn,review,td,tasks,agent,test,quality")
    
    args = parser.parse_args()
    
    # 获取 PRD 内容
    prd_text = None
    if args.prd:
        if Path(args.prd).exists():
            prd_text = Path(args.prd).read_text(encoding="utf-8")
        else:
            prd_text = args.prd
    elif args.prd_url:
        import urllib.request
        req = urllib.request.Request(args.prd_url, headers={'User-Agent': 'Mozilla/5.0'})
        prd_text = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
    else:
        print("ERROR: --prd or --prd-url is required")
        sys.exit(1)
    
    # 解析阶段
    stages = [s.strip() for s in args.stages.split(",")] if args.stages else None
    
    # 运行流水线
    pipeline = BizDeliveryPipeline(args.profile, args.output_dir, args.wiki_path)
    report = pipeline.run(prd_text, stages)
    
    # 输出报告
    print("\n" + "=" * 70)
    print("  交付完成")
    print("=" * 70)
    print(report.summary())


if __name__ == "__main__":
    main()
