"""
Risk Dashboard Generator - Refactored

Generates delivery risk dashboard using:
    - Code churn metrics (commits, files changed)
    - Knowledge distribution (bus factor)
    - Module coupling (co-changing files)
    - Jinja2 templates (XSS-safe)

Queries Azure DevOps API directly for fresh risk metrics data.

This replaces the original 574-line generate_risk_dashboard.py with a
clean, maintainable implementation of ~180 lines.

Usage:
    from execution.dashboards.risk import generate_risk_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/risk_dashboard.html')
    generate_risk_dashboard(output_path)
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from execution.collectors.ado_risk_metrics import collect_risk_metrics_for_project
from execution.core import get_logger
from execution.dashboards.components.cards import metric_card
from execution.dashboards.renderer import render_dashboard
from execution.framework import get_dashboard_framework
from execution.template_engine import render_template
from execution.utils.error_handling import log_and_raise

logger = get_logger(__name__)


def generate_risk_dashboard(output_path: Path | None = None) -> str:
    """
    Generate delivery risk dashboard HTML.

    This is the main entry point for generating the risk dashboard.
    It queries Azure DevOps API directly for fresh risk metrics data.

    Args:
        output_path: Optional path to write HTML file

    Returns:
        Generated HTML string

    Raises:
        FileNotFoundError: If project discovery file doesn't exist

    Example:
        from pathlib import Path
        html = generate_risk_dashboard(
            Path('.tmp/observatory/dashboards/risk_dashboard.html')
        )
        logger.info("Dashboard generated", extra={"html_size": len(html)})
    """
    logger.info("Generating risk dashboard")

    # Step 1: Query ADO API for fresh data
    logger.info("Querying Azure DevOps API for risk metrics")
    risk_data = asyncio.run(_query_risk_data())
    logger.info("Risk data loaded", extra={"project_count": len(risk_data["projects"])})

    # Step 2: Calculate summary statistics
    logger.info("Calculating summary metrics")
    summary_stats = _calculate_summary(risk_data["projects"])

    # Step 3: Prepare template context
    logger.info("Preparing dashboard components")
    context = _build_context(risk_data, summary_stats)

    # Step 4: Render template
    logger.info("Rendering HTML template")
    html = render_dashboard("dashboards/risk_dashboard.html", context)

    # Write to file if specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info("Dashboard written to file", extra={"path": str(output_path)})

    logger.info("Risk dashboard generated", extra={"html_size": len(html)})
    return html


async def _query_risk_data() -> dict:
    """
    Query Azure DevOps API for fresh risk metrics data.

    Returns:
        Dictionary with current week's risk data

    Raises:
        FileNotFoundError: If project discovery file doesn't exist
    """
    from execution.collectors.ado_rest_client import get_ado_rest_client
    from execution.domain.constants import flow_metrics

    # Load project discovery data
    discovery_path = Path(".tmp/observatory/ado_structure.json")

    if not discovery_path.exists():
        raise FileNotFoundError(
            f"Project discovery not found at {discovery_path}\n" "Run: python execution/discover_projects.py"
        )

    with open(discovery_path, encoding="utf-8") as f:
        discovery_data = json.load(f)

    projects = discovery_data.get("projects", [])
    if not projects:
        raise ValueError("No projects found in discovery data")

    logger.info(f"Querying risk metrics for {len(projects)} projects")

    # Get REST client
    rest_client = get_ado_rest_client()

    # Configuration for collector
    config = {
        "lookback_days": flow_metrics.LOOKBACK_DAYS,
    }

    # Query risk metrics for all projects concurrently
    tasks = [collect_risk_metrics_for_project(rest_client, project, config) for project in projects]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out exceptions and collect successful results
    project_metrics = []
    for project, result in zip(projects, results, strict=True):
        if isinstance(result, Exception):
            logger.error(
                "Error collecting metrics",
                extra={"project": project.get("project_name", "Unknown"), "error": str(result)},
            )
        else:
            project_metrics.append(result)

    # Build week data structure
    now = datetime.now()
    week_data = {
        "week_date": now.strftime("%Y-%m-%d"),
        "week_number": now.isocalendar()[1],
        "projects": project_metrics,
    }

    return week_data


def _calculate_summary(projects: list[dict]) -> dict:
    """
    Calculate summary statistics across all projects.

    Args:
        projects: List of project dictionaries

    Returns:
        Dictionary with summary stats
    """
    total_commits = sum(p.get("code_churn", {}).get("total_commits", 0) for p in projects)
    total_files = sum(p.get("code_churn", {}).get("unique_files_touched", 0) for p in projects)
    active_projects = sum(1 for p in projects if p.get("code_churn", {}).get("total_commits", 0) > 0)

    # Status determination based on code activity
    if total_commits > 1000:
        status_color = "#10b981"  # Green
        status_text = "HIGH ACTIVITY"
    elif total_commits > 300:
        status_color = "#f59e0b"  # Amber
        status_text = "MODERATE ACTIVITY"
    else:
        status_color = "#6b7280"  # Gray
        status_text = "LOW ACTIVITY"

    return {
        "total_commits": total_commits,
        "total_files": total_files,
        "active_projects": active_projects,
        "project_count": len(projects),
        "status_color": status_color,
        "status_text": status_text,
    }


def _build_context(risk_data: dict, summary_stats: dict) -> dict:
    """
    Build template context with all dashboard data.

    Args:
        risk_data: Week data with projects
        summary_stats: Calculated summary statistics

    Returns:
        Dictionary for template rendering
    """
    # Get dashboard framework (CSS/JS)
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#f59e0b",
        header_gradient_end="#d97706",
        include_table_scroll=True,
        include_expandable_rows=True,
        include_glossary=True,
    )

    # Build summary cards
    summary_cards = _build_summary_cards(summary_stats)

    # Build project rows
    projects = _build_project_rows(risk_data["projects"])

    # Build context
    context = {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "week_number": risk_data["week_number"],
        "week_date": risk_data["week_date"],
        "status_color": summary_stats["status_color"],
        "status_text": summary_stats["status_text"],
        "project_count": summary_stats["project_count"],
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

    # Total Commits
    cards.append(
        metric_card(
            title="Total Commits",
            value=f"{summary_stats['total_commits']:,}",
            subtitle="Commits in last 90 days",
        )
    )

    # Files Changed
    cards.append(
        metric_card(
            title="Files Changed",
            value=f"{summary_stats['total_files']:,}",
            subtitle="Unique files modified",
            css_class="info",
        )
    )

    # Active Projects
    cards.append(
        metric_card(
            title="Active Projects",
            value=str(summary_stats["active_projects"]),
            subtitle="Projects with commits (90d)",
            css_class="success",
        )
    )

    # Data Source
    cards.append(
        metric_card(
            title="Data Source",
            value="GIT",
            subtitle="Actual repository data",
            css_class="neutral",
        )
    )

    return cards


def _build_project_rows(projects: list[dict]) -> list[dict]:
    """
    Build project table rows with expandable drill-down details.

    Args:
        projects: List of project dictionaries

    Returns:
        List of project dictionaries for template
    """
    rows = []

    for project in projects:
        # Extract metrics
        code_churn = project.get("code_churn", {})
        commits = code_churn.get("total_commits", 0) or 0  # Handle None
        files = code_churn.get("unique_files_touched", 0) or 0  # Handle None

        # Extract knowledge distribution
        knowledge_dist = project.get("knowledge_distribution", {})
        single_owner_pct = knowledge_dist.get("single_owner_pct", 0) or 0
        total_files_analyzed = knowledge_dist.get("total_files_analyzed", 0)

        # Extract module coupling
        module_coupling = project.get("module_coupling", {})
        total_coupled_pairs = module_coupling.get("total_coupled_pairs", 0)

        # Determine activity level
        activity_level, activity_tooltip, activity_priority = _calculate_activity_level(commits)

        # Generate drill-down content
        drilldown_html = _generate_drilldown_html(project)

        # Format display values
        knowledge_display = f"{single_owner_pct:.1f}%" if single_owner_pct > 0 else "N/A"
        knowledge_title = f"{total_files_analyzed:,} files analyzed" if total_files_analyzed > 0 else "No file data"
        coupling_display = f"{total_coupled_pairs:,}" if total_coupled_pairs > 0 else "N/A"
        coupling_title = (
            "Files that change together frequently (3+ times)" if total_coupled_pairs > 0 else "No coupling data"
        )

        row = {
            "name": project.get("project_name", "Unknown"),
            "commits": commits,
            "files": files,
            "knowledge_display": knowledge_display,
            "knowledge_title": knowledge_title,
            "coupling_display": coupling_display,
            "coupling_title": coupling_title,
            "activity_level": activity_level,
            "activity_tooltip": activity_tooltip,
            "activity_priority": activity_priority,
            "drilldown_html": drilldown_html,
        }

        rows.append(row)

    # Sort by activity priority (High->Medium->Low), then by commits descending
    rows.sort(key=lambda x: (x["activity_priority"], -x["commits"]))

    return rows


def _calculate_activity_level(commit_count: int | None) -> tuple[str, str, int]:
    """
    Calculate activity level based on commit count.

    Args:
        commit_count: Number of commits (None treated as 0)

    Returns:
        Tuple of (activity_html, tooltip, priority)
        Priority: 0 = High (More active), 1 = Medium, 2 = Low
    """
    # Handle None values
    if commit_count is None:
        commit_count = 0

    if commit_count >= 100:
        activity_html = '<span style="color: #10b981;">● High Activity</span>'
        tooltip = f"{commit_count} commits (High activity)"
        priority = 0
    elif commit_count >= 20:
        activity_html = '<span style="color: #f59e0b;">● Medium Activity</span>'
        tooltip = f"{commit_count} commits (Medium activity)"
        priority = 1
    else:
        activity_html = '<span style="color: #6b7280;">● Low Activity</span>'
        tooltip = f"{commit_count} commits (Low activity)"
        priority = 2

    return activity_html, tooltip, priority


def _generate_drilldown_html(project: dict) -> str:
    """
    Generate drill-down detail content HTML for a project.

    Args:
        project: Project dictionary with metrics

    Returns:
        HTML string for expandable detail section
    """
    code_churn = project.get("code_churn", {})
    pr_dist = project.get("pr_size_distribution", {})
    repo_count = project.get("repository_count", 0)

    # Handle None values explicitly
    total_commits = code_churn.get("total_commits", 0)
    total_prs = pr_dist.get("total_prs", 0)
    has_commits = (total_commits or 0) > 0
    has_prs = (total_prs or 0) > 0
    has_activity = has_commits or has_prs

    # Generate commit metrics HTML
    commit_metric = ""
    file_changes_metric = ""
    avg_changes_metric = ""
    if has_commits:
        total_commits = code_churn.get("total_commits", 0) or 0
        total_file_changes = code_churn.get("total_file_changes", 0) or 0
        avg_changes = code_churn.get("avg_changes_per_commit", 0) or 0

        commit_metric = render_template(
            "dashboards/risk/metric_card.html",
            label="Total Commits",
            value=f"{total_commits:,}",
        )
        file_changes_metric = render_template(
            "dashboards/risk/metric_card.html",
            label="File Changes",
            value=f"{total_file_changes:,}",
        )
        avg_changes_metric = render_template(
            "dashboards/risk/metric_card.html",
            label="Avg Changes/Commit",
            value=f"{avg_changes:.1f}",
        )

    # Generate PR metrics HTML
    total_prs_metric = ""
    small_prs_metric = ""
    large_prs_metric = ""
    if has_prs:
        total_prs = pr_dist.get("total_prs", 0) or 0
        small_prs = pr_dist.get("small_prs", 0) or 0
        small_pct = pr_dist.get("small_pct", 0) or 0
        large_prs = pr_dist.get("large_prs", 0) or 0
        large_pct = pr_dist.get("large_pct", 0) or 0

        total_prs_metric = render_template(
            "dashboards/risk/metric_card.html",
            label="Total PRs",
            value=f"{total_prs:,}",
        )
        small_prs_metric = render_template(
            "dashboards/risk/metric_card.html",
            label=f"Small PRs ({small_pct:.0f}%)",
            value=f"{small_prs:,}",
        )
        large_prs_metric = render_template(
            "dashboards/risk/metric_card.html",
            label=f"Large PRs ({large_pct:.0f}%)",
            value=f"{large_prs:,}",
        )

    # Hot paths (high churn files)
    hot_paths = code_churn.get("hot_paths", [])

    # Render using template
    return render_template(
        "dashboards/risk/drilldown_detail.html",
        has_activity=has_activity,
        has_commits=has_commits,
        has_prs=has_prs,
        commit_metric=commit_metric,
        file_changes_metric=file_changes_metric,
        avg_changes_metric=avg_changes_metric,
        total_prs_metric=total_prs_metric,
        small_prs_metric=small_prs_metric,
        large_prs_metric=large_prs_metric,
        repo_count=repo_count,
        hot_paths=hot_paths,
    )


# Main execution for testing
if __name__ == "__main__":
    logger.info("Risk Dashboard Generator - Self Test")

    try:
        output_path = Path(".tmp/observatory/dashboards/risk_dashboard.html")
        html = generate_risk_dashboard(output_path)

        logger.info("Risk dashboard generated successfully", extra={"output": str(output_path), "html_size": len(html)})

        # Verify output
        if output_path.exists():
            file_size = output_path.stat().st_size
            logger.info("Output file verified", extra={"file_size": file_size})
        else:
            logger.warning("Output file not created")

    except FileNotFoundError as e:
        logger.error("Project discovery file not found", extra={"error": str(e)})
        logger.info("Run project discovery first: python execution/collectors/ado_project_discovery.py")

    except Exception as e:
        log_and_raise(
            logger,
            e,
            context={"output_path": str(output_path), "operation": "dashboard_generation"},
            error_type="Risk dashboard generation",
        )
