#!/usr/bin/env python3
"""自动测试代码生成器 — 基于 IR 数据生成测试代码框架。

从 IR 中提取函数签名、错误码、Request/Response struct，
自动生成 Go test / pytest 代码骨架，减少手动编写时间。

核心功能：
1. 从 IR 提取关键函数签名 → 生成测试用例骨架
2. 从 IR 提取错误码 → 生成断言代码
3. 从 IR 提取 Request/Response struct → 生成构造代码
4. 支持 Go testify/gomock 和 Python pytest 两种风格
5. 可配置的 Mock 策略注入

Usage:
    from test_code_generator import TestCodeGenerator
    gen = TestCodeGenerator(ir_dict)
    go_code = gen.generate_go_test("CreateAdGroup")
    py_code = gen.generate_pytest("create_adgroup")
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class TestCodeGenerator:
    """基于 IR 数据的测试代码生成器。"""

    # Go 测试模板 — 增强版：支持错误码断言、table-driven tests、context timeout/cancel、test helpers
    GO_TEST_TEMPLATE = '''// {TestName} 测试{Description}
func Test{TestName}(t *testing.T) {{
    ctrl := gomock.NewController(t)
    defer ctrl.Finish()

    // 1. Setup dependencies
{SetupDepsCode}

    // 2. Mock {MockTarget} 层
{MockCode}

    // 3. 构造 handler
    handler := New{HandlerService}(mockDao, mockService)

    // 4. Table-driven tests (auto-parametrized from error_codes)
    tests := []struct {{
        name     string
        req      *{RequestStruct}
        wantErr  bool
        wantCode int
    }}{{
{TableDrivenTests}
    }}

    for _, tt := range tests {{
        t.Run(tt.name, func(t *testing.T) {{
            // Use context with timeout for each sub-test
            ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
            defer cancel()
{ExecuteCode}
        }})
    }}
}}'''

    # Go 测试模板 — 带 context 取消 / 超时的边界测试
    GO_TEST_CONTEXT_TEMPLATE = '''// {TestName}_Context 测试 - context timeout/cancel 场景
func Test{TestName}_Context(t *testing.T) {{
    ctrl := gomock.NewController(t)
    defer ctrl.Finish()

{MockCode}
    handler := New{HandlerService}(mockDao, mockService)

    tests := []struct {{
        name       string
        setupCtx   func() context.Context
        wantErr    bool
        expectCode int
    }}{{
{ContextTableTests}
    }}

    for _, tt := range tests {{
        t.Run(tt.name, func(t *testing.T) {{
            ctx := tt.setupCtx()
{ContextExecuteCode}
        }})
    }}
}}'''

    # Go 测试 helper functions 模板
    GO_TEST_HELPERS_TEMPLATE = '''// ============================================================================
// Test Helper Functions
// ============================================================================

// newMockCtrl creates a fresh gomock controller for tests
func newMockCtrl(t *testing.T) *gomock.Controller {{
    return gomock.NewController(t)
}}

// mustNewHandler constructs handler with given mocks; panics on nil
func mustNewHandler(ctrl *gomock.Controller, dao *Mock{DaoInterface}, svc *Mock{SvcInterface}) *{HandlerService} {{
    h := New{HandlerService}(dao, svc)
    if h == nil {{
        t.Fatal("handler should not be nil")
    }}
    return h
}}

// assertResponse checks common response fields
func assertResponse(t *testing.T, result *{ResponseStruct}, err error, wantErr bool) {{
    if wantErr {{
        assert.Error(t, err)
        assert.Nil(t, result)
        return
    }}
    assert.NoError(t, err)
    assert.NotNil(t, result)
}}

// makeValidRequest builds a fully-populated valid request
func makeValidRequest() *{RequestStruct} {{
    return &{RequestStruct}{{
{HelperRequestFields}
    }}
}}

// defaultTimeout returns a context with default timeout
func defaultTimeout(ctx context.Context) (context.Context, context.CancelFunc) {{
    return context.WithTimeout(ctx, 5*time.Second)
}}

// deadlineExceededCtx returns a context that is already past deadline
func deadlineExceededCtx() context.Context {{
    ctx, _ := context.WithDeadline(context.Background(), time.Now().Add(-time.Second))
    return ctx
}}

// cancelledCtx returns an already-cancelled context
func cancelledCtx() context.Context {{
    ctx, cancel := context.WithCancel(context.Background())
    cancel()
    return ctx
}}'''

    GO_TEST_EXCEPTION_TEMPLATE = '''// {TestName} 异常分支测试
func Test{TestName}_Exception(t *testing.T) {{
    ctrl := gomock.NewController(t)
    defer ctrl.Finish()

    // 1. Mock 返回错误
{MockErrorSetup}

    // 2. 执行并断言错误码
{ExecuteAndAssert}
}}'''

    # Python pytest 模板 — 增强版：支持 fixture、参数化、错误码断言、async
    PYTEST_TEMPLATE = '''import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
{ImportCode}


# ============================================================================
# Auto-generated Fixtures
# ============================================================================
@pytest.fixture
def mock_dao():
    """Mock database access object."""
    dao = MagicMock()
    dao.insert.return_value = MagicMock(id=1)
    dao.query.return_value = [MagicMock(id=1)]
    dao.update.return_value = True
    dao.delete.return_value = True
    dao.get_by_id.return_value = MagicMock(id=1)
    return dao


@pytest.fixture
def mock_redis():
    """Mock Redis cache layer."""
    redis_client = MagicMock()
    redis_client.get.return_value = None  # Cache miss by default
    redis_client.set.return_value = True
    redis_client.delete.return_value = True
    redis_client.exists.return_value = False
    redis_client.ttl.return_value = 300
    return redis_client


@pytest.fixture
def mock_config():
    """Mock configuration provider."""
    config = MagicMock()
    config.get.return_value = "default"
    config.__getitem__ = lambda self, key: "default"
    config.__getattr__ = lambda self, key: None
    return config


@pytest.fixture
def mock_dependencies(mock_dao, mock_redis, mock_config):
    """Aggregate all mocked dependencies."""
    return {{
        'dao': mock_dao,
        'redis': mock_redis,
        'config': mock_config,
    }}


# ============================================================================
# Test Cases
# ============================================================================
@pytest.mark.asyncio
async def test_{TestName}(mock_dependencies):
    """测试{Description} - 正常流程"""
    mock_dao = mock_dependencies['dao']
    mock_redis = mock_dependencies['redis']
    mock_config = mock_dependencies['config']
{MockCode}
    # 2. 构造请求
    request = {RequestStruct}(
{RequestFields}
    )

    # 3. 执行
{ExecuteCode}

    # 4. 断言
{AssertCode}'''

    # Pytest parametrize 模板（从 error_codes 生成参数化测试）
    PYTEST_PARAMETRIZE_TEMPLATE = '''
# ============================================================================
# Parameterized Tests (auto-generated from error_codes)
# ============================================================================
@pytest.mark.parametrize("error_scenario,error_code,expected_message", [
{ParametrizeRows}
])
def test_{TestName}_error_scenarios(mock_dependencies, error_scenario, error_code, expected_message):
    """参数化测试 - 覆盖所有错误场景"""
    mock_dao = mock_dependencies['dao']
    mock_redis = mock_dependencies['redis']
    mock_config = mock_dependencies['config']
{ParamMockSetup}
    result = handler.{FunctionName}(request)
    assert result.error_code == error_code
    assert expected_message in result.message
'''

    # Pytest async test template
    PYTEST_ASYNC_TEMPLATE = '''import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
{ImportCode}


@pytest.fixture
def mock_dao():
    dao = AsyncMock()
    dao.insert.return_value = AsyncMock(id=1)
    dao.query.return_value = [AsyncMock(id=1)]
    return dao


@pytest.fixture
def mock_redis():
    redis_client = AsyncMock()
    redis_client.get.return_value = None
    redis_client.set.return_value = True
    return redis_client


@pytest.mark.asyncio
async def test_{TestName}_async(mock_dao, mock_redis):
    """异步测试{Description}"""
    mock_dao.{MethodName}.return_value = MagicMock(id=1)
{MockCode}
    result = await handler.{FunctionName}(request)
{AssertCode}
'''

    PYTEST_EXCEPTION_TEMPLATE = '''def test_{TestName}_exception(mock_dependencies):
    """测试{Description} - 异常分支"""
    mock_dao, mock_service, mock_redis = mock_dependencies
{MockErrorSetup}
    # 执行并断言错误码
{ExecuteAndAssert}
'''

    def __init__(self, ir_data: Dict[str, Any]):
        self.ir = ir_data or {}
        self.functions = self.ir.get('functions', [])
        self.structs = self.ir.get('structs', [])
        self.routes = self.ir.get('routes', [])
        self.error_codes = self.ir.get('error_codes', [])
        self.call_graph = self.ir.get('call_graph', [])
        self.entity_tables = self.ir.get('entity_tables', [])

        # 验证 IR 数据完整性
        self._validate_ir()

        # 构建函数名 → 文件映射
        self.func_to_file = {}
        for func in self.functions:
            if not isinstance(func, dict):
                continue
            fname = func.get('name', '')
            ffile = func.get('file', '')
            if fname and ffile:
                self.func_to_file[fname] = ffile

        # 构建 struct 映射
        self.struct_map = {}
        for s in self.structs:
            if not isinstance(s, dict):
                continue
            sname = s.get('name', '')
            if sname:
                self.struct_map[sname] = s

    def _validate_ir(self):
        """验证 IR 数据完整性，记录缺失信息"""
        warnings = []
        if not self.functions:
            warnings.append("IR 中无 functions 数据")
        if not self.routes:
            warnings.append("IR 中无 routes 数据")
        if not self.structs:
            warnings.append("IR 中无 structs 数据")
        if not self.error_codes:
            warnings.append("IR 中无 error_codes 数据")

        if warnings:
            print(f"⚠️  TestCodeGenerator IR 数据不完整: {'; '.join(warnings)}")

    def generate_go_test(self, handler_name: str, test_type: str = "success") -> Optional[str]:
        """为 Go handler 生成测试代码。

        Args:
            handler_name: Handler 函数名（如 CreateAdGroup）
            test_type: 测试类型 (success/exception/boundary/context)

        Returns:
            生成的 Go 测试代码，如果未找到匹配则返回 None
        """
        target_func = self._find_function(handler_name)
        if not target_func:
            print(f"⚠️  Function '{handler_name}' not found in IR")
            return None

        dependencies = self._get_dependencies(handler_name)
        mock_code = self._generate_go_mock(dependencies)
        request_struct, request_fields, table_tests = self._extract_request_struct(target_func)
        error_asserts = self._extract_error_codes_for_handler(handler_name)
        execute_code = self._generate_go_execute(handler_name, dependencies)

        description = self._describe_test(handler_name, test_type)
        handler_service = handler_name.replace('Handler', '').replace('handler', '')

        # Extract dao and service interface names for helper functions
        dao_interface, svc_interface = self._infer_interfaces(dependencies)

        if test_type == "exception":
            return self._generate_go_exception_test(
                handler_name, dependencies, error_asserts, mock_code, handler_service
            )

        if test_type == "context":
            return self._generate_go_context_test(
                handler_name, dependencies, mock_code, handler_service, request_struct
            )

        # Enhanced setup deps code
        setup_deps = self._generate_go_setup_deps(dependencies)

        test_code = self.GO_TEST_TEMPLATE.format(
            TestName=f"{handler_name}_Success",
            Description=description,
            MockTarget=self._get_mock_target(dependencies),
            MockCode=mock_code,
            SetupDepsCode=setup_deps,
            HandlerService=handler_service or "Handler",
            RequestStruct=request_struct or "Request",
            TableDrivenTests=table_tests,
            ExecuteCode=execute_code,
        )

        # Append helper functions
        helpers = self._generate_go_test_helpers(
            handler_service or "Handler",
            dao_interface or "Dao",
            svc_interface or "Service",
            request_struct or "Request",
            request_fields,
        )

        return test_code + "\n\n" + helpers

    def generate_pytest(self, function_name: str, test_type: str = "success") -> Optional[str]:
        """为 Python 函数生成 pytest 测试代码。

        Args:
            function_name: 函数名（如 create_adgroup）
            test_type: 测试类型 (success/exception/boundary/async)

        Returns:
            生成的 pytest 代码，如果未找到匹配则返回 None
        """
        target_func = self._find_function(function_name)
        if not target_func:
            print(f"⚠️  Function '{function_name}' not found in IR")
            return None

        dependencies = self._get_dependencies(function_name)
        mock_code = self._generate_pytest_mock(dependencies)
        request_struct, request_fields = self._extract_pytest_request(target_func)

        error_codes = self._get_error_codes_for_function(function_name)
        execute_code = self._generate_pytest_execute(function_name, request_struct)
        assert_code = self._generate_pytest_assert(test_type, error_codes)

        description = self._describe_test(function_name, test_type)

        if test_type == "exception":
            return self._generate_pytest_exception_test(
                function_name, dependencies, error_codes, mock_code, description
            )

        # Detect async functions from signature
        is_async = self._detect_async_function(target_func)

        test_code = self.PYTEST_TEMPLATE.format(
            TestName=function_name.replace('-', '_').replace(' ', '_'),
            Description=description,
            MockCode=mock_code,
            RequestStruct=request_struct or "Request",
            RequestFields=request_fields,
            ExecuteCode=execute_code,
            AssertCode=assert_code,
            ImportCode=self._generate_imports(function_name),
        )

        # Append parameterized tests from error_codes
        if error_codes:
            parametrize_code = self._generate_pytest_parametrize(
                function_name, error_codes, mock_code
            )
            test_code += "\n\n" + parametrize_code

        # If async detected, also generate async variant
        if is_async:
            async_code = self._generate_pytest_async_variant(
                function_name, dependencies, error_codes, mock_code, assert_code, description
            )
            test_code += "\n\n" + async_code

        return test_code

    def generate_batch_tests(self, handlers: List[str], test_types: Optional[List[str]] = None) -> Dict[str, str]:
        """批量生成多个测试用例。

        Args:
            handlers: Handler/函数名列表
            test_types: 测试类型列表 (默认 [success, exception])

        Returns:
            {filename: code_content}
        """
        test_types = test_types or ["success", "exception"]
        results = {}

        for handler in handlers:
            for test_type in test_types:
                # Try Go first
                go_code = self.generate_go_test(handler, test_type)
                if go_code:
                    safe_name = handler.lower().replace(' ', '_')
                    filename = f"test_{safe_name}_{test_type}.go"
                    results[filename] = go_code

                # Try Python
                py_name = handler[0].lower() + handler[1:] if handler else handler
                if handler and handler[0].isupper():
                    snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', handler).lower()
                else:
                    snake_name = py_name
                py_code = self.generate_pytest(snake_name, test_type)
                if py_code:
                    filename = f"test_{snake_name}_{test_type}.py"
                    results[filename] = py_code

        return results

    def generate_all(self, handlers: Optional[List[str]] = None) -> Dict[str, Any]:
        """生成完整的测试套件（单元 + 集成 + mock策略 + 数据准备）。

        Args:
            handlers: 要生成的 handler 列表，None 则从 IR routes 自动推断

        Returns:
            包含所有生成结果的字典
        """
        results = {
            'unit_tests': {},
            'integration_tests': {},
            'mock_strategies': {},
            'data_preparation': {},
        }

        target_handlers = handlers or []
        if not target_handlers:
            for route in self.routes[:20]:
                if isinstance(route, dict):
                    h = route.get('handler', '')
                    if h:
                        target_handlers.append(h.split('.')[-1])

        # Unit tests (Go + Python)
        for handler in target_handlers:
            for test_type in ['success', 'exception', 'context']:
                go_code = self.generate_go_test(handler, test_type)
                if go_code:
                    safe_name = handler.lower().replace(' ', '_')
                    results['unit_tests'][f"go/test_{safe_name}_{test_type}.go"] = go_code

                snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', handler).lower()
                py_code = self.generate_pytest(snake_name, test_type)
                if py_code:
                    results['unit_tests'][f"python/test_{snake_name}_{test_type}.py"] = py_code

        # Integration tests
        for handler in target_handlers:
            route_info = None
            for route in self.routes:
                if isinstance(route, dict) and route.get('handler', '').endswith(handler):
                    route_info = route
                    break
            integ = self.generate_integration_test_template(handler, route_info)
            if integ:
                safe_name = handler.lower().replace(' ', '_')
                results['integration_tests'][f"go/integration_{safe_name}.go"] = integ.get('go', '')
                results['integration_tests'][f"python/integration_{safe_name}.py"] = integ.get('python', '')

        # Mock strategies
        for handler in target_handlers[:10]:
            strategy = self.generate_mock_strategy(handler)
            if strategy.get('mock_layers'):
                safe_name = handler.lower().replace(' ', '_')
                results['mock_strategies'][f"mock_strategy_{safe_name}.json"] = strategy

        # Data preparation strategies
        for handler in target_handlers[:10]:
            prep = self.generate_data_preparation_strategy(handler)
            if prep.get('strategies'):
                safe_name = handler.lower().replace(' ', '_')
                results['data_preparation'][f"data_prep_{safe_name}.json"] = prep

        return results

    def _detect_async_function(self, func: Dict) -> bool:
        """检测函数是否为 async 函数。"""
        sig = func.get('signature', '') or func.get('params', '')
        name = func.get('name', '').lower()
        # Check signature for 'async' keyword
        if re.search(r'\basync\s+def\b', sig):
            return True
        # Check name for common async patterns
        if any(kw in name for kw in ['async', 'await', 'streaming']):
            return True
        # Check for async-related return type hints
        if 'async' in sig.lower() or 'coroutine' in sig.lower():
            return True
        return False

    def _generate_pytest_parametrize(self, function_name: str, error_codes: List[str],
                                      mock_code: str) -> str:
        """从 error_codes 生成 pytest.mark.parametrize 参数化测试。"""
        rows = []
        for ec in error_codes:
            ec_upper = ec.upper()
            scenario_name = f"err_{ec_lower}" if (ec_lower := ec.lower()) else "unknown_error"
            rows.append(f'        ("{scenario_name}", "{ec}", "Error: {ec}"),')

        return self.PYTEST_PARAMETRIZE_TEMPLATE.format(
            TestName=function_name.replace('-', '_'),
            ParametrizeRows='\n'.join(rows),
            FunctionName=function_name,
            ParamMockSetup=f'    {mock_code}' if mock_code.strip() != '# No external dependencies to mock' else '    # No mock setup needed',
        )

    def _generate_pytest_async_variant(self, function_name: str, dependencies: List[Dict],
                                        error_codes: List[str], mock_code: str,
                                        assert_code: str, description: str) -> str:
        """生成 async 测试变体。"""
        method_name = "query"  # default
        for dep in dependencies:
            if dep['type'] == 'call':
                target = dep.get('target', '')
                if 'dao' in target.lower() or 'db' in target.lower():
                    method_name = "insert" if 'create' in function_name.lower() else "query"
                    break

        return self.PYTEST_ASYNC_TEMPLATE.format(
            TestName=function_name.replace('-', '_'),
            Description=description,
            MethodName=method_name,
            ImportCode=self._generate_imports(function_name),
            MockCode=mock_code,
            FunctionName=function_name,
            AssertCode=assert_code,
        )

    def _infer_interfaces(self, dependencies: List[Dict]) -> Tuple[str, str]:
        """从依赖链推断 DAO 和 Service 接口名。"""
        dao_name = ""
        svc_name = ""
        for dep in dependencies:
            if dep['type'] != 'call':
                continue
            target = dep.get('target', '').lower()
            sanitized = self._sanitize_identifier(dep.get('target', ''))
            if any(kw in target for kw in ['dao', 'repo', 'mysql', 'db', 'sql']):
                if not dao_name:
                    dao_name = sanitized
            elif any(kw in target for kw in ['service', 'manager']):
                if not svc_name:
                    svc_name = sanitized
        return dao_name, svc_name

    def _generate_go_setup_deps(self, dependencies: List[Dict]) -> str:
        """生成 Go 依赖 setup 代码（import 提示 + context import）。"""
        lines = []
        has_context = False
        for dep in dependencies:
            if dep['type'] != 'call':
                continue
            target = dep.get('target', '')
            target_lower = target.lower()
            if 'context' in target_lower or 'ctx' in target_lower:
                has_context = True
            # Detect time dependency for timeout
            if any(kw in target_lower for kw in ['time', 'now', 'deadline']):
                has_context = True

        if has_context:
            lines.append('    // Ensure imports: "context", "time" are included')
        else:
            lines.append('    // No special dependencies to setup')
        return '\n'.join(f'    {line}' for line in lines)

    def _generate_go_context_test(self, handler_name: str, dependencies: List[Dict],
                                   mock_code: str, handler_service: str,
                                   request_struct: str) -> str:
        """生成 context.WithTimeout/cancel 场景的测试。"""
        # Build context test cases from error_codes boundary conditions
        context_rows = []

        # 1. Normal context (success path)
        context_rows.append(f'''{{
            name:       "normal_context",
            setupCtx:   func() context.Context {{ ctx, _ := defaultTimeout(context.Background()); return ctx }},
            wantErr:    false,
            expectCode: 0,
        }},''')

        # 2. Deadline exceeded
        context_rows.append(f'''{{
            name:       "deadline_exceeded",
            setupCtx:   deadlineExceededCtx,
            wantErr:    true,
            expectCode: 408,
        }},''')

        # 3. Cancelled context
        context_rows.append(f'''{{
            name:       "cancelled_context",
            setupCtx:   cancelledCtx,
            wantErr:    true,
            expectCode: 499,
        }},''')

        # 4. Generate additional context boundary tests from error_codes
        for ec in self.error_codes[:3]:
            if not isinstance(ec, dict):
                continue
            desc = ec.get('description', '')
            code = ec.get('name', ec.get('code', ''))
            if desc and code:
                scenario_name = re.sub(r'[^a-zA-Z0-9_]', '_', code).lower()
                context_rows.append(f'''{{
                    name:       "{scenario_name}",
                    setupCtx:   func() context.Context {{ ctx, _ := defaultTimeout(context.Background()); return ctx }},
                    wantErr:    true,
                    expectCode: {self._error_code_to_int(code)},
                }},''')

        execute_code = f'''    result, err := handler.{handler_name}(ctx, makeValidRequest())
            assertResponse(t, result, err, tt.wantErr)'''

        return self.GO_TEST_CONTEXT_TEMPLATE.format(
            TestName=handler_name,
            MockCode=f'    {mock_code}',
            HandlerService=handler_service or "Handler",
            ContextTableTests='\n'.join(context_rows),
            ContextExecuteCode=f'    {execute_code}',
        )

    @staticmethod
    def _error_code_to_int(code: str) -> int:
        """尝试将错误码名称转为整数，失败则返回 -1。"""
        code_upper = code.upper()
        if code_upper.startswith('ERR_'):
            code_upper = code_upper[4:]
        try:
            return int(code_upper)
        except ValueError:
            return -1

    def _generate_go_test_helpers(self, handler_service: str, dao_interface: str,
                                   svc_interface: str, request_struct: str,
                                   request_fields: str) -> str:
        """生成 Go test helper functions。"""
        # Parse request fields into struct initialization lines
        field_init_lines = []
        for line in request_fields.split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('//'):
                field_init_lines.append(f'        {line}')
            elif line and not line.startswith('//'):
                field_init_lines.append(f'        {line}: "",')

        if not field_init_lines:
            field_init_lines.append('        // Populate fields manually')

        return self.GO_TEST_HELPERS_TEMPLATE.format(
            DaoInterface=dao_interface or "Dao",
            SvcInterface=svc_interface or "Service",
            HandlerService=handler_service or "Handler",
            ResponseStruct="Response",
            RequestStruct=request_struct or "Request",
            HelperRequestFields='\n'.join(field_init_lines),
        )

    def _find_function(self, name: str) -> Optional[Dict]:
        """在 IR 中查找匹配的函数。"""
        name_lower = name.lower()
        # 也尝试将 snake_case 转为 camelCase 进行匹配
        name_camel = re.sub(r'_([a-z])', lambda m: m.group(1).upper(), name_lower)

        for func in self.functions:
            if not isinstance(func, dict):
                continue
            fname = func.get('name', '').lower()
            if name_lower == fname or name_lower in fname or fname in name_lower:
                return func
            # 也检查 camelCase 匹配
            if name_camel and (name_camel.lower() == fname or name_camel.lower() in fname):
                return func

        # 也检查 routes
        for route in self.routes:
            if not isinstance(route, dict):
                continue
            handler = route.get('handler', '').lower()
            if name_lower == handler or name_lower in handler or handler in name_lower:
                return {'name': route.get('handler', ''), 'file': route.get('file', '')}

        return None

    def _get_dependencies(self, func_name: str) -> List[Dict]:
        """从 call_graph 获取函数的依赖链。"""
        deps = []
        for edge in self.call_graph:
            if not isinstance(edge, dict):
                continue
            caller = edge.get('caller', '')
            callee = edge.get('callee', '')
            if caller == func_name:
                deps.append({
                    'type': 'call',
                    'source': caller,
                    'target': callee,
                })

        # 反向查找：谁调用了这个函数
        for edge in self.call_graph:
            if not isinstance(edge, dict):
                continue
            caller = edge.get('caller', '')
            callee = edge.get('callee', '')
            if callee == func_name:
                deps.append({
                    'type': 'called_by',
                    'source': caller,
                    'target': callee,
                })

        return deps[:10]

    @staticmethod
    def _sanitize_identifier(name: str) -> str:
        """将任意字符串转换为合法标识符（移除 . / - 等非法字符）。"""
        safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        if safe and safe[0].isdigit():
            safe = '_' + safe
        return safe or 'dep'

    def _generate_go_mock(self, dependencies: List[Dict]) -> str:
        """生成 Go gomock 代码。

        将依赖目标（如 AdGroupService.Create）转换为合法 Go 标识符：
        - 接口名: MockAdGroupService_Create
        - 变量名: mockAdGroupService_Create
        """
        lines = []
        for dep in dependencies:
            if dep['type'] != 'call':
                continue
            target = dep['target']
            safe_target = self._sanitize_identifier(target)
            # 避免双 Mock 前缀：如果 safe_target 已包含 Mock，不再加
            prefix = "" if safe_target.startswith("Mock") else "Mock"
            var_prefix = "" if safe_target.startswith("mock") else "mock"
            interface_name = f"{prefix}{safe_target}"
            var_name = f"{var_prefix}{safe_target}"
            lines.append(f'    {var_name} := NewMock{interface_name}(ctrl)')
            lines.append(f'    {var_name}.EXPECT().AnyMatch(gomock.Any()).Return(nil)')

        if not lines:
            lines.append('    // No external dependencies to mock')

        return '\n'.join(f'    {line}' for line in lines)
    def _generate_pytest_mock(self, dependencies: List[Dict]) -> str:
        """生成 Python pytest mock 代码。"""
        lines = []
        for dep in dependencies:
            if dep['type'] == 'call':
                target = self._sanitize_identifier(dep['target'])
                lines.append(f'    mock_{target}.return_value = MagicMock()')

        if not lines:
            lines.append('    # No external dependencies to mock')

        return '\n'.join(f'    {line}' for line in lines)

    @staticmethod
    def _default_value_for_type(field_type: str) -> str:
        """根据字段类型生成合理的默认值。"""
        t = (field_type or 'string').lower().replace(' ', '').replace('*', '')
        if 'int64' in t or 'int32' in t or 'int' in t:
            return '0'
        if 'float' in t or 'double' in t or 'decimal' in t:
            return '0.0'
        if 'bool' in t:
            return 'false'
        if 'time' in t or 'date' in t:
            return 'time.Now()'
        if '[]' in t or 'slice' in t:
            return '[]string{}'
        if 'map' in t:
            return 'map[string]string{}'
        if 'id' in t.lower():
            return '"test-id"'
        if 'name' in t.lower():
            return '"test-name"'
        if 'desc' in t.lower() or 'comment' in t.lower():
            return '"test-description"'
        if 'email' in t.lower():
            return '"test@example.com"'
        if 'phone' in t.lower() or 'mobile' in t.lower():
            return '"13800138000"'
        if 'url' in t.lower() or 'link' in t.lower():
            return '"https://example.com"'
        if 'status' in t.lower():
            return '0'
        if 'count' in t.lower() or 'num' in t.lower() or 'size' in t.lower():
            return '10'
        if 'price' in t.lower() or 'amount' in t.lower() or 'money' in t.lower():
            return '0.01'
        if 'list' in t.lower() or 'ids' in t.lower():
            return '[]string{"test-id-1"}'
        return '""'

    def _extract_request_struct(self, func: Dict) -> tuple:
        """从函数签名中提取 Request struct 信息。

        优先从 struct_map 查找 Request struct，其次从 signature 正则提取。
        """
        sig = func.get('signature', '') or func.get('params', '')
        fields = func.get('fields', [])

        struct_name = ''
        field_lines = []
        table_test_rows = []

        # 1. 从签名解析 Request 类型
        struct_match = re.findall(r'\*?(\w+)Request', sig)
        if struct_match:
            struct_name = struct_match[0]

        # 2. 从 IR structs 补充字段
        if struct_name and struct_name in self.struct_map:
            s = self.struct_map[struct_name]
            raw_fields = s.get('fields', []) if isinstance(s, dict) else getattr(s, 'fields', [])
            if isinstance(raw_fields, list):
                for rf in raw_fields[:5]:
                    if isinstance(rf, dict):
                        fname = rf.get('name', '')
                        ftype = rf.get('type', 'string')
                        if fname:
                            default_val = self._default_value_for_type(ftype)
                            field_lines.append(f'        {fname}: {default_val},')
                            table_test_rows.append(f'''{{
                            name: "normal_{fname}",
                            req: &{struct_name}{{{fname}: {default_val}}},
                            wantErr: false,
                        }},''')
                    elif isinstance(rf, str):
                        default_val = self._default_value_for_type('string')
                        field_lines.append(f'        {rf}: {default_val},')
                        table_test_rows.append(f'''{{
                            name: "normal_{rf.lower()}",
                            req: &{struct_name}{{{rf}: {default_val}}},
                            wantErr: false,
                        }},''')

        # 3. 从 func.fields 补充字段
        if isinstance(fields, list):
            for f in fields[:5]:
                if isinstance(f, dict):
                    fname = f.get('name', '')
                    ftype = f.get('type', 'string')
                    if fname and not any(fl.split(':')[0].strip() == fname for fl in field_lines):
                        default_val = self._default_value_for_type(ftype)
                        field_lines.append(f'        {fname}: {default_val},')
                        table_test_rows.append(f'''{{
                            name: "normal_{fname}",
                            req: &{struct_name or "Request"}{{{fname}: {default_val}}},
                            wantErr: false,
                        }},''')
                elif isinstance(f, str):
                    if f not in [fl.split(':')[0].strip() for fl in field_lines]:
                        default_val = self._default_value_for_type('string')
                        field_lines.append(f'        {f}: {default_val},')
                        table_test_rows.append(f'''{{
                            name: "normal_{f.lower()}",
                            req: &{struct_name or "Request"}{{{f}: {default_val}}},
                            wantErr: false,
                        }},''')

        # 如果没有从 fields 生成 table tests，添加一个默认测试行
        if not table_test_rows:
            table_test_rows.append('''{{
                name: "default",
                req: &{RequestStruct}{{}},
                wantErr: false,
            }},'''.format(RequestStruct=struct_name or "Request"))

        if not field_lines:
            field_lines.append('        // No fields extracted — manually populate Request struct')

        return struct_name, '\n'.join(field_lines), '\n'.join(table_test_rows)

    def _extract_error_codes_for_handler(self, handler_name: str) -> str:
        """为 handler 生成错误码断言代码。"""
        related_codes = []
        for ec in self.error_codes:
            if not isinstance(ec, dict):
                continue
            ec_name = ec.get('name', '').lower()
            ec_desc = ec.get('description', '').lower()
            handler_lower = handler_name.lower()

            if (handler_lower in ec_name or
                any(kw in ec_desc for kw in ['create', 'add', 'new', '创建', '新增']) or
                any(kw in ec_desc for kw in ['not found', '不存在', '404'])):
                related_codes.append(ec.get('name', ec.get('code', 'ERR_UNKNOWN')))

        if related_codes:
            codes_str = ', '.join(f'"{c}"' for c in related_codes[:5])
            return f'''    // Expected error codes: {codes_str}
    // assert.ErrorIs(t, err, errors.New({related_codes[0]}))'''
        return '    // No related error codes found — manually verify response status'

    def _generate_go_exception_test(self, handler_name: str, dependencies: List[Dict],
                                     error_asserts: str, mock_code: str,
                                     handler_service: str) -> str:
        """生成 Go 异常分支测试。"""
        mock_errors = []
        for dep in dependencies:
            if dep['type'] == 'call':
                target = self._sanitize_identifier(dep['target'])
                interface_name = f"Mock{target}"
                var_name = f"mock{target}"
                mock_errors.append(f'    {var_name} := NewMock{interface_name}(ctrl)')
                mock_errors.append(f'    {var_name}.EXPECT().AnyMatch(gomock.Any()).Return(errors.New("mock error"))')

        if not mock_errors:
            mock_errors.append('    // Mock layer returns error')

        return self.GO_TEST_EXCEPTION_TEMPLATE.format(
            TestName=handler_name,
            Description="异常分支",
            MockErrorSetup='\n'.join(mock_errors),
            ExecuteAndAssert=f'    // Assert error code\n    {error_asserts}',
        )

    def _get_error_codes_for_function(self, func_name: str) -> List[str]:
        """获取与函数相关的错误码列表。"""
        codes = []
        func_lower = func_name.lower()
        for ec in self.error_codes:
            if not isinstance(ec, dict):
                continue
            ec_name = ec.get('name', '').lower()
            desc = ec.get('description', '').lower()
            code_val = ec.get('code', 0)

            # Match 1: function name appears in error code name or description
            if func_lower in ec_name or func_lower in desc:
                codes.append(ec.get('name', ec.get('code', 'UNKNOWN')))
                continue

            # Match 2: action keyword matching (create/add/new/delete/update/get/list)
            action_keywords = ['create', 'add', 'new', '创建', '新增', 'insert']
            if any(kw in func_lower for kw in action_keywords):
                if any(kw in desc for kw in action_keywords) or any(kw in ec_name for kw in action_keywords):
                    codes.append(ec.get('name', ec.get('code', 'UNKNOWN')))
                    continue

            # Match 3: general error/fail/err keywords in description
            if any(kw in desc for kw in ['error', 'fail', 'err', 'invalid', 'not found', 'denied']):
                codes.append(ec.get('name', ec.get('code', 'UNKNOWN')))
                continue

            # Match 4: category-based matching
            category = ec.get('category', '').lower()
            if 'validation' in category and ('valid' in func_lower or 'create' in func_lower):
                codes.append(ec.get('name', ec.get('code', 'UNKNOWN')))
                continue

        return list(dict.fromkeys(codes))[:5]  # deduplicate while preserving order

    def _generate_pytest_exception_test(self, function_name: str, dependencies: List[Dict],
                                         error_codes: List[str], mock_code: str,
                                         description: str) -> str:
        """生成 Python 异常分支测试。"""
        mock_errors = []
        for dep in dependencies:
            if dep['type'] == 'call':
                target = self._sanitize_identifier(dep['target'])
                mock_errors.append(f'    mock_{target}.side_effect = Exception("mock error")')

        if not mock_errors:
            mock_errors.append('    # Mock layer returns error')

        error_codes_str = ', '.join(f'"{c}"' for c in error_codes) if error_codes else '"expected error"'

        return self.PYTEST_EXCEPTION_TEMPLATE.format(
            TestName=function_name.replace('-', '_'),
            Description=description,
            MockErrorSetup='\n'.join(mock_errors),
            ExecuteAndAssert=f'    # Assert error code contains: {error_codes_str}\n    assert result.error_code in [{error_codes_str}]',
        )

    def _generate_imports(self, function_name: str) -> str:
        """生成 pytest 导入语句。"""
        imports = [
            'from src.handler import {HandlerClass}',
            'from src.service import Service',
            'from src.dao import DAO',
        ]
        # 根据函数名猜测 handler 类名
        handler_class = function_name[0].upper() + function_name[1:] + 'Handler'
        imports[0] = imports[0].format(HandlerClass=handler_class)
        return '\n'.join(imports)

    def _extract_pytest_request(self, func: Dict) -> tuple:
        """从函数签名中提取 Python Request 信息。

        优先使用 func.fields 中的结构化字段，fallback 到正则解析参数。
        """
        sig = func.get('signature', '') or func.get('params', '')
        fields = func.get('fields', [])

        struct_name = ''
        field_lines = []

        # 优先从 fields 提取（更可靠）
        if isinstance(fields, list):
            for f in fields[:5]:
                if isinstance(f, dict):
                    fname = f.get('name', '')
                    ftype = f.get('type', 'str')
                    if fname:
                        default = self._default_python_value(ftype)
                        field_lines.append(f'        {fname}={default},')
                elif isinstance(f, str):
                    field_lines.append(f'        {f}=None,')

        # fallback: 从签名正则解析
        if not field_lines:
            param_match = re.findall(r'(\w+):\s*(\w+)', sig)
            for pname, ptype in param_match[:5]:
                default = '"value"' if ptype == 'str' else '0'
                field_lines.append(f'        {pname}={default},')

        if not field_lines:
            field_lines.append('        # No parameters extracted — manually construct request based on function signature')

        return struct_name, '\n'.join(field_lines)

    @staticmethod
    def _default_python_value(field_type: str) -> str:
        """根据 Python 类型生成默认值。"""
        t = (field_type or 'str').lower().replace(' ', '')
        if t in ('int', 'integer'):
            return '0'
        if t in ('float', 'double', 'decimal'):
            return '0.0'
        if t in ('bool',):
            return 'False'
        if t in ('str', 'string'):
            return '"value"'
        if t in ('list', 'array'):
            return '[]'
        if t in ('dict', 'mapping'):
            return '{}'
        return 'None'

    def _generate_go_execute(self, handler: str, deps: List[Dict]) -> str:
        """生成 Go 执行代码（table-driven 内部，引用 tt.req）。"""
        return f'    result, err := handler.{handler}(context.Background(), tt.req)'

    def _generate_pytest_execute(self, func_name: str, request_struct: str = "") -> str:
        """生成 Python 执行代码。"""
        return f'    result = handler.{func_name}(request)'

    def _generate_go_assert(self, test_type: str, handler: str) -> str:
        """生成 Go 断言代码。"""
        if test_type == "success":
            return '''    assert.NoError(t, err)
    assert.NotNil(t, result)
    assert.NotEmpty(t, result.ID)'''
        elif test_type == "exception":
            return '''    assert.Error(t, err)
    assert.Nil(t, result)
    assert.Contains(t, err.Error(), "expected error message")'''
        else:
            return '''    // Boundary conditions: empty input, max length, special chars
    assert.Error(t, err)
    assert.Nil(t, result)
    assert.Contains(t, err.Error(), "validation failed")'''

    def _generate_pytest_assert(self, test_type: str, error_codes: Optional[List[str]] = None) -> str:
        """生成 Python 断言代码。"""
        if test_type == "success":
            code = '''    assert result is not None
    assert result.id == 1
    # mock_dao.insert.assert_called_once()'''
        elif test_type == "exception":
            if error_codes:
                codes_str = ', '.join(f'"{c}"' for c in error_codes)
                code = f'''    assert result.error_code in [{codes_str}]
    assert result.message is not None'''
            else:
                code = '''    assert result.error_code != 0
    assert result.message is not None'''
        else:
            code = '''    # Boundary conditions: empty string, max length, special chars
    assert result.error_code != 0
    assert result.message is not None'''
        return code

    def _describe_test(self, func_name: str, test_type: str) -> str:
        """生成测试描述。"""
        descriptions = {
            'success': '正常流程',
            'exception': '异常分支',
            'boundary': '边界条件',
        }
        action = func_name.split('_')[-1] if '_' in func_name else func_name
        return f"{descriptions.get(test_type, '测试')} - {action}"

    def _get_mock_target(self, dependencies: List[Dict]) -> str:
        """获取主要 mock 目标。"""
        for dep in dependencies:
            if dep['type'] == 'call':
                return dep['target']
        return "external service"

    def generate_test_plan(self, prd_text: str) -> Dict[str, Any]:
        """基于 PRD 生成测试计划。

        从 PRD 中提取测试场景，映射到 IR 中的函数/路由。
        """
        plan = {
            'scenarios': [],
            'coverage_targets': {},
            'estimated_test_count': 0,
        }

        # 从 PRD 提取关键词
        keywords = self._extract_prd_keywords(prd_text)

        # 匹配 IR 中的路由
        for route in self.routes[:20]:
            if not isinstance(route, dict):
                continue
            path = route.get('path', '')
            method = route.get('method', 'GET')
            handler = route.get('handler', '')

            # 判断是否需要测试
            needs_test = True
            test_scenarios = ['正向流程']

            # 如果是 CRUD 路由，添加更多场景
            if 'POST' in method:
                test_scenarios.extend(['参数校验', '权限检查'])
            elif 'PUT' in method or 'PATCH' in method:
                test_scenarios.extend(['资源不存在', '并发修改'])
            elif 'DELETE' in method:
                test_scenarios.extend(['资源不存在', '权限检查'])

            plan['scenarios'].append({
                'route': f"{method} {path}",
                'handler': handler,
                'scenarios': test_scenarios,
                'priority': 'P0' if method in ['POST', 'PUT', 'DELETE'] else 'P1',
            })
            plan['estimated_test_count'] += len(test_scenarios)

        # 设置覆盖率目标
        plan['coverage_targets'] = {
            'P0': '100%',
            'P1': '≥80%',
            'P2': '≥50%',
            'line_coverage': '≥70%',
            'branch_coverage': '≥60%',
        }

        return plan

    def _extract_prd_keywords(self, text: str) -> List[str]:
        """从 PRD 文本提取关键词。"""
        parts = re.split(r'[，。、；:\s\n]+', text)
        keywords = []
        for p in parts:
            p = p.strip()
            if 2 <= len(p) <= 15:
                keywords.append(p)
        return list(dict.fromkeys(keywords))[:20]

    def generate_mock_strategy(self, func_name: str) -> Dict[str, Any]:
        """生成 Mock 策略文档。

        根据函数依赖链自动生成 Mock 策略，包括：
        - 需要 Mock 的层（DAO/Service/HTTP/RPC/Config/Redis/Time/Context）
        - Mock 返回值建议（智能推断）
        - Mock 边界条件（从 error_codes 提取）
        - 推荐的 Mock 模式

        Args:
            func_name: 函数名

        Returns:
            Mock 策略 dict
        """
        deps = self._get_dependencies(func_name)
        strategy = {
            'func': func_name,
            'mock_layers': {},
            'recommended_patterns': [],
            'boundary_conditions': [],
            'mock_return_values': {},
            'dependency_analysis': [],
        }

        # Analyze each dependency
        layer_map = {}
        for dep in deps:
            target = dep.get('target', '')
            if not target:
                continue
            target_lower = target.lower()

            # Classify dependency by layer with more granular matching
            # Order matters: check more specific patterns first
            if any(kw in target_lower for kw in ['dao', 'repo', 'mysql', 'sql']):
                layer = 'DAO'
            elif any(kw in target_lower for kw in ['redis', 'cache', 'memcache']):
                layer = 'Redis'
            elif any(kw in target_lower for kw in ['config', 'setting', 'env']):
                layer = 'Config'
            elif any(kw in target_lower for kw in ['http', 'client', 'api', 'external']):
                layer = 'HTTP'
            elif any(kw in target_lower for kw in ['rpc', 'grpc', 'proto']):
                layer = 'RPC'
            elif any(kw in target_lower for kw in ['time', 'date', 'now', 'clock']):
                layer = 'Time'
            elif any(kw in target_lower for kw in ['context', 'ctx', 'deadline']):
                layer = 'Context'
            elif any(kw in target_lower for kw in ['service', 'manager']):
                layer = 'Service'
            else:
                layer = 'Other'

            if layer not in layer_map:
                layer_map[layer] = []
            layer_map[layer].append(target)

            # Record dependency analysis
            strategy['dependency_analysis'].append({
                'target': target,
                'layer': layer,
                'call_type': dep.get('type', ''),
            })

        strategy['mock_layers'] = {k: list(set(v)) for k, v in layer_map.items()}

        # Generate recommended patterns per layer type
        layer_patterns = {
            'DAO': [
                'Use MagicMock for DAO methods',
                'Mock DB query results with realistic data shapes',
                'Test empty result sets (no rows found)',
                'Mock pagination parameters (limit/offset)',
                'Test unique constraint violations',
            ],
            'Service': [
                'Mock service method calls with chained returns',
                'Test service-level validation failures',
                'Mock side effects (e.g., event publishing)',
            ],
            'HTTP': [
                'Mock external API responses with success/error/status codes',
                'Test timeout scenarios (requests.exceptions.Timeout)',
                'Test malformed response handling',
                'Mock retry behavior on 5xx responses',
            ],
            'RPC': [
                'Mock gRPC stub methods with StatusCode',
                'Test RPC deadline exceeded errors',
                'Mock serialization/deserialization failures',
            ],
            'Config': [
                'Mock config values for different environments',
                'Test missing config key behavior',
                'Mock config type conversion errors',
            ],
            'Redis': [
                'Mock cache hit/miss scenarios',
                'Test cache serialization/deserialization errors',
                'Test cache TTL expiration behavior',
                'Mock Redis connection errors (ConnectionError)',
                'Test distributed lock scenarios',
            ],
            'Time': [
                'Use time mocking (freezegun / mock.patch.time)',
                'Test time-bound logic (expirations, schedules)',
                'Test clock skew scenarios',
            ],
            'Context': [
                'Test context cancellation mid-operation',
                'Test context deadline exceeded',
                'Test value extraction from context (user_id, tenant_id)',
            ],
            'Other': [
                'Identify the specific dependency and choose appropriate mock strategy',
            ],
        }

        for layer, patterns in layer_patterns.items():
            if layer in layer_map:
                strategy['recommended_patterns'].extend(patterns)

        # Add boundary conditions based on error_codes
        if self.error_codes:
            for ec in self.error_codes[:10]:
                if not isinstance(ec, dict):
                    continue
                desc = ec.get('description', '')
                code = ec.get('name', ec.get('code', ''))
                severity = ec.get('severity', 'ERROR')
                category = ec.get('category', '')

                if desc or code:
                    strategy['boundary_conditions'].append({
                        'error_code': code,
                        'scenario': desc[:80] if desc else code,
                        'severity': severity,
                        'category': category,
                    })

        # Smart mock return value inference from error_codes and dependencies
        strategy['mock_return_values'] = self._infer_mock_return_values(
            layer_map, deps
        )

        return strategy

    def _infer_mock_return_values(self, layer_map: Dict[str, List[str]],
                                   deps: List[Dict]) -> Dict[str, Any]:
        """根据依赖类型和 error_codes 智能推断 mock 返回值。"""
        return_values = {}

        # Infer from entity_tables for DAO return values
        for et in self.entity_tables[:5]:
            if not isinstance(et, dict):
                continue
            entity = et.get('entity', '')
            fields = et.get('fields', [])
            if entity and fields:
                sample_return = {}
                for f in fields[:6]:
                    if isinstance(f, dict):
                        fname = f.get('name', '')
                        ftype = f.get('type', 'string')
                        if fname:
                            sample_return[fname] = self._default_value_for_type(ftype)
                    elif isinstance(f, str):
                        sample_return[f] = '"sample-value"'
                if sample_return:
                    return_values[f'{entity}_dao'] = sample_return

        # Infer from struct definitions for Service return values
        for s in self.structs[:5]:
            if not isinstance(s, dict):
                continue
            sname = s.get('name', '')
            sfields = s.get('fields', [])
            if sname and sfields:
                sample_return = {}
                for sf in sfields[:5]:
                    if isinstance(sf, dict):
                        fname = sf.get('name', '')
                        ftype = sf.get('type', 'string')
                        if fname:
                            sample_return[fname] = self._default_value_for_type(ftype)
                    elif isinstance(sf, str):
                        sample_return[sf] = '"value"'
                if sample_return:
                    return_values[f'{sname}_service'] = sample_return

        # Error code-based return value suggestions
        for ec in self.error_codes[:5]:
            if not isinstance(ec, dict):
                continue
            code = ec.get('name', ec.get('code', ''))
            desc = ec.get('description', '')
            if code:
                return_values[f'{code}_response'] = {
                    'error_code': code,
                    'message': desc[:60] if desc else '',
                    'data': None,
                }

        return return_values

    def generate_data_preparation_strategy(self, func_name: str) -> Dict[str, Any]:
        """生成数据准备策略。

        根据函数签名和 IR 数据结构生成测试数据准备方案：
        - Fixture 模式（pytest fixture / Go TestMain）
        - Factory 模式（test factory functions）
        - Seeding 模式（数据库种子数据）
        - Transaction 模式（每个测试后回滚）
        - CleanSlate 模式（测试前清空）

        Args:
            func_name: 函数名

        Returns:
            数据准备策略 dict
        """
        target_func = self._find_function(func_name)
        strategy = {
            'func': func_name,
            'strategies': [],
            'fixture_suggestions': [],
            'seed_data_templates': [],
            'factory_patterns': [],
            'transaction_cleanup': [],
        }

        if not target_func:
            strategy['strategies'] = ['Use generic fixture pattern']
            return strategy

        # Analyze function signature to determine data needs
        sig = target_func.get('signature', '') or target_func.get('params', '')
        fields = target_func.get('fields', [])

        # Detect entity types from struct references
        entity_refs = set()
        for s in self.structs:
            if isinstance(s, dict):
                sname = s.get('name', '')
                if sname and sname.lower() in sig.lower():
                    entity_refs.add(sname)

        # Detect entity types from fields
        for f in fields:
            if isinstance(f, dict):
                fname = f.get('name', '')
                ftype = f.get('type', '')
                if ftype:
                    entity_refs.add(ftype)

        # Generate strategy recommendations
        if entity_refs:
            strategy['strategies'].append(
                'Transaction-based: wrap each test in transaction, rollback after'
            )
            strategy['strategies'].append(
                'Factory pattern: create helper functions for each entity type'
            )
            strategy['strategies'].append(
                'Seed data: pre-populate database with common test fixtures'
            )
            for entity in entity_refs:
                strategy['fixture_suggestions'].append(
                    f'{entity.lower()}_factory(): create valid {entity} instance'
                )
        else:
            strategy['strategies'].append('CleanSlate: reset state before each test')
            strategy['strategies'].append('Fixture: use pytest fixtures for shared setup')

        # Generate seed data templates from entity_tables
        for et in self.entity_tables[:8]:
            if not isinstance(et, dict):
                continue
            entity = et.get('entity', '')
            table = et.get('table', '')
            if not entity or not table:
                continue

            et_fields = et.get('fields', [])
            template = {
                'entity': entity,
                'table': table,
                'required_fields': [],
                'optional_fields': [],
                'sample_seed': {},
            }

            for f in et_fields[:10]:
                if isinstance(f, dict):
                    fname = f.get('name', '')
                    ftype = f.get('type', '')
                    is_pk = f.get('is_primary_key', False)
                    is_not_null = f.get('is_nullable', True)
                    default_val = f.get('default_value', '')
                    if fname:
                        if is_pk:
                            val = 'auto-generated UUID'
                            template['required_fields'].append(f'{fname}: {val}')
                            template['sample_seed'][fname] = '"uuid-xxxx-xxxx"'
                        elif default_val:
                            template['optional_fields'].append(f'{fname}: {default_val}')
                            template['sample_seed'][fname] = default_val
                        elif not is_not_null:
                            template['optional_fields'].append(
                                f'{fname}: {self._default_value_for_type(ftype)}'
                            )
                            template['sample_seed'][fname] = self._default_value_for_type(ftype)
                elif isinstance(f, str):
                    template['optional_fields'].append(f'{f}: "sample-value"')
                    template['sample_seed'][f] = '"sample-value"'

            if template['required_fields'] or template['optional_fields']:
                strategy['seed_data_templates'].append(template)

        # Generate factory pattern code suggestions
        if entity_refs or strategy['seed_data_templates']:
            all_entities = list(entity_refs)
            for sd in strategy['seed_data_templates']:
                ename = sd.get('entity', '')
                if ename and ename not in all_entities:
                    all_entities.append(ename)

            for entity in all_entities[:5]:
                factory_code = self._generate_factory_pattern(entity)
                if factory_code:
                    strategy['factory_patterns'].append(factory_code)

        # Generate transaction cleanup patterns
        strategy['transaction_cleanup'] = [
            {
                'python': '''@pytest.fixture(autouse=True)
def db_transaction(db_session):
    """Auto-rollback transaction after each test."""
    connection = db_session.connection()
    transaction = connection.begin()
    try:
        yield db_session
        transaction.rollback()
    finally:
        if transaction.is_active:
            transaction.rollback()''',
                'go': '''func TestMain(m *testing.M) {
    // Start transaction pool
    txnPool := NewTransactionPool()
    code := m.Run()
    txnPool.Cleanup()
    os.Exit(code)
}

func (s *Suite) SetupTest() {
    s.txn = s.db.Begin()
}

func (s *Suite) TearDownTest() {
    if s.txn != nil {
        s.txn.Rollback()
    }
}''',
            },
        ]

        return strategy

    def generate_integration_test_template(self, handler_name: str, route_info: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """生成端到端集成测试模板（HTTP handler → full stack）。

        生成一个完整的集成测试，覆盖从 HTTP 请求入口到数据库/缓存的完整链路：
        - Go: httptest + 真实依赖 mock
        - Python: FastAPI TestClient / requests_mock + fixture

        Args:
            handler_name: Handler 函数名
            route_info: 路由信息 dict（可选，从 IR routes 获取）

        Returns:
            集成测试代码 dict {'go': code, 'python': code, 'route': info, 'coverage': list}
        """
        target_func = self._find_function(handler_name)
        if not target_func:
            print(f"⚠️  Function '{handler_name}' not found in IR")
            return None

        dependencies = self._get_dependencies(handler_name)
        request_struct, request_fields, table_tests = self._extract_request_struct(target_func)
        error_codes = self._get_error_codes_for_function(handler_name)
        handler_service = handler_name.replace('Handler', '').replace('handler', '')

        # Detect HTTP method and path from routes
        http_method = 'POST'
        http_path = f'/{handler_name.lower()}'
        if route_info:
            http_method = route_info.get('method', 'POST')
            http_path = route_info.get('path', f'/{handler_name.lower()}')

        # Build integration test for both Go and Python
        go_integration = self._build_go_integration_test(
            handler_name, handler_service, request_struct, request_fields,
            table_tests, http_method, http_path, dependencies, error_codes
        )
        py_integration = self._build_py_integration_test(
            handler_name, handler_service, request_struct, request_fields,
            http_method, http_path, dependencies, error_codes
        )

        return {
            'go': go_integration,
            'python': py_integration,
            'route': {
                'method': http_method,
                'path': http_path,
                'handler': handler_name,
            },
            'coverage': [
                'HTTP handler entry point',
                'Request parsing and validation',
                'Service layer business logic',
                'DAO layer persistence',
                'Cache layer (Redis)',
                'Error handling and response formatting',
                'Transaction commit/rollback',
            ],
        }

    def _build_go_integration_test(self, handler_name: str, handler_service: str,
                                     request_struct: str, request_fields: str,
                                     table_tests: str, http_method: str, http_path: str,
                                     dependencies: List[Dict], error_codes: List[str]) -> str:
        """构建 Go 集成测试。"""
        # Build table-driven test rows with HTTP status codes
        test_rows = []
        # Normal success case
        test_rows.append(f'''{{
            name:       "success",
            method:     "{http_method}",
            path:       "{http_path}",
            body:       makeValidRequest(),
            wantStatus: http.StatusOK,
            wantErr:    false,
        }},''')

        # Error cases from error_codes
        for ec in error_codes[:3]:
            test_rows.append(f'''{{
            name:       "error_{ec.lower().replace("-", "_")}",
            method:     "{http_method}",
            path:       "{http_path}",
            body:       makeValidRequest(),
            wantStatus: http.StatusBadRequest,
            wantErr:    true,
        }},''')

        # Boundary: empty body
        test_rows.append(f'''{{
            name:       "empty_body",
            method:     "{http_method}",
            path:       "{http_path}",
            body:       nil,
            wantStatus: http.StatusBadRequest,
            wantErr:    true,
        }},''')

        # Boundary: invalid JSON
        test_rows.append(f'''{{
            name:       "invalid_json",
            method:     "{http_method}",
            path:       "{http_path}",
            body:       []byte("not-json"),
            wantStatus: http.StatusBadRequest,
            wantErr:    true,
        }},''')

        setup_code = ''
        for dep in dependencies:
            if dep['type'] == 'call':
                target = self._sanitize_identifier(dep.get('target', ''))
                setup_code += f'    router.HandleFunc("{http_path}", handler.{handler_name}).Methods("{http_method}")\n'

        return f'''// ============================================================================
// Integration Test: {handler_name} (HTTP → Full Stack)
// ============================================================================

import (
    "bytes"
    "encoding/json"
    "net/http"
    "net/http/httptest"
    "testing"

    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

func Test{handler_name}_Integration(t *testing.T) {{
    // 1. Setup full stack with mocks
    ctrl := gomock.NewController(t)
    defer ctrl.Finish()

{setup_code}
    // 2. Create router
    router := http.NewServeMux()
    handler := New{handler_service or "Handler"}(mockDao, mockService)
    router.HandleFunc("{http_path}", handler.{handler_name}).Methods("{http_method}")

    // 3. Table-driven integration tests
    tests := []struct {{
        name       string
        method     string
        path       string
        body       interface{{}}
        wantStatus int
        wantErr    bool
    }}{{
{table_tests}
    }}

    for _, tt := range tests {{
        t.Run(tt.name, func(t *testing.T) {{
            var bodyReader io.Reader
            if tt.body != nil {{
                data, err := json.Marshal(tt.body)
                require.NoError(t, err)
                bodyReader = bytes.NewReader(data)
            }}

            req := httptest.NewRequest(tt.method, tt.path, bodyReader)
            req.Header.Set("Content-Type", "application/json")
            w := httptest.NewRecorder()

            router.ServeHTTP(w, req)

            assert.Equal(t, tt.wantStatus, w.Code)
            if tt.wantErr {{
                assert.Contains(t, w.Body.String(), "error")
            }} else {{
                assert.NotEmpty(t, w.Body.String())
            }}
        }})
    }}
}}
'''

    def _build_py_integration_test(self, handler_name: str, handler_service: str,
                                    request_struct: str, request_fields: str,
                                    http_method: str, http_path: str,
                                    dependencies: List[Dict], error_codes: List[str]) -> str:
        """构建 Python 集成测试。"""
        # Build test scenarios
        scenarios = []
        scenarios.append(f'("success", "{http_method}", "{http_path}", make_valid_request(), 200, False)')
        for ec in error_codes[:3]:
            scenarios.append(f'("error_{ec.lower().replace("-", "_")}", "{http_method}", "{http_path}", make_valid_request(), 400, True)')
        scenarios.append(f'("empty_body", "{http_method}", "{http_path}", None, 400, True)')
        scenarios.append(f'("invalid_json", "{http_method}", "{http_path}", "not-json", 400, True)')

        return f'''# ============================================================================
# Integration Test: {handler_name} (HTTP → Full Stack)
# ============================================================================
import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport
{self._generate_imports(handler_name)}


@pytest.fixture
def app():
    """Create test application instance."""
    from src.main import create_app
    return create_app()


@pytest.fixture
async def client(app):
    """Create async HTTP client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
@pytest.mark.parametrize("name,method,path,payload,expected_status,expect_error", [
{chr(10).join("    " + s for s in scenarios)},
])
async def test_{handler_name}_integration(client, name, method, path, payload, expected_status, expect_error):
    """端到端集成测试 - scenario"""
    if isinstance(payload, dict):
        headers = {{"Content-Type": "application/json"}}
        response = await client.request(method, path, json=payload, headers=headers)
    elif payload is None:
        response = await client.request(method, path)
    else:
        headers = {{"Content-Type": "text/plain"}}
        response = await client.request(method, path, content=payload, headers=headers)

    assert response.status_code == expected_status
    if expect_error:
        body = response.json()
        assert "error" in str(body).lower() or "code" in str(body).lower()
    else:
        assert response.status_code == 200
'''

    def _generate_factory_pattern(self, entity: str) -> Optional[Dict[str, str]]:
        """为指定 entity 生成 factory pattern 代码建议。"""
        # Check if we have struct info for this entity
        struct_info = self.struct_map.get(entity, {})
        fields = struct_info.get('fields', []) if isinstance(struct_info, dict) else []

        if not fields:
            # Try entity_tables
            for et in self.entity_tables:
                if isinstance(et, dict) and et.get('entity', '').lower() == entity.lower():
                    fields = et.get('fields', [])
                    break

        if not fields:
            return None

        # Generate Python factory
        py_params = []
        py_body = []
        for f in fields[:6]:
            if isinstance(f, dict):
                fname = f.get('name', '')
                ftype = f.get('type', 'string')
                default = self._default_python_value(ftype)
                py_params.append(f'    {fname}: {default},')
                py_body.append(f'        {fname}={fname},')
            elif isinstance(f, str):
                py_params.append(f'    {f}=None,')
                py_body.append(f'        {f}={f},')

        return {
            'entity': entity,
            'python': f'''def make_{entity.lower()}({"".join(p.rstrip() for p in py_params)}) -> {entity}:
    """Factory function to create a valid {entity} instance for tests."""
    return {entity}(
{chr(10).join(py_body)}
    )''',
            'go': f'''// Make{entity} creates a valid {entity} instance for testing.
func Make{entity}() *{entity} {{
    return &{entity}{{
{chr(10).join("        " + p for p in py_params)}
    }}
}}''',
        }


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="自动测试代码生成器")
    parser.add_argument("--ir-cache", required=True, help="IR 缓存文件路径")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    parser.add_argument("--handlers", nargs='+', help="要生成测试的 handler 列表")
    parser.add_argument("--lang", default="go", choices=["go", "python"], help="目标语言")

    args = parser.parse_args()

    # 加载 IR 缓存
    ir_cache = json.loads(Path(args.ir_cache).read_text(encoding='utf-8'))

    # 创建生成器
    gen = TestCodeGenerator(ir_cache)

    # 确定要生成的 handlers
    handlers = args.handlers or []
    if not handlers:
        # 默认生成所有 route handler 的测试
        for route in ir_cache.get('routes', [])[:10]:
            if isinstance(route, dict):
                handler = route.get('handler', '')
                if handler:
                    handlers.append(handler.split('.')[-1])

    # 生成测试
    if args.lang == "go":
        for handler in handlers:
            code = gen.generate_go_test(handler)
            if code:
                output_path = Path(args.output_dir) / f"test_{handler.lower()}_test.go"
                output_path.write_text(code, encoding='utf-8')
                print(f"✅ Generated: {output_path}")
    else:
        for handler in handlers:
            snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', handler).lower()
            code = gen.generate_pytest(snake_name)
            if code:
                output_path = Path(args.output_dir) / f"test_{snake_name}.py"
                output_path.write_text(code, encoding='utf-8')
                print(f"✅ Generated: {output_path}")


if __name__ == "__main__":
    import json
    main()
