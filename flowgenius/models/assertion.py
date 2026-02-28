"""
Data models for assertion rules.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class AssertionType(Enum):
    """Types of assertions."""
    STATUS_CODE = "status_code"
    RESPONSE_TIME = "response_time"
    JSON_SCHEMA = "json_schema"
    JSON_PATH = "json_path"
    CONTAINS = "contains"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    REGEX = "regex"
    SNAPSHOT = "snapshot"
    HAS_KEY = "has_key"
    HAS_VALUE = "has_value"


class AssertionCategory(Enum):
    """Categories of assertions."""
    HEALTH = "health"  # Status code, response time
    CONTRACT = "contract"  # Schema validation
    SEMANTIC = "semantic"  # Business logic assertions
    SNAPSHOT = "snapshot"  # Snapshot comparison


@dataclass
class AssertionRule:
    """Represents an assertion rule for a test."""
    assertion_type: AssertionType
    category: AssertionCategory
    description: str

    # Assertion-specific fields
    expected_value: Optional[Any] = None
    actual_jsonpath: Optional[str] = None  # For JSON assertions
    jsonpath: Optional[str] = None  # Alias for actual_jsonpath
    expected_jsonpath: Optional[str] = None  # For snapshot comparison
    threshold: Optional[float] = None  # For greater_than/less_than
    regex_pattern: Optional[str] = None  # For regex assertions
    schema: Optional[Dict[str, Any]] = None  # For schema assertions

    # Metadata
    flow_id: str = ""
    confidence: float = 1.0  # Confidence level
    is_extracted: bool = False  # Whether this assertion was auto-extracted from traffic
    source: str = "auto"  # "auto", "swagger", "manual", "snapshot"

    def __post_init__(self):
        if self.jsonpath and not self.actual_jsonpath:
            self.actual_jsonpath = self.jsonpath

    def get_assertion_code(self) -> str:
        """Generate Python code for this assertion."""
        if self.assertion_type == AssertionType.STATUS_CODE:
            if isinstance(self.expected_value, list):
                return f"assert response.status_code in {self.expected_value}"
            return f"assert response.status_code == {self.expected_value}"

        elif self.assertion_type == AssertionType.RESPONSE_TIME:
            if self.threshold:
                return f"assert response.elapsed.total_seconds() < {self.threshold}"
            return f"assert response.elapsed.total_seconds() > 0"

        elif self.assertion_type == AssertionType.JSON_SCHEMA:
            if self.schema:
                return "# Schema validation (use jsonschema library)\n# validate_json(response.json(), schema)"

        elif self.assertion_type == AssertionType.JSON_PATH:
            if self.actual_jsonpath and self.expected_value is not None:
                if isinstance(self.expected_value, str):
                    return f"assert extract_jsonpath(response.json(), '{self.actual_jsonpath}') == '{self.expected_value}'"
                return f"assert extract_jsonpath(response.json(), '{self.actual_jsonpath}') == {self.expected_value}"

        elif self.assertion_type == AssertionType.CONTAINS:
            if self.actual_jsonpath and isinstance(self.expected_value, str):
                return f"assert '{self.expected_value}' in str(extract_jsonpath(response.json(), '{self.actual_jsonpath}'))"

        elif self.assertion_type == AssertionType.EQUALS:
            if self.actual_jsonpath and self.expected_value is not None:
                return f"assert extract_jsonpath(response.json(), '{self.actual_jsonpath}') == {repr(self.expected_value)}"

        elif self.assertion_type == AssertionType.HAS_KEY:
            if self.actual_jsonpath:
                return f"assert extract_jsonpath(response.json(), '{self.actual_jsonpath}') is not None"

        elif self.assertion_type == AssertionType.SNAPSHOT:
            if self.actual_jsonpath:
                return f"assert compare_snapshot(response.json(), '{self.actual_jsonpath}')"

        return f"# {self.description}"

    def get_description(self) -> str:
        """Get a human-readable description of this assertion."""
        if self.assertion_type == AssertionType.STATUS_CODE:
            return f"HTTP status code should be {self.expected_value}"
        elif self.assertion_type == AssertionType.RESPONSE_TIME:
            return f"Response time should be less than {self.threshold}s"
        elif self.assertion_type == AssertionType.JSON_SCHEMA:
            return "Response should match JSON schema"
        elif self.assertion_type == AssertionType.JSON_PATH:
            return f"JSON path {self.actual_jsonpath} should equal {self.expected_value}"
        elif self.assertion_type == AssertionType.CONTAINS:
            return f"Response should contain '{self.expected_value}'"
        elif self.assertion_type == AssertionType.EQUALS:
            return f"Field {self.actual_jsonpath} should equal {self.expected_value}"
        elif self.assertion_type == AssertionType.HAS_KEY:
            return f"Response should have key at {self.actual_jsonpath}"
        elif self.assertion_type == AssertionType.SNAPSHOT:
            return "Response should match snapshot"
        return self.description


@dataclass
class AssertionSet:
    """Represents a set of assertions for a specific flow."""
    flow_id: str
    assertions: List[AssertionRule] = field(default_factory=list)

    def add_assertion(self, assertion: AssertionRule):
        """Add an assertion to this set."""
        assertion.flow_id = self.flow_id
        self.assertions.append(assertion)

    def get_assertions_by_category(self, category: AssertionCategory) -> List[AssertionRule]:
        """Get all assertions of a specific category."""
        return [a for a in self.assertions if a.category == category]

    def get_health_assertions(self) -> List[AssertionRule]:
        """Get all health assertions."""
        return self.get_assertions_by_category(AssertionCategory.HEALTH)

    def get_contract_assertions(self) -> List[AssertionRule]:
        """Get all contract assertions."""
        return self.get_assertions_by_category(AssertionCategory.CONTRACT)

    def get_semantic_assertions(self) -> List[AssertionRule]:
        """Get all semantic assertions."""
        return self.get_assertions_by_category(AssertionCategory.SEMANTIC)

    def get_snapshot_assertions(self) -> List[AssertionRule]:
        """Get all snapshot assertions."""
        return self.get_assertions_by_category(AssertionCategory.SNAPSHOT)

    def generate_assertion_code(self) -> str:
        """Generate Python code for all assertions."""
        lines = []
        for assertion in self.assertions:
            lines.append(f"        # {assertion.get_description()}")
            code = assertion.get_assertion_code()
            if code and not code.startswith("#"):
                lines.append(f"        {code}")
            elif code:
                lines.append(code)
        return "\n".join(lines)


@dataclass
class Snapshot:
    """Represents a snapshot of a response for regression testing."""
    flow_id: str
    jsonpath: str
    value: Any
    timestamp: str
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "flow_id": self.flow_id,
            "jsonpath": self.jsonpath,
            "value": self.value,
            "timestamp": self.timestamp,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Snapshot":
        """Create snapshot from dictionary."""
        return cls(
            flow_id=data["flow_id"],
            jsonpath=data["jsonpath"],
            value=data["value"],
            timestamp=data["timestamp"],
            description=data.get("description")
        )