#!/usr/bin/env python3
"""
MultiModelRouter — 多模型智能路由

职责：
  - 根据任务类型选择最佳模型
  - 模型性能特征库
  - 成本/速度/质量权衡
  - 故障自动降级

设计原则：
  - 配置驱动，无需修改代码
  - 支持热更新模型配置
  - 可插拔的路由策略
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class ModelCapability(Enum):
    """模型能力标签"""
    CODE = "code"           # 代码生成
    ANALYSIS = "analysis"   # 分析推理
    CREATIVE = "creative"   # 创意写作
    FAST = "fast"           # 快速响应
    ACCURATE = "accurate"   # 高精度
    LONG_CTX = "long_context"  # 长上下文
    CHEAP = "cheap"         # 低成本


@dataclass
class ModelProfile:
    """模型配置档案"""
    id: str
    name: str
    provider: str  # "agnes", "openai", "anthropic", "local"
    
    # 能力评分 (0-100)
    capabilities: Dict[str, int] = field(default_factory=dict)
    
    # 性能参数
    max_tokens: int = 8000
    context_window: int = 32000
    rate_limit: int = 60  # 请求/分钟
    
    # 成本参数
    cost_per_token: float = 0.00001
    
    # 特征标签
    tags: List[str] = field(default_factory=list)
    
    # 可用性
    enabled: bool = True
    fallback_model: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "capabilities": self.capabilities,
            "max_tokens": self.max_tokens,
            "context_window": self.context_window,
            "rate_limit": self.rate_limit,
            "cost_per_token": self.cost_per_token,
            "tags": self.tags,
            "enabled": self.enabled,
            "fallback_model": self.fallback_model,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ModelProfile':
        return cls(**data)


class RoutingStrategy(Enum):
    """路由策略"""
    BEST_QUALITY = "best_quality"      # 最佳质量
    FASTEST = "fastest"               # 最快响应
    CHEAPEST = "cheapest"             # 最经济
    BALANCED = "balanced"             # 平衡（默认）
    CONTEXT_AWARE = "context_aware"   # 上下文感知


# 内置模型配置
DEFAULT_MODELS = {
    "agnes-flash": ModelProfile(
        id="agnes-flash",
        name="Agnes Flash",
        provider="agnes",
        capabilities={
            "code": 85,
            "analysis": 80,
            "creative": 75,
            "fast": 95,
            "accurate": 70,
            "long_context": 60,
        },
        max_tokens=4000,
        context_window=8000,
        rate_limit=100,
        cost_per_token=0.000005,
        tags=["fast", "code", "analysis"],
        enabled=True,
    ),
    "agnes-pro": ModelProfile(
        id="agnes-pro",
        name="Agnes Pro",
        provider="agnes",
        capabilities={
            "code": 95,
            "analysis": 92,
            "creative": 88,
            "fast": 60,
            "accurate": 95,
            "long_context": 85,
        },
        max_tokens=16000,
        context_window=32000,
        rate_limit=30,
        cost_per_token=0.00002,
        tags=["accurate", "code", "analysis", "long_context"],
        enabled=True,
        fallback_model="agnes-flash",
    ),
    "agnes-mini": ModelProfile(
        id="agnes-mini",
        name="Agnes Mini",
        provider="agnes",
        capabilities={
            "code": 70,
            "analysis": 65,
            "creative": 60,
            "fast": 98,
            "accurate": 55,
            "long_context": 40,
        },
        max_tokens=2000,
        context_window=4000,
        rate_limit=200,
        cost_per_token=0.000002,
        tags=["fast", "cheap"],
        enabled=True,
    ),
}


class MultiModelRouter:
    """多模型智能路由器"""
    
    def __init__(self, config_path: str = None):
        self.models: Dict[str, ModelProfile] = dict(DEFAULT_MODELS)
        self.strategy = RoutingStrategy.BALANCED
        self.stats: Dict[str, Dict] = {}  # 模型使用统计
        self.config_path = config_path
        
        if config_path:
            self._load_config(config_path)
    
    def _load_config(self, path: str):
        """加载模型配置"""
        p = Path(path)
        if p.exists():
            try:
                data = json.loads(p.read_text())
                for model_id, model_data in data.get("models", {}).items():
                    self.models[model_id] = ModelProfile.from_dict(model_data)
            except Exception as e:
                print(f"Failed to load model config: {e}")
    
    def _save_config(self, path: str):
        """保存模型配置"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {"models": {m.id: m.to_dict() for m in self.models.values()}}
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    def register_model(self, profile: ModelProfile):
        """注册新模型"""
        self.models[profile.id] = profile
        self._track_init(profile.id)
    
    def _track_init(self, model_id: str):
        """初始化统计"""
        if model_id not in self.stats:
            self.stats[model_id] = {
                "requests": 0,
                "success": 0,
                "errors": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "avg_latency_ms": 0,
            }
    
    def route(self, task_type: str, context_length: int = 0, 
              budget: Optional[float] = None) -> str:
        """
        根据任务类型路由到最佳模型
        
        Args:
            task_type: 任务类型 ("code", "review", "analysis", "creative", "test")
            context_length: 上下文长度
            budget: 预算限制（可选）
            
        Returns:
            选中的模型 ID
        """
        candidates = [m for m in self.models.values() if m.enabled]
        
        if not candidates:
            raise ValueError("No available models")
        
        # 过滤上下文长度不满足的模型
        candidates = [m for m in candidates if m.context_window >= context_length]
        
        if not candidates:
            # 降级到最大上下文窗口
            candidates = [max(self.models.values(), key=lambda m: m.context_window)]
        
        # 根据策略选择
        if self.strategy == RoutingStrategy.BEST_QUALITY:
            return self._select_best_quality(candidates, task_type)
        elif self.strategy == RoutingStrategy.FASTEST:
            return self._select_fastest(candidates)
        elif self.strategy == RoutingStrategy.CHEAPEST:
            return self._select_cheapest(candidates, budget)
        elif self.strategy == RoutingStrategy.CONTEXT_AWARE:
            return self._select_context_aware(candidates, task_type, context_length)
        else:  # BALANCED
            return self._select_balanced(candidates, task_type, context_length)
    
    def _select_best_quality(self, candidates: List[ModelProfile], task_type: str) -> str:
        """选择质量最好的模型"""
        task_scores = {
            "code": "code",
            "review": "analysis",
            "analysis": "analysis",
            "creative": "creative",
            "test": "code",
        }
        cap_key = task_scores.get(task_type, "analysis")
        
        best = max(candidates, key=lambda m: m.capabilities.get(cap_key, 0))
        return best.id
    
    def _select_fastest(self, candidates: List[ModelProfile]) -> str:
        """选择响应最快的模型"""
        best = max(candidates, key=lambda m: m.capabilities.get("fast", 0))
        return best.id
    
    def _select_cheapest(self, candidates: List[ModelProfile], budget: Optional[float] = None) -> str:
        """选择成本最低的模型"""
        if budget:
            affordable = [m for m in candidates if m.cost_per_token * m.max_tokens <= budget]
            if affordable:
                candidates = affordable
        
        best = min(candidates, key=lambda m: m.cost_per_token)
        return best.id
    
    def _select_context_aware(self, candidates: List[ModelProfile], 
                               task_type: str, context_length: int) -> str:
        """上下文感知的路由"""
        # 长上下文优先
        if context_length > 16000:
            long_ctx = [m for m in candidates if m.capabilities.get("long_context", 0) > 70]
            if long_ctx:
                candidates = long_ctx
        
        # 根据任务类型选择
        return self._select_best_quality(candidates, task_type)
    
    def _select_balanced(self, candidates: List[ModelProfile], 
                         task_type: str, context_length: int) -> str:
        """平衡选择：质量 + 速度 + 成本"""
        task_scores = {
            "code": ("code", 0.4),
            "review": ("analysis", 0.3),
            "analysis": ("analysis", 0.5),
            "creative": ("creative", 0.4),
            "test": ("code", 0.3),
        }
        
        cap_key, weight = task_scores.get(task_type, ("analysis", 0.3))
        
        def score(model: ModelProfile) -> float:
            cap_score = model.capabilities.get(cap_key, 50) / 100
            speed_score = model.capabilities.get("fast", 50) / 100 * 0.2
            cost_score = min(1.0, 0.00001 / max(model.cost_per_token, 0.000001)) * 0.1
            
            # 上下文适配惩罚
            ctx_penalty = 0
            if context_length > model.context_window * 0.8:
                ctx_penalty = 0.3
            
            return cap_score * weight + speed_score + cost_score - ctx_penalty
        
        best = max(candidates, key=score)
        return best.id
    
    def record_usage(self, model_id: str, tokens: int, success: bool = True, 
                     latency_ms: float = 0, cost: float = 0.0):
        """记录模型使用情况"""
        self._track_init(model_id)
        
        stats = self.stats[model_id]
        stats["requests"] += 1
        if success:
            stats["success"] += 1
        else:
            stats["errors"] += 1
        stats["total_tokens"] += tokens
        stats["total_cost"] += cost
        stats["avg_latency_ms"] = (
            stats["avg_latency_ms"] * (stats["requests"] - 1) + latency_ms
        ) / stats["requests"]
    
    def get_model_stats(self, model_id: str) -> Dict:
        """获取模型统计"""
        self._track_init(model_id)
        return self.stats[model_id]
    
    def get_all_stats(self) -> Dict:
        """获取所有模型统计"""
        return {mid: self.get_model_stats(mid) for mid in self.models.keys()}
    
    def set_strategy(self, strategy: RoutingStrategy):
        """设置路由策略"""
        self.strategy = strategy
    
    def get_recommendation(self, task_type: str, context_length: int = 0) -> Dict:
        """获取推荐模型"""
        model_id = self.route(task_type, context_length)
        model = self.models[model_id]
        stats = self.get_model_stats(model_id)
        
        return {
            "recommended_model": model_id,
            "model_name": model.name,
            "provider": model.provider,
            "expected_quality": model.capabilities.get(
                {"code": "code", "review": "analysis", "test": "code"}.get(task_type, "analysis"),
                50
            ),
            "estimated_cost": model.cost_per_token * context_length,
            "stats": stats,
        }


# ──────────────────────────────────────────────
# 用法示例
# ──────────────────────────────────────────────

if __name__ == "__main__":
    router = MultiModelRouter()
    
    print("=== 多模型路由测试 ===\n")
    
    # 测试不同任务类型的路由
    test_cases = [
        ("code", 2000),
        ("review", 8000),
        ("analysis", 16000),
        ("creative", 4000),
        ("test", 6000),
    ]
    
    for task_type, ctx_len in test_cases:
        rec = router.get_recommendation(task_type, ctx_len)
        print(f"任务类型: {task_type:10s} | 上下文: {ctx_len:5d}")
        print(f"  → 推荐模型: {rec['recommended_model']} ({rec['model_name']})")
        print(f"  → 预期质量: {rec['expected_quality']}")
        print(f"  → 预估成本: ${rec['estimated_cost']:.6f}")
        print()
    
    # 切换策略测试
    print("=== 策略切换测试 ===\n")
    
    router.set_strategy(RoutingStrategy.FASTEST)
    rec = router.get_recommendation("code", 2000)
    print(f"最快策略: {rec['recommended_model']}")
    
    router.set_strategy(RoutingStrategy.CHEAPEST)
    rec = router.get_recommendation("code", 2000)
    print(f"最经济策略: {rec['recommended_model']}")
    
    router.set_strategy(RoutingStrategy.BEST_QUALITY)
    rec = router.get_recommendation("code", 2000)
    print(f"最佳质量: {rec['recommended_model']}")
    
    print("\n=== 统计信息 ===")
    for mid, stats in router.get_all_stats().items():
        print(f"{mid}: {stats['requests']} requests, ${stats['total_cost']:.4f} cost")
