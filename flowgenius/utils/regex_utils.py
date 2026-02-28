"""
Regular expression utilities for log parsing and pattern matching.
"""
import re
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple, Union


# Common log format patterns
NGINX_COMBINED_PATTERN = r'(?P<remote_addr>\S+) - (?P<remote_user>\S+) \[(?P<time_local>[^\]]+)\] "(?P<request_method>\w+) (?P<request_uri>\S+) (?P<http_version>\S+)" (?P<status>\d+) (?P<body_bytes_sent>\d+) "(?P<http_referer>[^"]*)" "(?P<http_user_agent>[^"]*)"'
NGINX_ACCESS_PATTERN = r'(?P<remote_addr>\S+) - (?P<remote_user>\S+) \[(?P<time_local>[^\]]+)\] "(?P<request_method>\w+) (?P<request_uri>\S+) (?P<http_version>\S+)" (?P<status>\d+)'
APACHE_COMMON_PATTERN = r'(?P<remote_addr>\S+) (?P<remote_logname>\S+) (?P<remote_user>\S+) \[(?P<time_local>[^\]]+)\] "(?P<request_method>\w+) (?P<request_uri>\S+) (?P<http_version>\S+)" (?P<status>\d+) (?P<body_bytes_sent>\d+)'

# JSON extraction patterns
JSON_VALUE_PATTERN = r'(?P<key>"[^"]+"\s*:\s*)(?P<value>"[^"]*"|\d+\.?\d*|true|false|null)'
JSON_ARRAY_PATTERN = r'\[(.*?)\]'
JSON_OBJECT_PATTERN = r'\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'

# Common field patterns
TOKEN_PATTERN = r'(token|Token|TOKEN|access_token|auth_token)[:=]\s*["\']?([a-zA-Z0-9\-_\.]+)["\']?'
ID_PATTERN = r'(?:id|Id|ID)[:=]\s*["\']?(\d+)["\']?'
UUID_PATTERN = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def compile_pattern(pattern: Union[str, Pattern]) -> Pattern:
    """
    Compile a regex pattern, handling both string and compiled patterns.

    Args:
        pattern: The pattern to compile (string or compiled regex)

    Returns:
        Compiled regex pattern
    """
    if isinstance(pattern, Pattern):
        return pattern
    return re.compile(pattern)


def extract_match(pattern: Union[str, Pattern], text: str, group: Optional[Union[str, int]] = 0, default: Any = None) -> Any:
    """
    Extract a match from text using regex pattern.

    Args:
        pattern: The regex pattern to use
        text: The text to search in
        group: The group number or name to extract (default: 0 for full match)
        default: Default value if no match found

    Returns:
        The matched value or default
    """
    compiled = compile_pattern(pattern)
    match = compiled.search(text)

    if match:
        if isinstance(group, str):
            return match.groupdict().get(group, default)
        return match.group(group) if group < len(match.groups()) + 1 else default

    return default


def extract_all_matches(pattern: Union[str, Pattern], text: str, group: Union[str, int] = 0) -> List[Any]:
    """
    Extract all matches from text using regex pattern.

    Args:
        pattern: The regex pattern to use
        text: The text to search in
        group: The group number or name to extract

    Returns:
        List of matched values
    """
    compiled = compile_pattern(pattern)
    matches = compiled.findall(text)

    if isinstance(group, str) and matches:
        # For named groups, return the dict values
        result = []
        for match in matches:
            if isinstance(match, dict):
                result.append(match.get(group))
            elif isinstance(match, tuple):
                # Find the named group in pattern
                named_groups = compiled.groupindex
                if group in named_groups:
                    idx = named_groups[group]
                    result.append(match[idx - 1])
            else:
                result.append(match)
        return result

    return matches if matches else []


def extract_named_groups(pattern: Union[str, Pattern], text: str) -> Dict[str, str]:
    """
    Extract all named groups from text using regex pattern.

    Args:
        pattern: The regex pattern with named groups
        text: The text to search in

    Returns:
        Dictionary of group name -> value
    """
    compiled = compile_pattern(pattern)
    match = compiled.search(text)

    if match:
        return match.groupdict()

    return {}


def parse_log_line(log_format: str, log_line: str) -> Dict[str, str]:
    """
    Parse a log line using the specified format.

    Args:
        log_format: Regex pattern for log format (e.g., NGINX_ACCESS_PATTERN)
        log_line: The log line to parse

    Returns:
        Dictionary of parsed fields

    Examples:
        >>> log = '192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/users HTTP/1.1" 200'
        >>> parse_log_line(NGINX_ACCESS_PATTERN, log)
        {'remote_addr': '192.168.1.1', 'request_method': 'GET', ...}
    """
    return extract_named_groups(log_format, log_line)


def extract_json_values(text: str, key: str) -> List[str]:
    """
    Extract JSON values for a specific key from text.

    Args:
        text: The text to search in (may contain JSON)
        key: The JSON key to extract values for

    Returns:
        List of extracted values
    """
    pattern = rf'"{re.escape(key)}"\s*:\s*("[^"]*"|\d+\.?\d*|true|false|null)'
    matches = extract_all_matches(pattern, text, group=1)

    # Clean up quotes from string values
    cleaned = []
    for m in matches:
        if isinstance(m, str) and m.startswith('"') and m.endswith('"'):
            cleaned.append(m[1:-1])
        else:
            cleaned.append(m)

    return cleaned


def extract_tokens(text: str) -> List[str]:
    """
    Extract token-like strings from text.

    Args:
        text: The text to search in

    Returns:
        List of found tokens
    """
    tokens = []

    # Try explicit token patterns
    explicit_tokens = extract_all_matches(TOKEN_PATTERN, text, group=2)
    tokens.extend(explicit_tokens)

    # Try UUID pattern
    uuids = extract_all_matches(UUID_PATTERN, text)
    tokens.extend(uuids)

    # Try to find long alphanumeric strings (potential tokens)
    # Pattern: 20+ alphanumeric characters with possible dashes and underscores
    long_strings = extract_all_matches(r'\b[a-zA-Z0-9_\-\.]{20,}\b', text)
    tokens.extend(long_strings)

    return list(set(tokens))  # Remove duplicates


def extract_ids(text: str) -> List[int]:
    """
    Extract ID-like integers from text.

    Args:
        text: The text to search in

    Returns:
        List of found IDs
    """
    ids = extract_all_matches(ID_PATTERN, text, group=1)
    return [int(i) for i in ids if i.isdigit()]


def find_pattern_in_text(pattern: Union[str, Pattern], text: str, find_all: bool = False) -> Union[Optional[re.Match], List[re.Match]]:
    """
    Find pattern(s) in text.

    Args:
        pattern: The regex pattern to search for
        text: The text to search in
        find_all: Whether to find all matches or just the first

    Returns:
        Match object or list of match objects
    """
    compiled = compile_pattern(pattern)

    if find_all:
        return list(compiled.finditer(text))
    return compiled.search(text)


def replace_pattern(pattern: Union[str, Pattern], text: str, replacement: Union[str, Callable], count: int = 0) -> str:
    """
    Replace pattern matches in text.

    Args:
        pattern: The regex pattern to search for
        text: The text to search in
        replacement: Replacement string or callable
        count: Maximum number of replacements (0 = all)

    Returns:
        Modified text
    """
    compiled = compile_pattern(pattern)
    return compiled.sub(replacement, text, count=count)


def normalize_url(url: str) -> str:
    """
    Normalize a URL by removing query parameters and fragments.

    Args:
        url: The URL to normalize

    Returns:
        Normalized URL
    """
    # Remove query string
    url = url.split('?')[0]
    # Remove fragment
    url = url.split('#')[0]
    return url


def extract_query_params(url: str) -> Dict[str, str]:
    """
    Extract query parameters from a URL.

    Args:
        url: The URL with query parameters

    Returns:
        Dictionary of query parameters
    """
    params = {}
    if '?' in url:
        query_string = url.split('?')[1]
        query_string = query_string.split('#')[0]  # Remove fragment

        for param in query_string.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                params[key] = value

    return params


def validate_pattern(pattern: str) -> bool:
    """
    Validate if a regex pattern is syntactically correct.

    Args:
        pattern: The regex pattern to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        re.compile(pattern)
        return True
    except re.error:
        return False


def build_log_pattern(fields: List[str], separator: str = r'\s+') -> str:
    """
    Build a log parsing pattern from field specifications.

    Args:
        fields: List of field names (e.g., ["timestamp", "ip", "method"])
        separator: Regex pattern for field separator

    Returns:
        Compiled regex pattern string with named groups
    """
    groups = []
    for field in fields:
        # Escape special regex characters in field names
        escaped_field = field.replace('.', r'\.')
        groups.append(f'(?P<{escaped_field}>\\S+)')

    return separator.join(groups)