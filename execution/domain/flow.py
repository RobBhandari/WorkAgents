"""
Flow domain models - Engineering flow metrics

Represents flow metrics for tracking development velocity:
    - Lead time (created -> closed)
    - Cycle time (active -> closed)
    - WIP (work in progress)
    - Aging items
"""

from dataclasses import dataclass

from .metrics import MetricSnapshot


@dataclass
class FlowMetrics(MetricSnapshot):
    """
    Engineering flow metrics for a project at a point in time.

    Tracks lead time, cycle time, WIP, and aging metrics following
    the principles of flow efficiency.

    Metrics are measured in days, with P50/P85/P95 percentiles.

    Attributes:
        timestamp: When metrics were captured
        project: Project name
        lead_time_p50: Median lead time (created -> closed) in days
        lead_time_p85: 85th percentile lead time
        lead_time_p95: 95th percentile lead time
        cycle_time_p50: Median cycle time (first active -> closed) in days
        cycle_time_p85: 85th percentile cycle time
        cycle_time_p95: 95th percentile cycle time
        wip_count: Current work in progress (open items)
        aging_items: Items open > threshold (default 30 days)
        throughput: Items completed in measurement period

    Example:
        metrics = FlowMetrics(
            timestamp=datetime.now(),
            project="MyApp",
            lead_time_p50=7.5,
            lead_time_p85=15.2,
            lead_time_p95=25.8,
            cycle_time_p50=4.2,
            cycle_time_p85=8.5,
            cycle_time_p95=14.3,
            wip_count=25,
            aging_items=5,
            throughput=12
        )

        print(f"Typical lead time: {metrics.lead_time_p50} days")

        if metrics.has_flow_issues():
            print("Flow issues detected!")
    """

    # Lead time metrics (created -> closed)
    lead_time_p50: float | None = None
    lead_time_p85: float | None = None
    lead_time_p95: float | None = None

    # Cycle time metrics (first active -> closed)
    cycle_time_p50: float | None = None
    cycle_time_p85: float | None = None
    cycle_time_p95: float | None = None

    # WIP and aging
    wip_count: int = 0
    aging_items: int = 0

    # Throughput (completed items in period)
    throughput: int | None = None

    @property
    def has_lead_time_data(self) -> bool:
        """
        Check if lead time metrics are available.

        Returns:
            True if lead_time_p50 is not None, False otherwise

        Example:
            >>> metrics = FlowMetrics(timestamp=datetime.now(), project="App", lead_time_p50=7.5)
            >>> metrics.has_lead_time_data
            True
        """
        return self.lead_time_p50 is not None

    @property
    def has_cycle_time_data(self) -> bool:
        """
        Check if cycle time metrics are available.

        Returns:
            True if cycle_time_p50 is not None, False otherwise

        Example:
            >>> metrics = FlowMetrics(timestamp=datetime.now(), project="App", cycle_time_p50=4.2)
            >>> metrics.has_cycle_time_data
            True
        """
        return self.cycle_time_p50 is not None

    def lead_time_variability(self) -> float | None:
        """
        Calculate lead time variability (P95 / P50).

        Higher variability indicates unpredictable delivery times.
        Ideal range: 1.5-2.5

        Returns:
            Ratio of P95 to P50, or None if data unavailable or P50 is zero

        Example:
            >>> metrics = FlowMetrics(timestamp=datetime.now(), project="App", lead_time_p50=10.0, lead_time_p95=30.0)
            >>> metrics.lead_time_variability()
            3.0
        """
        if self.lead_time_p50 is None or self.lead_time_p95 is None or self.lead_time_p50 == 0:
            return None

        return self.lead_time_p95 / self.lead_time_p50

    def cycle_time_variability(self) -> float | None:
        """
        Calculate cycle time variability (P95 / P50).

        Returns:
            Ratio of P95 to P50, or None if data unavailable or P50 is zero

        Example:
            >>> metrics = FlowMetrics(timestamp=datetime.now(), project="App", cycle_time_p50=5.0, cycle_time_p95=12.0)
            >>> metrics.cycle_time_variability()
            2.4
        """
        if self.cycle_time_p50 is None or self.cycle_time_p95 is None or self.cycle_time_p50 == 0:
            return None

        return self.cycle_time_p95 / self.cycle_time_p50

    def has_high_variability(self, threshold: float = 3.0) -> bool:
        """
        Check if lead time variability is concerning.

        Args:
            threshold: Variability threshold (default: 3.0)

        Returns:
            True if variability exceeds threshold, False otherwise

        Example:
            >>> metrics = FlowMetrics(timestamp=datetime.now(), project="App", lead_time_p50=10.0, lead_time_p95=35.0)
            >>> metrics.has_high_variability()  # 3.5 > 3.0
            True
        """
        variability: float | None = self.lead_time_variability()
        return variability is not None and variability > threshold

    def aging_percentage(self) -> float | None:
        """
        Calculate percentage of WIP that is aging.

        Returns:
            Percentage of aging items (0-100), or None if no WIP

        Example:
            >>> metrics = FlowMetrics(timestamp=datetime.now(), project="App", wip_count=50, aging_items=10)
            >>> metrics.aging_percentage()
            20.0
        """
        if self.wip_count == 0:
            return None

        return (self.aging_items / self.wip_count) * 100

    def has_aging_issues(self, threshold_percent: float = 20.0) -> bool:
        """
        Check if aging items are a concern.

        Args:
            threshold_percent: Percentage threshold (default: 20%)

        Returns:
            True if aging percentage exceeds threshold, False otherwise

        Example:
            >>> metrics = FlowMetrics(timestamp=datetime.now(), project="App", wip_count=50, aging_items=15)
            >>> metrics.has_aging_issues()  # 30% > 20%
            True
        """
        aging_pct: float | None = self.aging_percentage()
        return aging_pct is not None and aging_pct > threshold_percent

    def has_flow_issues(self) -> bool:
        """
        Check if there are any flow efficiency concerns.

        Concerns include:
        - High lead time variability (>3x)
        - >20% of WIP is aging
        - Very high lead time (P50 >14 days)

        Returns:
            True if any flow issues detected, False otherwise

        Example:
            >>> metrics = FlowMetrics(
            ...     timestamp=datetime.now(), project="App",
            ...     lead_time_p50=20.0, wip_count=100, aging_items=30
            ... )
            >>> metrics.has_flow_issues()  # Multiple issues: slow delivery + aging
            True
        """
        issues: list[str] = []

        # Check variability
        if self.has_high_variability():
            issues.append("high_variability")

        # Check aging
        if self.has_aging_issues():
            issues.append("aging_items")

        # Check high lead time
        if self.lead_time_p50 and self.lead_time_p50 > 14:
            issues.append("slow_delivery")

        return len(issues) > 0

    def __str__(self) -> str:
        """
        String representation for logging/debugging.

        Returns:
            Formatted string with project, lead time, WIP, and aging counts

        Example:
            >>> metrics = FlowMetrics(timestamp=datetime.now(), project="MyApp", lead_time_p50=7.5, wip_count=25, aging_items=5)
            >>> str(metrics)
            'FlowMetrics(project=MyApp, lead_time_p50=7.5d, wip=25, aging=5)'
        """
        return (
            f"FlowMetrics(project={self.project}, "
            f"lead_time_p50={self.lead_time_p50:.1f}d, "
            f"wip={self.wip_count}, aging={self.aging_items})"
        )
