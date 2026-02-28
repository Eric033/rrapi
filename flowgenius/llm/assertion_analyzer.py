"""
LLM-enhanced assertion analysis module.

This module provides intelligent assertion generation capabilities using LLM
to understand business semantics and generate meaningful assertions.
"""
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from flowgenius.llm.base import LLMProvider
from flowgenius.llm.config import LLMConfig
from flowgenius.llm.prompt_templates import (
    ANALYZE_RESPONSE_STRUCTURE_PROMPT,
    GENERATE_ASSERTION_DESCRIPTION_PROMPT,
    ANALYZE_HISTORICAL_PATTERNS_PROMPT,
    truncate_json_for_prompt,
    PromptBuilder,
)
from flowgenius.models.api import APIEndpoint
from flowgenius.models.assertion import AssertionRule, AssertionType, AssertionCategory
from flowgenius.models.traffic import TrafficFlow
from flowgenius.utils.logger import get_logger
from flowgenius.utils.jsonpath import extract_jsonpath, extract_all_paths


@dataclass
class SemanticAssertion:
    """Represents a semantically meaningful assertion.

    Attributes:
        field_path: JSONPath to the field being asserted
        business_meaning: Business meaning of the field
        assertion_type: Type of assertion (gt_zero, equals, not_null, etc.)
        description: Human-readable description
        expected_value: Expected value (if applicable)
        boundary_suggestions: Suggestions for boundary testing
        confidence: Confidence level of the assertion
    """

    field_path: str
    business_meaning: str
    assertion_type: str
    description: str
    expected_value: Optional[Any] = None
    boundary_suggestions: List[str] = field(default_factory=list)
    confidence: float = 0.8

    def to_assertion_rule(self, flow_id: str = "") -> AssertionRule:
        """Convert to AssertionRule.

        Args:
            flow_id: Flow ID for the assertion

        Returns:
            AssertionRule instance
        """
        # Map semantic assertion types to AssertionType
        type_mapping = {
            "gt_zero": AssertionType.GREATER_THAN,
            "equals": AssertionType.EQUALS,
            "not_null": AssertionType.HAS_KEY,
            "type_check": AssertionType.JSON_PATH,
            "range": AssertionType.GREATER_THAN,
            "contains": AssertionType.CONTAINS,
        }

        assertion_type = type_mapping.get(
            self.assertion_type,
            AssertionType.JSON_PATH
        )

        return AssertionRule(
            assertion_type=assertion_type,
            category=AssertionCategory.SEMANTIC,
            description=self.description,
            actual_jsonpath=self.field_path,
            expected_value=self.expected_value,
            confidence=self.confidence,
            source="llm",
            flow_id=flow_id,
        )


@dataclass
class CorrelationHint:
    """Represents a hint about potential correlations.

    Attributes:
        field: Field path in the response
        likely_used_in: Where this field is likely used
        extraction_suggestion: How to extract this field
    """

    field: str
    likely_used_in: str
    extraction_suggestion: Optional[str] = None


@dataclass
class ResponseAnalysisResult:
    """Result of response structure analysis.

    Attributes:
        key_fields: List of key fields with semantic assertions
        correlation_hints: Hints for potential correlations
        response_pattern: Detected response patterns
    """

    key_fields: List[SemanticAssertion] = field(default_factory=list)
    correlation_hints: List[CorrelationHint] = field(default_factory=list)
    response_pattern: Dict[str, Any] = field(default_factory=dict)


class LLMAssertionAnalyzer:
    """LLM-enhanced assertion analyzer.

    This class uses LLM to analyze API responses and generate
    semantically meaningful assertions.
    """

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        config: Optional[LLMConfig] = None
    ):
        """Initialize the LLM assertion analyzer.

        Args:
            llm_provider: LLM provider instance
            config: LLM configuration (used if llm_provider not provided)
        """
        self.llm_provider = llm_provider
        self.config = config or LLMConfig()
        self.logger = get_logger("flowgenius.llm.assertion_analyzer")

    def analyze_response_structure(
        self,
        endpoint: Optional[APIEndpoint],
        response_data: Dict[str, Any],
        business_logic: Optional[str] = None
    ) -> ResponseAnalysisResult:
        """Analyze response structure using LLM.

        Args:
            endpoint: API endpoint definition
            response_data: Response data dictionary
            business_logic: Optional business logic description

        Returns:
            ResponseAnalysisResult with semantic assertions
        """
        if not self.llm_provider:
            self.logger.warning("No LLM provider configured, returning empty analysis")
            return ResponseAnalysisResult()

        try:
            # Build the prompt
            prompt = self._build_analysis_prompt(
                endpoint, response_data, business_logic
            )

            # Get LLM response
            result = self.llm_provider.generate_json(prompt)

            # Parse the result
            return self._parse_analysis_result(result)

        except Exception as e:
            self.logger.error(f"LLM analysis failed: {e}")
            return ResponseAnalysisResult()

    def _build_analysis_prompt(
        self,
        endpoint: Optional[APIEndpoint],
        response_data: Dict[str, Any],
        business_logic: Optional[str]
    ) -> str:
        """Build the analysis prompt.

        Args:
            endpoint: API endpoint
            response_data: Response data
            business_logic: Business logic description

        Returns:
            Formatted prompt string
        """
        method = endpoint.method if endpoint else "GET"
        path = endpoint.path if endpoint else "/"

        return ANALYZE_RESPONSE_STRUCTURE_PROMPT.format(
            method=method,
            path=path,
            business_logic=business_logic or "未提供业务描述",
            response_json=truncate_json_for_prompt(response_data),
        )

    def _parse_analysis_result(self, result: Dict[str, Any]) -> ResponseAnalysisResult:
        """Parse LLM analysis result.

        Args:
            result: LLM response dictionary

        Returns:
            ResponseAnalysisResult
        """
        key_fields = []
        for field_data in result.get("key_fields", []):
            assertion = SemanticAssertion(
                field_path=field_data.get("path", ""),
                business_meaning=field_data.get("business_meaning", ""),
                assertion_type=field_data.get("assertion_type", "not_null"),
                description=field_data.get("description", ""),
                expected_value=field_data.get("expected_value"),
                boundary_suggestions=field_data.get("boundary_suggestions", []),
                confidence=0.85,
            )
            key_fields.append(assertion)

        correlation_hints = []
        for hint_data in result.get("correlation_hints", []):
            hint = CorrelationHint(
                field=hint_data.get("field", ""),
                likely_used_in=hint_data.get("likely_used_in", ""),
                extraction_suggestion=hint_data.get("extraction_suggestion"),
            )
            correlation_hints.append(hint)

        return ResponseAnalysisResult(
            key_fields=key_fields,
            correlation_hints=correlation_hints,
            response_pattern=result.get("response_pattern", {}),
        )

    def generate_assertion_description(
        self,
        field_path: str,
        field_value: Any,
        method: str,
        path: str,
        assertion_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a meaningful assertion description using LLM.

        Args:
            field_path: JSONPath to the field
            field_value: Value of the field
            method: HTTP method
            path: API path
            assertion_type: Type of assertion
            context: Additional context

        Returns:
            Generated description string
        """
        if not self.llm_provider:
            return f"Field {field_path} should be valid"

        try:
            prompt = GENERATE_ASSERTION_DESCRIPTION_PROMPT.format(
                method=method,
                path=path,
                field_path=field_path,
                field_value=str(field_value),
                assertion_type=assertion_type,
                context=json.dumps(context, ensure_ascii=False) if context else "无",
            )

            description = self.llm_provider.generate(prompt)
            return description.strip()

        except Exception as e:
            self.logger.warning(f"Failed to generate description: {e}")
            return f"Field {field_path} should be valid"

    def analyze_historical_patterns(
        self,
        flows: List[TrafficFlow],
        historical_patterns: Dict[str, Any]
    ) -> List[SemanticAssertion]:
        """Analyze historical patterns using LLM.

        Args:
            flows: List of traffic flows
            historical_patterns: Historical pattern data

        Returns:
            List of semantic assertions based on patterns
        """
        if not self.llm_provider or not flows:
            return []

        try:
            # Build historical responses summary
            responses_summary = []
            for flow in flows[:5]:  # Limit to 5 responses for prompt size
                response_data = flow.response.get_body_json()
                if response_data:
                    responses_summary.append({
                        "url": flow.request.url,
                        "data": truncate_json_for_prompt(response_data, 500),
                    })

            prompt = ANALYZE_HISTORICAL_PATTERNS_PROMPT.format(
                method=flows[0].request.method if flows else "GET",
                path=flows[0].request.url if flows else "/",
                historical_responses=json.dumps(
                    responses_summary, ensure_ascii=False, indent=2
                ),
            )

            result = self.llm_provider.generate_json(prompt)

            assertions = []
            for field_data in result.get("recommended_assertions", []):
                assertion = SemanticAssertion(
                    field_path=field_data.get("path", ""),
                    business_meaning=field_data.get("description", ""),
                    assertion_type=field_data.get("assertion_type", "not_null"),
                    description=field_data.get("description", ""),
                    expected_value=field_data.get("expected_value"),
                    confidence=field_data.get("confidence", 0.8),
                )
                assertions.append(assertion)

            return assertions

        except Exception as e:
            self.logger.error(f"Historical pattern analysis failed: {e}")
            return []

    def generate_semantic_assertions(
        self,
        flow: TrafficFlow,
        endpoint: Optional[APIEndpoint] = None,
        business_logic: Optional[str] = None
    ) -> List[AssertionRule]:
        """Generate semantic assertions for a traffic flow.

        Args:
            flow: TrafficFlow to analyze
            endpoint: Optional API endpoint definition
            business_logic: Optional business logic description

        Returns:
            List of AssertionRule objects
        """
        response_data = flow.response.get_body_json()
        if not response_data:
            return []

        # Analyze response structure
        analysis = self.analyze_response_structure(
            endpoint, response_data, business_logic
        )

        # Convert semantic assertions to assertion rules
        rules = []
        for semantic_assertion in analysis.key_fields:
            rule = semantic_assertion.to_assertion_rule(flow.flow_id)
            rules.append(rule)

        return rules

    def enhance_assertion_description(
        self,
        assertion: AssertionRule,
        flow: TrafficFlow
    ) -> AssertionRule:
        """Enhance an assertion with a better description.

        Args:
            assertion: Original assertion rule
            flow: Traffic flow for context

        Returns:
            Enhanced assertion rule
        """
        if not self.llm_provider or assertion.actual_jsonpath is None:
            return assertion

        response_data = flow.response.get_body_json()
        if not response_data:
            return assertion

        field_value = extract_jsonpath(response_data, assertion.actual_jsonpath)

        new_description = self.generate_assertion_description(
            field_path=assertion.actual_jsonpath,
            field_value=field_value,
            method=flow.request.method,
            path=flow.request.url,
            assertion_type=assertion.assertion_type.value,
            context={"original_description": assertion.description},
        )

        # Create a new assertion with the enhanced description
        return AssertionRule(
            assertion_type=assertion.assertion_type,
            category=assertion.category,
            description=new_description,
            expected_value=assertion.expected_value,
            actual_jsonpath=assertion.actual_jsonpath,
            threshold=assertion.threshold,
            confidence=assertion.confidence,
            source="llm_enhanced",
            flow_id=assertion.flow_id,
        )