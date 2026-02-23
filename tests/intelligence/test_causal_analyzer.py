"""
Tests for execution/intelligence/causal_analyzer.py

Covers decompose_delta, get_top_contributors, and CausalContribution.from_dict.
All fixtures use synthetic data — no real project names, no external I/O.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from execution.domain.intelligence import CausalContribution
from execution.intelligence.causal_analyzer import decompose_delta, get_top_contributors

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _weeks(n: int) -> list[datetime]:
    """Generate n sequential weekly datetimes (deterministic)."""
    base = datetime(2025, 10, 6)
    return [base + timedelta(weeks=i) for i in range(n)]


# ---------------------------------------------------------------------------
# decompose_delta tests
# ---------------------------------------------------------------------------


def test_decompose_delta_correct_contribution_pct() -> None:
    """
    With two dimensions each moving by the same absolute amount,
    each should receive 50% contribution.
    """
    current = {"dim_A": 20.0, "dim_B": 10.0}
    prior = {"dim_A": 10.0, "dim_B": 20.0}
    # dim_A: delta = +10, dim_B: delta = -10 → total_abs = 20
    results = decompose_delta(current, prior)

    assert len(results) == 2
    for c in results:
        assert abs(c.contribution_pct - 50.0) < 1e-6


def test_decompose_delta_zero_total_returns_empty() -> None:
    """If nothing changed, decompose_delta should return an empty list."""
    current = {"dim_A": 5.0, "dim_B": 10.0}
    prior = {"dim_A": 5.0, "dim_B": 10.0}
    results = decompose_delta(current, prior)
    assert results == []


def test_decompose_delta_sorted_by_abs_contribution_desc() -> None:
    """Results must be sorted by |contribution_pct| descending."""
    current = {"big": 100.0, "small": 2.0, "medium": 20.0}
    prior = {"big": 10.0, "small": 1.0, "medium": 10.0}
    # big: delta=90, medium: delta=10, small: delta=1 → total=101
    results = decompose_delta(current, prior)
    pcts = [abs(c.contribution_pct) for c in results]
    assert pcts == sorted(pcts, reverse=True)


def test_decompose_delta_values_correct() -> None:
    """Check delta and contribution_pct are computed correctly."""
    current = {"A": 30.0}
    prior = {"A": 10.0}
    results = decompose_delta(current, prior)

    assert len(results) == 1
    c = results[0]
    assert c.dimension == "A"
    assert c.current_value == 30.0
    assert c.prior_value == 10.0
    assert c.delta == 20.0
    assert abs(c.contribution_pct - 100.0) < 1e-6


def test_decompose_delta_missing_dimension_in_prior() -> None:
    """Dimension only in current is treated as prior_value=0."""
    current = {"new_dim": 15.0}
    prior: dict[str, float] = {}
    results = decompose_delta(current, prior)
    assert len(results) == 1
    assert results[0].prior_value == 0.0
    assert results[0].delta == 15.0


def test_decompose_delta_missing_dimension_in_current() -> None:
    """Dimension only in prior is treated as current_value=0 (dimension disappeared)."""
    current: dict[str, float] = {}
    prior = {"gone_dim": 8.0}
    results = decompose_delta(current, prior)
    assert len(results) == 1
    assert results[0].current_value == 0.0
    assert results[0].delta == -8.0


def test_decompose_delta_multiple_dimensions_pct_sum() -> None:
    """All contribution_pct values should sum to 100.0."""
    current = {"A": 50.0, "B": 30.0, "C": 10.0}
    prior = {"A": 20.0, "B": 40.0, "C": 5.0}
    results = decompose_delta(current, prior)
    total_pct = sum(abs(c.contribution_pct) for c in results)
    assert abs(total_pct - 100.0) < 1e-4


# ---------------------------------------------------------------------------
# get_top_contributors tests
# ---------------------------------------------------------------------------


@pytest.fixture
def multi_project_df() -> pd.DataFrame:
    """
    Synthetic DataFrame with two projects over 10 weeks.
    Product_A improves significantly in last week; Product_B stays flat.
    """
    dates = _weeks(10)
    rows = []
    for i, d in enumerate(dates):
        rows.append({"week_date": d, "project": "Product_A", "open_bugs": 100.0 - i * 2})
        rows.append({"week_date": d, "project": "Product_B", "open_bugs": 50.0})
    return pd.DataFrame(rows)


def test_get_top_contributors_returns_causal_contributions(
    multi_project_df: pd.DataFrame,
) -> None:
    """Basic call should return a non-empty list of CausalContribution objects."""
    results = get_top_contributors(
        df=multi_project_df,
        value_col="open_bugs",
        dimension_col="project",
        n_weeks_back=2,
        top_n=3,
    )
    assert isinstance(results, list)
    assert len(results) > 0
    assert all(isinstance(c, CausalContribution) for c in results)


def test_get_top_contributors_respects_top_n(
    multi_project_df: pd.DataFrame,
) -> None:
    """top_n limit must be respected."""
    results = get_top_contributors(
        df=multi_project_df,
        value_col="open_bugs",
        dimension_col="project",
        n_weeks_back=2,
        top_n=1,
    )
    assert len(results) <= 1


def test_get_top_contributors_empty_df() -> None:
    """Empty DataFrame should return empty list without error."""
    df = pd.DataFrame(columns=["week_date", "project", "open_bugs"])
    results = get_top_contributors(df, "open_bugs", "project")
    assert results == []


def test_get_top_contributors_missing_value_col() -> None:
    """Missing value_col should return empty list (graceful degradation)."""
    dates = _weeks(5)
    df = pd.DataFrame({"week_date": dates, "project": ["P"] * 5})
    results = get_top_contributors(df, "nonexistent_col", "project")
    assert results == []


def test_get_top_contributors_insufficient_history() -> None:
    """
    If n_weeks_back >= total rows, there is no prior window.
    Should return empty list.
    """
    dates = _weeks(3)
    df = pd.DataFrame(
        {
            "week_date": dates,
            "project": ["P"] * 3,
            "open_bugs": [10.0, 11.0, 12.0],
        }
    )
    # n_weeks_back=5 exceeds the 3 available rows → no split possible
    results = get_top_contributors(df, "open_bugs", "project", n_weeks_back=5)
    assert results == []


def test_get_top_contributors_result_sorted_by_pct(
    multi_project_df: pd.DataFrame,
) -> None:
    """Returned contributions must be sorted by |contribution_pct| descending."""
    results = get_top_contributors(
        df=multi_project_df,
        value_col="open_bugs",
        dimension_col="project",
        n_weeks_back=2,
        top_n=5,
    )
    if len(results) > 1:
        pcts = [abs(c.contribution_pct) for c in results]
        assert pcts == sorted(pcts, reverse=True)


# ---------------------------------------------------------------------------
# CausalContribution.from_dict roundtrip
# ---------------------------------------------------------------------------


def test_causal_contribution_from_dict_roundtrip() -> None:
    """from_dict should reconstruct all fields correctly."""
    data = {
        "dimension": "Product_A",
        "current_value": 42.5,
        "prior_value": 30.0,
        "delta": 12.5,
        "contribution_pct": 75.0,
    }
    c = CausalContribution.from_dict(data)
    assert c.dimension == "Product_A"
    assert c.current_value == 42.5
    assert c.prior_value == 30.0
    assert c.delta == 12.5
    assert c.contribution_pct == 75.0


def test_causal_contribution_from_dict_coerces_types() -> None:
    """from_dict must coerce string numbers to float."""
    data = {
        "dimension": "Synth_B",
        "current_value": "10",
        "prior_value": "5",
        "delta": "5",
        "contribution_pct": "100",
    }
    c = CausalContribution.from_dict(data)
    assert isinstance(c.current_value, float)
    assert c.current_value == 10.0
