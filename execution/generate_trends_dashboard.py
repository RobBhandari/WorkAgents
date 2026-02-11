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


def main():
    """Main dashboard generation using 4-stage pipeline"""
    # Set UTF-8 encoding for Windows console
    if sys.platform == "win32":
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

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

    # Extract all trends
    trends = {}

    if metrics_data.get("quality"):
        quality_trends = calculator.extract_quality_trends(metrics_data["quality"]["weeks"])
        if quality_trends:
            trends["quality"] = quality_trends
            logger.info(f"Quality metrics extracted: {len(quality_trends['bugs']['trend_data'])} weeks")

    if metrics_data.get("security"):
        security_trends = calculator.extract_security_trends(metrics_data["security"]["weeks"])
        if security_trends:
            trends["security"] = security_trends
            logger.info(f"Security metrics extracted: {len(security_trends['vulnerabilities']['trend_data'])} weeks")

    if metrics_data.get("flow"):
        flow_trends = calculator.extract_flow_trends(metrics_data["flow"]["weeks"])
        if flow_trends:
            trends["flow"] = flow_trends
            logger.info(f"Flow metrics extracted: {len(flow_trends['lead_time']['trend_data'])} weeks")

    if metrics_data.get("deployment"):
        deployment_trends = calculator.extract_deployment_trends(metrics_data["deployment"]["weeks"])
        if deployment_trends:
            trends["deployment"] = deployment_trends
            logger.info(f"Deployment metrics extracted: {len(deployment_trends['build_success']['trend_data'])} weeks")

    if metrics_data.get("collaboration"):
        collaboration_trends = calculator.extract_collaboration_trends(metrics_data["collaboration"]["weeks"])
        if collaboration_trends:
            trends["collaboration"] = collaboration_trends
            logger.info(
                f"Collaboration metrics extracted: {len(collaboration_trends['pr_merge_time']['trend_data'])} weeks"
            )

    if metrics_data.get("ownership"):
        ownership_trends = calculator.extract_ownership_trends(metrics_data["ownership"]["weeks"])
        if ownership_trends:
            trends["ownership"] = ownership_trends
            logger.info(f"Ownership metrics extracted: {len(ownership_trends['work_unassigned']['trend_data'])} weeks")

    if metrics_data.get("risk"):
        risk_trends = calculator.extract_risk_trends(metrics_data["risk"]["weeks"])
        if risk_trends:
            trends["risk"] = risk_trends
            logger.info(f"Risk metrics extracted: {len(risk_trends['total_commits']['trend_data'])} weeks")

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
