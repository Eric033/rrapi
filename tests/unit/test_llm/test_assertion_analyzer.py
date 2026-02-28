"""Tests for LLM assertion analyzer."""

import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from flowgenius.llm.assertion_analyzer import (
    LLMAssertionAnalyzer,
    SemanticAssertion,
    CorrelationHint,
    ResponseAnalysisResult,
)
from flowgenius.llm.base import MockLLMProvider
from flowgenius.models.assertion import AssertionType, AssertionCategory
from flowgenius.models.traffic import TrafficFlow, TrafficRequest, TrafficResponse


@pytest.fixture
def sample_flow():
    """Create a sample traffic flow for testing."""
    request = TrafficRequest(
        url="https://api.example.com/users/123",
        method="GET",
        headers={"Authorization": "Bearer token123"},
        query_params={},
    )
    response = TrafficResponse(
        status_code=200,
        headers={"Content-Type": "application/json"},
        body='{"code": 0, "success": true, "data": {"user_id": 123, "name": "Test User"}}',
        content_type="application/json",
    )
    return TrafficFlow(request=request, response=response, flow_id="test-flow-1")


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    return MockLLMProvider()


class TestSemanticAssertion:
    """Tests for SemanticAssertion dataclass."""

    def test_creation(self):
        """Test creating a semantic assertion."""
        assertion = SemanticAssertion(
            field_path="$.data.user_id",
            business_meaning="用户ID",
            assertion_type="not_null",
            description="用户ID应存在",
            confidence=0.9,
        )

        assert assertion.field_path == "$.data.user_id"
        assert assertion.business_meaning == "用户ID"
        assert assertion.assertion_type == "not_null"
        assert assertion.confidence == 0.9

    def test_to_assertion_rule(self):
        """Test converting to AssertionRule."""
        assertion = SemanticAssertion(
            field_path="$.data.user_id",
            business_meaning="用户ID",
            assertion_type="equals",
            description="用户ID应等于123",
            expected_value=123,
            confidence=0.85,
        )

        rule = assertion.to_assertion_rule(flow_id="test-flow")

        assert rule.assertion_type == AssertionType.EQUALS
        assert rule.category == AssertionCategory.SEMANTIC
        assert rule.description == "用户ID应等于123"
        assert rule.actual_jsonpath == "$.data.user_id"
        assert rule.expected_value == 123
        assert rule.confidence == 0.85
        assert rule.source == "llm"
        assert rule.flow_id == "test-flow"


class TestCorrelationHint:
    """Tests for CorrelationHint dataclass."""

    def test_creation(self):
        """Test creating a correlation hint."""
        hint = CorrelationHint(
            field="$.data.token",
            likely_used_in="后续请求的 Authorization 头",
            extraction_suggestion="Bearer token 提取",
        )

        assert hint.field == "$.data.token"
        assert hint.likely_used_in == "后续请求的 Authorization 头"
        assert hint.extraction_suggestion == "Bearer token 提取"


class TestResponseAnalysisResult:
    """Tests for ResponseAnalysisResult dataclass."""

    def test_creation(self):
        """Test creating an analysis result."""
        result = ResponseAnalysisResult(
            key_fields=[
                SemanticAssertion(
                    field_path="$.code",
                    business_meaning="响应码",
                    assertion_type="equals",
                    description="响应码应为0",
                )
            ],
            correlation_hints=[
                CorrelationHint(
                    field="$.data.token",
                    likely_used_in="认证",
                )
            ],
            response_pattern={"has_error_handling": True},
        )

        assert len(result.key_fields) == 1
        assert len(result.correlation_hints) == 1
        assert result.response_pattern["has_error_handling"] is True


class TestLLMAssertionAnalyzer:
    """Tests for LLMAssertionAnalyzer class."""

    def test_init_without_provider(self):
        """Test initialization without LLM provider."""
        analyzer = LLMAssertionAnalyzer()

        assert analyzer.llm_provider is None

    def test_init_with_provider(self, mock_llm_provider):
        """Test initialization with LLM provider."""
        analyzer = LLMAssertionAnalyzer(llm_provider=mock_llm_provider)

        assert analyzer.llm_provider == mock_llm_provider

    def test_analyze_response_structure_without_provider(self, sample_flow):
        """Test analysis without LLM provider returns empty result."""
        analyzer = LLMAssertionAnalyzer()

        result = analyzer.analyze_response_structure(
            endpoint=None,
            response_data=sample_flow.response.get_body_json(),
        )

        assert isinstance(result, ResponseAnalysisResult)
        assert len(result.key_fields) == 0

    def test_analyze_response_structure_with_provider(self, sample_flow):
        """Test analysis with mock LLM provider."""
        llm_response = {
            "key_fields": [
                {
                    "path": "$.data.user_id",
                    "business_meaning": "用户ID",
                    "assertion_type": "not_null",
                    "description": "用户ID应存在",
                }
            ],
            "correlation_hints": [],
            "response_pattern": {},
        }

        provider = MockLLMProvider(
            default_response=json.dumps(llm_response)
        )
        analyzer = LLMAssertionAnalyzer(llm_provider=provider)

        result = analyzer.analyze_response_structure(
            endpoint=None,
            response_data=sample_flow.response.get_body_json(),
        )

        assert isinstance(result, ResponseAnalysisResult)
        assert len(result.key_fields) == 1
        assert result.key_fields[0].field_path == "$.data.user_id"

    def test_generate_assertion_description_without_provider(self, sample_flow):
        """Test description generation without provider."""
        analyzer = LLMAssertionAnalyzer()

        description = analyzer.generate_assertion_description(
            field_path="$.data.user_id",
            field_value=123,
            method="GET",
            path="/users/123",
            assertion_type="not_null",
        )

        assert "user_id" in description

    def test_generate_assertion_description_with_provider(self, sample_flow):
        """Test description generation with mock provider."""
        provider = MockLLMProvider(
            responses={"user_id": "用户ID应为有效值"}
        )
        analyzer = LLMAssertionAnalyzer(llm_provider=provider)

        description = analyzer.generate_assertion_description(
            field_path="$.data.user_id",
            field_value=123,
            method="GET",
            path="/users/123",
            assertion_type="not_null",
        )

        assert isinstance(description, str)

    def test_generate_semantic_assertions_without_provider(self, sample_flow):
        """Test semantic assertion generation without provider."""
        analyzer = LLMAssertionAnalyzer()

        assertions = analyzer.generate_semantic_assertions(sample_flow)

        assert isinstance(assertions, list)
        # Without LLM, should return empty list
        assert len(assertions) == 0

    def test_generate_semantic_assertions_with_provider(self, sample_flow):
        """Test semantic assertion generation with mock provider."""
        llm_response = {
            "key_fields": [
                {
                    "path": "$.code",
                    "business_meaning": "响应码",
                    "assertion_type": "equals",
                    "description": "响应码应为0表示成功",
                    "expected_value": 0,
                }
            ],
            "correlation_hints": [],
            "response_pattern": {},
        }

        provider = MockLLMProvider(
            default_response=json.dumps(llm_response)
        )
        analyzer = LLMAssertionAnalyzer(llm_provider=provider)

        assertions = analyzer.generate_semantic_assertions(sample_flow)

        assert isinstance(assertions, list)
        assert len(assertions) >= 1

    def test_analyze_historical_patterns_empty_flows(self):
        """Test historical pattern analysis with empty flows."""
        analyzer = LLMAssertionAnalyzer()

        result = analyzer.analyze_historical_patterns([], {})

        assert result == []

    def test_analyze_historical_patterns_with_provider(self, sample_flow):
        """Test historical pattern analysis with mock provider."""
        llm_response = {
            "consistent_fields": [
                {
                    "path": "$.code",
                    "value": 0,
                    "consistency_type": "always_equals",
                }
            ],
            "variable_fields": [],
            "recommended_assertions": [
                {
                    "path": "$.code",
                    "assertion_type": "equals",
                    "expected_value": 0,
                    "confidence": 1.0,
                }
            ],
        }

        provider = MockLLMProvider(
            default_response=json.dumps(llm_response)
        )
        analyzer = LLMAssertionAnalyzer(llm_provider=provider)

        result = analyzer.analyze_historical_patterns([sample_flow], {})

        assert isinstance(result, list)

    def test_enhance_assertion_description(self, sample_flow):
        """Test enhancing assertion description."""
        from flowgenius.models.assertion import AssertionRule

        original_assertion = AssertionRule(
            assertion_type=AssertionType.EQUALS,
            category=AssertionCategory.SEMANTIC,
            description="Field should equal 0",
            actual_jsonpath="$.code",
            expected_value=0,
            flow_id=sample_flow.flow_id,
        )

        provider = MockLLMProvider(
            responses={"code": "响应码应为0表示请求成功"}
        )
        analyzer = LLMAssertionAnalyzer(llm_provider=provider)

        enhanced = analyzer.enhance_assertion_description(
            original_assertion, sample_flow
        )

        assert enhanced is not None
        assert enhanced.assertion_type == original_assertion.assertion_type
        assert enhanced.category == original_assertion.category