"""
Swagger/OpenAPI parser for API definitions.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from flowgenius.models.api import (
    APIEndpoint,
    ParameterDefinition,
    PropertyDefinition,
    ResponseDefinition,
    SwaggerDoc
)
from flowgenius.utils.logger import get_logger


class SwaggerParser:
    """Parser for Swagger/OpenAPI specifications."""

    def __init__(self):
        """Initialize Swagger parser."""
        self.logger = get_logger("flowgenius.swagger_parser")

    def parse(self, swagger_source: Union[str, Path, Dict[str, Any]]) -> SwaggerDoc:
        """
        Parse Swagger/OpenAPI specification into SwaggerDoc.

        Args:
            swagger_source: Path to Swagger file, URL, or dict

        Returns:
            SwaggerDoc object
        """
        if isinstance(swagger_source, (str, Path)):
            swagger_data = self._load_swagger_file(swagger_source)
        else:
            swagger_data = swagger_source

        # Check if it's a URL (not implemented, would use requests)
        if isinstance(swagger_source, str) and swagger_source.startswith(("http://", "https://")):
            swagger_data = self._load_swagger_url(swagger_source)

        return self._parse_swagger(swagger_data)

    def _load_swagger_file(self, swagger_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load Swagger file from local path.

        Args:
            swagger_path: Path to Swagger file

        Returns:
            Swagger data dictionary
        """
        swagger_path = Path(swagger_path)
        if not swagger_path.exists():
            raise FileNotFoundError(f"Swagger file not found: {swagger_path}")

        with open(swagger_path, 'r', encoding='utf-8') as f:
            if swagger_path.suffix.lower() in ('.yaml', '.yml'):
                import yaml
                try:
                    return yaml.safe_load(f)
                except yaml.YAMLError as e:
                    raise ValueError(f"Invalid YAML file: {e}")
            else:
                try:
                    return json.load(f)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON file: {e}")

    def _load_swagger_url(self, swagger_url: str) -> Dict[str, Any]:
        """
        Load Swagger spec from URL.

        Args:
            swagger_url: URL to Swagger spec

        Returns:
            Swagger data dictionary
        """
        try:
            import requests
            response = requests.get(swagger_url, timeout=30)
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '')
            if 'yaml' in content_type or swagger_url.endswith(('.yaml', '.yml')):
                import yaml
                return yaml.safe_load(response.text)
            else:
                return response.json()

        except Exception as e:
            raise ValueError(f"Failed to load Swagger from URL: {e}")

    def _parse_swagger(self, swagger_data: Dict[str, Any]) -> SwaggerDoc:
        """
        Parse Swagger data into SwaggerDoc.

        Args:
            swagger_data: Swagger/OpenAPI data dictionary

        Returns:
            SwaggerDoc object
        """
        # Detect version
        openapi_version = self._detect_version(swagger_data)

        # Parse info
        info = swagger_data.get("info", {})

        # Parse servers
        servers = swagger_data.get("servers", [])
        if not servers and "host" in swagger_data:
            # Swagger 2.0 format
            host = swagger_data.get("host", "")
            base_path = swagger_data.get("basePath", "")
            schemes = swagger_data.get("schemes", ["http"])
            servers = [{"url": f"{schemes[0]}://{host}{base_path}"}]

        # Parse paths
        paths = self._parse_paths(swagger_data.get("paths", {}))

        # Parse components/definitions
        components = swagger_data.get("components") or swagger_data.get("definitions", {})

        return SwaggerDoc(
            openapi_version=openapi_version,
            info=info,
            servers=servers,
            paths=paths,
            components=components
        )

    def _detect_version(self, swagger_data: Dict[str, Any]) -> str:
        """
        Detect Swagger/OpenAPI version.

        Args:
            swagger_data: Swagger data dictionary

        Returns:
            Version string
        """
        if "openapi" in swagger_data:
            return swagger_data["openapi"]
        elif "swagger" in swagger_data:
            return f"swagger-{swagger_data['swagger']}"
        return "unknown"

    def _parse_paths(self, paths_data: Dict[str, Any]) -> Dict[str, Dict[str, APIEndpoint]]:
        """
        Parse paths section into APIEndpoint objects.

        Args:
            paths_data: Paths data from Swagger spec

        Returns:
            Dictionary mapping paths to methods to APIEndpoint objects
        """
        result = {}

        for path, methods in paths_data.items():
            result[path] = {}
            for method_name, method_data in methods.items():
                if method_name.upper() in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
                    endpoint = self._parse_endpoint(path, method_name.upper(), method_data)
                    result[path][method_name.upper()] = endpoint

        return result

    def _parse_endpoint(self, path: str, method: str, method_data: Dict[str, Any]) -> APIEndpoint:
        """
        Parse a single endpoint method.

        Args:
            path: API path
            method: HTTP method
            method_data: Method data from Swagger spec

        Returns:
            APIEndpoint object
        """
        # Parse parameters
        parameters = self._parse_parameters(method_data.get("parameters", []))

        # Parse request body
        request_body = method_data.get("requestBody")
        if request_body:
            request_body = self._parse_request_body(request_body)

        # Parse responses
        responses = {}
        for status_code, response_data in method_data.get("responses", {}).items():
            responses[status_code] = self._parse_response(response_data)

        return APIEndpoint(
            path=path,
            method=method,
            operation_id=method_data.get("operationId"),
            summary=method_data.get("summary"),
            description=method_data.get("description"),
            tags=method_data.get("tags", []),
            parameters=parameters,
            request_body=request_body,
            responses=responses,
            security=method_data.get("security", [])
        )

    def _parse_parameters(self, parameters_data: List[Dict[str, Any]]) -> List[ParameterDefinition]:
        """
        Parse parameters list.

        Args:
            parameters_data: Parameters data

        Returns:
            List of ParameterDefinition objects
        """
        parameters = []

        for param_data in parameters_data:
            param = ParameterDefinition(
                name=param_data.get("name", ""),
                in_=param_data.get("in", ""),
                description=param_data.get("description"),
                required=param_data.get("required", False),
                schema=param_data.get("schema"),
                type=param_data.get("type") or param_data.get("schema", {}).get("type"),
                default=param_data.get("default")
            )
            parameters.append(param)

        return parameters

    def _parse_request_body(self, request_body_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse request body data.

        Args:
            request_body_data: Request body data

        Returns:
            Parsed request body dictionary
        """
        content = request_body_data.get("content", {})
        if content:
            # OpenAPI 3.0 format
            return {
                "description": request_body_data.get("description"),
                "required": request_body_data.get("required", False),
                "content": content
            }

        # Fallback for Swagger 2.0
        return request_body_data

    def _parse_response(self, response_data: Dict[str, Any]) -> ResponseDefinition:
        """
        Parse response data.

        Args:
            response_data: Response data

        Returns:
            ResponseDefinition object
        """
        # Parse content type and schema
        content_type = None
        schema = None

        content = response_data.get("content", {})
        if content:
            # OpenAPI 3.0 format
            for ct, ct_data in content.items():
                content_type = ct
                schema = ct_data.get("schema")
                break
        else:
            # Swagger 2.0 format
            schema = response_data.get("schema")
            content_type = "application/json"

        # Parse schema to extract properties and required fields
        properties = None
        required_fields = []

        if schema:
            properties, required_fields = self._parse_schema(schema)

        return ResponseDefinition(
            status_code=str(response_data.get("code", response_data.get("__key", "200"))),
            description=response_data.get("description"),
            content_type=content_type,
            schema=schema,
            properties=properties,
            required_fields=required_fields
        )

    def _parse_schema(self, schema: Dict[str, Any]) -> tuple[Dict[str, PropertyDefinition], List[str]]:
        """
        Parse schema to extract properties.

        Args:
            schema: Schema object

        Returns:
            Tuple of (properties dict, required fields list)
        """
        properties = {}
        required_fields = schema.get("required", [])

        props_data = schema.get("properties", {})
        for prop_name, prop_schema in props_data.items():
            prop = PropertyDefinition(
                name=prop_name,
                type=prop_schema.get("type", "string"),
                required=prop_name in required_fields,
                description=prop_schema.get("description"),
                format=prop_schema.get("format"),
                enum=prop_schema.get("enum"),
                properties=self._parse_schema(prop_schema)[0] if prop_schema.get("type") == "object" else None,
                items=self._parse_property(prop_schema.get("items")) if prop_schema.get("type") == "array" else None
            )
            properties[prop_name] = prop

        return properties, required_fields

    def _parse_property(self, prop_schema: Dict[str, Any]) -> Optional[PropertyDefinition]:
        """
        Parse a single property.

        Args:
            prop_schema: Property schema

        Returns:
            PropertyDefinition object
        """
        if not prop_schema:
            return None

        properties, _ = self._parse_schema(prop_schema)
        return PropertyDefinition(
            name="",
            type=prop_schema.get("type", "string"),
            required=False,
            description=prop_schema.get("description"),
            format=prop_schema.get("format"),
            enum=prop_schema.get("enum"),
            properties=properties.get("properties") if properties else None
        )

    def get_endpoints(self, swagger_source: Union[str, Path, Dict[str, Any]]) -> List[APIEndpoint]:
        """
        Get all API endpoints from Swagger spec.

        Args:
            swagger_source: Swagger source

        Returns:
            List of APIEndpoint objects
        """
        swagger_doc = self.parse(swagger_source)
        return swagger_doc.get_all_endpoints()

    def find_endpoint(
        self,
        swagger_source: Union[str, Path, Dict[str, Any]],
        path: str,
        method: str
    ) -> Optional[APIEndpoint]:
        """
        Find a specific endpoint.

        Args:
            swagger_source: Swagger source
            path: API path
            method: HTTP method

        Returns:
            APIEndpoint object or None
        """
        swagger_doc = self.parse(swagger_source)
        return swagger_doc.find_endpoint(path, method.upper())

    def match_endpoint_by_url(
        self,
        swagger_source: Union[str, Path, Dict[str, Any]],
        url: str
    ) -> Optional[APIEndpoint]:
        """
        Find endpoint matching a URL.

        Args:
            swagger_source: Swagger source
            url: URL to match

        Returns:
            APIEndpoint object or None
        """
        swagger_doc = self.parse(swagger_source)
        return swagger_doc.find_endpoint_by_url(url)

    def get_server_urls(self, swagger_source: Union[str, Path, Dict[str, Any]]) -> List[str]:
        """
        Get all server URLs from Swagger spec.

        Args:
            swagger_source: Swagger source

        Returns:
            List of server URLs
        """
        swagger_doc = self.parse(swagger_source)
        return [server.get("url", "") for server in swagger_doc.servers]

    def validate_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """
        Validate data against JSON schema.

        Args:
            data: Data to validate
            schema: JSON schema

        Returns:
            True if valid
        """
        try:
            import jsonschema
            jsonschema.validate(data, schema)
            return True
        except Exception:
            return False