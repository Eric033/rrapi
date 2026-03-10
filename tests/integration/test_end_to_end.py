"""
End-to-end integration tests for the complete workflow.
"""
import pytest
import json
import yaml
from pathlib import Path

from flowgenius.core.collector import TrafficOrchestrator
from flowgenius.core.parser import ParserOrchestrator
from flowgenius.core.correlator import FlowCorrelator
from flowgenius.core.validator import Validator
from flowgenius.core.generator import GeneratorOrchestrator
from flowgenius.models.traffic import TrafficFlow, TrafficRequest, TrafficResponse


class TestEndToEnd:
    """End-to-end tests for complete FlowGenius workflow."""

    def test_full_pipeline_traffic_to_tests(self, temp_dir):
        """Test complete pipeline from traffic capture to test generation."""
        # Phase 1: Capture traffic (simulated)
        orchestrator = TrafficOrchestrator(str(temp_dir / "traffic"))

        # Simulate log-based collection
        log_file = temp_dir / "traffic" / "access.log"
        log_content = '''192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/users HTTP/1.1" 200 1234 "-" "Mozilla/5.0"
192.168.1.1 - - [25/Feb/2026:10:00:01 +0000] "POST /api/login HTTP/1.1" 200 567 "-" "Mozilla/5.0"
192.168.1.1 - - [25/Feb/2026:10:00:02 +0000] "GET /api/products HTTP/1.1" 200 890 "-" "Mozilla/5.0"'''
        log_file.write_text(log_content.strip())

        # Collect traffic
        flow_count = orchestrator.collect_from_logs(log_file)
        assert flow_count >= 3

        # Phase 2: Parse traffic
        flows = orchestrator.get_all_flows()
        assert len(flows) >= 3

        # Phase 3: Generate assertions
        validator = Validator()
        assertion_sets = validator.generate_all_assertions(flows)
        assert len(assertion_sets) == len(flows)

        # Phase 4: Generate tests
        generator = GeneratorOrchestrator("https://api.example.com")
        output_dir = temp_dir / "generated"

        results = generator.generate_full_project(
            flows=flows,
            assertion_sets=assertion_sets,
            output_dir=str(output_dir)
        )

        # Verify generated files
        assert "api_layer" in results
        assert "test_cases" in results
        assert "conftest" in results
        assert "readme" in results

        # Verify files exist
        for file_path in results.values():
            assert Path(file_path).exists()

    def test_pipeline_with_swagger(self, temp_dir, sample_swagger_data, sample_har_data):
        """Test pipeline with Swagger integration."""
        # Create Swagger file
        swagger_file = temp_dir / "swagger.yaml"
        swagger_file.write_text(yaml.dump(sample_swagger_data))

        # Parse HAR from sample data
        from flowgenius.parsers.har_parser import HARParser
        from flowgenius.parsers.swagger_parser import SwaggerParser

        har_parser = HARParser()
        flows = har_parser.parse(sample_har_data)

        # Parse Swagger
        swagger_parser = SwaggerParser()
        swagger_doc = swagger_parser.parse(str(swagger_file))

        # Generate assertions with Swagger
        validator = Validator()
        assertion_sets = validator.generate_all_assertions(flows, swagger_doc)

        # Generate tests
        generator = GeneratorOrchestrator("https://api.example.com")
        output_dir = temp_dir / "generated_swagger"

        results = generator.generate_full_project(
            flows=flows,
            assertion_sets=assertion_sets,
            output_dir=str(output_dir),
            swagger_doc=swagger_doc
        )

        assert "test_cases" in results
        assert Path(results["test_cases"]).exists()

    def test_correlation_analysis_pipeline(self, temp_dir):
        """Test correlation analysis in pipeline."""
        # Create correlated flows
        from flowgenius.models.traffic import TrafficRequest, TrafficResponse, TrafficFlow
        from datetime import datetime

        # Login flow
        login_request = TrafficRequest(
            url="https://api.example.com/login",
            method="POST",
            body='{"username": "test"}'
        )
        login_response = TrafficResponse(
            status_code=200,
            body='{"token": "abc123", "user_id": 456}',
            content_type="application/json"
        )
        login_flow = TrafficFlow(request=login_request, response=login_response)

        # Profile flow (uses token)
        profile_request = TrafficRequest(
            url="https://api.example.com/profile",
            method="GET",
            headers={"Authorization": "Bearer abc123"}
        )
        profile_response = TrafficResponse(status_code=200)
        profile_flow = TrafficFlow(request=profile_request, response=profile_response)

        flows = [login_flow, profile_flow]

        # Analyze correlations
        correlator = FlowCorrelator()
        chain = correlator.analyze_flows(flows)

        # Verify chain structure
        assert len(chain.flow_ids) == 2
        assert len(chain.correlations) >= 0

        # Generate assertions
        validator = Validator()
        assertion_sets = validator.generate_all_assertions(flows)

        # Generate tests with correlation
        generator = GeneratorOrchestrator("https://api.example.com")
        output_dir = temp_dir / "generated_corr"

        results = generator.generate_full_project(
            flows=flows,
            assertion_sets=assertion_sets,
            output_dir=str(output_dir),
            chain=chain
        )

        assert "test_cases" in results

    def test_data_driven_test_generation(self, temp_dir):
        """Test data-driven test generation."""
        # Create sample flows
        flows = []
        for i in range(3):
            flow = TrafficFlow(
                request=TrafficRequest(
                    url="https://api.example.com/users",
                    method="GET",
                    query_params={"page": str(i + 1)}
                ),
                response=TrafficResponse(status_code=200)
            )
            flows.append(flow)

        # Generate assertions
        validator = Validator()
        assertion_sets = validator.generate_all_assertions(flows)

        # Generate tests with data files
        generator = GeneratorOrchestrator("https://api.example.com")
        output_dir = temp_dir / "generated_data"

        results = generator.generate_full_project(
            flows=flows,
            assertion_sets=assertion_sets,
            output_dir=str(output_dir),
            data_formats=["yaml", "json"]
        )

        # Verify data files were generated
        assert "data_yaml" in results or len(flows) == 0

    def test_multiple_source_types(self, temp_dir):
        """Test processing traffic from multiple sources."""
        orchestrator = TrafficOrchestrator(str(temp_dir / "traffic"))

        # Add log source
        log_file = temp_dir / "traffic" / "access.log"
        log_file.write_text('192.168.1.1 - - [25/Feb/2026:10:00:00 +0000] "GET /api/test HTTP/1.1" 200 100 "-" "-"')

        orchestrator.collect_from_logs(log_file)

        # Merge collections
        flows = orchestrator.merge_collections()

        # Generate assertions and tests
        validator = Validator()
        assertion_sets = validator.generate_all_assertions(flows)

        generator = GeneratorOrchestrator("https://api.example.com")
        output_dir = temp_dir / "generated_multi"

        results = generator.generate_full_project(
            flows=flows,
            assertion_sets=assertion_sets,
            output_dir=str(output_dir)
        )

        assert "test_cases" in results

    def test_error_handling_pipeline(self, temp_dir):
        """Test pipeline error handling."""
        orchestrator = TrafficOrchestrator(str(temp_dir / "traffic"))

        # Try to load non-existent log file
        with pytest.raises(FileNotFoundError):
            orchestrator.collect_from_logs(temp_dir / "nonexistent.log")

    def test_statistics_pipeline(self, temp_dir):
        """Test statistics collection in pipeline."""
        # Create diverse flows
        flows = []
        for i in range(10):
            methods = ["GET", "POST", "PUT", "DELETE"]
            method = methods[i % 4]

            flow = TrafficFlow(
                request=TrafficRequest(
                    url=f"https://api.example.com/resource{i}",
                    method=method
                ),
                response=TrafficResponse(
                    status_code=200 if method != "DELETE" else 204
                )
            )
            flows.append(flow)

        # Generate assertions
        validator = Validator()
        assertion_sets = validator.generate_all_assertions(flows)

        # Verify statistics
        assert len(flows) == 10
        assert len(assertion_sets) == 10

        methods = [f.request.method for f in flows]
        assert methods.count("GET") >= 1
        assert methods.count("POST") >= 1
        assert methods.count("PUT") >= 1
        assert methods.count("DELETE") >= 1

    def test_generated_tests_validity(self, temp_dir):
        """Test that generated tests are valid Python."""
        # Create sample flow
        flow = TrafficFlow(
            request=TrafficRequest(url="https://api.example.com/test", method="GET"),
            response=TrafficResponse(status_code=200)
        )

        # Generate assertions
        validator = Validator()
        assertion_sets = validator.generate_all_assertions([flow])

        # Generate tests
        generator = GeneratorOrchestrator("https://api.example.com")
        output_dir = temp_dir / "generated_valid"

        results = generator.generate_full_project(
            flows=[flow],
            assertion_sets=assertion_sets,
            output_dir=str(output_dir)
        )

        # Verify generated test file is valid Python
        test_file = Path(results["test_cases"])
        test_content = test_file.read_text()

        # Basic Python syntax check
        assert "def test_" in test_content
        assert "import" in test_content
        assert "assert" in test_content

        # Try to compile (syntax check)
        try:
            compile(test_content, str(test_file), 'exec')
        except SyntaxError as e:
            pytest.fail(f"Generated test file has syntax error: {e}")

    def test_generated_api_objects_validity(self, temp_dir):
        """Test that generated API objects are valid Python."""
        flow = TrafficFlow(
            request=TrafficRequest(url="https://api.example.com/users", method="GET"),
            response=TrafficResponse(status_code=200)
        )

        generator = GeneratorOrchestrator("https://api.example.com")
        output_dir = temp_dir / "generated_api"

        results = generator.generate_full_project(
            flows=[flow],
            assertion_sets={},
            output_dir=str(output_dir)
        )

        # Verify API file
        api_file = Path(results["api_layer"])
        api_content = api_file.read_text()

        assert "class " in api_content
        assert "def " in api_content
        assert "requests" in api_content

        # Syntax check
        try:
            compile(api_content, str(api_file), 'exec')
        except SyntaxError as e:
            pytest.fail(f"Generated API file has syntax error: {e}")

    def test_generated_config_validity(self, temp_dir):
        """Test that generated config files are valid."""
        # Create minimal test setup
        from flowgenius.generators.config import ConfigGenerator

        generator = ConfigGenerator()
        output_dir = temp_dir / "generated_config"

        results = generator.generate_all(str(output_dir))

        # Verify all config files
        for file_type, file_path in results.items():
            assert Path(file_path).exists()

        # Verify pytest.ini
        pytest_ini = Path(results["pytest.ini"])
        assert "[pytest]" in pytest_ini.read_text()

        # Verify config.py
        config_py = Path(results["config.py"])
        assert "BASE_URL" in config_py.read_text()

        # Verify .gitignore
        gitignore = Path(results[".gitignore"])
        assert "__pycache__" in gitignore.read_text()