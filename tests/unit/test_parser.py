"""
Unit tests for parsers.
"""
import pytest
import json
import yaml
from pathlib import Path

from flowgenius.parsers.har_parser import HARParser
from flowgenius.parsers.swagger_parser import SwaggerParser
from flowgenius.parsers.log_parser import LogParser, JSONLogParser
from flowgenius.models.traffic import TrafficFlow
from flowgenius.models.api import APIEndpoint, SwaggerDoc


class TestHARParser:
    """Tests for HARParser."""

    def test_init(self):
        """Test HAR parser initialization."""
        parser = HARParser()
        assert parser is not None

    def test_parse_har_dict(self, sample_har_data):
        """Test parsing HAR data from dictionary."""
        parser = HARParser()
        flows = parser.parse(sample_har_data)

        assert len(flows) == 1
        assert flows[0].request.url == "https://api.example.com/login"
        assert flows[0].request.method == "POST"
        assert flows[0].response.status_code == 200

    def test_parse_har_file(self, temp_dir, sample_har_data):
        """Test parsing HAR data from file."""
        har_file = temp_dir / "test.har"
        with open(har_file, 'w') as f:
            json.dump(sample_har_data, f)

        parser = HARParser()
        flows = parser.parse(str(har_file))

        assert len(flows) == 1
        assert flows[0].request.method == "POST"

    def test_parse_invalid_har(self, temp_dir):
        """Test parsing invalid HAR file."""
        har_file = temp_dir / "invalid.har"
        har_file.write_text("invalid json")

        parser = HARParser()
        with pytest.raises(ValueError):
            parser.parse(str(har_file))

    def test_get_statistics(self, temp_dir, sample_har_data):
        """Test getting HAR statistics."""
        har_file = temp_dir / "test.har"
        with open(har_file, 'w') as f:
            json.dump(sample_har_data, f)

        parser = HARParser()
        stats = parser.get_statistics(str(har_file))

        assert stats["total_flows"] == 1
        assert stats["unique_urls"] == 1
        assert "methods" in stats

    def test_filter_by_method(self, sample_har_data):
        """Test filtering flows by method."""
        parser = HARParser()
        flows = parser.parse(sample_har_data)

        post_flows = parser.filter_by_method(flows, ["POST"])
        assert len(post_flows) == 1
        assert post_flows[0].request.method == "POST"

        get_flows = parser.filter_by_method(flows, ["GET"])
        assert len(get_flows) == 0


class TestSwaggerParser:
    """Tests for SwaggerParser."""

    def test_init(self):
        """Test Swagger parser initialization."""
        parser = SwaggerParser()
        assert parser is not None

    def test_parse_swagger_dict(self, sample_swagger_data):
        """Test parsing Swagger data from dictionary."""
        parser = SwaggerParser()
        swagger_doc = parser.parse(sample_swagger_data)

        assert isinstance(swagger_doc, SwaggerDoc)
        assert swagger_doc.openapi_version == "3.0.0"
        assert swagger_doc.info["title"] == "Sample API"

    def test_parse_swagger_json_file(self, temp_dir, sample_swagger_data):
        """Test parsing Swagger data from JSON file."""
        swagger_file = temp_dir / "swagger.json"
        with open(swagger_file, 'w') as f:
            json.dump(sample_swagger_data, f)

        parser = SwaggerParser()
        swagger_doc = parser.parse(str(swagger_file))

        assert swagger_doc.openapi_version == "3.0.0"

    def test_parse_swagger_yaml_file(self, temp_dir, sample_swagger_data):
        """Test parsing Swagger data from YAML file."""
        swagger_file = temp_dir / "swagger.yaml"
        with open(swagger_file, 'w') as f:
            yaml.dump(sample_swagger_data, f)

        parser = SwaggerParser()
        swagger_doc = parser.parse(str(swagger_file))

        assert swagger_doc.openapi_version == "3.0.0"

    def test_find_endpoint(self, sample_swagger_data):
        """Test finding specific endpoint."""
        parser = SwaggerParser()
        swagger_doc = parser.parse(sample_swagger_data)

        endpoint = swagger_doc.find_endpoint("/api/login", "POST")
        assert endpoint is not None
        assert endpoint.method == "POST"
        assert endpoint.path == "/api/login"

    def test_find_endpoint_by_url(self, sample_swagger_data):
        """Test finding endpoint by URL."""
        parser = SwaggerParser()
        swagger_doc = parser.parse(sample_swagger_data)

        endpoint = swagger_doc.find_endpoint_by_url("https://api.example.com/api/login")
        assert endpoint is not None

    def test_get_all_endpoints(self, sample_swagger_data):
        """Test getting all endpoints."""
        parser = SwaggerParser()
        swagger_doc = parser.parse(sample_swagger_data)
        endpoints = swagger_doc.get_all_endpoints()

        assert len(endpoints) == 2

    def test_endpoint_class_name(self, sample_swagger_data):
        """Test endpoint class name generation."""
        parser = SwaggerParser()
        swagger_doc = parser.parse(sample_swagger_data)
        endpoint = swagger_doc.find_endpoint("/api/login", "POST")

        class_name = endpoint.get_class_name()
        assert "Login" in class_name

    def test_endpoint_method_name(self, sample_swagger_data):
        """Test endpoint method name generation."""
        parser = SwaggerParser()
        swagger_doc = parser.parse(sample_swagger_data)
        endpoint = swagger_doc.find_endpoint("/api/login", "POST")

        method_name = endpoint.get_method_name()
        assert "login" in method_name.lower()


class TestLogParser:
    """Tests for LogParser."""

    def test_init(self):
        """Test log parser initialization."""
        parser = LogParser()
        assert parser is not None

    def test_parse_line(self, sample_log_lines):
        """Test parsing log line."""
        parser = LogParser()
        parsed = parser.parse_line(sample_log_lines[0])

        assert parsed is not None
        assert "request_uri" in parsed
        assert "status" in parsed

    def test_parse_invalid_line(self):
        """Test parsing invalid log line."""
        parser = LogParser()
        parsed = parser.parse_line("not a valid log line")
        assert parsed is None

    def test_parse_file(self, temp_dir):
        """Test parsing log file."""
        parser = LogParser()

        log_file = temp_dir / "test.log"
        log_file.write_text('192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/test HTTP/1.1" 200 100\n')

        entries = parser.parse_file(log_file)
        assert len(entries) == 1

    def test_parse_directory(self, temp_dir):
        """Test parsing log directory."""
        parser = LogParser()

        log_file = temp_dir / "test.log"
        log_file.write_text('192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/test HTTP/1.1" 200 100\n')

        results = parser.parse_directory(temp_dir)
        assert str(log_file) in results
        assert len(results[str(log_file)]) == 1


class TestJSONLogParser:
    """Tests for JSONLogParser."""

    def test_init(self):
        """Test JSON log parser initialization."""
        parser = JSONLogParser()
        assert parser is not None

    def test_parse_json_line(self):
        """Test parsing JSON log line."""
        parser = JSONLogParser()

        log_line = '{"method": "GET", "url": "/api/test", "status": 200}'
        parsed = parser.parse_line(log_line)

        assert parsed is not None
        assert parsed["method"] == "GET"
        assert parsed["status"] == 200

    def test_parse_invalid_json_line(self):
        """Test parsing invalid JSON log line."""
        parser = JSONLogParser()

        log_line = 'not json'
        parsed = parser.parse_line(log_line)
        assert parsed is None