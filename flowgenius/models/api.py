"""
Data models for API definitions from Swagger/OpenAPI.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class ParameterDefinition:
    """Represents a parameter definition from Swagger/OpenAPI."""
    name: str
    in_: str  # "query", "header", "path", "cookie"
    description: Optional[str] = None
    required: bool = False
    schema: Optional[Dict[str, Any]] = None
    type: Optional[str] = None
    default: Optional[Any] = None


@dataclass
class PropertyDefinition:
    """Represents a property definition in a schema."""
    name: str
    type: str
    required: bool = False
    description: Optional[str] = None
    format: Optional[str] = None
    enum: Optional[List[Any]] = None
    properties: Optional[Dict[str, "PropertyDefinition"]] = None
    items: Optional["PropertyDefinition"] = None


@dataclass
class ResponseDefinition:
    """Represents a response definition from Swagger/OpenAPI."""
    status_code: str  # "200", "400", etc.
    description: Optional[str] = None
    content_type: Optional[str] = None
    schema: Optional[Dict[str, Any]] = None
    properties: Optional[Dict[str, PropertyDefinition]] = None
    required_fields: List[str] = field(default_factory=list)


@dataclass
class APIEndpoint:
    """Represents an API endpoint from Swagger/OpenAPI."""
    path: str
    method: str  # "GET", "POST", "PUT", "DELETE", etc.
    operation_id: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    parameters: List[ParameterDefinition] = field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    responses: Dict[str, ResponseDefinition] = field(default_factory=dict)
    security: List[Dict[str, Any]] = field(default_factory=list)

    def get_class_name(self) -> str:
        """Generate a class name for this API endpoint."""
        path_parts = [p.strip("{}") for p in self.path.split("/") if p and not p.startswith("{")]
        method_name = self.method.lower()

        if path_parts:
            resource = path_parts[-1]
            if len(path_parts) > 1:
                action = path_parts[-2]
                return f"Api{action.capitalize()}{resource.capitalize()}"
            return f"Api{resource.capitalize()}"
        return f"Api{method_name}"

    def get_method_name(self) -> str:
        """Generate a method name for this API endpoint."""
        path_parts = [p.strip("{}") for p in self.path.split("/") if p]
        method_prefix = self.method.lower()

        if path_parts:
            action = path_parts[-1]
            if len(path_parts) > 1:
                resource = path_parts[-2]
                return f"{method_prefix}_{resource}_{action}"
            return f"{method_prefix}_{action}"
        return f"{method_prefix}_api"

    def get_success_response(self) -> Optional[ResponseDefinition]:
        """Get the success response (2xx status code)."""
        for code, response in self.responses.items():
            if code.startswith("2"):
                return response
        return None

    def get_required_params(self) -> List[ParameterDefinition]:
        """Get all required parameters."""
        return [p for p in self.parameters if p.required]


@dataclass
class SwaggerDoc:
    """Represents a complete Swagger/OpenAPI document."""
    openapi_version: str
    info: Dict[str, Any]
    servers: List[Dict[str, Any]] = field(default_factory=list)
    paths: Dict[str, Dict[str, APIEndpoint]] = field(default_factory=dict)
    components: Optional[Dict[str, Any]] = None

    def find_endpoint(self, path: str, method: str) -> Optional[APIEndpoint]:
        """Find an endpoint by path and method."""
        path_obj = self.paths.get(path)
        if path_obj:
            return path_obj.get(method.upper())
        return None

    def find_endpoint_by_url(self, url: str) -> Optional[APIEndpoint]:
        """Find an endpoint by URL (path only)."""
        # Extract path from URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path

        # Try exact match first
        endpoint = self.find_endpoint(path, "*") or None
        if endpoint:
            return endpoint

        # Try to match each path in swagger
        for swagger_path, methods in self.paths.items():
            if self._match_path(path, swagger_path):
                return list(methods.values())[0] if methods else None

        return None

    def _match_path(self, actual_path: str, swagger_path: str) -> bool:
        """Check if actual path matches swagger path with parameters."""
        actual_parts = actual_path.split("/")
        swagger_parts = swagger_path.split("/")

        if len(actual_parts) != len(swagger_parts):
            return False

        for actual, swagger in zip(actual_parts, swagger_parts):
            # Swagger parameter placeholder
            if swagger.startswith("{") and swagger.endswith("}"):
                continue
            if actual != swagger:
                return False

        return True

    def get_all_endpoints(self) -> List[APIEndpoint]:
        """Get all API endpoints."""
        endpoints = []
        for path, methods in self.paths.items():
            for method, endpoint in methods.items():
                endpoints.append(endpoint)
        return endpoints