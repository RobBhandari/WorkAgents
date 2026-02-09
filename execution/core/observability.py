"""
Observability Module - Error Tracking, Monitoring, and Alerting

Provides production-grade observability with:
- Sentry error tracking
- Slack notifications
- Dashboard uptime monitoring
- Data freshness alerts
- Performance tracking

Usage:
    from execution.core.observability import setup_observability, track_performance

    # Initialize observability
    setup_observability(environment="production")

    # Track slow operations
    with track_performance("dashboard_generation"):
        generate_dashboard()

    # Send alerts
    send_alert("Critical: 10 P1 bugs detected", severity="high")
"""

import json
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from execution.core.logging_config import get_logger

logger = get_logger(__name__)

# Optional imports (gracefully handle if not installed)
try:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration

    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    logger.warning("Sentry SDK not installed. Error tracking disabled. Install with: pip install sentry-sdk")


class ObservabilityConfig:
    """
    Configuration for observability features.

    Attributes:
        sentry_dsn: Sentry Data Source Name for error tracking
        slack_webhook_url: Slack webhook URL for notifications
        environment: Environment name (development, staging, production)
        enable_sentry: Whether to enable Sentry error tracking
        enable_slack: Whether to enable Slack notifications
    """

    def __init__(
        self,
        sentry_dsn: str | None = None,
        slack_webhook_url: str | None = None,
        environment: str = "development",
        enable_sentry: bool = False,
        enable_slack: bool = False,
    ):
        self.sentry_dsn = sentry_dsn
        self.slack_webhook_url = slack_webhook_url
        self.environment = environment
        self.enable_sentry = enable_sentry and SENTRY_AVAILABLE and sentry_dsn
        self.enable_slack = enable_slack and slack_webhook_url

        if enable_sentry and not SENTRY_AVAILABLE:
            logger.warning("Sentry requested but SDK not installed. Install with: pip install sentry-sdk")


# Global config instance
_observability_config: ObservabilityConfig | None = None


def setup_observability(
    sentry_dsn: str | None = None,
    slack_webhook_url: str | None = None,
    environment: str = "development",
    enable_sentry: bool = True,
    enable_slack: bool = True,
) -> None:
    """
    Initialize observability features.

    Args:
        sentry_dsn: Sentry DSN (or set SENTRY_DSN env var)
        slack_webhook_url: Slack webhook URL (or set SLACK_WEBHOOK_URL env var)
        environment: Environment name (development, staging, production)
        enable_sentry: Enable Sentry error tracking
        enable_slack: Enable Slack notifications

    Example:
        setup_observability(
            sentry_dsn="https://abc123@o123.ingest.sentry.io/456",
            slack_webhook_url="https://hooks.slack.com/services/T00/B00/xxx",
            environment="production"
        )
    """
    global _observability_config

    # Get from environment if not provided
    from execution.secure_config import get_config

    config = get_config()
    sentry_dsn = sentry_dsn or config.get_optional_env("SENTRY_DSN")
    slack_webhook_url = slack_webhook_url or config.get_optional_env("SLACK_WEBHOOK_URL")

    _observability_config = ObservabilityConfig(
        sentry_dsn=sentry_dsn,
        slack_webhook_url=slack_webhook_url,
        environment=environment,
        enable_sentry=enable_sentry,
        enable_slack=enable_slack,
    )

    # Initialize Sentry if enabled
    if _observability_config.enable_sentry and SENTRY_AVAILABLE:
        sentry_logging = LoggingIntegration(
            level=None,  # Capture all logs
            event_level="ERROR",  # Send errors and above to Sentry
        )

        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=environment,
            integrations=[sentry_logging],
            traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
            profiles_sample_rate=0.1,  # 10% for profiling
        )

        logger.info(
            "Sentry error tracking initialized",
            extra={"environment": environment, "traces_sample_rate": 0.1},
        )
    elif enable_sentry:
        logger.warning("Sentry error tracking requested but not available")

    # Log Slack status
    if _observability_config.enable_slack:
        logger.info("Slack notifications enabled", extra={"environment": environment})
    else:
        logger.info("Slack notifications disabled")


def capture_exception(exception: Exception, context: dict[str, Any] | None = None) -> None:
    """
    Capture an exception for error tracking.

    Args:
        exception: The exception to capture
        context: Additional context (tags, user info, etc.)

    Example:
        try:
            risky_operation()
        except Exception as e:
            capture_exception(e, context={
                "operation": "dashboard_generation",
                "project": "MyApp"
            })
            raise
    """
    if _observability_config and _observability_config.enable_sentry and SENTRY_AVAILABLE:
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_tag(key, value)
            sentry_sdk.capture_exception(exception)

        logger.error(
            "Exception captured by Sentry",
            exc_info=True,
            extra={"exception_type": type(exception).__name__, "context": context or {}},
        )
    else:
        logger.error("Exception occurred (Sentry not configured)", exc_info=True, extra={"context": context or {}})


def send_slack_notification(message: str, severity: str = "info", context: dict[str, Any] | None = None) -> bool:
    """
    Send notification to Slack.

    Args:
        message: Notification message
        severity: Severity level (info, warning, error, critical)
        context: Additional context to include

    Returns:
        True if sent successfully, False otherwise

    Example:
        send_slack_notification(
            "Critical: 10 P1 bugs detected",
            severity="critical",
            context={"project": "MyApp", "bug_count": 10}
        )
    """
    if not _observability_config or not _observability_config.enable_slack:
        logger.debug("Slack notifications disabled, skipping", extra={"message": message})
        return False

    # Color coding by severity
    colors = {
        "info": "#36a64f",  # Green
        "warning": "#ff9900",  # Orange
        "error": "#ff0000",  # Red
        "critical": "#8b0000",  # Dark red
    }

    # Build Slack message payload
    fields = [
        {"title": "Environment", "value": _observability_config.environment, "short": True},
        {"title": "Timestamp", "value": datetime.now().isoformat(), "short": True},
    ]

    # Add context fields
    if context:
        for key, value in context.items():
            fields.append({"title": key, "value": str(value), "short": True})

    payload = {
        "text": f"*{severity.upper()}*: {message}",
        "attachments": [
            {
                "color": colors.get(severity, "#808080"),
                "fields": fields,
            }
        ],
    }

    # Send to Slack
    if not _observability_config.slack_webhook_url:
        logger.error("Slack webhook URL not configured")
        return False

    try:
        from execution.http_client import post

        response = post(
            _observability_config.slack_webhook_url, json=payload, headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            logger.info("Slack notification sent", extra={"message": message, "severity": severity})
            return True
        else:
            logger.error(
                "Failed to send Slack notification",
                extra={"status_code": response.status_code, "response": response.text},
            )
            return False

    except Exception as e:
        logger.error("Error sending Slack notification", exc_info=True, extra={"error": str(e)})
        return False


@contextmanager
def track_performance(operation_name: str, alert_threshold_ms: float = 5000.0) -> Generator[dict[str, Any], None, None]:
    """
    Context manager to track operation performance.

    Args:
        operation_name: Name of the operation being tracked
        alert_threshold_ms: Alert if operation takes longer than this (milliseconds)

    Yields:
        Dictionary to store additional context

    Example:
        with track_performance("dashboard_generation", alert_threshold_ms=3000) as ctx:
            ctx["project"] = "MyApp"
            generate_dashboard()
            ctx["dashboard_size_kb"] = 245
    """
    context: dict[str, Any] = {}
    start_time = time.time()

    try:
        yield context
    finally:
        duration_ms = (time.time() - start_time) * 1000

        # Log performance
        logger.info(
            f"Performance: {operation_name}",
            extra={
                "operation": operation_name,
                "duration_ms": round(duration_ms, 2),
                "threshold_ms": alert_threshold_ms,
                **context,
            },
        )

        # Alert if slow
        if duration_ms > alert_threshold_ms:
            logger.warning(
                f"Slow operation detected: {operation_name}",
                extra={
                    "operation": operation_name,
                    "duration_ms": round(duration_ms, 2),
                    "threshold_ms": alert_threshold_ms,
                    "exceeded_by_ms": round(duration_ms - alert_threshold_ms, 2),
                    **context,
                },
            )

            # Send Slack alert for very slow operations
            if duration_ms > alert_threshold_ms * 2:
                send_slack_notification(
                    f"Slow operation: {operation_name} took {duration_ms:.0f}ms (threshold: {alert_threshold_ms:.0f}ms)",
                    severity="warning",
                    context={"duration_ms": round(duration_ms, 2), **context},
                )


def check_data_freshness(file_path: Path, max_age_hours: float = 24.0) -> tuple[bool, float]:
    """
    Check if data file is fresh (not stale).

    Args:
        file_path: Path to data file to check
        max_age_hours: Maximum age in hours before considered stale

    Returns:
        Tuple of (is_fresh, age_hours)

    Example:
        is_fresh, age = check_data_freshness(
            Path(".tmp/observatory/quality_history.json"),
            max_age_hours=24
        )

        if not is_fresh:
            send_alert(f"Stale data: {age:.1f} hours old")
    """
    if not file_path.exists():
        logger.error("Data file not found", extra={"file_path": str(file_path)})
        return False, float("inf")

    # Get file modification time
    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
    age_hours = (datetime.now() - mtime).total_seconds() / 3600

    is_fresh = age_hours <= max_age_hours

    logger.info(
        "Data freshness check",
        extra={
            "file_path": str(file_path),
            "age_hours": round(age_hours, 2),
            "max_age_hours": max_age_hours,
            "is_fresh": is_fresh,
        },
    )

    # Alert if stale
    if not is_fresh:
        logger.warning(
            "Stale data detected",
            extra={
                "file_path": str(file_path),
                "age_hours": round(age_hours, 2),
                "max_age_hours": max_age_hours,
                "exceeded_by_hours": round(age_hours - max_age_hours, 2),
            },
        )

        send_slack_notification(
            f"Stale data: {file_path.name} is {age_hours:.1f} hours old (threshold: {max_age_hours}h)",
            severity="warning",
            context={"file": file_path.name, "age_hours": round(age_hours, 2)},
        )

    return is_fresh, age_hours


def check_dashboard_availability(dashboard_path: Path) -> bool:
    """
    Check if dashboard file exists and is not empty.

    Args:
        dashboard_path: Path to dashboard HTML file

    Returns:
        True if available, False otherwise

    Example:
        if not check_dashboard_availability(Path(".tmp/observatory/dashboards/security.html")):
            send_alert("Security dashboard unavailable!")
    """
    if not dashboard_path.exists():
        logger.error("Dashboard file not found", extra={"dashboard": str(dashboard_path)})
        send_slack_notification(
            f"Dashboard unavailable: {dashboard_path.name}", severity="error", context={"path": str(dashboard_path)}
        )
        return False

    # Check if file is not empty
    size_bytes = dashboard_path.stat().st_size
    if size_bytes == 0:
        logger.error("Dashboard file is empty", extra={"dashboard": str(dashboard_path)})
        send_slack_notification(
            f"Dashboard empty: {dashboard_path.name}", severity="error", context={"path": str(dashboard_path)}
        )
        return False

    logger.info("Dashboard available", extra={"dashboard": dashboard_path.name, "size_kb": round(size_bytes / 1024, 2)})
    return True


# Convenience function for CI failure notifications
def notify_ci_failure(job_name: str, error_message: str, logs_url: str | None = None) -> None:
    """
    Send notification about CI job failure.

    Args:
        job_name: Name of the failed CI job
        error_message: Error message from the job
        logs_url: Optional URL to CI logs

    Example:
        notify_ci_failure(
            job_name="unit-tests",
            error_message="Test test_quality_metrics::test_closure_rate FAILED",
            logs_url="https://github.com/user/repo/actions/runs/123"
        )
    """
    context = {"job": job_name, "error": error_message[:200]}  # Truncate long errors

    if logs_url:
        context["logs"] = logs_url

    send_slack_notification(
        f"CI Failure: {job_name}",
        severity="error",
        context=context,
    )

    logger.error(
        "CI job failed",
        extra={
            "job_name": job_name,
            "error_message": error_message,
            "logs_url": logs_url,
        },
    )
