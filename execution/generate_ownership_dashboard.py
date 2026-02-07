#!/usr/bin/env python3
"""
Ownership Dashboard Generator

Creates a beautiful, self-contained HTML dashboard for ownership metrics.
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


def calculate_ownership_status(unassigned_pct):
    """
    Calculate ownership status based on unassigned percentage.
    Returns tuple: (status_html, tooltip_text, priority)

    HARD DATA ONLY - Status based solely on unassigned percentage (measurable fact).
    No arbitrary thresholds for classification - just raw percentages.

    Priority is used for sorting: 0 = High (>50%), 1 = Medium (25-50%), 2 = Low (<25%)

    Status determination based on unassigned work percentage:
    - Low Unassigned: < 25% unassigned
    - Medium Unassigned: 25-50% unassigned
    - High Unassigned: > 50% unassigned
    """
    tooltip = f"Unassigned: {unassigned_pct:.1f}%"

    # Determine status based purely on percentage ranges (descriptive, not prescriptive)
    if unassigned_pct > 50:
        status_html = '<span style="color: #ef4444;">● High Unassigned</span>'
        priority = 0
    elif unassigned_pct > 25:
        status_html = '<span style="color: #f59e0b;">⚠ Medium Unassigned</span>'
        priority = 1
    else:
        status_html = '<span style="color: #10b981;">✓ Low Unassigned</span>'
        priority = 2

    return status_html, tooltip, priority


def get_work_type_rag_status(unassigned_pct: float) -> tuple:
    """
    Determine RAG status for work type cards based on unassigned percentage.

    Returns: (color_class, color_hex, status_text)

    Thresholds:
    - Green (Good): < 25% unassigned
    - Amber (Caution): 25-50% unassigned
    - Red (Action Needed): > 50% unassigned
    """
    if unassigned_pct < 25:
        return "rag-green", "#10b981", "Good"
    elif unassigned_pct < 50:
        return "rag-amber", "#f59e0b", "Caution"
    else:
        return "rag-red", "#ef4444", "Action Needed"


def generate_ownership_drilldown_html(project):
    """Generate drill-down detail content HTML for a project"""
    html = '<div class="detail-content">'

    # Section 1: Assignment Distribution (Top Assignees)
    top_assignees = project["assignment_distribution"].get("top_assignees", [])
    load_imbalance = project["assignment_distribution"].get("load_imbalance_ratio")

    if top_assignees:
        # Filter out "Unassigned" from the list
        assigned_only = [(name, count) for name, count in top_assignees if name != "Unassigned"]

        if assigned_only:
            html += '<div class="detail-section">'
            html += "<h4>Work Distribution by Assignee</h4>"
            html += '<div class="detail-grid">'

            for name, count in assigned_only[:8]:  # Show max 8
                html += f"""<div class="detail-metric">
                    <div class="detail-metric-label">{name}</div>
                    <div class="detail-metric-value">{count} items</div>
                </div>"""

            html += "</div>"

            if load_imbalance:
                html += f'<p style="margin-top: 12px; color: #6b7280; font-size: 0.9rem;"><strong>Load Imbalance Ratio:</strong> {load_imbalance:.1f}:1 (max vs min workload)</p>'

            html += "</div>"

    # Section 2: Work Type Breakdown
    work_type_seg = project.get("work_type_segmentation", {})
    if work_type_seg:
        html += '<div class="detail-section">'
        html += "<h4>Ownership by Work Type</h4>"
        html += '<div class="detail-grid">'

        # Show Bug, Story, Task
        for wtype in ["Bug", "User Story", "Task"]:
            if wtype in work_type_seg:
                data = work_type_seg[wtype]
                total = data.get("total", 0)
                unassigned = data.get("unassigned", 0)
                unassigned_pct = data.get("unassigned_pct", 0)

                if total > 0:
                    # Get RAG status for this work type
                    rag_class, rag_color, rag_status = get_work_type_rag_status(unassigned_pct)

                    assigned = total - unassigned
                    html += f"""<div class="detail-metric {rag_class}" style="border-left-color: {rag_color};">
                        <div class="detail-metric-label">{wtype}</div>
                        <div class="detail-metric-value">
                            {total} total<br>
                            <span style="font-size: 0.85rem; color: var(--text-secondary);">{assigned} assigned</span> |
                            <span style="color: {rag_color}; font-size: 0.85rem;">{unassigned} unassigned ({unassigned_pct:.0f}%)</span>
                        </div>
                        <div class="detail-metric-status" style="color: {rag_color};">{rag_status}</div>
                    </div>"""

        html += "</div></div>"

    # Section 3: Area Unassigned Statistics (HARD DATA - NO CLASSIFICATION)
    area_stats = project.get("area_unassigned_stats", {})
    areas = area_stats.get("areas", [])

    if areas:
        html += '<div class="detail-section">'
        html += "<h4>Area Unassigned Statistics</h4>"
        html += '<p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 10px;">Top areas by unassigned percentage (all areas shown, no filtering)</p>'
        html += '<ul class="detail-list">'

        for area in areas[:10]:  # Show top 10 by unassigned %
            area_path = area.get("area_path", "Unknown")
            unassigned_pct = area.get("unassigned_pct", 0)
            total = area.get("total_items", 0)
            unassigned = area.get("unassigned_items", 0)
            html += f"""<li>
                <strong>{area_path}</strong>
                <em>({unassigned_pct:.1f}% unassigned • {unassigned}/{total} items)</em>
            </li>"""

        html += "</ul></div>"

    # If no data at all
    if not (top_assignees or areas):
        html += '<div class="no-data">No detailed metrics available for this project</div>'

    html += "</div>"
    return html


def load_ownership_data():
    """Load ownership metrics from history file"""
    with open(".tmp/observatory/ownership_history.json", encoding="utf-8") as f:
        data = json.load(f)
    return data["weeks"][-1]  # Most recent week


def generate_html(ownership_data):
    """Generate self-contained HTML dashboard"""

    # Extract project data
    projects = ownership_data["projects"]

    # Calculate portfolio stats
    total_unassigned = sum(p["unassigned"]["unassigned_count"] for p in projects)
    total_all_items = sum(p["total_items_analyzed"] for p in projects)
    avg_unassigned_pct = (total_unassigned / total_all_items * 100) if total_all_items > 0 else 0

    # Status determination (HARD DATA ONLY - based on unassigned percentage)
    if avg_unassigned_pct < 10:
        status_color = "#10b981"  # Green
        status_text = "HEALTHY"
    elif avg_unassigned_pct < 25:
        status_color = "#f59e0b"  # Amber
        status_text = "CAUTION"
    else:
        status_color = "#f87171"  # Red
        status_text = "ACTION NEEDED"

    # Get mobile-responsive framework
    framework_css, framework_js = get_dashboard_framework(
        header_gradient_start="#3b82f6",
        header_gradient_end="#2563eb",
        include_table_scroll=True,
        include_expandable_rows=True,
        include_glossary=True,
    )

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ownership Dashboard - Week {ownership_data['week_number']}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.3.0/dist/chart.umd.min.js"></script>
    {framework_css}
    <style>
        /* Dashboard-specific styles */
        .executive-summary {{
            background: var(--bg-secondary);
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 12px var(--shadow);
            transition: background-color 0.3s ease;
        }}

        .status-badge {{
            background: {status_color};
        }}

        .chart-container {{
            position: relative;
            height: 350px;
            margin-bottom: 8px;
        }}

        /* Detail content styles for expandable rows */
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
            border-left: 3px solid #3b82f6;
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
            border-left: 2px solid #3b82f6;
        }}

        .detail-list li .bug-id {{
            font-weight: 600;
            color: #3b82f6;
            margin-right: 8px;
        }}

        .no-data {{
            color: var(--text-secondary);
            font-style: italic;
            font-size: 0.9rem;
        }}

        .clickable-cell {{
            cursor: pointer;
            color: #3b82f6;
            font-weight: 600;
            transition: all 0.2s ease;
            position: relative;
        }}

        .clickable-cell:hover {{
            color: #2563eb;
            background: var(--bg-tertiary);
            transform: translateX(2px);
        }}

        .clickable-cell:hover::after {{
            content: " \u21b3";
            position: absolute;
            margin-left: 5px;
            color: var(--text-secondary);
        }}

        .detail-table {{
            width: 100%;
            margin-top: 10px;
            font-size: 0.85rem;
        }}

        .detail-table th {{
            padding: 8px;
            font-size: 0.75rem;
            background: var(--bg-tertiary);
        }}

        .detail-table td {{
            padding: 8px;
            font-size: 0.85rem;
        }}

        .detail-table tbody tr:hover {{
            background: var(--bg-tertiary);
        }}

        .footer {{
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 0.85rem;
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
            <h1>Ownership Dashboard</h1>
            <div class="subtitle">Work Assignment & Distribution</div>
            <div class="timestamp">Week {ownership_data['week_number']} • {ownership_data['week_date']} • Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>

        <!-- Executive Summary -->
        <div class="executive-summary">
            <div class="status-badge">{status_text}</div>
            <h2 style="margin-bottom: 10px;">Executive Summary</h2>
            <p style="color: var(--text-secondary); margin-bottom: 20px;">
                Ownership metrics across {len(projects)} projects. These metrics show how well work is assigned and distributed across teams.
            </p>

            <div class="summary-grid">
                <div class="summary-card">
                    <div class="label">Unassigned Rate</div>
                    <div class="value">{avg_unassigned_pct:.1f}<span class="unit">%</span></div>
                    <div class="explanation">Percentage of work without an assigned owner</div>
                </div>

                <div class="summary-card" style="border-left-color: #ef4444;">
                    <div class="label">Total Unassigned</div>
                    <div class="value">{total_unassigned:,}<span class="unit">items</span></div>
                    <div class="explanation">Work items that need owners</div>
                </div>

                <div class="summary-card" style="border-left-color: #3b82f6;">
                    <div class="label">Unassigned %</div>
                    <div class="value">{avg_unassigned_pct:.1f}<span class="unit">%</span></div>
                    <div class="explanation">Average across all projects</div>
                </div>

                <div class="summary-card" style="border-left-color: #10b981;">
                    <div class="label">Total Work Items</div>
                    <div class="value">{total_all_items:,}</div>
                    <div class="explanation">All open items analyzed</div>
                </div>
            </div>
        </div>

        <!-- Project Comparison Table -->
        <div class="card">
            <h2>Project Ownership Metrics</h2>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Project</th>
                            <th>Total Items</th>
                            <th>Unassigned</th>
                            <th>Unassigned %</th>
                            <th>Assignees</th>
                            <th>Avg Active Days</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
"""

    # Add project rows with expandable drill-down
    # First, prepare projects with their status for sorting
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

        # Determine status based on ownership metrics (HARD DATA ONLY)
        row_status, status_tooltip, status_priority = calculate_ownership_status(unassigned_pct=unassigned_pct)

        # Generate drill-down content
        drilldown_html = generate_ownership_drilldown_html(project)

        projects_with_status.append(
            {
                "project": project,
                "unassigned_pct": unassigned_pct,
                "unassigned_count": unassigned_count,
                "total": total,
                "assignee_count": assignee_count,
                "avg_active_days": avg_active_days,
                "sample_size": sample_size,
                "row_status": row_status,
                "status_tooltip": status_tooltip,
                "status_priority": status_priority,
                "drilldown_html": drilldown_html,
            }
        )

    # Sort by status priority (Red->Amber->Green), then by unassigned percentage descending
    projects_with_status.sort(key=lambda x: (x["status_priority"], -x["unassigned_pct"]))

    # Now render the sorted projects
    for idx, proj_data in enumerate(projects_with_status):
        project = proj_data["project"]
        unassigned_pct = proj_data["unassigned_pct"]
        unassigned_count = proj_data["unassigned_count"]
        total = proj_data["total"]
        assignee_count = proj_data["assignee_count"]
        avg_active_days = proj_data["avg_active_days"]
        sample_size = proj_data["sample_size"]
        row_status = proj_data["row_status"]
        status_tooltip = proj_data["status_tooltip"]
        drilldown_html = proj_data["drilldown_html"]

        # Format active days display
        if avg_active_days is not None:
            active_days_display = f"{avg_active_days:.1f}"
            active_days_title = f"{sample_size} developers tracked over 90 days"
        else:
            active_days_display = "N/A"
            active_days_title = "No commit data available"

        # Main data row (clickable)
        html += f"""                    <tr class="data-row" onclick="toggleDetail('ownership-detail-{idx}', this)">
                        <td><strong>{project['project_name']}</strong></td>
                        <td>{total:,}</td>
                        <td>{unassigned_count:,}</td>
                        <td>{unassigned_pct:.1f}%</td>
                        <td>{assignee_count}</td>
                        <td title="{active_days_title}">{active_days_display}</td>
                        <td title="{status_tooltip}">{row_status}</td>
                    </tr>
                    <tr class="detail-row" id="ownership-detail-{idx}">
                        <td colspan="7">
                            {drilldown_html}
                        </td>
                    </tr>
"""

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
                <div class="glossary-term">Unassigned Items</div>
                <div class="glossary-definition">
                    Work items without an assigned owner. These are at risk of being forgotten or delayed.
                    Every work item should have a clear owner responsible for moving it forward.
                    <br><strong>Target:</strong> Keep below 10%
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Work Type Status Indicators</div>
                <div class="glossary-definition">
                    Each work type card (Bug, User Story, Task) shows a status indicator based on the percentage of unassigned items.
                    The border color and background tint show at a glance whether ownership is well-distributed or needs attention.
                    <br><br>
                    <strong>Status Based on Unassigned Percentage:</strong>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong style="color: #10b981;">✓ Good (&lt; 25% unassigned):</strong> Most work has clear ownership - healthy assignment pattern</li>
                        <li><strong style="color: #f59e0b;">⚠ Caution (25-50% unassigned):</strong> Significant work lacks ownership - review assignment process and capacity</li>
                        <li><strong style="color: #ef4444;">● Action Needed (&gt; 50% unassigned):</strong> Majority of work is unassigned - immediate attention needed for capacity planning or triage</li>
                    </ul>
                    <strong>What to look for:</strong> Green cards indicate healthy ownership. Red cards suggest that work is piling up without owners, which can lead to delayed delivery and unclear accountability.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Area Unassigned Statistics</div>
                <div class="glossary-definition">
                    Shows unassigned work percentage by area path with no arbitrary classifications.
                    Simply displays which areas have the highest percentage of unassigned work, allowing you to see patterns.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Assignees</div>
                <div class="glossary-definition">
                    Number of unique team members with assigned work in a project.
                    More assignees suggests broader team engagement.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Avg Active Days</div>
                <div class="glossary-definition">
                    The average number of days per developer with commit activity in the last 90 days.
                    This measures developer engagement frequency. Calculated by counting the unique days each developer
                    made commits, then averaging across all developers in the project.
                    <br><br>
                    <strong>Example:</strong> If Developer A committed on 20 unique days and Developer B on 10 unique days,
                    the average is 15 days. Higher values indicate more consistent developer engagement.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Load Imbalance</div>
                <div class="glossary-definition">
                    Ratio of maximum to minimum workload across assignees.
                    High ratios (e.g., 5:1) suggest some team members are overloaded while others are underutilized.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Overall Status</div>
                <div class="glossary-definition">
                    Status is based on unassigned work percentage.
                    <br><br>
                    <strong>Status Categories:</strong>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong style="color: #10b981;">✓ Low Unassigned:</strong> Less than 25% of work unassigned</li>
                        <li><strong style="color: #f59e0b;">⚠ Medium Unassigned:</strong> 25-50% of work unassigned</li>
                        <li><strong style="color: #ef4444;">● High Unassigned:</strong> More than 50% of work unassigned</li>
                    </ul>
                </div>
            </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            <p>Director Observatory • Read-Only Metrics • No Enforcement</p>
            <p style="margin-top: 10px;">Data source: Azure DevOps • Updated: {ownership_data['week_date']}</p>
        </div>
    </div>

    {framework_js}
    <script>
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
    print("Ownership Dashboard Generator\n")
    print("=" * 60)

    # Load data
    try:
        ownership_data = load_ownership_data()
        print(f"Loaded ownership metrics for Week {ownership_data['week_number']} ({ownership_data['week_date']})")
    except FileNotFoundError:
        print("[ERROR] No ownership metrics found.")
        print("Run: python execution/ado_ownership_metrics.py")
        return

    # Generate HTML
    print("Generating dashboard...")
    html = generate_html(ownership_data)

    # Save to file
    output_file = ".tmp/observatory/dashboards/ownership_dashboard.html"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print("\n[SUCCESS] Dashboard generated!")
    print(f"  Location: {output_file}")
    print(f"  Size: {len(html):,} bytes")
    print(f"\nOpen in browser: start {output_file}")
    print("\nFeatures:")
    print("  ✓ Modern design with blue accents")
    print("  ✓ Interactive Chart.js visualizations")
    print("  ✓ Unassigned work tracking")
    print("  ✓ Area unassigned statistics (HARD DATA ONLY)")
    print("  ✓ Self-contained (works offline)")
    print("  ✓ Print-friendly CSS")


if __name__ == "__main__":
    main()
