"""
Intelligent correlation analysis engine with LLM enhancement support.
"""
import logging
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING
from collections import defaultdict

from flowgenius.models.traffic import TrafficFlow
from flowgenius.models.correlation import (
    CorrelationRule,
    CorrelationChain,
    ExtractionRule,
    VariableReference
)
from flowgenius.utils.jsonpath import (
    extract_all_paths,
    extract_jsonpath,
    get_jsonpath_value_type
)
from flowgenius.utils.logger import get_logger
from flowgenius.utils.regex_utils import extract_tokens, extract_ids

if TYPE_CHECKING:
    from flowgenius.llm.base import LLMProvider
    from flowgenius.llm.correlation_analyzer import LLMCorrelationAnalyzer


class FlowCorrelator:
    """Analyzes traffic flows to identify correlations.

    Supports optional LLM enhancement for semantic correlation analysis.
    """

    def __init__(
        self,
        llm_provider: Optional["LLMProvider"] = None,
        enable_llm: bool = True
    ):
        """Initialize flow correlator.

        Args:
            llm_provider: Optional LLM provider for semantic analysis
            enable_llm: Whether to use LLM enhancement if provider is available
        """
        self.logger = get_logger("flowgenius.correlator")
        self.llm_provider = llm_provider
        self.enable_llm = enable_llm and llm_provider is not None
        self._llm_analyzer: Optional["LLMCorrelationAnalyzer"] = None

        if self.enable_llm:
            try:
                from flowgenius.llm.correlation_analyzer import LLMCorrelationAnalyzer
                self._llm_analyzer = LLMCorrelationAnalyzer(llm_provider)
                self.logger.info("LLM-enhanced correlation analysis enabled")
            except ImportError:
                self.logger.warning("LLM module not available, falling back to rule-based analysis")
                self.enable_llm = False

    def analyze_flows(self, flows: List[TrafficFlow], enhance_with_llm: bool = True) -> CorrelationChain:
        """
        Analyze flows to identify correlations.

        Args:
            flows: List of TrafficFlow objects
            enhance_with_llm: Whether to enhance correlations with LLM (if available)

        Returns:
            CorrelationChain with identified correlations
        """
        self.logger.info(f"Analyzing {len(flows)} flows for correlations")

        chain = CorrelationChain()
        for flow in flows:
            chain.add_flow(flow.flow_id)

        # Identify correlations between flows
        correlations = self._identify_correlations(flows)
        for correlation in correlations:
            chain.add_correlation(correlation)

        self.logger.info(f"Found {len(correlations)} correlations")

        # Enhance with LLM if available and requested
        if enhance_with_llm and self.enable_llm and self._llm_analyzer:
            try:
                chain = self._llm_analyzer.enhance_correlation_chain(chain, flows)
                self.logger.info("Enhanced correlations with LLM analysis")
            except Exception as e:
                self.logger.warning(f"LLM enhancement failed: {e}")

        return chain

    def _identify_correlations(self, flows: List[TrafficFlow]) -> List[CorrelationRule]:
        """
        Identify correlations between flows.

        Args:
            flows: List of TrafficFlow objects to analyze

        Returns:
            List of CorrelationRule objects
        """
        correlations = []

        # Extract values from all responses
        response_values = self._extract_response_values(flows)

        # Find matching patterns between responses and requests
        for i, target_flow in enumerate(flows):
            for j, source_flow in enumerate(flows):
                if i == j:
                    continue

                # Only look for correlations from earlier flows (chronological)
                if source_flow.request.timestamp and target_flow.request.timestamp:
                    if source_flow.request.timestamp > target_flow.request.timestamp:
                        continue

                # Check for correlations
                found = self._find_correlations_between_flows(
                    source_flow,
                    target_flow,
                    response_values.get(source_flow.flow_id, {})
                )
                correlations.extend(found)

        return correlations

    def _extract_response_values(self, flows: List[TrafficFlow]) -> Dict[str, Dict[str, Any]]:
        """
        Extract all values from response bodies.

        Args:
            flows: List of TrafficFlow objects

        Returns:
            Dictionary mapping flow IDs to extracted values
        """
        response_values = {}

        for flow in flows:
            response_data = flow.response.get_body_json()
            if response_data:
                # Extract all possible JSONPaths and their values
                paths = extract_all_paths(response_data)
                values = {}
                for path in paths:
                    value = extract_jsonpath(response_data, path)
                    if value is not None:
                        values[path] = value
                response_values[flow.flow_id] = values

        return response_values

    def _find_correlations_between_flows(
        self,
        source_flow: TrafficFlow,
        target_flow: TrafficFlow,
        source_values: Dict[str, Any]
    ) -> List[CorrelationRule]:
        """
        Find correlations between a source flow and target flow.

        Args:
            source_flow: Flow that provides values
            target_flow: Flow that uses values
            source_values: Values extracted from source response

        Returns:
            List of CorrelationRule objects
        """
        correlations = []

        # Check for correlations in request headers
        header_correlations = self._check_header_correlations(
            source_flow, target_flow, source_values
        )
        correlations.extend(header_correlations)

        # Check for correlations in query parameters
        query_correlations = self._check_query_correlations(
            source_flow, target_flow, source_values
        )
        correlations.extend(query_correlations)

        # Check for correlations in request body
        body_correlations = self._check_body_correlations(
            source_flow, target_flow, source_values
        )
        correlations.extend(body_correlations)

        return correlations

    def _check_header_correlations(
        self,
        source_flow: TrafficFlow,
        target_flow: TrafficFlow,
        source_values: Dict[str, Any]
    ) -> List[CorrelationRule]:
        """Check for correlations in request headers."""
        correlations = []

        # Common headers that are often correlated
        correlation_headers = ["Authorization", "X-Auth-Token", "X-Token", "Cookie"]

        for header_name in correlation_headers:
            header_value = target_flow.request.headers.get(header_name)
            if not header_value:
                continue

            # Try to find this value in source response
            for path, value in source_values.items():
                if self._values_match(header_value, value):
                    correlation = CorrelationRule(
                        response_flow_id=source_flow.flow_id,
                        request_flow_id=target_flow.flow_id,
                        response_jsonpath=path,
                        request_location="header",
                        request_key=header_name,
                        confidence=0.9
                    )
                    correlations.append(correlation)
                    self.logger.debug(
                        f"Found header correlation: {header_name} <- {path}"
                    )
                    break

        return correlations

    def _check_query_correlations(
        self,
        source_flow: TrafficFlow,
        target_flow: TrafficFlow,
        source_values: Dict[str, Any]
    ) -> List[CorrelationRule]:
        """Check for correlations in query parameters."""
        correlations = []

        for param_name, param_value in target_flow.request.query_params.items():
            if not param_value:
                continue

            # Look for this value in source response
            for path, value in source_values.items():
                if self._values_match(param_value, str(value)):
                    correlation = CorrelationRule(
                        response_flow_id=source_flow.flow_id,
                        request_flow_id=target_flow.flow_id,
                        response_jsonpath=path,
                        request_location="query",
                        request_key=param_name,
                        confidence=0.8
                    )
                    correlations.append(correlation)
                    self.logger.debug(
                        f"Found query correlation: {param_name} <- {path}"
                    )
                    break

        return correlations

    def _check_body_correlations(
        self,
        source_flow: TrafficFlow,
        target_flow: TrafficFlow,
        source_values: Dict[str, Any]
    ) -> List[CorrelationRule]:
        """Check for correlations in request body."""
        correlations = []

        body_json = target_flow.request.get_body_json()
        if not body_json:
            return correlations

        # Get all paths in target request body
        target_paths = extract_all_paths(body_json)

        for target_path in target_paths:
            target_value = extract_jsonpath(body_json, target_path)
            if target_value is None or target_value == "":
                continue

            # Look for this value in source response
            for source_path, source_value in source_values.items():
                if self._values_match(str(target_value), str(source_value)):
                    # Filter out common values (dates, small numbers, etc.)
                    if self._is_correlation_candidate(target_value, source_value):
                        correlation = CorrelationRule(
                            response_flow_id=source_flow.flow_id,
                            request_flow_id=target_flow.flow_id,
                            response_jsonpath=source_path,
                            request_location="body",
                            request_jsonpath=target_path,
                            confidence=0.7
                        )
                        correlations.append(correlation)
                        self.logger.debug(
                            f"Found body correlation: {target_path} <- {source_path}"
                        )
                        break

        return correlations

    def _values_match(self, value1: str, value2: Any) -> bool:
        """
        Check if two values match.

        Args:
            value1: First value (string)
            value2: Second value (any type)

        Returns:
            True if values match
        """
        str_value2 = str(value2)
        return value1 == str_value2

    def _is_correlation_candidate(self, value1: Any, value2: Any) -> bool:
        """
        Check if a value pair is a valid correlation candidate.

        Args:
            value1: First value
            value2: Second value

        Returns:
            True if values are valid correlation candidates
        """
        # Filter out very short values
        if len(str(value1)) < 3:
            return False

        # Filter out common numbers
        try:
            num = int(value1)
            if num < 100:
                return False
        except (ValueError, TypeError):
            pass

        # Filter out common booleans
        if str(value1).lower() in ("true", "false", "yes", "no"):
            return False

        return True


class VariableExtractor:
    """Extracts variables from traffic flows."""

    def __init__(self):
        """Initialize variable extractor."""
        self.logger = get_logger("flowgenius.variable_extractor")

    def extract_variables(self, chain: CorrelationChain, flows: List[TrafficFlow]) -> Dict[str, Any]:
        """
        Extract variable values from flows based on correlation chain.

        Args:
            chain: CorrelationChain with rules
            flows: List of TrafficFlow objects

        Returns:
            Dictionary of variable names to values
        """
        variables = {}

        # Create flow lookup
        flow_map = {flow.flow_id: flow for flow in flows}

        # Process correlations in dependency order
        ordered_flow_ids = chain.get_ordered_flow_ids()

        for flow_id in ordered_flow_ids:
            flow = flow_map.get(flow_id)
            if not flow:
                continue

            # Get extraction rules for this flow
            extraction_rules = chain.get_extraction_rules(flow_id)

            for rule in extraction_rules:
                response_data = flow.response.get_body_json()
                if response_data:
                    value = extract_jsonpath(response_data, rule.source_jsonpath)
                    if value is not None:
                        variables[rule.variable_name] = value
                        self.logger.debug(
                            f"Extracted variable: {rule.variable_name} = {value}"
                        )

        chain.variables = variables
        return variables

    def generate_extraction_rules(self, chain: CorrelationChain) -> List[ExtractionRule]:
        """
        Generate extraction rules from correlation chain.

        Args:
            chain: CorrelationChain

        Returns:
            List of ExtractionRule objects
        """
        rules = []

        for correlation in chain.correlations:
            # Only create extraction for the first occurrence of each variable
            if not any(r.variable_name == correlation.variable_name for r in rules):
                rule = ExtractionRule(
                    source_flow_id=correlation.response_flow_id,
                    source_jsonpath=correlation.response_jsonpath,
                    variable_name=correlation.variable_name,
                    description=f"Extract {correlation.variable_name} from response"
                )
                rules.append(rule)

        return rules

    def generate_variable_references(self, chain: CorrelationChain) -> List[VariableReference]:
        """
        Generate variable references from correlation chain.

        Args:
            chain: CorrelationChain

        Returns:
            List of VariableReference objects
        """
        references = []

        for flow_id in chain.flow_ids:
            flow_refs = chain.get_flow_variables(flow_id)
            references.extend(flow_refs)

        return references


class ChainAnalyzer:
    """Analyzes correlation chains and builds dependency graphs."""

    def __init__(self):
        """Initialize chain analyzer."""
        self.logger = get_logger("flowgenius.chain_analyzer")

    def analyze_chain(self, chain: CorrelationChain) -> Dict[str, Any]:
        """
        Analyze a correlation chain and extract insights.

        Args:
            chain: CorrelationChain

        Returns:
            Analysis results dictionary
        """
        # Get ordered flows
        ordered_flows = chain.get_ordered_flow_ids()

        # Calculate depth of each flow in the chain
        depths = self._calculate_depths(chain)

        # Find root flows (no dependencies)
        roots = self._find_roots(chain)

        # Find leaf flows (nothing depends on them)
        leaves = self._find_leaves(chain)

        # Find isolated flows (no correlations)
        isolated = self._find_isolated(chain)

        return {
            "total_flows": len(chain.flow_ids),
            "total_correlations": len(chain.correlations),
            "max_depth": max(depths.values()) if depths else 0,
            "roots": roots,
            "leaves": leaves,
            "isolated": isolated,
            "ordered_flow_ids": ordered_flows,
            "depths": depths
        }

    def _calculate_depths(self, chain: CorrelationChain) -> Dict[str, int]:
        """Calculate dependency depth for each flow."""
        depths = {}
        visited = set()

        def calculate_depth(flow_id: str) -> int:
            if flow_id in depths:
                return depths[flow_id]

            if flow_id in visited:
                # Circular dependency, return 0
                depths[flow_id] = 0
                return 0

            visited.add(flow_id)

            dependencies = chain.get_dependencies(flow_id)
            if not dependencies:
                depths[flow_id] = 0
            else:
                max_dep_depth = max(calculate_depth(dep) for dep in dependencies)
                depths[flow_id] = max_dep_depth + 1

            visited.remove(flow_id)
            return depths[flow_id]

        for flow_id in chain.flow_ids:
            if flow_id not in depths:
                calculate_depth(flow_id)

        return depths

    def _find_roots(self, chain: CorrelationChain) -> List[str]:
        """Find root flows (no dependencies)."""
        roots = []
        for flow_id in chain.flow_ids:
            if not chain.get_dependencies(flow_id):
                roots.append(flow_id)
        return roots

    def _find_leaves(self, chain: CorrelationChain) -> List[str]:
        """Find leaf flows (nothing depends on them)."""
        dependent_flows = set()
        for correlation in chain.correlations:
            dependent_flows.add(correlation.request_flow_id)

        leaves = [fid for fid in chain.flow_ids if fid not in dependent_flows]
        return leaves

    def _find_isolated(self, chain: CorrelationChain) -> List[str]:
        """Find isolated flows (no correlations at all)."""
        correlated_flows = set()
        for correlation in chain.correlations:
            correlated_flows.add(correlation.response_flow_id)
            correlated_flows.add(correlation.request_flow_id)

        isolated = [fid for fid in chain.flow_ids if fid not in correlated_flows]
        return isolated

    def detect_cycles(self, chain: CorrelationChain) -> List[List[str]]:
        """
        Detect circular dependencies in the chain.

        Args:
            chain: CorrelationChain

        Returns:
            List of cycles (each cycle is a list of flow IDs)
        """
        cycles = []
        visited = set()
        recursion_stack = set()

        def dfs(flow_id: str, path: List[str]):
            visited.add(flow_id)
            recursion_stack.add(flow_id)
            path.append(flow_id)

            for dep in chain.get_dependencies(flow_id):
                if dep not in visited:
                    dfs(dep, path)
                elif dep in recursion_stack:
                    # Found a cycle
                    cycle_start = path.index(dep)
                    cycle = path[cycle_start:] + [dep]
                    cycles.append(cycle)

            recursion_stack.remove(flow_id)
            path.pop()

        for flow_id in chain.flow_ids:
            if flow_id not in visited:
                dfs(flow_id, [])

        return cycles