"""Tests for LLM prompt templates."""

import pytest

from flowgenius.llm.prompt_templates import (
    ANALYZE_RESPONSE_STRUCTURE_PROMPT,
    GENERATE_API_CLASS_PROMPT,
    GENERATE_TEST_CASE_PROMPT,
    EXPLAIN_CORRELATION_PROMPT,
    DETECT_FLOW_PATTERN_PROMPT,
    format_prompt,
    truncate_json_for_prompt,
    build_flow_sequence_description,
    PromptBuilder,
)


class TestPromptTemplates:
    """Tests for prompt template constants."""

    def test_analyze_response_structure_prompt(self):
        """Test that the analysis prompt contains required placeholders."""
        assert "{method}" in ANALYZE_RESPONSE_STRUCTURE_PROMPT
        assert "{path}" in ANALYZE_RESPONSE_STRUCTURE_PROMPT
        assert "{business_logic}" in ANALYZE_RESPONSE_STRUCTURE_PROMPT
        assert "{response_json}" in ANALYZE_RESPONSE_STRUCTURE_PROMPT

    def test_generate_api_class_prompt(self):
        """Test that the API class prompt contains required placeholders."""
        assert "{path}" in GENERATE_API_CLASS_PROMPT
        assert "{method}" in GENERATE_API_CLASS_PROMPT
        assert "{params}" in GENERATE_API_CLASS_PROMPT
        assert "{response_schema}" in GENERATE_API_CLASS_PROMPT
        assert "{business_logic}" in GENERATE_API_CLASS_PROMPT

    def test_generate_test_case_prompt(self):
        """Test that the test case prompt contains required placeholders."""
        assert "{path}" in GENERATE_TEST_CASE_PROMPT
        assert "{method}" in GENERATE_TEST_CASE_PROMPT
        assert "{request_params}" in GENERATE_TEST_CASE_PROMPT
        assert "{assertions}" in GENERATE_TEST_CASE_PROMPT

    def test_explain_correlation_prompt(self):
        """Test that the correlation prompt contains required placeholders."""
        assert "{source_url}" in EXPLAIN_CORRELATION_PROMPT
        assert "{source_field}" in EXPLAIN_CORRELATION_PROMPT
        assert "{target_url}" in EXPLAIN_CORRELATION_PROMPT
        assert "{target_location}" in EXPLAIN_CORRELATION_PROMPT

    def test_detect_flow_pattern_prompt(self):
        """Test that the flow pattern prompt contains required placeholder."""
        assert "{flow_sequence}" in DETECT_FLOW_PATTERN_PROMPT


class TestFormatPrompt:
    """Tests for format_prompt utility function."""

    def test_format_prompt_basic(self):
        """Test basic prompt formatting."""
        template = "Hello {name}!"
        result = format_prompt(template, name="World")

        assert result == "Hello World!"

    def test_format_prompt_multiple_params(self):
        """Test formatting with multiple parameters."""
        template = "{method} {path} - {description}"
        result = format_prompt(template, method="GET", path="/users", description="Get users")

        assert result == "GET /users - Get users"


class TestTruncateJsonForPrompt:
    """Tests for truncate_json_for_prompt utility function."""

    def test_small_json(self):
        """Test that small JSON is not truncated."""
        data = {"key": "value"}

        result = truncate_json_for_prompt(data)

        assert '"key"' in result
        assert '"value"' in result

    def test_large_json_truncation(self):
        """Test that large JSON is truncated."""
        data = {"data": "x" * 5000}

        result = truncate_json_for_prompt(data, max_length=100)

        assert len(result) <= 120  # Allow some buffer for truncation message
        assert "truncated" in result

    def test_nested_json(self):
        """Test handling nested JSON."""
        data = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            }
        }

        result = truncate_json_for_prompt(data)

        assert "level1" in result
        assert "level2" in result


class TestBuildFlowSequenceDescription:
    """Tests for build_flow_sequence_description utility function."""

    def test_empty_flows(self):
        """Test with empty flow list."""
        result = build_flow_sequence_description([])

        assert result == ""

    def test_single_flow(self):
        """Test with single flow."""
        flows = [
            {"method": "GET", "path": "/users", "description": "Get users"}
        ]

        result = build_flow_sequence_description(flows)

        assert "1. GET /users" in result
        assert "Get users" in result

    def test_multiple_flows(self):
        """Test with multiple flows."""
        flows = [
            {"method": "POST", "path": "/login"},
            {"method": "GET", "path": "/profile"},
        ]

        result = build_flow_sequence_description(flows)

        assert "1. POST /login" in result
        assert "2. GET /profile" in result

    def test_flow_with_params(self):
        """Test flow with parameters."""
        flows = [
            {"method": "GET", "path": "/users", "params": {"page": 1}}
        ]

        result = build_flow_sequence_description(flows)

        assert "page" in result


class TestPromptBuilder:
    """Tests for PromptBuilder class."""

    def test_set_api_info(self):
        """Test setting API information."""
        builder = PromptBuilder()
        builder.set_api_info("GET", "/users", "Get user list")

        assert builder._context["method"] == "GET"
        assert builder._context["path"] == "/users"
        assert builder._context["business_logic"] == "Get user list"

    def test_set_response_data(self):
        """Test setting response data."""
        builder = PromptBuilder()
        builder.set_response_data({"code": 0, "data": []})

        assert "response_json" in builder._context
        assert "code" in builder._context["response_json"]

    def test_set_field_info(self):
        """Test setting field information."""
        builder = PromptBuilder()
        builder.set_field_info("$.data.token", "abc123", "not_null")

        assert builder._context["field_path"] == "$.data.token"
        assert builder._context["field_value"] == "abc123"
        assert builder._context["assertion_type"] == "not_null"

    def test_set_flow_info(self):
        """Test setting flow correlation information."""
        builder = PromptBuilder()
        builder.set_flow_info(
            source_url="/login",
            source_field="$.data.token",
            target_url="/profile",
            target_location="header:Authorization"
        )

        assert builder._context["source_url"] == "/login"
        assert builder._context["source_field"] == "$.data.token"
        assert builder._context["target_url"] == "/profile"

    def test_build(self):
        """Test building the final prompt."""
        builder = PromptBuilder()
        builder.set_api_info("GET", "/users")
        builder.set_response_data({"users": []})

        template = "API: {method} {path}\nResponse: {response_json}"
        result = builder.build(template)

        assert "API: GET /users" in result
        assert "Response:" in result

    def test_chaining(self):
        """Test method chaining."""
        builder = PromptBuilder()
        result = (builder
            .set_api_info("GET", "/users")
            .set_response_data({"data": []})
            .set_field_info("$.code", 0, "equals"))

        assert result is builder
        assert "method" in builder._context
        assert "response_json" in builder._context
        assert "field_path" in builder._context