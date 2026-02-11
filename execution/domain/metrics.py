"""
Base domain models for metrics

Provides foundation classes for all metric types:
    - MetricSnapshot: Point-in-time metric value
    - TrendData: Time series data with helper methods
"""

from dataclasses import dataclass
from datetime import datetime


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
    project: str | None = None

    def __post_init__(self) -> None:
        """
        Validate timestamp is a datetime object.

        Raises:
            TypeError: If timestamp is not a datetime instance

        Example:
            >>> from datetime import datetime
            >>> snapshot = MetricSnapshot(timestamp=datetime.now())  # Valid
            >>> snapshot = MetricSnapshot(timestamp="2026-01-01")  # Raises TypeError
        """
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

    values: list[float]
    timestamps: list[datetime]
    label: str | None = None

    def __post_init__(self) -> None:
        """
        Validate that values and timestamps have same length.

        Raises:
            ValueError: If values and timestamps arrays have different lengths

        Example:
            >>> from datetime import datetime
            >>> trend = TrendData(values=[1, 2, 3], timestamps=[datetime.now(), datetime.now(), datetime.now()])  # Valid
            >>> trend = TrendData(values=[1, 2], timestamps=[datetime.now()])  # Raises ValueError
        """
        if len(self.values) != len(self.timestamps):
            raise ValueError(
                f"values and timestamps must have same length: " f"{len(self.values)} != {len(self.timestamps)}"
            )

    def latest(self) -> float | None:
        """
        Get the most recent value.

        Returns:
            Most recent value, or None if no data
        """
        return self.values[-1] if self.values else None

    def earliest(self) -> float | None:
        """
        Get the earliest value.

        Returns:
            Earliest value, or None if no data
        """
        return self.values[0] if self.values else None

    def week_over_week_change(self) -> float | None:
        """
        Calculate week-over-week change (absolute difference).

        Returns:
            Latest value minus previous value, or None if insufficient data
        """
        if len(self.values) < 2:
            return None
        return self.values[-1] - self.values[-2]

    def week_over_week_percent_change(self) -> float | None:
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

    def total_change(self) -> float | None:
        """
        Calculate total change from first to last value.

        Returns:
            Latest minus earliest value, or None if insufficient data
        """
        if len(self.values) < 2:
            return None
        return self.values[-1] - self.values[0]

    def is_improving(self, lower_is_better: bool = True) -> bool | None:
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

    def average(self) -> float | None:
        """
        Calculate average value across all data points.

        Returns:
            Average value, or None if no data
        """
        if not self.values:
            return None
        return sum(self.values) / len(self.values)

    def get_range(self, n: int = 4) -> "TrendData":
        """
        Get last N data points.

        Args:
            n: Number of most recent data points to include (default: 4)

        Returns:
            New TrendData instance containing only the last N points.
            If n >= total points, returns self unchanged.

        Example:
            >>> trend = TrendData(values=[1, 2, 3, 4, 5], timestamps=timestamps, label="Bugs")
            >>> last_3 = trend.get_range(3)
            >>> print(last_3.values)
            [3, 4, 5]
        """
        if n >= len(self.values):
            return self

        return TrendData(values=self.values[-n:], timestamps=self.timestamps[-n:], label=self.label)

    def moving_average(self, window: int = 7) -> list[float]:
        """
        Calculate simple moving average (SMA) with specified window size.

        For each point, averages the current point and (window-1) previous points.
        Returns NaN for points where insufficient history exists.

        Args:
            window: Number of data points to average (default: 7)

        Returns:
            List of moving averages, same length as values.
            Early values (< window) will be NaN.

        Example:
            >>> trend = TrendData(values=[10, 12, 15, 14, 13], timestamps=timestamps)
            >>> ma = trend.moving_average(window=3)
            >>> # ma = [NaN, NaN, 12.33, 13.67, 14.0]
        """
        if not self.values or window < 1:
            return []

        import math

        result = []
        for i in range(len(self.values)):
            if i < window - 1:
                result.append(math.nan)
            else:
                window_values = self.values[i - window + 1 : i + 1]
                result.append(sum(window_values) / len(window_values))

        return result

    def exponential_moving_average(self, alpha: float = 0.3) -> list[float]:
        """
        Calculate exponential moving average (EMA).

        EMA gives more weight to recent values. Formula:
            EMA[t] = alpha * value[t] + (1 - alpha) * EMA[t-1]

        Args:
            alpha: Smoothing factor (0 < alpha <= 1). Higher = more weight to recent values.
                  Common values: 0.1 (slow), 0.3 (medium), 0.5 (fast)

        Returns:
            List of exponential moving averages, same length as values.

        Example:
            >>> trend = TrendData(values=[100, 95, 90, 92, 88], timestamps=timestamps)
            >>> ema = trend.exponential_moving_average(alpha=0.3)
            >>> # Emphasizes recent trend while smoothing noise
        """
        if not self.values or alpha <= 0 or alpha > 1:
            return []

        result = [self.values[0]]  # First value is the starting point
        for i in range(1, len(self.values)):
            ema_value = alpha * self.values[i] + (1 - alpha) * result[-1]
            result.append(ema_value)

        return result

    def smooth(self, method: str = "sma", window: int = 7) -> "TrendData":
        """
        Create smoothed version of trend data using moving averages.

        Args:
            method: Smoothing method - "sma" (simple) or "ema" (exponential)
            window: Window size for SMA, or controls alpha for EMA (default: 7)

        Returns:
            New TrendData instance with smoothed values

        Example:
            >>> trend = TrendData(values=[...], timestamps=[...], label="Open Bugs")
            >>> smoothed = trend.smooth(method="sma", window=7)
            >>> smoothed_ema = trend.smooth(method="ema", window=7)
        """
        if method == "sma":
            smoothed_values = self.moving_average(window=window)
        elif method == "ema":
            # Convert window to alpha: larger window = smaller alpha (more smoothing)
            alpha = 2 / (window + 1)  # Standard EMA alpha formula
            smoothed_values = self.exponential_moving_average(alpha=alpha)
        else:
            raise ValueError(f"Unknown smoothing method: {method}. Use 'sma' or 'ema'")

        # Filter out NaN values for SMA
        import math

        if method == "sma":
            valid_indices = [i for i, v in enumerate(smoothed_values) if not math.isnan(v)]
            if not valid_indices:
                return TrendData(values=[], timestamps=[], label=f"{self.label} ({method.upper()})")

            smoothed_values = [smoothed_values[i] for i in valid_indices]
            filtered_timestamps = [self.timestamps[i] for i in valid_indices]
        else:
            filtered_timestamps = self.timestamps

        label_suffix = f" ({method.upper()}-{window})"
        return TrendData(values=smoothed_values, timestamps=filtered_timestamps, label=f"{self.label}{label_suffix}")
