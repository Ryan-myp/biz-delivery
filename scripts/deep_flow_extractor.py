#!/usr/bin/env python3
"""深度业务流程提取器 — 从 workflow YAML + Go 源码联合推断详细逻辑

当前系统的缺陷：
  _infer_core_business_flow_v2 只做函数级正则追调用链（depth=3），
  对 agent-based 架构（workflow YAML + custom executor）完全无效。

本模块解决：
  1. 解析 workflow.yaml / subflow/*.yaml → 步骤级流程图
  2. 解析 condition 表达式（and/or/equals/absent/all_present）
  3. 追踪 custom executor → Go 源码实现 → 工具调用列表
  4. 生成自然语言详细流程描述（供 prompt 注入）

示例输出（UA Campaign 创建）：
  步骤1: ua_slot_filler → 合并用户输入+历史session
  步骤2: ua_item_resolver → 解析item名称→item_id
  步骤3: ua_lookup_flow (子流程) → 处理查询类意图
    ├─ custom:ua_list_query → MCP工具调用(account/campaign/plan/strategy/template/item)
  步骤4: ua_precondition_guard → 前置条件检查
  步骤5: ua_validation → schema校验
  步骤6: ua_plan_flow (子流程)
    ├─ custom:ua_plan_resolver → 选择已有plan OR 创建新plan
    │   ├─ condition: create_plan==true → ua_plan_create_action
    │   └─ 创建plan → MCP: get_mkt_dap_adminapi_ua_marketing_plan_create
    └─ builtin:slot_guard → 检查 marketing_plan_name, plan_daily_budget
  ...
"""

import re
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict


# ── Workflow 解析器 ────────────────────────────────────────────────

class WorkflowStep:
    """单个 workflow 步骤."""
    def __init__(self, name: str, label: str, description: str,
                 executor: str, condition: Any = None, config: dict = None):
        self.name = name
        self.label = label
        self.description = description
        self.executor = executor
        self.condition = condition
        self.config = config or {}
        self.sub_steps: List['WorkflowStep'] = []

    def is_builtin(self) -> bool:
        return self.executor.startswith('builtin:')

    def is_custom(self) -> bool:
        return self.executor.startswith('custom:')

    def is_subflow(self) -> bool:
        return self.executor.startswith('subflow:')

    def to_dict(self) -> dict:
        d = {
            'name': self.name,
            'label': self.label,
            'description': self.description,
            'executor': self.executor,
            'is_builtin': self.is_builtin(),
            'is_custom': self.is_custom(),
            'is_subflow': self.is_subflow(),
        }
        if self.condition:
            d['condition'] = self.condition
        if self.config:
            d['config'] = self.config
        if self.sub_steps:
            d['sub_steps'] = [s.to_dict() for s in self.sub_steps]
        return d


class WorkflowParser:
    """解析 workflow YAML 文件，构建步骤树."""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)

    def parse_all(self) -> Dict[str, 'Workflow']:
        """解析所有 workflow 和 subflow 文件."""
        workflows = {}

        # 主 workflow
        main_wf = self._parse_file(self.base_dir / 'references' / 'workflow.yaml')
        if main_wf:
            workflows[main_wf.name] = main_wf

        # Subflow
        subflow_dir = self.base_dir / 'references' / 'subflows'
        if subflow_dir.exists():
            for f in sorted(subflow_dir.glob('*.yaml')):
                wf = self._parse_file(f)
                if wf:
                    workflows[wf.name] = wf

        # 平铺的 reference YAML（plan/create.md 等）
        for ref_dir in ['plan', 'strategy', 'publish', 'creative', 'template', 'account', 'item']:
            ref_path = self.base_dir / 'references' / ref_dir
            if ref_path.exists():
                for md_file in sorted(ref_path.glob('*.md')):
                    content = md_file.read_text(errors='ignore')
                    if content.strip():
                        wf_name = f"{ref_dir}_{md_file.stem}"
                        if wf_name not in workflows:
                            workflows[wf_name] = Workflow(
                                name=wf_name,
                                steps=[],
                                source=str(md_file),
                            )

        return workflows

    def _parse_file(self, path: Path) -> Optional['Workflow']:
        """解析单个 workflow YAML 文件."""
        if not path.exists():
            return None
        try:
            with open(path, encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception:
            return None

        name = data.get('workflow_name', path.stem)
        steps_data = data.get('steps', [])
        steps = [self._parse_step(s) for s in steps_data]

        return Workflow(name=name, steps=steps, source=str(path))

    def _parse_step(self, data: dict) -> WorkflowStep:
        """解析单个步骤."""
        return WorkflowStep(
            name=data.get('name', ''),
            label=data.get('label', data.get('name', '')),
            description=data.get('description', ''),
            executor=data.get('executor', 'unknown'),
            condition=data.get('condition'),
            config=data.get('config', {}),
        )


class Workflow:
    """一个完整的 workflow（主流程或子流程）."""

    def __init__(self, name: str, steps: List[WorkflowStep], source: str = ''):
        self.name = name
        self.steps = steps
        self.source = source

    def custom_executors(self) -> List[str]:
        """获取所有自定义 executor 名称."""
        execs = set()
        for step in self.steps:
            if step.is_custom():
                execs.add(step.executor.replace('custom:', ''))
            for sub in step.sub_steps:
                if sub.is_custom():
                    execs.add(sub.executor.replace('custom:', ''))
        return sorted(execs)

    def builtin_executors(self) -> List[str]:
        """获取所有内置 executor 名称."""
        execs = set()
        for step in self.steps:
            if step.is_builtin():
                execs.add(step.executor.replace('builtin:', ''))
        return sorted(execs)

    def subflow_names(self) -> List[str]:
        """获取引用的子流程名称."""
        names = set()
        for step in self.steps:
            if step.is_subflow():
                names.add(step.executor.replace('subflow:', ''))
        return sorted(names)

    def to_dict(self) -> dict:
        """序列化 workflow 为字典."""
        return {
            'name': self.name,
            'source': self.source,
            'step_count': len(self.steps),
            'custom_executors': self.custom_executors(),
            'builtin_executors': self.builtin_executors(),
            'subflows': self.subflow_names(),
            'steps': [s.to_dict() for s in self.steps],
        }

    def detailed_description(self) -> str:
        """生成详细自然语言流程描述."""
        lines = [f"## Workflow: {self.name}", ""]
        for i, step in enumerate(self.steps, 1):
            prefix = "  " if step.is_subflow() else ""
            cond = self._format_condition(step.condition)
            cond_str = f" [当: {cond}]" if cond else ""
            lines.append(f"{prefix}{i}. **{step.label}** `{step.name}`{cond_str}")
            lines.append(f"{prefix}   {step.description}")
            lines.append(f"{prefix}   Executor: {step.executor}")

            # 内置步骤的配置
            if step.is_builtin() and step.config:
                cfg = step.config
                if 'required_slots' in cfg:
                    lines.append(f"{prefix}   必填字段: {', '.join(cfg['required_slots'])}")
                if 'missing_fields' in cfg:
                    lines.append(f"{prefix}   展示名: {', '.join(cfg['missing_fields'])}")
                if 'ask_message' in cfg:
                    lines.append(f"{prefix}   追问: {cfg['ask_message'][:80]}")

            # 子步骤
            if step.sub_steps:
                for j, sub in enumerate(step.sub_steps, 1):
                    sub_cond = self._format_condition(sub.condition)
                    sub_str = f" [当: {sub_cond}]" if sub_cond else ""
                    lines.append(f"{prefix}   {i}.{j}. **{sub.label}** `{sub.name}`{sub_str}")
                    lines.append(f"{prefix}      {sub.description}")
                    lines.append(f"{prefix}      Executor: {sub.executor}")

            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _format_condition(cond: Any) -> str:
        """将 condition 字典格式化为可读字符串."""
        if not cond:
            return ""
        if isinstance(cond, str):
            return cond
        if isinstance(cond, dict):
            parts = []
            for k, v in cond.items():
                if k == 'equals':
                    parts.append(f"{v[0] if isinstance(v, list) else v} == {v[1] if isinstance(v, list) and len(v) > 1 else ''}")
                elif k == 'absent':
                    parts.append(f"缺少 {v}")
                elif k == 'all_present':
                    parts.append(f"包含 {', '.join(v)}")
                elif k == 'and':
                    parts.append(" AND ".join(str(x) for x in v))
                elif k == 'or':
                    parts.append(" OR ".join(str(x) for x in v))
            return " ".join(parts)
        return str(cond)


# ── Go 源码追踪器 ──────────────────────────────────────────────────

class GoExecutorTracer:
    """追踪 custom executor 的 Go 源码实现."""

    def __init__(self, repo_paths: List[str], max_files_per_repo: int = 500):
        self.repo_paths = [Path(p) for p in repo_paths]
        self.max_files_per_repo = max_files_per_repo
        self.func_index: Dict[str, List[Dict]] = {}  # func_name → [{file, line, body_preview}]
        self._build_index()

    def _build_index(self):
        """索引所有 Go 函数（限制文件数避免超时）."""
        for repo in self.repo_paths:
            count = 0
            for f in sorted(repo.rglob('*.go')):
                if count >= self.max_files_per_repo:
                    break
                if 'vendor/' in str(f) or '.git/' in str(f) or '_test.go' in str(f):
                    continue
                count += 1
                self._index_file(f)

    def _index_file(self, f: Path):
        """解析单个 Go 文件，索引函数."""
        try:
            text = f.read_text(errors='ignore')
        except Exception:
            return

        # 找 package 声明
        pkg_match = re.search(r'^package\s+(\w+)', text, re.MULTILINE)
        pkg = pkg_match.group(1) if pkg_match else ''

        # 找函数/方法
        for m in re.finditer(
            r'func\s+(?:\(\s*\*?\w+\s+\w+\s*\)\s+)?(\w+)\s*\(',
            text,
        ):
            func_name = m.group(1)
            line_no = text[:m.start()].count('\n') + 1
            # 取函数体前 200 字符作为预览
            body_start = m.end()
            brace_depth = 0
            body_end = body_start
            for i, c in enumerate(text[body_start:]):
                if c == '{':
                    brace_depth += 1
                elif c == '}':
                    if brace_depth == 0:
                        body_end = body_start + i + 1
                        break
                    brace_depth -= 1
            body_preview = text[body_start:body_start + 300].replace('\n', ' ').strip()[:200]

            entry = {'file': str(f.relative_to(self.repo_paths[0])),
                     'line': line_no, 'pkg': pkg, 'preview': body_preview}
            self.func_index.setdefault(func_name, []).append(entry)

    def trace_executor(self, executor_name: str) -> Dict:
        """追踪一个 custom executor 的实现."""
        result = {
            'executor': executor_name,
            'found': False,
            'files': [],
            'tool_calls': [],
            'key_logic': [],
        }

        # 1. 直接匹配函数名
        if executor_name in self.func_index:
            result['found'] = True
            result['files'] = self.func_index[executor_name][:3]

        # 2. 模糊匹配（下划线分隔）
        if not result['found']:
            for func_name, entries in self.func_index.items():
                if executor_name in func_name or func_name in executor_name:
                    result['found'] = True
                    result['files'] = entries[:3]
                    break

        # 3. 从文件内容中提取工具调用
        if result['found'] and result['files']:
            for file_info in result['files']:
                full_path = self.repo_paths[0] / file_info['file']
                if full_path.exists():
                    try:
                        text = full_path.read_text(errors='ignore')
                        # MCP 工具调用
                        for m in re.finditer(
                            r'(get_|call_|invoke_)?(mkt_dap|adminapi|google|facebook|tiktok|meta|dsp)[_\w]*',
                            text,
                        ):
                            call = m.group(0)
                            if call not in result['tool_calls'] and len(call) > 5:
                                result['tool_calls'].append(call)
                        # key 业务逻辑
                        for pattern in [
                            r'\.Create\w*\(', r'\.Update\w*\(', r'\.Get\w*\(',
                            r'\.List\w*\(', r'\.Validate\w*\(', r'\.Publish\w*\(',
                            r'MCPToolCaller', r'SPXClient', r'gasmq\.',
                        ]:
                            for m2 in re.finditer(pattern, text):
                                ctx = text[max(0, m2.start()-30):m2.end()+50]
                                if ctx not in result['key_logic']:
                                    result['key_logic'].append(ctx.strip()[:120])
                    except Exception:
                        pass

        # 限制输出量
        result['tool_calls'] = result['tool_calls'][:10]
        result['key_logic'] = result['key_logic'][:8]
        return result


# ── 条件表达式解析器 ───────────────────────────────────────────────

class ConditionAnalyzer:
    """解析 workflow condition 表达式，生成可读描述."""

    PREDICATE_MAP = {
        'equals': '等于',
        'absent': '缺失',
        'all_present': '全部包含',
        'present': '存在',
    }

    @staticmethod
    def analyze(cond: Any) -> str:
        if not cond:
            return ""
        if isinstance(cond, str):
            return cond
        if isinstance(cond, dict):
            return ConditionAnalyzer._parse_dict(cond)
        return str(cond)

    @staticmethod
    def _parse_dict(cond: dict) -> str:
        parts = []
        for op, val in cond.items():
            label = ConditionAnalyzer.PREDICATE_MAP.get(op, op)
            if op in ('and', 'or'):
                sub_parts = [ConditionAnalyzer._parse_item(v) for v in val]
                joiner = ' 且 ' if op == 'and' else ' 或 '
                parts.append(joiner.join(sub_parts))
            else:
                parts.append(f"{label}: {ConditionAnalyzer._parse_item(val)}")
        return '，'.join(parts)

    @staticmethod
    def _parse_item(val: Any) -> str:
        if isinstance(val, dict):
            return ConditionAnalyzer._parse_dict(val)
        if isinstance(val, list):
            return ', '.join(str(v) for v in val)
        return str(val)


# ── 主入口 ─────────────────────────────────────────────────────────

class DeepFlowExtractor:
    """深度业务流程提取器 — 联合 workflow YAML + Go 源码."""

    def __init__(self, repo_paths: List[str]):
        self.repo_paths = repo_paths
        self.tracer = GoExecutorTracer(repo_paths)

    def extract(self, agent_dir: str) -> Dict:
        """从 agent 目录提取完整流程信息.

        Returns:
            {
                'workflows': {name: workflow_dict},
                'executors': {name: trace_result},
                'summary': str,  # 自然语言概述
            }
        """
        parser = WorkflowParser(agent_dir)
        workflows = parser.parse_all()

        # 追踪所有 custom executor
        all_executors = set()
        for wf in workflows.values():
            all_executors.update(wf.custom_executors())

        traces = {}
        for exec_name in sorted(all_executors):
            traces[exec_name] = self.tracer.trace_executor(exec_name)

        # 生成自然语言总结
        summary = self._generate_summary(workflows, traces)

        return {
            'workflows': {name: wf.to_dict() for name, wf in workflows.items()},
            'executors': traces,
            'summary': summary,
        }

    def _generate_summary(self, workflows: Dict, traces: Dict) -> str:
        """生成业务流程自然语言概述."""
        lines = []

        # 找到主 workflow
        main_wf = None
        for name, wf in workflows.items():
            if name.endswith('_workflow') or name == 'ua_campaign_creation_workflow':
                main_wf = wf
                break
        if not main_wf and workflows:
            main_wf = list(workflows.values())[0]

        if not main_wf:
            return ""

        lines.append(f"### {main_wf.name} — 业务流程总览")
        lines.append(f"共 {len(main_wf.steps)} 个主步骤，{len(main_wf.subflow_names())} 个子流程")
        lines.append("")

        # 步骤描述
        for i, step in enumerate(main_wf.steps, 1):
            cond_desc = ConditionAnalyzer.analyze(step.condition)
            cond_str = f"（条件: {cond_desc}）" if cond_desc else ""
            lines.append(f"**{i}. {step.label}** — {step.description} {cond_str}")
            lines.append(f"   执行器: `{step.executor}`")

            if step.is_subflow():
                sub_name = step.executor.replace('subflow:', '')
                if sub_name in workflows:
                    sub_wf = workflows[sub_name]
                    lines.append(f"   → 子流程 `{sub_name}` ({len(sub_wf.steps)} 步)")
                    for j, sub_step in enumerate(sub_wf.steps[:4], 1):
                        sub_cond = ConditionAnalyzer.analyze(sub_step.condition)
                        sub_str = f" [{sub_cond}]" if sub_cond else ""
                        lines.append(f"     {j}. {sub_step.label}: {sub_step.description}{sub_str}")
                        if sub_step.is_custom():
                            exec_impl = sub_step.executor.replace('custom:', '')
                            if exec_impl in traces and traces[exec_impl]['found']:
                                tools = traces[exec_impl]['tool_calls']
                                if tools:
                                    lines.append(f"       工具调用: {', '.join(tools[:5])}")

            lines.append("")

        return "\n".join(lines)


def extract_deep_flows(agent_dirs: List[str], repo_paths: List[str]) -> Dict:
    """便捷入口.

    Args:
        agent_dirs: agent 代码目录列表（含 references/ 子目录）
        repo_paths: Go 源码仓库路径列表

    Returns:
        {agent_dir: {workflows, executors, summary}}
    """
    extractor = DeepFlowExtractor(repo_paths)
    results = {}
    for agent_dir in agent_dirs:
        path = Path(agent_dir)
        if path.exists():
            results[str(agent_dir)] = extractor.extract(str(path))
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-dir", required=True,
                        help="Agent directory containing references/")
    parser.add_argument("--repo-paths", nargs="*", default=[],
                        help="Go repository paths for executor tracing")
    parser.add_argument("--output", default=None,
                        help="Output JSON file")
    args = parser.parse_args()

    repo_paths = args.repo_paths or ["/Users/yanping.ma/GolandProjects/dap"]
    result = extract_deep_flows([args.agent_dir], repo_paths)

    output = args.output or f"/tmp/deep_flow_{Path(args.agent_dir).name}.json"
    Path(output).write_text(
        __import__('json').dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✅ Output: {output}")
    # Print summary
    for agent, data in result.items():
        print(f"\n{'='*60}")
        print(f"Agent: {agent}")
        print(f"{'='*60}")
        print(data.get('summary', '(no summary)'))
