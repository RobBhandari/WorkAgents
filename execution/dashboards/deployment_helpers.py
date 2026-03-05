"""
Deployment Dashboard Helper Functions

Extracted helper functions to keep deployment.py under 500 lines.
Contains trend chart loading logic for historical deployment metrics.
"""

import json
from pathlib import Path

from execution.core import get_logger
from execution.dashboards.components.forecast_chart import build_trend_chart

logger = get_logger(__name__)


def _deduplicate_weeks_by_date(weeks: list[dict]) -> list[dict]:
    """Deduplicate week entries by week_date, keeping last occurrence. Returns last 12."""
    seen: dict[str, dict] = {}
    for entry in weeks:
        date = entry.get("week_date", "")
        if date:
            seen[date] = entry
    return list(seen.values())[-12:]


def _extract_avg_success_rates(entries: list[dict]) -> tuple[list[float], list[str]]:
    """Extract portfolio-average build success rates from unique week entries."""
    values: list[float] = []
    labels: list[str] = []
    for entry in entries:
        rates = [
            float(p["build_success_rate"]["success_rate_pct"])
            for p in entry.get("projects", [])
            if p.get("build_success_rate", {}).get("total_builds", 0) > 0
        ]
        if rates:
            values.append(sum(rates) / len(rates))
            labels.append(entry.get("week_date", ""))
    return values, labels


def load_deployment_trend_chart() -> str:
    """
    Load deployment history and build a portfolio avg build success rate trend chart.

    Reads the last 12 unique date entries from deployment_history.json,
    computes portfolio-average build success rate per snapshot, and renders
    a Plotly trend chart.

    Returns:
        HTML string for the trend chart, or empty string if history unavailable.
    """
    history_path = Path(".tmp/observatory/deployment_history.json")
    if not history_path.exists():
        return ""

    try:
        with open(history_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError) as e:
        logger.warning("Could not load deployment_history.json for trend chart: %s", e)
        return ""

    weeks = data.get("weeks", [])
    if not weeks:
        return ""

    unique_entries = _deduplicate_weeks_by_date(weeks)
    values, labels = _extract_avg_success_rates(unique_entries)

    if not values:
        return ""

    return build_trend_chart(
        values,
        labels,
        "Avg Build Success Rate (%)",
        color="#10b981",
        height=250,
    )
