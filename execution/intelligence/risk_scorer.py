"""
Risk Scorer — execution/intelligence/risk_scorer.py

Single responsibility: Computes composite risk scores for projects from feature DataFrames.

Risk formula (weights from intelligence-layer skill):
    composite = 0.35 * vuln_risk + 0.25 * quality_risk + 0.20 * deployment_risk
              + 0.15 * flow_risk + 0.05 * ownership_risk

Each component returns a float in [0, 100]. Higher = more risk.
Missing data defaults to 50.0 (neutral / unknown risk).

Produced output: RiskScore domain objects (from execution.domain.intelligence).
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import linregress

from execution.core.logging_config import get_logger
from execution.domain.intelligence import RiskScore, RiskScoreComponent
from execution.intelligence.feature_engineering import VALID_METRICS, load_features
from execution.security.path_validator import PathValidator
from execution.security.validation import ValidationError

logger: logging.Logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Weights (must sum to 1.0)
# ---------------------------------------------------------------------------

_WEIGHTS: dict[str, float] = {
    "vuln_risk": 0.35,
    "quality_risk": 0.25,
    "deployment_risk": 0.20,
    "flow_risk": 0.15,
    "ownership_risk": 0.05,
}

# Neutral score used when a metric domain has no data
_NEUTRAL_SCORE: float = 50.0

# Minimum data points required to compute a reliable trend
_MIN_POINTS: int = 3

# Regression window: use last N unique data points for trend calculation
_TREND_WINDOW: int = 8


# ---------------------------------------------------------------------------
# Internal trend helpers
# ---------------------------------------------------------------------------


def _extract_unique_series(df: pd.DataFrame, col: str) -> list[float]:
    """
    Return a deduplicated, chronologically ordered value series for one column.

    Drops NaN rows and de-duplicates by (week_date, value) so that the same
    snapshot ingested multiple times does not artificially inflate confidence.
    """
    if col not in df.columns or df.empty:
        return []

    sub = df[["week_date", col]].dropna(subset=[col]).copy()
    if sub.empty:
        return []

    # Keep one row per week (latest within each week if duplicates exist)
    sub = sub.sort_values("week_date").drop_duplicates(subset=["week_date"], keep="last")
    return [float(v) for v in sub[col].tolist()]


def _compute_slope(series: list[float], window: int = _TREND_WINDOW) -> float:
    """
    Compute the OLS slope over the last `window` observations.

    Returns 0.0 when insufficient data is available.
    A positive slope means the metric is increasing; negative means decreasing.
    """
    recent = series[-window:] if len(series) >= window else series
    if len(recent) < _MIN_POINTS:
        return 0.0

    x = list(range(len(recent)))
    slope, *_ = linregress(x, recent)
    return float(slope)


def _apply_volatility_penalty(base_score: float, series: list[float]) -> float:
    """
    Penalise highly volatile metrics (CV > 0.5) by 20%.

    CV = coefficient of variation (std / |mean|).  Volatile metrics are harder
    to improve predictably so they earn a slightly higher risk score.
    """
    if len(series) < _MIN_POINTS:
        return base_score

    mean_val = float(np.mean(series))
    std_val = float(np.std(series))
    cv = std_val / max(abs(mean_val), 0.001)

    if cv > 0.5:
        return min(100.0, base_score * 1.2)
    return base_score


# ---------------------------------------------------------------------------
# Component scorers — each returns float in [0, 100]
# ---------------------------------------------------------------------------


def score_security_risk(df: pd.DataFrame) -> float:
    """
    Compute vuln_risk component (0-100) from security feature DataFrame.

    Uses total_vulnerabilities trend and critical count.
    Higher vulnerability counts and worsening trends produce higher risk.

    The portfolio row (_portfolio) is used when present; otherwise the mean
    across all product rows is used.
    """
    if df.empty:
        return _NEUTRAL_SCORE

    # Prefer portfolio-level row for a single representative series
    portfolio = df[df["project"] == "_portfolio"] if "project" in df.columns else df
    working_df = portfolio if not portfolio.empty else df

    vuln_series = _extract_unique_series(working_df, "total_vulnerabilities")
    critical_series = _extract_unique_series(working_df, "critical")

    if not vuln_series:
        return _NEUTRAL_SCORE

    current_vulns = float(vuln_series[-1]) if vuln_series else 0.0
    current_critical = float(critical_series[-1]) if critical_series else 0.0

    # Base risk: scale raw vuln count (calibrated to portfolio range ~2k-13k)
    base = min(70.0, current_vulns / 200.0)

    # Critical count adds up to 20 points (calibrated: ~500 criticals = 15 pts)
    critical_points = min(20.0, current_critical * 0.04)

    # Trend penalty: worsening trend (positive slope) adds up to 10 points
    slope = _compute_slope(vuln_series)
    trend_penalty = min(10.0, max(0.0, slope * 0.5)) if slope > 0 else 0.0

    raw_score = base + critical_points + trend_penalty
    raw_score = _apply_volatility_penalty(raw_score, vuln_series)
    return round(min(100.0, max(0.0, raw_score)), 2)


def score_quality_risk(df: pd.DataFrame) -> float:
    """
    Compute quality_risk component (0-100) from quality feature DataFrame.

    Uses open_bugs trend, p1_bugs count, and median bug age.
    Worsening trends and aging backlogs produce higher risk.
    """
    if df.empty:
        return _NEUTRAL_SCORE

    bug_series = _extract_unique_series(df, "open_bugs")
    p1_series = _extract_unique_series(df, "p1_bugs")
    age_series = _extract_unique_series(df, "median_age_days")

    if not bug_series:
        return _NEUTRAL_SCORE

    current_bugs = float(bug_series[-1])

    # Base risk: bug count scaled (calibrated: 100 bugs ~20pts, 500 bugs ~70pts)
    base = min(70.0, current_bugs * 0.15)

    # P1 penalty: each P1 = 3 risk points, up to 20 points
    current_p1 = float(p1_series[-1]) if p1_series else 0.0
    p1_points = min(20.0, current_p1 * 3.0)

    # Age penalty: bugs older than 90 days add up to 10 points
    current_age = float(age_series[-1]) if age_series else 0.0
    age_points = min(10.0, max(0.0, (current_age - 90.0) * 0.02))

    # Trend multiplier: worsening trend (positive slope on bugs) adds 30%
    slope = _compute_slope(bug_series)
    trend_mult = 1.3 if slope > 0 else 1.0

    raw_score = (base + p1_points + age_points) * trend_mult
    raw_score = _apply_volatility_penalty(raw_score, bug_series)
    return round(min(100.0, max(0.0, raw_score)), 2)


def score_deployment_risk(df: pd.DataFrame) -> float:
    """
    Compute deployment_risk component (0-100) from deployment feature DataFrame.

    Uses build_success_rate trend and deploy_frequency.
    Low success rate and worsening frequency produce higher risk.

    Note: build_success_rate in the feature store is stored as a percentage
    (0-100), not a fraction (0.0-1.0).
    """
    if df.empty:
        return _NEUTRAL_SCORE

    success_series = _extract_unique_series(df, "build_success_rate")
    freq_series = _extract_unique_series(df, "deploy_frequency")

    if not success_series:
        return _NEUTRAL_SCORE

    current_rate = float(success_series[-1])

    # Build risk: 90% = 0 risk; 60% = 90 risk (formula from intelligence-layer.md)
    # Feature store stores as percentage so convert to fraction first
    rate_fraction = current_rate / 100.0
    build_risk = max(0.0, (0.90 - rate_fraction) * 300.0)

    # Frequency risk: < 2 deployments/week adds risk, up to 50 points
    current_freq = float(freq_series[-1]) if freq_series else 2.0
    freq_risk = max(0.0, (2.0 - current_freq) * 25.0) if current_freq < 2.0 else 0.0

    # Trend penalty: worsening success rate (negative slope) adds 20 points
    slope = _compute_slope(success_series)
    trend_penalty = 20.0 if slope < 0 else 0.0

    raw_score = build_risk + freq_risk + trend_penalty
    raw_score = _apply_volatility_penalty(raw_score, success_series)
    return round(min(100.0, max(0.0, raw_score)), 2)


def score_flow_risk(df: pd.DataFrame) -> float:
    """
    Compute flow_risk component (0-100) from flow feature DataFrame.

    Uses lead_time_p85 trend and WIP level.
    High WIP and worsening lead time produce higher risk.
    """
    if df.empty:
        return _NEUTRAL_SCORE

    lead_series = _extract_unique_series(df, "lead_time_p85")
    wip_series = _extract_unique_series(df, "wip")

    if not lead_series and not wip_series:
        return _NEUTRAL_SCORE

    # WIP risk: calibrated to observed range (50-500 items)
    current_wip = float(wip_series[-1]) if wip_series else 0.0
    wip_risk = min(50.0, current_wip * 0.10)

    # Lead time risk: > 30 days = elevated, > 200 days = high risk
    current_lead = float(lead_series[-1]) if lead_series else 0.0
    lead_risk = min(40.0, max(0.0, (current_lead - 30.0) * 0.15))

    # Trend penalty: worsening lead time (positive slope) adds 10 points
    slope = _compute_slope(lead_series) if lead_series else 0.0
    trend_penalty = min(10.0, max(0.0, slope * 0.1)) if slope > 0 else 0.0

    raw_score = wip_risk + lead_risk + trend_penalty
    series_for_vol = lead_series if lead_series else wip_series
    raw_score = _apply_volatility_penalty(raw_score, series_for_vol)
    return round(min(100.0, max(0.0, raw_score)), 2)


def score_ownership_risk(df: pd.DataFrame) -> float:
    """
    Compute ownership_risk component (0-100) from ownership feature DataFrame.

    Uses unassigned_pct trend.
    High and worsening unassigned percentages produce higher risk.
    """
    if df.empty:
        return _NEUTRAL_SCORE

    pct_series = _extract_unique_series(df, "unassigned_pct")

    if not pct_series:
        return _NEUTRAL_SCORE

    current_pct = float(pct_series[-1])

    # Base risk: 0% unassigned = 0 risk; 100% unassigned = 80 risk
    base = min(80.0, current_pct * 0.80)

    # Trend multiplier: worsening trend (positive slope) adds 30%
    slope = _compute_slope(pct_series)
    trend_mult = 1.3 if slope > 0 else 1.0

    raw_score = base * trend_mult
    raw_score = _apply_volatility_penalty(raw_score, pct_series)
    return round(min(100.0, max(0.0, raw_score)), 2)


# ---------------------------------------------------------------------------
# Composite scorer
# ---------------------------------------------------------------------------


def _compute_composite(components: dict[str, float]) -> float:
    """Apply weights and return composite score in [0, 100]."""
    raw = (
        _WEIGHTS["vuln_risk"] * components["vuln_risk"]
        + _WEIGHTS["quality_risk"] * components["quality_risk"]
        + _WEIGHTS["deployment_risk"] * components["deployment_risk"]
        + _WEIGHTS["flow_risk"] * components["flow_risk"]
        + _WEIGHTS["ownership_risk"] * components["ownership_risk"]
    )
    return round(min(100.0, max(0.0, raw)), 2)


def _identify_primary_driver(components: dict[str, float]) -> str:
    """Return the name of the highest-scoring (riskiest) component."""
    return max(components, key=lambda k: components[k])


def _load_project_df(
    metric: str,
    project: str,
    feature_dir: Path,
) -> pd.DataFrame | None:
    """
    Load a per-project feature DataFrame.  Returns None on any load error.

    Security metrics use the _portfolio row, which does not correspond to
    a named project; for those we return the full portfolio DataFrame.
    """
    try:
        if metric == "security":
            df = load_features(metric, project=None, base_dir=feature_dir)
            # Return only the portfolio-level row for cross-project comparability
            portfolio = df[df["project"] == "_portfolio"]
            return portfolio if not portfolio.empty else df
        return load_features(metric, project=project, base_dir=feature_dir)
    except ValueError as e:
        logger.warning(
            "Feature load failed — using neutral score",
            extra={"metric": metric, "project": project, "error": str(e)},
        )
        return None


def compute_project_risk(
    project: str,
    feature_dir: Path = Path("data/features"),
) -> RiskScore:
    """
    Compute composite risk score for a single project.

    Loads feature DataFrames for each metric domain, calls component scorers,
    applies weights, and returns a RiskScore domain object.

    Missing metric data is handled gracefully: a neutral score of 50.0 is
    used for any component whose feature file cannot be loaded.

    Args:
        project: Generic project name (e.g. "Product_A").
        feature_dir: Directory containing Parquet feature files.

    Returns:
        RiskScore with per-component breakdown and composite total.
    """
    metric_to_scorer = {
        "security": score_security_risk,
        "quality": score_quality_risk,
        "deployment": score_deployment_risk,
        "flow": score_flow_risk,
        "ownership": score_ownership_risk,
    }

    component_name_map = {
        "security": "vuln_risk",
        "quality": "quality_risk",
        "deployment": "deployment_risk",
        "flow": "flow_risk",
        "ownership": "ownership_risk",
    }

    raw_components: dict[str, float] = {}

    for metric, scorer in metric_to_scorer.items():
        df = _load_project_df(metric, project, feature_dir)
        component_name = component_name_map[metric]

        if df is None or df.empty:
            raw_components[component_name] = _NEUTRAL_SCORE
            logger.info(
                "No data for component — using neutral score",
                extra={"project": project, "component": component_name},
            )
        else:
            raw_components[component_name] = scorer(df)

    composite = _compute_composite(raw_components)
    primary_driver = _identify_primary_driver(raw_components)

    components = [
        RiskScoreComponent(
            name=name,
            raw_score=score,
            weight=_WEIGHTS[name],
            weighted=round(score * _WEIGHTS[name], 2),
        )
        for name, score in raw_components.items()
    ]

    logger.info(
        "Risk score computed",
        extra={
            "project": project,
            "composite": composite,
            "primary_driver": primary_driver,
        },
    )

    return RiskScore(
        project=project,
        total=composite,
        components=components,
    )


def compute_all_risks(
    feature_dir: Path = Path("data/features"),
) -> list[RiskScore]:
    """
    Compute risk scores for all projects found in the feature store.

    Discovers projects by reading the quality feature file (the broadest
    cross-project dataset).  Falls back to deployment if quality is missing.

    Returns:
        List of RiskScore objects, one per project, sorted by total score
        descending (highest risk first).
    """
    projects = _discover_projects(feature_dir)

    if not projects:
        logger.warning("No projects discovered — returning empty risk list")
        return []

    scores: list[RiskScore] = []
    for project in projects:
        try:
            score = compute_project_risk(project, feature_dir=feature_dir)
            scores.append(score)
        except Exception as e:  # noqa: BLE001
            logger.error(
                "Failed to compute risk for project",
                extra={"project": project, "error": str(e)},
            )

    scores.sort(key=lambda r: r.total, reverse=True)
    logger.info(
        "All risk scores computed",
        extra={"project_count": len(scores)},
    )
    return scores


def _discover_projects(feature_dir: Path) -> list[str]:
    """
    Return the list of distinct generic project names from the feature store.

    Tries quality first, then deployment, then ownership as fallback sources.
    Excludes internal sentinel values such as "_portfolio".
    """
    for metric in ("quality", "deployment", "ownership"):
        try:
            df = load_features(metric, project=None, base_dir=feature_dir)
            if "project" in df.columns and not df.empty:
                projects = [p for p in df["project"].dropna().unique().tolist() if not str(p).startswith("_")]
                if projects:
                    logger.info(
                        "Projects discovered",
                        extra={"source_metric": metric, "count": len(projects)},
                    )
                    return sorted(projects)
        except ValueError:
            continue

    return []


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_risk_scores(
    scores: list[RiskScore],
    base_dir: Path = Path("data/insights"),
) -> Path:
    """
    Serialise risk scores to a JSON file in base_dir.

    Uses PathValidator to prevent path traversal.

    Args:
        scores: List of RiskScore objects to persist.
        base_dir: Output directory (created if absent).

    Returns:
        Absolute Path of the written JSON file.

    Raises:
        ValidationError: If the resolved output path escapes base_dir.
    """
    base_dir.mkdir(parents=True, exist_ok=True)

    filename = f"risk_scores_{datetime.now().strftime('%Y-%m-%d')}.json"

    safe_path_str = PathValidator.validate_safe_path(
        base_dir=str(base_dir.resolve()),
        user_path=filename,
    )
    output_path = Path(safe_path_str)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "scores": [
            {
                "project": s.project,
                "total": s.total,
                "level": s.level,
                "status": s.status,
                "components": [
                    {
                        "name": c.name,
                        "raw_score": c.raw_score,
                        "weight": c.weight,
                        "weighted": c.weighted,
                    }
                    for c in s.components
                ],
            }
            for s in scores
        ],
    }

    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info(
        "Risk scores saved",
        extra={"path": str(output_path), "count": len(scores)},
    )
    return output_path
