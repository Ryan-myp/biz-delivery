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
from _common import extract_prd_keywords
from learn_repo import GoScanner, IRDocument
from base_engine import EngineBase


class TestEngine(EngineBase):
    """测试用例生成引擎"""
    
    def __init__(self, profile: dict, output_dir: str, wiki_path: Optional[str] = None):
        super().__init__(profile, output_dir, wiki_path)

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
        filtered = self._query_evidence_for_prd(prd_text, cache_dir)
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
    
    def _build_test_prompt(self, filtered: dict, ir: IRDocument, prd_text: str, td_text: Optional[str] = None, cache_dir: str = None) -> str:
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
        
        # Entity-Table 映射
        if ir.entity_tables:
            prompt_parts.append("## Entity-Table 映射（前15张）")
            for et in ir.entity_tables[:15]:
                entity = et.get('entity', '?')
                table = et.get('table', '?')
                prompt_parts.append(f"- `{entity}` → `{table}`")
            prompt_parts.append("")
        
        # 错误码
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
        
        # SQL 操作
        if ir.sql_operations:
            prompt_parts.append("## SQL 操作示例（前10个）")
            for sq in ir.sql_operations[:10]:
                op = sq.get('sql_operation', '?')
                table = sq.get('table', '?')
                file = sq.get('file', '?')
                prompt_parts.append(f"- `{op}` on `{table}` in `{file}`")
            prompt_parts.append("")
        
        # 测试覆盖
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
        
        # 路由摘要
        if filtered.get('evidence'):
            prompt_parts.append("## 现有路由")
            for route in filtered.get('evidence', [])[:30]:
                prompt_parts.append(f"- `{route.method.upper()}` {route.path} → `{route.handler}`")
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
        
        # 新增：注入实际错误码用于测试断言
        if ir.error_codes:
            prompt_parts.append("### 6.1 可用错误码（从代码提取）")
            for ec in ir.error_codes[:15]:
                name = ec.get('name', '?')
                code = ec.get('code', '?')
                msg = ec.get('message', '')
                prompt_parts.append(f"- `{name}`: {code} — {msg}")
            prompt_parts.append("")
        
        # 新增：注入实际 Request/Response struct 用于测试
        if ir.structs:
            prompt_parts.append("### 6.2 可用 Struct（从代码提取）")
            for s in ir.structs[:15]:
                if isinstance(s, dict):
                    name = s.get('name', '?')
                    fields = s.get('fields', [])
                else:
                    name = getattr(s, 'name', '?')
                    fields = getattr(s, 'fields', [])
                prompt_parts.append(f"- **`{name}`**: {', '.join(str(f.get('name', '')) if isinstance(f, dict) else str(f) for f in fields[:5])}")
            prompt_parts.append("")
        
        # 新增：注入实际路由和 handler 用于测试构造
        if ir.routes:
            prompt_parts.append("### 6.3 实际路由（从 IR 提取）")
            for route in ir.routes[:20]:
                method = getattr(route, 'method', 'GET').upper()
                path = getattr(route, 'path', '?')
                handler = getattr(route, 'handler', '?')
                prompt_parts.append(f"- `{method}` {path} → `{handler}`")
            prompt_parts.append("")
        
        # 新增：注入实际函数签名用于测试构造
        if ir.functions:
            prompt_parts.append("### 6.4 关键函数签名（从 IR 提取）")
            for func in ir.functions[:15]:
                if isinstance(func, dict):
                    name = func.get('name', '?')
                    params = func.get('params', '')
                    returns = func.get('returns', '')
                    file = func.get('file', '')
                else:
                    name = getattr(func, 'name', '?')
                    params = getattr(func, 'params', '')
                    returns = getattr(func, 'returns', '')
                    file = getattr(func, 'file', '')
                sig = f"{name}({params}) -> {returns}" if params or returns else name
                prompt_parts.append(f"- `{sig}` @ `{file}`")
            prompt_parts.append("")
        
        # 新增：注入状态转换模式用于状态机测试
        state_patterns = [
            r'\.SetStatus\s*\(', r'\.UpdateStatus\s*\(', r'status\s*=\s*\w+',
            r'\.Approve\s*\(', r'\.Reject\s*\(', r'\.Publish\s*\(',
            r'\.Submit\s*\(', r'\.Transition\s*\(', r'\.ChangeState\s*\(',
        ]
        state_funcs = []
        for func in ir.functions:
            fname = func.get('name', '') if isinstance(func, dict) else getattr(func, 'name', '')
            for pat in state_patterns:
                if re.search(pat, fname, re.IGNORECASE):
                    state_funcs.append(fname)
                    break
        if state_funcs:
            prompt_parts.append("### 6.5 状态转换函数（从 IR 提取）")
            for sf in state_funcs[:10]:
                prompt_parts.append(f"- `{sf}`")
            prompt_parts.append("基于以上状态转换函数，生成状态机测试用例")
            prompt_parts.append("")
        
        # 数据准备策略
        prompt_parts.append("### 6.6 数据准备策略")
        prompt_parts.append("- **Test Fixtures**: 使用 JSON/YAML fixture 文件准备测试数据")
        prompt_parts.append("- **Factory Pattern**: 使用 factory 函数生成测试对象（避免硬编码）")
        prompt_parts.append("- **Database Seeding**: 测试前用 seed 数据初始化 DB 状态")
        prompt_parts.append("- **事务回滚**: 每个测试在事务中执行，测试后自动回滚")
        prompt_parts.append("- **Clean Slate**: 测试结束后清理所有测试产生的数据")
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
        prompt_parts.append("## 5. 状态转换测试（如有状态机）")
        prompt_parts.append("")
        prompt_parts.append("如果代码中发现状态转换函数（SetStatus/UpdateStatus/Approve/Reject/Publish/Submit/Transition），")
        prompt_parts.append("必须生成完整的状态机测试：")
        prompt_parts.append("")
        prompt_parts.append("| ID | 场景 | 前置状态 | 操作 | 目标状态 | 优先级 |")
        prompt_parts.append("|----|------|----------|------|----------|--------|")
        prompt_parts.append("| TC501 | 正常流转 | DRAFT | Submit | PENDING_APPROVAL | P0 |")
        prompt_parts.append("| TC502 | 非法流转 | LIVE | Delete | 不允许 | P0 |")
        prompt_parts.append("| TC503 | 循环流转 | DRAFT | Approve | PENDING_APPROVAL → APPROVED | P0 |")
        prompt_parts.append("| TC504 | 回退流转 | APPROVED | Reject | REJECTED | P1 |")
        prompt_parts.append("| TC505 | 幂等流转 | DRAFT | Submit | DRAFT（不改变） | P1 |")
        prompt_parts.append("| TC506 | 并发状态修改 | DRAFT | 同时 Submit × 2 | 只有一个成功 | P0 |")
        prompt_parts.append("")
        prompt_parts.append("### 状态机测试要点")
        prompt_parts.append("- **合法转换**: 每个状态 → 允许的操作 → 目标状态")
        prompt_parts.append("- **非法转换**: 每个状态 → 不允许的操作 → 返回错误")
        prompt_parts.append("- **边界状态**: 初始状态、终止状态、中间状态")
        prompt_parts.append("- **并发安全**: 同一资源同时触发状态转换时的行为")
        prompt_parts.append("- **审计日志**: 每次状态变更是否记录审计日志")
        prompt_parts.append("")
        prompt_parts.append("## 6. 安全测试")
        prompt_parts.append("")
        prompt_parts.append("| ID | 场景 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |")
        prompt_parts.append("|----|------|----------|----------|----------|--------|")
        prompt_parts.append("| TC601 | SQL 注入 | 已登录 | 1. POST /api/v1/xxx name=x' OR 1=1-- | 返回 400 或转义 | P0 |")
        prompt_parts.append("| TC602 | XSS 攻击 | 已登录 | 1. POST /api/v1/xxx name=<script>alert(1)</script> | 返回 400 或转义 | P0 |")
        prompt_parts.append("| TC603 | 越权访问 | 用户A | 1. 访问用户B的资源 | 返回 403 Forbidden | P0 |")
        prompt_parts.append("| TC604 | 重复提交 | 已登录 | 1. 快速连续提交两次相同请求 | 只处理一次 | P1 |")
        prompt_parts.append("")
        prompt_parts.append("## 7. 自动化测试建议")
        prompt_parts.append("")
        prompt_parts.append("### 7.1 Go 单元测试框架")
        prompt_parts.append("- 测试文件: `*_test.go`")
        prompt_parts.append("- 测试框架: testify/gomock")
        prompt_parts.append("- 覆盖范围: Service 层核心逻辑")
        prompt_parts.append("")
        prompt_parts.append("### 7.2 集成测试")
        prompt_parts.append("- 测试文件: `*_integration_test.go`")
        prompt_parts.append("- 覆盖范围: Handler + Service + DAO")
        prompt_parts.append("- 需要 Mock 外部依赖")
        prompt_parts.append("")
        prompt_parts.append("### 7.3 E2E 测试")
        prompt_parts.append("- 测试文件: `e2e/*_test.go`")
        prompt_parts.append("- 覆盖范围: 完整请求链路")
        prompt_parts.append("- 需要启动完整服务")
        prompt_parts.append("")
        prompt_parts.append("### 7.4 自动化测试代码生成（Go + testify）")
        prompt_parts.append("为每个 P0 测试用例生成对应的 Go 测试代码框架：")
        prompt_parts.append("")
        prompt_parts.append("```go")
        prompt_parts.append("// TestCreateAdGroup_Success 测试正常创建广告组")
        prompt_parts.append("func TestCreateAdGroup_Success(t *testing.T) {")
        prompt_parts.append("    // 1. Setup: 创建 mock 依赖")
        prompt_parts.append("    ctrl := gomock.NewController(t)")
        prompt_parts.append("    defer ctrl.Finish()")
        prompt_parts.append("    ")
        prompt_parts.append("    // 2. Mock DAO 层")
        prompt_parts.append("    mockDAO := NewMockAdGroupDAO(ctrl)")
        prompt_parts.append("    mockDAO.EXPECT().Insert(gomock.Any()).Return(nil)")
        prompt_parts.append("    ")
        prompt_parts.append("    // 3. Mock Service 层")
        prompt_parts.append("    mockService := NewMockAdGroupService(ctrl)")
        prompt_parts.append("    mockService.EXPECT().Validate(gomock.Any()).Return(nil)")
        prompt_parts.append("    ")
        prompt_parts.append("    // 4. 构造请求")
        prompt_parts.append("    req := &CreateAdGroupRequest{")
        prompt_parts.append("        Name:  \"test-adgroup\",")
        prompt_parts.append("        Status: 1,")
        prompt_parts.append("    }")
        prompt_parts.append("    ")
        prompt_parts.append("    // 5. 执行")
        prompt_parts.append("    result, err := handler.CreateAdGroup(context.Background(), req)")
        prompt_parts.append("    ")
        prompt_parts.append("    // 6. 断言")
        prompt_parts.append("    assert.NoError(t, err)")
        prompt_parts.append("    assert.NotNil(t, result)")
        prompt_parts.append("    assert.Equal(t, 1, result.ID)")
        prompt_parts.append("}")
        prompt_parts.append("```")
        prompt_parts.append("")
        prompt_parts.append("### 7.5 自动化测试代码生成（pytest）")
        prompt_parts.append("如果是 Python 项目，生成 pytest 测试代码：")
        prompt_parts.append("")
        prompt_parts.append("```python")
        prompt_parts.append("def test_create_adgroup_success(mock_dao, mock_service):")
        prompt_parts.append("    '''测试正常创建广告组'''")
        prompt_parts.append("    # 1. Mock 依赖")
        prompt_parts.append("    mock_dao.insert.return_value = MagicMock(id=1)")
        prompt_parts.append("    mock_service.validate.return_value = None")
        prompt_parts.append("    ")
        prompt_parts.append("    # 2. 构造请求")
        prompt_parts.append("    request = CreateAdGroupRequest(")
        prompt_parts.append("        name='test-adgroup',")
        prompt_parts.append("        status=1")
        prompt_parts.append("    )")
        prompt_parts.append("    ")
        prompt_parts.append("    # 3. 执行")
        prompt_parts.append("    result = handler.create_adgroup(request)")
        prompt_parts.append("    ")
        prompt_parts.append("    # 4. 断言")
        prompt_parts.append("    assert result is not None")
        prompt_parts.append("    assert result.id == 1")
        prompt_parts.append("    mock_dao.insert.assert_called_once()")
        prompt_parts.append("```")
        prompt_parts.append("")
        prompt_parts.append("### 7.6 基于实际代码生成测试（重要）")
        prompt_parts.append("测试代码必须基于实际代码结构生成：")
        prompt_parts.append("- 使用 IR 中的实际 struct 名作为 Request/Response 类型")
        prompt_parts.append("- 使用 IR 中的实际 handler 函数名")
        prompt_parts.append("- 使用 IR 中的实际 DAO 方法名")
        prompt_parts.append("- 使用 IR 中的实际错误码")
        prompt_parts.append("- 使用 IR 中的实际路由路径")
        prompt_parts.append("")
        
        # 新增：注入 Mock 策略细化
        prompt_parts.append("### 7.7 Mock 策略细化")
        prompt_parts.append("")
        prompt_parts.append("根据依赖类型选择合适的 Mock 策略：")
        prompt_parts.append("")
        prompt_parts.append("| 依赖类型 | Mock 策略 | 说明 |")
        prompt_parts.append("|----------|-----------|------|")
        prompt_parts.append("| DAO 层 | Interface + gomock | 定义接口，自动生成 mock |")
        prompt_parts.append("| Service 层 | 手动构造 | 直接调用真实逻辑，Mock 内部依赖 |")
        prompt_parts.append("| HTTP 外部调用 | httptest.NewRecorder | 启动本地 HTTP server |")
        prompt_parts.append("| RPC/gRPC | 自定义 dialer + mock client | 替换 grpc.Dial 为 mock |")
        prompt_parts.append("| Config | 覆盖配置值 | 测试前修改配置，测试后恢复 |")
        prompt_parts.append("| Redis | 使用 testcontainers/redis-server | 启动临时 Redis 实例 |")
        prompt_parts.append("| Time | time.Now = func() { ... } | 替换全局时间函数 |")
        prompt_parts.append("| Context | context.WithTimeout/Cancel | 测试超时和取消场景 |")
        prompt_parts.append("")
        
        # 新增：数据准备策略细化
        prompt_parts.append("### 7.8 数据准备策略细化")
        prompt_parts.append("")
        prompt_parts.append("| 策略 | 适用场景 | 优点 | 缺点 |")
        prompt_parts.append("|------|----------|------|------|")
        prompt_parts.append("| Test Fixtures | 简单对象 | 直观易读 | 数据量大时维护困难 |")
        prompt_parts.append("| Factory Pattern | 复杂对象 | 灵活可扩展 | 需要编写工厂函数 |")
        prompt_parts.append("| DB Seeding | 集成测试 | 真实数据环境 | 需要清理数据 |")
        prompt_parts.append("| Transaction Rollback | 单元测试 | 自动回滚 | 不适用于事务外操作 |")
        prompt_parts.append("| Clean Slate | E2E 测试 | 完全隔离 | 初始化成本高 |")
        prompt_parts.append("")
        
        # 新增：测试覆盖率目标
        prompt_parts.append("### 7.9 测试覆盖率目标")
        prompt_parts.append("")
        prompt_parts.append("- **P0 用例**: 100% 覆盖率（核心流程、鉴权、数据一致性）")
        prompt_parts.append("- **P1 用例**: ≥80% 覆盖率（异常分支、边界条件）")
        prompt_parts.append("- **P2 用例**: ≥50% 覆盖率（边缘场景）")
        prompt_parts.append("- **行覆盖率**: ≥70%")
        prompt_parts.append("- **分支覆盖率**: ≥60%")
        prompt_parts.append("")
        
        prompt_parts.append("## 测试优先级说明")
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
