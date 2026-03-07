"""Shared orchestration pipeline for the Executive Trends Dashboard.

build_trends_context() is the single entry point used by both the CLI
generator (generate_trends_dashboard.py) and the API endpoint.  It runs
the full pipeline (load → calculate → render context) and returns the
Jinja template context dict from TrendsRenderer.build_context().
"""

import logging
from pathlib import Path
from typing import Any

from execution.dashboards.trends.calculator import TrendsCalculator
from execution.dashboards.trends.data_loader import TrendsDataLoader
from execution.dashboards.trends.renderer import TrendsRenderer

logger = logging.getLogger(__name__)

# Descriptor table for simple (one-to-one) domain extractions.
# Each entry: (metrics_data key, trends key, calculator method name, log key)
_SIMPLE_DOMAIN_EXTRACTORS: list[tuple[str, str, str, str]] = [
    ("quality", "quality", "extract_quality_trends", "bugs"),
    ("flow", "flow", "extract_flow_trends", "lead_time"),
    ("deployment", "deployment", "extract_deployment_trends", "build_success"),
    ("collaboration", "collaboration", "extract_collaboration_trends", "pr_merge_time"),
    ("ownership", "ownership", "extract_ownership_trends", "work_unassigned"),
    ("risk", "risk", "extract_risk_trends", "total_commits"),
    ("exploitable", "exploitable", "extract_exploitable_trends", "exploitable"),
]


def _extract_security_trends(calculator: TrendsCalculator, weeks: list, trends: dict) -> None:
    """Extract all three security trend variants and add them to trends in place."""
    security_trends = calculator.extract_security_trends(weeks)
    if security_trends:
        trends["security"] = security_trends
        logger.info("Security metrics extracted: %d weeks", len(security_trends["vulnerabilities"]["trend_data"]))

    cc_trends = calculator.extract_security_code_cloud_trends(weeks)
    if cc_trends:
        trends["security_code_cloud"] = cc_trends
        logger.info("Security Code+Cloud metrics extracted: %d weeks", len(cc_trends["vulnerabilities"]["trend_data"]))

    infra_trends = calculator.extract_security_infra_trends(weeks)
    if infra_trends:
        trends["security_infra"] = infra_trends
        logger.info(
            "Security Infrastructure metrics extracted: %d weeks", len(infra_trends["vulnerabilities"]["trend_data"])
        )


def _extract_simple_domain(
    calculator: TrendsCalculator,
    weeks: list,
    trends: dict,
    trend_key: str,
    extractor_name: str,
    log_key: str,
) -> None:
    """Call a named extractor on calculator and store the result in trends if non-empty."""
    extractor = getattr(calculator, extractor_name)
    result = extractor(weeks)
    if result:
        trends[trend_key] = result
        logger.info("%s metrics extracted: %d weeks", trend_key.capitalize(), len(result[log_key]["trend_data"]))


def _extract_all_trends(calculator: TrendsCalculator, metrics_data: dict) -> dict:
    """Run all per-domain trend extractions and return the populated trends dict.

    Each domain is only processed when the corresponding key is present and
    non-empty in metrics_data.  Security is handled separately because it fans
    out into three sub-keys.
    """
    trends: dict = {}

    for data_key, trend_key, extractor_name, log_key in _SIMPLE_DOMAIN_EXTRACTORS:
        if metrics_data.get(data_key):
            _extract_simple_domain(
                calculator, metrics_data[data_key]["weeks"], trends, trend_key, extractor_name, log_key
            )

    if metrics_data.get("security"):
        _extract_security_trends(calculator, metrics_data["security"]["weeks"], trends)

    return trends


def build_trends_context(
    history_dir: Path = Path(".tmp/observatory"),
) -> dict[str, Any]:
    """Run the full Executive Trends pipeline and return the Jinja context dict.

    Stages:
        1. Load   — TrendsDataLoader.load_all_metrics()
        2. Calc   — TrendsCalculator + domain extractors + target progress
        3. Render — TrendsRenderer.build_context()

    Args:
        history_dir: Directory containing observatory history JSON files.

    Returns:
        Context dict from TrendsRenderer.build_context().  Keys include:
        "metrics", "metrics_json", "active_alerts", "timestamp",
        "framework_css", "framework_js", "generation_date".

    Raises:
        ValueError: If no historical data is found across all domains.
    """
    loader = TrendsDataLoader(history_dir=str(history_dir))
    metrics_data = loader.load_all_metrics()

    if not any(v for k, v in metrics_data.items() if k != "baselines" and v is not None):
        raise ValueError("No historical data found")

    calculator = TrendsCalculator(baselines=metrics_data.get("baselines", {}))

    target_progress = None
    if metrics_data.get("quality") and metrics_data.get("security"):
        target_progress = calculator.calculate_target_progress(
            quality_weeks=metrics_data["quality"]["weeks"],
            security_weeks=metrics_data["security"]["weeks"],
        )

    trends = _extract_all_trends(calculator, metrics_data)

    renderer = TrendsRenderer(trends_data=trends, target_progress=target_progress)
    return renderer.build_context()
