#!/usr/bin/env python3
"""
Generate Collaboration Dashboard from Azure DevOps API

Queries ADO directly for fresh collaboration metrics and generates dashboard.
Replaces the old history file approach with real-time API queries.

This is a standalone script wrapper for the async dashboard generator.
"""

import asyncio
import logging
import sys
from pathlib import Path

from execution.dashboards.collaboration import generate_collaboration_dashboard

logger = logging.getLogger(__name__)


def main():
    """Main entry point for collaboration dashboard generation"""
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
    logger.info("Collaboration Dashboard Generator")
    logger.info("=" * 70)

    # Generate dashboard
    output_path = Path(".tmp/observatory/dashboards/collaboration_dashboard.html")

    try:
        html = asyncio.run(generate_collaboration_dashboard(output_path))
        logger.info(f"Dashboard generated successfully: {output_path}")
        logger.info(f"HTML size: {len(html):,} bytes")
        return 0
    except FileNotFoundError as e:
        logger.error(f"Discovery file not found: {e}")
        logger.info("Run: python execution/collectors/discover_projects.py")
        return 1
    except Exception as e:
        logger.error(f"Dashboard generation failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
