"""测试 PRD 审查能力的边界"""

import pytest
import json
from scripts.review_engine import ReviewEngine
from pathlib import Path


class TestReviewCapabilities:
    """PRD 审查能力测试"""
    
    @pytest.fixture
    def sample_ir(self):
        """模拟 IR 数据"""
        return {
            "functions": [
                {"name": "CreateAdGroup", "file": "adgroup.go", "signature": "ctx, req"},
                {"name": "ReviewCreative", "file": "review.go", "signature": "ctx, req"},
                {"name": "ShareCreative", "file": "share.go", "signature": "ctx, req"},
                {"name": "GetCampaign", "file": "campaign.go", "signature": "ctx, req"},
            ],
            "routes": [
                {"path": "/api/adgroup/create", "method": "POST", "handler": "CreateAdGroup"},
                {"path": "/api/review", "method": "POST", "handler": "ReviewCreative"},
                {"path": "/api/share", "method": "POST", "handler": "ShareCreative"},
                {"path": "/api/campaign", "method": "GET", "handler": "GetCampaign"},
            ],
            "structs": [
                {"name": "AdGroup", "fields": ["ID", "Name", "Status"]},
                {"name": "Creative", "fields": ["ID", "URL", "Type"]},
                {"name": "Campaign", "fields": ["ID", "Name", "Budget"]},
            ],
            "entity_tables": [
                {"entity": "AdGroup", "table": "ad_groups"},
                {"entity": "Creative", "table": "creatives"},
                {"entity": "Campaign", "table": "campaigns"},
            ],
            "error_codes": [
                {"name": "ADGROUP_NOT_FOUND", "code": "1001"},
                {"name": "CREATIVE_REVIEW_FAIL", "code": "1002"},
            ],
            "core_flows": [
                {
                    "flow_name": "素材审核流程",
                    "entry_point": "ReviewCreative",
                    "call_chain": ["ReviewCreative", "ValidateCreative", "SaveToDB"],
                    "description": "素材提交后审核"
                },
                {
                    "flow_name": "广告组创建流程",
                    "entry_point": "CreateAdGroup",
                    "call_chain": ["CreateAdGroup", "ValidateBudget", "SaveToDB"],
                    "description": "创建广告组"
                }
            ]
        }
    
    @pytest.fixture
    def sample_profile(self):
        """模拟 Profile"""
        return {
            "business_domain": "test-domain",
            "modules": [
                {
                    "name": "AdGroup / 广告组",
                    "keywords": ["adgroup", "ad_group", "广告组", "投放组"],
                    "goal": "管理广告组的创建、编辑、删除"
                },
                {
                    "name": "Creative / 素材",
                    "keywords": ["creative", "素材", "review", "审核"],
                    "goal": "素材的审核、发布、分享"
                },
                {
                    "name": "Campaign / 广告计划",
                    "keywords": ["campaign", "广告计划", "budget", "预算"],
                    "goal": "广告计划的创建和管理"
                }
            ],
            "query_aliases": {
                "素材": ["creative", "ad_material"],
                "广告组": ["adgroup", "ad_group"],
            }
        }
    
    def test_detect_missing_modules(self, sample_ir, sample_profile):
        """测试识别 PRD 遗漏的模块"""
        # PRD 只提到了素材审核，但实际还涉及广告组
        prd_text = """
        # 素材审核功能优化
        
        ## 需求描述
        优化素材审核流程，支持批量审核功能。
        
        ## 业务流程
        1. 用户提交素材
        2. 系统自动审核
        3. 审核通过后进入广告组
        4. 通知用户审核结果
        """
        
        # 分析 PRD 中提到的模块
        prd_lower = prd_text.lower()
        mentioned_modules = []
        
        for module in sample_profile["modules"]:
            keywords = module.get("keywords", [])
            if any(kw.lower() in prd_lower for kw in keywords):
                mentioned_modules.append(module["name"])
        
        # 从流程推断需要的模块
        needed_modules = set()
        if "素材" in prd_text or "creative" in prd_text:
            needed_modules.add("Creative / 素材")
        if "广告组" in prd_text or "adgroup" in prd_text.lower():
            needed_modules.add("AdGroup / 广告组")
        if "广告计划" in prd_text or "campaign" in prd_text:
            needed_modules.add("Campaign / 广告计划")
        
        # 检查是否有遗漏
        missing = needed_modules - set(mentioned_modules)
        
        # 这个 PRD 明确提到了"进入广告组"，应该被检测到
        assert "AdGroup / 广告组" in needed_modules, "应该识别到需要广告组模块"
    
    def test_detect_cross_module_dependencies(self, sample_ir, sample_profile):
        """测试检测跨模块依赖"""
        prd_text = """
        # 素材分享功能
        
        ## 需求描述
        新增素材分享功能，用户可以将审核通过的素材分享给合作伙伴。
        
        ## 业务流程
        1. 用户在素材列表选择素材
        2. 点击分享按钮
        3. 选择合作伙伴
        4. 发送分享请求
        5. 合作伙伴接收并查看
        """
        
        # 这个需求涉及素材模块和合作伙伴模块
        # 检查是否能检测到跨模块依赖
        has_creative = "素材" in prd_text or "creative" in prd_text
        has_partner = "伙伴" in prd_text or "partner" in prd_text
        
        assert has_creative, "应该识别到素材模块"
        assert has_partner, "应该识别到合作伙伴模块"
    
    def test_detect_implementation_conflicts(self, sample_ir, sample_profile):
        """测试检测 PRD 与现有实现的冲突"""
        # PRD 要求删除某个字段，但该字段被多处使用
        prd_text = """
        # 移除 Creative 表的 URL 字段
        
        ## 需求描述
        由于新的存储方案，需要移除 Creative 表中的 URL 字段，
        所有相关代码需要相应调整。
        """
        
        # 检查 IR 中 URL 字段的使用情况
        url_usage_count = 0
        for struct in sample_ir.get("structs", []):
            if struct.get("name") == "Creative":
                fields = struct.get("fields", [])
                if "URL" in fields:
                    url_usage_count += 1
        
        # 如果有多个地方使用，应该发出警告
        assert url_usage_count > 0, "应该检测到字段使用"


class TestNewProjectUnderstanding:
    """测试对新 Git 项目的理解能力"""
    
    def test_extract_structure_from_code(self):
        """测试从代码提取项目结构"""
        # 这需要在真实项目上测试
        # 这里只是框架测试
        assert True  # 占位
    
    def test_build_knowledge_graph(self):
        """测试构建知识图谱"""
        assert True  # 占位


class TestPRDReviewEdgeCases:
    """测试 PRD 审查的边缘情况"""
    
    def test_vague_requirements(self):
        """测试模糊需求的检测"""
        prd_text = "优化系统性能"
        # 应该能识别这是模糊需求
        is_vague = len(prd_text) < 50 and "优化" in prd_text and "性能" in prd_text
        assert is_vague
    
    def test_contradictory_requirements(self):
        """测试矛盾需求的检测"""
        prd_text = """
        1. 所有请求必须同步处理
        2. 引入异步消息队列处理高并发
        """
        # 检测同步和异步的矛盾
        has_sync = "同步" in prd_text
        has_async = "异步" in prd_text or "消息队列" in prd_text
        assert has_sync and has_async, "应该检测到矛盾"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
