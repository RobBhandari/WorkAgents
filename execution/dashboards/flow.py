"""
Flow Dashboard Generator - Refactored

Generates engineering flow dashboard using:
    - Direct JSON loading (multi-project, multi-work-type)
    - Reusable components (cards, badges)
    - Jinja2 templates (XSS-safe)

This replaces the original 888-line generate_flow_dashboard.py with a
clean, maintainable implementation of ~280 lines.

Usage:
    from execution.dashboards.flow import generate_flow_dashboard
    from pathlib import Path

    output_path = Path('.tmp/observatory/dashboards/flow_dashboard.html')
    generate_flow_dashboard(output_path)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

# Import infrastructure
try:
    from ..dashboard_framework import get_dashboard_framework
    from ..dashboards.components.cards import metric_card
    from ..dashboards.renderer import render_dashboard
    from ..template_engine import render_template
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dashboard_framework import get_dashboard_framework  # type: ignore[no-redef]
    from dashboards.components.cards import metric_card  # type: ignore[no-redef]
    from dashboards.renderer import render_dashboard  # type: ignore[no-redef]
    from template_engine import render_template  # type: ignore[no-redef]


class FlowDataLoader:
    """Load flow metrics from history JSON file."""

    def __init__(self, history_file: Path | None = None):
        """
        Initialize loader.

        Args:
            history_file: Optional path to flow_history.json (defaults to .tmp/observatory/flow_history.json)
        """
        self.history_file = history_file or Path(".tmp/observatory/flow_history.json")

    def load_latest_week(self) -> dict:
        """
        Load latest week data with all projects and work types.

        Returns:
            Dictionary with structure: {week_date, week_number, projects[...]}

        Raises:
            FileNotFoundError: If history file doesn't exist
            json.JSONDecodeError: If file contains invalid JSON
        """
        with open(self.history_file, encoding="utf-8") as f:
            data = json.load(f)

        if "weeks" not in data or not data["weeks"]:
            raise ValueError("No weeks data found in flow_history.json")

        return data["weeks"][-1]  # Most recent week


def generate_flow_dashboard(output_path: Path | None = None) -> str:
    """
    Generate flow dashboard HTML.

    4-stage process:
    [1/4] Load data from flow_history.json
    [2/4] Calculate portfolio-wide summary statistics
    [3/4] Build template context (cards, tables, framework)
    [4/4] Render template

    Args:
        output_path: Optional path to write HTML file

    Returns:
        Generated HTML string

    Raises:
        FileNotFoundError: If flow_history.json doesn't exist

    Example:
        from pathlib import Path
        html = generate_flow_dashboard(
            Path('.tmp/observatory/dashboards/flow_dashboard.html')
        )
        print(f"Generated dashboard with {len(html)} characters")
    """
    print("[INFO] Generating Flow Dashboard...")

    # [1/4] Load data
    print("[1/4] Loading flow data...")
    loader = FlowDataLoader()
    week_data = loader.load_latest_week()
    print(f"      Loaded {len(week_data.get('projects', []))} projects")

    # [2/4] Calculate summaries
    print("[2/4] Calculating portfolio metrics...")
    summary_stats = _calculate_portfolio_summary(week_data)

    # [3/4] Build context
    print("[3/4] Preparing dashboard components...")
    context = _build_context(week_data, summary_stats)

    # [4/4] Render
    print("[4/4] Rendering HTML template...")
    html = render_dashboard("dashboards/flow_dashboard.html", context)

    # Write if path specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        print(f"[SUCCESS] Dashboard written to: {output_path}")

    print(f"[SUCCESS] Generated {len(html):,} characters of HTML")
    return html


def _calculate_portfolio_summary(week_data: dict) -> dict:
    """
    Calculate portfolio-wide summary statistics.

    Aggregates across all projects and work types.

    Args:
        week_data: Week data from flow_history.json

    Returns:
        {
            'avg_lead_time': float,
            'total_wip': int,
            'total_closed': int,
            'project_count': int,
            'by_type': {
                'Bug': {'open': int, 'closed': int, 'lead_times': [...]},
                'User Story': {...},
                'Task': {...}
            }
        }
    """
    projects = week_data.get("projects", [])

    totals_by_type = {
        "Bug": {"open": 0, "closed": 0, "lead_times": []},
        "User Story": {"open": 0, "closed": 0, "lead_times": []},
        "Task": {"open": 0, "closed": 0, "lead_times": []},
    }

    # Aggregate across all projects
    for project in projects:
        for work_type in ["Bug", "User Story", "Task"]:
            metrics = project.get("work_type_metrics", {}).get(work_type, {})
            totals_by_type[work_type]["open"] += metrics.get("open_count", 0)
            totals_by_type[work_type]["closed"] += metrics.get("closed_count_90d", 0)

            p85 = metrics.get("lead_time", {}).get("p85")
            if p85 and p85 > 0:
                totals_by_type[work_type]["lead_times"].append(p85)

    # Calculate averages
    all_lead_times = []
    for wt in ["Bug", "User Story", "Task"]:
        all_lead_times.extend(totals_by_type[wt]["lead_times"])

    avg_lead_time = sum(all_lead_times) / len(all_lead_times) if all_lead_times else 0
    total_wip = sum(totals_by_type[wt]["open"] for wt in ["Bug", "User Story", "Task"])
    total_closed = sum(totals_by_type[wt]["closed"] for wt in ["Bug", "User Story", "Task"])

    return {
        "avg_lead_time": avg_lead_time,
        "total_wip": total_wip,
        "total_closed": total_closed,
        "project_count": len(projects),
        "by_type": totals_by_type,
    }


def _calculate_status(p85: float, p50: float) -> tuple[str, str, int]:
    """
    Calculate flow status based on lead time metrics.

    Simplified from calculate_composite_flow_status() - same logic, cleaner code.

    Status determination:
    - Good: Both metrics meet target thresholds
    - Caution: One metric needs attention but not critical
    - Action Needed: Both metrics miss targets or any critical threshold exceeded

    Thresholds:
    - P85 Lead Time: Good < 60 days, Caution 60-150 days, Poor > 150 days
    - P50 Lead Time (Median): Good < 30 days, Caution 30-90 days, Poor > 90 days

    Args:
        p85: 85th percentile lead time in days
        p50: 50th percentile (median) lead time in days

    Returns:
        (status_html, tooltip_text, priority)
        Priority: 0=Action Needed, 1=Caution, 2=Good
    """
    issues = []
    details = []

    # Check P85
    if p85 > 0:
        if p85 > 150:
            issues.append("poor")
            details.append(f"P85 Lead Time {p85:.1f} days (poor - target <60)")
        elif p85 > 60:
            issues.append("caution")
            details.append(f"P85 Lead Time {p85:.1f} days (caution - target <60)")
        else:
            details.append(f"P85 Lead Time {p85:.1f} days (good)")
    else:
        details.append("P85 Lead Time: no data")

    # Check P50
    if p50 > 0:
        if p50 > 90:
            issues.append("poor")
            details.append(f"Median Lead Time {p50:.1f} days (poor - target <30)")
        elif p50 > 30:
            issues.append("caution")
            details.append(f"Median Lead Time {p50:.1f} days (caution - target <30)")
        else:
            details.append(f"Median Lead Time {p50:.1f} days (good)")
    else:
        details.append("Median Lead Time: no data")

    tooltip = "\n".join(details)

    # Determine status
    poor_count = issues.count("poor")
    caution_count = issues.count("caution")

    if poor_count >= 2:
        status_html = render_template("components/flow_status_badge.html", color="#ef4444", icon="●", text="Action Needed")
        priority = 0
    elif poor_count >= 1 or caution_count >= 2:
        status_html = render_template("components/flow_status_badge.html", color="#f59e0b", icon="⚠", text="Caution")
        priority = 1
    else:
        status_html = render_template("components/flow_status_badge.html", color="#10b981", icon="✓", text="Good")
        priority = 2

    return status_html, tooltip, priority


def _build_summary_cards(summary_stats: dict) -> list[str]:
    """
    Build 4 executive summary cards.

    Args:
        summary_stats: Portfolio summary from _calculate_portfolio_summary()

    Returns:
        List of pre-rendered HTML strings
    """
    cards = []

    # Card 1: Average Lead Time
    cards.append(
        metric_card(
            title="Average Lead Time", value=f"{summary_stats['avg_lead_time']:.0f}", subtitle="days - All work types"
        )
    )

    # Card 2: Total WIP
    cards.append(
        metric_card(title="Total WIP (Open)", value=f"{summary_stats['total_wip']:,}", subtitle="items - All work types")
    )

    # Card 3: Closed (90d)
    cards.append(metric_card(title="Closed (90 days)", value=f"{summary_stats['total_closed']:,}", subtitle="All work types"))

    # Card 4: Projects Tracked
    cards.append(metric_card(title="Projects Tracked", value=str(summary_stats["project_count"]), subtitle="Portfolio coverage"))

    return cards


def _build_work_type_cards(summary_stats: dict) -> list[str]:
    """
    Build 3 work type breakdown cards (Bug/Story/Task).

    Args:
        summary_stats: Portfolio summary from _calculate_portfolio_summary()

    Returns:
        List of pre-rendered HTML strings
    """
    cards = []
    colors = {"Bug": "#ef4444", "User Story": "#3b82f6", "Task": "#10b981"}
    labels = {"Bug": "Bugs", "User Story": "User Stories", "Task": "Tasks"}

    for work_type in ["Bug", "User Story", "Task"]:
        data = summary_stats["by_type"][work_type]
        cards.append(
            metric_card(
                title=labels[work_type],
                value=f"{data['open']:,}",
                subtitle=f"{data['closed']:,} closed (90d)",
                css_class=f"border-left: 4px solid {colors[work_type]};",
            )
        )

    return cards


def _format_project_row(project: dict, work_type: str) -> dict | None:
    """
    Format a single project row for a work type table.

    Args:
        project: Project dict from week data
        work_type: "Bug", "User Story", or "Task"

    Returns:
        Dict ready for template, or None if no data for this work type
    """
    metrics = project.get("work_type_metrics", {}).get(work_type, {})

    # Skip if no data
    open_count = metrics.get("open_count", 0)
    closed_count = metrics.get("closed_count_90d", 0)
    if open_count == 0 and closed_count == 0:
        return None

    # Extract metrics
    lead_time = metrics.get("lead_time", {})
    p85 = lead_time.get("p85", 0) or 0
    p50 = lead_time.get("p50", 0) or 0

    throughput = metrics.get("throughput", {})
    per_week = throughput.get("per_week", 0) or 0

    cv_data = metrics.get("cycle_time_variance", {})
    cv = cv_data.get("coefficient_of_variation", 0) or 0
    std_dev = cv_data.get("std_dev_days", 0) or 0

    # Check for cleanup work
    dual_metrics = metrics.get("dual_metrics", {})
    indicators = dual_metrics.get("indicators", {})
    has_cleanup = indicators.get("is_cleanup_effort", False)
    cleanup_pct = indicators.get("cleanup_percentage", 0)

    # Operational metrics (if cleanup detected)
    operational = dual_metrics.get("operational", {})
    op_p85 = operational.get("p85", 0) or 0
    op_p50 = operational.get("p50", 0) or 0
    op_closed = operational.get("closed_count", 0) or 0

    cleanup_data = dual_metrics.get("cleanup", {})
    cleanup_closed = cleanup_data.get("closed_count", 0) or 0

    # Calculate status
    status_html, tooltip, priority = _calculate_status(p85, p50)

    return {
        "name": project.get("project_name", "Unknown"),
        "has_cleanup": has_cleanup,
        "cleanup_pct": f"{cleanup_pct:.1f}",
        "p85": f"{p85:.1f}",
        "p50": f"{p50:.1f}",
        "op_p85": f"{op_p85:.1f}" if has_cleanup and op_p85 > 0 else None,
        "op_p50": f"{op_p50:.1f}" if has_cleanup and op_p50 > 0 else None,
        "throughput": f"{per_week:.1f}",
        "cv": f"{cv:.0f}",
        "std_dev": f"{std_dev:.1f}",
        "open": f"{open_count:,}",
        "closed": f"{closed_count:,}",
        "op_closed": f"{op_closed:,}" if has_cleanup and op_closed > 0 else None,
        "cleanup_closed": f"{cleanup_closed:,}" if has_cleanup and cleanup_closed > 0 else None,
        "status_html": status_html,
        "status_tooltip": tooltip,
        "status_priority": priority,
    }


def _build_project_tables(week_data: dict, summary_stats: dict) -> list[dict]:
    """
    Build project table data for 3 work types.

    Args:
        week_data: Week data from flow_history.json
        summary_stats: Portfolio summary from _calculate_portfolio_summary()

    Returns:
        List of 3 dicts (one per work type) with table-ready data
    """
    work_types_data = []
    colors = {"Bug": "#ef4444", "User Story": "#3b82f6", "Task": "#10b981"}

    for work_type in ["Bug", "User Story", "Task"]:
        # Build project rows
        rows = []
        for project in week_data.get("projects", []):
            row = _format_project_row(project, work_type)
            if row:
                rows.append(row)

        # Sort by status priority, then P85 descending
        rows.sort(key=lambda x: (x["status_priority"], -float(x["p85"])))

        # Calculate work type summary
        type_data = summary_stats["by_type"][work_type]
        avg_lead_time = sum(type_data["lead_times"]) / len(type_data["lead_times"]) if type_data["lead_times"] else 0

        work_types_data.append(
            {
                "name": work_type,
                "color": colors[work_type],
                "avg_lead_time": avg_lead_time,
                "total_open": type_data["open"],
                "total_closed": type_data["closed"],
                "projects": rows,
            }
        )

    return work_types_data


def _build_context(week_data: dict, summary_stats: dict) -> dict:
    """
    Build template context with all dashboard data.

    Args:
        week_data: Week data from flow_history.json
        summary_stats: Portfolio summary from _calculate_portfolio_summary()

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
    summary_cards = _build_summary_cards(summary_stats)
    work_type_cards = _build_work_type_cards(summary_stats)
    work_types = _build_project_tables(week_data, summary_stats)

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
    print("Flow Dashboard Generator - Self Test")
    print("=" * 60)

    try:
        output_path = Path(".tmp/observatory/dashboards/flow_dashboard.html")
        html = generate_flow_dashboard(output_path)

        print("\n" + "=" * 60)
        print("[SUCCESS] Flow dashboard generated!")
        print(f"[OUTPUT] {output_path}")
        print(f"[SIZE] {len(html):,} characters")

        if output_path.exists():
            file_size = output_path.stat().st_size
            print(f"[FILE] {file_size:,} bytes on disk")

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        print("\n[INFO] Run data collection first:")
        print("  python execution/collectors/ado_flow_metrics.py")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
