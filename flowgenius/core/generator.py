"""
Core script generation orchestration with LLM enhancement support.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from flowgenius.generators.api_object import APIObjectGenerator
from flowgenius.generators.testcase import TestCaseGenerator
from flowgenius.generators.datafile import DataFileGenerator
from flowgenius.generators.config import ConfigGenerator
from flowgenius.models.api import SwaggerDoc
from flowgenius.models.assertion import AssertionSet
from flowgenius.models.correlation import CorrelationChain
from flowgenius.models.traffic import TrafficFlow
from flowgenius.utils.logger import get_logger

if TYPE_CHECKING:
    from flowgenius.llm.base import LLMProvider
    from flowgenius.llm.code_generator import LLMCodeGenerator


class GeneratorOrchestrator:
    """Orchestrates the generation of test scripts and supporting files.

    Supports optional LLM enhancement for more semantic code generation.
    """

    def __init__(
        self,
        base_url: str = "https://api.example.com",
        llm_provider: Optional["LLMProvider"] = None,
        enable_llm: bool = True
    ):
        """
        Initialize generator orchestrator.

        Args:
            base_url: Base URL for API
            llm_provider: Optional LLM provider for enhanced code generation
            enable_llm: Whether to use LLM enhancement if provider is available
        """
        self.base_url = base_url
        self.api_object_generator = APIObjectGenerator()
        self.test_case_generator = TestCaseGenerator()
        self.data_file_generator = DataFileGenerator()
        self.config_generator = ConfigGenerator()
        self.logger = get_logger("flowgenius.generator")
        self.llm_provider = llm_provider
        self.enable_llm = enable_llm and llm_provider is not None
        self._llm_code_generator: Optional["LLMCodeGenerator"] = None

        if self.enable_llm:
            try:
                from flowgenius.llm.code_generator import LLMCodeGenerator
                self._llm_code_generator = LLMCodeGenerator(llm_provider)
                self.logger.info("LLM-enhanced code generation enabled")
            except ImportError:
                self.logger.warning("LLM module not available, falling back to rule-based generation")
                self.enable_llm = False

    def generate_full_project(
        self,
        flows: List[TrafficFlow],
        assertion_sets: Dict[str, AssertionSet],
        output_dir: str,
        swagger_doc: Optional[SwaggerDoc] = None,
        chain: Optional[CorrelationChain] = None,
        business_mappings: Optional[Dict[str, str]] = None,
        data_formats: List[str] = ["yaml", "json"]
    ) -> Dict[str, str]:
        """
        Generate a complete test project.

        Args:
            flows: List of TrafficFlow objects
            assertion_sets: Dictionary mapping flow IDs to AssertionSets
            output_dir: Output directory for generated files
            swagger_doc: Optional SwaggerDoc for API object generation
            chain: Optional CorrelationChain for variable handling
            business_mappings: Optional business logic mappings
            data_formats: Data file formats to generate

        Returns:
            Dictionary mapping file types to generated file paths
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results = {}

        # Create directory structure
        api_dir = output_path / "api"
        api_dir.mkdir(exist_ok=True)
        api_dir.joinpath("__init__.py").write_text("", encoding='utf-8')

        testcase_dir = output_path / "testcase"
        testcase_dir.mkdir(exist_ok=True)
        testcase_dir.joinpath("__init__.py").write_text("", encoding='utf-8')

        datas_dir = output_path / "datas"
        datas_dir.mkdir(exist_ok=True)

        # Generate API object layer
        api_module = self.api_object_generator.generate_module(flows, self.base_url)
        api_file = api_dir / "api_objects.py"
        api_file.write_text(api_module, encoding='utf-8')
        results["api_layer"] = str(api_file)
        self.logger.info(f"Generated API object layer: {api_file}")

        # Generate test cases
        api_mappings = self._build_api_mappings(flows, swagger_doc)
        test_module = self.test_case_generator.generate_test_module(
            flows, assertion_sets, grouped_by_endpoint=True
        )
        test_file = testcase_dir / "test_api.py"
        test_file.write_text(test_module, encoding='utf-8')
        results["test_cases"] = str(test_file)
        self.logger.info(f"Generated test cases: {test_file}")

        # Generate conftest.py
        conftest = self.test_case_generator.generate_conftest(self.base_url)
        conftest_file = testcase_dir / "conftest.py"
        conftest_file.write_text(conftest, encoding='utf-8')
        results["conftest"] = str(conftest_file)
        self.logger.info(f"Generated conftest.py: {conftest_file}")

        # Generate data files
        for fmt in data_formats:
            if fmt == "yaml":
                yaml_file = self.data_file_generator.generate_yaml(
                    flows, str(datas_dir / "test_data.yaml")
                )
                results["data_yaml"] = yaml_file
            elif fmt == "json":
                json_file = self.data_file_generator.generate_json(
                    flows, str(datas_dir / "test_data.json")
                )
                results["data_json"] = json_file

        # Generate configuration files
        config_files = self.config_generator.generate_all(
            str(output_path), self.base_url, "flowgenius_tests"
        )
        results.update(config_files)

        # Generate README
        readme = self._generate_readme(len(flows), len(assertion_sets))
        readme_file = output_path / "README.md"
        readme_file.write_text(readme, encoding='utf-8')
        results["readme"] = str(readme_file)

        self.logger.info(f"Generated complete project in {output_dir}")
        return results

    def _build_api_mappings(
        self,
        flows: List[TrafficFlow],
        swagger_doc: Optional[SwaggerDoc]
    ) -> Dict[str, str]:
        """Build mapping from flow IDs to API class names."""
        mappings = {}

        for flow in flows:
            if swagger_doc:
                endpoint = swagger_doc.find_endpoint_by_url(flow.request.url)
                if endpoint:
                    mappings[flow.flow_id] = endpoint.get_class_name()
                    continue

            # Fallback: generate class name from flow
            from urllib.parse import urlparse
            parsed = urlparse(flow.request.url)
            path_parts = [p for p in parsed.path.split('/') if p]
            if path_parts:
                resource = path_parts[-1]
                class_name = f"Api{resource.capitalize()}"
            else:
                class_name = "ApiEndpoint"
            mappings[flow.flow_id] = class_name

        return mappings

    def _generate_readme(self, num_flows: int, num_assertions: int) -> str:
        """Generate README.md for the generated project."""
        lines = [
            '# Generated API Tests',
            '',
            'This project contains automated API tests generated by FlowGenius SmartAdapter.',
            '',
            '## Project Structure',
            '',
            '```',
            '.',
            '├── api/                 # API object layer',
            '│   └── api_objects.py # Reusable API classes',
            '├── testcase/          # Pytest test cases',
            '│   ├── conftest.py   # Pytest configuration and fixtures',
            '│   └── test_api.py   # Generated test cases',
            '├── datas/            # Test data files',
            '├── config.py         # Configuration file',
            '└── README.md         # This file',
            '```',
            '',
            '## Statistics',
            '',
            f'- Number of test flows: {num_flows}',
            f'- Number of assertions: {num_assertions}',
            '',
            '## Running Tests',
            '',
            '```bash',
            '# Install dependencies',
            'pip install -r requirements.txt',
            '',
            '# Run all tests',
            'pytest',
            '',
            '# Run with coverage',
            'pytest --cov=api --cov-report=html',
            '',
            '# Generate Allure report',
            'pytest --alluredir=allure-results',
            'allure serve allure-results',
            '```',
            '',
            '## Configuration',
            '',
            'Edit `config.py` to change the base URL and other settings:',
            '',
            '```python',
            'BASE_URL = "https://your-api-url.com"',
            'TIMEOUT = 30',
            '```',
            '',
            '## Environment Variables',
            '',
            '- `API_BASE_URL`: Override the base URL',
            '- `ENV`: Set environment (development, staging, production)',
            '- `DEBUG`: Enable debug mode',
            '',
            '## Generated by FlowGenius SmartAdapter',
            '',
            'FlowGenius SmartAdapter is a traffic-driven automated API test script generation tool.',
            ''
        ]

        return '\n'.join(lines)

    def generate_single_test_file(
        self,
        flows: List[TrafficFlow],
        assertion_sets: Dict[str, AssertionSet],
        output_file: str
    ) -> str:
        """
        Generate a single test file with all test cases.

        Args:
            flows: List of TrafficFlow objects
            assertion_sets: Dictionary mapping flow IDs to AssertionSets
            output_file: Output file path

        Returns:
            Path to generated test file
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        test_module = self.test_case_generator.generate_test_module(
            flows, assertion_sets, grouped_by_endpoint=False
        )

        output_path.write_text(test_module, encoding='utf-8')
        self.logger.info(f"Generated test file: {output_path}")
        return str(output_path)

    def generate_api_objects_file(
        self,
        flows: List[TrafficFlow],
        output_file: str
    ) -> str:
        """
        Generate API objects file.

        Args:
            flows: List of TrafficFlow objects
            output_file: Output file path

        Returns:
            Path to generated API objects file
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        api_module = self.api_object_generator.generate_module(flows, self.base_url)
        output_path.write_text(api_module, encoding='utf-8')
        self.logger.info(f"Generated API objects file: {output_path}")
        return str(output_path)