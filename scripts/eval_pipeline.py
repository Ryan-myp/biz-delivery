#!/usr/bin/env python3
"""端到端评估框架 — 系统化评估 PRD 审查、技术方案、测试用例质量。

覆盖三种评估模式：
1. **coverage**: 检查 PRD 需求是否被审查/TD/测试覆盖
2. **quality**: 基于规则的质量评分（证据引用完整性、图表覆盖率等）
3. **consistency**: 检查三阶段一致性（PRD→审查→TD→测试）

用法:
    # 运行完整评估
    python3 eval_pipeline.py --profile profiles/my-service.json \
        --output-dir delivery/my-feature --mode full
    
    # 仅评估审查质量
    python3 eval_pipeline.py --profile profiles/my-service.json \
        --output-dir delivery/my-feature --mode review
    
    # 仅评估 TD 质量
    python3 eval_pipeline.py --profile profiles/my-service.json \
        --output-dir delivery/my-feature --mode td
    
    # 仅评估测试覆盖
    python3 eval_pipeline.py --profile profiles/my-service.json \
        --output-dir delivery/my-feature --mode test
"""

import json
import re
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class EvalMetric:
    """单个评估指标"""
    name: str
    score: float  # 0-1
    max_score: float
    details: str = ""
    severity: str = "info"  # info/warn/critical


@dataclass
class EvalReport:
    """评估报告"""
    mode: str
    metrics: List[EvalMetric] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    
    def add_metric(self, metric: EvalMetric):
        self.metrics.append(metric)
    
    @property
    def total_score(self) -> float:
        if not self.metrics:
            return 0.0
        total = sum(m.score for m in self.metrics)
        max_total = sum(m.max_score for m in self.metrics)
        return (total / max_total * 100) if max_total > 0 else 0.0
    
    @property
    def critical_issues(self) -> List[EvalMetric]:
        return [m for m in self.metrics if m.severity == "critical"]
    
    @property
    def warnings(self) -> List[EvalMetric]:
        return [m for m in self.metrics if m.severity == "warn"]
    
    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "total_score": round(self.total_score, 1),
            "metrics": [
                {
                    "name": m.name,
                    "score": round(m.score, 2),
                    "max_score": m.max_score,
                    "details": m.details,
                    "severity": m.severity,
                }
                for m in self.metrics
            ],
            "summary": self.summary,
            "critical_count": len(self.critical_issues),
            "warning_count": len(self.warnings),
        }


def load_report(report_path: str) -> Optional[str]:
    """安全加载报告文件，返回内容或 None"""
    if not report_path or not os.path.exists(report_path):
        return None
    try:
        content = Path(report_path).read_text(encoding="utf-8")
        return content if len(content) > 50 else None
    except Exception:
        return None


# ──────────────────────────────────────────────
# 1. PRD 审查质量评估
# ──────────────────────────────────────────────

def eval_review_quality(review_report: str, ir_data: dict, prd_text: str) -> EvalReport:
    """评估 PRD 审查报告质量。
    
    检查项：
    1. 问题分级完整性（P0/P1/P2 都有）
    2. 证据引用数量（#N 引用格式）
    3. 审查维度覆盖（合理性/场景/一致性/风险）
    4. 预检结果整合度
    5. 业务规则校验深度
    6. 兼容性检查完整性
    7. 性能风险评估详细度
    8. 安全检查覆盖
    """
    report = EvalReport(mode="review")
    
    if not review_report:
        report.add_metric(EvalMetric("report_exists", 0, 1, "审查报告不存在", "critical"))
        report.add_metric(EvalMetric("p0_p1_p2_coverage", 0, 1, "无报告，无法评估分级", "critical"))
        report.add_metric(EvalMetric("evidence_citation", 0, 1, "无报告，无法评估引用", "critical"))
        report.summary = {"status": "missing"}
        return report
    
    # 1. 报告长度
    report_len = len(review_report)
    if report_len > 2000:
        report.add_metric(EvalMetric("report_length", 1.0, 1.0, f"报告长度 {report_len} chars，内容充分"))
    elif report_len > 500:
        report.add_metric(EvalMetric("report_length", 0.5, 1.0, f"报告长度 {report_len} chars，偏短"))
    else:
        report.add_metric(EvalMetric("report_length", 0.2, 1.0, f"报告长度 {report_len} chars，严重不足", "warn"))
    
    # 2. 问题分级完整性
    p0_count = len(re.findall(r'\[?P0\]?|阻塞', review_report))
    p1_count = len(re.findall(r'\[?P1\]?|重要', review_report))
    p2_count = len(re.findall(r'\[?P2\]?|一般', review_report))
    
    if p0_count >= 1 and p1_count >= 1 and p2_count >= 1:
        report.add_metric(EvalMetric("p0_p1_p2_coverage", 1.0, 1.0, f"P0:{p0_count}, P1:{p1_count}, P2:{p2_count}"))
    elif p0_count >= 1 and p1_count >= 1:
        report.add_metric(EvalMetric("p0_p1_p2_coverage", 0.6, 1.0, f"缺少 P2 级别问题", "warn"))
    elif p0_count >= 1:
        report.add_metric(EvalMetric("p0_p1_p2_coverage", 0.4, 1.0, f"只有 P0，缺少 P1/P2 细化", "warn"))
    else:
        report.add_metric(EvalMetric("p0_p1_p2_coverage", 0.1, 1.0, "未检测到 P0/P1/P2 分级", "critical"))
    
    # 3. 证据引用数量（#N 引用格式）
    evidence_refs = re.findall(r'#\d+', review_report)
    evidence_ref_count = len(evidence_refs)
    if evidence_ref_count >= 5:
        report.add_metric(EvalMetric("evidence_citation", 1.0, 1.0, f"引用了 {evidence_ref_count} 处代码证据"))
    elif evidence_ref_count >= 2:
        report.add_metric(EvalMetric("evidence_citation", 0.5, 1.0, f"仅引用 {evidence_ref_count} 处证据，建议更多"))
    else:
        report.add_metric(EvalMetric("evidence_citation", 0.2, 1.0, f"仅引用 {evidence_ref_count} 处证据，缺乏代码支撑", "warn"))
    
    # 4. 审查维度覆盖
    dimensions = {
        "合理性检查": False,
        "场景遗漏": False,
        "前后不一致": False,
        "风险评估": False,
        "兼容性检查": False,
        "性能风险": False,
        "安全检查": False,
        "可观测性": False,
        "数据合规": False,
        "发布策略": False,
    }
    for dim in dimensions:
        if dim in review_report:
            dimensions[dim] = True
    
    covered = sum(dimensions.values())
    total_dims = len(dimensions)
    coverage_ratio = covered / total_dims
    
    if coverage_ratio >= 0.7:
        report.add_metric(EvalMetric("dimension_coverage", coverage_ratio, 1.0, 
                                     f"覆盖 {covered}/{total_dims} 个审查维度"))
    else:
        missing = [k for k, v in dimensions.items() if not v]
        report.add_metric(EvalMetric("dimension_coverage", coverage_ratio, 1.0,
                                     f"仅覆盖 {covered}/{total_dims} 维度，缺失: {missing[:3]}", "warn"))
    
    # 5. 业务规则校验深度
    business_rules_checks = [
        'error_code', 'auth_missing', 'struct_missing', 'state_machine',
        'rpc_dependency', 'compatibility', 'idempotency', 'audit'
    ]
    rule_hits = sum(1 for r in business_rules_checks if r.lower() in review_report.lower())
    rule_ratio = min(rule_hits / len(business_rules_checks), 1.0)
    
    if rule_ratio >= 0.6:
        report.add_metric(EvalMetric("business_rule_depth", rule_ratio, 1.0,
                                     f"检查了 {rule_hits}/{len(business_rules_checks)} 项业务规则"))
    else:
        report.add_metric(EvalMetric("business_rule_depth", rule_ratio, 1.0,
                                     f"仅检查 {rule_hits}/{len(business_rules_checks)} 项业务规则", "warn"))
    
    # 6. 预检结果整合
    precheck_indicators = ['预检', 'precheck', '自动检测', 'high_risk', 'critical']
    precheck_hits = sum(1 for ind in precheck_indicators if ind.lower() in review_report.lower())
    if precheck_hits >= 2:
        report.add_metric(EvalMetric("precheck_integration", 1.0, 1.0, "整合了预检结果"))
    else:
        report.add_metric(EvalMetric("precheck_integration", 0.3, 1.0, "未有效整合预检结果", "warn"))
    
    report.summary = {
        "status": "completed",
        "word_count": len(review_report),
        "dimensions_covered": covered,
        "total_dimensions": total_dims,
        "evidence_references": evidence_ref_count,
    }
    
    return report


# ──────────────────────────────────────────────
# 2. 技术方案质量评估
# ──────────────────────────────────────────────

def eval_td_quality(td_report: str, ir_data: dict, review_report: str, prd_text: str) -> EvalReport:
    """评估技术方案质量。
    
    检查项：
    1. 方案类型判断（兼容改进 vs 新功能）
    2. 架构图完整性（mermaid graph）
    3. 数据模型图完整性（erDiagram）
    4. 部署架构图完整性
    5. 接口设计详细度
    6. 数据库设计详细度
    7. 流程图/时序图
    8. 风险评估完整性
    9. 跨仓库依赖分析
    10. 与审查报告的关联性
    """
    report = EvalReport(mode="td")
    
    if not td_report:
        report.add_metric(EvalMetric("report_exists", 0, 1, "TD 报告不存在", "critical"))
        report.summary = {"status": "missing"}
        return report
    
    # 1. 报告长度
    report_len = len(td_report)
    if report_len > 3000:
        report.add_metric(EvalMetric("report_length", 1.0, 1.0, f"报告长度 {report_len} chars，内容充分"))
    elif report_len > 1000:
        report.add_metric(EvalMetric("report_length", 0.6, 1.0, f"报告长度 {report_len} chars，基本完整"))
    else:
        report.add_metric(EvalMetric("report_length", 0.3, 1.0, f"报告长度 {report_len} chars，过于简略", "warn"))
    
    # 2. 方案类型判断
    type_keywords = ['兼容改进', '新功能', '混合方案', 'compatible', 'new feature']
    type_found = any(kw in td_report for kw in type_keywords)
    report.add_metric(EvalMetric("type_classification", 1.0 if type_found else 0.2, 1.0,
                                 "正确识别方案类型" if type_found else "未明确方案类型",
                                 "warn" if not type_found else "info"))
    
    # 3. 架构图完整性
    mermaid_patterns = {
        'architecture': r'mermaid.*graph\s+TB|架构图|architecture.*diagram',
        'data_model': r'erDiagram|数据模型图|data.*model.*diagram',
        'deployment': r'部署架构|deployment.*diagram|graph\s+LR',
        'sequence': r'sequenceDiagram|时序图|flowchart',
        'state_machine': r'stateDiagram|状态机图|state.*machine',
        'dependency': r'依赖图|dependency.*graph|模块依赖',
    }
    
    diagram_scores = {}
    for name, pattern in mermaid_patterns.items():
        found = bool(re.search(pattern, td_report, re.IGNORECASE))
        diagram_scores[name] = 1.0 if found else 0.0
    
    avg_diagram_score = sum(diagram_scores.values()) / len(diagram_scores)
    report.add_metric(EvalMetric("diagram_coverage", avg_diagram_score, 1.0,
                                 f"图表覆盖率: {sum(1 for v in diagram_scores.values() if v)}/{len(diagram_scores)} 种"))
    
    # 4. 接口设计详细度
    api_indicators = ['Request', 'Response', 'HTTP', 'POST', 'GET', 'PUT', 'DELETE', '接口设计']
    api_hits = sum(1 for ind in api_indicators if ind in td_report)
    api_ratio = min(api_hits / 5, 1.0)
    report.add_metric(EvalMetric("api_design_detail", api_ratio, 1.0,
                                 f"包含 {api_hits} 项接口设计要素"))
    
    # 5. 数据库设计详细度
    db_indicators = ['CREATE TABLE', 'ALTER TABLE', '字段', '索引', 'primary key', '外键', '数据库设计']
    db_hits = sum(1 for ind in db_indicators if ind in td_report)
    db_ratio = min(db_hits / 5, 1.0)
    report.add_metric(EvalMetric("db_design_detail", db_ratio, 1.0,
                                 f"包含 {db_hits} 项数据库设计要素"))
    
    # 6. 风险评估完整性
    risk_indicators = ['风险', '难度', '依赖', '回滚', 'rollback', 'implementation difficulty']
    risk_hits = sum(1 for ind in risk_indicators if ind in td_report)
    risk_ratio = min(risk_hits / 3, 1.0)
    report.add_metric(EvalMetric("risk_assessment", risk_ratio, 1.0,
                                 f"包含 {risk_hits} 项风险评估要素"))
    
    # 7. 数据迁移方案（如果是新功能）
    migration_indicators = ['数据迁移', 'migration', 'backfill', '旧数据', '历史数据']
    migration_found = any(ind in td_report for ind in migration_indicators)
    if migration_found:
        report.add_metric(EvalMetric("migration_plan", 1.0, 1.0, "包含数据迁移方案"))
    else:
        report.add_metric(EvalMetric("migration_plan", 0.5, 1.0, "未提及数据迁移方案", "warn"))
    
    # 8. 与审查报告的关联性
    if review_report:
        td_references_review = sum(1 for ind in ['审查', 'review', 'P0', 'P1', 'P2', '兼容性'] 
                                  if ind in td_report)
        correlation = min(td_references_review / 3, 1.0)
        report.add_metric(EvalMetric("review_correlation", correlation, 1.0,
                                     f"TD 引用审查要点 {td_references_review} 次"))
    else:
        report.add_metric(EvalMetric("review_correlation", 0.5, 1.0, "无审查报告可供关联", "warn"))
    
    # 9. 跨仓库依赖分析
    cross_repo_indicators = ['跨服务', '微服务', 'RPC', 'gRPC', 'MQ', '消息队列', 'service topology']
    cross_repo_hits = sum(1 for ind in cross_repo_indicators if ind in td_report)
    if cross_repo_hits >= 2:
        report.add_metric(EvalMetric("cross_repo_analysis", 1.0, 1.0, "包含跨仓库依赖分析"))
    elif isinstance(ir_data, dict) and ir_data.get('services') and len(ir_data.get('services', [])) > 1:
        report.add_metric(EvalMetric("cross_repo_analysis", 0.2, 1.0, 
                                     "多仓库但未分析跨服务依赖", "critical"))
    else:
        report.add_metric(EvalMetric("cross_repo_analysis", 1.0, 1.0, "单仓库，无需跨仓库分析"))
    
    report.summary = {
        "status": "completed",
        "word_count": len(td_report),
        "diagrams_found": sum(1 for v in diagram_scores.values() if v > 0),
        "total_diagram_types": len(diagram_scores),
        "api_elements": api_hits,
        "db_elements": db_hits,
    }
    
    return report


# ──────────────────────────────────────────────
# 3. 测试用例质量评估
# ──────────────────────────────────────────────

def eval_test_quality(test_report: str, ir_data: dict, td_report: str, prd_text: str) -> EvalReport:
    """评估测试用例质量。
    
    检查项：
    1. 测试用例总数和优先级分布
    2. 正向流程覆盖
    3. 异常分支覆盖
    4. 边界条件覆盖
    5. 状态转换测试
    6. 安全测试覆盖
    7. 性能测试覆盖
    8. 错误码引用准确性
    9. 路由/接口覆盖
    10. 自动化测试代码生成
    """
    report = EvalReport(mode="test")
    
    if not test_report:
        report.add_metric(EvalMetric("report_exists", 0, 1, "测试报告不存在", "critical"))
        report.summary = {"status": "missing"}
        return report
    
    # 1. 测试用例总数
    tc_matches = re.findall(r'TC\d{3,}', test_report)
    tc_count = len(tc_matches)
    if tc_count >= 20:
        report.add_metric(EvalMetric("test_case_count", 1.0, 1.0, f"生成 {tc_count} 个测试用例"))
    elif tc_count >= 10:
        report.add_metric(EvalMetric("test_case_count", 0.7, 1.0, f"生成 {tc_count} 个测试用例，偏少"))
    else:
        report.add_metric(EvalMetric("test_case_count", 0.3, 1.0, f"仅生成 {tc_count} 个测试用例", "warn"))
    
    # 2. 优先级分布
    p0_tc = len(re.findall(r'\|.*?\|.*?\|.*?\|.*?\|.*?\|.*?P0\s*\|', test_report))
    p1_tc = len(re.findall(r'\|.*?\|.*?\|.*?\|.*?\|.*?\|.*?P1\s*\|', test_report))
    p2_tc = len(re.findall(r'\|.*?\|.*?\|.*?\|.*?\|.*?\|.*?P2\s*\|', test_report))
    
    if p0_tc >= 3 and p1_tc >= 2:
        report.add_metric(EvalMetric("priority_distribution", 1.0, 1.0, 
                                     f"P0:{p0_tc}, P1:{p1_tc}, P2:{p2_tc}"))
    elif p0_tc >= 1:
        report.add_metric(EvalMetric("priority_distribution", 0.6, 1.0,
                                     f"优先级分布: P0:{p0_tc}, P1:{p1_tc}, P2:{p2_tc}", "warn"))
    else:
        report.add_metric(EvalMetric("priority_distribution", 0.2, 1.0, "缺少优先级标注", "warn"))
    
    # 3. 测试维度覆盖
    dimensions = {
        "正向流程": r'正向流程|positive.*flow|主流程',
        "异常分支": r'异常分支|exception|error.*case',
        "边界条件": r'边界条件|boundary|edge.*case',
        "状态转换": r'状态转换|state.*transition|状态机',
        "安全测试": r'安全测试|security|XSS|SQL.*注入|越权',
        "性能测试": r'性能测试|performance|QPS|并发',
        "兼容性测试": r'兼容性测试|compatibility|backward',
        "自动化建议": r'自动化测试|pytest|go.*test|mock',
    }
    
    dimension_scores = {}
    for name, pattern in dimensions.items():
        found = bool(re.search(pattern, test_report, re.IGNORECASE))
        dimension_scores[name] = 1.0 if found else 0.0
    
    avg_dim_score = sum(dimension_scores.values()) / len(dimension_scores)
    covered_dims = [k for k, v in dimension_scores.items() if v > 0]
    report.add_metric(EvalMetric("dimension_coverage", avg_dim_score, 1.0,
                                 f"覆盖 {len(covered_dims)}/{len(dimensions)} 个测试维度: {covered_dims[:4]}"))
    
    # 4. 错误码引用
    error_codes = re.findall(r'[Ee]rr[A-Z]\d+|ERROR_\w+|errCode|错误码', test_report)
    actual_codes = set()
    if isinstance(ir_data, dict):
        for ec in ir_data.get('error_codes', []):
            if isinstance(ec, dict):
                actual_codes.add(ec.get('name', '').lower())
            else:
                actual_codes.add(str(ec).lower())
    
    if error_codes and actual_codes:
        matched = sum(1 for ec in error_codes if ec.lower() in ' '.join(actual_codes))
        code_ratio = min(matched / max(len(error_codes), 1), 1.0)
        report.add_metric(EvalMetric("error_code_accuracy", code_ratio, 1.0,
                                     f"错误码匹配率: {matched}/{len(error_codes)}"))
    elif not error_codes:
        report.add_metric(EvalMetric("error_code_accuracy", 0.3, 1.0, "未引用具体错误码", "warn"))
    else:
        report.add_metric(EvalMetric("error_code_accuracy", 1.0, 1.0, "IR 中无错误码定义"))
    
    # 5. 路由/接口覆盖
    routes_in_ir = set()
    if isinstance(ir_data, dict):
        for route in ir_data.get('routes', [])[:30]:
            if isinstance(route, dict):
                routes_in_ir.add(route.get('path', ''))
            else:
                routes_in_ir.add(getattr(route, 'path', ''))
    
    routes_referenced = sum(1 for r in routes_in_ir if r and r in test_report)
    route_ratio = min(routes_referenced / max(len(routes_in_ir), 1), 1.0)
    report.add_metric(EvalMetric("route_coverage", route_ratio, 1.0,
                                 f"覆盖 {routes_referenced}/{len(routes_in_ir)} 个路由"))
    
    # 6. Mock 策略
    mock_indicators = ['Mock', 'gomock', 'mock', 'stub', 'fake', 'testcontainers']
    mock_hits = sum(1 for ind in mock_indicators if ind in test_report)
    if mock_hits >= 2:
        report.add_metric(EvalMetric("mock_strategy", 1.0, 1.0, f"包含 {mock_hits} 项 Mock 策略"))
    else:
        report.add_metric(EvalMetric("mock_strategy", 0.4, 1.0, "Mock 策略不够详细", "warn"))
    
    # 7. 自动化测试代码
    code_gen_indicators = ['_test.go', 'pytest', 'go test', 'TestFunc', 'func Test']
    code_gen_hits = sum(1 for ind in code_gen_indicators if ind in test_report)
    if code_gen_hits >= 2:
        report.add_metric(EvalMetric("code_generation", 1.0, 1.0, "包含自动化测试代码模板"))
    else:
        report.add_metric(EvalMetric("code_generation", 0.5, 1.0, "未提供自动化测试代码模板", "info"))
    
    report.summary = {
        "status": "completed",
        "total_test_cases": tc_count,
        "p0_count": p0_tc,
        "p1_count": p1_tc,
        "p2_count": p2_tc,
        "dimensions_covered": len(covered_dims),
        "total_dimensions": len(dimensions),
        "routes_covered": routes_referenced,
        "total_routes": len(routes_in_ir),
    }
    
    return report


# ──────────────────────────────────────────────
# 4. 端到端一致性评估
# ──────────────────────────────────────────────

def eval_consistency(prd_text: str, review_report: str, td_report: str, test_report: str, 
                     ir_data: dict) -> EvalReport:
    """评估三阶段一致性。
    
    检查项：
    1. PRD 需求是否在审查中被识别
    2. 审查发现的问题是否在 TD 中得到解决
    3. TD 的设计是否在测试用例中得到验证
    4. 关键实体在三个阶段的一致性
    5. 核心流程的连贯性
    """
    report = EvalReport(mode="consistency")
    
    # 1. PRD 关键词提取
    prd_keywords = re.findall(r'[A-Z][a-z]+(?:[A-Z][a-z]+)*|[^\s]{2,8}', prd_text)
    prd_entities = set(kw for kw in prd_keywords if len(kw) >= 3)
    
    # 2. 审查报告中的实体覆盖
    review_entity_hits = sum(1 for ent in prd_entities if ent.lower() in review_report.lower())
    review_coverage = review_entity_hits / max(len(prd_entities), 1)
    report.add_metric(EvalMetric("prd_to_review_coverage", review_coverage, 1.0,
                                 f"PRD 实体在审查中覆盖: {review_entity_hits}/{len(prd_entities)}"))
    
    # 3. TD 对审查问题的响应
    if review_report and td_report:
        review_issues = re.findall(r'\[?(P\d)\]?.*?(?:阻塞|重要|一般)', review_report, re.IGNORECASE)
        td_issue_refs = sum(1 for issue in review_issues if issue.lower() in td_report.lower())
        if review_issues:
            response_ratio = td_issue_refs / len(review_issues)
            report.add_metric(EvalMetric("review_to_td_response", response_ratio, 1.0,
                                         f"TD 回应了 {td_issue_refs}/{len(review_issues)} 个审查问题"))
        else:
            report.add_metric(EvalMetric("review_to_td_response", 1.0, 1.0, "审查无明确问题列表"))
    else:
        report.add_metric(EvalMetric("review_to_td_response", 0.5, 1.0, "缺少审查或 TD 报告"))
    
    # 4. 测试对 TD 设计的验证
    if td_report and test_report:
        td_interfaces = re.findall(r'(?:POST|GET|PUT|DELETE)\s+/[\w/-]+', td_report)
        test_interface_refs = sum(1 for iface in td_interfaces if iface in test_report)
        if td_interfaces:
            test_coverage = test_interface_refs / len(td_interfaces)
            report.add_metric(EvalMetric("td_to_test_coverage", test_coverage, 1.0,
                                         f"测试覆盖了 {test_interface_refs}/{len(td_interfaces)} 个 TD 接口"))
        else:
            report.add_metric(EvalMetric("td_to_test_coverage", 0.7, 1.0, "TD 中未明确列出接口"))
    else:
        report.add_metric(EvalMetric("td_to_test_coverage", 0.5, 1.0, "缺少 TD 或测试报告"))
    
    # 5. 核心流程连贯性
    core_flows_list = []
    if isinstance(ir_data, dict):
        core_flows_list = ir_data.get('core_flows', [])
    
    if core_flows_list:
        flow_names = [cf.get('flow_name', '') if isinstance(cf, dict) else str(cf) 
                      for cf in core_flows_list[:5]]
        flows_in_prd = sum(1 for fn in flow_names if fn and fn in prd_text)
        flows_in_review = sum(1 for fn in flow_names if fn and fn in (review_report or ""))
        flows_in_td = sum(1 for fn in flow_names if fn and fn in (td_report or ""))
        flows_in_test = sum(1 for fn in flow_names if fn and fn in (test_report or ""))
        
        total_flows = max(len(flow_names), 1)
        consistency_score = (flows_in_prd + flows_in_review + flows_in_td + flows_in_test) / (total_flows * 4)
        report.add_metric(EvalMetric("flow_consistency", consistency_score, 1.0,
                                     f"核心流程在各阶段的连贯性: {consistency_score:.0%}"))
    else:
        report.add_metric(EvalMetric("flow_consistency", 0.5, 1.0, "IR 中无核心流程数据"))
    
    report.summary = {
        "status": "completed",
        "prd_entities": len(prd_entities),
        "review_coverage": f"{review_coverage:.0%}",
        "flow_consistency": f"{consistency_score:.0%}" if 'consistency_score' in dir() else "N/A",
    }
    
    return report


# ──────────────────────────────────────────────
# 5. 主入口
# ──────────────────────────────────────────────

def run_evaluation(mode: str, profile_path: str, output_dir: str, 
                   prd_text: Optional[str] = None) -> dict:
    """运行端到端评估。
    
    Args:
        mode: 'full' | 'review' | 'td' | 'test' | 'consistency'
        profile_path: Profile JSON 路径
        output_dir: 输出目录
        prd_text: PRD 文本（可选，用于一致性评估）
    
    Returns:
        评估结果字典
    """
    sys.path.insert(0, str(Path(__file__).parent))
    
    # 加载 profile
    with open(profile_path) as f:
        profile = json.load(f)
    
    # 加载 IR 数据
    ir_cache_path = Path(output_dir) / "ir_cache.json"
    ir_data = {}
    if ir_cache_path.exists():
        try:
            with open(ir_cache_path) as f:
                ir_data = json.load(f)
        except Exception:
            pass
    
    # 加载各阶段报告
    review_report = load_report(os.path.join(output_dir, "review_report.md"))
    td_report = load_report(os.path.join(output_dir, "technical_design.md"))
    test_report = load_report(os.path.join(output_dir, "test_cases.md"))
    
    results = {}
    
    if mode in ("full", "review"):
        print("\n📋 Evaluating Review Quality...")
        review_eval = eval_review_quality(review_report or "", ir_data, prd_text or "")
        results["review"] = review_eval.to_dict()
        print(f"  Score: {results['review']['total_score']:.1f}/100")
    
    if mode in ("full", "td"):
        print("\n📋 Evaluating TD Quality...")
        td_eval = eval_td_quality(td_report or "", ir_data, review_report or "", prd_text or "")
        results["td"] = td_eval.to_dict()
        print(f"  Score: {results['td']['total_score']:.1f}/100")
    
    if mode in ("full", "test"):
        print("\n📋 Evaluating Test Quality...")
        test_eval = eval_test_quality(test_report or "", ir_data, td_report or "", prd_text or "")
        results["test"] = test_eval.to_dict()
        print(f"  Score: {results['test']['total_score']:.1f}/100")
    
    if mode in ("full", "consistency"):
        print("\n📋 Evaluating Cross-Stage Consistency...")
        consistency_eval = eval_consistency(
            prd_text or "", review_report or "", td_report or "", test_report or "", ir_data
        )
        results["consistency"] = consistency_eval.to_dict()
        print(f"  Score: {results['consistency']['total_score']:.1f}/100")
    
    # 汇总
    overall_score = 0
    total_metrics = 0
    for section in results.values():
        overall_score += section.get("total_score", 0)
        total_metrics += 1
    
    final_result = {
        "mode": mode,
        "overall_score": round(overall_score / max(total_metrics, 1), 1),
        "sections": results,
        "timestamp": __import__('datetime').datetime.now().isoformat(),
    }
    
    # 保存评估报告
    eval_output_path = Path(output_dir) / "evaluation.json"
    with open(eval_output_path, 'w', encoding='utf-8') as f:
        json.dump(final_result, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Evaluation saved to: {eval_output_path}")
    
    return final_result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Biz-Delivery End-to-End Evaluation")
    parser.add_argument("--profile", required=True, help="Profile JSON path")
    parser.add_argument("--output-dir", required=True, help="Output directory with reports")
    parser.add_argument("--mode", default="full", 
                       choices=["full", "review", "td", "test", "consistency"],
                       help="Evaluation mode")
    parser.add_argument("--prd-text", default=None, help="PRD text for consistency evaluation")
    parser.add_argument("--output", default=None, help="Output file for evaluation result (default: output_dir/evaluation.json)")
    
    args = parser.parse_args()
    
    result = run_evaluation(
        mode=args.mode,
        profile_path=args.profile,
        output_dir=args.output_dir,
        prd_text=args.prd_text,
    )
    
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Overall Score: {result['overall_score']:.1f}/100")
    
    for section, data in result['sections'].items():
        print(f"\n  {section.upper()}: {data['total_score']:.1f}/100")
        for m in data.get('metrics', []):
            status = "❌" if m['severity'] == 'critical' else ("⚠️" if m['severity'] == 'warn' else "✅")
            print(f"    {status} {m['name']}: {m['score']}/{m['max_score']} - {m['details']}")
    
    # Save to custom output if specified
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved to: {args.output}")


if __name__ == "__main__":
    main()
