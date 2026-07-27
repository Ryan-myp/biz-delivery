#!/usr/bin/env python3
"""技术方案生成引擎 — 基于 PRD 审查结果 + 代码库 IR 生成 TD

工作流程：
1. 加载 profile，扫描代码获取 IR
2. 加载 PRD 内容和审查报告
3. 判断：在旧架构上做兼容改进 vs 实现全新功能
4. 如果是新功能，生成数据迁移方案
5. 输出 TD（架构设计 + 接口设计 + 数据库设计 + 流程图）
"""

import json
import sys
from pathlib import Path
from typing import Optional

# 导入证据查询和 learn_repo
sys.path.insert(0, str(Path(__file__).parent))
from learn_repo import IRDocument
from base_engine import EngineBase


class TDEngine(EngineBase):
    """技术方案生成引擎"""
    
    def __init__(self, profile: dict, output_dir: str, wiki_path: Optional[str] = None):
        super().__init__(profile, output_dir, wiki_path)

    def generate_td(self, prd_text: str, review_report: Optional[str] = None) -> dict:
        """生成技术方案
        
        Args:
            prd_text: PRD 内容
            review_report: 可选，PRD 审查报告
            
        Returns:
            TD 生成结果 dict
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
        
        # Step 3: 保存 prompt 供 LLM 调用
        prompt_file = self.output_dir / "td_prompt.md"
        try:
            prompt_file.write_text(prompt, encoding="utf-8")
            print(f"✅ Prompt saved to: {prompt_file}")
        except Exception as e:
            print(f"❌ Failed to save TD prompt: {e}")
            raise
        
        return {
            "status": "prompt_ready",
            "message": "TD prompt generated. Send to LLM, then call generate_with_response().",
            "prompt_file": str(prompt_file),
            "prd_length": len(prd_text),
        }

    def generate_with_response(self, llm_response: str) -> dict:
        """LLM 生成 TD 后，保存报告
        
        Args:
            llm_response: LLM 的 TD 输出
            
        Returns:
            TD 报告 dict
        """
        report_file = self.output_dir / "technical_design.md"
        try:
            report_file.write_text(llm_response, encoding="utf-8")
            print(f"✅ TD report saved to: {report_file}")
        except Exception as e:
            print(f"❌ Failed to save technical design: {e}")
            raise
        
        return {
            "status": "completed",
            "report_file": str(report_file),
            "sections": ["架构设计", "接口设计", "数据库设计", "数据迁移", "流程图", "活动图"],
        }
    
    def _build_td_prompt(self, filtered: dict, ir: IRDocument, prd_text: str, review_report: Optional[str] = None, cache_dir: str = None) -> str:
        """构建 TD 生成 prompt
        
        核心思路：
        - 让 LLM 基于代码库的真实结构来设计技术方案
        - 判断：兼容改进 vs 全新功能
        - 如果是新功能，生成数据迁移方案
        - 输出完整的 TD（架构 + 接口 + 数据库 + 流程图）
        """
        prompt_parts = []
        
        # 角色设定
        prompt_parts.append("# 技术方案生成任务")
        prompt_parts.append("")
        prompt_parts.append("你是一位资深架构师。请基于以下代码库扫描结果和 PRD，")
        prompt_parts.append("生成一份详细的技术设计方案（Technical Design Document）。")
        prompt_parts.append("")
        
        # 代码库摘要 — 使用 base_engine 共享方法
        prompt_parts.append("## 代码库摘要")
        prompt_parts.extend(self._build_ir_summary(ir))
        prompt_parts.append("")
        
        # 关键路由 — 使用 base_engine 共享方法
        prompt_parts.append(self._build_routes_section(ir, limit=30))
        
        # 业务逻辑 — 使用 base_engine 共享方法
        prompt_parts.append(self._build_business_logic_section(ir, limit=10))
        
        # Entity-Table 映射 — 使用 base_engine 共享方法
        prompt_parts.append(self._build_entity_table_section(ir, limit=15))
        
        # 错误码 — 使用 base_engine 共享方法
        prompt_parts.append(self._build_error_code_section(ir, limit=15))
        
        # 鉴权模型 — 使用 base_engine 共享方法
        prompt_parts.append(self._build_auth_model_section(ir))
        
        # SQL 操作 — 使用 base_engine 共享方法
        prompt_parts.append(self._build_sql_section(ir, limit=10))
        
        # 测试覆盖 — 使用 base_engine 共享方法
        prompt_parts.append(self._build_test_coverage_section(ir))
        
        # 核心业务流程 — 使用 base_engine 共享方法
        prompt_parts.append(self._build_core_flows_section(ir, limit=6))
        
        # 注入包结构（用于架构图生成）— 使用 base_engine 共享方法
        prompt_parts.append(self._build_packages_section(ir, limit=15))
        
        # 注入调用图（用于服务关系图）— 使用 base_engine 共享方法
        prompt_parts.append(self._build_call_graph_section(ir, limit=20))
        
        # 注入跨仓库依赖分析（多仓库场景）
        if hasattr(ir, 'services') and ir.services:
            service_names = []
            for svc in ir.services:
                if isinstance(svc, dict):
                    name = svc.get('name', svc.get('service_name', ''))
                else:
                    name = getattr(svc, 'name', getattr(svc, 'service_name', ''))
                if name:
                    service_names.append(name)
            if len(service_names) > 1:
                prompt_parts.append("## 🌐 跨仓库服务拓扑")
                prompt_parts.append(f"检测到 {len(service_names)} 个服务: {', '.join(service_names[:10])}")
                prompt_parts.append("")
                
                # 注入服务间调用关系
                if hasattr(ir, 'call_graph') and ir.call_graph:
                    prompt_parts.append("### 服务间调用链")
                    cross_service_calls = set()
                    for edge in ir.call_graph:
                        if isinstance(edge, dict):
                            caller_pkg = edge.get('caller', '')
                            callee_pkg = edge.get('callee', '')
                            if caller_pkg and callee_pkg:
                                caller_base = caller_pkg.split('/')[0] if '/' in caller_pkg else caller_pkg
                                callee_base = callee_pkg.split('/')[0] if '/' in callee_pkg else callee_pkg
                                if caller_base != callee_base:
                                    cross_service_calls.add((caller_base, callee_base))
                    
                    if cross_service_calls:
                        for src, dst in sorted(cross_service_calls)[:15]:
                            prompt_parts.append(f"- `{src}` → `{dst}`")
                    prompt_parts.append("")
                
                prompt_parts.append("设计方案时需要考虑：")
                prompt_parts.append("- 服务间通信方式（HTTP/RPC/MQ）")
                prompt_parts.append("- 跨服务事务一致性方案")
                prompt_parts.append("- 服务降级和熔断策略")
                prompt_parts.append("- 服务版本兼容性管理")
                prompt_parts.append("- **关键**: 新增功能不能破坏现有服务契约")
                prompt_parts.append("")
        
        # 注入实际生成的 Mermaid 图表（基于 IR 数据）
        try:
            from mermaid_generator import MermaidGenerator
            generator = MermaidGenerator({
                'packages': ir.packages if hasattr(ir, 'packages') else {},
                'call_graph': ir.call_graph if hasattr(ir, 'call_graph') else [],
                'entity_tables': ir.entity_tables if hasattr(ir, 'entity_tables') else [],
                'routes': ir.routes if hasattr(ir, 'routes') else [],
                'functions': ir.functions if hasattr(ir, 'functions') else [],
                'services': ir.services if hasattr(ir, 'services') else [],
                'core_flows': ir.core_flows if hasattr(ir, 'core_flows') else [],
                'structs': ir.structs if hasattr(ir, 'structs') else [],
                'sql_operations': ir.sql_operations if hasattr(ir, 'sql_operations') else [],
                'error_codes': ir.error_codes if hasattr(ir, 'error_codes') else [],
                'auth_models': ir.auth_models if hasattr(ir, 'auth_models') else [],
                'configs': ir.configs if hasattr(ir, 'configs') else [],
            })
            diagrams = generator.generate_all_diagrams()
            
            # Only access diagrams that actually exist
            if diagrams.get('architecture') != '':
                prompt_parts.append("## 📐 架构图（基于实际包结构自动生成）")
                prompt_parts.append(diagrams['architecture'])
                prompt_parts.append("")
            
            if diagrams.get('data_model') != '':
                prompt_parts.append("## 📊 数据模型图（基于实际表结构自动生成）")
                prompt_parts.append(diagrams['data_model'])
                prompt_parts.append("")
            
            if diagrams.get('deployment') != '':
                prompt_parts.append("## 🏗️ 部署架构图（基于服务拓扑自动生成）")
                prompt_parts.append(diagrams['deployment'])
                prompt_parts.append("")
            
            # Generate sequence diagram for top flow
            if ir.core_flows:
                top_flow = ir.core_flows[0] if isinstance(ir.core_flows[0], dict) else {}
                seq_diagram = generator.generate_sequence_diagram(top_flow)
                prompt_parts.append("## 🔄 核心流程时序图（基于实际调用链自动生成）")
                prompt_parts.append(seq_diagram)
                prompt_parts.append("")
            
            # Generate activity diagram for business process flows
            if diagrams.get('activity'):
                prompt_parts.append("## 📊 业务活动图（基于核心业务流程自动生成）")
                prompt_parts.append(diagrams['activity'])
                prompt_parts.append("")
            
            # Use MermaidGenerator outputs instead of inline broken versions
            if diagrams.get('state_machine'):
                prompt_parts.append("## 🔄 状态机图（基于 IR 状态转换函数自动生成）")
                prompt_parts.append(diagrams['state_machine'])
                prompt_parts.append("")
            
            if diagrams.get('dependency'):
                prompt_parts.append("## 🔗 模块依赖图（基于 IR call_graph 自动生成）")
                prompt_parts.append(diagrams['dependency'])
                prompt_parts.append("")
                
        except Exception as e:
            prompt_parts.append(f"⚠️  Mermaid diagram generation skipped: {e}")
            prompt_parts.append("")
        
        # 证据查询结果
        if filtered.get('evidence'):
            prompt_parts.append("## 代码库证据（基于 PRD 关键词查询）")
            for i, item in enumerate(filtered.get('evidence', [])[:20], 1):
                title = item.get('title', item.get('path', 'unknown'))
                score = item.get('score', 0)
                content_text = item.get('content', item.get('text', ''))
                prompt_parts.append(f"- **证据{i}** (score={score:.3f}): {title}")
                if content_text:
                    ct = content_text[:200].replace('\n', '\\n')
                    prompt_parts.append(f"  ```\\n  {ct}\\n  ```")
            prompt_parts.append("")

        # 业务卡片注入
        bc_file = Path(cache_dir) / "business_cards.json" if cache_dir else None
        if bc_file and bc_file.exists():
            try:
                with open(bc_file) as _bc_f:
                    import json as _bc_json
                    _bc_data = _bc_json.load(_bc_f)
                prompt_parts.append("## 业务知识卡片")
                _scenarios = _bc_data.get('scenario_cards', [])
                if _scenarios:
                    prompt_parts.append("### 场景卡（共{}个）".format(len(_scenarios)))
                    for _sc in _scenarios[:10]:
                        prompt_parts.append("- **{}**: {}".format(_sc['scenario'], _sc.get('description', '')[:200]))
                        if _sc.get('call_chain'):
                            prompt_parts.append("  调用: {}".format(', '.join(_sc['call_chain'][:5])))
                _entities = _bc_data.get('entity_relationships', [])
                if _entities:
                    prompt_parts.append("### 实体关系（共{}个）".format(len(_entities)))
                    for _er in _entities[:10]:
                        prompt_parts.append("- `{}` → `{}`".format(_er['entity'], _er['table']))
                _errors = _bc_data.get('error_categories', {})
                if _errors:
                    prompt_parts.append("### 错误分类")
                    for _cat, _errs in _errors.items():
                        prompt_parts.append("- **{}**: {} errors".format(_cat, len(_errs)))
            except Exception as _bc_err:
                prompt_parts.append("⚠️  business_cards.json 加载失败: {}".format(_bc_err))
                prompt_parts.append("")


        # PRD 内容
        prompt_parts.append("## PRD 内容")
        prompt_parts.append(prd_text)
        prompt_parts.append("")
        
        # 审查报告（如果有）
        if review_report:
            prompt_parts.append("## PRD 审查报告")
            prompt_parts.append(review_report)
            prompt_parts.append("")
        
        # TD 生成规则
        prompt_parts.append("## 技术方案生成规则")
        prompt_parts.append("")
        prompt_parts.append("### 第一步：判断方案类型")
        prompt_parts.append("基于代码库的现有结构，判断 PRD 需求属于哪种情况：")
        prompt_parts.append("1. **兼容改进** — 在现有架构/接口/表结构上做修改，不引入新模块")
        prompt_parts.append("2. **新功能** — 需要新增模块、接口、表结构")
        prompt_parts.append("3. **混合方案** — 兼容改进 + 新功能并存")
        prompt_parts.append("")
        prompt_parts.append("### 第二步：如果是兼容改进")
        prompt_parts.append("- 列出需要修改的现有模块/接口/表")
        prompt_parts.append("- 说明修改范围和影响面")
        prompt_parts.append("- 给出向后兼容方案（API version、字段废弃策略）")
        prompt_parts.append("")
        prompt_parts.append("### 第三步：如果是新功能")
        prompt_parts.append("- 设计新的模块/接口/表结构")
        prompt_parts.append("- **数据迁移方案**: 旧数据如何处理？是否需要迁移脚本？")
        prompt_parts.append("- **兼容性方案**: 新旧功能如何共存？灰度发布策略？")
        prompt_parts.append("")
        prompt_parts.append("### 第四步：生成完整 TD")
        prompt_parts.append("TD 必须包含以下章节：")
        prompt_parts.append("1. **背景与目标** — 一句话概括需求")
        prompt_parts.append("2. **方案类型** — 兼容改进 / 新功能 / 混合方案")
        prompt_parts.append("3. **架构设计** — 模块划分、服务关系、数据流向")
        prompt_parts.append("4. **接口设计** — HTTP/RPC 接口定义（Request/Response）")
        prompt_parts.append("5. **数据库设计** — 新增/修改的表结构（含字段、索引、注释）")
        prompt_parts.append("6. **数据迁移** — 旧数据处理方案（如有）")
        prompt_parts.append("7. **流程图** — Mermaid 流程图描述核心流程")
        prompt_parts.append("8. **架构图** — Mermaid graph 展示模块/服务关系（基于实际包结构）")
        prompt_parts.append("9. **数据模型图** — ER 图展示表关系（基于实际 entity_tables）")
        prompt_parts.append("10. **部署架构** — Mermaid 展示服务部署拓扑")
        prompt_parts.append("11. **风险评估** — 实现难度、依赖风险、回滚方案")
        prompt_parts.append("")
        
        # 新增：基于实际代码结构的图表生成指导
        prompt_parts.append("### 图表生成规则（重要）")
        prompt_parts.append("")
        prompt_parts.append("**架构图必须基于实际代码包结构生成**：")
        prompt_parts.append("- 从 IR 的 `packages` 字段提取实际包名")
        prompt_parts.append("- 从 IR 的 `call_graph` 字段提取实际调用关系")
        prompt_parts.append("- 每个包用 subgraph 分组，包含实际的 handler/service/dao 层")
        prompt_parts.append("- 标注实际的外部依赖（RPC/HTTP/MQ）")
        prompt_parts.append("- 使用 `graph TB` 方向（从上到下）")
        prompt_parts.append("")
        prompt_parts.append("**数据模型图必须基于实际表结构生成**：")
        prompt_parts.append("- 从 IR 的 `entity_tables` 字段提取实际表名和字段")
        prompt_parts.append("- 标注主键（PK）、外键（FK）、唯一索引（UK）")
        prompt_parts.append("- 标注表之间的关系（一对一、一对多、多对多）")
        prompt_parts.append("- 使用 `erDiagram` 语法")
        prompt_parts.append("")
        prompt_parts.append("**部署架构图必须基于实际服务拓扑生成**：")
        prompt_parts.append("- 从 IR 的 `service_topology` 字段提取实际服务")
        prompt_parts.append("- 标注负载均衡、缓存、数据库、消息队列")
        prompt_parts.append("- 标注服务间的通信协议（HTTP/gRPC/MQ）")
        prompt_parts.append("- 使用 `graph LR` 方向（从左到右）")
        prompt_parts.append("")
        prompt_parts.append("**流程图必须基于实际调用链生成**：")
        prompt_parts.append("- 从 IR 的 `core_flows` 字段提取实际调用链")
        prompt_parts.append("- 从 IR 的 `business_logic` 字段提取实际 handler → service → dao 调用")
        prompt_parts.append("- 使用 `sequenceDiagram` 或 `flowchart TD` 语法")
        prompt_parts.append("- 标注每个节点的类型（HTTP Handler / Service / DAO / DB）")
        prompt_parts.append("")
        
        # 输出格式
        prompt_parts.append("## 输出格式")
        prompt_parts.append("请按以下 Markdown 格式输出 TD：")
        prompt_parts.append("")
        prompt_parts.append("```markdown")
        prompt_parts.append("# 技术方案: [功能名称]")
        prompt_parts.append("")
        prompt_parts.append("## 1. 背景与目标 — 一句话描述 + 方案类型（兼容改进/新功能/混合）+ 理由")
        prompt_parts.append("")
        prompt_parts.append("## 2. 架构设计")
        prompt_parts.append("- **模块划分**: handler/service/dao 分层，新模块依赖哪些现有模块？")
        prompt_parts.append("- **数据流向**: API → Service → DAO → DB，标注缓存/MQ/外部依赖")
        prompt_parts.append("- **流程图**: mermaid graph TD 或 sequenceDiagram（基于实际调用链）")
        prompt_parts.append("")
        prompt_parts.append("## 3. 接口设计")
        prompt_parts.append("- **HTTP**: Method | Path | Handler | Description | Request struct | Response struct | Error codes")
        prompt_parts.append("- **RPC**: Proto 定义（如有）")
        prompt_parts.append("- **架构图**: mermaid graph TB 基于实际包结构")
        prompt_parts.append("- **ER 图**: mermaid erDiagram 基于实际表结构")
        prompt_parts.append("")
        prompt_parts.append("## 4. 数据库设计")
        prompt_parts.append("- **新增表**: CREATE TABLE 语句（含字段/索引/注释）")
        prompt_parts.append("- **修改表**: ALTER TABLE 语句（如有）")
        prompt_parts.append("")
        prompt_parts.append("## 5. 数据迁移")
        prompt_parts.append("- **旧数据处理**: 存量数据如何适配？")
        prompt_parts.append("- **迁移脚本**: SQL/Go 脚本 + 执行顺序")
        prompt_parts.append("")
        prompt_parts.append("## 6. 风险评估")
        prompt_parts.append("- **实现难度**: 高/中/低 — 理由")
        prompt_parts.append("- **依赖风险**: 无/低/中/高 — 说明")
        prompt_parts.append("- **回滚方案**: 具体步骤")
        prompt_parts.append("")
        prompt_parts.append("```\n")
        prompt_parts.append("")
        
        prompt = "\n".join(prompt_parts)
        return prompt


# ============================================================================
# 命令行入口
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Technical Design Engine")
    parser.add_argument("--profile", required=True, help="Profile JSON path")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--prd", help="PRD content (file path or raw text)")
    parser.add_argument("--review-report", help="Review report file path (optional)")
    parser.add_argument("--llm-response", help="LLM TD output (file path)")
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
        # 生成 TD prompt
        result = engine.generate_td(prd_text, review_report)
    
    print(f"\nResult: {json.dumps(result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
