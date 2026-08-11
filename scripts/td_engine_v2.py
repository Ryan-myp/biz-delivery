#!/usr/bin/env python3
"""技术方案生成引擎 v2 — 完整的 TD 生成流程（单步调用）

工作流程：
1. 扫描代码库获取 IR（缓存/并行/串行）
2. 基于 PRD + IR 自动生成完整 TD
3. 输出：架构图、数据模型、接口设计、风险评估

V2 改进：
- 单步调用：generate_td() 直接返回完整 TD
- 内置 LLM 调用：支持直接生成，无需两步流程
- 增强分析：新增变更影响分析、兼容性评估
- 代码级建议：基于 IR 给出具体实现指导
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from learn_repo import IRDocument
from base_engine import EngineBase

# LLM 配置（从环境变量读取）
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.agnes-ai.cn/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "agnes-2.5-flash")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8000"))


class TDEngine(EngineBase):
    """技术方案生成引擎 v2"""
    
    def __init__(self, profile: dict, output_dir: str, wiki_path: Optional[str] = None):
        super().__init__(profile, output_dir, wiki_path)
        
    def generate_td(self, prd_text: str, review_report: Optional[str] = None, 
                    use_llm: bool = True) -> dict:
        """生成技术方案（单步调用）
        
        Args:
            prd_text: PRD 内容
            review_report: 可选，PRD 审查报告
            use_llm: 是否使用 LLM 生成（True=直接生成，False=只生成 prompt）
            
        Returns:
            TD 生成结果 dict，包含 design 字段（完整技术方案）
        """
        # Step 0: 扫描代码库获取 IR
        print("📡 Step 0: Scanning codebase...")
        ir = self._scan_codebase()
        
        # Step 1: 查询代码库证据
        print("🔍 Step 1: Querying evidence from codebase...")
        cache_dir = str(self.output_dir)
        filtered = self._query_evidence_for_prd(prd_text, cache_dir)
        print(f"  Found {filtered.get('total', 0)} evidence items")
        
        # Step 2: 构建 TD prompt
        print("📝 Step 2: Building TD prompt...")
        prompt = self._build_td_prompt(filtered, ir, prd_text, review_report)
        
        # Step 3: 保存 prompt
        prompt_file = self.output_dir / "td_prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")
        print(f"✅ Prompt saved to: {prompt_file}")
        
        # Step 4: 如果启用 LLM，直接生成 TD
        if use_llm and LLM_API_KEY:
            print("🤖 Step 4: Generating TD with LLM...")
            design = self._call_llm(prompt)
            if design:
                # 保存生成的 TD
                report_file = self.output_dir / "technical_design.md"
                report_file.write_text(design, encoding="utf-8")
                print(f"✅ TD saved to: {report_file}")
                
                return {
                    "status": "completed",
                    "design": design,
                    "report_file": str(report_file),
                    "prompt_file": str(prompt_file),
                    "prd_length": len(prd_text),
                    "evidence_count": filtered.get("total", 0),
                    "sections": self._extract_sections(design),
                }
        
        # 否则返回 prompt 就绪状态
        return {
            "status": "prompt_ready",
            "message": "TD prompt generated. Send to LLM, then call generate_with_response().",
            "prompt_file": str(prompt_file),
            "prd_length": len(prd_text),
            "evidence_count": filtered.get("total", 0),
        }
    
    def _call_llm(self, prompt: str) -> Optional[str]:
        """调用 LLM 生成 TD"""
        try:
            import httpx
            headers = {
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": LLM_MAX_TOKENS,
                "temperature": 0.3,
            }
            
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(f"{LLM_BASE_URL}/chat/completions", 
                                   json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"❌ LLM call failed: {e}")
            return None
    
    def _extract_sections(self, design: str) -> list:
        """从 TD 中提取章节"""
        sections = []
        import re
        for match in re.finditer(r'^##\s+(.+)$', design, re.MULTILINE):
            sections.append(match.group(1).strip())
        return sections if sections else ["架构设计", "接口设计", "数据库设计", "风险评估"]
    
    def generate_with_response(self, llm_response: str, prompt_file: Optional[str] = None) -> dict:
        """LLM 生成 TD 后，保存报告（兼容旧接口）"""
        report_file = self.output_dir / "technical_design.md"
        report_file.write_text(llm_response, encoding="utf-8")
        
        return {
            "status": "completed",
            "report_file": str(report_file),
            "sections": self._extract_sections(llm_response),
        }
    
    def _build_td_prompt(self, filtered: dict, ir: IRDocument, prd_text: str, 
                         review_report: Optional[str] = None, cache_dir: str = None) -> str:
        """构建 TD 生成 prompt（增强版）"""
        prompt_parts = []
        
        # ══════════════════════════════════════════════════════════════
        # 角色设定
        # ══════════════════════════════════════════════════════════════
        prompt_parts.append("# 技术方案生成任务")
        prompt_parts.append("")
        prompt_parts.append("你是一位资深技术架构师，擅长基于代码库实际结构设计技术方案。")
        prompt_parts.append("你的设计必须：")
        prompt_parts.append("1. **基于事实**：所有设计决策都基于代码库的实际结构")
        prompt_parts.append("2. **最小变更**：优先复用现有模块，避免重复造轮子")
        prompt_parts.append("3. **向后兼容**：新设计不能破坏现有功能")
        prompt_parts.append("4. **可测试**：每个接口都有清晰的测试点")
        prompt_parts.append("")
        
        # ══════════════════════════════════════════════════════════════
        # 代码库分析结果
        # ══════════════════════════════════════════════════════════════
        prompt_parts.append("## 代码库分析结果")
        prompt_parts.extend(self._build_ir_summary(ir))
        prompt_parts.append("")
        
        # ══════════════════════════════════════════════════════════════
        # 路由和接口现状
        # ══════════════════════════════════════════════════════════════
        prompt_parts.append("## 现有路由和接口")
        prompt_parts.append(self._build_routes_section(ir, limit=30))
        prompt_parts.append("")
        
        # ══════════════════════════════════════════════════════════════
        # 业务逻辑现状
        # ══════════════════════════════════════════════════════════════
        prompt_parts.append("## 核心业务逻辑")
        prompt_parts.append(self._build_business_logic_section(ir, limit=10))
        prompt_parts.append("")
        
        # ══════════════════════════════════════════════════════════════
        # 数据库现状
        # ══════════════════════════════════════════════════════════════
        prompt_parts.append("## 数据库现状")
        prompt_parts.append(self._build_entity_table_section(ir, limit=15))
        prompt_parts.append(self._build_sql_section(ir, limit=10))
        prompt_parts.append("")
        
        # ══════════════════════════════════════════════════════════════
        # 错误码和鉴权
        # ══════════════════════════════════════════════════════════════
        prompt_parts.append("## 错误码和鉴权")
        prompt_parts.append(self._build_error_code_section(ir, limit=15))
        prompt_parts.append(self._build_auth_model_section(ir))
        prompt_parts.append("")
        
        # ══════════════════════════════════════════════════════════════
        # 包结构和调用图（用于架构图）
        # ══════════════════════════════════════════════════════════════
        prompt_parts.append("## 代码包结构")
        prompt_parts.append(self._build_packages_section(ir, limit=15))
        prompt_parts.append("")
        
        prompt_parts.append("## 服务调用关系")
        prompt_parts.append(self._build_call_graph_section(ir, limit=20))
        prompt_parts.append("")
        
        # ══════════════════════════════════════════════════════════════
        # Mermaid 图表（基于 IR 自动生成）
        # ══════════════════════════════════════════════════════════════
        prompt_parts.append("## 自动生成的架构图（基于代码库实际结构）")
        prompt_parts.append("以下图表由系统根据代码库自动生成，请直接使用或参考：")
        prompt_parts.append("")
        
        try:
            from mermaid_generator import MermaidGenerator
            generator = MermaidGenerator({
                'packages': getattr(ir, 'packages', {}),
                'call_graph': getattr(ir, 'call_graph', []),
                'entity_tables': getattr(ir, 'entity_tables', []),
                'routes': getattr(ir, 'routes', []),
                'functions': getattr(ir, 'functions', []),
                'services': getattr(ir, 'services', []),
                'core_flows': getattr(ir, 'core_flows', []),
                'structs': getattr(ir, 'structs', []),
                'sql_operations': getattr(ir, 'sql_operations', []),
                'error_codes': getattr(ir, 'error_codes', []),
                'auth_models': getattr(ir, 'auth_models', []),
                'configs': getattr(ir, 'configs', []),
            })
            diagrams = generator.generate_all_diagrams()
            
            if diagrams.get('architecture'):
                prompt_parts.append("### 系统架构图")
                prompt_parts.append(diagrams['architecture'])
                prompt_parts.append("")
            
            if diagrams.get('data_model'):
                prompt_parts.append("### 数据模型图")
                prompt_parts.append(diagrams['data_model'])
                prompt_parts.append("")
            
            if diagrams.get('deployment'):
                prompt_parts.append("### 部署架构图")
                prompt_parts.append(diagrams['deployment'])
                prompt_parts.append("")
            
            if ir.core_flows:
                top_flow = ir.core_flows[0] if isinstance(ir.core_flows[0], dict) else {}
                seq_diagram = generator.generate_sequence_diagram(top_flow)
                prompt_parts.append("### 核心流程时序图")
                prompt_parts.append(seq_diagram)
                prompt_parts.append("")
                
        except Exception as e:
            prompt_parts.append(f"⚠️  Mermaid 图表生成跳过: {e}")
            prompt_parts.append("")
        
        # ══════════════════════════════════════════════════════════════
        # PRD 内容
        # ══════════════════════════════════════════════════════════════
        prompt_parts.append("## PRD 需求内容")
        prompt_parts.append(prd_text)
        prompt_parts.append("")
        
        # ══════════════════════════════════════════════════════════════
        # 审查报告（如果有）
        # ══════════════════════════════════════════════════════════════
        if review_report:
            prompt_parts.append("## PRD 审查报告")
            prompt_parts.append(review_report)
            prompt_parts.append("")
        
        # ══════════════════════════════════════════════════════════════
        # TD 生成规则（关键部分）
        # ══════════════════════════════════════════════════════════════
        prompt_parts.append("## 技术方案生成规则")
        prompt_parts.append("")
        prompt_parts.append("### 第一步：方案类型判断")
        prompt_parts.append("基于代码库现有结构，判断 PRD 需求属于哪种情况：")
        prompt_parts.append("1. **兼容改进** — 在现有架构/接口/表上做修改，不引入新模块")
        prompt_parts.append("2. **新功能** — 需要新增模块、接口、表结构")
        prompt_parts.append("3. **混合方案** — 兼容改进 + 新功能并存")
        prompt_parts.append("")
        prompt_parts.append("### 第二步：设计决策要点")
        prompt_parts.append("- **最小变更原则**: 优先修改现有代码，而非新增")
        prompt_parts.append("- **向后兼容**: 不破坏现有 API 和行为")
        prompt_parts.append("- **数据迁移**: 如有表结构变更，提供迁移脚本")
        prompt_parts.append("- **灰度发布**: 新功能考虑 feature flag 或灰度策略")
        prompt_parts.append("- **性能影响**: 评估新增功能对现有性能的影响")
        prompt_parts.append("")
        prompt_parts.append("### 第三步：TD 输出结构")
        prompt_parts.append("必须包含以下章节：")
        prompt_parts.append("1. **背景与目标** — 需求一句话概括 + 方案类型 + 判断理由")
        prompt_parts.append("2. **架构设计** — 模块划分、服务关系、数据流向（基于实际包结构）")
        prompt_parts.append("3. **接口设计** — 新增/修改的 HTTP/RPC 接口定义")
        prompt_parts.append("4. **数据库设计** — 新增/修改的表结构（含 CREATE TABLE 语句）")
        prompt_parts.append("5. **数据迁移** — 存量数据处理方案（如有）")
        prompt_parts.append("6. **流程图** — Mermaid sequenceDiagram 或 flowchart")
        prompt_parts.append("7. **架构图** — Mermaid graph TB（基于实际包结构）")
        prompt_parts.append("8. **风险评估** — 实现难度、依赖风险、回滚方案")
        prompt_parts.append("9. **测试要点** — 核心测试场景和边界条件")
        prompt_parts.append("10. **灰度策略** — 上线计划和回滚方案")
        prompt_parts.append("")
        
        # ══════════════════════════════════════════════════════════════
        # 输出格式
        # ══════════════════════════════════════════════════════════════
        prompt_parts.append("## 输出格式")
        prompt_parts.append("直接输出完整技术方案 Markdown，不要解释过程。")
        prompt_parts.append("使用以下章节结构：")
        prompt_parts.append("")
        prompt_parts.append("```markdown")
        prompt_parts.append("# 技术方案: [功能名称]")
        prompt_parts.append("")
        prompt_parts.append("## 1. 背景与目标")
        prompt_parts.append("- **需求**: [一句话描述]")
        prompt_parts.append("- **方案类型**: [兼容改进/新功能/混合]")
        prompt_parts.append("- **判断理由**: [为什么选这个方案]")
        prompt_parts.append("")
        prompt_parts.append("## 2. 架构设计")
        prompt_parts.append("- **模块划分**: [handler/service/dao 分层]")
        prompt_parts.append("- **数据流向**: [API → Service → DAO → DB]")
        prompt_parts.append("- **核心依赖**: [新增功能依赖哪些现有模块]")
        prompt_parts.append("")
        prompt_parts.append("## 3. 接口设计")
        prompt_parts.append("| Method | Path | Handler | Description | Request | Response |")
        prompt_parts.append("|--------|------|---------|-------------|---------|----------|")
        prompt_parts.append("")
        prompt_parts.append("## 4. 数据库设计")
        prompt_parts.append("```sql")
        prompt_parts.append("-- 新增表")
        prompt_parts.append("CREATE TABLE ...")
        prompt_parts.append("")
        prompt_parts.append("-- 修改表（如有）")
        prompt_parts.append("ALTER TABLE ...")
        prompt_parts.append("```")
        prompt_parts.append("")
        prompt_parts.append("## 5. 数据迁移")
        prompt_parts.append("- **存量数据**: [如何处理]")
        prompt_parts.append("- **迁移脚本**: [SQL/Go 脚本]")
        prompt_parts.append("")
        prompt_parts.append("## 6. 流程图")
        prompt_parts.append("```mermaid")
        prompt_parts.append("sequenceDiagram ...")
        prompt_parts.append("```")
        prompt_parts.append("")
        prompt_parts.append("## 7. 架构图")
        prompt_parts.append("```mermaid")
        prompt_parts.append("graph TB ...")
        prompt_parts.append("```")
        prompt_parts.append("")
        prompt_parts.append("## 8. 风险评估")
        prompt_parts.append("| 风险项 | 级别 | 影响 | 缓解措施 |")
        prompt_parts.append("|--------|------|------|----------|")
        prompt_parts.append("")
        prompt_parts.append("## 9. 测试要点")
        prompt_parts.append("- **正向流程**: [核心链路]")
        prompt_parts.append("- **异常处理**: [边界条件]")
        prompt_parts.append("- **兼容性**: [旧功能验证]")
        prompt_parts.append("")
        prompt_parts.append("## 10. 灰度策略")
        prompt_parts.append("- **上线步骤**: [分阶段发布]")
        prompt_parts.append("- **回滚方案**: [快速恢复]")
        prompt_parts.append("```")
        prompt_parts.append("")
        
        return "\n".join(prompt_parts)


# ============================================================================
# 命令行入口
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Technical Design Engine v2")
    parser.add_argument("--profile", required=True, help="Profile JSON path")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--prd", help="PRD content (file path or raw text)")
    parser.add_argument("--review-report", help="Review report file path (optional)")
    parser.add_argument("--llm-response", help="LLM TD output (file path)")
    parser.add_argument("--no-llm", action="store_true", help="Only generate prompt, don't call LLM")
    parser.add_argument("--wiki-path", help="Wiki engine path")
    
    args = parser.parse_args()
    
    # 加载 Profile
    with open(args.profile) as f:
        profile = json.load(f)
    
    # 获取 PRD 内容
    prd_text = None
    if args.prd:
        if Path(args.prd).exists():
            prd_text = Path(args.prd).read_text(encoding="utf-8")
        else:
            prd_text = args.prd
    else:
        print("ERROR: --prd is required")
        sys.exit(1)
    
    # 获取审查报告（可选）
    review_report = None
    if args.review_report and Path(args.review_report).exists():
        review_report = Path(args.review_report).read_text(encoding="utf-8")
    
    # 执行 TD 生成
    engine = TDEngine(profile, args.output_dir, args.wiki_path)
    
    if args.llm_response:
        # LLM 已生成 TD
        llm_output = Path(args.llm_response).read_text(encoding="utf-8")
        result = engine.generate_with_response(llm_output)
    else:
        # 生成 TD（默认调用 LLM）
        use_llm = not args.no_llm
        result = engine.generate_td(prd_text, review_report, use_llm=use_llm)
    
    print(f"\nResult: {json.dumps(result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
