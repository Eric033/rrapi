"""
Core parsing orchestration module.
"""
from typing import Any, Dict, List, Optional, Union

from flowgenius.models.api import APIEndpoint, SwaggerDoc
from flowgenius.models.traffic import TrafficFlow
from flowgenius.parsers.har_parser import HARParser
from flowgenius.parsers.swagger_parser import SwaggerParser
from flowgenius.utils.logger import get_logger


class ParserOrchestrator:
    """Orchestrates parsing of various data formats."""

    def __init__(self):
        """Initialize parser orchestrator."""
        self.har_parser = HARParser()
        self.swagger_parser = SwaggerParser()
        self.logger = get_logger("flowgenius.parser")

    def parse_traffic(
        self,
        source: Union[str, "Path", Dict[str, Any]],
        source_type: Optional[str] = None
    ) -> List[TrafficFlow]:
        """
        Parse traffic data from various sources.

        Args:
            source: Traffic data source (HAR file, HAR dict, etc.)
            source_type: Source type hint ("har", "auto")

        Returns:
            List of TrafficFlow objects
        """
        if source_type is None:
            source_type = self._detect_source_type(source)

        if source_type == "har":
            return self.har_parser.parse(source)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

    def _detect_source_type(self, source: Any) -> str:
        """
        Detect the type of data source.

        Args:
            source: Data source

        Returns:
            Detected source type string
        """
        if isinstance(source, dict):
            # Check for HAR structure
            if "log" in source and "entries" in source.get("log", {}):
                return "har"
            return "unknown"

        if isinstance(source, str):
            # Check file extension
            if source.endswith(".har"):
                return "har"
            if source.endswith((".yaml", ".yml", ".json")):
                return "swagger"

        return "auto"

    def parse_swagger(
        self,
        source: Union[str, "Path", Dict[str, Any]]
    ) -> SwaggerDoc:
        """
        Parse Swagger/OpenAPI specification.

        Args:
            source: Swagger source (file path, URL, or dict)

        Returns:
            SwaggerDoc object
        """
        return self.swagger_parser.parse(source)

    def match_flows_to_endpoints(
        self,
        flows: List[TrafficFlow],
        swagger_doc: SwaggerDoc
    ) -> Dict[str, Optional[APIEndpoint]]:
        """
        Match traffic flows to Swagger endpoints.

        Args:
            flows: List of TrafficFlow objects
            swagger_doc: SwaggerDoc containing endpoint definitions

        Returns:
            Dictionary mapping flow IDs to matched APIEndpoint objects
        """
        matched = {}

        for flow in flows:
            endpoint = swagger_doc.find_endpoint_by_url(flow.request.url)
            matched[flow.flow_id] = endpoint

        self.logger.info(f"Matched {sum(1 for v in matched.values() if v is not None)}/{len(flows)} flows to endpoints")
        return matched

    def get_unmatched_flows(
        self,
        flows: List[TrafficFlow],
        matched: Dict[str, Optional[APIEndpoint]]
    ) -> List[TrafficFlow]:
        """
        Get flows that weren't matched to any Swagger endpoint.

        Args:
            flows: List of TrafficFlow objects
            matched: Dictionary mapping flow IDs to endpoints

        Returns:
            List of unmatched flows
        """
        return [flow for flow in flows if matched.get(flow.flow_id) is None]

    def enrich_flows_with_swagger(
        self,
        flows: List[TrafficFlow],
        swagger_doc: SwaggerDoc
    ) -> List[TrafficFlow]:
        """
        Enrich flows with information from Swagger.

        Args:
            flows: List of TrafficFlow objects
            swagger_doc: SwaggerDoc containing endpoint definitions

        Returns:
            List of enriched flows
        """
        for flow in flows:
            endpoint = swagger_doc.find_endpoint_by_url(flow.request.url)
            if endpoint:
                # Add endpoint info to flow (using a dict to avoid modifying dataclass)
                if not hasattr(flow, "_swagger_endpoint"):
                    flow._swagger_endpoint = endpoint
                else:
                    flow._swagger_endpoint = endpoint

        self.logger.info(f"Enriched flows with Swagger information")
        return flows

    def get_endpoint_for_flow(
        self,
        flow: TrafficFlow,
        swagger_doc: SwaggerDoc
    ) -> Optional[APIEndpoint]:
        """
        Get the Swagger endpoint for a specific flow.

        Args:
            flow: TrafficFlow object
            swagger_doc: SwaggerDoc

        Returns:
            APIEndpoint object or None
        """
        return swagger_doc.find_endpoint_by_url(flow.request.url)

    def get_all_endpoints(
        self,
        swagger_source: Union[str, "Path", Dict[str, Any]]
    ) -> List[APIEndpoint]:
        """
        Get all API endpoints from a Swagger source.

        Args:
            swagger_source: Swagger source

        Returns:
            List of APIEndpoint objects
        """
        swagger_doc = self.parse_swagger(swagger_source)
        return swagger_doc.get_all_endpoints()

    def get_endpoint_statistics(
        self,
        flows: List[TrafficFlow],
        swagger_doc: SwaggerDoc
    ) -> Dict[str, Any]:
        """
        Get statistics about flow-endpoint matching.

        Args:
            flows: List of TrafficFlow objects
            swagger_doc: SwaggerDoc

        Returns:
            Statistics dictionary
        """
        matched = self.match_flows_to_endpoints(flows, swagger_doc)

        matched_count = sum(1 for v in matched.values() if v is not None)
        unmatched_count = len(flows) - matched_count

        # Count by method
        method_counts = {}
        for flow in flows:
            method = flow.request.method
            method_counts[method] = method_counts.get(method, 0) + 1

        # Count by endpoint
        endpoint_counts = {}
        for endpoint in matched.values():
            if endpoint:
                key = f"{endpoint.method} {endpoint.path}"
                endpoint_counts[key] = endpoint_counts.get(key, 0) + 1

        return {
            "total_flows": len(flows),
            "matched_flows": matched_count,
            "unmatched_flows": unmatched_count,
            "match_rate": matched_count / len(flows) if flows else 0,
            "method_counts": method_counts,
            "endpoint_counts": endpoint_counts
        }