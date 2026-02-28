"""
LLM-enhanced correlation analysis module.

This module provides intelligent correlation analysis capabilities using LLM
to understand semantic relationships between API requests and responses.
"""
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from flowgenius.llm.base import LLMProvider
from flowgenius.llm.config import LLMConfig
from flowgenius.llm.prompt_templates import (
    EXPLAIN_CORRELATION_PROMPT,
    DETECT_FLOW_PATTERN_PROMPT,
    SUGGEST_VARIABLE_NAME_PROMPT,
    build_flow_sequence_description,
)
from flowgenius.models.correlation import CorrelationRule, CorrelationChain
from flowgenius.models.traffic import TrafficFlow
from flowgenius.utils.logger import get_logger
from flowgenius.utils.jsonpath import extract_jsonpath


@dataclass
class CorrelationExplanation:
    """Represents an explanation of a correlation.

    Attributes:
        correlation_type: Type of correlation (authentication, data_reference, etc.)
        variable_name: Suggested variable name (English)
        variable_name_cn: Variable name in Chinese
        explanation: Explanation of why this correlation exists
        extraction_method: How to extract the value (jsonpath, regex, header)
        extraction_expression: Expression to use for extraction
        usage_template: Template for using the variable
        confidence: Confidence level of the explanation
    """

    correlation_type: str
    variable_name: str
    variable_name_cn: str
    explanation: str
    extraction_method: str = "jsonpath"
    extraction_expression: str = ""
    usage_template: str = "{variable_name}"
    confidence: float = 0.8


@dataclass
class FlowPattern:
    """Represents a detected business flow pattern.

    Attributes:
        flow_name: Name of the flow (in Chinese)
        flow_description: Description of the flow
        steps: List of steps in the flow
        variables: Variables used in the flow
        error_handling: Error handling configuration
    """

    flow_name: str
    flow_description: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    variables: List[Dict[str, Any]] = field(default_factory=list)
    error_handling: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VariableNameSuggestion:
    """Represents a suggested variable name.

    Attributes:
        variable_name: Variable name in English (snake_case)
        variable_name_cn: Variable name in Chinese
        description: Description of what the variable represents
        naming_rationale: Why this name was chosen
    """

    variable_name: str
    variable_name_cn: str
    description: str
    naming_rationale: str = ""


class LLMCorrelationAnalyzer:
    """LLM-enhanced correlation analyzer.

    This class uses LLM to analyze correlations between API requests
    and provide semantic understanding of data flow.
    """

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        config: Optional[LLMConfig] = None
    ):
        """Initialize the LLM correlation analyzer.

        Args:
            llm_provider: LLM provider instance
            config: LLM configuration
        """
        self.llm_provider = llm_provider
        self.config = config or LLMConfig()
        self.logger = get_logger("flowgenius.llm.correlation_analyzer")

    def explain_correlation(
        self,
        source_flow: TrafficFlow,
        target_flow: TrafficFlow,
        source_field: str,
        target_location: str,
        matched_values: Optional[Dict[str, Any]] = None
    ) -> CorrelationExplanation:
        """Explain a correlation between two flows.

        Args:
            source_flow: Flow that provides the value
            target_flow: Flow that uses the value
            source_field: JSONPath of the source field
            target_location: Where the value is used in target
            matched_values: Matched values for context

        Returns:
            CorrelationExplanation with semantic understanding
        """
        if not self.llm_provider:
            return self._fallback_explanation(
                source_flow, target_flow, source_field, target_location
            )

        try:
            # Extract values for context
            source_response = source_flow.response.get_body_json() or {}
            source_value = extract_jsonpath(source_response, source_field)

            prompt = EXPLAIN_CORRELATION_PROMPT.format(
                source_url=source_flow.request.url,
                source_field=source_field,
                source_value=str(source_value)[:100] if source_value else "N/A",
                target_url=target_flow.request.url,
                target_location=target_location,
                target_value=str(matched_values)[:100] if matched_values else "N/A",
            )

            result = self.llm_provider.generate_json(prompt)

            return CorrelationExplanation(
                correlation_type=result.get("correlation_type", "data_reference"),
                variable_name=result.get("variable_name", "extracted_value"),
                variable_name_cn=result.get("variable_name_cn", "提取的值"),
                explanation=result.get("explanation", ""),
                extraction_method=result.get("extraction_method", "jsonpath"),
                extraction_expression=result.get("extraction_expression", source_field),
                usage_template=result.get("usage_template", "{variable_name}"),
                confidence=result.get("confidence", 0.8),
            )

        except Exception as e:
            self.logger.error(f"LLM correlation explanation failed: {e}")
            return self._fallback_explanation(
                source_flow, target_flow, source_field, target_location
            )

    def _fallback_explanation(
        self,
        source_flow: TrafficFlow,
        target_flow: TrafficFlow,
        source_field: str,
        target_location: str
    ) -> CorrelationExplanation:
        """Generate a fallback explanation.

        Args:
            source_flow: Source flow
            target_flow: Target flow
            source_field: Source field path
            target_location: Target location

        Returns:
            Basic CorrelationExplanation
        """
        # Generate variable name from source field
        field_parts = source_field.replace("$.data.", "").replace("$.", "").split(".")
        variable_name = "_".join(field_parts).lower()

        # Infer correlation type
        correlation_type = "data_reference"
        if "token" in source_field.lower() or "auth" in target_location.lower():
            correlation_type = "authentication"
        elif "session" in source_field.lower():
            correlation_type = "session"
        elif source_field.endswith("_id"):
            correlation_type = "data_reference"

        return CorrelationExplanation(
            correlation_type=correlation_type,
            variable_name=variable_name,
            variable_name_cn=variable_name,
            explanation=f"Value from {source_field} used in {target_location}",
            extraction_method="jsonpath",
            extraction_expression=source_field,
            usage_template="{variable_name}",
            confidence=0.6,
        )

    def suggest_variable_name(
        self,
        field_path: str,
        field_value: Any,
        api_endpoint: str,
        context: Optional[Dict[str, Any]] = None
    ) -> VariableNameSuggestion:
        """Suggest a semantic variable name.

        Args:
            field_path: JSONPath to the field
            field_value: Value of the field
            api_endpoint: API endpoint URL
            context: Additional context

        Returns:
            VariableNameSuggestion with semantic name
        """
        if not self.llm_provider:
            return self._fallback_variable_name(field_path, field_value)

        try:
            prompt = SUGGEST_VARIABLE_NAME_PROMPT.format(
                field_path=field_path,
                field_value=str(field_value)[:100] if field_value else "N/A",
                api_endpoint=api_endpoint,
                context=json.dumps(context, ensure_ascii=False) if context else "无",
            )

            result = self.llm_provider.generate_json(prompt)

            return VariableNameSuggestion(
                variable_name=result.get("variable_name", "extracted_value"),
                variable_name_cn=result.get("variable_name_cn", "提取的值"),
                description=result.get("description", ""),
                naming_rationale=result.get("naming_rationale", ""),
            )

        except Exception as e:
            self.logger.warning(f"Failed to suggest variable name: {e}")
            return self._fallback_variable_name(field_path, field_value)

    def _fallback_variable_name(
        self,
        field_path: str,
        field_value: Any
    ) -> VariableNameSuggestion:
        """Generate a fallback variable name.

        Args:
            field_path: Field path
            field_value: Field value

        Returns:
            Basic VariableNameSuggestion
        """
        field_parts = field_path.replace("$.data.", "").replace("$.", "").split(".")
        variable_name = "_".join(field_parts).lower()

        # Generate Chinese name based on common patterns
        name_mapping = {
            "token": "认证令牌",
            "id": "标识符",
            "user_id": "用户ID",
            "session_id": "会话ID",
            "name": "名称",
            "status": "状态",
            "code": "响应码",
            "message": "消息",
        }

        last_part = field_parts[-1] if field_parts else ""
        variable_name_cn = name_mapping.get(last_part.lower(), last_part)

        return VariableNameSuggestion(
            variable_name=variable_name,
            variable_name_cn=variable_name_cn,
            description=f"Value from {field_path}",
            naming_rationale="Generated from field path",
        )

    def detect_flow_pattern(
        self,
        flows: List[TrafficFlow]
    ) -> FlowPattern:
        """Detect a business flow pattern from a sequence of flows.

        Args:
            flows: List of TrafficFlow objects in sequence

        Returns:
            FlowPattern describing the detected business flow
        """
        if not flows:
            return FlowPattern(flow_name="空流程")

        if not self.llm_provider:
            return self._fallback_flow_pattern(flows)

        try:
            # Build flow sequence description
            flow_sequence = self._build_flow_sequence(flows)

            prompt = DETECT_FLOW_PATTERN_PROMPT.format(
                flow_sequence=flow_sequence
            )

            result = self.llm_provider.generate_json(prompt)

            return FlowPattern(
                flow_name=result.get("flow_name", "未命名流程"),
                flow_description=result.get("flow_description", ""),
                steps=result.get("steps", []),
                variables=result.get("variables", []),
                error_handling=result.get("error_handling", {}),
            )

        except Exception as e:
            self.logger.error(f"LLM flow pattern detection failed: {e}")
            return self._fallback_flow_pattern(flows)

    def _fallback_flow_pattern(self, flows: List[TrafficFlow]) -> FlowPattern:
        """Generate a fallback flow pattern.

        Args:
            flows: List of TrafficFlow objects

        Returns:
            Basic FlowPattern
        """
        steps = []
        variables = []

        for i, flow in enumerate(flows, 1):
            # Generate step description
            from urllib.parse import urlparse
            parsed = urlparse(flow.request.url)

            method_actions = {
                "GET": "查询",
                "POST": "创建",
                "PUT": "更新",
                "DELETE": "删除",
                "PATCH": "更新",
            }

            action = method_actions.get(flow.request.method, "请求")

            steps.append({
                "order": i,
                "api": parsed.path,
                "method": flow.request.method,
                "action": f"{action}操作",
                "purpose": "",
                "extracts": [],
                "is_required": True,
            })

        return FlowPattern(
            flow_name=f"API流程 ({len(flows)}个请求)",
            flow_description="自动检测的API调用序列",
            steps=steps,
            variables=variables,
            error_handling={},
        )

    def _build_flow_sequence(self, flows: List[TrafficFlow]) -> str:
        """Build a flow sequence description for the prompt.

        Args:
            flows: List of TrafficFlow objects

        Returns:
            Formatted flow sequence string
        """
        lines = []

        for i, flow in enumerate(flows, 1):
            from urllib.parse import urlparse
            parsed = urlparse(flow.request.url)

            lines.append(f"{i}. {flow.request.method} {parsed.path}")

            # Add request info
            if flow.request.query_params:
                params_str = json.dumps(flow.request.query_params, ensure_ascii=False)
                lines.append(f"   参数: {params_str[:100]}")

            # Add response info
            response_data = flow.response.get_body_json()
            if response_data:
                # Show only top-level keys
                if isinstance(response_data, dict):
                    keys = list(response_data.keys())[:5]
                    lines.append(f"   响应字段: {', '.join(keys)}")

        return "\n".join(lines)

    def enhance_correlation_chain(
        self,
        chain: CorrelationChain,
        flows: List[TrafficFlow]
    ) -> CorrelationChain:
        """Enhance a correlation chain with semantic understanding.

        Args:
            chain: Original CorrelationChain
            flows: List of TrafficFlow objects

        Returns:
            Enhanced CorrelationChain with better variable names
        """
        if not self.llm_provider:
            return chain

        # Create flow lookup
        flow_map = {flow.flow_id: flow for flow in flows}

        # Enhance each correlation
        enhanced_correlations = []
        for correlation in chain.correlations:
            source_flow = flow_map.get(correlation.response_flow_id)
            target_flow = flow_map.get(correlation.request_flow_id)

            if source_flow and target_flow:
                explanation = self.explain_correlation(
                    source_flow=source_flow,
                    target_flow=target_flow,
                    source_field=correlation.response_jsonpath,
                    target_location=correlation.request_location,
                )

                # Update variable name if better suggestion
                if explanation.variable_name:
                    correlation.variable_name = explanation.variable_name

            enhanced_correlations.append(correlation)

        # Create new chain with enhanced correlations
        from flowgenius.models.correlation import CorrelationChain
        enhanced_chain = CorrelationChain(
            flow_ids=chain.flow_ids,
            correlations=enhanced_correlations,
            variables=chain.variables,
        )

        return enhanced_chain

    def generate_correlation_summary(
        self,
        chain: CorrelationChain,
        flows: List[TrafficFlow]
    ) -> str:
        """Generate a human-readable summary of correlations.

        Args:
            chain: CorrelationChain
            flows: List of TrafficFlow objects

        Returns:
            Summary string
        """
        if not chain.correlations:
            return "未发现请求之间的关联关系。"

        flow_map = {flow.flow_id: flow for flow in flows}
        lines = [f"发现 {len(chain.correlations)} 个关联关系：", ""]

        for i, correlation in enumerate(chain.correlations, 1):
            source_flow = flow_map.get(correlation.response_flow_id)
            target_flow = flow_map.get(correlation.request_flow_id)

            source_url = source_flow.request.url if source_flow else correlation.response_flow_id
            target_url = target_flow.request.url if target_flow else correlation.request_flow_id

            lines.append(f"{i}. {correlation.variable_name}")
            lines.append(f"   来源: {source_url}")
            lines.append(f"   字段: {correlation.response_jsonpath}")
            lines.append(f"   用于: {target_url} ({correlation.request_location})")
            lines.append("")

        return "\n".join(lines)