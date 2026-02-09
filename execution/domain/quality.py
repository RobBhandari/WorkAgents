"""
Quality domain models - Bugs and quality metrics

Represents bug work items and quality metrics for tracking:
    - Bug count trends
    - Creation/closure rates
    - Aging analysis
    - Quality improvement tracking
"""

from dataclasses import dataclass

from .metrics import MetricSnapshot


@dataclass
class Bug:
    """
    Represents a bug work item from Azure DevOps.

    Attributes:
        id: Work item ID
        title: Bug title
        state: Current state (Active, Resolved, Closed, etc.)
        priority: Priority level (1-4, where 1 is highest)
        created_date: ISO 8601 date string (YYYY-MM-DD)
        closed_date: ISO 8601 date string or None if not closed
        age_days: Number of days since creation

    Example:
        bug = Bug(
            id=12345,
            title="Login fails with special characters",
            state="Active",
            priority=1,
            created_date="2026-01-15",
            closed_date=None,
            age_days=23
        )

        if bug.is_open:
            print(f"Bug {bug.id} has been open for {bug.age_days} days")

        if bug.is_high_priority:
            print("HIGH PRIORITY BUG!")
    """

    id: int
    title: str
    state: str
    priority: int | None
    created_date: str  # ISO 8601 format
    closed_date: str | None  # ISO 8601 format or None
    age_days: int

    @property
    def is_open(self) -> bool:
        """
        Check if bug is currently open.

        Returns:
            True if state indicates bug is not fully resolved
        """
        closed_states = {"Closed", "Resolved", "Removed", "Done"}
        return self.state not in closed_states

    @property
    def is_high_priority(self) -> bool:
        """
        Check if bug is high priority (P1 or P2).

        Returns:
            True if priority is 1 or 2, False otherwise
        """
        return self.priority in (1, 2) if self.priority else False

    def is_aging(self, threshold_days: int = 30) -> bool:
        """
        Check if bug has been open longer than threshold.

        Args:
            threshold_days: Age threshold in days (default: 30)

        Returns:
            True if open and older than threshold
        """
        return self.is_open and self.age_days > threshold_days


@dataclass(kw_only=True)
class QualityMetrics(MetricSnapshot):
    """
    Quality metrics for a project at a point in time.

    Tracks bug counts, creation/closure rates, and trends.

    Attributes:
        timestamp: When metrics were captured
        project: Project name
        open_bugs: Current count of open bugs
        closed_this_week: Bugs closed in the last 7 days
        created_this_week: Bugs created in the last 7 days
        net_change: closed_this_week - created_this_week (negative is good)
        p1_count: Count of P1 (critical) bugs
        p2_count: Count of P2 (high) bugs
        aging_bugs: Count of bugs older than 30 days

    Example:
        metrics = QualityMetrics(
            timestamp=datetime.now(),
            project="MyApp",
            open_bugs=50,
            closed_this_week=10,
            created_this_week=5,
            net_change=-5,
            p1_count=2,
            p2_count=8,
            aging_bugs=15
        )

        if metrics.is_improving:
            print("Quality is improving! 🎉")

        if metrics.has_critical_bugs:
            print("Critical P1 bugs need attention!")
    """

    open_bugs: int
    closed_this_week: int
    created_this_week: int
    net_change: int
    p1_count: int = 0
    p2_count: int = 0
    aging_bugs: int = 0

    @property
    def is_improving(self) -> bool:
        """
        Check if quality is improving (more bugs closed than created).

        Returns:
            True if net_change is negative (closed > created)
        """
        return self.net_change < 0

    @property
    def has_critical_bugs(self) -> bool:
        """
        Check if there are any P1 (critical) bugs.

        Returns:
            True if p1_count > 0
        """
        return self.p1_count > 0

    @property
    def high_priority_count(self) -> int:
        """
        Get total count of high-priority bugs (P1 + P2).

        Returns:
            Sum of P1 and P2 bugs
        """
        return self.p1_count + self.p2_count

    @property
    def closure_rate(self) -> float | None:
        """
        Calculate weekly closure rate as percentage.

        Returns:
            Percentage of open bugs closed this week, or None if no bugs
        """
        if self.open_bugs == 0:
            return None
        return (self.closed_this_week / self.open_bugs) * 100

    def __str__(self) -> str:
        """String representation for logging/debugging"""
        return f"QualityMetrics(project={self.project}, " f"open={self.open_bugs}, net_change={self.net_change:+d})"
