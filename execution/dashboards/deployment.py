"""
Deployment Dashboard Generator - Refactored

Generates DORA metrics deployment dashboard using:
    - Domain models (DeploymentMetrics)
    - Reusable components (metric cards)
    - Jinja2 templates (XSS-safe)
    - Direct Azure DevOps API queries (no history file dependency)

This replaces the original 436-line generate_deployment_dashboard.py with a
clean, maintainable implementation that queries ADO directly.

Usage:
    import asyncio
    from execution.dashboards.deployment import generate_deployment_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/deployment_dashboard.html')
    asyncio.run(generate_deployment_dashboard(output_path))
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

# Import domain models and utilities
from execution.collectors.ado_deployment_metrics import (
    calculate_build_duration,
    calculate_build_success_rate,
    calculate_deployment_frequency,
    calculate_lead_time_for_changes,
    query_builds,
)
from execution.collectors.ado_rest_client import get_ado_rest_client
from execution.core import get_logger
from execution.dashboards.renderer import render_dashboard
from execution.domain.deployment import DeploymentMetrics, from_json
from execution.framework import get_dashboard_framework
from execution.utils.error_handling import log_and_raise

logger = get_logger(__name__)


async def generate_deployment_dashboard(output_path: Path | None = None) -> str:
    """
    Generate deployment DORA metrics dashboard HTML by querying Azure DevOps API directly.

    This is the main entry point for generating the deployment dashboard.
    It queries ADO for fresh deployment data, processes it, and renders the HTML template.

    Args:
        output_path: Optional path to write HTML file

    Returns:
        Generated HTML string

    Raises:
        FileNotFoundError: If discovery data (ado_structure.json) doesn't exist

    Example:
        import asyncio
        from pathlib import Path
        html = await generate_deployment_dashboard(
            Path('.tmp/observatory/dashboards/deployment_dashboard.html')
        )
        logger.info("Dashboard generated", extra={"html_size": len(html)})
    """
    logger.info("Generating deployment dashboard")

    # Step 1: Query fresh deployment data from ADO
    logger.info("Querying deployment data from Azure DevOps API")
    metrics_list, raw_projects, collection_date = await _query_deployment_data()
    logger.info("Deployment data loaded", extra={"project_count": len(metrics_list)})

    # Step 2: Calculate summary statistics
    logger.info("Calculating summary metrics")
    summary_stats = _calculate_summary(metrics_list)

    # Step 3: Prepare template context
    logger.info("Preparing dashboard components")
    context = _build_context(metrics_list, raw_projects, summary_stats, collection_date)

    # Step 4: Render template
    logger.info("Rendering HTML template")
    html = render_dashboard("dashboards/deployment_dashboard.html", context)

    # Write to file if specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info("Dashboard written to file", extra={"path": str(output_path)})

    logger.info("Deployment dashboard generated", extra={"html_size": len(html)})
    return html


async def _query_deployment_data() -> tuple[list[DeploymentMetrics], list[dict], str]:
    """
    Query fresh deployment metrics from Azure DevOps API.

    Returns:
        Tuple of (metrics_list, raw_project_data, collection_date)

    Raises:
        FileNotFoundError: If discovery data (ado_structure.json) doesn't exist
    """
    # Load discovery data to get project list
    discovery_file = Path(".tmp/observatory/ado_structure.json")

    if not discovery_file.exists():
        raise FileNotFoundError(
            f"Discovery data file not found: {discovery_file}\n" "Run: python execution/collectors/ado_discovery.py"
        )

    with open(discovery_file, encoding="utf-8") as f:
        discovery_data = json.load(f)

    projects = discovery_data.get("projects", [])

    if not projects:
        raise ValueError("No projects found in discovery data")

    # Get ADO REST client
    rest_client = get_ado_rest_client()

    # Query deployment metrics for all projects concurrently
    lookback_days = 90
    tasks = [_collect_project_metrics(rest_client, project, lookback_days) for project in projects]
    raw_projects = await asyncio.gather(*tasks)

    # Filter out any None results (failed collections)
    raw_projects_filtered: list[dict[Any, Any]] = [p for p in raw_projects if p is not None]

    # Convert to domain models
    metrics_list = [from_json(project) for project in raw_projects_filtered]

    # Collection date is today
    collection_date = datetime.now().strftime("%Y-%m-%d")

    return metrics_list, raw_projects_filtered, collection_date


async def _collect_project_metrics(rest_client, project: dict, lookback_days: int) -> dict | None:
    """
    Collect deployment metrics for a single project.

    Args:
        rest_client: Azure DevOps REST API client
        project: Project metadata from discovery
        lookback_days: Period to analyze (days)

    Returns:
        Project metrics dictionary or None if collection fails
    """
    project_name = project["project_name"]
    ado_project_name = project.get("ado_project_name", project_name)

    try:
        logger.info(f"Collecting metrics for {project_name}")

        # Query builds
        builds = await query_builds(rest_client, ado_project_name, days=lookback_days)

        if not builds:
            logger.warning(f"No builds found for {project_name}")
            # Return zero metrics instead of None
            return {
                "project_name": project_name,
                "deployment_frequency": {
                    "total_successful_builds": 0,
                    "deployments_per_week": 0.0,
                    "lookback_days": lookback_days,
                    "pipeline_count": 0,
                },
                "build_success_rate": {
                    "total_builds": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "canceled": 0,
                    "partially_succeeded": 0,
                    "success_rate_pct": 0.0,
                    "by_result": {},
                    "by_pipeline": {},
                },
                "build_duration": {
                    "sample_size": 0,
                    "median_minutes": 0.0,
                    "p85_minutes": 0.0,
                    "min_minutes": 0.0,
                    "max_minutes": 0.0,
                },
                "lead_time_for_changes": {
                    "sample_size": 0,
                    "median_hours": 0.0,
                    "p85_hours": 0.0,
                },
            }

        # Calculate metrics
        deployment_frequency = calculate_deployment_frequency(builds, lookback_days)
        build_success_rate = calculate_build_success_rate(builds)
        build_duration = calculate_build_duration(builds)
        lead_time = await calculate_lead_time_for_changes(rest_client, ado_project_name, builds)

        return {
            "project_name": project_name,
            "deployment_frequency": deployment_frequency,
            "build_success_rate": build_success_rate,
            "build_duration": build_duration,
            "lead_time_for_changes": lead_time,
        }

    except Exception as e:
        logger.error(f"Error collecting metrics for {project_name}: {e}")
        return None


def _calculate_summary(metrics_list: list[DeploymentMetrics]) -> dict:
    """
    Calculate summary statistics across all projects.

    Args:
        metrics_list: List of project deployment metrics

    Returns:
        Dictionary with summary stats
    """
    total_builds = sum(m.build_success_rate.total_builds for m in metrics_list)
    total_successful = sum(m.deployment_frequency.total_successful_builds for m in metrics_list)
    overall_success_rate = (total_successful / total_builds * 100) if total_builds > 0 else 0.0

    return {
        "total_builds": total_builds,
        "total_successful": total_successful,
        "overall_success_rate": overall_success_rate,
        "project_count": len(metrics_list),
    }


def _build_context(
    metrics_list: list[DeploymentMetrics], raw_projects: list[dict], summary_stats: dict, collection_date: str
) -> dict:
    """
    Build template context with all dashboard data.

    Args:
        metrics_list: List of project metrics
        raw_projects: Raw project data with pipeline details
        summary_stats: Calculated summary statistics
        collection_date: Data collection date

    Returns:
        Dictionary for template rendering
    """
    # Get dashboard framework (CSS/JS)
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#667eea",
        header_gradient_end="#764ba2",
        include_table_scroll=True,
        include_expandable_rows=True,
        include_glossary=True,
    )

    # Build summary cards
    summary_cards = _build_summary_cards(summary_stats)

    # Build project rows
    projects = _build_project_rows(metrics_list, raw_projects)

    # Build context
    context = {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "generation_date": f"{collection_date} • Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "summary_cards": summary_cards,
        "projects": projects,
        "show_glossary": True,
    }

    return context


def _build_summary_cards(summary_stats: dict) -> list[str]:
    """
    Build summary metric cards HTML.

    Args:
        summary_stats: Summary statistics dictionary

    Returns:
        List of HTML strings for metric cards
    """
    cards = []

    # Total builds
    cards.append(f"""
        <div class="metric-card">
            <div class="metric-label">Total Builds (90 days)</div>
            <div class="metric-value">{summary_stats['total_builds']:,}</div>
            <div class="metric-detail">{summary_stats['total_successful']:,} successful</div>
        </div>
    """)

    # Overall success rate
    cards.append(f"""
        <div class="metric-card">
            <div class="metric-label">Overall Success Rate</div>
            <div class="metric-value">{summary_stats['overall_success_rate']:.1f}%</div>
            <div class="metric-detail">Across all projects</div>
        </div>
    """)

    # Projects tracked
    cards.append(f"""
        <div class="metric-card">
            <div class="metric-label">Projects Tracked</div>
            <div class="metric-value">{summary_stats['project_count']}</div>
            <div class="metric-detail">With deployment data</div>
        </div>
    """)

    return cards


def _build_pipeline_children(raw_project: dict) -> list[dict]:
    """
    Build child rows showing per-pipeline build statistics.

    Args:
        raw_project: Raw project data with pipeline breakdowns

    Returns:
        List of pipeline detail dictionaries with build breakdown
    """
    children = []

    # Get pipeline build success data
    success_rate = raw_project.get("build_success_rate", {})
    success_by_pipeline = success_rate.get("by_pipeline", {})

    # Build child row for each pipeline
    for pipeline_name in sorted(success_by_pipeline.keys()):
        # Get build statistics
        pipeline_stats = success_by_pipeline[pipeline_name]
        succeeded = pipeline_stats.get("succeeded", 0)
        failed = pipeline_stats.get("failed", 0)
        canceled = pipeline_stats.get("canceled", 0)
        partially_succeeded = pipeline_stats.get("partiallySucceeded", 0)

        # Calculate total builds and success rate
        total_builds = succeeded + failed + canceled + partially_succeeded
        if total_builds > 0:
            success_rate_pct = (succeeded / total_builds) * 100
        else:
            success_rate_pct = 0.0

        child = {
            "pipeline_name": pipeline_name,
            "total_builds": total_builds,
            "succeeded": succeeded,
            "failed": failed,
            "canceled": canceled,
            "partially_succeeded": partially_succeeded,
            "success_rate_pct": success_rate_pct,
        }

        children.append(child)

    return children


def _build_project_rows(metrics_list: list[DeploymentMetrics], raw_projects: list[dict]) -> list[dict]:
    """
    Build project table rows with deployment metrics.

    Args:
        metrics_list: List of project metrics
        raw_projects: Raw project data with pipeline details

    Returns:
        List of project dictionaries for template
    """
    rows = []

    # Create a lookup map for raw project data by project name
    raw_project_map = {p["project_name"]: p for p in raw_projects}

    # Sort by deployment frequency (descending)
    sorted_metrics = sorted(metrics_list, key=lambda m: m.deployment_frequency.deployments_per_week, reverse=True)

    for metrics in sorted_metrics:
        # Format display values
        deploys_per_week = metrics.deployment_frequency.deployments_per_week
        success_pct = metrics.build_success_rate.success_rate_pct
        total_builds = metrics.build_success_rate.total_builds
        succeeded = metrics.build_success_rate.succeeded
        median_duration = metrics.build_duration.median_minutes
        p85_duration = metrics.build_duration.p85_minutes
        median_lead_time = metrics.lead_time_for_changes.median_hours
        p85_lead_time = metrics.lead_time_for_changes.p85_hours
        total_successful = metrics.deployment_frequency.total_successful_builds

        # Build display strings
        deploys_display = f"{deploys_per_week:.1f}/week"
        success_display = f"{success_pct:.1f}%"
        duration_display = f"{median_duration:.1f}m"
        lead_time_display = f"{median_lead_time:.1f}h"

        # Build tooltips
        deploys_tooltip = f"{total_successful} successful builds"
        success_tooltip = f"{succeeded}/{total_builds} builds"
        duration_tooltip = f"P85: {p85_duration:.1f}m"
        lead_time_tooltip = f"P85: {p85_lead_time:.1f}h"

        # Status display
        status = metrics.status
        if status == "Good":
            status_display = "✓ Good"
            status_tooltip = f"Good: {success_pct:.1f}% success rate, {deploys_per_week:.1f} deploys/week"
        elif status == "Caution":
            status_display = "⚠ Caution"
            status_tooltip = f"Caution: {success_pct:.1f}% success rate, {deploys_per_week:.1f} deploys/week"
        elif status == "Inactive":
            status_display = "○ Inactive"
            status_tooltip = "Inactive: No deployments in 90 days"
        else:  # Action Needed
            status_display = "● Action Needed"
            status_tooltip = f"Action Needed: {success_pct:.1f}% success rate, {deploys_per_week:.1f} deploys/week"

        # Get pipeline-level details for child rows
        raw_project = raw_project_map.get(metrics.project_name, {})
        children = _build_pipeline_children(raw_project)

        row = {
            "name": metrics.project_name,
            "deploys_display": deploys_display,
            "deploys_tooltip": deploys_tooltip,
            "success_display": success_display,
            "success_tooltip": success_tooltip,
            "duration_display": duration_display,
            "duration_tooltip": duration_tooltip,
            "lead_time_display": lead_time_display,
            "lead_time_tooltip": lead_time_tooltip,
            "status_display": status_display,
            "status_tooltip": status_tooltip,
            "status_class": metrics.status_class,
            "children": children,  # Add child records for expand
        }

        rows.append(row)

    return rows


# Main execution for testing
if __name__ == "__main__":
    logger.info("Deployment Dashboard Generator - Self Test")

    async def main():
        try:
            output_path = Path(".tmp/observatory/dashboards/deployment_dashboard.html")
            html = await generate_deployment_dashboard(output_path)

            logger.info(
                "Deployment dashboard generated successfully",
                extra={"output": str(output_path), "html_size": len(html)},
            )

            # Verify output
            if output_path.exists():
                file_size = output_path.stat().st_size
                logger.info("Output file verified", extra={"file_size": file_size})
            else:
                logger.warning("Output file not created")

        except FileNotFoundError as e:
            logger.error("Discovery data file not found", extra={"error": str(e)})
            logger.info("Run data discovery first: python execution/collectors/ado_discovery.py")

        except Exception as e:
            log_and_raise(
                logger,
                e,
                context={"output_path": str(output_path)},
                error_type="Dashboard generation",
            )

    asyncio.run(main())
