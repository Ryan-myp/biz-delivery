#!/usr/bin/env python3
"""Mermaid diagram generator — creates actual mermaid code from IR data.

Generates:
1. Architecture diagram (graph TB) from packages + call_graph
2. Data model diagram (erDiagram) from entity_tables
3. Deployment diagram (graph LR) from service_topology
4. Sequence diagram from core_flows
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class MermaidGenerator:
    """Generate mermaid diagrams from IR data."""
    
    def __init__(self, ir_data: Dict[str, Any]):
        self.ir = ir_data
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
        return {
            'architecture': self.generate_architecture_diagram(),
            'data_model': self.generate_data_model_diagram(),
            'deployment': self.generate_deployment_diagram(),
            'sequence': self.generate_sequence_diagram(),
        }
