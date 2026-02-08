#!/usr/bin/env python3
"""
Flow Dashboard Generator

Creates a beautiful, self-contained HTML dashboard for engineering flow metrics.
Uses modern "mint" design with Chart.js for visualizations.
"""

import json
import os
import sys
from datetime import datetime

# Import mobile-responsive framework
try:
    from execution.dashboard_framework import get_dashboard_framework
    from execution.template_engine import render_template
except ModuleNotFoundError:
    from dashboard_framework import get_dashboard_framework
    from template_engine import render_template

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


def calculate_composite_flow_status(p85_lead_time, p50_lead_time):
    """
    Calculate composite flow status based on lead time metrics.
    Returns tuple: (status_html, tooltip_text, priority)

    Priority is used for sorting: 0 = Action Needed (Red), 1 = Caution (Amber), 2 = Good (Green)

    Status determination:
    - Good: Both metrics meet target thresholds
    - Caution: One metric needs attention but not critical
    - Action Needed: Both metrics miss targets or any critical threshold exceeded

    Thresholds:
    - P85 Lead Time: Good < 60 days, Caution 60-150 days, Poor > 150 days
    - P50 Lead Time (Median): Good < 30 days, Caution 30-90 days, Poor > 90 days

    Note: Open bugs count is intentionally excluded from status calculation.
    It's a backlog/capacity metric, not a flow metric. If bugs sit open forever,
    that already shows up in poor lead time metrics.
    """
    issues = []
    metric_details = []

    # Check P85 Lead Time
    if p85_lead_time > 0:
        if p85_lead_time > 150:
            issues.append("poor")
            metric_details.append(f"P85 Lead Time {p85_lead_time:.1f} days (poor - target <60)")
        elif p85_lead_time > 60:
            issues.append("caution")
            metric_details.append(f"P85 Lead Time {p85_lead_time:.1f} days (caution - target <60)")
        else:
            metric_details.append(f"P85 Lead Time {p85_lead_time:.1f} days (good)")
    else:
        metric_details.append("P85 Lead Time: no data")

    # Check P50 Lead Time (Median)
    if p50_lead_time > 0:
        if p50_lead_time > 90:
            issues.append("poor")
            metric_details.append(f"Median Lead Time {p50_lead_time:.1f} days (poor - target <30)")
        elif p50_lead_time > 30:
            issues.append("caution")
            metric_details.append(f"Median Lead Time {p50_lead_time:.1f} days (caution - target <30)")
        else:
            metric_details.append(f"Median Lead Time {p50_lead_time:.1f} days (good)")
    else:
        metric_details.append("Median Lead Time: no data")

    # Build tooltip text with line breaks
    tooltip = "\n".join(metric_details)

    # Determine overall status and priority
    if "poor" in issues and len([i for i in issues if i == "poor"]) >= 2:
        # Both metrics poor = Action Needed
        status_html = render_template("components/flow_status_badge.html",
                                     color="#ef4444", icon="●", text="Action Needed")
        priority = 0
    elif "poor" in issues:
        # One poor metric = Caution
        status_html = render_template("components/flow_status_badge.html",
                                     color="#f59e0b", icon="⚠", text="Caution")
        priority = 1
    elif "caution" in issues and len([i for i in issues if i == "caution"]) >= 2:
        # Both metrics caution = Caution
        status_html = render_template("components/flow_status_badge.html",
                                     color="#f59e0b", icon="⚠", text="Caution")
        priority = 1
    elif "caution" in issues:
        # One caution metric = Caution
        status_html = render_template("components/flow_status_badge.html",
                                     color="#f59e0b", icon="⚠", text="Caution")
        priority = 1
    else:
        # All metrics meet targets = Good
        status_html = render_template("components/flow_status_badge.html",
                                     color="#10b981", icon="✓", text="Good")
        priority = 2

    return status_html, tooltip, priority


def load_flow_data():
    """Load flow metrics from history file"""
    with open(".tmp/observatory/flow_history.json", encoding="utf-8") as f:
        data = json.load(f)
    return data["weeks"][-1]  # Most recent week


def generate_html(flow_data):
    """Generate self-contained HTML dashboard with work type segmentation"""

    # Get mobile-responsive framework
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#10b981",
        header_gradient_end="#059669",
        include_table_scroll=True,
        include_expandable_rows=False,
        include_glossary=True,
    )

    # Extract data for charts
    projects = flow_data["projects"]

    # Calculate portfolio stats by work type
    totals_by_type = {
        "Bug": {"open": 0, "closed": 0, "lead_times": []},
        "User Story": {"open": 0, "closed": 0, "lead_times": []},
        "Task": {"open": 0, "closed": 0, "lead_times": []},
    }

    for p in projects:
        for work_type in ["Bug", "User Story", "Task"]:
            metrics = p.get("work_type_metrics", {}).get(work_type, {})
            totals_by_type[work_type]["open"] += metrics.get("open_count", 0)
            totals_by_type[work_type]["closed"] += metrics.get("closed_count_90d", 0)
            p85 = metrics.get("lead_time", {}).get("p85")
            if p85 and p85 > 0:
                totals_by_type[work_type]["lead_times"].append(p85)

    # Calculate average lead time across all work types for status determination
    all_lead_times = []
    for wtype in ["Bug", "User Story", "Task"]:
        all_lead_times.extend(totals_by_type[wtype]["lead_times"])

    avg_lead_time = sum(all_lead_times) / len(all_lead_times) if all_lead_times else 0
    total_wip = sum(totals_by_type[wt]["open"] for wt in ["Bug", "User Story", "Task"])
    total_closed = sum(totals_by_type[wt]["closed"] for wt in ["Bug", "User Story", "Task"])

    # Status determination
    if avg_lead_time < 60:
        status_color = "#10b981"  # Green
        status_text = "HEALTHY"
    elif avg_lead_time < 150:
        status_color = "#f59e0b"  # Amber
        status_text = "CAUTION"
    else:
        status_color = "#f87171"  # Red
        status_text = "ACTION NEEDED"

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Engineering Flow Dashboard - Week {flow_data['week_number']}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.3.0/dist/chart.umd.min.js"></script>
    {framework_css}
    <style>
        /* Dashboard-specific styles for Flow Dashboard */

        /* Work type color indicators */
        .work-type-bug {{
            color: #ef4444;
        }}

        .work-type-story {{
            color: #3b82f6;
        }}

        .work-type-task {{
            color: #10b981;
            font-weight: 600;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        .header {{
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px var(--shadow);
        }}

        .header h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 10px;
        }}

        .header .subtitle {{
            font-size: 1.1rem;
            opacity: 0.9;
        }}

        .header .timestamp {{
            font-size: 0.9rem;
            opacity: 0.8;
            margin-top: 10px;
        }}

        .executive-summary {{
            background: var(--bg-secondary);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.9rem;
            background: {status_color};
            color: white;
            margin-bottom: 20px;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-top: 16px;
            align-items: start;
        }}

        .summary-card {{
            background: var(--bg-tertiary);
            padding: 16px;
            border-radius: 8px;
            border-left: 4px solid #10b981;
        }}

        .summary-card .label {{
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }}

        .summary-card .value {{
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-primary);
            font-variant-numeric: tabular-nums;
            line-height: 1.1;
            margin-bottom: 4px;
        }}

        .summary-card .unit {{
            font-size: 0.85rem;
            font-weight: 400;
            color: var(--text-secondary);
            margin-left: 4px;
        }}

        .summary-card .explanation {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 4px;
            line-height: 1.25;
        }}

        .card {{
            background: var(--bg-secondary);
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .card h2 {{
            font-size: 1.3rem;
            margin-bottom: 16px;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
            line-height: 1.4;
        }}

        .card h2 .info-icon {{
            cursor: help;
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: bold;
        }}

        .chart-container {{
            position: relative;
            height: 350px;
            margin-bottom: 8px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}

        thead {{
            background: var(--bg-tertiary);
        }}

        th {{
            padding: 12px;
            text-align: left;
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            border-bottom: 2px solid var(--border-color);
        }}

        td {{
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
            font-variant-numeric: tabular-nums;
        }}

        tbody tr:hover {{
            background: var(--bg-tertiary);
        }}

        .trend-up {{
            color: #ef4444;
        }}

        .trend-down {{
            color: #10b981;
        }}

        .trend-neutral {{
            color: var(--text-secondary);
        }}

        .glossary {{
            background: var(--bg-tertiary);
            padding: 0;
            border-radius: 12px;
            margin-top: 30px;
            overflow: hidden;
        }}

        .glossary-header {{
            padding: 20px 30px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
            user-select: none;
            transition: background-color 0.2s ease;
        }}

        .glossary-header:hover {{
            background: rgba(255, 255, 255, 0.05);
        }}

        [data-theme="light"] .glossary-header:hover {{
            background: rgba(0, 0, 0, 0.03);
        }}

        .glossary-header h3 {{
            font-size: 1.2rem;
            margin: 0;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .glossary-toggle {{
            font-size: 1.5rem;
            color: var(--text-secondary);
            transition: transform 0.3s ease;
        }}

        .glossary-toggle.expanded {{
            transform: rotate(180deg);
        }}

        .glossary-content {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.4s ease;
            padding: 0 30px;
        }}

        .glossary-content.expanded {{
            max-height: 5000px;
            padding: 0 30px 30px 30px;
        }}

        .glossary h3 {{
            font-size: 1.2rem;
            margin-bottom: 15px;
            color: var(--text-primary);
        }}

        .glossary-item {{
            margin-bottom: 15px;
        }}

        .glossary-term {{
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 4px;
        }}

        .glossary-definition {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            line-height: 1.5;
        }}

        .footer {{
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}

        @media print {{
            body {{
                background: var(--bg-secondary);
            }}
            .card, .executive-summary {{
                box-shadow: none;
                border: 1px solid var(--border-color);
            }}
        }}
    </style>
</head>
<body>
    <div class="theme-toggle" onclick="toggleTheme()" title="Toggle dark/light mode">
        <span id="theme-icon">🌙</span>
        <span id="theme-label">Dark</span>
    </div>

    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>Engineering Flow Dashboard</h1>
            <div class="subtitle">Portfolio Health at a Glance</div>
            <div class="timestamp">Week {flow_data['week_number']} • {flow_data['week_date']} • Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>

        <!-- Executive Summary -->
        <div class="executive-summary">
            <div class="status-badge">{status_text}</div>
            <h2 style="margin-bottom: 10px;">Executive Summary</h2>
            <p style="color: var(--text-secondary); margin-bottom: 16px; font-size: 0.95rem;">
                Flow metrics across {len(projects)} projects — segmented by Bug, User Story, and Task.
            </p>

            <div class="summary-grid">
                <div class="summary-card">
                    <div class="label">Average Lead Time</div>
                    <div class="value">{avg_lead_time:.0f}<span class="unit">days</span></div>
                    <div class="explanation">All work types</div>
                </div>

                <div class="summary-card" style="border-left-color: #ef4444;">
                    <div class="label">Total WIP (Open)</div>
                    <div class="value">{total_wip:,}<span class="unit">items</span></div>
                    <div class="explanation">All work types</div>
                </div>

                <div class="summary-card" style="border-left-color: #3b82f6;">
                    <div class="label">Closed (90 days)</div>
                    <div class="value">{total_closed:,}</div>
                    <div class="explanation">All work types</div>
                </div>

                <div class="summary-card" style="border-left-color: #f59e0b;">
                    <div class="label">Projects Tracked</div>
                    <div class="value">{len(projects)}</div>
                    <div class="explanation">Portfolio coverage</div>
                </div>
            </div>

            <div style="margin-top: 20px; padding: 16px; background: var(--bg-tertiary); border-radius: 8px;">
                <h3 style="font-size: 1rem; margin-bottom: 12px; color: var(--text-primary);">Work Type Breakdown</h3>
                <div class="summary-grid" style="grid-template-columns: repeat(3, 1fr);">
                    <div class="summary-card" style="border-left-color: #ef4444;">
                        <div class="label">Bugs</div>
                        <div class="value">{totals_by_type['Bug']['open']:,}<span class="unit" style="font-size: 0.5em;">open</span></div>
                        <div class="explanation">{totals_by_type['Bug']['closed']:,} closed (90d)</div>
                    </div>
                    <div class="summary-card" style="border-left-color: #3b82f6;">
                        <div class="label">User Stories</div>
                        <div class="value">{totals_by_type['User Story']['open']:,}<span class="unit" style="font-size: 0.5em;">open</span></div>
                        <div class="explanation">{totals_by_type['User Story']['closed']:,} closed (90d)</div>
                    </div>
                    <div class="summary-card" style="border-left-color: #10b981;">
                        <div class="label">Tasks</div>
                        <div class="value">{totals_by_type['Task']['open']:,}<span class="unit" style="font-size: 0.5em;">open</span></div>
                        <div class="explanation">{totals_by_type['Task']['closed']:,} closed (90d)</div>
                    </div>
                </div>
            </div>
        </div>
"""

    # Generate tables for each work type
    for work_type, color in [("Bug", "#ef4444"), ("User Story", "#3b82f6"), ("Task", "#10b981")]:
        avg_wt_lead_time = (
            sum(totals_by_type[work_type]["lead_times"]) / len(totals_by_type[work_type]["lead_times"])
            if totals_by_type[work_type]["lead_times"]
            else 0
        )

        html += f"""
        <!-- {work_type} Flow Table -->
        <div class="card">
            <h2 style="border-left: 4px solid {color}; padding-left: 12px;">{work_type} Flow Metrics
                <span style="font-size: 0.85rem; font-weight: 400; color: var(--text-secondary);">
                    — Avg Lead Time: {avg_wt_lead_time:.0f} days | Open: {totals_by_type[work_type]['open']:,} | Closed (90d): {totals_by_type[work_type]['closed']:,}
                </span>
            </h2>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Project</th>
                            <th>Lead Time (P85)</th>
                            <th>Lead Time (Median)</th>
                            <th>Throughput</th>
                            <th>Cycle Time Variance</th>
                            <th>Open</th>
                            <th>Closed (90d)</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
"""

        # Add project rows for this work type
        # First, prepare projects with their status for sorting
        projects_with_status = []
        for project in projects:
            work_type_metrics = project.get("work_type_metrics", {}).get(work_type, {})
            lead_time = work_type_metrics.get("lead_time", {})
            dual_metrics = work_type_metrics.get("dual_metrics", {})
            p85 = lead_time.get("p85") or 0
            p50 = lead_time.get("p50") or 0
            open_count = work_type_metrics.get("open_count", 0)
            closed_count = work_type_metrics.get("closed_count_90d", 0)

            # Extract throughput and cycle time variance
            throughput_data = work_type_metrics.get("throughput", {})
            throughput_per_week = throughput_data.get("per_week", 0) or 0

            cycle_variance_data = work_type_metrics.get("cycle_time_variance", {})
            std_dev_days = cycle_variance_data.get("std_dev_days", 0) or 0
            coefficient_of_variation = cycle_variance_data.get("coefficient_of_variation", 0) or 0

            # Skip if no data for this work type
            if open_count == 0 and closed_count == 0:
                continue

            # Check for cleanup work
            has_cleanup = dual_metrics.get("indicators", {}).get("is_cleanup_effort", False)
            operational_metrics = dual_metrics.get("operational", {}) if has_cleanup else None

            # Determine status (use operational metrics if cleanup is present)
            if has_cleanup and operational_metrics:
                status_p85 = operational_metrics.get("p85") or 0
                status_p50 = operational_metrics.get("p50") or 0
            else:
                status_p85 = p85
                status_p50 = p50

            row_status, status_tooltip, status_priority = calculate_composite_flow_status(
                p85_lead_time=status_p85, p50_lead_time=status_p50
            )

            projects_with_status.append(
                {
                    "project": project,
                    "p85": p85,
                    "p50": p50,
                    "open_count": open_count,
                    "closed_count": closed_count,
                    "throughput_per_week": throughput_per_week,
                    "std_dev_days": std_dev_days,
                    "coefficient_of_variation": coefficient_of_variation,
                    "row_status": row_status,
                    "status_tooltip": status_tooltip,
                    "status_priority": status_priority,
                    "has_cleanup": has_cleanup,
                    "dual_metrics": dual_metrics,
                    "operational_metrics": operational_metrics,
                }
            )

        # Sort by status priority (Red->Amber->Green), then by P85 lead time descending
        projects_with_status.sort(key=lambda x: (x["status_priority"], -x["p85"]))

        # Now render the sorted projects
        for idx, proj_data in enumerate(projects_with_status):
            project = proj_data["project"]
            p85 = proj_data["p85"]
            p50 = proj_data["p50"]
            open_count = proj_data["open_count"]
            closed_count = proj_data["closed_count"]
            throughput_per_week = proj_data["throughput_per_week"]
            std_dev_days = proj_data["std_dev_days"]
            coefficient_of_variation = proj_data["coefficient_of_variation"]
            row_status = proj_data["row_status"]
            status_tooltip = proj_data["status_tooltip"]
            has_cleanup = proj_data["has_cleanup"]
            dual_metrics = proj_data["dual_metrics"]
            operational_metrics = proj_data["operational_metrics"]

            # Main data row - show operational metrics if cleanup detected
            # Prepare context for template
            op_p85 = ""
            op_p50 = ""
            op_closed = ""
            cleanup_closed = ""
            cleanup_pct = 0

            if has_cleanup and operational_metrics:
                # Show operational metrics with cleanup indicator
                op_p85 = f"{operational_metrics.get('p85', 0):.1f}"
                op_p50 = f"{operational_metrics.get('p50', 0):.1f}"
                op_closed = f"{operational_metrics.get('closed_count', 0):,}"
                cleanup_closed = f"{dual_metrics.get('cleanup', {}).get('closed_count', 0):,}"
                cleanup_pct = f"{dual_metrics.get('indicators', {}).get('cleanup_percentage', 0):.0f}"

            html += render_template(
                "dashboards/flow_project_row.html",
                project_name=project['project_name'],
                has_cleanup=has_cleanup and operational_metrics,
                cleanup_pct=cleanup_pct,
                p85=f"{p85:.1f}",
                p50=f"{p50:.1f}",
                op_p85=op_p85,
                op_p50=op_p50,
                closed_count=f"{closed_count:,}",
                throughput_per_week=f"{throughput_per_week:.1f}",
                std_dev_days=f"{std_dev_days:.0f}",
                coefficient_of_variation=f"{coefficient_of_variation:.1f}",
                open_count=f"{open_count:,}",
                op_closed=op_closed,
                cleanup_closed=cleanup_closed,
                status_tooltip=status_tooltip,
                row_status=row_status,
                operational_metrics=operational_metrics
            )

        html += """                </tbody>
                </table>
            </div>
        </div>
"""

    html += f"""
        <!-- Glossary -->
        <div class="glossary">
            <div class="glossary-header" onclick="toggleGlossary()">
                <h3>📖 What These Metrics Mean</h3>
                <span class="glossary-toggle" id="glossary-toggle">▼</span>
            </div>
            <div class="glossary-content" id="glossary-content">
                <div class="glossary-item">
                <div class="glossary-term">Lead Time</div>
                <div class="glossary-definition">
                    The total time from when work is requested until it's completed and delivered.
                    Think of it as "order to delivery" time. Shorter lead times mean faster response to customer needs.
                    <br><strong>Good:</strong> Under 60 days | <strong>Needs attention:</strong> Over 150 days
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">85th Percentile (P85)</div>
                <div class="glossary-definition">
                    A statistical measure showing the value below which 85% of items fall.
                    This gives a realistic picture while filtering out extreme outliers.
                    If P85 is 77 days, it means 85% of work completes in 77 days or less.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Work in Progress (WIP)</div>
                <div class="glossary-definition">
                    The number of work items currently being worked on. High WIP means teams are juggling many tasks at once,
                    which can slow everything down due to context switching. Lower WIP often leads to faster completion times.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Median (P50)</div>
                <div class="glossary-definition">
                    The middle value - half of items complete faster, half slower.
                    Useful for understanding typical performance when P85 includes some very old items.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Throughput</div>
                <div class="glossary-definition">
                    The rate at which work items are completed, measured as items per week.
                    Calculated from items closed in the last 90 days divided by the number of weeks.
                    Higher throughput indicates more work getting done. This is a pure velocity metric.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Cycle Time Variance (CV)</div>
                <div class="glossary-definition">
                    The coefficient of variation measures how consistent your lead times are.
                    It's the standard deviation divided by the mean, expressed as a percentage.
                    <strong>Lower is better</strong> - it means more predictable delivery times.
                    <br><br>
                    Example: If CV is 50%, that means the standard deviation is half the mean.
                    A CV of 100% means the standard deviation equals the mean (high variability).
                    <br><br>
                    High CV suggests inconsistent processes or work item sizes. Low CV indicates
                    more predictable, standardized flow.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Overall Status (Composite Score)</div>
                <div class="glossary-definition">
                    The status indicator for each project is calculated by evaluating flow metrics: how quickly work moves through the system.
                    This gives you a clear view of delivery speed and consistency.
                    <br><br>
                    <strong>Status Determination:</strong>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong style="color: #10b981;">✓ Good:</strong> Both lead time metrics meet target thresholds</li>
                        <li><strong style="color: #f59e0b;">⚠ Caution:</strong> One or more lead time metrics need attention</li>
                        <li><strong style="color: #ef4444;">● Action Needed:</strong> Both lead time metrics miss targets</li>
                    </ul>
                    <br>
                    <strong>Metrics Used for Status:</strong>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong>P85 Lead Time:</strong> Good &lt; 60 days | Caution 60-150 days | Poor &gt; 150 days</li>
                        <li><strong>Median Lead Time:</strong> Good &lt; 30 days | Caution 30-90 days | Poor &gt; 90 days</li>
                    </ul>
                    <br>
                    <strong>Why only lead time metrics?</strong> Open bug count is a backlog/capacity metric, not a flow metric.
                    If bugs sit open for months, that already shows up as poor lead time. This keeps the focus on what matters
                    for flow: how fast work gets done, not how much is waiting. A project with 50 bugs closing in 5 days has
                    better flow than a project with 5 bugs taking 90 days each.
                    <br><br>
                    <strong>Why P85 and Median together?</strong> A project might have good P85 (most bugs close quickly)
                    but poor median (indicating a few very old bugs skewing the distribution), or vice versa.
                    Evaluating both gives you the full picture of flow consistency.
                </div>
            </div>

            <h3 style="margin-top: 30px; color: #dc2626;">⚠ Data Collection Assumptions</h3>

            <div class="glossary-item">
                <div class="glossary-term"><strong>Work Type Segmentation</strong></div>
                <div class="glossary-definition">
                    <strong>Flow metrics are SEGMENTED by work type:</strong> Bug, User Story, and Task tracked separately.
                    This provides visibility into how different types of work flow through your delivery process.
                    Each work type has independent lead time, WIP, and aging metrics.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term"><strong>State Filter - Open Items Only</strong></div>
                <div class="glossary-definition">
                    <strong>Only open items are counted for WIP and aging.</strong>
                    Items in "Closed" or "Removed" states are excluded from open counts.
                    Lead time calculations use items closed within the lookback period.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term"><strong>Time Period</strong></div>
                <div class="glossary-definition">
                    <strong>90-day lookback period</strong> for closed items used in lead time calculations.
                    Open items and WIP counts reflect current state (all open items, regardless of age).
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term"><strong>Historical Data</strong></div>
                <div class="glossary-definition">
                    <strong>Last 12 weeks only</strong> are kept in history for trending charts.
                    Older data is automatically pruned during collection.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term"><strong>Complete Data</strong></div>
                <div class="glossary-definition">
                    <strong>ALL bugs matching the filters are analyzed</strong> - no sampling or arbitrary limits.
                    Data collection processes all open bugs and all closed bugs within the 90-day window.
                </div>
            </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            <p>Director Observatory • Read-Only Metrics • No Enforcement</p>
            <p style="margin-top: 10px;">Data source: Azure DevOps • Updated: {flow_data['week_date']}</p>
        </div>
    </div>

    {framework_js}
    <script>
        // Dashboard-specific JavaScript
        // (Glossary toggle and table scroll are handled by framework)
    </script>
</body>
</html>
"""
    return html


def main():
    print("Flow Dashboard Generator\n")
    print("=" * 60)

    # Load data
    try:
        flow_data = load_flow_data()
        print(f"Loaded flow metrics for Week {flow_data['week_number']} ({flow_data['week_date']})")
    except FileNotFoundError:
        print("[ERROR] No flow metrics found.")
        print("Run: python execution/ado_flow_metrics.py")
        return

    # Generate HTML
    print("Generating dashboard...")
    html = generate_html(flow_data)

    # Save to file
    output_file = ".tmp/observatory/dashboards/flow_dashboard.html"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print("\n[SUCCESS] Dashboard generated!")
    print(f"  Location: {output_file}")
    print(f"  Size: {len(html):,} bytes")
    print(f"\nOpen in browser: start {output_file}")
    print("\nFeatures:")
    print("  ✓ Modern 'mint' design with emerald green accents")
    print("  ✓ Interactive Chart.js visualizations")
    print("  ✓ Plain English explanations for non-technical stakeholders")
    print("  ✓ Self-contained (works offline after first load)")
    print("  ✓ Print-friendly CSS")
    print("  ✓ Glossary of terms included")


if __name__ == "__main__":
    main()
