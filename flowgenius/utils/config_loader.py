"""
Configuration loading utilities for YAML and JSON files.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml


def load_config(
    config_path: Union[str, Path],
    default: Optional[Dict[str, Any]] = None,
    encoding: str = 'utf-8'
) -> Dict[str, Any]:
    """
    Load configuration from YAML or JSON file.

    Args:
        config_path: Path to configuration file
        default: Default configuration to use if file doesn't exist
        encoding: File encoding

    Returns:
        Configuration dictionary

    Examples:
        >>> config = load_config("config.yaml")
        >>> config = load_config("config.json", default={"port": 8080})
    """
    config_path = Path(config_path)

    if not config_path.exists():
        if default is None:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        return default.copy()

    file_ext = config_path.suffix.lower()

    with open(config_path, 'r', encoding=encoding) as f:
        if file_ext in ('.yaml', '.yml'):
            try:
                return yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML file {config_path}: {e}")
        elif file_ext == '.json':
            try:
                return json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON file {config_path}: {e}")
        else:
            raise ValueError(f"Unsupported configuration file format: {file_ext}")


def save_config(
    config: Dict[str, Any],
    config_path: Union[str, Path],
    format: Optional[str] = None,
    encoding: str = 'utf-8',
    indent: int = 2
):
    """
    Save configuration to YAML or JSON file.

    Args:
        config: Configuration dictionary to save
        config_path: Path to save configuration
        format: Output format ("yaml", "json", or None for auto-detect from extension)
        encoding: File encoding
        indent: Indentation level for output

    Examples:
        >>> save_config({"port": 8080}, "config.yaml")
        >>> save_config({"port": 8080}, "config.json", format="json")
    """
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if format is None:
        file_ext = config_path.suffix.lower()
        format = 'yaml' if file_ext in ('.yaml', '.yml') else 'json'

    with open(config_path, 'w', encoding=encoding) as f:
        if format == 'yaml':
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=indent)
        else:  # json
            json.dump(config, f, indent=indent, ensure_ascii=False)


def load_configs(
    config_dir: Union[str, Path],
    pattern: str = "*.{yaml,yml,json}",
    merge: bool = True
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Load multiple configuration files from a directory.

    Args:
        config_dir: Directory containing configuration files
        pattern: Glob pattern for matching files
        merge: Whether to merge configs or return list

    Returns:
        Merged configuration dict or list of configs

    Examples:
        >>> configs = load_configs("./configs", "*.yaml")
        >>> configs = load_configs("./configs", "*.json", merge=False)
    """
    config_dir = Path(config_dir)
    if not config_dir.exists():
        if merge:
            return {}
        return []

    configs = []
    for config_file in config_dir.glob(pattern):
        try:
            config = load_config(config_file)
            configs.append(config)
        except Exception as e:
            print(f"Warning: Failed to load {config_file}: {e}")

    if not merge:
        return configs

    # Merge configs (later configs override earlier ones)
    merged = {}
    for config in configs:
        merged = deep_merge(merged, config)
    return merged


def deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.

    Args:
        base: Base dictionary
        update: Update dictionary (takes precedence)

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def get_nested_config(
    config: Dict[str, Any],
    key_path: str,
    default: Any = None,
    separator: str = "."
) -> Any:
    """
    Get a nested configuration value using dot notation.

    Args:
        config: Configuration dictionary
        key_path: Dot-separated path to the value (e.g., "server.port")
        default: Default value if key not found
        separator: Key path separator

    Returns:
        Configuration value or default

    Examples:
        >>> config = {"server": {"port": 8080, "host": "localhost"}}
        >>> get_nested_config(config, "server.port")
        8080
        >>> get_nested_config(config, "server.timeout", 30)
        30
    """
    keys = key_path.split(separator)
    value = config

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def set_nested_config(
    config: Dict[str, Any],
    key_path: str,
    value: Any,
    separator: str = "."
) -> Dict[str, Any]:
    """
    Set a nested configuration value using dot notation.

    Args:
        config: Configuration dictionary
        key_path: Dot-separated path to the value
        value: Value to set
        separator: Key path separator

    Returns:
        Updated configuration dictionary

    Examples:
        >>> config = {"server": {}}
        >>> set_nested_config(config, "server.port", 8080)
        {'server': {'port': 8080}}
    """
    keys = key_path.split(separator)
    current = config

    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        elif not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]

    current[keys[-1]] = value
    return config


class Config:
    """Configuration manager class."""

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Optional path to configuration file
        """
        self._config: Dict[str, Any] = {}
        self._config_path = None

        if config_path:
            self.load(config_path)

    def load(self, config_path: Union[str, Path]):
        """Load configuration from file."""
        self._config_path = Path(config_path)
        self._config = load_config(self._config_path)

    def save(self, config_path: Optional[Union[str, Path]] = None):
        """Save configuration to file."""
        path = config_path or self._config_path
        if path:
            save_config(self._config, path)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        return get_nested_config(self._config, key, default)

    def set(self, key: str, value: Any):
        """Set configuration value using dot notation."""
        set_nested_config(self._config, key, value)

    def update(self, config: Dict[str, Any]):
        """Update configuration with dictionary."""
        self._config = deep_merge(self._config, config)

    @property
    def raw(self) -> Dict[str, Any]:
        """Get raw configuration dictionary."""
        return self._config.copy()

    def __getitem__(self, key: str) -> Any:
        """Get configuration value using bracket notation."""
        return self.get(key)

    def __setitem__(self, key: str, value: Any):
        """Set configuration value using bracket notation."""
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        """Check if key exists in configuration."""
        return self.get(key) is not None

    def __repr__(self) -> str:
        """String representation of configuration."""
        return f"Config({self._config})"


class BusinessMapping:
    """Business logic mapping configuration loader."""

    def __init__(self, mapping_path: Optional[Union[str, Path]] = None):
        """
        Initialize business mapping loader.

        Args:
            mapping_path: Path to business mapping YAML file
        """
        self.mapping_path = mapping_path
        self.mappings: List[Dict[str, Any]] = []

        if mapping_path:
            self.load(mapping_path)

    def load(self, mapping_path: Union[str, Path]):
        """
        Load business mapping from YAML file.

        Expected format:
            mappings:
              - path: /api/login
                business_logic: "用户登录"
                expected_response:
                  code: 0
                  success: true
        """
        config = load_config(mapping_path)
        self.mappings = config.get("mappings", [])

    def get_business_logic(self, path: str) -> Optional[str]:
        """Get business logic description for a path."""
        for mapping in self.mappings:
            if mapping.get("path") == path:
                return mapping.get("business_logic")
        return None

    def get_expected_response(self, path: str) -> Optional[Dict[str, Any]]:
        """Get expected response for a path."""
        for mapping in self.mappings:
            if mapping.get("path") == path:
                return mapping.get("expected_response")
        return None

    def find_mapping(self, path: str) -> Optional[Dict[str, Any]]:
        """Find complete mapping for a path."""
        for mapping in self.mappings:
            if mapping.get("path") == path:
                return mapping.copy()
        return None

    def add_mapping(self, path: str, business_logic: str, expected_response: Optional[Dict[str, Any]] = None):
        """Add a new mapping."""
        mapping = {
            "path": path,
            "business_logic": business_logic
        }
        if expected_response:
            mapping["expected_response"] = expected_response
        self.mappings.append(mapping)

    def save(self, path: Optional[Union[str, Path]] = None):
        """Save mappings to file."""
        save_path = path or self.mapping_path
        if save_path:
            config = {"mappings": self.mappings}
            save_config(config, save_path)


def validate_config_structure(config: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """
    Validate configuration structure against a schema.

    Args:
        config: Configuration to validate
        schema: Schema definition (nested dict with 'type', 'required', 'default' keys)

    Returns:
        True if configuration is valid

    Examples:
        >>> schema = {
        ...     "port": {"type": int, "required": True, "default": 8080},
        ...     "host": {"type": str, "required": False, "default": "localhost"}
        ... }
        >>> validate_config_structure({"port": 8080}, schema)
        True
    """
    for key, definition in schema.items():
        required = definition.get("required", False)
        field_type = definition.get("type")
        default = definition.get("default")

        if required and key not in config:
            return False

        if key in config:
            if field_type and not isinstance(config[key], field_type):
                # Try to convert if possible
                try:
                    config[key] = field_type(config[key])
                except (ValueError, TypeError):
                    return False

        elif default is not None:
            config[key] = default

    return True