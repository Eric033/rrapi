"""
Unit tests for validator.
"""
import pytest
import json
from pathlib import Path

from flowgenius.models.traffic import TrafficRequest, TrafficResponse, TrafficFlow
from flowgenius.models.assertion import AssertionRule, AssertionSet, AssertionType, AssertionCategory
from flowgenius.models.api import APIEndpoint, ResponseDefinition
from flowgenius.core.validator import AssertionGenerator, PatternAnalyzer, SnapshotManager, Validator


class TestAssertionGenerator:
    """Tests for AssertionGenerator."""

    def test_init(self):
        """Test assertion generator initialization."""
        generator = AssertionGenerator()
        assert generator is not None

    def test_generate_health_assertions(self, sample_flow):
        """Test health assertion generation."""
        generator = AssertionGenerator()
        assertions = generator._generate_health_assertions(sample_flow)

        assert len(assertions) >= 1
        assert any(a.assertion_type == AssertionType.STATUS_CODE for a in assertions)

    def test_generate_assertions(self, sample_flow):
        """Test full assertion generation."""
        generator = AssertionGenerator()
        assertion_set = generator.generate_assertions(sample_flow)

        assert isinstance(assertion_set, AssertionSet)
        assert assertion_set.flow_id == sample_flow.flow_id
        assert len(assertion_set.assertions) > 0

    def test_generate_with_swagger_endpoint(self, sample_flow):
        """Test assertion generation with Swagger endpoint."""
        generator = AssertionGenerator()

        # Create mock endpoint
        endpoint = APIEndpoint(
            path="/api/test",
            method="GET",
            responses={
                "200": ResponseDefinition(
                    status_code="200",
                    properties={"id": type('Prop', (), {'name': 'id', 'type': 'integer', 'required': True})()},
                    required_fields=["id"]
                )
            }
        )

        assertion_set = generator.generate_assertions(sample_flow, endpoint)

        # Should have health assertions at minimum
        assert len(assertion_set.get_health_assertions()) > 0

    def test_generate_contract_assertions(self, sample_flow):
        """Test contract assertion generation."""
        generator = AssertionGenerator()

        endpoint = APIEndpoint(
            path="/api/test",
            method="GET",
            responses={"200": ResponseDefinition(status_code="200")}
        )

        assertions = generator._generate_contract_assertions(sample_flow, endpoint)

        # May be empty if no schema defined
        assert isinstance(assertions, list)

    def test_generate_semantic_assertions(self, sample_flow):
        """Test semantic assertion generation."""
        generator = AssertionGenerator()

        assertions = generator._generate_semantic_assertions(sample_flow, None)

        assert isinstance(assertions, list)

    def test_generate_snapshot_assertions(self, sample_flow):
        """Test snapshot assertion generation."""
        generator = AssertionGenerator()

        assertions = generator._generate_snapshot_assertions(sample_flow)

        assert isinstance(assertions, list)

    def test_assertion_set(self):
        """Test AssertionSet functionality."""
        assertion_set = AssertionSet(flow_id="test_flow")

        assertion = AssertionRule(
            assertion_type=AssertionType.STATUS_CODE,
            category=AssertionCategory.HEALTH,
            description="Status code check",
            expected_value=200
        )
        assertion_set.add_assertion(assertion)

        assert len(assertion_set.assertions) == 1
        assert len(assertion_set.get_health_assertions()) == 1

    def test_assertion_rule_get_code(self):
        """Test assertion code generation."""
        assertion = AssertionRule(
            assertion_type=AssertionType.STATUS_CODE,
            category=AssertionCategory.HEALTH,
            description="Status check",
            expected_value=200
        )

        code = assertion.get_assertion_code()
        assert "200" in code
        assert "assert" in code

    def test_assertion_rule_description(self):
        """Test assertion description."""
        assertion = AssertionRule(
            assertion_type=AssertionType.STATUS_CODE,
            category=AssertionCategory.HEALTH,
            description="Test",
            expected_value=200
        )

        desc = assertion.get_description()
        assert "200" in desc


class TestPatternAnalyzer:
    """Tests for PatternAnalyzer."""

    def test_init(self):
        """Test pattern analyzer initialization."""
        analyzer = PatternAnalyzer()
        assert analyzer is not None

    def test_analyze_patterns_empty(self):
        """Test pattern analysis with no flows."""
        analyzer = PatternAnalyzer()
        patterns = analyzer.analyze_patterns([])

        assert patterns == {}

    def test_analyze_patterns_single_flow(self):
        """Test pattern analysis with single flow."""
        analyzer = PatternAnalyzer()

        flow = self._create_flow_with_response({"code": 0, "success": True})
        patterns = analyzer.analyze_patterns([flow])

        # Should have patterns for the flow's URL
        assert len(patterns) > 0

    def test_analyze_patterns_multiple_flows(self):
        """Test pattern analysis with multiple flows."""
        analyzer = PatternAnalyzer()

        # Create multiple flows with same URL but consistent response
        url = "https://api.example.com/test"
        flows = [
            self._create_flow_with_response({"code": 0, "success": True}, url),
            self._create_flow_with_response({"code": 0, "success": True}, url),
        ]

        patterns = analyzer.analyze_patterns(flows)

        assert url in patterns

    def test_find_consistent_fields(self):
        """Test finding consistent fields across flows."""
        analyzer = PatternAnalyzer()

        flows = [
            self._create_flow_with_response({"code": 0}),
            self._create_flow_with_response({"code": 0}),
        ]

        patterns = analyzer.analyze_patterns(flows)
        url = flows[0].request.url

        if url in patterns:
            # Should find consistent code field
            field_data = patterns[url].get("$.code", {})
            if field_data:
                assert field_data.get("consistent") is True

    def _create_flow_with_response(self, response_body: dict, url: str = "https://api.example.com/test") -> TrafficFlow:
        """Helper to create flow with response."""
        request = TrafficRequest(url=url, method="GET")
        response = TrafficResponse(
            status_code=200,
            body=json.dumps(response_body),
            content_type="application/json"
        )
        return TrafficFlow(request=request, response=response)


class TestSnapshotManager:
    """Tests for SnapshotManager."""

    def test_init(self, temp_dir):
        """Test snapshot manager initialization."""
        manager = SnapshotManager(str(temp_dir))
        assert manager.snapshot_dir.exists()

    def test_save_snapshot(self, temp_dir, sample_flow):
        """Test saving a snapshot."""
        manager = SnapshotManager(str(temp_dir))

        snapshot = manager.save_snapshot(
            sample_flow,
            "$.code",
            "Response code snapshot"
        )

        assert snapshot.flow_id == sample_flow.flow_id
        assert snapshot.jsonpath == "$.code"

    def test_load_snapshot(self, temp_dir, sample_flow):
        """Test loading a snapshot."""
        manager = SnapshotManager(str(temp_dir))

        manager.save_snapshot(sample_flow, "$.code")
        loaded = manager.load_snapshot(sample_flow.flow_id, "$.code")

        assert loaded is not None
        assert loaded.flow_id == sample_flow.flow_id

    def test_load_nonexistent_snapshot(self, temp_dir):
        """Test loading non-existent snapshot."""
        manager = SnapshotManager(str(temp_dir))

        loaded = manager.load_snapshot("nonexistent", "$.code")
        assert loaded is None

    def test_compare_to_snapshot(self, temp_dir, sample_flow):
        """Test comparing flow to snapshot."""
        manager = SnapshotManager(str(temp_dir))

        snapshot = manager.save_snapshot(sample_flow, "$.code")
        matches = manager.compare_to_snapshot(sample_flow, snapshot)

        assert matches is True

    def test_save_and_load_persistence(self, temp_dir, sample_flow):
        """Test snapshot persistence."""
        manager1 = SnapshotManager(str(temp_dir))
        manager1.save_snapshot(sample_flow, "$.code")

        # Create new manager instance
        manager2 = SnapshotManager(str(temp_dir))
        loaded = manager2.load_snapshot(sample_flow.flow_id, "$.code")

        assert loaded is not None


class TestValidator:
    """Tests for Validator."""

    def test_init(self):
        """Test validator initialization."""
        validator = Validator()
        assert validator is not None

    def test_generate_all_assertions(self):
        """Test generating assertions for multiple flows."""
        validator = Validator()

        flows = [
            self._create_flow(),
            self._create_flow(),
        ]

        assertion_sets = validator.generate_all_assertions(flows)

        assert len(assertion_sets) == len(flows)

    def test_generate_assertions_with_swagger(self):
        """Test generating assertions with Swagger document."""
        validator = Validator()

        flow = self._create_flow()
        swagger_doc = None  # Would be actual SwaggerDoc in real test

        assertion_sets = validator.generate_all_assertions([flow], swagger_doc)

        assert flow.flow_id in assertion_sets

    def test_validate_assertions(self):
        """Test assertion validation."""
        validator = Validator()

        flow = self._create_flow()
        assertion_set = AssertionSet(flow_id=flow.flow_id)

        assertion = AssertionRule(
            assertion_type=AssertionType.STATUS_CODE,
            category=AssertionCategory.HEALTH,
            description="Status check",
            expected_value=200
        )
        assertion_set.add_assertion(assertion)

        results = validator.validate_assertions(flow, assertion_set)

        assert assertion.description in results

    def test_validate_single_assertion_status_code(self):
        """Test validating status code assertion."""
        validator = Validator()

        flow = self._create_flow(status_code=200)
        assertion = AssertionRule(
            assertion_type=AssertionType.STATUS_CODE,
            category=AssertionCategory.HEALTH,
            description="Status code check",
            expected_value=200
        )

        result = validator._validate_single_assertion(
            flow, {}, assertion
        )

        assert result is True

    def test_validate_single_assertion_response_time(self):
        """Test validating response time assertion."""
        validator = Validator()

        flow = self._create_flow(response_time=1.0)
        assertion = AssertionRule(
            assertion_type=AssertionType.RESPONSE_TIME,
            category=AssertionCategory.HEALTH,
            description="Response time check",
            threshold=5.0
        )

        result = validator._validate_single_assertion(
            flow, {}, assertion
        )

        assert result is True

    def test_validate_single_assertion_equals(self):
        """Test validating equals assertion."""
        validator = Validator()

        flow = self._create_flow_with_body({"code": 0})
        assertion = AssertionRule(
            assertion_type=AssertionType.EQUALS,
            category=AssertionCategory.SEMANTIC,
            description="Value equals check",
            actual_jsonpath="$.code",
            expected_value=0
        )

        response_data = flow.response.get_body_json() or {}
        result = validator._validate_single_assertion(
            flow, response_data, assertion
        )

        assert result is True

    def _create_flow(self, status_code: int = 200, response_time: float = 0.5) -> TrafficFlow:
        """Helper to create test flow."""
        request = TrafficRequest(url="https://api.example.com/test", method="GET")
        response = TrafficResponse(
            status_code=status_code,
            time=response_time,
            body='{"code": 0, "success": true}',
            content_type="application/json"
        )
        return TrafficFlow(request=request, response=response)

    def _create_flow_with_body(self, body: dict) -> TrafficFlow:
        """Helper to create flow with specific body."""
        request = TrafficRequest(url="https://api.example.com/test", method="GET")
        response = TrafficResponse(
            status_code=200,
            body=json.dumps(body),
            content_type="application/json"
        )
        return TrafficFlow(request=request, response=response)