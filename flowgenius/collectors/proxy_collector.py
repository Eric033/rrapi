"""
MitmProxy-based traffic collector.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from flowgenius.models.traffic import TrafficRequest, TrafficResponse, TrafficFlow
from flowgenius.utils.logger import get_logger


class ProxyCollector:
    """Traffic collector using MitmProxy."""

    def __init__(self, output_dir: str = ".", filter_static: bool = True):
        """
        Initialize proxy collector.

        Args:
            output_dir: Directory to save captured traffic
            filter_static: Whether to filter static resources
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.filter_static = filter_static
        self.flows: List[TrafficFlow] = []
        self.logger = get_logger("flowgenius.proxy")

        # Static resource filters
        self.static_extensions: Set[str] = {
            ".css", ".js", ".png", ".jpg", ".jpeg", ".gif",
            ".ico", ".svg", ".woff", ".woff2", ".ttf", ".eot"
        }
        self.static_content_types: Set[str] = {
            "text/css",
            "text/javascript",
            "application/javascript",
            "image/",
            "font/",
        }

    def should_filter(self, request: TrafficRequest, response: TrafficResponse) -> bool:
        """
        Check if this request/response should be filtered out.

        Args:
            request: Traffic request
            response: Traffic response

        Returns:
            True if should filter, False otherwise
        """
        if not self.filter_static:
            return False

        # Check by request URL extension
        for ext in self.static_extensions:
            if request.url.lower().endswith(ext):
                return True

        # Check by response content-type
        if response.content_type:
            ct_lower = response.content_type.lower()
            for ct in self.static_content_types:
                if ct_lower.startswith(ct):
                    return True

        return False

    def capture_flow(self, request_data: Dict[str, Any], response_data: Dict[str, Any]) -> Optional[TrafficFlow]:
        """
        Capture a traffic flow from MitmProxy data.

        Args:
            request_data: MitmProxy request data
            response_data: MitmProxy response data

        Returns:
            TrafficFlow object or None if filtered
        """
        try:
            # Parse request
            request = TrafficRequest(
                url=request_data.get("url", ""),
                method=request_data.get("method", "GET"),
                headers=dict(request_data.get("headers", {})),
                body=request_data.get("content"),
                query_params=dict(request_data.get("query", {})),
                timestamp=datetime.fromtimestamp(request_data.get("timestamp", 0)),
                content_type=request_data.get("headers", {}).get("Content-Type")
            )

            # Parse response
            response = TrafficResponse(
                status_code=response_data.get("status_code", 0),
                headers=dict(response_data.get("headers", {})),
                body=response_data.get("content"),
                time=response_data.get("time"),
                content_type=response_data.get("headers", {}).get("Content-Type")
            )

            # Check if should filter
            if self.should_filter(request, response):
                return None

            # Create flow
            flow = TrafficFlow(request=request, response=response)
            self.flows.append(flow)

            self.logger.info(f"Captured flow: {request.method} {request.url}")
            return flow

        except Exception as e:
            self.logger.error(f"Failed to capture flow: {e}", exc_info=True)
            return None

    def save_har(self, filename: Optional[str] = None) -> str:
        """
        Save captured flows to HAR format.

        Args:
            filename: Optional custom filename

        Returns:
            Path to saved HAR file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"traffic_{timestamp}.har"

        har_path = self.output_dir / filename

        # Build HAR structure
        har_data = {
            "log": {
                "version": "1.2",
                "creator": {
                    "name": "FlowGenius SmartAdapter",
                    "version": "1.0.0"
                },
                "entries": []
            }
        }

        for flow in self.flows:
            entry = {
                "startedDateTime": flow.request.timestamp.isoformat() if flow.request.timestamp else "",
                "request": {
                    "method": flow.request.method,
                    "url": flow.request.url,
                    "httpVersion": "HTTP/1.1",
                    "headers": [
                        {"name": k, "value": v}
                        for k, v in flow.request.headers.items()
                    ],
                    "queryString": [
                        {"name": k, "value": v}
                        for k, v in flow.request.query_params.items()
                    ],
                    "postData": {
                        "text": flow.request.body or "",
                        "mimeType": flow.request.content_type or "application/json"
                    } if flow.request.body else None
                },
                "response": {
                    "status": flow.response.status_code,
                    "statusText": self._get_status_text(flow.response.status_code),
                    "httpVersion": "HTTP/1.1",
                    "headers": [
                        {"name": k, "value": v}
                        for k, v in flow.response.headers.items()
                    ],
                    "content": {
                        "text": flow.response.body or "",
                        "mimeType": flow.response.content_type or "application/json",
                        "size": len(flow.response.body or "")
                    }
                },
                "timings": {
                    "receive": flow.response.time * 1000 if flow.response.time else 0
                }
            }
            har_data["log"]["entries"].append(entry)

        with open(har_path, 'w', encoding='utf-8') as f:
            json.dump(har_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Saved HAR file to {har_path}")
        return str(har_path)

    def _get_status_text(self, status_code: int) -> str:
        """Get HTTP status text for status code."""
        status_texts = {
            200: "OK",
            201: "Created",
            204: "No Content",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            500: "Internal Server Error",
            502: "Bad Gateway",
            503: "Service Unavailable"
        }
        return status_texts.get(status_code, "Unknown")

    def get_flows(self) -> List[TrafficFlow]:
        """Get all captured flows."""
        return self.flows.copy()

    def clear_flows(self):
        """Clear all captured flows."""
        self.flows.clear()

    def get_flow_count(self) -> int:
        """Get number of captured flows."""
        return len(self.flows)

    def get_unique_urls(self) -> Set[str]:
        """Get set of unique URLs from captured flows."""
        return {flow.request.url for flow in self.flows}

    def get_flows_by_method(self, method: str) -> List[TrafficFlow]:
        """Get flows filtered by HTTP method."""
        return [flow for flow in self.flows if flow.request.method.upper() == method.upper()]

    def get_flows_by_path(self, path: str) -> List[TrafficFlow]:
        """Get flows filtered by URL path."""
        normalized_path = path.rstrip('/')
        return [
            flow for flow in self.flows
            if flow.request.url.rstrip('/').endswith(normalized_path)
        ]


class FlowCaptureAddon:
    """MitmProxy addon for flow capture."""

    def __init__(self, output_dir: str = ".", filter_static: bool = True):
        """
        Initialize addon.

        Args:
            output_dir: Directory to save captured flows
            filter_static: Whether to filter static resources
        """
        self.collector = ProxyCollector(output_dir, filter_static)
        self.logger = get_logger("flowgenius.addon")

    def request(self, flow):
        """Called when a request is received."""
        # Store request data for later
        pass

    def response(self, flow):
        """Called when a response is received."""
        try:
            # MitmProxy flow object structure
            request_data = {
                "url": flow.request.pretty_url,
                "method": flow.request.method,
                "headers": dict(flow.request.headers),
                "content": flow.request.content.decode('utf-8', errors='ignore') if flow.request.content else None,
                "query": dict(flow.request.query),
                "timestamp": flow.timestamp_start
            }

            response_data = {
                "status_code": flow.response.status_code,
                "headers": dict(flow.response.headers),
                "content": flow.response.content.decode('utf-8', errors='ignore') if flow.response.content else None,
                "time": (flow.timestamp_end - flow.timestamp_start) if hasattr(flow, 'timestamp_end') else None
            }

            self.collector.capture_flow(request_data, response_data)

        except Exception as e:
            self.logger.error(f"Failed to process flow: {e}", exc_info=True)

    def save(self):
        """Save captured flows."""
        return self.collector.save_har()

    def get_flows(self) -> List[TrafficFlow]:
        """Get all captured flows."""
        return self.collector.get_flows()