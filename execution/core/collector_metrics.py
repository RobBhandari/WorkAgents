"""
Collector Performance Tracking Module

Provides automatic performance and health monitoring for data collectors:
    - CollectorMetricsTracker: Tracks metrics for a single collector run
    - track_collector_performance(): Context manager for automatic tracking
    - get_current_tracker(): Access tracker from REST client

Integrates with existing observability infrastructure (Sentry, Slack, logging)
to provide comprehensive collector pipeline monitoring.
"""

import json
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

from execution.core.logging_config import get_logger
from execution.core.observability import capture_exception, send_slack_notification, track_performance

logger = get_logger(__name__)

# Global tracker instance for REST client access
_current_tracker: "CollectorMetricsTracker | None" = None


class CollectorMetricsTracker:
    """
    Tracks performance and health metrics for a single collector run.

    Automatically captures execution time, API usage, rate limiting, and errors.
    Integrates with REST client via global get_current_tracker() function.

    Attributes:
        collector_name: Name of collector (e.g., "quality", "deployment")
        start_time: Timestamp when tracker was started (None before start())
        execution_time_ms: Total execution time in milliseconds
        success: Whether collector completed without errors
        project_count: Number of projects processed
        api_call_count: Number of API requests made
        rate_limit_hits: Number of 429 rate limit responses
        retry_count: Number of transient error retries
        error_message: Error text if failed (None if successful)
        error_type: Exception class name if failed (None if successful)

    Example:
        >>> tracker = CollectorMetricsTracker("quality")
        >>> tracker.start()
        >>> # ... do work ...
        >>> tracker.record_api_call()  # Called automatically by REST client
        >>> tracker.end(success=True)
        >>> tracker.execution_time_ms
        45230.5
    """

    def __init__(self, collector_name: str):
        """
        Initialize tracker for collector.

        Args:
            collector_name: Name of collector (e.g., "quality", "deployment")
        """
        self.collector_name = collector_name
        self.start_time: float | None = None
        self.execution_time_ms: float = 0
        self.success: bool = False
        self.project_count: int = 0
        self.api_call_count: int = 0
        self.rate_limit_hits: int = 0
        self.retry_count: int = 0
        self.error_message: str | None = None
        self.error_type: str | None = None

    def start(self) -> None:
        """
        Start tracking execution time.

        Records current timestamp for execution time calculation.

        Example:
            >>> tracker = CollectorMetricsTracker("quality")
            >>> tracker.start()
            >>> tracker.start_time is not None
            True
        """
        self.start_time = time.time()
        logger.debug(f"Started tracking: {self.collector_name}")

    def end(self, success: bool, error: Exception | None = None) -> None:
        """
        End tracking and calculate execution time.

        Args:
            success: Whether collector completed successfully
            error: Exception if failed (None if successful)

        Example:
            >>> tracker = CollectorMetricsTracker("quality")
            >>> tracker.start()
            >>> time.sleep(0.1)
            >>> tracker.end(success=True)
            >>> tracker.success
            True
            >>> tracker.execution_time_ms > 100
            True
        """
        if self.start_time is not None:
            self.execution_time_ms = (time.time() - self.start_time) * 1000

        self.success = success

        if error:
            self.error_message = str(error)
            self.error_type = type(error).__name__
            logger.debug(
                "Collector ended with error",
                extra={"collector": self.collector_name, "error": self.error_message, "error_type": self.error_type},
            )
        else:
            logger.debug(
                "Collector ended successfully",
                extra={"collector": self.collector_name, "execution_time_ms": self.execution_time_ms},
            )

    def record_api_call(self) -> None:
        """
        Record an API call.

        Called automatically by REST client for each API request.

        Example:
            >>> tracker = CollectorMetricsTracker("quality")
            >>> tracker.record_api_call()
            >>> tracker.api_call_count
            1
        """
        self.api_call_count += 1

    def record_rate_limit_hit(self) -> None:
        """
        Record a rate limit hit (429 response).

        Called automatically by REST client when rate limited.
        Logs warning and sends Slack alert if threshold exceeded.

        Example:
            >>> tracker = CollectorMetricsTracker("quality")
            >>> tracker.record_rate_limit_hit()
            >>> tracker.rate_limit_hits
            1
        """
        self.rate_limit_hits += 1
        logger.warning(
            f"Rate limit hit for {self.collector_name} collector",
            extra={"collector": self.collector_name, "total_rate_limit_hits": self.rate_limit_hits},
        )

        # Alert if multiple rate limits in single run (>3 is critical)
        if self.rate_limit_hits > 3:
            send_slack_notification(
                f"Rate limit threshold exceeded: {self.collector_name} collector",
                severity="critical",
                context={"collector": self.collector_name, "rate_limit_hits": self.rate_limit_hits},
            )

    def record_retry(self) -> None:
        """
        Record a transient error retry.

        Called automatically by REST client on server errors or network issues.

        Example:
            >>> tracker = CollectorMetricsTracker("quality")
            >>> tracker.record_retry()
            >>> tracker.retry_count
            1
        """
        self.retry_count += 1

    def to_dict(self) -> dict[str, Any]:
        """
        Convert metrics to dictionary for JSON serialization.

        Returns:
            Dictionary with all metric fields

        Example:
            >>> tracker = CollectorMetricsTracker("quality")
            >>> tracker.start()
            >>> tracker.end(success=True)
            >>> data = tracker.to_dict()
            >>> data["collector_name"]
            'quality'
            >>> data["success"]
            True
        """
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "collector_name": self.collector_name,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "success": self.success,
            "project_count": self.project_count,
            "api_call_count": self.api_call_count,
            "rate_limit_hits": self.rate_limit_hits,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "error_type": self.error_type,
        }

    def save(self, history_file: Path) -> bool:
        """
        Save metrics to history file (weekly aggregation).

        Appends metrics to current week's collector list, creating file/week if needed.
        Maintains 52-week retention (trims old data automatically).
        Uses atomic write (temp file + rename) to prevent corruption.

        Args:
            history_file: Path to collector_performance_history.json

        Returns:
            True if saved successfully, False on error

        Raises:
            No exceptions raised (logs errors internally)

        Example:
            >>> tracker = CollectorMetricsTracker("quality")
            >>> tracker.start()
            >>> tracker.end(success=True)
            >>> success = tracker.save(Path(".tmp/observatory/collector_performance_history.json"))
            >>> success
            True
        """
        try:
            # Load existing history or create new
            if history_file.exists():
                with history_file.open("r", encoding="utf-8") as f:
                    history = json.load(f)
            else:
                history = {"weeks": []}
                logger.info(f"Creating new collector performance history file: {history_file}")

            # Get current week (ISO week format)
            now = datetime.now(UTC)
            current_week_date = now.strftime("%Y-%m-%d")  # Use ISO date for consistency
            current_week_number = now.isocalendar()[1]

            # Find or create current week entry
            current_week = None
            for week in history["weeks"]:
                if week["week_date"] == current_week_date:
                    current_week = week
                    break

            if current_week is None:
                current_week = {
                    "week_date": current_week_date,
                    "week_number": current_week_number,
                    "collectors": [],
                }
                history["weeks"].append(current_week)
                logger.debug(f"Created new week entry: {current_week_date}")

            # Append metrics to current week
            current_week["collectors"].append(self.to_dict())

            # Trim to 52 weeks retention
            if len(history["weeks"]) > 52:
                history["weeks"] = history["weeks"][-52:]
                logger.debug("Trimmed history to 52 weeks")

            # Atomic save (temp file + rename to prevent corruption)
            history_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = history_file.with_suffix(".tmp")

            with temp_file.open("w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)

            temp_file.replace(history_file)  # Atomic rename

            logger.info(
                "Saved collector performance metrics",
                extra={
                    "collector": self.collector_name,
                    "file": str(history_file),
                    "execution_time_ms": self.execution_time_ms,
                    "success": self.success,
                },
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to save collector performance metrics",
                exc_info=True,
                extra={"collector": self.collector_name, "file": str(history_file), "error": str(e)},
            )
            return False


def get_current_tracker() -> "CollectorMetricsTracker | None":
    """
    Get the currently active tracker (for REST client use).

    Returns:
        Active tracker or None if no collector is being tracked

    Example:
        >>> # Inside a collector wrapped with track_collector_performance()
        >>> tracker = get_current_tracker()
        >>> if tracker:
        ...     tracker.record_api_call()
    """
    return _current_tracker


@contextmanager
def track_collector_performance(collector_name: str) -> Generator["CollectorMetricsTracker", None, None]:
    """
    Context manager for automatic collector performance tracking.

    Wraps collector execution to automatically track:
        - Execution time (start to finish)
        - Success/failure state
        - API calls, rate limits, retries (via REST client integration)
        - Errors with Sentry/Slack alerting

    Args:
        collector_name: Name of collector (e.g., "quality", "deployment")

    Yields:
        CollectorMetricsTracker instance for manual updates (e.g., project_count)

    Example:
        >>> async def main():
        ...     with track_collector_performance("quality") as tracker:
        ...         # ... collect metrics ...
        ...         results = await asyncio.gather(*tasks)
        ...         tracker.project_count = len(results)
        ...         # ... save results ...
        ...     # Metrics auto-saved on exit
    """
    global _current_tracker

    tracker = CollectorMetricsTracker(collector_name)
    _current_tracker = tracker

    # Integrate with Sentry performance tracking (120s threshold = critical)
    with track_performance(f"collector_{collector_name}", alert_threshold_ms=120000) as perf_ctx:
        perf_ctx["collector"] = collector_name
        tracker.start()

        try:
            yield tracker
            tracker.end(success=True)

            logger.info(
                "Collector completed successfully",
                extra={
                    "collector": collector_name,
                    "execution_time_ms": tracker.execution_time_ms,
                    "api_calls": tracker.api_call_count,
                    "rate_limit_hits": tracker.rate_limit_hits,
                    "retry_count": tracker.retry_count,
                    "project_count": tracker.project_count,
                },
            )

            # Add metrics to Sentry context
            perf_ctx["execution_time_ms"] = tracker.execution_time_ms
            perf_ctx["api_calls"] = tracker.api_call_count
            perf_ctx["project_count"] = tracker.project_count

        except Exception as e:
            tracker.end(success=False, error=e)

            logger.error(
                "Collector failed",
                exc_info=True,
                extra={
                    "collector": collector_name,
                    "execution_time_ms": tracker.execution_time_ms,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

            # Send Slack alert on failure
            send_slack_notification(
                f"Collector failed: {collector_name}",
                severity="error",
                context={"collector": collector_name, "error": str(e), "error_type": type(e).__name__},
            )

            # Capture exception to Sentry with context
            capture_exception(e, context={"collector": collector_name, "execution_time_ms": tracker.execution_time_ms})

            # Re-raise to preserve normal error handling
            raise

        finally:
            # Save metrics regardless of success/failure
            history_file = Path(".tmp/observatory/collector_performance_history.json")
            tracker.save(history_file)

            # Clear global tracker
            _current_tracker = None
