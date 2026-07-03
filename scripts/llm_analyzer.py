from typing import Dict, List, Optional
from pathlib import Path
import json

class LLMAnalyzer:
    """LLM 分析器 — 从代码片段生成业务语义描述"""

    def __init__(self, repo_path: str, ir_cache_path: str):
        self.repo_path = Path(repo_path)
        self.ir_cache_path = Path(ir_cache_path)
        self.ir_cache = self._load_ir_cache()

    def _load_ir_cache(self) -> dict:
        if self.ir_cache_path.exists():
            with open(self.ir_cache_path) as f:
                return json.load(f)
        return {}




    def generate_business_cards(self, output_path: str = None) -> dict:
        """生成完整的业务卡片包"""
        # 1. 基础分析（无需 LLM）
        scenario_cards = self._extract_scenario_cards()
        entity_relationships = self._extract_entity_relationships()
        error_categories = self._extract_error_categories()
        auth_models = self._extract_auth_models()
        
        # 2. LLM 分析（需要 API key，当前用启发式兜底）
        llm_analyses = []
        # 如果有 API key，取消下面这行的注释
        # try:
        #     llm_analyses = self.analyze_all_scenarios(max_scenarios=10)
        #     print(f"  LLM analyzed {len(llm_analyses)} scenarios")
        # except Exception as e:
        #     print(f"  LLM analysis skipped: {e}")
        
        cards = {
            'version': '2.0',
            'scenario_cards': scenario_cards,
            'entity_relationships': entity_relationships,
            'error_categories': error_categories,
            'auth_models': auth_models,
            'llm_analyses': llm_analyses,
        }
        
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(cards, f, indent=2, ensure_ascii=False)
        
        return cards

    def _extract_scenario_cards(self) -> List[Dict]:
        """从 business_logic 提取场景卡"""
        business_logic = self.ir_cache.get('business_logic', [])
        routes = self.ir_cache.get('routes', [])
        
        route_map = {}
        for r in routes:
            handler = r.get('handler', '')
            if handler:
                route_map[handler] = {
                    'path': r.get('path', ''),
                    'method': r.get('method', ''),
                }
        
        cards = []
        for bl in business_logic:
            handler = bl.get('handler', '')
            route_info = route_map.get(handler, {})
            
            cards.append({
                'scenario': handler,
                'entry_point': f"{route_info.get('method', 'GET')} {route_info.get('path', '')}",
                'description': bl.get('description', ''),
                'call_chain': bl.get('calls', [])[:10],
                'control_points': bl.get('control_points', [])[:5],
                'data_points': bl.get('data_points', [])[:5],
                'file': bl.get('file', ''),
                'route': route_info.get('path', ''),
                'method': route_info.get('method', ''),
            })
        
        return cards

    def _extract_entity_relationships(self) -> List[Dict]:
        entity_tables = self.ir_cache.get('entity_tables', [])
        return [
            {'entity': et.get('entity', ''), 'table': et.get('table', ''), 'file': et.get('file', '')}
            for et in entity_tables
        ]

    def _extract_error_categories(self) -> Dict[str, List[Dict]]:
        error_codes = self.ir_cache.get('error_codes', [])
        categories = {}
        for ec in error_codes:
            cat = ec.get('category', 'unknown')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append({
                'name': ec.get('name', ''),
                'code': ec.get('code', ''),
                'message': ec.get('message', ''),
            })
        return categories

    def _extract_auth_models(self) -> List[Dict]:
        return self.ir_cache.get('auth_models', [])


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='LLM Analyzer')
    parser.add_argument('--repo-path', required=True)
    parser.add_argument('--ir-cache', required=True)
    parser.add_argument('--output', default='business_cards.json')
    args = parser.parse_args()

    analyzer = LLMAnalyzer(args.repo_path, args.ir_cache)
    cards = analyzer.generate_business_cards(args.output)
    print(f"Generated {len(cards['scenario_cards'])} scenario cards")
    print(f"Generated {len(cards['llm_analyses'])} LLM analyses")
    print(f"Saved to {args.output}")
