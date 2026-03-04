#!/usr/bin/env python3
"""
Generate Executive Trends Dashboard from Observatory history files

Orchestrates the 4-stage pipeline for dashboard generation:
1. Load Data - TrendsDataLoader loads historical JSON files
2. Calculate Trends - TrendsCalculator extracts and processes metrics
3. Render Dashboard - TrendsRenderer generates HTML output
4. Save Output - Write dashboard to file

Refactored from 1,414 lines to ~100 lines using pipeline pattern.
"""

import logging
import sys
from pathlib import Path

from execution.dashboards.trends.calculator import TrendsCalculator
from execution.dashboards.trends.data_loader import TrendsDataLoader
from execution.dashboards.trends.renderer import TrendsRenderer

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    """Configure UTF-8 console output and standard logging format."""
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _extract_security_trends(calculator: TrendsCalculator, weeks: list, trends: dict) -> None:
    """Extract all three security trend variants and add them to trends in place."""
    security_trends = calculator.extract_security_trends(weeks)
    if security_trends:
        trends["security"] = security_trends
        logger.info(f"Security metrics extracted: {len(security_trends['vulnerabilities']['trend_data'])} weeks")

    cc_trends = calculator.extract_security_code_cloud_trends(weeks)
    if cc_trends:
        trends["security_code_cloud"] = cc_trends
        logger.info(f"Security Code+Cloud metrics extracted: {len(cc_trends['vulnerabilities']['trend_data'])} weeks")

    infra_trends = calculator.extract_security_infra_trends(weeks)
    if infra_trends:
        trends["security_infra"] = infra_trends
        logger.info(
            f"Security Infrastructure metrics extracted: {len(infra_trends['vulnerabilities']['trend_data'])} weeks"
        )


def _log_domain_extracted(domain: str, result: dict, log_key: str) -> None:
    """Emit a standard log line after a domain trend is extracted."""
    logger.info(f"{domain.capitalize()} metrics extracted: {len(result[log_key]['trend_data'])} weeks")


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
        _log_domain_extracted(trend_key, result, log_key)


# Descriptor table for simple (one-to-one) domain extractions.
# Each entry: (metrics_data key, trends key, calculator method name, log key within result)
_SIMPLE_DOMAIN_EXTRACTORS: list[tuple[str, str, str, str]] = [
    ("quality", "quality", "extract_quality_trends", "bugs"),
    ("flow", "flow", "extract_flow_trends", "lead_time"),
    ("deployment", "deployment", "extract_deployment_trends", "build_success"),
    ("collaboration", "collaboration", "extract_collaboration_trends", "pr_merge_time"),
    ("ownership", "ownership", "extract_ownership_trends", "work_unassigned"),
    ("risk", "risk", "extract_risk_trends", "total_commits"),
    ("exploitable", "exploitable", "extract_exploitable_trends", "exploitable"),
]


def _extract_all_trends(calculator: TrendsCalculator, metrics_data: dict) -> dict:
    """
    Run all per-domain trend extractions and return the populated trends dict.

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


def main() -> None:
    """Main dashboard generation using 4-stage pipeline"""
    _setup_logging()

    logger.info("=" * 70)
    logger.info("Executive Trends Dashboard Generator")
    logger.info("=" * 70)

    # Stage 1: Load Data
    loader = TrendsDataLoader(history_dir=".tmp/observatory")
    metrics_data = loader.load_all_metrics()

    # Validate we have data
    if not any(v for k, v in metrics_data.items() if k != "baselines" and v is not None):
        logger.warning("No historical data found")
        sys.exit(1)

    # Stage 2: Calculate Trends
    calculator = TrendsCalculator(baselines=metrics_data.get("baselines", {}))

    # Calculate target progress
    target_progress = None
    if metrics_data.get("quality") and metrics_data.get("security"):
        target_progress = calculator.calculate_target_progress(
            quality_weeks=metrics_data["quality"]["weeks"], security_weeks=metrics_data["security"]["weeks"]
        )

    trends = _extract_all_trends(calculator, metrics_data)

    # Stage 3: Render Dashboard
    logger.info("Generating dashboard...")
    renderer = TrendsRenderer(trends_data=trends, target_progress=target_progress)

    # Stage 4: Save Output
    output_path = Path(".tmp/observatory/dashboards/index.html")
    generated_file = renderer.generate_dashboard_file(output_path)

    logger.info(f"Dashboard generated: {generated_file}")
    logger.info(f"Total metrics: {len(trends) + (1 if target_progress else 0)}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
