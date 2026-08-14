#!/usr/bin/env python3
"""LLM 增强摘要生成器 — 可选的专家级摘要增强.

使用 LLM 对模板化摘要进行增强，生成更专业、更深入的业务分析.

Usage:
    python3 llm_enhanced_summary.py --input summary.md --output enhanced.md [--model gpt-4]
    python3 llm_enhanced_summary.py --json analysis_result.json
"""

import json
import sys
from pathlib import Path
from typing import Dict, Optional


def generate_llm_prompt(ir_summary: Dict, patterns: Dict, stages: Dict) -> str:
    """生成 LLM 提示词."""
    return f"""你是一位资深技术专家，正在分析一个软件项目的代码库。请根据以下分析结果，生成一份专业的业务摘要报告。

## 项目基本信息
- 语言: {ir_summary.get('language', 'unknown')}
- 框架: {ir_summary.get('framework', 'unknown')}
- 架构: {ir_summary.get('architecture', 'unknown')}
- 规模: {ir_summary.get('scale', 'unknown')} ({ir_summary.get('total_files', 0)} 文件)
- 结构体: {ir_summary.get('structs', 0)}
- 函数: {ir_summary.get('functions', 0)}
- 路由: {ir_summary.get('routes', 0)}

## 架构模式检测
状态机: {len(patterns.get('state_machines', []))} 个
Redis锁: {len(patterns.get('redis_locks', []))} 个
重试机制: {len(patterns.get('retry_logic', []))} 个
Kafka: {len(patterns.get('kafka_patterns', []))} 个
幂等性: {len(patterns.get('idempotency', []))} 个
枚举: {len(patterns.get('enums', []))} 组

## 任务
请生成一份专业的中文业务摘要，包括:
1. 项目定位和核心价值
2. 关键技术架构选型分析
3. 核心业务流程描述
4. 设计模式和最佳实践
5. 潜在风险和优化建议

要求:
- 使用专业术语，体现资深专家视角
- 每个部分简洁有力，不超过3句话
- 突出项目的技术亮点和创新点
- 输出 Markdown 格式"""


def call_llm(prompt: str, model: str = "gpt-4", api_key: Optional[str] = None) -> Optional[str]:
    """调用 LLM API 生成增强摘要.
    
    支持 OpenAI-compatible API (如 OpenAI, Azure, 本地模型).
    """
    try:
        import openai
    except ImportError:
        print("⚠️  需要 openai 包: pip install openai")
        return None

    client = openai.OpenAI(
        api_key=api_key or sys.getenv("OPENAI_API_KEY"),
        base_url=sys.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一位资深技术架构师，擅长分析代码库并生成专业报告。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ LLM 调用失败: {e}")
        return None


def enhance_summary(input_path: str, output_path: str, model: str = "gpt-4", use_llm: bool = True) -> bool:
    """增强摘要文件."""
    # 读取原始分析结果
    result_json = Path(input_path) / "analysis_result.json"
    if not result_json.exists():
        print(f"❌ 找不到 {result_json}")
        return False

    with open(result_json) as f:
        data = json.load(f)

    ir_summary = data.get("ir_summary", {})
    stages = data.get("stages", {})
    patterns = stages.get("patterns", {})

    # 生成提示词
    prompt = generate_llm_prompt(ir_summary, patterns, stages)

    if not use_llm:
        # 使用模板化增强（无需 LLM）
        enhanced = generate_template_enhancement(ir_summary, patterns)
    else:
        # 调用 LLM
        print("🤖 调用 LLM 生成增强摘要...")
        enhanced = call_llm(prompt, model)
        if not enhanced:
            print("⚠️  LLM 调用失败，使用模板化增强")
            enhanced = generate_template_enhancement(ir_summary, patterns)

    # 写入增强摘要
    output_file = Path(output_path) / "enhanced_summary.md"
    output_file.write_text(enhanced, encoding="utf-8")
    print(f"✅ 增强摘要已保存: {output_file}")
    return True


def generate_template_enhancement(ir_summary: Dict, patterns: Dict) -> str:
    """生成模板化增强摘要（无需 LLM）."""
    lines = [
        "# 📊 项目业务深度分析报告（专家增强版）",
        "",
        f"**项目**: {ir_summary.get('project_path', 'unknown')}",
        f"**语言**: {ir_summary.get('language', 'unknown')} | **框架**: {ir_summary.get('framework', 'unknown')} | **架构**: {ir_summary.get('architecture', 'unknown')}",
        f"**规模**: {ir_summary.get('scale', 'unknown')} ({ir_summary.get('total_files', 0)} 文件)",
        "",
        "---",
        "",
        "## 一、项目定位与核心价值",
        "",
        f"这是一个 **{ir_summary.get('scale', 'unknown')}** 规模的 **{ir_summary.get('language', 'unknown')}** 项目，",
        f"采用 **{ir_summary.get('framework', 'unknown')}** 框架，架构风格为 **{ir_summary.get('architecture', 'unknown')}**。",
        "",
        "### 技术特点",
        "",
        f"- **代码规模**: {ir_summary.get('structs', 0)} 个结构体，{ir_summary.get('functions', 0)} 个函数，{ir_summary.get('routes', 0)} 个路由",
        f"- **架构复杂度**: {'高' if ir_summary.get('structs', 0) > 100 else '中' if ir_summary.get('structs', 0) > 50 else '低'}",
        "",
    ]

    # 架构模式分析
    sm_count = len(patterns.get('state_machines', []))
    redis_count = len(patterns.get('redis_locks', []))
    kafka_count = len(patterns.get('kafka_patterns', []))
    retry_count = len(patterns.get('retry_logic', []))
    enum_count = len(patterns.get('enums', []))

    lines.append("## 二、架构模式分析")
    lines.append("")

    if sm_count > 0:
        lines.append(f"### 状态机设计 ({sm_count} 个)")
        lines.append("项目使用了显式的状态机模式来管理业务流程状态，这是保证数据一致性和可追溯性的关键设计。")
        lines.append("")

    if redis_count > 0:
        lines.append(f"### 并发控制 ({redis_count} 个 Redis 锁)")
        lines.append("项目广泛使用 Redis 分布式锁来保证并发安全，说明系统具有较高的并发访问需求。")
        lines.append("")

    if kafka_count > 0:
        lines.append(f"### 异步解耦 ({kafka_count} 个 Kafka 消费/生产)")
        lines.append("项目通过 Kafka 实现服务间异步通信，有效解耦了核心业务流程，提升了系统可扩展性。")
        lines.append("")

    if retry_count > 0:
        lines.append(f"### 容错机制 ({retry_count} 个重试逻辑)")
        lines.append("项目实现了完善的重试机制，确保系统在部分失败时仍能保持可用性。")
        lines.append("")

    lines.append("## 三、专家评估")
    lines.append("")
    lines.append("### 优势")
    lines.append("- 架构清晰，模式规范")
    lines.append("- 并发控制完善，考虑了分布式场景")
    lines.append("- 异步处理合理，系统可扩展性强")
    lines.append("")

    lines.append("### 建议")
    lines.append("- 建议补充单元测试覆盖率")
    lines.append("- 考虑引入可观测性（Prometheus + Grafana）")
    lines.append("- 优化错误码标准化")
    lines.append("")

    lines.append("---")
    lines.append("*Generated by biz-delivery LLM Enhanced Summary*")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LLM 增强摘要生成")
    parser.add_argument("--input", required=True, help="分析输出目录")
    parser.add_argument("--output", help="输出目录（默认同输入）")
    parser.add_argument("--model", default="gpt-4", help="LLM 模型")
    parser.add_argument("--no-llm", action="store_true", help="使用模板化增强（不调用 LLM）")
    args = parser.parse_args()

    output_dir = args.output or args.input
    success = enhance_summary(args.input, output_dir, args.model, not args.no_llm)
    sys.exit(0 if success else 1)
