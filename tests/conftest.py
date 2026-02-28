"""
Pytest configuration and fixtures for tests.
"""
import pytest
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_request_data() -> Dict[str, Any]:
    """Sample HTTP request data."""
    return {
        "url": "https://api.example.com/users/123",
        "method": "GET",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": "Bearer token123"
        },
        "query": {"page": "1", "limit": "10"},
        "content": None,
        "timestamp": 1708861200.0
    }


@pytest.fixture
def sample_response_data() -> Dict[str, Any]:
    """Sample HTTP response data."""
    return {
        "status_code": 200,
        "headers": {
            "Content-Type": "application/json",
            "Content-Length": "1234"
        },
        "content": json.dumps({
            "code": 0,
            "success": True,
            "data": {
                "id": 123,
                "name": "Test User",
                "email": "test@example.com",
                "token": "abc123xyz456"
            }
        }),
        "time": 0.5
    }


@pytest.fixture
def sample_flow(sample_request_data, sample_response_data):
    """Sample traffic flow."""
    from flowgenius.models.traffic import TrafficRequest, TrafficResponse, TrafficFlow

    request = TrafficRequest(
        url=sample_request_data["url"],
        method=sample_request_data["method"],
        headers=sample_request_data["headers"],
        query_params=sample_request_data["query"],
        timestamp=datetime.fromtimestamp(sample_request_data["timestamp"]),
        content_type=sample_request_data["headers"]["Content-Type"]
    )

    response = TrafficResponse(
        status_code=sample_response_data["status_code"],
        headers=sample_response_data["headers"],
        body=sample_response_data["content"],
        time=sample_response_data["time"],
        content_type=sample_response_data["headers"]["Content-Type"]
    )

    return TrafficFlow(request=request, response=response)


@pytest.fixture
def sample_har_data() -> Dict[str, Any]:
    """Sample HAR file data."""
    return {
        "log": {
            "version": "1.2",
            "creator": {"name": "FlowGenius"},
            "entries": [
                {
                    "startedDateTime": "2026-02-25T10:00:00Z",
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/login",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"}
                        ],
                        "queryString": [],
                        "postData": {
                            "text": json.dumps({"username": "test", "password": "123456"}),
                            "mimeType": "application/json"
                        }
                    },
                    "response": {
                        "status": 200,
                        "statusText": "OK",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"}
                        ],
                        "content": {
                            "text": json.dumps({
                                "code": 0,
                                "success": True,
                                "data": {"token": "abc123"}
                            }),
                            "mimeType": "application/json"
                        }
                    },
                    "timings": {"receive": 500}
                }
            ]
        }
    }


@pytest.fixture
def sample_swagger_data() -> Dict[str, Any]:
    """Sample Swagger/OpenAPI data."""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Sample API",
            "version": "1.0.0"
        },
        "servers": [
            {"url": "https://api.example.com"}
        ],
        "paths": {
            "/api/login": {
                "post": {
                    "operationId": "login",
                    "summary": "User login",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["username", "password"],
                                    "properties": {
                                        "username": {"type": "string"},
                                        "password": {"type": "string"}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Login successful",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "code": {"type": "integer"},
                                            "success": {"type": "boolean"},
                                            "data": {
                                                "type": "object",
                                                "properties": {
                                                    "token": {"type": "string"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/api/users/{id}": {
                "get": {
                    "operationId": "getUser",
                    "summary": "Get user by ID",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "User found",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "name": {"type": "string"},
                                            "email": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }


@pytest.fixture
def sample_log_lines() -> List[str]:
    """Sample Nginx log lines."""
    return [
        '192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/users HTTP/1.1" 200 1234 "-" "Mozilla/5.0"',
        '192.168.1.1 - - [25/Feb/2026:10:00:01 +0000] "POST /api/login HTTP/1.1" 200 567 "-" "Mozilla/5.0"',
        '192.168.1.2 - - [25/Feb/2026:10:00:02 +0000] "GET /api/products HTTP/1.1" 200 890 "-" "Mozilla/5.0"',
    ]


@pytest.fixture
def temp_dir(tmp_path) -> Path:
    """Temporary directory for test files."""
    return tmp_path


@pytest.fixture
def base_url() -> str:
    """Base URL for API tests."""
    return "https://api.example.com"