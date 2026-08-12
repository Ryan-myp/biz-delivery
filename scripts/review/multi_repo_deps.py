#!/usr/bin/env python3
"""多仓库依赖追踪模块 — 跨仓库 RPC/MQ/HTTP 依赖分析

当项目涉及多个仓库时，追踪仓库间的依赖关系，
识别跨仓库调用链和潜在风险。

Usage:
    from scripts.review.multi_repo_deps import analyze_multi_repo_dependencies
    
    deps = analyze_multi_repo_dependencies(ir_data_list, profile)
"""

from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from pathlib import Path
import re


# ──────────────────────────────────────────────
# Dependency Types — 依赖类型定义
# ──────────────────────────────────────────────

DEPENDENCY_TYPES = {
    "rpc": ["rpc", "grpc", "stub", "client", "call"],
    "mq": ["kafka", "rabbitmq", "mq", "topic", "queue", "message", "publish", "subscribe"],
    "http": ["http", "rest", "api", "endpoint", "url"],
    "db": ["mysql", "postgres", "database", "sql", "gorm", "entity"],
    "cache": ["redis", "memcached", "cache"],
}


# ──────────────────────────────────────────────
# Cross-Repo Dependency Tracker — 跨仓库依赖追踪器
# ──────────────────────────────────────────────

class CrossRepoDependencyTracker:
    """跨仓库依赖追踪器"""
    
    def __init__(self, ir_data_list: List[Dict], profiles: Dict[str, Dict] = None):
        """
        Args:
            ir_data_list: 多个仓库的 IR 数据列表
            profiles: 仓库名 -> Profile 映射
        """
        self.ir_data_list = ir_data_list
        self.profiles = profiles or {}
        self.repo_names = [ir.get("repo_name", "") for ir in ir_data_list]
        
        # 依赖关系图
        self.rpc_deps: Dict[str, Set[str]] = defaultdict(set)
        self.mq_deps: Dict[str, Set[str]] = defaultdict(set)
        self.http_deps: Dict[str, Set[str]] = defaultdict(set)
        
        # 跨仓库函数调用
        self.cross_repo_calls: List[Dict] = []
        
        self._build_dependency_graph()
    
    def _build_dependency_graph(self):
        """构建依赖关系图"""
        # 为每个仓库构建导入和调用索引
        repo_imports = {}
        repo_calls = {}
        
        for ir in self.ir_data_list:
            repo_name = ir.get("repo_name", "")
            
            # 导入
            imports = set()
            for imp in ir.get("imports", []):
                if isinstance(imp, dict):
                    module = imp.get("module", "")
                    if module:
                        imports.add(module.lower())
            repo_imports[repo_name] = imports
            
            # 函数调用
            calls = set()
            for func in ir.get("functions", []):
                if isinstance(func, dict):
                    for callee in func.get("calls", []):
                        calls.add(callee.lower())
            repo_calls[repo_name] = calls
        
        # 检测跨仓库依赖
        for i, ir1 in enumerate(self.ir_data_list):
            repo1 = ir1.get("repo_name", "")
            
            for j, ir2 in enumerate(self.ir_data_list):
                if i == j:
                    continue
                repo2 = ir2.get("repo_name", "")
                
                # RPC 依赖
                if self._has_rpc_dependency(ir1, ir2, repo_imports, repo_calls):
                    self.rpc_deps[repo1].add(repo2)
                    self.cross_repo_calls.append({
                        "type": "rpc",
                        "source": repo1,
                        "target": repo2,
                        "description": f"{repo1} 调用 {repo2} 的 RPC 服务"
                    })
                
                # MQ 依赖
                if self._has_mq_dependency(ir1, ir2):
                    self.mq_deps[repo1].add(repo2)
                    self.cross_repo_calls.append({
                        "type": "mq",
                        "source": repo1,
                        "target": repo2,
                        "description": f"{repo1} 与 {repo2} 共享消息队列"
                    })
                
                # HTTP 依赖
                if self._has_http_dependency(ir1, ir2):
                    self.http_deps[repo1].add(repo2)
                    self.cross_repo_calls.append({
                        "type": "http",
                        "source": repo1,
                        "target": repo2,
                        "description": f"{repo1} 调用 {repo2} 的 HTTP API"
                    })
    
    def _has_rpc_dependency(self, ir1: dict, ir2: dict, 
                            imports1: Dict[str, Set[str]], calls1: Set[str]) -> bool:
        """检测 RPC 依赖"""
        # 检查导入
        ir2_modules = set()
        for imp in ir2.get("imports", []):
            if isinstance(imp, dict):
                module = imp.get("module", "")
                if module:
                    ir2_modules.add(module.lower())
        
        # 检查是否有共享的 RPC 相关导入
        rpc_keywords = ["grpc", "stub", "rpc", "proto"]
        for kw in rpc_keywords:
            if any(kw in m for m in imports1.get(ir1.get("repo_name", ""), set()) & ir2_modules):
                return True
        
        return False
    
    def _has_mq_dependency(self, ir1: dict, ir2: dict) -> bool:
        """检测 MQ 依赖"""
        # 检查 topic 名称是否一致
        topics1 = self._extract_mq_topics(ir1)
        topics2 = self._extract_mq_topics(ir2)
        
        return bool(topics1 & topics2)
    
    def _extract_mq_topics(self, ir: dict) -> Set[str]:
        """从 IR 提取 MQ topic"""
        topics = set()
        for func in ir.get("functions", []):
            if isinstance(func, dict):
                name = func.get("name", "").lower()
                if any(kw in name for kw in ["publish", "subscribe", "send", "consume"]):
                    # 尝试从签名提取 topic
                    sig = func.get("signature", "")
                    topic_match = re.search(r'"([^"]+)"', sig)
                    if topic_match:
                        topics.add(topic_match.group(1))
        return topics
    
    def _has_http_dependency(self, ir1: dict, ir2: dict) -> bool:
        """检测 HTTP 依赖"""
        # 检查 URL 是否指向另一个仓库的服务
        ir2_hosts = self._extract_hosts(ir2)
        
        for func in ir1.get("functions", []):
            if isinstance(func, dict):
                sig = func.get("signature", "")
                for host in ir2_hosts:
                    if host in sig:
                        return True
        return False
    
    def _extract_hosts(self, ir: dict) -> Set[str]:
        """从 IR 提取 HTTP 主机"""
        hosts = set()
        for config in ir.get("configs", []):
            if isinstance(config, dict):
                url = config.get("value", "")
                if url and "http" in url:
                    match = re.search(r'https?://([^/]+)', url)
                    if match:
                        hosts.add(match.group(1))
        return hosts
    
    def get_all_dependencies(self) -> Dict[str, Dict]:
        """获取所有依赖关系"""
        return {
            "rpc": dict(self.rpc_deps),
            "mq": dict(self.mq_deps),
            "http": dict(self.http_deps),
            "calls": self.cross_repo_calls,
        }
    
    def get_depended_by(self, repo_name: str) -> Set[str]:
        """获取依赖当前仓库的其他仓库"""
        dependents = set()
        for source, targets in self.rpc_deps.items():
            if repo_name in targets:
                dependents.add(source)
        for source, targets in self.mq_deps.items():
            if repo_name in targets:
                dependents.add(source)
        for source, targets in self.http_deps.items():
            if repo_name in targets:
                dependents.add(source)
        return dependents
    
    def get_dependents(self, repo_name: str) -> Set[str]:
        """获取当前仓库依赖的其他仓库"""
        dependents = set()
        dependents.update(self.rpc_deps.get(repo_name, set()))
        dependents.update(self.mq_deps.get(repo_name, set()))
        dependents.update(self.http_deps.get(repo_name, set()))
        return dependents


# ──────────────────────────────────────────────
# Impact Analyzer — 影响分析器
# ──────────────────────────────────────────────

class MultiRepoImpactAnalyzer:
    """多仓库影响分析器"""
    
    def __init__(self, tracker: CrossRepoDependencyTracker):
        self.tracker = tracker
    
    def analyze_impact(self, repo_name: str, prd_text: str = None) -> Dict:
        """分析 PRD 对多仓库的影响
        
        Args:
            repo_name: 当前仓库名
            prd_text: PRD 文本
            
        Returns:
            影响分析报告
        """
        report = {
            "repo": repo_name,
            "direct_dependencies": list(self.tracker.get_dependents(repo_name)),
            "reverse_dependencies": list(self.tracker.get_depended_by(repo_name)),
            "risks": [],
        }
        
        # 风险 1: 单点依赖
        deps = self.tracker.get_dependents(repo_name)
        if len(deps) >= 3:
            report["risks"].append({
                "type": "high_coupling",
                "severity": "high",
                "description": f"仓库 {repo_name} 依赖 {len(deps)} 个其他仓库，耦合度高",
                "suggestion": "考虑拆分为更小的服务，或引入 API 网关统一出口"
            })
        
        # 风险 2: 被过多依赖
        reverse_deps = self.tracker.get_depended_by(repo_name)
        if len(reverse_deps) >= 3:
            report["risks"].append({
                "type": "high_dependents",
                "severity": "high",
                "description": f"仓库 {repo_name} 被 {len(reverse_deps)} 个仓库依赖，变更影响面大",
                "suggestion": "变更时需充分评估影响，建议使用 feature flag 灰度发布"
            })
        
        # 风险 3: 缺少熔断降级
        if prd_text and any(kw in prd_text for kw in ["高可用", "容灾", "降级", "circuit breaker"]):
            has_fallback = any(
                "fallback" in str(f).lower() or "circuit" in str(f).lower()
                for ir in self.tracker.ir_data_list
                for f in ir.get("functions", [])
            )
            if not has_fallback:
                report["risks"].append({
                    "type": "no_circuit_breaker",
                    "severity": "medium",
                    "description": "PRD 涉及高可用需求但未发现熔断降级实现",
                    "suggestion": "建议为跨仓库调用添加熔断器和降级逻辑"
                })
        
        return report


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def analyze_multi_repo_dependencies(
    ir_data_list: List[Dict],
    profiles: Dict[str, Dict] = None
) -> Dict:
    """分析多仓库依赖关系
    
    Args:
        ir_data_list: 多个仓库的 IR 数据列表
        profiles: 仓库名 -> Profile 映射
        
    Returns:
        依赖分析报告
    """
    tracker = CrossRepoDependencyTracker(ir_data_list, profiles)
    analyzer = MultiRepoImpactAnalyzer(tracker)
    
    results = {
        "dependencies": tracker.get_all_dependencies(),
        "repo_summaries": {},
    }
    
    for ir in ir_data_list:
        repo_name = ir.get("repo_name", "")
        if repo_name:
            results["repo_summaries"][repo_name] = analyzer.analyze_impact(repo_name)
    
    return results


if __name__ == "__main__":
    # 测试示例
    sample_irs = [
        {
            "repo_name": "service-a",
            "imports": [{"module": "github.com/company/service-b/client"}],
            "functions": [
                {"name": "CallServiceB", "calls": ["ServiceBClient.DoSomething"]}
            ]
        },
        {
            "repo_name": "service-b",
            "imports": [{"module": "github.com/company/service-a/types"}],
            "functions": [
                {"name": "DoSomething", "signature": "ctx, req *RequestA"}
            ]
        }
    ]
    
    result = analyze_multi_repo_dependencies(sample_irs)
    print("=== 多仓库依赖分析 ===")
    print(f"RPC 依赖: {result['dependencies']['rpc']}")
    print(f"MQ 依赖: {result['dependencies']['mq']}")
    print(f"HTTP 依赖: {result['dependencies']['http']}")
