"""
Base domain models for metrics

Provides foundation classes for all metric types:
    - MetricSnapshot: Point-in-time metric value
    - TrendData: Time series data with helper methods
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class MetricSnapshot:
    """
    Base class for point-in-time metric snapshots.

    All specific metric types (QualityMetrics, SecurityMetrics, etc.)
    inherit from this class to provide consistent timestamp and project tracking.

    Attributes:
        timestamp: When this metric was captured
        project: Optional project identifier (for multi-project metrics)
    """
    timestamp: datetime
    project: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate timestamp is a datetime object"""
        if not isinstance(self.timestamp, datetime):
            raise TypeError(f"timestamp must be datetime, got {type(self.timestamp)}")


@dataclass
class TrendData:
    """
    Time series data for a metric with helper methods.

    Useful for calculating trends, week-over-week changes, and visualizations.

    Attributes:
        values: List of metric values (chronological order)
        timestamps: List of corresponding timestamps
        label: Optional label for the metric (e.g., "Open Bugs", "Critical Vulns")

    Example:
        trend = TrendData(
            values=[50, 45, 42, 38],
            timestamps=[week1, week2, week3, week4],
            label="Open Bugs"
        )
        print(f"Latest: {trend.latest()}")
        print(f"Change: {trend.week_over_week_change()}")
        print(f"Improving: {trend.is_improving()}")
    """
    values: List[float]
    timestamps: List[datetime]
    label: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate that values and timestamps have same length"""
        if len(self.values) != len(self.timestamps):
            raise ValueError(
                f"values and timestamps must have same length: "
                f"{len(self.values)} != {len(self.timestamps)}"
            )

    def latest(self) -> Optional[float]:
        """
        Get the most recent value.

        Returns:
            Most recent value, or None if no data
        """
        return self.values[-1] if self.values else None

    def earliest(self) -> Optional[float]:
        """
        Get the earliest value.

        Returns:
            Earliest value, or None if no data
        """
        return self.values[0] if self.values else None

    def week_over_week_change(self) -> Optional[float]:
        """
        Calculate week-over-week change (absolute difference).

        Returns:
            Latest value minus previous value, or None if insufficient data
        """
        if len(self.values) < 2:
            return None
        return self.values[-1] - self.values[-2]

    def week_over_week_percent_change(self) -> Optional[float]:
        """
        Calculate week-over-week percent change.

        Returns:
            Percent change from previous to latest, or None if insufficient data
            or if previous value is zero
        """
        if len(self.values) < 2:
            return None

        previous = self.values[-2]
        if previous == 0:
            return None  # Avoid division by zero

        latest = self.values[-1]
        return ((latest - previous) / previous) * 100

    def total_change(self) -> Optional[float]:
        """
        Calculate total change from first to last value.

        Returns:
            Latest minus earliest value, or None if insufficient data
        """
        if len(self.values) < 2:
            return None
        return self.values[-1] - self.values[0]

    def is_improving(self, lower_is_better: bool = True) -> Optional[bool]:
        """
        Check if trend is improving.

        Args:
            lower_is_better: If True, decreasing values = improving (default for bugs)
                            If False, increasing values = improving (e.g., test coverage)

        Returns:
            True if improving, False if worsening, None if insufficient data
        """
        change = self.week_over_week_change()
        if change is None:
            return None

        if lower_is_better:
            return change < 0  # Decreasing is good
        else:
            return change > 0  # Increasing is good

    def average(self) -> Optional[float]:
        """
        Calculate average value across all data points.

        Returns:
            Average value, or None if no data
        """
        if not self.values:
            return None
        return sum(self.values) / len(self.values)

    def get_range(self, n: int = 4) -> 'TrendData':
        """
        Get last N data points.

        Args:
            n: Number of most recent data points to include

        Returns:
            New TrendData with last N points
        """
        if n >= len(self.values):
            return self

        return TrendData(
            values=self.values[-n:],
            timestamps=self.timestamps[-n:],
            label=self.label
        )
