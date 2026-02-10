"""
Ownership Dashboard Generator - Refactored

Generates ownership metrics dashboard showing:
    - Work assignment and distribution
    - Unassigned work tracking
    - Team load balancing
    - Work type segmentation

This replaces the original 631-line generate_ownership_dashboard.py with a
clean, maintainable implementation of ~200 lines.

Usage:
    from execution.dashboards.ownership import generate_ownership_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/ownership_dashboard.html')
    generate_ownership_dashboard(output_path)
"""

import json
import os
from pathlib import Path
from typing import Any

from execution.core import get_logger
from execution.dashboards.renderer import render_dashboard

# Import dependencies
from execution.framework import get_dashboard_framework
from execution.template_engine import render_template

logger = get_logger(__name__)


def generate_ownership_dashboard(output_path: Path | None = None) -> str:
    """
    Generate ownership metrics dashboard HTML.

    This is the main entry point for generating the ownership dashboard.
    It loads data, processes it, and renders the HTML template.

    Args:
        output_path: Optional path to write HTML file

    Returns:
        Generated HTML string

    Raises:
        FileNotFoundError: If ownership_history.json doesn't exist

    Example:
        from pathlib import Path
        html = generate_ownership_dashboard(
            Path('.tmp/observatory/dashboards/ownership_dashboard.html')
        )
        print(f"Generated dashboard with {len(html)} characters")
    """
    logger.info("Generating ownership dashboard")

    # Step 1: Load data
    logger.info("Loading ownership metrics")
    ownership_data = _load_ownership_data()
    logger.info("Ownership data loaded", extra={"project_count": len(ownership_data["projects"])})

    # Step 2: Calculate summary statistics
    logger.info("Calculating summary metrics")
    summary_stats = _calculate_summary(ownership_data)

    # Step 3: Prepare template context
    logger.info("Preparing dashboard components")
    context = _build_context(ownership_data, summary_stats)

    # Step 4: Render template
    logger.info("Rendering HTML template")
    html = render_dashboard("dashboards/ownership_dashboard.html", context)

    # Write to file if specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info("Dashboard written to file", extra={"path": str(output_path)})

    logger.info("Ownership dashboard generated", extra={"html_size": len(html)})
    return html


def _load_ownership_data() -> dict[str, Any]:
    """
    Load ownership metrics from history file.

    Returns:
        Most recent week's ownership data

    Raises:
        FileNotFoundError: If history file doesn't exist
    """
    history_file = ".tmp/observatory/ownership_history.json"

    if not os.path.exists(history_file):
        raise FileNotFoundError(
            f"Ownership history file not found: {history_file}\nRun: python execution/ado_ownership_metrics.py"
        )

    with open(history_file, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    result: dict[str, Any] = data["weeks"][-1]  # Most recent week
    return result


def _calculate_summary(ownership_data: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate summary statistics across all projects.

    Args:
        ownership_data: Ownership data for a week

    Returns:
        Dictionary with summary statistics
    """
    projects = ownership_data["projects"]

    # Calculate portfolio-wide stats
    total_unassigned = sum(p["unassigned"]["unassigned_count"] for p in projects)
    total_all_items = sum(p["total_items_analyzed"] for p in projects)
    avg_unassigned_pct = (total_unassigned / total_all_items * 100) if total_all_items > 0 else 0

    # Determine status based on unassigned percentage
    if avg_unassigned_pct < 10:
        status_color = "#10b981"  # Green
        status_text = "HEALTHY"
    elif avg_unassigned_pct < 25:
        status_color = "#f59e0b"  # Amber
        status_text = "CAUTION"
    else:
        status_color = "#f87171"  # Red
        status_text = "ACTION NEEDED"

    return {
        "total_unassigned": total_unassigned,
        "total_all_items": total_all_items,
        "avg_unassigned_pct": avg_unassigned_pct,
        "status_color": status_color,
        "status_text": status_text,
        "project_count": len(projects),
    }


def _build_context(ownership_data: dict[str, Any], summary_stats: dict[str, Any]) -> dict[str, Any]:
    """
    Build template context with all dashboard data.

    Args:
        ownership_data: Ownership metrics data
        summary_stats: Calculated summary statistics

    Returns:
        Dictionary for template rendering
    """
    # Get dashboard framework (CSS/JS)
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#3b82f6",
        header_gradient_end="#2563eb",
        include_table_scroll=True,
        include_expandable_rows=True,
        include_glossary=True,
    )

    # Build project rows with drill-down details
    project_rows = _build_project_rows(ownership_data["projects"])

    # Build context
    context = {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "week_number": ownership_data["week_number"],
        "week_date": ownership_data["week_date"],
        "summary_stats": summary_stats,
        "project_rows": project_rows,
    }

    return context


def _build_project_rows(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Build project table rows with expandable drill-down details.

    Args:
        projects: List of project ownership data

    Returns:
        List of project row dictionaries for template
    """
    # Prepare projects with status for sorting
    projects_with_status = []

    for project in projects:
        unassigned_pct = project["unassigned"]["unassigned_pct"]
        unassigned_count = project["unassigned"]["unassigned_count"]
        total = project["total_items_analyzed"]
        assignee_count = project["assignment_distribution"]["assignee_count"]

        # Extract developer active days
        dev_active_days = project.get("developer_active_days", {})
        avg_active_days = dev_active_days.get("avg_active_days", None)
        sample_size = dev_active_days.get("sample_size", 0)

        # Determine status
        status_info = _calculate_ownership_status(unassigned_pct)

        # Generate drill-down content
        drilldown_html = _generate_ownership_drilldown_html(project)

        projects_with_status.append(
            {
                "project_name": project["project_name"],
                "total": total,
                "unassigned_count": unassigned_count,
                "unassigned_pct": unassigned_pct,
                "assignee_count": assignee_count,
                "avg_active_days": avg_active_days,
                "sample_size": sample_size,
                "status_html": status_info["status_html"],
                "status_tooltip": status_info["tooltip"],
                "status_priority": status_info["priority"],
                "drilldown_html": drilldown_html,
            }
        )

    # Sort by status priority (Red->Amber->Green), then by unassigned percentage descending
    projects_with_status.sort(key=lambda x: (x["status_priority"], -x["unassigned_pct"]))

    return projects_with_status


def _calculate_ownership_status(unassigned_pct: float) -> dict[str, str | int]:
    """
    Calculate ownership status based on unassigned percentage.

    Args:
        unassigned_pct: Percentage of unassigned work

    Returns:
        Dictionary with status_html, tooltip, and priority
    """
    tooltip = f"Unassigned: {unassigned_pct:.1f}%"

    if unassigned_pct > 50:
        status_html = '<span style="color: #ef4444;">● High Unassigned</span>'
        priority = 0
    elif unassigned_pct > 25:
        status_html = '<span style="color: #f59e0b;">⚠ Medium Unassigned</span>'
        priority = 1
    else:
        status_html = '<span style="color: #10b981;">✓ Low Unassigned</span>'
        priority = 2

    return {"status_html": status_html, "tooltip": tooltip, "priority": priority}


def _generate_ownership_drilldown_html(project: dict[str, Any]) -> str:
    """
    Generate drill-down detail content HTML for a project.

    Args:
        project: Project ownership data

    Returns:
        HTML string for expandable detail section
    """
    # Section 1: Assignment Distribution (Top Assignees)
    top_assignees = project["assignment_distribution"].get("top_assignees", [])
    load_imbalance = project["assignment_distribution"].get("load_imbalance_ratio")

    # Filter out "Unassigned" from the list
    assigned_only = [(name, count) for name, count in top_assignees if name != "Unassigned"] if top_assignees else []

    # Section 2: Work Type Breakdown
    work_type_seg = project.get("work_type_segmentation", {})
    work_type_metrics = []

    if work_type_seg:
        for wtype in ["Bug", "User Story", "Task"]:
            if wtype in work_type_seg:
                data = work_type_seg[wtype]
                total = data.get("total", 0)
                unassigned = data.get("unassigned", 0)
                unassigned_pct = data.get("unassigned_pct", 0)

                if total > 0:
                    rag_status = _get_work_type_rag_status(unassigned_pct)
                    assigned = total - unassigned

                    work_type_metrics.append(
                        {
                            "rag_class": rag_status["rag_class"],
                            "rag_color": rag_status["rag_color"],
                            "wtype": wtype,
                            "total": total,
                            "assigned": assigned,
                            "unassigned": unassigned,
                            "unassigned_pct": f"{unassigned_pct:.0f}",
                            "rag_status": rag_status["status_text"],
                        }
                    )

    # Section 3: Area Unassigned Statistics
    area_stats = project.get("area_unassigned_stats", {})
    raw_areas = area_stats.get("areas", [])

    areas = [
        {
            "area_path": area.get("area_path", "Unknown"),
            "unassigned_pct": f"{area.get('unassigned_pct', 0):.1f}",
            "total_items": area.get("total_items", 0),
            "unassigned_items": area.get("unassigned_items", 0),
        }
        for area in raw_areas
    ]

    # Render using template
    return render_template(
        "ownership/drilldown_detail.html",
        assigned_only=assigned_only,
        load_imbalance=f"{load_imbalance:.1f}" if load_imbalance else None,
        work_type_metrics=work_type_metrics,
        areas=areas,
    )


def _get_work_type_rag_status(unassigned_pct: float) -> dict[str, str]:
    """
    Determine RAG status for work type cards based on unassigned percentage.

    Args:
        unassigned_pct: Percentage of unassigned work

    Returns:
        Dictionary with rag_class, rag_color, and status_text
    """
    if unassigned_pct < 25:
        return {"rag_class": "rag-green", "rag_color": "#10b981", "status_text": "Good"}
    elif unassigned_pct < 50:
        return {"rag_class": "rag-amber", "rag_color": "#f59e0b", "status_text": "Caution"}
    else:
        return {"rag_class": "rag-red", "rag_color": "#ef4444", "status_text": "Action Needed"}


# Main execution for testing
if __name__ == "__main__":
    logger.info("Ownership Dashboard Generator - Self Test")

    try:
        output_path = Path(".tmp/observatory/dashboards/ownership_dashboard.html")
        html = generate_ownership_dashboard(output_path)

        logger.info(
            "Ownership dashboard generated successfully", extra={"output": str(output_path), "html_size": len(html)}
        )

        # Verify output
        if output_path.exists():
            file_size = output_path.stat().st_size
            logger.info("Output file verified", extra={"file_size": file_size})
        else:
            logger.warning("Output file not created")

    except FileNotFoundError as e:
        logger.error("Ownership data file not found", extra={"error": str(e)})
        logger.info("Run data collection first: python execution/ado_ownership_metrics.py")

    except Exception as e:
        logger.error("Dashboard generation failed", extra={"error": str(e)}, exc_info=True)
