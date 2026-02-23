"""
Intelligence Platform domain models.

Domain models for ML/forecasting outputs. All domain models inherit from
MetricSnapshot to maintain consistency with the existing domain model pattern.

Models:
    ForecastPoint        — Single forecast data point at a given horizon week
    ForecastResult       — P10/P50/P90 forecast bands + model metadata
    TrendStrengthScore   — Trend strength and direction (0-100 score)
    RiskScoreComponent   — Single weighted component of the composite risk score
    RiskScore            — Composite risk score with component breakdown
    ScenarioPoint        — Single Monte Carlo scenario forecast point (Phase C)
    ScenarioResult       — Full Monte Carlo scenario result with P10/P50/P90 (Phase C)
    CausalContribution   — Single dimension's contribution to a metric change (Phase C)
    MetricInsight        — Generated text insight for a metric (Phase C)
    HealthClassification — RandomForest health classification result (Phase D)
                           (defined in intelligence_ml.py; re-exported here)
    ClusterResult        — KMeans/DBSCAN cluster assignment result (Phase D)
                           (defined in intelligence_ml.py; re-exported here)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from execution.domain.metrics import MetricSnapshot  # PC-9: absolute import (never relative)


@dataclass
class ForecastPoint:
    """Single forecast data point at a given horizon week."""

    week: int  # Horizon in weeks from now (1, 4, 13, 26)
    p10: float  # 10th percentile (pessimistic)
    p50: float  # 50th percentile (median forecast)
    p90: float  # 90th percentile (optimistic)


@dataclass(kw_only=True)
class ForecastResult(MetricSnapshot):
    """
    Forecast output for a single metric/project combination.

    Inherits from MetricSnapshot:
        timestamp (datetime) — when this forecast was generated (= generated_date)
        project  (str|None) — project name (generic form, e.g. "Product_A")

    Produced by forecast_engine.py; consumed by dashboard generators
    and risk_scorer.py.

    Attributes:
        metric:          Metric name (e.g. "open_bugs", "vulnerabilities")
        forecast:        P10/P50/P90 bands at each horizon week
        model:           Model used ("prophet" or "arima")
        mape:            Mean Absolute Percent Error on holdout (0.0–1.0)
        trend_direction: "improving" | "worsening" | "flat"
        trend_strength:  R² of linear fit (0.0–1.0; higher = more reliable)

    Example:
        result = ForecastResult(
            timestamp=datetime.now(),
            project="Product_A",
            metric="open_bugs",
            forecast=[ForecastPoint(week=4, p10=80.0, p50=95.0, p90=110.0)],
            model="prophet",
            mape=0.08,
            trend_direction="improving",
            trend_strength=0.72,
        )
    """

    metric: str
    forecast: list[ForecastPoint] = field(default_factory=list)
    model: str = "prophet"
    mape: float = 0.0
    trend_direction: str = "flat"  # "improving" | "worsening" | "flat"
    trend_strength: float = 0.0  # R² 0.0–1.0

    @property
    def status(self) -> str:
        """Human-readable forecast status based on trend direction."""
        if self.trend_direction == "improving":
            return "Improving"
        if self.trend_direction == "worsening":
            return "Action Needed"
        return "Stable"

    @property
    def status_class(self) -> str:
        """CSS class for status badge."""
        if self.trend_direction == "improving":
            return "status-good"
        if self.trend_direction == "worsening":
            return "status-action"
        return "status-caution"

    @property
    def forecast_4w(self) -> ForecastPoint | None:
        """4-week forecast point, or None if not available."""
        return next((f for f in self.forecast if f.week == 4), None)

    @classmethod
    def from_json(cls, data: dict) -> ForecastResult:
        """Deserialise from forecast JSON file."""
        return cls(
            timestamp=datetime.fromisoformat(data["generated_date"]),
            project=data.get("project"),
            metric=data["metric"],
            forecast=[
                ForecastPoint(
                    week=int(f["week"]),
                    p10=float(f["p10"]),
                    p50=float(f["p50"]),
                    p90=float(f["p90"]),
                )
                for f in data.get("forecast", [])
            ],
            model=data.get("model", "prophet"),
            mape=float(data.get("mape", 0.0)),
            trend_direction=data.get("trend_direction", "flat"),
            trend_strength=float(data.get("trend_strength", 0.0)),
        )


@dataclass(kw_only=True)
class TrendStrengthScore(MetricSnapshot):
    """
    Trend strength and direction score for a metric.

    Inherits from MetricSnapshot:
        timestamp (datetime) — when this score was computed
        project  (str|None) — project name

    Produced by forecast_engine.py or as a standalone computation.

    Attributes:
        metric:         Metric name
        score:          0–100 (higher = stronger trend)
        direction:      "improving" | "worsening" | "flat"
        r_squared:      R² of linear fit (0.0–1.0)
        weeks_analyzed: Number of history weeks used
    """

    metric: str
    score: float = 0.0  # 0–100
    direction: str = "flat"  # "improving" | "worsening" | "flat"
    r_squared: float = 0.0
    weeks_analyzed: int = 0

    @property
    def status(self) -> str:
        if self.direction == "improving":
            return "Improving"
        if self.direction == "worsening":
            return "Worsening"
        return "Flat"

    @property
    def status_class(self) -> str:
        if self.direction == "improving":
            return "status-good"
        if self.direction == "worsening":
            return "status-action"
        return "status-caution"

    @classmethod
    def from_json(cls, data: dict) -> TrendStrengthScore:
        """Deserialise from a JSON dict."""
        ts_raw = data.get("timestamp") or datetime.now().isoformat()
        return cls(
            timestamp=datetime.fromisoformat(ts_raw),
            project=data.get("project"),
            metric=data["metric"],
            score=float(data.get("score", 0.0)),
            direction=data.get("direction", "flat"),
            r_squared=float(data.get("r_squared", 0.0)),
            weeks_analyzed=int(data.get("weeks_analyzed", 0)),
        )


@dataclass
class RiskScoreComponent:
    """A single weighted component of the composite risk score."""

    name: str  # e.g. "vuln_risk", "quality_risk"
    raw_score: float  # 0–100 before weighting
    weight: float  # 0.0–1.0
    weighted: float  # raw_score * weight


@dataclass
class RiskScore:
    """
    Composite risk score for a project.

    Produced by risk_scorer.py. Weights per the intelligence-layer skill:
        vuln_risk       35%
        quality_risk    25%
        deployment_risk 20%
        flow_risk       15%
        ownership_risk   5%

    Attributes:
        project:     Project name (generic form)
        total:       Composite score 0–100 (higher = more risk)
        components:  Per-component breakdown
        level:       "critical" (>80) | "high" (>60) | "medium" (>40) | "low"
    """

    project: str
    total: float
    components: list[RiskScoreComponent] = field(default_factory=list)

    @property
    def level(self) -> str:
        if self.total > 80:
            return "critical"
        if self.total > 60:
            return "high"
        if self.total > 40:
            return "medium"
        return "low"

    @property
    def status(self) -> str:
        if self.level in ("critical", "high"):
            return "Action Needed"
        if self.level == "medium":
            return "Caution"
        return "Good"

    @property
    def status_class(self) -> str:
        if self.level in ("critical", "high"):
            return "status-action"
        if self.level == "medium":
            return "status-caution"
        return "status-good"

    @classmethod
    def from_json(cls, data: dict) -> RiskScore:
        """Deserialise from risk scores JSON file."""
        components = [
            RiskScoreComponent(
                name=c["name"],
                raw_score=float(c["raw_score"]),
                weight=float(c["weight"]),
                weighted=float(c["weighted"]),
            )
            for c in data.get("components", [])
        ]
        return cls(
            project=data["project"],
            total=float(data["total"]),
            components=components,
        )


# ---------------------------------------------------------------------------
# Scenario simulation domain models (Phase C — Monte Carlo)
# ---------------------------------------------------------------------------


@dataclass
class ScenarioPoint:
    """Single scenario forecast point (p10/p50/p90 from simulation)."""

    week: int  # Horizon week (1-based, e.g. 1, 2, ..., 13)
    p10: float  # 10th percentile across simulations (pessimistic)
    p50: float  # 50th percentile across simulations (median)
    p90: float  # 90th percentile across simulations (optimistic)


@dataclass(kw_only=True)
class ScenarioResult(MetricSnapshot):
    """
    Result of a Monte Carlo scenario simulation.

    Produced by scenario_simulator.run_monte_carlo().
    Inherits from MetricSnapshot:
        timestamp (datetime) — when this simulation was generated
        project  (str|None) — project name (optional; None for cross-project simulations)

    Attributes:
        scenario_name:              Display name (e.g. "BAU", "Accelerated", "Sprint")
        metric:                     Metric name (e.g. "open_bugs", "vulnerabilities")
        horizon_weeks:              Number of weeks projected forward
        n_simulations:              Number of Monte Carlo runs performed
        forecast:                   P10/P50/P90 at each horizon week
        probability_of_improvement: Fraction of simulations where final value
                                    is better than the starting value (0.0–1.0)
        description:                Optional free-text description of this scenario
    """

    scenario_name: str
    metric: str
    horizon_weeks: int
    n_simulations: int
    forecast: list[ScenarioPoint] = field(default_factory=list)
    probability_of_improvement: float = 0.0  # 0.0–1.0
    description: str = ""

    @property
    def status(self) -> str:
        """Human-readable status based on probability of improvement."""
        if self.probability_of_improvement >= 0.7:
            return "Improving"
        if self.probability_of_improvement < 0.4:
            return "Action Needed"
        return "Stable"

    @property
    def status_class(self) -> str:
        """CSS class for status badge."""
        if self.probability_of_improvement >= 0.7:
            return "status-good"
        if self.probability_of_improvement < 0.4:
            return "status-action"
        return "status-caution"

    @property
    def summary_p50_at_horizon(self) -> float:
        """P50 value at maximum horizon week."""
        return max(self.forecast, key=lambda p: p.week).p50 if self.forecast else 0.0

    @classmethod
    def from_dict(cls, data: dict) -> ScenarioResult:
        """
        Deserialise from a plain dictionary (e.g. from JSON).

        Expected keys:
            scenario_name, metric, horizon_weeks, n_simulations,
            forecast (list of {week, p10, p50, p90}),
            probability_of_improvement, description (optional),
            timestamp (optional ISO string — defaults to now)
        """
        ts_raw = data.get("timestamp") or datetime.now().isoformat()
        forecast_points = [
            ScenarioPoint(
                week=int(fp["week"]),
                p10=float(fp["p10"]),
                p50=float(fp["p50"]),
                p90=float(fp["p90"]),
            )
            for fp in data.get("forecast", [])
        ]
        return cls(
            timestamp=datetime.fromisoformat(ts_raw),
            project=data.get("project"),
            scenario_name=str(data["scenario_name"]),
            metric=str(data["metric"]),
            horizon_weeks=int(data["horizon_weeks"]),
            n_simulations=int(data["n_simulations"]),
            forecast=forecast_points,
            probability_of_improvement=float(data["probability_of_improvement"]),
            description=str(data.get("description", "")),
        )


# ---------------------------------------------------------------------------
# Phase C intelligence domain models — Causal + Insight
# ---------------------------------------------------------------------------


@dataclass
class CausalContribution:
    """
    A single dimension's contribution to a metric change.

    No MetricSnapshot inheritance — CausalContribution has no timestamp;
    it represents a point-in-time decomposition, not a history snapshot.

    Attributes:
        dimension:        Dimension label (e.g. "Product_A", "critical", "Bug")
        current_value:    Current period value for this dimension
        prior_value:      Prior period value for this dimension
        delta:            current_value - prior_value
        contribution_pct: This dimension's share of total absolute delta (0–100)
    """

    dimension: str
    current_value: float
    prior_value: float
    delta: float
    contribution_pct: float

    @classmethod
    def from_dict(cls, data: dict) -> CausalContribution:
        """Deserialise from a plain dictionary."""
        return cls(
            dimension=str(data["dimension"]),
            current_value=float(data["current_value"]),
            prior_value=float(data["prior_value"]),
            delta=float(data["delta"]),
            contribution_pct=float(data["contribution_pct"]),
        )


@dataclass(kw_only=True)
class MetricInsight(MetricSnapshot):
    """
    A generated insight for a metric.

    Produced by insight_generator.py using either a template or an LLM stub.
    Inherits from MetricSnapshot:
        timestamp (datetime) — when this insight was generated
        project  (str|None) — project name (optional)

    Attributes:
        metric:       Metric name the insight describes (e.g. "open_bugs")
        template_key: Template identifier used (e.g. "anomaly_spike")
        text:         The human-readable insight text
        severity:     "info" | "warning" | "critical"
        source:       "template" | "llm"
    """

    metric: str
    template_key: str
    text: str
    severity: str = "info"
    source: str = "template"

    @property
    def status(self) -> str:
        """Human-readable status based on severity."""
        if self.severity == "critical":
            return "Action Needed"
        if self.severity == "warning":
            return "Caution"
        return "Good"

    @property
    def status_class(self) -> str:
        """CSS class for status badge."""
        if self.severity == "critical":
            return "status-action"
        if self.severity == "warning":
            return "status-caution"
        return "status-good"

    @classmethod
    def from_dict(cls, data: dict) -> MetricInsight:
        """Deserialise from a plain dictionary.

        The 'timestamp' key is optional — defaults to datetime.now() if absent.
        """
        ts_raw = data.get("timestamp") or datetime.now().isoformat()
        return cls(
            timestamp=datetime.fromisoformat(ts_raw),
            project=data.get("project"),
            metric=str(data["metric"]),
            template_key=str(data["template_key"]),
            text=str(data["text"]),
            severity=str(data.get("severity", "info")),
            source=str(data.get("source", "template")),
        )

    @property
    def severity_emoji(self) -> str:
        """Return an emoji corresponding to this insight's severity level."""
        return {"info": "💡", "warning": "⚠️", "critical": "🔴"}.get(self.severity, "💡")


# ---------------------------------------------------------------------------
# Phase D domain models — re-exported from intelligence_ml.py
# (Separated to keep this file within the 500-line limit)
# ---------------------------------------------------------------------------

from execution.domain.intelligence_ml import (  # noqa: F401, E402
    ClusterResult,
    HealthClassification,
)
