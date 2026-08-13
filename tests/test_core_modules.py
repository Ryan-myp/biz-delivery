"""
核心脚本深度测试套件
覆盖：LLMAnalyzer、SmartRouter、QueryCache
目标：提升 scripts/ 核心模块覆盖率
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================
# LLMAnalyzer 测试
# ============================================================

class TestLLMAnalyzer:
    """LLM 分析器测试"""
    
    def _make_ir_cache(self, tmp_path):
        """创建 IR 缓存文件"""
        ir_data = {
            "business_logic": [
                {
                    "handler": "UserHandler",
                    "description": "用户登录业务逻辑",
                    "calls": ["auth_service", "user_repo"],
                    "control_points": ["check_password"],
                    "data_points": ["user_id", "token"],
                    "file": "handlers/user.py",
                },
                {
                    "handler": "OrderHandler",
                    "description": "下单业务逻辑",
                    "calls": ["inventory_service"],
                    "control_points": ["check_stock"],
                    "data_points": ["order_id"],
                    "file": "handlers/order.py",
                },
            ],
            "routes": [
                {
                    "handler": "UserHandler",
                    "path": "/api/login",
                    "method": "POST",
                },
                {
                    "handler": "OrderHandler",
                    "path": "/api/orders",
                    "method": "POST",
                },
            ],
            "entity_tables": [
                {"entity": "User", "table": "users", "file": "models/user.go"},
                {"entity": "Order", "table": "orders", "file": "models/order.go"},
            ],
            "error_codes": [
                {"name": "INVALID_PASSWORD", "code": "AUTH_001", "message": "密码错误", "category": "auth"},
                {"name": "USER_NOT_FOUND", "code": "AUTH_002", "message": "用户不存在", "category": "auth"},
                {"name": "NO_STOCK", "code": "ORDER_001", "message": "库存不足", "category": "order"},
            ],
            "auth_models": [
                {"model": "JWT", "expire": "24h"},
            ],
        }
        
        cache_path = tmp_path / "ir_cache.json"
        cache_path.write_text(json.dumps(ir_data), encoding="utf-8")
        return str(cache_path)
    
    def test_init_creates_instance(self, tmp_path):
        """测试初始化"""
        from scripts.llm_analyzer import LLMAnalyzer
        analyzer = LLMAnalyzer(str(tmp_path), str(tmp_path / "ir_cache.json"))
        assert analyzer.repo_path == tmp_path
        assert analyzer.ir_cache == {}
    
    def test_init_loads_existing_cache(self, tmp_path):
        """测试加载已有缓存"""
        from scripts.llm_analyzer import LLMAnalyzer
        cache_path = self._make_ir_cache(tmp_path)
        
        analyzer = LLMAnalyzer(str(tmp_path), cache_path)
        assert "business_logic" in analyzer.ir_cache
        assert len(analyzer.ir_cache["business_logic"]) == 2
    
    def test_init_missing_cache(self, tmp_path):
        """测试缓存文件不存在"""
        from scripts.llm_analyzer import LLMAnalyzer
        analyzer = LLMAnalyzer(str(tmp_path), str(tmp_path / "missing.json"))
        assert analyzer.ir_cache == {}
    
    def test_generate_business_cards(self, tmp_path):
        """测试生成业务卡片"""
        from scripts.llm_analyzer import LLMAnalyzer
        cache_path = self._make_ir_cache(tmp_path)
        
        analyzer = LLMAnalyzer(str(tmp_path), cache_path)
        cards = analyzer.generate_business_cards()
        
        assert cards["version"] == "2.0"
        assert len(cards["scenario_cards"]) == 2
        assert len(cards["entity_relationships"]) == 2
        assert len(cards["auth_models"]) == 1
        assert cards["llm_analyses"] == []
    
    def test_generate_business_cards_with_output(self, tmp_path):
        """测试输出到文件"""
        from scripts.llm_analyzer import LLMAnalyzer
        cache_path = self._make_ir_cache(tmp_path)
        output_path = tmp_path / "cards.json"
        
        analyzer = LLMAnalyzer(str(tmp_path), cache_path)
        cards = analyzer.generate_business_cards(str(output_path))
        
        assert output_path.exists()
        saved = json.loads(output_path.read_text(encoding="utf-8"))
        assert saved["version"] == "2.0"
        assert len(saved["scenario_cards"]) == 2
    
    def test_extract_scenario_cards_route_mapping(self, tmp_path):
        """测试场景卡路由映射"""
        from scripts.llm_analyzer import LLMAnalyzer
        cache_path = self._make_ir_cache(tmp_path)
        
        analyzer = LLMAnalyzer(str(tmp_path), cache_path)
        cards = analyzer._extract_scenario_cards()
        
        # UserHandler 应该映射到 POST /api/login
        user_card = next(c for c in cards if c["scenario"] == "UserHandler")
        assert user_card["entry_point"] == "POST /api/login"
        assert user_card["route"] == "/api/login"
        assert user_card["method"] == "POST"
        assert len(user_card["call_chain"]) == 2
        assert len(user_card["control_points"]) == 1
    
    def test_extract_scenario_cards_empty(self, tmp_path):
        """测试空 business_logic"""
        from scripts.llm_analyzer import LLMAnalyzer
        empty_cache = tmp_path / "empty.json"
        empty_cache.write_text(json.dumps({}), encoding="utf-8")
        
        analyzer = LLMAnalyzer(str(tmp_path), str(empty_cache))
        cards = analyzer._extract_scenario_cards()
        assert cards == []
    
    def test_extract_entity_relationships(self, tmp_path):
        """测试实体关系提取"""
        from scripts.llm_analyzer import LLMAnalyzer
        cache_path = self._make_ir_cache(tmp_path)
        
        analyzer = LLMAnalyzer(str(tmp_path), cache_path)
        rels = analyzer._extract_entity_relationships()
        assert len(rels) == 2
        assert rels[0]["entity"] == "User"
        assert rels[0]["table"] == "users"
    
    def test_extract_error_categories(self, tmp_path):
        """测试错误分类"""
        from scripts.llm_analyzer import LLMAnalyzer
        cache_path = self._make_ir_cache(tmp_path)
        
        analyzer = LLMAnalyzer(str(tmp_path), cache_path)
        cats = analyzer._extract_error_categories()
        
        assert "auth" in cats
        assert "order" in cats
        assert len(cats["auth"]) == 2
        assert cats["auth"][0]["name"] == "INVALID_PASSWORD"
        assert cats["auth"][0]["code"] == "AUTH_001"
    
    def test_extract_error_categories_empty(self, tmp_path):
        """测试空错误码"""
        from scripts.llm_analyzer import LLMAnalyzer
        empty_cache = tmp_path / "empty.json"
        empty_cache.write_text(json.dumps({}), encoding="utf-8")
        
        analyzer = LLMAnalyzer(str(tmp_path), str(empty_cache))
        cats = analyzer._extract_error_categories()
        assert cats == {}
    
    def test_extract_auth_models(self, tmp_path):
        """测试认证模型提取"""
        from scripts.llm_analyzer import LLMAnalyzer
        cache_path = self._make_ir_cache(tmp_path)
        
        analyzer = LLMAnalyzer(str(tmp_path), cache_path)
        auth = analyzer._extract_auth_models()
        assert len(auth) == 1
        assert auth[0]["model"] == "JWT"


# ============================================================
# QueryCache 测试
# ============================================================

class TestQueryCache:
    """查询缓存测试"""
    
    def test_set_and_get(self, tmp_path):
        """测试设置和获取"""
        from scripts.query_cache import QueryCache
        cache = QueryCache(tmp_path)
        
        cache.set("查询用户", ["code", "api_docs"], {"scopes": ["code"]})
        result = cache.get("查询用户", ["code", "api_docs"])
        
        assert result is not None
        assert result["scopes"] == ["code"]
        assert "cached_at" in result
    
    def test_get_missing(self, tmp_path):
        """测试获取不存在的缓存"""
        from scripts.query_cache import QueryCache
        cache = QueryCache(tmp_path)
        
        result = cache.get("不存在的查询", ["code"])
        assert result is None
    
    def test_get_expired(self, tmp_path):
        """测试过期缓存"""
        from scripts.query_cache import QueryCache
        cache = QueryCache(tmp_path, ttl_seconds=0)  # 立即过期
        
        cache.set("查询", ["code"], {"scopes": ["code"]})
        result = cache.get("查询", ["code"])
        assert result is None
    
    def test_key_uniqueness(self, tmp_path):
        """测试 key 唯一性"""
        from scripts.query_cache import QueryCache
        cache = QueryCache(tmp_path)
        
        cache.set("查询A", ["code"], {"data": "A"})
        cache.set("查询A", ["code", "schema"], {"data": "B"})
        
        r1 = cache.get("查询A", ["code"])
        r2 = cache.get("查询A", ["code", "schema"])
        
        assert r1["data"] == "A"
        assert r2["data"] == "B"
    
    def test_clear_all(self, tmp_path):
        """测试清除所有缓存"""
        from scripts.query_cache import QueryCache
        cache = QueryCache(tmp_path)
        
        cache.set("查询1", ["code"], {"a": 1})
        cache.set("查询2", ["schema"], {"b": 2})
        
        cache.clear()
        
        assert cache.get("查询1", ["code"]) is None
        assert cache.get("查询2", ["schema"]) is None
    
    def test_clear_with_query(self, tmp_path):
        """测试按关键词清除"""
        from scripts.query_cache import QueryCache
        cache = QueryCache(tmp_path)
        
        cache.set("查询用户信息", ["code"], {"a": 1})
        cache.set("查询订单信息", ["code"], {"b": 2})
        
        cache.clear("用户")
        
        assert cache.get("查询用户信息", ["code"]) is None
        # 订单缓存不受影响
        assert cache.get("查询订单信息", ["code"]) is not None
    
    def test_clear_corrupted_file(self, tmp_path):
        """测试清除损坏文件"""
        from scripts.query_cache import QueryCache
        cache = QueryCache(tmp_path)
        
        # 创建损坏文件
        cache.set("查询", ["code"], {"a": 1})
        key_file = list(tmp_path.glob("*.json"))[0]
        key_file.write_text("这不是 JSON", encoding="utf-8")
        
        # 不应报错
        cache.clear("查询")
    
    def test_dir_created(self, tmp_path):
        """测试目录自动创建"""
        from scripts.query_cache import QueryCache
        nested = tmp_path / "a" / "b" / "c"
        cache = QueryCache(nested)
        assert nested.exists()


# ============================================================
# SmartRouter 测试
# ============================================================

class TestSmartRouter:
    """智能路由测试"""
    
    def test_extract_intent_create(self):
        """测试创建意图"""
        from scripts.smart_routing import extract_intent
        intent, confidence = extract_intent("帮我创建用户")
        assert intent == "create"
        assert confidence > 0
    
    def test_extract_intent_query(self):
        """测试查询意图"""
        from scripts.smart_routing import extract_intent
        intent, confidence = extract_intent("查询用户信息")
        assert intent == "query"
        assert confidence > 0
    
    def test_extract_intent_debug(self):
        """测试调试意图"""
        from scripts.smart_routing import extract_intent
        intent, confidence = extract_intent("帮我修复这个错误")
        assert intent == "debug"
    
    def test_extract_intent_unknown(self):
        """测试未知意图"""
        from scripts.smart_routing import extract_intent
        intent, confidence = extract_intent("xyzxyz")
        assert intent == "unknown"
        assert confidence == 0.0
    
    def test_extract_intent_english(self):
        """测试英文查询"""
        from scripts.smart_routing import extract_intent
        intent, confidence = extract_intent("how to delete user")
        assert intent in ("delete", "question")
    
    def test_get_scope_weights_known(self):
        """测试已知意图权重"""
        from scripts.smart_routing import get_scope_weights
        weights = get_scope_weights("create")
        assert weights["code"] == 0.8
    
    def test_get_scope_weights_unknown(self):
        """测试未知意图默认权重"""
        from scripts.smart_routing import get_scope_weights
        weights = get_scope_weights("unknown_intent")
        assert weights["code"] == 0.7
        assert weights["api_docs"] == 0.7
    
    def test_get_query_type(self):
        """测试查询类型映射"""
        from scripts.smart_routing import get_query_type
        assert get_query_type("create") == "code"
        assert get_query_type("callchain") == "callgraph"
        assert get_query_type("dataflow") == "dataflow"
        assert get_query_type("unknown") == "code"
    
    def test_select_scopes_creates(self):
        """测试创建意图的 scope 选择"""
        from scripts.smart_routing import select_scopes
        scopes = select_scopes("创建用户", ["code", "api_docs", "schema"], top_n=2)
        assert "code" in scopes  # 创建意图优先 code
    
    def test_select_scopes_top_n(self):
        """测试 top_n 限制"""
        from scripts.smart_routing import select_scopes
        scopes = select_scopes("查询用户", ["code", "api_docs", "schema", "callgraph"], top_n=2)
        assert len(scopes) == 2
    
    def test_route_query_no_cache(self, tmp_path):
        """测试无缓存路由"""
        from scripts.smart_routing import SmartRouter
        router = SmartRouter(cache_dir=None)
        
        scopes, meta = router.route_query("创建用户", ["code", "api_docs"])
        
        assert meta["from_cache"] is False
        assert "intent" in meta
        assert "confidence" in meta
        assert "query_type" in meta
    
    def test_route_query_with_cache(self, tmp_path):
        """测试带缓存路由"""
        from scripts.smart_routing import SmartRouter
        router = SmartRouter(cache_dir=tmp_path)
        
        scopes1, meta1 = router.route_query("查询用户", ["code", "api_docs"])
        scopes2, meta2 = router.route_query("查询用户", ["code", "api_docs"])
        
        assert meta1["from_cache"] is False
        assert meta2["from_cache"] is True
        assert scopes1 == scopes2
    
    def test_route_query_cache_different_scopes(self, tmp_path):
        """测试不同 scopes 的缓存区分"""
        from scripts.smart_routing import SmartRouter
        router = SmartRouter(cache_dir=tmp_path)
        
        router.route_query("查询用户", ["code"])
        _, meta = router.route_query("查询用户", ["code", "schema"])
        
        assert meta["from_cache"] is False
