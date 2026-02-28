#!/usr/bin/env python
"""
Generate Pytest test scripts from traffic data and Swagger definitions.

Usage:
    python generate_tests.py --traffic SOURCE --output-dir DIR [OPTIONS]

Options:
    --traffic SOURCE       Traffic source: HAR file, log file, or directory
    --swagger SOURCE        Swagger/OpenAPI specification (file path or URL)
    --output-dir DIR        Output directory for generated tests [default: ./generated]
    --base-url URL         Base URL for API [default: https://api.example.com]
    --business-mapping FILE Business mapping configuration file (YAML)
    --data-formats FORMAT  Data file formats: yaml, json, csv, excel, all [default: yaml,json]
    --no-swagger           Generate without Swagger integration
    --snapshot-dir DIR     Directory for snapshot comparison data
    -h, --help              Show this help message
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from flowgenius.core.collector import TrafficOrchestrator
from flowgenius.core.parser import ParserOrchestrator
from flowgenius.core.correlator import FlowCorrelator
from flowgenius.core.validator import Validator
from flowgenius.core.generator import GeneratorOrchestrator
from flowgenius.parsers.har_parser import HARParser
from flowgenius.parsers.swagger_parser import SwaggerParser
from flowgenius.parsers.log_parser import LogParser
from flowgenius.utils.config_loader import BusinessMapping
from flowgenius.utils.logger import setup_colored_logger, TrafficLogger


def load_traffic(source: str) -> list:
    """Load traffic from various sources."""
    from flowgenius.models.traffic import TrafficFlow

    source_path = Path(source)

    if not source_path.exists():
        raise FileNotFoundError(f"Traffic source not found: {source}")

    # Determine source type
    if source_path.suffix == ".har":
        # HAR file
        parser = HARParser()
        flows = parser.parse(source_path)
        print(f"Loaded {len(flows)} flows from HAR file")
        return flows

    elif source_path.is_file():
        # Log file
        collector = TrafficOrchestrator(".")
        count = collector.collect_from_logs(source_path)
        flows = collector.get_all_flows()
        print(f"Extracted {count} flows from log file")
        return flows

    elif source_path.is_dir():
        # Directory - could be HAR files or log files
        har_files = list(source_path.glob("*.har"))
        if har_files:
            # Use HAR files
            all_flows = []
            parser = HARParser()
            for har_file in har_files:
                flows = parser.parse(har_file)
                all_flows.extend(flows)
            print(f"Loaded {len(all_flows)} flows from {len(har_files)} HAR files")
            return all_flows

        # Try as log directory
        collector = TrafficOrchestrator(".")
        results = collector.collect_from_logs(source_path)
        flows = collector.get_all_flows()
        total = sum(results.values())
        print(f"Extracted {total} flows from log directory")
        return flows

    else:
        raise ValueError(f"Unknown traffic source type: {source}")


def load_swagger(source: Optional[str]):
    """Load Swagger/OpenAPI specification."""
    if not source:
        return None

    parser = SwaggerParser()
    swagger_doc = parser.parse(source)
    print(f"Loaded Swagger specification with {len(swagger_doc.get_all_endpoints())} endpoints")
    return swagger_doc


def load_business_mapping(source: Optional[str]):
    """Load business logic mapping."""
    if not source:
        return None

    mapping = BusinessMapping(source)
    print(f"Loaded {len(mapping.mappings)} business mappings")
    return mapping


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Pytest test scripts from traffic data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate tests from HAR file
    python generate_tests.py --traffic traffic.har --output-dir ./tests

    # Generate tests with Swagger integration
    python generate_tests.py --traffic traffic.har --swagger swagger.yaml --output-dir ./tests

    # Generate tests from log files
    python generate_tests.py --traffic /var/log/nginx/ --output-dir ./tests

    # Generate with business mappings
    python generate_tests.py --traffic traffic.har --business-mapping mapping.yaml

    # Generate all data formats
    python generate_tests.py --traffic traffic.har --data-formats all
        """
    )

    parser.add_argument(
        "--traffic",
        type=str,
        required=True,
        help="Traffic source: HAR file, log file, or directory"
    )
    parser.add_argument(
        "--swagger",
        type=str,
        help="Swagger/OpenAPI specification (file path or URL)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./generated",
        help="Output directory for generated tests [default: ./generated]"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="https://api.example.com",
        help="Base URL for API [default: https://api.example.com]"
    )
    parser.add_argument(
        "--business-mapping",
        type=str,
        help="Business mapping configuration file (YAML)"
    )
    parser.add_argument(
        "--data-formats",
        type=str,
        default="yaml,json",
        help="Data file formats: yaml, json, csv, excel, all [default: yaml,json]"
    )
    parser.add_argument(
        "--no-swagger",
        action="store_true",
        help="Generate without Swagger integration"
    )
    parser.add_argument(
        "--snapshot-dir",
        type=str,
        help="Directory for snapshot comparison data"
    )

    args = parser.parse_args()

    # Setup logger
    logger = setup_colored_logger("flowgenius.generate")
    traffic_logger = TrafficLogger(str(args.output_dir))

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        print("=" * 60)
        print("FlowGenius SmartAdapter - Test Generation")
        print("=" * 60)

        # Step 1: Load traffic
        print("\n[Step 1/5] Loading traffic data...")
        flows = load_traffic(args.traffic)

        if not flows:
            logger.error("No traffic flows found")
            sys.exit(1)

        # Step 2: Load Swagger (if provided)
        swagger_doc = None
        if args.swagger and not args.no_swagger:
            print("\n[Step 2/5] Loading Swagger specification...")
            swagger_doc = load_swagger(args.swagger)

            if swagger_doc:
                # Match flows to endpoints
                parser = ParserOrchestrator()
                matched = parser.match_flows_to_endpoints(flows, swagger_doc)
                matched_count = sum(1 for v in matched.values() if v is not None)
                print(f"Matched {matched_count}/{len(flows)} flows to Swagger endpoints")

        # Step 3: Analyze correlations
        print("\n[Step 3/5] Analyzing request correlations...")
        correlator = FlowCorrelator()
        chain = correlator.analyze_flows(flows)
        print(f"Found {len(chain.correlations)} correlations between flows")

        # Step 4: Generate assertions
        print("\n[Step 4/5] Generating assertions...")
        validator = Validator()

        if args.snapshot_dir:
            validator.snapshot_manager.snapshot_dir = Path(args.snapshot_dir)

        assertion_sets = validator.generate_all_assertions(
            flows, swagger_doc, str(args.snapshot_dir) if args.snapshot_dir else None
        )

        total_assertions = sum(len(s.assertions) for s in assertion_sets.values())
        print(f"Generated {total_assertions} assertions for {len(assertion_sets)} flows")

        # Step 5: Generate test scripts
        print("\n[Step 5/5] Generating test scripts...")

        # Load business mappings if provided
        business_mappings = None
        if args.business_mapping:
            mapping = load_business_mapping(args.business_mapping)
            if mapping:
                business_mappings = {
                    mapping.mappings[i].get("path"): mapping.mappings[i].get("business_logic")
                    for i in range(len(mapping.mappings))
                }

        # Parse data formats
        if args.data_formats == "all":
            data_formats = ["yaml", "json", "csv", "excel"]
        else:
            data_formats = args.data_formats.replace(" ", "").split(",")

        # Generate full project
        generator = GeneratorOrchestrator(args.base_url)
        results = generator.generate_full_project(
            flows=flows,
            assertion_sets=assertion_sets,
            output_dir=str(output_dir),
            swagger_doc=swagger_doc,
            chain=chain,
            business_mappings=business_mappings,
            data_formats=data_formats
        )

        # Summary
        print("\n" + "=" * 60)
        print("Generation Complete!")
        print("=" * 60)
        print(f"\nOutput directory: {output_dir}")
        print("\nGenerated files:")
        for file_type, file_path in results.items():
            print(f"  [{file_type}] {file_path}")

        # Print statistics
        print(f"\nStatistics:")
        print(f"  Traffic flows: {len(flows)}")
        print(f"  Assertions: {total_assertions}")
        print(f"  Correlations: {len(chain.correlations)}")
        if swagger_doc:
            print(f"  Swagger endpoints: {len(swagger_doc.get_all_endpoints())}")

        # Next steps
        print("\nNext steps:")
        print(f"  cd {output_dir}")
        print("  pip install -r requirements.txt")
        print("  pytest")
        print("  pytest --alluredir=allure-results")
        print("  allure serve allure-results")

        sys.exit(0)

    except Exception as e:
        logger.error(f"Error generating tests: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()