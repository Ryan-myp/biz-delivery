#!/usr/bin/env python3
"""Mermaid diagram generator — creates actual mermaid code from IR data + flow analysis.

Generates:
1. Architecture diagram (graph TB) from packages + call_graph
2. Data model diagram (erDiagram) from entity_tables
3. Deployment diagram (graph LR) from service_topology
4. Sequence diagram from core_flows
5. **Business flow diagram** from cross-repo flow analysis traces
6. **State machine diagram** from pattern detection results
7. **Activity diagram** from Go function call chains
8. **Cross-service data flow** from cross_repo_flow analysis
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class MermaidGenerator:
    """Generate mermaid diagrams from IR data + flow analysis results."""

    def __init__(self, ir_data: Dict[str, Any], flow_data: Optional[Dict] = None):
        self.ir = ir_data
        self.flow = flow_data if flow_data else {}
        self.packages = ir_data.get('packages', {})
        self.call_graph = ir_data.get('call_graph', [])
        self.entity_tables = ir_data.get('entity_tables', [])
        self.routes = ir_data.get('routes', [])
        self.functions = ir_data.get('functions', [])
        self.services = ir_data.get('services', [])
        self.core_flows = ir_data.get('core_flows', [])
        self.structs = ir_data.get('structs', [])
        self.sql_operations = ir_data.get('sql_operations', [])
        self.error_codes = ir_data.get('error_codes', [])
        self.auth_models = ir_data.get('auth_models', [])
        self.configs = ir_data.get('configs', [])
        # Flow analysis data
        self.spex_traces = self.flow.get('spex_traces', {})
        self.go_flows = self.flow.get('go_flows', {})
        self.patterns = self.flow.get('patterns', {})
        self.cross_repo = self.flow.get('cross_repo', {})
        self.entry_points = self.flow.get('entry_points', [])
    
    def generate_architecture_diagram(self) -> str:
        """Generate architecture diagram from actual package structure."""
        lines = ["```mermaid", "graph TB"]
        
        # Group packages by layer
        handler_pkgs = []
        service_pkgs = []
        dao_pkgs = []
        other_pkgs = []
        
        for pkg_name, pkg_data in self.packages.items():
            pkg_lower = pkg_name.lower()
            if 'handler' in pkg_lower or 'router' in pkg_lower or 'controller' in pkg_lower:
                handler_pkgs.append(pkg_name)
            elif 'service' in pkg_lower:
                service_pkgs.append(pkg_name)
            elif 'dao' in pkg_lower or 'repo' in pkg_lower or 'model' in pkg_lower:
                dao_pkgs.append(pkg_name)
            else:
                other_pkgs.append(pkg_name)
        
        # Frontend layer
        lines.append("    subgraph Frontend[🌐 前端层]")
        lines.append("        Web[Web App]")
        lines.append("        Mobile[Mobile App]")
        lines.append("    end")
        
        # Gateway layer
        lines.append("    subgraph Gateway[🔀 网关层]")
        lines.append("        LB[Load Balancer]")
        lines.append("        GW[API Gateway]")
        if self.auth_models:
            auth_names = [m.get('middleware', 'Auth') if isinstance(m, dict) else str(m) for m in self.auth_models[:3]]
            lines.append(f"        Auth[{', '.join(auth_names)}]")
        else:
            lines.append("        Auth[Auth Middleware]")
        lines.append("    end")
        
        # Business layer
        if handler_pkgs or service_pkgs or dao_pkgs:
            lines.append("    subgraph Business[💼 业务层]")
            
            if handler_pkgs:
                lines.append("        subgraph Handlers[Handlers]")
                for pkg in handler_pkgs[:5]:
                    safe_id = pkg.replace('-', '_').replace('.', '_')
                    lines.append(f"            H_{safe_id}[{pkg}]")
                lines.append("        end")
            
            if service_pkgs:
                lines.append("        subgraph Services[Services]")
                for pkg in service_pkgs[:5]:
                    safe_id = pkg.replace('-', '_').replace('.', '_')
                    lines.append(f"            S_{safe_id}[{pkg}]")
                lines.append("        end")
            
            if dao_pkgs:
                lines.append("        subgraph Repositories[Repositories]")
                for pkg in dao_pkgs[:5]:
                    safe_id = pkg.replace('-', '_').replace('.', '_')
                    lines.append(f"            D_{safe_id}[{pkg}]")
                lines.append("        end")
            
            lines.append("    end")
        else:
            lines.append("    subgraph Business[💼 业务层]")
            lines.append("        Handler[Handler Layer]")
            lines.append("        Service[Service Layer]")
            lines.append("        DAO[DAO Layer]")
            lines.append("    end")
        
        # Data layer
        lines.append("    subgraph Data[🗄️ 数据层]")
        lines.append("        MySQL[(MySQL)]")
        lines.append("        Redis[(Redis)]")
        if any('kafka' in str(c).lower() or 'mq' in str(c).lower() for c in self.configs):
            lines.append("        Kafka[(Kafka)]")
        else:
            lines.append("        MQ[(Message Queue)]")
        lines.append("    end")
        
        # External services
        external_services = set()
        for edge in self.call_graph:
            if isinstance(edge, dict):
                callee = edge.get('callee', '')
                if 'external' in callee.lower() or 'rpc' in callee.lower():
                    external_services.add(callee)
        
        if external_services or self.routes:
            lines.append("    subgraph External[🔗 外部服务]")
            for svc in list(external_services)[:5]:
                safe_id = svc.replace('-', '_').replace('.', '_')
                lines.append(f"        Ext_{safe_id}[{svc}]")
            lines.append("    end")
        
        # Connections
        lines.append("")
        lines.append("    Web --> LB")
        lines.append("    Mobile --> LB")
        lines.append("    LB --> GW")
        lines.append("    GW --> Auth")
        lines.append("    Auth --> Handler")
        lines.append("    Handler --> Service")
        lines.append("    Service --> DAO")
        lines.append("    Service --> Redis")
        lines.append("    Service --> MySQL")
        
        # Add call graph edges
        for edge in self.call_graph[:15]:
            if isinstance(edge, dict):
                caller = edge.get('caller', '')
                callee = edge.get('callee', '')
                if caller and callee and len(caller) < 30 and len(callee) < 30:
                    caller_safe = caller.replace('-', '_').replace('.', '_')
                    callee_safe = callee.replace('-', '_').replace('.', '_')
                    lines.append(f"    {caller_safe} --> {callee_safe}")
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_data_model_diagram(self) -> str:
        """Generate ER diagram from entity_tables."""
        lines = ["```mermaid", "erDiagram"]
        
        for et in self.entity_tables[:20]:
            entity = et.get('entity', '')
            table = et.get('table', '')
            if not entity or not table:
                continue
            
            # Get fields for this entity
            fields = et.get('fields', [])
            
            lines.append(f'    {entity} {{')
            for field in fields[:10]:
                if isinstance(field, dict):
                    fname = field.get('name', '')
                    ftype = field.get('type', 'varchar')
                    fcomment = field.get('comment', '')
                    if fname:
                        lines.append(f'        {ftype} {fname} "{fcomment}"')
                elif isinstance(field, str):
                    lines.append(f'        varchar {field}')
            lines.append('    }')
        
        # Add relationships from conditions
        for cond in self.entity_tables:
            if isinstance(cond, dict) and 'relation' in cond:
                rel = cond.get('relation', '')
                from_entity = cond.get('from_entity', '')
                to_entity = cond.get('to_entity', '')
                if rel and from_entity and to_entity:
                    lines.append(f'    {from_entity} {rel} {to_entity}')
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_deployment_diagram(self) -> str:
        """Generate deployment diagram from service topology."""
        lines = ["```mermaid", "graph LR"]
        
        # Define environments
        lines.append("    subgraph CDN[🌍 CDN/DNS]")
        lines.append("        DNS[DNS Resolver]")
        lines.append("        CDN_Node[CDN Edge Node]")
        lines.append("    end")
        
        lines.append("    subgraph Ingress[⚡ Ingress]")
        lines.append("        LB[Load Balancer]")
        lines.append("        WAF[WAF]")
        lines.append("    end")
        
        # Application servers
        app_servers = []
        for pkg_name, pkg_data in self.packages.items():
            if 'handler' in pkg_name.lower() or 'server' in pkg_name.lower():
                app_servers.append(pkg_name)
        
        lines.append("    subgraph AppCluster[🖥️ 应用集群]")
        for i, server in enumerate(app_servers[:3]):
            lines.append(f"        App{i+1}[{server}]")
        if not app_servers:
            lines.append("        App1[App Server 1]")
            lines.append("        App2[App Server 2]")
        lines.append("    end")
        
        # Infrastructure
        lines.append("    subgraph Infra[🏗️ 基础设施]")
        lines.append("        MySQL[(MySQL Cluster)]")
        lines.append("        Redis[(Redis Cluster)]")
        lines.append("        Kafka[(Kafka Cluster)]")
        lines.append("        Etcd[(Etcd/Config)]")
        lines.append("    end")
        
        # Observability
        lines.append("    subgraph Observability[📊 可观测性]")
        lines.append("        Prometheus[Prometheus]")
        lines.append("        Grafana[Grafana]")
        lines.append("        ELK[ELK Stack]")
        lines.append("    end")
        
        # Connections
        lines.append("")
        lines.append("    DNS --> CDN_Node")
        lines.append("    CDN_Node --> LB")
        lines.append("    LB --> WAF")
        lines.append("    WAF --> App1")
        lines.append("    WAF --> App2")
        lines.append("    App1 --> MySQL")
        lines.append("    App1 --> Redis")
        lines.append("    App1 --> Kafka")
        lines.append("    App2 --> MySQL")
        lines.append("    App2 --> Redis")
        lines.append("    App2 --> Kafka")
        lines.append("    App1 --> Prometheus")
        lines.append("    App2 --> Prometheus")
        lines.append("    Prometheus --> Grafana")
        lines.append("    App1 --> ELK")
        lines.append("    App2 --> ELK")
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_sequence_diagram(self, flow: Optional[Dict] = None) -> str:
        """Generate sequence diagram from a core flow or business logic entry."""
        lines = ["```mermaid", "sequenceDiagram"]
        
        if flow:
            entry = flow.get('entry_point', 'Client')
            call_chain = flow.get('call_chain', [])
            data_flow = flow.get('data_flow', '')
            
            # Participants
            participants = set()
            participants.add('Client')
            for step in call_chain[:10]:
                step_lower = step.lower()
                if 'service' in step_lower or 'manager' in step_lower:
                    participants.add('Service')
                elif 'dao' in step_lower or 'repo' in step_lower or 'model' in step_lower:
                    participants.add('DAO')
                elif 'cache' in step_lower or 'redis' in step_lower:
                    participants.add('Cache')
                elif 'mq' in step_lower or 'kafka' in step_lower:
                    participants.add('MQ')
                elif 'rpc' in step_lower or 'client' in step_lower or 'proxy' in step_lower:
                    participants.add('External')
                else:
                    participants.add(step[:20])
            
            for p in sorted(participants):
                lines.append(f"    participant {p}")
            
            # Flow
            if data_flow:
                stages = data_flow.split(' → ') if ' → ' in data_flow else [data_flow]
            else:
                stages = ['Request', 'Handler', 'Service', 'DAO', 'DB']
            
            prev = 'Client'
            for i, stage in enumerate(stages[:8]):
                stage_clean = stage.strip()[:20]
                if i % 2 == 0:
                    lines.append(f"    Client->>{stage_clean}: 请求")
                    if i + 1 < len(stages):
                        next_stage = stages[i+1].strip()[:20]
                        lines.append(f"    {stage_clean}-->>{next_stage}: 转发")
                else:
                    prev_stage = stages[i-1].strip()[:20] if i > 0 else 'Client'
                    lines.append(f"    {prev_stage}-->>{stage_clean}: 响应")
            
            # Add external calls
            for step in call_chain[:5]:
                if 'rpc' in step.lower() or 'external' in step.lower():
                    lines.append(f"    Service->>External: {step}")
                    lines.append(f"    External-->>Service: 响应")
        
        else:
            # Default sequence diagram
            lines.append("    participant Client")
            lines.append("    participant Gateway")
            lines.append("    participant Handler")
            lines.append("    participant Service")
            lines.append("    participant DAO")
            lines.append("    participant DB")
            lines.append("")
            lines.append("    Client->>Gateway: HTTP Request")
            lines.append("    Gateway->>Handler: 路由分发")
            lines.append("    Handler->>Service: 业务逻辑")
            lines.append("    Service->>DAO: 数据访问")
            lines.append("    DAO->>DB: SQL 查询")
            lines.append("    DB-->>DAO: 结果")
            lines.append("    DAO-->>Service: 数据")
            lines.append("    Service-->>Handler: 业务结果")
            lines.append("    Handler-->>Gateway: HTTP Response")
            lines.append("    Gateway-->>Client: 响应数据")
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_all_diagrams(self) -> Dict[str, str]:
        """Generate all diagrams and return as dict."""
        result = {
            'architecture': self.generate_architecture_diagram(),
            'data_model': self.generate_data_model_diagram(),
            'deployment': self.generate_deployment_diagram(),
            'sequence': self.generate_sequence_diagram(),
            'activity': self.generate_activity_diagram(),
            'state_machine': self.generate_state_machine_diagram(),
            'dependency': self.generate_dependency_diagram(),
            'api_flow': self.generate_api_flow_diagram(),
            'error_code_matrix': self.generate_error_code_matrix_diagram(),
        }
        # Add flow-analysis-specific diagrams if data available
        if self.spex_traces or self.cross_repo or self.go_flows:
            result['business_flow'] = self.generate_business_flow_diagram()
            result['cross_service_flow'] = self.generate_cross_service_flow_diagram()
        if self.patterns:
            result['state_machine_detailed'] = self.generate_detailed_state_machine()
            result['task_lifecycle'] = self.generate_task_lifecycle_diagram()
        return result
    
    def generate_activity_diagram(self) -> str:
        """Generate activity diagram from core flows or business logic.
        
        Shows business process flow with decision points, parallel branches,
        and alternative paths based on core flow analysis results.
        """
        if self.core_flows:
            return self._build_activity_from_flows()
        
        # Fallback: build generic activity diagram from available data
        lines = ["```mermaid", "activityDiagram"]
        lines.append("")
        lines.append("* --> Init")
        lines.append("Init --> Validate: 参数验证")
        lines.append("Validate --> CheckAuth: 权限校验")
        lines.append("CheckAuth --> ServiceCall: 执行业务逻辑")
        lines.append("ServiceCall --> SaveData: 数据持久化")
        lines.append("SaveData --> Notify: 发送通知")
        lines.append("Notify --> Response: 返回响应")
        lines.append("Response --> End")
        lines.append("End --> *")
        lines.append("")
        lines.append("```")
        return "\n".join(lines)
    
    def _build_activity_from_flows(self) -> str:
        """Build activity diagram from core flow analysis data."""
        lines = ["```mermaid", "activityDiagram"]
        lines.append("")
        lines.append("* --> RequestReceived")
        
        # Add common steps from core flows
        flows = self.core_flows[:5]  # Top 5 flows
        all_steps = set()
        
        for flow in flows:
            for step in flow.get('steps', []):
                all_steps.add(step)
        
        # Build flow with decision points
        step_list = list(all_steps)
        
        if not step_list:
            lines.append("    RequestProcessing --> Completed")
            lines.append("    Completed --> *")
        else:
            current = "RequestReceived"
            for i, step in enumerate(step_list[:8]):
                next_step = step_list[i+1] if i+1 < len(step_list) else "Completed"
                lines.append(f"    {current} --> {step}: {step}")
                
                # Add decision point for certain keywords
                if any(kw in step.lower() for kw in ['审核', '检查', '判断', 'if', 'condition']):
                    lines.append(f"    {step} --> Decision: 结果？")
                    lines.append(f"    Decision -- Success --> {next_step}")
                    lines.append(f"    Decision -- Failure --> ErrorHandling")
                    lines.append(f"    ErrorHandling --> RetryOrAbort")
                    lines.append(f"    RetryOrAbort --> {next_step}")
                    current = "RetryOrAbort"
                else:
                    lines.append(f"    {step} --> {next_step}")
                    current = step
            
            lines.append(f"    {current} --> Completed")
            lines.append("    Completed --> *")
        
        lines.append("")
        lines.append("```")
        return "\n".join(lines)
    
    def generate_state_machine_diagram(self) -> str:
        """Generate state machine diagram from IR state transition functions.
        
        Detects state transition patterns (SetStatus, Approve, Reject, Publish, Submit)
        and generates a mermaid stateDiagram-v2.
        """
        lines = ["```mermaid", "stateDiagram-v2"]
        
        # Detect states from struct fields and constants
        states = set()
        transitions = []
        
        for struct in self.structs:
            if isinstance(struct, dict):
                name = struct.get('name', '')
                fields = struct.get('fields', [])
            else:
                name = getattr(struct, 'name', '')
                fields = getattr(struct, 'fields', [])
            
            if not name:
                continue
            
            # Check for status/state fields
            for field in fields:
                if isinstance(field, dict):
                    fname = field.get('name', '').lower()
                else:
                    fname = str(field).lower()
                
                if 'status' in fname or 'state' in fname or 'stage' in fname:
                    # Try to detect state values from comments or defaults
                    comment = field.get('comment', '') if isinstance(field, dict) else ''
                    if comment:
                        import re as re_mod
                        # Extract state values from comments like "1=draft 2=pending 3=approved"
                        state_matches = re_mod.findall(r'(\d+)=([\w]+)', comment)
                        for val, state in state_matches:
                            states.add(state)
        
        # Detect transitions from function names
        transition_patterns = {
            'Submit': 'SUBMITTED',
            'Approve': 'APPROVED',
            'Reject': 'REJECTED',
            'Publish': 'PUBLISHED',
            'Unpublish': 'UNPUBLISHED',
            'Activate': 'ACTIVE',
            'Deactivate': 'INACTIVE',
            'Archive': 'ARCHIVED',
            'Recall': 'RECALLED',
            'Resubmit': 'RESUBMITTED',
            'Audit': 'AUDITED',
        }
        
        for func in self.functions:
            if isinstance(func, dict):
                fname = func.get('name', '')
            else:
                fname = getattr(func, 'name', '')
            
            for pattern, state in transition_patterns.items():
                if pattern.lower() in fname.lower():
                    transitions.append(('TO_' + state, state))
                    states.add(state)
                    break
        
        # If we found states, generate the diagram
        if states:
            # Add initial state
            lines.append("    [*] --> DRAFT")
            states.discard('DRAFT')
            
            for state in sorted(states):
                if state == 'DRAFT':
                    continue
                lines.append(f"    DRAFT --> {state}")
            
            # Add transitions
            for trans_name, state in transitions:
                lines.append(f"    {state} --> {trans_name}")
            
            lines.append("    [*] --> DRAFT")
        else:
            # Fallback: generic state machine template
            lines.append("    [*] --> Draft")
            lines.append("    Draft --> PendingApproval")
            lines.append("    PendingApproval --> Approved")
            lines.append("    PendingApproval --> Rejected")
            lines.append("    Approved --> Published")
            lines.append("    Rejected --> Draft")
            lines.append("    Published --> Archived")
            lines.append("    Published --> Rejected")
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_dependency_diagram(self) -> str:
        """Generate module dependency diagram from call_graph.
        
        Shows package-level dependencies with direction arrows.
        """
        lines = ["```mermaid", "graph LR"]
        
        # Group by package
        packages = {}
        for edge in self.call_graph:
            if isinstance(edge, dict):
                caller = edge.get('caller', '')
                callee = edge.get('callee', '')
            else:
                caller = getattr(edge, 'caller', '')
                callee = getattr(edge, 'callee', '')
            
            if not caller or not callee:
                continue
            
            caller_pkg = caller.split('/')[-2] if '/' in caller else caller.split('.')[0]
            callee_pkg = callee.split('/')[-2] if '/' in callee else callee.split('.')[0]
            
            if caller_pkg not in packages:
                packages[caller_pkg] = set()
            packages[caller_pkg].add(callee_pkg)
        
        # Add nodes
        for pkg in packages:
            safe_id = pkg.replace('/', '_').replace('.', '_')
            lines.append(f"    {safe_id}[\"{pkg}\"]")
        
        # Add edges
        for pkg, deps in packages.items():
            safe_id = pkg.replace('/', '_').replace('.', '_')
            for dep in deps:
                dep_safe = dep.replace('/', '_').replace('.', '_')
                lines.append(f"    {safe_id} --> {dep_safe}")
        
        if not packages:
            lines.append("    Handler[Handler Layer]")
            lines.append("    Service[Service Layer]")
            lines.append("    DAO[DAO Layer]")
            lines.append("    Handler --> Service")
            lines.append("    Service --> DAO")
        
        lines.append("```")
        return "\n".join(lines)

    def generate_api_flow_diagram(self) -> str:
        """Generate API flow diagram from routes + call_graph.
        
        Shows the end-to-end flow of a typical API request.
        """
        if not self.routes and not self.call_graph:
            return "```mermaid\nflowchart TD\n    [No API data available]\n```"
        
        lines = ["```mermaid", "flowchart TD"]
        lines.append("")
        lines.append("    participant Client")
        lines.append("    participant Gateway")
        lines.append("    participant Handler")
        lines.append("    participant Service")
        lines.append("    participant DAO")
        lines.append("    participant DB")
        
        lines.append("")
        lines.append("    Client->>Gateway: HTTP Request")
        lines.append("    Gateway->>Handler: Route dispatch")
        
        if self.routes:
            first_route = self.routes[0]
            if isinstance(first_route, dict):
                method = first_route.get('method', 'GET').upper()
                path = first_route.get('path', '?')
                handler = first_route.get('handler', '?')
            else:
                method = getattr(first_route, 'method', 'GET').upper()
                path = getattr(first_route, 'path', '?')
                handler = getattr(first_route, 'handler', '?')
            lines.append(f"    Handler->>Service: {method} {path}")
        else:
            lines.append("    Handler->>Service: Business logic")
        
        lines.append("    Service->>DAO: Data access")
        lines.append("    DAO->>DB: SQL query")
        lines.append("    DB-->>DAO: Result")
        lines.append("    DAO-->>Service: Data")
        lines.append("    Service->>Handler: Response")
        lines.append("    Handler->>Gateway: HTTP Response")
        lines.append("    Gateway->>Client: Return data")
        lines.append("")
        
        external_calls = set()
        for edge in self.call_graph[:5]:
            if isinstance(edge, dict):
                callee = edge.get('callee', '')
            else:
                callee = getattr(edge, 'callee', '')
            if callee and 'external' in str(callee).lower():
                external_calls.add(callee)
        
        if external_calls:
            lines.append("    Service->>External: RPC/HTTP calls")
            for ext in list(external_calls)[:3]:
                safe_id = str(ext).replace('-', '_').replace('.', '_')
                lines.append(f"    External-->>{safe_id}: Response")
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_error_code_matrix_diagram(self) -> str:
        """Generate error code matrix from error_codes IR data."""
        if not self.error_codes:
            return "```mermaid\nstateDiagram-v2\n    [*] --> Ready\n    No error codes defined\n```"
        
        lines = ["```mermaid", "stateDiagram-v2"]
        lines.append("")
        lines.append("* --> Ready")
        lines.append("")
        lines.append("## Error Code Matrix")
        lines.append("")
        
        for ec in self.error_codes[:10]:
            if isinstance(ec, dict):
                name = ec.get('name', 'UNKNOWN')
                code = ec.get('code', '000')
            else:
                name = getattr(ec, 'name', 'UNKNOWN')
                code = getattr(ec, 'code', '000')
            
            if code.startswith('4'):
                http_status = '4xx Client Error'
            elif code.startswith('5'):
                http_status = '5xx Server Error'
            elif code.lstrip('-').isdigit() and int(code) < 400:
                http_status = 'Success'
            else:
                http_status = 'Error'
            
            lines.append(f"    Ready --> {name}: [{code}] {http_status}")
        
        lines.append("")
        lines.append("```")
        return "\n".join(lines)

    def generate_business_flow_diagram(self) -> str:
        """从 SPX Processor 和 Go 调用链生成业务流程图."""
        lines = ["```mermaid", "flowchart TB"]
        lines.append("    classDef entry fill:#f9f,stroke:#333,stroke-width:2px")
        lines.append("    classDef external fill:#bbf,stroke:#333,stroke-width:1px")
        lines.append("    classDef db fill:#dfd,stroke:#333,stroke-width:1px")
        lines.append("    classDef kafka fill:#fbd,stroke:#333,stroke-width:1px")
        lines.append("    classDef lock fill:#fdb,stroke:#333,stroke-width:1px")
        lines.append("")
        if self.entry_points:
            for ep in self.entry_points[:3]:
                name = ep.get('name', 'unknown')
                file = ep.get('file', '')
                short_name = name[:25]
                lines.append(f'    A["<b>{short_name}</b><br/><small>{file}</small>"]')
                lines.append("    class A entry")
                for call in ep.get('calls', [])[:5]:
                    callee = call.get('name', '')
                    is_cross = call.get('cross_repo') or call.get('external_call')
                    if is_cross:
                        lines.append(f'    A -->|"SPX RPC"| B["{callee[:25]}"]')
                        lines.append("    class B external")
                    else:
                        lines.append(f"    A --> {callee[:25]}")
        if self.spex_traces:
            for func_name, trace in list(self.spex_traces.items())[:3]:
                func_short = func_name[:20]
                top_call = None
                for call in trace.get('calls', []):
                    if call.get('cross_repo') or call.get('external_call'):
                        top_call = call
                        break
                if top_call:
                    callee_name = top_call.get('name', 'external')[:25]
                    lines.append(f"    subgraph SPX[{func_short}]")
                    lines.append(f"        C[\"{func_short}\"]")
                    lines.append(f"        C --> D[\"{callee_name}\"]")
                    for sub in top_call.get('calls', [])[:3]:
                        sub_name = sub.get('name', '')[:20]
                        lines.append(f'        D --> "{sub_name}"')
                    lines.append("    end")
        lines.append("")
        lines.append("```")
        return "\n".join(lines)

    def generate_cross_service_flow_diagram(self) -> str:
        """生成跨服务数据流图 — 基于 cross_repo_flow 的追踪结果."""
        lines = ["```mermaid", "flowchart LR"]
        lines.append("    classDef repo fill:#e8e8ff,stroke:#666,stroke-width:2px")
        lines.append("    classDef svc fill:#fff4e8,stroke:#666,stroke-width:1px")
        lines.append("    classDef rpc fill:#ffe8e8,stroke:#666,stroke-width:1px")
        lines.append("")
        repos = set()
        rpc_calls = []
        if self.cross_repo:
            calls = self.cross_repo.get('calls', [])
            for call in calls[:20]:
                caller = call.get('caller', '')
                callee = call.get('callee', '')
                cross_repo = call.get('cross_repo', False)
                caller_pkg = caller.split('/')
                callee_pkg = callee.split('/')
                caller_svc = caller_pkg[-3] if len(caller_pkg) > 3 else caller_pkg[-1]
                callee_svc = callee_pkg[-3] if len(callee_pkg) > 3 else callee_pkg[-1]
                repos.add(caller_svc)
                repos.add(callee_svc)
                if cross_repo:
                    rpc_calls.append((caller_svc, callee_svc, call.get('func', '')))
        for repo in sorted(repos):
            safe = repo.replace('-', '_').replace('.', '_')
            lines.append(f'    {safe}["📦 {repo}"]')
            lines.append(f"    class {safe} repo")
        for caller_svc, callee_svc, func in rpc_calls[:10]:
            caller_safe = caller_svc.replace('-', '_').replace('.', '_')
            callee_safe = callee_svc.replace('-', '_').replace('.', '_')
            func_short = func[:30] if func else 'SPX RPC'
            lines.append(f'    {caller_safe} -.->|"SPX: {func_short}"| {callee_safe}')
        lines.append("")
        lines.append("```")
        return "\n".join(lines)

    def generate_detailed_state_machine(self) -> str:
        """从模式检测结果生成详细状态机图."""
        states = []
        patterns = self.patterns
        for item in patterns.get('state_machines', []):
            for state_val in item.get('states', []):
                m = re.match(r'(\w+)=(\w+)', state_val)
                if m:
                    states.append(m.group(1).lower())
        task_states = {
            'UNKNOWN': '未知', 'CANCELED': '已取消', 'SCHEDULING': '待调度',
            'PRE_EXECUTION': '预处理', 'EXECUTING': '执行中',
            'EXECUTION_SUCCESS': '执行成功', 'CALLBACK_SUCCESS': '回调成功',
            'EXECUTION_FAILURE': '执行失败', 'CALLBACK_FAILURE': '回调失败',
            'SUCCESSED': '已完成', 'FAILED': '已失败',
        }
        states.extend(task_states.keys())
        states = list(dict.fromkeys(states))
        lines = ["```mermaid", "stateDiagram-v2"]
        lines.append("    title 系统状态机（从代码模式检测）")
        lines.append("")
        if states:
            initial = 'UNKNOWN' if 'UNKNOWN' in states else states[0]
            lines.append(f"    [*] --> {initial}")
            for item in patterns.get('task_group_patterns', []):
                desc = item.get('desc', '')
                if '创建' in desc:
                    lines.append(f"    {initial} --> 创建任务组")
                if '完成' in desc:
                    lines.append(f"    执行成功 --> 任务组完成")
            for state in states:
                if state == initial:
                    continue
                if any(kw in state.lower() for kw in ['success', 'succ', '完成']):
                    lines.append(f"    EXECUTING --> {state}")
                elif any(kw in state.lower() for kw in ['fail', '失败']):
                    lines.append(f"    EXECUTING --> {state}")
                elif any(kw in state.lower() for kw in ['cancel', '取消']):
                    lines.append(f"    [*] --> {state}")
                elif any(kw in state.lower() for kw in ['pending', '待', 'schedul']):
                    lines.append(f"    [*] --> {state}")
                elif any(kw in state.lower() for kw in ['execut', '执行']):
                    lines.append(f"    待调度 --> {state}")
                else:
                    lines.append(f"    {initial} --> {state}")
        else:
            lines.append("    [*] --> Draft")
            lines.append("    Draft --> PendingApproval")
            lines.append("    PendingApproval --> Approved")
            lines.append("    PendingApproval --> Rejected")
            lines.append("    Approved --> Published")
            lines.append("    Published --> Archived")
        lines.append("")
        lines.append("```")
        return "\n".join(lines)

    def generate_task_lifecycle_diagram(self) -> str:
        """生成任务系统生命周期图."""
        lines = ["```mermaid", "flowchart TD"]
        lines.append("    classDef node fill:#e8f4fd,stroke:#0366d6,stroke-width:2px")
        lines.append("    classDef decision fill:#fff3cd,stroke:#856404,stroke-width:2px")
        lines.append("    classDef success fill:#d4edda,stroke:#155724,stroke-width:2px")
        lines.append("    classDef fail fill:#f8d7da,stroke:#721c24,stroke-width:2px")
        lines.append("    classDef kafka fill:#e2e3e5,stroke:#383d41,stroke-width:1px,dashed")
        lines.append("")
        lines.append("    subgraph SubmitPhase[提交阶段]")
        lines.append('        A["SpexSubmitTask<br/>(SPX RPC)"]')
        lines.append('        B["写入 MySQL<br/>(task_info)"]')
        lines.append('        C["发送 Kafka<br/>(task_priority)"]')
        lines.append("        class A,B,C node")
        lines.append("    end")
        lines.append("")
        lines.append("    subgraph ExecutePhase[执行阶段]")
        lines.append('        D["taskworker<br/>Kafka 消费"]')
        lines.append('        E["WorkerProcessTask"]')
        lines.append('        F{"CheckConfirm<br/>幂等校验"}')
        lines.append('        G["RPC 调用<br/>RunFunc"]')
        lines.append("        class D,E,F decision")
        lines.append("        class G node")
        lines.append("    end")
        lines.append("")
        lines.append("    subgraph ResultPhase[结果处理]")
        lines.append('        H{"执行成功?"}')
        lines.append('        I["状态: SUCCESS"]')
        lines.append('        J["发送 Callback<br/>CallbackFunc"]')
        lines.append('        K{"重试?"}')
        lines.append('        L["重新入 Kafka<br/>(retryOrder+1)"]')
        lines.append('        M["状态: FAILED"]')
        lines.append("        class H,K decision")
        lines.append("        class I,J success")
        lines.append("        class L kafka")
        lines.append("    end")
        lines.append("")
        lines.append("    A --> B --> C")
        lines.append("    C -.->|Kafka| D")
        lines.append("    D --> E --> F")
        lines.append("    F -->|TRY| G")
        lines.append("    F -->|CANCEL| M")
        lines.append("    G --> H")
        lines.append("    H -->|Yes| I --> J")
        lines.append("    H -->|No| K")
        lines.append("    K -->|retryOrder < retryMax| L --> C")
        lines.append("    K -->|已达最大重试| M")
        lines.append("")
        lines.append("```")
        return "\n".join(lines)

    def generate_facebook_sync_flow_diagram(self) -> str:
        """生成 Facebook 全量同步流程图 — 经典场景示例."""
        lines = ["```mermaid", "flowchart TB"]
        lines.append("    classDef trigger fill:#ffeaa7,stroke:#fdcb6e,stroke-width:2px")
        lines.append("    classDef api fill:#74b9ff,stroke:#0984e3,stroke-width:2px")
        lines.append("    classDef diff fill:#a29bfe,stroke:#6c5ce7,stroke-width:2px")
        lines.append("    classDef store fill:#55efc4,stroke:#00b894,stroke-width:2px")
        lines.append("    classDef alert fill:#ff7675,stroke:#d63031,stroke-width:2px")
        lines.append("    classDef db fill:#dfe6e9,stroke:#636e72,stroke-width:1px")
        lines.append("")
        lines.append("    subgraph Trigger[🕐 触发层]")
        lines.append('        A["Cron/MMS<br/>定时调度"]')
        lines.append('        B["自定义同步<br/>(指定campaign)"]')
        lines.append("        class A,B trigger")
        lines.append("    end")
        lines.append("")
        lines.append("    subgraph Init[📋 初始化]")
        lines.append('        C["获取 AdAccount<br/>列表(Apollo配置)"]')
        lines.append('        D["查询 Catalog<br/>+ ProductSet"]')
        lines.append("        class C,D db")
        lines.append("    end")
        lines.append("")
        lines.append("    subgraph FBQuery[🔍 FB API 查询层]")
        lines.append('        E["getCampaignIds()<br/>GetCampaignByAccountId"]')
        lines.append('        F["getCampaignList()<br/>GoPool并发<br/>(CONCURRENCY_LEVEL)"]')
        lines.append('        G["getAdSetInfoList()<br/>并发查询adset"]')
        lines.append('        H["getAdList()<br/>并发查询ad"]')
        lines.append('        I["getAdCreativeList()"]')
        lines.append("        class E,F,G,H,I api")
        lines.append("    end")
        lines.append("")
        lines.append("    subgraph Diff[📊 Diff 计算层]")
        lines.append('        J{"FB有?"}')
        lines.append('        K{"字段变更?"}')
        lines.append('        L{"FB存在?"}')
        lines.append('        M["NeedAdded<br/>新增"]')
        lines.append('        N["NeedUpdated<br/>更新"]')
        lines.append('        O["NeedDeleted<br/>删除<br/>(二次确认)"]')
        lines.append("        class J,K,L diff")
        lines.append("        class M,N,O alert")
        lines.append("    end")
        lines.append("")
        lines.append("    subgraph Store[💾 存储层]")
        lines.append('        P["StoreCampaign<br/>del→upd→add"]')
        lines.append('        Q["StoreAdset<br/>del→upd→add"]')
        lines.append('        R["StoreAd<br/>del→upd→add"]')
        lines.append('        S["AddAdCreative"]')
        lines.append("        class P,Q,R,S store")
        lines.append("    end")
        lines.append("")
        lines.append("    subgraph Filter[🚫 过滤]")
        lines.append('        T["ARCHIVED<br/>Campaign"]')
        lines.append('        U["UA Campaign<br/>(business_goal=2)"]')
        lines.append('        V["不支持<br/>Objective"]')
        lines.append("        class T,U,V diff")
        lines.append("    end")
        lines.append("")
        lines.append("    A & B --> C --> D")
        lines.append("    D --> E --> T --> U --> F")
        lines.append("    F --> J")
        lines.append("    J -- FB有 --> K")
        lines.append("    J -- FB无 --> V --> L")
        lines.append("    K -- 有变更 --> N")
        lines.append("    K -- 无变更 --> G")
        lines.append("    L -- 存在 --> O")
        lines.append("    L -- 不存在 --> M")
        lines.append("    M & N --> G --> H --> I")
        lines.append("    P --> Q --> R --> S")
        lines.append("")
        lines.append("```")
        return "\n".join(lines)

    def generate_ads_change_sync_diagram(self) -> str:
        """生成 ADS 变更实时同步 Sequence 图."""
        lines = ["```mermaid", "sequenceDiagram"]
        lines.append("    title ADS 变更实时同步（DAP → ADP）")
        lines.append("    autonumber")
        lines.append("")
        lines.append("    participant Client as 客户端(DAP)")
        lines.append("    participant Kafka as GAS/Kafka")
        lines.append("    participant Proc as AdsChangeProcessor")
        lines.append("    participant SyncSvc as AdsChangeSyncServiceImpl")
        lines.append("    participant DapDB as DAP MySQL")
        lines.append("    participant AdpDB as ADP SPX")
        lines.append("")
        lines.append("    Client->>Kafka: AdsChangeInfo(campaign/adset/ad)")
        lines.append("    Kafka->>Proc: Process(msg)")
        lines.append("    Proc->>SyncSvc: MsgHandler(info)")
        lines.append("")
        lines.append("    alt ObjectLevel == Campaign")
        lines.append("        SyncSvc->>DapDB: QueryDapCampaignById")
        lines.append("        SyncSvc->>DapDB: QueryFbCampaignById")
        lines.append("        SyncSvc->>AdpDB: QueryOpsCampaign")
        lines.append("        alt ADP未查到 → 创建")
        lines.append("            SyncSvc->>AdpDB: CreateOrUpdateCampaign(INSERT)")
        lines.append("        else ADP查到 → 更新")
        lines.append("            SyncSvc->>AdpDB: CreateOrUpdateCampaign(UPDATE_ALL)")
        lines.append("        end")
        lines.append("        SyncSvc->>AdpDB: OperateDraftAds(删除草稿)")
        lines.append("    elseif ObjectLevel == AdSet")
        lines.append("        SyncSvc->>DapDB: QueryDapAdSetById + QueryFbAdSetById")
        lines.append("        SyncSvc->>AdpDB: QueryOpsAdGroup")
        lines.append("        alt 未查到 → CREATE")
        lines.append("            SyncSvc->>AdpDB: CreateOrUpdateAdGroup(INSERT)")
        lines.append("        else 查到 → UPDATE_ALL")
        lines.append("            SyncSvc->>AdpDB: CreateOrUpdateAdGroup(UPDATE_ALL)")
        lines.append("        end")
        lines.append("    elseif ObjectLevel == Ad")
        lines.append("        SyncSvc->>DapDB: QueryDapAdById + QueryFbAdById")
        lines.append("        SyncSvc->>DapDB: GetAllAdCreative(creativeId)")
        lines.append("        SyncSvc->>AdpDB: QueryOpsAd")
        lines.append("        alt 未查到 → CREATE")
        lines.append("            SyncSvc->>AdpDB: CreateOrUpdateAd(INSERT)")
        lines.append("        else 查到 → UPDATE_ALL")
        lines.append("            SyncSvc->>AdpDB: CreateOrUpdateAd(UPDATE_ALL)")
        lines.append("        end")
        lines.append("    end")
        lines.append("")
        lines.append("    SyncSvc->>AdpDB: SyncAdsLogToAdp(最近5天日志)")
        lines.append("    Kafka-->>Proc: 消费确认")
        lines.append("")
        lines.append("```")
        return "\n".join(lines)


# ============================================================================
# End of MermaidGenerator class
# ============================================================================
