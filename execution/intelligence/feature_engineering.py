"""
Feature Engineering — execution/intelligence/feature_engineering.py

Single responsibility: Extracts and stores feature DataFrames from history JSON files.

Reads weekly JSON history files from .tmp/observatory/ and transforms them into
structured Parquet feature files in data/features/ for use by forecast_engine.py
and anomaly_detector.py.

Security requirements satisfied:
- VALID_METRICS whitelist for all metric name → filename construction (Phase B cond. 1)
- PathValidator.validate_safe_path() called before every Parquet write (Phase B cond. 2)
- Parquet outputs contain only generic project names (source data already genericized,
  Phase B cond. 4)
"""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from execution.core.logging_config import get_logger
from execution.security.path_validator import PathValidator
from execution.security.validation import ValidationError

logger: logging.Logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# VALID_METRICS — single source of truth for allowed metric names.
# Imported by duckdb_views.py and any other module that constructs metric
# filenames or SQL identifiers.  DO NOT redefine this constant elsewhere.
# ---------------------------------------------------------------------------
VALID_METRICS: frozenset[str] = frozenset(
    {
        "quality",
        "security",
        "flow",
        "deployment",
        "ownership",
        "risk",
        "collaboration",
        "exploitable",
    }
)

# Base directory for history files (relative to project root at runtime)
_HISTORY_DIR: Path = Path(".tmp/observatory")

# Mapping: metric name → history filename
_HISTORY_FILES: dict[str, str] = {
    "quality": "quality_history.json",
    "security": "security_history.json",
    "flow": "flow_history.json",
    "deployment": "deployment_history.json",
    "ownership": "ownership_history.json",
    "risk": "risk_history.json",
    "collaboration": "collaboration_history.json",
    "exploitable": "exploitable_history.json",
}


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------


def _validate_metric(metric: str) -> None:
    """Raise ValueError if metric is not in VALID_METRICS whitelist."""
    if metric not in VALID_METRICS:
        raise ValueError(f"Invalid metric '{metric}'. " f"Allowed values: {sorted(VALID_METRICS)}")


# ---------------------------------------------------------------------------
# Per-metric extraction helpers
# ---------------------------------------------------------------------------


def _extract_quality_row(week_date: str, project: dict) -> dict:
    """Extract quality feature columns from one project snapshot."""
    return {
        "week_date": week_date,
        "project": project.get("project_key", ""),
        "open_bugs": project.get("open_bugs_count"),
        "p1_bugs": None,  # Not in current schema; reserved for future collector
        "closed_bugs": project.get("total_bugs_analyzed"),
        "median_age_days": (project.get("bug_age_distribution", {}).get("median_age_days")),
        "mttr_days": project.get("mttr", {}).get("mttr_days"),
    }


def _extract_security_row(week_date: str, metrics: dict) -> list[dict]:
    """
    Extract security feature rows from one week's top-level metrics dict.

    Security history is keyed by numeric ArmorCode product IDs, not project names.
    Each ID becomes its own row so the DataFrame stays tidy.
    """
    rows: list[dict] = []
    total_critical = metrics.get("severity_breakdown", {}).get("critical", 0)
    total_high = metrics.get("severity_breakdown", {}).get("high", 0)
    total_vulns = metrics.get("current_total", 0)

    # Portfolio-level row (project = "_portfolio")
    rows.append(
        {
            "week_date": week_date,
            "project": "_portfolio",
            "total_vulnerabilities": total_vulns,
            "critical": total_critical,
            "high": total_high,
        }
    )

    # Per-product-ID rows
    for product_id, breakdown in metrics.get("product_breakdown", {}).items():
        rows.append(
            {
                "week_date": week_date,
                "project": str(product_id),
                "total_vulnerabilities": breakdown.get("total", 0),
                "critical": breakdown.get("critical", 0),
                "high": breakdown.get("high", 0),
            }
        )
    return rows


def _extract_flow_row(week_date: str, project: dict) -> dict:
    """Extract flow feature columns from one project snapshot."""
    # Aggregate across work types for representative Bug lead time
    bug_metrics = project.get("work_type_metrics", {}).get("Bug", {})
    lead_time = bug_metrics.get("lead_time", {})
    throughput = bug_metrics.get("throughput", {})
    return {
        "week_date": week_date,
        "project": project.get("project_key", ""),
        "throughput": throughput.get("per_week"),
        "lead_time_p85": lead_time.get("p85"),
        "wip": bug_metrics.get("wip"),
    }


def _extract_deployment_row(week_date: str, project: dict) -> dict:
    """Extract deployment feature columns from one project snapshot."""
    return {
        "week_date": week_date,
        "project": project.get("project_key", ""),
        "build_success_rate": (project.get("build_success_rate", {}).get("success_rate_pct")),
        "deploy_frequency": (project.get("deployment_frequency", {}).get("deployments_per_week")),
    }


def _extract_ownership_row(week_date: str, project: dict) -> dict:
    """Extract ownership feature columns from one project snapshot."""
    unassigned = project.get("unassigned", {})
    total = unassigned.get("total_items", 0)
    unassigned_count = unassigned.get("unassigned_count", 0)
    unassigned_pct = unassigned.get("unassigned_pct")

    # stale_work_pct: items with no assignment beyond threshold (not directly stored;
    # approximate from aging_items if available, else None)
    stale_work_pct = None

    return {
        "week_date": week_date,
        "project": project.get("project_key", ""),
        "unassigned_pct": unassigned_pct,
        "unassigned_count": unassigned_count,
        "total_items": total,
        "stale_work_pct": stale_work_pct,
    }


# ---------------------------------------------------------------------------
# Generic fallback extractor for metrics without dedicated helpers
# ---------------------------------------------------------------------------


def _extract_generic_projects_rows(week_date: str, projects: list) -> list[dict]:
    """Return minimal rows for metrics that have a projects list but no dedicated extractor."""
    rows: list[dict] = []
    for project in projects:
        rows.append(
            {
                "week_date": week_date,
                "project": project.get("project_key", project.get("project_name", "")),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Week-level dispatch helper (extracted to keep extract_features McCabe < 10)
# ---------------------------------------------------------------------------


def _extract_week_rows(metric: str, week_date: str, week: dict) -> list[dict]:
    """Extract feature rows for a single week entry based on metric type."""
    if metric == "security":
        return _extract_security_row(week_date, week.get("metrics", {}))
    result: list[dict] = []
    for project in week.get("projects", []):
        if metric == "quality":
            result.append(_extract_quality_row(week_date, project))
        elif metric == "flow":
            result.append(_extract_flow_row(week_date, project))
        elif metric == "deployment":
            result.append(_extract_deployment_row(week_date, project))
        elif metric == "ownership":
            result.append(_extract_ownership_row(week_date, project))
        else:
            result.extend(_extract_generic_projects_rows(week_date, [project]))
    return result


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------


def extract_features(metric: str, history_path: Path) -> pd.DataFrame:
    """
    Extract a flat feature DataFrame from one history JSON file.

    Args:
        metric: Metric name — must be in VALID_METRICS.
        history_path: Path to the history JSON file.

    Returns:
        DataFrame with columns: week_date, project, [metric-specific columns].

    Raises:
        ValueError: If metric is not in VALID_METRICS or history file is malformed.
        FileNotFoundError: If history_path does not exist.
    """
    _validate_metric(metric)

    if not history_path.exists():
        raise FileNotFoundError(f"History file not found for metric '{metric}': {history_path}")

    try:
        raw = json.loads(history_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"History file for '{metric}' contains invalid JSON: {e}") from e

    weeks = raw.get("weeks", [])
    if not isinstance(weeks, list):
        raise ValueError(
            f"History file for '{metric}' has unexpected structure: "
            f"'weeks' must be a list, got {type(weeks).__name__}"
        )

    rows: list[dict] = []

    for week in weeks:
        week_date = week.get("week_date", "")
        rows.extend(_extract_week_rows(metric, week_date, week))

    if not rows:
        logger.warning(
            "No feature rows extracted",
            extra={"metric": metric, "history_path": str(history_path)},
        )

    df = pd.DataFrame(rows)

    if not df.empty and "week_date" in df.columns:
        df["week_date"] = pd.to_datetime(df["week_date"], errors="coerce")
        df = df.sort_values("week_date").reset_index(drop=True)

    logger.info(
        "Features extracted",
        extra={"metric": metric, "rows": len(df), "columns": list(df.columns)},
    )
    return df


# ---------------------------------------------------------------------------
# Save / load helpers
# ---------------------------------------------------------------------------


def _build_filename(metric: str, today: str | None = None) -> str:
    """Build the Parquet filename for a given metric and date."""
    _validate_metric(metric)
    date_str = today or date.today().isoformat()
    return f"{metric}_features_{date_str}.parquet"


def save_features(
    df: pd.DataFrame,
    metric: str,
    base_dir: Path = Path("data/features"),
) -> Path:
    """
    Save feature DataFrame as Parquet.

    Uses PathValidator.validate_safe_path() before writing to prevent path traversal.

    Args:
        df: Feature DataFrame produced by extract_features().
        metric: Metric name — must be in VALID_METRICS.
        base_dir: Directory for Parquet output (default: data/features).

    Returns:
        Absolute Path of the written Parquet file.

    Raises:
        ValueError: If metric is not in VALID_METRICS.
        ValidationError: If the resolved output path escapes base_dir.
    """
    _validate_metric(metric)

    base_dir.mkdir(parents=True, exist_ok=True)
    filename = _build_filename(metric)

    # Security: validate path stays within base_dir before writing
    safe_path_str = PathValidator.validate_safe_path(
        base_dir=str(base_dir.resolve()),
        user_path=filename,
    )
    output_path = Path(safe_path_str)

    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, output_path)

    logger.info(
        "Feature Parquet saved",
        extra={"metric": metric, "path": str(output_path), "rows": len(df)},
    )
    return output_path


def load_features(
    metric: str,
    project: str | None = None,
    base_dir: Path = Path("data/features"),
) -> pd.DataFrame:
    """
    Load the most recent feature Parquet for a metric, with optional project filter.

    Selects the lexicographically latest file matching
    ``{metric}_features_*.parquet`` so that re-running the pipeline does not
    require callers to track file dates.

    Args:
        metric: Metric name — must be in VALID_METRICS.
        project: Optional project key to filter rows (e.g. "Product_A").
        base_dir: Directory to search for Parquet files (default: data/features).

    Returns:
        DataFrame with all feature columns, optionally filtered to one project.

    Raises:
        ValueError: If metric is not in VALID_METRICS or no Parquet file is found.
    """
    _validate_metric(metric)

    pattern = f"{metric}_features_*.parquet"
    candidates = sorted(base_dir.glob(pattern))

    if not candidates:
        raise ValueError(
            f"No feature Parquet found for metric '{metric}' in '{base_dir}'. "
            "Run feature_engineering.__main__ to build features first."
        )

    latest = candidates[-1]  # Lexicographic sort → latest date wins
    df = pd.read_parquet(latest)

    if project is not None:
        if "project" in df.columns:
            df = df[df["project"] == project].reset_index(drop=True)
        else:
            logger.warning(
                "Project filter requested but 'project' column not present",
                extra={"metric": metric, "project": project},
            )

    logger.info(
        "Features loaded",
        extra={
            "metric": metric,
            "project": project or "all",
            "source": str(latest),
            "rows": len(df),
        },
    )
    return df


# ---------------------------------------------------------------------------
# __main__ entry point — build all features
# ---------------------------------------------------------------------------


def _build_all_features(
    history_dir: Path = _HISTORY_DIR,
    output_dir: Path = Path("data/features"),
) -> None:
    """Build and save feature Parquet files for all supported metrics."""
    logger.info("Starting full feature build", extra={"history_dir": str(history_dir)})

    for metric, filename in _HISTORY_FILES.items():
        history_path = history_dir / filename
        if not history_path.exists():
            logger.warning(
                "History file missing — skipping metric",
                extra={"metric": metric, "path": str(history_path)},
            )
            continue

        try:
            df = extract_features(metric, history_path)
            output_path = save_features(df, metric, base_dir=output_dir)
            logger.info(
                "Feature file written",
                extra={"metric": metric, "rows": len(df), "output": str(output_path)},
            )
        except (ValueError, ValidationError, FileNotFoundError) as e:
            logger.error(
                "Failed to build features for metric",
                extra={"metric": metric, "error": str(e)},
            )

    logger.info("Feature build complete")


if __name__ == "__main__":
    _build_all_features()
