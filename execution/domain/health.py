"""
Engineering Health domain models

Per-product composite health scoring combining:
- Bug quality trend (improving/stable/worsening + anomaly detection)
- Security vulnerability posture (exploitable vuln density)

Used by the Engineering Health Dashboard to provide a single 0-100 health
score per product, plus organisation-wide summary.
"""

from dataclasses import dataclass, field
from datetime import datetime

from execution.domain.metrics import MetricSnapshot


@dataclass(kw_only=True)
class ProductHealth(MetricSnapshot):
    """Composite health snapshot for a single product.

    Attributes:
        product_name: Display name of the product
        health_score: Composite score 0-100 (bug_score + security_score)
        health_status: Human-readable status ("Healthy", "At Risk", "Critical")
        bug_score: Bug dimension sub-score (0-50)
        security_score: Security dimension sub-score (0-50)
        bug_trend: Direction of bug count trend ("improving", "stable", "worsening")
        bug_forecast_4wk: Predicted open bug count 4 weeks from now
        bug_ci_lower: Lower bound of 95% confidence interval
        bug_ci_upper: Upper bound of 95% confidence interval
        current_bug_count: Latest recorded open bug count
        has_anomaly: True if this week's bug count is statistically unusual
        anomaly_severity: "critical" (>3σ) or "warning" (2-3σ), None if no anomaly
        anomaly_description: Human-readable description of the anomaly
        exploitable_total: Latest exploitable vulnerability count (for display)

    Example:
        health = ProductHealth(
            timestamp=datetime.now(),
            product_name="Product A",
            health_score=72.5,
            health_status="Healthy",
            bug_score=35.0,
            security_score=37.5,
            bug_trend="stable",
            bug_forecast_4wk=180,
            bug_ci_lower=165,
            bug_ci_upper=195,
            current_bug_count=184,
            has_anomaly=False,
            anomaly_severity=None,
            anomaly_description=None,
            exploitable_total=1,
        )
    """

    product_name: str
    health_score: float
    health_status: str
    bug_score: float
    security_score: float
    bug_trend: str
    bug_forecast_4wk: int | None
    bug_ci_lower: int | None
    bug_ci_upper: int | None
    current_bug_count: int
    has_anomaly: bool
    anomaly_severity: str | None
    anomaly_description: str | None
    exploitable_total: int

    @property
    def status_class(self) -> str:
        """CSS class for status badge."""
        if self.health_status == "Healthy":
            return "status-good"
        elif self.health_status == "At Risk":
            return "status-caution"
        return "status-action"

    @property
    def trend_arrow(self) -> str:
        """Arrow indicator for bug trend direction."""
        if self.bug_trend == "improving":
            return "↓"
        elif self.bug_trend == "worsening":
            return "↑"
        return "→"

    @property
    def trend_class(self) -> str:
        """CSS class for trend indicator (green=improving, red=worsening)."""
        if self.bug_trend == "improving":
            return "trend-down"
        elif self.bug_trend == "worsening":
            return "trend-up"
        return "trend-stable"

    @property
    def forecast_label(self) -> str:
        """Human-readable forecast string."""
        if self.bug_forecast_4wk is None:
            return "Insufficient data"
        ci_text = ""
        if self.bug_ci_lower is not None and self.bug_ci_upper is not None:
            ci_text = f" (CI: {self.bug_ci_lower}–{self.bug_ci_upper})"
        return f"{self.bug_forecast_4wk} bugs{ci_text}"

    @classmethod
    def from_json(cls, data: dict) -> "ProductHealth":
        """Deserialize from JSON dict (for loading cached health data)."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            product_name=data["product_name"],
            health_score=data["health_score"],
            health_status=data["health_status"],
            bug_score=data["bug_score"],
            security_score=data["security_score"],
            bug_trend=data["bug_trend"],
            bug_forecast_4wk=data.get("bug_forecast_4wk"),
            bug_ci_lower=data.get("bug_ci_lower"),
            bug_ci_upper=data.get("bug_ci_upper"),
            current_bug_count=data.get("current_bug_count", 0),
            has_anomaly=data.get("has_anomaly", False),
            anomaly_severity=data.get("anomaly_severity"),
            anomaly_description=data.get("anomaly_description"),
            exploitable_total=data.get("exploitable_total", 0),
        )


@dataclass
class OrgHealthSummary:
    """Organisation-wide health summary.

    Attributes:
        overall_score: Median health score across all scored products
        healthy_count: Products with health_score >= 70
        at_risk_count: Products with 40 <= health_score < 70
        critical_count: Products with health_score < 40
        total_products: Total number of products scored
        critical_anomalies: Product names with >3σ bug spike this week
        warning_anomalies: Product names with 2-3σ bug spike this week
        security_target_probability: P(hitting June 30 70%-reduction target), 0-100
        security_predicted_count_june30: Predicted total vuln count on June 30
        security_target_count: Required count to hit target (246 * 0.3 = 74)
        security_predicted_shortfall: predicted_count - target (negative = ahead)
        org_security_trajectory: "On Track" / "At Risk" / "Behind"
    """

    overall_score: float
    healthy_count: int
    at_risk_count: int
    critical_count: int
    total_products: int
    critical_anomalies: list[str] = field(default_factory=list)
    warning_anomalies: list[str] = field(default_factory=list)
    security_target_probability: float = 0.0
    security_predicted_count_june30: int = 0
    security_target_count: int = 74
    security_predicted_shortfall: int = 0
    org_security_trajectory: str = "Unknown"

    @property
    def has_critical_anomaly(self) -> bool:
        """True if any product has a critical (>3σ) anomaly this week."""
        return len(self.critical_anomalies) > 0

    @property
    def overall_status(self) -> str:
        """Organisation-level status label."""
        if self.overall_score >= 70:
            return "Healthy"
        elif self.overall_score >= 40:
            return "At Risk"
        return "Critical"

    @property
    def overall_status_class(self) -> str:
        """CSS class for org-level status."""
        if self.overall_score >= 70:
            return "status-good"
        elif self.overall_score >= 40:
            return "status-caution"
        return "status-action"
