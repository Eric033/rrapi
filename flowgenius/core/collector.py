"""
Core traffic collection orchestration.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from flowgenius.collectors.proxy_collector import ProxyCollector
from flowgenius.collectors.log_collector import LogCollector, create_nginx_parser
from flowgenius.models.traffic import TrafficFlow
from flowgenius.utils.logger import get_logger


class TrafficOrchestrator:
    """Orchestrates traffic collection from multiple sources."""

    def __init__(self, output_dir: str = "."):
        """
        Initialize traffic orchestrator.

        Args:
            output_dir: Directory to save collected traffic
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.proxy_collector = ProxyCollector(str(self.output_dir))
        self.log_collector = LogCollector(str(self.output_dir))
        self.logger = get_logger("flowgenius.orchestrator")

    def collect_from_proxy(
        self,
        port: int = 8080,
        web_ui: bool = True,
        ssl: bool = True
    ) -> str:
        """
        Start MitmProxy for traffic capture.

        Args:
            port: Proxy port to listen on
            web_ui: Whether to start web UI
            ssl: Whether to enable SSL interception

        Returns:
            HAR file path when capture is complete
        """
        self.logger.info(f"Starting MitmProxy on port {port}")

        # Note: Actual MitmProxy startup is handled by the start_proxy.py script
        # This method returns the collector instance for external use
        return str(self.output_dir)

    def collect_from_logs(
        self,
        log_source: Union[str, Path],
        log_format: str = "nginx_combined",
        max_lines: Optional[int] = None
    ) -> int:
        """
        Collect traffic from log files.

        Args:
            log_source: Path to log file or directory
            log_format: Log format ("nginx_combined", "nginx_access", "apache_common")
            max_lines: Maximum number of lines to parse

        Returns:
            Number of flows collected
        """
        log_path = Path(log_source)

        if log_format.startswith("nginx"):
            self.log_collector = create_nginx_parser("combined" if log_format == "nginx_combined" else "access")
        elif log_format.startswith("apache"):
            from flowgenius.collectors.log_collector import create_apache_parser
            self.log_collector = create_apache_parser("common")
        else:
            self.log_collector = LogCollector()

        if log_path.is_file():
            count = self.log_collector.load_log_file(log_path, max_lines=max_lines)
        elif log_path.is_dir():
            results = self.log_collector.load_log_directory(log_path)
            count = sum(results.values())
        else:
            raise FileNotFoundError(f"Log source not found: {log_source}")

        self.logger.info(f"Collected {count} flows from {log_source}")
        return count

    def merge_collections(self) -> List[TrafficFlow]:
        """
        Merge flows from proxy and log collectors.

        Returns:
            Combined list of flows
        """
        proxy_flows = self.proxy_collector.get_flows()
        log_flows = self.log_collector.get_flows()

        # Combine and deduplicate by URL and method
        seen = set()
        merged = []

        for flow in proxy_flows + log_flows:
            key = (flow.request.url, flow.request.method)
            if key not in seen:
                seen.add(key)
                merged.append(flow)

        self.logger.info(f"Merged {len(merged)} unique flows")
        return merged

    def save_merged_har(self, filename: Optional[str] = None) -> str:
        """
        Save merged flows to HAR file.

        Args:
            filename: Optional custom filename

        Returns:
            Path to saved HAR file
        """
        import json
        from datetime import datetime

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"merged_traffic_{timestamp}.har"

        har_path = self.output_dir / filename
        flows = self.merge_collections()

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

        for flow in flows:
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

        self.logger.info(f"Saved merged HAR file to {har_path}")
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

    def get_all_flows(self) -> List[TrafficFlow]:
        """Get all collected flows."""
        return self.merge_collections()

    def clear_all(self):
        """Clear all collected flows."""
        self.proxy_collector.clear_flows()
        self.log_collector.clear_flows()

    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        return {
            "proxy_flows": self.proxy_collector.get_flow_count(),
            "log_flows": self.log_collector.get_flow_count(),
            "merged_flows": len(self.merge_collections()),
            "unique_urls": len({f.request.url for f in self.merge_collections()})
        }