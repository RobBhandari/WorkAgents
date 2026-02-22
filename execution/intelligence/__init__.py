"""
Intelligence Platform — execution/intelligence/

Predictive analytics engine for the WorkAgents Observatory.

Public API (import from here for cross-module use):

    from execution.intelligence import (
        load_features, VALID_METRICS,              # feature store
        forecast_metric, compute_trend_strength,   # forecasting
        detect_anomalies,                          # anomaly detection
        detect_change_points,                      # change-point detection
        compute_project_risk, compute_all_risks,   # risk scoring
        find_top_opportunities,                    # opportunity scoring
        run_monte_carlo, compare_scenarios,        # Phase C: scenario simulation
        compute_correlation_matrix,                # Phase C: correlation analysis
        find_leading_indicators,                   # Phase C: correlation analysis
        decompose_delta, get_top_contributors,     # Phase C: causal analysis
        generate_insight, generate_template_insight,  # Phase C: insight generation
    )

Modules:
    feature_engineering   — Parquet feature store built from history JSON
    duckdb_views          — Analytical SQL views over JSON/Parquet (in-memory DuckDB)
    forecast_engine       — P10/P50/P90 forecasting (linear regression + confidence intervals)
    anomaly_detector      — Isolation Forest + z-score anomaly detection
    change_point_detector — ruptures PELT change-point detection
    risk_scorer           — Composite risk score (0-100) with 5 weighted components
    opportunity_scorer    — Improvement opportunity scoring
    scenario_simulator    — Monte Carlo scenario simulation (Phase C)
    correlation_analyzer  — Cross-metric Pearson correlation + leading indicators (Phase C)
    causal_analyzer       — Causal decomposition / root-cause attribution (Phase C)
    insight_generator     — Template-based and LLM-stub insight generation (Phase C)

Phase:
    Phase B — Intelligence Foundation (Week 3-6)
    Phase C — Predictive Platform (Week 7-10)
"""

from execution.intelligence.anomaly_detector import detect_anomalies
from execution.intelligence.causal_analyzer import decompose_delta, get_top_contributors
from execution.intelligence.change_point_detector import detect_change_points
from execution.intelligence.correlation_analyzer import compute_correlation_matrix, find_leading_indicators
from execution.intelligence.feature_engineering import VALID_METRICS, load_features
from execution.intelligence.forecast_engine import compute_trend_strength, forecast_metric
from execution.intelligence.insight_generator import generate_insight, generate_template_insight
from execution.intelligence.opportunity_scorer import find_top_opportunities
from execution.intelligence.risk_scorer import compute_all_risks, compute_project_risk
from execution.intelligence.scenario_simulator import compare_scenarios, run_monte_carlo

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
    # Phase C: Scenario simulation
    "run_monte_carlo",
    "compare_scenarios",
    # Phase C: Correlation analysis
    "compute_correlation_matrix",
    "find_leading_indicators",
    # Phase C: Causal analysis
    "decompose_delta",
    "get_top_contributors",
    # Phase C: Insight generation
    "generate_insight",
    "generate_template_insight",
]
