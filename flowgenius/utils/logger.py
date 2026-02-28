"""
Logging configuration and utilities.
"""
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "flowgenius",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
    log_dir: Optional[str] = None
) -> logging.Logger:
    """
    Set up and configure a logger.

    Args:
        name: Logger name
        level: Logging level (default: logging.INFO)
        log_file: Optional log file path
        log_format: Custom log format string
        log_dir: Directory for log files (if log_file is relative)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Default format
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    formatter = logging.Formatter(log_format)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        if log_dir and not os.path.isabs(log_file):
            log_path = Path(log_dir) / log_file
        else:
            log_path = Path(log_file)

        # Create log directory if it doesn't exist
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Rotating file handler (10MB max, 5 backups)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "flowgenius") -> logging.Logger:
    """
    Get an existing logger or create a new one with default configuration.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


class TrafficLogger:
    """Specialized logger for traffic capture and processing."""

    def __init__(self, name: str = "flowgenius.traffic", log_dir: Optional[str] = None):
        """
        Initialize traffic logger.

        Args:
            name: Logger name
            log_dir: Directory for traffic logs
        """
        self.logger = setup_logger(
            name,
            level=logging.DEBUG,
            log_file="traffic.log" if log_dir else None,
            log_dir=log_dir
        )

    def log_request(self, url: str, method: str, headers: dict, body: Optional[str] = None):
        """Log an HTTP request."""
        self.logger.info(f"Request: {method} {url}")
        self.logger.debug(f"Headers: {headers}")
        if body:
            self.logger.debug(f"Body: {body[:500]}")  # Truncate long bodies

    def log_response(self, url: str, status_code: int, response_time: Optional[float] = None):
        """Log an HTTP response."""
        msg = f"Response: {url} - Status: {status_code}"
        if response_time:
            msg += f" - Time: {response_time:.3f}s"
        self.logger.info(msg)

    def log_correlation(self, from_flow: str, to_flow: str, variable: str):
        """Log a correlation between flows."""
        self.logger.info(f"Correlation: {from_flow} -> {to_flow} ({variable})")

    def log_assertion(self, flow_id: str, assertion_type: str, description: str):
        """Log an assertion generation."""
        self.logger.debug(f"Assertion for {flow_id}: {assertion_type} - {description}")

    def log_generation(self, output_file: str, num_tests: int):
        """Log test script generation."""
        self.logger.info(f"Generated {num_tests} tests in {output_file}")

    def log_error(self, message: str, exc_info: bool = False):
        """Log an error."""
        self.logger.error(message, exc_info=exc_info)

    def log_warning(self, message: str):
        """Log a warning."""
        self.logger.warning(message)


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colored output for console."""

    COLORS = {
        logging.DEBUG: "\033[36m",    # Cyan
        logging.INFO: "\033[32m",     # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",    # Red
        logging.CRITICAL: "\033[35m", # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colors."""
        if record.levelno in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelno]}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_colored_logger(
    name: str = "flowgenius",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    log_dir: Optional[str] = None
) -> logging.Logger:
    """
    Set up a logger with colored console output.

    Args:
        name: Logger name
        level: Logging level
        log_file: Optional log file path
        log_dir: Directory for log files

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Colored console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        if log_dir and not os.path.isabs(log_file):
            log_path = Path(log_dir) / log_file
        else:
            log_path = Path(log_file)

        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(file_handler)

    return logger


def log_function_call(logger: Optional[logging.Logger] = None):
    """
    Decorator to log function calls.

    Args:
        logger: Logger instance to use (creates one if not provided)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if logger is None:
                func_logger = get_logger()
            else:
                func_logger = logger

            func_logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
            try:
                result = func(*args, **kwargs)
                func_logger.debug(f"{func.__name__} returned successfully")
                return result
            except Exception as e:
                func_logger.error(f"{func.__name__} failed with error: {e}", exc_info=True)
                raise

        return wrapper
    return decorator


class TrafficCapture:
    """Context manager for capturing traffic logs."""

    def __init__(self, output_dir: str, base_name: str = "capture"):
        """
        Initialize traffic capture context.

        Args:
            output_dir: Directory to save captured logs
            base_name: Base name for log files
        """
        self.output_dir = Path(output_dir)
        self.base_name = base_name
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.output_dir / f"{base_name}_{self.timestamp}.log"
        self.har_file = self.output_dir / f"{base_name}_{self.timestamp}.har"
        self._flows = []

    def __enter__(self):
        """Start capturing traffic."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop capturing traffic and save to file."""
        self._save_captured_data()

    def add_flow(self, flow: dict):
        """Add a traffic flow to the capture."""
        self._flows.append(flow)

    def _save_captured_data(self):
        """Save captured data to files."""
        import json
        if self._flows:
            with open(self.har_file, 'w', encoding='utf-8') as f:
                json.dump({"flows": self._flows}, f, indent=2, ensure_ascii=False)