"""
Flow Dashboard Generator - Refactored

Generates engineering flow dashboard using:
    - Direct ADO API queries (real-time data)
    - Reusable components (cards, badges)
    - Jinja2 templates (XSS-safe)

This replaces the original 888-line generate_flow_dashboard.py with a
clean, maintainable implementation split across flow.py and flow_helpers.py.

Usage:
    import asyncio
    from execution.dashboards.flow import generate_flow_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/flow_dashboard.html')
    html = asyncio.run(generate_flow_dashboard(output_path))
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from execution.collectors.ado_flow_metrics import collect_flow_metrics_for_project
from execution.collectors.ado_rest_client import get_ado_rest_client
from execution.core import get_logger
from execution.dashboards.flow_helpers import (
    build_project_tables,
    build_summary_cards,
    build_work_type_cards,
    calculate_portfolio_summary,
)
from execution.dashboards.renderer import render_dashboard
from execution.domain.constants import flow_metrics
from execution.framework import get_dashboard_framework
from execution.utils.error_handling import log_and_raise
from execution.utils_atomic_json import load_json_with_recovery

logger = get_logger(__name__)


async def _collect_flow_data() -> dict[str, Any]:
    """
    Collect flow metrics from Azure DevOps API.

    Queries ADO directly for all projects and work types.

    Returns:
        Dictionary with structure: {week_date, week_number, projects[...]}

    Raises:
        FileNotFoundError: If discovery data (ado_structure.json) doesn't exist
        Exception: If ADO API calls fail
    """
    logger.info("Collecting flow data from Azure DevOps API")

    # Load discovery data to get project list
    discovery_path = Path(".tmp/observatory/ado_structure.json")
    if not discovery_path.exists():
        raise FileNotFoundError(
            f"Discovery data not found at {discovery_path}. " "Run: python execution/collectors/ado_discovery.py"
        )

    discovery_data = load_json_with_recovery(str(discovery_path))
    projects = discovery_data.get("projects", [])

    if not projects:
        raise ValueError("No projects found in discovery data")

    logger.info("Projects discovered", extra={"project_count": len(projects)})

    # Get ADO REST client
    rest_client = get_ado_rest_client()

    # Build config
    config = {
        "lookback_days": flow_metrics.LOOKBACK_DAYS,
        "aging_threshold_days": flow_metrics.AGING_THRESHOLD_DAYS,
    }

    # Collect metrics for all projects concurrently
    logger.info("Querying flow metrics (concurrent execution)")
    tasks = [collect_flow_metrics_for_project(rest_client, project, config) for project in projects]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out failures
    project_metrics: list[dict[str, Any]] = []
    for project, result in zip(projects, results, strict=True):
        if isinstance(result, Exception):
            logger.error(
                "Failed to collect metrics for project",
                extra={"project_name": project["project_name"], "error": str(result)},
            )
        elif isinstance(result, dict):
            project_metrics.append(result)

    logger.info("Flow data collected", extra={"successful_projects": len(project_metrics)})

    # Build week data structure
    now = datetime.now()
    week_data = {
        "week_date": now.strftime("%Y-%m-%d"),
        "week_number": now.isocalendar()[1],
        "projects": project_metrics,
    }

    return week_data


async def generate_flow_dashboard(output_path: Path | None = None) -> str:
    """
    Generate flow dashboard HTML.

    4-stage process:
    [1/4] Query data from Azure DevOps API
    [2/4] Calculate portfolio-wide summary statistics
    [3/4] Build template context (cards, tables, framework)
    [4/4] Render template

    Args:
        output_path: Optional path to write HTML file

    Returns:
        Generated HTML string

    Raises:
        FileNotFoundError: If discovery data doesn't exist
        Exception: If ADO API calls fail

    Example:
        import asyncio
        from pathlib import Path

        html = await generate_flow_dashboard(
            Path('.tmp/observatory/dashboards/flow_dashboard.html')
        )
        logger.info("Dashboard generated", extra={"html_size": len(html)})
    """
    logger.info("Generating flow dashboard")

    # [1/4] Query data from ADO API
    logger.info("Querying Azure DevOps API")
    week_data = await _collect_flow_data()
    logger.info("Flow data queried", extra={"project_count": len(week_data.get("projects", []))})

    # [2/4] Calculate summaries
    logger.info("Calculating portfolio metrics")
    summary_stats = calculate_portfolio_summary(week_data)

    # [3/4] Build context
    logger.info("Preparing dashboard components")
    context = _build_context(week_data, summary_stats)

    # [4/4] Render
    logger.info("Rendering HTML template")
    html = render_dashboard("dashboards/flow_dashboard.html", context)

    # Write if path specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info("Dashboard written to file", extra={"path": str(output_path)})

    logger.info("Flow dashboard generated", extra={"html_size": len(html)})
    return html


def _build_context(week_data: dict[str, Any], summary_stats: dict[str, Any]) -> dict[str, Any]:
    """
    Build template context with all dashboard data.

    Args:
        week_data: Week data from ADO API
        summary_stats: Portfolio summary from calculate_portfolio_summary()

    Returns:
        Context dict for template rendering
    """
    # Get framework
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#10b981",
        header_gradient_end="#059669",
        include_table_scroll=True,
        include_glossary=True,
    )

    # Build components
    summary_cards = build_summary_cards(summary_stats)
    work_type_cards = build_work_type_cards(summary_stats)
    work_types = build_project_tables(week_data, summary_stats)

    # Determine portfolio status
    avg_lead = summary_stats["avg_lead_time"]
    if avg_lead < 60:
        portfolio_status = "HEALTHY"
        portfolio_color = "#10b981"
    elif avg_lead < 150:
        portfolio_status = "CAUTION"
        portfolio_color = "#f59e0b"
    else:
        portfolio_status = "ACTION NEEDED"
        portfolio_color = "#f87171"

    return {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "week_number": week_data.get("week_number", "N/A"),
        "week_date": week_data.get("week_date", "N/A"),
        "portfolio_status": portfolio_status,
        "portfolio_status_color": portfolio_color,
        "summary_cards": summary_cards,
        "work_type_cards": work_type_cards,
        "work_types": work_types,
        "project_count": summary_stats["project_count"],
    }


# Main for testing
if __name__ == "__main__":
    logger.info("Flow Dashboard Generator - Self Test")

    async def main() -> None:
        try:
            output_path = Path(".tmp/observatory/dashboards/flow_dashboard.html")
            html = await generate_flow_dashboard(output_path)

            logger.info(
                "Flow dashboard generated successfully", extra={"output": str(output_path), "html_size": len(html)}
            )

            if output_path.exists():
                file_size = output_path.stat().st_size
                logger.info("Output file verified", extra={"file_size": file_size})

        except FileNotFoundError as e:
            logger.error("Discovery data not found", extra={"error": str(e)})
            logger.info("Run discovery first: python execution/collectors/ado_discovery.py")

        except Exception as e:
            log_and_raise(
                logger,
                e,
                context={"output_path": str(output_path)},
                error_type="Dashboard generation",
            )

    asyncio.run(main())
