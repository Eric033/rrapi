"""
Log-based traffic collector.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union
from urllib.parse import parse_qs, urlparse

from flowgenius.models.traffic import TrafficRequest, TrafficResponse, TrafficFlow
from flowgenius.utils.logger import get_logger
from flowgenius.utils.regex_utils import (
    NGINX_ACCESS_PATTERN,
    NGINX_COMBINED_PATTERN,
    APACHE_COMMON_PATTERN,
    extract_match,
    extract_named_groups,
    normalize_url
)


class LogCollector:
    """Traffic collector from log files."""

    def __init__(
        self,
        log_pattern: Optional[str] = None,
        output_dir: str = ".",
        filter_static: bool = True,
        custom_parser: Optional[Callable] = None
    ):
        """
        Initialize log collector.

        Args:
            log_pattern: Regex pattern for log parsing (default: NGINX_ACCESS_PATTERN)
            output_dir: Directory to save extracted traffic
            filter_static: Whether to filter static resources
            custom_parser: Custom parser function for non-standard log formats
        """
        self.log_pattern = log_pattern or NGINX_ACCESS_PATTERN
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.filter_static = filter_static
        self.custom_parser = custom_parser
        self.flows: List[TrafficFlow] = []
        self.logger = get_logger("flowgenius.log")

        # Static resource filters
        self.static_extensions: Set[str] = {
            ".css", ".js", ".png", ".jpg", ".jpeg", ".gif",
            ".ico", ".svg", ".woff", ".woff2", ".ttf", ".eot"
        }

    def parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single log line.

        Args:
            line: Log line to parse

        Returns:
            Parsed data dict or None if parsing fails
        """
        if self.custom_parser:
            return self.custom_parser(line)

        # Try standard pattern
        parsed = extract_named_groups(self.log_pattern, line)
        if not parsed or 'request_uri' not in parsed:
            return None

        return parsed

    def extract_traffic_from_log(self, log_line: str) -> Optional[TrafficFlow]:
        """
        Extract traffic information from a log line.

        Args:
            log_line: Log line to process

        Returns:
            TrafficFlow object or None if extraction fails
        """
        try:
            parsed = self.parse_log_line(log_line)
            if not parsed:
                return None

            # Extract request components
            request_uri = parsed.get('request_uri', '')
            request_method = parsed.get('request_method', 'GET')
            status_code = int(parsed.get('status', 0))

            # Parse URL and query parameters
            parsed_url = urlparse(request_uri)
            url = parsed_url.path
            query_params = {}
            if parsed_url.query:
                query_params = {k: v[0] if v else '' for k, v in parse_qs(parsed_url.query).items()}

            # Parse timestamp
            timestamp = None
            if 'time_local' in parsed:
                try:
                    # Nginx format: 25/Feb/2026:10:00:00 +0000
                    time_str = parsed['time_local'].split(' ')[0]
                    timestamp = datetime.strptime(time_str, "%d/%b/%Y:%H:%M:%S")
                except Exception:
                    pass

            # Create request
            request = TrafficRequest(
                url=url,
                method=request_method,
                query_params=query_params,
                timestamp=timestamp
            )

            # Check if should filter (log only has request info)
            if self.filter_static:
                for ext in self.static_extensions:
                    if url.lower().endswith(ext):
                        return None

            # Create response (log only has status code)
            response = TrafficResponse(
                status_code=status_code
            )

            # Create flow
            flow = TrafficFlow(request=request, response=response)
            self.flows.append(flow)

            self.logger.info(f"Extracted flow from log: {request_method} {url}")
            return flow

        except Exception as e:
            self.logger.error(f"Failed to extract traffic from log line: {e}", exc_info=True)
            return None

    def load_log_file(
        self,
        log_file: Union[str, Path],
        encoding: str = 'utf-8',
        max_lines: Optional[int] = None
    ) -> int:
        """
        Load traffic from a log file.

        Args:
            log_file: Path to log file
            encoding: File encoding
            max_lines: Maximum number of lines to parse (None for all)

        Returns:
            Number of flows extracted
        """
        log_path = Path(log_file)
        if not log_path.exists():
            raise FileNotFoundError(f"Log file not found: {log_path}")

        count = 0
        with open(log_path, 'r', encoding=encoding, errors='ignore') as f:
            for i, line in enumerate(f, 1):
                if max_lines and i > max_lines:
                    break

                line = line.strip()
                if not line:
                    continue

                if self.extract_traffic_from_log(line):
                    count += 1

        self.logger.info(f"Loaded {count} flows from {log_path}")
        return count

    def load_log_directory(
        self,
        log_dir: Union[str, Path],
        pattern: str = "*.log",
        encoding: str = 'utf-8'
    ) -> Dict[str, int]:
        """
        Load traffic from all log files in a directory.

        Args:
            log_dir: Directory containing log files
            pattern: Glob pattern for matching log files
            encoding: File encoding

        Returns:
            Dictionary mapping file paths to flow counts
        """
        log_path = Path(log_dir)
        if not log_path.exists():
            raise FileNotFoundError(f"Log directory not found: {log_path}")

        results = {}
        for log_file in log_path.glob(pattern):
            try:
                count = self.load_log_file(log_file, encoding)
                results[str(log_file)] = count
            except Exception as e:
                self.logger.error(f"Failed to load {log_file}: {e}")
                results[str(log_file)] = 0

        total = sum(results.values())
        self.logger.info(f"Loaded total of {total} flows from {len(results)} files")
        return results

    def save_har(self, filename: Optional[str] = None) -> str:
        """
        Save extracted flows to HAR format.

        Args:
            filename: Optional custom filename

        Returns:
            Path to saved HAR file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"log_traffic_{timestamp}.har"

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
                    "queryString": [
                        {"name": k, "value": v}
                        for k, v in flow.request.query_params.items()
                    ]
                },
                "response": {
                    "status": flow.response.status_code,
                    "statusText": self._get_status_text(flow.response.status_code)
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
        """Get all extracted flows."""
        return self.flows.copy()

    def clear_flows(self):
        """Clear all extracted flows."""
        self.flows.clear()

    def get_flow_count(self) -> int:
        """Get number of extracted flows."""
        return len(self.flows)

    def get_unique_urls(self) -> Set[str]:
        """Get set of unique URLs from extracted flows."""
        return {flow.request.url for flow in self.flows}


class ApplicationLogParser:
    """Parser for custom application logs containing HTTP request/response."""

    def __init__(
        self,
        request_pattern: str,
        response_pattern: str,
        correlation_key: str = "request_id"
    ):
        """
        Initialize application log parser.

        Args:
            request_pattern: Regex pattern to match request log lines
            response_pattern: Regex pattern to match response log lines
            correlation_key: Field name used to correlate request and response
        """
        self.request_pattern = request_pattern
        self.response_pattern = response_pattern
        self.correlation_key = correlation_key
        self.pending_requests: Dict[str, Dict[str, Any]] = {}
        self.logger = get_logger("flowgenius.app_log")

    def parse_application_log(self, log_file: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Parse application log file to extract complete request-response pairs.

        Args:
            log_file: Path to application log file

        Returns:
            List of complete request-response pairs
        """
        completed = []

        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # Try to match as request
                request_data = extract_named_groups(self.request_pattern, line)
                if request_data and self.correlation_key in request_data:
                    self.pending_requests[request_data[self.correlation_key]] = request_data
                    continue

                # Try to match as response
                response_data = extract_named_groups(self.response_pattern, line)
                if response_data and self.correlation_key in response_data:
                    corr_id = response_data[self.correlation_key]
                    if corr_id in self.pending_requests:
                        completed.append({
                            "request": self.pending_requests.pop(corr_id),
                            "response": response_data
                        })

        return completed


def create_nginx_parser(log_format: str = "combined") -> LogCollector:
    """
    Create a log collector pre-configured for Nginx logs.

    Args:
        log_format: Nginx log format ("combined" or "access")

    Returns:
        Configured LogCollector instance
    """
    pattern = NGINX_COMBINED_PATTERN if log_format == "combined" else NGINX_ACCESS_PATTERN
    return LogCollector(log_pattern=pattern)


def create_apache_parser(log_format: str = "common") -> LogCollector:
    """
    Create a log collector pre-configured for Apache logs.

    Args:
        log_format: Apache log format ("common" or "combined")

    Returns:
        Configured LogCollector instance
    """
    # Note: Apache combined format is similar to Nginx
    pattern = NGINX_COMBINED_PATTERN if log_format == "combined" else APACHE_COMMON_PATTERN
    return LogCollector(log_pattern=pattern)