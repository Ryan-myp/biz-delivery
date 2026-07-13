#!/usr/bin/env python3
"""跨仓库依赖追踪器 — 用于多仓库场景的服务拓扑分析和依赖关系推断。

核心功能：
1. 跨仓库函数调用追踪（从 call_graph 推断跨服务依赖）
2. 服务拓扑图生成（基于 IR 数据自动构建服务关系图）
3. 实体路由映射（entity → route 跨仓库关联）
4. 影响分析（修改某个服务会影响哪些下游服务）

Usage:
    from cross_repo_dependency import CrossRepoDependencyTracker
    
    tracker = CrossRepoDependencyTracker(repo_ir_map)
    
    # 获取服务拓扑
    topology = tracker.build_service_topology()
    
    # 查询跨仓库依赖
    deps = tracker.get_cross_repo_deps('adgroup-service')
    
    # 影响分析
    impact = tracker.analyze_impact('creative-handler')
"""

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class CrossRepoDependencyTracker:
    """跨仓库依赖追踪器。"""
    
    # 依赖类型分类
    DEPENDENCY_TYPES = {
        'sync_call': '同步调用',
        'async_mq': '异步消息队列',
        'rpc': 'RPC/gRPC 调用',
        'http': 'HTTP 调用',
        'db_shared': '共享数据库',
        'cache_shared': '共享缓存',
    }
    
    def __init__(self, repo_ir_map: Dict[str, dict]):
        """初始化跨仓库依赖追踪器。
        
        Args:
            repo_ir_map: {repo_name: ir_dict} 映射，每个 IR 字典包含
                        functions, routes, call_graph, imports 等字段
        """
        self.repo_ir_map = repo_ir_map
        self.repo_names = list(repo_ir_map.keys())
        
        # 合并所有仓库的数据
        self.all_functions = {}  # func_name → {repo, file, ...}
        self.all_routes = []
        self.all_call_graph = []
        self.all_imports = []
        self.all_services = []
        
        self._build_global_index()
    
    def _build_global_index(self):
        """构建全局索引 — 将所有仓库的数据合并到统一索引中。"""
        for repo_name, ir_data in self.repo_ir_map.items():
            if not isinstance(ir_data, dict):
                continue
            
            # 索引函数
            for func in ir_data.get('functions', []):
                if isinstance(func, dict):
                    fname = func.get('name', '')
                    if fname:
                        self.all_functions[fname] = {
                            'repo': repo_name,
                            'file': func.get('file', ''),
                            'signature': func.get('signature', ''),
                        }
            
            # 索引路由
            for route in ir_data.get('routes', []):
                if isinstance(route, dict):
                    route['repo'] = repo_name
                    self.all_routes.append(route)
            
            # 索引调用图
            for edge in ir_data.get('call_graph', []):
                if isinstance(edge, dict):
                    edge['repo'] = repo_name
                    self.all_call_graph.append(edge)
            
            # 索引 imports
            for imp in ir_data.get('imports', []):
                if isinstance(imp, dict):
                    imp['repo'] = repo_name
                    self.all_imports.append(imp)
            
            # 索引 services
            for svc in ir_data.get('services', []):
                if isinstance(svc, dict):
                    svc['repo'] = repo_name
                    self.all_services.append(svc)
    
    def build_service_topology(self) -> Dict[str, Any]:
        """构建服务拓扑图。
        
        Returns:
            {
                'services': [{name, repo, type, functions[], depends_on[], depended_by[]}],
                'cross_repo_edges': [(src_service, dst_service, dep_type)],
                'service_count': N,
                'edge_count': M,
            }
        """
        # 按仓库分组函数
        repo_func_groups = defaultdict(list)
        for fname, info in self.all_functions.items():
            repo_func_groups[info['repo']].append(fname)
        
        # 按仓库分组路由
        repo_route_groups = defaultdict(list)
        for route in self.all_routes:
            repo_route_groups[route.get('repo', '')].append(route)
        
        # 构建服务列表
        services = []
        for repo_name, funcs in repo_func_groups.items():
            # 推断服务类型
            svc_type = self._infer_service_type(funcs, repo_name)
            
            # 找出该服务的函数
            service_funcs = [f for f in funcs if f in self.all_functions]
            
            services.append({
                'name': repo_name,
                'repo': repo_name,
                'type': svc_type,
                'function_count': len(service_funcs),
                'functions': service_funcs[:10],
                'route_count': len(repo_route_groups.get(repo_name, [])),
            })
        
        # 构建依赖边
        edges = []
        seen_edges = set()
        
        for edge in self.all_call_graph:
            caller = edge.get('caller', '')
            callee = edge.get('callee', '')
            
            if not caller or not callee:
                continue
            
            # 查找 caller 和 callee 所属的服务
            caller_svc = self._find_service_for_function(caller)
            callee_svc = self._find_service_for_function(callee)
            
            if not caller_svc or not callee_svc:
                continue
            
            # 跳过同服务内部调用
            if caller_svc == callee_svc:
                continue
            
            # 去重
            edge_key = (caller_svc, callee_svc)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            
            # 推断依赖类型
            dep_type = self._infer_dependency_type(edge)
            
            edges.append({
                'source': caller_svc,
                'target': callee_svc,
                'type': dep_type,
                'cn_type': self.DEPENDENCY_TYPES.get(dep_type, dep_type),
            })
        
        return {
            'services': services,
            'cross_repo_edges': edges,
            'service_count': len(services),
            'edge_count': len(edges),
        }
    
    def get_cross_repo_deps(self, service_name: str) -> List[Dict]:
        """获取指定服务的跨仓库依赖。
        
        Args:
            service_name: 服务名（通常是仓库名）
            
        Returns:
            [{source, target, type, cn_type}]
        """
        deps = []
        for edge in self.all_call_graph:
            if not isinstance(edge, dict):
                continue
            
            caller = edge.get('caller', '')
            callee = edge.get('callee', '')
            
            caller_svc = self._find_service_for_function(caller)
            callee_svc = self._find_service_for_function(callee)
            
            if caller_svc == service_name and callee_svc != service_name:
                deps.append({
                    'source': caller_svc,
                    'target': callee_svc,
                    'type': self._infer_dependency_type(edge),
                    'cn_type': self.DEPENDENCY_TYPES.get(self._infer_dependency_type(edge), ''),
                })
            elif callee_svc == service_name and caller_svc != service_name:
                deps.append({
                    'source': caller_svc,
                    'target': callee_svc,
                    'type': self._infer_dependency_type(edge),
                    'cn_type': self.DEPENDENCY_TYPES.get(self._infer_dependency_type(edge), ''),
                    'direction': 'incoming',
                })
        
        return deps
    
    def analyze_impact(self, function_name: str) -> Dict[str, Any]:
        """影响分析 — 如果修改某个函数，会影响哪些其他服务。
        
        Args:
            function_name: 要分析的函数名
            
        Returns:
            {
                'function': str,
                'direct_dependents': [...],
                'transitive_dependents': [...],
                'affected_services': [...],
                'risk_level': 'low/medium/high/critical',
            }
        """
        # 直接依赖者
        direct_dependents = []
        transitive_dependents = set()
        
        # BFS 查找所有依赖者
        queue = [function_name]
        visited = {function_name}
        
        while queue:
            current = queue.pop(0)
            for edge in self.all_call_graph:
                if not isinstance(edge, dict):
                    continue
                
                caller = edge.get('caller', '')
                callee = edge.get('callee', '')
                
                if callee == current and caller not in visited:
                    visited.add(caller)
                    queue.append(caller)
                    
                    # 查找 caller 所属服务
                    caller_svc = self._find_service_for_function(caller)
                    if caller_svc:
                        direct_dependents.append({
                            'function': caller,
                            'service': caller_svc,
                        })
                        transitive_dependents.add(caller_svc)
        
        # 受影响的服务
        affected_services = list(transitive_dependents)
        
        # 风险评估
        risk_level = self._assess_risk(len(affected_services), direct_dependents)
        
        return {
            'function': function_name,
            'direct_dependents': direct_dependents[:10],
            'transitive_dependents': list(transitive_dependents)[:10],
            'affected_services': affected_services,
            'impact_count': len(affected_services),
            'risk_level': risk_level,
        }
    
    def generate_dependency_matrix(self) -> Dict[str, Dict[str, str]]:
        """生成服务依赖矩阵。
        
        Returns:
            {service_a: {service_b: dep_type, ...}, ...}
        """
        matrix = defaultdict(dict)
        
        for edge in self.all_call_graph:
            if not isinstance(edge, dict):
                continue
            
            caller = edge.get('caller', '')
            callee = edge.get('callee', '')
            
            caller_svc = self._find_service_for_function(caller)
            callee_svc = self._find_service_for_function(callee)
            
            if caller_svc and callee_svc and caller_svc != callee_svc:
                dep_type = self._infer_dependency_type(edge)
                # 保留最高优先级的依赖类型
                priority = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
                current = matrix[caller_svc].get(callee_svc, 'unknown')
                if priority.get(dep_type, 0) > priority.get(current, 0):
                    matrix[caller_svc][callee_svc] = dep_type
        
        # 转换为普通 dict
        return {k: dict(v) for k, v in matrix.items()}
    
    def generate_topology_diagram(self) -> str:
        """生成 Mermaid 服务拓扑图。"""
        topology = self.build_service_topology()
        lines = ["```mermaid", "graph LR"]
        
        # 定义节点样式
        for svc in topology['services']:
            safe_name = svc['name'].replace('-', '_').replace('.', '_')
            svc_type = svc.get('type', 'unknown')
            icon = self._get_service_icon(svc_type)
            lines.append(f"    {safe_name}[{icon} {svc['name']}\\n({svc_type})]")
        
        # 添加边
        for edge in topology['cross_repo_edges'][:20]:
            src_safe = edge['source'].replace('-', '_').replace('.', '_')
            dst_safe = edge['target'].replace('-', '_').replace('.', '_')
            arrow = self._get_edge_arrow(edge['type'])
            label = edge.get('cn_type', edge['type'])
            lines.append(f"    {src_safe} -- {label} --> {dst_safe}")
        
        lines.append("```")
        return "\n".join(lines)
    
    # ── 辅助方法 ──────────────────────────────
    
    def _infer_service_type(self, funcs: List[str], repo_name: str) -> str:
        """根据函数名推断服务类型。"""
        func_text = ' '.join(funcs).lower()
        
        if any(kw in func_text for kw in ['handler', 'router', 'controller', 'api']):
            return 'handler'
        elif any(kw in func_text for kw in ['service', 'manager', 'biz']):
            return 'service'
        elif any(kw in func_text for kw in ['dao', 'repository', 'repo']):
            return 'dao'
        elif any(kw in func_text for kw in ['middleware', 'auth', 'intercept']):
            return 'middleware'
        else:
            return 'mixed'
    
    def _find_service_for_function(self, func_name: str) -> Optional[str]:
        """查找函数所属的服务（仓库）。"""
        if func_name in self.all_functions:
            return self.all_functions[func_name].get('repo')
        
        # 也检查 call_graph
        for edge in self.all_call_graph:
            if not isinstance(edge, dict):
                continue
            if edge.get('caller') == func_name:
                return edge.get('repo')
            if edge.get('callee') == func_name:
                return edge.get('repo')
        
        return None
    
    def _infer_dependency_type(self, edge: Dict) -> str:
        """从调用图边推断依赖类型。"""
        caller = edge.get('caller', '').lower()
        callee = edge.get('callee', '').lower()
        
        # MQ/Kafka 模式
        if any(kw in caller for kw in ['publish', 'emit', 'send', 'produce', 'kafka', 'mq']):
            return 'async_mq'
        
        # RPC 模式
        if any(kw in caller for kw in ['rpc', 'grpc', 'client', 'proxy', 'pb_']):
            return 'rpc'
        
        # HTTP 模式
        if any(kw in caller for kw in ['http.', 'do_request', 'call_api']):
            return 'http'
        
        # 默认同步调用
        return 'sync_call'
    
    def _assess_risk(self, affected_count: int, dependents: List[Dict]) -> str:
        """评估影响风险等级。"""
        if affected_count >= 5:
            return 'critical'
        elif affected_count >= 3:
            return 'high'
        elif affected_count >= 1:
            return 'medium'
        return 'low'
    
    def _get_service_icon(self, svc_type: str) -> str:
        """获取服务图标。"""
        icons = {
            'handler': '🌐',
            'service': '⚙️',
            'dao': '🗄️',
            'middleware': '🔒',
            'mixed': '📦',
        }
        return icons.get(svc_type, '📦')
    
    def _get_edge_arrow(self, dep_type: str) -> str:
        """获取依赖类型的箭头样式。"""
        arrows = {
            'sync_call': '-->',
            'async_mq': '-.->',
            'rpc': '-.->',
            'http': '-->',
            'db_shared': '-.-',
            'cache_shared': '-.-',
        }
        return arrows.get(dep_type, '-->')


# ============================================================================
# Convenience functions
# ============================================================================

def load_multi_repo_ir(cache_dirs: List[str]) -> Dict[str, dict]:
    """从多个缓存目录加载 IR 数据。
    
    Args:
        cache_dirs: 缓存目录列表
        
    Returns:
        {repo_name: ir_dict}
    """
    result = {}
    for cache_dir in cache_dirs:
        cache_file = Path(cache_dir) / "ir_cache.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding='utf-8'))
                repo_name = data.get('repo_name', Path(cache_dir).name)
                result[repo_name] = data
            except Exception:
                pass
    return result


def build_cross_repo_tracker(profile_path: str) -> CrossRepoDependencyTracker:
    """从 profile 文件构建跨仓库依赖追踪器。
    
    Args:
        profile_path: Profile JSON 文件路径
        
    Returns:
        CrossRepoDependencyTracker 实例
    """
    with open(profile_path) as f:
        profile = json.load(f)
    
    repos = profile.get('repositories', [])
    cache_dirs = []
    for repo in repos:
        repo_path = repo.get('path', '')
        if repo_path:
            # 假设 knowledge 目录在 repo 同级
            kb_dir = str(Path(repo_path).parent / 'knowledge' / profile.get('business_domain', 'unknown'))
            cache_dirs.append(kb_dir)
    
    ir_map = load_multi_repo_ir(cache_dirs)
    return CrossRepoDependencyTracker(ir_map)


# CLI entry point
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description="跨仓库依赖追踪器")
    parser.add_argument("--profile", help="Profile JSON 路径")
    parser.add_argument("--cache-dirs", nargs='+', help="IR 缓存目录列表")
    parser.add_argument("--action", default="topology", 
                       choices=["topology", "deps", "impact", "matrix", "diagram"],
                       help="执行的操作")
    parser.add_argument("--service", help="目标服务名（用于 deps/impact 操作）")
    
    args = parser.parse_args()
    
    # 加载 IR
    if args.profile:
        tracker = build_cross_repo_tracker(args.profile)
    elif args.cache_dirs:
        ir_map = load_multi_repo_ir(args.cache_dirs)
        tracker = CrossRepoDependencyTracker(ir_map)
    else:
        print("ERROR: --profile or --cache-dirs is required")
        import sys
        sys.exit(1)
    
    # 执行操作
    if args.action == "topology":
        topology = tracker.build_service_topology()
        print(json.dumps(topology, indent=2, ensure_ascii=False))
    elif args.action == "deps":
        if not args.service:
            print("ERROR: --service is required for deps action")
            import sys
            sys.exit(1)
        deps = tracker.get_cross_repo_deps(args.service)
        print(json.dumps(deps, indent=2, ensure_ascii=False))
    elif args.action == "impact":
        if not args.service:
            print("ERROR: --service is required for impact action")
            import sys
            sys.exit(1)
        impact = tracker.analyze_impact(args.service)
        print(json.dumps(impact, indent=2, ensure_ascii=False))
    elif args.action == "matrix":
        matrix = tracker.generate_dependency_matrix()
        print(json.dumps(matrix, indent=2, ensure_ascii=False))
    elif args.action == "diagram":
        diagram = tracker.generate_topology_diagram()
        print(diagram)
