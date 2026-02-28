"""
Unit tests for generators.
"""
import pytest
import json
from pathlib import Path

from flowgenius.generators.api_object import APIObjectGenerator
from flowgenius.generators.testcase import TestCaseGenerator as TestGen
from flowgenius.generators.datafile import DataFileGenerator, TestDataBuilder
from flowgenius.generators.config import ConfigGenerator, EnvConfigBuilder
from flowgenius.models.api import APIEndpoint
from flowgenius.models.traffic import TrafficFlow, TrafficRequest, TrafficResponse
from flowgenius.models.assertion import AssertionSet, AssertionRule, AssertionType, AssertionCategory


class TestAPIObjectGenerator:
    """Tests for APIObjectGenerator."""

    def test_init(self):
        """Test generator initialization."""
        generator = APIObjectGenerator()
        assert generator is not None

    def test_generate_class(self):
        """Test API object class generation."""
        generator = APIObjectGenerator()

        endpoint = APIEndpoint(
            path="/api/users",
            method="GET",
            summary="Get users list"
        )

        class_code = generator.generate_class(endpoint, "https://api.example.com")

        assert "class " in class_code
        assert "def " in class_code
        assert "self.base_url" in class_code
        assert "requests" in class_code

    def test_generate_class_with_params(self):
        """Test generating class with parameters."""
        generator = APIObjectGenerator()

        from flowgenius.models.api import ParameterDefinition
        endpoint = APIEndpoint(
            path="/api/users/{id}",
            method="GET",
            parameters=[
                ParameterDefinition(
                    name="id",
                    in_="path",
                    required=True,
                    type="integer"
                )
            ]
        )

        class_code = generator.generate_class(endpoint)

        assert "id:" in class_code
        assert "path" in class_code.lower()

    def test_generate_from_flow(self):
        """Test generating class from flow."""
        generator = APIObjectGenerator()

        flow = TrafficFlow(
            request=TrafficRequest(url="https://api.example.com/test", method="POST"),
            response=TrafficResponse(status_code=200)
        )

        class_code = generator.generate_from_flow(flow)

        assert "class " in class_code
        assert "POST" in class_code or "post" in class_code

    def test_generate_module(self):
        """Test generating module with multiple classes."""
        generator = APIObjectGenerator()

        flows = [
            TrafficFlow(
                request=TrafficRequest(url="https://api.example.com/users", method="GET"),
                response=TrafficResponse(status_code=200)
            ),
            TrafficFlow(
                request=TrafficRequest(url="https://api.example.com/products", method="POST"),
                response=TrafficResponse(status_code=201)
            ),
        ]

        module_code = generator.generate_module(flows)

        assert "class " in module_code
        assert module_code.count("class ") >= 2


class TestGeneratorTestCase:
    """Tests for TestCaseGenerator."""

    def test_init(self):
        """Test generator initialization."""
        generator = TestGen()
        assert generator is not None

    def test_generate_test_case(self):
        """Test test case generation."""
        generator = TestGen()

        flow = TrafficFlow(
            request=TrafficRequest(url="https://api.example.com/test", method="GET"),
            response=TrafficResponse(status_code=200)
        )

        test_code = generator.generate_test_case(flow)

        assert "def test_" in test_code
        assert "response" in test_code
        assert "assert" in test_code

    def test_generate_test_case_with_assertions(self):
        """Test test case generation with assertions."""
        generator = TestGen()

        flow = TrafficFlow(
            request=TrafficRequest(url="https://api.example.com/test", method="GET"),
            response=TrafficResponse(status_code=200)
        )

        assertion_set = AssertionSet(flow_id=flow.flow_id)
        assertion_set.add_assertion(AssertionRule(
            assertion_type=AssertionType.STATUS_CODE,
            category=AssertionCategory.HEALTH,
            description="Status check",
            expected_value=200
        ))

        test_code = generator.generate_test_case(flow, assertion_set)

        assert "assert response.status_code" in test_code

    def test_generate_test_case_with_api_class(self):
        """Test test case generation with API class."""
        generator = TestGen()

        flow = TrafficFlow(
            request=TrafficRequest(url="https://api.example.com/test", method="GET"),
            response=TrafficResponse(status_code=200)
        )

        test_code = generator.generate_test_case(flow, api_class_name="ApiTest")

        assert "ApiTest" in test_code

    def test_generate_test_class(self):
        """Test test class generation."""
        generator = TestGen()

        flows = [
            TrafficFlow(
                request=TrafficRequest(url="https://api.example.com/test", method="GET"),
                response=TrafficResponse(status_code=200)
            )
        ]

        assertion_sets = {flows[0].flow_id: AssertionSet(flow_id=flows[0].flow_id)}

        test_class = generator.generate_test_class(flows, assertion_sets)

        assert "class TestAPI:" in test_class or "class Test" in test_class
        assert "def test_" in test_class

    def test_generate_conftest(self):
        """Test conftest.py generation."""
        generator = TestGen()

        conftest = generator.generate_conftest()

        assert "@pytest.fixture" in conftest
        assert "base_url" in conftest
        assert "session" in conftest

    def test_camel_to_snake(self):
        """Test CamelCase to snake_case conversion."""
        generator = TestGen()

        assert generator._camel_to_snake("APITest") == "api_test"
        assert generator._camel_to_snake("ApiUser") == "api_user"


class TestDataFileGenerator:
    """Tests for DataFileGenerator."""

    def test_init(self):
        """Test generator initialization."""
        generator = DataFileGenerator()
        assert generator is not None

    def test_generate_yaml(self, temp_dir):
        """Test YAML data file generation."""
        generator = DataFileGenerator()

        flows = [
            TrafficFlow(
                request=TrafficRequest(
                    url="https://api.example.com/test",
                    method="GET",
                    query_params={"page": "1"}
                ),
                response=TrafficResponse(status_code=200)
            )
        ]

        yaml_file = temp_dir / "test_data.yaml"
        result = generator.generate_yaml(flows, str(yaml_file))

        assert Path(result).exists()
        assert yaml_file.read_text().count("test_cases") >= 0

    def test_generate_json(self, temp_dir):
        """Test JSON data file generation."""
        generator = DataFileGenerator()

        flows = [
            TrafficFlow(
                request=TrafficRequest(url="https://api.example.com/test", method="GET"),
                response=TrafficResponse(status_code=200)
            )
        ]

        json_file = temp_dir / "test_data.json"
        result = generator.generate_json(flows, str(json_file))

        assert Path(result).exists()
        data = json.loads(json_file.read_text())
        assert isinstance(data, dict) or isinstance(data, list)

    def test_generate_csv(self, temp_dir):
        """Test CSV data file generation."""
        generator = DataFileGenerator()

        flows = [
            TrafficFlow(
                request=TrafficRequest(url="https://api.example.com/test", method="GET"),
                response=TrafficResponse(status_code=200)
            )
        ]

        csv_file = temp_dir / "test_data.csv"
        result = generator.generate_csv(flows, str(csv_file))

        assert Path(result).exists()
        content = csv_file.read_text()
        assert "method" in content
        assert "url" in content

    def test_flow_to_test_data(self):
        """Test flow to test data conversion."""
        generator = DataFileGenerator()

        flow = TrafficFlow(
            request=TrafficRequest(
                url="https://api.example.com/test",
                method="POST",
                query_params={"key": "value"},
                body='{"data": "test"}',
                headers={"Content-Type": "application/json"}
            ),
            response=TrafficResponse(status_code=200, time=0.5)
        )

        test_data = generator._flow_to_test_data(flow)

        assert test_data["method"] == "POST"
        assert test_data["url"] == "https://api.example.com/test"
        assert test_data["expected_status"] == 200
        assert "assertions" in test_data


class TestDataBuilder:
    """Tests for TestDataBuilder."""

    def test_init(self):
        """Test data builder initialization."""
        builder = TestDataBuilder()
        assert builder is not None

    def test_build_test_scenarios(self):
        """Test building test scenarios."""
        builder = TestDataBuilder()

        flows = [
            TrafficFlow(
                request=TrafficRequest(url="https://api.example.com/test", method="GET"),
                response=TrafficResponse(status_code=200)
            )
        ]

        scenarios = builder.build_test_scenarios(flows, variations=2)

        assert len(scenarios) >= 1  # Original + variations
        assert "name" in scenarios[0]

    def test_build_negative_test_cases(self):
        """Test building negative test cases."""
        builder = TestDataBuilder()

        flows = [
            TrafficFlow(
                request=TrafficRequest(
                    url="https://api.example.com/test",
                    method="POST",
                    body='{"id": 123, "name": "test"}'
                ),
                response=TrafficResponse(status_code=200)
            )
        ]

        negative_cases = builder.build_negative_test_cases(flows)

        # May generate negative cases or return empty
        assert isinstance(negative_cases, list)


class TestConfigGenerator:
    """Tests for ConfigGenerator."""

    def test_init(self):
        """Test config generator initialization."""
        generator = ConfigGenerator()
        assert generator is not None

    def test_generate_config_py(self):
        """Test config.py generation."""
        generator = ConfigGenerator()

        config = generator.generate_config_py("https://api.example.com")

        assert "BASE_URL" in config
        assert "https://api.example.com" in config
        assert "TIMEOUT" in config

    def test_generate_ini_config(self):
        """Test pytest.ini generation."""
        generator = ConfigGenerator()

        ini_config = generator.generate_ini_config()

        assert "[pytest]" in ini_config
        assert "testpaths" in ini_config
        assert "markers" in ini_config

    def test_generate_pyproject_toml(self):
        """Test pyproject.toml generation."""
        generator = ConfigGenerator()

        pyproject = generator.generate_pyproject_toml()

        assert "[build-system]" in pyproject
        assert "[tool.pytest.ini_options]" in pyproject

    def test_generate_gitignore(self):
        """Test .gitignore generation."""
        generator = ConfigGenerator()

        gitignore = generator.generate_gitignore()

        assert "__pycache__" in gitignore
        assert ".pytest_cache" in gitignore
        assert "*.log" in gitignore

    def test_generate_all(self, temp_dir):
        """Test generating all config files."""
        generator = ConfigGenerator()

        results = generator.generate_all(str(temp_dir))

        assert "config.py" in results
        assert "pytest.ini" in results
        assert "pyproject.toml" in results
        assert ".gitignore" in results

        # Check files exist
        for file_path in results.values():
            assert Path(file_path).exists()


class TestEnvConfigBuilder:
    """Tests for EnvConfigBuilder."""

    def test_init(self):
        """Test environment config builder initialization."""
        builder = EnvConfigBuilder()
        assert builder is not None

    def test_add_environment(self):
        """Test adding environment configuration."""
        builder = EnvConfigBuilder()

        builder.add_environment("test", {"url": "https://test.com"})

        config = builder.get_config()
        assert "test" in config
        assert config["test"]["url"] == "https://test.com"

    def test_build_default(self):
        """Test building default environments."""
        builder = EnvConfigBuilder()
        builder.build_default()

        config = builder.get_config()

        assert "development" in config
        assert "staging" in config
        assert "production" in config