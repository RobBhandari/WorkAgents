"""
Tests for execution/intelligence/correlation_analyzer.py

All fixtures use synthetic data only — no real project names, no file I/O
except through mocked load_features.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from execution.intelligence.correlation_analyzer import (
    compute_correlation_matrix,
    compute_pairwise_correlation,
    find_leading_indicators,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def perfectly_correlated() -> tuple[list[float], list[float]]:
    """Two identical series — perfect positive correlation (r=1.0)."""
    a = [float(i) for i in range(1, 21)]
    b = [float(i) for i in range(1, 21)]
    return a, b


@pytest.fixture
def perfectly_anticorrelated() -> tuple[list[float], list[float]]:
    """Reversed series — perfect negative correlation (r=-1.0)."""
    a = [float(i) for i in range(1, 21)]
    b = [float(21 - i) for i in range(1, 21)]
    return a, b


@pytest.fixture
def zero_variance_series() -> tuple[list[float], list[float]]:
    """Constant series — zero variance."""
    a = [10.0] * 20
    b = [float(i) for i in range(1, 21)]
    return a, b


@pytest.fixture
def short_series() -> tuple[list[float], list[float]]:
    """Only 2 data points — below MIN_POINTS=3."""
    return [1.0, 2.0], [3.0, 4.0]


@pytest.fixture
def lagged_series() -> tuple[list[float], list[float]]:
    """
    Series where metric_a is a ramp and metric_b is a *noisy* version
    shifted by 2 weeks with disruptive noise at the start (making lag_weeks=0
    give lower |r| than lag_weeks=2).

    a = [1..20]
    b = [50, 50, 1, 2, ..., 18]  (first 2 positions are far-off outliers,
                                   then follows a[0..17])
    """
    a = [float(i) for i in range(1, 21)]
    # Start with two large noise values; then the true signal delayed by 2
    b = [50.0, 50.0] + [float(i) for i in range(1, 19)]
    return a, b


@pytest.fixture
def sample_quality_df() -> pd.DataFrame:
    """Synthetic quality DataFrame with open_bugs column."""
    dates = pd.date_range("2025-01-01", periods=20, freq="W")
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Synth_A"] * 20,
            "open_bugs": [float(300 - i * 5) for i in range(20)],
        }
    )


@pytest.fixture
def sample_security_df() -> pd.DataFrame:
    """Synthetic security DataFrame with total_vulnerabilities column."""
    dates = pd.date_range("2025-01-01", periods=20, freq="W")
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["_portfolio"] * 20,
            "total_vulnerabilities": [float(200 + i * 3) for i in range(20)],
            "critical": [float(10 + i) for i in range(20)],
        }
    )


# ---------------------------------------------------------------------------
# compute_pairwise_correlation tests
# ---------------------------------------------------------------------------


def test_compute_pairwise_correlation_perfect_positive(
    perfectly_correlated: tuple[list[float], list[float]],
) -> None:
    """Identical series should yield r = 1.0."""
    a, b = perfectly_correlated
    r = compute_pairwise_correlation(a, b)
    assert abs(r - 1.0) < 1e-9


def test_compute_pairwise_correlation_perfect_negative(
    perfectly_anticorrelated: tuple[list[float], list[float]],
) -> None:
    """Reversed series should yield r = -1.0."""
    a, b = perfectly_anticorrelated
    r = compute_pairwise_correlation(a, b)
    assert abs(r + 1.0) < 1e-9


def test_compute_pairwise_correlation_zero_variance(
    zero_variance_series: tuple[list[float], list[float]],
) -> None:
    """Constant series has zero variance — should return 0.0."""
    a, b = zero_variance_series
    r = compute_pairwise_correlation(a, b)
    assert r == 0.0


def test_compute_pairwise_correlation_too_short(
    short_series: tuple[list[float], list[float]],
) -> None:
    """Series with < 3 points after alignment returns 0.0."""
    a, b = short_series
    r = compute_pairwise_correlation(a, b)
    assert r == 0.0


def test_compute_pairwise_correlation_negative_lag() -> None:
    """Negative lag_weeks is invalid — returns 0.0."""
    a = [float(i) for i in range(1, 21)]
    b = [float(i) for i in range(1, 21)]
    r = compute_pairwise_correlation(a, b, lag_weeks=-1)
    assert r == 0.0


def test_compute_pairwise_correlation_lag_reduces_correlation(
    lagged_series: tuple[list[float], list[float]],
) -> None:
    """
    Without lag, the shifted series has lower |r|.
    With lag_weeks=2, the alignment should reveal the true correlation.
    """
    a, b = lagged_series
    r_no_lag = compute_pairwise_correlation(a, b, lag_weeks=0)
    r_with_lag = compute_pairwise_correlation(a, b, lag_weeks=2)
    # With the correct lag, |r| should be higher than without lag
    assert abs(r_with_lag) > abs(r_no_lag)


def test_compute_pairwise_correlation_lag_too_large() -> None:
    """Lag >= series length → series shrinks below MIN_POINTS → returns 0.0."""
    a = [1.0, 2.0, 3.0, 4.0]
    b = [1.0, 2.0, 3.0, 4.0]
    r = compute_pairwise_correlation(a, b, lag_weeks=4)
    assert r == 0.0


# ---------------------------------------------------------------------------
# compute_correlation_matrix tests
# ---------------------------------------------------------------------------


def test_compute_correlation_matrix_returns_nested_dict(
    sample_quality_df: pd.DataFrame,
    sample_security_df: pd.DataFrame,
) -> None:
    """Matrix should be a nested dict with self-correlation = 1.0."""
    with patch("execution.intelligence.correlation_analyzer.load_features") as mock_load:
        mock_load.side_effect = lambda metric, project, base_dir: (
            sample_quality_df if metric == "quality" else sample_security_df
        )
        matrix = compute_correlation_matrix(
            feature_dir=Path("data/features"),
            metrics=["quality", "security"],
        )

    assert isinstance(matrix, dict)
    assert "quality" in matrix
    assert "security" in matrix
    # Self-correlation must be 1.0
    assert abs(matrix["quality"]["quality"] - 1.0) < 1e-9
    assert abs(matrix["security"]["security"] - 1.0) < 1e-9


def test_compute_correlation_matrix_skips_empty_metric(
    sample_quality_df: pd.DataFrame,
) -> None:
    """Metrics that return empty DataFrame should be absent from matrix."""
    with patch("execution.intelligence.correlation_analyzer.load_features") as mock_load:

        def side_effect(metric: str, project: str | None, base_dir: Path) -> pd.DataFrame:
            if metric == "quality":
                return sample_quality_df
            raise ValueError(f"No data for {metric}")

        mock_load.side_effect = side_effect

        matrix = compute_correlation_matrix(
            feature_dir=Path("data/features"),
            metrics=["quality", "flow"],
        )

    # Only "quality" should appear; "flow" was skipped
    assert "quality" in matrix
    assert "flow" not in matrix


def test_compute_correlation_matrix_invalid_metric_raises() -> None:
    """Passing an invalid metric name must raise ValueError immediately."""
    with pytest.raises(ValueError, match="Invalid metric name"):
        compute_correlation_matrix(
            feature_dir=Path("data/features"),
            metrics=["quality", "NOT_A_VALID_METRIC"],
        )


def test_compute_correlation_matrix_with_lag(
    sample_quality_df: pd.DataFrame,
    sample_security_df: pd.DataFrame,
) -> None:
    """Matrix with lag_weeks=2 should still return valid nested dict."""
    with patch("execution.intelligence.correlation_analyzer.load_features") as mock_load:
        mock_load.side_effect = lambda metric, project, base_dir: (
            sample_quality_df if metric == "quality" else sample_security_df
        )
        matrix = compute_correlation_matrix(
            feature_dir=Path("data/features"),
            metrics=["quality", "security"],
            lag_weeks=2,
        )

    assert isinstance(matrix, dict)
    for m_a, row in matrix.items():
        for m_b, r in row.items():
            assert -1.0 <= r <= 1.0


# ---------------------------------------------------------------------------
# find_leading_indicators tests
# ---------------------------------------------------------------------------


def test_find_leading_indicators_filters_by_threshold() -> None:
    """Only pairs with |r| >= threshold should be returned."""
    matrix = {
        "A": {"A": 1.0, "B": 0.8, "C": 0.3},
        "B": {"A": 0.8, "B": 1.0, "C": 0.2},
        "C": {"A": 0.3, "B": 0.2, "C": 1.0},
    }
    results = find_leading_indicators(matrix, threshold=0.5)
    # Only A↔B pairs should qualify (|0.8| >= 0.5); C pairs do not
    assert all(abs(r) >= 0.5 for _, _, r in results)
    metric_pairs = [(a, b) for a, b, _ in results]
    assert ("A", "B") in metric_pairs
    assert ("B", "A") in metric_pairs
    # Self-pairs excluded
    assert ("A", "A") not in metric_pairs


def test_find_leading_indicators_sorted_by_abs_r() -> None:
    """Results must be sorted by |r| descending."""
    matrix = {
        "A": {"A": 1.0, "B": 0.9, "C": -0.7},
        "B": {"A": 0.9, "B": 1.0, "C": 0.6},
        "C": {"A": -0.7, "B": 0.6, "C": 1.0},
    }
    results = find_leading_indicators(matrix, threshold=0.5)
    abs_rs = [abs(r) for _, _, r in results]
    assert abs_rs == sorted(abs_rs, reverse=True)


def test_find_leading_indicators_empty_matrix() -> None:
    """Empty matrix should return empty list without error."""
    results = find_leading_indicators({}, threshold=0.5)
    assert results == []


def test_find_leading_indicators_no_pairs_above_threshold() -> None:
    """If no pair meets threshold, returns empty list."""
    matrix = {
        "A": {"A": 1.0, "B": 0.3},
        "B": {"A": 0.3, "B": 1.0},
    }
    results = find_leading_indicators(matrix, threshold=0.9)
    assert results == []


def test_find_leading_indicators_negative_correlation() -> None:
    """Strong negative correlations (|r| >= threshold) must be included."""
    matrix = {
        "A": {"A": 1.0, "B": -0.85},
        "B": {"A": -0.85, "B": 1.0},
    }
    results = find_leading_indicators(matrix, threshold=0.5)
    correlations = [r for _, _, r in results]
    assert -0.85 in correlations
