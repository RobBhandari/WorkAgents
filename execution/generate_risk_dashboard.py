#!/usr/bin/env python3
"""
Delivery Risk Dashboard Generator

Creates a beautiful, self-contained HTML dashboard for delivery risk metrics.
Uses modern "mint" design with Chart.js for visualizations.

Focuses on work item-based risk signals (reopened bugs, change patterns).
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

# Set UTF-8 encoding for Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def calculate_risk_level(commit_count):
    """
    Calculate activity level based on commit count
    Returns tuple: (activity_html, tooltip, priority)
    Priority is used for sorting: 0 = High (More active), 1 = Medium, 2 = Low
    """
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


def generate_risk_drilldown_html(project):
    """Generate drill-down detail content HTML for a project"""
    html = '<div class="detail-content">'

    # Section 1: Code Churn Metrics
    code_churn = project.get('code_churn', {})
    pr_dist = project.get('pr_size_distribution', {})
    repo_count = project.get('repository_count', 0)

    html += '<div class="detail-section">'
    html += '<h4>Code Activity Metrics (Last 90 Days - All Project Activity)</h4>'

    if code_churn.get('total_commits', 0) > 0 or pr_dist.get('total_prs', 0) > 0:
        html += '<div class="detail-grid">'

        if code_churn.get('total_commits', 0) > 0:
            html += f'''<div class="detail-metric">
                <div class="detail-metric-label">Total Commits</div>
                <div class="detail-metric-value">{code_churn['total_commits']}</div>
            </div>'''

            html += f'''<div class="detail-metric">
                <div class="detail-metric-label">Files Changed</div>
                <div class="detail-metric-value">{code_churn.get('total_file_changes', 0)}</div>
            </div>'''

            html += f'''<div class="detail-metric">
                <div class="detail-metric-label">Avg Changes/Commit</div>
                <div class="detail-metric-value">{code_churn.get('avg_changes_per_commit', 0):.1f}</div>
            </div>'''

        if pr_dist.get('total_prs', 0) > 0:
            html += f'''<div class="detail-metric">
                <div class="detail-metric-label">Total PRs</div>
                <div class="detail-metric-value">{pr_dist['total_prs']}</div>
            </div>'''

            html += f'''<div class="detail-metric">
                <div class="detail-metric-label">Small PRs</div>
                <div class="detail-metric-value">{pr_dist.get('small_prs', 0)} ({pr_dist.get('small_pct', 0):.0f}%)</div>
            </div>'''

            html += f'''<div class="detail-metric">
                <div class="detail-metric-label">Large PRs</div>
                <div class="detail-metric-value">{pr_dist.get('large_prs', 0)} ({pr_dist.get('large_pct', 0):.0f}%)</div>
            </div>'''

        html += '</div>'
    else:
        # Show message when no activity data is found
        if repo_count > 0:
            html += f'<p style="color: #6b7280; font-size: 0.9rem;">No commits or PRs found in last 90 days across {repo_count} repositor{"y" if repo_count == 1 else "ies"}.</p>'
        else:
            html += '<p style="color: #6b7280; font-size: 0.9rem;">No repository data available.</p>'

    html += '</div>'

    # Section 3: Hot Paths (High Churn Files)
    hot_paths = code_churn.get('hot_paths', [])
    if hot_paths:
        html += '<div class="detail-section">'
        html += '<h4>Hot Paths (High Churn Files)</h4>'
        html += '<ul class="detail-list">'
        for path_data in hot_paths[:10]:  # Show max 10
            path = path_data.get('path', 'Unknown')
            changes = path_data.get('change_count', 0)
            html += f'''<li>
                <strong>{path}</strong>
                <em>({changes} changes)</em>
            </li>'''
        html += '</ul></div>'

    # Section 4: Repository Info
    if repo_count > 0:
        html += f'<div class="detail-section">'
        html += f'<p style="color: #6b7280; font-size: 0.9rem;"><strong>Repositories:</strong> {repo_count} repos tracked for this project</p>'
        html += '</div>'

    # If no data at all
    if not (code_churn.get('total_commits', 0) > 0 or pr_dist.get('total_prs', 0) > 0):
        html += '<div class="no-data">No detailed metrics available for this project</div>'

    html += '</div>'
    return html


def load_risk_data():
    """Load risk metrics from history file"""
    with open('.tmp/observatory/risk_history.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['weeks'][-1]  # Most recent week


def generate_html(risk_data):
    """Generate self-contained HTML dashboard"""

    # Extract project data
    projects = risk_data['projects']

    # Calculate portfolio stats
    total_commits = sum(p['code_churn']['total_commits'] for p in projects)
    total_files = sum(p['code_churn']['unique_files_touched'] for p in projects)

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

    html = f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Delivery Risk Dashboard - Week {risk_data['week_number']}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.3.0/dist/chart.umd.min.js"></script>
    <style>
        :root {{
            --bg-primary: #f9fafb;
            --bg-secondary: #ffffff;
            --bg-tertiary: #f9fafb;
            --text-primary: #1f2937;
            --text-secondary: #6b7280;
            --border-color: #e5e7eb;
            --shadow: rgba(0,0,0,0.1);
        }}

        [data-theme="dark"] {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #cbd5e1;
            --border-color: #475569;
            --shadow: rgba(0,0,0,0.3);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-primary);
            padding: 20px;
            color: var(--text-primary);
            transition: background-color 0.3s ease, color 0.3s ease;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        .theme-toggle {{
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
            background: var(--bg-secondary);
            border: 2px solid var(--border-color);
            border-radius: 50px;
            padding: 8px 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 1.1rem;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px var(--shadow);
        }}

        .theme-toggle:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 16px var(--shadow);
        }}

        .theme-toggle span {{
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-secondary);
        }}

        .header {{
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
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
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 12px var(--shadow);
            transition: background-color 0.3s ease;
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
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 16px;
            margin-top: 16px;
            align-items: start;
        }}

        .summary-card {{
            background: var(--bg-tertiary);
            padding: 16px;
            border-radius: 8px;
            border-left: 4px solid #f59e0b;
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
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin: 12px 0;
        }}

        .detail-metric {{
            background: var(--bg-secondary);
            padding: 12px;
            border-radius: 6px;
            border-left: 3px solid #f59e0b;
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
            color: #f59e0b;
            margin-right: 8px;
        }}

        .no-data {{
            color: var(--text-secondary);
            font-style: italic;
            font-size: 0.9rem;
        }}

        .alert-box {{
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 16px;
            border-radius: 6px;
            margin: 20px 0;
        }}

        .alert-box .alert-title {{
            font-weight: 600;
            color: #92400e;
            margin-bottom: 8px;
        }}

        .alert-box .alert-message {{
            font-size: 0.9rem;
            color: #78350f;
            line-height: 1.5;
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
            <h1>Delivery Risk Dashboard</h1>
            <div class="subtitle">Change Stability & Risk Signals</div>
            <div class="timestamp">Week {risk_data['week_number']} • {risk_data['week_date']} • Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>

        <!-- Executive Summary -->
        <div class="executive-summary">
            <h2 style="margin-bottom: 10px;">Executive Summary</h2>
            <p style="color: var(--text-secondary); margin-bottom: 20px;">
                Code activity metrics across {len(projects)} projects. All metrics based on actual commit data from Git repositories.
            </p>

            <div class="summary-grid">
                <div class="summary-card">
                    <div class="label">Total Commits</div>
                    <div class="value">{total_commits}</div>
                    <div class="explanation">Commits in last 90 days</div>
                </div>

                <div class="summary-card" style="border-left-color: #3b82f6;">
                    <div class="label">Files Changed</div>
                    <div class="value">{total_files}</div>
                    <div class="explanation">Unique files modified</div>
                </div>

                <div class="summary-card" style="border-left-color: #10b981;">
                    <div class="label">Active Projects</div>
                    <div class="value">{sum(1 for p in projects if p['code_churn']['total_commits'] > 0)}</div>
                    <div class="explanation">Projects with commits (90d)</div>
                </div>

                <div class="summary-card" style="border-left-color: #6b7280;">
                    <div class="label">Data Source</div>
                    <div class="value" style="font-size: 1.2rem;">GIT</div>
                    <div class="explanation">Actual repository data</div>
                </div>
            </div>
        </div>

        <!-- Project Activity Table -->
        <div class="card">
            <h2>Project Activity Summary</h2>
            <table>
                <thead>
                    <tr>
                        <th>Project</th>
                        <th>Commits (90d)</th>
                        <th>Files Changed</th>
                        <th>Single Owner %</th>
                        <th>Coupled Pairs</th>
                        <th>Activity Level</th>
                    </tr>
                </thead>
                <tbody>
'''

    # Add project rows with expandable drill-down
    # First, prepare projects with their activity level for sorting
    projects_with_activity = []
    for project in projects:
        commits = project['code_churn']['total_commits']
        files = project['code_churn']['unique_files_touched']

        # Extract knowledge distribution
        knowledge_dist = project.get('knowledge_distribution', {})
        single_owner_pct = knowledge_dist.get('single_owner_pct', 0) or 0
        total_files_analyzed = knowledge_dist.get('total_files_analyzed', 0)

        # Extract module coupling
        module_coupling = project.get('module_coupling', {})
        total_coupled_pairs = module_coupling.get('total_coupled_pairs', 0)

        # Determine activity level and tooltip
        activity_level, activity_tooltip, activity_priority = calculate_risk_level(commits)

        # Generate drill-down content
        drilldown_html = generate_risk_drilldown_html(project)

        projects_with_activity.append({
            'project': project,
            'commits': commits,
            'files': files,
            'single_owner_pct': single_owner_pct,
            'total_files_analyzed': total_files_analyzed,
            'total_coupled_pairs': total_coupled_pairs,
            'activity_level': activity_level,
            'activity_tooltip': activity_tooltip,
            'activity_priority': activity_priority,
            'drilldown_html': drilldown_html
        })

    # Sort by activity priority (High->Medium->Low), then by commits descending
    projects_with_activity.sort(key=lambda x: (x['activity_priority'], -x['commits']))

    # Now render the sorted projects
    for idx, proj_data in enumerate(projects_with_activity):
        project = proj_data['project']
        commits = proj_data['commits']
        files = proj_data['files']
        single_owner_pct = proj_data['single_owner_pct']
        total_files_analyzed = proj_data['total_files_analyzed']
        total_coupled_pairs = proj_data['total_coupled_pairs']
        activity_level = proj_data['activity_level']
        activity_tooltip = proj_data['activity_tooltip']
        drilldown_html = proj_data['drilldown_html']

        # Format display values
        knowledge_display = f'{single_owner_pct:.1f}%' if single_owner_pct > 0 else 'N/A'
        knowledge_title = f'{total_files_analyzed:,} files analyzed' if total_files_analyzed > 0 else 'No file data'
        coupling_display = f'{total_coupled_pairs:,}' if total_coupled_pairs > 0 else 'N/A'
        coupling_title = 'Files that change together frequently (3+ times)' if total_coupled_pairs > 0 else 'No coupling data'

        # Main data row (clickable)
        html += f'''                    <tr class="data-row" onclick="toggleDetail('risk-detail-{idx}', this)">
                        <td><strong>{project['project_name']}</strong></td>
                        <td>{commits}</td>
                        <td>{files}</td>
                        <td title="{knowledge_title}">{knowledge_display}</td>
                        <td title="{coupling_title}">{coupling_display}</td>
                        <td title="{activity_tooltip}">{activity_level}</td>
                    </tr>
                    <tr class="detail-row" id="risk-detail-{idx}">
                        <td colspan="6">
                            {drilldown_html}
                        </td>
                    </tr>
'''

    html += f'''                </tbody>
            </table>
        </div>
        <!-- Glossary -->
        <div class="glossary">
            <div class="glossary-header" onclick="toggleGlossary()">
                <h3>📖 What These Metrics Mean</h3>
                <span class="glossary-toggle" id="glossary-toggle">▼</span>
            </div>
            <div class="glossary-content" id="glossary-content">
                <div class="glossary-item">
                <div class="glossary-term">Commits</div>
                <div class="glossary-definition">
                    Individual code changes committed to Git repositories. Each commit represents a discrete change to the codebase.
                    <br><strong>What high commit counts mean:</strong> More active development, more features being built, or more bugs being fixed.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Files Changed</div>
                <div class="glossary-definition">
                    Unique files that have been modified at least once in the time period. Calculated by tracking which files
                    appear in commit diffs. This is <strong>actual file change data</strong> from Git repositories.
                    <br><strong>What this tells you:</strong> Scope of changes across the codebase.
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Single Owner % (Knowledge Distribution)</div>
                <div class="glossary-definition">
                    Percentage of files that have been modified by only one developer in the last 90 days.
                    This is a "bus factor" metric - files with only one contributor represent knowledge concentration risk.
                    <br><br>
                    <strong>What this means:</strong>
                    <ul style="margin-top: 8px; padding-left: 20px;">
                        <li><strong>High %:</strong> More files depend on single individuals (higher risk)</li>
                        <li><strong>Low %:</strong> Knowledge is more distributed (lower risk)</li>
                    </ul>
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Coupled Pairs (Module Coupling)</div>
                <div class="glossary-definition">
                    Number of file pairs that have been changed together in commits 3 or more times.
                    Files that change together frequently may indicate tight coupling, shared concerns, or architectural dependencies.
                    <br><br>
                    <strong>What high coupling means:</strong>
                    <ul style="margin-top: 8px; padding-left: 20px;">
                        <li>Changes in one area ripple to other areas</li>
                        <li>Refactoring becomes more complex</li>
                        <li>Testing requires broader scope</li>
                    </ul>
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Code Churn / Hot Paths</div>
                <div class="glossary-definition">
                    Files that are changed most frequently. High churn files are modified repeatedly and may indicate:
                    <ul style="margin-top: 8px; padding-left: 20px;">
                        <li>Core shared code used by many features</li>
                        <li>Unstable requirements or frequent bug fixes</li>
                        <li>Areas needing refactoring or better abstraction</li>
                    </ul>
                    <strong>Data Source:</strong> Actual file paths from Git commit diffs
                </div>
            </div>

            <div class="glossary-item">
                <div class="glossary-term">Activity Level</div>
                <div class="glossary-definition">
                    Classification based on commit count:
                    <ul style="margin-top: 8px; padding-left: 20px;">
                        <li><strong>High Activity:</strong> 100+ commits (very active development)</li>
                        <li><strong>Medium Activity:</strong> 20-99 commits (moderate development)</li>
                        <li><strong>Low Activity:</strong> &lt;20 commits (minimal changes)</li>
                    </ul>
                </div>
            </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            <p>Director Observatory • Read-Only Metrics • No Enforcement</p>
            <p style="margin-top: 10px;">Data source: Azure DevOps • Updated: {risk_data['week_date']}</p>
        </div>
    </div>

    <script>
        // Glossary toggle function
        function toggleGlossary() {{
            const content = document.getElementById('glossary-content');
            const toggle = document.getElementById('glossary-toggle');
            content.classList.toggle('expanded');
            toggle.classList.toggle('expanded');
        }}

        // Expandable row toggle function
        function toggleDetail(detailId, rowElement) {{
            const detailRow = document.getElementById(detailId);
            const isExpanded = detailRow.classList.contains('show');

            if (isExpanded) {{
                detailRow.classList.remove('show');
                rowElement.classList.remove('expanded');
            }} else {{
                detailRow.classList.add('show');
                rowElement.classList.add('expanded');
            }}
        }}

        // Chart.js theme configuration
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        const chartColors = {{
            text: isDark ? '#cbd5e1' : '#6b7280',
            grid: isDark ? '#475569' : '#e5e7eb',
            border: isDark ? '#475569' : '#ffffff',
        }};

        Chart.defaults.color = chartColors.text;
        Chart.defaults.borderColor = chartColors.grid;

        // Theme Toggle Functionality
        function toggleTheme() {{
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);

            updateThemeIcon(newTheme);
        }}

        function updateThemeIcon(theme) {{
            const icon = document.getElementById('theme-icon');
            const label = document.getElementById('theme-label');

            if (theme === 'dark') {{
                icon.textContent = '🌙';
                label.textContent = 'Dark';
            }} else {{
                icon.textContent = '☀️';
                label.textContent = 'Light';
            }}
        }}

        // Load theme preference on page load
        document.addEventListener('DOMContentLoaded', function() {{
            const savedTheme = localStorage.getItem('theme') || 'dark';
            document.documentElement.setAttribute('data-theme', savedTheme);
            updateThemeIcon(savedTheme);
        }});

    </script>
</body>
</html>
'''
    return html


def main():
    print("Delivery Risk Dashboard Generator\n")
    print("=" * 60)

    # Load data
    try:
        risk_data = load_risk_data()
        print(f"Loaded risk metrics for Week {risk_data['week_number']} ({risk_data['week_date']})")
    except FileNotFoundError:
        print("[ERROR] No risk metrics found.")
        print("Run: python execution/ado_risk_metrics.py")
        return

    # Generate HTML
    print("Generating dashboard...")
    html = generate_html(risk_data)

    # Save to file
    output_file = '.tmp/observatory/dashboards/risk_dashboard.html'
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n[SUCCESS] Dashboard generated!")
    print(f"  Location: {output_file}")
    print(f"  Size: {len(html):,} bytes")
    print(f"\nOpen in browser: start {output_file}")
    print("\nFeatures:")
    print("  ✓ Modern design with amber activity theme")
    print("  ✓ Interactive Chart.js visualizations")
    print("  ✓ HARD DATA ONLY - no speculation")
    print("  ✓ Code activity tracking (actual commits)")
    print("  ✓ File change analysis")
    print("  ✓ Self-contained (works offline)")
    print("  ✓ Print-friendly CSS")
    print("  ✓ Dark/Light mode toggle")


if __name__ == "__main__":
    main()
