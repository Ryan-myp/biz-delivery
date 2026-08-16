"""
biz-delivery Web UI - 基于Streamlit的可视化界面
提供交互式专家审查、文档生成、质量门禁等功能

核心功能:
  1. PRD专家审查
  2. 文档自动生成
  3. 质量门禁检查
  4. 案例学习浏览
  5. 质量趋势可视化
"""
import streamlit as st
import sys
import os
from pathlib import Path
from datetime import datetime
import json

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.expert_system import SeniorExpertSystem
from scripts.case_learning_engine import CaseLearningEngine, init_sample_cases
from scripts.quality_gate_cli import QualityGateCLI
from scripts.performance_optimizer import get_optimizer
from skills.documentation.doc_skill_v2 import DocumentationSkillV2


def main():
    """主函数"""
    # 页面配置
    st.set_page_config(
        page_title="biz-delivery 专家系统",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # 初始化
    if 'expert' not in st.session_state:
        st.session_state.expert = SeniorExpertSystem()
    if 'cases' not in st.session_state:
        st.session_state.cases = init_sample_cases()
    if 'gate' not in st.session_state:
        st.session_state.gate = QualityGateCLI()
    if 'optimizer' not in st.session_state:
        st.session_state.optimizer = get_optimizer()

    # 侧边栏
    st.sidebar.title("🎯 biz-delivery")
    st.sidebar.markdown("---")
    
    menu = st.sidebar.radio(
        "选择功能",
        ["📋 PRD审查", "📝 文档生成", "🏷️ 质量门禁", "📚 案例学习", "📊 质量趋势", "⚙️ 系统设置"]
    )

    # 主内容区
    if menu == "📋 PRD审查":
        render_prd_review()
    elif menu == "📝 文档生成":
        render_doc_generation()
    elif menu == "🏷️ 质量门禁":
        render_quality_gate()
    elif menu == "📚 案例学习":
        render_case_learning()
    elif menu == "📊 质量趋势":
        render_quality_trend()
    elif menu == "⚙️ 系统设置":
        render_settings()


def render_prd_review():
    """PRD审查页面"""
    st.title("📋 PRD专家审查")
    st.markdown("输入产品需求文档，系统将进行多维度专家审查")

    # 输入区
    col1, col2 = st.columns([3, 1])
    with col1:
        prd_content = st.text_area(
            "请输入PRD内容",
            height=300,
            placeholder="# 项目名称\n\n## 背景\n...\n\n## 功能需求\n...",
            key="prd_input",
        )
    with col2:
        st.markdown("### 快速模板")
        if st.button("广告竞价"):
            st.session_state.prd_template = """# 广告竞价引擎优化\n\n## 背景\n当前DSP系统QPS 5万，P99延迟150ms，需优化到P99<100ms。\n\n## 功能需求\n1. 竞价引擎优化 - RTB实时竞价\n2. 预算追踪 - 预扣机制防超投\n3. 降级策略 - 画像→规则→默认出价\n4. 反作弊 - 设备指纹+ML模型\n\n## 非功能需求\n- P99延迟 < 100ms\n- 预算超投率 < 0.1%\n- 可用性 99.99%"""
            st.rerun()
        if st.button("Agent平台"):
            st.session_state.prd_template = """# Agent平台设计\n\n## 背景\n需要构建支持多Agent协作的AI平台\n\n## 功能需求\n1. ReAct模式支持\n2. 记忆系统（短期+长期）\n3. Tool调用框架\n4. 安全Guardrails\n\n## 非功能需求\n- Token成本控制\n- 响应延迟 < 2s\n- 安全性"""
            st.rerun()
        if st.button("电商系统"):
            st.session_state.prd_template = """# 电商订单系统\n\n## 背景\n双11高并发场景，需要支撑10万QPS\n\n## 功能需求\n1. 订单状态机\n2. 库存预扣\n3. 支付Saga\n4. 幂等控制\n\n## 非功能需求\n- P99 < 200ms\n- 零超卖\n- 99.99%可用性"""
            st.rerun()

    # 审查按钮
    if st.button("🔍 开始审查", type="primary", disabled=not prd_content):
        with st.spinner("正在进行专家审查..."):
            result = st.session_state.expert.review(prd_content)
            st.session_state.last_review = result
            st.success("审查完成!")

    # 显示结果
    if 'last_review' in st.session_state:
        result = st.session_state.last_review
        st.markdown("---")
        
        # 基本信息
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("识别领域", result['domain'])
        with col2:
            value = result.get('analysis', {}).get('business_value', {})
            st.metric("业务价值", f"{value.get('score', 0)}/100")
        with col3:
            feasibility = result.get('analysis', {}).get('technical_feasibility', {})
            st.metric("技术可行性", feasibility.get('feasibility', 'N/A'))

        st.markdown("---")
        
        # 展开详细分析
        with st.expander("📊 详细分析", expanded=True):
            # 业务价值
            st.subheader("业务价值评估")
            value = result.get('analysis', {}).get('business_value', {})
            st.markdown(f"""
            - **目标用户**: {'✅ 已定义' if value.get('has_target_user') else '❌ 缺失'}
            - **量化指标**: {'✅ 已定义' if value.get('has_quantified_metrics') else '❌ 缺失'}
            - **商业价值**: {'✅ 已说明' if value.get('has_business_value') else '❌ 缺失'}
            - **建议**: {value.get('recommendation', '')}
            """)

            # 技术可行性
            st.subheader("技术可行性")
            tech = result.get('analysis', {}).get('technical_feasibility', {})
            if tech.get('items_checked'):
                for item in tech['items_checked']:
                    icon = "✅" if item.get('covered') else "⚠️"
                    st.markdown(f"- {icon} {item.get('item')}: {'已覆盖' if item.get('covered') else '未覆盖'}")
            
            # 风险
            st.subheader("风险评估")
            risks = result.get('analysis', {}).get('risk_assessment', [])
            for risk in risks[:5]:
                level = risk.get('level', '中')
                icon = "🔴" if level == '高' else "🟡" if level == '中' else "🟢"
                st.markdown(f"- {icon} **{level}**: {risk.get('risk', '')}")
                if risk.get('mitigation'):
                    st.markdown(f"  - 💡 缓解措施: {risk['mitigation']}")

            # 建议
            st.subheader("优化建议")
            suggestions = result.get('analysis', {}).get('optimization_suggestions', [])
            for sug in suggestions[:5]:
                st.markdown(f"- **[{sug.get('type', '')}]** {sug.get('suggestion', '')}")

        # 模式检测
        with st.expander("🔍 模式检测"):
            patterns = st.session_state.expert.detect_patterns(prd_content, result['domain'])
            if patterns:
                for p in patterns:
                    st.markdown(f"### {p['name']}")
                    st.markdown(f"**指标**: {', '.join(p['indicators'])}")
                    for s in p['suggestions'][:3]:
                        st.markdown(f"- 💡 {s}")
            else:
                st.info("未检测到特殊模式")

        # 导出
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 导出JSON"):
                json_str = json.dumps(result, ensure_ascii=False, indent=2)
                st.download_button("下载JSON", data=json_str, file_name="review_result.json", mime="application/json")
        with col2:
            if st.button("📄 导出报告"):
                st.markdown(result.get('report', ''))


def render_doc_generation():
    """文档生成页面"""
    st.title("📝 文档自动生成")
    st.markdown("基于PRD和代码自动生成本地化文档")

    col1, col2 = st.columns([2, 1])
    
    with col1:
        prd_content = st.text_area("PRD内容", height=200, key="doc_prd")
        code_path = st.text_input("代码路径", value="/Users/yanping.ma/biz-delivery", key="doc_path")
    
    with col2:
        st.markdown("### 文档类型")
        doc_types = st.multiselect(
            "选择文档类型",
            ["readme", "api", "architecture", "changelog", "contributing", "security"],
            default=["readme", "api"],
            key="doc_types",
        )
        domain = st.selectbox(
            "选择领域",
            ["advertising", "agent", "ecommerce", "finance", "cloud_native", 
             "devops", "data_engineering", "security", "ml_ops", "gaming", 
             "iot", "saas", "social", "logistics", "fullstack"],
            index=0,
            key="doc_domain",
        )

    if st.button("🚀 生成文档", type="primary"):
        with st.spinner("正在生成文档..."):
            doc_skill = DocumentationSkillV2({"output_dir": "/tmp/web-docs"})
            result = doc_skill.run({
                "code_path": code_path,
                "domain": domain,
                "doc_types": doc_types,
                "prd_content": prd_content,
            })
            
            if result.success:
                st.success(f"✅ 成功生成 {len(result.output.get('files_generated', []))} 个文档")
                
                # 显示生成的文件
                for f in result.output.get('files_generated', []):
                    with st.expander(f"📄 {Path(f).name}"):
                        try:
                            content = Path(f).read_text()
                            st.code(content, language="markdown")
                        except:
                            st.error("无法读取文件内容")
            else:
                st.error(f"生成失败: {result.errors}")


def render_quality_gate():
    """质量门禁页面"""
    st.title("🏷️ 质量门禁")
    st.markdown("检查项目质量，生成质量报告")

    output_dir = st.text_input("输出目录", value="/tmp/biz-delivery-quality", key="quality_dir")
    
    col1, col2 = st.columns(2)
    with col1:
        strict = st.checkbox("严格模式 (70分通过)", value=False, key="quality_strict")
    with col2:
        if st.button("🔍 执行检查", type="primary"):
            with st.spinner("正在执行质量检查..."):
                result = st.session_state.gate.check(output_dir, strict)
                st.session_state.last_quality = result
    
    if 'last_quality' in st.session_state:
        result = st.session_state.last_quality
        
        # 显示评分
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("质量得分", f"{result['score']}/{result['max_score']}")
        with col2:
            rating_colors = {'A+': 'green', 'A': 'green', 'B+': 'blue', 'B': 'orange', 'C': 'red'}
            st.markdown(f"### <span style='color:{rating_colors.get(result['rating'], 'gray')}'>评级: {result['rating']}</span>", unsafe_allow_html=True)
        with col3:
            st.metric("通过率", "✅ 通过" if result['passed'] else "❌ 不通过")
        
        # 检查详情
        st.markdown("---")
        st.subheader("检查项详情")
        for name, data in result['checks'].items():
            icon = "✅" if data['passed'] else "❌"
            st.markdown(f"- {icon} **{name}**: {data['detail']} ({data['weight']}分)")
        
        # 生成HTML报告
        if st.button("📊 生成HTML报告"):
            report_path = st.session_state.gate.generate_html_report(
                result, f"{output_dir}/quality_report.html"
            )
            st.success(f"报告已生成: {report_path}")
            with open(report_path) as f:
                st.components.v1.html(f.read(), height=600)


def render_case_learning():
    """案例学习页面"""
    st.title("📚 案例学习")
    st.markdown("浏览专家案例，学习最佳实践")

    cases = st.session_state.cases
    
    # 统计信息
    stats = cases.get_stats()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总案例数", stats['total_cases'])
    with col2:
        st.metric("成功率", stats['success_rate'])
    with col3:
        st.metric("领域覆盖", len(stats['by_domain']))
    
    st.markdown("---")
    
    # 案例列表
    st.subheader("案例列表")
    for case in cases.cases:
        with st.expander(f"📋 {case.case_id} - {case.domain}"):
            st.markdown(f"**领域**: {case.domain} ({case.sub_domain})")
            st.markdown(f"**摘要**: {case.prd_summary}")
            st.markdown(f"**结果**: {case.outcome}")
            st.markdown(f"**质量分**: {case.quality_score}/100")
            
            col1, col2 = st.columns(2)
            with col1:
                if case.issues_found:
                    st.markdown("**问题**:")
                    for issue in case.issues_found[:3]:
                        st.markdown(f"- {issue.get('name', '')}")
            with col2:
                if case.solutions:
                    st.markdown("**解决方案**:")
                    for sol in case.solutions[:3]:
                        st.markdown(f"- {sol.get('solution', '')}")
            
            if case.lessons:
                st.markdown("**经验教训**:")
                for lesson in case.lessons:
                    st.markdown(f"- 💡 {lesson}")


def render_quality_trend():
    """质量趋势页面"""
    st.title("📊 质量趋势")
    st.markdown("查看历史质量数据趋势")

    days = st.slider("查询天数", 1, 90, 30, key="trend_days")
    
    trend = st.session_state.gate.get_trend(days)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("趋势", trend.get('trend', 'no_data'))
    with col2:
        st.metric("检查次数", trend.get('checks_count', 0))
    with col3:
        st.metric("平均分", f"{trend.get('avg_score', 0):.1f}")
    with col4:
        st.metric("最新评分", f"{trend.get('latest', {}).get('percentage', 0)}%")
    
    # 显示历史数据
    st.markdown("---")
    st.subheader("历史记录")
    
    if trend.get('checks_count', 0) > 0:
        for h in st.session_state.gate.history[-10:]:
            st.markdown(f"- {h['timestamp']}: **{h['rating']}** ({h['percentage']}%)")
    else:
        st.info("暂无历史记录")


def render_settings():
    """系统设置页面"""
    st.title("⚙️ 系统设置")
    
    st.markdown("---")
    st.subheader("性能统计")
    opt = st.session_state.optimizer
    stats = opt.get_stats()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("缓存命中率", stats.get('hit_rate', '0%'))
        st.metric("缓存大小", stats.get('memory_cache_size', 0))
    with col2:
        st.metric("并行调用", stats.get('parallel_calls', 0))
        st.metric("顺序调用", stats.get('sequential_calls', 0))
    
    st.markdown("---")
    st.subheader("系统信息")
    st.markdown("""
    - **版本**: biz-delivery v2.0
    - **领域覆盖**: 15个
    - **专家规则**: 275+条
    - **知识库文档**: 1787篇
    - **预置案例**: 7个
    """)
    
    if st.button("🗑️ 清空缓存"):
        opt.cache.clear()
        st.success("缓存已清空")


if __name__ == "__main__":
    main()
