#!/usr/bin/env python3
"""
Community Enhancement - 社区自动命名 + 重要性排序

基于图中心性和语义分析，自动为社区命名并排序重要性
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import Counter, defaultdict


class CommunityEnhancer:
    """社区增强器 - 自动命名 + 重要性排序"""
    
    # 命名关键词映射
    _NAME_KEYWORDS = {
        'graph': ['graph', 'edge', 'node', 'vertex', 'vertex'],
        'runner': ['runner', 'execute', 'process', 'invoke', 'run'],
        'channel': ['channel', 'pipe', 'stream', 'buffer'],
        'handler': ['handler', 'callback', 'listener', 'middleware'],
        'builder': ['builder', 'config', 'factory', 'creator'],
        'model': ['model', 'chat', 'completion', 'generate'],
        'schema': ['schema', 'type', 'struct', 'interface', 'message'],
        'component': ['component', 'piece', 'part'],
        'workflow': ['workflow', 'flow', 'pipeline', 'sequence'],
        'tool': ['tool', 'utility', 'helper', 'utils'],
        'auth': ['auth', 'permission', 'security', 'token'],
        'cache': ['cache', 'memory', 'buffer', 'store'],
        'database': ['db', 'query', 'repo', 'dao', 'repository', 'mongo', 'redis'],
        'http': ['http', 'request', 'response', 'route', 'handler'],
        'api': ['api', 'endpoint', 'rpc', 'grpc'],
        'event': ['event', 'publish', 'subscribe', 'listen'],
        'queue': ['queue', 'task', 'worker', 'job'],
        'config': ['config', 'setting', 'option', 'env'],
        'log': ['log', 'trace', 'debug', 'metric'],
        'test': ['test', 'spec', 'fake', 'mock'],
    }
    
    # 文件扩展名到语言
    _LANG_EXTENSIONS = {
        '.go': 'go',
        '.py': 'python',
        '.java': 'java',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.js': 'javascript',
    }
    
    @classmethod
    def analyze_communities(cls, graph_data: Dict) -> Dict:
        """分析社区，返回带命名的社区列表"""
        nodes = graph_data.get('nodes', [])
        edges = graph_data.get('edges', [])
        communities = graph_data.get('communities', {})
        
        if not communities:
            return {'communities': [], 'total': 0}
        
        # 按社区分组节点
        community_nodes = defaultdict(list)
        for node_id, comm_id in communities.items():
            community_nodes[comm_id].append(node_id)
        
        # 分析每个社区
        results = []
        for comm_id, node_ids in community_nodes.items():
            # 1. 自动命名
            name = cls._auto_name_community(node_ids, nodes)
            
            # 2. 计算重要性分数
            importance = cls._calculate_importance(node_ids, nodes, edges)
            
            # 3. 提取关键节点
            key_nodes = cls._extract_key_nodes(node_ids, nodes, edges)
            
            # 4. 提取共同特征
            features = cls._extract_features(node_ids, nodes, edges)
            
            results.append({
                'id': comm_id,
                'name': name,
                'size': len(node_ids),
                'importance': importance,
                'key_nodes': key_nodes,
                'features': features,
            })
        
        # 按重要性排序
        results.sort(key=lambda x: x['importance'], reverse=True)
        
        # 重新编号
        for i, r in enumerate(results):
            r['id'] = i
        
        return {
            'communities': results,
            'total': len(results),
            'total_nodes': len(nodes),
            'total_edges': len(edges),
        }
    
    @classmethod
    def _auto_name_community(cls, node_ids: List[str], nodes: List[Dict]) -> str:
        """自动命名社区"""
        # 收集所有节点名
        node_names = []
        node_files = []
        
        node_map = {n['id']: n for n in nodes}
        for nid in node_ids:
            if nid in node_map:
                node_names.append(node_map[nid].get('label', ''))
                node_files.append(node_map[nid].get('source_file', ''))
        
        # 分析文件路径中的关键词
        path_keywords = []
        for f in node_files:
            parts = Path(f).parts
            if len(parts) >= 2:
                path_keywords.extend(parts[-2:])
        
        # 分析节点名称关键词
        name_counts = Counter(node_names)
        top_names = [n for n, _ in name_counts.most_common(5)]
        
        # 匹配命名模式
        combined = ' '.join(top_names + path_keywords).lower()
        
        for keyword, patterns in cls._NAME_KEYWORDS.items():
            for pattern in patterns:
                if pattern in combined:
                    # 找到最匹配的关键词
                    name_matches = sum(1 for n in top_names if pattern in n.lower())
                    if name_matches > 0:
                        return f"{keyword.capitalize()}-related"
        
        # 回退：使用最高频的文件路径
        path_counts = Counter(path_keywords)
        if path_counts:
            most_common_path = path_counts.most_common(1)[0][0]
            return f"{most_common_path.replace('.', '-').replace('/', '-')}-module"
        
        return f"community-{node_ids[0] if node_ids else '0'}"
    
    @classmethod
    def _calculate_importance(cls, node_ids: List[str], nodes: List[Dict], edges: List[Dict]) -> float:  # type: ignore
        """计算社区重要性分数"""
        if not node_ids:
            return 0.0
        
        # 基于：度中心性 + 介数中心性 + 结构完整性
        node_map = {n['id']: n for n in nodes}
        
        # 计算总度数
        total_degree = 0
        internal_edges = 0
        external_edges = 0
        
        node_set = set(node_ids)
        
        for edge in edges:
            src = edge.get('source', '')
            tgt = edge.get('target', '')
            
            if src in node_set and tgt in node_set:
                internal_edges += 1
            elif src in node_set or tgt in node_set:
                external_edges += 1
        
        # 计算平均度数
        avg_degree = 0
        for nid in node_ids:
            if nid in node_map:
                # 计算该节点的度数
                degree = sum(1 for e in edges if e.get('source') == nid or e.get('target') == nid)
                total_degree += degree
        
        avg_degree = total_degree / len(node_ids) if node_ids else 0
        
        # 重要性 = 内部密度 * 外部连接 * 平均度数
        internal_density = internal_edges / (len(node_ids) * (len(node_ids) - 1) / 2) if len(node_ids) > 1 else 0
        connectivity = external_edges / len(node_ids) if node_ids else 0
        
        importance = internal_density * 10 + connectivity * 2 + avg_degree * 0.5
        
        return round(importance, 2)
    
    @classmethod
    def _extract_key_nodes(cls, node_ids: List[str], nodes: List[Dict], edges: List[Dict]) -> List[Dict]:
        """提取关键节点"""
        node_map = {n['id']: n for n in nodes}
        node_set = set(node_ids)
        
        # 计算每个节点的度数
        degrees = {}
        for nid in node_ids:
            if nid in node_map:
                degree = sum(1 for e in edges if e.get('source') == nid or e.get('target') == nid)
                degrees[nid] = degree
        
        # 按度数排序，取前5个
        top_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return [
            {
                'id': nid,
                'label': node_map.get(nid, {}).get('label', nid),
                'type': node_map.get(nid, {}).get('type', ''),
                'degree': deg,
            }
            for nid, deg in top_nodes
        ]
    
    @classmethod
    def _extract_features(cls, node_ids: List[str], nodes: List[Dict], edges: List[Dict]) -> Dict:
        """提取社区特征"""
        node_map = {n['id']: n for n in nodes}
        
        types = Counter()
        files = Counter()
        
        for nid in node_ids:
            if nid in node_map:
                n = node_map[nid]
                types[n.get('type', 'UNKNOWN')] += 1
                files[n.get('source_file', '')] += 1
        
        return {
            'type_distribution': dict(types.most_common(5)),
            'file_count': len(files),
            'top_files': [f for f, _ in files.most_common(3)],
        }


def enhance_communities(graph_path: str, output_path: str = None) -> Dict:
    """增强社区分析"""
    # 读取图数据
    with open(graph_path, 'r', encoding='utf-8') as f:
        graph_data = json.load(f)
    
    # 分析社区
    result = CommunityEnhancer.analyze_communities(graph_data)
    
    # 保存结果
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"✅ 社区分析结果已保存到: {output_file}")
    
    return result


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python community_enhancer.py <graph.json> [output.json]")
        sys.exit(1)
    
    graph_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = enhance_communities(graph_path, output_path)
    print(f"\n📊 分析完成: {result['total']} 个社区, {result['total_nodes']} 节点")
    
    # 打印社区摘要
    print("\n🏘️  社区列表（按重要性排序）:")
    for comm in result['communities'][:10]:
        print(f"  #{comm['id']+1} {comm['name']}: {comm['size']} nodes, importance={comm['importance']}")
        for kn in comm['key_nodes'][:3]:
            print(f"      - {kn['label']} (degree={kn['degree']})")
