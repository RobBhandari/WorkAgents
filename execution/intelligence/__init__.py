"""
Intelligence Platform — execution/intelligence/

Predictive analytics engine for the WorkAgents Observatory.

Public API (import from here for cross-module use):

    from execution.intelligence import (
        load_features, VALID_METRICS,         # feature store
        forecast_metric, compute_trend_strength,  # forecasting
        detect_anomalies,                     # anomaly detection
        detect_change_points,                 # change-point detection
        compute_project_risk, compute_all_risks,  # risk scoring
        find_top_opportunities,               # opportunity scoring
    )

Modules:
    feature_engineering  — Parquet feature store built from history JSON
    duckdb_views         — Analytical SQL views over JSON/Parquet (in-memory DuckDB)
    forecast_engine      — P10/P50/P90 forecasting (linear regression + confidence intervals)
    anomaly_detector     — Isolation Forest + z-score anomaly detection
    change_point_detector — ruptures PELT change-point detection
    risk_scorer          — Composite risk score (0-100) with 5 weighted components
    opportunity_scorer   — Improvement opportunity scoring

Phase:
    Phase B — Intelligence Foundation (Week 3-6)
"""

from execution.intelligence.anomaly_detector import detect_anomalies
from execution.intelligence.change_point_detector import detect_change_points
from execution.intelligence.feature_engineering import VALID_METRICS, load_features
from execution.intelligence.forecast_engine import compute_trend_strength, forecast_metric
from execution.intelligence.opportunity_scorer import find_top_opportunities
from execution.intelligence.risk_scorer import compute_all_risks, compute_project_risk

__all__ = [
    # Feature store
    "load_features",
    "VALID_METRICS",
    # Forecasting
    "forecast_metric",
    "compute_trend_strength",
    # Anomaly detection
    "detect_anomalies",
    # Change-point detection
    "detect_change_points",
    # Risk scoring
    "compute_project_risk",
    "compute_all_risks",
    # Opportunity scoring
    "find_top_opportunities",
]
