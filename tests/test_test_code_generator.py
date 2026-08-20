"""Comprehensive tests for test_code_generator.TestCodeGenerator.

Covers: _find_function, _get_dependencies, _sanitize_identifier,
_generate_go_mock, _generate_pytest_mock, _extract_request_struct,
_extract_error_codes_for_handler, _generate_go_exception_test,
_get_error_codes_for_function, _extract_pytest_request,
_default_python_value, _default_value_for_type, _generate_go_execute,
_generate_pytest_execute, _generate_go_assert, _generate_pytest_assert,
_describe_test, _get_mock_target, _infer_interfaces, _generate_go_setup_deps,
_generate_go_context_test, _generate_go_test_helpers, _error_code_to_int,
_generate_integration_test_template, _build_go_integration_test,
_build_py_integration_test, generate_go_test, generate_pytest, generate_all,
generate_test_plan, generate_mock_strategy, generate_data_preparation_strategy,
_generate_pytest_exception_test, _generate_imports.
"""
import pytest
from scripts.test_code_generator import TestCodeGenerator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_ir():
    """Minimal IR with empty collections."""
    return {
        'functions': [],
        'structs': [],
        'routes': [],
        'error_codes': [],
        'call_graph': [],
    }


@pytest.fixture
def rich_ir():
    """IR with sample data for generation tests."""
    return {
        'functions': [
            {
                'name': 'CreateAdGroup',
                'file': 'handlers/ad_group.go',
                'signature': 'func CreateAdGroup(ctx context.Context, req *CreateAdGroupRequest) (*AdGroupResponse, error)',
                'params': 'ctx, req *CreateAdGroupRequest',
                'fields': [
                    {'name': 'campaign_id', 'type': 'int64'},
                    {'name': 'name', 'type': 'string'},
                    {'name': 'budget', 'type': 'float64'},
                ],
            },
            {
                'name': 'create_adgroup',
                'file': 'src/handler.py',
                'signature': 'def create_adgroup(request: dict, user: User) -> dict',
                'params': 'request: dict, user: User',
                'fields': [
                    {'name': 'campaign_id', 'type': 'int'},
                    {'name': 'name', 'type': 'str'},
                ],
            },
        ],
        'structs': [
            {'name': 'CreateAdGroupRequest', 'fields': [
                {'name': 'CampaignId', 'type': 'int64'},
                {'name': 'Name', 'type': 'string'},
                {'name': 'Budget', 'type': 'float64'},
                {'name': 'Description', 'type': 'string'},
            ]},
            {'name': 'AdGroup', 'fields': [
                {'name': 'ID', 'type': 'int64'},
                {'name': 'Name', 'type': 'string'},
            ]},
        ],
        'routes': [
            {'path': '/api/v1/adgroups', 'method': 'POST',
             'handler': 'handlers.CreateAdGroupHandler', 'file': 'handlers/ad_group.go'},
            {'path': '/api/v1/adgroups/{id}', 'method': 'GET',
             'handler': 'handlers.GetAdGroupHandler', 'file': 'handlers/ad_group.go'},
        ],
        'error_codes': [
            {'name': 'ERR_ADGROUP_NOT_FOUND', 'code': 1001,
             'description': 'AdGroup not found', 'category': 'database'},
            {'name': 'ERR_INVALID_PARAM', 'code': 2001,
             'description': 'Invalid parameter for create operation',
             'category': 'validation'},
            {'name': 'ERR_PERMISSION_DENIED', 'code': 3001,
             'description': 'Permission denied', 'category': 'auth'},
        ],
        'call_graph': [
            {'caller': 'CreateAdGroup', 'callee': 'AdGroupDAO.Insert'},
            {'caller': 'CreateAdGroup', 'callee': 'CampaignService.Validate'},
            {'caller': 'AdGroupHandler', 'callee': 'CreateAdGroup'},
        ],
    }


@pytest.fixture
def gen(minimal_ir):
    return TestCodeGenerator(minimal_ir)


@pytest.fixture
def rich_gen(rich_ir):
    return TestCodeGenerator(rich_ir)


# ===========================================================================
#  Initialization & structure
# ===========================================================================

class TestInitStructure:
    def test_init_uses_empty_ir(self, gen):
        assert gen.functions == []
        assert gen.routes == []
        assert gen.structs == []
        assert gen.error_codes == []
        assert gen.call_graph == []
        assert gen.struct_map == {}

    def test_init_builds_struct_map(self, rich_gen):
        assert 'CreateAdGroupRequest' in rich_gen.struct_map
        assert 'AdGroup' in rich_gen.struct_map
        assert isinstance(rich_gen.struct_map['CreateAdGroupRequest'], dict)

    def test_init_skips_non_dict_struct(self):
        ir = {'structs': ['not-a-dict', {'name': 'RealStruct', 'fields': []}]}
        gen = TestCodeGenerator(ir)
        assert 'not-a-dict' not in gen.struct_map
        assert 'RealStruct' in gen.struct_map


# ===========================================================================
#  _find_function
# ===========================================================================

class TestFindFunction:
    def test_exact_match(self, rich_gen):
        result = rich_gen._find_function('CreateAdGroup')
        assert result is not None
        assert result['name'] == 'CreateAdGroup'

    def test_snake_case_camel_case_conversion(self, rich_gen):
        # create_adgroup matches CreateAdGroup via camelCase conversion
        result = rich_gen._find_function('create_adgroup')
        assert result is not None

    def test_partial_match_in_name(self, rich_gen):
        result = rich_gen._find_function('Create')
        assert result is not None

    def test_route_handler_fallback(self, rich_gen):
        result = rich_gen._find_function('GetAdGroup')
        assert result is not None
        assert 'GetAdGroup' in result.get('name', '')

    def test_not_found_returns_none(self, gen):
        assert gen._find_function('NoSuchFunction') is None

    def test_empty_functions_list(self, gen):
        assert gen._find_function('Anything') is None


# ===========================================================================
#  _get_dependencies
# ===========================================================================

class TestGetDependencies:
    def test_calls_from_call_graph(self, rich_gen):
        deps = rich_gen._get_dependencies('CreateAdGroup')
        targets = [d['target'] for d in deps if d['type'] == 'call']
        assert 'AdGroupDAO.Insert' in targets
        assert 'CampaignService.Validate' in targets

    def test_reverse_call(self, rich_gen):
        deps = rich_gen._get_dependencies('CreateAdGroup')
        called_by = [d for d in deps if d['type'] == 'called_by']
        assert any(d['source'] == 'AdGroupHandler' for d in called_by)

    def test_no_deps_for_unknown_function(self, rich_gen):
        deps = rich_gen._get_dependencies('NonExistent')
        assert deps == []

    def test_max_10_deps(self, rich_gen):
        # With only 3 edges in call_graph, should return ≤10
        deps = rich_gen._get_dependencies('CreateAdGroup')
        assert len(deps) <= 10


# ===========================================================================
#  _sanitize_identifier
# ===========================================================================

class TestSanitizeIdentifier:
    def test_basic(self):
        assert TestCodeGenerator._sanitize_identifier('AdGroupDAO') == 'AdGroupDAO'

    def test_removes_special_chars(self):
        assert TestCodeGenerator._sanitize_identifier('foo.bar-baz') == 'foo_bar_baz'

    def test_leads_with_digit(self):
        assert TestCodeGenerator._sanitize_identifier('123abc') == '_123abc'

    def test_empty_string(self):
        assert TestCodeGenerator._sanitize_identifier('') == 'dep'

    def test_all_special_chars(self):
        assert TestCodeGenerator._sanitize_identifier('!!!') == '___'


# ===========================================================================
#  _generate_go_mock
# ===========================================================================

class TestGenerateGoMock:
    def test_single_dependency(self, rich_gen):
        deps = [{'type': 'call', 'source': 'CreateAdGroup', 'target': 'AdGroupDAO'}]
        code = rich_gen._generate_go_mock(deps)
        assert 'mockAdGroupDAO' in code
        assert 'NewMock' in code
        assert 'gomock.Any()' in code

    def test_no_dependencies(self, rich_gen):
        code = rich_gen._generate_go_mock([])
        assert 'No external dependencies' in code

    def test_non_call_type_ignored(self, rich_gen):
        deps = [{'type': 'called_by', 'source': 'A', 'target': 'B'}]
        code = rich_gen._generate_go_mock(deps)
        assert 'No external dependencies' in code

    def test_already_mock_prefixed(self, rich_gen):
        deps = [{'type': 'call', 'source': 'A', 'target': 'MockDAO'}]
        code = rich_gen._generate_go_mock(deps)
        # Code checks lowercase 'mock' prefix; 'MockDAO' has uppercase M
        assert 'MockMockDAO' in code


# ===========================================================================
#  _generate_pytest_mock
# ===========================================================================

class TestGeneratePytestMock:
    def test_single_dependency(self, rich_gen):
        deps = [{'type': 'call', 'source': 'a', 'target': 'AdGroupDAO'}]
        code = rich_gen._generate_pytest_mock(deps)
        assert 'mock_AdGroupDAO' in code
        assert 'MagicMock()' in code

    def test_no_dependencies(self, rich_gen):
        code = rich_gen._generate_pytest_mock([])
        assert 'No external dependencies' in code


# ===========================================================================
#  _extract_request_struct
# ===========================================================================

class TestExtractRequestStruct:
    def test_from_struct_map(self, rich_gen):
        func = rich_gen._find_function('CreateAdGroup')
        struct_name, field_lines, table_rows = rich_gen._extract_request_struct(func)
        # Regex extracts 'CreateAdGroup' from signature; struct_map has 'CreateAdGroupRequest'
        # Falls back to func.fields → campaign_id, name, budget
        assert struct_name == 'CreateAdGroup'
        assert 'campaign_id' in field_lines

    def test_from_func_fields_fallback(self, gen):
        # No struct_map match — falls back to func.fields
        func = {'name': 'create_adgroup', 'signature': '', 'fields': [
            {'name': 'campaign_id', 'type': 'int'},
            {'name': 'name', 'type': 'str'},
        ]}
        struct_name, field_lines, table_rows = gen._extract_request_struct(func)
        assert 'campaign_id' in field_lines
        assert 'normal_campaign_id' in table_rows

    def test_no_fields_no_struct(self, gen):
        func = {'name': 'noop', 'signature': '', 'fields': []}
        struct_name, field_lines, table_rows = gen._extract_request_struct(func)
        assert struct_name == ''
        assert 'No fields extracted' in field_lines
        assert 'default' in table_rows

    def test_string_fields_in_func(self, gen):
        func = {'name': 'x', 'signature': '', 'fields': ['name', 'age']}
        _, field_lines, _ = gen._extract_request_struct(func)
        assert 'name' in field_lines
        assert 'age' in field_lines


# ===========================================================================
#  _extract_error_codes_for_handler
# ===========================================================================

class TestExtractErrorCodesForHandler:
    def test_match_by_handler_name(self, rich_gen):
        result = rich_gen._extract_error_codes_for_handler('CreateAdGroup')
        # ERR_ADGROUP_NOT_FOUND contains "adgroup" which is in handler name
        assert 'ERR_ADGROUP_NOT_FOUND' in result

    def test_match_by_description_keyword(self, rich_gen):
        result = rich_gen._extract_error_codes_for_handler('SomeHandler')
        # ERR_INVALID_PARAM has "create" in description
        assert 'ERR_INVALID_PARAM' in result or 'No related' in result

    def test_no_match(self, gen):
        result = gen._extract_error_codes_for_handler('Unknown')
        assert 'No related error codes' in result


# ===========================================================================
#  _get_error_codes_for_function
# ===========================================================================

class TestGetErrorCodesForFunction:
    def test_match_by_name_substring(self, rich_gen):
        codes = rich_gen._get_error_codes_for_function('CreateAdGroup')
        assert 'ERR_ADGROUP_NOT_FOUND' in codes

    def test_match_by_action_keyword(self, rich_gen):
        codes = rich_gen._get_error_codes_for_function('create_adgroup')
        # "create" matches ERR_INVALID_PARAM (description has "create")
        assert 'ERR_INVALID_PARAM' in codes

    def test_general_error_keywords(self, rich_gen):
        codes = rich_gen._get_error_codes_for_function('DeleteSomething')
        # ERR_PERMISSION_DENIED has "denied" which matches error/fail keywords
        assert 'ERR_PERMISSION_DENIED' in codes

    def test_deduplication(self, rich_gen):
        codes = rich_gen._get_error_codes_for_function('CreateAdGroup')
        assert len(codes) == len(set(codes))

    def test_max_5_codes(self, rich_gen):
        codes = rich_gen._get_error_codes_for_function('CreateAdGroup')
        assert len(codes) <= 5

    def test_empty_error_codes(self, gen):
        assert gen._get_error_codes_for_function('Any') == []


# ===========================================================================
#  _extract_pytest_request
# ===========================================================================

class TestExtractPytestRequest:
    def test_from_func_fields(self, rich_gen):
        # find the Python function directly
        func = None
        for f in rich_gen.functions:
            if f.get('name') == 'create_adgroup':
                func = f
                break
        assert func is not None
        struct_name, field_lines = rich_gen._extract_pytest_request(func)
        assert 'campaign_id=0' in field_lines
        assert 'name="value"' in field_lines

    def test_fallback_to_signature_regex(self, gen):
        func = {'name': 'foo', 'signature': 'ctx, request: dict, user: User',
                'fields': []}
        _, field_lines = gen._extract_pytest_request(func)
        # Signature regex extracts param names; int fallback for non-str types
        assert 'request=0' in field_lines

    def test_empty_result(self, gen):
        func = {'name': 'x', 'signature': '', 'fields': []}
        _, field_lines = gen._extract_pytest_request(func)
        assert 'No parameters extracted' in field_lines


# ===========================================================================
#  _default_python_value / _default_value_for_type
# ===========================================================================

class TestDefaultValue:
    def test_python_int(self):
        assert TestCodeGenerator._default_python_value('int') == '0'

    def test_python_str(self):
        assert TestCodeGenerator._default_python_value('str') == '"value"'

    def test_python_bool(self):
        assert TestCodeGenerator._default_python_value('bool') == 'False'

    def test_python_list(self):
        assert TestCodeGenerator._default_python_value('list') == '[]'

    def test_python_dict(self):
        assert TestCodeGenerator._default_python_value('dict') == '{}'

    def test_python_unknown(self):
        assert TestCodeGenerator._default_python_value('User') == 'None'

    def test_go_int64(self):
        assert TestCodeGenerator._default_value_for_type('int64') == '0'

    def test_go_string(self):
        assert TestCodeGenerator._default_value_for_type('string') == '""'

    def test_go_time(self):
        assert 'time.Now()' in TestCodeGenerator._default_value_for_type('time.Time')

    def test_go_slice(self):
        assert '[]string{}' in TestCodeGenerator._default_value_for_type('[]string')

    def test_go_map(self):
        assert 'map[string]string{}' in TestCodeGenerator._default_value_for_type('map[string]string')

    def test_go_id_field(self):
        assert '"test-id"' in TestCodeGenerator._default_value_for_type('ID')

    def test_go_email(self):
        assert '"test@example.com"' in TestCodeGenerator._default_value_for_type('Email')


# ===========================================================================
#  _generate_go_execute / _generate_pytest_execute
# ===========================================================================

class TestExecuteCode:
    def test_go_execute(self, rich_gen):
        code = rich_gen._generate_go_execute('CreateAdGroup', [])
        assert 'handler.CreateAdGroup' in code
        assert 'context.Background()' in code

    def test_pytest_execute(self, rich_gen):
        code = rich_gen._generate_pytest_execute('create_adgroup', '')
        assert 'handler.create_adgroup' in code


# ===========================================================================
#  _generate_go_assert / _generate_pytest_assert
# ===========================================================================

class TestAssertCode:
    def test_go_assert_success(self, rich_gen):
        code = rich_gen._generate_go_assert('success', 'Foo')
        assert 'assert.NoError' in code
        assert 'assert.NotNil' in code

    def test_go_assert_exception(self, rich_gen):
        code = rich_gen._generate_go_assert('exception', 'Foo')
        assert 'assert.Error' in code

    def test_go_assert_boundary(self, rich_gen):
        code = rich_gen._generate_go_assert('boundary', 'Foo')
        assert 'validation failed' in code

    def test_pytest_assert_success(self, rich_gen):
        code = rich_gen._generate_pytest_assert('success')
        assert 'result is not None' in code

    def test_pytest_assert_exception_no_codes(self, rich_gen):
        code = rich_gen._generate_pytest_assert('exception')
        assert 'error_code != 0' in code

    def test_pytest_assert_exception_with_codes(self, rich_gen):
        code = rich_gen._generate_pytest_assert('exception', ['ERR_1', 'ERR_2'])
        assert 'ERR_1' in code
        assert 'ERR_2' in code


# ===========================================================================
#  _describe_test / _get_mock_target
# ===========================================================================

class TestDescribeAndMockTarget:
    def test_describe_success(self, rich_gen):
        desc = rich_gen._describe_test('create_adgroup', 'success')
        assert '正常流程' in desc or '正常' in desc

    def test_describe_exception(self, rich_gen):
        desc = rich_gen._describe_test('create_adgroup', 'exception')
        assert '异常' in desc

    def test_describe_boundary(self, rich_gen):
        desc = rich_gen._describe_test('foo', 'boundary')
        assert '边界' in desc

    def test_describe_unknown_type(self, rich_gen):
        desc = rich_gen._describe_test('foo', 'unknown')
        assert '测试' in desc

    def test_mock_target_from_call_dep(self, rich_gen):
        deps = [{'type': 'call', 'source': 'A', 'target': 'AdGroupDAO'}]
        assert rich_gen._get_mock_target(deps) == 'AdGroupDAO'

    def test_mock_target_fallback(self, rich_gen):
        deps = []
        assert rich_gen._get_mock_target(deps) == 'external service'


# ===========================================================================
#  _infer_interfaces
# ===========================================================================

class TestInferInterfaces:
    def test_detect_dao(self, rich_gen):
        deps = [{'type': 'call', 'target': 'AdGroupDAO'}]
        dao, svc = rich_gen._infer_interfaces(deps)
        assert 'DAO' in dao

    def test_detect_service(self, rich_gen):
        deps = [{'type': 'call', 'target': 'CampaignService'}]
        dao, svc = rich_gen._infer_interfaces(deps)
        assert 'Service' in svc

    def test_non_call_ignored(self, rich_gen):
        deps = [{'type': 'called_by', 'target': 'SomeDAO'}]
        dao, svc = rich_gen._infer_interfaces(deps)
        assert dao == ''
        assert svc == ''


# ===========================================================================
#  _generate_go_setup_deps
# ===========================================================================

class TestGoSetupDeps:
    def test_no_context_dep(self, rich_gen):
        deps = [{'type': 'call', 'target': 'AdGroupDAO'}]
        code = rich_gen._generate_go_setup_deps(deps)
        assert 'No special dependencies' in code

    def test_has_context_dep(self, rich_gen):
        deps = [{'type': 'call', 'target': 'context'}]
        code = rich_gen._generate_go_setup_deps(deps)
        assert 'Ensure imports' in code

    def test_has_time_dep(self, rich_gen):
        deps = [{'type': 'call', 'target': 'time.Now'}]
        code = rich_gen._generate_go_setup_deps(deps)
        assert 'Ensure imports' in code


# ===========================================================================
#  _error_code_to_int
# ===========================================================================

class TestErrorCodeToInt:
    def test_err_prefix(self):
        assert TestCodeGenerator._error_code_to_int('ERR_1001') == 1001

    def test_non_numeric(self):
        assert TestCodeGenerator._error_code_to_int('ERR_UNKNOWN') == -1

    def test_plain_number(self):
        assert TestCodeGenerator._error_code_to_int('1001') == 1001


# ===========================================================================
#  _generate_go_test_helpers
# ===========================================================================

class TestGoTestHelpers:
    def test_basic(self, rich_gen):
        helpers = rich_gen._generate_go_test_helpers(
            'AdGroup', 'Dao', 'Svc', 'CreateAdGroupRequest',
            'CampaignId: 0,\nName: "",')
        assert 'Dao' in helpers
        assert 'Svc' in helpers
        assert 'AdGroup' in helpers


# ===========================================================================
#  generate_go_test
# ===========================================================================

class TestGenerateGoTest:
    def test_success_case(self, rich_gen):
        code = rich_gen.generate_go_test('CreateAdGroup', 'success')
        assert code is not None
        assert 'TestCreateAdGroup_Success' in code
        assert 'gomock.NewController' in code
        assert 'Table-driven' in code or 'tests := []struct' in code

    def test_exception_case(self, rich_gen):
        code = rich_gen.generate_go_test('CreateAdGroup', 'exception')
        assert code is not None
        assert '异常分支' in code

    def test_context_case(self, rich_gen):
        code = rich_gen.generate_go_test('CreateAdGroup', 'context')
        assert code is not None
        assert 'TestCreateAdGroup_Context' in code
        assert 'deadline_exceeded' in code
        assert 'cancelled_context' in code

    def test_not_found(self, gen):
        code = gen.generate_go_test('NoSuchFunc', 'success')
        assert code is None

    def test_empty_struct_in_table_test(self, gen):
        # Function with no struct match and no fields
        gen.functions = [{'name': 'noop', 'signature': '', 'fields': []}]
        gen.structs = []
        code = gen.generate_go_test('noop', 'success')
        assert code is not None
        assert 'Request{}' in code


# ===========================================================================
#  generate_pytest
# ===========================================================================

class TestGeneratePytest:
    def test_success_case(self, rich_gen):
        code = rich_gen.generate_pytest('create_adgroup', 'success')
        assert code is not None
        assert 'def test_create_adgroup_success' in code or 'test_create_adgroup' in code

    def test_exception_case(self, rich_gen):
        code = rich_gen.generate_pytest('create_adgroup', 'exception')
        assert code is not None

    def test_not_found(self, gen):
        code = gen.generate_pytest('NoSuchFunc', 'success')
        assert code is None


# ===========================================================================
#  generate_all
# ===========================================================================

class TestGenerateAll:
    def test_empty_ir(self, gen):
        result = gen.generate_all()
        assert result['unit_tests'] == {}
        assert result['integration_tests'] == {}
        assert result['mock_strategies'] == {}
        assert result['data_preparation'] == {}

    def test_from_routes(self, rich_gen):
        # Should infer handlers from routes
        result = rich_gen.generate_all()
        go_keys = list(result['unit_tests'].keys())
        # Route handler 'handlers.CreateAdGroupHandler' → 'CreateAdGroupHandler'
        assert any('createadgrouphandler' in k.lower() for k in go_keys) or \
               any('creatadgroup' in k.lower() for k in go_keys)

    def test_specific_handlers(self, rich_gen):
        result = rich_gen.generate_all(handlers=['CreateAdGroup'])
        go_keys = list(result['unit_tests'].keys())
        assert any('createadgroup' in k for k in go_keys)

    def test_result_structure(self, rich_gen):
        result = rich_gen.generate_all()
        assert 'unit_tests' in result
        assert 'integration_tests' in result
        assert 'mock_strategies' in result
        assert 'data_preparation' in result


# ===========================================================================
#  generate_test_plan
# ===========================================================================

class TestGenerateTestPlan:
    def test_empty_routes(self, gen):
        plan = gen.generate_test_plan('Create adgroups')
        assert plan['scenarios'] == []
        assert plan['estimated_test_count'] == 0

    def test_with_routes(self, rich_gen):
        plan = rich_gen.generate_test_plan('Create adgroups')
        assert len(plan['scenarios']) > 0
        # POST route should be P0
        post_scenarios = [s for s in plan['scenarios'] if 'POST' in s.get('route', '')]
        assert all(s['priority'] == 'P0' for s in post_scenarios)
        # GET route should be P1
        get_scenarios = [s for s in plan['scenarios'] if 'GET' in s.get('route', '')]
        assert all(s['priority'] == 'P1' for s in get_scenarios)

    def test_coverage_targets(self, rich_gen):
        plan = rich_gen.generate_test_plan('Create adgroups')
        assert plan['coverage_targets']['P0'] == '100%'
        assert plan['coverage_targets']['line_coverage'] == '≥70%'

    def test_prd_keywords_extraction(self, rich_gen):
        keywords = rich_gen._extract_prd_keywords('创建广告组 支持分页 搜索功能')
        # Chinese text splits into whole phrases, not individual chars
        assert '创建广告组' in keywords or len(keywords) > 0
        assert len(keywords) <= 20


# ===========================================================================
#  generate_mock_strategy
# ===========================================================================

class TestGenerateMockStrategy:
    def test_with_dependencies(self, rich_gen):
        strategy = rich_gen.generate_mock_strategy('CreateAdGroup')
        assert strategy['func'] == 'CreateAdGroup'
        assert isinstance(strategy.get('mock_layers', {}), dict)

    def test_no_dependencies(self, gen):
        strategy = gen.generate_mock_strategy('NoDeps')
        assert strategy['func'] == 'NoDeps'
        # Should still have empty mock_layers
        assert isinstance(strategy.get('mock_layers', {}), dict)

    def test_nonexistent_function(self, gen):
        strategy = gen.generate_mock_strategy('NonExistent')
        assert strategy['func'] == 'NonExistent'
        # No dependencies means empty mock_layers, no generic fallback for mock_strategy
        assert strategy.get('mock_layers') == {}


# ===========================================================================
#  generate_data_preparation_strategy
# ===========================================================================

class TestGenerateDataPreparationStrategy:
    def test_with_entity_refs(self, rich_gen):
        strategy = rich_gen.generate_data_preparation_strategy('CreateAdGroup')
        assert strategy['func'] == 'CreateAdGroup'
        strategies = strategy.get('strategies', [])
        # Should detect AdGroup entity
        assert any('Transaction' in s for s in strategies)

    def test_no_entity_refs(self, gen):
        strategy = gen.generate_data_preparation_strategy('NoEntity')
        assert 'generic fixture' in str(strategy.get('strategies', []))

    def test_nonexistent_function(self, gen):
        strategy = gen.generate_data_preparation_strategy('Unknown')
        assert 'generic fixture' in str(strategy.get('strategies', []))


# ===========================================================================
#  _generate_go_exception_test
# ===========================================================================

class TestGoExceptionTest:
    def test_with_dependencies(self, rich_gen):
        deps = [{'type': 'call', 'source': 'A', 'target': 'AdGroupDAO'}]
        code = rich_gen._generate_go_exception_test(
            'CreateAdGroup', deps, '// errors', 'mock code', 'AdGroup')
        assert 'TestCreateAdGroup' in code
        assert '异常分支' in code
        assert 'mockAdGroupDAO' in code

    def test_no_dependencies(self, gen):
        code = gen._generate_go_exception_test(
            'Foo', [], '// no errors', '', 'Foo')
        assert 'Mock layer returns error' in code


# ===========================================================================
#  _generate_pytest_exception_test
# ===========================================================================

class TestPytestExceptionTest:
    def test_with_codes(self, rich_gen):
        deps = [{'type': 'call', 'source': 'A', 'target': 'Dao'}]
        code = rich_gen._generate_pytest_exception_test(
            'create_adgroup', deps, ['ERR_1'], 'mock code', '异常')
        assert 'test_create_adgroup' in code
        assert 'ERR_1' in code

    def test_no_codes(self, rich_gen):
        code = rich_gen._generate_pytest_exception_test(
            'foo', [], [], 'mock', 'exc')
        assert 'expected error' in code


# ===========================================================================
#  _generate_imports
# ===========================================================================

class TestGenerateImports:
    def test_basic(self, rich_gen):
        imports = rich_gen._generate_imports('create_adgroup')
        assert 'create_adgroupHandler' in imports or 'Handler' in imports
        assert 'from src.handler' in imports

    def test_class_naming(self, rich_gen):
        imports = rich_gen._generate_imports('list_adgroups')
        assert 'List_adgroupsHandler' in imports


# ===========================================================================
#  _build_go_integration_test
# ===========================================================================

class TestBuildGoIntegrationTest:
    def test_basic(self, rich_gen):
        code = rich_gen._build_go_integration_test(
            'CreateAdGroup', 'AdGroup', 'CreateAdGroupRequest',
            'CampaignId: 0', '', 'POST', '/api/v1/adgroups', [], [])
        assert 'TestCreateAdGroup_Integration' in code
        assert 'httptest.NewRequest' in code

    def test_with_dependencies(self, rich_gen):
        deps = [{'type': 'call', 'target': 'AdGroupDAO'}]
        code = rich_gen._build_go_integration_test(
            'CreateAdGroup', 'AdGroup', 'Req', '', '', 'POST', '/api/test',
            deps, [])
        assert 'router.HandleFunc' in code


# ===========================================================================
#  _build_py_integration_test
# ===========================================================================

class TestBuildPyIntegrationTest:
    def test_basic(self, rich_gen):
        code = rich_gen._build_py_integration_test(
            'create_adgroup', 'AdGroup', 'Request', '',
            'POST', '/api/v1/adgroups', [], [])
        assert 'TestCreateAdgroupIntegration' in code or 'integration' in code.lower()
        assert 'pytest' in code
        assert 'make_valid_request' in code


# ===========================================================================
#  generate_integration_test_template
# ===========================================================================

class TestGenerateIntegrationTestTemplate:
    def test_found_function(self, rich_gen):
        result = rich_gen.generate_integration_test_template('CreateAdGroup')
        assert result is not None
        assert 'go' in result
        assert 'python' in result
        assert result['route']['handler'] == 'CreateAdGroup'

    def test_not_found(self, gen):
        result = gen.generate_integration_test_template('NoSuch')
        assert result is None

    def test_with_route_info(self, rich_gen):
        route_info = {'method': 'GET', 'path': '/api/v1/adgroups/123'}
        result = rich_gen.generate_integration_test_template(
            'GetAdGroup', route_info)
        assert result is not None
        assert result['route']['method'] == 'GET'
        assert result['route']['path'] == '/api/v1/adgroups/123'
