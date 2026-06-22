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
import os
import sys
import time
from pathlib import Path
from typing import Optional

# 导入证据查询和 learn_repo
sys.path.insert(0, str(Path(__file__).parent))
from query_evidence import run_evidence_query
from learn_repo import GoScanner, IRDocument


class TDEngine:
    """技术方案生成引擎"""
    
    def _scan_codebase(self) -> IRDocument:
        """扫描代码库获取 IR"""
        if not self.repos:
            print("⚠️  No repositories configured, skipping scan")
            return IRDocument(
                repo_name="none",
                repo_path="",
                language="unknown",
            )
        
        repo = self.repos[0]
        repo_path = Path(repo["path"])
        language = repo.get("language", "go")
        
        if language == "go":
            scanner = GoScanner()
        else:
            print(f"⚠️  Unsupported language: {language}")
            return IRDocument(
                repo_name=repo["name"],
                repo_path=str(repo_path),
                language=language,
            )
        
        ir = scanner.scan_directory(repo_path)
        ir.repo_name = repo["name"]
        ir.repo_path = str(repo_path)
        
        # 清理 route handler
        for route in ir.routes:
            if hasattr(route, 'handler'):
                route.handler = re.sub(r'\s*\([^)]*$', '', route.handler)
                route.handler = re.sub(r'\s*\([^)]*\).*', '', route.handler)
                if '.' in route.handler:
                    route.handler = route.handler.split('.')[-1]
                route.handler = route.handler.strip()
        
        print(f"  Found: {len(ir.structs)} structs, {len(ir.functions)} functions, {len(ir.routes)} routes")
        
        return ir
    
    def __init__(self, profile: dict, output_dir: str, wiki_path: Optional[str] = None):
        self.profile = profile
        self.output_dir = Path(output_dir)
        self.wiki_path = wiki_path
        self.business_domain = profile.get("business_domain", "unknown")
        self.repos = profile.get("repositories", [])
        
    def _query_evidence_for_prd(self, ir, prd_text: str, cache_dir: str = None) -> dict:
        """从 PRD 提取关键词，调用 query_evidence 查询代码库证据"""
        import re
        keywords = re.findall(r'[一-龥]{2,8}', prd_text) + re.findall(r'[a-zA-Z]{3,}', prd_text)
        keywords = list(set(keywords))[:10]
        
        all_evidence = []
        for kw in keywords:
            try:
                result = run_evidence_query(query=kw, wiki_path=self.wiki_path, top_k=5, sources=["code", "schema", "api_docs"])
                if result.get('evidence'):
                    all_evidence.extend(result['evidence'])
            except:
                pass
        
        # 去重
        seen = set()
        unique = []
        for item in all_evidence:
            path = item.get('path', item.get('file_path', ''))
            if path and path not in seen:
                seen.add(path)
                unique.append(item)
        
        return {
            'keywords': keywords,
            'evidence': unique,
            'total': len(unique),
        }

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
        filtered = self._query_evidence_for_prd(ir, prd_text, cache_dir)
        print(f"  Found {filtered.get('total', 0)} evidence items")
        
        # Step 2: 构建 TD prompt
        print("📝 Step 2: Building TD prompt...")
        prompt = self._build_td_prompt(filtered, ir, prd_text, review_report)
        
        # Step 3: 保存 prompt 供 LLM 调用
        prompt_file = self.output_dir / "td_prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")
        print(f"✅ Prompt saved to: {prompt_file}")
        
        return {
            "status": "prompt_ready",
            "message": "TD prompt generated. Send to LLM, then call generate_with_response().",
            "prompt_file": str(prompt_file),
            "prd_length": len(prd_text),
        }
    
    def _query_evidence_for_prd(self, ir, prd_text: str, cache_dir: str = None) -> dict:
        """从 PRD 提取关键词，调用 query_evidence 查询代码库证据"""
        import re
        keywords = re.findall(r'[一-龥]{2,8}', prd_text) + re.findall(r'[a-zA-Z]{3,}', prd_text)
        keywords = list(set(keywords))[:10]
        
        all_evidence = []
        for kw in keywords:
            try:
                result = run_evidence_query(query=kw, wiki_path=self.wiki_path, top_k=5, sources=["code", "schema", "api_docs"])
                if result.get('evidence'):
                    all_evidence.extend(result['evidence'])
            except:
                pass
        
        # 去重
        seen = set()
        unique = []
        for item in all_evidence:
            path = item.get('path', item.get('file_path', ''))
            if path and path not in seen:
                seen.add(path)
                unique.append(item)
        
        return {
            'keywords': keywords,
            'evidence': unique,
            'total': len(unique),
        }

    def generate_with_response(self, llm_response: str) -> dict:
        """LLM 生成 TD 后，保存报告
        
        Args:
            llm_response: LLM 的 TD 输出
            
        Returns:
            TD 报告 dict
        """
        report_file = self.output_dir / "technical_design.md"
        report_file.write_text(llm_response, encoding="utf-8")
        
        return {
            "status": "completed",
            "report_file": str(report_file),
            "sections": ["架构设计", "接口设计", "数据库设计", "数据迁移", "流程图"],
        }
    
    def _query_evidence(self, prd_text: str) -> list:
        """从 PRD 提取关键词，查询代码库证据"""
        import re
        keywords = re.findall(r'[一-龥]{2,8}', prd_text) + re.findall(r'[a-zA-Z]{3,}', prd_text)
        keywords = list(set(keywords))[:10]
        
        all_evidence = []
        for kw in keywords:
            try:
                result = run_evidence_query(query=kw, wiki_path=self.wiki_path, top_k=5, sources=["code", "schema", "api_docs"])
                if result.get('evidence'):
                    all_evidence.extend(result['evidence'])
            except:
                pass
        
        # 去重
        seen = set()
        unique = []
        for item in all_evidence:
            path = item.get('path', item.get('file_path', ''))
            if path and path not in seen:
                seen.add(path)
                unique.append(item)
        return {
            'keywords': keywords,
            'evidence': unique,
            'total': len(unique),
        }
    
    def _build_td_prompt(self, filtered: dict, ir: IRDocument, prd_text: str, review_report: Optional[str] = None) -> str:
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
        
        # 代码库摘要
        prompt_parts.append("## 代码库摘要")
        prompt_parts.append(f"- **业务域**: {self.business_domain}")
        prompt_parts.append(f"- **仓库**: {', '.join(r['name'] for r in self.repos)}")
        prompt_parts.append(f"- **语言**: {ir.language}")
        prompt_parts.append(f"- **Structs**: {len(ir.structs)}")
        prompt_parts.append(f"- **Functions**: {len(ir.functions)}")
        prompt_parts.append(f"- **Routes**: {len(ir.routes)}")
        prompt_parts.append(f"- **Tables**: {len(ir.tables)}")
        prompt_parts.append("")
        
        # 关键路由
        if ir.routes:
            prompt_parts.append("## 关键路由（前20条）")
            for route in ir.routes[:20]:
                prompt_parts.append(f"- `{route.method.upper()}` {route.path} → `{route.handler}`")
            prompt_parts.append("")
        
        # 关键表结构
        if ir.tables:
            prompt_parts.append("## 关键表结构（前10张）")
            for table in ir.tables[:10]:
                cols = ', '.join(getattr(table, 'columns', []))[:5] if hasattr(table, 'columns') else ''
                prompt_parts.append(f"- `{table.name}`: {cols}")
            prompt_parts.append("")
        
        # 路由摘要
        if filtered.get('evidence'):
            prompt_parts.append("## 现有路由")
            for route in filtered.get('evidence', [])[:30]:
                prompt_parts.append(f"- `{route.method.upper()}` {route.path} → `{route.handler}`")
            prompt_parts.append("")
        
        # 表结构摘要 — 从 IR 缓存中获取
        if ir and hasattr(ir, 'tables') and ir.tables:
            prompt_parts.append("## 现有表结构")
            for table in ir.tables[:20]:
                cols = ', '.join(getattr(table, 'columns', []))[:10] if hasattr(table, 'columns') else ''
                prompt_parts.append(f"- `{table.name if hasattr(table, 'name') else 'unknown'}`: {cols}")
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
        prompt_parts.append("8. **风险评估** — 实现难度、依赖风险、回滚方案")
        prompt_parts.append("")
        
        # 输出格式
        prompt_parts.append("## 输出格式")
        prompt_parts.append("请按以下 Markdown 格式输出 TD：")
        prompt_parts.append("")
        prompt_parts.append("```markdown")
        prompt_parts.append("# 技术方案: [功能名称]")
        prompt_parts.append("")
        prompt_parts.append("## 1. 背景与目标")
        prompt_parts.append("[一句话描述]")
        prompt_parts.append("")
        prompt_parts.append("## 2. 方案类型")
        prompt_parts.append("[兼容改进 / 新功能 / 混合方案] — 理由")
        prompt_parts.append("")
        prompt_parts.append("## 3. 架构设计")
        prompt_parts.append("### 3.1 模块划分")
        prompt_parts.append("- 模块A: 职责")
        prompt_parts.append("- 模块B: 职责")
        prompt_parts.append("")
        prompt_parts.append("### 3.2 数据流向")
        prompt_parts.append("[描述]")
        prompt_parts.append("")
        prompt_parts.append("### 3.3 流程图")
        prompt_parts.append("```mermaid")
        prompt_parts.append("graph TD")
        prompt_parts.append("    A[起点] --> B[处理1]")
        prompt_parts.append("    B --> C[处理2]")
        prompt_parts.append("    C --> D[终点]")
        prompt_parts.append("```")
        prompt_parts.append("")
        prompt_parts.append("## 4. 接口设计")
        prompt_parts.append("### 4.1 HTTP 接口")
        prompt_parts.append("| Method | Path | Handler | Description |")
        prompt_parts.append("|--------|------|---------|-------------|")
        prompt_parts.append("| POST   | /api/v1/xxx | XxxHandler | 创建XXX |")
        prompt_parts.append("")
        prompt_parts.append("#### Request")
        prompt_parts.append("```go")
        prompt_parts.append("type CreateXxxRequest struct {")
        prompt_parts.append("    Name  string `json:\"name\" binding:\"required\"`")
        prompt_parts.append("    Value int    `json:\"value\"`")
        prompt_parts.append("}")
        prompt_parts.append("```")
        prompt_parts.append("")
        prompt_parts.append("#### Response")
        prompt_parts.append("```go")
        prompt_parts.append("type CreateXxxResponse struct {")
        prompt_parts.append("    Id     int    `json:\"id\"`")
        prompt_parts.append("    Status string `json:\"status\"`")
        prompt_parts.append("}")
        prompt_parts.append("```")
        prompt_parts.append("")
        prompt_parts.append("### 4.2 RPC 接口（如有）")
        prompt_parts.append("[Proto 定义]")
        prompt_parts.append("")
        prompt_parts.append("## 5. 数据库设计")
        prompt_parts.append("### 5.1 新增表")
        prompt_parts.append("```sql")
        prompt_parts.append("CREATE TABLE `xxx` (")
        prompt_parts.append("  `id` bigint unsigned NOT NULL AUTO_INCREMENT,")
        prompt_parts.append("  `name` varchar(255) NOT NULL COMMENT '名称',")
        prompt_parts.append("  `status` tinyint NOT NULL DEFAULT '1' COMMENT '状态: 1=启用 0=禁用',")
        prompt_parts.append("  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,")
        prompt_parts.append("  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,")
        prompt_parts.append("  PRIMARY KEY (`id`),")
        prompt_parts.append("  UNIQUE KEY `uk_name` (`name`)")
        prompt_parts.append(") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='XXX表';")
        prompt_parts.append("```")
        prompt_parts.append("")
        prompt_parts.append("### 5.2 修改表（如有）")
        prompt_parts.append("[描述]")
        prompt_parts.append("")
        prompt_parts.append("## 6. 数据迁移")
        prompt_parts.append("### 6.1 旧数据处理")
        prompt_parts.append("[描述]")
        prompt_parts.append("")
        prompt_parts.append("### 6.2 迁移脚本")
        prompt_parts.append("[SQL/Go 脚本]")
        prompt_parts.append("")
        prompt_parts.append("## 7. 风险评估")
        prompt_parts.append("- **实现难度**: 高/中/低 — 理由")
        prompt_parts.append("- **依赖风险**: 无/低/中/高 — 说明")
        prompt_parts.append("- **回滚方案**: [描述]")
        prompt_parts.append("")
        prompt_parts.append("```")
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
