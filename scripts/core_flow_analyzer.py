#!/usr/bin/env python3
"""Enhanced core flow extraction — infers business flows from code.

Replaces the basic _infer_core_business_flow in learn_repo.py with
a more sophisticated analyzer that detects:
1. Bidirectional dependencies (call graph + reverse call graph)
2. State machine transitions from code patterns
3. Data ownership mapping (which service owns which entity)
4. Cross-cutting concerns (auth, logging, metrics, retries)
5. Async/event-driven flows (MQ publish/consume pairs)
"""

import re
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict


class CoreFlowAnalyzer:
    """Enhanced core flow analyzer."""

    # Patterns that indicate state transitions
    STATE_TRANSITION_PATTERNS = [
        r'\.SetStatus\s*\(',
        r'\.UpdateStatus\s*\(',
        r'status\s*=\s*\w+',
        r'Status\s*:\s*\w+',
        r'\.Approve\s*\(',
        r'\.Reject\s*\(',
        r'\.Publish\s*\(',
        r'\.Submit\s*\(',
        r'\.Transition\s*\(',
        r'\.ChangeState\s*\(',
    ]

    # Patterns that indicate async/event operations
    ASYNC_PATTERNS = [
        r'mq\.\w+\s*\(',
        r'kafka\.\w+\s*\(',
        r'publish\s*\(',
        r'Emit\s*\(',
        r'Send\s*\(',
        r'async\.\w+\s*\(',
    ]

    # Patterns that indicate CRUD operations
    CRUD_PATTERNS = {
        'create': [r'\.Create\s*\(', r'\.Insert\s*\(', r'\.Build\s*\(', r'New\w+'],
        'read': [r'\.Get\s*\(', r'\.Query\s*\(', r'\.List\s*\(', r'\.Find\s*\(', r'\.Search\s*\('],
        'update': [r'\.Update\s*\(', r'\.Modify\s*\(', r'\.Patch\s*\('],
        'delete': [r'\.Delete\s*\(', r'\.Remove\s*\(', r'\.Destroy\s*\('],
    }

    def __init__(self, ir_data: dict):
        self.ir = ir_data
        self.call_graph = ir_data.get('call_graph', [])
        self.reverse_graph: Dict[str, List[str]] = defaultdict(list)
        self.business_logic = ir_data.get('business_logic', [])
        self.routes = ir_data.get('routes', [])
        self.functions = ir_data.get('functions', [])
        self.structs = ir_data.get('structs', [])
        self.entity_tables = ir_data.get('entity_tables', [])
        self.core_flows = ir_data.get('core_flows', [])
        self.services = ir_data.get('services', [])

        # Build reverse call graph
        self._build_reverse_graph()

    def _build_reverse_graph(self):
        """Build reverse call graph (callee → callers)."""
        for edge in self.call_graph:
            if isinstance(edge, dict):
                caller = edge.get('caller', edge.get('from', ''))
                callee = edge.get('callee', edge.get('to', ''))
            else:
                caller = getattr(edge, 'caller', '')
                callee = getattr(edge, 'callee', '')
            if caller and callee:
                self.reverse_graph[callee].append(caller)

    def infer_flows(self) -> List[Dict]:
        """Run all flow inference strategies and return combined results."""
        flows = []

        # Strategy 1: Infer from business_logic (existing)
        flows.extend(self._infer_from_business_logic())

        # Strategy 2: Infer state machine flows
        flows.extend(self._infer_state_machine_flows())

        # Strategy 3: Infer async/event flows
        flows.extend(self._infer_async_flows())

        # Strategy 4: Infer CRUD-based flows
        flows.extend(self._infer_crud_flows())

        # Strategy 5: Infer data flows (new — route → handler → service → dao → db)
        flows.extend(self._infer_data_flow_routes())

        # Merge and deduplicate
        merged = self._merge_similar_flows(flows)
        return self._rank_flows(merged)

    def _infer_data_flow_routes(self) -> List[Dict]:
        """Infer data flows from routes using func_layer classification.
        
        Complements infer_data_flows() by producing simplified flow entries
        compatible with the existing flow format.
        """
        flows = []
        func_layer = {}
        for func in self.functions:
            if not isinstance(func, dict):
                continue
            fname = func.get('name', '')
            ffile = func.get('file', '')
            if not fname or not ffile:
                continue
            file_lower = ffile.lower()
            if any(kw in file_lower for kw in ['handler', 'router', 'controller']):
                layer = 'Handler'
            elif any(kw in file_lower for kw in ['service', 'manager', 'biz']):
                layer = 'Service'
            elif any(kw in file_lower for kw in ['dao', 'repo', 'repository']):
                layer = 'DAO'
            else:
                layer = 'Unknown'
            func_layer[fname] = layer

        for route in self.routes:
            if not isinstance(route, dict):
                continue
            handler = route.get('handler', '')
            path = route.get('path', '')
            method = route.get('method', 'GET')
            if not handler:
                continue
            entities = self._extract_entities_from_path(path)
            layers = [f"HTTP {method}"]
            current = handler
            visited = set()
            queue = [(handler, 0)]
            while queue:
                fn, depth = queue.pop(0)
                if fn in visited or depth > 4:
                    continue
                visited.add(fn)
                layer = func_layer.get(fn, 'Unknown')
                if layer not in layers:
                    layers.append(layer)
                for edge in self.call_graph:
                    if not isinstance(edge, dict):
                        continue
                    caller = edge.get('caller', '')
                    callee = edge.get('callee', '')
                    if caller == fn and callee not in visited:
                        queue.append((callee, depth + 1))
            if entities:
                layers.append('DB/Cache')
            if len(layers) >= 3:
                flows.append({
                    'flow_name': f"{path} 数据流",
                    'flow_type': 'data_flow',
                    'entry_point': handler,
                    'route': path,
                    'call_chain': list(visited)[:15],
                    'max_depth': len(layers) - 1,
                    'data_flow': " → ".join(layers),
                    'stages': layers,
                    'entities': entities,
                    'score': len(layers) * 15 + len(entities) * 10,
                })
        return flows

    def _infer_from_business_logic(self) -> List[Dict]:
        """Infer flows from existing business_logic entries."""
        flows = []
        for bl in self.business_logic:
            route = bl.get('route', '')
            handler = bl.get('handler', '')
            call_chain = bl.get('call_chain', [])
            call_tree = bl.get('call_tree', [])
            data_flow = bl.get('data_flow', {})

            # Calculate max depth
            max_depth = self._calc_depth(call_tree)

            flows.append({
                'flow_name': self._infer_flow_name(handler, route),
                'flow_type': 'http_handler',
                'entry_point': handler,
                'route': route,
                'call_chain': call_chain[:20],
                'max_depth': max_depth,
                'data_flow': data_flow if isinstance(data_flow, str) else json.dumps(data_flow, ensure_ascii=False)[:200],
                'stages': self._extract_stages(call_chain),
                'score': max_depth * 10 + len(call_chain),
            })
        return flows

    def _infer_state_machine_flows(self) -> List[Dict]:
        """Detect state machine flows from code patterns."""
        flows = []

        # Find structs with status fields
        status_structs = set()
        for struct in self.structs:
            if isinstance(struct, dict):
                name = struct.get('name', '')
                fields = struct.get('fields', [])
            else:
                name = getattr(struct, 'name', '')
                fields = getattr(struct, 'fields', [])

            has_status = False
            for f in fields:
                if isinstance(f, dict):
                    fname = f.get('name', '')
                else:
                    fname = str(f)
                if 'status' in fname.lower() or 'state' in fname.lower():
                    has_status = True
                    break

            if has_status:
                status_structs.add(name)

        if not status_structs:
            return flows

        # For each status struct, find related methods
        for struct_name in status_structs:
            related_methods = []
            for func in self.functions:
                if isinstance(func, dict):
                    fname = func.get('name', '')
                else:
                    fname = getattr(func, 'name', '')

                # Check if method name suggests state transition
                if any(pattern in fname.lower() for pattern in
                       ['approve', 'reject', 'publish', 'submit', 'activate',
                        'deactivate', 'pause', 'resume', 'status', 'transition']):
                    related_methods.append(fname)

            if related_methods:
                # Find the route that triggers these
                entry_point = related_methods[0] if related_methods else struct_name
                routes = [r.get('path', '') if isinstance(r, dict) else getattr(r, 'path', '')
                          for r in self.routes if entry_point.lower() in
                          (r.get('handler', '') if isinstance(r, dict) else getattr(r, 'handler', '')).lower()]

                flows.append({
                    'flow_name': f"{struct_name} 状态机流程",
                    'flow_type': 'state_machine',
                    'entry_point': entry_point,
                    'route': routes[0] if routes else '',
                    'call_chain': related_methods[:15],
                    'max_depth': 3,
                    'data_flow': f"Request → Handler → {struct_name}Service → StatusTransition → DB",
                    'stages': ['Request', 'Handler', f'{struct_name}Service', 'StatusTransition', 'DB'],
                    'states': self._detect_states(struct_name),
                    'score': 50 + len(related_methods) * 5,
                })

        return flows

    def _detect_states(self, struct_name: str) -> List[str]:
        """Detect possible states from code patterns."""
        states = []
        # Look for constant definitions that might be states
        state_patterns = [
            r'Status\d+', r'State\d+', r'Pending', r'Active', r'Inactive',
            r'Draft', r'Approved', r'Rejected', r'Published', r'Archived',
        ]
        for pattern in state_patterns:
            for func in self.functions:
                fname = func.get('name', '') if isinstance(func, dict) else getattr(func, 'name', '')
                if re.search(pattern, fname, re.IGNORECASE):
                    state_name = re.search(pattern, fname, re.IGNORECASE)
                    if state_name and state_name.group() not in states:
                        states.append(state_name.group())
        return states[:10]

    def _infer_async_flows(self) -> List[Dict]:
        """Detect async/event-driven flows from MQ patterns."""
        flows = []

        # Find producer-consumer pairs
        producers = []
        consumers = []

        for func in self.functions:
            fname = func.get('name', '') if isinstance(func, dict) else getattr(func, 'name', '')
            file = func.get('file', '') if isinstance(func, dict) else getattr(func, 'file', '')

            # Check for MQ publish patterns
            if any(re.search(p, fname, re.IGNORECASE) for p in ['publish', 'emit', 'send', 'produce']):
                producers.append({'name': fname, 'file': file})

            # Check for MQ consume patterns
            if any(re.search(p, fname, re.IGNORECASE) for p in ['consume', 'handle', 'process', 'worker', 'listener']):
                consumers.append({'name': fname, 'file': file})

        # Try to pair producers with consumers
        for prod in producers:
            for cons in consumers:
                # Heuristic: same domain name in both
                prod_domain = prod['name'].lower().split('publish')[0].split('emit')[0].split('send')[0]
                cons_domain = cons['name'].lower().split('consume')[0].split('handle')[0].split('process')[0]
                if prod_domain and cons_domain and (prod_domain in cons_domain or cons_domain in prod_domain):
                    flows.append({
                        'flow_name': f"异步消息流: {prod['name']} → {cons['name']}",
                        'flow_type': 'async_event',
                        'entry_point': prod['name'],
                        'route': '',
                        'call_chain': [prod['name'], 'MQ/Broker', cons['name']],
                        'max_depth': 3,
                        'data_flow': f"{prod['name']} → MQ → {cons['name']}",
                        'stages': ['Producer', 'MQ', 'Consumer'],
                        'producer': prod['name'],
                        'consumer': cons['name'],
                        'score': 40,
                    })
                    break  # One pairing per producer

        return flows

    def _infer_crud_flows(self) -> List[Dict]:
        """Detect CRUD-based flows from route patterns."""
        flows = []

        # Group routes by resource
        resource_routes = defaultdict(list)
        for route in self.routes:
            path = route.get('path', '') if isinstance(route, dict) else getattr(route, 'path', '')
            # Extract resource name from path (e.g., /api/v1/creatives → creatives)
            parts = path.strip('/').split('/')
            if len(parts) >= 3:
                resource = parts[-2] if len(parts) > 3 else parts[-1]
                resource_routes[resource].append(route)

        for resource, routes in resource_routes.items():
            methods = [r.get('method', '') if isinstance(r, dict) else getattr(r, 'method', '') for r in routes]
            handlers = [r.get('handler', '') if isinstance(r, dict) else getattr(r, 'handler', '') for r in routes]

            crud_ops = []
            for m in methods:
                if 'POST' in m:
                    crud_ops.append('Create')
                elif 'GET' in m:
                    crud_ops.append('Read')
                elif 'PUT' in m or 'PATCH' in m:
                    crud_ops.append('Update')
                elif 'DELETE' in m:
                    crud_ops.append('Delete')

            if crud_ops:
                flows.append({
                    'flow_name': f"{resource} CRUD 流程",
                    'flow_type': 'crud',
                    'entry_point': handlers[0] if handlers else resource,
                    'route': routes[0].get('path', '') if isinstance(routes[0], dict) else getattr(routes[0], 'path', ''),
                    'call_chain': handlers[:10],
                    'max_depth': 3,
                    'data_flow': f"Request → {resource}Handler → {resource}Service → {resource}DAO → DB",
                    'stages': ['Request', f'{resource}Handler', f'{resource}Service', f'{resource}DAO', 'DB'],
                    'crud_ops': crud_ops,
                    'score': 30 + len(handlers) * 5,
                })

        return flows

    def _merge_similar_flows(self, flows: List[Dict]) -> List[Dict]:
        """Merge flows with similar characteristics."""
        if not flows:
            return flows

        # Group by flow_type
        groups = defaultdict(list)
        for flow in flows:
            groups[flow.get('flow_type', 'unknown')].append(flow)

        merged = []
        for ftype, group in groups.items():
            # Within each group, merge flows with overlapping call chains
            used = [False] * len(group)
            for i in range(len(group)):
                if used[i]:
                    continue
                base = dict(group[i])
                base_call_set = set(base.get('call_chain', []))

                for j in range(i + 1, len(group)):
                    if used[j]:
                        continue
                    other = group[j]
                    other_call_set = set(other.get('call_chain', []))

                    # Jaccard similarity
                    intersection = base_call_set & other_call_set
                    union = base_call_set | other_call_set
                    if not union:
                        continue
                    similarity = len(intersection) / len(union)

                    if similarity > 0.5:
                        # Merge
                        base['call_chain'] = list(dict.fromkeys(base.get('call_chain', []) + other.get('call_chain', [])))[:30]
                        base['handlers'] = list(dict.fromkeys(base.get('handlers', [base['entry_point']]) + [other.get('entry_point', '')]))[:10]
                        base['max_depth'] = max(base.get('max_depth', 0), other.get('max_depth', 0))
                        base['score'] += other.get('score', 0) * 0.5
                        used[j] = True

                merged.append(base)

        return merged

    def _rank_flows(self, flows: List[Dict]) -> List[Dict]:
        """Rank flows by importance."""
        # Sort by score (descending)
        flows.sort(key=lambda x: x.get('score', 0), reverse=True)
        return flows[:15]  # Top 15 flows

    def _calc_depth(self, call_tree: list, current: int = 0) -> int:
        """Calculate max depth of call tree."""
        if not call_tree:
            return current
        max_d = current
        for entry in call_tree:
            if isinstance(entry, dict):
                d = self._calc_depth(entry.get('calls', []), current + 1)
            else:
                d = current + 1
            max_d = max(max_d, d)
        return max_d

    def _extract_stages(self, call_chain: List[str]) -> List[str]:
        """Extract logical stages from call chain."""
        stages = []
        stage_keywords = {
            'Request': ['bind', 'parse', 'validate', 'req'],
            'Handler': ['handler', 'controller'],
            'Service': ['service', 'manager'],
            'DAO': ['dao', 'repository', 'repo'],
            'DB': ['db', 'query', 'exec', 'insert', 'update', 'delete'],
            'Cache': ['cache', 'redis'],
            'MQ': ['publish', 'consume', 'mq', 'kafka'],
            'RPC': ['rpc', 'client', 'proxy'],
        }
        for name in call_chain:
            name_lower = name.lower()
            for stage, keywords in stage_keywords.items():
                if any(kw in name_lower for kw in keywords):
                    if stage not in stages:
                        stages.append(stage)
        return stages

    def _infer_flow_name(self, handler: str, route: str) -> str:
        """Infer a human-readable flow name."""
        verb_map = {
            'create': '创建', 'add': '新增', 'insert': '插入',
            'update': '更新', 'edit': '编辑', 'modify': '修改',
            'delete': '删除', 'remove': '移除',
            'get': '查询', 'list': '列表', 'search': '搜索', 'query': '检索',
            'approve': '审核', 'review': '复核', 'audit': '审计',
            'publish': '发布', 'release': '上线', 'submit': '提交',
            'pause': '暂停', 'resume': '恢复', 'activate': '激活',
            'share': '分享', 'export': '导出', 'import': '导入',
            'sync': '同步', 'refresh': '刷新',
        }
        text = f"{handler} {route}".lower()
        for eng, cn in verb_map.items():
            if eng in text:
                # Try to get the noun before the verb
                parts = text.split(eng)
                noun = parts[0].strip().replace('_', ' ').replace('-', ' ')
                if noun:
                    return f"{noun} {cn}流程"
                return f"{cn}流程"
        return f"业务流 ({handler})"

    # ──────────────────────────────────────────────
    # NEW: Enhanced data flow inference
    # ──────────────────────────────────────────────

    def infer_data_flows(self) -> List[Dict]:
        """Infer data flows from routes → handlers → services → DAOs → DB.
        
        Strategy:
        1. Start from HTTP routes as entry points
        2. Trace handler → service → dao layers via call_graph
        3. Map entity_tables to identify DB ownership
        4. Detect cross-service dependencies via RPC/MQ patterns
        
        Returns: [{flow_name, entry_point, layers, entities, score}]
        """
        flows = []
        
        # Build a map: function name → which layer it belongs to
        func_layer = {}
        for func in self.functions:
            fname = func.get('name', '') if isinstance(func, dict) else getattr(func, 'name', '')
            file = func.get('file', '') if isinstance(func, dict) else getattr(func, 'file', '')
            
            if not fname or not file:
                continue
            
            # Classify by file path or name patterns
            file_lower = file.lower()
            if any(kw in file_lower for kw in ['handler', 'router', 'controller', 'api']):
                layer = 'Handler'
            elif any(kw in file_lower for kw in ['service', 'manager', 'biz']):
                layer = 'Service'
            elif any(kw in file_lower for kw in ['dao', 'repo', 'repository', 'model']):
                layer = 'DAO'
            elif any(kw in file_lower for kw in ['middleware', 'auth', 'intercept']):
                layer = 'Middleware'
            else:
                layer = 'Unknown'
            
            func_layer[fname] = layer
        
        # For each route, build the full data flow chain
        for route in self.routes:
            if not isinstance(route, dict):
                continue
            
            handler = route.get('handler', '')
            path = route.get('path', '')
            method = route.get('method', 'GET')
            
            if not handler:
                continue
            
            # Extract entities from route path
            entities = self._extract_entities_from_path(path)
            
            # Build layer chain from handler name
            layers = [f"HTTP {method}"]
            current = handler
            visited = set()
            
            # BFS through call_graph to find downstream functions
            queue = [(handler, 0)]
            while queue:
                fn, depth = queue.pop(0)
                if fn in visited or depth > 4:
                    continue
                visited.add(fn)
                
                layer = func_layer.get(fn, 'Unknown')
                if layer not in layers:
                    layers.append(layer)
                
                # Find callees of this function
                for edge in self.call_graph:
                    if not isinstance(edge, dict):
                        continue
                    caller = edge.get('caller', '')
                    callee = edge.get('callee', '')
                    if caller == fn and callee not in visited:
                        queue.append((callee, depth + 1))
            
            # Add data storage layer if we have entity_tables
            if entities:
                layers.append('DB/Cache')
            
            if len(layers) >= 3:
                flows.append({
                    'flow_name': f"{path} 数据流",
                    'entry_point': handler,
                    'route': path,
                    'http_method': method,
                    'layers': layers,
                    'entities': entities,
                    'depth': len(layers) - 1,
                    'score': len(layers) * 15 + len(entities) * 10,
                })
        
        # Sort by depth (deeper = more complex = more important)
        flows.sort(key=lambda x: x['score'], reverse=True)
        return flows[:20]
    
    def _extract_entities_from_path(self, path: str) -> List[str]:
        """Extract entity names from API path like /api/v1/creatives/{id}/review."""
        parts = path.strip('/').split('/')
        entities = []
        for part in parts:
            # Skip version segments like 'v1'
            if re.match(r'^v\d+$', part):
                continue
            # Skip placeholder segments like '{id}'
            if re.match(r'^\{.*\}$', part):
                continue
            if part and len(part) > 2:
                entities.append(part)
        return entities

    # ──────────────────────────────────────────────
    # NEW: Service topology inference
    # ──────────────────────────────────────────────

    def infer_service_topology(self) -> Dict[str, Any]:
        """Infer service/component topology from call_graph and function metadata.
        
        Groups functions into logical services/components based on:
        1. File path patterns (e.g., service/adgroup/, dao/adgroup/)
        2. Call graph connectivity (strongly connected components)
        3. Shared entity/table ownership
        
        Returns: {
            'services': [{name, type, functions[], depends_on[], owns_entities[]}],
            'cross_service_deps': [(src_service, dst_service, dep_type)],
        }
        """
        # Build function → file path map
        func_to_file = {}
        for func in self.functions:
            if isinstance(func, dict):
                fname = func.get('name', '')
                ffile = func.get('file', '')
            else:
                fname = getattr(func, 'name', '')
                ffile = getattr(func, 'file', '')
            if fname and ffile:
                func_to_file[fname] = ffile
        
        # Group functions by service (inferred from file path)
        service_groups = defaultdict(list)
        for fname, ffile in func_to_file.items():
            # Extract service name from file path
            parts = Path(ffile).parts
            # Find the deepest meaningful directory component
            service_name = None
            for i, part in enumerate(parts):
                if any(kw in part.lower() for kw in ['service', 'handler', 'router', 'controller', 'dao', 'repo', 'middleware']):
                    if i + 1 < len(parts):
                        service_name = parts[i + 1]
                    else:
                        service_name = part
                    break
            if not service_name:
                # Fallback: use first directory after package
                if len(parts) > 1:
                    service_name = parts[-2] if len(parts) > 2 else parts[-1]
                else:
                    service_name = 'default'
            
            service_groups[service_name].append(fname)
        
        # Classify service types
        services = []
        for svc_name, funcs in service_groups.items():
            svc_type = 'unknown'
            # Check if this service is primarily a handler/router
            if any('handler' in f or 'router' in f or 'controller' in f 
                   for f in [func_to_file.get(fn, '').lower() for fn in funcs]):
                svc_type = 'handler'
            elif any('dao' in f or 'repo' in f or 'repository' in f 
                     for f in [func_to_file.get(fn, '').lower() for fn in funcs]):
                svc_type = 'dao'
            elif any('service' in f or 'manager' in f or 'biz' in f 
                     for f in [func_to_file.get(fn, '').lower() for fn in funcs]):
                svc_type = 'service'
            elif any('middleware' in f or 'auth' in f for f in [func_to_file.get(fn, '').lower() for fn in funcs]):
                svc_type = 'middleware'
            
            # Find entities owned by this service
            owned_entities = set()
            for func in funcs:
                # Check if function name suggests entity ownership
                for et in self.entity_tables:
                    if isinstance(et, dict):
                        entity = et.get('entity', '')
                    else:
                        entity = str(et)
                    if entity.lower() in func.lower() or func.lower() in entity.lower():
                        owned_entities.add(entity)
            
            services.append({
                'name': svc_name,
                'type': svc_type,
                'functions': funcs[:15],
                'owns_entities': list(owned_entities)[:10],
                'function_count': len(funcs),
            })
        
        # Detect cross-service dependencies from call_graph
        cross_deps = []
        svc_map = {svc['name']: svc for svc in services}
        seen_deps = set()
        
        for edge in self.call_graph:
            if not isinstance(edge, dict):
                continue
            caller = edge.get('caller', '')
            callee = edge.get('callee', '')
            
            caller_svc = None
            callee_svc = None
            for svc_name, svc_funcs in svc_map.items():
                if caller in svc_funcs['functions']:
                    caller_svc = svc_name
                if callee in svc_funcs['functions']:
                    callee_svc = svc_name
            
            if caller_svc and callee_svc and caller_svc != callee_svc:
                dep_key = (caller_svc, callee_svc)
                if dep_key not in seen_deps:
                    seen_deps.add(dep_key)
                    dep_type = 'sync_call'
                    # Check if it's an async/MQ call
                    if any(kw in caller.lower() for kw in ['publish', 'emit', 'send', 'mq', 'kafka']):
                        dep_type = 'async_mq'
                    elif any(kw in caller.lower() for kw in ['rpc', 'client', 'proxy']):
                        dep_type = 'rpc'
                    
                    cross_deps.append({
                        'source': caller_svc,
                        'target': callee_svc,
                        'type': dep_type,
                    })
        
        return {
            'services': services,
            'cross_service_deps': cross_deps,
            'service_count': len(services),
            'dep_count': len(cross_deps),
        }

    # ──────────────────────────────────────────────
    # NEW: Entity ownership analysis
    # ──────────────────────────────────────────────

    def analyze_entity_ownership(self) -> List[Dict]:
        """Analyze which services/entities own which tables and operations.
        
        Returns: [{entity, table, operations[], owning_services[], access_patterns[]}]
        """
        if not self.entity_tables:
            return []
        
        ownership = []
        for et in self.entity_tables:
            if not isinstance(et, dict):
                continue
            
            entity = et.get('entity', '')
            table = et.get('table', '')
            ops = et.get('operations', [])
            
            # Find which functions access this entity
            accessing_funcs = []
            for func in self.functions:
                if isinstance(func, dict):
                    fname = func.get('name', '')
                else:
                    fname = getattr(func, 'name', '')
                if entity.lower() in fname.lower() or table.lower() in fname.lower():
                    accessing_funcs.append(fname)
            
            # Find which routes touch this entity
            touching_routes = []
            for route in self.routes:
                if not isinstance(route, dict):
                    continue
                path = route.get('path', '')
                handler = route.get('handler', '')
                if entity.lower() in path.lower() or entity.lower() in handler.lower():
                    touching_routes.append(f"{route.get('method', 'GET')} {path}")
            
            ownership.append({
                'entity': entity,
                'table': table,
                'operations': ops[:10],
                'accessing_functions': accessing_funcs[:10],
                'touching_routes': touching_routes[:10],
                'read_count': sum(1 for o in ops if o in ['SELECT', 'Get', 'Query', 'List']),
                'write_count': sum(1 for o in ops if o in ['INSERT', 'UPDATE', 'DELETE', 'Create', 'Modify', 'Remove']),
            })
        
        # Sort by access frequency (more accessed = more important)
        ownership.sort(key=lambda x: len(x['accessing_functions']) + len(x['touching_routes']), reverse=True)
        return ownership[:20]

    # ──────────────────────────────────────────────
    # NEW: Business process clustering
    # ──────────────────────────────────────────────

    def cluster_business_processes(self) -> List[Dict]:
        """Cluster related flows into business processes.
        
        E.g., CreateAdGroup → ReviewAdGroup → PublishAdGroup → MonitorAdGroup
        are clustered into one "广告组生命周期" process.
        
        Strategy:
        1. Group routes by resource name (e.g., all /creatives/* routes)
        2. Within each group, order by HTTP method (POST→PUT→DELETE)
        3. Detect state transitions (submit→approve→publish)
        4. Merge related clusters into complete business processes
        """
        # Group routes by resource
        resource_routes = defaultdict(list)
        for route in self.routes:
            if not isinstance(route, dict):
                continue
            path = route.get('path', '')
            resource = self._extract_root_resource(path)
            if resource:
                resource_routes[resource].append(route)
        
        processes = []
        for resource, routes in resource_routes.items():
            if len(routes) < 2:
                continue
            
            # Analyze what operations exist for this resource
            operations = []
            for r in routes:
                method = r.get('method', '')
                handler = r.get('handler', '')
                operations.append({
                    'method': method,
                    'handler': handler,
                    'path': r.get('path', ''),
                })
            
            # Detect lifecycle stages
            lifecycle = self._detect_lifecycle(resource, operations)
            
            if lifecycle:
                processes.append({
                    'process_name': f"{self._cn_resource(resource)} 业务流程",
                    'resource': resource,
                    'stages': lifecycle,
                    'operations': operations[:10],
                    'has_state_machine': any(s.get('is_state_transition') for s in lifecycle),
                    'score': len(lifecycle) * 20,
                })
        
        processes.sort(key=lambda x: x['score'], reverse=True)
        return processes[:10]
    
    def _extract_root_resource(self, path: str) -> Optional[str]:
        """Extract root resource from path like /api/v1/creatives/review → creatives."""
        parts = path.strip('/').split('/')
        # Skip /api/vN/ prefix
        idx = 0
        if parts and parts[idx] == 'api':
            idx += 1
        if idx < len(parts) and re.match(r'^v\d+$', parts[idx]):
            idx += 1
        # The next segment is the resource
        if idx < len(parts):
            return parts[idx]
        return None
    
    def _cn_resource(self, resource: str) -> str:
        """Translate English resource name to Chinese."""
        cn_map = {
            'creative': '素材', 'adgroup': '广告组', 'campaign': '广告计划',
            'account': '账户', 'report': '报表', 'stats': '统计',
            'user': '用户', 'order': '订单', 'product': '商品',
            'budget': '预算', 'bid': '出价', 'targeting': '定向',
            'placement': '广告位', 'feedback': '反馈', 'audit': '审核',
            'ad': '广告', 'media': '媒体', 'channel': '渠道',
        }
        return cn_map.get(resource.lower(), resource)
    
    def _detect_lifecycle(self, resource: str, operations: List[Dict]) -> List[Dict]:
        """Detect lifecycle stages from operations.
        
        E.g., POST=create, PUT=update, DELETE=delete, POST+review=approve
        """
        stages = []
        stage_names = {'create': '创建', 'update': '更新', 'delete': '删除',
                       'get': '查询', 'list': '列表', 'search': '搜索'}
        
        for op in operations:
            method = op['method']
            handler = op['handler'].lower()
            
            # Determine stage type
            stage_type = 'operation'
            is_state_transition = False
            
            if 'create' in handler or 'add' in handler or 'insert' in handler:
                stage_type = 'create'
            elif 'delete' in handler or 'remove' in handler:
                stage_type = 'delete'
            elif 'update' in handler or 'edit' in handler:
                stage_type = 'update'
            elif 'get' in handler or 'query' in handler or 'detail' in handler:
                stage_type = 'read'
            elif 'list' in handler or 'search' in handler or 'page' in handler:
                stage_type = 'list'
            elif any(kw in handler for kw in ['approve', 'reject', 'review', 'audit']):
                stage_type = 'approval'
                is_state_transition = True
            elif any(kw in handler for kw in ['publish', 'release', 'activate']):
                stage_type = 'publish'
                is_state_transition = True
            elif any(kw in handler for kw in ['pause', 'stop', 'deactivate']):
                stage_type = 'pause'
                is_state_transition = True
            elif any(kw in handler for kw in ['sync', 'refresh']):
                stage_type = 'sync'
            elif 'export' in handler:
                stage_type = 'export'
            elif 'import' in handler:
                stage_type = 'import'
            
            if stage_type in stage_names:
                cn_name = stage_names[stage_type]
            else:
                cn_name = handler.split('.')[-1] if '.' in handler else handler
            
            stages.append({
                'type': stage_type,
                'name': cn_name,
                'handler': op['handler'],
                'method': method,
                'path': op['path'],
                'is_state_transition': is_state_transition,
            })
        
        # Reorder: read/list first, then create, then update, then approval/publish
        order = {'list': 0, 'read': 1, 'create': 2, 'update': 3, 
                 'approval': 4, 'publish': 5, 'pause': 6, 'delete': 7,
                 'sync': 8, 'export': 9, 'import': 10, 'operation': 11}
        stages.sort(key=lambda s: order.get(s['type'], 11))
        
        return stages if stages else []

    # ──────────────────────────────────────────────
    # NEW: Critical path detection
    # ──────────────────────────────────────────────

    def infer_critical_paths(self) -> List[Dict]:
        """Detect critical business paths (黄金路径).
        
        Strategy:
        1. Find routes with state transitions (submit → approve → publish)
        2. Trace the full call chain for each critical route
        3. Score by: depth × entity_count × transition_count
        4. Classify into business domains
        
        Returns: [{path_name, domain, stages[], score, is_golden_path}]
        """
        paths = []
        
        # Build handler → layer map
        func_layer = {}
        for func in self.functions:
            if not isinstance(func, dict):
                continue
            fname = func.get('name', '')
            ffile = func.get('file', '')
            if not fname or not ffile:
                continue
            fl = ffile.lower()
            if any(kw in fl for kw in ['handler', 'router', 'controller']):
                layer = 'Handler'
            elif any(kw in fl for kw in ['service', 'manager', 'biz']):
                layer = 'Service'
            elif any(kw in fl for kw in ['dao', 'repo', 'repository']):
                layer = 'DAO'
            else:
                layer = 'Unknown'
            func_layer[fname] = layer
        
        # Detect golden paths: routes with create→review→publish lifecycle
        golden_patterns = [
            {
                'name': '创建→审核→发布',
                'verbs': [['create', 'add', 'build', 'new'], ['approve', 'review', 'audit'], ['publish', 'release', 'activate']],
                'domain': 'content_lifecycle',
                'cn_domain': '内容生命周期',
            },
            {
                'name': '创建→投放→监控',
                'verbs': [['create', 'add', 'build'], ['launch', 'start', 'deploy', 'bid'], ['monitor', 'track', 'report', 'stats']],
                'domain': 'campaign_lifecycle',
                'cn_domain': '投放生命周期',
            },
            {
                'name': '查询→分析→优化',
                'verbs': [['query', 'get', 'search', 'list'], ['analyze', 'report', 'stats'], ['optimize', 'adjust', 'tune']],
                'domain': 'optimization',
                'cn_domain': '优化流程',
            },
        ]
        
        # For each route, check if it matches any golden pattern
        for route in self.routes:
            if not isinstance(route, dict):
                continue
            handler = route.get('handler', '')
            path = route.get('path', '')
            method = route.get('method', 'GET')
            
            if not handler:
                continue
            
            # Extract verb from handler name
            handler_lower = handler.lower().split('.')[-1]
            
            for gp in golden_patterns:
                matched_verbs = []
                for verb_group in gp['verbs']:
                    if any(v in handler_lower for v in verb_group):
                        matched_verbs.append(verb_group[0])
                
                if len(matched_verbs) >= 2:  # At least 2 stages matched
                    # Build full call chain via BFS
                    layers = [f"HTTP {method}"]
                    visited = set()
                    queue = [(handler, 0)]
                    while queue:
                        fn, depth = queue.pop(0)
                        if fn in visited or depth > 4:
                            continue
                        visited.add(fn)
                        layer = func_layer.get(fn, 'Unknown')
                        if layer not in layers:
                            layers.append(layer)
                        for edge in self.call_graph:
                            if not isinstance(edge, dict):
                                continue
                            if edge.get('caller') == fn and edge.get('callee') not in visited:
                                queue.append((edge.get('callee'), depth + 1))
                    
                    # Count state transitions in related functions
                    transition_count = sum(
                        1 for fn in visited
                        if any(re.search(p, fn, re.IGNORECASE) 
                               for p in ['approve', 'reject', 'publish', 'submit', 'activate'])
                    )
                    
                    # Extract entities
                    entities = self._extract_entities_from_path(path)
                    
                    paths.append({
                        'path_name': f"{self._cn_resource(entities[0] if entities else 'resource')} {gp['name']}",
                        'domain': gp['domain'],
                        'cn_domain': gp['cn_domain'],
                        'entry_point': handler,
                        'route': path,
                        'stages': layers,
                        'call_chain': list(visited)[:15],
                        'matched_verbs': matched_verbs,
                        'transition_count': transition_count,
                        'entities': entities,
                        'is_golden_path': True,
                        'score': len(layers) * 20 + transition_count * 15 + len(entities) * 10,
                    })
                    break
        
        # Also detect high-traffic paths (most called functions)
        func_call_count = defaultdict(int)
        for edge in self.call_graph:
            if isinstance(edge, dict):
                callee = edge.get('callee', '')
                if callee:
                    func_call_count[callee] += 1
        
        for func, count in sorted(func_call_count.items(), key=lambda x: -x[1])[:5]:
            if not any(p['entry_point'] == func for p in paths):
                layers = [func_layer.get(func, 'Unknown')]
                paths.append({
                    'path_name': f"{func} (高频调用)",
                    'domain': 'high_traffic',
                    'cn_domain': '高频调用',
                    'entry_point': func,
                    'route': '',
                    'stages': layers,
                    'call_chain': [func],
                    'call_count': count,
                    'is_golden_path': False,
                    'score': count * 5,
                })
        
        paths.sort(key=lambda x: x['score'], reverse=True)
        return paths[:10]

    def classify_by_business_domain(self, flows: List[Dict]) -> Dict[str, List[Dict]]:
        """将 flows 按业务域分类。
        
        基于 route prefix + entity name 推断业务域：
        - creative/素材 → 素材管理域
        - adgroup/广告组 → 投放管理域  
        - campaign/广告计划 → 计划管理域
        - report/stats → 数据分析域
        - auth/user → 权限管理域
        """
        domain_map = {
            'creative': ('素材管理', 'content'),
            'adgroup': ('广告组管理', 'delivery'),
            'campaign': ('广告计划', 'delivery'),
            'account': ('账户管理', 'account'),
            'report': ('报表分析', 'analytics'),
            'stats': ('统计分析', 'analytics'),
            'user': ('用户管理', 'account'),
            'auth': ('鉴权管理', 'security'),
            'rbac': ('角色权限', 'security'),
            'budget': ('预算管理', 'delivery'),
            'bid': ('出价管理', 'delivery'),
            'targeting': ('定向管理', 'delivery'),
            'placement': ('广告位管理', 'delivery'),
        }
        
        classified = defaultdict(list)
        for flow in flows:
            domain_key = '通用流程'
            route = flow.get('route', '') or flow.get('path', '')
            entities = flow.get('entities', [])
            call_chain = flow.get('call_chain', []) + flow.get('handlers', [])
            
            combined_text = ' '.join([route] + entities + call_chain).lower()
            
            for keyword, (cn_name, domain_id) in domain_map.items():
                if keyword in combined_text:
                    domain_key = cn_name
                    break
            
            classified[domain_key].append(flow)
        
        # Sort within each domain by score
        for domain in classified:
            classified[domain].sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return dict(classified)

    # ──────────────────────────────────────────────
    # NEW: Entity-to-route mapping
    # ──────────────────────────────────────────────

    def map_entity_to_routes(self) -> List[Dict]:
        """建立 entity → route 映射关系。
        
        对于每个 entity_table，找到所有涉及该实体的路由和函数。
        帮助 PRD 审查时判断"PRD 提到的实体是否有对应的代码实现"。
        """
        mappings = []
        
        for et in self.entity_tables:
            if not isinstance(et, dict):
                continue
            entity = et.get('entity', '')
            table = et.get('table', '')
            if not entity:
                continue
            
            # Find routes that reference this entity
            matching_routes = []
            for route in self.routes:
                if not isinstance(route, dict):
                    continue
                path = route.get('path', '')
                handler = route.get('handler', '')
                if entity.lower() in path.lower() or entity.lower() in handler.lower():
                    matching_routes.append({
                        'method': route.get('method', ''),
                        'path': path,
                        'handler': handler,
                    })
            
            # Find functions that operate on this entity
            matching_funcs = []
            for func in self.functions:
                if not isinstance(func, dict):
                    continue
                fname = func.get('name', '')
                if entity.lower() in fname.lower():
                    matching_funcs.append({
                        'name': fname,
                        'file': func.get('file', ''),
                    })
            
            # Count read/write operations
            ops = et.get('operations', [])
            read_ops = sum(1 for o in ops if o in ['SELECT', 'Get', 'Query', 'List', 'Find'])
            write_ops = sum(1 for o in ops if o in ['INSERT', 'UPDATE', 'DELETE', 'Create', 'Modify', 'Remove'])
            
            mappings.append({
                'entity': entity,
                'table': table,
                'routes': matching_routes[:10],
                'functions': matching_funcs[:10],
                'read_operations': read_ops,
                'write_operations': write_ops,
                'has_route_coverage': len(matching_routes) > 0,
                'score': len(matching_routes) * 10 + len(matching_funcs) * 5,
            })
        
        mappings.sort(key=lambda x: x['score'], reverse=True)
        return mappings[:20]

    # ──────────────────────────────────────────────
    # NEW: Dynamic golden path inference (replaces hardcoded patterns)
    # ──────────────────────────────────────────────

    def _infer_dynamic_lifecycle_patterns(self) -> List[Dict]:
        """动态推断生命周期模式，替代硬编码的 golden_patterns。
        
        Strategy:
        1. 从函数名中检测状态转换动词（approve/reject/publish/submit 等）
        2. 按实体分组，找出每个实体的完整生命周期
        3. 自动构建 create→transition→publish 路径
        
        Returns: [{name, verbs[], domain, cn_domain, confidence}]
        """
        # Collect all state transition functions
        transition_funcs = []
        for func in self.functions:
            if not isinstance(func, dict):
                continue
            fname = func.get('name', '')
            if not fname:
                continue
            fname_lower = fname.lower()
            
            # Check for state transition patterns
            for pattern in ['approve', 'reject', 'publish', 'submit', 'activate', 
                           'deactivate', 'pause', 'resume', 'transition', 'status']:
                if pattern in fname_lower:
                    transition_funcs.append(fname)
                    break
        
        if not transition_funcs:
            return []
        
        # Group transitions by entity (from struct names or route paths)
        entity_transitions = defaultdict(list)
        for func_name in transition_funcs:
            # Try to find which entity this function belongs to
            for edge in self.call_graph:
                if not isinstance(edge, dict):
                    continue
                caller = edge.get('caller', '')
                callee = edge.get('callee', '')
                if callee == func_name:
                    # Extract entity from caller name
                    parts = caller.split('.')
                    if len(parts) > 1:
                        entity_key = parts[-2].lower()
                        entity_transitions[entity_key].append(func_name)
                    break
        
        # Build lifecycle patterns for each entity
        patterns = []
        for entity, funcs in entity_transitions.items():
            if len(funcs) < 2:
                continue
            
            # Detect lifecycle stages
            has_create = any('create' in f or 'add' in f or 'build' in f for f in funcs)
            has_approve = any('approve' in f or 'review' in f or 'audit' in f for f in funcs)
            has_publish = any('publish' in f or 'release' in f or 'activate' in f for f in funcs)
            has_delete = any('delete' in f or 'remove' in f for f in funcs)
            
            lifecycle_stages = []
            if has_create:
                lifecycle_stages.append('create')
            if has_approve:
                lifecycle_stages.append('approve')
            if has_publish:
                lifecycle_stages.append('publish')
            if has_delete:
                lifecycle_stages.append('delete')
            
            if len(lifecycle_stages) >= 2:
                stage_names = {'create': '创建', 'approve': '审核', 'publish': '发布', 'delete': '删除'}
                cn_name = '→'.join(stage_names.get(s, str(s)) for s in lifecycle_stages)
                
                patterns.append({
                    'name': cn_name,
                    'verbs': lifecycle_stages,
                    'entities': [entity],
                    'functions': funcs[:10],
                    'stage_count': len(lifecycle_stages),
                    'confidence': min(1.0, len(lifecycle_stages) / 4.0),
                })
        
        return patterns

    def infer_critical_paths_enhanced(self) -> List[Dict]:
        """增强的黄金路径检测 — 结合动态生命周期模式和硬编码模式。
        
        改进:
        1. 动态推断生命周期模式（替代完全硬编码）
        2. 合并动态模式和预定义模式
        3. 更精确的评分（考虑实体覆盖度、调用深度、状态转换数）
        """
        paths = []
        
        # Build handler → layer map
        func_layer = {}
        for func in self.functions:
            if not isinstance(func, dict):
                continue
            fname = func.get('name', '')
            ffile = func.get('file', '')
            if not fname or not ffile:
                continue
            fl = ffile.lower()
            if any(kw in fl for kw in ['handler', 'router', 'controller']):
                layer = 'Handler'
            elif any(kw in fl for kw in ['service', 'manager', 'biz']):
                layer = 'Service'
            elif any(kw in fl for kw in ['dao', 'repo', 'repository']):
                layer = 'DAO'
            else:
                layer = 'Unknown'
            func_layer[fname] = layer
        
        # Get dynamically inferred lifecycle patterns
        dynamic_patterns = self._infer_dynamic_lifecycle_patterns()
        
        # Keep original hardcoded patterns as fallback
        golden_patterns = [
            {
                'name': '创建→审核→发布',
                'verbs': [['create', 'add', 'build', 'new'], ['approve', 'review', 'audit'], ['publish', 'release', 'activate']],
                'domain': 'content_lifecycle',
                'cn_domain': '内容生命周期',
            },
            {
                'name': '创建→投放→监控',
                'verbs': [['create', 'add', 'build'], ['launch', 'start', 'deploy', 'bid'], ['monitor', 'track', 'report', 'stats']],
                'domain': 'campaign_lifecycle',
                'cn_domain': '投放生命周期',
            },
            {
                'name': '查询→分析→优化',
                'verbs': [['query', 'get', 'search', 'list'], ['analyze', 'report', 'stats'], ['optimize', 'adjust', 'tune']],
                'domain': 'optimization',
                'cn_domain': '优化流程',
            },
        ]
        
        # Combine dynamic and hardcoded patterns
        all_patterns = dynamic_patterns + [{'dynamic': False, 'name': p['name'], 'verbs': p['verbs'],
                                            'domain': p['domain'], 'cn_domain': p['cn_domain']}
                                           for p in golden_patterns]
        
        # For each route, check if it matches any pattern
        matched_handlers = set()
        for route in self.routes:
            if not isinstance(route, dict):
                continue
            handler = route.get('handler', '')
            path = route.get('path', '')
            method = route.get('method', 'GET')
            
            if not handler:
                continue
            
            handler_lower = handler.lower().split('.')[-1]
            
            for gp in all_patterns:
                if not isinstance(gp, dict):
                    continue
                    
                verb_groups = gp.get('verbs', [])
                matched_verbs = []
                for verb_group in verb_groups:
                    if any(v in handler_lower for v in verb_group):
                        matched_verbs.append(verb_group[0])
                
                if len(matched_verbs) >= 2 and handler not in matched_handlers:
                    # Build full call chain via BFS
                    layers = [f"HTTP {method}"]
                    visited = set()
                    queue = [(handler, 0)]
                    while queue:
                        fn, depth = queue.pop(0)
                        if fn in visited or depth > 4:
                            continue
                        visited.add(fn)
                        layer = func_layer.get(fn, 'Unknown')
                        if layer not in layers:
                            layers.append(layer)
                        for edge in self.call_graph:
                            if not isinstance(edge, dict):
                                continue
                            if edge.get('caller') == fn and edge.get('callee') not in visited:
                                queue.append((edge.get('callee'), depth + 1))
                    
                    # Count state transitions
                    transition_count = sum(
                        1 for fn in visited
                        if any(re.search(p, fn, re.IGNORECASE) 
                               for p in ['approve', 'reject', 'publish', 'submit', 'activate'])
                    )
                    
                    # Extract entities
                    entities = self._extract_entities_from_path(path)
                    
                    # Calculate score with enhanced factors
                    base_score = len(layers) * 20 + transition_count * 15 + len(entities) * 10
                    # Bonus for dynamic patterns (higher confidence)
                    bonus = 10 if gp.get('dynamic', True) else 0
                    # Bonus for deeper call chains
                    depth_bonus = max(0, len(layers) - 3) * 5
                    
                    matched_handlers.add(handler)
                    paths.append({
                        'path_name': f"{self._cn_resource(entities[0] if entities else 'resource')} {gp.get('name', 'lifecycle')}",
                        'domain': gp.get('domain', 'unknown'),
                        'cn_domain': gp.get('cn_domain', gp.get('name', '')),
                        'entry_point': handler,
                        'route': path,
                        'stages': layers,
                        'call_chain': list(visited)[:15],
                        'matched_verbs': matched_verbs,
                        'transition_count': transition_count,
                        'entities': entities,
                        'is_golden_path': True,
                        'score': base_score + bonus + depth_bonus,
                        'confidence': gp.get('confidence', 0.7) if 'confidence' in gp else 0.5,
                    })
                    break
        
        # Also detect high-traffic paths
        func_call_count = defaultdict(int)
        for edge in self.call_graph:
            if isinstance(edge, dict):
                callee = edge.get('callee', '')
                if callee:
                    func_call_count[callee] += 1
        
        for func, count in sorted(func_call_count.items(), key=lambda x: -x[1])[:5]:
            if not any(p['entry_point'] == func for p in paths):
                layers = [func_layer.get(func, 'Unknown')]
                paths.append({
                    'path_name': f"{func} (高频调用)",
                    'domain': 'high_traffic',
                    'cn_domain': '高频调用',
                    'entry_point': func,
                    'route': '',
                    'stages': layers,
                    'call_chain': [func],
                    'call_count': count,
                    'is_golden_path': False,
                    'score': count * 5,
                    'confidence': 0.3,
                })
        
        paths.sort(key=lambda x: x['score'], reverse=True)
        return paths[:10]

    # ──────────────────────────────────────────────
    # NEW: Flow coverage analysis
    # ──────────────────────────────────────────────

    def analyze_flow_coverage(self) -> Dict[str, Any]:
        """分析流程覆盖率 — 检测哪些业务流程有/没有代码实现。
        
        Strategy:
        1. 从 entity_tables 提取所有实体
        2. 对每个实体，检查是否有对应的路由和函数
        3. 标记未覆盖的实体（可能是新需求或遗漏）
        
        Returns: {covered_entities, uncovered_entities, coverage_rate, missing_operations}
        """
        covered = []
        uncovered = []
        missing_ops = []
        
        for et in self.entity_tables:
            if not isinstance(et, dict):
                continue
            entity = et.get('entity', '')
            if not entity:
                continue
            
            # Check if there are routes covering this entity
            has_routes = False
            for route in self.routes:
                if not isinstance(route, dict):
                    continue
                path = route.get('path', '')
                handler = route.get('handler', '')
                if entity.lower() in path.lower() or entity.lower() in handler.lower():
                    has_routes = True
                    break
            
            # Check if there are functions operating on this entity
            has_functions = False
            for func in self.functions:
                if not isinstance(func, dict):
                    continue
                fname = func.get('name', '')
                if entity.lower() in fname.lower():
                    has_functions = True
                    break
            
            if has_routes and has_functions:
                covered.append(entity)
            elif not has_routes:
                uncovered.append({
                    'entity': entity,
                    'missing': 'routes',
                    'table': et.get('table', ''),
                    'operations': et.get('operations', []),
                })
                missing_ops.append({
                    'entity': entity,
                    'operation': 'CRUD routes',
                    'severity': 'high',
                })
            elif not has_functions:
                uncovered.append({
                    'entity': entity,
                    'missing': 'functions',
                    'table': et.get('table', ''),
                    'operations': et.get('operations', []),
                })
                missing_ops.append({
                    'entity': entity,
                    'operation': 'service functions',
                    'severity': 'medium',
                })
        
        total = len(covered) + len(uncovered)
        coverage_rate = len(covered) / total if total > 0 else 0.0
        
        return {
            'covered_entities': covered,
            'uncovered_entities': uncovered,
            'coverage_rate': round(coverage_rate, 2),
            'missing_operations': missing_ops[:20],
            'total_entities': total,
        }

    # ──────────────────────────────────────────────
    # NEW: PRD flow alignment
    # ──────────────────────────────────────────────

    def align_prd_flows(self, prd_keywords: List[str]) -> Dict[str, Any]:
        """PRD 流程对齐分析 — 检查 PRD 提到的流程是否在代码中有对应实现。
        
        Strategy:
        1. 从 PRD keywords 中提取实体名和操作名
        2. 在代码中查找对应的路由、函数、状态转换
        3. 标记匹配、部分匹配和未匹配的项
        
        Args:
            prd_keywords: PRD 中的关键词列表（如 ['素材创建', '审核通过', '批量发布']）
        
        Returns: {matched, partial, unmatched, alignment_score}
        """
        matched = []
        partial = []
        unmatched = []
        
        # Build lookup maps
        route_map = {}
        for route in self.routes:
            if not isinstance(route, dict):
                continue
            handler = route.get('handler', '')
            path = route.get('path', '')
            if handler:
                route_map[handler.lower()] = {'path': path, 'method': route.get('method', '')}
        
        func_map = {}
        for func in self.functions:
            if not isinstance(func, dict):
                continue
            fname = func.get('name', '')
            if fname:
                func_map[fname.lower()] = func
        
        for keyword in prd_keywords:
            keyword_lower = keyword.lower()
            found_exact = False
            found_partial = False
            
            # Check exact match in handlers
            for handler in route_map:
                if keyword_lower in handler or handler in keyword_lower:
                    matched.append({
                        'keyword': keyword,
                        'type': 'route',
                        'detail': route_map[handler],
                        'match_type': 'exact',
                    })
                    found_exact = True
                    break
            
            if not found_exact:
                # Check in function names
                for func_name in func_map:
                    if keyword_lower in func_name or func_name in keyword_lower:
                        matched.append({
                            'keyword': keyword,
                            'type': 'function',
                            'detail': func_map[func_name],
                            'match_type': 'exact',
                        })
                        found_exact = True
                        break
            
            if not found_exact:
                # Check partial match (entity name only)
                for et in self.entity_tables:
                    if not isinstance(et, dict):
                        continue
                    entity = et.get('entity', '')
                    if entity.lower() in keyword_lower or keyword_lower in entity.lower():
                        partial.append({
                            'keyword': keyword,
                            'type': 'entity',
                            'detail': {'entity': entity, 'table': et.get('table', '')},
                            'match_type': 'partial',
                        })
                        found_partial = True
                        break
            
            if not found_exact and not found_partial:
                unmatched.append({
                    'keyword': keyword,
                    'reason': 'no_matching_code',
                })
        
        total = len(matched) + len(partial) + len(unmatched)
        alignment_score = (len(matched) * 1.0 + len(partial) * 0.5) / total if total > 0 else 0.0
        
        return {
            'matched': matched,
            'partial': partial,
            'unmatched': unmatched,
            'alignment_score': round(alignment_score, 2),
            'total_keywords': total,
        }

    # ──────────────────────────────────────────────
    # NEW: Enhanced data flow with DAO method tracking
    # ──────────────────────────────────────────────

    def infer_data_flows_enhanced(self) -> List[Dict]:
        """增强的数据流推断 — 追踪到 DAO 方法级别。
        
        改进:
        1. 从 handler 追踪到具体的 DAO 方法（不只是层）
        2. 识别读写操作
        3. 检测缓存使用
        4. 识别事务边界
        """
        flows = []
        
        # Build detailed function map
        func_details = {}
        for func in self.functions:
            if not isinstance(func, dict):
                continue
            fname = func.get('name', '')
            ffile = func.get('file', '')
            if not fname or not ffile:
                continue
            
            fl = ffile.lower()
            if any(kw in fl for kw in ['handler', 'router', 'controller']):
                layer = 'Handler'
            elif any(kw in fl for kw in ['service', 'manager', 'biz']):
                layer = 'Service'
            elif any(kw in fl for kw in ['dao', 'repo', 'repository']):
                layer = 'DAO'
            elif any(kw in fl for kw in ['middleware', 'auth', 'intercept']):
                layer = 'Middleware'
            else:
                layer = 'Unknown'
            
            func_details[fname] = {'layer': layer, 'file': ffile}
        
        # For each route, trace full data flow
        for route in self.routes:
            if not isinstance(route, dict):
                continue
            
            handler = route.get('handler', '')
            path = route.get('path', '')
            method = route.get('method', 'GET')
            
            if not handler:
                continue
            
            entities = self._extract_entities_from_path(path)
            
            # Build layer chain
            layers = [f"HTTP {method}"]
            visited = set()
            dao_methods = []  # Track specific DAO methods called
            cache_usage = []  # Track cache operations
            
            queue = [(handler, 0)]
            while queue:
                fn, depth = queue.pop(0)
                if fn in visited or depth > 4:
                    continue
                visited.add(fn)
                
                detail = func_details.get(fn, {})
                layer = detail.get('layer', 'Unknown')
                if layer not in layers:
                    layers.append(layer)
                
                # Detect DAO methods
                if layer == 'DAO':
                    dao_methods.append(fn)
                
                # Detect cache usage
                if any(kw in fn.lower() for kw in ['cache', 'redis', 'get_cache', 'set_cache']):
                    cache_usage.append(fn)
                
                # Find callees
                for edge in self.call_graph:
                    if not isinstance(edge, dict):
                        continue
                    if edge.get('caller') == fn and edge.get('callee') not in visited:
                        queue.append((edge.get('callee'), depth + 1))
            
            # Add data storage layer
            if entities:
                layers.append('DB/Cache')
            
            # Detect transaction boundaries
            has_transaction = any('tx' in fn.lower() or 'transaction' in fn.lower() 
                                 for fn in visited)
            
            if len(layers) >= 3:
                flows.append({
                    'flow_name': f"{path} 数据流",
                    'entry_point': handler,
                    'route': path,
                    'http_method': method,
                    'layers': layers,
                    'entities': entities,
                    'dao_methods': dao_methods[:10],
                    'cache_usage': cache_usage[:5],
                    'has_transaction': has_transaction,
                    'depth': len(layers) - 1,
                    'call_chain': list(visited)[:15],
                    'score': len(layers) * 15 + len(entities) * 10 + len(dao_methods) * 5,
                })
        
        flows.sort(key=lambda x: x['score'], reverse=True)
        return flows[:20]

    # ──────────────────────────────────────────────
    # NEW: Unified analysis entry point
    # ──────────────────────────────────────────────

    def analyze_all(self) -> Dict[str, Any]:
        """Run all flow inference strategies and return a unified result.

        This is the single entry point for getting ALL flow analysis data.
        Called from learn_repo.py to populate the enhanced IR fields.

        Returns:
            {
                'flows': [...],                    # Combined flows from all strategies
                'critical_paths': [...],           # Golden paths (create→review→publish)
                'data_flows': [...],               # Route→Handler→Service→DAO→DB chains
                'service_topology': {...},         # Service groups + cross-service deps
                'entity_ownership': [...],         # Entity → operations → routes mapping
                'business_processes': [...],       # Clustered lifecycle processes
                'entity_route_map': [...],         # Entity → route mapping
                'domain_classified': {...},        # Flows grouped by business domain
                'flow_coverage': {...},            # NEW: Flow coverage analysis
                'prd_alignment': {...},            # NEW: PRD flow alignment (requires prd_keywords)
                'data_flows_enhanced': [...],      # NEW: Enhanced data flow with DAO tracking
                '_timing': {...},                  # Diagnostic: time taken per strategy
            }
        """
        import time as _time
        start = _time.time()
        result = {}

        # Run infer_flows() once and reuse for both 'flows' and 'domain_classified'
        flows = self.infer_flows()
        result['flows'] = flows

        strategies = [
            ('critical_paths', lambda: self.infer_critical_paths_enhanced()),
            ('data_flows', lambda: self.infer_data_flows_enhanced()),
            ('service_topology', lambda: self.infer_service_topology()),
            ('entity_ownership', lambda: self.analyze_entity_ownership()),
            ('business_processes', lambda: self.cluster_business_processes()),
            ('entity_route_map', lambda: self.map_entity_to_routes()),
            ('domain_classified', lambda: self.classify_by_business_domain(flows)),
            ('flow_coverage', lambda: self.analyze_flow_coverage()),
        ]
        
        timing = {}
        for name, fn in strategies:
            t0 = _time.time()
            try:
                result[name] = fn()
            except Exception as e:
                result[name] = []
                print(f"⚠️  CoreFlowAnalyzer.{name} failed: {e}")
            timing[f'{name}_ms'] = round((_time.time() - t0) * 1000, 1)
        
        result['_timing'] = timing
        result['_total_ms'] = round((_time.time() - start) * 1000, 1)
        
        return result

    def align_with_prd(self, prd_keywords: List[str]) -> Dict[str, Any]:
        """PRD 流程对齐分析 — 独立入口方法。
        
        Args:
            prd_keywords: PRD 中的关键词列表
        
        Returns: Alignment analysis result
        """
        return self.align_prd_flows(prd_keywords)
