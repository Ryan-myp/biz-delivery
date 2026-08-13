#!/usr/bin/env python3
"""跨模块影响分析模块 — 调用链推断与影响范围分析

当 PRD 提到某个实体或功能时，通过调用图追踪所有受影响的位置，
识别隐式依赖的模块。

Usage:
    from scripts.review.cross_module_analysis import analyze_cross_module_impact
    
    impacts = analyze_cross_module_impact(prd_entities, ir, profile)
"""

from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from pathlib import Path
import re


# ──────────────────────────────────────────────
# Call Graph Analysis — 调用图分析
# ──────────────────────────────────────────────

class CallGraphAnalyzer:
    """调用图分析器 — 追踪函数调用关系"""
    
    def __init__(self, ir_data: dict):
        self.ir = ir_data
        self.call_graph: Dict[str, List[str]] = defaultdict(list)
        self.reverse_graph: Dict[str, List[str]] = defaultdict(list)
        self._build_graph()
    
    def _build_graph(self):
        """构建调用图"""
        # 从 core_flows 提取调用关系
        for flow in self.ir.get("core_flows", []):
            chain = flow.get("call_chain", [])
            for i in range(len(chain) - 1):
                caller = chain[i]
                callee = chain[i + 1]
                self.call_graph[caller].append(callee)
                self.reverse_graph[callee].append(caller)
        
        # 从 functions 提取显式调用
        for func in self.ir.get("functions", []):
            if isinstance(func, dict):
                name = func.get("name", "")
                calls = func.get("calls", [])
                for callee in calls:
                    self.call_graph[name].append(callee)
                    self.reverse_graph[callee].append(name)
    
    def get_callers(self, func_name: str, max_depth: int = 3) -> Set[str]:
        """获取函数的所有调用者（向上追溯）"""
        callers = set()
        queue = [(func_name, 0)]
        visited = {func_name}
        
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for caller in self.reverse_graph.get(current, []):
                if caller not in visited:
                    visited.add(caller)
                    callers.add(caller)
                    queue.append((caller, depth + 1))
        
        return callers
    
    def get_callees(self, func_name: str, max_depth: int = 3) -> Set[str]:
        """获取函数的所有被调用者（向下追踪）"""
        callees = set()
        queue = [(func_name, 0)]
        visited = {func_name}
        
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for callee in self.call_graph.get(current, []):
                if callee not in visited:
                    visited.add(callee)
                    callees.add(callee)
                    queue.append((callee, depth + 1))
        
        return callees
    
    def get_full_impact_chain(self, func_name: str) -> Dict[str, Set[str]]:
        """获取完整的调用链影响（调用者 + 被调用者）"""
        return {
            "callers": self.get_callers(func_name),
            "callees": self.get_callees(func_name),
        }


# ──────────────────────────────────────────────
# Module Tracker — 模块追踪器
# ──────────────────────────────────────────────

class ModuleTracker:
    """模块追踪器 — 将函数映射到所属模块"""
    
    def __init__(self, ir_data: dict, profile: dict = None):
        self.ir = ir_data
        self.profile = profile or {}
        self.func_to_module: Dict[str, str] = {}
        self._build_mapping()
    
    def _build_mapping(self):
        """构建函数到模块的映射"""
        # 从 modules 配置构建关键词索引
        modules = self.profile.get("modules", [])
        module_keywords = {}
        for module in modules:
            if isinstance(module, dict):
                name = module.get("name", "")
                keywords = module.get("keywords", [])
                for kw in keywords:
                    module_keywords[kw.lower()] = name
        
        # 从 functions 提取文件路径，推断模块
        for func in self.ir.get("functions", []):
            if isinstance(func, dict):
                name = func.get("name", "")
                file_path = func.get("file", "")
                
                # 根据文件名推断模块
                for kw, module_name in module_keywords.items():
                    if kw in file_path.lower():
                        self.func_to_module[name] = module_name
                        break
                else:
                    # 默认模块
                    self.func_to_module[name] = self._infer_module_from_path(file_path)
    
    def _infer_module_from_path(self, path: str) -> str:
        """从文件路径推断模块名"""
        if not path:
            return "unknown"
        parts = Path(path).parts
        if len(parts) >= 2:
            return parts[-2]  # 上级目录作为模块名
        return parts[-1].replace(".go", "").replace(".py", "")
    
    def get_module_for_function(self, func_name: str) -> str:
        """获取函数所属模块"""
        return self.func_to_module.get(func_name, "unknown")
    
    def get_all_modules(self) -> List[str]:
        """获取所有已知模块"""
        return list(set(self.func_to_module.values()))


# ──────────────────────────────────────────────
# Entity Matcher — 实体匹配器
# ──────────────────────────────────────────────

class EntityMatcher:
    """实体匹配器 — 从 PRD 文本提取并匹配实体"""
    
    def __init__(self, ir_data: dict):
        self.ir = ir_data
        self.all_entities: Set[str] = set()
        self._build_entity_index()
    
    def _build_entity_index(self):
        """构建实体索引"""
        # 收集所有代码实体
        for struct in self.ir.get("structs", []):
            if isinstance(struct, dict):
                self.all_entities.add(struct.get("name", "").lower())
        
        for func in self.ir.get("functions", []):
            if isinstance(func, dict):
                self.all_entities.add(func.get("name", "").lower())
        
        for route in self.ir.get("routes", []):
            if isinstance(route, dict):
                self.all_entities.add(route.get("path", "").lower())
        
        for entity in self.ir.get("entity_tables", []):
            if isinstance(entity, dict):
                self.all_entities.add(entity.get("entity", "").lower())
                self.all_entities.add(entity.get("table", "").lower())
    
    def extract_entities_from_prd(self, prd_text: str) -> List[str]:
        """从 PRD 文本提取实体"""
        entities = set()
        prd_lower = prd_text.lower()
        
        # 驼峰命名实体
        camel_pattern = re.compile(r'[A-Z][a-z]+(?:[A-Z][a-z]+)*')
        for match in camel_pattern.finditer(prd_text):
            entities.add(match.group().lower())
        
        # 中文实体（2-6 个字符）
        cn_pattern = re.compile(r'[\u4e00-\u9fff]{2,6}')
        for match in cn_pattern.finditer(prd_text):
            entities.add(match.group())
        
        # 路由路径
        route_pattern = re.compile(r'/api/\w+(?:/\w+)*')
        for match in route_pattern.finditer(prd_text):
            entities.add(match.group().lower())
        
        # 匹配已知实体
        matched = []
        for entity in entities:
            if entity in self.all_entities:
                matched.append(entity)
            else:
                # fuzzy match
                best_match = self._fuzzy_match(entity)
                if best_match:
                    matched.append(best_match)
        
        return matched
    
    def _fuzzy_match(self, entity: str, threshold: float = 0.5) -> Optional[str]:
        """模糊匹配实体"""
        best_match = None
        best_score = 0
        
        for known in self.all_entities:
            score = self._similarity(entity, known)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = known
        
        return best_match
    
    def _similarity(self, s1: str, s2: str) -> float:
        """计算相似度"""
        if not s1 or not s2:
            return 0.0
        if s1 == s2:
            return 1.0
        
        # 简单包含检查
        if s1 in s2 or s2 in s1:
            return 0.8
        
        # 编辑距离
        len1, len2 = len(s1), len(s2)
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # 共享字符比例
        common = len(set(s1) & set(s2))
        union = len(set(s1) | set(s2))
        return common / union if union > 0 else 0.0


# ──────────────────────────────────────────────
# Cross-Module Impact Analyzer — 主分析器
# ──────────────────────────────────────────────

class CrossModuleImpactAnalyzer:
    """跨模块影响分析器 — 综合分析 PRD 涉及的模块影响"""
    
    def __init__(self, ir_data: dict, profile: dict = None):
        self.ir = ir_data
        self.profile = profile or {}
        self.call_analyzer = CallGraphAnalyzer(ir_data)
        self.module_tracker = ModuleTracker(ir_data, profile)
        self.entity_matcher = EntityMatcher(ir_data)
    
    def analyze(self, prd_text: str) -> Dict:
        """分析 PRD 的跨模块影响
        
        Returns:
            {
                "matched_entities": [...],
                "impacted_functions": {...},
                "impacted_modules": [...],
                "cross_module_risks": [...],
                "missing_modules": [...],
            }
        """
        # 1. 提取 PRD 实体
        prd_entities = self.entity_matcher.extract_entities_from_prd(prd_text)
        
        # 2. 追踪每个实体的影响链
        impacted_functions = {}
        for entity in prd_entities:
            impact = self.call_analyzer.get_full_impact_chain(entity)
            impacted_functions[entity] = impact
        
        # 3. 映射到模块
        impacted_modules = set()
        module_functions = defaultdict(list)
        for func, impact in impacted_functions.items():
            all_related = impact.get("callers", set()) | impact.get("callees", set()) | {func}
            for f in all_related:
                module = self.module_tracker.get_module_for_function(f)
                impacted_modules.add(module)
                module_functions[module].append(f)
        
        # 4. 检测跨模块风险
        cross_module_risks = self._detect_cross_module_risks(
            prd_entities, impacted_functions, impacted_modules
        )
        
        # 5. 检测遗漏模块
        missing_modules = self._detect_missing_modules(
            prd_text, impacted_modules
        )
        
        return {
            "matched_entities": prd_entities,
            "impacted_functions": {k: list(v.get("callers", set()) | v.get("callees", set())) 
                                   for k, v in impacted_functions.items()},
            "impacted_modules": list(impacted_modules),
            "module_functions": dict(module_functions),
            "cross_module_risks": cross_module_risks,
            "missing_modules": missing_modules,
        }
    
    def _detect_cross_module_risks(
        self,
        prd_entities: List[str],
        impacted_functions: Dict,
        impacted_modules: Set[str]
    ) -> List[Dict]:
        """检测跨模块风险"""
        risks = []
        
        # 风险 1: 涉及多个模块
        if len(impacted_modules) >= 2:
            risks.append({
                "type": "multi_module_dependency",
                "severity": "medium",
                "description": f"PRD 涉及 {len(impacted_modules)} 个模块: {', '.join(list(impacted_modules)[:5])}",
                "suggestion": "需要评估跨模块协调方案，考虑引入事件驱动或 API 网关解耦"
            })
        
        # 风险 2: 有未匹配的实体（可能是新模块）
        unmatched = [e for e in prd_entities if e not in self.entity_matcher.all_entities]
        if unmatched:
            risks.append({
                "type": "unmatched_entities",
                "severity": "high",
                "description": f"PRD 提到的实体在代码中未找到: {', '.join(unmatched[:5])}",
                "suggestion": "这些实体可能需要新建，请确认是否属于遗漏模块"
            })
        
        return risks
    
    def _detect_missing_modules(
        self,
        prd_text: str,
        impacted_modules: Set[str]
    ) -> List[Dict]:
        """检测遗漏的模块"""
        missing = []
        
        # 从 PRD 提取模块关键词
        module_keywords = {
            "MQ/消息队列": ["mq", "kafka", "rabbitmq", "消息", "队列", "topic"],
            "数据库": ["mysql", "postgres", "database", "db", "表", "字段"],
            "缓存": ["redis", "cache", "缓存"],
            "鉴权": ["auth", "permission", "权限", "鉴权", "rbac"],
            "监控": ["monitor", "log", "日志", "监控", "alert"],
            "调度": ["cron", "scheduler", "定时", "任务"],
        }
        
        prd_lower = prd_text.lower()
        for module_name, keywords in module_keywords.items():
            if any(kw in prd_lower for kw in keywords):
                # 检查是否已覆盖
                already_covered = False
                for mod in impacted_modules:
                    if module_name in mod or any(kw in mod.lower() for kw in keywords):
                        already_covered = True
                        break
                
                if not already_covered:
                    missing.append({
                        "type": "missing_module",
                        "severity": "medium",
                        "module": module_name,
                        "keywords": [kw for kw in keywords if kw in prd_lower],
                        "suggestion": f"PRD 涉及 {module_name}，但当前分析未覆盖，请确认是否需要额外处理"
                    })
        
        return missing


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def analyze_cross_module_impact(
    prd_text: str,
    ir_data: dict,
    profile: dict = None
) -> Dict:
    """分析 PRD 的跨模块影响
    
    Args:
        prd_text: PRD 文本
        ir_data: IR 数据
        profile: 业务 Profile
        
    Returns:
        影响分析结果
    """
    analyzer = CrossModuleImpactAnalyzer(ir_data, profile)
    return analyzer.analyze(prd_text)


if __name__ == "__main__":
    # 测试示例
    sample_ir = {
        "functions": [
            {"name": "ReviewCreative", "file": "review.go", "calls": ["ValidateCreative", "SaveToDB"]},
            {"name": "ValidateCreative", "file": "review.go"},
            {"name": "SaveToDB", "file": "db.go"},
            {"name": "PublishMQ", "file": "mq.go"},
            {"name": "CreateAdGroup", "file": "adgroup.go", "calls": ["ValidateCreative", "SaveToDB"]},
        ],
        "core_flows": [
            {
                "flow_name": "素材审核",
                "entry_point": "ReviewCreative",
                "call_chain": ["ReviewCreative", "ValidateCreative", "SaveToDB", "PublishMQ"]
            }
        ],
        "structs": [
            {"name": "Creative", "fields": ["ID", "URL", "Type", "Status"]}
        ],
        "entity_tables": [
            {"entity": "Creative", "table": "creatives"}
        ]
    }
    
    sample_profile = {
        "modules": [
            {"name": "Creative / 素材", "keywords": ["creative", "素材", "review"]},
            {"name": "MQ / 消息队列", "keywords": ["mq", "kafka", "消息"]},
            {"name": "DB / 数据库", "keywords": ["db", "save", "mysql"]},
            {"name": "AdGroup / 广告组", "keywords": ["adgroup", "广告组"]},
        ]
    }
    
    sample_prd = """
    # 素材批量审核功能
    
    用户可以选择多个素材进行批量审核，审核结果通过 MQ 推送给上游系统。
    审核通过后，素材自动进入广告组。
    """
    
    result = analyze_cross_module_impact(sample_prd, sample_ir, sample_profile)
    print("=== 跨模块影响分析 ===")
    print(f"匹配的实体: {result['matched_entities']}")
    print(f"影响的模块: {result['impacted_modules']}")
    print(f"跨模块风险: {len(result['cross_module_risks'])} 个")
    for risk in result['cross_module_risks']:
        print(f"  - [{risk['severity']}] {risk['description']}")
    print(f"遗漏的模块: {len(result['missing_modules'])} 个")
    for m in result['missing_modules']:
        print(f"  - {m['module']}: {m['keywords']}")
