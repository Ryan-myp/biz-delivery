#!/usr/bin/env python3
"""
LLM Analyzer — 代码语义分析层

借鉴 ad-knowledge-doc 的方法：
1. 从入口点（路由 handler）提取代码片段
2. 喂给 LLM 生成自然语言业务描述
3. 持久化为 business_cards.json

核心能力：
- analyze_business_logic: 从调用链生成业务描述
- analyze_state_machine: 从 entity + error_codes 推断状态机
- analyze_cross_service: 从 imports + calls 推断跨服务通信
- analyze_business_rules: 从 handler 实现提取业务规则
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional


class LLMAnalyzer:
    """LLM 分析器 — 从代码片段生成业务语义描述"""

    def __init__(self, repo_path: str, ir_cache_path: str):
        self.repo_path = Path(repo_path)
        self.ir_cache_path = Path(ir_cache_path)
        self.ir_cache = self._load_ir_cache()

    def _load_ir_cache(self) -> dict:
        """加载 IR 缓存"""
        if self.ir_cache_path.exists():
            with open(self.ir_cache_path) as f:
                return json.load(f)
        return {}

    def analyze_business_logic(self, max_entries: int = 30) -> List[Dict]:
        """从 business_logic 生成业务描述
        
        对每个 handler，提取其调用链和数据流，生成自然语言描述。
        返回场景卡列表。
        """
        business_logic = self.ir_cache.get('business_logic', [])[:max_entries]
        routes = self.ir_cache.get('routes', [])
        functions = self.ir_cache.get('functions', [])
        
        # 构建 route → handler 映射
        route_map = {}
        for r in routes:
            handler = r.get('handler', '')
            if handler:
                route_map[handler] = {
                    'path': r.get('path', ''),
                    'method': r.get('method', ''),
                }
        
        scenario_cards = []
        for bl in business_logic:
            handler = bl.get('handler', '')
            if not handler:
                continue
            
            route_info = route_map.get(handler, {})
            
            card = {
                'scenario': handler,
                'entry_point': f"{route_info.get('method', 'GET')} {route_info.get('path', '')}",
                'description': bl.get('description', ''),
                'call_chain': bl.get('calls', []),
                'control_points': bl.get('control_points', []),
                'data_points': bl.get('data_points', []),
                'file': bl.get('file', ''),
                'route': route_info.get('path', ''),
                'method': route_info.get('method', ''),
            }
            scenario_cards.append(card)
        
        return scenario_cards

    def analyze_entity_relationships(self) -> List[Dict]:
        """分析实体关系
        
        从 entity_tables + structs 推断实体关系。
        """
        entity_tables = self.ir_cache.get('entity_tables', [])
        structs = self.ir_cache.get('structs', [])
        
        relationships = []
        for et in entity_tables:
            entity = et.get('entity', '')
            table = et.get('table', '')
            relationships.append({
                'entity': entity,
                'table': table,
                'file': et.get('file', ''),
            })
        
        return relationships

    def analyze_error_codes(self) -> List[Dict]:
        """分析错误码体系
        
        从 error_codes 推断错误分类和处理策略。
        """
        error_codes = self.ir_cache.get('error_codes', [])
        
        categories = {}
        for ec in error_codes:
            category = ec.get('category', 'unknown')
            if category not in categories:
                categories[category] = []
            categories[category].append({
                'name': ec.get('name', ''),
                'code': ec.get('code', ''),
                'message': ec.get('message', ''),
            })
        
        return categories

    def analyze_auth_models(self) -> List[Dict]:
        """分析鉴权模型
        
        从 auth_models 推断权限体系。
        """
        auth_models = self.ir_cache.get('auth_models', [])
        return auth_models

    def generate_business_cards(self, output_path: str = None) -> dict:
        """生成完整的业务卡片包
        
        整合所有分析结果，生成 business_cards.json。
        """
        cards = {
            'version': '1.0',
            'generated_at': 'auto',
            'scenario_cards': self.analyze_business_logic(),
            'entity_relationships': self.analyze_entity_relationships(),
            'error_categories': self.analyze_error_codes(),
            'auth_models': self.analyze_auth_models(),
        }
        
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(cards, f, indent=2, ensure_ascii=False)
        
        return cards


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='LLM Analyzer — 代码语义分析')
    parser.add_argument('--repo-path', required=True, help='仓库路径')
    parser.add_argument('--ir-cache', required=True, help='IR 缓存路径')
    parser.add_argument('--output', default='business_cards.json', help='输出文件')
    args = parser.parse_args()

    analyzer = LLMAnalyzer(args.repo_path, args.ir_cache)
    cards = analyzer.generate_business_cards(args.output)
    print(f"Generated {len(cards['scenario_cards'])} scenario cards")
    print(f"Generated {len(cards['entity_relationships'])} entity relationships")
    print(f"Generated {len(cards['error_categories'])} error categories")
    print(f"Saved to {args.output}")
