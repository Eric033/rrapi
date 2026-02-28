#!/usr/bin/env python
"""
Start MitmProxy with FlowGenius addon for traffic capture.

Usage:
    python start_proxy.py [--port PORT] [--web]
    python start_proxy.py -h | --help

Options:
    --port PORT        Proxy port [default: 8080]
    --web              Start web UI
    -h, --help         Show this help message
"""
import subprocess
import sys
from pathlib import Path


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Start MitmProxy with FlowGenius traffic capture addon"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Proxy port to listen on [default: 8080]"
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Start web UI (mitmweb)"
    )

    args = parser.parse_args()

    # Build addon script path (mitmproxy_addon is in project root)
    addon_script = str(Path(__file__).parent.parent / "mitmproxy_addon" / "flow_capture.py")

    # Build mitmproxy command
    if args.web:
        command = ["mitmweb"]
    else:
        command = ["mitmdump"]

    command.extend([
        "-p", str(args.port),
        "-s", addon_script,
        "--set", "ssl_insecure=true"
    ])

    print(f"Starting MitmProxy on port {args.port}")
    print(f"Addon script: {addon_script}")
    print(f"Web UI: {'http://localhost:8081' if args.web else 'disabled'}")
    print(f"\nCommand: {' '.join(command)}")
    print("\nPress Ctrl+C to stop capturing\n")

    # Start mitmproxy
    try:
        subprocess.run(command)
    except KeyboardInterrupt:
        print("\n\nTraffic capture stopped")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting MitmProxy: {e}")
        print("\nMake sure MitmProxy is installed:")
        print("  uv pip install mitmproxy")
        sys.exit(1)


if __name__ == "__main__":
    main()