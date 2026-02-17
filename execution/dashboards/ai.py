"""
AI Contributions Dashboard Generator - Refactored

Generates AI vs Human contributions dashboard showing:
    - Devin AI vs Human PR contributions
    - Top contributors analysis
    - Project-level breakdown
    - Recent AI PR activity

Queries Azure DevOps API directly for fresh PR metrics data.

This replaces the original 708-line generate_ai_dashboard.py with a
clean, maintainable implementation of ~220 lines.

Usage:
    from execution.dashboards.ai import generate_ai_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/ai_contributions_latest.html')
    generate_ai_dashboard(output_path)
"""

import asyncio
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from execution.collectors.ado_collaboration_metrics import query_pull_requests
from execution.collectors.ado_rest_client import get_ado_rest_client
from execution.collectors.ado_rest_transformers import GitTransformer
from execution.core import get_logger
from execution.dashboards.renderer import render_dashboard
from execution.domain.constants import flow_metrics
from execution.framework import get_dashboard_framework
from execution.utils.error_handling import log_and_raise

logger = get_logger(__name__)


def generate_ai_dashboard(output_path: Path | None = None) -> str:
    """
    Generate AI contributions dashboard HTML.

    This is the main entry point for generating the AI dashboard.
    It queries Azure DevOps API directly for fresh PR metrics data.

    Args:
        output_path: Optional path to write HTML file

    Returns:
        Generated HTML string

    Raises:
        FileNotFoundError: If required data files don't exist

    Example:
        from pathlib import Path
        html = generate_ai_dashboard(
            Path('.tmp/observatory/dashboards/ai_contributions_latest.html')
        )
        logger.info("Dashboard generated", extra={"html_size": len(html)})
    """
    logger.info("Generating AI contributions dashboard")

    # Step 1: Query ADO API for fresh PR data
    logger.info("Querying Azure DevOps API for PR metrics")
    pr_data = asyncio.run(_query_pr_data())
    logger.info("PR data loaded", extra={"total_prs": len(pr_data)})

    # Step 1b: Load Devin analysis
    logger.info("Loading Devin analysis")
    analysis = _load_devin_analysis()

    # Extract author and project stats from fresh PR data
    author_stats = _get_author_stats_from_prs(pr_data)
    project_stats = _get_project_stats_from_prs(pr_data)
    logger.info(
        "AI contribution data loaded", extra={"author_count": len(author_stats), "project_count": len(project_stats)}
    )

    # Step 2: Calculate summary statistics
    logger.info("Calculating summary metrics")
    summary_stats = _calculate_summary(analysis, author_stats, project_stats)

    # Step 3: Prepare template context
    logger.info("Preparing dashboard components")
    context = _build_context(analysis, author_stats, project_stats, summary_stats)

    # Step 4: Render template
    logger.info("Rendering HTML template")
    html = render_dashboard("dashboards/ai_dashboard.html", context)

    # Write to file if specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info("Dashboard written to file", extra={"path": str(output_path)})

    logger.info("AI contributions dashboard generated", extra={"html_size": len(html)})
    return html


def _load_devin_analysis() -> dict[str, Any]:
    """
    Load Devin analysis from JSON file.

    Returns:
        Dictionary with Devin PR analysis

    Raises:
        FileNotFoundError: If analysis file doesn't exist
    """
    analysis_file = ".tmp/observatory/devin_analysis.json"

    if not os.path.exists(analysis_file):
        raise FileNotFoundError(
            f"Devin analysis file not found: {analysis_file}\nRun: py execution/analyze_devin_prs.py"
        )

    with open(analysis_file, encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
        return result


async def _query_pr_data() -> list[dict]:
    """
    Query Azure DevOps API for fresh PR metrics data.

    Returns:
        List of PR dictionaries with author and project information

    Raises:
        FileNotFoundError: If project discovery file doesn't exist
    """
    # Load project discovery data
    discovery_path = Path(".tmp/observatory/project_discovery.json")

    if not discovery_path.exists():
        raise FileNotFoundError(
            f"Project discovery not found at {discovery_path}\n"
            "Run: python execution/collectors/ado_project_discovery.py"
        )

    with open(discovery_path, encoding="utf-8") as f:
        discovery_data = json.load(f)

    projects = discovery_data.get("projects", [])
    if not projects:
        raise ValueError("No projects found in discovery data")

    logger.info(f"Querying PR metrics for {len(projects)} projects")

    # Get REST client
    rest_client = get_ado_rest_client()

    # Configuration for collector
    config = {
        "lookback_days": flow_metrics.LOOKBACK_DAYS,
    }

    # Query PRs for all projects concurrently
    all_prs = []

    for project in projects:
        project_name = project.get("project_name", "Unknown")
        ado_project_name = project.get("ado_project_name", project_name)

        # Get repositories via REST API
        try:
            repos_response = await rest_client.get_repositories(project=ado_project_name)
            repos = GitTransformer.transform_repositories_response(repos_response)
            logger.info(f"Found {len(repos)} repositories for {project_name}")
        except Exception as e:
            logger.warning("API error getting repositories", extra={"project": ado_project_name, "error": str(e)})
            continue

        # Query PRs for all repos in this project
        pr_tasks = [
            query_pull_requests(rest_client, ado_project_name, repo["id"], days=config["lookback_days"])
            for repo in repos
        ]

        pr_results = await asyncio.gather(*pr_tasks, return_exceptions=True)

        # Aggregate PRs from all repos
        for repo, result in zip(repos, pr_results, strict=True):
            if isinstance(result, Exception):
                logger.error(
                    "Error collecting PRs",
                    extra={"project": project_name, "repo": repo.get("name", "Unknown"), "error": str(result)},
                )
            else:
                # Add project name to each PR
                for pr in result:
                    pr["project_name"] = project_name
                all_prs.extend(result)

    logger.info(f"Collected {len(all_prs)} PRs across all projects")
    return all_prs


def _get_author_stats_from_prs(pr_data: list[dict]) -> dict[str, int]:
    """
    Calculate author contribution statistics from PR data.

    Args:
        pr_data: List of PR dictionaries from ADO API

    Returns:
        Dictionary mapping author name to PR count
    """
    author_stats: dict[str, int] = defaultdict(int)

    for pr in pr_data:
        author = pr.get("created_by", "Unknown")
        author_stats[author] += 1

    return dict(author_stats)


def _get_project_stats_from_prs(pr_data: list[dict]) -> dict[str, dict[str, int]]:
    """
    Calculate per-project Devin contribution stats from PR data.

    Args:
        pr_data: List of PR dictionaries from ADO API

    Returns:
        Dictionary mapping project name to stats (total, devin count)
    """
    project_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "devin": 0})

    for pr in pr_data:
        project_name = pr.get("project_name", "Unknown")
        project_stats[project_name]["total"] += 1

        author = pr.get("created_by", "").lower()
        if "devin" in author:
            project_stats[project_name]["devin"] += 1

    return dict(project_stats)


def _calculate_summary(
    analysis: dict[str, Any], author_stats: dict[str, int], project_stats: dict[str, dict[str, int]]
) -> dict[str, Any]:
    """
    Calculate summary statistics for the dashboard.

    Args:
        analysis: Devin PR analysis data
        author_stats: Author contribution statistics
        project_stats: Project contribution statistics

    Returns:
        Dictionary with summary statistics
    """
    summary = analysis["summary"]

    return {
        "total_prs": summary["total_prs"],
        "devin_prs": summary["devin_prs"],
        "human_prs": summary["human_prs"],
        "devin_percentage": summary["devin_percentage"],
        "author_count": len(author_stats),
        "project_count": len(project_stats),
    }


def _build_context(
    analysis: dict[str, Any],
    author_stats: dict[str, int],
    project_stats: dict[str, dict[str, int]],
    summary_stats: dict[str, Any],
) -> dict[str, Any]:
    """
    Build template context with all dashboard data.

    Args:
        analysis: Devin PR analysis
        author_stats: Author statistics
        project_stats: Project statistics
        summary_stats: Calculated summary statistics

    Returns:
        Dictionary for template rendering
    """
    # Get dashboard framework (CSS/JS)
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#8b5cf6",
        header_gradient_end="#7c3aed",
        include_table_scroll=True,
        include_glossary=False,  # AI dashboard has custom methodology section
    )

    # Build chart data
    top_authors = sorted(author_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    author_labels = [author for author, _ in top_authors]
    author_counts = [count for _, count in top_authors]

    # Build project breakdown data
    project_items = []
    for project, stats in sorted(project_stats.items(), key=lambda x: x[1]["total"], reverse=True):
        if stats["total"] > 0:
            project_items.append(
                {
                    "name": project,
                    "total": stats["total"],
                    "devin": stats["devin"],
                    "human": stats["total"] - stats["devin"],
                    "devin_pct": round(stats["devin"] / stats["total"] * 100, 1),
                }
            )

    # Build recent PRs table rows
    recent_prs = []
    for pr in analysis.get("devin_prs", [])[:15]:  # Show 15 most recent
        recent_prs.append(
            {
                "pr_id": pr["pr_id"],
                "project": pr["project"],
                "title": pr["title"],
                "created_by": pr["created_by"],
                "commit_count": pr["commit_count"],
                "created_date": pr["created_date"][:10] if pr.get("created_date") else "N/A",
            }
        )

    # Build context
    context = {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "summary_stats": summary_stats,
        "author_labels": author_labels,
        "author_counts": author_counts,
        "project_items": project_items,
        "recent_prs": recent_prs,
    }

    return context


# Main execution for testing
if __name__ == "__main__":
    logger.info("AI Contributions Dashboard Generator - Self Test")

    try:
        output_path = Path(".tmp/observatory/dashboards/ai_contributions_latest.html")
        html = generate_ai_dashboard(output_path)

        logger.info("AI dashboard generated successfully", extra={"output": str(output_path), "html_size": len(html)})

        # Verify output
        if output_path.exists():
            file_size = output_path.stat().st_size
            logger.info("Output file verified", extra={"file_size": file_size})
        else:
            logger.warning("Output file not created")

    except FileNotFoundError as e:
        logger.error("AI contribution data file not found", extra={"error": str(e)})
        logger.info("Run data collection first: python execution/analyze_devin_prs.py")

    except Exception as e:
        log_and_raise(logger, e, context={"operation": "generate_ai_dashboard"}, error_type="AI dashboard generation")
