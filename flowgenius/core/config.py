from dataclasses import dataclass, field
from typing import Set, List

@dataclass
class ExclusionPolicy:
    """Policy for excluding values from correlation candidates."""
    min_string_length: int = 3
    min_integer_value: int = 100
    excluded_booleans: Set[str] = field(default_factory=lambda: {"true", "false", "yes", "no"})

@dataclass
class SemanticDictionary:
    """Dictionary of semantic keys for assertion generation."""
    semantic_keys: List[str] = field(default_factory=lambda: ["code", "status", "success", "error", "message", "result", "data"])
    snapshot_fields: List[str] = field(default_factory=lambda: ["code", "success", "status", "data"])
    success_status_values: Set[str] = field(default_factory=lambda: {"success", "ok", "completed"})

@dataclass
class RuleConfig:
    """Configuration for business logic rules and exclusions."""
    exclusion_policy: ExclusionPolicy = field(default_factory=ExclusionPolicy)
    semantic_dictionary: SemanticDictionary = field(default_factory=SemanticDictionary)

# Global default config instance
default_rule_config = RuleConfig()
