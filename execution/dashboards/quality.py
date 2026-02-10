"""
Quality Dashboard Generator - Refactored

Generates quality metrics dashboard using:
    - Data from ado_quality_loader
    - Reusable components (cards, metrics)
    - Jinja2 templates (XSS-safe)

This replaces the original 1113-line generate_quality_dashboard.py with a
clean, maintainable implementation split across quality.py and quality_legacy.py.

Note: Legacy HTML generation functions are in quality_legacy.py and should be
migrated to Jinja2 templates in the future.

Usage:
    from execution.dashboards.quality import generate_quality_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/quality_dashboard.html')
    generate_quality_dashboard(output_path)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from execution.core import get_logger
from execution.dashboards.quality_legacy import build_summary_cards, generate_distribution_section
from execution.dashboards.renderer import render_dashboard

# Import infrastructure
from execution.framework import get_dashboard_framework
from execution.template_engine import render_template
from execution.utils.error_handling import log_and_raise

logger = get_logger(__name__)


def generate_quality_dashboard(output_path: Path | None = None) -> str:
    """
    Generate quality dashboard HTML.

    This is the main entry point for generating the quality dashboard.
    It loads data, processes it, and renders the HTML template.

    Args:
        output_path: Optional path to write HTML file

    Returns:
        Generated HTML string

    Raises:
        FileNotFoundError: If quality_history.json doesn't exist

    Example:
        from pathlib import Path
        html = generate_quality_dashboard(
            Path('.tmp/observatory/dashboards/quality_dashboard.html')
        )
        print(f"Generated dashboard with {len(html)} characters")
    """
    logger.info("Generating quality dashboard")

    # Step 1: Load data
    logger.info("Loading quality data")
    quality_data = _load_quality_data()
    logger.info(
        "Quality data loaded",
        extra={"week_number": quality_data["week_number"], "week_date": quality_data["week_date"]},
    )

    # Step 2: Calculate summary statistics
    logger.info("Calculating summary metrics")
    summary_stats = _calculate_summary(quality_data["projects"])

    # Step 3: Prepare template context
    logger.info("Preparing dashboard components")
    context = _build_context(quality_data, summary_stats)

    # Step 4: Render template
    logger.info("Rendering HTML template")
    html = render_dashboard("dashboards/quality_dashboard.html", context)

    # Write to file if specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info("Dashboard written to file", extra={"path": str(output_path)})

    logger.info("Quality dashboard generated", extra={"html_size": len(html)})
    return html


def _load_quality_data() -> dict[str, Any]:
    """
    Load quality metrics from history file.

    Returns:
        Dictionary with week data and projects

    Raises:
        FileNotFoundError: If quality_history.json doesn't exist
    """
    history_file = Path(".tmp/observatory/quality_history.json")
    if not history_file.exists():
        raise FileNotFoundError(f"Quality history not found: {history_file}")

    with open(history_file, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    if not data.get("weeks"):
        raise ValueError("No weeks data in quality history")

    # Return most recent week
    result: dict[str, Any] = data["weeks"][-1]
    return result


def _calculate_summary(projects: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Calculate summary statistics across all projects.

    Args:
        projects: List of project metrics

    Returns:
        Dictionary with summary stats
    """
    # Aggregate totals
    total_bugs = sum(p["total_bugs_analyzed"] for p in projects)
    total_open = sum(p["open_bugs_count"] for p in projects)
    total_excluded = sum(p.get("excluded_security_bugs", {}).get("total", 0) for p in projects)

    # Calculate average MTTR
    mttr_values = [p.get("mttr", {}).get("mttr_days") for p in projects if p.get("mttr", {}).get("mttr_days")]
    avg_mttr = (sum(mttr_values) / len(mttr_values)) if mttr_values else 0

    # Determine status based on MTTR
    if avg_mttr < 7:
        status_color = "#10b981"  # Green
        status_text = "HEALTHY"
    elif avg_mttr < 14:
        status_color = "#f59e0b"  # Amber
        status_text = "CAUTION"
    else:
        status_color = "#f87171"  # Red
        status_text = "ACTION NEEDED"

    return {
        "total_bugs": total_bugs,
        "total_open": total_open,
        "total_excluded": total_excluded,
        "avg_mttr": avg_mttr,
        "status_color": status_color,
        "status_text": status_text,
        "project_count": len(projects),
    }


def _build_context(quality_data: dict[str, Any], summary_stats: dict[str, Any]) -> dict[str, Any]:
    """
    Build template context with all dashboard data.

    Args:
        quality_data: Week data with projects
        summary_stats: Calculated summary statistics

    Returns:
        Dictionary for template rendering
    """
    # Get dashboard framework (CSS/JS)
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#8b5cf6",
        header_gradient_end="#7c3aed",
        include_table_scroll=True,
        include_expandable_rows=True,
        include_glossary=True,
    )

    # Build summary cards
    summary_cards = build_summary_cards(summary_stats)

    # Build project rows with drill-down
    projects = _build_project_rows(quality_data["projects"])

    # Build context
    context = {
        "framework_css": framework_css,
        "framework_js": framework_js,
        "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "week_number": quality_data["week_number"],
        "week_date": quality_data["week_date"],
        "status_color": summary_stats["status_color"],
        "status_text": summary_stats["status_text"],
        "project_count": summary_stats["project_count"],
        "summary_cards": summary_cards,
        "projects": projects,
    }

    return context


def _build_project_rows(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Build project table rows with expandable drill-down details.

    Args:
        projects: List of project metrics

    Returns:
        List of project dictionaries for template
    """
    # Prepare projects with status for sorting
    projects_with_status = []

    for project in projects:
        median_age = project["bug_age_distribution"]["median_age_days"]
        open_bugs = project["open_bugs_count"]
        mttr = project.get("mttr", {}).get("mttr_days")

        # Determine composite status
        row_status, status_tooltip, status_priority = _calculate_composite_status(mttr=mttr, median_age=median_age)

        median_age_str = f"{median_age:.0f} days" if median_age else "N/A"
        mttr_str = f"{mttr:.1f} days" if mttr else "N/A"

        # Generate drill-down content
        details_html = _generate_drilldown_html(project)

        projects_with_status.append(
            {
                "name": project["project_name"],
                "mttr_str": mttr_str,
                "median_age_str": median_age_str,
                "open_bugs": open_bugs,
                "status": row_status,
                "status_tooltip": status_tooltip,
                "status_priority": status_priority,
                "details_html": details_html,
            }
        )

    # Sort by status priority (Red->Amber->Green), then by open bugs
    projects_with_status.sort(key=lambda x: (x["status_priority"], -x["open_bugs"]))

    return projects_with_status


def _calculate_composite_status(mttr: float | None, median_age: float | None) -> tuple[str, str, int]:
    """
    Calculate composite quality status based on metrics.

    Returns tuple: (status_html, tooltip_text, priority)

    Priority is used for sorting: 0 = Action Needed (Red), 1 = Caution (Amber), 2 = Good (Green)
    """
    issues = []
    metric_details = []

    # Check MTTR
    if mttr is not None:
        if mttr > 14:
            issues.append("poor")
            metric_details.append(f"MTTR {mttr:.1f} days (poor - target <7)")
        elif mttr > 7:
            issues.append("caution")
            metric_details.append(f"MTTR {mttr:.1f} days (caution - target <7)")
        else:
            metric_details.append(f"MTTR {mttr:.1f} days (good)")

    # Check Median Bug Age
    if median_age is not None:
        if median_age > 60:
            issues.append("poor")
            metric_details.append(f"Median bug age {median_age:.0f} days (poor - target <30)")
        elif median_age > 30:
            issues.append("caution")
            metric_details.append(f"Median bug age {median_age:.0f} days (caution - target <30)")
        else:
            metric_details.append(f"Median bug age {median_age:.0f} days (good)")

    # Build tooltip text
    tooltip = "\n".join(metric_details)

    # Determine overall status
    if "poor" in issues and len([i for i in issues if i == "poor"]) >= 2:
        # Both metrics poor = Action Needed
        status_html = '<span style="color: #ef4444;">● Action Needed</span>'
        priority = 0
    elif "poor" in issues:
        # One poor metric = Caution
        status_html = '<span style="color: #f59e0b;">⚠ Caution</span>'
        priority = 1
    elif "caution" in issues:
        # Some caution metrics = Caution
        status_html = '<span style="color: #f59e0b;">⚠ Caution</span>'
        priority = 1
    else:
        # All metrics meet targets = Good
        status_html = '<span style="color: #10b981;">✓ Good</span>'
        priority = 2

    return status_html, tooltip, priority


def _generate_drilldown_html(project: dict[str, Any]) -> str:
    """
    Generate drill-down detail content HTML for a project.

    Args:
        project: Project metrics dictionary

    Returns:
        HTML string for expandable detail section
    """
    html = '<div class="detail-content">'

    bug_age = project["bug_age_distribution"]
    mttr_data = project.get("mttr", {})

    # Section 1: Additional Metrics (P85, P95)
    if bug_age.get("p85_age_days") or bug_age.get("p95_age_days") or mttr_data.get("p85_mttr_days"):
        html += '<div class="detail-section">'
        html += "<h4>Detailed Metrics</h4>"
        html += '<div class="detail-grid">'

        if bug_age.get("p85_age_days"):
            rag_class, rag_color, rag_status = _get_metric_rag_status("Bug Age P85", bug_age["p85_age_days"])
            html += render_template(
                "dashboards/detail_metric.html",
                rag_class=rag_class,
                rag_color=rag_color,
                label="Bug Age P85",
                value=f"{bug_age['p85_age_days']:.1f} days",
                status=rag_status,
            )

        if bug_age.get("p95_age_days"):
            rag_class, rag_color, rag_status = _get_metric_rag_status("Bug Age P95", bug_age["p95_age_days"])
            html += render_template(
                "dashboards/detail_metric.html",
                rag_class=rag_class,
                rag_color=rag_color,
                label="Bug Age P95",
                value=f"{bug_age['p95_age_days']:.1f} days",
                status=rag_status,
            )

        if mttr_data.get("p85_mttr_days"):
            rag_class, rag_color, rag_status = _get_metric_rag_status("MTTR P85", mttr_data["p85_mttr_days"])
            html += render_template(
                "dashboards/detail_metric.html",
                rag_class=rag_class,
                rag_color=rag_color,
                label="MTTR P85",
                value=f"{mttr_data['p85_mttr_days']:.1f} days",
                status=rag_status,
            )

        if mttr_data.get("p95_mttr_days"):
            rag_class, rag_color, rag_status = _get_metric_rag_status("MTTR P95", mttr_data["p95_mttr_days"])
            html += render_template(
                "dashboards/detail_metric.html",
                rag_class=rag_class,
                rag_color=rag_color,
                label="MTTR P95",
                value=f"{mttr_data['p95_mttr_days']:.1f} days",
                status=rag_status,
            )

        html += "</div></div>"

    # Section 2: Bug Age Distribution
    if bug_age.get("ages_distribution"):
        html += generate_distribution_section("Bug Age Distribution", bug_age["ages_distribution"], "bug_age", "bugs")

    # Section 3: MTTR Distribution
    if mttr_data.get("mttr_distribution"):
        html += generate_distribution_section("MTTR Distribution", mttr_data["mttr_distribution"], "mttr", "bugs")

    # If no data at all
    if not (bug_age.get("ages_distribution") or mttr_data.get("mttr_distribution")):
        html += '<div class="no-data">No detailed metrics available for this project</div>'

    html += "</div>"
    return html


def _get_metric_rag_status(metric_name: str, value: float) -> tuple[str, str, str]:
    """
    Determine RAG status for a detailed metric.

    Returns: (color_class, color_hex, status_text)
    """
    if value is None:
        return "rag-unknown", "#6b7280", "No Data"

    thresholds = {
        "Bug Age P85": [
            (60, "rag-green", "Good"),
            (180, "rag-amber", "Caution"),
            (float("inf"), "rag-red", "Action Needed"),
        ],
        "Bug Age P95": [
            (90, "rag-green", "Good"),
            (365, "rag-amber", "Caution"),
            (float("inf"), "rag-red", "Action Needed"),
        ],
        "MTTR P85": [
            (14, "rag-green", "Good"),
            (30, "rag-amber", "Caution"),
            (float("inf"), "rag-red", "Action Needed"),
        ],
        "MTTR P95": [
            (21, "rag-green", "Good"),
            (45, "rag-amber", "Caution"),
            (float("inf"), "rag-red", "Action Needed"),
        ],
    }

    colors = {"rag-green": "#10b981", "rag-amber": "#f59e0b", "rag-red": "#ef4444"}

    for threshold, color_class, status in thresholds.get(metric_name, []):
        if value < threshold:
            return color_class, colors[color_class], status

    return "rag-unknown", "#6b7280", "Unknown"


# Main execution for testing
if __name__ == "__main__":
    logger.info("Quality Dashboard Generator - Self Test")

    try:
        output_path = Path(".tmp/observatory/dashboards/quality_dashboard.html")
        html = generate_quality_dashboard(output_path)

        logger.info(
            "Quality dashboard generated successfully", extra={"output": str(output_path), "html_size": len(html)}
        )

        # Verify output
        if output_path.exists():
            file_size = output_path.stat().st_size
            logger.info("Output file verified", extra={"file_size": file_size})
        else:
            logger.warning("Output file not created")

    except FileNotFoundError as e:
        logger.error("Quality data file not found", extra={"error": str(e)})
        logger.info("Run data collection first: python execution/collectors/ado_quality_metrics.py")
        raise

    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        log_and_raise(
            logger,
            e,
            context={"output_path": str(output_path) if output_path else None},
            error_type="Dashboard generation",
        )
