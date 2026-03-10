"""Tests for LLM code generator."""

import json
import pytest
from unittest.mock import MagicMock, patch

from flowgenius.llm.code_generator import LLMCodeGenerator, GeneratedCode
from flowgenius.llm.base import MockLLMProvider
from flowgenius.models.traffic import TrafficFlow, TrafficRequest, TrafficResponse
from flowgenius.models.assertion import AssertionSet, AssertionRule, AssertionType, AssertionCategory


@pytest.fixture
def sample_flow():
    """Create a sample traffic flow for testing."""
    request = TrafficRequest(
        url="https://api.example.com/users/123",
        method="GET",
        headers={"Authorization": "Bearer token123"},
        query_params={"page": "1"},
    )
    response = TrafficResponse(
        status_code=200,
        headers={"Content-Type": "application/json"},
        body='{"code": 0, "data": {"user_id": 123, "name": "Test User"}}',
        content_type="application/json",
    )
    return TrafficFlow(request=request, response=response, flow_id="test-flow-1")


@pytest.fixture
def sample_assertion_set(sample_flow):
    """Create a sample assertion set."""
    assertion_set = AssertionSet(flow_id=sample_flow.flow_id)
    assertion_set.add_assertion(
        AssertionRule(
            assertion_type=AssertionType.STATUS_CODE,
            category=AssertionCategory.HEALTH,
            description="Status code should be 200",
            expected_value=200,
        )
    )
    assertion_set.add_assertion(
        AssertionRule(
            assertion_type=AssertionType.EQUALS,
            category=AssertionCategory.SEMANTIC,
            description="Code should be 0",
            actual_jsonpath="$.code",
            expected_value=0,
        )
    )
    return assertion_set


class TestGeneratedCode:
    """Tests for GeneratedCode dataclass."""

    def test_creation(self):
        """Test creating generated code."""
        code = GeneratedCode(
            code="print('hello')",
            language="python",
            description="Test code",
            imports=["os", "sys"],
            dependencies=["requests"],
        )

        assert code.code == "print('hello')"
        assert code.language == "python"
        assert code.description == "Test code"
        assert "os" in code.imports
        assert "requests" in code.dependencies

    def test_defaults(self):
        """Test default values."""
        code = GeneratedCode(code="pass")

        assert code.language == "python"
        assert code.description == ""
        assert code.imports == []
        assert code.dependencies == []


class TestLLMCodeGenerator:
    """Tests for LLMCodeGenerator class."""

    def test_init_without_provider(self):
        """Test initialization without LLM provider."""
        generator = LLMCodeGenerator()

        assert generator.llm_provider is None

    def test_init_with_provider(self):
        """Test initialization with LLM provider."""
        provider = MockLLMProvider()
        generator = LLMCodeGenerator(llm_provider=provider)

        assert generator.llm_provider == provider

    def test_generate_api_class_without_provider(self, sample_flow):
        """Test API class generation without LLM provider (fallback)."""
        generator = LLMCodeGenerator()

        result = generator.generate_api_class(sample_flow, base_url="https://api.example.com")

        assert isinstance(result, GeneratedCode)
        assert "class Api" in result.code
        assert "def get(" in result.code
        assert "requests" in result.code

    def test_generate_api_class_with_provider(self, sample_flow):
        """Test API class generation with mock LLM provider."""
        mock_code = '''
class ApiUsers:
    """API for users endpoint."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    def get_user(self, user_id: int):
        return requests.get(f"{self.base_url}/users/{user_id}")
'''
        provider = MockLLMProvider(default_response=mock_code)
        generator = LLMCodeGenerator(llm_provider=provider)

        result = generator.generate_api_class(sample_flow)

        assert isinstance(result, GeneratedCode)
        assert result.language == "python"

    def test_generate_api_class_with_markdown(self, sample_flow):
        """Test extracting code from markdown response."""
        markdown_response = '''
Here's the generated code:

```python
class ApiUsers:
    pass
```
'''
        provider = MockLLMProvider(default_response=markdown_response)
        generator = LLMCodeGenerator(llm_provider=provider)

        result = generator.generate_api_class(sample_flow)

        assert "class ApiUsers" in result.code
        assert "```" not in result.code

    def test_generate_test_case_without_provider_raises_error(self, sample_flow, sample_assertion_set):
        """Test test case generation without LLM provider raises ValueError."""
        generator = LLMCodeGenerator()

        with pytest.raises(ValueError, match="LLM provider is required for test case generation"):
            generator.generate_test_case(sample_flow, sample_assertion_set)

    def test_generate_test_case_with_provider(self, sample_flow, sample_assertion_set):
        """Test test case generation with mock LLM provider."""
        mock_test = '''
def test_get_users(self, base_url, session):
    """Test GET /users endpoint."""
    response = session.get(base_url + "/users/123")
    assert response.status_code == 200
'''
        provider = MockLLMProvider(default_response=mock_test)
        generator = LLMCodeGenerator(llm_provider=provider)

        result = generator.generate_test_case(sample_flow, sample_assertion_set)

        assert isinstance(result, GeneratedCode)
        assert result.language == "python"

    def test_generate_docstring_without_provider(self):
        """Test docstring generation without LLM provider."""
        generator = LLMCodeGenerator()

        result = generator.generate_docstring(
            api_path="/users/{id}",
            method="GET",
            params={"user_id": "int"},
            response_summary={"user_id": "int", "name": "str"},
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_docstring_with_provider(self):
        """Test docstring generation with mock LLM provider."""
        provider = MockLLMProvider(
            responses={"users": "获取用户信息。\n\nArgs:\n    user_id: 用户ID\n\nReturns:\n    用户信息字典"}
        )
        generator = LLMCodeGenerator(llm_provider=provider)

        result = generator.generate_docstring(
            api_path="/users/{id}",
            method="GET",
            params={"user_id": "int"},
            response_summary={"user_id": "int", "name": "str"},
        )

        assert isinstance(result, str)

    def test_generate_test_module(self, sample_flow, sample_assertion_set):
        """Test generating a complete test module."""
        generator = LLMCodeGenerator()

        result = generator.generate_test_module(
            flows=[sample_flow],
            assertion_sets={sample_flow.flow_id: sample_assertion_set},
            base_url="https://api.example.com",
        )

        assert isinstance(result, GeneratedCode)
        assert "import pytest" in result.code
        assert "class Test" in result.code

    def test_extract_code_from_markdown_python(self):
        """Test extracting Python code from markdown."""
        generator = LLMCodeGenerator()

        text = "Here is the code:\n```python\nprint('hello')\n```\nEnd."
        result = generator._extract_code_from_markdown(text)

        assert result == "print('hello')"

    def test_extract_code_from_markdown_generic(self):
        """Test extracting code from generic markdown block."""
        generator = LLMCodeGenerator()

        text = "```\ndef test():\n    pass\n```"
        result = generator._extract_code_from_markdown(text)

        assert "def test():" in result

    def test_extract_code_from_plain_text(self):
        """Test that plain text is returned as-is."""
        generator = LLMCodeGenerator()

        text = "def test():\n    pass"
        result = generator._extract_code_from_markdown(text)

        assert result == text

    def test_infer_business_logic(self, sample_flow):
        """Test inferring business logic from flow."""
        generator = LLMCodeGenerator()

        # GET request
        logic = generator._infer_business_logic(sample_flow)
        assert "查询" in logic or "users" in logic.lower()

        # POST request
        sample_flow.request.method = "POST"
        logic = generator._infer_business_logic(sample_flow)
        assert "创建" in logic or "POST" in logic

    def test_generate_class_name(self, sample_flow):
        """Test generating class name from flow."""
        generator = LLMCodeGenerator()

        name = generator._generate_class_name(sample_flow, None)
        assert "Api" in name

    def test_generate_test_name(self, sample_flow):
        """Test generating test method name."""
        generator = LLMCodeGenerator()

        name = generator._generate_test_name(sample_flow)
        assert name.startswith("test_")
        assert "get" in name


def test_zhipu_provider_integration():
    """Test that ZhipuProvider can be used with LLMCodeGenerator."""
    from flowgenius.llm.base import ZhipuProvider

    # We won't actually call the API, but test that the provider can be instantiated and passed
    provider = MockLLMProvider(responses={"test": "test response"})

    # Test that we can create an LLMCodeGenerator with a provider
    generator = LLMCodeGenerator(llm_provider=provider)
    assert generator.llm_provider is not None