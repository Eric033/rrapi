"""
Integration tests for log parsing functionality.
"""
import pytest
import json
from pathlib import Path

from flowgenius.collectors.log_collector import LogCollector, create_nginx_parser
from flowgenius.parsers.log_parser import LogParser, JSONLogParser
from flowgenius.parsers.har_parser import HARParser


class TestLogParseIntegration:
    """Integration tests for log parsing."""

    def test_nginx_log_file_full_workflow(self, temp_dir):
        """Test complete Nginx log file parsing workflow."""
        # Create sample Nginx access log file
        log_file = temp_dir / "access.log"
        log_content = """
192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/users HTTP/1.1" 200 1234 "-" "Mozilla/5.0"
192.168.1.1 - - [25/Feb/2026:10:00:01 +0000] "POST /api/login HTTP/1.1" 200 567 "-" "Mozilla/5.0"
192.168.1.2 - - [25/Feb/2026:10:00:02 +0000] "GET /api/products HTTP/1.1" 200 890 "-" "Mozilla/5.0"
192.168.1.1 - - [25/Feb/2026:10:00:03 +0000] "GET /style.css HTTP/1.1" 200 456 "-" "Mozilla/5.0"
192.168.1.2 - - [25/Feb/2026:10:00:04 +0000] "GET /app.js HTTP/1.1" 200 789 "-" "Mozilla/5.0"
192.168.1.3 - - [25/Feb/2026:10:00:05 +0000] "GET /api/orders HTTP/1.1" 404 123 "-" "Mozilla/5.0"
"""
        log_file.write_text(log_content.strip())

        # Parse with log collector
        collector = LogCollector(str(temp_dir), filter_static=True)
        count = collector.load_log_file(log_file)

        # Should have captured 4 flows (2 static resources filtered)
        assert count == 4
        assert collector.get_flow_count() == 4

        # Get unique URLs
        unique_urls = collector.get_unique_urls()
        assert "/api/users" in unique_urls
        assert "/api/login" in unique_urls
        assert "/api/products" in unique_urls
        assert "/api/orders" in unique_urls

        # Static resources should not be in URLs
        assert "/style.css" not in unique_urls
        assert "/app.js" not in unique_urls

    def test_log_to_har_conversion(self, temp_dir):
        """Test converting log data to HAR format."""
        log_file = temp_dir / "test.log"
        log_file.write_text('192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/test HTTP/1.1" 200 100 "-" "-"')

        # Parse log
        collector = LogCollector(str(temp_dir))
        collector.load_log_file(log_file)

        # Save to HAR
        har_path = collector.save_har()

        # Verify HAR structure
        with open(har_path, 'r') as f:
            har_data = json.load(f)

        assert "log" in har_data
        assert "entries" in har_data["log"]
        assert len(har_data["log"]["entries"]) == 1

        entry = har_data["log"]["entries"][0]
        assert entry["request"]["url"] == "/api/test"
        assert entry["request"]["method"] == "GET"
        assert entry["response"]["status"] == 200

    def test_log_directory_batch_processing(self, temp_dir):
        """Test processing multiple log files in a directory."""
        # Create multiple log files
        log_dir = temp_dir / "logs"
        log_dir.mkdir()

        for i in range(3):
            log_file = log_dir / f"access_{i}.log"
            log_file.write_text(f'192.168.1.1 - - [25/Feb/2026:10:00:0{i} +0000] "GET /api/test{i} HTTP/1.1" 200 100 "-" "-"')

        # Process directory
        collector = LogCollector(str(temp_dir))
        results = collector.load_log_directory(log_dir)

        # Verify all files were processed
        assert len(results) == 3

        # Verify total flows
        total_flows = sum(results.values())
        assert total_flows == 3

    def test_nginx_combined_format(self, temp_dir):
        """Test parsing Nginx combined log format."""
        log_file = temp_dir / "combined.log"
        log_content = '192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/test HTTP/1.1" 200 1234 "https://example.com" "Mozilla/5.0"'
        log_file.write_text(log_content)

        collector = create_nginx_parser("combined")
        count = collector.load_log_file(log_file)

        assert count == 1

        # Verify additional fields from combined format
        flows = collector.get_flows()
        assert len(flows) == 1

    def test_apache_common_format(self, temp_dir):
        """Test parsing Apache common log format."""
        log_file = temp_dir / "apache.log"
        log_content = '127.0.0.1 - frank [25/Feb/2026:10:00:00 +0000] "GET /api/test HTTP/1.0" 200 2326'
        log_file.write_text(log_content)

        from flowgenius.collectors.log_collector import create_apache_parser
        collector = create_apache_parser("common")
        count = collector.load_log_file(log_file)

        assert count == 1

    def test_json_log_format(self, temp_dir):
        """Test parsing JSON-formatted logs."""
        log_file = temp_dir / "json.log"
        log_content = '''{"method": "GET", "url": "/api/users", "status": 200, "timestamp": "2026-02-25T10:00:00Z"}
{"method": "POST", "url": "/api/login", "status": 200, "timestamp": "2026-02-25T10:00:01Z"}
{"method": "GET", "url": "/api/products", "status": 200, "timestamp": "2026-02-25T10:00:02Z"}'''
        log_file.write_text(log_content)

        parser = JSONLogParser()
        entries = parser.parse_file(log_file)

        assert len(entries) == 3

        # Verify parsed data
        assert entries[0]["method"] == "GET"
        assert entries[0]["url"] == "/api/users"
        assert entries[0]["status"] == 200

    def test_custom_log_pattern(self, temp_dir):
        """Test parsing with custom log pattern."""
        # Create a custom log format
        log_file = temp_dir / "custom.log"
        log_content = '''[2026-02-25 10:00:00] GET /api/test -> 200
[2026-02-25 10:00:01] POST /api/login -> 201'''

        log_file.write_text(log_content)

        # Custom pattern: [timestamp] method url -> status
        custom_pattern = r'\[(?P<timestamp>[^\]]+)\] (?P<request_method>\w+) (?P<request_uri>\S+) -> (?P<status>\d+)'

        parser = LogParser(custom_pattern)
        entries = parser.parse_file(log_file)

        assert len(entries) == 2
        assert entries[0]["request_method"] == "GET"
        assert entries[0]["status"] == 200

    def test_large_log_file(self, temp_dir):
        """Test parsing a large log file efficiently."""
        log_file = temp_dir / "large.log"

        # Generate 1000 log lines
        lines = []
        for i in range(1000):
            lines.append(f'192.168.1.{i % 256} - - [25/Feb/2026:10:00:{i:02d} +0000] "GET /api/test HTTP/1.1" 200 100 "-" "-"')

        log_file.write_text('\n'.join(lines))

        # Parse with max_lines limit
        parser = LogParser()
        entries = parser.parse_file(log_file, max_lines=100)

        assert len(entries) == 100

    def test_mixed_success_error_responses(self, temp_dir):
        """Test parsing logs with mixed success and error responses."""
        log_file = temp_dir / "mixed.log"
        log_content = '''
192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/test HTTP/1.1" 200 100 "-" "-"
192.168.1.1 - - [25/Feb/2026:10:00:01 +0000] "GET /api/notfound HTTP/1.1" 404 50 "-" "-"
192.168.1.1 - - [25/Feb/2026:10:00:02 +0000] "POST /api/error HTTP/1.1" 500 75 "-" "-"
192.168.1.1 - - [25/Feb/2026:10:00:03 +0000] "GET /api/unauthorized HTTP/1.1" 401 60 "-" "-"
'''
        log_file.write_text(log_content.strip())

        collector = LogCollector(str(temp_dir))
        count = collector.load_log_file(log_file)

        # All requests should be captured
        assert count == 4

        # Verify status codes
        flows = collector.get_flows()
        status_codes = [f.response.status_code for f in flows]
        assert 200 in status_codes
        assert 404 in status_codes
        assert 500 in status_codes
        assert 401 in status_codes

    def test_query_params_in_log(self, temp_dir):
        """Test extracting query parameters from log URLs."""
        log_file = temp_dir / "params.log"
        log_content = '192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/users?page=1&limit=10&sort=name HTTP/1.1" 200 100 "-" "-"'
        log_file.write_text(log_content)

        parser = LogParser()
        entries = parser.parse_file(log_file)

        assert len(entries) == 1

        # Verify query params were extracted
        assert "query_params" in entries[0]
        assert entries[0]["query_params"]["page"] == "1"
        assert entries[0]["query_params"]["limit"] == "10"
        assert entries[0]["query_params"]["sort"] == "name"

    def test_log_parser_statistics(self, temp_dir):
        """Test getting statistics from parsed logs."""
        log_file = temp_dir / "stats.log"
        log_content = '''
192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/test1 HTTP/1.1" 200 100 "-" "-"
192.168.1.1 - - [25/Feb/2026:10:00:01 +0000] "POST /api/test2 HTTP/1.1" 201 50 "-" "-"
192.168.1.1 - - [25/Feb/2026:10:00:02 +0000] "GET /api/test1 HTTP/1.1" 200 100 "-" "-"
192.168.1.1 - - [25/Feb/2026:10:00:03 +0000] "DELETE /api/test3 HTTP/1.1" 204 20 "-" "-"
'''
        log_file.write_text(log_content.strip())

        collector = LogCollector(str(temp_dir))
        collector.load_log_file(log_file)

        flows = collector.get_flows()

        # Count methods
        methods = {}
        for flow in flows:
            methods[flow.request.method] = methods.get(flow.request.method, 0) + 1

        assert methods.get("GET") == 2
        assert methods.get("POST") == 1
        assert methods.get("DELETE") == 1

        # Count status codes
        status_codes = {}
        for flow in flows:
            status_codes[flow.response.status_code] = status_codes.get(flow.response.status_code, 0) + 1

        assert status_codes.get(200) == 2
        assert status_codes.get(201) == 1
        assert status_codes.get(204) == 1