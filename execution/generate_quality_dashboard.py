#!/usr/bin/env python3
"""
Quality Dashboard Generator

Creates a beautiful, self-contained HTML dashboard for quality metrics.
Uses modern "mint" design with Chart.js for visualizations.
"""

import json
import os
import sys
from datetime import datetime

# Import mobile-responsive framework
try:
    from execution.dashboard_framework import get_dashboard_framework
except ModuleNotFoundError:
    from dashboard_framework import get_dashboard_framework

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


def calculate_composite_status(mttr, median_age):
    """
    Calculate composite quality status based on HARD DATA metrics only.
    Returns tuple: (status_html, tooltip_text, priority)

    Priority is used for sorting: 0 = Action Needed (Red), 1 = Caution (Amber), 2 = Good (Green)

    Status determination:
    - Good: All metrics meet target thresholds
    - Caution: One or more metrics need attention but not critical
    - Action Needed: Multiple metrics miss targets or any critical threshold exceeded

    Thresholds:
    - MTTR: Good < 7 days, Caution 7-14 days, Poor > 14 days
    - Median Bug Age: Good < 30 days, Caution 30-60 days, Poor > 60 days
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


def get_metric_rag_status(metric_name: str, value: float) -> tuple:
    """
    Determine RAG status for a detailed metric.

    Returns: (color_class, color_hex, status_text)

    Thresholds:
    - Bug Age P85: Good < 60, Caution 60-180, Poor > 180 days
    - Bug Age P95: Good < 90, Caution 90-365, Poor > 365 days
    - MTTR P85: Good < 14, Caution 14-30, Poor > 30 days
    - MTTR P95: Good < 21, Caution 21-45, Poor > 45 days
    """
    if value is None:
        return "rag-unknown", "#6b7280", "No Data"

    if metric_name == "Bug Age P85":
        if value < 60:
            return "rag-green", "#10b981", "Good"
        elif value < 180:
            return "rag-amber", "#f59e0b", "Caution"
        else:
            return "rag-red", "#ef4444", "Action Needed"

    elif metric_name == "Bug Age P95":
        if value < 90:
            return "rag-green", "#10b981", "Good"
        elif value < 365:
            return "rag-amber", "#f59e0b", "Caution"
        else:
            return "rag-red", "#ef4444", "Action Needed"

    elif metric_name == "MTTR P85":
        if value < 14:
            return "rag-green", "#10b981", "Good"
        elif value < 30:
            return "rag-amber", "#f59e0b", "Caution"
        else:
            return "rag-red", "#ef4444", "Action Needed"

    elif metric_name == "MTTR P95":
        if value < 21:
            return "rag-green", "#10b981", "Good"
        elif value < 45:
            return "rag-amber", "#f59e0b", "Caution"
        else:
            return "rag-red", "#ef4444", "Action Needed"

    # Default - no RAG status
    return "rag-unknown", "#6b7280", "Unknown"


def get_distribution_bucket_rag_status(bucket_type: str, bucket_name: str) -> tuple:
    """
    Determine RAG status for distribution buckets based on the time range.

    Returns: (color_class, color_hex)

    Logic:
    - Earlier time buckets (faster fixes, newer bugs) are better = Green
    - Middle time buckets = Caution (Amber)
    - Later time buckets (slower fixes, older bugs) = Action Needed (Red)
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


def generate_quality_drilldown_html(project):
    """Generate drill-down detail content HTML for a project"""
    html = '<div class="detail-content">'

    # Section 1: Additional Metrics (P85, P95)
    bug_age = project["bug_age_distribution"]
    mttr_data = project.get("mttr", {})

    if bug_age.get("p85_age_days") or bug_age.get("p95_age_days") or mttr_data.get("p85_mttr_days"):
        html += '<div class="detail-section">'
        html += "<h4>Detailed Metrics</h4>"
        html += '<div class="detail-grid">'

        if bug_age.get("p85_age_days"):
            rag_class, rag_color, rag_status = get_metric_rag_status("Bug Age P85", bug_age["p85_age_days"])
            html += render_template(
                "dashboards/detail_metric.html",
                rag_class=rag_class,
                rag_color=rag_color,
                label="Bug Age P85",
                value=f"{bug_age['p85_age_days']:.1f} days",
                status=rag_status,
            )

        if bug_age.get("p95_age_days"):
            rag_class, rag_color, rag_status = get_metric_rag_status("Bug Age P95", bug_age["p95_age_days"])
            html += render_template(
                "dashboards/detail_metric.html",
                rag_class=rag_class,
                rag_color=rag_color,
                label="Bug Age P95",
                value=f"{bug_age['p95_age_days']:.1f} days",
                status=rag_status,
            )

        if mttr_data.get("p85_mttr_days"):
            rag_class, rag_color, rag_status = get_metric_rag_status("MTTR P85", mttr_data["p85_mttr_days"])
            html += render_template(
                "dashboards/detail_metric.html",
                rag_class=rag_class,
                rag_color=rag_color,
                label="MTTR P85",
                value=f"{mttr_data['p85_mttr_days']:.1f} days",
                status=rag_status,
            )

        if mttr_data.get("p95_mttr_days"):
            rag_class, rag_color, rag_status = get_metric_rag_status("MTTR P95", mttr_data["p95_mttr_days"])
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
        ages_dist = bug_age["ages_distribution"]
        html += '<div class="detail-section">'
        html += "<h4>Bug Age Distribution</h4>"
        html += '<div class="detail-grid">'

        # 0-7 Days
        rag_class, rag_color = get_distribution_bucket_rag_status("bug_age", "0-7_days")
        html += render_template(
            "dashboards/detail_metric.html",
            rag_class=rag_class,
            rag_color=rag_color,
            label="0-7 Days",
            value=f"{ages_dist.get('0-7_days', 0)} bugs",
        )

        # 8-30 Days
        rag_class, rag_color = get_distribution_bucket_rag_status("bug_age", "8-30_days")
        html += render_template(
            "dashboards/detail_metric.html",
            rag_class=rag_class,
            rag_color=rag_color,
            label="8-30 Days",
            value=f"{ages_dist.get('8-30_days', 0)} bugs",
        )

        # 31-90 Days
        rag_class, rag_color = get_distribution_bucket_rag_status("bug_age", "31-90_days")
        html += render_template(
            "dashboards/detail_metric.html",
            rag_class=rag_class,
            rag_color=rag_color,
            label="31-90 Days",
            value=f"{ages_dist.get('31-90_days', 0)} bugs",
        )

        # 90+ Days
        rag_class, rag_color = get_distribution_bucket_rag_status("bug_age", "90+_days")
        html += render_template(
            "dashboards/detail_metric.html",
            rag_class=rag_class,
            rag_color=rag_color,
            label="90+ Days",
            value=f"{ages_dist.get('90+_days', 0)} bugs",
        )

        html += "</div></div>"

    # Section 3: MTTR Distribution
    if mttr_data.get("mttr_distribution"):
        mttr_dist = mttr_data["mttr_distribution"]
        html += '<div class="detail-section">'
        html += "<h4>MTTR Distribution</h4>"
        html += '<div class="detail-grid">'

        # 0-1 Days
        rag_class, rag_color = get_distribution_bucket_rag_status("mttr", "0-1_days")
        html += render_template(
            "dashboards/detail_metric.html",
            rag_class=rag_class,
            rag_color=rag_color,
            label="0-1 Days",
            value=f"{mttr_dist.get('0-1_days', 0)} bugs",
        )

        # 1-7 Days
        rag_class, rag_color = get_distribution_bucket_rag_status("mttr", "1-7_days")
        html += render_template(
            "dashboards/detail_metric.html",
            rag_class=rag_class,
            rag_color=rag_color,
            label="1-7 Days",
            value=f"{mttr_dist.get('1-7_days', 0)} bugs",
        )

        # 7-30 Days
        rag_class, rag_color = get_distribution_bucket_rag_status("mttr", "7-30_days")
        html += render_template(
            "dashboards/detail_metric.html",
            rag_class=rag_class,
            rag_color=rag_color,
            label="7-30 Days",
            value=f"{mttr_dist.get('7-30_days', 0)} bugs",
        )

        # 30+ Days
        rag_class, rag_color = get_distribution_bucket_rag_status("mttr", "30+_days")
        html += render_template(
            "dashboards/detail_metric.html",
            rag_class=rag_class,
            rag_color=rag_color,
            label="30+ Days",
            value=f"{mttr_dist.get('30+_days', 0)} bugs",
        )

        html += "</div></div>"

    # If no data at all
    if not (bug_age.get("ages_distribution") or mttr_data.get("mttr_distribution")):
        html += '<div class="no-data">No detailed metrics available for this project</div>'

    html += "</div>"
    return html


def load_quality_data():
    """Load quality metrics from history file"""
    with open(".tmp/observatory/quality_history.json", encoding="utf-8") as f:
        data = json.load(f)
    return data["weeks"][-1]  # Most recent week


def generate_html(quality_data):
    """Generate self-contained HTML dashboard"""

    # Get mobile-responsive framework
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#8b5cf6",
        header_gradient_end="#7c3aed",
        include_table_scroll=True,
        include_expandable_rows=True,  # Quality dashboard has expandable rows
        include_glossary=True,
    )

    # Extract data for charts - HARD DATA ONLY
    projects = quality_data["projects"]
    project_names = [p["project_name"] for p in projects]
    median_bug_ages = [
        p["bug_age_distribution"]["median_age_days"] if p["bug_age_distribution"]["median_age_days"] else 0
        for p in projects
    ]
    mttr_days = [p.get("mttr", {}).get("mttr_days", 0) if p.get("mttr", {}).get("mttr_days") else 0 for p in projects]

    # Calculate portfolio stats
    total_bugs = sum(p["total_bugs_analyzed"] for p in projects)
    total_open = sum(p["open_bugs_count"] for p in projects)

    # Calculate excluded security bugs (if available)
    total_excluded = sum(p.get("excluded_security_bugs", {}).get("total", 0) for p in projects)
    total_excluded_open = sum(p.get("excluded_security_bugs", {}).get("open", 0) for p in projects)

    # Calculate average MTTR across projects
    mttr_values = [p.get("mttr", {}).get("mttr_days") for p in projects if p.get("mttr", {}).get("mttr_days")]
    avg_mttr = (sum(mttr_values) / len(mttr_values)) if mttr_values else 0

    # Status determination based on MTTR
    if avg_mttr < 7:
        status_color = "#10b981"  # Green
        status_text = "HEALTHY"
    elif avg_mttr < 14:
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
    <title>Quality Dashboard - Week {quality_data['week_number']}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.3.0/dist/chart.umd.min.js"></script>
    {framework_css}
    <style>
        /* Dashboard-specific styles for Quality Dashboard */

        .executive-summary {{
            background: var(--bg-secondary);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px var(--shadow);
            transition: background-color 0.3s ease;
        }}

        @media (min-width: 768px) {{
            .executive-summary {{
                padding: 24px;
                border-radius: 12px;
                margin-bottom: 30px;
            }}
        }}

        .status-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.8rem;
            background: {status_color};
            color: white;
            margin-bottom: 16px;
        }}

        @media (min-width: 768px) {{
            .status-badge {{
                padding: 8px 16px;
                font-size: 0.9rem;
                margin-bottom: 20px;
            }}
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 16px;
            margin-top: 16px;
            align-items: start;
        }}

        .summary-card {{
            background: var(--bg-tertiary);
            padding: 16px;
            border-radius: 8px;
            border-left: 4px solid #8b5cf6;
            transition: background-color 0.3s ease;
        }}

        .summary-card .label {{
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }}

        .summary-card .value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-primary);
            font-variant-numeric: tabular-nums;
        }}

        .summary-card .unit {{
            font-size: 1rem;
            font-weight: 400;
            color: var(--text-secondary);
            margin-left: 4px;
        }}

        .summary-card .explanation {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-top: 8px;
            line-height: 1.4;
        }}

        .card {{
            background: var(--bg-secondary);
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px var(--shadow);
            transition: background-color 0.3s ease;
        }}

        .card h2 {{
            font-size: 1.3rem;
            margin-bottom: 16px;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
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
            color: var(--text-primary);
        }}

        tbody tr:hover {{
            background: var(--bg-tertiary);
        }}

        /* Expandable Row Styles */
        tbody tr.data-row {{
            cursor: pointer;
            transition: background-color 0.2s ease;
        }}

        tbody tr.data-row:hover {{
            background: var(--bg-tertiary);
        }}

        tbody tr.data-row td:first-child {{
            position: relative;
            padding-left: 30px;
        }}

        tbody tr.data-row td:first-child::before {{
            content: '▶';
            position: absolute;
            left: 12px;
            font-size: 0.7rem;
            color: var(--text-secondary);
            transition: transform 0.3s ease;
        }}

        tbody tr.data-row.expanded td:first-child::before {{
            transform: rotate(90deg);
        }}

        tr.detail-row {{
            display: none;
        }}

        tr.detail-row.show {{
            display: table-row;
        }}

        tr.detail-row td {{
            padding: 0;
            border-bottom: 2px solid var(--border-color);
        }}

        .detail-content {{
            padding: 20px;
            background: var(--bg-tertiary);
            animation: slideDown 0.3s ease;
        }}

        @keyframes slideDown {{
            from {{
                opacity: 0;
                max-height: 0;
            }}
            to {{
                opacity: 1;
                max-height: 1000px;
            }}
        }}

        .detail-content h4 {{
            font-size: 1rem;
            margin: 0 0 12px 0;
            color: var(--text-primary);
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
        }}

        .detail-section {{
            margin-bottom: 16px;
        }}

        .detail-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin: 12px 0;
        }}

        .detail-metric {{
            background: var(--bg-secondary);
            padding: 12px;
            border-radius: 6px;
            border-left: 3px solid #8b5cf6;
        }}

        .detail-metric-label {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }}

        .detail-metric-value {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
        }}

        .detail-metric-status {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 6px;
        }}

        .detail-metric.rag-green {{
            background: rgba(16, 185, 129, 0.05);
        }}

        .detail-metric.rag-amber {{
            background: rgba(245, 158, 11, 0.05);
        }}

        .detail-metric.rag-red {{
            background: rgba(239, 68, 68, 0.05);
        }}

        .detail-list {{
            list-style: none;
            padding: 0;
            margin: 8px 0;
        }}

        .detail-list li {{
            padding: 8px;
            background: var(--bg-secondary);
            margin-bottom: 6px;
            border-radius: 4px;
            font-size: 0.85rem;
            border-left: 2px solid #ef4444;
        }}

        .detail-list li .bug-id {{
            font-weight: 600;
            color: #8b5cf6;
            margin-right: 8px;
        }}

        .detail-list li .bug-severity {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.75rem;
            background: #fef3c7;
            color: #92400e;
            margin-left: 8px;
        }}

        .no-data {{
            color: var(--text-secondary);
            font-style: italic;
            font-size: 0.9rem;
        }}

        .glossary {{
            background: var(--bg-tertiary);
            padding: 0;
            border-radius: 12px;
            margin-top: 30px;
            transition: background-color 0.3s ease;
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
                background: white;
            }}
            .card, .executive-summary {{
                box-shadow: none;
                border: 1px solid #e5e7eb;
            }}
        }}
    </style>
</head>
<body>
    <!-- Theme Toggle -->
    <div class="theme-toggle" onclick="toggleTheme()" title="Toggle dark/light mode">
        <span id="theme-icon">🌙</span>
        <span id="theme-label">Dark</span>
    </div>

    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>Quality Dashboard</h1>
            <div class="subtitle">Bug Quality & Fix Effectiveness</div>
            <div class="timestamp">Week {quality_data['week_number']} • {quality_data['week_date']} • Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>

        <!-- Executive Summary -->
        <div class="executive-summary">
            <div class="status-badge">{status_text}</div>
            <h2 style="margin-bottom: 10px;">Executive Summary</h2>
            <p style="color: var(--text-secondary); margin-bottom: 20px;">
                Quality metrics across {len(projects)} projects. These metrics show how effectively we fix bugs and prevent quality issues.
            </p>

            <div class="summary-grid">
                <div class="summary-card">
                    <div class="label">MTTR (Mean Time To Repair)</div>
                    <div class="value">{avg_mttr:.1f}<span class="unit">days</span></div>
                    <div class="explanation">Average time from bug creation to closure</div>
                </div>

                <div class="summary-card" style="border-left-color: #3b82f6;">
                    <div class="label">Total Bugs Analyzed</div>
                    <div class="value">{total_bugs:,}</div>
                    <div class="explanation">Bugs analyzed in last 90 days</div>
                </div>

                <div class="summary-card" style="border-left-color: #f59e0b;">
                    <div class="label">Open Bugs</div>
                    <div class="value">{total_open:,}</div>
                    <div class="explanation">Currently open bugs across all projects</div>
                </div>

                <div class="summary-card" style="border-left-color: #10b981;">
                    <div class="label">Security Bugs Excluded</div>
                    <div class="value">{total_excluded:,}</div>
                    <div class="explanation">ArmorCode bugs excluded to prevent double-counting</div>
                </div>
            </div>
        </div>

        <!-- Project Comparison Table -->
        <div class="card">
            <h2>Project Quality Metrics</h2>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Project</th>
                            <th>MTTR</th>
                            <th>Median Bug Age</th>
                            <th>Open Bugs</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
"""

    # Add project rows with expandable drill-down
    # First, prepare projects with their status for sorting
    projects_with_status = []
    for project in projects:
        median_age = project["bug_age_distribution"]["median_age_days"]
        open_bugs = project["open_bugs_count"]
        mttr = project.get("mttr", {}).get("mttr_days")

        # Determine composite status based on HARD DATA metrics only
        row_status, status_tooltip, status_priority = calculate_composite_status(mttr=mttr, median_age=median_age)

        median_age_str = f"{median_age:.0f} days" if median_age else "N/A"
        mttr_str = f"{mttr:.1f} days" if mttr else "N/A"

        # Generate drill-down content
        drilldown_html = generate_quality_drilldown_html(project)

        projects_with_status.append(
            {
                "project": project,
                "median_age_str": median_age_str,
                "mttr_str": mttr_str,
                "open_bugs": open_bugs,
                "row_status": row_status,
                "status_tooltip": status_tooltip,
                "status_priority": status_priority,
                "drilldown_html": drilldown_html,
            }
        )

    # Sort by status priority (Red->Amber->Green), then by MTTR descending
    projects_with_status.sort(key=lambda x: (x["status_priority"], -x["open_bugs"]))

    # Now render the sorted projects
    for idx, proj_data in enumerate(projects_with_status):
        project = proj_data["project"]
        median_age_str = proj_data["median_age_str"]
        mttr_str = proj_data["mttr_str"]
        open_bugs = proj_data["open_bugs"]
        row_status = proj_data["row_status"]
        status_tooltip = proj_data["status_tooltip"]
        drilldown_html = proj_data["drilldown_html"]

        # Main data row (clickable)
        html += render_template(
            "dashboards/quality_detail_rows.html",
            idx=idx,
            project_name=project["project_name"],
            mttr_str=mttr_str,
            median_age_str=median_age_str,
            open_bugs=open_bugs,
            status_tooltip=status_tooltip,
            row_status=row_status,
            drilldown_html=drilldown_html,
        )

    html += f"""                </tbody>
                </table>
            </div>
        </div>

        <!-- Glossary -->
        <div class="glossary">
            <div class="glossary-header" onclick="toggleGlossary()">
                <h3>📖 What These Metrics Mean</h3>
                <span class="glossary-toggle" id="glossary-toggle">▼</span>
            </div>
            <div class="glossary-content" id="glossary-content">
                <div class="glossary-item">
                <div class="glossary-term">MTTR (Mean Time To Repair)</div>
                <div class="glossary-definition">
                    Average time (in days) from when a bug is created to when it's closed.
                    This measures how quickly your team resolves bugs. Lower MTTR means faster bug resolution.
                    Calculated as: (Bug Closed Date - Bug Created Date) averaged across all closed bugs.
                    <br><strong>Target:</strong> Keep below 7 days for most bugs
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Bug Age (Median)</div>
                <div class="glossary-definition">
                    The middle value of how long bugs stay open before being fixed.
                    Calculated from actual System.CreatedDate → Now for all open bugs.
                    Older bugs suggest capacity constraints or prioritization issues.
                    <br><strong>Target:</strong> Depends on severity - critical bugs should be fixed quickly
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Percentile Metrics (P85, P95)</div>
                <div class="glossary-definition">
                    While median shows the middle value, percentiles reveal how your worst-performing bugs are doing.
                    <strong>P85</strong> means 85% of bugs are at or below this value, while <strong>P95</strong> means 95% are at or below.
                    These metrics help identify tail-end problems that median alone might hide.
                    <br><br>
                    <strong>Bug Age P85:</strong> Shows how long your slowest 15% of bugs have been sitting open.
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong style="color: #10b981;">✓ &lt; 60 days:</strong> Most bugs are being addressed in a reasonable timeframe</li>
                        <li><strong style="color: #f59e0b;">⚠ 60-180 days:</strong> A significant portion of bugs are aging - review prioritization and capacity</li>
                        <li><strong style="color: #ef4444;">● &gt; 180 days:</strong> Many bugs are stale (6+ months) - likely indicates backlog neglect or insufficient capacity</li>
                    </ul>
                    <br>
                    <strong>Bug Age P95:</strong> Reveals your absolute worst-case bug aging - the oldest 5% that need attention.
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong style="color: #10b981;">✓ &lt; 90 days:</strong> Even your oldest bugs are relatively fresh</li>
                        <li><strong style="color: #f59e0b;">⚠ 90-365 days:</strong> Your oldest bugs are approaching or exceeding 1 year - consider triage or closure</li>
                        <li><strong style="color: #ef4444;">● &gt; 365 days:</strong> Significant technical debt accumulation - oldest bugs are ancient and may no longer be relevant</li>
                    </ul>
                    <br>
                    <strong>MTTR P85:</strong> Shows how long it takes to fix your slower-to-resolve bugs (not just the easy ones).
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong style="color: #10b981;">✓ &lt; 14 days:</strong> Most bugs are fixed within 2 weeks - healthy fix velocity</li>
                        <li><strong style="color: #f59e0b;">⚠ 14-30 days:</strong> Slower bugs take 2-4 weeks to fix - may indicate complexity or resource constraints</li>
                        <li><strong style="color: #ef4444;">● &gt; 30 days:</strong> Many bugs take over a month to fix - investigate root causes (complexity, prioritization, capacity)</li>
                    </ul>
                    <br>
                    <strong>MTTR P95:</strong> Captures your most difficult or delayed bug fixes.
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong style="color: #10b981;">✓ &lt; 21 days:</strong> Even complex bugs get resolved within 3 weeks</li>
                        <li><strong style="color: #f59e0b;">⚠ 21-45 days:</strong> Hardest bugs take 3-6 weeks - monitor for patterns (specific areas, types, teams)</li>
                        <li><strong style="color: #ef4444;">● &gt; 45 days:</strong> Worst-case fixes take over 6 weeks - likely indicates systematic issues with complex bugs</li>
                    </ul>
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Distribution Bucket Colors</div>
                <div class="glossary-definition">
                    Both Bug Age and MTTR distribution buckets are color-coded to show which time ranges represent healthy vs. problematic performance.
                    The border color indicates the inherent quality of having bugs in that time bucket.
                    <br><br>
                    <strong>Bug Age Distribution:</strong>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong style="color: #10b981;">Green (0-30 days):</strong> Fresh bugs that are being actively worked - this is healthy</li>
                        <li><strong style="color: #f59e0b;">Amber (31-90 days):</strong> Bugs aging into medium-term backlog - watch for accumulation</li>
                        <li><strong style="color: #ef4444;">Red (90+ days):</strong> Stale bugs accumulating technical debt - these need attention</li>
                    </ul>
                    <strong>What to look for:</strong> You want most bugs in the green buckets. High counts in red buckets (90+ days) indicate backlog accumulation and potential technical debt.
                    <br><br>
                    <strong>MTTR Distribution:</strong>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong style="color: #10b981;">Green (0-7 days):</strong> Fast bug fixes - excellent resolution speed</li>
                        <li><strong style="color: #f59e0b;">Amber (7-30 days):</strong> Moderate fix time - acceptable but watch for trends</li>
                        <li><strong style="color: #ef4444;">Red (30+ days):</strong> Slow fixes - investigate causes (complexity, capacity, prioritization)</li>
                    </ul>
                    <strong>What to look for:</strong> Healthy projects have most bugs in green buckets (quick fixes). High counts in red buckets suggest systematic delays in bug resolution.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Overall Status</div>
                <div class="glossary-definition">
                    The status indicator for each project is calculated by evaluating quality metrics together.
                    <br><br>
                    <strong>Status Determination:</strong>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong style="color: #10b981;">✓ Good:</strong> All metrics meet target thresholds</li>
                        <li><strong style="color: #f59e0b;">⚠ Caution:</strong> One metric needs attention</li>
                        <li><strong style="color: #ef4444;">● Action Needed:</strong> Multiple metrics miss targets</li>
                    </ul>
                    <br>
                    <strong>Thresholds Used:</strong>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong>MTTR:</strong> Good &lt; 7 days | Caution 7-14 days | Poor &gt; 14 days</li>
                        <li><strong>Median Bug Age:</strong> Good &lt; 30 days | Caution 30-60 days | Poor &gt; 60 days</li>
                    </ul>
                </div>
            </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            <p>Director Observatory • Read-Only Metrics • No Enforcement</p>
            <p style="margin-top: 10px;">Data source: Azure DevOps • Updated: {quality_data['week_date']}</p>
        </div>
    </div>

    {framework_js}
    <script>
        // Dashboard-specific JavaScript

        // Chart.js theme configuration
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        const chartColors = {{
            text: isDark ? '#cbd5e1' : '#6b7280',
            grid: isDark ? '#475569' : '#e5e7eb',
            border: isDark ? '#475569' : '#ffffff',
        }};

        Chart.defaults.color = chartColors.text;
        Chart.defaults.borderColor = chartColors.grid;

    </script>
</body>
</html>
"""
    return html


def main():
    print("Quality Dashboard Generator\n")
    print("=" * 60)

    # Load data
    try:
        quality_data = load_quality_data()
        print(f"Loaded quality metrics for Week {quality_data['week_number']} ({quality_data['week_date']})")
    except FileNotFoundError:
        print("[ERROR] No quality metrics found.")
        print("Run: python execution/ado_quality_metrics.py")
        return

    # Generate HTML
    print("Generating dashboard...")
    html = generate_html(quality_data)

    # Save to file
    output_file = ".tmp/observatory/dashboards/quality_dashboard.html"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print("\n[SUCCESS] Dashboard generated!")
    print(f"  Location: {output_file}")
    print(f"  Size: {len(html):,} bytes")
    print(f"\nOpen in browser: start {output_file}")
    print("\nFeatures:")
    print("  ✓ Modern design with purple accents")
    print("  ✓ HARD DATA ONLY - no speculation")
    print("  ✓ MTTR tracking (actual field calculations)")
    print("  ✓ Bug age distribution (actual time open)")
    print("  ✓ Self-contained (works offline)")
    print("  ✓ Print-friendly CSS")
    print("  ✓ Dark/Light mode toggle")


if __name__ == "__main__":
    main()
