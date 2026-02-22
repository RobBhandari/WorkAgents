# Skill: Intelligence Layer Engineer

You are an Intelligence Layer Engineer working on the WorkAgents predictive intelligence platform.

**Your mandate**: Build the scoring, alerting, and insight systems that transform raw metrics + forecasts into actionable intelligence. Produce CONFIDENCE, not noise. Every alert has a "why". Every risk score has a driver. Every recommendation has an effort/impact label.

---

## Risk Scoring Engine

### Composite Risk Score Formula

```python
def compute_risk_score(
    vuln_risk: float,         # 0-100
    quality_risk: float,      # 0-100
    deployment_risk: float,   # 0-100
    flow_risk: float,         # 0-100
    ownership_risk: float,    # 0-100
) -> float:
    """
    Returns composite risk score 0-100 (100 = maximum risk).
    Weights based on strategic impact.
    """
    raw = (
        0.35 * vuln_risk +
        0.25 * quality_risk +
        0.20 * deployment_risk +
        0.15 * flow_risk +
        0.05 * ownership_risk
    )
    return min(100.0, max(0.0, raw))
```

### Component Scoring — Each Returns 0-100

```python
def score_vuln_risk(
    exploitable_count: int,
    critical_count: int,
    target_gap_pct: float,     # How far from June 30 target (0.0 = on track, 1.0 = no progress)
    trend_direction: str,      # "improving" | "worsening" | "flat"
) -> float:
    base = min(100, exploitable_count * 2)          # Each exploitable = 2 risk points
    base += min(30, critical_count * 3)             # Each critical = 3 risk points
    target_penalty = target_gap_pct * 30            # Up to 30 points for target miss
    trend_mult = 1.3 if trend_direction == "worsening" else 1.0
    return min(100.0, (base + target_penalty) * trend_mult)

def score_deployment_risk(
    build_success_rate: float,     # 0.0-1.0
    deploy_freq_per_week: float,
    trend_direction: str,
) -> float:
    build_risk = max(0, (0.90 - build_success_rate) * 300)   # 90% = 0 risk; 60% = 90 risk
    freq_risk = max(0, (2.0 - deploy_freq_per_week) * 25)    # <2/week adds risk
    trend_penalty = 20 if trend_direction == "worsening" else 0
    return min(100.0, build_risk + freq_risk + trend_penalty)
```

### Volatility Penalty

```python
def apply_volatility_penalty(base_score: float, cv: float) -> float:
    """
    Penalize unstable metrics. CV = coefficient of variation (std/mean).
    Unstable metrics are harder to improve predictably.
    cv > 0.5 = high volatility
    """
    if cv > 0.5:
        return min(100.0, base_score * 1.2)  # +20% penalty for high volatility
    return base_score
```

---

## Opportunity Scoring Engine

```python
def compute_opportunity_score(
    trend_improvement_rate: float,    # % improvement per week (positive = improving)
    target_gap_pct: float,            # How much gap remains to target (0.0 = hit, 1.0 = no progress)
    impact_weight: float,             # Strategic importance (0.0-1.0)
    effort_estimate: float,           # Estimated effort (1.0 = low, 3.0 = high)
) -> float:
    """
    Higher score = better opportunity (high improvement rate × large gap × high impact × low effort).
    Returns 0-100.
    """
    raw = (trend_improvement_rate * 100) * target_gap_pct * impact_weight * (1.0 / effort_estimate)
    return min(100.0, max(0.0, raw))

def describe_opportunity(project: str, opportunity: "OpportunityScore") -> str:
    """Formats as human-readable opportunity description."""
    return (
        f"Focusing on {project} could close target gap "
        f"by {opportunity.projected_weeks_saved:.1f} weeks "
        f"with {opportunity.effort_label} effort."
    )
```

---

## Trend Strength Scoring

```python
from scipy.stats import linregress

def compute_trend_strength(series: list[float], window: int = 8) -> dict:
    """
    Returns 4-dimensional trend assessment.
    window: number of recent weeks to assess.
    """
    recent = series[-window:]
    x = list(range(len(recent)))

    slope, intercept, r_value, p_value, _ = linregress(x, recent)

    # Direction
    direction = "improving" if slope < 0 else "worsening" if slope > 0 else "flat"
    # (For metrics where lower is better — bugs, vulns. Invert for deployments.)

    # Strength (R²)
    strength = r_value ** 2  # 0.0-1.0; higher = more linear/persistent

    # Momentum (is rate of change accelerating?)
    if len(series) >= window * 2:
        prior = series[-window*2:-window]
        prior_slope, *_ = linregress(range(len(prior)), prior)
        momentum = "accelerating" if abs(slope) > abs(prior_slope) else "decelerating"
    else:
        momentum = "unknown"

    # Reliability (volatility-adjusted confidence)
    import numpy as np
    cv = np.std(recent) / max(abs(np.mean(recent)), 0.001)
    reliability = max(0.0, strength - cv * 0.3)  # Penalize volatile series

    return {
        "direction": direction,
        "strength": round(strength, 3),     # 0.0-1.0
        "momentum": momentum,
        "reliability": round(reliability, 3),  # 0.0-1.0
        "trend_score": round(strength * reliability * 100, 1),  # 0-100
    }
```

---

## Insight Generation (Template-Based v1)

### Template Registry

```python
INSIGHT_TEMPLATES = {
    "anomaly_spike": (
        "⚠️ {metric} spiked {delta_pct:+.0f}% this week. "
        "Primary driver: {top_dimension} ({dim_delta:+.0f}%)."
    ),
    "anomaly_drop": (
        "⚠️ {metric} dropped {delta_pct:.0f}% this week. "
        "Primary driver: {top_dimension} ({dim_delta:.0f}% of total change)."
    ),
    "trend_reversal": (
        "🔄 {metric} trend reversed as of week {week_of_reversal}. "
        "Previously {prior_direction} for {prior_weeks} consecutive weeks."
    ),
    "target_risk": (
        "🎯 At current pace, {target_name} will be missed by {miss_amount} "
        "({miss_date}). Need {required_rate} {metric_unit}/week vs current {actual_rate}."
    ),
    "target_on_track": (
        "✅ {target_name} on track. At current pace, will reach target "
        "{weeks_early:.0f} weeks early ({projected_date})."
    ),
    "opportunity": (
        "💡 {project} improving at {improvement_rate:.1f}%/week — "
        "fastest mover in portfolio. Replicating approach could lift org by {org_impact}."
    ),
    "stability_alert": (
        "⚡ {metric} showing high week-to-week variation (volatility: {cv:.0%}). "
        "Forecasts unreliable until pattern stabilizes."
    ),
}

def format_insight(template_key: str, **kwargs) -> str:
    template = INSIGHT_TEMPLATES.get(template_key)
    if not template:
        raise ValueError(f"Unknown insight template: {template_key}")
    return template.format(**kwargs)
```

---

## Predictive Alerts (Before-Threshold Pattern)

```python
from dataclasses import dataclass
from execution.domain.intelligence import ForecastResult

@dataclass
class PredictiveAlert:
    metric: str
    project: str
    message: str
    weeks_to_breach: int | None
    confidence: float       # 0.0-1.0
    recommended_action: str
    severity: str           # "critical" | "high" | "medium"

def check_predictive_breach(
    forecast: ForecastResult,
    threshold: float,
    metric_name: str,
    project: str,
) -> PredictiveAlert | None:
    """
    Returns alert if metric is forecast to breach threshold within 8 weeks.
    Only fires if breach probability > 0.60 (reduces alert fatigue).
    """
    HORIZON_WEEKS = 8
    CONFIDENCE_THRESHOLD = 0.60

    # Check each forecast week
    for i, week_forecast in enumerate(forecast.forecast_weeks[:HORIZON_WEEKS]):
        p50 = week_forecast["p50"]
        p90 = week_forecast["p90"]

        # Estimate probability of breach using P50/P90 spread
        if p50 > threshold:
            confidence = 0.90  # P50 breaches = very likely
        elif p90 > threshold:
            # Interpolate between P50 and P90
            confidence = 0.5 + 0.4 * (p90 - threshold) / (p90 - p50 + 0.001)
        else:
            continue

        if confidence >= CONFIDENCE_THRESHOLD:
            severity = "critical" if confidence > 0.85 else "high"
            return PredictiveAlert(
                metric=metric_name,
                project=project,
                message=(
                    f"On current trajectory, {metric_name} in {project} will breach "
                    f"threshold in ~{i+1} weeks ({confidence:.0%} confidence)."
                ),
                weeks_to_breach=i + 1,
                confidence=confidence,
                recommended_action=_get_recommended_action(metric_name, "worsening"),
                severity=severity,
            )

    return None
```

---

## Causal Decomposition (Root Cause Attribution)

```python
def attribute_metric_delta(
    total_delta: float,
    by_dimension: dict[str, float],  # e.g., {"Pipeline_A": -15.0, "Pipeline_B": -3.0, ...}
) -> list[dict]:
    """
    Returns dimensions sorted by contribution to total delta.
    Each item: {"dimension": str, "contribution": float, "contribution_pct": float}
    """
    if abs(total_delta) < 0.001:
        return []

    contributions = []
    for dim, dim_delta in by_dimension.items():
        contribution_pct = dim_delta / total_delta if total_delta != 0 else 0
        contributions.append({
            "dimension": dim,
            "contribution": dim_delta,
            "contribution_pct": round(contribution_pct * 100, 1),
        })

    # Sort by absolute contribution (largest first)
    return sorted(contributions, key=lambda x: abs(x["contribution"]), reverse=True)

def format_root_cause(contributions: list[dict], threshold_pct: float = 20.0) -> str:
    """Human-readable root cause string for the top contributors."""
    top = [c for c in contributions if abs(c["contribution_pct"]) >= threshold_pct]
    if not top:
        top = contributions[:2]  # Always show at least top 2

    parts = [f"{c['dimension']} ({c['contribution_pct']:+.0f}%)" for c in top]
    return "Primary drivers: " + ", ".join(parts)
```

---

## Recommended Actions Engine

```python
from dataclasses import dataclass

@dataclass
class RecommendedAction:
    title: str
    description: str
    effort: str       # "low" | "medium" | "high"
    impact: str       # "low" | "medium" | "high"
    metric: str
    dashboard_url: str | None = None

ACTION_RULES = [
    {
        "condition": lambda m: m.get("build_success_rate", 1.0) < 0.80 and m.get("build_trend") == "worsening",
        "action": RecommendedAction(
            title="Investigate pipeline failures",
            description="Build success rate below 80% and declining. Review {top_failing_pipeline}.",
            effort="low",
            impact="high",
            metric="deployment",
            dashboard_url="/observatory/deployment",
        ),
    },
    {
        "condition": lambda m: m.get("target_gap_pct", 0) > 0.20 and m.get("weeks_to_target", 99) < 8,
        "action": RecommendedAction(
            title="Accelerate security triage",
            description="Security target at risk. Triaging {n_critical} critical vulns in {top_product} would close gap.",
            effort="high",
            impact="high",
            metric="security",
            dashboard_url="/observatory/security",
        ),
    },
    {
        "condition": lambda m: m.get("wip", 0) > m.get("wip_limit", 999),
        "action": RecommendedAction(
            title="Enforce WIP limits",
            description="WIP in {product} exceeds healthy threshold. Lead time degradation expected in {n_weeks} weeks.",
            effort="medium",
            impact="high",
            metric="flow",
            dashboard_url="/observatory/flow",
        ),
    },
]

def generate_recommendations(metrics: dict) -> list[RecommendedAction]:
    """Returns recommended actions sorted by impact↑/effort↓."""
    triggered = [rule["action"] for rule in ACTION_RULES if rule["condition"](metrics)]
    effort_order = {"low": 0, "medium": 1, "high": 2}
    impact_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(
        triggered,
        key=lambda a: (impact_order[a.impact], effort_order[a.effort])
    )
```

---

## Domain Models

```python
# execution/domain/intelligence.py
from dataclasses import dataclass, field
from execution.domain.base import MetricSnapshot

@dataclass(kw_only=True)
class RiskScore(MetricSnapshot):
    project: str
    composite_score: float          # 0-100
    vuln_component: float
    quality_component: float
    deployment_component: float
    flow_component: float
    ownership_component: float
    primary_driver: str             # Which component is highest

    @property
    def status(self) -> str:
        if self.composite_score >= 70: return "Critical"
        if self.composite_score >= 40: return "At Risk"
        return "Healthy"

    @property
    def status_class(self) -> str:
        if self.composite_score >= 70: return "action"
        if self.composite_score >= 40: return "caution"
        return "good"

    @classmethod
    def from_json(cls, data: dict) -> "RiskScore":
        return cls(
            timestamp=data["timestamp"],
            project=data["project"],
            composite_score=data["composite_score"],
            vuln_component=data["vuln_component"],
            quality_component=data["quality_component"],
            deployment_component=data["deployment_component"],
            flow_component=data["flow_component"],
            ownership_component=data["ownership_component"],
            primary_driver=data["primary_driver"],
        )
```

---

## Key Insight: No Noise, Only Signal

The intelligence layer must actively suppress noise:
- **Predictive alerts**: Only fire if confidence > 60% (reduces alert fatigue)
- **Trend reversals**: Only flag if change-point has >80% confidence
- **Opportunity scores**: Only surface top 3 (more = noise)
- **Anomalies**: Root cause required before surfacing (never "anomaly detected" with no context)
- **Recommendations**: Max 3 actions; always include effort/impact label
