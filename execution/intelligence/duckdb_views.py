"""
DuckDB Views — execution/intelligence/duckdb_views.py

Single responsibility: Provides analytical SQL queries over feature Parquet files via DuckDB.

Uses in-memory DuckDB (no persistent .duckdb file) to avoid path traversal risks.
All SQL identifier interpolation uses the VALID_METRICS whitelist before substitution.
All SQL value filters use parameterized queries.

Security requirements satisfied:
- VALID_METRICS imported from feature_engineering (Phase B cond. 1 — defined once)
- SQL identifiers validated against VALID_METRICS before interpolation (Phase B cond. 3)
- Parameterized queries for all value filters (Phase B cond. 3)
- In-memory DuckDB: no persistent .db file, no path traversal surface (Phase B cond. 3)
"""

import logging
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from execution.core.logging_config import get_logger
from execution.intelligence.feature_engineering import VALID_METRICS, load_features

logger: logging.Logger = get_logger(__name__)

# Default feature store directory (injectable for testing)
_DEFAULT_FEATURE_DIR: Path = Path("data/features")


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------


def get_connection() -> duckdb.DuckDBPyConnection:
    """
    Return a new in-memory DuckDB connection.

    Each call returns a fresh connection with no shared state between calls.
    In-memory mode is used exclusively — no persistent .duckdb file is ever
    created, which eliminates path traversal risk entirely.

    Returns:
        A new duckdb.DuckDBPyConnection instance (in-memory).
    """
    return duckdb.connect(database=":memory:")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _assert_valid_metric(metric: str) -> None:
    """
    Raise ValueError if metric is not in VALID_METRICS.

    Must be called before any SQL identifier interpolation involving metric names
    to prevent SQL injection via crafted metric strings.
    """
    if metric not in VALID_METRICS:
        raise ValueError(f"Invalid metric '{metric}'. " f"Allowed values: {sorted(VALID_METRICS)}")


def _load_into_connection(
    conn: duckdb.DuckDBPyConnection,
    metric: str,
    base_dir: Path,
) -> None:
    """
    Load the latest feature Parquet for a metric into a DuckDB connection as a view.

    The view name is ``features`` (fixed identifier — not derived from user input).
    The Parquet file path is built from the whitelisted metric name.

    Args:
        conn: In-memory DuckDB connection.
        metric: Metric name — must be in VALID_METRICS (caller's responsibility).
        base_dir: Directory containing feature Parquet files.

    Raises:
        ValueError: If no Parquet file exists for the metric.
    """
    # Use load_features() to get the latest DataFrame, then register it as a table.
    # This avoids passing a file path into DuckDB SQL (no SQL path injection surface).
    df = load_features(metric=metric, base_dir=base_dir)
    conn.register("features", df)


# ---------------------------------------------------------------------------
# Public query functions
# ---------------------------------------------------------------------------


def query_metric_trend(
    metric: str,
    project: str,
    weeks: int = 20,
    base_dir: Path = _DEFAULT_FEATURE_DIR,
) -> pd.DataFrame:
    """
    Return the last N weeks of a metric for a project as a DataFrame.

    SQL safety:
    - ``metric`` is validated against VALID_METRICS before use.
    - ``project`` and ``weeks`` are passed as parameterized values — never
      interpolated into the SQL string.

    Args:
        metric: Metric name — must be in VALID_METRICS.
        project: Project key to filter on (e.g. "Product_A").
        weeks: Number of most-recent weeks to return (default 20).
        base_dir: Feature Parquet directory.

    Returns:
        DataFrame sorted by week_date ascending, limited to ``weeks`` rows.

    Raises:
        ValueError: If metric is not in VALID_METRICS or no data is available.
    """
    _assert_valid_metric(metric)

    conn = get_connection()
    try:
        _load_into_connection(conn, metric, base_dir)

        # Parameterized query: project and weeks are bound values, not interpolated.
        # The table name "features" is a fixed literal (not from user input).
        result: pd.DataFrame = conn.execute(
            """
            SELECT *
            FROM features
            WHERE project = ?
            ORDER BY week_date ASC
            LIMIT ?
            """,
            [project, weeks],
        ).df()
    finally:
        conn.close()

    logger.info(
        "Metric trend query complete",
        extra={"metric": metric, "project": project, "rows": len(result)},
    )
    return result


def query_portfolio_summary(
    metric: str,
    base_dir: Path = _DEFAULT_FEATURE_DIR,
) -> pd.DataFrame:
    """
    Return per-project latest values for a metric.

    For each project in the feature store, returns the most recent week's data row.

    SQL safety:
    - ``metric`` is validated against VALID_METRICS before use.
    - The table name "features" is a fixed literal (not from user input).
    - No user-supplied values are interpolated into SQL strings.

    Args:
        metric: Metric name — must be in VALID_METRICS.
        base_dir: Feature Parquet directory.

    Returns:
        DataFrame with one row per project (latest week only), sorted by project.

    Raises:
        ValueError: If metric is not in VALID_METRICS or no data is available.
    """
    _assert_valid_metric(metric)

    conn = get_connection()
    try:
        _load_into_connection(conn, metric, base_dir)

        result: pd.DataFrame = conn.execute("""
            SELECT *
            FROM features
            WHERE week_date = (
                SELECT MAX(week_date) FROM features WHERE project = features.project
            )
            ORDER BY project ASC
            """).df()
    finally:
        conn.close()

    logger.info(
        "Portfolio summary query complete",
        extra={"metric": metric, "projects": len(result)},
    )
    return result


def query_project_list(
    metric: str,
    base_dir: Path = _DEFAULT_FEATURE_DIR,
) -> list[str]:
    """
    Return the sorted list of distinct project keys available for a metric.

    Args:
        metric: Metric name — must be in VALID_METRICS.
        base_dir: Feature Parquet directory.

    Returns:
        Sorted list of project key strings.

    Raises:
        ValueError: If metric is not in VALID_METRICS or no data is available.
    """
    _assert_valid_metric(metric)

    conn = get_connection()
    try:
        _load_into_connection(conn, metric, base_dir)
        result = conn.execute("SELECT DISTINCT project FROM features ORDER BY project ASC").fetchall()
    finally:
        conn.close()

    projects = [row[0] for row in result]
    logger.info(
        "Project list query complete",
        extra={"metric": metric, "project_count": len(projects)},
    )
    return projects
