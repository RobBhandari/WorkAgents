"""
Causal Analyzer — execution/intelligence/causal_analyzer.py

Root cause attribution: decomposes metric delta by dimension.
Uses proportional contribution analysis (not true causal inference).

Each dimension's share of the total absolute movement is computed, giving
an interpretable "who drove the change" breakdown for dashboards.
"""

from __future__ import annotations

import logging

import pandas as pd

from execution.core.logging_config import get_logger
from execution.domain.intelligence import CausalContribution

logger: logging.Logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Core decomposition
# ---------------------------------------------------------------------------


def decompose_delta(
    current: dict[str, float],
    prior: dict[str, float],
) -> list[CausalContribution]:
    """
    Attribute metric delta to dimensions via proportional contribution analysis.

    For each dimension present in either `current` or `prior`, the absolute
    delta is computed.  The contribution_pct is each dimension's share of the
    total absolute movement across all dimensions.

    Args:
        current: {dimension: current_period_value}
        prior:   {dimension: prior_period_value}

    Returns:
        List of CausalContribution sorted by |contribution_pct| descending.
        Returns empty list if total absolute delta is zero (no change).

    Notes:
        - Dimensions present only in `current` are treated as prior_value = 0.
        - Dimensions present only in `prior` are treated as current_value = 0.
        - All values are coerced to float for safety.
    """
    all_dims = set(current.keys()) | set(prior.keys())

    deltas: list[tuple[str, float, float, float]] = []
    for dim in all_dims:
        c_val = float(current.get(dim, 0.0))
        p_val = float(prior.get(dim, 0.0))
        delta = c_val - p_val
        deltas.append((dim, c_val, p_val, delta))

    total_abs_delta = sum(abs(d) for _, _, _, d in deltas)

    if total_abs_delta == 0.0:
        return []

    contributions: list[CausalContribution] = [
        CausalContribution(
            dimension=dim,
            current_value=c_val,
            prior_value=p_val,
            delta=delta,
            contribution_pct=round(abs(delta) / total_abs_delta * 100.0, 2),
        )
        for dim, c_val, p_val, delta in deltas
    ]

    contributions.sort(key=lambda c: abs(c.contribution_pct), reverse=True)
    return contributions


# ---------------------------------------------------------------------------
# DataFrame-based top contributors
# ---------------------------------------------------------------------------


def _split_current_prior(
    df: pd.DataFrame,
    value_col: str,
    dimension_col: str,
    n_weeks_back: int,
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Split a DataFrame into current and prior period dimension means.

    Groups by `dimension_col`, then uses the last `n_weeks_back` rows as
    "current" and the rows before that as "prior".

    Args:
        df:            Feature DataFrame sorted chronologically.
        value_col:     Column with the numeric metric value.
        dimension_col: Column with dimension labels (e.g. "project").
        n_weeks_back:  Number of rows defining the "current" window.

    Returns:
        Tuple (current_means, prior_means) where each is {dimension: mean}.
        Returns ({}, {}) if the DataFrame is too short to split.
    """
    if df.empty or value_col not in df.columns or dimension_col not in df.columns:
        return {}, {}

    # Sort so "current" is the tail
    df_sorted = (
        df.sort_values("week_date").reset_index(drop=True) if "week_date" in df.columns else df.reset_index(drop=True)
    )

    n_total = len(df_sorted)
    if n_total <= n_weeks_back:
        return {}, {}

    prior_df = df_sorted.iloc[: n_total - n_weeks_back]
    current_df = df_sorted.iloc[n_total - n_weeks_back :]

    current_means: dict[str, float] = {
        str(dim): float(grp[value_col].mean())
        for dim, grp in current_df.groupby(dimension_col)
        if not grp[value_col].isna().all()
    }
    prior_means: dict[str, float] = {
        str(dim): float(grp[value_col].mean())
        for dim, grp in prior_df.groupby(dimension_col)
        if not grp[value_col].isna().all()
    }

    return current_means, prior_means


def get_top_contributors(
    df: pd.DataFrame,
    value_col: str,
    dimension_col: str,
    n_weeks_back: int = 1,
    top_n: int = 3,
) -> list[CausalContribution]:
    """
    Get the top contributing dimensions to a metric change over the last period.

    Computes per-dimension mean over the last `n_weeks_back` rows (current
    window) vs all prior rows, then delegates to decompose_delta.

    Args:
        df:            Feature DataFrame (must contain `value_col` and `dimension_col`).
        value_col:     Numeric column to analyse (e.g. "open_bugs").
        dimension_col: Column identifying dimensions (e.g. "project").
        n_weeks_back:  Number of most-recent rows treated as "current" period.
        top_n:         Maximum number of top contributors to return.

    Returns:
        List of up to `top_n` CausalContribution objects sorted by
        |contribution_pct| descending.

        Returns empty list if:
            - df is empty
            - value_col is absent
            - insufficient history (df has <= n_weeks_back rows)
    """
    if df.empty:
        return []

    if value_col not in df.columns:
        logger.warning(
            "value_col not found in DataFrame",
            extra={"value_col": value_col, "columns": list(df.columns)},
        )
        return []

    current_means, prior_means = _split_current_prior(df, value_col, dimension_col, n_weeks_back)

    if not current_means and not prior_means:
        logger.info(
            "Insufficient history for causal decomposition",
            extra={"rows": len(df), "n_weeks_back": n_weeks_back},
        )
        return []

    contributions = decompose_delta(current_means, prior_means)
    return contributions[:top_n]
