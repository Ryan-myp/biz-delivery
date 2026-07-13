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

    # Go 测试模板
    GO_TEST_TEMPLATE = '''// {TestName} 测试{Description}
func Test{TestName}(t *testing.T) {{
    // 1. Setup: 创建 mock 依赖
    ctrl := gomock.NewController(t)
    defer ctrl.Finish()

    // 2. Mock {MockTarget} 层
{MockCode}
    // 3. 构造请求
    req := &{RequestStruct}{{
{RequestFields}
    }}

    // 4. 执行
{ExecuteCode}

    // 5. 断言
{AssertCode}
}}'''

    # Python pytest 模板
    PYTEST_TEMPLATE = '''def test_{TestName}(mock_dao, mock_service):
    """测试{Description}"""
    # 1. Mock 依赖
{MockCode}
    # 2. 构造请求
    request = {RequestStruct}(
{RequestFields}
    )

    # 3. 执行
{ExecuteCode}

    # 4. 断言
{AssertCode}'''

    def __init__(self, ir_data: Dict[str, Any]):
        self.ir = ir_data
        self.functions = ir_data.get('functions', [])
        self.structs = ir_data.get('structs', [])
        self.routes = ir_data.get('routes', [])
        self.error_codes = ir_data.get('error_codes', [])
        self.call_graph = ir_data.get('call_graph', [])
        self.entity_tables = ir_data.get('entity_tables', [])
        
        # 构建函数名 → 文件映射
        self.func_to_file = {}
        for func in self.functions:
            if isinstance(func, dict):
                fname = func.get('name', '')
                ffile = func.get('file', '')
                if fname and ffile:
                    self.func_to_file[fname] = ffile
        
        # 构建 struct 映射
        self.struct_map = {}
        for s in self.structs:
            if isinstance(s, dict):
                sname = s.get('name', '')
                if sname:
                    self.struct_map[sname] = s
    
    def generate_go_test(self, handler_name: str, test_type: str = "success") -> Optional[str]:
        """为 Go handler 生成测试代码。
        
        Args:
            handler_name: Handler 函数名（如 CreateAdGroup）
            test_type: 测试类型 (success/exception/boundary)
            
        Returns:
            生成的 Go 测试代码，如果未找到匹配则返回 None
        """
        # 查找匹配的函数
        target_func = self._find_function(handler_name)
        if not target_func:
            print(f"⚠️  Function '{handler_name}' not found in IR")
            return None
        
        # 获取依赖链
        dependencies = self._get_dependencies(handler_name)
        
        # 生成 Mock 代码
        mock_code = self._generate_go_mock(dependencies)
        
        # 生成请求结构
        request_struct, request_fields = self._extract_request_struct(target_func)
        
        # 生成执行代码
        execute_code = self._generate_go_execute(handler_name, dependencies)
        
        # 生成断言代码
        assert_code = self._generate_go_assert(test_type, handler_name)
        
        # 组装完整测试
        description = self._describe_test(handler_name, test_type)
        test_code = self.GO_TEST_TEMPLATE.format(
            TestName=f"{handler_name}_{test_type.capitalize()}",
            Description=description,
            MockTarget=self._get_mock_target(dependencies),
            MockCode=mock_code,
            RequestStruct=request_struct or "Request",
            RequestFields=request_fields,
            ExecuteCode=execute_code,
            AssertCode=assert_code,
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
        execute_code = self._generate_pytest_execute(function_name)
        assert_code = self._generate_pytest_assert(test_type)
        
        description = self._describe_test(function_name, test_type)
        test_code = self.PYTEST_TEMPLATE.format(
            TestName=function_name.replace('-', '_').replace(' ', '_'),
            Description=description,
            MockCode=mock_code,
            RequestStruct=request_struct or "Request",
            RequestFields=request_fields,
            ExecuteCode=execute_code,
            AssertCode=assert_code,
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
                if handler[0].isupper():
                    snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', handler).lower()
                else:
                    snake_name = handler
                py_code = self.generate_pytest(snake_name, test_type)
                if py_code:
                    filename = f"test_{snake_name}_{test_type}.py"
                    results[filename] = py_code
        
        return results
    
    def _find_function(self, name: str) -> Optional[Dict]:
        """在 IR 中查找匹配的函数。"""
        name_lower = name.lower()
        for func in self.functions:
            if not isinstance(func, dict):
                continue
            fname = func.get('name', '').lower()
            if name_lower == fname or name_lower in fname or fname in name_lower:
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
    
    def _generate_go_mock(self, dependencies: List[Dict]) -> str:
        """生成 Go gomock 代码。"""
        lines = []
        for dep in dependencies:
            if dep['type'] == 'call':
                target = dep['target']
                # 猜测接口名
                interface_name = f"Mock{target}"
                lines.append(f'    mock{interface_name} := NewMock{interface_name}(ctrl)')
                lines.append(f'    mock{interface_name}.EXPECT().AnyMatch(gomock.Any()).Return(nil)')
        
        if not lines:
            lines.append('    // No external dependencies to mock')
        
        return '\n'.join(f'    {line}' for line in lines)
    
    def _generate_pytest_mock(self, dependencies: List[Dict]) -> str:
        """生成 Python pytest mock 代码。"""
        lines = []
        for dep in dependencies:
            if dep['type'] == 'call':
                target = dep['target']
                lines.append(f'    mock_{target}.return_value = MagicMock()')
        
        if not lines:
            lines.append('    # No external dependencies to mock')
        
        return '\n'.join(f'    {line}' for line in lines)
    
    def _extract_request_struct(self, func: Dict) -> tuple:
        """从函数签名中提取 Request struct 信息。"""
        sig = func.get('signature', '') or func.get('params', '')
        fields = func.get('fields', [])
        
        struct_name = ''
        field_lines = []
        
        # 解析参数中的 struct 类型
        struct_match = re.findall(r'\*?(\w+)Request', sig)
        if struct_match:
            struct_name = struct_match[0]
        
        # 从 fields 提取字段
        if isinstance(fields, list):
            for f in fields[:5]:
                if isinstance(f, dict):
                    fname = f.get('name', '')
                    ftype = f.get('type', 'string')
                    if fname:
                        json_tag = f.get('json_tag', '')
                        field_lines.append(f'        {fname}: "{fname}", // TODO: fill actual value')
                elif isinstance(f, str):
                    field_lines.append(f'        {f}: "{f}", // TODO: fill actual value')
        
        if not field_lines:
            field_lines.append('        // TODO: construct request fields based on actual struct')
        
        return struct_name, '\n'.join(field_lines)
    
    def _extract_pytest_request(self, func: Dict) -> tuple:
        """从函数签名中提取 Python Request 信息。"""
        sig = func.get('signature', '') or func.get('params', '')
        fields = func.get('fields', [])
        
        struct_name = ''
        field_lines = []
        
        # 解析参数
        param_match = re.findall(r'(\w+):\s*(\w+)', sig)
        for pname, ptype in param_match[:5]:
            default = '"value"' if ptype == 'str' else '0'
            field_lines.append(f'        {pname}={default},')
        
        if not field_lines:
            field_lines.append('        # TODO: construct request based on actual function signature')
        
        return struct_name, '\n'.join(field_lines)
    
    def _generate_go_execute(self, handler: str, deps: List[Dict]) -> str:
        """生成 Go 执行代码。"""
        return f'    result, err := handler.{handler}(context.Background(), req)'
    
    def _generate_pytest_execute(self, func_name: str) -> str:
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
            return '''    // TODO: add boundary condition assertions'''
    
    def _generate_pytest_assert(self, test_type: str) -> str:
        """生成 Python 断言代码。"""
        if test_type == "success":
            return '''    assert result is not None
    assert result.id == 1
    # mock_dao.insert.assert_called_once()'''
        elif test_type == "exception":
            return '''    with pytest.raises(Exception):
        handler.some_method(request)'''
        else:
            return '''    # TODO: add boundary condition assertions'''
    
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
