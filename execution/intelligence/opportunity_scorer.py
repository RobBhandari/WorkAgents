"""
Opportunity Scorer — execution/intelligence/opportunity_scorer.py

Single responsibility: Identifies improvement opportunities from feature DataFrames.

Opportunity scoring formula (from intelligence-layer skill):
    opportunity = trend_improvement_rate × target_gap × impact_weight × (1/effort)

An "opportunity" is a project/metric combination showing either:
  - strong improvement momentum (best to replicate), or
  - a large gap with any positive movement (highest leverage for org score).

Returned as OpportunityScore dataclasses — defined here as an intelligence-layer
concept, NOT in domain/intelligence.py (which holds domain models only).
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import linregress

from execution.core.logging_config import get_logger
from execution.intelligence.feature_engineering import VALID_METRICS, load_features

logger: logging.Logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# OpportunityScore — intelligence-layer concept (not a domain model)
# ---------------------------------------------------------------------------


@dataclass
class OpportunityScore:
    """
    Scored improvement opportunity for a single project/metric combination.

    Attributes:
        project:            Generic project name (e.g. "Product_A").
        metric:             Metric domain (e.g. "open_bugs").
        opportunity_score:  0-100 composite opportunity score.
        trend_direction:    "improving" | "worsening" | "flat".
        improvement_rate:   Rate of change per observation (positive = improving).
        description:        Human-readable insight string.
        recommended_action: One specific, actionable step.
    """

    project: str
    metric: str
    opportunity_score: float
    trend_direction: str
    improvement_rate: float
    description: str
    recommended_action: str


# ---------------------------------------------------------------------------
# Description templates
# ---------------------------------------------------------------------------

OPPORTUNITY_TEMPLATES: dict[str, str] = {
    "improving_fast": ("{project} {metric} improving at {rate:.1f}% per week — fastest mover."),
    "improving_steady": ("{project} {metric} on improving trend — {weeks} weeks consistent."),
    "large_gap": ("{project} {metric} has large gap — " "reducing would significantly improve org score."),
    "flat_potential": ("{project} {metric} flat — " "small push could convert to consistent improvement."),
}

# ---------------------------------------------------------------------------
# Per-metric configuration
# ---------------------------------------------------------------------------

# Metrics to score, with column name, direction, impact weight, and effort estimate
_METRIC_CONFIG: list[dict] = [
    {
        "feature_name": "quality",
        "column": "open_bugs",
        "lower_is_better": True,
        "impact_weight": 0.9,
        "effort": 1.5,
        "label": "open bugs",
        "action": "Triage oldest open bugs and close resolved items to reduce backlog.",
    },
    {
        "feature_name": "deployment",
        "column": "build_success_rate",
        "lower_is_better": False,  # higher success rate is better
        "impact_weight": 0.8,
        "effort": 2.0,
        "label": "build success rate",
        "action": "Review top failing pipelines and fix flaky tests to raise success rate.",
    },
    {
        "feature_name": "flow",
        "column": "lead_time_p85",
        "lower_is_better": True,
        "impact_weight": 0.7,
        "effort": 2.5,
        "label": "lead time (p85)",
        "action": "Reduce WIP and focus on completing in-flight work to cut lead time.",
    },
    {
        "feature_name": "ownership",
        "column": "unassigned_pct",
        "lower_is_better": True,
        "impact_weight": 0.6,
        "effort": 1.0,
        "label": "unassigned work pct",
        "action": "Run a triage session to assign open items and reduce unassigned backlog.",
    },
]

# Minimum weeks of data required to produce a meaningful score
_MIN_POINTS: int = 3

# Trend window (number of most-recent data points used for regression)
_TREND_WINDOW: int = 8


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_series(df: pd.DataFrame, col: str) -> list[float]:
    """
    Return a deduplicated, chronologically ordered value list for one column.

    Drops NaN, de-duplicates by week_date (keeps latest within each week).
    """
    if col not in df.columns or df.empty:
        return []

    sub = df[["week_date", col]].dropna(subset=[col]).copy()
    if sub.empty:
        return []

    sub = sub.sort_values("week_date").drop_duplicates(subset=["week_date"], keep="last")
    return [float(v) for v in sub[col].tolist()]


def _compute_trend(
    series: list[float],
    lower_is_better: bool,
    window: int = _TREND_WINDOW,
) -> tuple[str, float]:
    """
    Compute trend direction and normalised improvement rate.

    Returns:
        (direction, improvement_rate_pct_per_week)

    improvement_rate is positive when the metric is improving, regardless of
    whether lower_is_better or higher_is_better is selected.
    """
    recent = series[-window:] if len(series) >= window else series

    if len(recent) < _MIN_POINTS:
        return "flat", 0.0

    x = list(range(len(recent)))
    slope, *_ = linregress(x, recent)
    slope = float(slope)

    mean_val = float(np.mean(recent))
    if abs(mean_val) < 0.001:
        pct_per_week = 0.0
    else:
        pct_per_week = abs(slope) / abs(mean_val) * 100.0

    # For lower_is_better metrics, a negative slope means improvement
    if lower_is_better:
        improving = slope < 0
    else:
        improving = slope > 0

    direction = "improving" if improving else ("worsening" if slope != 0 else "flat")
    improvement_rate = pct_per_week if improving else -pct_per_week

    return direction, round(improvement_rate, 4)


def _compute_target_gap(series: list[float], lower_is_better: bool) -> float:
    """
    Estimate target gap as a fraction [0.0, 1.0].

    Uses the best observed value as a proxy for the target.
    A gap of 1.0 means no progress; 0.0 means at or past target.
    """
    if not series:
        return 0.5  # Unknown

    current = series[-1]
    best = min(series) if lower_is_better else max(series)
    worst = max(series) if lower_is_better else min(series)

    span = abs(worst - best)
    if span < 0.001:
        return 0.0  # No variation → effectively at target

    if lower_is_better:
        gap = (current - best) / span
    else:
        gap = (best - current) / span

    return round(max(0.0, min(1.0, float(gap))), 4)


def _choose_template(
    direction: str,
    improvement_rate: float,
    weeks_improving: int,
) -> str:
    """Select the most appropriate description template key."""
    if direction == "improving" and abs(improvement_rate) >= 1.0:
        return "improving_fast"
    if direction == "improving":
        return "improving_steady"
    if direction == "flat":
        return "flat_potential"
    return "large_gap"


def _count_improving_weeks(series: list[float], lower_is_better: bool) -> int:
    """Count consecutive trailing weeks of improvement."""
    if len(series) < 2:
        return 0

    count = 0
    for i in range(len(series) - 1, 0, -1):
        delta = series[i] - series[i - 1]
        if lower_is_better:
            if delta < 0:
                count += 1
            else:
                break
        else:
            if delta > 0:
                count += 1
            else:
                break
    return count


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_opportunity(
    df: pd.DataFrame,
    metric_col: str,
    project: str,
    *,
    lower_is_better: bool = True,
    impact_weight: float = 1.0,
    effort: float = 1.5,
    label: str | None = None,
    recommended_action: str = "Review this metric and identify improvement levers.",
) -> OpportunityScore | None:
    """
    Score the improvement opportunity for a single metric/project.

    Returns None when there is insufficient data to produce a reliable score.

    Args:
        df:                 Feature DataFrame (already filtered to one project).
        metric_col:         Column name to analyse (e.g. "open_bugs").
        project:            Generic project name.
        lower_is_better:    True for bugs/vulns; False for success_rate/throughput.
        impact_weight:      Strategic importance 0.0-1.0.
        effort:             Effort estimate (1.0 = low, 3.0 = high).
        label:              Human-readable metric label.
        recommended_action: Specific action string.

    Returns:
        OpportunityScore or None if data is insufficient.
    """
    series = _extract_series(df, metric_col)

    if len(series) < _MIN_POINTS:
        logger.debug(
            "Insufficient data for opportunity scoring",
            extra={"project": project, "metric": metric_col, "points": len(series)},
        )
        return None

    direction, improvement_rate = _compute_trend(series, lower_is_better)
    target_gap = _compute_target_gap(series, lower_is_better)

    # Improvement rate used in the formula is the absolute % change per week
    abs_rate = abs(improvement_rate) / 100.0  # convert pct → fraction

    # Formula: opportunity = trend_improvement_rate × target_gap × impact_weight / effort
    raw = abs_rate * target_gap * impact_weight * (1.0 / max(effort, 0.1))

    # Worsening metrics get a reduced opportunity score (gap exists but no momentum)
    if direction == "worsening":
        raw *= 0.4

    opp_score = round(min(100.0, max(0.0, raw * 100.0)), 2)

    metric_label = label or metric_col
    weeks_improving = _count_improving_weeks(series, lower_is_better)
    template_key = _choose_template(direction, improvement_rate, weeks_improving)

    description = OPPORTUNITY_TEMPLATES[template_key].format(
        project=project,
        metric=metric_label,
        rate=abs(improvement_rate),
        weeks=weeks_improving,
    )

    return OpportunityScore(
        project=project,
        metric=metric_label,
        opportunity_score=opp_score,
        trend_direction=direction,
        improvement_rate=improvement_rate,
        description=description,
        recommended_action=recommended_action,
    )


def find_top_opportunities(
    feature_dir: Path = Path("data/features"),
    top_n: int = 5,
) -> list[OpportunityScore]:
    """
    Find the top N improvement opportunities across all projects and metrics.

    Iterates over the configured metric domains, loads per-project DataFrames,
    and scores each project/metric combination.  Returns the top_n results
    sorted by opportunity_score descending.

    Args:
        feature_dir: Directory containing Parquet feature files.
        top_n:       Maximum number of opportunities to return.

    Returns:
        List of OpportunityScore objects, sorted by score descending.
        May contain fewer than top_n entries if data is sparse.
    """
    all_scores: list[OpportunityScore] = []

    for cfg in _METRIC_CONFIG:
        feature_name = cfg["feature_name"]
        column = cfg["column"]

        try:
            full_df = load_features(feature_name, project=None, base_dir=feature_dir)
        except ValueError as e:
            logger.warning(
                "Cannot load feature file — skipping metric",
                extra={"metric": feature_name, "error": str(e)},
            )
            continue

        if "project" not in full_df.columns or full_df.empty:
            continue

        projects = [p for p in full_df["project"].dropna().unique().tolist() if not str(p).startswith("_")]

        for project in projects:
            project_df = full_df[full_df["project"] == project].copy()
            if project_df.empty:
                continue

            opp = score_opportunity(
                df=project_df,
                metric_col=column,
                project=project,
                lower_is_better=bool(cfg["lower_is_better"]),
                impact_weight=float(cfg["impact_weight"]),
                effort=float(cfg["effort"]),
                label=cfg["label"],
                recommended_action=cfg["action"],
            )

            if opp is not None:
                all_scores.append(opp)

    all_scores.sort(key=lambda o: o.opportunity_score, reverse=True)
    top = all_scores[:top_n]

    logger.info(
        "Top opportunities identified",
        extra={"total_scored": len(all_scores), "returned": len(top)},
    )
    return top
