"""
Anomaly Detector — execution/intelligence/anomaly_detector.py

Single responsibility: Detects anomalous weeks in metric time series using
z-score (backward-compatible baseline) and Isolation Forest (primary method).

Upgrade from execution/ml/anomaly_detector.py:
- Retains z-score approach for backward compatibility
- Adds Isolation Forest as the primary detection method (sklearn)
- Returns a root-cause dimension hint (dimension column most correlated with spike)
- DOES NOT serialize the model to disk (in-memory fit-and-predict only)

Security clearance: CONDITIONAL (Phase B) — no pickle serialization,
dimension labels drawn from ALLOWED_ROOT_CAUSE_DIMENSIONS whitelist.
No file I/O, no API calls, no database queries in this module.
"""

import logging
from typing import TypedDict

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from execution.core.logging_config import get_logger

logger: logging.Logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Whitelist enforced per Phase B security cond. 2 and Phase A alert_engine.py
# Dimension labels must come from this set to prevent arbitrary JSON strings
# from flowing into root_cause_hint and ultimately into alert templates.
ALLOWED_ROOT_CAUSE_DIMENSIONS: frozenset[str] = frozenset(
    {
        "security",
        "quality",
        "flow",
        "deployment",
        "ownership",
        "risk",
        "collaboration",
        "exploitable",
    }
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


class AnomalyResult(TypedDict):
    """Structured anomaly detection result for a single week."""

    week_date: str  # ISO date string of the anomalous week
    value: float  # Observed metric value
    z_score: float  # Z-score of this point (using rolling or global stats)
    is_anomaly: bool  # True if flagged as anomalous
    method: str  # "zscore" or "isolation_forest"
    root_cause_hint: str  # Dimension most correlated with spike; empty if none


# ---------------------------------------------------------------------------
# Z-score detection (backward-compatible)
# ---------------------------------------------------------------------------


def detect_anomalies_zscore(
    values: list[float] | np.ndarray,
    *,
    threshold: float = 3.0,
) -> list[int]:
    """
    Detect anomalies using z-score threshold.

    Computes the global mean and standard deviation across all values,
    then flags indices whose absolute z-score exceeds the threshold.

    Args:
        values:    1-D array of metric values (chronological order).
        threshold: Absolute z-score above which a point is flagged (default 3.0).

    Returns:
        List of 0-based indices of anomalous data points.
        Empty list if standard deviation is zero (constant series).
    """
    arr = np.asarray(values, dtype=float)
    if len(arr) == 0:
        return []

    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0

    if std == 0.0:
        return []

    z_scores = np.abs((arr - mean) / std)
    return [int(i) for i in np.where(z_scores > threshold)[0]]


# ---------------------------------------------------------------------------
# Isolation Forest detection (primary)
# ---------------------------------------------------------------------------


def detect_anomalies_isolation_forest(
    df: pd.DataFrame,
    value_col: str,
    *,
    contamination: float = 0.05,
) -> list[int]:
    """
    Detect anomalies using Isolation Forest.

    SECURITY: Model is fit and used in-memory only — NOT serialized to pickle
    or any other format. This is a deliberate security requirement (Phase B
    cond. 6).

    The feature matrix passed to Isolation Forest consists of:
      - The metric value column
      - Any numeric dimension columns present in the DataFrame

    Operates on non-null rows only; returned indices reference positions in
    the original (un-filtered) DataFrame.

    Args:
        df:            DataFrame with at least one numeric column (value_col).
        value_col:     Primary metric column to analyse.
        contamination: Expected fraction of anomalies (0.0 < x < 0.5).
                       Default 0.05 = 5%.

    Returns:
        List of 0-based integer indices (in df) of detected anomalies.
        Empty list if value_col is absent or fewer than 2 non-null rows exist.
    """
    if value_col not in df.columns:
        logger.warning(
            "value_col not found in DataFrame for Isolation Forest",
            extra={"value_col": value_col, "columns": list(df.columns)},
        )
        return []

    # Build feature matrix from value_col + any numeric columns (exclude dates)
    numeric_cols = [
        col
        for col in df.select_dtypes(include=[np.number]).columns
        if col != "week_number"  # exclude artificial index-like columns
    ]

    if value_col not in numeric_cols:
        numeric_cols = [value_col] + numeric_cols

    # Ensure value_col is the first column (deterministic feature ordering)
    ordered_cols = [value_col] + [c for c in numeric_cols if c != value_col]

    clean = df[ordered_cols].dropna()
    if len(clean) < 2:
        return []

    feature_matrix = clean.to_numpy(dtype=float)

    # Clamp contamination to valid range
    safe_contamination = float(max(0.01, min(0.499, contamination)))

    # SECURITY: in-memory only — no joblib.dump / pickle.dump
    model = IsolationForest(
        contamination=safe_contamination,
        random_state=42,
        n_estimators=100,
    )
    labels = model.fit_predict(feature_matrix)

    # Map clean-DataFrame positions back to original df positions
    clean_positions = list(clean.index)
    anomaly_original_indices = [int(clean_positions[i]) for i, label in enumerate(labels) if label == -1]
    return anomaly_original_indices


# ---------------------------------------------------------------------------
# Root-cause dimension hint
# ---------------------------------------------------------------------------


def _compute_root_cause_hint(
    df: pd.DataFrame,
    value_col: str,
    anomaly_indices: list[int],
) -> str:
    """
    Return the dimension column most correlated with the anomalous spike.

    Correlation is measured as the absolute mean deviation of anomalous rows
    minus non-anomalous rows, normalised by the overall standard deviation.
    The dimension with the highest normalised gap is returned.

    Security: dimension names must be in ALLOWED_ROOT_CAUSE_DIMENSIONS.
    Arbitrary column names not in the whitelist are silently skipped.

    Returns:
        A non-empty string such as "security" if a dominant driver is found,
        or an empty string if no clear driver exists or no data is available.
    """
    if not anomaly_indices:
        return ""

    # Candidate dimension columns: numeric, whitelisted, not the target metric
    candidate_cols = [
        col
        for col in df.select_dtypes(include=[np.number]).columns
        if col != value_col and col in ALLOWED_ROOT_CAUSE_DIMENSIONS
    ]

    if not candidate_cols:
        return ""

    anomaly_mask = df.index.isin(anomaly_indices)
    best_dim = ""
    best_gap = 0.0

    for col in candidate_cols:
        series = df[col].dropna()
        if len(series) < 2:
            continue

        overall_std = float(series.std(ddof=1))
        if overall_std == 0.0:
            continue

        anomaly_vals = df.loc[anomaly_mask, col].dropna()
        normal_vals = df.loc[~anomaly_mask, col].dropna()

        if anomaly_vals.empty or normal_vals.empty:
            continue

        gap = abs(float(anomaly_vals.mean()) - float(normal_vals.mean())) / overall_std
        if gap > best_gap:
            best_gap = gap
            best_dim = col

    return best_dim


# ---------------------------------------------------------------------------
# Primary entry point
# ---------------------------------------------------------------------------


def detect_anomalies(
    df: pd.DataFrame,
    value_col: str,
    *,
    method: str = "isolation_forest",
    threshold: float = 3.0,
    contamination: float = 0.05,
) -> list[AnomalyResult]:
    """
    Primary entry point: detect anomalies and return structured results.

    Runs the requested detection method and augments each anomalous row with
    a z-score (for display) and a root-cause dimension hint.

    Args:
        df:            DataFrame with columns [week_date, <value_col>, ...].
        value_col:     Metric column to analyse.
        method:        "isolation_forest" (default) or "zscore".
        threshold:     Z-score threshold used by the "zscore" method (default 3.0).
        contamination: Expected anomaly fraction for "isolation_forest" (default 0.05).

    Returns:
        List of AnomalyResult TypedDicts, one per detected anomalous row,
        sorted by week_date ascending.

    Raises:
        ValueError: If method is not "isolation_forest" or "zscore".
    """
    if method not in ("isolation_forest", "zscore"):
        raise ValueError(f"Unknown method '{method}'. Use 'isolation_forest' or 'zscore'.")

    if value_col not in df.columns:
        logger.warning(
            "value_col not found — returning empty anomaly list",
            extra={"value_col": value_col},
        )
        return []

    # Compute global z-scores for display (regardless of detection method)
    series_vals = df[value_col].dropna().to_numpy(dtype=float)
    global_mean = float(np.mean(series_vals)) if len(series_vals) > 0 else 0.0
    global_std = float(np.std(series_vals, ddof=1)) if len(series_vals) > 1 else 1.0
    if global_std == 0.0:
        global_std = 1.0

    # Run detection
    if method == "isolation_forest":
        anomaly_indices = detect_anomalies_isolation_forest(df, value_col, contamination=contamination)
    else:  # method == "zscore"
        values_list = df[value_col].tolist()
        anomaly_indices = detect_anomalies_zscore(values_list, threshold=threshold)

    root_cause_hint = _compute_root_cause_hint(df, value_col, anomaly_indices)

    results: list[AnomalyResult] = []
    for idx in anomaly_indices:
        if idx not in df.index:
            continue
        row = df.loc[idx]

        raw_value = row.get(value_col, None) if isinstance(row, pd.Series) else None
        if raw_value is None or (isinstance(raw_value, float) and np.isnan(raw_value)):
            continue
        value = float(raw_value)

        z = (value - global_mean) / global_std

        raw_date = row.get("week_date", "") if isinstance(row, pd.Series) else ""
        if hasattr(raw_date, "isoformat"):
            week_date_str = raw_date.isoformat()[:10]
        else:
            week_date_str = str(raw_date)[:10]

        results.append(
            AnomalyResult(
                week_date=week_date_str,
                value=value,
                z_score=round(z, 3),
                is_anomaly=True,
                method=method,
                root_cause_hint=root_cause_hint,
            )
        )

    # Sort chronologically
    results.sort(key=lambda r: r["week_date"])

    logger.info(
        "Anomaly detection complete",
        extra={
            "value_col": value_col,
            "method": method,
            "anomalies_found": len(results),
            "root_cause_hint": root_cause_hint or "(none)",
        },
    )
    return results
