"""
Collector Health Domain Models

Represents performance and health metrics for data collectors:
    - CollectorPerformanceMetrics: Individual collector run metrics
    - CollectorHealthSummary: Aggregated statistics across all collectors

These models track execution time, API usage, rate limiting, and errors
to provide visibility into collector pipeline health.
"""

from dataclasses import dataclass
from datetime import datetime

from execution.domain.metrics import MetricSnapshot


@dataclass(kw_only=True)
class CollectorPerformanceMetrics(MetricSnapshot):
    """
    Performance metrics for a single collector run.

    Inherits from MetricSnapshot to provide consistent timestamp tracking.
    Captures execution time, API usage, rate limiting, and error information
    for monitoring collector health.

    Attributes:
        timestamp: When this collector run completed (inherited from MetricSnapshot)
        collector_name: Name of collector (e.g., "quality", "deployment")
        execution_time_ms: Total execution time in milliseconds
        success: Whether collector completed without errors
        project_count: Number of projects processed
        api_call_count: Total API requests made
        rate_limit_hits: Number of 429 rate limit responses
        retry_count: Number of transient error retries
        error_message: Error text if failed (None if successful)
        error_type: Exception class name if failed (None if successful)

    Example:
        >>> from datetime import datetime
        >>> metrics = CollectorPerformanceMetrics(
        ...     timestamp=datetime.now(),
        ...     collector_name="quality",
        ...     execution_time_ms=45230.5,
        ...     success=True,
        ...     project_count=12,
        ...     api_call_count=150,
        ...     rate_limit_hits=0,
        ...     retry_count=2
        ... )
        >>> metrics.status
        'Good'
        >>> metrics.execution_time_seconds
        45.23
    """

    collector_name: str
    execution_time_ms: float
    success: bool
    project_count: int
    api_call_count: int
    rate_limit_hits: int
    retry_count: int
    error_message: str | None = None
    error_type: str | None = None

    @property
    def status(self) -> str:
        """
        Determine collector health status based on execution and success.

        Status Thresholds:
            - Failed: Collector raised exception
            - Action Needed: >120 seconds execution time
            - Caution: 60-120 seconds execution time
            - Good: <60 seconds execution time

        Returns:
            Status string: "Failed", "Action Needed", "Caution", or "Good"

        Example:
            >>> metrics = CollectorPerformanceMetrics(
            ...     timestamp=datetime.now(),
            ...     collector_name="quality",
            ...     execution_time_ms=45000,
            ...     success=True,
            ...     project_count=10,
            ...     api_call_count=100,
            ...     rate_limit_hits=0,
            ...     retry_count=0
            ... )
            >>> metrics.status
            'Good'
        """
        if not self.success:
            return "Failed"
        if self.execution_time_ms > 120000:  # >120 seconds
            return "Action Needed"
        if self.execution_time_ms > 60000:  # 60-120 seconds
            return "Caution"
        return "Good"

    @property
    def status_class(self) -> str:
        """
        Get CSS class for status badge styling.

        Maps status to CSS class names for consistent dashboard styling.

        Returns:
            CSS class string: "action", "caution", or "good"

        Example:
            >>> metrics = CollectorPerformanceMetrics(
            ...     timestamp=datetime.now(),
            ...     collector_name="quality",
            ...     execution_time_ms=150000,
            ...     success=True,
            ...     project_count=10,
            ...     api_call_count=100,
            ...     rate_limit_hits=0,
            ...     retry_count=0
            ... )
            >>> metrics.status_class
            'action'
        """
        status_map = {
            "Failed": "action",
            "Action Needed": "action",
            "Caution": "caution",
            "Good": "good",
        }
        return status_map[self.status]

    @property
    def execution_time_seconds(self) -> float:
        """
        Get execution time in seconds for human-readable display.

        Returns:
            Execution time in seconds (float)

        Example:
            >>> metrics = CollectorPerformanceMetrics(
            ...     timestamp=datetime.now(),
            ...     collector_name="quality",
            ...     execution_time_ms=45230.5,
            ...     success=True,
            ...     project_count=10,
            ...     api_call_count=100,
            ...     rate_limit_hits=0,
            ...     retry_count=0
            ... )
            >>> metrics.execution_time_seconds
            45.2305
        """
        return self.execution_time_ms / 1000


@dataclass
class CollectorHealthSummary:
    """
    Aggregated health statistics across all collectors.

    Provides summary metrics for monitoring overall collector pipeline health.

    Attributes:
        total_runs: Total number of collector runs
        successful_runs: Number of runs that completed without errors
        failed_runs: Number of runs that raised exceptions
        avg_execution_time_ms: Average execution time across all runs
        total_api_calls: Sum of API calls across all collectors
        total_rate_limit_hits: Sum of rate limit hits across all collectors
        slowest_collector: Name of slowest collector (by execution time)
        slowest_collector_time_ms: Execution time of slowest collector

    Example:
        >>> summary = CollectorHealthSummary(
        ...     total_runs=7,
        ...     successful_runs=6,
        ...     failed_runs=1,
        ...     avg_execution_time_ms=52340.5,
        ...     total_api_calls=850,
        ...     total_rate_limit_hits=0,
        ...     slowest_collector="risk",
        ...     slowest_collector_time_ms=89234.2
        ... )
        >>> summary.success_rate_pct
        85.71...
        >>> summary.overall_status
        'Caution'
    """

    total_runs: int
    successful_runs: int
    failed_runs: int
    avg_execution_time_ms: float
    total_api_calls: int
    total_rate_limit_hits: int
    slowest_collector: str | None
    slowest_collector_time_ms: float | None

    @property
    def success_rate_pct(self) -> float:
        """
        Calculate success rate percentage.

        Returns:
            Success rate (0-100)

        Example:
            >>> summary = CollectorHealthSummary(
            ...     total_runs=7,
            ...     successful_runs=6,
            ...     failed_runs=1,
            ...     avg_execution_time_ms=50000,
            ...     total_api_calls=500,
            ...     total_rate_limit_hits=0,
            ...     slowest_collector="risk",
            ...     slowest_collector_time_ms=80000
            ... )
            >>> summary.success_rate_pct
            85.71...
        """
        if self.total_runs == 0:
            return 0.0
        return (self.successful_runs / self.total_runs) * 100

    @property
    def failure_rate_pct(self) -> float:
        """
        Calculate failure rate percentage.

        Returns:
            Failure rate (0-100)

        Example:
            >>> summary = CollectorHealthSummary(
            ...     total_runs=7,
            ...     successful_runs=6,
            ...     failed_runs=1,
            ...     avg_execution_time_ms=50000,
            ...     total_api_calls=500,
            ...     total_rate_limit_hits=0,
            ...     slowest_collector="risk",
            ...     slowest_collector_time_ms=80000
            ... )
            >>> summary.failure_rate_pct
            14.28...
        """
        return 100 - self.success_rate_pct

    @property
    def overall_status(self) -> str:
        """
        Determine overall pipeline health status.

        Status Criteria:
            - Action Needed: Failure rate >10% OR avg time >120s OR rate limits >0
            - Caution: Failure rate >0% OR avg time >60s
            - Good: All collectors succeeded and ran fast

        Returns:
            Status string: "Action Needed", "Caution", or "Good"

        Example:
            >>> summary = CollectorHealthSummary(
            ...     total_runs=7,
            ...     successful_runs=7,
            ...     failed_runs=0,
            ...     avg_execution_time_ms=45000,
            ...     total_api_calls=500,
            ...     total_rate_limit_hits=0,
            ...     slowest_collector="risk",
            ...     slowest_collector_time_ms=70000
            ... )
            >>> summary.overall_status
            'Good'
        """
        # Critical issues requiring immediate action
        if self.failure_rate_pct > 10 or self.avg_execution_time_ms > 120000 or self.total_rate_limit_hits > 0:
            return "Action Needed"

        # Minor issues requiring attention
        if self.failure_rate_pct > 0 or self.avg_execution_time_ms > 60000:
            return "Caution"

        return "Good"


def from_json(data: dict) -> CollectorPerformanceMetrics:
    """
    Deserialize collector performance metrics from JSON.

    Factory method for loading metrics from history file.

    Args:
        data: Dictionary containing metric fields (from JSON)

    Returns:
        CollectorPerformanceMetrics instance

    Raises:
        KeyError: If required fields are missing
        ValueError: If timestamp format is invalid

    Example:
        >>> data = {
        ...     "timestamp": "2026-02-11T14:30:00.123456",
        ...     "collector_name": "quality",
        ...     "execution_time_ms": 45230.5,
        ...     "success": True,
        ...     "project_count": 12,
        ...     "api_call_count": 150,
        ...     "rate_limit_hits": 0,
        ...     "retry_count": 2,
        ...     "error_message": None,
        ...     "error_type": None
        ... }
        >>> metrics = from_json(data)
        >>> metrics.collector_name
        'quality'
    """
    return CollectorPerformanceMetrics(
        timestamp=datetime.fromisoformat(data["timestamp"]),
        collector_name=data["collector_name"],
        execution_time_ms=data["execution_time_ms"],
        success=data["success"],
        project_count=data["project_count"],
        api_call_count=data["api_call_count"],
        rate_limit_hits=data["rate_limit_hits"],
        retry_count=data["retry_count"],
        error_message=data.get("error_message"),
        error_type=data.get("error_type"),
    )
