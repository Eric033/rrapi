"""
Data models for correlation rules between requests and responses.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExtractionRule:
    """Represents a rule for extracting a value from a response."""
    source_flow_id: str
    source_jsonpath: str  # e.g., "$.data.token"
    source_regex: Optional[str] = None
    variable_name: str = ""
    description: Optional[str] = None

    def __post_init__(self):
        if not self.variable_name:
            # Generate variable name from jsonpath
            path_parts = self.source_jsonpath.replace("$.data.", "").split(".")
            self.variable_name = "_".join(path_parts)


@dataclass
class VariableReference:
    """Represents a reference to a variable in a request."""
    target_flow_id: str
    target_location: str  # "header", "query", "body"
    target_key: str
    variable_name: str


@dataclass
class CorrelationRule:
    """Represents a correlation between a response field and a request field."""
    response_flow_id: str
    request_flow_id: str
    response_jsonpath: str
    request_location: str  # "header", "query", "body"
    request_jsonpath: Optional[str] = None  # For body location
    request_key: Optional[str] = None  # For header/query location
    variable_name: str = ""
    confidence: float = 1.0  # 0.0 to 1.0, confidence level of the correlation

    def __post_init__(self):
        if not self.variable_name:
            # Generate variable name from response jsonpath
            path_parts = self.response_jsonpath.replace("$.data.", "").replace("$.", "").split(".")
            self.variable_name = "_".join(path_parts)


@dataclass
class CorrelationChain:
    """Represents a chain of correlated flows."""
    flow_ids: List[str] = field(default_factory=list)
    correlations: List[CorrelationRule] = field(default_factory=list)
    variables: Dict[str, str] = field(default_factory=dict)  # variable_name -> value

    def add_flow(self, flow_id: str):
        """Add a flow to the chain."""
        if flow_id not in self.flow_ids:
            self.flow_ids.append(flow_id)

    def add_correlation(self, correlation: CorrelationRule):
        """Add a correlation rule to the chain."""
        self.correlations.append(correlation)

    def get_dependencies(self, flow_id: str) -> List[str]:
        """Get all flow IDs that this flow depends on."""
        dependencies = []
        for correlation in self.correlations:
            if correlation.request_flow_id == flow_id:
                if correlation.response_flow_id not in dependencies:
                    dependencies.append(correlation.response_flow_id)
        return dependencies

    def get_flow_variables(self, flow_id: str) -> List[VariableReference]:
        """Get all variables used in a specific flow."""
        references = []
        for correlation in self.correlations:
            if correlation.request_flow_id == flow_id:
                if correlation.request_location == "header":
                    ref = VariableReference(
                        target_flow_id=flow_id,
                        target_location="header",
                        target_key=correlation.request_key or "",
                        variable_name=correlation.variable_name
                    )
                elif correlation.request_location == "query":
                    ref = VariableReference(
                        target_flow_id=flow_id,
                        target_location="query",
                        target_key=correlation.request_key or "",
                        variable_name=correlation.variable_name
                    )
                else:  # body
                    ref = VariableReference(
                        target_flow_id=flow_id,
                        target_location="body",
                        target_key=correlation.request_jsonpath or "",
                        variable_name=correlation.variable_name
                    )
                references.append(ref)
        return references

    def get_extraction_rules(self, flow_id: str) -> List[ExtractionRule]:
        """Get all extraction rules for a specific flow."""
        rules = []
        for correlation in self.correlations:
            if correlation.response_flow_id == flow_id:
                rule = ExtractionRule(
                    source_flow_id=flow_id,
                    source_jsonpath=correlation.response_jsonpath,
                    variable_name=correlation.variable_name
                )
                rules.append(rule)
        return rules

    def is_dependency(self, flow_a: str, flow_b: str) -> bool:
        """Check if flow_a is a dependency of flow_b."""
        return flow_a in self.get_dependencies(flow_b)

    def get_ordered_flow_ids(self) -> List[str]:
        """Get flow IDs in dependency order (topological sort)."""
        from collections import defaultdict, deque

        # Build dependency graph
        graph = defaultdict(list)
        in_degree = {fid: 0 for fid in self.flow_ids}

        for correlation in self.correlations:
            source = correlation.response_flow_id
            target = correlation.request_flow_id
            if source != target and target not in graph[source]:
                graph[source].append(target)
                in_degree[target] += 1

        # Topological sort using Kahn's algorithm
        queue = deque([fid for fid in self.flow_ids if in_degree[fid] == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)

            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Add any remaining nodes (in case of cycles)
        for fid in self.flow_ids:
            if fid not in result:
                result.append(fid)

        return result