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
from typing import List, Optional

# 导入 learn_repo 的扫描器和 IR
sys.path.insert(0, str(Path(__file__).parent))
from learn_repo import GoScanner, IRDocument
from query_evidence import run_evidence_query


class ReviewEngine:
    """PRD 审查引擎"""
    
    def __init__(self, profile: dict, output_dir: str, wiki_path: Optional[str] = None, kb_dir: Optional[str] = None):
        self.profile = profile
        self.output_dir = Path(output_dir)
        self.wiki_path = wiki_path
        self.business_domain = profile.get("business_domain", "unknown")
        self.repos = profile.get("repositories", [])
        self.kb_dir = kb_dir
        if not self.kb_dir:
            # 从 profile 推断
            skill_dir = Path(__file__).parent.parent
            self.kb_dir = str(skill_dir / "knowledge" / self.business_domain)
        
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
        prompt = self._build_review_prompt(filtered, ir, prd_text, cache_dir)
        
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
        
        # 先搜 terminology（中文业务词 → 代码映射），提取相关 handler 名
        expanded_keywords = list(keywords)
        for keyword in keywords:
            try:
                result = run_evidence_query(
                    query=keyword,
                    wiki_path=self.wiki_path,
                    top_k=5,
                    sources=["code"],
                    cache_dir=cache_dir,
                )
                for ev in result.get('evidence', []):
                    if ev.get('type') == 'terminology':
                        for handler in ev.get('related_handlers', []):
                            if handler not in expanded_keywords:
                                expanded_keywords.append(handler)
            except:
                pass
        
        # 调用 query_evidence 查询代码
        all_evidence = []
        for keyword in expanded_keywords:
            try:
                result = run_evidence_query(
                    query=keyword,
                    wiki_path=self.wiki_path,
                    top_k=5,
                    sources=["code", "schema", "api_docs"],
                    cache_dir=cache_dir,
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
    
    def _build_review_prompt(self, filtered: dict, ir: IRDocument, prd_text: str, cache_dir: str = None) -> str:
        """构建 PRD 审查 prompt — 注入完整 IR 数据"""
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
        
        # 代码库全量摘要
        prompt_parts.append("## 代码库全量摘要")
        prompt_parts.append(f"- **业务域**: {self.business_domain}")
        prompt_parts.append(f"- **仓库**: {', '.join(r['name'] for r in self.repos)}")
        prompt_parts.append(f"- **语言**: {ir.language}")
        prompt_parts.append(f"- **Structs**: {len(ir.structs)}")
        prompt_parts.append(f"- **Functions**: {len(ir.functions)}")
        prompt_parts.append(f"- **Routes**: {len(ir.routes)}")
        prompt_parts.append(f"- **Entity Tables**: {len(ir.entity_tables)}")
        prompt_parts.append(f"- **SQL Operations**: {len(ir.sql_operations)}")
        prompt_parts.append(f"- **Error Codes**: {len(ir.error_codes)}")
        prompt_parts.append(f"- **Auth Models**: {len(ir.auth_models)}")
        prompt_parts.append(f"- **Test Coverage**: {ir.coverage_report.get('coverage_pct', 0)}%")
        prompt_parts.append("")
        
        # 关键路由（前30条）
        if ir.routes:
            prompt_parts.append("## 关键路由（前30条）")
            for route in ir.routes[:30]:
                method = getattr(route, 'method', 'GET').upper()
                path = getattr(route, 'path', '?')
                handler = getattr(route, 'handler', '?')
                prompt_parts.append(f"- `{method}` {path} → `{handler}`")
            prompt_parts.append("")
        
        # 业务逻辑（从入口点追踪的调用链）
        if ir.business_logic:
            prompt_parts.append("## 业务逻辑（入口点调用链）")
            for bl in ir.business_logic[:10]:
                route = bl.get('route', '?')
                method = bl.get('method', 'GET')
                handler = bl.get('handler', '?')
                desc = bl.get('description', '')
                prompt_parts.append(f"- `{method}` {route} → `{handler}`")
                prompt_parts.append(f"  逻辑: {desc}")
                calls = bl.get('calls', [])
                if calls:
                    prompt_parts.append(f"  调用: {', '.join(calls[:8])}")
                second = bl.get('second_layer', [])
                if second:
                    for sl in second[:5]:
                        prompt_parts.append(f"    - {sl.get('name', '?')}() @ {sl.get('file', '?')}")
                prompt_parts.append("")
        
        # Entity Table 映射
        if ir.entity_tables:
            prompt_parts.append("## Entity-Table 映射（前15张）")
            for et in ir.entity_tables[:15]:
                entity = et.get('entity', '?')
                table = et.get('table', '?')
                prompt_parts.append(f"- `{entity}` → `{table}`")
            prompt_parts.append("")
        
        # 错误码（前15个）
        if ir.error_codes:
            prompt_parts.append("## 错误码（前15个）")
            for ec in ir.error_codes[:15]:
                name = ec.get('name', '?')
                code = ec.get('code', '?')
                msg = ec.get('message', '')
                prompt_parts.append(f"- `{name}`: {code} — {msg}")
            prompt_parts.append("")
        
        # 鉴权模型
        if ir.auth_models:
            prompt_parts.append("## 鉴权模型")
            for am in ir.auth_models:
                mw = am.get('middleware', '?')
                logic = am.get('logic', '')
                prompt_parts.append(f"- **{mw}**: {logic}")
            prompt_parts.append("")
        
        # SQL 操作（前10个）
        if ir.sql_operations:
            prompt_parts.append("## SQL 操作示例（前10个）")
            for sq in ir.sql_operations[:10]:
                op = sq.get('sql_operation', '?')
                table = sq.get('table', '?')
                file = sq.get('file', '?')
                prompt_parts.append(f"- `{op}` on `{table}` in `{file}`")
            prompt_parts.append("")

        
        # 测试覆盖情况
# 从 profile 加载状态机/业务规则/服务拓扑
        
        # 从 profile 加载状态机/业务规则/服务拓扑
        profile_data = self.profile.get('profile', {})
        
        # 注入核心业务流程（从 IR 自动推断）
        if hasattr(ir, 'core_flows') and ir.core_flows:
            prompt_parts.append("## 核心业务流程（从代码自动推断）")
            for cf in ir.core_flows[:8]:
                prompt_parts.append(f"- **{cf.get('flow_name', '?')}**: {cf.get('entry_point', '?')}")
                prompt_parts.append(f"  路由: {cf.get('route_prefix', '?')}")
                prompt_parts.append(f"  调用链: {', '.join(cf.get('call_chain', [])[:6])}")
                prompt_parts.append(f"  数据流: {cf.get('data_flow', '?')}")
                prompt_parts.append(f"  深度: {cf.get('max_depth', 0)}")
            prompt_parts.append("")
        
        if profile_data.get("state_machines"):
            prompt_parts.append("## 状态机（从 profile 配置）")
            for entity, sm in profile_data["state_machines"].items():
                prompt_parts.append(f"- **{entity}**: {sm.get('fields', [])}")
                for field, details in sm.get("Status", {}).items():
                    if isinstance(details, dict) and "values" in details:
                        prompt_parts.append(f"  {field}: {details['values']}")
            prompt_parts.append("")

        if profile_data.get("business_rules"):
            prompt_parts.append("## 业务规则（从 profile 配置）")
            for cat, rules in profile_data["business_rules"].items():
                prompt_parts.append(f"- **{cat}**: {rules[:5]}")
            prompt_parts.append("")

        if profile_data.get("service_topology"):
            prompt_parts.append("## 服务拓扑（从 profile 配置）")
            for svc in profile_data["service_topology"].get("services", []):
                name = svc.get("name", "unknown")
                desc = svc.get("description", "")
                deps = svc.get("dependencies", [])
                if deps:
                    prompt_parts.append(f"- **{name}**: {desc} → 依赖: {deps}")
                else:
                    prompt_parts.append(f"- **{name}**: {desc}")
            prompt_parts.append("")
        # 注入知识摘要
        summary_file = Path(self.kb_dir) / "summary.md" if self.kb_dir else None
        if summary_file and summary_file.exists():
            prompt_parts.append("## 项目知识摘要（从代码自动提取）")
            prompt_parts.append(summary_file.read_text(encoding='utf-8'))
            prompt_parts.append("")
        
        # 注入知识库（从 ryan-personal-knowledge 自动选择相关知识）
        kb_refs = self._get_kb_references(prd_text)
        if kb_refs:
            prompt_parts.append("## 相关知识参考（从知识库自动提取）")
            for ref in kb_refs:
                prompt_parts.append(ref)
            prompt_parts.append("")

        if ir.test_functions:
            prompt_parts.append("## 测试覆盖情况")
            prompt_parts.append(f"- **测试文件**: {len(ir.test_files)}")
            prompt_parts.append(f"- **测试函数**: {len(ir.test_functions)}")
            prompt_parts.append(f"- **框架**: {ir.coverage_report.get('framework', 'unknown')}")
            if ir.coverage_report.get('uncovered_highlights'):
                uncovered = ir.coverage_report['uncovered_highlights'][:10]
                prompt_parts.append(f"- **未覆盖函数**: {', '.join(uncovered)}")
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
        
        # 业务卡片（从 business_cards.json 加载）
        # 从 kb_dir 找 business_cards.json
        bc_file = None
        if self.kb_dir:
            candidate = Path(self.kb_dir) / "business_cards.json"
            if candidate.exists():
                bc_file = candidate
        if not bc_file and cache_dir:
            candidate = Path(cache_dir) / "business_cards.json"
            if candidate.exists():
                bc_file = candidate
        if bc_file and bc_file.exists():
            try:
                with open(bc_file) as f:
                    bc_data = json.load(f)
                
                prompt_parts.append("## 业务知识卡片（从代码自动提取）")
                prompt_parts.append("")
                
                # 场景卡
                scenarios = bc_data.get('scenario_cards', [])
                if scenarios:
                    prompt_parts.append(f"### 业务场景（共{len(scenarios)}个）")
                    for sc in scenarios[:10]:
                        prompt_parts.append(f"- **{sc['scenario']}**: {sc['entry_point']}")
                        prompt_parts.append(f"  - 描述: {sc.get('description', '')[:200]}")
                        if sc.get('call_chain'):
                            prompt_parts.append(f"  - 调用链: {', '.join(sc['call_chain'][:5])}")
                        if sc.get('data_points'):
                            prompt_parts.append(f"  - 数据流: {', '.join(sc['data_points'][:3])}")
                    prompt_parts.append("")
                
                # 实体关系
                entities = bc_data.get('entity_relationships', [])
                if entities:
                    prompt_parts.append(f"### 实体关系（共{len(entities)}个）")
                    for er in entities[:10]:
                        prompt_parts.append(f"- `{er['entity']}` → `{er['table']}`")
                    prompt_parts.append("")
                
                # 错误分类
                errors = bc_data.get('error_categories', {})
                if errors:
                    prompt_parts.append("### 错误码分类")
                    for cat, errs in errors.items():
                        prompt_parts.append(f"- **{cat}**: {len(errs)} 个错误码")
                        for e in errs[:3]:
                            prompt_parts.append(f"  - `{e.get('name', '')}`: {e.get('message', '')}")
                    prompt_parts.append("")
                
                # 鉴权模型
                auths = bc_data.get('auth_models', [])
                if auths:
                    prompt_parts.append("### 鉴权模型")
                    for am in auths:
                        prompt_parts.append(f"- **{am.get('middleware', '')}**: {am.get('logic', '')}")
                    prompt_parts.append("")
            except Exception as e:
                prompt_parts.append(f"⚠️  Failed to load business_cards.json: {e}")
                prompt_parts.append("")

        # PRD 内容
        prompt_parts.append("## PRD 内容")
        prompt_parts.append(prd_text)
        prompt_parts.append("")
        
        # 审查规则（保持不变）
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
        
        # 新增：兼容性检查（从 profile 读取旧接口列表）
        prompt_parts.append("### 5. 兼容性检查（从 profile 配置）")
        if profile_data.get("business_rules"):
            prompt_parts.append("- **约束冲突**: PRD 是否违反了已有的业务规则/约束？")
            for cat, rules in profile_data["business_rules"].items():
                if isinstance(rules, list) and len(rules) <= 10:
                    prompt_parts.append(f"  - 已有规则 `{cat}`: {', '.join(str(r) for r in rules[:3])}")
        if profile_data.get("service_topology"):
            prompt_parts.append("- **服务依赖**: PRD 涉及的服务是否会影响上下游依赖？")
            for svc in profile_data["service_topology"].get("services", []):
                name = svc.get("name", "")
                deps = svc.get("dependencies", [])
                if deps:
                    prompt_parts.append(f"  - `{name}` 依赖: {', '.join(deps[:5])}")
        prompt_parts.append("")
        
        # 新增：性能风险评估
        prompt_parts.append("### 6. 性能风险评估")
        if hasattr(ir, 'perf_hotspots') and ir.perf_hotspots:
            prompt_parts.append("- **已知性能热点**（从代码分析）:")
            for hs in ir.perf_hotspots[:5]:
                prompt_parts.append(f"  - `{hs.get('func', '?')}` @ {hs.get('file', '?')}: {hs.get('reason', 'N/A')}")
        prompt_parts.append("- **QPS 评估**: PRD 描述的功能预计 QPS 是多少？现有架构能否支撑？")
        prompt_parts.append("- **数据库压力**: 新增查询是否走了索引？是否有 N+1 查询风险？")
        prompt_parts.append("- **缓存策略**: 读多写少的场景是否考虑了缓存？缓存失效策略？")
        prompt_parts.append("- **外部依赖**: 调用的外部 API 是否有超时/重试/熔断策略？")
        prompt_parts.append("")
        
        # 新增：核心业务流程校验
        if hasattr(ir, 'core_flows') and ir.core_flows:
            prompt_parts.append("### 7. 核心业务流程校验")
            prompt_parts.append("- **流程冲突**: PRD 描述的流程是否与现有核心流程冲突？")
            for cf in ir.core_flows[:5]:
                flow_name = cf.get('flow_name', '?')
                data_flow = cf.get('data_flow', '?')
                prompt_parts.append(f"  - 现有流程 `{flow_name}`: {data_flow}")
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
        prompt_parts.append("## 问题清单（按优先级排序）")
        prompt_parts.append("")
        prompt_parts.append("### P0 — 阻塞（必须修改才能继续）")
        prompt_parts.append("- **[P0]** [标题] 描述 + 影响 + 建议修改方案")
        prompt_parts.append("- 定义：与现有架构冲突、数据模型不匹配、核心流程缺失")
        prompt_parts.append("")
        prompt_parts.append("### P1 — 重要（建议修改）")
        prompt_parts.append("- **[P1]** [标题] 描述 + 建议")
        prompt_parts.append("- 定义：异常处理缺失、边界条件未考虑、权限不明确")
        prompt_parts.append("")
        prompt_parts.append("### P2 — 一般（可选优化）")
        prompt_parts.append("- **[P2]** [标题] 描述 + 建议")
        prompt_parts.append("- 定义：用户体验优化、性能优化建议、文档完善")
        prompt_parts.append("")
        prompt_parts.append("## 合理性检查")
        prompt_parts.append("- [问题1] 描述 + 严重性（P0/P1/P2）+ 建议")
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
        prompt_parts.append("## 兼容性检查")
        prompt_parts.append("- **业务规则冲突**: [具体规则] — 违反程度 + 建议")
        prompt_parts.append("- **服务依赖影响**: [服务名] — 影响范围 + 建议")
        prompt_parts.append("- **旧接口兼容**: 旧接口是否受影响？是否需要 versioning？")
        prompt_parts.append("")
        prompt_parts.append("## 性能风险评估")
        prompt_parts.append("- **QPS 预估**: [数值] — 现有架构是否支撑？")
        prompt_parts.append("- **数据库风险**: [索引/N+1/锁竞争] — 说明")
        prompt_parts.append("- **缓存策略**: [有/无] — 建议")
        prompt_parts.append("- **外部依赖风险**: [超时/重试/熔断] — 说明")
        prompt_parts.append("")
        prompt_parts.append("## 核心流程校验")
        prompt_parts.append("- **流程冲突**: PRD 流程是否与现有核心流程冲突？")
        prompt_parts.append("- **数据流冲突**: PRD 数据流向是否与现有架构一致？")
        prompt_parts.append("")
        prompt_parts.append("## 结论与建议")
        prompt_parts.append("[总结性建议]")
        prompt_parts.append("```")
        prompt_parts.append("")
        
        prompt = "\n".join(prompt_parts)
        return prompt

    def _get_kb_references(self, prd_text: str) -> List[str]:
        """根据 PRD 内容，从知识库选择相关知识 — 增强版"""
        references = []
        
        # 知识库路径
        kb_base = Path('/Users/yanping.ma/ryan-personal-knowledge/knowledge')
        if not kb_base.exists():
            return references
        
        # PRD 关键词（按权重排序）
        high_priority = ['竞价', '出价', 'bidding', '竞价引擎', 'CTR', 'CVR', '排序', '召回', '推荐']
        medium_priority = ['redis', '缓存', 'kafka', '消息队列', 'mysql', '数据库', 'es', 'elasticsearch', '搜索']
        low_priority = ['k8s', 'docker', '部署', '架构', '设计', '高并发', '微服务', 'agent', 'AI']
        
        # 精确匹配（高优先级）
        for kw in high_priority:
            if kw.lower() in prd_text.lower():
                kb_dir = 'advertising'
                kb_path = kb_base / kb_dir
                if kb_path.exists():
                    # 读取前 3 个深度文件（前 150 行）
                    md_files = sorted(kb_path.rglob('*-deep.md'))[:3]
                    for md_file in md_files:
                        try:
                            content = md_file.read_text(encoding='utf-8', errors='ignore')
                            lines = content.split('\n')[:150]
                            references.append(f"### {md_file.relative_to(kb_base)}")
                            references.append('\n'.join(lines))
                            references.append("")
                        except:
                            pass
                    break  # 只取最高优先级
        
        # 中优先级
        if not references:
            for kw in medium_priority:
                if kw.lower() in prd_text.lower():
                    kb_dir = 'middleware'
                    kb_path = kb_base / kb_dir
                    if kb_path.exists():
                        md_files = sorted(kb_path.rglob('*-deep.md'))[:2]
                        for md_file in md_files:
                            try:
                                content = md_file.read_text(encoding='utf-8', errors='ignore')
                                lines = content.split('\n')[:150]
                                references.append(f"### {md_file.relative_to(kb_base)}")
                                references.append('\n'.join(lines))
                                references.append("")
                            except:
                                pass
                        break
        
        # 低优先级
        if not references:
            for kw in low_priority:
                if kw.lower() in prd_text.lower():
                    kb_dir = 'architecture'
                    kb_path = kb_base / kb_dir
                    if kb_path.exists():
                        md_files = sorted(kb_path.rglob('*-deep.md'))[:2]
                        for md_file in md_files:
                            try:
                                content = md_file.read_text(encoding='utf-8', errors='ignore')
                                lines = content.split('\n')[:150]
                                references.append(f"### {md_file.relative_to(kb_base)}")
                                references.append('\n'.join(lines))
                                references.append("")
                            except:
                                pass
                        break
        
        return references



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
