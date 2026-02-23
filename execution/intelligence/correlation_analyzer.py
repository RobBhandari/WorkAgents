"""
Correlation Analyzer — execution/intelligence/correlation_analyzer.py

Cross-metric Pearson correlation with optional lag.
Loads feature Parquet files and computes pairwise correlations.

Security: VALID_METRICS whitelist enforced; no file writes; pure computation.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr

from execution.core.logging_config import get_logger
from execution.intelligence.feature_engineering import VALID_METRICS, load_features

logger: logging.Logger = get_logger(__name__)

# Minimum number of aligned data points required for a valid correlation
_MIN_POINTS: int = 3


# ---------------------------------------------------------------------------
# Low-level computation
# ---------------------------------------------------------------------------


def compute_pairwise_correlation(
    metric_a_series: list[float],
    metric_b_series: list[float],
    lag_weeks: int = 0,
) -> float:
    """
    Compute Pearson correlation between two series with optional lag.

    When lag_weeks > 0, metric_b is shifted forward by lag_weeks (metric_a
    leads metric_b).  Alignment is performed by trimming both series to the
    overlapping window after the shift.

    Args:
        metric_a_series: Chronologically ordered float values for metric A.
        metric_b_series: Chronologically ordered float values for metric B.
        lag_weeks:       Number of weeks to shift metric_b forward (>=0).

    Returns:
        Pearson r in [-1.0, 1.0].
        Returns 0.0 when:
            - Either series has < _MIN_POINTS after alignment.
            - Either series has zero variance (constant).
            - lag_weeks is negative (invalid).

    Security:
        Inputs are coerced to float via list construction — no raw user strings
        are passed to scipy.
    """
    if lag_weeks < 0:
        logger.warning("lag_weeks must be >= 0; returning 0.0", extra={"lag_weeks": lag_weeks})
        return 0.0

    a = list(metric_a_series)
    b = list(metric_b_series)

    if lag_weeks > 0:
        # metric_a leads metric_b: drop first lag_weeks of a, last lag_weeks of b
        a = a[lag_weeks:]
        b = b[: len(b) - lag_weeks] if lag_weeks <= len(b) else []

    # Align to the shorter series length
    min_len = min(len(a), len(b))
    a = a[:min_len]
    b = b[:min_len]

    if min_len < _MIN_POINTS:
        return 0.0

    std_a = float(np.std(a))
    std_b = float(np.std(b))
    if std_a == 0.0 or std_b == 0.0:
        return 0.0

    r, _ = pearsonr(a, b)
    return float(r)


# ---------------------------------------------------------------------------
# Matrix builder
# ---------------------------------------------------------------------------


def _load_numeric_series(
    metric: str,
    feature_dir: Path,
    project: str | None,
) -> list[float]:
    """
    Load numeric values for a metric from its feature Parquet.

    Returns:
        Aggregated (mean across projects per week) numeric series as float list.
        Returns [] on any load error or if fewer than _MIN_POINTS rows.
    """
    try:
        df = load_features(metric, project=project, base_dir=feature_dir)
    except ValueError as exc:
        logger.warning(
            "Feature load failed for metric",
            extra={"metric": metric, "error": str(exc)},
        )
        return []

    if df.empty:
        return []

    # Pick numeric columns (exclude week_date and project identifiers)
    numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c not in ("week_date",)]
    if not numeric_cols:
        return []

    # Aggregate per week_date then flatten to a single series (mean of means)
    if "week_date" in df.columns:
        agg = df.groupby("week_date")[numeric_cols].mean(numeric_only=True)
        agg = agg.sort_index()
        # Use the mean across all numeric columns as the single representative series
        combined = agg.mean(axis=1)
    else:
        combined = df[numeric_cols].mean(axis=1)

    values = [float(v) for v in combined.tolist() if not np.isnan(v)]

    if len(values) < _MIN_POINTS:
        return []

    return values


def compute_correlation_matrix(
    feature_dir: Path = Path("data/features"),
    metrics: list[str] | None = None,
    lag_weeks: int = 0,
    project: str | None = None,
) -> dict[str, dict[str, float]]:
    """
    Build pairwise Pearson correlation matrix for all specified metrics.

    Args:
        feature_dir: Directory containing Parquet feature files.
        metrics:     List of metric names to include; defaults to list(VALID_METRICS).
        lag_weeks:   Optional lag applied to all metric_b series.
        project:     Optional project name to filter features (e.g. "Product_A").

    Returns:
        Nested dict {metric_a: {metric_b: r}} for all pairs including self-correlation.

    Raises:
        ValueError: If any metric name in `metrics` is not in VALID_METRICS.
    """
    if metrics is None:
        metrics = sorted(VALID_METRICS)

    # Validate all metric names upfront
    invalid = [m for m in metrics if m not in VALID_METRICS]
    if invalid:
        raise ValueError(f"Invalid metric name(s): {invalid}. " f"Allowed values: {sorted(VALID_METRICS)}")

    # Load series for each metric (skip those with insufficient data)
    series_map: dict[str, list[float]] = {}
    for metric in metrics:
        series = _load_numeric_series(metric, feature_dir, project)
        if series:
            series_map[metric] = series
        else:
            logger.info(
                "Skipping metric — insufficient numeric data",
                extra={"metric": metric},
            )

    matrix: dict[str, dict[str, float]] = {}
    loaded_metrics = sorted(series_map.keys())

    for m_a in loaded_metrics:
        matrix[m_a] = {}
        for m_b in loaded_metrics:
            r = compute_pairwise_correlation(
                series_map[m_a],
                series_map[m_b],
                lag_weeks=lag_weeks,
            )
            matrix[m_a][m_b] = round(r, 4)

    logger.info(
        "Correlation matrix computed",
        extra={"metrics": loaded_metrics, "lag_weeks": lag_weeks},
    )
    return matrix


# ---------------------------------------------------------------------------
# Leading indicator detection
# ---------------------------------------------------------------------------


def find_leading_indicators(
    correlation_matrix: dict[str, dict[str, float]],
    threshold: float = 0.5,
) -> list[tuple[str, str, float]]:
    """
    Find metric pairs whose absolute correlation meets or exceeds `threshold`.

    Self-pairs (metric_a == metric_b) are excluded.

    Args:
        correlation_matrix: Output of compute_correlation_matrix().
        threshold:          Minimum |r| to include in results (default 0.5).

    Returns:
        List of (metric_a, metric_b, r) tuples, sorted by |r| descending.
        Symmetric pairs are both included (a→b and b→a).
    """
    results: list[tuple[str, str, float]] = []

    for m_a, row in correlation_matrix.items():
        for m_b, r in row.items():
            if m_a == m_b:
                continue
            if abs(r) >= threshold:
                results.append((m_a, m_b, r))

    results.sort(key=lambda t: abs(t[2]), reverse=True)
    return results
