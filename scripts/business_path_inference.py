#!/usr/bin/env python3
"""Enhanced business path inference engine.

Infers critical business paths from code structure:
1. CRUD lifecycle paths (Create → Read → Update → Delete)
2. Approval/workflow paths (Draft → Review → Publish)
3. Data flow chains (User → API → Handler → Service → DAO → DB)
4. Async/event-driven paths (Producer → MQ → Consumer)
5. Authentication/authorization paths

Uses call_graph + routes + functions + entity_tables to build a
comprehensive picture of the application's business logic.

Replaces the basic flow inference in core_flow_analyzer.py with
a more focused, higher-signal approach.
"""

import re
import json
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

LIFECYCLE_VERBS = {
    'create': ['create', 'add', 'insert', 'build', 'new', 'init'],
    'read': ['get', 'list', 'query', 'find', 'search', 'fetch', 'view'],
    'update': ['update', 'edit', 'modify', 'patch', 'change'],
    'delete': ['delete', 'remove', 'destroy', 'drop'],
}

APPROVAL_VERBS = ['approve', 'reject', 'review', 'audit', 'verify']
PUBLISH_VERBS = ['publish', 'release', 'launch', 'go_live', 'deploy']
SUBMIT_VERBS = ['submit', 'send', 'post', 'forward']
STATUS_VERBS = ['activate', 'deactivate', 'pause', 'resume', 'enable', 'disable', 'suspend', 'archive']

HTTP_METHOD_TO_ACTION = {
    'POST': 'create',
    'PUT': 'update',
    'PATCH': 'update',
    'DELETE': 'delete',
    'GET': 'read',
}

HTTP_METHOD_TO_CN = {
    'POST': '创建',
    'PUT': '更新',
    'PATCH': '修改',
    'DELETE': '删除',
    'GET': '查询',
}


class BusinessPathInference:
    """Infer critical business paths from IR data."""

    def __init__(self, ir_data: dict):
        self.ir = ir_data
        self.call_graph = ir_data.get('call_graph', [])
        self.routes = ir_data.get('routes', [])
        self.functions = ir_data.get('functions', [])
        self.structs = ir_data.get('structs', [])
        self.entity_tables = ir_data.get('entity_tables', [])
        self.services = ir_data.get('services', [])
        self.business_logic = ir_data.get('business_logic', [])
        self.error_codes = ir_data.get('error_codes', [])
        self.auth_models = ir_data.get('auth_models', [])
        self.configs = ir_data.get('configs', [])
        self.packages = ir_data.get('packages', {})

        # Build indexes
        self._build_indexes()

    def _build_indexes(self):
        """Build lookup indexes for efficient queries."""
        # func_name -> function info
        self.func_map: Dict[str, dict] = {}
        for f in self.functions:
            if isinstance(f, dict):
                name = f.get('name', '')
                if name:
                    self.func_map[name] = f

        # file_path -> list of functions
        self.file_to_funcs: Dict[str, List[dict]] = defaultdict(list)
        for f in self.functions:
            if isinstance(f, dict):
                ffile = f.get('file', '')
                fname = f.get('name', '')
                if ffile and fname:
                    self.file_to_funcs[ffile].append(f)

        # caller -> callees (call graph adjacency list)
        self.call_adj: Dict[str, List[str]] = defaultdict(list)
        # callee -> callers (reverse call graph)
        self.reverse_adj: Dict[str, List[str]] = defaultdict(list)
        for edge in self.call_graph:
            if isinstance(edge, dict):
                caller = edge.get('caller', edge.get('from', ''))
                callee = edge.get('callee', edge.get('to', ''))
            else:
                caller = getattr(edge, 'caller', getattr(edge, 'from', ''))
                callee = getattr(edge, 'callee', getattr(edge, 'to', ''))
            if caller and callee:
                self.call_adj[caller].append(callee)
                self.reverse_adj[callee].append(caller)

        # route -> handler
        self.route_handlers: List[dict] = []
        for r in self.routes:
            if isinstance(r, dict) and r.get('handler'):
                self.route_handlers.append(r)

        # entity -> related functions (via error codes, structs)
        self.entity_to_funcs: Dict[str, List[str]] = defaultdict(list)
        for struct in self.structs:
            if isinstance(struct, dict):
                sname = struct.get('name', '').lower()
                for entity in self._extract_entity_names(sname):
                    self.entity_to_funcs[entity].append(struct.get('name', ''))

    def _extract_entity_names(self, name: str) -> List[str]:
        """Extract entity names from struct/function names."""
        names = []
        # Split camelCase / snake_case
        parts = re.split(r'[_\-\s]+|(?<=[a-z])(?=[A-Z])', name.lower())
        for p in parts:
            if len(p) > 2 and p not in ('service', 'handler', 'dao', 'repo', 'model', 'struct', 'type', 'func', 'api'):
                names.append(p)
        return names[:3]

    def infer_all(self) -> dict:
        """Run all inference strategies and return combined results."""
        result = {
            'lifecycle_paths': self.infer_lifecycle_paths(),
            'approval_workflows': self.infer_approval_workflows(),
            'data_flow_chains': self.infer_data_flow_chains(),
            'async_event_paths': self.infer_async_event_paths(),
            'auth_paths': self.infer_auth_paths(),
            'top_entry_points': self.find_top_entry_points(),
            'entity_relationships': self.map_entity_relationships(),
            'business_workflows': self.infer_business_workflows(),
        }
        # NEW: Infer retry/idempotency patterns
        result['reliability_patterns'] = self.infer_reliability_patterns()
        # NEW: Infer error handling patterns
        result['error_handling'] = self.infer_error_handling_patterns()
        # NEW: Infer transaction patterns
        result['transaction_patterns'] = self.infer_transaction_patterns()
        # Compute importance ranking across all flow types
        result['importance_ranking'] = self._compute_importance_ranking(result)
        return result

    # ──────────────────────────────────────────────
    # NEW: Multi-Step Business Workflow Inference
    # ──────────────────────────────────────────────

    def infer_business_workflows(self) -> List[dict]:
        """Detect multi-step business workflows from code structure.

        Looks for coherent sequences like:
        - Create → Submit → Review → Approve → Publish (ad campaign lifecycle)
        - Order placed → Payment → Fulfillment → Shipped → Delivered
        - Draft → Review → Approved → Published → Archived

        Strategy:
        1. Group functions by entity (using entity name extraction)
        2. Within each entity, detect verb-based phase sequences
        3. Validate sequence using call_graph edges (caller→callee ordering)
        4. Score by completeness and call graph evidence
        """
        workflows = []

        # Step 1: Group all functions by their entity
        entity_funcs: Dict[str, List[dict]] = defaultdict(list)
        for func_name, func_info in self.func_map.items():
            entity = self._extract_entity_from_func(func_name)
            if entity:
                entity_funcs[entity].append({
                    'name': func_name,
                    'file': func_info.get('file', ''),
                    'params': func_info.get('params', []),
                    'returns': func_info.get('returns', ''),
                })

        # Step 2: For each entity with 3+ functions, try to build workflow
        for entity, funcs in entity_funcs.items():
            if len(funcs) < 3:
                continue

            phases = self._detect_workflow_phases(entity, funcs)
            if not phases:
                continue

            # Step 3: Validate phase ordering via call graph
            ordered_phases = self._validate_phase_order(phases)
            if not ordered_phases or len(ordered_phases) < 2:
                continue

            # Step 4: Check for route coverage
            routes_by_entity = [r for r in self.route_handlers
                                if entity.lower() in r.get('path', '').lower()]

            # Step 5: Build workflow summary
            phase_names = [p['phase'] for p in ordered_phases]
            all_functions = [f['name'] for p in ordered_phases for f in p['functions']]
            all_routes = [r.get('path', '') for r in routes_by_entity]

            # Detect if this is a state-machine based workflow
            states = self._detect_states_for_entity(entity)
            is_state_machine = len(states) >= 2

            workflows.append({
                'entity': entity,
                'workflow_type': self._classify_workflow_type(ordered_phases),
                'phases': ordered_phases,
                'phase_sequence': phase_names,
                'total_functions': len(all_functions),
                'related_routes': all_routes[:8],
                'states': states,
                'is_state_machine': is_state_machine,
                'has_submit_approve_publish': any(
                    p['phase'] in ('submit', 'review', 'approve', 'publish')
                    for p in ordered_phases
                ),
                'score': self._score_workflow(ordered_phases, len(routes_by_entity)),
            })

        # Sort by score
        workflows.sort(key=lambda x: x['score'], reverse=True)
        return workflows[:15]

    def _detect_workflow_phases(self, entity: str, funcs: List[dict]) -> List[dict]:
        """Detect workflow phases within an entity's functions.

        Returns list of {phase, functions, order} dicts.
        """
        phase_patterns = {
            'create': {
                'verbs': ['create', 'add', 'build', 'new', 'init', 'insert', 'post'],
                'cn': '创建',
                'order': 10,
            },
            'read': {
                'verbs': ['get', 'list', 'query', 'find', 'search', 'fetch', 'view'],
                'cn': '查询',
                'order': 5,
            },
            'update': {
                'verbs': ['update', 'edit', 'modify', 'patch', 'change'],
                'cn': '更新',
                'order': 20,
            },
            'delete': {
                'verbs': ['delete', 'remove', 'destroy', 'drop'],
                'cn': '删除',
                'order': 90,
            },
            'submit': {
                'verbs': ['submit', 'send', 'post', 'forward', 'dispatch'],
                'cn': '提交',
                'order': 30,
            },
            'review': {
                'verbs': ['review', 'audit', 'verify', 'check', 'inspect'],
                'cn': '审核',
                'order': 40,
            },
            'approve': {
                'verbs': ['approve', 'accept', 'confirm', 'authorize'],
                'cn': '批准',
                'order': 50,
            },
            'reject': {
                'verbs': ['reject', 'deny', 'decline'],
                'cn': '拒绝',
                'order': 55,
            },
            'publish': {
                'verbs': ['publish', 'release', 'launch', 'go_live', 'deploy', 'activate'],
                'cn': '发布',
                'order': 60,
            },
            'archive': {
                'verbs': ['archive', 'deactivate', 'suspend', 'disable'],
                'cn': '归档',
                'order': 80,
            },
            'notify': {
                'verbs': ['notify', 'send_msg', 'send_email', 'push', 'alert'],
                'cn': '通知',
                'order': 70,
            },
        }

        # Classify each function into a phase
        phase_funcs: Dict[str, List[dict]] = defaultdict(list)
        for func in funcs:
            fn_lower = func['name'].lower()
            best_phase = None
            best_score = 0

            for phase_name, pattern in phase_patterns.items():
                score = sum(1 for v in pattern['verbs'] if v in fn_lower)
                if score > best_score:
                    best_score = score
                    best_phase = phase_name

            if best_phase and best_score > 0:
                phase_funcs[best_phase].append(func)

        # Build ordered phase list (only phases with functions)
        phases = []
        for phase_name, info in sorted(phase_patterns.items(), key=lambda x: x[1]['order']):
            if phase_name in phase_funcs:
                phases.append({
                    'phase': phase_name,
                    'cn': info['cn'],
                    'functions': phase_funcs[phase_name],
                    'order': info['order'],
                })

        return phases

    def _validate_phase_order(self, phases: List[dict]) -> List[dict]:
        """Validate and reorder phases based on call graph evidence.

        If function A calls function B, A should come before B in the workflow.
        Reorders phases to match actual call direction.
        """
        if not phases:
            return phases

        # Collect all functions in order
        func_list = []
        for p in phases:
            for f in p['functions']:
                func_list.append(f['name'])

        # Check call graph edges between functions
        edge_count = 0
        for i, caller in enumerate(func_list):
            for callee in func_list[i + 1:]:
                if caller in self.call_adj and callee in self.call_adj[caller]:
                    edge_count += 1
                    break

        # If we have evidence of ordering, trust it; otherwise use phase order
        has_evidence = edge_count > 0

        if has_evidence:
            # Build a topological sort based on call graph
            func_to_phase = {}
            for p in phases:
                for f in p['functions']:
                    func_to_phase[f['name']] = p

            # Simple ordering: if caller exists before callee in call graph, keep order
            ordered = []
            seen_phases = set()
            for p in sorted(phases, key=lambda x: x['order']):
                if p['phase'] not in seen_phases:
                    ordered.append(p)
                    seen_phases.add(p['phase'])
            return ordered

        return phases

    def _classify_workflow_type(self, phases: List[dict]) -> str:
        """Classify the workflow type based on detected phases."""
        phase_names = {p['phase'] for p in phases}

        if {'submit', 'review', 'approve'}.issubset(phase_names):
            return 'approval_workflow'
        if {'create', 'publish'}.issubset(phase_names):
            return 'content_lifecycle'
        if {'create', 'update', 'delete'}.issubset(phase_names):
            return 'crud_lifecycle'
        if any(p in phase_names for p in ('submit', 'approve', 'publish')):
            return 'multi_step_workflow'
        if len(phases) >= 3:
            return 'multi_step_workflow'
        return 'partial_workflow'

    def _score_workflow(self, phases: List[dict], route_count: int) -> float:
        """Score a workflow by completeness and evidence."""
        score = 0.0

        # Phase count bonus
        score += len(phases) * 10

        # Critical phase bonuses
        critical_phases = {'create', 'submit', 'review', 'approve', 'publish'}
        phase_names = {p['phase'] for p in phases}
        score += len(phase_names & critical_phases) * 15

        # Route coverage bonus
        score += min(route_count * 5, 25)

        # State machine bonus
        if any(p.get('phase') in ('approve', 'reject', 'publish') for p in phases):
            score += 20

        return score

    # ──────────────────────────────────────────────
    # 8. Importance Ranking (traffic, error impact, business value, completeness)
    # ──────────────────────────────────────────────

    def _compute_importance_ranking(self, inference_results: dict) -> List[dict]:
        """Rank all flows by a composite importance score.

        Scoring dimensions:
          - traffic_score: high-frequency endpoints (GET list), in-degree, fan-out
          - error_impact_score: critical path failures, auth/revenue flows
          - business_value_score: revenue-generating verbs, approval/publish flows
          - completeness_score: has_full_crud, more CRUD ops = higher
        """
        # Collect all candidate flows into a unified list
        candidates = []

        # Lifecycle paths
        for lp in inference_results.get('lifecycle_paths', []):
            entity = lp.get('entity', '')
            routes = lp.get('routes', [])
            actions = set(r.get('action', '') for r in routes)
            candidates.append({
                'flow_name': f"{entity} lifecycle ({', '.join(lp.get('present_actions', []))})",
                'flow_type': 'lifecycle',
                'entity': entity,
                'route_count': len(routes),
                'actions': actions,
                'has_full_crud': lp.get('has_full_crud', False),
                'score': 0,
                '_traffic': 0, '_error': 0, '_biz': 0, '_complete': 0,
            })

        # Approval workflows
        for wf in inference_results.get('approval_workflows', []):
            candidates.append({
                'flow_name': f"{wf.get('entity', '')} approval workflow",
                'flow_type': 'approval_workflow',
                'entity': wf.get('entity', ''),
                'route_count': wf.get('step_count', 0),
                'actions': set(),
                'has_full_crud': False,
                'score': 0,
                '_traffic': 0, '_error': 0, '_biz': 0, '_complete': 0,
            })

        # Data flow chains
        for df in inference_results.get('data_flow_chains', []):
            candidates.append({
                'flow_name': f"{df.get('method', '')} {df.get('route', '')} data flow",
                'flow_type': 'data_flow',
                'entity': df.get('entities', [''])[0] if df.get('entities') else '',
                'route_count': 1,
                'actions': {df.get('method', '').lower()},
                'has_full_crud': False,
                'score': 0,
                '_traffic': 0, '_error': 0, '_biz': 0, '_complete': 0,
            })

        # Async event paths
        for ep in inference_results.get('async_event_paths', []):
            candidates.append({
                'flow_name': f"async {ep.get('domain', '')} event",
                'flow_type': 'async_event',
                'entity': ep.get('domain', ''),
                'route_count': 2,
                'actions': set(),
                'has_full_crud': False,
                'score': 0,
                '_traffic': 0, '_error': 0, '_biz': 0, '_complete': 0,
            })

        # Auth paths
        for ap in inference_results.get('auth_paths', []):
            candidates.append({
                'flow_name': f"auth {' + '.join(ap.get('type', ''))}",
                'flow_type': 'auth',
                'entity': 'auth',
                'route_count': len(ap.get('auth_endpoints', [])),
                'actions': set(),
                'has_full_crud': False,
                'score': 0,
                '_traffic': 0, '_error': 0, '_biz': 0, '_complete': 0,
            })

        # Top entry points
        for tp in inference_results.get('top_entry_points', []):
            candidates.append({
                'flow_name': f"entry point: {tp.get('name', '')}",
                'flow_type': 'entry_point',
                'entity': '',
                'route_count': 1,
                'actions': set(),
                'has_full_crud': False,
                'score': 0,
                '_traffic': tp.get('in_degree', 0) * 15 + tp.get('fan_out', 0) * 5,
                '_error': 0, '_biz': 0, '_complete': 0,
            })

        # Now compute composite scores
        ranked = []
        for c in candidates:
            c['_traffic'] = self._calc_traffic_score(c)
            c['_error'] = self._calc_error_impact_score(c)
            c['_biz'] = self._calc_business_value_score(c)
            c['_complete'] = self._calc_completeness_score(c)
            c['score'] = round(
                c['_traffic'] * 0.30 +
                c['_error'] * 0.25 +
                c['_biz'] * 0.25 +
                c['_complete'] * 0.20,
                1
            )
            ranked.append({
                'rank': 0,
                'flow_name': c['flow_name'],
                'flow_type': c['flow_type'],
                'entity': c.get('entity', ''),
                'score': c['score'],
                'traffic_score': c['_traffic'],
                'error_impact_score': c['_error'],
                'business_value_score': c['_biz'],
                'completeness_score': c['_complete'],
                'has_full_crud': c.get('has_full_crud', False),
                'route_count': c.get('route_count', 0),
            })

        # Sort descending, assign ranks
        ranked.sort(key=lambda x: x['score'], reverse=True)
        for i, item in enumerate(ranked):
            item['rank'] = i + 1

        return ranked[:10]

    def _calc_traffic_score(self, c: dict) -> float:
        """High-frequency endpoints like GET list, high in-degree/fan-out."""
        score = 0.0
        actions = c.get('actions', set())
        route_count = c.get('route_count', 0)

        # GET list / search are high-traffic
        if 'read' in actions or 'get' in actions or 'list' in actions:
            score += 40
        elif 'search' in actions or 'query' in actions:
            score += 30

        # In-degree from call graph (via top_entry_points)
        if c.get('flow_type') == 'entry_point':
            score += c.get('_traffic', 0) * 0.5

        # More routes = more traffic surface
        score += min(route_count * 5, 20)
        return min(score, 100)

    def _calc_error_impact_score(self, c: dict) -> float:
        """Critical path failures have outsized impact."""
        score = 0.0
        flow_type = c.get('flow_type', '')

        # Auth failures block everything
        if flow_type == 'auth':
            score += 60

        # Approval workflows: failure means stuck business objects
        if flow_type == 'approval_workflow':
            score += 45

        # Lifecycle with full CRUD is a critical operational path
        if flow_type == 'lifecycle' and c.get('has_full_crud'):
            score += 50
        elif flow_type == 'lifecycle':
            score += 30

        # Revenue-critical paths (create/update)
        if 'create' in c.get('actions', set()):
            score += 35
        if 'update' in c.get('actions', set()):
            score += 20

        return min(score, 100)

    def _calc_business_value_score(self, c: dict) -> float:
        """Revenue-generating and user-facing flows score higher."""
        score = 0.0
        actions = c.get('actions', set())
        flow_type = c.get('flow_type', '')

        # Create = revenue generation
        if 'create' in actions:
            score += 50
        if 'update' in actions:
            score += 20

        # Publish/release = go-live value
        if flow_type == 'approval_workflow':
            score += 40

        # Lifecycle with create+read = core business
        if flow_type == 'lifecycle':
            score += 30

        # Entry points that are handlers get traffic value
        if flow_type == 'entry_point':
            score += 20

        return min(score, 100)

    def _calc_completeness_score(self, c: dict) -> float:
        """More CRUD ops implemented = more complete = more important."""
        score = 0.0
        actions = c.get('actions', set())
        if c.get('has_full_crud'):
            score += 60
        else:
            score += len(actions) * 15
        return min(score, 100)

    # ──────────────────────────────────────────────
    # 1. Lifecycle Path Inference (CRUD → Full Lifecycle)
    # ──────────────────────────────────────────────

    def infer_lifecycle_paths(self) -> List[dict]:
        """Infer full CRUD lifecycles per entity.

        Groups routes by resource/entity, then checks which CRUD operations
        are present. Reports gaps (e.g., has Create/Read but no Delete).
        """
        # Group routes by entity
        entity_routes: Dict[str, List[dict]] = defaultdict(list)
        for rh in self.route_handlers:
            path = rh.get('path', '')
            method = rh.get('method', 'GET')
            handler = rh.get('handler', '')

            # Extract entity from path: /api/v1/creatives → creatives
            parts = path.strip('/').split('/')
            if len(parts) >= 2:
                # Try last meaningful segment
                entity = parts[-1] if len(parts) > 2 else parts[-2]
                entity = re.sub(r'^v\d+$', '', entity)  # skip version segments
                if entity:
                    entity_routes[entity].append({
                        'path': path,
                        'method': method,
                        'handler': handler,
                        'action': HTTP_METHOD_TO_ACTION.get(method, 'unknown'),
                    })

        lifecycle_paths = []
        for entity, routes in entity_routes.items():
            actions = set(r['action'] for r in routes)
            action_names = {
                'create': '创建',
                'read': '查询',
                'update': '更新',
                'delete': '删除',
            }

            present = [action_names.get(a, a) for a in sorted(actions) if a != 'unknown']
            missing = [action_names.get(a, a) for a in ['create', 'read', 'update', 'delete'] if a not in actions]

            # Build the chain
            chain_steps = []
            for r in sorted(routes, key=lambda x: ['create', 'read', 'update', 'delete'].index(x['action']) if x['action'] in ['create', 'read', 'update', 'delete'] else 99):
                chain_steps.append({
                    'method': r['method'],
                    'path': r['path'],
                    'handler': r['handler'],
                    'action': action_names.get(r['action'], r['action']),
                })

            # Trace full call chain for each route
            full_chains = []
            for r in routes:
                chain = self._trace_call_chain(r['handler'])
                if chain:
                    full_chains.append({
                        'route': r['path'],
                        'method': r['method'],
                        'call_chain': chain,
                    })

            lifecycle_paths.append({
                'entity': entity,
                'present_actions': present,
                'missing_actions': missing,
                'has_full_crud': set(['create', 'read', 'update', 'delete']).issubset(actions),
                'route_count': len(routes),
                'routes': chain_steps,
                'call_chains': full_chains[:5],
                'score': len(actions) * 20 - len(missing) * 10,
            })

        # Sort by score (most complete lifecycles first)
        lifecycle_paths.sort(key=lambda x: x['score'], reverse=True)
        return lifecycle_paths[:10]

    def _trace_call_chain(self, handler: str, max_depth: int = 5) -> List[str]:
        """Trace the call chain starting from a handler via BFS on call_graph."""
        if not handler or handler not in self.call_adj:
            return [handler] if handler else []

        visited = set()
        chain = []
        queue = [(handler, 0)]

        while queue:
            node, depth = queue.pop(0)
            if node in visited or depth > max_depth:
                continue
            visited.add(node)
            chain.append(node)

            for callee in self.call_adj.get(node, []):
                if callee not in visited:
                    queue.append((callee, depth + 1))

        return chain[:15]

    # ──────────────────────────────────────────────
    # 2. Approval/Workflow Path Inference
    # ──────────────────────────────────────────────

    def infer_approval_workflows(self) -> List[dict]:
        """Detect approval/workflow patterns.

        Looks for:
        - Functions with submit/approve/reject/publish verbs
        - Routes that trigger these actions
        - Status transitions in structs
        """
        workflows = []

        # Find candidate entities with approval-related functions
        entity_approvals: Dict[str, List[dict]] = defaultdict(list)

        for func_name, func_info in self.func_map.items():
            fn_lower = func_name.lower()
            is_approval = any(v in fn_lower for v in APPROVAL_VERBS)
            is_publish = any(v in fn_lower for v in PUBLISH_VERBS)
            is_submit = any(v in fn_lower for v in SUBMIT_VERBS)
            is_status = any(v in fn_lower for v in STATUS_VERBS)

            if not (is_approval or is_publish or is_submit or is_status):
                continue

            # Extract entity from function name
            entity = self._extract_entity_from_func(func_name)

            verb_type = 'approval'
            if is_publish:
                verb_type = 'publish'
            elif is_submit:
                verb_type = 'submit'
            elif is_status:
                verb_type = 'status_change'

            entity_approvals[entity].append({
                'function': func_name,
                'verb_type': verb_type,
                'file': func_info.get('file', ''),
            })

        for entity, approvals in entity_approvals.items():
            if not entity:
                continue

            # Build workflow description
            steps = []
            for a in approvals:
                cn_type = {
                    'submit': '提交',
                    'approval': '审核',
                    'publish': '发布',
                    'status_change': '状态变更',
                }.get(a['verb_type'], a['verb_type'])
                steps.append(f"{cn_type}: {a['function']}")

            # Check for status constants in structs
            states = self._detect_states_for_entity(entity)

            workflows.append({
                'entity': entity,
                'workflow_type': 'approval_workflow',
                'steps': steps,
                'states': states,
                'step_count': len(steps),
                'score': len(steps) * 15 + len(states) * 10,
            })

        workflows.sort(key=lambda x: x['score'], reverse=True)
        return workflows[:8]

    def _extract_entity_from_func(self, func_name: str) -> str:
        """Extract entity name from function name like CreateAdGroup, UpdateCreative."""
        # Try PascalCase split first
        parts = re.split(r'(?<=[a-z])(?=[A-Z])', func_name)
        if len(parts) > 1:
            # First part is usually the entity
            entity = parts[0]
            if len(entity) > 1:
                return entity.lower()

        # Try prefix removal
        prefixes = ['Create', 'Update', 'Delete', 'Get', 'List', 'Search',
                     'Approve', 'Reject', 'Publish', 'Submit', 'Activate',
                     'Deactivate', 'Handle', 'Process', 'Validate']
        for prefix in prefixes:
            if func_name.startswith(prefix):
                remainder = func_name[len(prefix):]
                if remainder:
                    return remainder.lower()

        return ''

    def _detect_states_for_entity(self, entity: str) -> List[str]:
        """Detect state values from struct fields and function names."""
        states = []
        entity_lower = entity.lower()

        for struct in self.structs:
            if not isinstance(struct, dict):
                continue
            sname = struct.get('name', '').lower()
            if entity_lower not in sname:
                continue

            # Look at field names for status indicators
            for field in struct.get('fields', []):
                if isinstance(field, dict):
                    fname = field.get('name', '').lower()
                else:
                    fname = str(field).lower()
                if 'status' in fname or 'state' in fname or 'phase' in fname:
                    states.append(f"status_field:{fname}")

        # Also check function names for state transitions
        for func_name in self.func_map:
            fn_lower = func_name.lower()
            if entity_lower in fn_lower:
                for state_kw in ['pending', 'active', 'draft', 'approved', 'rejected',
                                  'published', 'archived', 'disabled', 'enabled', 'paused']:
                    if state_kw in fn_lower and state_kw not in states:
                        states.append(state_kw)

        return states[:10]

    # ──────────────────────────────────────────────
    # 3. Data Flow Chain Inference
    # ──────────────────────────────────────────────

    def infer_data_flow_chains(self) -> List[dict]:
        """Infer data flow chains: User → API → Handler → Service → DAO → DB.

        For each route, traces the full call chain and classifies each layer.
        """
        chains = []

        for rh in self.route_handlers:
            handler = rh.get('handler', '')
            path = rh.get('path', '')
            method = rh.get('method', 'GET')

            if not handler:
                continue

            # Trace the full call chain
            call_chain = self._trace_call_chain(handler)
            if not call_chain:
                continue

            # Classify each function into layers
            layers = self._classify_layers(call_chain)

            # Extract entities from route path
            entities = self._extract_entities_from_path(path)

            # Check for external dependencies
            ext_deps = self._detect_external_deps(call_chain)

            # Flow completeness check: verify expected layer progression
            completeness_issues = self._check_flow_completeness(layers)

            chains.append({
                'route': path,
                'method': method,
                'entry_handler': handler,
                'call_chain': call_chain,
                'layers': layers,
                'depth': len(layers),
                'entities': entities,
                'external_deps': ext_deps,
                'has_db_access': any('DB' in l for l in layers),
                'has_cache': any('Cache' in l for l in layers),
                'has_mq': any('MQ' in l for l in layers),
                'has_auth': any('Middleware' in l or 'Auth' in l for l in layers),
                'completeness_issues': completeness_issues,
                'score': len(layers) * 10 + len(entities) * 15 - len(completeness_issues) * 5,
            })

        chains.sort(key=lambda x: x['score'], reverse=True)
        return chains[:15]

    def _classify_layers(self, call_chain: List[str]) -> List[str]:
        """Classify each function in the chain into architectural layers.
        
        Enhanced strategy:
        1. File path keywords (primary)
        2. Function name patterns (secondary)  
        3. Struct embedding / type annotations (tertiary)
        4. Call graph position (quaternary)
        """
        layers = []
        seen_layers = set()

        for func_name in call_chain:
            func_info = self.func_map.get(func_name, {})
            file_path = func_info.get('file', '').lower()
            
            # Try to get return type or struct info from structs
            struct_type = self._infer_struct_type(func_name, func_info)
            
            layer = self._determine_layer(file_path, func_name, struct_type)
            if layer and layer not in seen_layers:
                seen_layers.add(layer)
                layers.append(layer)

        # Ensure canonical order: Handler → Middleware → Service → DAO → Cache/RPC/MQ → DB
        layer_order = ['Handler', 'Middleware', 'Service', 'DAO', 'Cache', 'RPC', 'MQ', 'DB']
        ordered = [l for l in layer_order if l in layers]
        # Add any remaining layers not in canonical order
        for l in layers:
            if l not in ordered:
                ordered.append(l)

        return ordered

    def _infer_struct_type(self, func_name: str, func_info: dict) -> Optional[str]:
        """Infer the struct/type this function operates on."""
        # From function name: CreateAdGroup → AdGroup
        parts = re.split(r'(?<=[a-z])(?=[A-Z])', func_name)
        if len(parts) > 1:
            entity = parts[0]
            if entity and len(entity) > 1:
                return entity.lower()
        
        # From receiver in func_info
        receiver = func_info.get('receiver', '')
        if receiver:
            return receiver.lower()
        
        return None

    def _determine_layer(self, file_path: str, func_name: str, struct_type: Optional[str] = None) -> str:
        """Determine the architectural layer of a function.
        
        Enhanced with struct-type-based inference.
        """
        path_kw = {
            'Handler': ['handler', 'controller', 'router', 'api', 'endpoint', 'http'],
            'Service': ['service', 'manager', 'biz', 'usecase', 'business'],
            'DAO': ['dao', 'repository', 'repo', 'model', 'db', 'storage'],
            'Middleware': ['middleware', 'intercept', 'guard', 'auth', 'logging'],
            'Cache': ['cache', 'redis', 'store', 'memcached'],
            'MQ': ['mq', 'kafka', 'rabbit', 'producer', 'consumer', 'worker', 'listener'],
            'RPC': ['rpc', 'client', 'proxy', 'grpc', 'remote'],
            'DB': ['migration', 'seed', 'migrate', 'schema'],
        }

        for layer, keywords in path_kw.items():
            if any(kw in file_path for kw in keywords):
                return layer

        # Fallback: check function name patterns
        name_patterns = {
            'Handler': ['Handler$', 'Handle$', 'Controller$', 'ServeHTTP$'],
            'Service': ['Service$', 'Manager$', 'UseCase$'],
            'DAO': ['DAO$', 'Repository$', 'Repo$', 'GetBy', 'FindBy', 'ListBy'],
            'Middleware': ['Middleware$', 'Guard$', 'Interceptor$'],
        }

        for layer, patterns in name_patterns.items():
            for pat in patterns:
                if re.search(pat, func_name):
                    return layer

        # Struct-type based inference: if struct is named like "XService", classify as Service
        if struct_type:
            struct_lower = struct_type.lower()
            if 'service' in struct_lower or 'manager' in struct_lower:
                return 'Service'
            if 'dao' in struct_lower or 'repo' in struct_lower or 'repository' in struct_lower:
                return 'DAO'
            if 'handler' in struct_lower or 'controller' in struct_lower:
                return 'Handler'

        return 'Unknown'

    def _extract_entities_from_path(self, path: str) -> List[str]:
        """Extract entity names from URL path."""
        entities = []
        parts = path.strip('/').split('/')

        skip_segments = {'api', 'v1', 'v2', 'v3', 'internal', 'public', 'admin'}
        for part in parts:
            part = re.sub(r'\{.*?\}', '', part)  # remove path params like {id}
            if part and part not in skip_segments and len(part) > 1:
                entities.append(part)

        return list(set(entities))[:5]

    def _detect_external_deps(self, call_chain: List[str]) -> List[str]:
        """Detect external dependencies from function names and configs."""
        deps = []

        # Check configs for external service URLs
        for config in self.configs:
            if isinstance(config, dict):
                url = config.get('url', config.get('endpoint', ''))
                if url and 'localhost' not in url and '127.0.0.1' not in url:
                    domain = url.split('/')[2] if '//' in url else url
                    if domain and domain not in deps:
                        deps.append(domain)

        # Check for known external patterns in function names
        external_patterns = ['stripe', 'aws', 'gcp', 'aliyun', 'twilio', 'sendgrid',
                             's3', 'oss', 'cdn', 'sms', 'email', 'webhook']
        for func_name in call_chain:
            fn_lower = func_name.lower()
            for pat in external_patterns:
                if pat in fn_lower and pat not in deps:
                    deps.append(pat)

        return deps[:5]

    def _check_flow_completeness(self, layers: List[str]) -> List[str]:
        """检查数据流完整性 — 验证分层架构的层数是否完整。
        
        完整的数据流应遵循: Handler → (Middleware) → Service → DAO → DB
        缺失的层可能表示问题:
        - 无 Middleware/Auth 在写操作上 → 安全风险
        - Handler → DAO 直接调用 → 缺少业务逻辑层
        - 读操作无缓存 → 潜在性能问题
        """
        issues = []
        
        has_handler = 'Handler' in layers
        has_service = 'Service' in layers
        has_dao = 'DAO' in layers
        has_middleware = 'Middleware' in layers
        has_cache = 'Cache' in layers
        has_db = 'DB' in layers
        
        # 检查1: Handler直接调用DAO（缺少Service层）
        if has_handler and has_dao and not has_service:
            issues.append("Handler直接调用DAO，缺少Service业务逻辑层")
        
        # 检查2: 写操作没有鉴权中间件
        if has_handler and has_dao and not has_middleware:
            issues.append("数据写入流程缺少鉴权中间件检查")
        
        # 检查3: 读操作无缓存且层数过少（性能提示）
        if has_handler and has_dao and not has_cache and len(layers) < 4:
            issues.append("查询流程无缓存且层数过少，可能存在性能风险")
        
        return issues

    # ──────────────────────────────────────────────
    # 4. Async/Event Path Inference
    # ──────────────────────────────────────────────

    def infer_async_event_paths(self) -> List[dict]:
        """Detect producer-consumer pairs and async event flows."""
        paths = []

        producers = []
        consumers = []

        for func_name, func_info in self.func_map.items():
            fn_lower = func_name.lower()
            file = func_info.get('file', '').lower()

            is_producer = any(kw in fn_lower for kw in ['publish', 'emit', 'produce', 'send_msg', 'fire_event'])
            is_consumer = any(kw in fn_lower for kw in ['consume', 'handle_event', 'process_msg', 'worker', 'listener', 'on_message'])

            # Also detect via file path
            if not is_producer and any(kw in file for kw in ['producer', 'publisher', 'emitter']):
                is_producer = True
            if not is_consumer and any(kw in file for kw in ['consumer', 'worker', 'listener', 'handler']):
                is_consumer = True

            if is_producer:
                producers.append({'name': func_name, 'file': func_info.get('file', '')})
            if is_consumer:
                consumers.append({'name': func_name, 'file': func_info.get('file', '')})

        # Pair producers with consumers
        for prod in producers:
            prod_domain = self._extract_domain_from_func(prod['name'])
            if not prod_domain:
                continue

            for cons in consumers:
                cons_domain = self._extract_domain_from_func(cons['name'])
                if not cons_domain:
                    continue

                # Match by domain similarity
                if prod_domain == cons_domain or prod_domain in cons_domain or cons_domain in prod_domain:
                    paths.append({
                        'producer': prod['name'],
                        'consumer': cons['name'],
                        'domain': prod_domain,
                        'path_type': 'async_event',
                        'stages': [f"Producer: {prod['name']}", 'MQ/Broker', f"Consumer: {cons['name']}"],
                        'score': 40,
                    })
                    break

        return paths[:10]

    def _extract_domain_from_func(self, func_name: str) -> str:
        """Extract domain keyword from function name."""
        # Remove common prefixes/suffixes
        cleaned = re.sub(r'^(On|Handle|Process|Publish|Emit|Send|Consume)', '', func_name)
        # Split camelCase
        parts = re.split(r'(?<=[a-z])(?=[A-Z])', cleaned)
        for p in parts:
            if 2 < len(p) < 20:
                return p.lower()
        return cleaned.lower()[:15]

    # ──────────────────────────────────────────────
    # 5. Auth Path Inference
    # ──────────────────────────────────────────────

    def infer_auth_paths(self) -> List[dict]:
        """Infer authentication and authorization paths."""
        paths = []

        # Detect auth middleware
        auth_middlewares = []
        for config in self.configs:
            if isinstance(config, dict):
                name = config.get('name', config.get('key', '')).lower()
                if any(kw in name for kw in ['jwt', 'oauth', 'token', 'session', 'cookie', 'auth']):
                    auth_middlewares.append(config.get('name', name))

        for struct in self.structs:
            if isinstance(struct, dict):
                sname = struct.get('name', '').lower()
                if any(kw in sname for kw in ['permission', 'role', 'rbac', 'abac', 'policy']):
                    auth_middlewares.append(struct.get('name', ''))

        # Detect auth-protected routes
        protected_routes = []
        for rh in self.route_handlers:
            handler = rh.get('handler', '')
            # Check if handler has auth-related calls
            if any(kw in handler.lower() for kw in ['auth', 'login', 'token', 'permission', 'role', 'verify']):
                protected_routes.append({
                    'route': rh.get('path', ''),
                    'handler': handler,
                    'type': 'auth_endpoint',
                })

        # Check for RBAC patterns in call graph
        rbac_funcs = []
        for func_name in self.func_map:
            fn_lower = func_name.lower()
            if any(kw in fn_lower for kw in ['authorize', 'check_permission', 'has_role', 'can_access', 'is_admin']):
                rbac_funcs.append(func_name)

        if auth_middlewares or protected_routes or rbac_funcs:
            paths.append({
                'type': 'authentication',
                'middlewares': auth_middlewares[:5],
                'auth_endpoints': protected_routes[:5],
                'rbac_functions': rbac_funcs[:5],
                'score': len(auth_middlewares) * 10 + len(protected_routes) * 15 + len(rbac_funcs) * 10,
            })

        return paths

    # ──────────────────────────────────────────────
    # 6. Top Entry Points
    # ──────────────────────────────────────────────

    def find_top_entry_points(self) -> List[dict]:
        """Find the most important entry points in the application.

        Entry points ranked by:
        - Number of downstream callers (in-degree in call graph)
        - Whether it's an HTTP handler
        - Whether it's referenced in business_logic
        """
        # Calculate in-degree for each function
        in_degree: Dict[str, int] = defaultdict(int)
        for edge in self.call_graph:
            if isinstance(edge, dict):
                callee = edge.get('callee', edge.get('to', ''))
            else:
                callee = getattr(edge, 'callee', getattr(edge, 'to', ''))
            if callee:
                in_degree[callee] += 1

        # Score each function
        candidates = []
        for func_name, func_info in self.func_map.items():
            score = in_degree.get(func_name, 0) * 10

            # Boost for HTTP handlers
            file = func_info.get('file', '').lower()
            if any(kw in file for kw in ['handler', 'controller', 'router']):
                score += 50

            # Boost for functions with many callees (fan-out)
            fan_out = len(self.call_adj.get(func_name, []))
            score += fan_out * 5

            # Boost for business logic functions
            if any(kw in func_name.lower() for kw in ['execute', 'run', 'process', 'handle']):
                score += 20

            candidates.append({
                'name': func_name,
                'file': func_info.get('file', ''),
                'score': score,
                'in_degree': in_degree.get(func_name, 0),
                'fan_out': fan_out,
                'is_handler': any(kw in file for kw in ['handler', 'controller', 'router']),
            })

        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates[:10]

    # ──────────────────────────────────────────────
    # 7. Entity Relationships
    # ──────────────────────────────────────────────

    def map_entity_relationships(self) -> List[dict]:
        """Map entity relationships from entity_tables, struct definitions, and cross-references.
        
        Enhanced with:
        1. Foreign key relationships from entity_tables
        2. Struct embedding (nested structs like AdGroup in Campaign)
        3. Cross-reference via function parameters/return types
        4. Self-references (parent_id, etc.)
        """
        relationships = []
        seen = set()  # dedup (source, target, relationship)
        
        def add_rel(source, target, rel, field='', score=20):
            key = (source, target, rel)
            if key not in seen:
                seen.add(key)
                relationships.append({
                    'source': source,
                    'target': target,
                    'relationship': rel,
                    'field': field,
                    'score': score,
                })
        
        # 1. Foreign keys from entity_tables
        for table in self.entity_tables:
            if not isinstance(table, dict):
                continue
            
            tname = table.get('name', '')
            if not tname:
                continue
            
            fks = table.get('foreign_keys', [])
            fields = table.get('fields', [])
            
            for fk in fks:
                if isinstance(fk, dict):
                    ref_table = fk.get('ref_table', fk.get('references', ''))
                    ref_field = fk.get('ref_field', fk.get('column', ''))
                    constraint = fk.get('constraint', fk.get('type', 'unknown'))
                    add_rel(tname, ref_table, constraint, ref_field, 30)
            
            # Self-references (parent_id, etc.)
            for field in fields:
                if isinstance(field, dict):
                    fname = field.get('name', '').lower()
                else:
                    fname = str(field).lower()
                if 'parent' in fname or 'ancestor' in fname or 'root' in fname:
                    add_rel(tname, tname, 'self_ref', fname, 25)
        
        # 2. Struct embedding — detect nested struct references
        # e.g., Campaign struct contains AdGroup field → Campaign has AdGroup
        struct_names = set()
        for s in self.structs:
            if isinstance(s, dict):
                name = s.get('name', '')
                if name:
                    struct_names.add(name.lower())
        
        for s in self.structs:
            if not isinstance(s, dict):
                continue
            sname = s.get('name', '').lower()
            if not sname:
                continue
            
            fields = s.get('fields', [])
            for field in fields:
                if isinstance(field, dict):
                    fname = field.get('name', '').lower()
                    ftype = field.get('type', '').lower()
                else:
                    fname = str(field).lower()
                    ftype = ''
                
                # Check if field type references another struct
                for sn in struct_names:
                    if sn != sname and (sn in ftype or ftype in sn):
                        add_rel(sname, sn, 'embeds', fname, 20)
                
                # Check for ID suffix → foreign key reference
                if fname.endswith('_id') and fname[:-3] in struct_names:
                    ref_entity = fname[:-3]
                    add_rel(sname, ref_entity, 'references', fname, 25)
        
        # 3. Cross-reference via error codes — errors often mention multiple entities
        for ec in self.error_codes:
            if isinstance(ec, dict):
                msg = ec.get('message', ec.get('description', '')).lower()
                for sn in struct_names:
                    if sn in msg:
                        # Error mentions this entity — potential relationship with other mentioned entities
                        pass
        
        return sorted(relationships, key=lambda x: x['score'], reverse=True)[:30]


# ──────────────────────────────────────────────
# NEW: Reliability Pattern Inference
# ──────────────────────────────────────────────

    def infer_reliability_patterns(self) -> List[dict]:
        """Detect retry, idempotency, and circuit breaker patterns from code.
        
        Looks for:
        - Retry logic (for loops with backoff, retry library usage)
        - Idempotency keys (unique constraints, dedup logic)
        - Circuit breakers (fallback patterns, timeout handling)
        - Dead letter queues (error handling with retry exhaustion)
        """
        patterns = []
        
        # 1. Detect idempotency patterns
        idempotent_funcs = []
        for func_name, func_info in self.func_map.items():
            fn_lower = func_name.lower()
            # Patterns: CreateWithIdempotencyKey, CheckDuplicate, Upsert, GetOrCreate
            if any(kw in fn_lower for kw in ['idempoten', 'dedup', 'upsert', 'get_or_create', 'unique_key', 'setnx', 'lock_key']):
                idempotent_funcs.append({
                    'name': func_name,
                    'file': func_info.get('file', ''),
                    'pattern': 'idempotency',
                })
        
        # 2. Detect retry patterns
        retry_funcs = []
        for func_name, func_info in self.func_map.items():
            fn_lower = func_name.lower()
            file = func_info.get('file', '').lower()
            if any(kw in fn_lower for kw in ['retry', 'backoff', 'exponential_retry']) or \
               any(kw in file for kw in ['retry', 'backoff']):
                retry_funcs.append({
                    'name': func_name,
                    'file': func_info.get('file', ''),
                    'pattern': 'retry',
                })
        
        # 3. Detect circuit breaker / fallback patterns
        cb_funcs = []
        for func_name, func_info in self.func_map.items():
            fn_lower = func_name.lower()
            if any(kw in fn_lower for kw in ['fallback', 'circuit_breaker', 'timeout_handler', 'degrade', 'fallback_']):
                cb_funcs.append({
                    'name': func_name,
                    'file': func_info.get('file', ''),
                    'pattern': 'circuit_breaker',
                })
        
        # 4. Detect dead letter queue patterns
        dlq_funcs = []
        for func_name, func_info in self.func_map.items():
            fn_lower = func_name.lower()
            if any(kw in fn_lower for kw in ['dead_letter', 'dlq', 'failed_msg', 'requeue', 'max_retry_exceeded']):
                dlq_funcs.append({
                    'name': func_name,
                    'file': func_info.get('file', ''),
                    'pattern': 'dead_letter_queue',
                })
        
        if idempotent_funcs:
            patterns.append({
                'type': 'idempotency',
                'functions': idempotent_funcs[:5],
                'coverage': f"{len(idempotent_funcs)} functions with idempotency protection",
                'risk_level': 'low' if len(idempotent_funcs) > 3 else 'medium',
            })
        
        if retry_funcs:
            patterns.append({
                'type': 'retry',
                'functions': retry_funcs[:5],
                'coverage': f"{len(retry_funcs)} retry patterns detected",
                'risk_level': 'low',
            })
        
        if cb_funcs:
            patterns.append({
                'type': 'circuit_breaker',
                'functions': cb_funcs[:5],
                'coverage': f"{len(cb_funcs)} fallback/circuit breaker patterns",
                'risk_level': 'low' if len(cb_funcs) > 2 else 'high',
            })
        
        if dlq_funcs:
            patterns.append({
                'type': 'dead_letter_queue',
                'functions': dlq_funcs[:5],
                'coverage': f"{len(dlq_funcs)} DLQ handlers",
                'risk_level': 'medium',
            })
        
        return patterns
    
    def infer_error_handling_patterns(self) -> List[dict]:
        """Detect error handling strategies from code structure.
        
        Looks for:
        - Error wrapping vs direct returns
        - Custom error types vs generic errors
        - Error code mapping
        - Panic/recover patterns
        """
        patterns = []
        
        # Analyze error codes for coverage
        error_code_categories = defaultdict(list)
        for ec in self.error_codes:
            if isinstance(ec, dict):
                cat = ec.get('category', 'unknown')
                error_code_categories[cat].append(ec.get('name', ''))
        
        # Detect panic/recover patterns
        panic_funcs = []
        for func_name in self.func_map:
            fn_lower = func_name.lower()
            if 'panic' in fn_lower or 'recover' in fn_lower:
                panic_funcs.append(func_name)
        
        # Detect error wrapping patterns via call graph
        wrapped_errors = []
        for edge in self.call_graph:
            if isinstance(edge, dict):
                caller = edge.get('caller', edge.get('from', ''))
                callee = edge.get('callee', edge.get('to', ''))
                if caller and callee and ('wrap' in caller.lower() or 'wrap' in callee.lower()):
                    wrapped_errors.append({
                        'caller': caller,
                        'callee': callee,
                    })
        
        if error_code_categories:
            total_errors = sum(len(v) for v in error_code_categories.values())
            categories_covered = len(error_code_categories)
            patterns.append({
                'type': 'error_code_coverage',
                'categories': dict(list(error_code_categories.items())[:10]),
                'total_codes': total_errors,
                'categories_count': categories_covered,
                'risk_level': 'low' if total_errors > 20 else 'medium',
            })
        
        if panic_funcs:
            patterns.append({
                'type': 'panic_recover',
                'functions': panic_funcs[:5],
                'risk_level': 'high' if len(panic_funcs) > 3 else 'medium',
                'note': 'Panic/recover patterns detected — consider using error returns instead',
            })
        
        return patterns
    
    def infer_transaction_patterns(self) -> List[dict]:
        """Detect database transaction patterns.
        
        Looks for:
        - Begin/Commit/Rollback sequences
        - Transaction-scoped operations
        - Cross-entity atomicity
        """
        patterns = []
        
        tx_funcs = []
        for func_name, func_info in self.func_map.items():
            fn_lower = func_name.lower()
            file = func_info.get('file', '').lower()
            if any(kw in fn_lower for kw in ['transaction', 'begin', 'commit', 'rollback', 'tx_']):
                tx_funcs.append({
                    'name': func_name,
                    'file': func_info.get('file', ''),
                    'pattern': 'database_transaction',
                })
            elif any(kw in file for kw in ['transaction', 'tx/', 'db_tx']):
                tx_funcs.append({
                    'name': func_name,
                    'file': func_info.get('file', ''),
                    'pattern': 'database_transaction',
                })
        
        if tx_funcs:
            # Group by entity
            entity_groups = defaultdict(list)
            for tf in tx_funcs:
                entity = self._extract_entity_from_func(tf['name'])
                entity_groups[entity].append(tf['name'])
            
            patterns.append({
                'type': 'database_transaction',
                'functions': tx_funcs[:10],
                'entities_affected': list(entity_groups.keys())[:8],
                'total_transactions': len(tx_funcs),
                'risk_level': 'medium',
            })
        
        return patterns


# ──────────────────────────────────────────────
# Convenience function
# ──────────────────────────────────────────────

def infer_business_paths(ir_data: dict) -> dict:
    """Quick entry point for business path inference."""
    analyzer = BusinessPathInference(ir_data)
    return analyzer.infer_all()
