#!/usr/bin/env python3
"""
HTML Visualizer - 代码图谱 HTML 可视化

生成交互式网络图，展示代码结构、依赖关系、社区分布
"""

import json
from pathlib import Path
from typing import Dict, List, Optional


class HTMLVisualizer:
    """HTML 可视化生成器"""
    
    # 颜色方案
    COLORS = {
        'struct': '#3498db',      # 蓝色 - 结构体
        'interface': '#9b59b6',   # 紫色 - 接口
        'function': '#2ecc71',    # 绿色 - 函数
        'method': '#1abc9c',      # 青色 - 方法
        'file': '#95a5a6',        # 灰色 - 文件
        'module': '#f39c12',      # 橙色 - 模块
        'god': '#e74c3c',         # 红色 - God节点
    }
    
    # 社区颜色
    COMMUNITY_COLORS = [
        '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
        '#42d4f4', '#f032e6', '#bfebf4', '#fabebe', '#000075',
        '#808080', '#ffe119', '#469990', '#dcbeff', '#9A6324'
    ]
    
    @classmethod
    def generate_html(cls, graph_data: Dict, output_path: str) -> str:
        """生成 HTML 可视化"""
        
        nodes = graph_data.get('nodes', [])
        edges = graph_data.get('edges', [])
        communities = graph_data.get('communities', {})
        god_nodes = graph_data.get('god_nodes', [])
        
        # 准备数据
        node_data = []
        for node in nodes:
            node_id = node.get('id', '')
            label = node.get('label', '')
            ntype = node.get('type', 'UNKNOWN').lower()
            source_file = node.get('source_file', '')
            community = communities.get(node_id, -1)
            
            # 判断是否是 God 节点
            is_god = any(g['id'] == node_id for g in god_nodes)
            
            # 确定颜色
            color = cls.COLORS.get(ntype, '#95a5a6')
            if is_god:
                color = cls.COLORS['god']
            elif community >= 0:
                color = cls.COMMUNITY_COLORS[community % len(cls.COMMUNITY_COLORS)]
            
            node_data.append({
                'id': node_id,
                'label': label[:30],  # 截断过长的标签
                'type': ntype,
                'file': source_file,
                'community': community,
                'is_god': is_god,
                'color': color,
                'size': 8 if is_god else 5,
            })
        
        edge_data = []
        for edge in edges:
            edge_data.append({
                'source': edge.get('source', ''),
                'target': edge.get('target', ''),
                'relation': edge.get('relation', ''),
            })
        
        # 统计信息
        stats = {
            'total_nodes': len(nodes),
            'total_edges': len(edges),
            'god_nodes': len(god_nodes),
            'communities': len(set(communities.values())) if communities else 0,
            'by_type': cls._count_by_type(nodes),
        }
        
        # 生成 HTML
        html = cls._render_html(node_data, edge_data, stats, god_nodes)
        
        # 保存文件
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding='utf-8')
        
        return str(output_path)
    
    @classmethod
    def _count_by_type(cls, nodes: List[Dict]) -> Dict[str, int]:
        """按类型统计"""
        counts = {}
        for node in nodes:
            ntype = node.get('type', 'UNKNOWN')
            counts[ntype] = counts.get(ntype, 0) + 1
        return counts
    
    @classmethod
    def _render_html(cls, nodes: List[Dict], edges: List[Dict], 
                     stats: Dict, god_nodes: List[Dict]) -> str:
        """渲染 HTML"""
        
        # 转换为 JSON 字符串
        nodes_json = json.dumps(nodes, ensure_ascii=False)
        edges_json = json.dumps(edges, ensure_ascii=False)
        god_json = json.dumps(god_nodes, ensure_ascii=False)
        
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>代码图谱可视化</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            overflow: hidden;
        }}
        #container {{
            width: 100vw;
            height: 100vh;
            position: relative;
        }}
        svg {{
            width: 100%;
            height: 100%;
        }}
        .node {{
            cursor: pointer;
            transition: all 0.3s;
        }}
        .node:hover {{
            filter: brightness(1.3);
        }}
        .link {{
            stroke: #444;
            stroke-opacity: 0.6;
        }}
        .link-god {{
            stroke: #e74c3c;
            stroke-opacity: 0.8;
        }}
        
        /* 侧边栏 */
        #sidebar {{
            position: absolute;
            top: 10px;
            left: 10px;
            width: 300px;
            max-height: 90vh;
            overflow-y: auto;
            background: rgba(26, 26, 46, 0.95);
            border-radius: 10px;
            padding: 15px;
            border: 1px solid #333;
            backdrop-filter: blur(10px);
        }}
        #sidebar h2 {{
            font-size: 18px;
            margin-bottom: 10px;
            color: #fff;
        }}
        .stat {{
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            border-bottom: 1px solid #333;
        }}
        .stat-label {{
            color: #aaa;
        }}
        .stat-value {{
            font-weight: bold;
            color: #4fc3f7;
        }}
        
        /* 图例 */
        #legend {{
            position: absolute;
            bottom: 10px;
            left: 10px;
            background: rgba(26, 26, 46, 0.95);
            border-radius: 10px;
            padding: 15px;
            border: 1px solid #333;
        }}
        #legend h3 {{
            font-size: 14px;
            margin-bottom: 10px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 3px 0;
            font-size: 12px;
        }}
        .legend-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }}
        
        /* 详细信息面板 */
        #info-panel {{
            position: absolute;
            top: 10px;
            right: 10px;
            width: 300px;
            background: rgba(26, 26, 46, 0.95);
            border-radius: 10px;
            padding: 15px;
            border: 1px solid #333;
            display: none;
        }}
        #info-panel h3 {{
            font-size: 16px;
            margin-bottom: 10px;
            color: #4fc3f7;
        }}
        #info-panel p {{
            font-size: 12px;
            color: #aaa;
            margin: 5px 0;
        }}
        
        /* 控制按钮 */
        #controls {{
            position: absolute;
            top: 10px;
            right: 320px;
            display: flex;
            gap: 5px;
        }}
        .btn {{
            background: #333;
            border: 1px solid #555;
            color: #eee;
            padding: 5px 10px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 12px;
        }}
        .btn:hover {{
            background: #444;
        }}
        .btn.active {{
            background: #4fc3f7;
            color: #000;
        }}
    </style>
</head>
<body>
    <div id="container">
        <div id="sidebar">
            <h2>📊 代码图谱分析</h2>
            <div class="stat">
                <span class="stat-label">总节点数</span>
                <span class="stat-value">{stats['total_nodes']}</span>
            </div>
            <div class="stat">
                <span class="stat-label">总边数</span>
                <span class="stat-value">{stats['total_edges']}</span>
            </div>
            <div class="stat">
                <span class="stat-label">God 节点</span>
                <span class="stat-value">{stats['god_nodes']}</span>
            </div>
            <div class="stat">
                <span class="stat-label">社区数</span>
                <span class="stat-value">{stats['communities']}</span>
            </div>
            <div style="margin-top: 15px;">
                <h3>📋 类型分布</h3>
                {''.join(f'<div class="stat"><span class="stat-label">{k}</span><span class="stat-value">{v}</span></div>' 
                         for k, v in stats['by_type'].items())}
            </div>
        </div>
        
        <div id="legend">
            <h3>🎨 图例</h3>
            <div class="legend-item"><div class="legend-dot" style="background: #e74c3c;"></div>God 节点（高连接度）</div>
            <div class="legend-item"><div class="legend-dot" style="background: #3498db;"></div>Struct（结构体）</div>
            <div class="legend-item"><div class="legend-dot" style="background: #9b59b6;"></div>Interface（接口）</div>
            <div class="legend-item"><div class="legend-dot" style="background: #2ecc71;"></div>Function（函数）</div>
            <div class="legend-item"><div class="legend-dot" style="background: #f39c12;"></div>Module（模块）</div>
        </div>
        
        <div id="info-panel">
            <h3 id="info-title">节点详情</h3>
            <p id="info-id"></p>
            <p id="info-type"></p>
            <p id="info-file"></p>
            <p id="info-community"></p>
        </div>
        
        <div id="controls">
            <button class="btn" onclick="zoomIn()">🔍+</button>
            <button class="btn" onclick="zoomOut()">🔍-</button>
            <button class="btn" onclick="resetView()">↺ 重置</button>
            <button class="btn" onclick="toggleLabels()">🏷️ 标签</button>
        </div>
        
        <svg id="graph"></svg>
    </div>
    
    <script>
        const nodes = {nodes_json};
        const edges = {edges_json};
        const godNodes = {god_json};
        
        // 设置画布
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        const svg = d3.select('#graph')
            .attr('viewBox', [0, 0, width, height]);
        
        // 添加缩放行为
        const g = svg.append('g');
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {{
                g.attr('transform', event.transform);
            }});
        svg.call(zoom);
        
        // 创建力模拟
        const simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(edges).id(d => d.id).distance(100))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collide', d3.forceCollide().radius(20));
        
        // 绘制连线
        const link = g.append('g')
            .attr('class', 'links')
            .selectAll('line')
            .data(edges)
            .join('line')
            .attr('class', d => {{
                const sourceGod = godNodes.some(gn => gn.id === d.source.id || gn.id === d.source);
                const targetGod = godNodes.some(gn => gn.id === d.target.id || gn.id === d.target);
                return sourceGod || targetGod ? 'link link-god' : 'link';
            }})
            .attr('stroke-width', d => {{
                const sourceGod = godNodes.some(gn => gn.id === d.source.id || gn.id === d.source);
                const targetGod = godNodes.some(gn => gn.id === d.target.id || gn.id === d.target);
                return sourceGod || targetGod ? 2 : 1;
            }});
        
        // 绘制节点
        const node = g.append('g')
            .attr('class', 'nodes')
            .selectAll('circle')
            .data(nodes)
            .join('circle')
            .attr('class', 'node')
            .attr('r', d => d.size)
            .attr('fill', d => d.color)
            .attr('stroke', '#fff')
            .attr('stroke-width', 0.5)
            .call(drag(simulation))
            .on('click', (event, d) => showInfo(d));
        
        // 添加标签
        let labelsVisible = true;
        const labels = g.append('g')
            .attr('class', 'labels')
            .selectAll('text')
            .data(nodes)
            .join('text')
            .text(d => d.label)
            .attr('font-size', '10px')
            .attr('fill', '#aaa')
            .attr('dx', 12)
            .attr('dy', 4);
        
        // 模拟 tick
        simulation.on('tick', () => {{
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);
            
            node
                .attr('cx', d => d.x)
                .attr('cy', d => d.y);
            
            labels
                .attr('x', d => d.x)
                .attr('y', d => d.y);
        }});
        
        // 拖拽行为
        function drag(simulation) {{
            return d3.drag()
                .on('start', (event, d) => {{
                    if (!event.active) simulation.alphaTarget(0.3).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                }})
                .on('drag', (event, d) => {{
                    d.fx = event.x;
                    d.fy = event.y;
                }})
                .on('end', (event, d) => {{
                    if (!event.active) simulation.alphaTarget(0);
                    d.fx = null;
                    d.fy = null;
                }});
        }}
        
        // 显示信息
        function showInfo(d) {{
            const panel = document.getElementById('info-panel');
            panel.style.display = 'block';
            document.getElementById('info-title').textContent = d.label;
            document.getElementById('info-id').textContent = 'ID: ' + d.id;
            document.getElementById('info-type').textContent = 'Type: ' + d.type;
            document.getElementById('info-file').textContent = 'File: ' + d.file;
            document.getElementById('info-community').textContent = 'Community: ' + (d.community >= 0 ? d.community : 'None');
        }}
        
        // 控制函数
        function zoomIn() {{
            svg.transition().duration(300).call(zoom.scaleBy, 1.5);
        }}
        
        function zoomOut() {{
            svg.transition().duration(300).call(zoom.scaleBy, 0.67);
        }}
        
        function resetView() {{
            svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity);
        }}
        
        function toggleLabels() {{
            labelsVisible = !labelsVisible;
            labels.style('display', labelsVisible ? null : 'none');
        }}
    </script>
</body>
</html>
'''
        
        return html


def generate_visualization(graph_path: str, output_path: str = None) -> str:
    """生成可视化"""
    # 读取图数据
    with open(graph_path, 'r', encoding='utf-8') as f:
        graph_data = json.load(f)
    
    # 生成 HTML
    if output_path is None:
        output_path = Path(graph_path).parent / 'graph_visualization.html'
    
    result = HTMLVisualizer.generate_html(graph_data, output_path)
    print(f"✅ 可视化已生成: {result}")
    return result


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python html_visualizer.py <graph.json> [output.html]")
        sys.exit(1)
    
    graph_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    generate_visualization(graph_path, output_path)
