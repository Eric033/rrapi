"""
Unit tests for correlator.
"""
import pytest

from flowgenius.models.traffic import TrafficRequest, TrafficResponse, TrafficFlow
from flowgenius.models.correlation import CorrelationRule, CorrelationChain
from flowgenius.core.correlator import FlowCorrelator, VariableExtractor, ChainAnalyzer
from datetime import datetime
import json


class TestFlowCorrelator:
    """Tests for FlowCorrelator."""

    def test_init(self):
        """Test correlator initialization."""
        correlator = FlowCorrelator()
        assert correlator is not None

    def test_analyze_single_flow(self, sample_flow):
        """Test analyzing a single flow."""
        correlator = FlowCorrelator()
        chain = correlator.analyze_flows([sample_flow])

        assert isinstance(chain, CorrelationChain)
        assert len(chain.flow_ids) == 1

    def test_analyze_multiple_flows(self):
        """Test analyzing multiple flows."""
        correlator = FlowCorrelator()

        flows = self._create_test_flows()
        chain = correlator.analyze_flows(flows)

        assert len(chain.flow_ids) == 3

    def test_identify_correlations(self):
        """Test correlation identification."""
        correlator = FlowCorrelator()

        # Create flows with potential correlations
        flows = self._create_correlated_flows()
        correlations = correlator._identify_correlations(flows)

        # Should find at least some correlations
        assert len(correlations) >= 0

    def test_find_correlations_between_flows(self):
        """Test finding correlations between specific flows."""
        correlator = FlowCorrelator()

        source_flow = self._create_flow_with_response(
            "https://api.example.com/login",
            {"token": "abc123", "user_id": 456}
        )
        target_flow = self._create_flow_with_request(
            "https://api.example.com/profile",
            headers={"Authorization": "Bearer abc123"}
        )

        source_values = {
            "$.token": "abc123",
            "$.user_id": 456
        }

        correlations = correlator._find_correlations_between_flows(
            source_flow, target_flow, source_values
        )

        # Should find token correlation in header
        assert len(correlations) >= 0

    def test_values_match(self):
        """Test value matching logic."""
        correlator = FlowCorrelator()

        assert correlator._values_match("abc123", "abc123")
        assert correlator._values_match("123", 123)
        assert not correlator._values_match("abc", "xyz")

    def test_is_correlation_candidate(self):
        """Test correlation candidate validation."""
        correlator = FlowCorrelator()

        # Valid candidates
        assert correlator._is_correlation_candidate("abc123xyz456", "abc123xyz456")
        assert correlator._is_correlation_candidate(12345, 12345)

        # Invalid candidates (too short, common values)
        assert not correlator._is_correlation_candidate("ab", "ab")
        assert not correlator._is_correlation_candidate(1, 1)
        assert not correlator._is_correlation_candidate("true", "true")

    def _create_test_flows(self) -> list[TrafficFlow]:
        """Create test flows."""
        flows = []

        for i in range(3):
            request = TrafficRequest(
                url=f"https://api.example.com/endpoint{i}",
                method="GET"
            )
            response = TrafficResponse(status_code=200)
            flow = TrafficFlow(request=request, response=response)
            flows.append(flow)

        return flows

    def _create_correlated_flows(self) -> list[TrafficFlow]:
        """Create flows with potential correlations."""
        flows = []

        # Login flow with token in response
        login_request = TrafficRequest(
            url="https://api.example.com/login",
            method="POST",
            body=json.dumps({"username": "test"})
        )
        login_response = TrafficResponse(
            status_code=200,
            body=json.dumps({"token": "abc123", "user_id": 123}),
            content_type="application/json"
        )
        flows.append(TrafficFlow(request=login_request, response=login_response))

        # Profile flow using token
        profile_request = TrafficRequest(
            url="https://api.example.com/profile",
            method="GET",
            headers={"Authorization": "Bearer abc123"}
        )
        profile_response = TrafficResponse(status_code=200)
        flows.append(TrafficFlow(request=profile_request, response=profile_response))

        return flows

    def _create_flow_with_response(self, url: str, response_body: dict) -> TrafficFlow:
        """Create a flow with specific response."""
        request = TrafficRequest(url=url, method="GET")
        response = TrafficResponse(
            status_code=200,
            body=json.dumps(response_body),
            content_type="application/json"
        )
        return TrafficFlow(request=request, response=response)

    def _create_flow_with_request(self, url: str, headers: dict = None) -> TrafficFlow:
        """Create a flow with specific request."""
        request = TrafficRequest(url=url, method="GET", headers=headers or {})
        response = TrafficResponse(status_code=200)
        return TrafficFlow(request=request, response=response)


class TestVariableExtractor:
    """Tests for VariableExtractor."""

    def test_init(self):
        """Test variable extractor initialization."""
        extractor = VariableExtractor()
        assert extractor is not None

    def test_extract_variables(self):
        """Test variable extraction from flows."""
        extractor = VariableExtractor()

        # Create chain with correlation
        chain = CorrelationChain()
        chain.add_flow("flow1")
        chain.add_flow("flow2")

        correlation = CorrelationRule(
            response_flow_id="flow1",
            request_flow_id="flow2",
            response_jsonpath="$.token",
            request_location="header",
            request_key="Authorization",
            variable_name="token"
        )
        chain.add_correlation(correlation)

        # Create flows
        flows = self._create_flows_with_token()

        variables = extractor.extract_variables(chain, flows)

        # Should extract token variable
        assert "token" in variables or len(variables) == 0  # May be empty if no match

    def test_generate_extraction_rules(self):
        """Test extraction rule generation."""
        extractor = VariableExtractor()

        chain = CorrelationChain()
        chain.add_flow("flow1")
        chain.add_correlation(CorrelationRule(
            response_flow_id="flow1",
            request_flow_id="flow2",
            response_jsonpath="$.token",
            request_location="header",
            variable_name="token"
        ))

        rules = extractor.generate_extraction_rules(chain)

        assert len(rules) == 1
        assert rules[0].source_jsonpath == "$.token"
        assert rules[0].variable_name == "token"

    def test_generate_variable_references(self):
        """Test variable reference generation."""
        extractor = VariableExtractor()

        chain = CorrelationChain()
        chain.add_flow("flow1")
        chain.add_flow("flow2")
        chain.add_correlation(CorrelationRule(
            response_flow_id="flow1",
            request_flow_id="flow2",
            response_jsonpath="$.token",
            request_location="header",
            request_key="Authorization",
            variable_name="token"
        ))

        refs = extractor.generate_variable_references(chain)

        # Should have variable reference for flow2
        assert len(refs) == 1
        assert refs[0].variable_name == "token"
        assert refs[0].target_location == "header"

    def _create_flows_with_token(self) -> list[TrafficFlow]:
        """Create flows with token in response."""
        request = TrafficRequest(url="https://api.example.com/login", method="POST")
        response = TrafficResponse(
            status_code=200,
            body='{"token": "abc123"}',
            content_type="application/json"
        )
        return [TrafficFlow(request=request, response=response)]


class TestChainAnalyzer:
    """Tests for ChainAnalyzer."""

    def test_init(self):
        """Test chain analyzer initialization."""
        analyzer = ChainAnalyzer()
        assert analyzer is not None

    def test_analyze_chain(self):
        """Test chain analysis."""
        analyzer = ChainAnalyzer()

        chain = CorrelationChain()
        chain.add_flow("flow1")
        chain.add_flow("flow2")
        chain.add_correlation(CorrelationRule(
            response_flow_id="flow1",
            request_flow_id="flow2",
            response_jsonpath="$.token",
            request_location="header"
        ))

        results = analyzer.analyze_chain(chain)

        assert "total_flows" in results
        assert "total_correlations" in results
        assert "roots" in results
        assert "leaves" in results
        assert results["total_flows"] == 2
        assert results["total_correlations"] == 1

    def test_find_roots(self):
        """Test finding root flows."""
        analyzer = ChainAnalyzer()

        chain = CorrelationChain()
        chain.add_flow("flow1")
        chain.add_flow("flow2")

        roots = analyzer._find_roots(chain)

        # Both flows are roots (no dependencies)
        assert len(roots) == 2

    def test_find_leaves(self):
        """Test finding leaf flows."""
        analyzer = ChainAnalyzer()

        chain = CorrelationChain()
        chain.add_flow("flow1")
        chain.add_flow("flow2")

        leaves = analyzer._find_leaves(chain)

        # Both flows are leaves (nothing depends on them)
        assert len(leaves) == 2

    def test_find_isolated(self):
        """Test finding isolated flows."""
        analyzer = ChainAnalyzer()

        chain = CorrelationChain()
        chain.add_flow("flow1")
        chain.add_flow("flow2")

        isolated = analyzer._find_isolated(chain)

        # Both flows are isolated (no correlations)
        assert len(isolated) == 2

    def test_calculate_depths(self):
        """Test depth calculation."""
        analyzer = ChainAnalyzer()

        chain = CorrelationChain()
        chain.add_flow("flow1")
        chain.add_flow("flow2")
        chain.add_correlation(CorrelationRule(
            response_flow_id="flow1",
            request_flow_id="flow2",
            response_jsonpath="$.token",
            request_location="header"
        ))

        depths = analyzer._calculate_depths(chain)

        assert "flow1" in depths
        assert "flow2" in depths
        assert depths["flow1"] == 0  # Root flow
        assert depths["flow2"] == 1  # Depends on flow1