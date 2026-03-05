"""
Project Clustering — execution/intelligence/clustering.py

Groups projects into behavioral clusters based on engineering metric features.
Uses KMeans (default) or DBSCAN, re-fitted each run from the feature store.

Security:
- No model serialization (no pickle/joblib). Re-fit each run.
- Metric names validated against VALID_METRICS before path construction.
- Column schema validated before sklearn ingestion.
- Cluster assignments coerced to Python int (not numpy.int64).
"""

from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.preprocessing import StandardScaler

from execution.core.logging_config import get_logger
from execution.domain.intelligence import ClusterResult
from execution.intelligence.feature_engineering import VALID_METRICS, load_features

logger: logging.Logger = get_logger(__name__)

# Minimum number of projects needed to run clustering
_MIN_PROJECTS: int = 3

# Metric → column used for clustering feature
_METRIC_FEATURE_MAP: dict[str, str] = {
    "quality": "open_bugs",
    "flow": "lead_time_p85",
    "deployment": "deploy_frequency",
    "security": "total_vulnerabilities",
}

# Human-readable feature names aligned to columns pulled from the feature store
_CLUSTER_FEATURE_NAMES: list[str] = [
    "open_bugs",
    "lead_time_p85",
    "deploy_frequency",
    "total_vulnerabilities",
]

# Expected numeric column types (used for schema validation)
_EXPECTED_NUMERIC: frozenset[str] = frozenset(_CLUSTER_FEATURE_NAMES)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_cluster_dataframe(metric: str) -> pd.DataFrame | None:
    """
    Load features for a metric from the Parquet feature store.
    Returns None if unavailable or insufficient data.

    Security: metric validated against VALID_METRICS before any path construction.
    """
    if metric not in VALID_METRICS:
        logger.warning(
            "Invalid metric for clustering",
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
            "Failed to load features",
            extra={"metric": metric, "error": str(exc)},
        )
        return None


def _validate_numeric_columns(df: pd.DataFrame, expected_cols: list[str]) -> list[str]:
    """
    Validate that expected columns exist and are numeric.

    Returns the list of valid numeric columns that are actually present.
    Logs a warning for any column that is absent or non-numeric.
    """
    valid: list[str] = []
    for col in expected_cols:
        if col not in df.columns:
            logger.warning(
                "Expected cluster feature column missing",
                extra={"column": col},
            )
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            logger.warning(
                "Cluster feature column is not numeric — skipping",
                extra={"column": col, "dtype": str(df[col].dtype)},
            )
            continue
        valid.append(col)
    return valid


def _aggregate_per_project(df: pd.DataFrame, feature_col: str) -> pd.DataFrame:
    """
    Aggregate a per-week feature DataFrame to one row per project.

    Uses the mean of the feature column, excluding rows without a project
    value or a valid numeric entry in feature_col.
    """
    if "project" not in df.columns or feature_col not in df.columns:
        return pd.DataFrame()

    sub = df[["project", feature_col]].dropna(subset=[feature_col])
    sub = sub[sub["project"].astype(str).str.len() > 0]

    if sub.empty:
        return pd.DataFrame()

    agg = sub.groupby("project", as_index=True)[feature_col].mean().rename(feature_col)
    return agg.to_frame()


def _build_feature_matrix(
    dfs: dict[str, pd.DataFrame],
    feature_map: dict[str, str],
) -> tuple[pd.DataFrame, list[str]] | tuple[None, None]:
    """
    Build a project × feature matrix from multiple metric DataFrames.

    Validates column schema before aggregation.
    Returns (feature_df, project_list) or (None, None) if insufficient data.
    """
    aggregated_frames: list[pd.DataFrame] = []

    for metric, feature_col in feature_map.items():
        df = dfs.get(metric)
        if df is None or df.empty:
            continue

        # Schema validation: confirm the feature column is numeric
        valid_cols = _validate_numeric_columns(df, [feature_col])
        if not valid_cols:
            continue

        agg = _aggregate_per_project(df, feature_col)
        if not agg.empty:
            aggregated_frames.append(agg)

    if not aggregated_frames:
        return None, None

    # Outer join on project index — missing metrics get NaN
    combined = aggregated_frames[0]
    for frame in aggregated_frames[1:]:
        combined = combined.join(frame, how="outer")

    # Drop projects that have ALL features missing
    combined.dropna(how="all", inplace=True)

    # Fill remaining NaN with column mean (imputation)
    combined.fillna(combined.mean(numeric_only=True), inplace=True)

    # Validate that remaining columns are numeric
    valid_numeric = _validate_numeric_columns(combined, list(combined.columns))
    if not valid_numeric:
        return None, None

    combined = combined[valid_numeric]

    if len(combined) < _MIN_PROJECTS:
        return None, None

    projects = [str(p) for p in combined.index.tolist()]
    return combined, projects


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def cluster_projects(
    algorithm: str = "kmeans",
    n_clusters: int = 3,
    random_seed: int | None = 42,
) -> list[ClusterResult]:
    """
    Cluster projects based on engineering metric features.

    Re-fits the clustering model each run — no model persistence.

    Args:
        algorithm:    "kmeans" (default) or "dbscan".
        n_clusters:   Number of clusters for KMeans (ignored for DBSCAN).
        random_seed:  For reproducibility (KMeans only).

    Returns:
        List of ClusterResult, one per project. Empty list if insufficient data.

    Security:
        Cluster IDs are coerced to Python int. Feature vectors stored for
        transparency but never logged at row level.
    """
    # Load all relevant metric DataFrames
    dfs: dict[str, pd.DataFrame] = {}
    for metric in _METRIC_FEATURE_MAP:
        loaded = _load_cluster_dataframe(metric)
        if loaded is not None:
            dfs[metric] = loaded

    if not dfs:
        logger.warning(
            "No feature data available for clustering",
            extra={"algorithm": algorithm},
        )
        return []

    feature_df, projects = _build_feature_matrix(dfs, _METRIC_FEATURE_MAP)

    if feature_df is None or projects is None or len(projects) < _MIN_PROJECTS:
        logger.warning(
            "Insufficient projects for clustering",
            extra={
                "n_projects": len(projects) if projects else 0,
                "min_required": _MIN_PROJECTS,
            },
        )
        return []

    # Normalise features with StandardScaler
    scaler = StandardScaler()
    x_scaled: np.ndarray = scaler.fit_transform(feature_df.values)

    # Fit clustering model
    if algorithm == "dbscan":
        model = DBSCAN(eps=0.5, min_samples=2)
        labels: np.ndarray = model.fit_predict(x_scaled)
        unique_labels = set(labels.tolist()) - {-1}
        n_found = int(len(unique_labels))
    else:
        # Default: KMeans
        safe_k = min(n_clusters, len(projects))
        model_km = KMeans(n_clusters=safe_k, n_init=10, random_state=random_seed)
        labels = model_km.fit_predict(x_scaled)
        n_found = int(safe_k)

    feature_names = feature_df.columns.tolist()

    results: list[ClusterResult] = []
    for i, project_name in enumerate(projects):
        raw_vector = feature_df.iloc[i]
        feature_vector = {feat: round(float(raw_vector[feat]), 4) for feat in feature_names if feat in raw_vector.index}
        results.append(
            ClusterResult(
                project=str(project_name),
                cluster_id=int(labels[i]),  # Coerce numpy.int64 → Python int
                algorithm=algorithm,
                n_clusters=n_found,
                feature_vector=feature_vector,
            )
        )

    logger.info(
        "Clustering complete",
        extra={
            "n_projects": len(results),
            "n_clusters_found": n_found,
            "algorithm": algorithm,
        },
    )
    return results
