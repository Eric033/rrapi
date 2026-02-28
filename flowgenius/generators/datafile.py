"""
Data file generation (YAML/JSON) for data-driven testing.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from flowgenius.models.traffic import TrafficFlow
from flowgenius.utils.logger import get_logger


class DataFileGenerator:
    """Generates data files (YAML/JSON) for data-driven testing."""

    def __init__(self):
        """Initialize data file generator."""
        self.logger = get_logger("flowgenius.data_file_generator")

    def generate_yaml(
        self,
        flows: List[TrafficFlow],
        output_path: Optional[str] = None,
        group_by_url: bool = True
    ) -> str:
        """
        Generate YAML data file from flows.

        Args:
            flows: List of TrafficFlow objects
            output_path: Optional output file path
            group_by_url: Whether to group test data by URL

        Returns:
            Generated YAML content or path if output_path provided
        """
        if group_by_url:
            test_data = self._group_flows_by_url(flows)
        else:
            test_data = [self._flow_to_test_data(flow) for flow in flows]

        yaml_content = yaml.dump(test_data, default_flow_style=False, allow_unicode=True, indent=2)

        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
            self.logger.info(f"Generated YAML data file: {output_file}")
            return str(output_file)

        return yaml_content

    def generate_json(
        self,
        flows: List[TrafficFlow],
        output_path: Optional[str] = None,
        group_by_url: bool = True
    ) -> str:
        """
        Generate JSON data file from flows.

        Args:
            flows: List of TrafficFlow objects
            output_path: Optional output file path
            group_by_url: Whether to group test data by URL

        Returns:
            Generated JSON content or path if output_path provided
        """
        if group_by_url:
            test_data = self._group_flows_by_url(flows)
        else:
            test_data = [self._flow_to_test_data(flow) for flow in flows]

        json_content = json.dumps(test_data, indent=2, ensure_ascii=False)

        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(json_content)
            self.logger.info(f"Generated JSON data file: {output_file}")
            return str(output_file)

        return json_content

    def _flow_to_test_data(self, flow: TrafficFlow) -> Dict[str, Any]:
        """Convert a flow to test data dictionary."""
        data = {
            "name": f"{flow.request.method} {flow.request.url}",
            "method": flow.request.method,
            "url": flow.request.url,
            "expected_status": flow.response.status_code
        }

        if flow.request.headers:
            data["headers"] = flow.request.headers

        if flow.request.query_params:
            data["params"] = flow.request.query_params

        if flow.request.body:
            body_json = flow.request.get_body_json()
            if body_json:
                data["body"] = body_json
            else:
                data["body"] = flow.request.body

        # Add assertions
        data["assertions"] = {
            "status_code": flow.response.status_code,
            "response_time": flow.response.time if flow.response.time else 5.0
        }

        return data

    def _group_flows_by_url(self, flows: List[TrafficFlow]) -> Dict[str, Any]:
        """Group flows by URL for structured data file."""
        grouped = {}

        for flow in flows:
            url = flow.request.url
            if url not in grouped:
                grouped[url] = {
                    "url": url,
                    "test_cases": []
                }

            grouped[url]["test_cases"].append({
                "method": flow.request.method,
                "name": f"{flow.request.method} - Test Case {len(grouped[url]['test_cases']) + 1}",
                "expected_status": flow.response.status_code,
                "params": flow.request.query_params or {},
                "body": flow.request.get_body_json() or None,
                "headers": flow.request.headers or {}
            })

        return grouped

    def generate_csv(
        self,
        flows: List[TrafficFlow],
        output_path: str
    ) -> str:
        """
        Generate CSV data file from flows.

        Args:
            flows: List of TrafficFlow objects
            output_path: Output file path

        Returns:
            Path to generated CSV file
        """
        import csv

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow([
                "name", "method", "url", "expected_status",
                "params", "body", "headers"
            ])

            # Write data rows
            for flow in flows:
                writer.writerow([
                    f"{flow.request.method} {flow.request.url}",
                    flow.request.method,
                    flow.request.url,
                    flow.response.status_code,
                    json.dumps(flow.request.query_params) if flow.request.query_params else "",
                    flow.request.body or "",
                    json.dumps(flow.request.headers) if flow.request.headers else ""
                ])

        self.logger.info(f"Generated CSV data file: {output_file}")
        return str(output_file)

    def generate_excel(
        self,
        flows: List[TrafficFlow],
        output_path: str
    ) -> str:
        """
        Generate Excel data file from flows.

        Args:
            flows: List of TrafficFlow objects
            output_path: Output file path

        Returns:
            Path to generated Excel file
        """
        try:
            import pandas as pd

            # Prepare data
            data_rows = []
            for flow in flows:
                data_rows.append({
                    "Name": f"{flow.request.method} {flow.request.url}",
                    "Method": flow.request.method,
                    "URL": flow.request.url,
                    "Expected Status": flow.response.status_code,
                    "Params": json.dumps(flow.request.query_params) if flow.request.query_params else "",
                    "Body": flow.request.body or "",
                    "Headers": json.dumps(flow.request.headers) if flow.request.headers else ""
                })

            # Create DataFrame and save
            df = pd.DataFrame(data_rows)
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_excel(output_file, index=False, engine='openpyxl')

            self.logger.info(f"Generated Excel data file: {output_file}")
            return str(output_file)

        except ImportError:
            self.logger.warning("pandas not available, falling back to CSV")
            return self.generate_csv(flows, output_path.replace('.xlsx', '.csv'))

    def generate_multiple_data_files(
        self,
        flows: List[TrafficFlow],
        output_dir: str,
        formats: List[str] = ["yaml", "json"]
    ) -> Dict[str, str]:
        """
        Generate multiple data files in different formats.

        Args:
            flows: List of TrafficFlow objects
            output_dir: Directory to save files
            formats: List of formats to generate ("yaml", "json", "csv", "excel")

        Returns:
            Dictionary mapping format to file path
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results = {}

        if "yaml" in formats:
            yaml_file = output_path / "test_data.yaml"
            results["yaml"] = self.generate_yaml(flows, str(yaml_file))

        if "json" in formats:
            json_file = output_path / "test_data.json"
            results["json"] = self.generate_json(flows, str(json_file))

        if "csv" in formats:
            csv_file = output_path / "test_data.csv"
            results["csv"] = self.generate_csv(flows, str(csv_file))

        if "excel" in formats:
            excel_file = output_path / "test_data.xlsx"
            results["excel"] = self.generate_excel(flows, str(excel_file))

        self.logger.info(f"Generated {len(results)} data files in {output_dir}")
        return results


class TestDataBuilder:
    """Builds test data structures from traffic flows."""

    def __init__(self):
        """Initialize test data builder."""
        self.logger = get_logger("flowgenius.test_data_builder")

    def build_test_scenarios(
        self,
        flows: List[TrafficFlow],
        variations: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Build test scenarios with variations.

        Args:
            flows: Base flows to build from
            variations: Number of variations per flow

        Returns:
            List of test scenario dictionaries
        """
        scenarios = []

        for flow in flows:
            # Original scenario
            scenarios.append(self._flow_to_test_data(flow))

            # Generate variations
            for i in range(1, variations + 1):
                variation = self._generate_variation(flow, i)
                scenarios.append(variation)

        return scenarios

    def _generate_variation(self, flow: TrafficFlow, variation_num: int) -> Dict[str, Any]:
        """Generate a variation of a flow for testing."""
        data = self._flow_to_test_data(flow).copy()
        data["name"] = f'{data["name"]} - Variation {variation_num}'

        # Add variation parameters based on flow method
        if flow.request.method in ("POST", "PUT", "PATCH") and flow.request.body:
            body_json = flow.request.get_body_json()
            if body_json:
                # Modify a field to create variation
                for key in body_json:
                    if isinstance(body_json[key], int):
                        body_json[key] = body_json[key] + variation_num * 10
                        data["body"] = body_json
                        break

        return data

    def build_negative_test_cases(
        self,
        flows: List[TrafficFlow]
    ) -> List[Dict[str, Any]]:
        """
        Build negative test cases (error scenarios).

        Args:
            flows: Base flows to build from

        Returns:
            List of negative test case dictionaries
        """
        negative_cases = []

        for flow in flows:
            # Missing required parameter
            negative_case = self._flow_to_test_data(flow).copy()
            negative_case["name"] = f'{negative_case["name"]} - Missing Parameter'
            if flow.request.method in ("POST", "PUT", "PATCH") and flow.request.body:
                body_json = flow.request.get_body_json()
                if body_json:
                    # Remove first parameter
                    if len(body_json) > 0:
                        key_to_remove = list(body_json.keys())[0]
                        body_json_copy = body_json.copy()
                        del body_json_copy[key_to_remove]
                        negative_case["body"] = body_json_copy
                        negative_case["expected_status"] = 400  # Bad Request
                        negative_cases.append(negative_case)

            # Invalid data type
            invalid_type_case = self._flow_to_test_data(flow).copy()
            invalid_type_case["name"] = f'{invalid_type_case["name"]} - Invalid Data Type'
            if flow.request.method in ("POST", "PUT", "PATCH") and flow.request.body:
                body_json = flow.request.get_body_json()
                if body_json:
                    for key in body_json:
                        if isinstance(body_json[key], (int, float)):
                            body_json_copy = body_json.copy()
                            body_json_copy[key] = "invalid_string"
                            invalid_type_case["body"] = body_json_copy
                            invalid_type_case["expected_status"] = 400
                            negative_cases.append(invalid_type_case)
                            break

        return negative_cases