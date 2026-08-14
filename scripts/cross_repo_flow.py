#!/usr/bin/env python3
"""
Cross-repository flow analyzer for dap + ad_delivery_platform.

从 dap 的入口函数出发，追踪到 ad_delivery_platform 的实现，
完整还原跨仓库的 RPC/SPX 调用链。
"""
import re
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict


# ADP 内部客户端包（ad_delivery_platform 内部的跨服务调用）
ADP_INTERNAL_CLIENTS = {
    'adsdomainclient': 'adsdomain microservice (campaign/adgroup/ad creative CRUD)',
    'accountdomainclient': 'accountdomain microservice (ad account info/query)',
    'productdomainclient': 'product microservice (product set/campaign binding)',
    'commondomainclient': 'commondomain microservice (operation log/audit)',
    'adsclient': 'ads microservice direct RPC',
    'gasclient': 'GAS message queue client',
    'alarmclient': 'alarm client',
    'spexclient': 'SPX RPC client',
    'googleproxy': 'Google Ads API proxy',
    'facebookproxyclient': 'Facebook Marketing API proxy',
    'tiktokproxyclient': 'TikTok Marketing API proxy',
}

# dap → adp 跨仓库客户端包
DAP_TO_ADP_CLIENTS = {
    'adsclient': 'ad_delivery_platform ads service (campaign/adgroup/ad CRUD)',
    'accountdomain': 'ad_delivery_platform accountdomain service (account info)',
    'adp_common_client': 'ad_delivery_platform common RPC (query/operate draft)',
    'adsdomain': 'ad_delivery_platform adsdomain service (ad details)',
    'admgmtclient': 'ad_delivery_platform admgmt service (ad management)',
    'marketing_plan_client': 'ad_delivery_platform marketing plan service',
    'strategy_group': 'ad_delivery_platform strategy group service',
    'campaign_strategy_client': 'ad_delivery_platform campaign strategy service',
    'commondomain': 'ad_delivery_platform common domain service',
}


def find_matching_brace(text: str, open_pos: int) -> int:
    """找到 open_pos 处 '{' 对应的匹配 '}' 位置."""
    depth = 1
    i = open_pos + 1
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


class CrossRepoIndex:
    """跨仓库 Go 函数索引 + 调用图."""

    def __init__(self, repo_paths: List[str]):
        self.repo_paths = [Path(p) for p in repo_paths]
        self.func_index: Dict[str, List[Dict]] = {}
        self.call_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_call: Dict[str, Set[str]] = defaultdict(set)
        self.file_cache: Dict[str, str] = {}

    def build(self, max_files: int = 3000):
        # 均衡采集两个仓库的文件，避免单一仓库占满配额
        all_files = []
        for repo in self.repo_paths:
            for f in sorted(repo.rglob('*.go')):
                if 'vendor/' in str(f) or '.git/' in str(f) or '_test.go' in str(f):
                    continue
                all_files.append((str(repo), f))
        # 交替取文件，确保各仓库都有覆盖
        per_repo = max(200, max_files // len(self.repo_paths))
        selected = []
        for repo_path in self.repo_paths:
            repo_files = [(r, f) for r, f in all_files if str(r) == str(repo_path)]
            selected.extend(repo_files[:per_repo])
        count = 0
        for repo_path, f in selected:
            if count >= max_files:
                break
            count += 1
            try:
                text = f.read_text(errors='ignore')
            except Exception:
                continue
            self.file_cache[str(f)] = text

            pkg_match = re.search(r'^package\s+(\w+)', text, re.MULTILINE)
            pkg = pkg_match.group(1) if pkg_match else ''
            rel = str(f.relative_to(repo_path))

            for m in re.finditer(r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(', text):
                fname = m.group(1)
                line_no = text[:m.start()].count('\n') + 1
                body_start = text.index('{', m.end()) + 1
                body_end = find_matching_brace(text, body_start - 1)
                if body_end <= 0:
                    continue
                body = text[body_start:body_end]

                self.func_index.setdefault(fname, []).append({
                    'file': rel, 'line': line_no, 'pkg': pkg, 'body': body,
                })

                # 提取调用关系
                callees = set()
                for cm in re.finditer(r'\b(\w+)\s*\(', body):
                    callee = cm.group(1)
                    excluded = {'if', 'for', 'switch', 'return', 'defer', 'go',
                                'select', 'make', 'new', 'append', 'len', 'cap',
                                'close', 'copy', 'delete', 'panic', 'recover',
                                'fmt', 'log', 'err', 'nil', 'string', 'int',
                                'bool', 'ctx', 'c', 'w', 'r', 'rsp', 'res',
                                'done', 'cancel', 'Error', 'WithSuccess',
                                'WithError', 'NewContext', 'Reflect', 'User',
                                'Now', 'Unix', 'Int64', 'AsInt64', 'LogE',
                                'LogI', 'ConstructResp', 'sync', 'context',
                                'errors', 'json', 'strings', 'strconv', 'time',
                                'rand', 'math', 'os', 'encoding', 'io', 'net',
                                'http', 'bufio', 'crypto', 'hash', 'mime',
                                'sort', 'unicode', 'unsafe', 'println', 'print',
                                'require', 'assert', 't', 's', 'b', 'n', 'i',
                                'j', 'k', 'x', 'y', 'z', 'a', 'e', 'd', 'g',
                                'h', 'l', 'm', 'o', 'p', 'q', 'v', 'err', 'ok',
                                'resp', 'req', 'result', 'input', 'logCtx',
                                'dapCtx', 'commonRsp', 'commonReq', 'request',
                                'taskParams', 'taskHandler', 'createList',
                                'saveReq', 'marketConfig', 'commonConfig',
                                'accInfo', 'ctxLog', 'adGroup', 'campaign',
                                'accountInfo', 'process', 'build', 'convert',
                                'fill', 'check', 'get', 'set', 'add', 'update',
                                'delete', 'query', 'handle', 'parse', 'validate'}
                    if callee not in excluded:
                        callees.add(callee)

                self.call_graph[fname].update(callees)
                for callee in callees:
                    self.reverse_call[callee].add(fname)

        print(f"  Indexed {count} files, {len(self.func_index)} functions across repos")

    def trace_func(self, func_name: str, max_depth: int = 4, visited: Set[str] = None) -> Dict:
        """递归追踪函数调用链，标注跨仓库调用."""
        if visited is None:
            visited = set()
        if func_name in visited or max_depth <= 0:
            return {'name': func_name, 'depth': 0, 'calls': [], 'truncated': True}
        visited.add(func_name)

        entries = self.func_index.get(func_name, [])
        if not entries:
            return {'name': func_name, 'depth': 0, 'calls': [], 'truncated': False}

        body = entries[0].get('body', '')
        file_info = entries[0].get('file', '')
        line_no = entries[0].get('line', 0)
        pkg = entries[0].get('pkg', '')
        callees = self.call_graph.get(func_name, set())

        traced_calls = []
        for callee in sorted(callees)[:12]:
            call_info = {'name': callee, 'depth': 4 - max_depth}
            sub = self.trace_func(callee, max_depth - 1, visited.copy())
            call_info.update(sub)

            # 判断调用类型
            call_info['call_type'] = 'local'
            if callee in self.func_index:
                # 在索引中找到 — 本地调用
                callee_pkg = self.func_index[callee][0]['pkg'] if self.func_index[callee] else ''
                if callee_pkg != pkg:
                    call_info['call_type'] = 'cross-pkg'
            else:
                # 不在索引中 — 外部调用（跨仓库或标准库）
                call_info['call_type'] = 'external'
                # 进一步分类
                for prefix, desc in {**DAP_TO_ADP_CLIENTS, **ADP_INTERNAL_CLIENTS}.items():
                    if callee.startswith(prefix) or any(callee.startswith(p) for p in prefix.split('_')):
                        call_info['cross_repo'] = True
                        call_info['external_call'] = True
                        call_info['external_desc'] = desc
                        break

            traced_calls.append(call_info)

        features = self._extract_features(body, callees)
        return {
            'name': func_name, 'depth': 4 - max_depth + 1,
            'file': file_info, 'line': line_no, 'pkg': pkg,
            'calls': traced_calls, 'features': features,
        }

    def _extract_features(self, body: str, callees: Set[str]) -> Dict:
        features = {'adp_calls': [], 'conditions': [], 'returns': []}
        all_known_clients = {**DAP_TO_ADP_CLIENTS, **ADP_INTERNAL_CLIENTS}
        for prefix in all_known_clients:
            for callee in callees:
                if callee.startswith(prefix):
                    features['adp_calls'].append(f'{callee}()')
        for m in re.finditer(r'if\s+\w+', body):
            cond = m.group(0)[:80]
            if cond not in features['conditions']:
                features['conditions'].append(cond)
        for m in re.finditer(r'return\s+[\w.,]+', body):
            ret = m.group(0)[:80]
            if ret not in features['returns']:
                features['returns'].append(ret)
        return features


def analyze_cross_repo(dap_path: str, adp_path: str, entry_points: List[str]) -> Dict:
    """分析跨仓库调用链."""
    t0 = time.time()
    print(f"  🔬 Building cross-repo index: dap={dap_path}, adp={adp_path}")

    idx = CrossRepoIndex([dap_path, adp_path])
    idx.build(max_files=1500)

    results = {}
    for entry in entry_points:
        print(f"  Tracing {entry}...")
        trace = idx.trace_func(entry, max_depth=4)
        results[entry] = trace

    elapsed = time.time() - t0
    print(f"  Cross-repo analysis done in {elapsed:.1f}s")
    return results


def generate_cross_repo_summary(results: Dict) -> str:
    """生成跨仓库调用链摘要."""
    lines = ["## 跨仓库业务流程分析（dap → ad_delivery_platform 完整调用链）", ""]

    for entry, trace in results.items():
        lines.append(f"### 入口: `{entry}`")
        lines.append("")
        _format_trace(lines, trace, indent=0)
        lines.append("")

    return '\n'.join(lines)


def _format_trace(lines: List[str], trace: Dict, indent: int):
    prefix = "  " * indent
    name = trace.get('name', '')
    pkg = trace.get('pkg', '')
    file_info = trace.get('file', '')
    line_no = trace.get('line', 0)
    call_type = trace.get('call_type', 'local')
    cross_repo = trace.get('cross_repo', False)
    external_desc = trace.get('external_desc', '')

    icon = "↗" if cross_repo else "→" if call_type == 'external' else "  "
    type_label = f" [{call_type}]" if call_type != 'local' else ""
    repo_label = f" ↗{external_desc}" if cross_repo and external_desc else ""

    lines.append(f"{prefix}{icon} **{name}**`@ {file_info}:{line_no}`{type_label}{repo_label}")

    for call in trace.get('calls', [])[:8]:
        if call.get('depth', 0) <= trace.get('depth', 0) + 1:
            _format_trace(lines, call, indent + 1)


def analyze_spex_full(dap_path: str, adp_path: str) -> Dict:
    """完整分析 SPX Processor → ad_delivery_platform 的调用链."""
    t0 = time.time()
    print(f"  🔬 Full cross-repo SPX analysis...")

    idx = CrossRepoIndex([dap_path, adp_path])
    idx.build(max_files=1500)

    # 追踪核心入口
    entries = [
        'AutoCreateCampaignRun',    # SPX 入口
        'SaveDraftCampaign',        # 草稿创建
        'HandleTaskCallBack',       # 回调处理
        'OperateDraftAds',          # adp 侧处理
        'SpexOperateDraftAds',      # adp handler
        'AppSaveDraft',             # adp ops appservice
        'processDraftCampaign',     # adp 内部流程
    ]

    results = {}
    for entry in entries:
        if entry in idx.func_index:
            trace = idx.trace_func(entry, max_depth=4)
            results[entry] = trace

    elapsed = time.time() - t0
    print(f"  SPX full analysis done in {elapsed:.1f}s: {len(results)} entry points")
    return results
