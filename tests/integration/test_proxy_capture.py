"""
Integration tests for proxy capture functionality.
"""
import pytest
import json
import subprocess
import time
from pathlib import Path
from unittest.mock import Mock, patch

from flowgenius.collectors.proxy_collector import ProxyCollector
from flowgenius.parsers.har_parser import HARParser


class TestProxyCapture:
    """Integration tests for proxy-based traffic capture."""

    def test_proxy_collector_full_workflow(self, temp_dir):
        """Test complete proxy collector workflow."""
        collector = ProxyCollector(str(temp_dir), filter_static=True)

        # Simulate capturing multiple flows
        requests = [
            {
                "url": "https://api.example.com/users",
                "method": "GET",
                "headers": {"Content-Type": "application/json"},
                "query": {"page": "1"},
                "content": None,
                "timestamp": time.time()
            },
            {
                "url": "https://api.example.com/users/123",
                "method": "GET",
                "headers": {"Content-Type": "application/json"},
                "query": {},
                "content": None,
                "timestamp": time.time()
            },
            {
                "url": "https://api.example.com/users",
                "method": "POST",
                "headers": {"Content-Type": "application/json"},
                "query": {},
                "content": json.dumps({"name": "Test", "email": "test@example.com"}),
                "timestamp": time.time()
            }
        ]

        responses = [
            {
                "status_code": 200,
                "headers": {"Content-Type": "application/json"},
                "content": json.dumps({"users": []}),
                "time": 0.5
            },
            {
                "status_code": 200,
                "headers": {"Content-Type": "application/json"},
                "content": json.dumps({"id": 123, "name": "User"}),
                "time": 0.3
            },
            {
                "status_code": 201,
                "headers": {"Content-Type": "application/json"},
                "content": json.dumps({"id": 124, "name": "Test"}),
                "time": 0.4
            }
        ]

        # Capture flows
        for req, resp in zip(requests, responses):
            flow = collector.capture_flow(req, resp)
            assert flow is not None

        # Verify flow count
        assert collector.get_flow_count() == 3

        # Save to HAR
        har_path = collector.save_har()
        assert Path(har_path).exists()

        # Parse HAR and verify
        parser = HARParser()
        flows = parser.parse(har_path)
        assert len(flows) == 3

        # Verify methods
        methods = [f.request.method for f in flows]
        assert "GET" in methods
        assert "POST" in methods

    def test_static_resource_filtering(self, temp_dir):
        """Test that static resources are correctly filtered."""
        collector = ProxyCollector(str(temp_dir), filter_static=True)

        # Static resource requests
        static_requests = [
            {
                "url": "https://example.com/style.css",
                "method": "GET",
                "headers": {"Content-Type": "text/css"},
                "query": {},
                "content": None,
                "timestamp": time.time()
            },
            {
                "url": "https://example.com/app.js",
                "method": "GET",
                "headers": {"Content-Type": "application/javascript"},
                "query": {},
                "content": None,
                "timestamp": time.time()
            }
        ]

        responses = [
            {"status_code": 200, "headers": {}, "content": "body {}", "time": 0.1},
            {"status_code": 200, "headers": {}, "content": "console.log()", "time": 0.1}
        ]

        # Try to capture static resources
        for req, resp in zip(static_requests, responses):
            flow = collector.capture_flow(req, resp)
            assert flow is None  # Should be filtered

        assert collector.get_flow_count() == 0

    def test_api_requests_not_filtered(self, temp_dir):
        """Test that API requests are not filtered."""
        collector = ProxyCollector(str(temp_dir), filter_static=True)

        api_request = {
            "url": "https://api.example.com/data",
            "method": "GET",
            "headers": {"Content-Type": "application/json"},
            "query": {},
            "content": None,
            "timestamp": time.time()
        }

        api_response = {
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "content": json.dumps({"data": "value"}),
            "time": 0.5
        }

        flow = collector.capture_flow(api_request, api_response)
        assert flow is not None
        assert collector.get_flow_count() == 1

    def test_har_file_roundtrip(self, temp_dir):
        """Test HAR file save and load roundtrip."""
        collector = ProxyCollector(str(temp_dir))

        # Capture a flow
        request = {
            "url": "https://api.example.com/test",
            "method": "POST",
            "headers": {"Content-Type": "application/json", "Authorization": "Bearer token"},
            "query": {},
            "content": json.dumps({"key": "value"}),
            "timestamp": time.time()
        }

        response = {
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "content": json.dumps({"result": "success"}),
            "time": 1.0
        }

        collector.capture_flow(request, response)

        # Save HAR
        har_path = collector.save_har("roundtrip.har")

        # Load and verify
        parser = HARParser()
        flows = parser.parse(har_path)

        assert len(flows) == 1
        assert flows[0].request.url == "https://api.example.com/test"
        assert flows[0].request.method == "POST"
        assert "Authorization" in flows[0].request.headers
        assert flows[0].response.status_code == 200
        assert flows[0].response.time == 1.0

    def test_multiple_saves(self, temp_dir):
        """Test saving HAR file multiple times."""
        collector = ProxyCollector(str(temp_dir))

        # Capture first flow
        collector.capture_flow(
            {"url": "https://api.example.com/test1", "method": "GET", "headers": {}, "query": {}, "content": None, "timestamp": time.time()},
            {"status_code": 200, "headers": {}, "content": "{}", "time": 0.1}
        )

        har1 = collector.save_har("test1.har")

        # Capture second flow
        collector.capture_flow(
            {"url": "https://api.example.com/test2", "method": "GET", "headers": {}, "query": {}, "content": None, "timestamp": time.time()},
            {"status_code": 200, "headers": {}, "content": "{}", "time": 0.1}
        )

        har2 = collector.save_har("test2.har")

        # Both files should exist and have correct content
        parser = HARParser()
        flows1 = parser.parse(har1)
        flows2 = parser.parse(har2)

        assert len(flows1) == 1
        assert len(flows2) == 2  # Second HAR has both flows

    def test_statistics_calculation(self, temp_dir):
        """Test statistics calculation from captured flows."""
        collector = ProxyCollector(str(temp_dir))

        # Capture diverse flows
        methods = ["GET", "POST", "PUT", "DELETE"]
        for i, method in enumerate(methods):
            collector.capture_flow(
                {"url": f"https://api.example.com/resource{i}", "method": method, "headers": {}, "query": {}, "content": None, "timestamp": time.time()},
                {"status_code": 200 if method != "DELETE" else 204, "headers": {}, "content": "{}", "time": 0.5}
            )

        # Get flows
        flows = collector.get_flows()

        # Calculate statistics manually
        unique_urls = set(f.request.url for f in flows)
        method_counts = {}
        for flow in flows:
            method = flow.request.method
            method_counts[method] = method_counts.get(method, 0) + 1

        assert len(unique_urls) == 4
        assert len(method_counts) == 4
        assert method_counts["GET"] == 1
        assert method_counts["POST"] == 1

    def test_clear_flows(self, temp_dir):
        """Test clearing captured flows."""
        collector = ProxyCollector(str(temp_dir))

        # Capture some flows
        for i in range(3):
            collector.capture_flow(
                {"url": f"https://api.example.com/test{i}", "method": "GET", "headers": {}, "query": {}, "content": None, "timestamp": time.time()},
                {"status_code": 200, "headers": {}, "content": "{}", "time": 0.1}
            )

        assert collector.get_flow_count() == 3

        # Clear flows
        collector.clear_flows()
        assert collector.get_flow_count() == 0

    def test_get_unique_urls(self, temp_dir):
        """Test getting unique URLs from captured flows."""
        collector = ProxyCollector(str(temp_dir))

        # Capture flows with duplicate URLs
        for i in range(3):
            collector.capture_flow(
                {"url": "https://api.example.com/users", "method": "GET", "headers": {}, "query": {}, "content": None, "timestamp": time.time()},
                {"status_code": 200, "headers": {}, "content": "{}", "time": 0.1}
            )

        unique_urls = collector.get_unique_urls()
        assert len(unique_urls) == 1
        assert "https://api.example.com/users" in unique_urls