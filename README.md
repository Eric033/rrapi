# FlowGenius SmartAdapter

A traffic-driven automated API test script generation tool that solves the problem of missing or outdated API documentation. By leveraging multi-dimensional traffic analysis and an intelligent rule engine, it generates high-availability Pytest test scripts with a single click.

## Features

### Dual-Mode Traffic Collection
- **Proxy Mode**: Capture HTTP/HTTPS traffic in real-time using MitmProxy
- **Log Mode**: Extract traffic from Nginx, Apache, or custom application logs

### Intelligent Analysis
- Automatic request-response correlation analysis
- Variable extraction for dependent requests (tokens, IDs, etc.)
- JSONPath and regex-based pattern matching

### Smart Assertion Generation
- Health assertions (status code, response time)
- Contract assertions (Swagger/OpenAPI schema validation)
- Semantic assertions (business logic validation)
- Snapshot comparison for regression testing

### Test Generation
- Pytest-compatible test scripts
- API object layer for reusable code
- Data-driven testing support (YAML, JSON, CSV, Excel)
- Allure report integration

## Installation

```bash
# Clone the repository
git clone https://github.com/example/flowgenius-smartadapter.git
cd flowgenius-smartadapter

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

## Quick Start

### 1. Capture Traffic

**Using MitmProxy (Proxy Mode):**
```bash
python scripts/start_proxy.py --web
```

Then navigate through your application to capture traffic. Press Ctrl+C to stop capturing.

**Using Log Files (Log Mode):**
```bash
python scripts/process_logs.py --source /path/to/access.log --output-dir ./traffic
```

### 2. Generate Tests

```bash
python scripts/generate_tests.py \
    --traffic ./traffic/traffic.har \
    --swagger https://api.example.com/swagger.json \
    --output-dir ./generated_tests
```

### 3. Run Tests

```bash
cd generated_tests
pip install -r requirements.txt
pytest

# With coverage
pytest --cov=api --cov-report=html

# With Allure report
pytest --alluredir=allure-results
allure serve allure-results
```

## Project Structure

```
flowgenius/
├── flowgenius/                    # Main package
│   ├── core/                      # Core modules
│   │   ├── collector.py           # Traffic collection orchestration
│   │   ├── parser.py              # Traffic parsing orchestration
│   │   ├── correlator.py          # Correlation analysis engine
│   │   ├── validator.py           # Assertion generation engine
│   │   └── generator.py           # Script generation orchestration
│   ├── collectors/                # Traffic collectors
│   │   ├── proxy_collector.py     # MitmProxy-based collector
│   │   └── log_collector.py       # Log-based collector
│   ├── parsers/                   # Parsers for different formats
│   │   ├── har_parser.py          # HAR format parser
│   │   ├── swagger_parser.py      # Swagger/OpenAPI parser
│   │   └── log_parser.py          # Custom log parser
│   ├── generators/                # Code generators
│   │   ├── api_object.py          # API object layer generation
│   │   ├── testcase.py            # Pytest test case generation
│   │   ├── datafile.py            # Data file generation
│   │   └── config.py              # Configuration file generation
│   ├── models/                    # Data models
│   │   ├── traffic.py             # Traffic models
│   │   ├── api.py                 # API definition models
│   │   ├── correlation.py         # Correlation models
│   │   └── assertion.py           # Assertion models
│   └── utils/                     # Utilities
│       ├── jsonpath.py            # JSONPath utilities
│       ├── regex_utils.py         # Regex utilities
│       ├── logger.py              # Logging setup
│       └── config_loader.py       # Configuration loader
├── mitmproxy_addon/               # MitmProxy addon
│   └── flow_capture.py            # Traffic capture addon
├── scripts/                       # CLI tools
│   ├── start_proxy.py             # Start MitmProxy
│   ├── process_logs.py            # Process log files
│   └── generate_tests.py          # Main generation script
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests
│   ├── integration/               # Integration tests
│   └── fixtures/                  # Test fixtures
├── examples/                      # Example usage
│   ├── configs/                   # Example configurations
│   ├── logs/                      # Example log files
│   └── generated/                 # Example generated tests
└── docs/                          # Documentation
```

## Configuration

### Business Logic Mapping

Map API endpoints to business logic descriptions:

```yaml
# examples/configs/business_mapping.yaml
mappings:
  - path: /api/login
    business_logic: "用户登录"
    expected_response:
      code: 0
      success: true
  - path: /api/pay
    business_logic: "支付成功"
    expected_response:
      code: 0
      status: "success"
```

Use with the `--business-mapping` option:
```bash
python scripts/generate_tests.py \
    --traffic traffic.har \
    --business-mapping examples/configs/business_mapping.yaml \
    --output-dir ./generated
```

## CLI Reference

### start_proxy.py

Start MitmProxy for traffic capture.

```bash
python scripts/start_proxy.py [OPTIONS]

Options:
  --port PORT        Proxy port [default: 8080]
  --output-dir DIR   Output directory for HAR files [default: .]
  --web              Start web UI (mitmweb)
  --no-filter        Don't filter static resources
  --max N            Maximum number of flows to capture
```

### process_logs.py

Process log files to extract traffic.

```bash
python scripts/process_logs.py --source SOURCE [OPTIONS]

Options:
  --source SOURCE     Log file or directory to process
  --output-dir DIR    Output directory for HAR files [default: .]
  --format FORMAT     Log format: nginx_combined, nginx_access, apache_common, custom
  --pattern PATTERN   Custom regex pattern (use with --format custom)
  --max-lines N       Maximum number of lines to parse
  --no-filter         Don't filter static resources
```

### generate_tests.py

Generate Pytest test scripts.

```bash
python scripts/generate_tests.py --traffic SOURCE [OPTIONS]

Options:
  --traffic SOURCE       Traffic source: HAR file, log file, or directory
  --swagger SOURCE        Swagger/OpenAPI specification (file path or URL)
  --output-dir DIR        Output directory for generated tests
  --base-url URL         Base URL for API
  --business-mapping FILE Business mapping configuration file (YAML)
  --data-formats FORMAT  Data file formats: yaml, json, csv, excel, all
  --no-swagger           Generate without Swagger integration
  --snapshot-dir DIR     Directory for snapshot comparison data
```

## Generated Project Structure

```bash
generated/
├── api/                 # API object layer
│   ├── __init__.py
│   └── api_objects.py   # Reusable API classes
├── testcase/            # Pytest test cases
│   ├── conftest.py      # Pytest configuration
│   └── test_api.py      # Generated test cases
├── datas/               # Test data files
│   ├── test_data.yaml
│   └── test_data.json
├── config.py            # Configuration
├── pytest.ini           # Pytest configuration
├── setup.cfg            # Setup configuration
└── README.md            # Generated README
```

## Testing

### Run Unit Tests
```bash
pytest tests/unit/ -v
```

### Run Integration Tests
```bash
pytest tests/integration/ -v
```

### Run All Tests with Coverage
```bash
pytest --cov=flowgenius --cov-report=html
```

## Development

### Code Style
```bash
# Format code with Black
black flowgenius/ tests/

# Lint with flake8
flake8 flowgenius/ tests/

# Type check with mypy
mypy flowgenius/
```

## Documentation

- [User Guide](docs/user_guide.md) - Comprehensive user documentation
- [API Reference](docs/api_reference.md) - API documentation
- [Architecture](docs/architecture.md) - Architecture and design

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with [MitmProxy](https://mitmproxy.org/)
- Uses [Pytest](https://pytest.org/) for test framework
- Supports [Swagger/OpenAPI](https://swagger.io/) specifications

## Support

For issues, questions, or contributions, please visit our [GitHub repository](https://github.com/example/flowgenius-smartadapter).