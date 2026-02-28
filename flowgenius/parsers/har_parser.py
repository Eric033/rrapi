"""
HAR (HTTP Archive) format parser.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from flowgenius.models.traffic import TrafficFlow, TrafficRequest, TrafficResponse
from flowgenius.utils.logger import get_logger


class HARParser:
    """Parser for HAR (HTTP Archive) files."""

    def __init__(self):
        """Initialize HAR parser."""
        self.logger = get_logger("flowgenius.har_parser")

    def parse(self, har_source: Union[str, Path, Dict[str, Any]]) -> List[TrafficFlow]:
        """
        Parse HAR file or data into TrafficFlow objects.

        Args:
            har_source: Path to HAR file or HAR data dict

        Returns:
            List of TrafficFlow objects
        """
        if isinstance(har_source, (str, Path)):
            har_data = self._load_har_file(har_source)
        else:
            har_data = har_source

        entries = self._extract_entries(har_data)
        flows = []

        for entry in entries:
            flow = self._parse_entry(entry)
            if flow:
                flows.append(flow)

        self.logger.info(f"Parsed {len(flows)} flows from HAR")
        return flows

    def _load_har_file(self, har_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load HAR file and parse JSON.

        Args:
            har_path: Path to HAR file

        Returns:
            HAR data dictionary
        """
        har_path = Path(har_path)
        if not har_path.exists():
            raise FileNotFoundError(f"HAR file not found: {har_path}")

        with open(har_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid HAR file: {e}")

    def _extract_entries(self, har_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract entries from HAR data.

        Args:
            har_data: HAR data dictionary

        Returns:
            List of entry dictionaries
        """
        # Standard HAR format
        if "log" in har_data and "entries" in har_data["log"]:
            return har_data["log"]["entries"]

        # Alternative format (entries at root)
        if "entries" in har_data:
            return har_data["entries"]

        # Try to find entries anywhere in the structure
        entries = self._find_entries_recursive(har_data)
        if entries:
            return entries

        self.logger.warning("No entries found in HAR data")
        return []

    def _find_entries_recursive(self, data: Any) -> List[Dict[str, Any]]:
        """
        Recursively find entries in HAR data.

        Args:
            data: HAR data to search

        Returns:
            List of entry dictionaries
        """
        if isinstance(data, dict):
            if "request" in data and "response" in data:
                return [data]

            for value in data.values():
                result = self._find_entries_recursive(value)
                if result:
                    return result

        elif isinstance(data, list):
            for item in data:
                result = self._find_entries_recursive(item)
                if result:
                    return result

        return []

    def _parse_entry(self, entry: Dict[str, Any]) -> Optional[TrafficFlow]:
        """
        Parse a single HAR entry into TrafficFlow.

        Args:
            entry: HAR entry dictionary

        Returns:
            TrafficFlow object or None if parsing fails
        """
        try:
            request_data = entry.get("request", {})
            response_data = entry.get("response", {})

            # Parse request
            request = self._parse_request(request_data, entry.get("startedDateTime"))

            # Parse response
            response = self._parse_response(response_data, entry.get("timings"))

            # Create flow
            return TrafficFlow(request=request, response=response)

        except Exception as e:
            self.logger.error(f"Failed to parse entry: {e}", exc_info=True)
            return None

    def _parse_request(self, request_data: Dict[str, Any], started_time: Optional[str]) -> TrafficRequest:
        """
        Parse HAR request data into TrafficRequest.

        Args:
            request_data: HAR request data
            started_time: Request start time string

        Returns:
            TrafficRequest object
        """
        # Parse timestamp
        timestamp = None
        if started_time:
            try:
                # ISO format: 2026-02-25T10:00:00.000Z
                timestamp = datetime.fromisoformat(started_time.replace('Z', '+00:00'))
            except Exception:
                pass

        # Parse headers
        headers = {}
        for header in request_data.get("headers", []):
            headers[header.get("name", "")] = header.get("value", "")

        # Parse query parameters
        query_params = {}
        for param in request_data.get("queryString", []):
            query_params[param.get("name", "")] = param.get("value", "")

        # Parse request body
        body = None
        content_type = None
        post_data = request_data.get("postData")
        if post_data:
            body = post_data.get("text", "")
            content_type = post_data.get("mimeType") or headers.get("Content-Type")

        return TrafficRequest(
            url=request_data.get("url", ""),
            method=request_data.get("method", "GET"),
            headers=headers,
            body=body,
            query_params=query_params,
            timestamp=timestamp,
            content_type=content_type
        )

    def _parse_response(self, response_data: Dict[str, Any], timings: Optional[Dict[str, Any]]) -> TrafficResponse:
        """
        Parse HAR response data into TrafficResponse.

        Args:
            response_data: HAR response data
            timings: Response timings data

        Returns:
            TrafficResponse object
        """
        # Parse headers
        headers = {}
        for header in response_data.get("headers", []):
            headers[header.get("name", "")] = header.get("value", "")

        # Parse response body
        content = response_data.get("content", {})
        body = content.get("text", "")
        content_type = content.get("mimeType") or headers.get("Content-Type")

        # Parse response time
        time = None
        if timings:
            # Sum all timing values for total time
            time = sum(
                timings.get(k, 0) / 1000.0  # Convert ms to seconds
                for k in ["blocked", "dns", "connect", "send", "wait", "receive"]
                if k in timings
            )

        return TrafficResponse(
            status_code=response_data.get("status", 0),
            headers=headers,
            body=body,
            time=time,
            content_type=content_type
        )

    def parse_to_dict(self, har_source: Union[str, Path]) -> Dict[str, Any]:
        """
        Parse HAR file to dictionary format.

        Args:
            har_source: Path to HAR file

        Returns:
            Dictionary representation of HAR data
        """
        har_data = self._load_har_file(har_source)
        entries = self._extract_entries(har_data)

        return {
            "version": har_data.get("log", {}).get("version", "1.2"),
            "creator": har_data.get("log", {}).get("creator", {}),
            "entries": entries
        }

    def get_statistics(self, har_source: Union[str, Path]) -> Dict[str, Any]:
        """
        Get statistics from HAR file.

        Args:
            har_source: Path to HAR file

        Returns:
            Statistics dictionary
        """
        flows = self.parse(har_source)

        if not flows:
            return {"total_flows": 0}

        # Collect statistics
        methods = {}
        status_codes = {}
        unique_urls = set()

        for flow in flows:
            method = flow.request.method
            methods[method] = methods.get(method, 0) + 1

            status = flow.response.status_code
            status_codes[status] = status_codes.get(status, 0) + 1

            unique_urls.add(flow.request.url)

        # Calculate average response time
        response_times = [f.response.time for f in flows if f.response.time is not None]
        avg_response_time = sum(response_times) / len(response_times) if response_times else None

        return {
            "total_flows": len(flows),
            "unique_urls": len(unique_urls),
            "methods": methods,
            "status_codes": status_codes,
            "average_response_time": avg_response_time
        }

    def filter_by_method(self, flows: List[TrafficFlow], methods: List[str]) -> List[TrafficFlow]:
        """
        Filter flows by HTTP method.

        Args:
            flows: List of flows to filter
            methods: List of methods to include

        Returns:
            Filtered list of flows
        """
        methods_upper = [m.upper() for m in methods]
        return [f for f in flows if f.request.method.upper() in methods_upper]

    def filter_by_status_code(self, flows: List[TrafficFlow], status_codes: List[int]) -> List[TrafficFlow]:
        """
        Filter flows by response status code.

        Args:
            flows: List of flows to filter
            status_codes: List of status codes to include

        Returns:
            Filtered list of flows
        """
        return [f for f in flows if f.response.status_code in status_codes]

    def filter_by_url_pattern(self, flows: List[TrafficFlow], pattern: str) -> List[TrafficFlow]:
        """
        Filter flows by URL pattern.

        Args:
            flows: List of flows to filter
            pattern: URL pattern (substring match)

        Returns:
            Filtered list of flows
        """
        pattern_lower = pattern.lower()
        return [f for f in flows if pattern_lower in f.request.url.lower()]