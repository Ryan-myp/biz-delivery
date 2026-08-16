"""
Visualization Dashboard - 可视化仪表盘
基于Plotly的质量趋势、缺陷分布、性能指标可视化

核心功能:
  1. 质量趋势图 - 折线图展示质量评分变化
  2. 缺陷分布图 - 饼图/柱状图展示缺陷类型分布
  3. 领域覆盖图 - 雷达图展示各领域覆盖情况
  4. 性能指标图 - 仪表盘展示关键性能指标
  5. 项目对比图 - 柱状图对比不同项目质量
"""
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional


class VisualizationDashboard:
    """可视化仪表盘"""

    def __init__(self, history_data: Optional[List[Dict]] = None):
        self.history = history_data or []
        self.colors = {
            'primary': '#4361ee',
            'success': '#2ec4b6',
            'warning': '#ff9f1c',
            'danger': '#e71d36',
            'info': '#4895ef',
            'light': '#f8f9fa',
            'dark': '#212529',
        }

    def generate_quality_trend_chart(self, days: int = 30) -> go.Figure:
        """生成质量趋势图"""
        cutoff = datetime.now() - timedelta(days=days)
        recent = [h for h in self.history if datetime.fromisoformat(h['timestamp']) > cutoff]

        if not recent:
            return self._create_empty_chart("暂无质量数据")

        dates = [datetime.fromisoformat(h['timestamp']).strftime('%m-%d') for h in recent]
        scores = [h['percentage'] for h in recent]
        ratings = [h['rating'] for h in recent]

        fig = go.Figure()

        # 主线条
        fig.add_trace(go.Scatter(
            x=dates, y=scores,
            mode='lines+markers',
            name='质量得分',
            line=dict(color=self.colors['primary'], width=3),
            marker=dict(size=10),
        ))

        # 阈值线
        fig.add_hline(y=90, line_dash="dash", line_color=self.colors['success'],
                     annotation_text="A+ (90%)")
        fig.add_hline(y=80, line_dash="dash", line_color=self.colors['info'],
                     annotation_text="A (80%)")
        fig.add_hline(y=60, line_dash="dash", line_color=self.colors['warning'],
                     annotation_text="通过线 (60%)")

        fig.update_layout(
            title=dict(text='📈 质量趋势 (最近30天)', font=dict(size=20)),
            xaxis_title='日期',
            yaxis_title='质量得分',
            yaxis=dict(range=[0, 100]),
            template='plotly_white',
            height=400,
        )

        return fig

    def generate_defect_distribution_chart(self, defects: Optional[List[Dict]] = None) -> go.Figure:
        """生成缺陷分布图"""
        if not defects:
            defects = [
                {'type': '安全', 'count': 15},
                {'type': '性能', 'count': 8},
                {'type': '架构', 'count': 12},
                {'type': '领域', 'count': 25},
                {'type': '代码风格', 'count': 10},
            ]

        types = [d['type'] for d in defects]
        counts = [d['count'] for d in defects]

        fig = go.Figure(data=[
            go.Pie(
                labels=types,
                values=counts,
                hole=0.4,
                marker=dict(colors=[
                    self.colors['danger'], self.colors['warning'],
                    self.colors['info'], self.colors['primary'], self.colors['success']
                ]),
                textinfo='label+percent',
                textposition='outside',
            )
        ])

        fig.update_layout(
            title=dict(text='🥧 缺陷类型分布', font=dict(size=20)),
            template='plotly_white',
            height=400,
        )

        return fig

    def generate_domain_coverage_chart(self, coverage_data: Optional[Dict] = None) -> go.Figure:
        """生成领域覆盖雷达图"""
        if not coverage_data:
            coverage_data = {
                'advertising': 95, 'agent': 88, 'ecommerce': 82,
                'finance': 90, 'cloud_native': 85, 'devops': 88,
                'security': 92, 'ml_ops': 85, 'gaming': 78,
                'iot': 80, 'saas': 82, 'social': 75, 'logistics': 78,
            }

        domains = list(coverage_data.keys())
        scores = list(coverage_data.values())

        # 闭合雷达图
        domains.append(domains[0])
        scores.append(scores[0])

        fig = go.Figure()

        fig.add_trace(go.Scatterpolar(
            r=scores,
            theta=domains,
            fill='toself',
            name='覆盖率',
            line_color=self.colors['primary'],
            fillcolor=self.colors['primary'] + '30',
        ))

        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100]),
            ),
            showlegend=False,
            title=dict(text='🎯 领域覆盖雷达图', font=dict(size=20)),
            template='plotly_white',
            height=450,
        )

        return fig

    def generate_performance_gauge(self, metrics: Optional[Dict] = None) -> go.Figure:
        """生成性能仪表盘"""
        if not metrics:
            metrics = {
                'qps': 50000,
                'p99_latency': 85,
                'availability': 99.99,
                'error_rate': 0.01,
            }

        fig = make_subplots(
            rows=2, cols=2,
            specs=[[{"type": "indicator"}, {"type": "indicator"}],
                   [{"type": "indicator"}, {"type": "indicator"}]],
            subplot_titles=('QPS', 'P99延迟(ms)', '可用性(%)', '错误率(%)'),
        )

        # QPS
        fig.add_trace(go.Indicator(
            mode="number+gauge",
            value=metrics['qps'],
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={'axis': {'range': [0, 100000]}, 'bar': {'color': self.colors['primary']}},
        ), row=1, col=1)

        # P99延迟
        fig.add_trace(go.Indicator(
            mode="number+gauge",
            value=metrics['p99_latency'],
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={'axis': {'range': [0, 200]}, 'bar': {'color': self.colors['success'] if metrics['p99_latency'] < 100 else self.colors['warning']}},
        ), row=1, col=2)

        # 可用性
        fig.add_trace(go.Indicator(
            mode="number+gauge",
            value=metrics['availability'],
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={'axis': {'range': [0, 100]}, 'bar': {'color': self.colors['success']}},
        ), row=2, col=1)

        # 错误率
        fig.add_trace(go.Indicator(
            mode="number+gauge",
            value=metrics['error_rate'],
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={'axis': {'range': [0, 1]}, 'bar': {'color': self.colors['success']}},
        ), row=2, col=2)

        fig.update_layout(
            title=dict(text='⚡ 性能指标仪表盘', font=dict(size=20)),
            height=500,
            template='plotly_white',
        )

        return fig

    def generate_project_comparison_chart(self, projects: Optional[List[Dict]] = None) -> go.Figure:
        """生成项目对比图"""
        if not projects:
            projects = [
                {'name': '广告竞价', 'score': 85, 'rating': 'A'},
                {'name': 'Agent平台', 'score': 90, 'rating': 'A+'},
                {'name': '电商平台', 'score': 78, 'rating': 'B+'},
                {'name': '金融交易', 'score': 92, 'rating': 'A+'},
                {'name': '云原生', 'score': 88, 'rating': 'A'},
            ]

        names = [p['name'] for p in projects]
        scores = [p['score'] for p in projects]
        colors = [self.colors['success'] if s >= 80 else self.colors['warning'] if s >= 60 else self.colors['danger']
                 for s in scores]

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=names,
            y=scores,
            marker_color=colors,
            text=scores,
            textposition='outside',
        ))

        fig.add_hline(y=60, line_dash="dash", line_color=self.colors['warning'],
                     annotation_text="通过线")
        fig.add_hline(y=80, line_dash="dash", line_color=self.colors['success'],
                     annotation_text="优秀线")

        fig.update_layout(
            title=dict(text='📊 项目质量对比', font=dict(size=20)),
            xaxis_title='项目',
            yaxis_title='质量得分',
            yaxis=dict(range=[0, 100]),
            template='plotly_white',
            height=400,
        )

        return fig

    def generate_full_dashboard(self, output_path: str = './dashboard.html'):
        """生成完整仪表盘HTML"""
        from plotly.io import to_html

        # 创建所有图表
        trend_chart = to_html(self.generate_quality_trend_chart(), full_html=False, include_plotlyjs=False)
        defect_chart = to_html(self.generate_defect_distribution_chart(), full_html=False, include_plotlyjs=False)
        coverage_chart = to_html(self.generate_domain_coverage_chart(), full_html=False, include_plotlyjs=False)
        perf_chart = to_html(self.generate_performance_gauge(), full_html=False, include_plotlyjs=False)
        compare_chart = to_html(self.generate_project_comparison_chart(), full_html=False, include_plotlyjs=False)

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>biz-delivery 质量仪表盘</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .header {{ text-align: center; padding: 20px; background: white; border-radius: 10px; margin-bottom: 20px; }}
        .header h1 {{ margin: 0; color: #333; }}
        .header p {{ margin: 10px 0 0; color: #666; }}
        .grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }}
        .card {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .card.full {{ grid-column: span 2; }}
        .metric {{ display: flex; justify-content: space-around; padding: 20px; }}
        .metric-item {{ text-align: center; }}
        .metric-value {{ font-size: 36px; font-weight: bold; color: #4361ee; }}
        .metric-label {{ color: #666; margin-top: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 biz-delivery 质量仪表盘</h1>
        <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="metric">
        <div class="metric-item">
            <div class="metric-value">{len(self.history)}</div>
            <div class="metric-label">审查次数</div>
        </div>
        <div class="metric-item">
            <div class="metric-value">15</div>
            <div class="metric-label">覆盖领域</div>
        </div>
        <div class="metric-item">
            <div class="metric-value">275+</div>
            <div class="metric-label">专家规则</div>
        </div>
        <div class="metric-item">
            <div class="metric-value">34</div>
            <div class="metric-label">知识库文档</div>
        </div>
    </div>

    <div class="grid">
        <div class="card full">
            <div id="trend-chart"></div>
        </div>
        <div class="card">
            <div id="defect-chart"></div>
        </div>
        <div class="card">
            <div id="coverage-chart"></div>
        </div>
        <div class="card full">
            <div id="perf-chart"></div>
        </div>
        <div class="card full">
            <div id="compare-chart"></div>
        </div>
    </div>

    <script>
        {trend_chart}
        Plotly.newPlot('trend-chart', {trend_chart.split('Plotly.newPlot(')[1].split(')')[0] + ')'}, {{}});
        
        {defect_chart}
        Plotly.newPlot('defect-chart', {defect_chart.split('Plotly.newPlot(')[1].split(')')[0] + ')'}, {{}});
        
        {coverage_chart}
        Plotly.newPlot('coverage-chart', {coverage_chart.split('Plotly.newPlot(')[1].split(')')[0] + ')'}, {{}});
        
        {perf_chart}
        Plotly.newPlot('perf-chart', {perf_chart.split('Plotly.newPlot(')[1].split(')')[0] + ')'}, {{}});
        
        {compare_chart}
        Plotly.newPlot('compare-chart', {compare_chart.split('Plotly.newPlot(')[1].split(')')[0] + ')'}, {{}});
    </script>
</body>
</html>"""

        Path(output_path).write_text(html_content, encoding='utf-8')
        return output_path

    def _create_empty_chart(self, message: str) -> go.Figure:
        """创建空图表"""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref='paper', yref='paper',
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20, color='#999'),
        )
        fig.update_layout(template='plotly_white', height=300)
        return fig


if __name__ == '__main__':
    import sys
    from pathlib import Path

    # 模拟历史数据
    history = [
        {'timestamp': (datetime.now() - timedelta(days=i)).isoformat(),
         'percentage': 70 + i * 2, 'rating': 'B+' if i < 5 else 'A'}
        for i in range(10)
    ]

    dashboard = VisualizationDashboard(history)
    output = dashboard.generate_full_dashboard('./dashboard.html')
    print(f"✅ 仪表盘已生成: {output}")
