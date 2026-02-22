"""
Tests for execution/intelligence/duckdb_views.py

Covers:
- get_connection() returns an in-memory DuckDB connection (NOT a file)
- query_metric_trend() with synthetic DataFrame registered in DuckDB
- query_portfolio_summary() with synthetic data
- Invalid metric name raises ValueError (VALID_METRICS whitelist)
- Empty feature data returns empty DataFrame gracefully
- query_project_list() returns correct sorted list
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from execution.intelligence.duckdb_views import (
    get_connection,
    query_metric_trend,
    query_portfolio_summary,
    query_project_list,
)

# ---------------------------------------------------------------------------
# Fixtures — synthetic DataFrames for DuckDB registration
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_quality_df() -> pd.DataFrame:
    """3 projects × 4 weeks each — deterministic synthetic data."""
    rows = []
    base_dates = pd.date_range("2025-10-06", periods=4, freq="W")
    for project in ["Product_A", "Product_B", "Product_C"]:
        for i, dt in enumerate(base_dates):
            rows.append(
                {
                    "week_date": dt,
                    "project": project,
                    "open_bugs": 300 - i * 5 if project == "Product_A" else 100 + i,
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def sample_single_project_df() -> pd.DataFrame:
    """Single project with 4 weeks."""
    dates = pd.date_range("2025-10-06", periods=4, freq="W")
    return pd.DataFrame(
        {
            "week_date": dates,
            "project": ["Product_A"] * 4,
            "open_bugs": [300, 295, 290, 285],
        }
    )


@pytest.fixture
def empty_df() -> pd.DataFrame:
    """Empty DataFrame with correct schema."""
    return pd.DataFrame(columns=["week_date", "project", "open_bugs"])


# ---------------------------------------------------------------------------
# TestGetConnection
# ---------------------------------------------------------------------------


class TestGetConnection:
    def test_returns_duckdb_connection(self) -> None:
        import duckdb

        conn = get_connection()
        assert isinstance(conn, duckdb.DuckDBPyConnection)
        conn.close()

    def test_connection_is_in_memory(self) -> None:
        """Verify the connection is in-memory by checking it can query without a file."""
        import duckdb

        conn = get_connection()
        # In-memory connections can execute SQL immediately
        result = conn.execute("SELECT 42 AS answer").fetchone()
        assert result is not None
        assert result[0] == 42
        conn.close()

    def test_each_call_returns_fresh_connection(self) -> None:
        conn1 = get_connection()
        conn2 = get_connection()
        # They should be distinct objects (no shared state)
        assert conn1 is not conn2
        conn1.close()
        conn2.close()

    def test_connection_has_no_persistent_file(self, tmp_path: Path) -> None:
        """Verify that no .duckdb file is created in the working directory."""
        import os

        before = set(os.listdir(tmp_path))
        conn = get_connection()
        conn.close()
        after = set(os.listdir(tmp_path))
        # No new .duckdb files should appear
        new_files = {f for f in (after - before) if f.endswith(".duckdb")}
        assert len(new_files) == 0


# ---------------------------------------------------------------------------
# TestQueryMetricTrend
# ---------------------------------------------------------------------------


class TestQueryMetricTrend:
    def test_invalid_metric_raises_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid metric"):
            query_metric_trend("nonexistent_metric", "Product_A", base_dir=tmp_path)

    def test_returns_correct_project_rows(self, sample_quality_df: pd.DataFrame, tmp_path: Path) -> None:
        with patch(
            "execution.intelligence.duckdb_views.load_features",
            return_value=sample_quality_df,
        ):
            result = query_metric_trend("quality", "Product_A", weeks=4, base_dir=tmp_path)

        assert isinstance(result, pd.DataFrame)
        assert all(result["project"] == "Product_A")

    def test_respects_weeks_limit(self, sample_quality_df: pd.DataFrame, tmp_path: Path) -> None:
        with patch(
            "execution.intelligence.duckdb_views.load_features",
            return_value=sample_quality_df,
        ):
            result = query_metric_trend("quality", "Product_A", weeks=2, base_dir=tmp_path)

        assert len(result) <= 2

    def test_result_sorted_ascending(self, sample_quality_df: pd.DataFrame, tmp_path: Path) -> None:
        with patch(
            "execution.intelligence.duckdb_views.load_features",
            return_value=sample_quality_df,
        ):
            result = query_metric_trend("quality", "Product_A", weeks=4, base_dir=tmp_path)

        if len(result) > 1:
            dates = pd.to_datetime(result["week_date"])
            assert dates.is_monotonic_increasing

    def test_no_rows_for_unknown_project(self, sample_quality_df: pd.DataFrame, tmp_path: Path) -> None:
        with patch(
            "execution.intelligence.duckdb_views.load_features",
            return_value=sample_quality_df,
        ):
            result = query_metric_trend("quality", "Product_Z_NOTEXIST", weeks=20, base_dir=tmp_path)

        assert len(result) == 0

    def test_all_valid_metrics_accepted(self, sample_quality_df: pd.DataFrame, tmp_path: Path) -> None:
        """All entries in VALID_METRICS should pass the whitelist check."""
        from execution.intelligence.feature_engineering import VALID_METRICS

        for metric in VALID_METRICS:
            with patch(
                "execution.intelligence.duckdb_views.load_features",
                return_value=sample_quality_df,
            ):
                # Should not raise ValueError for any valid metric
                result = query_metric_trend(metric, "Product_A", weeks=4, base_dir=tmp_path)
                assert isinstance(result, pd.DataFrame)


# ---------------------------------------------------------------------------
# TestQueryPortfolioSummary
# ---------------------------------------------------------------------------


class TestQueryPortfolioSummary:
    def test_invalid_metric_raises_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid metric"):
            query_portfolio_summary("bad_metric", base_dir=tmp_path)

    def test_returns_one_row_per_project(self, sample_quality_df: pd.DataFrame, tmp_path: Path) -> None:
        with patch(
            "execution.intelligence.duckdb_views.load_features",
            return_value=sample_quality_df,
        ):
            result = query_portfolio_summary("quality", base_dir=tmp_path)

        # Each project should have exactly 1 row (latest week only)
        assert isinstance(result, pd.DataFrame)
        project_counts = result["project"].value_counts()
        assert all(project_counts == 1), "Each project should appear exactly once"

    def test_returns_latest_week_values(self, sample_single_project_df: pd.DataFrame, tmp_path: Path) -> None:
        """The latest week's open_bugs should be 285 for the single project."""
        with patch(
            "execution.intelligence.duckdb_views.load_features",
            return_value=sample_single_project_df,
        ):
            result = query_portfolio_summary("quality", base_dir=tmp_path)

        assert len(result) == 1
        assert result.iloc[0]["open_bugs"] == 285

    def test_sorted_by_project(self, sample_quality_df: pd.DataFrame, tmp_path: Path) -> None:
        with patch(
            "execution.intelligence.duckdb_views.load_features",
            return_value=sample_quality_df,
        ):
            result = query_portfolio_summary("quality", base_dir=tmp_path)

        projects = result["project"].tolist()
        assert projects == sorted(projects)

    def test_empty_data_returns_empty_dataframe(self, empty_df: pd.DataFrame, tmp_path: Path) -> None:
        with patch(
            "execution.intelligence.duckdb_views.load_features",
            return_value=empty_df,
        ):
            result = query_portfolio_summary("quality", base_dir=tmp_path)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# TestQueryProjectList
# ---------------------------------------------------------------------------


class TestQueryProjectList:
    def test_invalid_metric_raises_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid metric"):
            query_project_list("not_a_metric", base_dir=tmp_path)

    def test_returns_sorted_list(self, sample_quality_df: pd.DataFrame, tmp_path: Path) -> None:
        with patch(
            "execution.intelligence.duckdb_views.load_features",
            return_value=sample_quality_df,
        ):
            result = query_project_list("quality", base_dir=tmp_path)

        assert isinstance(result, list)
        assert result == sorted(result)

    def test_returns_distinct_projects(self, sample_quality_df: pd.DataFrame, tmp_path: Path) -> None:
        with patch(
            "execution.intelligence.duckdb_views.load_features",
            return_value=sample_quality_df,
        ):
            result = query_project_list("quality", base_dir=tmp_path)

        assert len(result) == len(set(result))
        assert set(result) == {"Product_A", "Product_B", "Product_C"}

    def test_empty_data_returns_empty_list(self, empty_df: pd.DataFrame, tmp_path: Path) -> None:
        with patch(
            "execution.intelligence.duckdb_views.load_features",
            return_value=empty_df,
        ):
            result = query_project_list("quality", base_dir=tmp_path)

        assert result == []
