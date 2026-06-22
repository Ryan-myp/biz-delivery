#!/usr/bin/env python3
"""测试用例生成引擎 — 基于 PRD + 代码库 IR 生成测试用例

工作流程：
1. 加载 profile，扫描代码获取 IR
2. 加载 PRD 内容和 TD（可选）
3. 生成测试用例：正向流程、异常分支、边界条件
4. 输出测试用例文档
"""

import json
import re
import os
import sys
import time
from pathlib import Path
from typing import Optional

# 导入证据查询和 learn_repo
sys.path.insert(0, str(Path(__file__).parent))
from query_evidence import run_evidence_query
from learn_repo import GoScanner, IRDocument


class TestEngine:
    """测试用例生成引擎"""
    
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
        # 智能关键词提取：先按标点/空格分句，再提取有意义的短语
        sentences = re.split(r'[，。、；：\s\n]]+', prd_text)
        keywords = []
        for s in sentences:
            s = s.strip()
            if 2 <= len(s) <= 12:  # 合理长度的中文短语
                keywords.append(s)
            elif len(s) >= 3:  # 英文单词
                keywords.append(s)
        # 去重，保留前 10 个
        keywords = list(dict.fromkeys(keywords))[:10]
        
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

    def generate_tests(self, prd_text: str, td_text: Optional[str] = None) -> dict:
        """生成测试用例
        
        Args:
            prd_text: PRD 内容
            td_text: 可选，技术方案内容
            
        Returns:
            测试用例生成结果 dict
        """
        # Step 0: 扫描代码库获取 IR
        print("📡 Step 0: Scanning codebase...")
        ir = self._scan_codebase()
        
        # Step 1: 查询代码库证据
        print("🔍 Step 1: Querying evidence from codebase...")
        cache_dir = str(self.output_dir)
        filtered = self._query_evidence_for_prd(ir, prd_text, cache_dir)
        print(f"  Found {filtered.get('total', 0)} evidence items")
        
        # Step 2: 构建测试用例 prompt
        print("📝 Step 2: Building test case prompt...")
        prompt = self._build_test_prompt(filtered, ir, prd_text, td_text)
        
        # Step 3: 保存 prompt 供 LLM 调用
        prompt_file = self.output_dir / "test_prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")
        print(f"✅ Prompt saved to: {prompt_file}")
        
        return {
            "status": "prompt_ready",
            "message": "Test case prompt generated. Send to LLM, then call generate_with_response().",
            "prompt_file": str(prompt_file),
            "prd_length": len(prd_text),
        }
    
    def _query_evidence_for_prd(self, ir, prd_text: str, cache_dir: str = None) -> dict:
        """从 PRD 提取关键词，调用 query_evidence 查询代码库证据"""
        import re
        # 智能关键词提取：先按标点/空格分句，再提取有意义的短语
        sentences = re.split(r'[，。、；：\s\n]]+', prd_text)
        keywords = []
        for s in sentences:
            s = s.strip()
            if 2 <= len(s) <= 12:  # 合理长度的中文短语
                keywords.append(s)
            elif len(s) >= 3:  # 英文单词
                keywords.append(s)
        # 去重，保留前 10 个
        keywords = list(dict.fromkeys(keywords))[:10]
        
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
        """LLM 生成测试用例后，保存报告
        
        Args:
            llm_response: LLM 的测试用例输出
            
        Returns:
            测试用例报告 dict
        """
        report_file = self.output_dir / "test_cases.md"
        report_file.write_text(llm_response, encoding="utf-8")
        
        return {
            "status": "completed",
            "report_file": str(report_file),
            "sections": ["正向流程", "异常分支", "边界条件", "性能测试", "安全测试"],
        }
    
    def _query_evidence(self, prd_text: str) -> list:
        """从 PRD 提取关键词，查询代码库证据"""
        import re
        # 智能关键词提取：先按标点/空格分句，再提取有意义的短语
        sentences = re.split(r'[，。、；：\s\n]]+', prd_text)
        keywords = []
        for s in sentences:
            s = s.strip()
            if 2 <= len(s) <= 12:  # 合理长度的中文短语
                keywords.append(s)
            elif len(s) >= 3:  # 英文单词
                keywords.append(s)
        # 去重，保留前 10 个
        keywords = list(dict.fromkeys(keywords))[:10]
        
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
    
    def _build_test_prompt(self, filtered: dict, ir: IRDocument, prd_text: str, td_text: Optional[str] = None) -> str:
        """构建测试用例生成 prompt
        
        核心思路：
        - 让 LLM 基于 PRD 描述的业务流程生成测试用例
        - 覆盖正向流程、异常分支、边界条件
        - 参考代码库的路由和函数定义，确保测试覆盖真实接口
        """
        prompt_parts = []
        
        # 角色设定
        prompt_parts.append("# 测试用例生成任务")
        prompt_parts.append("")
        prompt_parts.append("你是一位资深 QA 工程师。请基于以下 PRD 和代码库扫描结果，")
        prompt_parts.append("生成一份全面的测试用例，覆盖正向流程、异常分支和边界条件。")
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
        
        # PRD 内容
        prompt_parts.append("## PRD 内容")
        prompt_parts.append(prd_text)
        prompt_parts.append("")
        
        # TD 内容（如果有）
        if td_text:
            prompt_parts.append("## 技术方案")
            prompt_parts.append(td_text)
            prompt_parts.append("")
        
        # 测试用例生成规则
        prompt_parts.append("## 测试用例生成规则")
        prompt_parts.append("")
        prompt_parts.append("### 1. 正向流程测试")
        prompt_parts.append("- 覆盖 PRD 描述的主流程")
        prompt_parts.append("- 每个流程节点都要有对应的测试用例")
        prompt_parts.append("- 包括：请求参数、预期结果、数据库状态变化")
        prompt_parts.append("")
        prompt_parts.append("### 2. 异常分支测试")
        prompt_parts.append("- **权限不足**: 未登录、无权限操作")
        prompt_parts.append("- **数据校验失败**: 必填字段缺失、格式错误、超限")
        prompt_parts.append("- **业务异常**: 资源不存在、状态不允许操作、并发冲突")
        prompt_parts.append("- **系统异常**: 数据库连接失败、RPC 超时、第三方服务不可用")
        prompt_parts.append("")
        prompt_parts.append("### 3. 边界条件测试")
        prompt_parts.append("- **空数据**: 列表为空、字段为空字符串")
        prompt_parts.append("- **极值**: 最大/最小值、超长字符串")
        prompt_parts.append("- **并发**: 同一资源同时修改、幂等性检查")
        prompt_parts.append("- **分页**: 第一页、最后一页、空页、超大页")
        prompt_parts.append("")
        prompt_parts.append("### 4. 兼容性测试（如果是新功能）")
        prompt_parts.append("- 旧接口是否受影响？")
        prompt_parts.append("- 旧数据是否能正常访问？")
        prompt_parts.append("- 灰度发布策略是否正确？")
        prompt_parts.append("")
        prompt_parts.append("### 5. 性能测试（如果是高频接口）")
        prompt_parts.append("- QPS 要求是多少？")
        prompt_parts.append("- 是否有缓存策略？")
        prompt_parts.append("- 数据库查询是否加了索引？")
        prompt_parts.append("")
        
        # 输出格式
        prompt_parts.append("## 输出格式")
        prompt_parts.append("请按以下 Markdown 格式输出测试用例：")
        prompt_parts.append("")
        prompt_parts.append("```markdown")
        prompt_parts.append("# 测试用例: [功能名称]")
        prompt_parts.append("")
        prompt_parts.append("## 1. 正向流程测试")
        prompt_parts.append("")
        prompt_parts.append("| ID | 场景 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |")
        prompt_parts.append("|----|------|----------|----------|----------|--------|")
        prompt_parts.append("| TC001 | 创建XXX | 已登录、有权限 | 1. POST /api/v1/xxx\\n2. 携带有效参数 | 返回 200，创建成功 | P0 |")
        prompt_parts.append("| TC002 | 查询XXX列表 | 已登录 | 1. GET /api/v1/xxx?page=1&size=10 | 返回 200，列表数据 | P0 |")
        prompt_parts.append("")
        prompt_parts.append("## 2. 异常分支测试")
        prompt_parts.append("")
        prompt_parts.append("| ID | 场景 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |")
        prompt_parts.append("|----|------|----------|----------|----------|--------|")
        prompt_parts.append("| TC101 | 未登录访问 | 未登录 | 1. POST /api/v1/xxx | 返回 401 Unauthorized | P0 |")
        prompt_parts.append("| TC102 | 必填字段缺失 | 已登录 | 1. POST /api/v1/xxx 不带 name 字段 | 返回 400，错误信息 | P0 |")
        prompt_parts.append("| TC103 | 资源不存在 | 已登录 | 1. GET /api/v1/xxx/{invalid_id} | 返回 404 Not Found | P1 |")
        prompt_parts.append("| TC104 | 并发修改冲突 | 已登录 | 1. 两个请求同时修改同一资源 | 返回 409 Conflict | P1 |")
        prompt_parts.append("")
        prompt_parts.append("## 3. 边界条件测试")
        prompt_parts.append("")
        prompt_parts.append("| ID | 场景 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |")
        prompt_parts.append("|----|------|----------|----------|----------|--------|")
        prompt_parts.append("| TC201 | 空列表查询 | 已登录 | 1. GET /api/v1/xxx 无数据 | 返回 200，空数组 | P1 |")
        prompt_parts.append("| TC202 | 超长字符串 | 已登录 | 1. POST /api/v1/xxx name=1000字符 | 返回 400 或截断 | P1 |")
        prompt_parts.append("| TC203 | 超大分页 | 已登录 | 1. GET /api/v1/xxx?page=1&size=10000 | 返回 400 或限制 | P2 |")
        prompt_parts.append("")
        prompt_parts.append("## 4. 兼容性测试（如有）")
        prompt_parts.append("")
        prompt_parts.append("| ID | 场景 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |")
        prompt_parts.append("|----|------|----------|----------|----------|--------|")
        prompt_parts.append("| TC301 | 旧接口不受影响 | 已登录 | 1. 调用旧接口 | 返回 200，功能正常 | P0 |")
        prompt_parts.append("| TC302 | 旧数据可读 | 有旧数据 | 1. 查询旧数据 | 返回 200，数据完整 | P0 |")
        prompt_parts.append("")
        prompt_parts.append("## 5. 自动化测试建议")
        prompt_parts.append("")
        prompt_parts.append("### 5.1 单元测试")
        prompt_parts.append("- 测试文件: `*_test.go`")
        prompt_parts.append("- 测试框架: goconvey/testify")
        prompt_parts.append("- 覆盖范围: Service 层核心逻辑")
        prompt_parts.append("")
        prompt_parts.append("### 5.2 集成测试")
        prompt_parts.append("- 测试文件: `*_integration_test.go`")
        prompt_parts.append("- 覆盖范围: Handler + Service + DAO")
        prompt_parts.append("- 需要 Mock 外部依赖")
        prompt_parts.append("")
        prompt_parts.append("### 5.3 E2E 测试")
        prompt_parts.append("- 测试文件: `e2e/*_test.go`")
        prompt_parts.append("- 覆盖范围: 完整请求链路")
        prompt_parts.append("- 需要启动完整服务")
        prompt_parts.append("")
        prompt_parts.append("## 测试优先级说明")
        prompt_parts.append("- **P0**: 阻塞性测试，必须通过")
        prompt_parts.append("- **P1**: 重要功能测试，建议通过")
        prompt_parts.append("- **P2**: 边缘场景测试，视时间而定")
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
    
    parser = argparse.ArgumentParser(description="Test Case Generation Engine")
    parser.add_argument("--profile", required=True, help="Profile JSON path")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--prd", help="PRD content (file path or raw text)")
    parser.add_argument("--td", help="Technical design file path (optional)")
    parser.add_argument("--llm-response", help="LLM test output (file path)")
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
    
    # 获取 TD 内容（可选）
    td_text = None
    if args.td and Path(args.td).exists():
        td_text = Path(args.td).read_text(encoding="utf-8")
    
    # 执行测试用例生成
    engine = TestEngine(profile, args.output_dir, args.wiki_path)
    
    if args.llm_response:
        # LLM 已生成测试用例
        llm_output = Path(args.llm_response).read_text(encoding="utf-8")
        result = engine.generate_with_response(llm_output)
    else:
        # 生成测试用例 prompt
        result = engine.generate_tests(prd_text, td_text)
    
    print(f"\nResult: {json.dumps(result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
