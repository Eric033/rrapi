"""
JSONPath extraction utilities using jsonpath-ng.
"""
from typing import Any, List, Optional, Union
from jsonpath_ng import parse
from jsonpath_ng.ext import parse as parse_ext


def extract_jsonpath(data: Any, jsonpath: str, default: Any = None, use_ext: bool = False) -> Any:
    """
    Extract a value from data using JSONPath expression.

    Args:
        data: The data to extract from (dict, list, or complex structure)
        jsonpath: The JSONPath expression (e.g., "$.data.token", "$.users[*].id")
        default: Default value to return if extraction fails
        use_ext: Whether to use extended JSONPath parser (supports more features)

    Returns:
        The extracted value, or default if extraction fails

    Examples:
        >>> data = {"data": {"token": "abc123", "user": {"id": 1}}}
        >>> extract_jsonpath(data, "$.data.token")
        'abc123'
        >>> extract_jsonpath(data, "$.data.user.id")
        1
    """
    try:
        if use_ext:
            jsonpath_expr = parse_ext(jsonpath)
        else:
            jsonpath_expr = parse(jsonpath)

        matches = list(jsonpath_expr.find(data))

        if not matches:
            return default

        # If multiple matches, return list of values
        if len(matches) > 1:
            return [match.value for match in matches]

        # Single match, return the value
        return matches[0].value

    except Exception:
        return default


def extract_jsonpath_list(data: Any, jsonpath: str, use_ext: bool = False) -> List[Any]:
    """
    Extract all matching values as a list using JSONPath expression.

    Args:
        data: The data to extract from
        jsonpath: The JSONPath expression
        use_ext: Whether to use extended JSONPath parser

    Returns:
        List of extracted values, empty list if no matches

    Examples:
        >>> data = {"users": [{"id": 1}, {"id": 2}]}
        >>> extract_jsonpath_list(data, "$.users[*].id")
        [1, 2]
    """
    try:
        if use_ext:
            jsonpath_expr = parse_ext(jsonpath)
        else:
            jsonpath_expr = parse(jsonpath)

        matches = jsonpath_expr.find(data)
        return [match.value for match in matches]

    except Exception:
        return []


def extract_all_paths(data: Any, prefix: str = "$") -> List[str]:
    """
    Extract all possible JSONPath expressions from a data structure.

    Args:
        data: The data to analyze
        prefix: The prefix for generated paths

    Returns:
        List of all possible JSONPath expressions
    """
    paths = []

    def _extract(obj, current_path):
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{current_path}.{key}"
                paths.append(new_path)
                if isinstance(value, (dict, list)):
                    _extract(value, new_path)
        elif isinstance(obj, list) and obj:
            # Only recurse into non-empty lists
            first_item = obj[0]
            if isinstance(first_item, (dict, list)):
                for idx, item in enumerate(obj):
                    new_path = f"{current_path}[{idx}]"
                    if isinstance(item, (dict, list)):
                        _extract(item, new_path)

    try:
        _extract(data, prefix)
    except Exception:
        pass

    return paths


def find_common_paths(data1: Any, data2: Any) -> List[str]:
    """
    Find common JSONPath expressions between two data structures.

    Args:
        data1: First data structure
        data2: Second data structure

    Returns:
        List of common JSONPath expressions
    """
    paths1 = set(extract_all_paths(data1))
    paths2 = set(extract_all_paths(data2))
    return list(paths1 & paths2)


def get_jsonpath_value_type(data: Any, jsonpath: str) -> Optional[str]:
    """
    Get the type of value at a JSONPath expression.

    Args:
        data: The data to analyze
        jsonpath: The JSONPath expression

    Returns:
        The type name as string, or None if path doesn't exist
    """
    value = extract_jsonpath(data, jsonpath)
    if value is None:
        return None

    if isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "number"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    else:
        return type(value).__name__


def matches_jsonpath_type(data: Any, jsonpath: str, expected_type: str) -> bool:
    """
    Check if the value at a JSONPath matches the expected type.

    Args:
        data: The data to check
        jsonpath: The JSONPath expression
        expected_type: Expected type name ("string", "integer", "number", "boolean", "array", "object")

    Returns:
        True if type matches, False otherwise
    """
    actual_type = get_jsonpath_value_type(data, jsonpath)
    return actual_type == expected_type


def validate_jsonpath_expression(jsonpath: str) -> bool:
    """
    Validate if a JSONPath expression is syntactically correct.

    Args:
        jsonpath: The JSONPath expression to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        parse(jsonpath)
        return True
    except Exception:
        try:
            parse_ext(jsonpath)
            return True
        except Exception:
            return False