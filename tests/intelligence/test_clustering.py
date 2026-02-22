"""
Tests for execution/intelligence/clustering.py

Single responsibility: verify that project clustering produces valid, correctly
typed results from synthetic feature DataFrames.

All fixtures use synthetic data only — no real project names, no real ADO data.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from execution.domain.intelligence import ClusterResult
from execution.intelligence.clustering import (
    _METRIC_FEATURE_MAP,
    _MIN_PROJECTS,
    _build_feature_matrix,
    _load_cluster_dataframe,
    cluster_projects,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature_df(n_rows: int = 5, metric: str = "quality") -> pd.DataFrame:
    """
    Synthetic feature DataFrame with project + relevant columns.

    Mirrors the structure produced by feature_engineering.extract_features().
    """
    from datetime import datetime, timedelta

    rng = np.random.default_rng(42)
    base = datetime(2025, 10, 6)
    dates = [base + timedelta(weeks=i) for i in range(n_rows)]

    if metric == "quality":
        return pd.DataFrame(
            {
                "week_date": dates,
                "project": [f"Product_{chr(65 + i)}" for i in range(n_rows)],
                "open_bugs": rng.integers(10, 300, n_rows).tolist(),
                "closed_bugs": rng.integers(5, 100, n_rows).tolist(),
            }
        )
    if metric == "flow":
        return pd.DataFrame(
            {
                "week_date": dates,
                "project": [f"Product_{chr(65 + i)}" for i in range(n_rows)],
                "lead_time_p85": rng.normal(30, 10, n_rows).tolist(),
                "wip": rng.integers(10, 200, n_rows).tolist(),
            }
        )
    if metric == "deployment":
        return pd.DataFrame(
            {
                "week_date": dates,
                "project": [f"Product_{chr(65 + i)}" for i in range(n_rows)],
                "deploy_frequency": rng.normal(3, 1, n_rows).tolist(),
                "build_success_rate": rng.uniform(70, 99, n_rows).tolist(),
            }
        )
    if metric == "security":
        return pd.DataFrame(
            {
                "week_date": dates,
                "project": [f"Product_{chr(65 + i)}" for i in range(n_rows)],
                "total_vulnerabilities": rng.integers(0, 500, n_rows).tolist(),
                "critical": rng.integers(0, 50, n_rows).tolist(),
            }
        )
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": [f"Product_{chr(65 + i)}" for i in range(n_rows)],
        }
    )


def _multi_metric_side_effect(metric: str, n_rows: int = 6) -> pd.DataFrame:
    """Side-effect factory: returns an appropriate df per metric."""
    return _make_feature_df(n_rows=n_rows, metric=metric)


# ---------------------------------------------------------------------------
# Tests: _load_cluster_dataframe
# ---------------------------------------------------------------------------


def test_load_cluster_dataframe_rejects_invalid_metric() -> None:
    """_load_cluster_dataframe returns None for metrics not in VALID_METRICS."""
    result = _load_cluster_dataframe("not_a_real_metric_xyz")
    assert result is None


def test_load_cluster_dataframe_returns_none_on_os_error() -> None:
    """_load_cluster_dataframe returns None when load_features raises OSError."""
    with patch(
        "execution.intelligence.clustering.load_features",
        side_effect=OSError("disk error"),
    ):
        result = _load_cluster_dataframe("quality")
    assert result is None


def test_load_cluster_dataframe_returns_none_on_value_error() -> None:
    """_load_cluster_dataframe returns None when load_features raises ValueError."""
    with patch(
        "execution.intelligence.clustering.load_features",
        side_effect=ValueError("no parquet"),
    ):
        result = _load_cluster_dataframe("quality")
    assert result is None


def test_load_cluster_dataframe_returns_none_for_empty_df() -> None:
    """_load_cluster_dataframe returns None when load_features returns empty df."""
    with patch(
        "execution.intelligence.clustering.load_features",
        return_value=pd.DataFrame(),
    ):
        result = _load_cluster_dataframe("quality")
    assert result is None


# ---------------------------------------------------------------------------
# Tests: _build_feature_matrix
# ---------------------------------------------------------------------------


def test_build_feature_matrix_returns_none_when_no_data() -> None:
    """_build_feature_matrix returns (None, None) when all metrics missing."""
    result_df, result_projects = _build_feature_matrix({}, _METRIC_FEATURE_MAP)
    assert result_df is None
    assert result_projects is None


def test_build_feature_matrix_returns_none_when_too_few_projects() -> None:
    """_build_feature_matrix returns (None, None) with < _MIN_PROJECTS rows."""
    tiny_df = _make_feature_df(n_rows=2, metric="quality")
    dfs = {"quality": tiny_df}
    result_df, result_projects = _build_feature_matrix(dfs, _METRIC_FEATURE_MAP)
    assert result_df is None
    assert result_projects is None


def test_build_feature_matrix_returns_dataframe_with_enough_data() -> None:
    """_build_feature_matrix returns a valid (df, projects) with sufficient data."""
    quality_df = _make_feature_df(n_rows=5, metric="quality")
    dfs = {"quality": quality_df}
    feature_map = {"quality": "open_bugs"}
    result_df, result_projects = _build_feature_matrix(dfs, feature_map)
    assert result_df is not None
    assert result_projects is not None
    assert len(result_projects) >= _MIN_PROJECTS


# ---------------------------------------------------------------------------
# Tests: cluster_projects — return type
# ---------------------------------------------------------------------------


def test_cluster_projects_returns_list() -> None:
    """cluster_projects() should return a list."""

    def _side_effect(metric: str, **kwargs: object) -> pd.DataFrame:
        return _make_feature_df(n_rows=6, metric=metric)

    with patch(
        "execution.intelligence.clustering.load_features",
        side_effect=_side_effect,
    ):
        result = cluster_projects(algorithm="kmeans", n_clusters=2)

    assert isinstance(result, list)


def test_cluster_result_has_correct_types() -> None:
    """Each ClusterResult should have int cluster_id and str project."""

    def _side_effect(metric: str, **kwargs: object) -> pd.DataFrame:
        return _make_feature_df(n_rows=6, metric=metric)

    with patch(
        "execution.intelligence.clustering.load_features",
        side_effect=_side_effect,
    ):
        results = cluster_projects(algorithm="kmeans", n_clusters=2)

    for r in results:
        assert isinstance(r.cluster_id, int), "cluster_id must be Python int, not numpy.int64"
        assert isinstance(r.project, str)
        assert isinstance(r.feature_vector, dict)
        assert isinstance(r.algorithm, str)
        assert isinstance(r.n_clusters, int)


def test_cluster_id_is_python_int_not_numpy() -> None:
    """cluster_id must be Python int (not numpy.int64) at all output boundaries."""

    def _side_effect(metric: str, **kwargs: object) -> pd.DataFrame:
        return _make_feature_df(n_rows=5, metric=metric)

    with patch(
        "execution.intelligence.clustering.load_features",
        side_effect=_side_effect,
    ):
        results = cluster_projects(algorithm="kmeans", n_clusters=2)

    for r in results:
        assert type(r.cluster_id) is int, f"Expected int, got {type(r.cluster_id)}"


def test_feature_vector_values_are_python_floats() -> None:
    """Feature vector values must be Python float (rounded to 4 decimal places)."""

    def _side_effect(metric: str, **kwargs: object) -> pd.DataFrame:
        return _make_feature_df(n_rows=5, metric=metric)

    with patch(
        "execution.intelligence.clustering.load_features",
        side_effect=_side_effect,
    ):
        results = cluster_projects(algorithm="kmeans", n_clusters=2)

    for r in results:
        for k, v in r.feature_vector.items():
            assert isinstance(v, float), f"feature_vector[{k}] must be Python float"


# ---------------------------------------------------------------------------
# Tests: cluster_projects — insufficient data
# ---------------------------------------------------------------------------


def test_cluster_projects_insufficient_data_returns_empty() -> None:
    """With fewer than _MIN_PROJECTS projects, should return empty list."""

    def _side_effect(metric: str, **kwargs: object) -> pd.DataFrame:
        return _make_feature_df(n_rows=1, metric=metric)

    with patch(
        "execution.intelligence.clustering.load_features",
        side_effect=_side_effect,
    ):
        result = cluster_projects()

    assert result == []


def test_cluster_projects_no_features_returns_empty() -> None:
    """When all load_features calls fail, should return empty list."""
    with patch(
        "execution.intelligence.clustering.load_features",
        side_effect=ValueError("no parquet found"),
    ):
        result = cluster_projects()

    assert result == []


# ---------------------------------------------------------------------------
# Tests: DBSCAN algorithm path
# ---------------------------------------------------------------------------


def test_dbscan_noise_point_cluster_id_is_negative_one() -> None:
    """DBSCAN may assign cluster_id -1 to noise points — must be int."""

    def _side_effect(metric: str, **kwargs: object) -> pd.DataFrame:
        return _make_feature_df(n_rows=10, metric=metric)

    with patch(
        "execution.intelligence.clustering.load_features",
        side_effect=_side_effect,
    ):
        results = cluster_projects(algorithm="dbscan")

    # All cluster_ids must be Python int, including -1 for noise
    for r in results:
        assert isinstance(r.cluster_id, int)
        assert r.algorithm == "dbscan"


def test_dbscan_results_algorithm_field() -> None:
    """ClusterResult.algorithm field must reflect the algorithm used."""

    def _side_effect(metric: str, **kwargs: object) -> pd.DataFrame:
        return _make_feature_df(n_rows=6, metric=metric)

    with patch(
        "execution.intelligence.clustering.load_features",
        side_effect=_side_effect,
    ):
        results = cluster_projects(algorithm="dbscan")

    for r in results:
        assert r.algorithm == "dbscan"


def test_kmeans_results_algorithm_field() -> None:
    """ClusterResult.algorithm field must be 'kmeans' when using KMeans."""

    def _side_effect(metric: str, **kwargs: object) -> pd.DataFrame:
        return _make_feature_df(n_rows=6, metric=metric)

    with patch(
        "execution.intelligence.clustering.load_features",
        side_effect=_side_effect,
    ):
        results = cluster_projects(algorithm="kmeans", n_clusters=2)

    for r in results:
        assert r.algorithm == "kmeans"


# ---------------------------------------------------------------------------
# Tests: ClusterResult domain model
# ---------------------------------------------------------------------------


def test_cluster_result_from_dict_roundtrip() -> None:
    """ClusterResult.from_dict should deserialise correctly."""
    data = {
        "project": "Product_A",
        "cluster_id": 2,
        "algorithm": "kmeans",
        "n_clusters": 3,
        "feature_vector": {"open_bugs": 0.5, "lead_time_p85": 1.2},
    }
    cr = ClusterResult.from_dict(data)
    assert cr.project == "Product_A"
    assert cr.cluster_id == 2
    assert cr.algorithm == "kmeans"
    assert cr.n_clusters == 3
    assert cr.feature_vector["open_bugs"] == 0.5


def test_cluster_result_default_feature_vector() -> None:
    """ClusterResult with no feature_vector key defaults to empty dict."""
    data = {
        "project": "Product_B",
        "cluster_id": 0,
        "algorithm": "dbscan",
        "n_clusters": 1,
    }
    cr = ClusterResult.from_dict(data)
    assert cr.feature_vector == {}


def test_cluster_result_cluster_id_coerced_from_string() -> None:
    """ClusterResult.from_dict coerces cluster_id to int."""
    data = {
        "project": "Product_C",
        "cluster_id": "1",
        "algorithm": "kmeans",
        "n_clusters": 2,
    }
    cr = ClusterResult.from_dict(data)
    assert cr.cluster_id == 1
    assert isinstance(cr.cluster_id, int)
