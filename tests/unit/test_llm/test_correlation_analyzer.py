"""Tests for LLM correlation analyzer."""

import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from flowgenius.llm.correlation_analyzer import (
    LLMCorrelationAnalyzer,
    CorrelationExplanation,
    FlowPattern,
    VariableNameSuggestion,
)
from flowgenius.llm.base import MockLLMProvider
from flowgenius.models.traffic import TrafficFlow, TrafficRequest, TrafficResponse
from flowgenius.models.correlation import CorrelationChain, CorrelationRule


@pytest.fixture
def login_flow():
    """Create a login flow with token in response."""
    request = TrafficRequest(
        url="https://api.example.com/auth/login",
        method="POST",
        headers={"Content-Type": "application/json"},
        body='{"username": "test", "password": "test123"}',
        content_type="application/json",
    )
    response = TrafficResponse(
        status_code=200,
        body='{"code": 0, "data": {"token": "abc123token", "user_id": 1}}',
        content_type="application/json",
    )
    return TrafficFlow(request=request, response=response, flow_id="login-flow")


@pytest.fixture
def user_flow():
    """Create a user flow that uses token from login."""
    request = TrafficRequest(
        url="https://api.example.com/users/profile",
        method="GET",
        headers={"Authorization": "Bearer abc123token"},
    )
    response = TrafficResponse(
        status_code=200,
        body='{"code": 0, "data": {"name": "Test User"}}',
        content_type="application/json",
    )
    return TrafficFlow(request=request, response=response, flow_id="user-flow")


class TestCorrelationExplanation:
    """Tests for CorrelationExplanation dataclass."""

    def test_creation(self):
        """Test creating a correlation explanation."""
        explanation = CorrelationExplanation(
            correlation_type="authentication",
            variable_name="auth_token",
            variable_name_cn="认证令牌",
            explanation="Token from login used for authentication",
            extraction_method="jsonpath",
            extraction_expression="$.data.token",
            usage_template="Bearer {variable_name}",
            confidence=0.95,
        )

        assert explanation.correlation_type == "authentication"
        assert explanation.variable_name == "auth_token"
        assert explanation.variable_name_cn == "认证令牌"
        assert explanation.extraction_method == "jsonpath"
        assert explanation.confidence == 0.95


class TestFlowPattern:
    """Tests for FlowPattern dataclass."""

    def test_creation(self):
        """Test creating a flow pattern."""
        pattern = FlowPattern(
            flow_name="用户登录流程",
            flow_description="用户登录并获取个人信息",
            steps=[
                {"order": 1, "api": "/auth/login", "method": "POST"},
                {"order": 2, "api": "/users/profile", "method": "GET"},
            ],
            variables=[
                {"name": "auth_token", "source_step": 1},
            ],
        )

        assert pattern.flow_name == "用户登录流程"
        assert len(pattern.steps) == 2
        assert len(pattern.variables) == 1

    def test_defaults(self):
        """Test default values."""
        pattern = FlowPattern(flow_name="Test Flow")

        assert pattern.flow_description == ""
        assert pattern.steps == []
        assert pattern.variables == []


class TestVariableNameSuggestion:
    """Tests for VariableNameSuggestion dataclass."""

    def test_creation(self):
        """Test creating a variable name suggestion."""
        suggestion = VariableNameSuggestion(
            variable_name="auth_token",
            variable_name_cn="认证令牌",
            description="JWT token for authentication",
            naming_rationale="Based on the field being in login response",
        )

        assert suggestion.variable_name == "auth_token"
        assert suggestion.variable_name_cn == "认证令牌"
        assert suggestion.description == "JWT token for authentication"


class TestLLMCorrelationAnalyzer:
    """Tests for LLMCorrelationAnalyzer class."""

    def test_init_without_provider(self):
        """Test initialization without LLM provider."""
        analyzer = LLMCorrelationAnalyzer()

        assert analyzer.llm_provider is None

    def test_init_with_provider(self):
        """Test initialization with LLM provider."""
        provider = MockLLMProvider()
        analyzer = LLMCorrelationAnalyzer(llm_provider=provider)

        assert analyzer.llm_provider == provider

    def test_explain_correlation_without_provider(self, login_flow, user_flow):
        """Test explaining correlation without LLM provider (fallback)."""
        analyzer = LLMCorrelationAnalyzer()

        explanation = analyzer.explain_correlation(
            source_flow=login_flow,
            target_flow=user_flow,
            source_field="$.data.token",
            target_location="header:Authorization",
        )

        assert isinstance(explanation, CorrelationExplanation)
        assert explanation.variable_name != ""
        assert explanation.extraction_expression == "$.data.token"

    def test_explain_correlation_with_provider(self, login_flow, user_flow):
        """Test explaining correlation with mock LLM provider."""
        llm_response = {
            "correlation_type": "authentication",
            "variable_name": "auth_token",
            "variable_name_cn": "认证令牌",
            "explanation": "登录返回的token用于后续请求认证",
            "extraction_method": "jsonpath",
            "extraction_expression": "$.data.token",
            "usage_template": "Bearer {variable_name}",
            "confidence": 0.95,
        }

        provider = MockLLMProvider(default_response=json.dumps(llm_response))
        analyzer = LLMCorrelationAnalyzer(llm_provider=provider)

        explanation = analyzer.explain_correlation(
            source_flow=login_flow,
            target_flow=user_flow,
            source_field="$.data.token",
            target_location="header:Authorization",
        )

        assert isinstance(explanation, CorrelationExplanation)
        assert explanation.correlation_type == "authentication"
        assert explanation.variable_name == "auth_token"
        assert explanation.confidence == 0.95

    def test_suggest_variable_name_without_provider(self):
        """Test variable name suggestion without LLM provider."""
        analyzer = LLMCorrelationAnalyzer()

        suggestion = analyzer.suggest_variable_name(
            field_path="$.data.token",
            field_value="abc123",
            api_endpoint="/auth/login",
        )

        assert isinstance(suggestion, VariableNameSuggestion)
        assert "token" in suggestion.variable_name

    def test_suggest_variable_name_with_provider(self):
        """Test variable name suggestion with mock LLM provider."""
        llm_response = {
            "variable_name": "auth_token",
            "variable_name_cn": "认证令牌",
            "description": "JWT token for API authentication",
            "naming_rationale": "Token is returned from login endpoint",
        }

        provider = MockLLMProvider(default_response=json.dumps(llm_response))
        analyzer = LLMCorrelationAnalyzer(llm_provider=provider)

        suggestion = analyzer.suggest_variable_name(
            field_path="$.data.token",
            field_value="abc123",
            api_endpoint="/auth/login",
        )

        assert isinstance(suggestion, VariableNameSuggestion)
        assert suggestion.variable_name == "auth_token"
        assert suggestion.variable_name_cn == "认证令牌"

    def test_detect_flow_pattern_empty_flows(self):
        """Test detecting flow pattern with empty flows."""
        analyzer = LLMCorrelationAnalyzer()

        pattern = analyzer.detect_flow_pattern([])

        assert isinstance(pattern, FlowPattern)
        assert pattern.flow_name == "空流程"

    def test_detect_flow_pattern_without_provider(self, login_flow, user_flow):
        """Test detecting flow pattern without LLM provider."""
        analyzer = LLMCorrelationAnalyzer()

        pattern = analyzer.detect_flow_pattern([login_flow, user_flow])

        assert isinstance(pattern, FlowPattern)
        assert len(pattern.steps) == 2

    def test_detect_flow_pattern_with_provider(self, login_flow, user_flow):
        """Test detecting flow pattern with mock LLM provider."""
        llm_response = {
            "flow_name": "用户登录流程",
            "flow_description": "用户登录后获取个人信息",
            "steps": [
                {"order": 1, "api": "/auth/login", "method": "POST", "action": "用户登录"},
                {"order": 2, "api": "/users/profile", "method": "GET", "action": "获取用户信息"},
            ],
            "variables": [
                {"name": "auth_token", "source_step": 1, "used_in_steps": [2]},
            ],
            "error_handling": {},
        }

        provider = MockLLMProvider(default_response=json.dumps(llm_response))
        analyzer = LLMCorrelationAnalyzer(llm_provider=provider)

        pattern = analyzer.detect_flow_pattern([login_flow, user_flow])

        assert isinstance(pattern, FlowPattern)
        assert pattern.flow_name == "用户登录流程"
        assert len(pattern.steps) == 2
        assert len(pattern.variables) == 1

    def test_enhance_correlation_chain(self, login_flow, user_flow):
        """Test enhancing correlation chain with LLM."""
        chain = CorrelationChain()
        chain.add_flow(login_flow.flow_id)
        chain.add_flow(user_flow.flow_id)
        chain.add_correlation(
            CorrelationRule(
                response_flow_id=login_flow.flow_id,
                request_flow_id=user_flow.flow_id,
                response_jsonpath="$.data.token",
                request_location="header",
                request_key="Authorization",
                variable_name="token",
            )
        )

        llm_response = {
            "correlation_type": "authentication",
            "variable_name": "auth_token",
            "variable_name_cn": "认证令牌",
            "explanation": "Token for authentication",
        }

        provider = MockLLMProvider(default_response=json.dumps(llm_response))
        analyzer = LLMCorrelationAnalyzer(llm_provider=provider)

        enhanced_chain = analyzer.enhance_correlation_chain(chain, [login_flow, user_flow])

        assert isinstance(enhanced_chain, CorrelationChain)
        assert len(enhanced_chain.correlations) == 1
        assert enhanced_chain.correlations[0].variable_name == "auth_token"

    def test_generate_correlation_summary(self, login_flow, user_flow):
        """Test generating correlation summary."""
        chain = CorrelationChain()
        chain.add_flow(login_flow.flow_id)
        chain.add_flow(user_flow.flow_id)
        chain.add_correlation(
            CorrelationRule(
                response_flow_id=login_flow.flow_id,
                request_flow_id=user_flow.flow_id,
                response_jsonpath="$.data.token",
                request_location="header",
                request_key="Authorization",
                variable_name="auth_token",
            )
        )

        analyzer = LLMCorrelationAnalyzer()

        summary = analyzer.generate_correlation_summary(chain, [login_flow, user_flow])

        assert isinstance(summary, str)
        assert "auth_token" in summary
        assert "1" in summary  # Number of correlations

    def test_generate_correlation_summary_empty(self):
        """Test generating correlation summary with empty chain."""
        chain = CorrelationChain()
        analyzer = LLMCorrelationAnalyzer()

        summary = analyzer.generate_correlation_summary(chain, [])

        assert "未发现" in summary

    def test_build_flow_sequence(self, login_flow, user_flow):
        """Test building flow sequence description."""
        analyzer = LLMCorrelationAnalyzer()

        sequence = analyzer._build_flow_sequence([login_flow, user_flow])

        assert "1. POST" in sequence
        assert "2. GET" in sequence
        assert "/auth/login" in sequence

    def test_fallback_variable_name_common_fields(self):
        """Test fallback variable name generation for common fields."""
        analyzer = LLMCorrelationAnalyzer()

        # Token field
        suggestion = analyzer._fallback_variable_name("$.data.token", "abc123")
        assert "token" in suggestion.variable_name.lower()

        # ID field
        suggestion = analyzer._fallback_variable_name("$.data.user_id", 123)
        assert "user_id" in suggestion.variable_name

    def test_fallback_flow_pattern(self, login_flow, user_flow):
        """Test fallback flow pattern generation."""
        analyzer = LLMCorrelationAnalyzer()

        pattern = analyzer._fallback_flow_pattern([login_flow, user_flow])

        assert isinstance(pattern, FlowPattern)
        assert len(pattern.steps) == 2
        assert pattern.steps[0]["method"] == "POST"
        assert pattern.steps[1]["method"] == "GET"