#!/usr/bin/env python3
"""Hook: 业务专属测试维度

定义特定业务的测试维度和用例生成策略。

Usage:
    from hooks.test_dimensions import get_test_dimensions
    
    dimensions = get_test_dimensions(profile)
"""

from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class TestDimension:
    name: str
    description: str
    priority: int  # 1-5, 越高越重要
    templates: List[str]  # 测试用例模板


def get_test_dimensions(profile: Dict[str, Any]) -> List[TestDimension]:
    """根据业务 Profile 获取测试维度
    
    Args:
        profile: 业务 Profile
        
    Returns:
        测试维度列表
    """
    # 通用测试维度
    dimensions = [
        TestDimension(
            name="正向流程",
            description="验证主业务流程是否正常",
            priority=5,
            templates=["create", "read", "update", "delete"]
        ),
        TestDimension(
            name="异常处理",
            description="验证异常情况下的错误处理",
            priority=4,
            templates=["error_handling", "exception"]
        ),
        TestDimension(
            name="边界条件",
            description="验证边界值处理",
            priority=4,
            templates=["boundary", "empty", "max", "min"]
        ),
        TestDimension(
            name="权限控制",
            description="验证权限拦截",
            priority=3,
            templates=["auth", "permission"]
        ),
    ]
    
    # 根据业务域添加专属维度
    business_domain = profile.get("business_domain", "")
    
    if business_domain == "creative-platform":
        dimensions.extend([
            TestDimension(
                name="素材格式",
                description="验证不同素材格式的处理",
                priority=4,
                templates=["image", "video", "gif", "pdf"]
            ),
            TestDimension(
                name="渠道兼容",
                description="验证多渠道发布兼容性",
                priority=4,
                templates=["meta", "tiktok", "dv360"]
            ),
            TestDimension(
                name="状态转换",
                description="验证广告组状态机转换",
                priority=5,
                templates=["init_to_submitted", "submitted_to_shared", "shared_to_live"]
            ),
        ])
    
    elif business_domain == "ad-platform":
        dimensions.extend([
            TestDimension(
                name="竞价策略",
                description="验证不同竞价策略的正确性",
                priority=5,
                templates=["cpc", "cpm", "ocpx"]
            ),
            TestDimension(
                name="预算控制",
                description="验证预算限制和消耗控制",
                priority=4,
                templates=["daily_budget", "lifetime_budget"]
            ),
        ])
    
    # 从 profile 中读取自定义维度
    custom_dimensions = profile.get("test_dimensions", [])
    for dim in custom_dimensions:
        dimensions.append(TestDimension(
            name=dim.get("name", "unknown"),
            description=dim.get("description", ""),
            priority=dim.get("priority", 3),
            templates=dim.get("templates", [])
        ))
    
    # 按优先级排序
    dimensions.sort(key=lambda x: x.priority, reverse=True)
    
    return dimensions


def get_test_templates(profile: Dict[str, Any], dimension_name: str) -> List[str]:
    """获取指定维度的测试模板
    
    Args:
        profile: 业务 Profile
        dimension_name: 维度名称
        
    Returns:
        测试模板列表
    """
    dimensions = get_test_dimensions(profile)
    for dim in dimensions:
        if dim.name == dimension_name:
            return dim.templates
    return []
