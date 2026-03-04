"""
Flow Dashboard Helper Functions

Extracted helper functions to keep flow.py under 500 lines.
Contains calculation, formatting, and component building logic.
"""

from typing import Any

from execution.dashboards.components.cards import metric_card
from execution.template_engine import render_template


def calculate_portfolio_summary(week_data: dict[str, Any]) -> dict[str, Any]:
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
    projects: list[dict[str, Any]] = week_data.get("projects", [])

    totals_by_type: dict[str, dict[str, Any]] = {
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
    all_lead_times: list[float] = []
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


def calculate_status(p85: float, p50: float) -> tuple[str, str, int]:
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
        status_html = render_template(
            "components/flow_status_badge.html", color="#ef4444", icon="●", text="Action Needed"
        )
        priority = 0
    elif poor_count >= 1 or caution_count >= 2:
        status_html = render_template("components/flow_status_badge.html", color="#f59e0b", icon="⚠", text="Caution")
        priority = 1
    else:
        status_html = render_template("components/flow_status_badge.html", color="#10b981", icon="✓", text="Good")
        priority = 2

    return status_html, tooltip, priority


def build_summary_cards(summary_stats: dict[str, Any]) -> list[str]:
    """
    Build 4 executive summary cards.

    Args:
        summary_stats: Portfolio summary from calculate_portfolio_summary()

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
        metric_card(
            title="Total WIP (Open)", value=f"{summary_stats['total_wip']:,}", subtitle="items - All work types"
        )
    )

    # Card 3: Closed (90d)
    cards.append(
        metric_card(title="Closed (90 days)", value=f"{summary_stats['total_closed']:,}", subtitle="All work types")
    )

    # Card 4: Projects Tracked
    cards.append(
        metric_card(title="Projects Tracked", value=str(summary_stats["project_count"]), subtitle="Portfolio coverage")
    )

    return cards


def build_work_type_cards(summary_stats: dict[str, Any]) -> list[str]:
    """
    Build 3 work type breakdown cards (Bug/Story/Task).

    Args:
        summary_stats: Portfolio summary from calculate_portfolio_summary()

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


def _as_num(value: Any) -> float:
    """Return the value as a float, converting None/falsy to 0.0."""
    return float(value) if value else 0.0


def _extract_project_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Extract and flatten all nested metric values from a work-type metrics dict."""
    lead_time = metrics.get("lead_time", {})
    throughput = metrics.get("throughput", {})
    cv_data = metrics.get("cycle_time_variance", {})
    dual_metrics = metrics.get("dual_metrics", {})
    indicators = dual_metrics.get("indicators", {})
    operational = dual_metrics.get("operational", {})
    cleanup_data = dual_metrics.get("cleanup", {})
    return {
        "p85": _as_num(lead_time.get("p85")),
        "p50": _as_num(lead_time.get("p50")),
        "per_week": _as_num(throughput.get("per_week")),
        "cv": _as_num(cv_data.get("coefficient_of_variation")),
        "std_dev": _as_num(cv_data.get("std_dev_days")),
        "has_cleanup": indicators.get("is_cleanup_effort", False),
        "cleanup_pct": indicators.get("cleanup_percentage", 0),
        "op_p85": _as_num(operational.get("p85")),
        "op_p50": _as_num(operational.get("p50")),
        "op_closed": _as_num(operational.get("closed_count")),
        "cleanup_closed": _as_num(cleanup_data.get("closed_count")),
    }


def _format_cleanup_fields(m: dict[str, Any]) -> dict[str, Any]:
    """Format cleanup-specific display values, returning None when cleanup not applicable."""
    if not m["has_cleanup"]:
        return {"op_p85": None, "op_p50": None, "op_closed": None, "cleanup_closed": None}
    return {
        "op_p85": f"{m['op_p85']:.1f}" if m["op_p85"] > 0 else None,
        "op_p50": f"{m['op_p50']:.1f}" if m["op_p50"] > 0 else None,
        "op_closed": f"{m['op_closed']:,.0f}" if m["op_closed"] > 0 else None,
        "cleanup_closed": f"{m['cleanup_closed']:,.0f}" if m["cleanup_closed"] > 0 else None,
    }


def format_project_row(project: dict[str, Any], work_type: str) -> dict[str, Any] | None:
    """
    Format a single project row for a work type table.

    Args:
        project: Project dict from week data
        work_type: "Bug", "User Story", or "Task"

    Returns:
        Dict ready for template, or None if no data for this work type
    """
    metrics = project.get("work_type_metrics", {}).get(work_type, {})

    open_count = metrics.get("open_count", 0)
    closed_count = metrics.get("closed_count_90d", 0)
    if open_count == 0 and closed_count == 0:
        return None

    m = _extract_project_metrics(metrics)
    status_html, tooltip, priority = calculate_status(m["p85"], m["p50"])

    cleanup = _format_cleanup_fields(m)
    return {
        "name": project.get("project_name", "Unknown"),
        "has_cleanup": m["has_cleanup"],
        "cleanup_pct": f"{m['cleanup_pct']:.1f}",
        "p85": f"{m['p85']:.1f}",
        "p50": f"{m['p50']:.1f}",
        "op_p85": cleanup["op_p85"],
        "op_p50": cleanup["op_p50"],
        "throughput": f"{m['per_week']:.1f}",
        "cv": f"{m['cv']:.0f}",
        "std_dev": f"{m['std_dev']:.1f}",
        "open": f"{open_count:,}",
        "closed": f"{closed_count:,}",
        "op_closed": cleanup["op_closed"],
        "cleanup_closed": cleanup["cleanup_closed"],
        "status_html": status_html,
        "status_tooltip": tooltip,
        "status_priority": priority,
    }


def build_project_tables(week_data: dict[str, Any], summary_stats: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Build project table data for 3 work types.

    Args:
        week_data: Week data from flow_history.json
        summary_stats: Portfolio summary from calculate_portfolio_summary()

    Returns:
        List of 3 dicts (one per work type) with table-ready data
    """
    work_types_data: list[dict[str, Any]] = []
    colors = {"Bug": "#ef4444", "User Story": "#3b82f6", "Task": "#10b981"}

    for work_type in ["Bug", "User Story", "Task"]:
        # Build project rows
        rows: list[dict[str, Any]] = []
        for project in week_data.get("projects", []):
            row = format_project_row(project, work_type)
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
