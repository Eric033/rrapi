"""
Custom log parser for various log formats.
"""
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Pattern, Union
from urllib.parse import parse_qs, urlparse

from flowgenius.utils.logger import get_logger
from flowgenius.utils.regex_utils import (
    NGINX_ACCESS_PATTERN,
    NGINX_COMBINED_PATTERN,
    APACHE_COMMON_PATTERN,
    compile_pattern,
    extract_match,
    extract_named_groups,
    extract_tokens,
    extract_ids
)


class LogParser:
    """Parser for various log formats."""

    def __init__(self, log_pattern: Optional[str] = None):
        """
        Initialize log parser.

        Args:
            log_pattern: Regex pattern for parsing log lines (optional)
        """
        self.log_pattern = compile_pattern(log_pattern or NGINX_ACCESS_PATTERN)
        self.logger = get_logger("flowgenius.log_parser")

    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single log line.

        Args:
            line: Log line to parse

        Returns:
            Parsed data dictionary or None
        """
        if not line.strip():
            return None

        match = self.log_pattern.search(line)
        if not match:
            return None

        # Try to get named groups first
        try:
            groups = match.groupdict()
            if groups:
                return self._process_parsed_data(groups)
        except Exception:
            pass

        # Fallback to numbered groups
        return {
            "raw": line,
            "match": match.group(0)
        }

    def _process_parsed_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process parsed log data.

        Args:
            data: Raw parsed data

        Returns:
            Processed data dictionary
        """
        processed = data.copy()

        # Convert status code to int if present
        if "status" in processed:
            try:
                processed["status"] = int(processed["status"])
            except (ValueError, TypeError):
                pass

        # Convert body bytes sent to int if present
        if "body_bytes_sent" in processed:
            try:
                processed["body_bytes_sent"] = int(processed["body_bytes_sent"])
            except (ValueError, TypeError):
                pass

        # Parse timestamp if present
        if "time_local" in processed:
            processed["timestamp"] = self._parse_timestamp(processed["time_local"])

        # Parse URL and extract components
        if "request_uri" in processed:
            parsed = urlparse(processed["request_uri"])
            processed["path"] = parsed.path
            processed["query_string"] = parsed.query
            if parsed.query:
                processed["query_params"] = {
                    k: v[0] if v else ''
                    for k, v in parse_qs(parsed.query).items()
                }
            else:
                processed["query_params"] = {}

        return processed

    def _parse_timestamp(self, time_str: str) -> Optional[datetime]:
        """
        Parse timestamp string.

        Args:
            time_str: Timestamp string (various formats)

        Returns:
            Datetime object or None
        """
        # Common timestamp formats
        formats = [
            "%d/%b/%Y:%H:%M:%S %z",  # Nginx: 25/Feb/2026:10:00:00 +0000
            "%d/%b/%Y:%H:%M:%S",     # Nginx without timezone
            "%Y-%m-%d %H:%M:%S",     # Simple: 2026-02-25 10:00:00
            "%Y-%m-%dT%H:%M:%S",     # ISO: 2026-02-25T10:00:00
            "%Y-%m-%dT%H:%M:%SZ",    # ISO with Z
        ]

        for fmt in formats:
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue

        return None

    def parse_file(
        self,
        log_file: Union[str, "Path"],
        encoding: str = 'utf-8',
        max_lines: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Parse an entire log file.

        Args:
            log_file: Path to log file
            encoding: File encoding
            max_lines: Maximum lines to parse

        Returns:
            List of parsed log entries
        """
        entries = []

        from pathlib import Path
        log_path = Path(log_file)
        if not log_path.exists():
            raise FileNotFoundError(f"Log file not found: {log_path}")

        with open(log_path, 'r', encoding=encoding, errors='ignore') as f:
            for i, line in enumerate(f, 1):
                if max_lines and i > max_lines:
                    break

                entry = self.parse_line(line)
                if entry:
                    entries.append(entry)

        self.logger.info(f"Parsed {len(entries)} log entries from {log_path}")
        return entries

    def parse_directory(
        self,
        log_dir: Union[str, "Path"],
        pattern: str = "*.log",
        encoding: str = 'utf-8'
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parse all log files in a directory.

        Args:
            log_dir: Directory containing log files
            pattern: Glob pattern for matching files
            encoding: File encoding

        Returns:
            Dictionary mapping file paths to parsed entries
        """
        from pathlib import Path
        log_path = Path(log_dir)
        if not log_path.exists():
            raise FileNotFoundError(f"Log directory not found: {log_path}")

        results = {}
        for log_file in log_path.glob(pattern):
            try:
                entries = self.parse_file(log_file, encoding)
                results[str(log_file)] = entries
            except Exception as e:
                self.logger.error(f"Failed to parse {log_file}: {e}")
                results[str(log_file)] = []

        total_entries = sum(len(entries) for entries in results.values())
        self.logger.info(f"Parsed {total_entries} entries from {len(results)} files")
        return results


class JSONLogParser(LogParser):
    """Parser for JSON-formatted logs."""

    def __init__(self):
        """Initialize JSON log parser."""
        super().__init__(None)  # No regex pattern needed
        self.logger = get_logger("flowgenius.json_log_parser")

    def parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a JSON log line.

        Args:
            line: JSON log line

        Returns:
            Parsed data dictionary or None
        """
        import json

        if not line.strip():
            return None

        try:
            data = json.loads(line)
            return self._process_parsed_data(data)
        except json.JSONDecodeError as e:
            self.logger.debug(f"Failed to parse JSON line: {e}")
            return None


class ApplicationLogParser:
    """
    Parser for custom application logs containing HTTP request/response.

    This parser handles logs where requests and responses are logged separately
    and need to be correlated.
    """

    def __init__(
        self,
        request_pattern: str,
        response_pattern: str,
        correlation_field: str = "request_id"
    ):
        """
        Initialize application log parser.

        Args:
            request_pattern: Regex pattern to match request log lines
            response_pattern: Regex pattern to match response log lines
            correlation_field: Field name used to correlate request and response
        """
        self.request_pattern = compile_pattern(request_pattern)
        self.response_pattern = compile_pattern(response_pattern)
        self.correlation_field = correlation_field
        self.pending_requests: Dict[str, Dict[str, Any]] = {}
        self.logger = get_logger("flowgenius.app_log_parser")

    def parse_file(
        self,
        log_file: Union[str, "Path"],
        encoding: str = 'utf-8'
    ) -> List[Dict[str, Any]]:
        """
        Parse application log file.

        Args:
            log_file: Path to log file
            encoding: File encoding

        Returns:
            List of complete request-response pairs
        """
        from pathlib import Path
        log_path = Path(log_file)
        if not log_path.exists():
            raise FileNotFoundError(f"Log file not found: {log_path}")

        completed_pairs = []

        with open(log_path, 'r', encoding=encoding, errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # Try to match as request
                request_match = self.request_pattern.search(line)
                if request_match:
                    try:
                        request_data = request_match.groupdict()
                        corr_id = request_data.get(self.correlation_field)
                        if corr_id:
                            self.pending_requests[corr_id] = request_data
                    except Exception as e:
                        self.logger.debug(f"Failed to parse request: {e}")
                    continue

                # Try to match as response
                response_match = self.response_pattern.search(line)
                if response_match:
                    try:
                        response_data = response_match.groupdict()
                        corr_id = response_data.get(self.correlation_field)
                        if corr_id and corr_id in self.pending_requests:
                            completed_pairs.append({
                                "request": self.pending_requests.pop(corr_id),
                                "response": response_data
                            })
                    except Exception as e:
                        self.logger.debug(f"Failed to parse response: {e}")
                    continue

        # Log pending requests that never got responses
        if self.pending_requests:
            self.logger.warning(f"{len(self.pending_requests)} requests without responses")

        self.logger.info(f"Parsed {len(completed_pairs)} request-response pairs")
        return completed_pairs


def extract_tokens_from_logs(log_entries: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Extract tokens from log entries.

    Args:
        log_entries: List of parsed log entries

    Returns:
        Dictionary of token types to token values
    """
    tokens_by_type = {}

    for entry in log_entries:
        # Look in request URI
        uri = entry.get("request_uri", "")
        if uri:
            found = extract_tokens(uri)
            tokens_by_type["uri"] = tokens_by_type.get("uri", []) + found

        # Look in other fields
        for key, value in entry.items():
            if isinstance(value, str) and len(value) > 10:
                found = extract_tokens(value)
                if found:
                    tokens_by_type[key] = tokens_by_type.get(key, []) + found

    return tokens_by_type


def extract_ids_from_logs(log_entries: List[Dict[str, Any]]) -> List[int]:
    """
    Extract IDs from log entries.

    Args:
        log_entries: List of parsed log entries

    Returns:
        List of extracted IDs
    """
    ids = []

    for entry in log_entries:
        uri = entry.get("request_uri", "")
        if uri:
            found = extract_ids(uri)
            ids.extend(found)

        for key, value in entry.items():
            if isinstance(value, str):
                found = extract_ids(value)
                ids.extend(found)

    return ids


def create_nginx_parser(format_type: str = "combined") -> LogParser:
    """
    Create a log parser for Nginx logs.

    Args:
        format_type: Nginx log format ("combined" or "access")

    Returns:
        Configured LogParser instance
    """
    pattern = NGINX_COMBINED_PATTERN if format_type == "combined" else NGINX_ACCESS_PATTERN
    return LogParser(pattern)


def create_apache_parser(format_type: str = "common") -> LogParser:
    """
    Create a log parser for Apache logs.

    Args:
        format_type: Apache log format ("common" or "combined")

    Returns:
        Configured LogParser instance
    """
    pattern = NGINX_COMBINED_PATTERN if format_type == "combined" else APACHE_COMMON_PATTERN
    return LogParser(pattern)