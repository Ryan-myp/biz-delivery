"""
Test Case Skill 实现
职责：根据 PRD 生成测试用例

纯确定性实现，基于模板生成
"""

import re
from typing import Any, Dict, List, Optional
from ..base import SkillBase, SkillResult


class TestCaseSkill(SkillBase):
    """测试用例生成 Skill - 基于模板生成"""
    
    REQUIRED_INPUT = ["prd_content"]
    
    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        super().__init__(profile)
    
    def run(self, input_data: Dict[str, Any]) -> SkillResult:
        """执行测试用例生成"""
        # 验证输入
        errors = self.validate_input(input_data)
        if errors:
            return SkillResult(success=False, errors=errors)
        
        prd_content = input_data["prd_content"]
        profile = input_data.get("profile", self.profile)
        
        try:
            # 从 PRD 提取功能点
            features = self._extract_features(prd_content)
            
            # 生成测试用例
            test_cases = self._generate_test_cases(features, profile)
            
            # 分类
            p0_cases = [c for c in test_cases if c["priority"] == "P0"]
            p1_cases = [c for c in test_cases if c["priority"] == "P1"]
            p2_cases = [c for c in test_cases if c["priority"] == "P2"]
            
            # 覆盖率估算
            coverage = self._estimate_coverage(test_cases, len(features))
            
            return SkillResult(
                success=True,
                output={
                    "test_cases": test_cases,
                    "total_cases": len(test_cases),
                    "p0_count": len(p0_cases),
                    "p1_count": len(p1_cases),
                    "p2_count": len(p2_cases),
                    "features_count": len(features),
                    "coverage_estimate": coverage,
                },
                metadata={
                    "skill": "test_case_generation",
                    "approach": "template_based",
                    "dimensions": self._get_dimensions(profile),
                }
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                errors=[f"Test case generation failed: {str(e)}"]
            )
    
    def _extract_features(self, prd_content: str) -> List[Dict]:
        """从 PRD 提取功能点"""
        features = []
        
        # 提取需求章节
        req_section = re.search(r"##\s*需求.*?\n(.*?)(?=##\s|$)", prd_content, re.DOTALL | re.IGNORECASE)
        if req_section:
            lines = [l.strip() for l in req_section.group(1).split('\n') if l.strip()]
            for line in lines[:10]:
                # 尝试提取功能点
                if line.startswith('-') or line.startswith('*'):
                    feature = line[1:].strip()
                else:
                    feature = line
                
                if feature:
                    features.append({
                        "name": feature,
                        "type": self._classify_feature(feature),
                    })
        
        # 提取 API
        apis = re.findall(r"(GET|POST|PUT|DELETE)\s+(/\S+)", prd_content)
        for method, path in apis[:5]:
            features.append({
                "name": f"{method} {path}",
                "type": "api",
            })
        
        return features
    
    def _classify_feature(self, feature: str) -> str:
        """分类功能点"""
        keywords = {
            "auth": ["登录", "注册", "认证", "授权", "token", "jwt"],
            "data": ["查询", "列表", "详情", "搜索", "过滤"],
            "create": ["创建", "新增", "提交", "保存"],
            "update": ["更新", "修改", "编辑", "变更"],
            "delete": ["删除", "移除", "注销"],
        }
        
        for ftype, kws in keywords.items():
            for kw in kws:
                if kw in feature:
                    return ftype
        
        return "other"
    
    def _generate_test_cases(self, features: List[Dict], profile: Dict) -> List[Dict]:
        """生成测试用例"""
        test_cases = []
        case_id = 1
        
        # 为每个功能点生成测试用例
        for feature in features:
            # 正向用例
            test_cases.append({
                "id": f"TC{case_id:03d}",
                "feature": feature["name"],
                "type": "positive",
                "priority": "P0",
                "description": f"验证 {feature['name']} 正常流程",
                "steps": [
                    f"准备 {feature['name']} 所需数据",
                    f"执行 {feature['name']} 操作",
                    "验证返回结果符合预期",
                ],
                "expected": f"{feature['name']} 操作成功",
            })
            case_id += 1
            
            # 异常用例
            test_cases.append({
                "id": f"TC{case_id:03d}",
                "feature": feature["name"],
                "type": "negative",
                "priority": "P1",
                "description": f"验证 {feature['name']} 异常情况",
                "steps": [
                    f"准备无效 {feature['name']} 数据",
                    f"执行 {feature['name']} 操作",
                    "验证返回错误信息",
                ],
                "expected": f"{feature['name']} 操作失败，返回错误码",
            })
            case_id += 1
            
            # 边界用例
            test_cases.append({
                "id": f"TC{case_id:03d}",
                "feature": feature["name"],
                "type": "boundary",
                "priority": "P2",
                "description": f"验证 {feature['name']} 边界条件",
                "steps": [
                    f"准备边界值 {feature['name']} 数据",
                    f"执行 {feature['name']} 操作",
                    "验证边界情况处理正确",
                ],
                "expected": f"边界情况下 {feature['name']} 正确处理",
            })
            case_id += 1
        
        return test_cases
    
    def _estimate_coverage(self, test_cases: List[Dict], feature_count: int) -> Dict:
        """估算覆盖率"""
        if feature_count == 0:
            return {"positive": 0, "negative": 0, "boundary": 0, "total": 0}
        
        positive = sum(1 for c in test_cases if c["type"] == "positive")
        negative = sum(1 for c in test_cases if c["type"] == "negative")
        boundary = sum(1 for c in test_cases if c["type"] == "boundary")
        
        return {
            "positive": positive,
            "negative": negative,
            "boundary": boundary,
            "total": len(test_cases),
            "positive_ratio": positive / max(len(test_cases), 1),
            "negative_ratio": negative / max(len(test_cases), 1),
            "boundary_ratio": boundary / max(len(test_cases), 1),
        }
    
    def _get_dimensions(self, profile: Dict) -> List[str]:
        """获取测试维度"""
        return profile.get("test_dimensions", ["正向流程", "异常分支", "边界条件", "性能测试", "安全测试"])
