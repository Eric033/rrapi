"""
Prompt templates for LLM-based analysis and generation.

This module contains all prompt templates used for:
- Response structure analysis
- Assertion generation
- Code generation
- Correlation analysis
"""

from typing import Any, Dict, List, Optional


# =============================================================================
# Assertion Analysis Prompts
# =============================================================================

ANALYZE_RESPONSE_STRUCTURE_PROMPT = """你是一个 API 测试专家。分析以下 API 响应，生成智能断言建议。

API 端点: {method} {path}
业务描述: {business_logic}

响应数据:
```json
{response_json}
```

请分析并返回 JSON 格式结果:
{{
    "key_fields": [
        {{
            "path": "$.data.balance",
            "business_meaning": "用户余额",
            "assertion_type": "gt_zero|equals|not_null|type_check|range",
            "description": "用户余额应大于0",
            "expected_value": null,
            "boundary_suggestions": ["测试余额为0的情况", "测试余额为负数的情况"]
        }}
    ],
    "correlation_hints": [
        {{
            "field": "$.data.token",
            "likely_used_in": "后续请求的 Authorization 头",
            "extraction_suggestion": "Bearer token 提取"
        }}
    ],
    "response_pattern": {{
        "is_paginated": false,
        "has_error_handling": true,
        "error_field": "$.code",
        "success_indicator": "$.success"
    }}
}}
"""

GENERATE_ASSERTION_DESCRIPTION_PROMPT = """为以下 API 断言生成一个清晰、有业务含义的描述。

API 端点: {method} {path}
字段路径: {field_path}
字段值: {field_value}
断言类型: {assertion_type}
上下文信息: {context}

请返回一个简洁的中文描述（不超过50字），说明这个断言的业务含义。

示例:
- "登录成功后应返回有效的用户认证令牌"
- "用户余额查询结果应为非负数值"
- "订单创建成功后应返回有效的订单编号"
"""

ANALYZE_HISTORICAL_PATTERNS_PROMPT = """分析以下 API 响应的历史模式，识别一致性规则。

API 端点: {method} {path}
历史响应数据:
{historical_responses}

请返回 JSON 格式结果:
{{
    "consistent_fields": [
        {{
            "path": "$.code",
            "value": 0,
            "consistency_type": "always_equals",
            "description": "成功响应的代码始终为0"
        }}
    ],
    "variable_fields": [
        {{
            "path": "$.data.timestamp",
            "value_type": "timestamp",
            "value_range": "当前时间",
            "description": "响应时间戳，每次请求都会变化"
        }}
    ],
    "recommended_assertions": [
        {{
            "path": "$.code",
            "assertion_type": "equals",
            "expected_value": 0,
            "confidence": 1.0
        }}
    ]
}}
"""


# =============================================================================
# Code Generation Prompts
# =============================================================================

GENERATE_API_CLASS_PROMPT = """生成一个 Python API 对象类。

API 信息:
- 路径: {path}
- 方法: {method}
- 请求参数: {params}
- 响应结构: {response_schema}
- 业务描述: {business_logic}

要求:
1. 使用 requests 库
2. 添加完整的类型注解（Python 3.10+ 语法）
3. 添加中文文档字符串
4. 遵循 PEP 8 规范
5. 支持超时和重试配置
6. 包含错误处理

请返回完整的 Python 类代码，包含所有必要的导入语句。

示例输出格式:
```python
from typing import Any, Dict, Optional
import requests

class ApiUser:
    \"\"\"用户相关 API 封装。\"\"\"

    def __init__(self, base_url: str, timeout: int = 30) -> None:
        ...

    def get_user_info(self, user_id: int) -> requests.Response:
        \"\"\"获取用户信息。

        Args:
            user_id: 用户ID

        Returns:
            Response 对象
        \"\"\"
        ...
```
"""

GENERATE_TEST_CASE_PROMPT = """生成一个 Pytest 测试用例。

测试信息:
- API 路径: {path}
- 请求方法: {method}
- 请求参数: {request_params}
- 断言规则: {assertions}
- 关联变量: {correlation_vars}
- 业务描述: {business_logic}

要求:
1. 使用 Pytest 框架
2. 使用 fixture 管理测试资源
3. 添加中文文档字符串说明测试目的
4. 包含清晰的断言和错误信息
5. 支持数据驱动测试
6. 处理关联变量提取和使用

请返回完整的测试方法代码。
"""

GENERATE_DOCSTRING_PROMPT = """为以下 API 方法生成文档字符串。

API 信息:
- 路径: {path}
- 方法: {method}
- 参数说明: {params}
- 返回值结构: {response_summary}
- 业务描述: {business_logic}

请生成符合 Google 风格的中文文档字符串，包含:
1. 方法概述
2. Args 部分（参数说明）
3. Returns 部分（返回值说明）
4. Raises 部分（可能的异常）
5. Examples 部分（使用示例）
"""


# =============================================================================
# Correlation Analysis Prompts
# =============================================================================

EXPLAIN_CORRELATION_PROMPT = """分析两个 API 请求之间的关联关系。

源请求: {source_url}
响应字段: {source_field}
响应值: {source_value}
目标请求: {target_url}
使用位置: {target_location}
使用值: {target_value}

请返回 JSON 格式结果:
{{
    "correlation_type": "authentication|data_reference|session|pagination|chaining",
    "variable_name": "建议的变量名（英文，snake_case）",
    "variable_name_cn": "变量中文名",
    "explanation": "关联原因的详细说明",
    "extraction_method": "jsonpath|regex|header",
    "extraction_expression": "$.data.token",
    "usage_template": "Bearer {{{{variable_name}}}}",
    "confidence": 0.95
}}
"""

DETECT_FLOW_PATTERN_PROMPT = """分析以下 API 请求序列，识别业务流程。

请求序列:
{flow_sequence}

请返回 JSON 格式结果:
{{
    "flow_name": "流程名称（中文）",
    "flow_description": "流程描述",
    "steps": [
        {{
            "order": 1,
            "api": "/api/login",
            "method": "POST",
            "action": "用户登录",
            "purpose": "获取认证token",
            "extracts": ["token"],
            "is_required": true
        }}
    ],
    "variables": [
        {{
            "name": "auth_token",
            "source_step": 1,
            "source_path": "$.data.token",
            "used_in_steps": [2, 3, 4]
        }}
    ],
    "error_handling": {{
        "retry_steps": [1],
        "fallback_flow": null
    }}
}}
"""

SUGGEST_VARIABLE_NAME_PROMPT = """为以下 API 响应字段建议一个语义化的变量名。

字段路径: {field_path}
字段值: {field_value}
API 端点: {api_endpoint}
上下文: {context}

请返回 JSON 格式结果:
{{
    "variable_name": "auth_token",
    "variable_name_cn": "认证令牌",
    "description": "用于后续请求的身份验证",
    "naming_rationale": "基于该字段在登录响应中返回，用于认证"
}}
"""


# =============================================================================
# Utility Functions
# =============================================================================

def format_prompt(template: str, **kwargs) -> str:
    """Format a prompt template with the given parameters.

    Args:
        template: Prompt template string
        **kwargs: Template parameters

    Returns:
        Formatted prompt string
    """
    return template.format(**kwargs)


def truncate_json_for_prompt(data: Any, max_length: int = 2000) -> str:
    """Truncate JSON data for inclusion in prompts.

    Args:
        data: JSON-serializable data
        max_length: Maximum string length

    Returns:
        Truncated JSON string
    """
    import json

    json_str = json.dumps(data, ensure_ascii=False, indent=2)

    if len(json_str) <= max_length:
        return json_str

    # Truncate and add ellipsis
    return json_str[:max_length] + "\n... (truncated)"


def build_flow_sequence_description(flows: List[Dict[str, Any]]) -> str:
    """Build a description of a flow sequence for analysis.

    Args:
        flows: List of flow information dictionaries

    Returns:
        Formatted flow sequence description
    """
    lines = []

    for i, flow in enumerate(flows, 1):
        lines.append(f"{i}. {flow.get('method', 'GET')} {flow.get('path', '/')}")
        if flow.get('description'):
            lines.append(f"   描述: {flow['description']}")
        if flow.get('params'):
            lines.append(f"   参数: {flow['params']}")

    return "\n".join(lines)


class PromptBuilder:
    """Builder class for constructing LLM prompts."""

    def __init__(self):
        """Initialize the prompt builder."""
        self._context: Dict[str, Any] = {}

    def set_api_info(
        self,
        method: str,
        path: str,
        business_logic: Optional[str] = None
    ) -> "PromptBuilder":
        """Set API information.

        Args:
            method: HTTP method
            path: API path
            business_logic: Business logic description

        Returns:
            self for chaining
        """
        self._context["method"] = method
        self._context["path"] = path
        if business_logic:
            self._context["business_logic"] = business_logic
        return self

    def set_response_data(self, response_data: Dict[str, Any]) -> "PromptBuilder":
        """Set response data.

        Args:
            response_data: Response data dictionary

        Returns:
            self for chaining
        """
        self._context["response_json"] = truncate_json_for_prompt(response_data)
        return self

    def set_field_info(
        self,
        field_path: str,
        field_value: Any,
        assertion_type: Optional[str] = None
    ) -> "PromptBuilder":
        """Set field information.

        Args:
            field_path: JSONPath to the field
            field_value: Value of the field
            assertion_type: Type of assertion

        Returns:
            self for chaining
        """
        self._context["field_path"] = field_path
        self._context["field_value"] = str(field_value)
        if assertion_type:
            self._context["assertion_type"] = assertion_type
        return self

    def set_flow_info(
        self,
        source_url: str,
        source_field: str,
        target_url: str,
        target_location: str
    ) -> "PromptBuilder":
        """Set flow correlation information.

        Args:
            source_url: Source request URL
            source_field: Source field path
            target_url: Target request URL
            target_location: Target location

        Returns:
            self for chaining
        """
        self._context["source_url"] = source_url
        self._context["source_field"] = source_field
        self._context["target_url"] = target_url
        self._context["target_location"] = target_location
        return self

    def build(self, template: str) -> str:
        """Build the prompt from the template.

        Args:
            template: Prompt template string

        Returns:
            Formatted prompt string
        """
        return template.format(**self._context)