#!/usr/bin/env python3
"""
biz-delivery 端到端流程测试

模拟真实项目流程：PRD → 审查 → TD → 测试用例
"""

import sys
import json
from pathlib import Path

# 添加 biz-delivery 路径
sys.path.insert(0, str(Path(__file__).parent))


class EndToEndTest:
    """端到端测试"""
    
    def __init__(self):
        from td_engine_v2 import TDEngine
        from review_engine import ReviewEngine
        from test_engine import TestEngine
        
        self.profile = {
            "name": "e2e-test-project",
            "repositories": [],
            "business_domain": "test",
        }
        self.output_dir = "/tmp/biz_e2e_test"
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        self.td_engine = TDEngine(self.profile, self.output_dir)
        self.review_engine = ReviewEngine(self.profile, self.output_dir)
        self.test_engine = TestEngine(self.profile, self.output_dir)
    
    def run_full_pipeline(self, prd_content: str) -> dict:
        """运行完整流程"""
        results = {}
        
        # Step 1: PRD 审查
        print("📋 Step 1: 审查 PRD...")
        review_result = self.review_engine.review(prd_content)
        results["review"] = review_result
        print(f"  ✅ 审查完成: {review_result.get('status', 'unknown')}")
        
        # Step 2: 生成 TD
        print("📝 Step 2: 生成技术方案...")
        td_result = self.td_engine.generate_td(prd_content, use_llm=False)
        results["td"] = td_result
        print(f"  ✅ TD 生成完成: {td_result.get('status', 'unknown')}")
        
        # Step 3: 生成测试用例
        print("🧪 Step 3: 生成测试用例...")
        test_result = self.test_engine.generate_tests(prd_content)
        results["tests"] = test_result
        print(f"  ✅ 测试用例生成完成: {test_result.get('status', 'unknown')}")
        
        # Step 4: 汇总结果
        print("📊 Step 4: 汇总结果...")
        results["summary"] = {
            "total_steps": 3,
            "completed_steps": 3,
            "all_passed": all(r.get("status") == "prompt_ready" 
                            for r in [review_result, td_result, test_result])
        }
        
        return results
    
    def test_with_real_prd(self):
        """使用真实 PRD 测试"""
        prd = """
# 用户出价系统

## 功能需求
1. 用户可以在广告列表页面设置出价
2. 出价支持手动和自动两种模式
3. 系统根据出价排名展示广告
4. 每日预算控制，超预算停止投放

## 数据模型
- 出价记录表: bids(id, user_id, ad_id, amount, mode, created_at)
- 预算表: budgets(id, campaign_id, daily_limit, spent, date)

## 接口需求
- POST /api/bids - 创建出价
- GET /api/bids/{id} - 查询出价
- PUT /api/bids/{id} - 更新出价
- DELETE /api/bids/{id} - 删除出价
"""
        
        print("=" * 60)
        print("    biz-delivery 端到端流程测试")
        print("=" * 60)
        print()
        
        results = self.run_full_pipeline(prd)
        
        print()
        print("=" * 60)
        print("    测试结果")
        print("=" * 60)
        print()
        
        if results["summary"]["all_passed"]:
            print("✅ 全流程测试通过！")
        else:
            print("❌ 全流程测试失败，请检查日志")
        
        # 保存结果
        result_file = Path(self.output_dir) / "e2e_result.json"
        result_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n📄 详细结果: {result_file}")
        
        return results


def main():
    test = EndToEndTest()
    test.test_with_real_prd()


if __name__ == "__main__":
    main()
