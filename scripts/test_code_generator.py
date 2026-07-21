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

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class TestCodeGenerator:
    """基于 IR 数据的测试代码生成器。"""

    # Go 测试模板 — 增强版：支持错误码断言和 table-driven tests
    GO_TEST_TEMPLATE = '''// {TestName} 测试{Description}
func Test{TestName}(t *testing.T) {{
    ctrl := gomock.NewController(t)
    defer ctrl.Finish()

    // 1. Mock {MockTarget} 层
{MockCode}

    // 2. 构造 handler
    handler := New{HandlerService}(mockDao, mockService)

    // 3. Table-driven tests
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
{ExecuteCode}
        }})
    }}
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

    # Python pytest 模板 — 增强版：支持 fixture、参数化、错误码断言
    PYTEST_TEMPLATE = '''import pytest
from unittest.mock import MagicMock, patch
{ImportCode}


@pytest.fixture
def mock_dependencies():
    """Mock 所有外部依赖"""
    mock_dao = MagicMock()
    mock_service = MagicMock()
    mock_redis = MagicMock()
    return mock_dao, mock_service, mock_redis


def test_{TestName}(mock_dependencies):
    """测试{Description} - 正常流程"""
    mock_dao, mock_service, mock_redis = mock_dependencies
{MockCode}
    # 2. 构造请求
    request = {RequestStruct}(
{RequestFields}
    )

    # 3. 执行
{ExecuteCode}

    # 4. 断言
{AssertCode}'''

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
            test_type: 测试类型 (success/exception/boundary)

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

        if test_type == "exception":
            return self._generate_go_exception_test(
                handler_name, dependencies, error_asserts, mock_code, handler_service
            )

        test_code = self.GO_TEST_TEMPLATE.format(
            TestName=f"{handler_name}_Success",
            Description=description,
            MockTarget=self._get_mock_target(dependencies),
            MockCode=mock_code,
            HandlerService=handler_service or "Handler",
            RequestStruct=request_struct or "Request",
            TableDrivenTests=table_tests,
            ExecuteCode=execute_code,
        )

        return test_code

    def generate_pytest(self, function_name: str, test_type: str = "success") -> Optional[str]:
        """为 Python 函数生成 pytest 测试代码。

        Args:
            function_name: 函数名（如 create_adgroup）
            test_type: 测试类型 (success/exception/boundary)

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
                # 尝试 Go
                go_code = self.generate_go_test(handler, test_type)
                if go_code:
                    safe_name = handler.lower().replace(' ', '_')
                    filename = f"test_{safe_name}_{test_type}.go"
                    results[filename] = go_code

                # 尝试 Python
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
            table_test_rows.append('''{
                name: "default",
                req: &{RequestStruct}{},
                wantErr: false,
            },'''.format(RequestStruct=struct_name or "Request"))

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
            desc = ec.get('description', '').lower()
            if func_lower in desc or any(kw in desc for kw in ['error', 'fail', 'err']):
                codes.append(ec.get('name', ec.get('code', 'UNKNOWN')))
        return codes[:5]

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
        parts = re.split(r'[，。、；：\s\n]+', text)
        keywords = []
        for p in parts:
            p = p.strip()
            if 2 <= len(p) <= 15:
                keywords.append(p)
        return list(dict.fromkeys(keywords))[:20]


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
