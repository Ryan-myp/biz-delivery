#!/usr/bin/env python3
"""Hook: 业务术语映射

将业务术语映射到代码关键词，用于证据查询和代码扫描。

Usage:
    from hooks.map_terms import map_terms
    
    keywords = map_terms({"素材审核": "creative_review", ...})
"""

from typing import Dict, List


def map_terms(terms: Dict[str, str]) -> Dict[str, List[str]]:
    """将业务术语映射到代码关键词
    
    Args:
        terms: 业务术语字典，key 为业务术语，value 为解释
        
    Returns:
        映射结果，key 为业务术语，value 为代码关键词列表
        
    Example:
        >>> map_terms({"素材审核": "素材审核流程"})
        {
            "素材审核": ["creative_review", "review_creative", "审核素材"],
            "广告组": ["adgroup", "ad_group", "AdGroup"]
        }
    """
    mappings = {}
    
    for term, desc in terms.items():
        # 默认映射策略：
        # 1. 保留原始术语
        # 2. 生成驼峰和下划线版本
        # 3. 添加常见变体
        
        keywords = [term]
        
        # 添加英文翻译（如果术语是中文）
        if any('\u4e00' <= c <= '\u9fff' for c in term):
            # 简单映射表（可扩展）
            english_map = {
                "素材": ["creative", "material"],
                "审核": ["review", "audit"],
                "广告组": ["adgroup", "ad_group"],
                "广告计划": ["campaign"],
                "竞价": ["bidding", "bid"],
                "投放": ["delivery", "publish"],
                "权限": ["permission", "auth"],
                "配置": ["config"],
            }
            for keyword, engs in english_map.items():
                if keyword in term:
                    keywords.extend(engs)
        
        # 添加驼峰和下划线版本
        lower = term.lower()
        keywords.append(lower.replace(" ", "_"))
        keywords.append(lower.replace(" ", ""))
        
        mappings[term] = list(set(keywords))
    
    return mappings


def get_domain_keywords(domain: str) -> Dict[str, List[str]]:
    """根据业务域返回默认术语映射
    
    Args:
        domain: 业务域名，如 "creative-platform", "ad-platform"
        
    Returns:
        默认术语映射表
    """
    default_mappings = {
        "creative-platform": {
            "素材": ["creative", "material", "media"],
            "广告组": ["adgroup", "ad_group"],
            "模板": ["template"],
            "分享": ["share"],
            "合作伙伴": ["partner", "pns"],
        },
        "ad-platform": {
            "广告计划": ["campaign"],
            "创意": ["creative"],
            "定向": ["targeting"],
            "出价": ["bidding", "bid"],
            "投放": ["delivery", "publish"],
        },
    }
    
    return default_mappings.get(domain, {})
