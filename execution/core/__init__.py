"""
Core infrastructure module.

Provides:
- Secure configuration management (secure_config)
- HTTP client with retry logic (http_client)
- Security utilities (security_utils)
- Structured logging (logging_config)
- Observability (observability)
"""

from .logging_config import get_logger, log_with_context, setup_logging
from .observability import (
    capture_exception,
    check_dashboard_availability,
    check_data_freshness,
    notify_ci_failure,
    send_slack_notification,
    setup_observability,
    track_performance,
)

__all__ = [
    # Logging
    "get_logger",
    "setup_logging",
    "log_with_context",
    # Observability
    "setup_observability",
    "capture_exception",
    "send_slack_notification",
    "track_performance",
    "check_data_freshness",
    "check_dashboard_availability",
    "notify_ci_failure",
]
