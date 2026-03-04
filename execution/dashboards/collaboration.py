"""
Collaboration Dashboard Generator - Refactored

Generates collaboration metrics dashboard showing PR review metrics:
    - PR merge time (median, P85)
    - Review iteration count
    - PR size (commits)
    - Composite status based on thresholds

Queries Azure DevOps API directly for fresh data (no history file dependency).

Usage:
    import asyncio
    from execution.dashboards.collaboration import generate_collaboration_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/collaboration.html')
    asyncio.run(generate_collaboration_dashboard(output_path))
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from execution.collectors.ado_collaboration_metrics import collect_collaboration_metrics_for_project
from execution.collectors.ado_rest_client import get_ado_rest_client
from execution.core import get_logger
from execution.dashboards.components.cards import metric_card
from execution.dashboards.renderer import render_dashboard

# Import framework components
from execution.framework import get_dashboard_framework
from execution.secure_config import get_config
from execution.utils.error_handling import log_and_raise

logger = get_logger(__name__)


async def generate_collaboration_dashboard(output_path: Path | None = None) -> str:
    """
    Generate collaboration dashboard HTML by querying Azure DevOps API directly.

    This is the main entry point for generating the collaboration dashboard.
    It queries ADO for fresh PR metrics data, processes it, and renders the HTML template.

    Args:
        output_path: Optional path to write HTML file

    Returns:
        Generated HTML string

    Raises:
        ValueError: If ADO REST client initialization fails
        SystemExit: If discovery file not found

    Example:
        import asyncio
        from pathlib import Path
        html = await generate_collaboration_dashboard(
            Path('.tmp/observatory/dashboards/collaboration.html')
        )
        logger.info("Dashboard generated", extra={"html_size": len(html)})
    """
    logger.info("Generating collaboration dashboard from ADO API")

    # Step 1: Load data from ADO API
    logger.info("Querying Azure DevOps API for collaboration metrics")
    data = await _load_collaboration_data()
    logger.info("Collaboration data loaded from ADO", extra={"project_count": len(data["projects"])})

    # Step 2: Calculate summary statistics
    logger.info("Calculating summary metrics")
    summary_stats = _calculate_summary(data["projects"])

    # Step 3: Prepare template context
    logger.info("Preparing dashboard components")
    context = _build_context(data, summary_stats)

    # Step 4: Render template
    logger.info("Rendering HTML template")
    html = render_dashboard("dashboards/collaboration_dashboard.html", context)

    # Write to file if specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info("Dashboard written to file", extra={"path": str(output_path)})

    logger.info("Collaboration dashboard generated", extra={"html_size": len(html)})
    return html


async def _load_collaboration_data() -> dict:
    """
    Load collaboration metrics by querying Azure DevOps API directly.

    Returns:
        Fresh collaboration data with projects

    Raises:
        SystemExit: If discovery file not found
        ValueError: If ADO REST client initialization fails
    """
    # Load discovery data to get project list
    discovery_file = Path(".tmp/observatory/ado_structure.json")

    if not discovery_file.exists():
        raise FileNotFoundError(
            f"Discovery file not found: {discovery_file}\n" "Run: python execution/collectors/discover_projects.py"
        )

    with open(discovery_file, encoding="utf-8") as f:
        discovery_data = json.load(f)

    projects = discovery_data.get("projects", [])

    if not projects:
        logger.warning("No projects found in discovery data")
        return {
            "week_date": datetime.now().strftime("%Y-%m-%d"),
            "projects": [],
        }

    # Get configuration
    config = get_config()
    lookback_days_str = config.get_optional_env("LOOKBACK_DAYS", "90")
    lookback_days = int(lookback_days_str) if lookback_days_str else 90

    # Initialize ADO REST client
    logger.info("Connecting to Azure DevOps REST API...")
    rest_client = get_ado_rest_client()
    logger.info("Connected to ADO REST API")

    # Collect metrics for all projects concurrently
    logger.info(f"Collecting collaboration metrics for {len(projects)} projects (concurrent execution)...")

    tasks = [
        collect_collaboration_metrics_for_project(rest_client, project, {"lookback_days": lookback_days})
        for project in projects
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter successful results
    project_metrics = []
    for project, result in zip(projects, results, strict=True):
        if isinstance(result, Exception):
            logger.error(f"Error collecting metrics for {project.get('project_name', 'Unknown')}: {result}")
        else:
            project_metrics.append(result)

    logger.info(f"Successfully collected metrics for {len(project_metrics)}/{len(projects)} projects")

    return {
        "week_date": datetime.now().strftime("%Y-%m-%d"),
        "projects": project_metrics,
    }


def _calculate_summary(projects: list[dict]) -> dict:
    """
    Calculate summary statistics across all projects.

    Args:
        projects: List of project dictionaries with PR metrics

    Returns:
        Dictionary with summary stats
    """
    total_prs = sum(p.get("total_prs_analyzed", 0) for p in projects)
    projects_with_prs = sum(1 for p in projects if p.get("total_prs_analyzed", 0) > 0)
    avg_prs = total_prs // projects_with_prs if projects_with_prs > 0 else 0

    return {
        "total_prs": total_prs,
        "projects_with_prs": projects_with_prs,
        "avg_prs_per_project": avg_prs,
    }


def _build_context(data: dict, summary_stats: dict) -> dict:
    """
    Build template context with all dashboard data.

    Args:
        data: Loaded collaboration data
        summary_stats: Calculated summary statistics

    Returns:
        Dictionary for template rendering
    """
    # Get dashboard framework (CSS/JS)
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#0f172a",
        header_gradient_end="#0f172a",
        include_table_scroll=True,
        include_expandable_rows=False,
        include_glossary=True,
    )

    # Build summary cards
    summary_cards = _build_summary_cards(summary_stats)

    # Build project rows
    projects = _build_project_rows(data["projects"])

    # Build context
    context = {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "collection_date": data["week_date"],
        "summary_cards": summary_cards,
        "projects": projects,
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

    # Total PRs
    cards.append(
        metric_card(
            title="Total PRs (90 days)",
            value=f"{summary_stats['total_prs']:,}",
            subtitle="Across all projects",
        )
    )

    # Projects with PRs
    cards.append(
        metric_card(
            title="Projects with PRs",
            value=str(summary_stats["projects_with_prs"]),
            subtitle="Active code review",
        )
    )

    # Average PRs per project
    cards.append(
        metric_card(
            title="Avg PRs per Project",
            value=str(summary_stats["avg_prs_per_project"]),
            subtitle="Review activity",
        )
    )

    return cards


def _extract_merge_time_fields(project: dict) -> tuple[float, float, int]:
    """Extract and normalise merge-time fields from a project dict."""
    merge_time = project.get("pr_merge_time", {})
    median_merge: float = merge_time.get("median_hours", 0) or 0
    p85_merge: float = merge_time.get("p85_hours", 0) or 0
    merge_sample: int = merge_time.get("sample_size", 0)
    return median_merge, p85_merge, merge_sample


def _extract_iteration_fields(project: dict) -> tuple[float, float]:
    """Extract and normalise iteration fields from a project dict."""
    iterations = project.get("review_iteration_count", {})
    median_iterations: float = iterations.get("median_iterations", 0) or 0
    max_iterations: float = iterations.get("max_iterations", 0) or 0
    return median_iterations, max_iterations


def _extract_pr_size_fields(project: dict) -> tuple[float, float]:
    """Extract and normalise PR-size fields from a project dict."""
    pr_size = project.get("pr_size", {})
    median_commits: float = pr_size.get("median_commits", 0) or 0
    p85_commits: float = pr_size.get("p85_commits", 0) or 0
    return median_commits, p85_commits


def _build_project_rows(projects: list[dict]) -> list[dict]:
    """
    Build project table rows with status.

    Args:
        projects: List of project dictionaries

    Returns:
        List of project dictionaries for template
    """
    projects_with_status = [_build_single_project_row(p) for p in projects]

    # Sort by status priority (Red->Amber->Green), then by total PRs
    projects_with_status.sort(key=lambda x: (x["status_priority"], -x["total_prs"]))

    return projects_with_status


def _format_project_display(
    median_merge: float,
    p85_merge: float,
    merge_sample: int,
    median_iterations: float,
    max_iterations: float,
    median_commits: float,
    p85_commits: float,
) -> tuple[str, str, str, str, str, str]:
    """Format raw metric values into display strings and detail strings."""
    merge_display = f"{median_merge:.1f}h" if median_merge else "N/A"
    merge_detail = f"P85: {p85_merge:.1f}h, {merge_sample} PRs" if merge_sample else "No data"
    iterations_display = f"{median_iterations:.1f}" if median_iterations else "N/A"
    iterations_detail = f"Max: {max_iterations}" if max_iterations else "No data"
    size_display = f"{median_commits:.1f}" if median_commits else "N/A"
    size_detail = f"P85: {p85_commits:.1f} commits" if p85_commits else "No data"
    return merge_display, merge_detail, iterations_display, iterations_detail, size_display, size_detail


def _build_single_project_row(project: dict) -> dict:
    """Build the template row dict for one project."""
    proj_name = project["project_name"]
    total_prs = project.get("total_prs_analyzed", 0)

    median_merge, p85_merge, merge_sample = _extract_merge_time_fields(project)
    median_iterations, max_iterations = _extract_iteration_fields(project)
    median_commits, p85_commits = _extract_pr_size_fields(project)

    merge_display, merge_detail, iterations_display, iterations_detail, size_display, size_detail = (
        _format_project_display(
            median_merge, p85_merge, merge_sample, median_iterations, max_iterations, median_commits, p85_commits
        )
    )

    status_text, status_class, status_tooltip, status_priority = _calculate_composite_status(
        merge_time=median_merge if median_merge else None,
        iterations=median_iterations if median_iterations else None,
        pr_size=median_commits if median_commits else None,
    )

    return {
        "name": proj_name,
        "total_prs": total_prs,
        "merge_display": merge_display,
        "merge_detail": merge_detail,
        "iterations_display": iterations_display,
        "iterations_detail": iterations_detail,
        "size_display": size_display,
        "size_detail": size_detail,
        "status_text": status_text,
        "status_class": status_class,
        "status_tooltip": status_tooltip,
        "status_priority": status_priority,
    }


def _evaluate_metric_level(value: float, poor_threshold: float, caution_threshold: float) -> str:
    """
    Return 'poor', 'caution', or 'good' for a metric value given thresholds.

    Args:
        value: The metric value (already confirmed > 0).
        poor_threshold: Value strictly above this is 'poor'.
        caution_threshold: Value strictly above this (but not poor) is 'caution'.

    Returns:
        One of 'poor', 'caution', 'good'.
    """
    if value > poor_threshold:
        return "poor"
    if value > caution_threshold:
        return "caution"
    return "good"


def _check_merge_time(merge_time: float | None, issues: list[str], metric_details: list[str]) -> None:
    """Evaluate merge_time and append to issues/metric_details in place."""
    if merge_time is None or merge_time <= 0:
        return
    level = _evaluate_metric_level(merge_time, poor_threshold=72, caution_threshold=24)
    if level == "poor":
        issues.append("poor")
        metric_details.append(f"Merge time {merge_time:.1f}h (poor - target <24h)")
    elif level == "caution":
        issues.append("caution")
        metric_details.append(f"Merge time {merge_time:.1f}h (caution - target <24h)")
    else:
        metric_details.append(f"Merge time {merge_time:.1f}h (good)")


def _check_iterations(iterations: float | None, issues: list[str], metric_details: list[str]) -> None:
    """Evaluate iterations and append to issues/metric_details in place."""
    if iterations is None or iterations <= 0:
        return
    level = _evaluate_metric_level(iterations, poor_threshold=5, caution_threshold=2)
    if level == "poor":
        issues.append("poor")
        metric_details.append(f"{iterations:.1f} iterations (poor - target ≤2)")
    elif level == "caution":
        issues.append("caution")
        metric_details.append(f"{iterations:.1f} iterations (caution - target ≤2)")
    else:
        metric_details.append(f"{iterations:.1f} iterations (good)")


def _check_pr_size(pr_size: float | None, issues: list[str], metric_details: list[str]) -> None:
    """Evaluate pr_size and append to issues/metric_details in place."""
    if pr_size is None or pr_size <= 0:
        return
    level = _evaluate_metric_level(pr_size, poor_threshold=10, caution_threshold=5)
    if level == "poor":
        issues.append("poor")
        metric_details.append(f"{pr_size:.1f} commits (poor - target ≤5)")
    elif level == "caution":
        issues.append("caution")
        metric_details.append(f"{pr_size:.1f} commits (caution - target ≤5)")
    else:
        metric_details.append(f"{pr_size:.1f} commits (good)")


def _resolve_status(issues: list[str], metric_details: list[str]) -> tuple[str, str, int]:
    """
    Determine the overall status label, CSS class, and sort priority from issues list.

    Returns:
        Tuple of (status_text, status_class, priority).
    """
    poor_count = issues.count("poor")
    if poor_count >= 2:
        return "● Action Needed", "action", 0
    if poor_count == 1 or "caution" in issues:
        return "⚠ Caution", "caution", 1
    if metric_details:
        return "✓ Good", "good", 2
    return "○ No Data", "no-data", 3


def _calculate_composite_status(
    merge_time: float | None, iterations: float | None, pr_size: float | None
) -> tuple[str, str, str, int]:
    """
    Calculate composite collaboration status based on metrics.

    Returns tuple: (status_text, status_class, tooltip_text, priority)

    Priority is used for sorting: 0 = Action Needed (Red), 1 = Caution (Amber), 2 = Good (Green), 3 = No Data

    Status determination:
    - Good: All metrics meet target thresholds
    - Caution: One or more metrics need attention but not critical
    - Action Needed: Multiple metrics miss targets or any critical threshold exceeded

    Thresholds:
    - Merge Time: Good < 24h, Caution 24-72h, Poor > 72h
    - Iterations: Good <= 2, Caution 3-5, Poor > 5
    - PR Size: Good <= 5 commits, Caution 6-10 commits, Poor > 10 commits

    Args:
        merge_time: Median merge time in hours
        iterations: Median iteration count
        pr_size: Median PR size in commits

    Returns:
        Tuple of (status_text, status_class, tooltip_text, priority)
    """
    issues: list[str] = []
    metric_details: list[str] = []

    _check_merge_time(merge_time, issues, metric_details)
    _check_iterations(iterations, issues, metric_details)
    _check_pr_size(pr_size, issues, metric_details)

    tooltip = "\n".join(metric_details) if metric_details else "No data available"
    status_text, status_class, priority = _resolve_status(issues, metric_details)

    return status_text, status_class, tooltip, priority


# Main execution for testing
if __name__ == "__main__":
    logger.info("Collaboration Dashboard Generator - Self Test")

    async def main():
        try:
            output_path = Path(".tmp/observatory/dashboards/collaboration_dashboard.html")
            html = await generate_collaboration_dashboard(output_path)

            logger.info(
                "Collaboration dashboard generated successfully",
                extra={"output": str(output_path), "html_size": len(html)},
            )

            # Verify output
            if output_path.exists():
                file_size = output_path.stat().st_size
                logger.info("Output file verified", extra={"file_size": file_size})
            else:
                logger.warning("Output file not created")

        except FileNotFoundError as e:
            logger.error("Discovery file not found", extra={"error": str(e)})
            logger.info("Run discovery first: python execution/collectors/discover_projects.py")

        except Exception as e:
            log_and_raise(
                logger,
                e,
                context={"output_path": str(output_path), "operation": "dashboard_generation"},
                error_type="Collaboration dashboard generation",
            )

    asyncio.run(main())
