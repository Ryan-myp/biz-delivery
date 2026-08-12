#!/usr/bin/env python3
"""字段级冲突检测模块 — 检测 PRD 与现有实现的字段级冲突

当 PRD 要求添加、删除、修改字段时，系统会检查：
1. 该字段是否已被多处使用
2. 删除字段是否是破坏性变更
3. 字段类型变更是否兼容

Usage:
    from scripts.review.field_conflict import detect_field_conflicts
    
    conflicts = detect_field_conflicts(prd_changes, ir_structs)
"""

from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
import re


# ──────────────────────────────────────────────
# Field Change Parser — PRD 字段变更解析
# ──────────────────────────────────────────────

class FieldChangeParser:
    """解析 PRD 中的字段变更描述"""
    
    # 字段新增模式
    ADD_FIELD_PATTERNS = [
        r'新增\s*(?:字段|column|field)?\s*([\w_]+)\s*(?:在|to|on)?\s*([^\s,。]+)',
        r'(?:add|新增|添加)\s+([\w_]+)\s+(?:to|在|到)\s+([^\s,。]+)',
        r'([\w_]+)\s+字段(?:新增|增加)',
    ]
    
    # 字段删除模式
    REMOVE_FIELD_PATTERNS = [
        r'删除\s*(?:字段|column|field)?\s*([\w_]+)\s*(?:在|from|of)?\s*([^\s,。]+)',
        r'(?:delete|删除|移除)\s+([\w_]+)\s+(?:from|在|从)\s+([^\s,。]+)',
        r'([\w_]+)\s+字段(?:删除|移除)',
    ]
    
    # 字段修改模式
    MODIFY_FIELD_PATTERNS = [
        r'修改\s*(?:字段|column|field)?\s*([\w_]+)\s*([^\n。]+)',
        r'(?:modify|修改|变更)\s+([\w_]+)\s+(?:to|为|成)\s+([^\n。]+)',
    ]
    
    # 表名模式
    TABLE_PATTERN = re.compile(r'(?:表|table)\s*[:：]?\s*([^\s,。]+)')
    
    def parse_field_changes(self, prd_text: str) -> List[Dict]:
        """解析 PRD 中的字段变更
        
        Returns:
            [
                {"type": "add", "field": "batch_id", "table": "Creative", ...},
                {"type": "remove", "field": "old_status", "table": "Creative", ...},
            ]
        """
        changes = []
        
        # 提取所有表名
        tables = self.TABLE_PATTERN.findall(prd_text)
        
        # 解析新增字段
        for pattern in self.ADD_FIELD_PATTERNS:
            for match in re.finditer(pattern, prd_text):
                if len(match.groups()) >= 2:
                    field, table = match.groups()
                    changes.append({
                        "type": "add",
                        "field": field.strip(),
                        "table": table.strip(),
                        "context": match.group(0)
                    })
        
        # 解析删除字段
        for pattern in self.REMOVE_FIELD_PATTERNS:
            for match in re.finditer(pattern, prd_text):
                if len(match.groups()) >= 2:
                    field, table = match.groups()
                    changes.append({
                        "type": "remove",
                        "field": field.strip(),
                        "table": table.strip(),
                        "context": match.group(0)
                    })
        
        # 解析修改字段
        for pattern in self.MODIFY_FIELD_PATTERNS:
            for match in re.finditer(pattern, prd_text):
                if len(match.groups()) >= 1:
                    field = match.groups()[0].strip()
                    desc = match.groups()[1].strip() if len(match.groups()) > 1 else ""
                    changes.append({
                        "type": "modify",
                        "field": field,
                        "description": desc,
                        "context": match.group(0)
                    })
        
        return changes


# ──────────────────────────────────────────────
# Field Usage Tracker — 字段使用追踪
# ──────────────────────────────────────────────

class FieldUsageTracker:
    """追踪字段在代码中的使用情况"""
    
    def __init__(self, ir_structs: List[Dict], ir_functions: List[Dict] = None):
        self.structs = {s.get("name", "").lower(): s for s in ir_structs}
        self.functions = ir_functions or []
        self.field_usages: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        self._build_usage_index()
    
    def _build_usage_index(self):
        """构建字段使用索引"""
        # 从 structs 提取字段
        for struct_name, struct in self.structs.items():
            fields = struct.get("fields", [])
            for field in fields:
                if isinstance(field, dict):
                    field_name = field.get("name", field.get("field", str(field)))
                else:
                    field_name = str(field)
                self.field_usages[struct_name.lower()][field_name.lower()] = [struct_name]
        
        # 从 functions 提取字段引用（简化版，实际应解析 AST）
        for func in self.functions:
            if isinstance(func, dict):
                name = func.get("name", "")
                fields = func.get("fields_used", [])
                struct = func.get("struct", "")
                if struct and fields:
                    struct_lower = struct.lower()
                    for field in fields:
                        self.field_usages[struct_lower][field.lower()].append(name)
    
    def get_field_usage_count(self, struct_name: str, field_name: str) -> int:
        """获取字段的使用次数"""
        struct_lower = struct_name.lower()
        field_lower = field_name.lower()
        usages = self.field_usages.get(struct_lower, {})
        return len(usages.get(field_lower, []))
    
    def get_field_references(self, struct_name: str, field_name: str) -> List[str]:
        """获取字段的引用位置列表"""
        struct_lower = struct_name.lower()
        field_lower = field_name.lower()
        return self.field_usages.get(struct_lower, {}).get(field_lower, [])
    
    def is_field_in_struct(self, struct_name: str, field_name: str) -> bool:
        """检查字段是否存在于结构体中"""
        struct_lower = struct_name.lower()
        field_lower = field_name.lower()
        return field_lower in self.field_usages.get(struct_lower, {})


# ──────────────────────────────────────────────
# Conflict Detector — 冲突检测器
# ──────────────────────────────────────────────

class FieldConflictDetector:
    """字段级冲突检测器"""
    
    def __init__(self, ir_data: dict):
        self.ir = ir_data
        self.field_parser = FieldChangeParser()
        self.field_tracker = FieldUsageTracker(
            ir_data.get("structs", []),
            ir_data.get("functions", [])
        )
    
    def detect_conflicts(self, prd_text: str) -> List[Dict]:
        """检测 PRD 中的字段级冲突
        
        Args:
            prd_text: PRD 文本
            
        Returns:
            冲突列表
        """
        changes = self.field_parser.parse_field_changes(prd_text)
        conflicts = []
        
        for change in changes:
            conflict = self._check_change(change)
            if conflict:
                conflicts.extend(conflict)
        
        return conflicts
    
    def _check_change(self, change: Dict) -> List[Dict]:
        """检查单个字段变更的冲突"""
        conflicts = []
        change_type = change.get("type", "")
        field = change.get("field", "")
        table = change.get("table", "")
        
        if change_type == "remove" and table:
            # 检查删除字段的影响
            usage_count = self.field_tracker.get_field_usage_count(table, field)
            references = self.field_tracker.get_field_references(table, field)
            
            if usage_count > 0:
                conflicts.append({
                    "type": "breaking_change",
                    "severity": "critical",
                    "field": field,
                    "table": table,
                    "usage_count": usage_count,
                    "references": references[:5],
                    "message": f"删除字段 '{field}' 会影响 {usage_count} 处代码",
                    "suggestion": f"确认以下代码是否需要同步修改: {', '.join(references[:3])}"
                })
            else:
                conflicts.append({
                    "type": "unused_field",
                    "severity": "info",
                    "field": field,
                    "table": table,
                    "message": f"字段 '{field}' 在代码中未找到引用，可能是新设计或命名不匹配"
                })
        
        elif change_type == "add" and table:
            # 检查新增字段的冲突
            if self.field_tracker.is_field_in_struct(table, field):
                conflicts.append({
                    "type": "duplicate_field",
                    "severity": "warning",
                    "field": field,
                    "table": table,
                    "message": f"字段 '{field}' 在 {table} 中已存在，请确认是否重复定义"
                })
        
        elif change_type == "modify":
            # 修改字段类型检查
            if table and field:
                if self.field_tracker.is_field_in_struct(table, field):
                    conflicts.append({
                        "type": "field_modification",
                        "severity": "medium",
                        "field": field,
                        "table": table,
                        "description": change.get("description", ""),
                        "message": f"字段 '{field}' 的类型/约束可能发生变更，请评估兼容性",
                        "suggestion": "建议增加数据迁移脚本和兼容性检查"
                    })
        
        return conflicts


# ──────────────────────────────────────────────
# Schema Change Analyzer — Schema 变更分析
# ──────────────────────────────────────────────

class SchemaChangeAnalyzer:
    """Schema 变更分析器 — 检测表级别的变更风险"""
    
    def __init__(self, ir_data: dict):
        self.ir = ir_data
        self.entity_tables = {
            et.get("entity", "").lower(): et.get("table", "")
            for et in ir_data.get("entity_tables", [])
        }
    
    def analyze_schema_changes(self, prd_text: str) -> List[Dict]:
        """分析 PRD 中的 Schema 变更风险"""
        risks = []
        
        # 检测大表操作风险
        big_table_keywords = ["大表", "百万行", "千万行", "亿级", "millions", "large table"]
        has_big_table = any(kw in prd_text for kw in big_table_keywords)
        
        if has_big_table:
            # 检查是否有 online DDL 方案
            has_online_ddl = "online" in prd_text.lower() and "ddl" in prd_text.lower()
            if not has_online_ddl:
                risks.append({
                    "type": "big_table_no_online_ddl",
                    "severity": "critical",
                    "message": "PRD 涉及大表变更但未提及 online DDL 方案",
                    "suggestion": "大表 DDL 必须使用 online 模式（如 pt-online-schema-change），避免锁表"
                })
            
            # 检查是否有 backfill 策略
            has_backfill = "backfill" in prd_text.lower() or "回填" in prd_text or "历史数据" in prd_text
            if not has_backfill:
                risks.append({
                    "type": "no_backfill_strategy",
                    "severity": "high",
                    "message": "大表变更需要数据回填但未发现相关策略",
                    "suggestion": "新增字段需要 backfill 策略，考虑分批处理 + 进度追踪 + 失败重试"
                })
        
        # 检测索引变更风险
        index_keywords = ["索引", "index", "unique", "唯一键"]
        has_index_change = any(kw in prd_text for kw in index_keywords)
        
        if has_index_change:
            risks.append({
                "type": "index_change_risk",
                "severity": "medium",
                "message": "PRD 涉及索引变更，需评估对查询性能的影响",
                "suggestion": "建议在低峰期执行索引变更，并准备回滚方案"
            })
        
        return risks


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def detect_field_conflicts(
    prd_text: str,
    ir_data: dict
) -> Dict:
    """检测 PRD 中的字段级冲突
    
    Args:
        prd_text: PRD 文本
        ir_data: IR 数据
        
    Returns:
        冲突检测结果
    """
    detector = FieldConflictDetector(ir_data)
    schema_analyzer = SchemaChangeAnalyzer(ir_data)
    
    field_conflicts = detector.detect_conflicts(prd_text)
    schema_risks = schema_analyzer.analyze_schema_changes(prd_text)
    
    return {
        "field_conflicts": field_conflicts,
        "schema_risks": schema_risks,
        "total_issues": len(field_conflicts) + len(schema_risks),
        "critical_count": len([c for c in field_conflicts if c.get("severity") == "critical"]) + 
                         len([r for r in schema_risks if r.get("severity") == "critical"]),
    }


if __name__ == "__main__":
    # 测试示例
    sample_ir = {
        "structs": [
            {"name": "Creative", "fields": ["ID", "URL", "Type", "Status", "CreatedAt"]}
        ],
        "functions": [
            {"name": "GetCreative", "struct": "Creative", "fields_used": ["ID", "URL", "Status"]},
            {"name": "UpdateCreative", "struct": "Creative", "fields_used": ["ID", "Status"]},
            {"name": "DeleteCreative", "struct": "Creative", "fields_used": ["ID"]},
        ],
        "entity_tables": [
            {"entity": "Creative", "table": "creatives"}
        ]
    }
    
    sample_prd = """
    # 素材表字段调整
    
    ## 变更内容
    1. 新增 batch_id 字段到 Creative 表
    2. 删除 Creative 表的 old_status 字段（已废弃）
    3. 修改 Creative 表的 URL 字段长度为 2048
    """
    
    result = detect_field_conflicts(sample_prd, sample_ir)
    print("=== 字段级冲突检测 ===")
    print(f"总问题数: {result['total_issues']}")
    print(f"严重问题: {result['critical_count']}")
    print()
    print("字段冲突:")
    for conflict in result['field_conflicts']:
        print(f"  [{conflict['severity']}] {conflict['message']}")
    print()
    print("Schema 风险:")
    for risk in result['schema_risks']:
        print(f"  [{risk['severity']}] {risk['message']}")
