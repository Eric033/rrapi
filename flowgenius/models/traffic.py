"""
Data models for traffic request and response.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TrafficRequest:
    """Represents an HTTP traffic request."""
    url: str
    method: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    query_params: Dict[str, str] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    content_type: Optional[str] = None

    def get_body_json(self) -> Optional[Dict[str, Any]]:
        """Parse request body as JSON."""
        if self.body and self.content_type and "application/json" in self.content_type:
            import json
            try:
                return json.loads(self.body)
            except json.JSONDecodeError:
                pass
        return None

    def is_static_resource(self) -> bool:
        """Check if this request is for a static resource."""
        static_extensions = {".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf", ".eot"}
        url_lower = self.url.lower()

        # Check by extension
        for ext in static_extensions:
            if url_lower.endswith(ext):
                return True

        # Check by content-type
        if self.content_type:
            ct_lower = self.content_type.lower()
            static_content_types = {
                "text/css",
                "text/javascript",
                "application/javascript",
                "image/",
                "font/",
            }
            for ct in static_content_types:
                if ct_lower.startswith(ct):
                    return True

        return False

    def get_api_name(self) -> str:
        """Generate a readable API name from the URL."""
        path_parts = [p for p in self.url.split("/") if p and not p.startswith("{")]
        if path_parts:
            return "_".join(path_parts[-2:]) if len(path_parts) >= 2 else path_parts[0]
        return f"{self.method.lower()}_api"


@dataclass
class TrafficResponse:
    """Represents an HTTP traffic response."""
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    time: Optional[float] = None  # Response time in seconds
    content_type: Optional[str] = None

    def get_body_json(self) -> Optional[Dict[str, Any]]:
        """Parse response body as JSON."""
        if self.body and self.content_type and "application/json" in self.content_type:
            import json
            try:
                return json.loads(self.body)
            except json.JSONDecodeError:
                pass
        return None

    def is_json(self) -> bool:
        """Check if response is JSON."""
        return self.content_type and "application/json" in self.content_type.lower()


@dataclass
class TrafficFlow:
    """Represents a complete traffic flow with request and response."""
    request: TrafficRequest
    response: TrafficResponse
    flow_id: str = ""

    def __post_init__(self):
        if not self.flow_id:
            import uuid
            self.flow_id = str(uuid.uuid4())

    def get_full_path(self) -> str:
        """Get the full path with query parameters."""
        path = self.request.url
        if self.request.query_params:
            query_str = "&".join(f"{k}={v}" for k, v in self.request.query_params.items())
            path = f"{path}?{query_str}"
        return path