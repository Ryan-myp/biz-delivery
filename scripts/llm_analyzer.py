#!/usr/bin/env python3
"""
LLM Analyzer — 代码语义分析层

核心思路：把代码片段喂给 LLM，让它生成自然语言业务描述。
"""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


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

    def _call_llm(self, prompt: str) -> Optional[str]:
        """调用 LLM — 优先用 Hermes agent context，否则用 Agnes API"""
        # 方案 1: 用 hermes CLI
        try:
            result = subprocess.run(
                ['hermes', 'chat', '--text', prompt],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass
        
        # 方案 2: 用 Agnes API
        api_key = os.environ.get('HERMES_LLM_API_KEY', '')
        if not api_key:
            api_key = os.environ.get('AGNES_API_KEY', '')
        
        if api_key:
            try:
                import urllib.request
                payload = json.dumps({
                    "model": "agnes-2.0-flash",
                    "messages": [
                        {"role": "system", "content": "你是一个代码分析专家。请用中文描述代码的业务逻辑。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                }).encode('utf-8')
                
                req = urllib.request.Request(
                    'https://apihub.agnes-ai.com/v1/chat/completions',
                    data=payload,
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {api_key}',
                    }
                )
                
                with urllib.request.urlopen(req, timeout=120) as resp:
                    llm_response = json.loads(resp.read().decode('utf-8'))
                    return llm_response['choices'][0]['message']['content']
            except Exception as e:
                print(f"  LLM API failed: {e}")
        
        return None

    def analyze_scenario(self, scenario: dict) -> Optional[dict]:
        """用 LLM 分析单个场景的业务逻辑"""
        handler = scenario.get('handler', '')
        route = scenario.get('route', '')
        method = scenario.get('method', '')
        calls = scenario.get('calls', [])
        control_points = scenario.get('control_points', [])
        data_points = scenario.get('data_points', [])
        file = scenario.get('file', '')
        
        if not handler:
            return None
        
        prompt = f"""你是一个资深 Go 后端架构师。请分析以下 handler 的业务逻辑，用中文描述。

Handler: {handler}
Route: {method} {route}
File: {file}

调用链:
{chr(10).join(f"- {c}" for c in calls[:10])}

控制流:
{chr(10).join(f"- {cp}" for cp in control_points[:5])}

数据流:
{chr(10).join(f"- {dp}" for dp in data_points[:5])}

请回答：
1. 这个 handler 的业务目标是什么？
2. 它的主要处理流程是怎样的？（用自然语言描述，不要代码）
3. 涉及哪些关键实体和数据表？
4. 有哪些重要的业务规则和约束？
5. 可能的异常场景有哪些？

请用简洁的中文回答，每个问题 1-2 句话。"""
        
        llm_result = self._call_llm(prompt)
        if llm_result:
            # 尝试提取结构化数据
            result = {
                'handler': handler,
                'route': route,
                'method': method,
                'file': file,
                'llm_analysis': llm_result,
            }
            return result
        return None

    def analyze_all_scenarios(self, max_scenarios: int = 10) -> List[dict]:
        """分析所有场景，生成业务描述"""
        business_logic = self.ir_cache.get('business_logic', [])[:max_scenarios]
        results = []
        
        for i, bl in enumerate(business_logic):
            print(f"  Analyzing scenario {i+1}/{len(business_logic)}: {bl.get('handler', '?')}")
            result = self.analyze_scenario(bl)
            if result:
                results.append(result)
        
        return results

    def generate_business_cards(self, output_path: str = None) -> dict:
        """生成完整的业务卡片包"""
        # 1. 基础分析（无需 LLM）
        scenario_cards = self._extract_scenario_cards()
        entity_relationships = self._extract_entity_relationships()
        error_categories = self._extract_error_categories()
        auth_models = self._extract_auth_models()
        
        # 2. LLM 分析（需要 API key）
        llm_analyses = []
        try:
            llm_analyses = self.analyze_all_scenarios(max_scenarios=10)
            print(f"  LLM analyzed {len(llm_analyses)} scenarios")
        except Exception as e:
            print(f"  LLM analysis skipped: {e}")
        
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
