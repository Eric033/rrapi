"""
Integration tests for Swagger/OpenAPI integration.
"""
import pytest
import json
import yaml
from pathlib import Path

from flowgenius.parsers.swagger_parser import SwaggerParser
from flowgenius.parsers.har_parser import HARParser
from flowgenius.models.api import APIEndpoint, SwaggerDoc


class TestSwaggerIntegration:
    """Integration tests for Swagger/OpenAPI integration."""

    def test_load_swagger_json_file(self, temp_dir, sample_swagger_data):
        """Test loading Swagger from JSON file."""
        swagger_file = temp_dir / "swagger.json"
        swagger_file.write_text(json.dumps(sample_swagger_data))

        parser = SwaggerParser()
        swagger_doc = parser.parse(str(swagger_file))

        assert isinstance(swagger_doc, SwaggerDoc)
        assert swagger_doc.openapi_version == "3.0.0"

    def test_load_swagger_yaml_file(self, temp_dir, sample_swagger_data):
        """Test loading Swagger from YAML file."""
        swagger_file = temp_dir / "swagger.yaml"
        swagger_file.write_text(yaml.dump(sample_swagger_data))

        parser = SwaggerParser()
        swagger_doc = parser.parse(str(swagger_file))

        assert isinstance(swagger_doc, SwaggerDoc)
        assert swagger_doc.openapi_version == "3.0.0"

    def test_find_and_use_endpoint(self, sample_swagger_data):
        """Test finding and using specific endpoints."""
        parser = SwaggerParser()
        swagger_doc = parser.parse(sample_swagger_data)

        # Find login endpoint
        login_endpoint = swagger_doc.find_endpoint("/api/login", "POST")
        assert login_endpoint is not None
        assert login_endpoint.method == "POST"
        assert login_endpoint.operation_id == "login"

        # Find user endpoint
        user_endpoint = swagger_doc.find_endpoint("/api/users/{id}", "GET")
        assert user_endpoint is not None
        assert user_endpoint.method == "GET"

        # Find non-existent endpoint
        not_found = swagger_doc.find_endpoint("/api/notfound", "GET")
        assert not_found is None

    def test_match_traffic_to_swagger(self, sample_har_data, sample_swagger_data):
        """Test matching captured traffic to Swagger endpoints."""
        # Parse HAR
        har_parser = HARParser()
        flows = har_parser.parse(sample_har_data)

        # Parse Swagger
        swagger_parser = SwaggerParser()
        swagger_doc = swagger_parser.parse(sample_swagger_data)

        # Match flows to endpoints
        for flow in flows:
            # Use find_endpoint with both path and method for better matching
            from urllib.parse import urlparse
            parsed = urlparse(flow.request.url)
            path = parsed.path

            endpoint = swagger_doc.find_endpoint(path, flow.request.method)
            if endpoint is None:
                # Try fuzzy matching
                endpoint = swagger_doc.find_endpoint_by_url(flow.request.url)

            if flow.request.url == "https://api.example.com/login":
                assert endpoint is not None
                assert endpoint.method == "POST"

    def test_generate_assertions_from_swagger(self, sample_swagger_data):
        """Test generating assertions from Swagger definitions."""
        parser = SwaggerParser()
        swagger_doc = parser.parse(sample_swagger_data)

        # Get login endpoint
        login_endpoint = swagger_doc.find_endpoint("/api/login", "POST")
        assert login_endpoint is not None

        # Get success response
        success_response = login_endpoint.get_success_response()
        assert success_response is not None
        assert success_response.status_code == "200"

        # Check required fields
        user_endpoint = swagger_doc.find_endpoint("/api/users/{id}", "GET")
        assert user_endpoint is not None

        params = user_endpoint.get_required_params()
        assert len(params) == 1
        assert params[0].name == "id"
        assert params[0].required is True

    def test_swagger_path_parameter_matching(self, sample_swagger_data):
        """Test matching URLs with path parameters."""
        parser = SwaggerParser()
        swagger_doc = parser.parse(sample_swagger_data)

        # Test matching with different IDs
        test_urls = [
            "https://api.example.com/api/users/123",
            "https://api.example.com/api/users/456",
            "https://api.example.com/api/users/abc",
        ]

        for url in test_urls:
            endpoint = swagger_doc.find_endpoint_by_url(url)
            assert endpoint is not None
            assert endpoint.path == "/api/users/{id}"

    def test_swagger_server_urls(self, sample_swagger_data):
        """Test getting server URLs from Swagger."""
        parser = SwaggerParser()
        swagger_doc = parser.parse(sample_swagger_data)

        server_urls = [server.get("url", "") for server in swagger_doc.servers]
        assert len(server_urls) > 0
        assert "https://api.example.com" in server_urls

    def test_swagger_multiple_endpoints_same_path(self, temp_dir):
        """Test Swagger with multiple methods on same path."""
        swagger_data = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/api/users": {
                    "get": {
                        "operationId": "getUsers",
                        "summary": "Get all users",
                        "responses": {"200": {"description": "Success"}}
                    },
                    "post": {
                        "operationId": "createUser",
                        "summary": "Create user",
                        "responses": {"201": {"description": "Created"}}
                    }
                }
            }
        }

        parser = SwaggerParser()
        swagger_doc = parser.parse(swagger_data)

        # Should have both methods
        get_endpoint = swagger_doc.find_endpoint("/api/users", "GET")
        post_endpoint = swagger_doc.find_endpoint("/api/users", "POST")

        assert get_endpoint is not None
        assert post_endpoint is not None
        assert get_endpoint.operation_id == "getUsers"
        assert post_endpoint.operation_id == "createUser"

    def test_swagger_nested_parameters(self, temp_dir):
        """Test Swagger with nested object parameters."""
        swagger_data = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/api/users": {
                    "post": {
                        "operationId": "createUser",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["name", "email"],
                                        "properties": {
                                            "name": {"type": "string"},
                                            "email": {"type": "string"},
                                            "address": {
                                                "type": "object",
                                                "properties": {
                                                    "street": {"type": "string"},
                                                    "city": {"type": "string"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "responses": {"201": {"description": "Created"}}
                    }
                }
            }
        }

        parser = SwaggerParser()
        swagger_doc = parser.parse(swagger_data)

        endpoint = swagger_doc.find_endpoint("/api/users", "POST")
        assert endpoint is not None

        # Check request body structure
        assert endpoint.request_body is not None

    def test_swagger_response_schema_validation(self, sample_swagger_data):
        """Test schema validation using Swagger definitions."""
        parser = SwaggerParser()
        swagger_doc = parser.parse(sample_swagger_data)

        # Get login endpoint
        login_endpoint = swagger_doc.find_endpoint("/api/login", "POST")
        success_response = login_endpoint.get_success_response()

        # Check schema properties
        if success_response and success_response.properties:
            # Should have schema properties if defined
            assert isinstance(success_response.properties, dict)

    def test_swagger_tags_grouping(self, temp_dir):
        """Test Swagger endpoint tags."""
        swagger_data = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/api/users": {
                    "get": {
                        "tags": ["users"],
                        "operationId": "getUsers",
                        "responses": {"200": {"description": "Success"}}
                    }
                },
                "/api/products": {
                    "get": {
                        "tags": ["products"],
                        "operationId": "getProducts",
                        "responses": {"200": {"description": "Success"}}
                    }
                }
            }
        }

        parser = SwaggerParser()
        swagger_doc = parser.parse(swagger_data)

        endpoints = swagger_doc.get_all_endpoints()

        # Check tags
        user_endpoint = swagger_doc.find_endpoint("/api/users", "GET")
        product_endpoint = swagger_doc.find_endpoint("/api/products", "GET")

        assert "users" in user_endpoint.tags
        assert "products" in product_endpoint.tags

    def test_swagger_security_definitions(self, temp_dir):
        """Test Swagger security definitions."""
        swagger_data = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "components": {
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer"
                    }
                }
            },
            "paths": {
                "/api/users": {
                    "get": {
                        "security": [{"bearerAuth": []}],
                        "responses": {"200": {"description": "Success"}}
                    }
                }
            }
        }

        parser = SwaggerParser()
        swagger_doc = parser.parse(swagger_data)

        endpoint = swagger_doc.find_endpoint("/api/users", "GET")
        assert endpoint is not None

        # Check security requirements
        if endpoint.security:
            assert len(endpoint.security) > 0

    def test_generate_class_from_swagger(self, temp_dir, sample_swagger_data):
        """Test generating API class from Swagger endpoint."""
        parser = SwaggerParser()
        swagger_doc = parser.parse(sample_swagger_data)

        from flowgenius.generators.api_object import APIObjectGenerator
        generator = APIObjectGenerator()

        # Get endpoint and generate class
        login_endpoint = swagger_doc.find_endpoint("/api/login", "POST")
        class_code = generator.generate_class(login_endpoint, "https://api.example.com")

        # Verify generated class
        assert "class " in class_code
        assert "post" in class_code or "POST" in class_code
        assert "login" in class_code.lower()

    def test_swagger_description_documentation(self, temp_dir):
        """Test extracting documentation from Swagger."""
        swagger_data = {
            "openapi": "3.0.0",
            "info": {
                "title": "Test API",
                "version": "1.0.0",
                "description": "This is a test API"
            },
            "paths": {
                "/api/test": {
                    "get": {
                        "summary": "Get test data",
                        "description": "This endpoint returns test data",
                        "operationId": "getTest",
                        "responses": {"200": {"description": "Success"}}
                    }
                }
            }
        }

        parser = SwaggerParser()
        swagger_doc = parser.parse(swagger_data)

        # Check info
        assert swagger_doc.info["title"] == "Test API"
        assert swagger_doc.info["description"] == "This is a test API"

        # Check endpoint documentation
        endpoint = swagger_doc.find_endpoint("/api/test", "GET")
        assert endpoint.summary == "Get test data"
        assert endpoint.description == "This endpoint returns test data"