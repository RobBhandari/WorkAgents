"""
Quality Dashboard Generator - Refactored

Generates quality metrics dashboard using:
    - Data from ado_quality_loader
    - Reusable components (cards, metrics)
    - Jinja2 templates (XSS-safe)

This replaces the original 1113-line generate_quality_dashboard.py with a
clean, maintainable implementation of ~280 lines.

Usage:
    from execution.dashboards.quality import generate_quality_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/quality_dashboard.html')
    generate_quality_dashboard(output_path)
"""

import json
from datetime import datetime
from pathlib import Path

# Import infrastructure
try:
    from ..dashboard_framework import get_dashboard_framework
    from ..dashboards.renderer import render_dashboard
    from ..template_engine import render_template
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dashboard_framework import get_dashboard_framework  # type: ignore[no-redef]
    from dashboards.renderer import render_dashboard  # type: ignore[no-redef]
    from template_engine import render_template  # type: ignore[no-redef]


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
    print("[INFO] Generating Quality Dashboard...")

    # Step 1: Load data
    print("[1/4] Loading quality data...")
    quality_data = _load_quality_data()
    print(f"      Loaded Week {quality_data['week_number']} ({quality_data['week_date']})")

    # Step 2: Calculate summary statistics
    print("[2/4] Calculating summary metrics...")
    summary_stats = _calculate_summary(quality_data["projects"])

    # Step 3: Prepare template context
    print("[3/4] Preparing dashboard components...")
    context = _build_context(quality_data, summary_stats)

    # Step 4: Render template
    print("[4/4] Rendering HTML template...")
    html = render_dashboard("dashboards/quality_dashboard.html", context)

    # Write to file if specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        print(f"[SUCCESS] Dashboard written to: {output_path}")

    print(f"[SUCCESS] Generated {len(html):,} characters of HTML")
    return html


def _load_quality_data() -> dict:
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
        data = json.load(f)

    if not data.get("weeks"):
        raise ValueError("No weeks data in quality history")

    # Return most recent week
    return data["weeks"][-1]


def _calculate_summary(projects: list[dict]) -> dict:
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


def _build_context(quality_data: dict, summary_stats: dict) -> dict:
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
    summary_cards = _build_summary_cards(summary_stats)

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


def _build_summary_cards(summary_stats: dict) -> list[str]:
    """
    Build summary metric cards HTML.

    Args:
        summary_stats: Summary statistics dictionary

    Returns:
        List of HTML strings for metric cards
    """
    cards = []

    # MTTR Card
    cards.append(
        f"""<div class="summary-card">
            <div class="label">MTTR (Mean Time To Repair)</div>
            <div class="value">{summary_stats['avg_mttr']:.1f}<span class="unit">days</span></div>
            <div class="explanation">Average time from bug creation to closure</div>
        </div>"""
    )

    # Total Bugs Card
    cards.append(
        f"""<div class="summary-card" style="border-left-color: #3b82f6;">
            <div class="label">Total Bugs Analyzed</div>
            <div class="value">{summary_stats['total_bugs']:,}</div>
            <div class="explanation">Bugs analyzed in last 90 days</div>
        </div>"""
    )

    # Open Bugs Card
    cards.append(
        f"""<div class="summary-card" style="border-left-color: #f59e0b;">
            <div class="label">Open Bugs</div>
            <div class="value">{summary_stats['total_open']:,}</div>
            <div class="explanation">Currently open bugs across all projects</div>
        </div>"""
    )

    # Security Bugs Excluded Card
    cards.append(
        f"""<div class="summary-card" style="border-left-color: #10b981;">
            <div class="label">Security Bugs Excluded</div>
            <div class="value">{summary_stats['total_excluded']:,}</div>
            <div class="explanation">ArmorCode bugs excluded to prevent double-counting</div>
        </div>"""
    )

    return cards


def _build_project_rows(projects: list[dict]) -> list[dict]:
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


def _generate_drilldown_html(project: dict) -> str:
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
        html += _generate_distribution_section(
            "Bug Age Distribution", bug_age["ages_distribution"], "bug_age", "bugs"
        )

    # Section 3: MTTR Distribution
    if mttr_data.get("mttr_distribution"):
        html += _generate_distribution_section("MTTR Distribution", mttr_data["mttr_distribution"], "mttr", "bugs")

    # If no data at all
    if not (bug_age.get("ages_distribution") or mttr_data.get("mttr_distribution")):
        html += '<div class="no-data">No detailed metrics available for this project</div>'

    html += "</div>"
    return html


def _generate_distribution_section(title: str, distribution: dict, bucket_type: str, unit: str) -> str:
    """Generate a distribution section with colored buckets."""
    html = '<div class="detail-section">'
    html += f"<h4>{title}</h4>"
    html += '<div class="detail-grid">'

    # Define bucket names based on type
    if bucket_type == "bug_age":
        buckets = [("0-7 Days", "0-7_days"), ("8-30 Days", "8-30_days"), ("31-90 Days", "31-90_days"), ("90+ Days", "90+_days")]
    else:  # mttr
        buckets = [("0-1 Days", "0-1_days"), ("1-7 Days", "1-7_days"), ("7-30 Days", "7-30_days"), ("30+ Days", "30+_days")]

    for label, key in buckets:
        count = distribution.get(key, 0)
        rag_class, rag_color = _get_distribution_bucket_rag_status(bucket_type, key)
        html += render_template(
            "dashboards/detail_metric.html",
            rag_class=rag_class,
            rag_color=rag_color,
            label=label,
            value=f"{count} {unit}",
        )

    html += "</div></div>"
    return html


def _get_metric_rag_status(metric_name: str, value: float) -> tuple[str, str, str]:
    """
    Determine RAG status for a detailed metric.

    Returns: (color_class, color_hex, status_text)
    """
    if value is None:
        return "rag-unknown", "#6b7280", "No Data"

    thresholds = {
        "Bug Age P85": [(60, "rag-green", "Good"), (180, "rag-amber", "Caution"), (float("inf"), "rag-red", "Action Needed")],
        "Bug Age P95": [(90, "rag-green", "Good"), (365, "rag-amber", "Caution"), (float("inf"), "rag-red", "Action Needed")],
        "MTTR P85": [(14, "rag-green", "Good"), (30, "rag-amber", "Caution"), (float("inf"), "rag-red", "Action Needed")],
        "MTTR P95": [(21, "rag-green", "Good"), (45, "rag-amber", "Caution"), (float("inf"), "rag-red", "Action Needed")],
    }

    colors = {"rag-green": "#10b981", "rag-amber": "#f59e0b", "rag-red": "#ef4444"}

    for threshold, color_class, status in thresholds.get(metric_name, []):
        if value < threshold:
            return color_class, colors[color_class], status

    return "rag-unknown", "#6b7280", "Unknown"


def _get_distribution_bucket_rag_status(bucket_type: str, bucket_name: str) -> tuple[str, str]:
    """
    Determine RAG status for distribution buckets.

    Returns: (color_class, color_hex)
    """
    if bucket_type == "bug_age":
        if bucket_name in ["0-7_days", "8-30_days"]:
            return "rag-green", "#10b981"
        elif bucket_name == "31-90_days":
            return "rag-amber", "#f59e0b"
        elif bucket_name == "90+_days":
            return "rag-red", "#ef4444"
    elif bucket_type == "mttr":
        if bucket_name in ["0-1_days", "1-7_days"]:
            return "rag-green", "#10b981"
        elif bucket_name == "7-30_days":
            return "rag-amber", "#f59e0b"
        elif bucket_name == "30+_days":
            return "rag-red", "#ef4444"

    # Default
    return "rag-unknown", "#6b7280"


# Main execution for testing
if __name__ == "__main__":
    print("Quality Dashboard Generator - Self Test")
    print("=" * 60)

    try:
        output_path = Path(".tmp/observatory/dashboards/quality_dashboard.html")
        html = generate_quality_dashboard(output_path)

        print("\n" + "=" * 60)
        print("[SUCCESS] Quality dashboard generated!")
        print(f"[OUTPUT] {output_path}")
        print(f"[SIZE] {len(html):,} characters")

        # Verify output
        if output_path.exists():
            file_size = output_path.stat().st_size
            print(f"[FILE] {file_size:,} bytes on disk")
        else:
            print("[WARNING] Output file not created")

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        print("\n[INFO] Run data collection first:")
        print("  python execution/collectors/ado_quality_metrics.py")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
