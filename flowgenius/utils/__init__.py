"""
Utility modules for FlowGenius.
"""
from .jsonpath import (
    extract_jsonpath,
    extract_jsonpath_list,
    extract_all_paths,
    find_common_paths,
    get_jsonpath_value_type,
    matches_jsonpath_type,
    validate_jsonpath_expression
)
from .regex_utils import (
    compile_pattern,
    extract_match,
    extract_all_matches,
    extract_named_groups,
    parse_log_line,
    extract_json_values,
    extract_tokens,
    extract_ids,
    find_pattern_in_text,
    replace_pattern,
    normalize_url,
    extract_query_params,
    validate_pattern,
    build_log_pattern,
    NGINX_COMBINED_PATTERN,
    NGINX_ACCESS_PATTERN,
    APACHE_COMMON_PATTERN,
    TOKEN_PATTERN,
    ID_PATTERN,
    UUID_PATTERN
)
from .logger import (
    setup_logger,
    get_logger,
    TrafficLogger,
    ColoredFormatter,
    log_function_call,
    TrafficCapture
)
from .config_loader import (
    load_config,
    save_config,
    load_configs,
    deep_merge,
    get_nested_config,
    set_nested_config,
    Config,
    BusinessMapping,
    validate_config_structure
)

__all__ = [
    # JSONPath utilities
    'extract_jsonpath',
    'extract_jsonpath_list',
    'extract_all_paths',
    'find_common_paths',
    'get_jsonpath_value_type',
    'matches_jsonpath_type',
    'validate_jsonpath_expression',
    # Regex utilities
    'compile_pattern',
    'extract_match',
    'extract_all_matches',
    'extract_named_groups',
    'parse_log_line',
    'extract_json_values',
    'extract_tokens',
    'extract_ids',
    'find_pattern_in_text',
    'replace_pattern',
    'normalize_url',
    'extract_query_params',
    'validate_pattern',
    'build_log_pattern',
    'NGINX_COMBINED_PATTERN',
    'NGINX_ACCESS_PATTERN',
    'APACHE_COMMON_PATTERN',
    'TOKEN_PATTERN',
    'ID_PATTERN',
    'UUID_PATTERN',
    # Logger utilities
    'setup_logger',
    'get_logger',
    'TrafficLogger',
    'ColoredFormatter',
    'log_function_call',
    'TrafficCapture',
    # Config utilities
    'load_config',
    'save_config',
    'load_configs',
    'deep_merge',
    'get_nested_config',
    'set_nested_config',
    'Config',
    'BusinessMapping',
    'validate_config_structure'
]