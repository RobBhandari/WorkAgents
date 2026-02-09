"""
Centralized logging configuration with structured JSON output.

Provides:
- JSON structured logging for production
- Human-readable console logging for development
- Automatic context injection (timestamp, module, level)
- Log level configuration per module
- File rotation support

Usage:
    from execution.core.logging_config import get_logger

    logger = get_logger(__name__)
    logger.info("Processing metrics", extra={
        "project": "MyApp",
        "metric_count": 42
    })
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    Format log records as JSON for structured logging.

    Produces machine-readable logs suitable for log aggregation tools
    (Datadog, Splunk, CloudWatch, etc.)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields (from logger.info("msg", extra={...}))
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


class ContextFormatter(logging.Formatter):
    """
    Human-readable formatter for console output.

    Includes color coding for log levels (when supported).
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with color coding"""
        # Add color to level name
        levelname = record.levelname
        if sys.stderr.isatty():  # Only use colors if outputting to terminal
            color = self.COLORS.get(levelname, "")
            record.levelname = f"{color}{levelname}{self.RESET}"

        return super().format(record)


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    json_output: bool = False,
) -> None:
    """
    Configure application-wide logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        json_output: If True, use JSON formatter; if False, use human-readable format

    Example:
        # Development (human-readable console)
        setup_logging(level="DEBUG")

        # Production (JSON to file)
        setup_logging(
            level="INFO",
            log_file=Path(".tmp/logs/app.log"),
            json_output=True
        )
    """
    # Convert string level to logging constant
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    if json_output:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            ContextFormatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)

        # Always use JSON for file output
        file_handler.setFormatter(JSONFormatter())

        root_logger.addHandler(file_handler)

    # Set specific module log levels
    logging.getLogger("urllib3").setLevel(logging.WARNING)  # Reduce noise from requests
    logging.getLogger("requests").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for the specified module.

    Args:
        name: Module name (use __name__ in calling module)

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Starting data collection")
    """
    return logging.getLogger(name)


def log_with_context(logger: logging.Logger, level: str, message: str, **context: Any) -> None:
    """
    Log message with additional context fields.

    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **context: Additional context fields (key-value pairs)

    Example:
        log_with_context(
            logger,
            "info",
            "Metrics collected",
            project="MyApp",
            bug_count=42,
            duration_ms=1234
        )
    """
    log_func = getattr(logger, level.lower())

    # Create LogRecord with extra fields
    log_func(message, extra={"extra_fields": context})


# Default configuration (can be overridden by calling setup_logging)
if not logging.getLogger().handlers:
    setup_logging(level="INFO", json_output=False)
