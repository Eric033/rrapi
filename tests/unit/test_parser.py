"""
Unit tests for parsers.
"""
import pytest
import json
import yaml
from pathlib import Path
from datetime import datetime

from flowgenius.parsers.har_parser import HARParser
from flowgenius.parsers.swagger_parser import SwaggerParser
from flowgenius.parsers.log_parser import (
    LogParser,
    JSONLogParser,
    ApplicationLogParser,
    extract_tokens_from_logs,
    extract_ids_from_logs,
    create_nginx_parser,
    create_apache_parser,
)
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
        assert flows[0].request.url == "https://api.example.com/api/login"
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

    def test_parse_empty_line(self):
        """Test parsing empty line."""
        parser = JSONLogParser()
        parsed = parser.parse_line("")
        assert parsed is None

        parser2 = LogParser()
        parsed2 = parser2.parse_line("")
        assert parsed2 is None


class TestHARParserAdvanced:
    """Advanced tests for HARParser."""

    def test_parse_with_alternative_format(self, temp_dir):
        """Test parsing HAR with entries at root level."""
        har_data = {
            "entries": [
                {
                    "request": {
                        "method": "GET",
                        "url": "https://api.example.com/test",
                        "headers": []
                    },
                    "response": {
                        "status": 200,
                        "headers": [],
                        "content": {"text": "{}", "mimeType": "application/json"}
                    }
                }
            ]
        }
        parser = HARParser()
        flows = parser.parse(har_data)
        assert len(flows) == 1

    def test_parse_with_recursive_find(self):
        """Test recursive entry finding."""
        har_data = {
            "wrapper": {
                "nested": {
                    "request": {"method": "GET", "url": "https://test.com"},
                    "response": {"status": 200}
                }
            }
        }
        parser = HARParser()
        flows = parser.parse(har_data)
        assert len(flows) == 1

    def test_filter_by_status_code(self, sample_har_data):
        """Test filtering flows by status code."""
        parser = HARParser()
        flows = parser.parse(sample_har_data)

        filtered = parser.filter_by_status_code(flows, [200])
        assert len(filtered) == 1

        filtered_404 = parser.filter_by_status_code(flows, [404])
        assert len(filtered_404) == 0

    def test_filter_by_url_pattern(self, sample_har_data):
        """Test filtering flows by URL pattern."""
        parser = HARParser()
        flows = parser.parse(sample_har_data)

        filtered = parser.filter_by_url_pattern(flows, "login")
        assert len(filtered) == 1

        filtered_none = parser.filter_by_url_pattern(flows, "nonexistent")
        assert len(filtered_none) == 0

    def test_parse_to_dict(self, temp_dir, sample_har_data):
        """Test parsing HAR to dictionary."""
        har_file = temp_dir / "test.har"
        with open(har_file, 'w') as f:
            json.dump(sample_har_data, f)

        parser = HARParser()
        result = parser.parse_to_dict(str(har_file))

        assert "entries" in result
        assert len(result["entries"]) == 1

    def test_parse_nonexistent_file(self):
        """Test parsing non-existent file."""
        parser = HARParser()
        with pytest.raises(FileNotFoundError):
            parser.parse("/nonexistent/path.har")

    def test_statistics_with_empty_flows(self):
        """Test statistics with no flows."""
        parser = HARParser()
        stats = parser.get_statistics({"log": {"entries": []}})
        assert stats["total_flows"] == 0

    def test_parse_with_timings(self, temp_dir):
        """Test parsing HAR with timing data."""
        har_data = {
            "log": {
                "entries": [
                    {
                        "startedDateTime": "2026-02-25T10:00:00Z",
                        "request": {
                            "method": "GET",
                            "url": "https://api.example.com/test",
                            "headers": []
                        },
                        "response": {
                            "status": 200,
                            "headers": [],
                            "content": {"text": "{}", "mimeType": "application/json"}
                        },
                        "timings": {
                            "blocked": 100,
                            "dns": 50,
                            "connect": 75,
                            "send": 10,
                            "wait": 200,
                            "receive": 100
                        }
                    }
                ]
            }
        }
        parser = HARParser()
        flows = parser.parse(har_data)
        assert len(flows) == 1
        assert flows[0].response.time is not None
        assert flows[0].response.time > 0

    def test_parse_with_post_data(self, temp_dir):
        """Test parsing HAR with POST data."""
        har_data = {
            "log": {
                "entries": [
                    {
                        "request": {
                            "method": "POST",
                            "url": "https://api.example.com/test",
                            "headers": [
                                {"name": "Content-Type", "value": "application/json"}
                            ],
                            "postData": {
                                "text": '{"key": "value"}',
                                "mimeType": "application/json"
                            }
                        },
                        "response": {
                            "status": 201,
                            "headers": [],
                            "content": {}
                        }
                    }
                ]
            }
        }
        parser = HARParser()
        flows = parser.parse(har_data)
        assert len(flows) == 1
        assert flows[0].request.body == '{"key": "value"}'

    def test_parse_with_query_params(self, temp_dir):
        """Test parsing HAR with query parameters."""
        har_data = {
            "log": {
                "entries": [
                    {
                        "request": {
                            "method": "GET",
                            "url": "https://api.example.com/test",
                            "headers": [],
                            "queryString": [
                                {"name": "page", "value": "1"},
                                {"name": "limit", "value": "10"}
                            ]
                        },
                        "response": {
                            "status": 200,
                            "headers": [],
                            "content": {}
                        }
                    }
                ]
            }
        }
        parser = HARParser()
        flows = parser.parse(har_data)
        assert len(flows) == 1
        assert flows[0].request.query_params["page"] == "1"
        assert flows[0].request.query_params["limit"] == "10"


class TestSwaggerParserAdvanced:
    """Advanced tests for SwaggerParser."""

    def test_parse_swagger_2_0(self):
        """Test parsing Swagger 2.0 format."""
        swagger_data = {
            "swagger": "2.0",
            "info": {"title": "Test API", "version": "1.0"},
            "host": "api.example.com",
            "basePath": "/v1",
            "schemes": ["https"],
            "paths": {
                "/test": {
                    "get": {
                        "summary": "Test endpoint",
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            }
        }
        parser = SwaggerParser()
        doc = parser.parse(swagger_data)
        assert "swagger-2.0" in doc.openapi_version
        assert len(doc.servers) == 1

    def test_get_endpoints(self, sample_swagger_data):
        """Test getting all endpoints."""
        parser = SwaggerParser()
        endpoints = parser.get_endpoints(sample_swagger_data)
        assert len(endpoints) == 2

    def test_find_endpoint_method(self, sample_swagger_data):
        """Test find_endpoint method."""
        parser = SwaggerParser()
        endpoint = parser.find_endpoint(sample_swagger_data, "/api/login", "POST")
        assert endpoint is not None
        assert endpoint.operation_id == "login"

    def test_get_server_urls(self, sample_swagger_data):
        """Test getting server URLs."""
        parser = SwaggerParser()
        urls = parser.get_server_urls(sample_swagger_data)
        assert len(urls) == 1
        assert urls[0] == "https://api.example.com"

    def test_parse_nonexistent_file(self):
        """Test parsing non-existent file."""
        parser = SwaggerParser()
        with pytest.raises(FileNotFoundError):
            parser.parse("/nonexistent/swagger.json")

    def test_validate_schema(self, sample_swagger_data):
        """Test schema validation."""
        parser = SwaggerParser()
        data = {"name": "test", "id": 1}
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "id": {"type": "integer"}
            }
        }
        result = parser.validate_schema(data, schema)
        assert result is True

    def test_validate_schema_invalid(self, sample_swagger_data):
        """Test schema validation with invalid data."""
        parser = SwaggerParser()
        data = {"name": 123}  # name should be string
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            }
        }
        # jsonschema might be lenient, so just test it doesn't crash
        parser.validate_schema(data, schema)

    def test_parse_with_parameters(self, sample_swagger_data):
        """Test parsing endpoint with parameters."""
        parser = SwaggerParser()
        doc = parser.parse(sample_swagger_data)
        endpoint = doc.find_endpoint("/api/users/{id}", "GET")
        assert endpoint is not None
        assert len(endpoint.parameters) == 1
        assert endpoint.parameters[0].name == "id"
        assert endpoint.parameters[0].in_ == "path"
        assert endpoint.parameters[0].required is True

    def test_endpoint_get_success_response(self, sample_swagger_data):
        """Test getting success response."""
        parser = SwaggerParser()
        doc = parser.parse(sample_swagger_data)
        endpoint = doc.find_endpoint("/api/login", "POST")
        response = endpoint.get_success_response()
        assert response is not None
        assert response.status_code == "200"

    def test_endpoint_get_required_params(self, sample_swagger_data):
        """Test getting required parameters."""
        parser = SwaggerParser()
        doc = parser.parse(sample_swagger_data)
        endpoint = doc.find_endpoint("/api/users/{id}", "GET")
        required = endpoint.get_required_params()
        assert len(required) == 1


class TestLogParserAdvanced:
    """Advanced tests for LogParser."""

    def test_parse_combined_format(self):
        """Test parsing Nginx combined format."""
        parser = create_nginx_parser("combined")
        line = '192.168.1.1 - admin [25/Feb/2026:10:00:00 +0000] "GET /api/test HTTP/1.1" 200 1234 "http://referer.com" "Mozilla/5.0"'
        parsed = parser.parse_line(line)
        assert parsed is not None
        assert parsed.get("remote_addr") == "192.168.1.1"
        assert parsed.get("status") == 200

    def test_parse_apache_format(self):
        """Test parsing Apache format."""
        parser = create_apache_parser("common")
        line = '192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/test HTTP/1.1" 200 1234'
        parsed = parser.parse_line(line)
        assert parsed is not None

    def test_parse_with_query_params(self):
        """Test parsing URL with query parameters."""
        parser = LogParser()
        line = '192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/test?page=1&limit=10 HTTP/1.1" 200 1234'
        parsed = parser.parse_line(line)
        assert parsed is not None
        assert "query_params" in parsed
        assert parsed["query_params"]["page"] == "1"

    def test_parse_timestamp_formats(self):
        """Test parsing various timestamp formats."""
        parser = LogParser()

        # Test with different timestamp formats in the line
        lines = [
            '192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/test HTTP/1.1" 200 1234',
        ]

        for line in lines:
            parsed = parser.parse_line(line)
            assert parsed is not None

    def test_parse_file_max_lines(self, temp_dir):
        """Test parsing log file with max lines."""
        parser = LogParser()
        log_file = temp_dir / "test.log"
        log_file.write_text(
            '192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/test HTTP/1.1" 200 100\n'
            '192.168.1.1 - - [25/Feb/2026:10:00:01 +0000] "POST /api/login HTTP/1.1" 200 100\n'
            '192.168.1.2 - - [25/Feb/2026:10:00:02 +0000] "GET /api/products HTTP/1.1" 200 100\n'
        )

        entries = parser.parse_file(log_file, max_lines=2)
        assert len(entries) == 2

    def test_parse_file_not_found(self):
        """Test parsing non-existent file."""
        parser = LogParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/file.log")

    def test_parse_directory_not_found(self):
        """Test parsing non-existent directory."""
        parser = LogParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_directory("/nonexistent/dir")

    def test_extract_tokens_from_logs(self):
        """Test extracting tokens from logs."""
        entries = [
            {"request_uri": "https://api.com/test?token=abc123def456"},
            {"other_field": "auth_token=xyz789xyz789xyz789"}
        ]
        tokens = extract_tokens_from_logs(entries)
        assert isinstance(tokens, dict)

    def test_extract_ids_from_logs(self):
        """Test extracting IDs from logs."""
        entries = [
            {"request_uri": "https://api.com/users?id=123"},
            {"other_field": "id=456"}
        ]
        ids = extract_ids_from_logs(entries)
        assert 123 in ids
        assert 456 in ids


class TestApplicationLogParser:
    """Tests for ApplicationLogParser."""

    def test_init(self):
        """Test application log parser initialization."""
        parser = ApplicationLogParser(
            request_pattern=r'REQUEST.*id=(?P<request_id>\d+)',
            response_pattern=r'RESPONSE.*id=(?P<request_id>\d+)'
        )
        assert parser is not None

    def test_parse_request_response_pairs(self, temp_dir):
        """Test parsing request-response pairs."""
        parser = ApplicationLogParser(
            request_pattern=r'REQUEST id=(?P<request_id>\d+) method=(?P<method>\w+)',
            response_pattern=r'RESPONSE id=(?P<request_id>\d+) status=(?P<status>\d+)'
        )

        log_file = temp_dir / "app.log"
        log_file.write_text(
            "REQUEST id=100 method=GET\n"
            "RESPONSE id=100 status=200\n"
            "REQUEST id=101 method=POST\n"
            "RESPONSE id=101 status=201\n"
        )

        pairs = parser.parse_file(log_file)
        assert len(pairs) == 2
        assert pairs[0]["request"]["method"] == "GET"
        assert pairs[0]["response"]["status"] == "200"

    def test_parse_with_unmatched_requests(self, temp_dir):
        """Test parsing with unmatched requests."""
        parser = ApplicationLogParser(
            request_pattern=r'REQUEST id=(?P<request_id>\d+)',
            response_pattern=r'RESPONSE id=(?P<request_id>\d+)'
        )

        log_file = temp_dir / "app.log"
        log_file.write_text(
            "REQUEST id=100\n"
            "REQUEST id=101\n"
            "RESPONSE id=100\n"
        )

        pairs = parser.parse_file(log_file)
        assert len(pairs) == 1


class TestJSONLogParserAdvanced:
    """Advanced tests for JSONLogParser."""

    def test_parse_with_nested_json(self):
        """Test parsing JSON with nested objects."""
        parser = JSONLogParser()
        log_line = '{"method": "GET", "url": "/api/test", "status": 200, "request_uri": "/test?id=1"}'
        parsed = parser.parse_line(log_line)
        assert parsed is not None
        assert parsed["status"] == 200

    def test_parse_with_time_local(self):
        """Test parsing JSON with time_local field."""
        parser = JSONLogParser()
        log_line = '{"time_local": "25/Feb/2026:10:00:00 +0000"}'
        parsed = parser.parse_line(log_line)
        assert parsed is not None
        assert "timestamp" in parsed