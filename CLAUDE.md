# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FlowGenius SmartAdapter is a traffic-driven automated API test script generation tool. It captures HTTP traffic (via MitmProxy or log parsing), analyzes request-response correlations, and generates Pytest test scripts with assertions.We need to make full use of large model capabilities.

## Common Commands

```bash
# Run tests with coverage
uv run pytest tests/unit/ -v --cov=flowgenius --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_correlator.py -v

# Run all tests
uv run pytest tests/ -v

# Format code
uv run black flowgenius/ tests/

# Lint code
uv run flake8 flowgenius/ tests/

# Type check
uv run mypy flowgenius/

# Start MitmProxy for traffic capture
uv run python scripts/start_proxy.py --web

# Process log files
uv run python scripts/process_logs.py --source /path/to/access.log --output-dir ./traffic

# Generate test scripts
uv run python scripts/generate_tests.py --traffic ./traffic.har --output-dir ./generated
```

## Architecture

### Four-Layer Pipeline

1. **Traffic Collection Layer** (`flowgenius/collectors/`)
   - `proxy_collector.py` - MitmProxy-based real-time capture
   - `log_collector.py` - Parse Nginx/Apache logs
   - Outputs: HAR files, `TrafficFlow` objects

2. **Parsing Layer** (`flowgenius/parsers/`)
   - `har_parser.py` - Parse HAR → `TrafficFlow` models
   - `swagger_parser.py` - Parse OpenAPI → `APIEndpoint` models
   - `log_parser.py` - Custom log format parsing

3. **Intelligence Layer** (`flowgenius/core/`)
   - `correlator.py` - Chain tracing: finds request dependencies (e.g., login response token → next request header)
   - `validator.py` - Generates 4 assertion types: health, contract, semantic, snapshot

4. **Generation Layer** (`flowgenius/generators/`)
   - `api_object.py` - Generates reusable API class (`class ApiLogin`)
   - `testcase.py` - Generates Pytest test methods
   - `datafile.py` - Generates YAML/JSON/CSV test data

### Data Flow

```
Traffic (HAR/Logs) → TrafficFlow → CorrelationAnalysis → AssertionSet → Generated Pytest
         ↓                                          ↑
    Swagger/OpenAPI (optional) ────────────────────┘
```

### Key Models

- `TrafficRequest/TrafficResponse/TrafficFlow` - HTTP transaction models
- `APIEndpoint` - Swagger endpoint definition
- `CorrelationRule` - Maps response fields → request parameters (JSONPath-based)
- `AssertionRule` - Single assertion with type, category, expected value

## Key Integration Points

- **MitmProxy addon**: `mitmproxy_addon/flow_capture.py` - Captures traffic, exports HAR on shutdown
- **Swagger integration**: `parsers/swagger_parser.py` matches URLs to parameterized paths (`/users/{id}`)
- **JSONPath extraction**: `utils/jsonpath.py` wraps `jsonpath-ng` for variable extraction

## Test Structure

- `tests/conftest.py` - Shared fixtures (sample_flow, sample_har_data, sample_swagger_data)
- `tests/unit/` - Unit tests per module
- `tests/integration/` - End-to-end workflow tests

## Dependencies

Managed via `pyproject.toml` and `requirements.txt`. Use `uv` for package management.

Core: `requests`, `jsonpath-ng`, `pyyaml`, `jsonschema`
Dev: `pytest`, `pytest-cov`, `allure-pytest`, `black`, `flake8`, `mypy`
Optional: `mitmproxy` (for proxy capture mode)

## Important Notes

- Python version: `>=3.10`
- Package discovery includes both `flowgenius` and `mitmproxy_addon` packages
- Generated tests use `requests` library (not httpx or aiohttp)
- Correlation engine uses topological sort for dependency ordering
