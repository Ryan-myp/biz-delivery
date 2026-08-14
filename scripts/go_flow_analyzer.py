#!/usr/bin/env python3
"""从 Go 源码入口追踪真实业务流程 — 不从 YAML 读，纯代码分析

策略：
1. 找 package 级入口函数（ExecuteUniversal / Run / Handle）
2. 追踪函数调用链（递归向上解析依赖）
3. 识别 MCP/SPX 工具调用（外部 API 边界）
4. 识别 session/state 状态转换（业务状态机）
5. 识别条件分支（if/switch 对流程的影响）

输出：自然语言描述的真实业务逻辑流程
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict


# ── Go 函数索引 ──────────────────────────────────────────────────

class GoFunctionIndex:
    """索引所有 Go 函数/方法，支持跨文件追踪调用关系."""

    def __init__(self, repo_paths: List[str], max_files_per_repo: int = 800):
        self.repo_paths = [Path(p) for p in repo_paths]
        self.max_files = max_files_per_repo
        self.func_index: Dict[str, List[Dict]] = {}  # name → [{file, line, body}]
        self.call_graph: Dict[str, Set[str]] = defaultdict(set)  # func → callees
        self.reverse_call: Dict[str, Set[str]] = defaultdict(set)  # callee → callers
        self._build()

    def _build(self):
        for repo in self.repo_paths:
            count = 0
            for f in sorted(repo.rglob('*.go')):
                if count >= self.max_files:
                    break
                if 'vendor/' in str(f) or '.git/' in str(f) or '_test.go' in str(f):
                    continue
                count += 1
                self._index_file(f)

    def _index_file(self, f: Path):
        try:
            text = f.read_text(errors='ignore')
        except Exception:
            return

        pkg_match = re.search(r'^package\s+(\w+)', text, re.MULTILINE)
        pkg = pkg_match.group(1) if pkg_match else ''
        rel = str(f.relative_to(self.repo_paths[0]))

        # 提取所有函数（包括方法）— 匹配到开头的 {
        for m in re.finditer(
            r'func\s+(?:\(\s*\w+\s+\*?\w+\s*\)\s+)?(\w+)\s*\([^)]*\)\s*(?:\([^)]*\))?\s*\{',
            text,
        ):
            fname = m.group(1)
            line_no = text[:m.start()].count('\n') + 1
            body_start = m.end()  # m.end() is AFTER the opening {
            depth = 0
            body_end = body_start
            for i, c in enumerate(text[body_start:], 1):
                if c == '{':
                    depth += 1
                elif c == '}':
                    if depth == 0:
                        body_end = body_start + i
                        break
                    depth -= 1
            body = text[body_start:body_end]

            self.func_index.setdefault(fname, []).append({
                'file': rel, 'line': line_no, 'pkg': pkg, 'body': body,
            })

            # 提取函数体内的调用
            callees = set()
            for cm in re.finditer(
                r'\b(\w+)\s*\(',
                body,
            ):
                callee = cm.group(1)
                if callee not in ('if', 'for', 'switch', 'return', 'defer', 'go',
                                  'select', 'make', 'new', 'append', 'len', 'cap',
                                  'close', 'copy', 'delete', 'panic', 'recover',
                                  'fmt', 'log', 'err', 'nil', 'string', 'int', 'bool',
                                  'ctx', 'c', 'w', 'r', 'rsp', 'res', 'done', 'cancel',
                                  'Error', 'WithSuccess', 'WithError', 'NewContext',
                                  'Reflect', 'User', 'Now', 'Unix', 'Int64', 'Int64s',
                                  'AsInt64', 'LogE', 'LogI', 'ConstructResp', 'lockAdGroup',
                                  'UnLockAdGroup', 'sync', 'context', 'errors', 'json',
                                  'strings', 'strconv', 'time', 'rand', 'math', 'os',
                                  'encoding', 'io', 'net', 'http', 'bufio', 'crypto',
                                  'hash', 'mime', 'sort', 'unicode', 'unsafe'):
                    callees.add(callee)

            self.call_graph[fname].update(callees)
            for callee in callees:
                self.reverse_call[callee].add(fname)

    def get_all_funcs(self) -> List[str]:
        return sorted(self.func_index.keys())

    def get_body(self, func_name: str) -> Optional[str]:
        """获取函数体（取第一个匹配）."""
        entries = self.func_index.get(func_name, [])
        if entries:
            return entries[0]['body']
        return None

    def get_file_and_line(self, func_name: str) -> Tuple[str, int]:
        entries = self.func_index.get(func_name, [])
        if entries:
            return entries[0]['file'], entries[0]['line']
        return '', 0


# ── 入口点识别 ────────────────────────────────────────────────────

ENTRY_POINT_PATTERNS = [
    r'ExecuteUniversal',
    r'Execute',
    r'Handle',
    r'Run\(',           # 各种 Runner.Run
    r'serveHTTP',
    r'HandleFunc',
    r'GET\s*\(',
    r'POST\s*\(',
    r'func\s+\w+.*Request.*Response',  # handler 签名
]

MCP_TOOL_PATTERNS = [
    r'MCPToolCaller',
    r'SPXClient',
    r'gasmq\.',
    r'kafka\.',
    r'\.Create\w*\(',
    r'\.Update\w*\(',
    r'\.Get\w*\(',
    r'\.List\w*\(',
    r'\.Publish\w*\(',
    r'\.Validate\w*\(',
]

STATE_PATTERN = r'(State\w+|Status\w+|state\w+|status\w+)'


# ── 流程分析器 ────────────────────────────────────────────────────

class FlowAnalyzer:
    """从 Go 源码分析业务流程."""

    def __init__(self, index: GoFunctionIndex, agent_dir: str):
        self.idx = index
        self.agent_dir = Path(agent_dir)
        self.pkg_name = self._detect_package()

    def _detect_package(self) -> str:
        for f in self.agent_dir.rglob('*.go'):
            m = re.match(r'.*package\s+(\w+)', f.read_text(errors='ignore'), re.MULTILINE)
            if m:
                return m.group(1)
        return 'unknown'

    def analyze(self) -> Dict:
        """分析整个 agent 目录的业务流程."""
        # 1. 找入口函数
        entry_funcs = self._find_entry_points()
        # 2. 追踪每个入口的完整调用链
        traces = {}
        for func in entry_funcs:
            trace = self._trace_function(func, max_depth=4)
            traces[func] = trace

        # 3. 构建状态机（从状态转换函数推断）
        state_machine = self._extract_state_machine()

        # 4. 生成自然语言描述
        summary = self._generate_summary(entry_funcs, traces, state_machine)

        return {
            'package': self.pkg_name,
            'agent_dir': str(self.agent_dir),
            'entry_points': entry_funcs,
            'traces': traces,
            'state_machine': state_machine,
            'summary': summary,
        }

    def _find_entry_points(self) -> List[str]:
        """找出 agent 包中的主要入口函数."""
        entries = []
        # 优先找 ExecuteUniversal / Execute / Run 类入口
        for pattern in ['ExecuteUniversal', 'Execute', 'Run']:
            for fname in self.idx.get_all_funcs():
                if pattern in fname and fname not in entries:
                    entries.append(fname)

        # 再找 executor.Run 方法
        for fname in self.idx.get_all_funcs():
            if 'Executor' in fname and 'Run' in fname:
                if fname not in entries:
                    entries.append(fname)

        # 找主处理函数
        main_names = ['runUA', 'handle', 'Process', 'Start']
        for prefix in main_names:
            for fname in self.idx.get_all_funcs():
                if fname.startswith(prefix) and fname not in entries:
                    entries.append(fname)

        return entries

    def _trace_function(self, func_name: str, max_depth: int = 4,
                         visited: Set[str] = None, agent_pkg: str = None) -> Dict:
        """递归追踪函数调用链."""
        if visited is None:
            visited = set()
        if func_name in visited or max_depth <= 0:
            return {'name': func_name, 'depth': 0, 'calls': [], 'truncated': True}
        visited.add(func_name)

        body = self.idx.get_body(func_name)
        if not body:
            return {'name': func_name, 'depth': 0, 'calls': [], 'truncated': False}

        # 提取直接调用
        direct_calls = set()
        for m in re.finditer(r'\b(\w+)\s*\(', body):
            callee = m.group(1)
            if callee not in ('if', 'for', 'switch', 'return', 'defer', 'go', 'select',
                              'make', 'new', 'append', 'len', 'cap', 'close', 'copy',
                              'delete', 'panic', 'recover', 'fmt', 'log', 'err', 'nil',
                              'string', 'int', 'bool', 'ctx', 'c', 'w', 'r', 'rsp', 'res',
                              'done', 'cancel', 'Error', 'WithSuccess', 'WithError',
                              'NewContext', 'Reflect', 'User', 'Now', 'Unix', 'Int64',
                              'AsInt64', 'LogE', 'LogI', 'ConstructResp',
                              'sync', 'context', 'errors', 'json', 'strings', 'strconv',
                              'time', 'rand', 'math', 'os', 'encoding', 'io', 'net',
                              'http', 'bufio', 'crypto', 'hash', 'mime', 'sort',
                              'unicode', 'unsafe', 'println', 'print', 'require', 'assert',
                              't', 's', 'b', 'n', 'i', 'j', 'k', 'x', 'y', 'z',
                              'a', 'e', 'd', 'g', 'h', 'l', 'm', 'o', 'p', 'q', 'v',
                              'ctx', 'err', 'ok', 'resp', 'req', 'result', 'input'):
                direct_calls.add(callee)

        # 递归追踪 — 限制在 agent 包内
        traced_calls = []
        for callee in sorted(direct_calls)[:8]:
            call_info = {'name': callee, 'depth': 1}
            # 如果 callee 在 index 中且不是纯标准库函数
            if callee in self.idx.func_index:
                # 检查是否来自 agent 包
                entries = self.idx.func_index[callee]
                is_agent_func = any(
                    agent_pkg in e.get('file', '') or agent_pkg in e.get('pkg', '')
                    for e in entries
                ) if agent_pkg else True
                if is_agent_func:
                    sub_trace = self._trace_function(callee, max_depth - 1, visited.copy(), agent_pkg)
                    call_info.update(sub_trace)
                else:
                    call_info['truncated'] = True
            else:
                call_info['truncated'] = True
            traced_calls.append(call_info)

        # 提取关键特征
        features = self._extract_key_features(body, callee_list=direct_calls)

        return {
            'name': func_name,
            'depth': 4 - max_depth + 1,
            'calls': traced_calls,
            'features': features,
            'file': self.idx.get_file_and_line(func_name)[0],
            'line': self.idx.get_file_and_line(func_name)[1],
        }

    def _extract_key_features(self, body: str, callee_list: Set[str] = None) -> Dict:
        """提取函数体中的关键特征."""
        features = {
            'mcp_calls': [],
            'state_transitions': [],
            'conditions': [],
            'returns': [],
        }
        if callee_list is None:
            callee_list = set()

        # MCP / 外部工具调用（从调用列表识别）
        mcp_keywords = {'RunConfirmedToolAction', 'RunUniqueLookup', 'RunStatusWatch',
                        'CallTool', 'MCPToolCaller', 'SPXClient', 'gasmq', 'kafka'}
        for callee in callee_list:
            if callee in mcp_keywords:
                features['mcp_calls'].append(f'{callee}()')

        # MCP 调用模式（从代码文本）
        for pattern in MCP_TOOL_PATTERNS:
            for m in re.finditer(pattern, body):
                ctx = body[max(0, m.start()-20):m.end()+40].strip()
                if ctx not in features['mcp_calls']:
                    features['mcp_calls'].append(ctx[:100])

        # 状态转换（只识别 agent 包自己的状态常量）
        agent_states = {'StateIntentCaptured', 'StateNeedPlan', 'StateNeedStrategy',
                        'StateNeedCreative', 'StateNeedPublish', 'StatePublishing',
                        'StateCompleted', 'StatusRunning', 'StatusWaiting',
                        'StatusPending', 'TaskStatusPending', 'TaskStatusRunning'}
        for m in re.finditer(r'(State|Status)\s*=\s*(\w+)', body):
            state_val = m.group(2)
            if state_val in agent_states or state_val.startswith('State') or state_val.startswith('Status'):
                transition = f"{m.group(1)} → {state_val}"
                if transition not in features['state_transitions']:
                    features['state_transitions'].append(transition)

        # 关键条件分支
        slot_conditions = [m.group(0) for m in re.finditer(
            r'if\s+slots\.\w+|if\s+req\.\w+|if\s+slots\.\w+\s*[!=]=', body)]
        features['conditions'] = slot_conditions[:5]

        # Return 语句
        for m in re.finditer(r'return\s+[\w.]+', body):
            ret = m.group(0)[:80]
            if ret not in features['returns']:
                features['returns'].append(ret)

        return features

    def _extract_state_machine(self) -> Dict:
        """从代码推断状态机."""
        states = set()
        transitions = []

        for fname, entries in self.idx.func_index.items():
            for entry in entries:
                body = entry['body']
                # 找 State = XX 赋值
                for m in re.finditer(r'(State|Status)\s*=\s*(\w+)', body):
                    states.add(m.group(2))
                    transitions.append({
                        'from_func': fname,
                        'state': m.group(2),
                        'context': body[max(0, m.start()-50):m.end()+50].strip()[:100],
                    })

        return {
            'states': sorted(states),
            'transitions': transitions[:20],
        }

    def _generate_summary(self, entries: List[str], traces: Dict,
                           state_machine: Dict) -> str:
        """生成自然语言流程摘要."""
        lines = []
        pkg = self.pkg_name

        # 找到 agent 包名（用于过滤跨包调用）
        agent_pkg = self.pkg_name

        lines.append(f"### {pkg} 业务流程（从 Go 源码自动追踪）")
        lines.append(f"入口函数: {', '.join(entries[:3])}")
        lines.append("")

        # 追踪核心 runUA* 函数
        run_funcs = [f for f in self.idx.get_all_funcs() if f.startswith('runUA')]
        if not run_funcs:
            run_funcs = [e for e in entries if e.startswith('run') or e.startswith('Execute')]

        for func in run_funcs[:6]:
            trace = self._trace_function(func, max_depth=3, agent_pkg=agent_pkg)
            features = trace.get('features', {})
            mcp = features.get('mcp_calls', [])
            states = features.get('state_transitions', [])
            conds = features.get('conditions', [])
            file, line = self.idx.get_file_and_line(func)

            lines.append(f"**{func}** `@ {file}:{line}`")

            # 描述函数行为
            if conds:
                lines.append(f"  条件判断: {', '.join(conds[:2])}")
            if mcp:
                lines.append(f"  外部调用: {', '.join(mcp[:3])}")
            if states:
                lines.append(f"  状态变更: {', '.join(states[:2])}")

            # 子调用
            for call in trace.get('calls', [])[:5]:
                call_name = call.get('name', '')
                call_features = call.get('features', {})
                call_mcp = call_features.get('mcp_calls', [])
                call_cond = call_features.get('conditions', [])
                detail = ""
                if call_mcp:
                    detail = f"  → {call_name}() [MCP: {', '.join(call_mcp[:2])}]"
                elif call_cond:
                    detail = f"  → {call_name}() [条件: {call_cond[0][:50]}]"
                else:
                    detail = f"  → {call_name}()"
                lines.append(detail)

            lines.append("")

        return '\n'.join(lines)


# ── 主入口 ─────────────────────────────────────────────────────────

def analyze_go_agent(agent_dir: str, repo_paths: List[str]) -> Dict:
    """从 Go 源码分析 agent 业务流程.

    Args:
        agent_dir: agent 源码目录
        repo_paths: Go 仓库路径列表

    Returns:
        {package, entry_points, traces, state_machine, summary}
    """
    idx = GoFunctionIndex(repo_paths)
    analyzer = FlowAnalyzer(idx, agent_dir)
    return analyzer.analyze()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-dir", required=True)
    parser.add_argument("--repo-paths", nargs="*", default=["/Users/yanping.ma/GolandProjects/dap"])
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    result = analyze_go_agent(args.agent_dir, args.repo_paths)

    output = args.output or f"/tmp/go_flow_{Path(args.agent_dir).name}.json"
    import json
    Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Output: {output}")
    print(result['summary'])
