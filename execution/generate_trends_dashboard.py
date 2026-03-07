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

from execution.dashboards.renderer import render_dashboard
from execution.dashboards.trends.pipeline import build_trends_context

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


def _log_domain_extracted(domain: str, result: dict, log_key: str) -> None:
    """Emit a standard log line after a domain trend is extracted."""
    logger.info(f"{domain.capitalize()} metrics extracted: {len(result[log_key]['trend_data'])} weeks")


def main() -> None:
    """Main dashboard generation using 4-stage pipeline"""
    _setup_logging()

    logger.info("=" * 70)
    logger.info("Executive Trends Dashboard Generator")
    logger.info("=" * 70)

    # Stages 1–3: load, calculate, render context
    try:
        context = build_trends_context(history_dir=Path(".tmp/observatory"))
    except ValueError:
        logger.warning("No historical data found")
        sys.exit(1)

    # Stage 4: render HTML and save output
    logger.info("Generating dashboard...")
    output_path = Path(".tmp/observatory/dashboards/index.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html = render_dashboard("dashboards/trends_dashboard.html", context)
    output_path.write_text(html, encoding="utf-8")

    logger.info(f"Dashboard generated: {output_path}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
