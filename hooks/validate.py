#!/usr/bin/env python3
"""Hook: 业务校验规则

定义 PRD 审查结果的校验规则，确保业务完整性。

Usage:
    from hooks.validate import validate
    
    result = validate(review_result, profile)
"""

from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum


class ValidationResult(Enum):
    PASS = "pass"
    NEEDS_REVISION = "needs_revision"
    BLOCKED = "blocked"
    PARTIAL = "partial"


@dataclass
class ValidationIssue:
    severity: str  # "error", "warning", "info"
    category: str  # "completeness", "correctness", "risk"
    message: str
    suggestion: str = ""


def validate(review_result: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    """校验 PRD 审查结果的业务完整性
    
    Args:
        review_result: 审查结果，包含 p0_issues, p1_issues, p2_issues 等
        profile: 业务 Profile 配置
        
    Returns:
        校验结果 dict，包含:
        - status: ValidationResult
        - issues: List[ValidationIssue]
        - summary: str
    """
    issues = []
    
    # 1. 检查是否有 P0 问题
    p0_issues = review_result.get("p0_issues", [])
    if p0_issues:
        issues.append(ValidationIssue(
            severity="error",
            category="completeness",
            message=f"发现 {len(p0_issues)} 个 P0 问题，需要解决后才能进入开发",
            suggestion="请优先处理 P0 问题"
        ))
    
    # 2. 检查必须检查项
    must_check = profile.get("review_rules", {}).get("must_check", [])
    if must_check:
        checked_sections = review_result.get("checked_sections", [])
        missing = [m for m in must_check if m not in checked_sections]
        if missing:
            issues.append(ValidationIssue(
                severity="warning",
                category="completeness",
                message=f"未检查以下项目: {', '.join(missing)}",
                suggestion="请补充检查这些项目"
            ))
    
    # 3. 检查状态机覆盖
    state_machines = profile.get("state_machines", {})
    if state_machines:
        # TODO: 检查状态转换是否完整
        pass
    
    # 4. 检查错误码覆盖
    error_codes = review_result.get("error_codes", [])
    if not error_codes and p0_issues:
        issues.append(ValidationIssue(
            severity="warning",
            category="correctness",
            message="有 P0 问题但未提供错误码定义",
            suggestion="请为每个 P0 问题定义错误码"
        ))
    
    # 5. 根据 quality_gate 判断最终状态
    quality_gate = profile.get("review_rules", {}).get("quality_gate", "needs_revision")
    
    if p0_issues:
        status = ValidationResult.BLOCKED
    elif quality_gate == "ready" and not p0_issues:
        status = ValidationResult.PASS
    else:
        status = ValidationResult.NEEDS_REVISION
    
    return {
        "status": status.value,
        "issues": [vars(i) for i in issues],
        "summary": f"校验完成: {status.value}, 共 {len(issues)} 个问题"
    }


def check_state_machine_coverage(profile: Dict[str, Any], prd_text: str) -> List[str]:
    """检查 PRD 是否覆盖了所有状态机转换
    
    Args:
        profile: 业务 Profile
        prd_text: PRD 内容
        
    Returns:
        未覆盖的状态转换列表
    """
    state_machines = profile.get("state_machines", {})
    uncovered = []
    
    for sm_name, sm_config in state_machines.items():
        values = sm_config.get("values", {})
        for code, status_name in values.items():
            if status_name not in prd_text:
                uncovered.append(f"{sm_name}.{status_name}")
    
    return uncovered
