"""
Project Health Classifier — execution/intelligence/health_classifier.py

Classifies each project as Green/Amber/Red using a RandomForest classifier
re-fitted each run from the feature store. No model serialization.

Security:
- No pickle/joblib. Re-fit each run.
- Output labels validated against _VALID_HEALTH_LABELS allowlist.
- Confidence scores coerced to Python float with 4 decimal precision.
- Feature-level data never logged.
"""

from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from execution.core.logging_config import get_logger
from execution.domain.intelligence import HealthClassification
from execution.intelligence.feature_engineering import VALID_METRICS, load_features

logger: logging.Logger = get_logger(__name__)

_VALID_HEALTH_LABELS: frozenset[str] = frozenset({"Green", "Amber", "Red"})
_MODEL_VERSION: str = "v1.0.0"

# Minimum number of labelled samples required to fit the classifier
_MIN_SAMPLES: int = 3

# Metrics to load features from and the column each contributes
_FEATURE_METRIC_MAP: dict[str, str] = {
    "quality": "open_bugs",
    "security": "total_vulnerabilities",
    "flow": "lead_time_p85",
    "deployment": "deploy_frequency",
    "risk": "risk_score",
}

# Thresholds for rule-based label derivation from risk_score
_HEALTH_THRESHOLDS: dict[str, float] = {
    "green_max_risk": 30.0,  # risk_score <= 30 → Green
    "amber_max_risk": 60.0,  # risk_score 30–60 → Amber
    # risk_score > 60 → Red
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_metric_dataframe(metric: str) -> pd.DataFrame | None:
    """
    Load the most recent feature Parquet for a metric.

    Security: metric validated against VALID_METRICS before path construction.
    Returns None on any load error.
    """
    if metric not in VALID_METRICS:
        logger.warning(
            "Invalid metric for health classifier",
            extra={"metric": metric},
        )
        return None
    try:
        df = load_features(metric)
        if df is None or df.empty:
            return None
        return df
    except (OSError, ValueError) as exc:
        logger.warning(
            "Failed to load features for health classifier",
            extra={"metric": metric, "error": str(exc)},
        )
        return None


def _validate_numeric_column(df: pd.DataFrame, col: str) -> bool:
    """Return True if col exists in df and is numeric."""
    if col not in df.columns:
        return False
    return bool(pd.api.types.is_numeric_dtype(df[col]))


def _aggregate_per_project(df: pd.DataFrame, feature_col: str) -> pd.DataFrame:
    """
    Reduce a per-week feature DataFrame to one row per project (column mean).

    Returns empty DataFrame if required columns are absent.
    """
    if "project" not in df.columns or feature_col not in df.columns:
        return pd.DataFrame()

    sub = df[["project", feature_col]].dropna(subset=[feature_col])
    sub = sub[sub["project"].astype(str).str.len() > 0]
    if sub.empty:
        return pd.DataFrame()

    agg = sub.groupby("project", as_index=True)[feature_col].mean().rename(feature_col)
    return agg.to_frame()


def _derive_health_label(row: pd.Series) -> str:
    """
    Rule-based health label derived from feature values.

    Used to bootstrap training labels (no pre-labelled dataset available).
    Prefers risk_score if available; otherwise uses composite of vulnerability
    count and open_bugs to determine label.
    """
    risk = row.get("risk_score")
    if pd.notna(risk):
        risk_val = float(risk)
        if risk_val <= _HEALTH_THRESHOLDS["green_max_risk"]:
            return "Green"
        if risk_val <= _HEALTH_THRESHOLDS["amber_max_risk"]:
            return "Amber"
        return "Red"

    # Fallback composite: use vulnerability count and open bugs
    vuln = row.get("total_vulnerabilities", float("nan"))
    bugs = row.get("open_bugs", float("nan"))

    score = 0.0
    count = 0

    if pd.notna(vuln):
        # Normalise: 0 vulns = 0 pts, 200+ vulns = 60 pts
        score += min(60.0, float(vuln) * 0.3)
        count += 1

    if pd.notna(bugs):
        # Normalise: 0 bugs = 0 pts, 500+ bugs = 75 pts
        score += min(75.0, float(bugs) * 0.15)
        count += 1

    if count == 0:
        return "Amber"  # No data — neutral default

    composite = score / count
    if composite <= _HEALTH_THRESHOLDS["green_max_risk"]:
        return "Green"
    if composite <= _HEALTH_THRESHOLDS["amber_max_risk"]:
        return "Amber"
    return "Red"


def _build_training_dataframe() -> tuple[pd.DataFrame, pd.Series] | tuple[None, None]:
    """
    Build (X, y) training data by loading features and deriving labels.

    Returns (None, None) if insufficient data (fewer than _MIN_SAMPLES projects).
    """
    aggregated: list[pd.DataFrame] = []

    for metric, feature_col in _FEATURE_METRIC_MAP.items():
        df = _load_metric_dataframe(metric)
        if df is None or df.empty:
            continue

        if not _validate_numeric_column(df, feature_col):
            logger.warning(
                "Feature column missing or non-numeric — skipping",
                extra={"metric": metric, "column": feature_col},
            )
            continue

        agg = _aggregate_per_project(df, feature_col)
        if not agg.empty:
            aggregated.append(agg)

    if not aggregated:
        return None, None

    # Join all metric aggregations on project index
    combined = aggregated[0]
    for frame in aggregated[1:]:
        combined = combined.join(frame, how="outer")

    # Drop projects with all features missing
    combined.dropna(how="all", inplace=True)

    # Fill remaining NaN with column means (imputation)
    combined.fillna(combined.mean(numeric_only=True), inplace=True)

    if len(combined) < _MIN_SAMPLES:
        return None, None

    # Derive labels using rule-based heuristic
    labels = combined.apply(_derive_health_label, axis=1)

    return combined, labels


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _validate_label(label_raw: str, project_name: str) -> str:
    """Validate a classifier label against the allowlist, defaulting to Amber."""
    label = str(label_raw)
    if label not in _VALID_HEALTH_LABELS:
        logger.warning(
            "Unexpected classifier label — defaulting to Amber",
            extra={"label": label, "project": project_name},
        )
        return "Amber"
    return label


def _build_classification_results(
    feature_df: pd.DataFrame,
    labels_raw: np.ndarray,
    proba: np.ndarray,
    importances: dict[str, float],
) -> list[HealthClassification]:
    """Build HealthClassification list from classifier outputs."""
    results: list[HealthClassification] = []
    for project_name, label_raw, prob_row in zip(feature_df.index, labels_raw, proba, strict=True):
        label = _validate_label(str(label_raw), str(project_name))
        confidence = round(float(max(prob_row)), 4)

        results.append(
            HealthClassification(
                timestamp=datetime.now(),
                project=str(project_name),
                label=label,
                confidence=confidence,
                feature_importances=importances,
                model_version=_MODEL_VERSION,
            )
        )
    return results


def classify_project_health(
    random_seed: int | None = 42,
) -> list[HealthClassification]:
    """
    Classify each project's health as Green, Amber, or Red.

    Uses RandomForestClassifier re-fitted each run from the feature store.
    No model serialization — re-fit is fast (<1 s for typical dataset sizes).

    Args:
        random_seed: For reproducibility.

    Returns:
        List of HealthClassification, one per project.
        Empty list if insufficient data.

    Security:
        Output labels validated against _VALID_HEALTH_LABELS.
        Confidence scores coerced to float. Feature vectors not logged.
    """
    feature_df, y = _build_training_dataframe()

    if feature_df is None or y is None or len(feature_df) < _MIN_SAMPLES:
        logger.warning(
            "Insufficient data for health classification",
            extra={"n_samples": len(feature_df) if feature_df is not None else 0},
        )
        return []

    clf = RandomForestClassifier(n_estimators=100, random_state=random_seed)
    clf.fit(feature_df, y)

    proba: np.ndarray = clf.predict_proba(feature_df)
    labels_raw: np.ndarray = clf.predict(feature_df)

    importances: dict[str, float] = {
        feat: round(float(imp), 4)
        for feat, imp in zip(feature_df.columns.tolist(), clf.feature_importances_.tolist(), strict=True)
    }

    results = _build_classification_results(feature_df, labels_raw, proba, importances)

    label_distribution = {lb: sum(1 for r in results if r.label == lb) for lb in _VALID_HEALTH_LABELS}
    logger.info(
        "Health classification complete",
        extra={
            "n_projects": len(results),
            "label_distribution": label_distribution,
        },
    )
    return results
