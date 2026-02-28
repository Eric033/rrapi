"""
Pytest test case code generation.
"""
import logging
from typing import Any, Dict, List, Optional
from collections import defaultdict

from flowgenius.models.api import APIEndpoint
from flowgenius.models.assertion import AssertionSet
from flowgenius.models.correlation import CorrelationChain
from flowgenius.models.traffic import TrafficFlow
from flowgenius.utils.logger import get_logger
from flowgenius.utils.jsonpath import extract_jsonpath


class TestCaseGenerator:
    """Generates Pytest test cases from traffic flows."""

    def __init__(self):
        """Initialize test case generator."""
        self.logger = get_logger("flowgenius.test_case_generator")

    def generate_test_case(
        self,
        flow: TrafficFlow,
        assertion_set: Optional[AssertionSet] = None,
        api_class_name: Optional[str] = None,
        business_logic: Optional[str] = None
    ) -> str:
        """
        Generate a single test case.

        Args:
            flow: TrafficFlow object
            assertion_set: AssertionSet with validations
            api_class_name: Name of the API object class to use
            business_logic: Business logic description for docstring

        Returns:
            Generated test case code
        """
        lines = []

        # Docstring
        docstring = f'"""测试 {business_logic or flow.request.url}"""' if business_logic else f'"""测试 {flow.request.method} {flow.request.url}"""'
        lines.append(f'    def test_{self._get_test_method_name(flow)}(self, base_url, session):')
        lines.append(f'        {docstring}')

        # Import and instantiate API class if provided
        if api_class_name:
            lines.append(f'        api = {api_class_name}(base_url)')
            lines.append('')
            lines.append(f'        # 发送请求')
            lines.append(f'        response = api.{flow.request.method.lower()}(')

            # Add parameters
            params_added = False
            if flow.request.query_params:
                lines.append(f'            params={self._format_dict(flow.request.query_params)},')
                params_added = True
            if flow.request.body:
                body = flow.request.get_body_json()
                if body:
                    lines.append(f'            body={self._format_dict(body)},')
                    params_added = True

            if params_added:
                lines[-1] = lines[-1][:-1]  # Remove trailing comma from last param
            lines.append(f'        )')
        else:
            lines.append(f'        # 发送请求')
            lines.append(f'        response = session.{flow.request.method.lower()}(')
            lines.append(f'            base_url + "{flow.request.url}",')

            if flow.request.headers:
                lines.append(f'            headers={self._format_dict(flow.request.headers)},')
            if flow.request.query_params:
                lines.append(f'            params={self._format_dict(flow.request.query_params)},')
            if flow.request.body:
                body = flow.request.get_body_json()
                if body:
                    lines.append(f'            json={self._format_dict(body)},')

            # Remove trailing comma
            lines[-1] = lines[-1][:-1] if lines[-1].endswith(',') else lines[-1]
            lines.append(f'        )')

        lines.append('')

        # Generate assertions
        if assertion_set:
            assertion_code = self._generate_assertion_code(assertion_set, flow)
            lines.append(assertion_code)
        else:
            # Default assertions
            lines.append(f'        # 基础校验')
            lines.append(f'        assert response.status_code == {flow.response.status_code}')
            if flow.response.time:
                lines.append(f'        assert response.elapsed.total_seconds() < 5.0')

        lines.append('')

        return '\n'.join(lines)

    def _get_test_method_name(self, flow: TrafficFlow) -> str:
        """Generate a test method name for a flow."""
        # Extract a clean name from the URL
        from urllib.parse import urlparse
        parsed = urlparse(flow.request.url)
        path_parts = [p for p in parsed.path.split('/') if p and not p.startswith('{')]

        if path_parts:
            resource = path_parts[-1]
            method = flow.request.method.lower()
            return f'{method}_{resource}'

        return f'{flow.request.method.lower()}_api'

    def _format_dict(self, d: Dict[str, Any]) -> str:
        """Format a dictionary as Python code."""
        if not d:
            return '{}'
        import json
        return json.dumps(d, indent=12, ensure_ascii=False)

    def _generate_assertion_code(self, assertion_set: AssertionSet, flow: TrafficFlow) -> str:
        """Generate assertion code from assertion set."""
        lines = []

        # Group assertions by category
        health_assertions = assertion_set.get_health_assertions()
        contract_assertions = assertion_set.get_contract_assertions()
        semantic_assertions = assertion_set.get_semantic_assertions()
        snapshot_assertions = assertion_set.get_snapshot_assertions()

        # Health assertions
        if health_assertions:
            lines.append('        # 基础健康校验')
            for assertion in health_assertions:
                code = assertion.get_assertion_code()
                if code and not code.startswith('#'):
                    lines.append(f'        {code}')

        # Contract assertions
        if contract_assertions:
            lines.append('')
            lines.append('        # 契约校验')
            for assertion in contract_assertions:
                code = assertion.get_assertion_code()
                if code and not code.startswith('#'):
                    lines.append(f'        {code}')

        # Semantic assertions
        if semantic_assertions:
            lines.append('')
            lines.append('        # 业务语义校验')
            for assertion in semantic_assertions:
                code = assertion.get_assertion_code()
                if code and not code.startswith('#'):
                    lines.append(f'        {code}')

        # Snapshot assertions
        if snapshot_assertions:
            lines.append('')
            lines.append('        # 快照对比校验')
            for assertion in snapshot_assertions:
                code = assertion.get_assertion_code()
                if code and not code.startswith('#'):
                    lines.append(f'        {code}')

        return '\n'.join(lines)

    def generate_test_class(
        self,
        flows: List[TrafficFlow],
        assertion_sets: Dict[str, AssertionSet],
        api_mappings: Optional[Dict[str, str]] = None,
        business_mappings: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Generate a test class with multiple test cases.

        Args:
            flows: List of TrafficFlow objects
            assertion_sets: Dictionary mapping flow IDs to AssertionSets
            api_mappings: Dictionary mapping flow IDs to API class names
            business_mappings: Dictionary mapping URLs to business logic descriptions

        Returns:
            Generated test class code
        """
        lines = [
            '"""',
            'Test cases for API endpoints',
            'Automatically generated by FlowGenius SmartAdapter',
            '"""',
            '',
            'import pytest',
            'import requests',
            'from typing import Dict, Any',
            ''
        ]

        # Add imports for API classes if provided
        if api_mappings:
            unique_api_classes = set(api_mappings.values())
            for api_class in unique_api_classes:
                lines.append(f'from api.{self._camel_to_snake(api_class)} import {api_class}')
            lines.append('')

        lines.append('')
        lines.append('class TestAPI:')
        lines.append('    """Generated API test class."""')
        lines.append('')

        # Add conftest-like fixture methods
        lines.append('    @pytest.fixture')
        lines.append('    def base_url(self):')
        lines.append('        """Base URL for API requests."""')
        lines.append('        return "https://api.example.com"')
        lines.append('')
        lines.append('    @pytest.fixture')
        lines.append('    def session(self):')
        lines.append('        """Requests session."""')
        lines.append('        return requests.Session()')
        lines.append('')

        # Generate test cases
        for flow in flows:
            assertion_set = assertion_sets.get(flow.flow_id)
            api_class = api_mappings.get(flow.flow_id) if api_mappings else None
            business_logic = business_mappings.get(flow.request.url) if business_mappings else None

            test_case = self.generate_test_case(
                flow, assertion_set, api_class, business_logic
            )
            lines.append(test_case)

        return '\n'.join(lines)

    def _camel_to_snake(self, name: str) -> str:
        """Convert CamelCase to snake_case."""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def generate_data_driven_test(
        self,
        flows: List[TrafficFlow],
        assertion_sets: Dict[str, AssertionSet],
        test_data: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a data-driven test case.

        Args:
            flows: List of TrafficFlow objects (uses first flow as template)
            assertion_sets: AssertionSets for flows
            test_data: Test data for parametrization

        Returns:
            Generated data-driven test code
        """
        if not flows:
            return ""

        template_flow = flows[0]
        lines = [
            '"""',
            'Data-driven test cases',
            'Automatically generated by FlowGenius SmartAdapter',
            '"""',
            '',
            'import pytest',
            'from typing import Dict, Any',
            ''
        ]

        # Generate test data file reference
        lines.append('# Test data loaded from test_data.yaml')
        lines.append('')
        lines.append('@pytest.mark.parametrize("test_case", test_data)')
        lines.append(f'    def test_{self._get_test_method_name(template_flow)}(test_case, base_url, session):')
        lines.append(f'        """Test {template_flow.request.method} {template_flow.request.url}"""')
        lines.append('        response = session.{template_flow.request.method.lower()}(')
        lines.append(f'            base_url + test_case["url"],')
        lines.append('            headers=test_case.get("headers", {}),')
        lines.append('            params=test_case.get("params", {}),')
        lines.append('            json=test_case.get("body")')
        lines.append('        )')
        lines.append('')
        lines.append('        # Assertions')
        lines.append('        assert response.status_code == test_case["expected_status"]')
        lines.append('')

        return '\n'.join(lines)

    def generate_test_module(
        self,
        flows: List[TrafficFlow],
        assertion_sets: Dict[str, AssertionSet],
        grouped_by_endpoint: bool = True
    ) -> str:
        """
        Generate a complete test module.

        Args:
            flows: List of TrafficFlow objects
            assertion_sets: Dictionary mapping flow IDs to AssertionSets
            grouped_by_endpoint: Whether to group tests by endpoint

        Returns:
            Generated test module code
        """
        lines = [
            '"""',
            'API test module',
            'Automatically generated by FlowGenius SmartAdapter',
            '"""',
            '',
            'import pytest',
            'import requests',
            ''
        ]

        if grouped_by_endpoint:
            # Group flows by endpoint
            endpoint_flows = defaultdict(list)
            for flow in flows:
                key = (flow.request.method, flow.request.url)
                endpoint_flows[key].append(flow)

            # Generate test class for each endpoint
            for (method, url), endpoint_flow_list in endpoint_flows.items():
                class_name = self._get_class_name_from_url(url, method)
                lines.append('')
                lines.append(f'class {class_name}:')
                lines.append(f'    """Test cases for {method} {url}"""')
                lines.append('')

                # Generate test cases
                for flow in endpoint_flow_list:
                    assertion_set = assertion_sets.get(flow.flow_id)
                    test_case = self.generate_test_case(flow, assertion_set)
                    lines.append(test_case)
        else:
            # Single test class with all tests
            test_class = self.generate_test_class(flows, assertion_sets)
            lines.append(test_class)

        return '\n'.join(lines)

    def _get_class_name_from_url(self, url: str, method: str) -> str:
        """Generate a class name from URL and method."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p and not p.startswith('{')]

        if path_parts:
            resource = path_parts[-1]
            return f'Test{resource.capitalize()}'
        return 'TestAPI'

    def generate_conftest(self, base_url: str = "https://api.example.com") -> str:
        """
        Generate conftest.py with shared fixtures.

        Args:
            base_url: Base URL for API tests

        Returns:
            Generated conftest.py code
        """
        lines = [
            '"""',
            'Pytest configuration and shared fixtures',
            'Automatically generated by FlowGenius SmartAdapter',
            '"""',
            '',
            'import pytest',
            'import requests',
            'from typing import Generator',
            ''
        ]

        # Base URL fixture
        lines.append('@pytest.fixture(scope="session")')
        lines.append('def base_url() -> str:')
        lines.append(f'    """Base URL for API requests."""')
        lines.append(f'    return "{base_url}"')
        lines.append('')

        # Session fixture
        lines.append('@pytest.fixture(scope="function")')
        lines.append('def session(base_url: str) -> Generator[requests.Session, None, None]:')
        lines.append('    """Create a requests session."""')
        lines.append('    session = requests.Session()')
        lines.append('    yield session')
        lines.append('    session.close()')
        lines.append('')

        # Auth token fixture (placeholder)
        lines.append('@pytest.fixture(scope="session")')
        lines.append('def auth_token(base_url: str) -> str:')
        lines.append('    """Get authentication token."""')
        lines.append('    # Implement actual login logic')
        lines.append('    response = requests.post(')
        lines.append(f'        f"{{base_url}}/api/login",')
        lines.append('        json={"username": "test", "password": "test123"}')
        lines.append('    )')
        lines.append('    response.raise_for_status()')
        lines.append('    return response.json()["data"]["token"]')
        lines.append('')

        # Custom assertions
        lines.append('# Custom assertion helpers')
        lines.append('')
        lines.append('def assert_response_success(response: requests.Response):')
        lines.append('    """Assert response indicates success."""')
        lines.append('    assert response.status_code >= 200 and response.status_code < 300')
        lines.append('    data = response.json()')
        lines.append('    assert data.get("code") == 0 or data.get("success") is True')
        lines.append('')

        lines.append('def assert_jsonpath_exists(response_data: dict, jsonpath: str):')
        lines.append('    """Assert a value exists at the given JSONPath."""')
        lines.append('    from flowgenius.utils.jsonpath import extract_jsonpath')
        lines.append('    value = extract_jsonpath(response_data, jsonpath)')
        lines.append('    assert value is not None')
        lines.append('')

        return '\n'.join(lines)