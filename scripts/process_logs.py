#!/usr/bin/env python
"""
Process log files to extract traffic information.

Usage:
    python process_logs.py --source SOURCE --output-dir DIR [OPTIONS]

Options:
    --source SOURCE     Log file or directory to process
    --output-dir DIR    Output directory for HAR files [default: .]
    --format FORMAT     Log format: nginx_combined, nginx_access, apache_common, custom
    --pattern PATTERN   Custom regex pattern for log parsing (use with --format custom)
    --max-lines N       Maximum number of lines to parse
    --no-filter         Don't filter static resources
    -h, --help          Show this help message
"""
import argparse
import sys
from pathlib import Path

from flowgenius.collectors.log_collector import (
    LogCollector,
    create_nginx_parser,
    create_apache_parser
)
from flowgenius.utils.logger import setup_colored_logger


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Process log files to extract traffic information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process Nginx access log
    python process_logs.py --source /var/log/nginx/access.log --format nginx_combined

    # Process directory of log files
    python process_logs.py --source /var/log/nginx/ --output-dir ./output

    # Process with custom pattern
    python process_logs.py --source app.log --format custom --pattern "\\[(?P<timestamp>.+?)\\] (?P<method>\\w+) (?P<path>\\S+)"

    # Process without filtering static resources
    python process_logs.py --source access.log --no-filter
        """
    )

    parser.add_argument(
        "--source",
        type=str,
        required=True,
        help="Log file or directory to process"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Output directory for HAR files [default: .]"
    )
    parser.add_argument(
        "--format",
        type=str,
        default="nginx_combined",
        choices=["nginx_combined", "nginx_access", "apache_common", "custom"],
        help="Log format [default: nginx_combined]"
    )
    parser.add_argument(
        "--pattern",
        type=str,
        help="Custom regex pattern for log parsing (required with --format custom)"
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=None,
        help="Maximum number of lines to parse"
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Don't filter static resources"
    )

    args = parser.parse_args()

    # Setup logger
    logger = setup_colored_logger("flowgenius.process_logs")

    # Validate custom pattern
    if args.format == "custom" and not args.pattern:
        logger.error("Custom pattern required with --format custom")
        sys.exit(1)

    # Ensure output directory exists
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create appropriate collector
    if args.format == "custom":
        from flowgenius.collectors.log_collector import LogCollector
        collector = LogCollector(
            log_pattern=args.pattern,
            output_dir=str(output_dir),
            filter_static=not args.no_filter
        )
    elif args.format.startswith("nginx"):
        collector = create_nginx_parser("combined" if args.format == "nginx_combined" else "access")
        collector.output_dir = Path(args.output_dir)
        collector.filter_static = not args.no_filter
    elif args.format.startswith("apache"):
        collector = create_apache_parser("common")
        collector.output_dir = Path(args.output_dir)
        collector.filter_static = not args.no_filter
    else:
        logger.error(f"Unknown log format: {args.format}")
        sys.exit(1)

    # Process log(s)
    source_path = Path(args.source)

    try:
        if source_path.is_file():
            # Process single file
            logger.info(f"Processing log file: {source_path}")
            count = collector.load_log_file(source_path, max_lines=args.max_lines)
            logger.info(f"Extracted {count} flows")

        elif source_path.is_dir():
            # Process directory
            logger.info(f"Processing log directory: {source_path}")
            results = collector.load_log_directory(source_path)
            total = sum(results.values())
            logger.info(f"Extracted {total} flows from {len(results)} files")

            for file_path, file_count in results.items():
                logger.info(f"  {file_path}: {file_count} flows")

        else:
            logger.error(f"Source not found: {source_path}")
            sys.exit(1)

        # Save to HAR
        har_path = collector.save_har()
        logger.info(f"Saved HAR file: {har_path}")

        # Print statistics
        flows = collector.get_flows()
        logger.info(f"Total flows captured: {len(flows)}")
        logger.info(f"Unique URLs: {len(collector.get_unique_urls())}")

    except Exception as e:
        logger.error(f"Error processing logs: {e}", exc_info=True)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()