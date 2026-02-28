"""
Data models for FlowGenius.
"""
from .traffic import TrafficRequest, TrafficResponse, TrafficFlow
from .api import (
    ParameterDefinition,
    PropertyDefinition,
    ResponseDefinition,
    APIEndpoint,
    SwaggerDoc
)
from .correlation import (
    ExtractionRule,
    VariableReference,
    CorrelationRule,
    CorrelationChain
)
from .assertion import (
    AssertionType,
    AssertionCategory,
    AssertionRule,
    AssertionSet,
    Snapshot
)

__all__ = [
    # Traffic models
    'TrafficRequest',
    'TrafficResponse',
    'TrafficFlow',
    # API models
    'ParameterDefinition',
    'PropertyDefinition',
    'ResponseDefinition',
    'APIEndpoint',
    'SwaggerDoc',
    # Correlation models
    'ExtractionRule',
    'VariableReference',
    'CorrelationRule',
    'CorrelationChain',
    # Assertion models
    'AssertionType',
    'AssertionCategory',
    'AssertionRule',
    'AssertionSet',
    'Snapshot'
]