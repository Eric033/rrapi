"""
Smart assertion generation engine with LLM enhancement support.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING
from collections import Counter, defaultdict

from flowgenius.models.api import APIEndpoint, PropertyDefinition, ResponseDefinition, SwaggerDoc
from flowgenius.models.assertion import (
    AssertionRule,
    AssertionSet,
    AssertionType,
    AssertionCategory,
    Snapshot
)
from flowgenius.models.traffic import TrafficFlow
from flowgenius.utils.jsonpath import extract_jsonpath, get_jsonpath_value_type, extract_all_paths
from flowgenius.utils.logger import get_logger

if TYPE_CHECKING:
    from flowgenius.llm.base import LLMProvider
    from flowgenius.llm.assertion_analyzer import LLMAssertionAnalyzer


class AssertionGenerator:
    """Generates assertions for traffic flows with optional LLM enhancement."""

    def __init__(
        self,
        llm_provider: Optional["LLMProvider"] = None,
        enable_llm: bool = True
    ):
        """Initialize assertion generator.

        Args:
            llm_provider: Optional LLM provider for semantic analysis
            enable_llm: Whether to use LLM enhancement if provider is available
        """
        self.logger = get_logger("flowgenius.assertion_generator")
        self.llm_provider = llm_provider
        self.enable_llm = enable_llm and llm_provider is not None
        self._llm_analyzer: Optional["LLMAssertionAnalyzer"] = None

        if self.enable_llm:
            try:
                from flowgenius.llm.assertion_analyzer import LLMAssertionAnalyzer
                self._llm_analyzer = LLMAssertionAnalyzer(llm_provider)
                self.logger.info("LLM-enhanced assertion generation enabled")
            except ImportError:
                self.logger.warning("LLM module not available, falling back to rule-based generation")
                self.enable_llm = False

    def generate_assertions(
        self,
        flow: TrafficFlow,
        swagger_endpoint: Optional[APIEndpoint] = None,
        historical_patterns: Optional[Dict[str, Any]] = None
    ) -> AssertionSet:
        """
        Generate assertions for a single flow.

        Args:
            flow: TrafficFlow to generate assertions for
            swagger_endpoint: Optional Swagger endpoint for schema validation
            historical_patterns: Optional historical response patterns

        Returns:
            AssertionSet containing all assertions
        """
        assertion_set = AssertionSet(flow_id=flow.flow_id)

        # Generate health assertions (status code, response time)
        health_assertions = self._generate_health_assertions(flow)
        for assertion in health_assertions:
            assertion_set.add_assertion(assertion)

        # Generate contract assertions (schema validation)
        if swagger_endpoint:
            contract_assertions = self._generate_contract_assertions(flow, swagger_endpoint)
            for assertion in contract_assertions:
                assertion_set.add_assertion(assertion)

        # Generate semantic assertions (business logic)
        semantic_assertions = self._generate_semantic_assertions(
            flow, historical_patterns, swagger_endpoint
        )
        for assertion in semantic_assertions:
            assertion_set.add_assertion(assertion)

        # Generate snapshot assertions
        snapshot_assertions = self._generate_snapshot_assertions(flow)
        for assertion in snapshot_assertions:
            assertion_set.add_assertion(assertion)

        self.logger.debug(
            f"Generated {len(assertion_set.assertions)} assertions for flow {flow.flow_id}"
        )
        return assertion_set

    def _generate_health_assertions(self, flow: TrafficFlow) -> List[AssertionRule]:
        """Generate health check assertions."""
        assertions = []

        # Status code assertion
        status_assertion = AssertionRule(
            assertion_type=AssertionType.STATUS_CODE,
            category=AssertionCategory.HEALTH,
            description="HTTP status code should indicate success",
            expected_value=200 if flow.response.status_code >= 200 and flow.response.status_code < 300 else flow.response.status_code,
            confidence=1.0,
            source="auto"
        )
        assertions.append(status_assertion)

        # Response time assertion
        if flow.response.time:
            time_assertion = AssertionRule(
                assertion_type=AssertionType.RESPONSE_TIME,
                category=AssertionCategory.HEALTH,
                description="Response time should be acceptable",
                threshold=max(5.0, flow.response.time * 2),  # 2x actual or 5 seconds minimum
                confidence=0.8,
                source="auto"
            )
            assertions.append(time_assertion)

        return assertions

    def _generate_contract_assertions(
        self,
        flow: TrafficFlow,
        endpoint: APIEndpoint
    ) -> List[AssertionRule]:
        """Generate contract validation assertions."""
        assertions = []

        # Get success response definition
        success_response = endpoint.get_success_response()
        if not success_response:
            return assertions

        # Validate against schema
        if success_response.schema:
            schema_assertion = AssertionRule(
                assertion_type=AssertionType.JSON_SCHEMA,
                category=AssertionCategory.CONTRACT,
                description="Response should match API schema",
                schema=success_response.schema,
                confidence=0.9,
                source="swagger"
            )
            assertions.append(schema_assertion)

        # Check required fields
        response_data = flow.response.get_body_json()
        if response_data and success_response.required_fields:
            for field in success_response.required_fields:
                if field in response_data:
                    has_key_assertion = AssertionRule(
                        assertion_type=AssertionType.HAS_KEY,
                        category=AssertionCategory.CONTRACT,
                        description=f"Response should contain required field '{field}'",
                        actual_jsonpath=f"$.{field}",
                        confidence=1.0,
                        source="swagger"
                    )
                    assertions.append(has_key_assertion)

        # Validate field types if properties are defined
        if response_data and success_response.properties:
            for prop_name, prop_def in success_response.properties.items():
                if prop_name in response_data:
                    if prop_def.type:
                        actual_type = get_jsonpath_value_type(response_data, f"$.{prop_name}")
                        if actual_type == prop_def.type:
                            type_assertion = AssertionRule(
                                assertion_type=AssertionType.JSON_PATH,
                                category=AssertionCategory.CONTRACT,
                                description=f"Field '{prop_name}' should be of type {prop_def.type}",
                                actual_jsonpath=f"$.{prop_name}",
                                expected_value=response_data[prop_name],
                                confidence=0.9,
                                source="swagger"
                            )
                            assertions.append(type_assertion)

        return assertions

    def _generate_semantic_assertions(
        self,
        flow: TrafficFlow,
        historical_patterns: Optional[Dict[str, Any]],
        swagger_endpoint: Optional[APIEndpoint] = None
    ) -> List[AssertionRule]:
        """Generate semantic business logic assertions.

        Uses LLM for semantic analysis when available, falls back to rule-based
        generation otherwise.
        """
        response_data = flow.response.get_body_json()
        if not response_data:
            return []

        # Try LLM-enhanced generation first
        if self.enable_llm and self._llm_analyzer:
            try:
                llm_assertions = self._generate_semantic_assertions_llm(
                    flow, response_data, swagger_endpoint, historical_patterns
                )
                if llm_assertions:
                    return llm_assertions
            except Exception as e:
                self.logger.warning(f"LLM semantic analysis failed, falling back: {e}")

        # Fallback to rule-based generation
        return self._generate_semantic_assertions_rule_based(flow, historical_patterns)

    def _generate_semantic_assertions_llm(
        self,
        flow: TrafficFlow,
        response_data: Dict[str, Any],
        swagger_endpoint: Optional[APIEndpoint],
        historical_patterns: Optional[Dict[str, Any]]
    ) -> List[AssertionRule]:
        """Generate semantic assertions using LLM.

        Args:
            flow: TrafficFlow to analyze
            response_data: Response body as dictionary
            swagger_endpoint: Optional API endpoint definition
            historical_patterns: Historical response patterns

        Returns:
            List of AssertionRule objects from LLM analysis
        """
        if not self._llm_analyzer:
            return []

        # Get business logic description
        business_logic = None
        if swagger_endpoint and swagger_endpoint.summary:
            business_logic = swagger_endpoint.summary

        # Generate semantic assertions using LLM
        assertions = self._llm_analyzer.generate_semantic_assertions(
            flow=flow,
            endpoint=swagger_endpoint,
            business_logic=business_logic
        )

        self.logger.debug(
            f"LLM generated {len(assertions)} semantic assertions for flow {flow.flow_id}"
        )

        return assertions

    def _generate_semantic_assertions_rule_based(
        self,
        flow: TrafficFlow,
        historical_patterns: Optional[Dict[str, Any]]
    ) -> List[AssertionRule]:
        """Generate semantic assertions using rule-based approach.

        Args:
            flow: TrafficFlow to analyze
            historical_patterns: Historical response patterns

        Returns:
            List of AssertionRule objects from rule-based analysis
        """
        assertions = []
        response_data = flow.response.get_body_json()

        if not response_data:
            return assertions

        # Common semantic patterns
        semantic_fields = [
            "code", "status", "success", "error", "message",
            "result", "data"
        ]

        for field in semantic_fields:
            if field in response_data:
                value = response_data[field]

                # Boolean success pattern
                if field == "success" and isinstance(value, bool):
                    if value:
                        assertion = AssertionRule(
                            assertion_type=AssertionType.EQUALS,
                            category=AssertionCategory.SEMANTIC,
                            description="Response should indicate success",
                            actual_jsonpath=f"$.{field}",
                            expected_value=True,
                            confidence=0.8,
                            source="auto",
                            is_extracted=True
                        )
                        assertions.append(assertion)

                # Code pattern (usually 0 for success)
                elif field == "code" and isinstance(value, int):
                    if value == 0:
                        assertion = AssertionRule(
                            assertion_type=AssertionType.EQUALS,
                            category=AssertionCategory.SEMANTIC,
                            description="Response code should indicate success",
                            actual_jsonpath=f"$.{field}",
                            expected_value=0,
                            confidence=0.8,
                            source="auto",
                            is_extracted=True
                        )
                        assertions.append(assertion)

                # Status pattern
                elif field == "status" and isinstance(value, str):
                    if value.lower() in ("success", "ok", "completed"):
                        assertion = AssertionRule(
                            assertion_type=AssertionType.EQUALS,
                            category=AssertionCategory.SEMANTIC,
                            description=f"Response status should be '{value}'",
                            actual_jsonpath=f"$.{field}",
                            expected_value=value,
                            confidence=0.7,
                            source="auto",
                            is_extracted=True
                        )
                        assertions.append(assertion)

        # Check historical patterns if available
        if historical_patterns:
            historical_assertions = self._generate_historical_assertions(
                flow, historical_patterns
            )
            assertions.extend(historical_assertions)

        return assertions

    def _generate_historical_assertions(
        self,
        flow: TrafficFlow,
        historical_patterns: Dict[str, Any]
    ) -> List[AssertionRule]:
        """Generate assertions based on historical patterns."""
        assertions = []

        url = flow.request.url
        response_data = flow.response.get_body_json()

        if not response_data:
            return assertions

        # Check if this URL has historical data
        if url in historical_patterns:
            patterns = historical_patterns[url]

            # Check for consistent fields
            for field_path, pattern_info in patterns.items():
                if pattern_info.get("consistent", False):
                    expected_value = pattern_info.get("value")
                    if expected_value is not None:
                        assertion = AssertionRule(
                            assertion_type=AssertionType.EQUALS,
                            category=AssertionCategory.SEMANTIC,
                            description=f"Field '{field_path}' should consistently equal '{expected_value}'",
                            actual_jsonpath=field_path,
                            expected_value=expected_value,
                            confidence=pattern_info.get("confidence", 0.9),
                            source="historical",
                            is_extracted=True
                        )
                        assertions.append(assertion)

        return assertions

    def _generate_snapshot_assertions(self, flow: TrafficFlow) -> List[AssertionRule]:
        """Generate snapshot comparison assertions."""
        assertions = []

        response_data = flow.response.get_body_json()
        if not response_data:
            return assertions

        # Create snapshot assertions for key fields
        snapshot_fields = ["code", "success", "status", "data"]

        for field in snapshot_fields:
            if field in response_data:
                assertion = AssertionRule(
                    assertion_type=AssertionType.SNAPSHOT,
                    category=AssertionCategory.SNAPSHOT,
                    description=f"Field '{field}' should match snapshot",
                    actual_jsonpath=f"$.{field}",
                    expected_jsonpath=f"$.{field}",
                    confidence=0.6,
                    source="snapshot"
                )
                assertions.append(assertion)

        return assertions


class PatternAnalyzer:
    """Analyzes historical traffic to identify patterns."""

    def __init__(self):
        """Initialize pattern analyzer."""
        self.logger = get_logger("flowgenius.pattern_analyzer")

    def analyze_patterns(
        self,
        flows: List[TrafficFlow]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze flows to identify consistent patterns.

        Args:
            flows: List of TrafficFlow objects

        Returns:
            Dictionary mapping URLs to pattern information
        """
        patterns = defaultdict(lambda: defaultdict(list))

        # Group flows by URL
        url_flows = defaultdict(list)
        for flow in flows:
            url_flows[flow.request.url].append(flow)

        # Analyze each URL's responses
        for url, url_flow_list in url_flows.items():
            for flow in url_flow_list:
                response_data = flow.response.get_body_json()
                if response_data:
                    # Extract all fields and their values
                    paths = extract_all_paths(response_data)
                    for path in paths:
                        value = extract_jsonpath(response_data, path)
                        if value is not None:
                            patterns[url][path].append(value)

        # Analyze consistency for each field
        results = {}
        for url, field_data in patterns.items():
            results[url] = {}
            for field_path, values in field_data.items():
                # Check if all values are the same
                if len(set(str(v) for v in values)) == 1:
                    results[url][field_path] = {
                        "value": values[0],
                        "consistent": True,
                        "confidence": 1.0,
                        "count": len(values)
                    }
                else:
                    results[url][field_path] = {
                        "value": None,
                        "consistent": False,
                        "confidence": 0.0,
                        "count": len(values)
                    }

        return results


class SnapshotManager:
    """Manages response snapshots for regression testing."""

    def __init__(self, snapshot_dir: str = "."):
        """
        Initialize snapshot manager.

        Args:
            snapshot_dir: Directory to store snapshots
        """
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger("flowgenius.snapshot_manager")

    def save_snapshot(
        self,
        flow: TrafficFlow,
        field_path: str,
        description: Optional[str] = None
    ) -> Snapshot:
        """
        Save a snapshot for a specific field.

        Args:
            flow: TrafficFlow to snapshot
            field_path: JSONPath to snapshot
            description: Optional description

        Returns:
            Snapshot object
        """
        response_data = flow.response.get_body_json()
        if not response_data:
            raise ValueError("Response body is not JSON")

        value = extract_jsonpath(response_data, field_path)
        if value is None:
            raise ValueError(f"Field {field_path} not found in response")

        snapshot = Snapshot(
            flow_id=flow.flow_id,
            jsonpath=field_path,
            value=value,
            timestamp=datetime.now().isoformat(),
            description=description
        )

        # Save to file
        snapshot_file = self._get_snapshot_file(flow.flow_id)
        self._save_snapshots_to_file(snapshot_file, [snapshot])

        self.logger.debug(f"Saved snapshot for {flow.flow_id}: {field_path}")
        return snapshot

    def load_snapshot(self, flow_id: str, field_path: str) -> Optional[Snapshot]:
        """
        Load a snapshot for a specific field.

        Args:
            flow_id: Flow ID
            field_path: JSONPath to load

        Returns:
            Snapshot object or None
        """
        snapshot_file = self._get_snapshot_file(flow_id)
        if not snapshot_file.exists():
            return None

        snapshots = self._load_snapshots_from_file(snapshot_file)
        for snapshot in snapshots:
            if snapshot.jsonpath == field_path:
                return snapshot

        return None

    def _get_snapshot_file(self, flow_id: str) -> Path:
        """Get the snapshot file path for a flow."""
        # Use first 8 chars of flow_id as filename
        filename = f"snapshot_{flow_id[:8]}.json"
        return self.snapshot_dir / filename

    def _save_snapshots_to_file(self, snapshot_file: Path, snapshots: List[Snapshot]):
        """Save snapshots to file."""
        data = [s.to_dict() for s in snapshots]
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_snapshots_from_file(self, snapshot_file: Path) -> List[Snapshot]:
        """Load snapshots from file."""
        with open(snapshot_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [Snapshot.from_dict(item) for item in data]

    def compare_to_snapshot(
        self,
        flow: TrafficFlow,
        snapshot: Snapshot
    ) -> bool:
        """
        Compare flow response to snapshot.

        Args:
            flow: TrafficFlow to compare
            snapshot: Snapshot to compare against

        Returns:
            True if matches snapshot
        """
        response_data = flow.response.get_body_json()
        if not response_data:
            return False

        current_value = extract_jsonpath(response_data, snapshot.jsonpath)
        return current_value == snapshot.value


class Validator:
    """Main validation orchestration with optional LLM enhancement."""

    def __init__(
        self,
        llm_provider: Optional["LLMProvider"] = None,
        enable_llm: bool = True
    ):
        """Initialize validator.

        Args:
            llm_provider: Optional LLM provider for semantic analysis
            enable_llm: Whether to use LLM enhancement if provider is available
        """
        self.assertion_generator = AssertionGenerator(llm_provider, enable_llm)
        self.pattern_analyzer = PatternAnalyzer()
        self.snapshot_manager = SnapshotManager()
        self.logger = get_logger("flowgenius.validator")
        self.llm_provider = llm_provider

        if llm_provider and enable_llm:
            self.logger.info("Validator initialized with LLM enhancement")

    def generate_all_assertions(
        self,
        flows: List[TrafficFlow],
        swagger_doc: Optional[SwaggerDoc] = None,
        snapshot_dir: Optional[str] = None
    ) -> Dict[str, AssertionSet]:
        """
        Generate assertions for all flows.

        Args:
            flows: List of TrafficFlow objects
            swagger_doc: Optional SwaggerDoc for schema validation
            snapshot_dir: Optional directory for snapshots

        Returns:
            Dictionary mapping flow IDs to AssertionSets
        """
        # Initialize snapshot manager if directory provided
        if snapshot_dir:
            self.snapshot_manager = SnapshotManager(snapshot_dir)

        # Analyze historical patterns
        historical_patterns = self.pattern_analyzer.analyze_patterns(flows)

        # Generate assertions for each flow
        assertion_sets = {}

        for flow in flows:
            # Find matching Swagger endpoint
            endpoint = None
            if swagger_doc:
                endpoint = swagger_doc.find_endpoint_by_url(flow.request.url)

            # Generate assertions
            assertion_set = self.assertion_generator.generate_assertions(
                flow,
                endpoint,
                historical_patterns.get(flow.request.url)
            )
            assertion_sets[flow.flow_id] = assertion_set

        self.logger.info(f"Generated assertions for {len(assertion_sets)} flows")
        return assertion_sets

    def validate_assertions(
        self,
        flow: TrafficFlow,
        assertion_set: AssertionSet
    ) -> Dict[str, bool]:
        """
        Validate assertions against a flow's response.

        Args:
            flow: TrafficFlow to validate
            assertion_set: AssertionSet containing assertions

        Returns:
            Dictionary mapping assertion descriptions to pass/fail results
        """
        results = {}
        response_data = flow.response.get_body_json() or {}

        for assertion in assertion_set.assertions:
            try:
                result = self._validate_single_assertion(flow, response_data, assertion)
                results[assertion.description] = result
            except Exception as e:
                self.logger.error(f"Failed to validate assertion: {e}")
                results[assertion.description] = False

        return results

    def _validate_single_assertion(
        self,
        flow: TrafficFlow,
        response_data: Dict[str, Any],
        assertion: AssertionRule
    ) -> bool:
        """Validate a single assertion."""
        if assertion.assertion_type == AssertionType.STATUS_CODE:
            expected = assertion.expected_value
            if isinstance(expected, list):
                return flow.response.status_code in expected
            return flow.response.status_code == expected

        elif assertion.assertion_type == AssertionType.RESPONSE_TIME:
            if assertion.threshold and flow.response.time:
                return flow.response.time < assertion.threshold
            return flow.response.time is not None and flow.response.time > 0

        elif assertion.assertion_type == AssertionType.HAS_KEY:
            if assertion.actual_jsonpath:
                value = extract_jsonpath(response_data, assertion.actual_jsonpath)
                return value is not None

        elif assertion.assertion_type == AssertionType.EQUALS:
            if assertion.actual_jsonpath:
                value = extract_jsonpath(response_data, assertion.actual_jsonpath)
                return value == assertion.expected_value

        elif assertion.assertion_type == AssertionType.SNAPSHOT:
            snapshot = self.snapshot_manager.load_snapshot(flow.flow_id, assertion.actual_jsonpath or "")
            if snapshot:
                return self.snapshot_manager.compare_to_snapshot(flow, snapshot)

        return True  # Default to True for unimplemented assertion types