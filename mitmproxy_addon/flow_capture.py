"""
MitmProxy addon for FlowGenius traffic capture.

This addon should be used with mitmdump or mitmweb:
    mitmdump -s flow_capture.py -p 8080
    mitmweb -s flow_capture.py -p 8080

Configuration options can be set via command line:
    mitmdump -s "flow_capture.py --output-dir ./output --filter-static"
"""
import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

# Initialize addon variables
OUTPUT_DIR = "."
FILTER_STATIC = True
CAPTURE_COUNT = 0
MAX_CAPTURES = None  # None for unlimited


def configure_logging():
    """Configure logging for the addon."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger("flowgenius.addon")


logger = configure_logging()


def load(context):
    """
    Load addon.

    Args:
        context: MitmProxy context (Loader object)
    """
    global OUTPUT_DIR, FILTER_STATIC, MAX_CAPTURES

    # Use defaults - configuration can be done via environment or script args if needed
    OUTPUT_DIR = Path(".")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FILTER_STATIC = True
    MAX_CAPTURES = None

    logger.info(f"FlowCapture addon loaded")
    logger.info(f"  Output directory: {OUTPUT_DIR}")
    logger.info(f"  Filter static: {FILTER_STATIC}")
    logger.info(f"  Max captures: {MAX_CAPTURES or 'unlimited'}")


def should_filter(flow):
    """
    Check if flow should be filtered (static resources).

    Args:
        flow: MitmProxy flow object

    Returns:
        True if should filter
    """
    if not FILTER_STATIC:
        return False

    url = flow.request.pretty_url.lower()
    static_extensions = [".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf", ".eot"]

    # Check by extension
    for ext in static_extensions:
        if url.endswith(ext):
            return True

    # Check by content-type
    if "content-type" in flow.response.headers:
        content_type = flow.response.headers["content-type"].lower()
        static_content_types = ["text/css", "text/javascript", "application/javascript", "image/", "font/"]
        for ct in static_content_types:
            if content_type.startswith(ct):
                return True

    return False


def request(flow):
    """Called when a request is received."""
    pass


def response(flow):
    """Called when a response is received."""
    global CAPTURE_COUNT

    # Check if reached max captures
    if MAX_CAPTURES and CAPTURE_COUNT >= MAX_CAPTURES:
        return

    # Check if should filter
    if should_filter(flow):
        return

    try:
        # Extract request data
        request_data = {
            "url": flow.request.pretty_url,
            "method": flow.request.method,
            "headers": dict(flow.request.headers),
            "content": flow.request.content.decode('utf-8', errors='ignore') if flow.request.content else None,
            "query": dict(flow.request.query),
            "timestamp": flow.timestamp_start
        }

        # Extract response data
        response_data = {
            "status_code": flow.response.status_code,
            "headers": dict(flow.response.headers),
            "content": flow.response.content.decode('utf-8', errors='ignore') if flow.response.content else None,
            "time": (flow.timestamp_end - flow.timestamp_start) if hasattr(flow, 'timestamp_end') else None
        }

        # Create flow entry
        entry = {
            "startedDateTime": datetime.fromtimestamp(request_data["timestamp"]).isoformat(),
            "request": {
                "method": request_data["method"],
                "url": request_data["url"],
                "httpVersion": "HTTP/1.1",
                "headers": [{"name": k, "value": v} for k, v in request_data["headers"].items()],
                "queryString": [{"name": k, "value": v} for k, v in request_data["query"].items()],
                "postData": {
                    "text": request_data["content"] or "",
                    "mimeType": request_data["headers"].get("Content-Type", "application/json")
                } if request_data["content"] else None
            },
            "response": {
                "status": response_data["status_code"],
                "statusText": get_status_text(response_data["status_code"]),
                "httpVersion": "HTTP/1.1",
                "headers": [{"name": k, "value": v} for k, v in response_data["headers"].items()],
                "content": {
                    "text": response_data["content"] or "",
                    "mimeType": response_data["headers"].get("Content-Type", "application/json"),
                    "size": len(response_data["content"] or "")
                }
            },
            "timings": {
                "receive": (response_data["time"] * 1000) if response_data["time"] else 0
            }
        }

        # Add to HAR data
        if not hasattr(flow, "__flowgenius_entries"):
            flow.__flowgenius_entries = []
        flow.__flowgenius_entries.append(entry)

        CAPTURE_COUNT += 1
        logger.info(f"Captured flow #{CAPTURE_COUNT}: {request_data['method']} {request_data['url']}")

    except Exception as e:
        logger.error(f"Failed to capture flow: {e}", exc_info=True)


def get_status_text(status_code):
    """Get HTTP status text."""
    status_texts = {
        200: "OK", 201: "Created", 204: "No Content",
        400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
        500: "Internal Server Error", 502: "Bad Gateway", 503: "Service Unavailable"
    }
    return status_texts.get(status_code, "Unknown")


def done(context):
    """Called when MitmProxy is shutting down."""
    global CAPTURE_COUNT

    # Gather all captured entries
    all_entries = []
    for flow in context.flows:
        if hasattr(flow, "__flowgenius_entries"):
            all_entries.extend(flow.__flowgenius_entries)

    if not all_entries:
        logger.info("No flows captured")
        return

    # Build HAR structure
    har_data = {
        "log": {
            "version": "1.2",
            "creator": {
                "name": "FlowGenius SmartAdapter",
                "version": "1.0.0"
            },
            "entries": all_entries
        }
    }

    # Save HAR file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    har_file = OUTPUT_DIR / f"traffic_{timestamp}.har"

    with open(har_file, 'w', encoding='utf-8') as f:
        json.dump(har_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {CAPTURE_COUNT} flows to {har_file}")


# For testing outside MitmProxy
if __name__ == "__main__":
    print("This addon is intended to be used with MitmProxy:")
    print("  mitmdump -s flow_capture.py -p 8080")
    print("  mitmweb -s flow_capture.py -p 8080")
    print("")
    print("Options:")
    print("  --output-dir DIR  Output directory for HAR files (default: .)")
    print("  --no-filter       Don't filter static resources")
    print("  --max N           Maximum number of flows to capture")