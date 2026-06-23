#!/usr/bin/env python3
"""PRD 审查引擎 — 基于代码库 IR 审查 PRD 的合理性、场景遗漏、前后一致性

工作流程：
1. 加载 profile，扫描代码获取 IR（复用 learn_repo.py）
2. 加载 PRD 内容
3. 构建审查 prompt：IR 摘要 + PRD 内容 + 审查规则
4. 调用 LLM 输出审查报告
5. 保存审查报告到 output_dir
"""

import json
import re
import os
import sys
import time
from pathlib import Path
from typing import Optional

# 导入 learn_repo 的扫描器和 IR
sys.path.insert(0, str(Path(__file__).parent))
from learn_repo import GoScanner, IRDocument
from query_evidence import run_evidence_query


class ReviewEngine:
    """PRD 审查引擎"""
    
    def __init__(self, profile: dict, output_dir: str, wiki_path: Optional[str] = None):
        self.profile = profile
        self.output_dir = Path(output_dir)
        self.wiki_path = wiki_path
        self.business_domain = profile.get("business_domain", "unknown")
        self.repos = profile.get("repositories", [])
        
    def review(self, prd_text: str) -> dict:
        """执行 PRD 审查
        
        Args:
            prd_text: PRD 内容
            
        Returns:
            审查结果 dict
        """
        # Step 1: 扫描代码获取 IR
        print("📡 Step 1: Scanning codebase...")
        ir = self._scan_codebase()
        
        # Step 2: 从 PRD 提取关键词，查询代码库证据
        print("🔍 Step 2: Querying evidence from codebase...")
        # 假设 IR 缓存保存在 output_dir 下
        cache_dir = str(self.output_dir)
        filtered = self._query_evidence_for_prd(ir, prd_text, cache_dir)
        
        # Step 3: 构建审查 prompt（含证据）
        print("📝 Step 3: Building review prompt...")
        prompt = self._build_review_prompt(filtered, ir, prd_text)
        
        # Step 3: 保存 prompt 供 LLM 调用
        prompt_file = self.output_dir / "review_prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")
        print(f"✅ Prompt saved to: {prompt_file}")
        
        # Step 4: 返回 prompt 路径（LLM 审查后再生成报告）
        return {
            "status": "prompt_ready",
            "message": "Review prompt generated. Send to LLM, then call review_with_response().",
            "prompt_file": str(prompt_file),
            "prd_length": len(prd_text),
        }
    
    def review_with_response(self, llm_response: str, prompt_file: Optional[str] = None) -> dict:
        """LLM 审查后，生成结构化审查报告
        
        Args:
            llm_response: LLM 的审查输出
            prompt_file: 可选，原始 prompt 文件路径
            
        Returns:
            审查报告 dict
        """
        report_file = self.output_dir / "review_report.md"
        report_file.write_text(llm_response, encoding="utf-8")
        
        return {
            "status": "completed",
            "report_file": str(report_file),
            "sections": ["合理性检查", "场景遗漏", "前后一致性", "风险评估"],
        }
    
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
        
        # 清理 route handler（去掉括号等脏数据）
        for route in ir.routes:
            if hasattr(route, 'handler'):
                route.handler = re.sub(r'\s*\([^)]*$', '', route.handler)
                route.handler = re.sub(r'\s*\([^)]*\).*', '', route.handler)
                if '.' in route.handler:
                    route.handler = route.handler.split('.')[-1]
                route.handler = route.handler.strip()
        
        print(f"  Found: {len(ir.structs)} structs, {len(ir.functions)} functions, {len(ir.routes)} routes")
        
        return ir
    
    def _query_evidence_for_prd(self, ir: IRDocument, prd_text: str, cache_dir: str) -> dict:
        """从 PRD 提取关键词，调用 query_evidence 查询代码库证据
        
        策略：
        1. 从 PRD 提取关键词
        2. 针对每个关键词调用 query_evidence 搜索
        3. 返回相关证据
        
        返回: {
            'keywords': [...],
            'evidence': [...],
            'total': int,
        }
        """
        import re
        # 提取关键词：按标点/空格分句，取有意义的短语
        parts = re.split(r'[，。、；：\s\n]+', prd_text)
        keywords = []
        for p in parts:
            p = p.strip()
            if 2 <= len(p) <= 15:
                keywords.append(p)
            elif len(p) >= 3:  # 长英文单词
                keywords.append(p)
        keywords = list(dict.fromkeys(keywords))[:10]  # 去重保序
        
        print(f"  Extracted {len(keywords)} keywords: {keywords[:5]}")
        
        # 调用 query_evidence 查询
        all_evidence = []
        for keyword in keywords:
            try:
                result = run_evidence_query(
                    query=keyword,
                    wiki_path=self.wiki_path,
                    top_k=5,
                    sources=["code", "schema", "api_docs"],
                    cache_dir=cache_dir,  # 传入 IR 缓存目录
                )
                if result.get('evidence'):
                    all_evidence.extend(result['evidence'])
            except Exception as e:
                print(f"  ⚠️  Query failed for '{keyword}': {e}")
        
        # 去重
        seen = set()
        unique_evidence = []
        for item in all_evidence:
            path = item.get('path', item.get('file_path', ''))
            if path and path not in seen:
                seen.add(path)
                unique_evidence.append(item)
        
        print(f"  Found {len(unique_evidence)} evidence items")
        
        return {
            'keywords': keywords,
            'evidence': unique_evidence,
            'total': len(unique_evidence),
        }
    
    def _build_review_prompt(self, filtered: dict, ir: IRDocument, prd_text: str) -> str:
        """构建 PRD 审查 prompt
        
        核心思路：
        - 让 LLM 基于代码库的真实结构（路由、函数、表结构）来审查 PRD
        - 检查 PRD 描述的功能是否在代码中已实现或可映射
        - 检查场景遗漏（正向流程、异常处理、边界条件、权限控制）
        - 检查前后一致性（术语、流程、数据流向）
        """
        prompt_parts = []
        
        # 角色设定
        prompt_parts.append("# PRD 审查任务")
        prompt_parts.append("")
        prompt_parts.append("你是一位资深架构师和技术负责人。请基于以下代码库扫描结果，")
        prompt_parts.append("对输入的 PRD 进行严格审查，找出：")
        prompt_parts.append("1. **合理性问题** — PRD 描述的功能是否与现有架构冲突？")
        prompt_parts.append("2. **场景遗漏** — 是否缺少正向流程、异常处理、边界条件？")
        prompt_parts.append("3. **前后不一致** — PRD 内部的术语、流程、数据流向是否矛盾？")
        prompt_parts.append("4. **风险评估** — 实现难度、依赖风险、兼容性风险")
        prompt_parts.append("")
        
        # 证据查询结果（从 PRD 关键词查到的相关代码）
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
        
        # 全量 IR 摘要（作为上下文）
        prompt_parts.append("## 代码库全量摘要")
        prompt_parts.append(f"- **业务域**: {self.business_domain}")
        prompt_parts.append(f"- **仓库**: {', '.join(r['name'] for r in self.repos)}")
        prompt_parts.append(f"- **语言**: {ir.language}")
        prompt_parts.append(f"- **Structs**: {len(ir.structs)}")
        prompt_parts.append(f"- **Functions**: {len(ir.functions)}")
        prompt_parts.append(f"- **Routes**: {len(ir.routes)}")
        prompt_parts.append(f"- **Tables**: {len(ir.tables)}")
        prompt_parts.append("")
        
        # 关键路由（前20条）
        if ir.routes:
            prompt_parts.append("## 关键路由（前20条）")
            for route in ir.routes[:20]:
                prompt_parts.append(f"- `{route.method.upper()}` {route.path} → `{route.handler}`")
            prompt_parts.append("")
        
        # 关键表结构（前10张）
        if ir.tables:
            prompt_parts.append("## 关键表结构（前10张）")
            for table in ir.tables[:10]:
                cols = ', '.join(getattr(table, 'columns', []))[:5] if hasattr(table, 'columns') else ''
                prompt_parts.append(f"- `{table.name}`: {cols}")
            prompt_parts.append("")
        
        # PRD 内容
        prompt_parts.append("## PRD 内容")
        prompt_parts.append(prd_text)
        prompt_parts.append("")
        
        # 审查规则
        prompt_parts.append("## 审查规则")
        prompt_parts.append("")
        prompt_parts.append("### 1. 合理性检查")
        prompt_parts.append("- PRD 描述的功能是否在现有架构范围内？是否需要新增模块？")
        prompt_parts.append("- PRD 的数据流向是否与现有表结构/服务接口匹配？")
        prompt_parts.append("- PRD 提到的术语是否在代码库中有对应实体？")
        prompt_parts.append("- 是否存在与现有业务逻辑冲突的需求？")
        prompt_parts.append("")
        prompt_parts.append("### 2. 场景遗漏")
        prompt_parts.append("- **正向流程**: 是否覆盖了完整的主流程？")
        prompt_parts.append("- **异常处理**: 是否考虑了网络超时、数据校验失败、权限不足等异常？")
        prompt_parts.append("- **边界条件**: 是否考虑了空数据、超限数据、并发冲突等边界？")
        prompt_parts.append("- **权限控制**: 是否明确了操作者的权限要求？")
        prompt_parts.append("- **数据迁移**: 如果是新功能，旧数据如何处理？")
        prompt_parts.append("")
        prompt_parts.append("### 3. 前后一致性")
        prompt_parts.append("- PRD 内部的术语是否一致？（如：素材 vs 创意 vs asset）")
        prompt_parts.append("- 流程描述是否前后矛盾？")
        prompt_parts.append("- 数据流向是否清晰一致？")
        prompt_parts.append("- 接口定义是否与其他模块兼容？")
        prompt_parts.append("")
        prompt_parts.append("### 4. 风险评估")
        prompt_parts.append("- **实现难度**: 高/中/低，理由是什么？")
        prompt_parts.append("- **依赖风险**: 是否依赖其他未就绪的服务/模块？")
        prompt_parts.append("- **兼容性风险**: 是否影响现有功能？是否需要灰度发布？")
        prompt_parts.append("")
        
        # 输出格式
        prompt_parts.append("## 输出格式")
        prompt_parts.append("请按以下 Markdown 格式输出审查报告：")
        prompt_parts.append("")
        prompt_parts.append("```markdown")
        prompt_parts.append("# PRD 审查报告")
        prompt_parts.append("")
        prompt_parts.append("## 总体评价")
        prompt_parts.append("[通过 / 需修订 / 阻塞] — 一句话总结")
        prompt_parts.append("")
        prompt_parts.append("## 合理性检查")
        prompt_parts.append("- [问题1] 描述 + 严重性（高/中/低）+ 建议")
        prompt_parts.append("- ...")
        prompt_parts.append("")
        prompt_parts.append("## 场景遗漏")
        prompt_parts.append("- [遗漏1] 描述 + 建议补充的流程/异常/边界")
        prompt_parts.append("- ...")
        prompt_parts.append("")
        prompt_parts.append("## 前后不一致")
        prompt_parts.append("- [不一致1] 描述 + 建议修正")
        prompt_parts.append("- ...")
        prompt_parts.append("")
        prompt_parts.append("## 风险评估")
        prompt_parts.append("- **实现难度**: 高/中/低 — 理由")
        prompt_parts.append("- **依赖风险**: 无/低/中/高 — 说明")
        prompt_parts.append("- **兼容性风险**: 无/低/中/高 — 说明")
        prompt_parts.append("")
        prompt_parts.append("## 结论与建议")
        prompt_parts.append("[总结性建议]")
        prompt_parts.append("```")
        prompt_parts.append("")
        
        prompt = "\n".join(prompt_parts)
        return prompt


# ============================================================================
# 命令行入口
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="PRD Review Engine")
    parser.add_argument("--profile", required=True, help="Profile JSON path")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--prd", help="PRD content (file path or raw text)")
    parser.add_argument("--prd-url", help="PRD URL (fetch content)")
    parser.add_argument("--llm-response", help="LLM review output (file path)")
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
    elif args.prd_url:
        print(f"Fetching PRD from URL: {args.prd_url}")
        # TODO: 实现 URL 抓取
        print("⚠️  URL fetching not implemented yet")
        sys.exit(1)
    else:
        print("ERROR: --prd or --prd-url is required")
        sys.exit(1)
    
    # 执行审查
    engine = ReviewEngine(profile, args.output_dir, args.wiki_path)
    
    if args.llm_response:
        # LLM 已审查，生成报告
        llm_output = Path(args.llm_response).read_text(encoding="utf-8")
        result = engine.review_with_response(llm_output)
    else:
        # 生成审查 prompt
        result = engine.review(prd_text)
    
    print(f"\nResult: {json.dumps(result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
