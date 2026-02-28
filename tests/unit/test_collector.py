"""
Unit tests for traffic collectors.
"""
import pytest
import json
from pathlib import Path
from datetime import datetime

from flowgenius.collectors.proxy_collector import ProxyCollector
from flowgenius.collectors.log_collector import LogCollector, create_nginx_parser
from flowgenius.models.traffic import TrafficRequest, TrafficResponse, TrafficFlow


class TestProxyCollector:
    """Tests for ProxyCollector."""

    def test_init(self, temp_dir):
        """Test proxy collector initialization."""
        collector = ProxyCollector(str(temp_dir), filter_static=True)
        assert collector.output_dir == Path(temp_dir)
        assert collector.filter_static is True
        assert collector.get_flow_count() == 0

    def test_capture_flow_success(self, temp_dir, sample_request_data, sample_response_data):
        """Test successful flow capture."""
        collector = ProxyCollector(str(temp_dir))
        flow = collector.capture_flow(sample_request_data, sample_response_data)

        assert flow is not None
        assert flow.request.url == sample_request_data["url"]
        assert flow.request.method == sample_request_data["method"]
        assert flow.response.status_code == sample_response_data["status_code"]
        assert collector.get_flow_count() == 1

    def test_capture_flow_filtered_static(self, temp_dir):
        """Test that static resources are filtered."""
        collector = ProxyCollector(str(temp_dir), filter_static=True)

        static_request = {
            "url": "https://example.com/style.css",
            "method": "GET",
            "headers": {},
            "query": {},
            "content": None,
            "timestamp": 0
        }
        static_response = {
            "status_code": 200,
            "headers": {"Content-Type": "text/css"},
            "content": "body {}",
            "time": 0.1
        }

        flow = collector.capture_flow(static_request, static_response)
        assert flow is None  # Should be filtered
        assert collector.get_flow_count() == 0

    def test_should_filter_by_extension(self, temp_dir):
        """Test filtering by file extension."""
        collector = ProxyCollector(str(temp_dir), filter_static=True)

        request = TrafficRequest(url="https://example.com/app.js", method="GET")
        response = TrafficResponse(status_code=200)

        assert collector.should_filter(request, response) is True

    def test_should_filter_by_content_type(self, temp_dir):
        """Test filtering by content type."""
        collector = ProxyCollector(str(temp_dir), filter_static=True)

        request = TrafficRequest(url="https://example.com/data", method="GET")
        response = TrafficResponse(status_code=200, content_type="image/png")

        assert collector.should_filter(request, response) is True

    def test_save_har(self, temp_dir):
        """Test saving captured flows to HAR file."""
        collector = ProxyCollector(str(temp_dir))
        collector.capture_flow(
            {"url": "https://api.example.com/test", "method": "GET", "headers": {}, "query": {}, "content": None, "timestamp": 0},
            {"status_code": 200, "headers": {}, "content": "{}", "time": 0.5}
        )

        har_path = collector.save_har("test.har")
        assert Path(har_path).exists()

        with open(har_path, 'r') as f:
            har_data = json.load(f)
            assert "log" in har_data
            assert len(har_data["log"]["entries"]) == 1

    def test_get_flows_by_method(self, temp_dir):
        """Test filtering flows by method."""
        collector = ProxyCollector(str(temp_dir))

        collector.capture_flow(
            {"url": "https://api.example.com/test", "method": "GET", "headers": {}, "query": {}, "content": None, "timestamp": 0},
            {"status_code": 200, "headers": {}, "content": "{}", "time": 0.5}
        )
        collector.capture_flow(
            {"url": "https://api.example.com/test", "method": "POST", "headers": {}, "query": {}, "content": "{}", "timestamp": 0},
            {"status_code": 201, "headers": {}, "content": "{}", "time": 0.5}
        )

        get_flows = collector.get_flows_by_method("GET")
        post_flows = collector.get_flows_by_method("POST")

        assert len(get_flows) == 1
        assert len(post_flows) == 1
        assert get_flows[0].request.method == "GET"
        assert post_flows[0].request.method == "POST"


class TestLogCollector:
    """Tests for LogCollector."""

    def test_init(self, temp_dir):
        """Test log collector initialization."""
        from flowgenius.collectors.log_collector import LogCollector
        collector = LogCollector(output_dir=str(temp_dir))
        assert collector.output_dir == Path(temp_dir)
        assert collector.filter_static is True

    def test_parse_log_line_nginx(self, temp_dir, sample_log_lines):
        """Test parsing Nginx log line."""
        from flowgenius.collectors.log_collector import LogCollector
        collector = LogCollector(output_dir=str(temp_dir))
        parsed = collector.parse_log_line(sample_log_lines[0])

        assert parsed is not None
        assert parsed["remote_addr"] == "192.168.1.1"
        assert parsed["request_method"] == "GET"
        assert parsed["request_uri"] == "/api/users"
        assert parsed["status"] == "200"

    def test_extract_traffic_from_log(self, temp_dir, sample_log_lines):
        """Test extracting traffic from log line."""
        from flowgenius.collectors.log_collector import LogCollector
        collector = LogCollector(output_dir=str(temp_dir))
        flow = collector.extract_traffic_from_log(sample_log_lines[0])

        assert flow is not None
        assert flow.request.method == "GET"
        assert flow.response.status_code == 200
        assert flow.request.url == "/api/users"

    def test_load_log_file(self, temp_dir):
        """Test loading traffic from log file."""
        from flowgenius.collectors.log_collector import LogCollector
        collector = LogCollector(output_dir=str(temp_dir))

        log_file = temp_dir / "access.log"
        log_file.write_text('192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/test HTTP/1.1" 200 100\n')

        count = collector.load_log_file(log_file)
        assert count == 1
        assert collector.get_flow_count() == 1

    def test_load_log_directory(self, temp_dir):
        """Test loading traffic from log directory."""
        from flowgenius.collectors.log_collector import LogCollector
        collector = LogCollector(output_dir=str(temp_dir))

        log_file = temp_dir / "access.log"
        log_file.write_text('192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/test HTTP/1.1" 200 100\n')

        results = collector.load_log_directory(temp_dir)
        assert str(log_file) in results
        assert results[str(log_file)] == 1

    def test_filter_static_resources(self, temp_dir):
        """Test filtering static resources from logs."""
        from flowgenius.collectors.log_collector import LogCollector
        collector = LogCollector(output_dir=str(temp_dir), filter_static=True)

        log_line = '192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /style.css HTTP/1.1" 200 100\n'
        flow = collector.extract_traffic_from_log(log_line)

        assert flow is None  # Should be filtered

    def test_save_har(self, temp_dir):
        """Test saving extracted flows to HAR file."""
        from flowgenius.collectors.log_collector import LogCollector
        collector = LogCollector(output_dir=str(temp_dir))

        log_file = temp_dir / "access.log"
        log_file.write_text('192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/test HTTP/1.1" 200 100\n')

        collector.load_log_file(log_file)
        har_path = collector.save_har("log_test.har")

        assert Path(har_path).exists()

    def test_create_nginx_parser(self, temp_dir):
        """Test creating Nginx parser."""
        from flowgenius.collectors.log_collector import create_nginx_parser
        parser = create_nginx_parser("combined")
        assert parser is not None
        assert parser.filter_static is True

        parser_access = create_nginx_parser("access")
        assert parser_access is not None