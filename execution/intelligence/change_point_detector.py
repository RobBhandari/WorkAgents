"""
Change Point Detector — execution/intelligence/change_point_detector.py

Single responsibility: Detects regime changes in metric time series using
the PELT algorithm (ruptures library).

Security clearance: CLEARED (Phase B pre-implementation).
No file I/O, no API calls, no database queries, no serialization.
Pure computation over Python objects.
"""

import logging

import numpy as np
import pandas as pd
import ruptures

from execution.core.logging_config import get_logger

logger: logging.Logger = get_logger(__name__)


def detect_change_points(
    values: list[float] | np.ndarray,
    *,
    min_size: int = 3,
    penalty: float = 10.0,
) -> list[int]:
    """
    Detect change points in a time series using the ruptures PELT algorithm.

    Uses the radial basis function (rbf) cost model, which is well-suited to
    detecting changes in mean and variance for real-valued engineering metrics.

    Args:
        values:   1-D time series (list or numpy array of floats).
        min_size: Minimum number of samples between change points.
                  Lower values allow more densely-packed change points.
        penalty:  Regularisation penalty controlling sensitivity.
                  Higher values → fewer change points detected.
                  Typical range: 1.0 (sensitive) to 50.0 (conservative).

    Returns:
        List of 0-based indices at which a regime change was detected.
        The final sentinel index (len(values)) returned by ruptures is
        excluded — only interior change-point positions are returned.
        Empty list if the series is too short, constant, or if ruptures
        encounters any error.

    Example:
        >>> detect_change_points([10, 10, 10, 50, 50, 50], penalty=2.0)
        [3]
        >>> detect_change_points([1.0, 2.0, 1.5, 1.8], min_size=3)
        []
    """
    arr = np.asarray(values, dtype=float)

    if arr.ndim == 1:
        signal = arr.reshape(-1, 1)
    else:
        signal = arr

    n = signal.shape[0]
    if n < 2 * min_size:
        logger.debug(
            "Series too short for change-point detection",
            extra={"n": n, "min_size": min_size},
        )
        return []

    try:
        model = ruptures.Pelt(model="rbf", min_size=min_size)
        model.fit(signal)
        breakpoints = model.predict(pen=penalty)
        # ruptures always appends len(signal) as the final sentinel — exclude it
        interior = [bp for bp in breakpoints if bp < n]
        logger.debug(
            "Change points detected",
            extra={"n": n, "penalty": penalty, "change_points": interior},
        )
        return interior
    except ruptures.exceptions.BadSegmentationParameters as exc:
        logger.warning(
            "ruptures BadSegmentationParameters — returning empty",
            extra={"error": str(exc), "n": n, "min_size": min_size, "penalty": penalty},
        )
        return []
    except Exception as exc:  # noqa: BLE001 — graceful degradation for all ruptures errors
        logger.warning(
            "Unexpected error in change-point detection — returning empty",
            extra={"error": str(exc), "error_type": type(exc).__name__},
        )
        return []


def detect_change_point_weeks(
    df: pd.DataFrame,
    metric_col: str,
    *,
    min_size: int = 3,
    penalty: float = 10.0,
) -> list[str]:
    """
    Convenience wrapper: returns week_date strings for each detected change point.

    Filters to non-null rows, runs detect_change_points(), then maps the
    returned indices back to the corresponding week_date values.

    Args:
        df:         DataFrame with columns [week_date, <metric_col>].
                    week_date must be sortable (string ISO dates or datetime).
        metric_col: Column containing the metric values to analyse.
        min_size:   Forwarded to detect_change_points().
        penalty:    Forwarded to detect_change_points().

    Returns:
        List of ISO date strings (YYYY-MM-DD) where regime changes were detected.
        Empty list if metric_col is absent, no data, or no change points found.

    Example:
        >>> detect_change_point_weeks(df, "open_bugs", penalty=5.0)
        ["2025-09-15", "2026-01-06"]
    """
    if metric_col not in df.columns:
        logger.warning(
            "metric_col not found in DataFrame",
            extra={"metric_col": metric_col, "columns": list(df.columns)},
        )
        return []

    clean = df[["week_date", metric_col]].dropna(subset=[metric_col]).copy()
    if clean.empty:
        return []

    # Sort by week_date so indices correspond to chronological order
    clean = clean.sort_values("week_date").reset_index(drop=True)

    values = clean[metric_col].to_numpy(dtype=float)
    indices = detect_change_points(values, min_size=min_size, penalty=penalty)

    week_dates: list[str] = []
    for idx in indices:
        if 0 <= idx < len(clean):
            raw = clean.loc[idx, "week_date"]
            # Normalise to ISO string regardless of whether week_date is str or datetime
            if hasattr(raw, "isoformat"):
                week_dates.append(raw.isoformat()[:10])
            else:
                week_dates.append(str(raw)[:10])

    return week_dates
