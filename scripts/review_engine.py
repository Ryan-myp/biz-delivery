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
from typing import Dict, List, Optional

# 导入 learn_repo 的扫描器和 IR
sys.path.insert(0, str(Path(__file__).parent))
from _common import extract_prd_keywords
from learn_repo import GoScanner, IRDocument
from base_engine import EngineBase
from query_evidence import fuzzy_score as _fuzzy_score


class ReviewEngine(EngineBase):
    """PRD 审查引擎"""
    
    def __init__(self, profile: dict, output_dir: str, wiki_path: Optional[str] = None):
        super().__init__(profile, output_dir, wiki_path)
        # kb_dir is auto-inferred in EngineBase
        
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
        filtered = self._query_and_validate(ir, prd_text, cache_dir)
        
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
        
        # 解析 LLM 输出，提取结构化数据
        parsed = self._parse_review_report(llm_response)
        
        return {
            "status": "completed",
            "report_file": str(report_file),
            "sections": ["合理性检查", "场景遗漏", "前后一致性", "风险评估"],
            "parsed": parsed,
        }
    
    def _parse_review_report(self, llm_response: str) -> dict:
        """解析 LLM 审查报告，提取结构化数据。
        
        从 Markdown 格式的审查报告中提取：
        - P0/P1/P2 问题清单
        - 总体评价
        - 各项检查的结论
        """
        result = {
            'overall_status': 'unknown',
            'p0_issues': [],
            'p1_issues': [],
            'p2_issues': [],
            'sections': {},
        }
        
        # 提取总体评价
        status_match = re.search(r'(通过|需修订|阻塞|Approved|Needs Revision|Blocked)', llm_response)
        if status_match:
            result['overall_status'] = status_match.group(1)
        
        # 提取 P0 问题
        p0_section = self._extract_section(llm_response, 'P0')
        if p0_section:
            result['p0_issues'] = self._parse_issue_list(p0_section)
        
        # 提取 P1 问题
        p1_section = self._extract_section(llm_response, 'P1')
        if p1_section:
            result['p1_issues'] = self._parse_issue_list(p1_section)
        
        # 提取 P2 问题
        p2_section = self._extract_section(llm_response, 'P2')
        if p2_section:
            result['p2_issues'] = self._parse_issue_list(p2_section)
        
        # 提取各 section 内容
        for section_name in ['合理性检查', '场景遗漏', '前后不一致', '风险评估', 
                            '兼容性检查', '性能风险评估', '安全检查', '可观测性检查',
                            '数据合规检查', '发布策略检查', '结论与建议']:
            content = self._extract_section(llm_response, section_name)
            if content:
                result['sections'][section_name] = content.strip()
        
        return result
    
    def _extract_section(self, text: str, heading: str) -> Optional[str]:
        """从 Markdown 文本中提取指定 section 的内容。"""
        # 匹配 ### heading 或 ## heading 后面的内容
        pattern = rf'(?:#{1,2}\s+)?{re.escape(heading)}.*?\n((?:[^\n]*\n?)*)'
        match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
        if match:
            content = match.group(1).strip()
            # 截断到下一个 ### 或 ## heading
            next_heading = re.search(r'\n###?\s+\w', content)
            if next_heading:
                content = content[:next_heading.start()]
            return content
        return None
    
    def _parse_issue_list(self, section_text: str) -> List[Dict]:
        """从 section 文本中解析问题列表。"""
        issues = []
        for line in section_text.split('\n'):
            line = line.strip()
            if not line or not line.startswith('-'):
                continue
            # 提取 [P0]/[P1]/[P2] 标记
            issue_match = re.match(r'-\s*\[?(P\d)\]?\s+(.+)', line)
            if issue_match:
                priority = issue_match.group(1)
                content = issue_match.group(2).strip()
                issues.append({
                    'priority': priority,
                    'title': content.split(' ')[0] if ' ' in content else content[:30],
                    'description': content,
                })
        return issues
    
    def _query_and_validate(self, ir: IRDocument, prd_text: str, cache_dir: str) -> dict:
        """从 PRD 提取关键词，调用 query_evidence 查询代码库证据。

        增强策略：
        1. 使用 base_engine._query_evidence_for_prd 共享实现（避免重复）
        2. 预检：检查 PRD 中提到的实体是否在代码中存在
        3. 业务规则自动校验
        """
        # 使用 base_engine 的共享证据查询方法
        filtered = self._query_evidence_for_prd(prd_text, cache_dir)
        
        # 预检：检查 PRD 中提到的实体是否在代码中存在
        prechecks = self._run_prechecks(ir, prd_text, filtered.get('evidence', []))
        
        # 业务规则自动校验
        profile_data = self._normalize_profile(self.profile)
        rule_checks = self._validate_business_rules(ir, prd_text, profile_data)
        if rule_checks:
            prechecks.extend(rule_checks)
        
        filtered['prechecks'] = prechecks
        print(f"  Found {filtered['total']} evidence items, {len(prechecks)} prechecks")
        
        return filtered
    
    def _run_prechecks(self, ir: IRDocument, prd_text: str, evidence: list) -> List[Dict]:
        """运行预检查 — 在 LLM 审查前先标记明显问题
        
        返回: [{check_name, severity, description}]
        """
        checks = []
        
        # 1. PRD 提到的业务实体是否在代码中存在
        prd_entities = set()
        # 从 PRD 提取可能的实体名（大写驼峰、中文业务词）
        camel_entities = re.findall(r'[A-Z][a-z]+[A-Z]\\w*', prd_text)
        chinese_entities = re.findall(r'[\\u4e00-\\u9fff]{2,6}', prd_text)
        
        code_entities = set()
        for s in ir.structs:
            if hasattr(s, 'name'):
                code_entities.add(s.name)
            elif isinstance(s, dict):
                code_entities.add(s.get('name', ''))
        for f in ir.functions:
            if hasattr(f, 'name'):
                code_entities.add(f.name)
            elif isinstance(f, dict):
                code_entities.add(f.get('name', ''))
        
        for entity in camel_entities:
            if entity in code_entities:
                checks.append({
                    'check': 'entity_exists',
                    'severity': 'info',
                    'entity': entity,
                    'message': f"PRD 提到的实体 '{entity}' 在代码中存在",
                })
            else:
                # 检查 fuzzy 匹配
                best_match = None
                best_score = 0
                for ce in code_entities:
                    score = _fuzzy_score(entity.lower(), ce.lower())
                    if score > best_score:
                        best_score = score
                        best_match = ce
                if best_score < 0.5:
                    checks.append({
                        'check': 'entity_missing',
                        'severity': 'warn',
                        'entity': entity,
                        'message': f"PRD 提到的实体 '{entity}' 在代码中未找到（fuzzy 最佳匹配: {best_match} @ {best_score:.2f}）",
                    })
        
        # 2. PRD 提到的路由是否在代码中存在
        prd_routes = re.findall(r'/api/\w+/\w+', prd_text)
        code_routes = set()
        for r in ir.routes:
            if hasattr(r, 'path'):
                code_routes.add(r.path)
            elif isinstance(r, dict):
                code_routes.add(r.get('path', ''))
        
        for route in prd_routes:
            if route not in code_routes:
                # fuzzy match
                best_route = None
                best_score = 0
                for cr in code_routes:
                    score = _fuzzy_score(route.lower(), cr.lower())
                    if score > best_score:
                        best_score = score
                        best_route = cr
                if best_score < 0.5:
                    checks.append({
                        'check': 'route_missing',
                        'severity': 'warn',
                        'route': route,
                        'message': f"PRD 提到的路由 '{route}' 在代码中未找到",
                    })
        
        # 3. 性能风险预检：PRD 提到高并发/大批量但代码中没有缓存
        perf_keywords = ['高并发', '大量', '批量', 'QPS', 'performance', 'throughput']
        has_perf_req = any(kw in prd_text for kw in perf_keywords)
        has_cache = any('redis' in str(s).lower() or 'cache' in str(s).lower() for s in code_entities)
        if has_perf_req and not has_cache:
            checks.append({
                'check': 'performance_risk',
                'severity': 'high',
                'message': "PRD 提到性能相关需求但代码中未发现缓存策略",
            })
        
        # 4. API 变更影响面分析
        api_impact = self._analyze_api_impact(ir, prd_text)
        if api_impact:
            checks.extend(api_impact)
        
        # 5. 跨仓库依赖分析（多仓库场景）
        cross_repo_checks = self._analyze_cross_repo_deps(ir, prd_text)
        if cross_repo_checks:
            checks.extend(cross_repo_checks)
        
        return checks
    
    def _analyze_cross_repo_deps(self, ir: IRDocument, prd_text: str) -> List[Dict]:
        """跨仓库依赖分析 — 检测 PRD 对多仓库架构的影响
        
        检查项：
        1. PRD 涉及的服务是否在多个仓库中存在
        2. 跨仓库调用链的风险（RPC/MQ/HTTP）
        3. 共享实体（struct/table）的变更传播
        4. 服务拓扑中的单点故障
        """
        checks = []
        
        # 1. 检测 PRD 是否涉及多服务/多仓库
        multi_service_keywords = ['跨服务', '跨仓库', '微服务', 'rpc', 'grpc', 
                                   'service-to-service', '分布式', 'dubbo', 'feign']
        has_cross_service = any(kw in prd_text.lower() for kw in multi_service_keywords)
        
        # 2. 检测外部服务调用
        external_service_keywords = ['调用', '依赖', '对接', '集成', 'consumer', 'producer',
                                      '消息队列', 'mq', 'kafka', 'rabbitmq', 'redis']
        has_external_deps = any(kw in prd_text for kw in external_service_keywords)
        
        # 3. 如果有跨服务/外部依赖，检查代码中是否有对应的服务定义
        if has_cross_service or has_external_deps:
            # 检查 services 字段
            services = getattr(ir, 'services', [])
            if services:
                service_names = []
                for svc in services:
                    if isinstance(svc, dict):
                        name = svc.get('name', svc.get('service_name', ''))
                    else:
                        name = getattr(svc, 'name', getattr(svc, 'service_name', ''))
                    if name:
                        service_names.append(name)
                
                if len(service_names) > 1:
                    checks.append({
                        'rule': 'multi_service_detected',
                        'severity': 'info',
                        'description': f'代码库检测到 {len(service_names)} 个服务: {", ".join(service_names[:5])}',
                        'suggestion': '多服务架构需要注意：1) 服务间契约版本管理 2) 跨服务事务一致性 3) 降级策略',
                    })
            
            # 检查 call_graph 中的跨服务调用
            call_graph = getattr(ir, 'call_graph', [])
            if call_graph:
                # 检测是否有跨包/跨服务的调用
                cross_package_calls = 0
                for edge in call_graph:
                    if isinstance(edge, dict):
                        caller_pkg = edge.get('caller', '')
                        callee_pkg = edge.get('callee', '')
                        # 如果 caller 和 callee 在不同 package，视为跨包调用
                        if caller_pkg and callee_pkg:
                            caller_base = caller_pkg.split('/')[0] if '/' in caller_pkg else caller_pkg
                            callee_base = callee_pkg.split('/')[0] if '/' in callee_pkg else callee_pkg
                            if caller_base != callee_base:
                                cross_package_calls += 1
                
                if cross_package_calls > 10:
                    checks.append({
                        'rule': 'high_cross_package_coupling',
                        'severity': 'warn',
                        'description': f'检测到 {cross_package_calls} 个跨包调用，耦合度较高',
                        'suggestion': '建议：1) 引入接口抽象层 2) 使用依赖注入 3) 限制跨包直接调用',
                    })
        
        # 4. 检测共享实体变更风险
        shared_entity_keywords = ['公共', '共享', 'common', 'shared', 'base', '基类', '父类']
        has_shared_entity = any(kw in prd_text for kw in shared_entity_keywords)
        
        if has_shared_entity:
            # 检查是否有 common/shared 包
            has_common_pkg = False
            for pkg in getattr(ir, 'packages', {}):
                pkg_str = str(pkg).lower()
                if any(kw in pkg_str for kw in ['common', 'shared', 'base', 'internal']):
                    has_common_pkg = True
                    break
            
            if has_common_pkg:
                checks.append({
                    'rule': 'shared_entity_change_risk',
                    'severity': 'high',
                    'description': 'PRD 涉及共享实体变更，可能影响所有下游服务',
                    'suggestion': '共享实体变更需要：1) 向后兼容 2) 通知所有调用方 3) 灰度发布 4) 版本管理',
                })
        
        return checks
    
    def _validate_business_rules(self, ir: IRDocument, prd_text: str, profile: dict) -> List[Dict]:
        """自动化业务规则校验 — 从 profile 读取规则，预检 PRD 合规性
        
        检查项：
        1. 错误码校验：PRD 提到的错误场景是否有对应错误码
        2. 权限校验：PRD 提到的操作是否有鉴权
        3. 数据模型校验：PRD 字段是否在现有 struct 中有对应
        4. 状态机校验：PRD 流程是否符合状态机定义
        5. 外部依赖校验：PRD 调用的外部服务是否在代码中存在
        6. Profile business_rules 约束冲突检测
        7. Profile service_topology 服务依赖验证
        8. 模块职责边界检查（基于 profile.modules）
        
        Returns:
            List of [{rule, severity, description, suggestion}]
        """
        checks = []
        profile_data = profile.get('profile', {}) if isinstance(profile, dict) else profile
        
        # 0. Profile business_rules 约束冲突检测
        checks.extend(self._check_business_rule_constraints(ir, prd_text, profile_data))
        
        # 1. 错误码覆盖检查
        existing_error_codes = set()
        for ec in getattr(ir, 'error_codes', []):
            if hasattr(ec, 'name'):
                existing_error_codes.add(ec.name.lower())
            elif isinstance(ec, dict):
                existing_error_codes.add(ec.get('name', '').lower())
        
        # 从 PRD 提取错误场景关键词
        error_keywords = ['失败', '错误', '异常', '超时', '拒绝', 'denied', 'error', 'fail', 
                         'timeout', '403', '404', '500', '限制', '限流', 'rate limit']
        prd_error_scenes = [kw for kw in error_keywords if kw in prd_text]
        
        if prd_error_scenes and not existing_error_codes:
            checks.append({
                'rule': 'error_code_coverage',
                'severity': 'high',
                'description': f"PRD 提到了 {len(prd_error_scenes)} 个错误场景，但代码库中未发现错误码定义",
                'suggestion': '需要在 error_code.go 或类似文件中定义对应错误码',
            })
        
        # 2. 鉴权检查
        auth_models = getattr(ir, 'auth_models', [])
        has_auth = len(auth_models) > 0
        
        auth_keywords = ['鉴权', '权限', 'auth', 'permission', 'token', '登录', '认证']
        prd_has_auth = any(kw in prd_text for kw in auth_keywords)
        
        if prd_has_auth and not has_auth:
            checks.append({
                'rule': 'auth_missing',
                'severity': 'high',
                'description': 'PRD 涉及权限相关操作，但代码库中未发现鉴权中间件',
                'suggestion': '确认是否使用现有鉴权体系，或需要新增鉴权逻辑',
            })
        
        # 3. 数据模型校验
        existing_structs = set()
        for s in getattr(ir, 'structs', []):
            if hasattr(s, 'name'):
                existing_structs.add(s.name.lower())
            elif isinstance(s, dict):
                existing_structs.add(s.get('name', '').lower())
        
        # 从 PRD 提取可能的 struct 名
        prd_struct_candidates = re.findall(r'[A-Z][a-z]+(?:[A-Z][a-z]+)*', prd_text)
        missing_structs = [s for s in prd_struct_candidates if s.lower() not in existing_structs]
        
        # 过滤掉常见非业务 struct（如 Request, Response, Context 等）
        skip_structs = {'request', 'response', 'context', 'option', 'config', 'params', 'input', 'output'}
        missing_structs = [s for s in missing_structs if s.lower() not in skip_structs]
        
        if missing_structs[:5]:  # 最多报告 5 个
            checks.append({
                'rule': 'struct_missing',
                'severity': 'medium',
                'description': f"PRD 可能涉及以下未在代码中发现的 struct: {', '.join(missing_structs[:5])}",
                'suggestion': '确认是否需要新建 struct，或使用现有 struct',
            })
        
        # 4. 状态机校验
        state_machines = profile_data.get('state_machines', {})
        if state_machines:
            # 从 PRD 提取状态转换关键词
            state_keywords = ['状态', 'status', 'transition', '流转', '审批', '审核', '发布']
            prd_has_state = any(kw in prd_text for kw in state_keywords)
            
            if prd_has_state:
                for entity, sm in state_machines.items():
                    allowed_transitions = []
                    if isinstance(sm, dict):
                        for field, details in sm.get('Status', {}).items():
                            if isinstance(details, dict) and 'transitions' in details:
                                allowed_transitions.extend(details['transitions'])
                    
                    if not allowed_transitions:
                        checks.append({
                            'rule': 'state_machine_no_transitions',
                            'severity': 'low',
                            'description': f"状态机 `{entity}` 未定义转换规则，无法校验 PRD 流程",
                            'suggestion': '在 profile 中补充 state_machines 的 transitions 定义',
                        })
        
        # 5. 外部依赖校验
        existing_imports = set()
        for imp in getattr(ir, 'imports', []):
            if hasattr(imp, 'module'):
                existing_imports.add(imp.module.lower())
            elif isinstance(imp, dict):
                existing_imports.add(imp.get('module', '').lower())
        
        # 从 PRD 提取可能的 RPC/HTTP 依赖
        rpc_keywords = ['RPC', 'gRPC', 'HTTP', 'API', '服务调用', '微服务', 'dubbo', 'thrift']
        prd_rpc_refs = [kw for kw in rpc_keywords if kw in prd_text]
        
        if prd_rpc_refs:
            # 检查是否引用了已知的 RPC 包
            known_rpc_pkgs = [pkg for pkg in existing_imports if any(k in pkg for k in ['rpc', 'grpc', 'pb', 'proto'])]
            if not known_rpc_pkgs:
                checks.append({
                    'rule': 'rpc_dependency_unknown',
                    'severity': 'medium',
                    'description': f"PRD 提到了 {len(prd_rpc_refs)} 个外部依赖场景，但未发现 RPC/gRPC 包引用",
                    'suggestion': '确认外部服务是否已注册为依赖，或需要新增 RPC 客户端',
                })
        
        # 6. 兼容性检查
        checks.extend(self._check_compatibility(ir, prd_text, profile_data))
        
        # 7. 性能风险评估
        checks.extend(self._assess_performance_risk(ir, prd_text, profile_data))
        
        # 8. 核心流程校验
        checks.extend(self._validate_core_flows(ir, prd_text))
        
        # 9. 安全漏洞检测
        checks.extend(self._detect_security_risks(ir, prd_text))
        
        # 10. 可观测性检查
        checks.extend(self._check_observability(ir, prd_text))
        
        # 11. 模块职责边界检查
        checks.extend(self._check_module_boundaries(ir, prd_text, profile_data))
        
        # 12. Schema 迁移风险检查
        checks.extend(self._check_schema_migration_risk(ir, prd_text))
        
        # 13. 分布式锁检查
        checks.extend(self._check_distributed_lock_risk(ir, prd_text))
        
        # 14. 数据一致性校验（事务/ACID）
        checks.extend(self._check_data_consistency(ir, prd_text))
        
        # 15. 数据保留与合规检查
        checks.extend(self._check_data_retention_compliance(ir, prd_text))
        
        # 16. 灰度发布与回滚检查
        checks.extend(self._check_gradual_release_strategy(ir, prd_text))
        
        return checks
    
    def _check_business_rule_constraints(self, ir: IRDocument, prd_text: str, profile_data: dict) -> List[Dict]:
        """检查 PRD 是否违反 profile 中定义的 business_rules 约束。
        
        从 profile.business_rules 读取规则分类和约束条件，
        检查 PRD 需求是否与已有规则冲突。
        """
        checks = []
        business_rules = profile_data.get('business_rules', {})
        if not business_rules:
            return checks
        
        # 检查 PRD 是否要求与现有错误码规则冲突的操作
        for category, rules in business_rules.items():
            if not isinstance(rules, list):
                continue
            
            # 检查是否提到被禁止的错误处理方式
            forbidden_patterns = {
                'database_errors': ['直接抛异常', 'panic', '不处理 DB 错误', '忽略数据库错误'],
                'redis_errors': ['不处理 Redis 失败', 'Redis 失败不影响主流程'],
                'http_errors': ['不处理 HTTP 请求失败', '忽略网络错误'],
            }
            
            for pattern_list in forbidden_patterns.values():
                for pattern in pattern_list:
                    if pattern in prd_text:
                        checks.append({
                            'rule': f'forbidden_{category}',
                            'severity': 'high',
                            'description': f"PRD 描述 '{pattern}' 违反 {category} 中的错误处理规范",
                            'suggestion': f'参考 {category} 中的错误码定义，使用标准错误处理方式',
                        })
        
        return checks
    
    def _check_module_boundaries(self, ir: IRDocument, prd_text: str, profile_data: dict) -> List[Dict]:
        """检查 PRD 需求是否跨模块职责边界。
        
        从 profile.modules 读取各模块的职责描述和关键词，
        判断 PRD 需求是否应该属于某个模块，或者是否需要跨模块协调。
        """
        checks = []
        modules = profile_data.get('modules', [])
        if not modules:
            return checks
        
        # 检查 PRD 中提到的功能是否属于现有模块
        prd_lower = prd_text.lower()
        unassigned_features = []
        
        for module in modules:
            if not isinstance(module, dict):
                continue
            keywords = module.get('keywords', [])
            module_name = module.get('name', '')
            
            # 如果 PRD 中提到该模块的关键词，说明属于该模块
            matched = any(kw.lower() in prd_lower for kw in keywords)
            if matched:
                # 记录哪些模块被匹配到
                pass
            else:
                # 检查 PRD 中是否有新模块关键词
                pass
        
        # 检查是否存在跨模块依赖风险
        cross_module_deps = []
        for module in modules:
            if not isinstance(module, dict):
                continue
            name = module.get('name', '')
            goal = module.get('goal', '').lower()
            if goal and goal in prd_lower:
                cross_module_deps.append(name)
        
        if len(cross_module_deps) >= 2:
            checks.append({
                'rule': 'cross_module_dependency',
                'severity': 'medium',
                'description': f"PRD 涉及多个模块: {', '.join(cross_module_deps[:3])}",
                'suggestion': '需要评估跨模块协调方案，考虑引入事件驱动或 API 网关解耦',
            })
        
        return checks
    
    def _check_schema_migration_risk(self, ir: IRDocument, prd_text: str) -> List[Dict]:
        """Schema 迁移风险检查 — 检测数据库变更的潜在风险。
        
        检查项：
        1. PRD 要求新增/修改表但未发现 migration 工具
        2. 大表 DDL 变更（无 online DDL）
        3. 字段类型变更导致的数据不兼容
        4. 缺少 backfill 策略
        """
        checks = []
        
        # 检测 PRD 中的 schema 变更需求
        schema_keywords = ['新增表', '修改表', 'ALTER TABLE', 'DROP TABLE', '新增字段', 
                          '删除字段', '修改字段', 'type change', 'schema change', 
                          '数据迁移', 'backfill', 'online ddl', 'gorethink']
        has_schema_change = any(kw in prd_text for kw in schema_keywords)
        
        if not has_schema_change:
            return checks
        
        # 检查是否有 migration 工具
        has_migration_tool = any(
            'migration' in str(i).lower() or 'migrate' in str(i).lower() or
            'golang-migrate' in str(i).lower() or 'goose' in str(i).lower() or
            'flyway' in str(i).lower() or 'liquibase' in str(i).lower()
            for i in getattr(ir, 'imports', [])
        )
        
        # 检查是否有 migration 脚本目录
        has_migration_dir = False
        for func in getattr(ir, 'functions', []):
            fname = func.get('name', '') if isinstance(func, dict) else getattr(func, 'name', '')
            if 'migration' in str(fname).lower() or 'migrate' in str(fname).lower():
                has_migration_dir = True
                break
        
        if not (has_migration_tool or has_migration_dir):
            checks.append({
                'rule': 'no_migration_tool',
                'severity': 'high',
                'description': 'PRD 涉及 Schema 变更但代码库未发现 migration 工具/脚本',
                'suggestion': '建议引入 golang-migrate/goose，所有 DDL 变更必须通过 migration 脚本管理',
            })
        
        # 检查是否提到大表操作
        big_table_keywords = ['大表', '百万行', '千万行', '亿级', 'millions of rows', 'large table']
        has_big_table = any(kw in prd_text for kw in big_table_keywords)
        
        if has_big_table:
            # 检查是否有 online DDL 意识
            has_online_ddl = 'online' in prd_text.lower() and ('ddl' in prd_text.lower() or 'schema' in prd_text.lower())
            if not has_online_ddl:
                checks.append({
                    'rule': 'big_table_no_online_ddl',
                    'severity': 'critical',
                    'description': 'PRD 涉及大表变更但未提及 online DDL 方案',
                    'suggestion': '大表 DDL 必须使用 online 模式（如 pt-online-schema-change），避免锁表',
                })
            
            # 检查是否有 backfill 策略
            has_backfill = 'backfill' in prd_text.lower() or '回填' in prd_text or '历史数据' in prd_text
            if not has_backfill:
                checks.append({
                    'rule': 'no_backfill_strategy',
                    'severity': 'high',
                    'description': '大表变更需要数据回填但未发现相关策略',
                    'suggestion': '新增字段需要 backfill 策略，考虑分批处理 + 进度追踪 + 失败重试',
                })
        
        return checks
    
    def _check_distributed_lock_risk(self, ir: IRDocument, prd_text: str) -> List[Dict]:
        """分布式锁检查 — 检测并发场景下的锁需求。
        
        检查项：
        1. PRD 涉及并发操作但未使用分布式锁
        2. Redis lock 实现缺失
        3. 锁超时/死锁风险
        4. 锁粒度问题（全局锁 vs 细粒度锁）
        """
        checks = []
        
        # 检测 PRD 中的并发场景
        concurrency_keywords = ['并发', '同时', '竞争条件', 'race condition', 'lock', 
                               '分布式锁', 'redis lock', 'mutex', 'semaphore',
                               '竞态', '超卖', '库存扣减', '余额扣减']
        has_concurrency_req = any(kw in prd_text for kw in concurrency_keywords)
        
        if not has_concurrency_req:
            return checks
        
        # 检查是否有分布式锁实现
        has_lock_impl = any(
            'lock' in str(f).lower() or 'mutex' in str(f).lower() or
            'semaphore' in str(f).lower() or 'setnx' in str(f).lower() or
            'redlock' in str(f).lower() or 'distributed_lock' in str(f).lower()
            for f in getattr(ir, 'functions', [])
        )
        
        # 检查是否有 Redis 依赖
        has_redis = any(
            'redis' in str(i).lower() or 'go-redis' in str(i).lower() or
            'github.com/redis' in str(i).lower()
            for i in getattr(ir, 'imports', [])
        )
        
        if has_concurrency_req and not has_lock_impl:
            checks.append({
                'rule': 'concurrency_no_lock',
                'severity': 'critical',
                'description': 'PRD 涉及并发操作但代码中未发现分布式锁实现',
                'suggestion': '并发场景必须使用分布式锁（Redis SETNX/RedLock）或数据库唯一约束保证一致性',
            })
        
        if has_concurrency_req and not has_redis:
            checks.append({
                'rule': 'concurrency_no_redis',
                'severity': 'high',
                'description': 'PRD 涉及并发操作但代码中未发现 Redis 依赖',
                'suggestion': '分布式锁通常基于 Redis 实现，需确认 Redis 服务可用性',
            })
        
        # 检查锁超时配置
        timeout_keywords = ['超时', 'timeout', 'TTL', '过期时间', 'expire']
        has_timeout_mentioned = any(kw in prd_text for kw in timeout_keywords)
        if has_concurrency_req and not has_timeout_mentioned:
            checks.append({
                'rule': 'lock_no_timeout',
                'severity': 'medium',
                'description': '并发场景涉及锁但未提及超时设置',
                'suggestion': '分布式锁必须设置合理的 TTL（建议 5-30s），防止死锁',
            })
        
        return checks
    
    def _check_data_consistency(self, ir: IRDocument, prd_text: str) -> List[Dict]:
        """数据一致性校验 — 检测事务/ACID 相关需求。
        
        检查项：
        1. PRD 涉及多步操作但未使用事务
        2. 跨表/跨服务数据一致性
        3. 最终一致性 vs 强一致性选择
        4. 补偿机制/重试策略
        """
        checks = []
        
        # 检测 PRD 中的数据一致性需求
        consistency_keywords = ['事务', 'transaction', 'ACID', '一致性', 'rollback',
                               '回滚', '补偿', 'Saga', '两阶段提交', '2PC',
                               '最终一致', '强一致', '数据同步', '双写',
                               '写入', '更新', '删除', '创建', 'multi-step']
        has_consistency_req = any(kw in prd_text for kw in consistency_keywords)
        
        if not has_consistency_req:
            return checks
        
        # 检查是否有事务实现
        has_tx_impl = any(
            'tx' in str(f).lower() or 'transaction' in str(f).lower() or
            'BeginTx' in str(f) or 'Commit' in str(f) or 'Rollback' in str(f)
            for f in getattr(ir, 'functions', [])
        )
        
        if has_consistency_req and not has_tx_impl:
            checks.append({
                'rule': 'no_transaction_impl',
                'severity': 'high',
                'description': 'PRD 涉及数据一致性但代码中未发现事务实现',
                'suggestion': '多步写操作必须使用事务（BEGIN/COMMIT/ROLLBACK）保证 ACID',
            })
        
        # 检查跨服务一致性
        cross_service_keywords = ['跨服务', '微服务', 'distributed', 'RPC', 'gRPC',
                                 '多系统', '跨系统', '同步', '异步消息']
        has_cross_service = any(kw in prd_text for kw in cross_service_keywords)
        
        if has_cross_service:
            has_mq = any(
                'kafka' in str(i).lower() or 'rabbitmq' in str(i).lower() or
                'amqp' in str(i).lower() or 'mq' in str(i).lower()
                for i in getattr(ir, 'imports', [])
            )
            if not has_mq:
                checks.append({
                    'rule': 'cross_service_no_mq',
                    'severity': 'medium',
                    'description': '跨服务场景未使用消息队列进行异步解耦',
                    'suggestion': '跨服务一致性建议使用 MQ（Kafka/RabbitMQ）+ 补偿机制实现最终一致性',
                })
            
            # 检查是否有补偿机制
            has_compensation = '补偿' in prd_text or 'retry' in prd_text.lower() or 'circuit' in prd_text.lower()
            if not has_compensation:
                checks.append({
                    'rule': 'no_compensation_mechanism',
                    'severity': 'high',
                    'description': '跨服务场景缺少补偿/重试机制',
                    'suggestion': '分布式事务需要补偿机制（Saga/TCC）和重试策略保证最终一致性',
                })
        
        return checks
    
    def _check_data_retention_compliance(self, ir: IRDocument, prd_text: str) -> List[Dict]:
        """数据保留与合规检查 — GDPR/PIPL 数据隐私合规
        
        检查项：
        1. PRD 涉及个人数据处理但未发现脱敏/加密实现
        2. 数据保留期限未定义
        3. 用户数据删除/导出权利未实现
        4. 跨境数据传输未声明
        """
        checks = []
        
        # 检测个人数据处理
        pdp_keywords = ['个人信息', 'personal data', '用户数据', '用户信息', 
                       '隐私', 'privacy', 'GDPR', 'PIPL', '数据出境', 
                       '数据删除', '数据导出', '用户同意', 'consent',
                       'cookie', 'tracking', '画像', 'profile', '用户行为']
        has_pdp = any(kw in prd_text for kw in pdp_keywords)
        
        if not has_pdp:
            return checks
        
        # 检查是否有数据脱敏实现
        has_masking = any(
            'mask' in str(f).lower() or 'desensit' in str(f).lower() or
            'anonym' in str(f).lower() or 'pseudonym' in str(f).lower()
            for f in getattr(ir, 'functions', [])
        )
        
        # 检查是否有数据删除实现
        has_deletion = any(
            'delete' in str(f).lower() or 'remove' in str(f).lower() or
            'soft_delete' in str(f).lower() or 'hard_delete' in str(f).lower()
            for f in getattr(ir, 'functions', [])
        )
        
        if has_pdp and not has_masking:
            checks.append({
                'rule': 'pdp_no_masking',
                'severity': 'high',
                'description': 'PRD 涉及个人数据处理但代码中未发现数据脱敏实现',
                'suggestion': '个人敏感数据（手机号/身份证/邮箱）必须脱敏展示，日志中不得明文存储',
            })
        
        if has_pdp and not has_deletion:
            checks.append({
                'rule': 'pdp_no_deletion',
                'severity': 'medium',
                'description': 'PRD 涉及个人数据但未发现数据删除实现',
                'suggestion': '需要实现用户数据删除/导出接口，满足 GDPR/PIPL 合规要求',
            })
        
        # 检查数据保留期限
        retention_keywords = ['保留', 'retention', '过期', 'expire', '清理', 'cleanup', '归档', 'archive']
        has_retention = any(kw in prd_text for kw in retention_keywords)
        if has_pdp and not has_retention:
            checks.append({
                'rule': 'no_data_retention_policy',
                'severity': 'medium',
                'description': 'PRD 涉及个人数据但未定义数据保留期限',
                'suggestion': '需要明确数据保留策略（如：用户数据保留 2 年，日志保留 6 个月）',
            })
        
        return checks
    
    def _check_gradual_release_strategy(self, ir: IRDocument, prd_text: str) -> List[Dict]:
        """灰度发布与回滚检查 — 变更风险控制
        
        检查项：
        1. PRD 涉及核心功能变更但未提灰度发布
        2. 回滚方案缺失
        3. Feature Flag 策略缺失
        """
        checks = []
        
        # 检测高风险变更
        high_risk_keywords = ['核心', '核心功能', '主流程', 'main flow', 
                             '重大变更', 'breaking change', '重构', 'refactor',
                             '架构调整', '架构升级', '大规模', 'massive change']
        has_high_risk = any(kw in prd_text for kw in high_risk_keywords)
        
        if not has_high_risk:
            return checks
        
        # 检查是否有 feature flag 实现
        has_feature_flag = any(
            'feature' in str(f).lower() and 'flag' in str(f).lower() or
            'toggle' in str(f).lower() or '开关' in str(f).lower() or
            'enable_' in str(f).lower() or 'disable_' in str(f).lower()
            for f in getattr(ir, 'functions', [])
        )
        
        # 检查是否有灰度/金丝雀发布相关
        gradual_keywords = ['gradual', '灰度', 'canary', '金丝雀', 'rollout', '回滚', 'rollback']
        has_gradual = any(kw in prd_text.lower() for kw in gradual_keywords)
        
        if has_high_risk and not has_gradual:
            checks.append({
                'rule': 'no_gradual_release',
                'severity': 'high',
                'description': 'PRD 涉及高风险变更但未提及灰度发布或回滚方案',
                'suggestion': '高风险变更必须：1) 使用 Feature Flag 控制 2) 灰度发布（1% → 10% → 50% → 100%）3) 准备回滚方案',
            })
        
        if has_high_risk and not has_feature_flag:
            checks.append({
                'rule': 'no_feature_flag',
                'severity': 'medium',
                'description': '高风险变更未使用 Feature Flag 控制',
                'suggestion': '建议引入 Feature Flag 系统（如 LaunchDarkly/自建），支持运行时开关功能',
            })
        
        return checks
    
    def _check_compatibility(self, ir: IRDocument, prd_text: str, profile_data: dict) -> List[Dict]:
        """兼容性检查 — 新旧接口兼容、数据迁移风险"""
        checks = []
        
        # 检查 PRD 是否修改了现有接口
        existing_routes = set()
        for r in getattr(ir, 'routes', []):
            if hasattr(r, 'path'):
                existing_routes.add(r.path)
            elif isinstance(r, dict):
                existing_routes.add(r.get('path', ''))
        
        # 从 PRD 提取可能的路由修改
        prd_routes = re.findall(r'/api/\w+/\w+', prd_text)
        prd_routes.extend(re.findall(r'/v\d+/\w+', prd_text))
        
        modified_routes = [r for r in prd_routes if r in existing_routes]
        if modified_routes:
            checks.append({
                'rule': 'existing_api_modification',
                'severity': 'high',
                'description': f"PRD 涉及修改 {len(modified_routes)} 个现有接口: {', '.join(modified_routes[:5])}",
                'suggestion': '需要评估修改对上游的影响，考虑 API versioning 或兼容变更策略',
            })
        
        # 检查是否有版本管理
        has_versioning = any('v1' in str(r) or 'v2' in str(r) or 'version' in str(r).lower() for r in existing_routes)
        if modified_routes and not has_versioning:
            checks.append({
                'rule': 'no_api_versioning',
                'severity': 'medium',
                'description': '修改现有接口但未发现 API versioning 策略',
                'suggestion': '建议引入 API versioning（如 /api/v1/, /api/v2/）',
            })
        
        # 检查数据库变更
        db_change_keywords = ['新增表', '修改表', 'ALTER', 'DROP', '迁移', 'migration', 'schema change']
        has_db_changes = any(kw in prd_text for kw in db_change_keywords)
        
        if has_db_changes:
            has_migration = any('migration' in str(i).lower() or 'migrate' in str(i).lower() 
                              for i in getattr(ir, 'imports', []))
            if not has_migration:
                checks.append({
                    'rule': 'db_migration_risk',
                    'severity': 'high',
                    'description': 'PRD 涉及数据库变更但未发现迁移脚本',
                    'suggestion': '需要编写数据迁移脚本，考虑滚动部署和双向兼容',
                })
        
        # 检查配置变更
        config_keywords = ['配置', 'config', 'apollo', 'nacos', 'etcd', '环境变量', 'env']
        has_config_changes = any(kw in prd_text for kw in config_keywords)
        if has_config_changes:
            checks.append({
                'rule': 'config_change_risk',
                'severity': 'medium',
                'description': 'PRD 涉及配置变更',
                'suggestion': '配置变更需要灰度发布，设置默认值保证向后兼容',
            })
        
        # 新增：幂等性检查
        idempotency_keywords = ['幂等', 'idempotent', '重复提交', '多次', 'retry', '重试']
        has_idempotency_req = any(kw in prd_text for kw in idempotency_keywords)
        if has_idempotency_req:
            # 检查代码中是否有幂等性实现
            has_idempotency_impl = any(
                'idempotent' in str(f).lower() or 'lock' in str(f).lower() or 
                'unique' in str(f).lower()
                for f in getattr(ir, 'functions', [])
            )
            if not has_idempotency_impl:
                checks.append({
                    'rule': 'idempotency_missing',
                    'severity': 'high',
                    'description': 'PRD 涉及幂等性需求但代码中未发现幂等性实现',
                    'suggestion': '建议使用分布式锁（Redis SETNX）或唯一索引保证幂等性',
                })
        
        # 新增：审计日志检查
        audit_keywords = ['审计', 'audit', '日志', 'log', '操作记录', 'trace']
        has_audit_req = any(kw in prd_text for kw in audit_keywords)
        if has_audit_req:
            has_audit_impl = any(
                'audit' in str(f).lower() or 'log' in str(f).lower() or 
                'trace' in str(f).lower()
                for f in getattr(ir, 'functions', [])
            )
            if not has_audit_impl:
                checks.append({
                    'rule': 'audit_missing',
                    'severity': 'medium',
                    'description': 'PRD 涉及审计/日志需求但代码中未发现审计实现',
                    'suggestion': '建议新增审计日志中间件，记录关键操作的 user/action/time/ip',
                })
        
        # 新增：限流检查
        rate_limit_keywords = ['限流', 'rate limit', 'throttle', 'qps 限制', '流量控制']
        has_rate_limit_req = any(kw in prd_text for kw in rate_limit_keywords)
        if has_rate_limit_req:
            has_rate_limit_impl = any(
                'rate' in str(f).lower() or 'limit' in str(f).lower() or
                'throttl' in str(f).lower()
                for f in getattr(ir, 'functions', [])
            )
            if not has_rate_limit_impl:
                checks.append({
                    'rule': 'rate_limit_missing',
                    'severity': 'high',
                    'description': 'PRD 涉及限流需求但代码中未发现限流实现',
                    'suggestion': '建议使用 Redis + Lua 或令牌桶算法实现限流',
                })
        
        # ── 增强：API Versioning 策略检查 ──────────────────────────
        # 检测 PRD 是否要求破坏性变更（Breaking Change）
        breaking_keywords = ['删除字段', '修改字段类型', '重命名接口', '改变请求结构', 
                             'breaking change', 'remove field', 'rename endpoint',
                             '改变响应格式', '不兼容变更']
        has_breaking_change = any(kw in prd_text for kw in breaking_keywords)
        
        if has_breaking_change:
            # 检查是否有 deprecation header / 废弃标记
            has_deprecation = any(
                'deprecat' in str(f).lower() or 'deprecated' in str(r).lower() or
                'X-Deprecated' in str(r).lower() or 'Deprecation-Until' in str(r).lower()
                for r in getattr(ir, 'routes', [])
                for f in getattr(ir, 'functions', [])
            )
            if not has_deprecation:
                checks.append({
                    'rule': 'no_deprecation_strategy',
                    'severity': 'critical',
                    'description': 'PRD 涉及破坏性变更但未发现废弃策略',
                    'suggestion': '破坏性变更必须：1) 添加 X-Deprecated header 2) 保留旧接口 N 个版本 3) 提供迁移指南 4) 通知所有调用方',
                })
            
            # 检查是否有新旧接口共存方案
            has_dual_api = any('v1' in str(r) and 'v2' in str(r) for r in existing_routes)
            if not has_dual_api:
                checks.append({
                    'rule': 'no_dual_api_strategy',
                    'severity': 'high',
                    'description': '破坏性变更需要新旧接口共存，但未发现多版本路由',
                    'suggestion': '建议采用 /api/v1/ (deprecated) + /api/v2/ (new) 双版本共存方案',
                })
        
        # ── 增强：前端适配成本评估 ──────────────────────────
        frontend_keywords = ['前端', 'frontend', 'H5', '小程序', 'App', 'client', '移动端', 'web']
        has_frontend = any(kw in prd_text for kw in frontend_keywords)
        
        if has_frontend and modified_routes:
            # 检测路由变更是否影响前端
            path_change_keywords = ['路径调整', '路由变更', 'path change', 'endpoint rename']
            has_path_rename = any(kw in prd_text for kw in path_change_keywords)
            if has_path_rename:
                checks.append({
                    'rule': 'frontend_impact',
                    'severity': 'high',
                    'description': f'路由变更将影响 {len(frontend_keywords)} 个前端端，需要前端适配',
                    'suggestion': '需要：1) 前端适配计划 2) 灰度发布 3) 兼容性代理层 4) 前端联调时间评估',
                })
        
        # ── 增强：第三方 API 变更影响 ──────────────────────────
        third_party_keywords = ['第三方', 'external', 'third party', 'partner', '合作方', '外部系统']
        has_third_party = any(kw in prd_text for kw in third_party_keywords)
        
        if has_third_party and modified_routes:
            # 检查是否有 webhook/callback 机制
            has_webhook = any(
                'webhook' in str(f).lower() or 'callback' in str(f).lower() or
                'notify' in str(f).lower() or 'push' in str(f).lower()
                for f in getattr(ir, 'functions', [])
            )
            if not has_webhook:
                checks.append({
                    'rule': 'third_party_no_callback',
                    'severity': 'medium',
                    'description': '涉及第三方交互但未发现 webhook/callback 机制',
                    'suggestion': '第三方集成建议实现 webhook 回调机制，避免轮询开销',
                })
        
        # ── 增强：数据向后兼容检查 ──────────────────────────
        # 检测 PRD 是否要求新增可选字段 vs 必填字段
        optional_keywords = ['可选', 'optional', 'nullable', '可以为空']
        required_keywords = ['必填', 'required', 'not null', '不能为空']
        
        has_optional = any(kw in prd_text for kw in optional_keywords)
        has_required = any(kw in prd_text for kw in required_keywords)
        
        if has_required and has_db_changes:
            # 检查默认值策略
            has_default = 'default' in prd_text.lower() or '默认值' in prd_text or 'DEFAULT' in prd_text
            if not has_default:
                checks.append({
                    'rule': 'no_default_for_required_field',
                    'severity': 'high',
                    'description': '新增必填字段但未指定默认值策略',
                    'suggestion': 'DDL 变更时必填字段必须有 DEFAULT 值，否则历史数据插入会失败',
                })
        
        return checks
    
    def _analyze_api_impact(self, ir: IRDocument, prd_text: str) -> List[Dict]:
        """API 变更影响面分析 — 检测 PRD 对现有 API 的影响
        
        检查项：
        1. PRD 修改的路由对哪些 handler/service 有连锁影响
        2. 修改的 struct 字段对 Request/Response 的影响
        3. 新增/删除的接口对上游调用方的影响
        4. 路由路径变更对前端/客户端的影响
        """
        checks = []
        
        # 1. 检测路由变更
        prd_route_changes = []
        # 检测"新增/修改/删除 XX 接口"模式
        route_patterns = [
            r'(?:新增|修改|删除|调整|重构)\s*(?:接口|API|路由|endpoint)',
            r'/api/\w+',
            r'/v\d+/\w+',
        ]
        for pattern in route_patterns:
            matches = re.findall(pattern, prd_text)
            prd_route_changes.extend(matches)
        
        # 2. 检测 struct 变更
        struct_change_keywords = ['新增字段', '删除字段', '修改字段', '字段类型', 
                                  'struct', 'request', 'response', 'payload']
        has_struct_change = any(kw in prd_text for kw in struct_change_keywords)
        
        # 3. 检测 handler/service 变更
        handler_keywords = ['handler', 'service', 'dao', 'repository', '中间件', 'middleware']
        has_component_change = any(kw in prd_text for kw in handler_keywords)
        
        # 综合判断：如果 PRD 涉及接口/路由/字段变更，做影响面分析
        if prd_route_changes or has_struct_change or has_component_change:
            # 收集受影响的路由
            affected_routes = []
            for route in getattr(ir, 'routes', []):
                route_path = getattr(route, 'path', '') if hasattr(route, 'path') else route.get('path', '')
                handler = getattr(route, 'handler', '') if hasattr(route, 'handler') else route.get('handler', '')
                if route_path and (has_struct_change or has_component_change):
                    affected_routes.append({'path': route_path, 'handler': handler})
            
            if affected_routes and len(affected_routes) > 5:
                # 如果 struct 变更，可能影响大量路由
                checks.append({
                    'rule': 'wide_api_impact',
                    'severity': 'high',
                    'description': f"PRD 涉及的变更可能影响 {len(affected_routes)} 个现有路由",
                    'suggestion': '需要逐个检查受影响路由的 Request/Response 结构，确保兼容变更',
                    'affected_count': len(affected_routes),
                })
            
            # 检测路由路径变更风险
            path_change_keywords = ['路由变更', '路径调整', 'path change', 'rename route', 'deprecate']
            has_path_change = any(kw in prd_text for kw in path_change_keywords)
            if has_path_change:
                checks.append({
                    'rule': 'route_path_change',
                    'severity': 'critical',
                    'description': 'PRD 涉及路由路径变更，影响范围大',
                    'suggestion': '路由变更是破坏性变更，需要考虑：1) 旧路由兼容期 2) 前端适配成本 3) 第三方调用方通知',
                })
            
            # 检测接口删除风险
            delete_keywords = ['删除接口', '废弃', 'deprecated', '下线', '移除']
            has_delete = any(kw in prd_text for kw in delete_keywords)
            if has_delete:
                checks.append({
                    'rule': 'api_deprecation_risk',
                    'severity': 'high',
                    'description': 'PRD 涉及接口删除/废弃，需要评估影响面',
                    'suggestion': '接口废弃需要：1) 设置 deprecation header 2) 保留 2 个版本兼容期 3) 通知所有调用方',
                })
        
        # 4. 检测 DB 字段变更对 ORM 的影响
        db_field_keywords = ['新增列', '修改列', '删除列', 'NOT NULL', 'DEFAULT', 'index', '外键', 'foreign key']
        has_db_field_change = any(kw in prd_text for kw in db_field_keywords)
        if has_db_field_change:
            # 检查是否有 ORM model 定义
            has_orm = any(
                'gorm' in str(f).lower() or 'sqlx' in str(f).lower() or
                'model' in str(f).lower()
                for f in getattr(ir, 'imports', [])
            )
            if has_orm:
                checks.append({
                    'rule': 'orm_model_update_required',
                    'severity': 'medium',
                    'description': 'DB 字段变更需要同步更新 ORM model 定义',
                    'suggestion': '确保所有涉及的 struct 都添加了正确的 gorm tag，注意 migration 顺序',
                })
        
        return checks
    
    def _assess_performance_risk(self, ir: IRDocument, prd_text: str, profile_data: dict) -> List[Dict]:
        """性能风险评估"""
        checks = []
        
        # 1. 高并发场景检查
        perf_keywords = ['高并发', '大量', '批量', 'QPS', 'performance', 'throughput', 
                        '百万', '千万', '亿', 'massive', 'high concurrency']
        has_perf_req = any(kw in prd_text for kw in perf_keywords)
        
        if has_perf_req:
            has_cache = any('redis' in str(s).lower() or 'cache' in str(s).lower() 
                          for s in getattr(ir, 'structs', []))
            if not has_cache:
                checks.append({
                    'rule': 'no_cache_strategy',
                    'severity': 'high',
                    'description': 'PRD 提到性能相关需求但代码中未发现缓存策略',
                    'suggestion': '建议引入 Redis 缓存，考虑缓存穿透/击穿/雪崩防护',
                })
            
            has_async = any('async' in str(f).lower() or 'goroutine' in str(f).lower() or 
                          'mq' in str(f).lower() or 'kafka' in str(f).lower() or
                          'rabbitmq' in str(f).lower()
                          for f in getattr(ir, 'functions', []))
            if not has_async:
                checks.append({
                    'rule': 'no_async_processing',
                    'severity': 'medium',
                    'description': '高并发场景未发现有异步处理机制',
                    'suggestion': '建议引入消息队列（Kafka/RabbitMQ）进行异步解耦',
                })
        
        # 2. 大数据量检查
        big_data_keywords = ['大数据', '分页', 'page', 'pagination', '导出', 'export', '下载', 'download']
        has_big_data = any(kw in prd_text for kw in big_data_keywords)
        
        if has_big_data:
            has_pagination = any('page' in str(f).lower() or 'limit' in str(f).lower() or
                               'offset' in str(f).lower()
                               for f in getattr(ir, 'functions', []))
            if not has_pagination:
                checks.append({
                    'rule': 'no_pagination_check',
                    'severity': 'medium',
                    'description': '大数据量场景未发现有分页查询实现',
                    'suggestion': '确保所有列表接口都有分页限制，防止 OOM',
                })
        
        # 3. 外部依赖超时/重试/熔断检查
        external_dep_keywords = ['外部', 'third', 'external', 'API', 'RPC', 'gRPC', 'timeout', '超时', '重试', 'retry', '熔断', 'circuit breaker']
        has_external_deps = any(kw in prd_text for kw in external_dep_keywords)
        
        if has_external_deps:
            has_timeout_config = any('timeout' in str(c).lower() or 'Timeout' in str(c).lower()
                                    for c in getattr(ir, 'configs', []))
            if not has_timeout_config:
                checks.append({
                    'rule': 'no_timeout_config',
                    'severity': 'high',
                    'description': 'PRD 涉及外部依赖调用但未发现超时配置',
                    'suggestion': '必须设置合理的超时时间（建议 3-5s），并配置重试和熔断',
                })
        
        # 4. 数据库索引检查
        db_keywords = ['索引', 'index', 'unique', '联合索引', '复合索引']
        has_index_req = any(kw in prd_text for kw in db_keywords)
        if has_index_req:
            checks.append({
                'rule': 'index_consideration',
                'severity': 'medium',
                'description': 'PRD 涉及索引设计',
                'suggestion': '索引设计需考虑查询模式，避免过多索引影响写入性能',
            })
        
        return checks
    
    def _detect_security_risks(self, ir: IRDocument, prd_text: str) -> List[Dict]:
        """安全漏洞检测 — 从 PRD 中识别安全风险"""
        checks = []
        
        # 1. 敏感数据处理
        sensitive_keywords = ['密码', 'password', 'token', 'secret', '密钥', '加密', 
                             'encrypt', 'decrypt', '签名', 'sign', '证书', 'certificate',
                             '手机号', 'phone', '身份证', 'id_card', '邮箱', 'email',
                             '个人信息', 'PII', '隐私', 'privacy']
        has_sensitive = any(kw in prd_text for kw in sensitive_keywords)
        
        if has_sensitive:
            # 检查是否有加密/脱敏实现
            has_encryption = any(
                'encrypt' in str(f).lower() or 'hash' in str(f).lower() or
                'mask' in str(f).lower() or 'desensit' in str(f).lower() or
                'crypto' in str(f).lower()
                for f in getattr(ir, 'functions', [])
            )
            if not has_encryption:
                checks.append({
                    'rule': 'sensitive_data_no_protection',
                    'severity': 'high',
                    'description': 'PRD 涉及敏感数据处理但代码中未发现加密/脱敏实现',
                    'suggestion': '敏感数据必须加密存储（AES-256），传输中使用 TLS，展示时脱敏',
                })
        
        # 2. SQL 注入风险
        sql_keywords = ['SQL', 'sql', '拼接', '动态查询', 'raw query']
        has_sql_risk = any(kw in prd_text for kw in sql_keywords)
        if has_sql_risk:
            # 检查是否有参数化查询
            has_param_query = any(
                '?' in str(f) or '%s' in str(f) or ':param' in str(f) or
                'prepared' in str(f).lower() or 'parameterized' in str(f).lower()
                for f in getattr(ir, 'functions', [])
            )
            if not has_param_query:
                checks.append({
                    'rule': 'sql_injection_risk',
                    'severity': 'high',
                    'description': 'PRD 涉及 SQL 操作但代码中未发现参数化查询实现',
                    'suggestion': '所有 SQL 查询必须使用参数化查询，禁止字符串拼接',
                })
        
        # 3. 越权访问风险
        rbac_keywords = ['角色', 'role', '权限', 'permission', 'RBAC', 'ABAC', 'ACL']
        has_rbac = any(kw in prd_text for kw in rbac_keywords)
        if has_rbac:
            has_auth_middleware = any(
                'auth' in str(m).lower() or 'permission' in str(m).lower() or
                'rbac' in str(m).lower() or 'middleware' in str(m).lower()
                for m in getattr(ir, 'auth_models', [])
            )
            if not has_auth_middleware:
                checks.append({
                    'rule': 'rbac_without_implementation',
                    'severity': 'high',
                    'description': 'PRD 涉及角色权限但代码中未发现 RBAC 中间件实现',
                    'suggestion': '需要实现基于角色的访问控制，每个接口检查权限',
                })
        
        return checks
    
    def _check_observability(self, ir: IRDocument, prd_text: str) -> List[Dict]:
        """可观测性检查 — 日志、监控、告警"""
        checks = []
        
        # 1. 日志需求
        log_keywords = ['日志', 'log', 'logging', 'trace', 'traceId', '链路追踪']
        has_log_req = any(kw in prd_text for kw in log_keywords)
        
        if has_log_req:
            has_logger = any(
                'logger' in str(f).lower() or 'zap' in str(f).lower() or
                'slog' in str(f).lower() or 'logrus' in str(f).lower() or
                'logging' in str(f).lower()
                for f in getattr(ir, 'functions', [])
            )
            if not has_logger:
                checks.append({
                    'rule': 'logging_not_implemented',
                    'severity': 'medium',
                    'description': 'PRD 涉及日志需求但代码中未发现结构化日志实现',
                    'suggestion': '使用结构化日志（zap/logrus），包含 traceId、userId 等上下文',
                })
        
        # 2. 监控/指标
        metric_keywords = ['监控', 'metric', 'prometheus', 'grafana', 'dashboard', '告警', 'alert']
        has_metric_req = any(kw in prd_text for kw in metric_keywords)
        
        if has_metric_req:
            has_metrics = any(
                'metric' in str(f).lower() or 'prometheus' in str(f).lower() or
                'histogram' in str(f).lower() or 'counter' in str(f).lower() or
                'gauge' in str(f).lower()
                for f in getattr(ir, 'functions', [])
            )
            if not has_metrics:
                checks.append({
                    'rule': 'metrics_not_implemented',
                    'severity': 'medium',
                    'description': 'PRD 涉及监控需求但代码中未发现 Prometheus 指标实现',
                    'suggestion': '添加关键业务指标（QPS、延迟、错误率），使用 Prometheus histogram',
                })
        
        # 3. 健康检查
        health_keywords = ['健康检查', 'health check', 'liveness', 'readiness', '探针']
        has_health_req = any(kw in prd_text for kw in health_keywords)
        
        if has_health_req:
            has_health_endpoint = any(
                'health' in str(r).lower() or 'ping' in str(r).lower() or
                'ready' in str(r).lower()
                for r in getattr(ir, 'routes', [])
            )
            if not has_health_endpoint:
                checks.append({
                    'rule': 'health_check_missing',
                    'severity': 'low',
                    'description': 'PRD 涉及健康检查但代码中未发现 /health 端点',
                    'suggestion': '添加 /health (liveness) 和 /ready (readiness) 端点',
                })
        
        return checks
    
    def _validate_core_flows(self, ir: IRDocument, prd_text: str) -> List[Dict]:
        """核心流程校验 — 比对 PRD 流程与 IR 推断的 core_flows"""
        checks = []
        
        if not hasattr(ir, 'core_flows') or not ir.core_flows:
            return checks
        
        flow_keywords = ['流程', '步骤', 'step', 'workflow', 'pipeline', '阶段', 'phase']
        has_flow_desc = any(kw in prd_text for kw in flow_keywords)
        
        if not has_flow_desc:
            return checks
        
        # 从 PRD 提取可能的实体名（大写驼峰、中文业务词）
        camel_entities = re.findall(r'[A-Z][a-z]+[A-Z]\\w*', prd_text)
        chinese_entities = re.findall(r'[\\u4e00-\\u9fff]{2,6}', prd_text)
        prd_entities.update(camel_entities)
        prd_entities.update(chinese_entities)
        
        # 检查现有核心流程中的实体
        existing_flow_entities = set()
        for cf in ir.core_flows:
            existing_flow_entities.update(cf.get('handlers', []))
            existing_flow_entities.update(cf.get('call_chain', []))
        
        # 检查 PRD 实体是否在现有流程中
        missing_in_flow = [e for e in prd_entities if e.lower() not in ' '.join(existing_flow_entities).lower()]
        significant_missing = [e for e in missing_in_flow if len(e) >= 3 and e.lower() not in 
                             ['request', 'response', 'context', 'error', 'param']]
        
        if significant_missing[:3]:
            checks.append({
                'rule': 'flow_entity_missing',
                'severity': 'medium',
                'description': f"PRD 提到的以下实体在现有核心流程中未找到: {', '.join(significant_missing[:3])}",
                'suggestion': '需要确认这些实体的处理方式，可能需要新增流程节点',
            })
        
        return checks
    
    def _build_review_prompt(self, filtered: dict, ir: IRDocument, prd_text: str, cache_dir: str = None) -> str:
        """构建 PRD 审查 prompt — 注入完整 IR 数据
        
        优化：使用 base_engine 共享方法减少重复代码
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
        
        # 使用 base_engine 共享方法生成标准 IR 章节
        prompt_parts.append(self._build_routes_section(ir, limit=30))
        prompt_parts.append(self._build_business_logic_section(ir, limit=10))
        prompt_parts.append(self._build_entity_table_section(ir, limit=15))
        prompt_parts.append(self._build_error_code_section(ir, limit=15))
        prompt_parts.append(self._build_auth_model_section(ir))
        prompt_parts.append(self._build_sql_section(ir, limit=10))
        
        profile_data = self._normalize_profile(self.profile)
        
        # 注入核心业务流程（从 IR 自动推断）
        prompt_parts.append(self._build_core_flows_section(ir, limit=8))
        
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

        prompt_parts.append(self._build_test_coverage_section(ir))
        
        # 证据查询结果（按类型加权排序：function/route > struct > business_logic > schema）
        if filtered.get('evidence'):
            prompt_parts.append("## 代码库证据（基于 PRD 关键词查询，按相关度加权）")
            prompt_parts.append("")
            prompt_parts.append("**权重规则**: function/route = 1.5x | struct = 1.2x | entity_table = 1.0x | business_logic = 0.8x")
            
            # 计算加权分数
            weighted_evidence = []
            for item in filtered.get('evidence', [])[:25]:
                item_type = item.get('type', '')
                raw_score = item.get('score', 0)
                
                # 类型权重
                type_weights = {
                    'function': 1.5,
                    'route': 1.5,
                    'struct': 1.2,
                    'entity_table': 1.0,
                    'business_logic': 0.8,
                    'api': 1.3,
                    'schema': 0.7,
                }
                weight = type_weights.get(item_type, 1.0)
                weighted_score = raw_score * weight
                
                weighted_evidence.append({
                    **item,
                    'weighted_score': weighted_score,
                    'type_weight': weight,
                })
            
            # 按加权分数排序
            weighted_evidence.sort(key=lambda x: x['weighted_score'], reverse=True)
            
            # 展示 Top 20
            for i, item in enumerate(weighted_evidence[:20], 1):
                title = item.get('title', item.get('path', 'unknown'))
                score = item.get('score', 0)
                weighted = item.get('weighted_score', 0)
                content_text = item.get('content', item.get('text', ''))
                item_type = item.get('type', '?')
                prompt_parts.append(f"- **证据{i}** [type={item_type}] (raw={score:.3f}, weighted={weighted:.3f}): {title}")
                if content_text:
                    ct = content_text[:200].replace('\n', '\\n')
                    prompt_parts.append(f"  ```\\n  {ct}\\n  ```")
            prompt_parts.append("")
        
        # 预检查结果（从 _run_prechecks + _validate_business_rules 自动检测）
        if filtered.get('prechecks'):
            prompt_parts.append("## 预检查结果（自动检测）")
            # severity 映射: high->high, warn/medium->warn, info/low->info
            high_checks = [c for c in filtered['prechecks'] if c.get('severity') in ('high', 'critical')]
            warn_checks = [c for c in filtered['prechecks'] if c.get('severity') in ('warn', 'medium')]
            info_checks = [c for c in filtered['prechecks'] if c.get('severity') in ('info', 'low')]
            
            label_field = 'check' if any('check' in c for c in filtered['prechecks']) else 'rule'
            
            if high_checks:
                prompt_parts.append("### 🔴 高风险（必须关注）")
                for c in high_checks:
                    rule_name = c.get(label_field, c.get('rule', '?'))
                    msg = c.get('message', c.get('description', ''))
                    suggestion = c.get('suggestion', '')
                    prompt_parts.append(f"- **{rule_name}**: {msg}")
                    if suggestion:
                        prompt_parts.append(f"  建议: {suggestion}")
            if warn_checks:
                prompt_parts.append("### 🟡 警告（建议关注）")
                for c in warn_checks:
                    rule_name = c.get(label_field, c.get('rule', '?'))
                    msg = c.get('message', c.get('description', ''))
                    suggestion = c.get('suggestion', '')
                    prompt_parts.append(f"- **{rule_name}**: {msg}")
                    if suggestion:
                        prompt_parts.append(f"  建议: {suggestion}")
            if info_checks:
                prompt_parts.append("### 🔵 信息（仅供参考）")
                for c in info_checks:
                    rule_name = c.get(label_field, c.get('rule', '?'))
                    msg = c.get('message', c.get('description', ''))
                    prompt_parts.append(f"- **{rule_name}**: {msg}")
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
        
        # 资深工程师思维
        prompt_parts.append("## 资深工程师思维（必读）")
        prompt_parts.append("")
        prompt_parts.append("你是一位拥有 10 年经验的资深广告技术架构师。在审查 PRD 时，请按以下思维框架思考：")
        prompt_parts.append("")
        prompt_parts.append("### 1. 先看全局，再看局部")
        prompt_parts.append("- 先理解整个系统的架构（看包结构、路由、调用链）")
        prompt_parts.append("- 再看 PRD 提到的功能在系统中的位置")
        prompt_parts.append("- 最后判断是否合理")
        prompt_parts.append("")
        prompt_parts.append("### 2. 数据流向优先")
        prompt_parts.append("- 用户请求 → API → Service → DAO → DB")
        prompt_parts.append("- 每个环节都要考虑：数据从哪里来？到哪里去？")
        prompt_parts.append("- 特别注意：缓存、消息队列、外部 API")
        prompt_parts.append("")
        prompt_parts.append("### 3. 异常处理比正常流程更重要")
        prompt_parts.append("- 正常流程 10 分钟能写完，异常处理要 10 小时")
        prompt_parts.append("- 必查：网络超时、数据校验失败、权限不足、并发冲突")
        prompt_parts.append("- 必查：幂等性、重试策略、降级方案")
        prompt_parts.append("")
        prompt_parts.append("### 4. 性能意识")
        prompt_parts.append("- 高并发场景：QPS 多少？现有架构能撑住吗？")
        prompt_parts.append("- 大数据量：分页查询会不会 OOM？")
        prompt_parts.append("- 外部依赖：第三方 API 超时怎么处理？")
        prompt_parts.append("")
        prompt_parts.append("### 5. 向后兼容")
        prompt_parts.append("- 新功能不能破坏旧功能")
        prompt_parts.append("- 旧接口不能突然下线")
        prompt_parts.append("- 数据库变更要考虑数据迁移")
        prompt_parts.append("")
        prompt_parts.append("### 6. 安全底线")
        prompt_parts.append("- SQL 注入、XSS、越权访问")
        prompt_parts.append("- 敏感数据加密存储")
        prompt_parts.append("- 接口鉴权是否到位？")
        prompt_parts.append("")
        prompt_parts.append("### 7. 可观测性")
        prompt_parts.append("- 新功能要有日志、监控、告警")
        prompt_parts.append("- 关键操作要有审计日志")
        prompt_parts.append("- 出问题能快速定位吗？")
        prompt_parts.append("")
        prompt_parts.append("### 8. 看真实排障案例（从知识库）")
        prompt_parts.append("- 不要空想，要看别人踩过的坑")
        prompt_parts.append("- 比如：Redis 内存溢出 → 大 Key 拆分、淘汰策略")
        prompt_parts.append("- 比如：MySQL 慢查询 → 索引优化、SQL 改写")
        prompt_parts.append("- 比如：Kafka 消息堆积 → 消费者扩容、批处理")
        prompt_parts.append("")
        # 判断 PRD 类型：新功能 vs 现有功能增强
        is_new_feature = True
        existing_features = []
        for route in ir.routes[:20]:
            if route.get('handler', '').lower() in prd_text.lower() or route.get('path', '').lower() in prd_text.lower():
                is_new_feature = False
                existing_features.append(route.get('path', ''))
        
        if is_new_feature:
            prompt_parts.append("## 新功能架构设计（从零开始）")
            prompt_parts.append("")
            prompt_parts.append("PRD 描述的是一个全新的功能，现有代码中没有对应的实现。请按以下架构设计原则思考：")
            prompt_parts.append("")
            prompt_parts.append("### 1. 模块划分")
            prompt_parts.append("- **新增模块**: 需要新建哪些模块？（如：handler/service/dao）")
            prompt_parts.append("- **依赖关系**: 新模块依赖哪些现有模块？")
            prompt_parts.append("- **职责分离**: 每个模块的职责是什么？")
            prompt_parts.append("")
            prompt_parts.append("### 2. 数据模型")
            prompt_parts.append("- **新增表**: 需要新建哪些数据库表？")
            prompt_parts.append("- **字段设计**: 每个表的字段定义（类型/约束/索引）")
            prompt_parts.append("- **关联关系**: 表之间的关联关系（一对多/多对多）")
            prompt_parts.append("")
            prompt_parts.append("### 3. 接口设计")
            prompt_parts.append("- **RESTful API**: 需要新建哪些 HTTP 接口？")
            prompt_parts.append("- **Request/Response**: 每个接口的请求/响应结构")
            prompt_parts.append("- **错误码**: 需要定义哪些错误码？")
            prompt_parts.append("")
            prompt_parts.append("### 4. 业务流程")
            prompt_parts.append("- **主流程**: 核心业务流程的步骤")
            prompt_parts.append("- **异常处理**: 各种异常情况的处理策略")
            prompt_parts.append("- **幂等性**: 接口是否需要幂等设计？")
            prompt_parts.append("- **事务**: 哪些操作需要事务保证？")
            prompt_parts.append("")
            prompt_parts.append("### 5. 性能与安全")
            prompt_parts.append("- **缓存策略**: 哪些数据需要缓存？缓存多久？")
            prompt_parts.append("- **限流策略**: 接口是否需要限流？")
            prompt_parts.append("- **鉴权**: 接口需要什么权限？")
            prompt_parts.append("- **数据加密**: 敏感数据是否需要加密？")
            prompt_parts.append("")
        else:
            prompt_parts.append("## 功能增强审查")
            prompt_parts.append("")
            prompt_parts.append(f"PRD 描述的功能在现有代码中已有类似实现（如：{', '.join(existing_features[:3])}）。请重点审查：")
            prompt_parts.append("- **复用性**: 是否能复用现有模块？")
            prompt_parts.append("- **兼容性**: 新功能是否与现有接口兼容？")
            prompt_parts.append("- **扩展性**: 现有架构是否支持新功能的扩展？")
            prompt_parts.append("")
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
        # 注意：state_machines/business_rules/service_topology 已在上方注入，这里只补充审查规则提示
        prompt_parts.append("### 5. 兼容性检查（从 profile 配置）")
        if profile_data.get("business_rules"):
            prompt_parts.append("- **约束冲突**: PRD 是否违反了已有的业务规则/约束？")
        if profile_data.get("service_topology"):
            prompt_parts.append("- **服务依赖**: PRD 涉及的服务是否会影响上下游依赖？")
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
        prompt_parts.append("## 安全检查")
        prompt_parts.append("- **敏感数据保护**: 密码/token/个人信息是否加密存储和脱敏展示？")
        prompt_parts.append("- **SQL 注入**: 动态查询是否使用参数化查询？")
        prompt_parts.append("- **越权访问**: 是否实现 RBAC/ABAC 权限控制？")
        prompt_parts.append("- **XSS/CSRF**: 前端输入是否经过 sanitization？")
        prompt_parts.append("")
        prompt_parts.append("## 可观测性检查")
        prompt_parts.append("- **结构化日志**: 是否使用 zap/logrus，包含 traceId/userId？")
        prompt_parts.append("- **Prometheus 指标**: QPS、延迟、错误率是否暴露？")
        prompt_parts.append("- **健康检查**: /health (liveness) 和 /ready (readiness) 端点是否存在？")
        prompt_parts.append("- **告警规则**: 关键指标是否有告警阈值配置？")
        prompt_parts.append("")
        prompt_parts.append("## 数据合规检查")
        prompt_parts.append("- **个人数据处理**: 是否涉及个人信息？是否有脱敏/加密？")
        prompt_parts.append("- **数据保留**: 是否定义了数据保留期限？")
        prompt_parts.append("- **用户权利**: 是否支持用户数据删除/导出？")
        prompt_parts.append("- **跨境传输**: 是否涉及数据出境？是否需要合规审批？")
        prompt_parts.append("")
        prompt_parts.append("## 发布策略检查")
        prompt_parts.append("- **灰度发布**: 高风险变更是否制定了灰度发布方案？")
        prompt_parts.append("- **Feature Flag**: 是否使用 Feature Flag 控制功能开关？")
        prompt_parts.append("- **回滚方案**: 是否有明确的回滚步骤和时间窗口？")
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
        
        # 知识库路径 — 优先使用 EngineBase 推断的 kb_dir，回退到默认路径
        kb_base = None
        if self.kb_dir:
            kb_base = Path(self.kb_dir)
            if not kb_base.exists():
                kb_base = None
        if not kb_base:
            default_kb = Path.home() / 'ryan-personal-knowledge' / 'knowledge'
            if default_kb.exists():
                kb_base = default_kb
        
        if not kb_base or not kb_base.exists():
            return references
        
        # PRD 关键词（按权重排序）
        high_priority = ['竞价', '出价', 'bidding', '竞价引擎', 'CTR', 'CVR', '排序', '召回', '推荐',
                        '分享', '素材', '创意', 'creative', 'adgroup', '广告组', 'campaign', '通知', 'notify']
        medium_priority = ['redis', '缓存', 'kafka', '消息队列', 'mysql', '数据库', 'es', 'elasticsearch', '搜索',
                          '权限', 'permission', 'role', 'acl', '审核', 'review', 'approve', 'reject', '批量', 'batch']
        low_priority = ['k8s', 'docker', '部署', '架构', '设计', '高并发', '微服务', 'agent', 'AI',
                       '性能', 'performance', 'qps', 'tps', '延迟', 'latency', '超时', 'timeout', '重试', 'retry']
        
        # 精确匹配（高优先级）
        for kw in high_priority:
            if kw.lower() in prd_text.lower():
                kb_dir = 'advertising'
                kb_path = kb_base / kb_dir
                if kb_path.exists():
                    # 读取前 2 个深度文件 + 1 个排障手册（各 150 行）
                    md_files = sorted(kb_path.rglob('*-deep.md'))[:2]
                    # 加上广告排障手册
                    ad_trouble = kb_base / 'advertising' / 'ad-troubleshooting-manual-deep.md'
                    if ad_trouble.exists():
                        md_files.append(ad_trouble)
                    for md_file in md_files:
                        try:
                            content = md_file.read_text(encoding='utf-8', errors='ignore')
                            lines = content.split('\n')[:150]
                            references.append(f"### {md_file.relative_to(kb_base)}")
                            references.append('\n'.join(lines))
                            references.append("")
                        except Exception:
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
                            except Exception:
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
                            except Exception:
                                pass
                        break
        
        return references


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
        try:
            import urllib.request
            req = urllib.request.Request(args.prd_url, headers={'User-Agent': 'Mozilla/5.0'})
            prd_text = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"❌ Failed to fetch PRD from URL: {e}")
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
